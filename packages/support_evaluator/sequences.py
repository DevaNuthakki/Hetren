"""Tier 2 recovery sequences: up to two recoveries per episode (evaluator side).

Tier 1 (dataset v2) allows one recovery; tier 2 allows up to two, applied
one at a time, each through a gateway scoped to exactly the proposed call
(``apply_recovery``). ``set_mapping``, ``restore_from_source`` and ``rerun``
are followed by a re-run of the task with the same behaviour; ``reroute`` is
a final outcome fix.

Sequence labels (``label_sequence``) extend the tier 1 run label:

- Every tier 1 label except ``abstain`` with ``no_verified_recovery`` is kept
  (one recovery if one verifies). A persistent tool error still allows only
  ``rerun`` and is never searched further: the error masks what else is wrong.
- Otherwise the label is the shortest verified sequence of two recoveries,
  or ``abstain`` when none verifies. A sequence verifies when the final state
  passes the tier 1 checks (outcome, account record, queue configuration)
  and every regression ticket still routes correctly.
- The first recovery is a world edit (``set_mapping`` or
  ``restore_from_source``) that changes state: a first ``reroute`` is undone
  by any later re-run, and a first ``rerun`` adds nothing because a world
  edit re-runs the task anyway. The second is any candidate recovery on the
  state after the first.
- Ties are broken by (verb 1, verb 2, hash 1, hash 2) in ``RECOVERY_ORDER``.

``search_pairs`` prunes the pair space without changing the label: two world
edits commute (the last re-run decides the outcome), so each such pair is
tried once; pairs whose final directory cannot map the target's reference to
the expected account are skipped; pairs are tried in tie-break order and
the search stops at the first verified one. ``naive_pairs`` tries every pair
and is the test oracle for it.

Episodes (``label_case_tier2``): after a recovery the policy sees the
``compact-evidence-v2`` input (the recovery, the re-run, later probes) and
gives a second recovery or ``no_intervention`` (stop). The probe budget is
shared across the episode. Step 1's probes reduce the label entropy over the
first action; at step 2 the hypotheses still consistent get the same first
recovery (renamed into their own world), are filtered again by the
abstracted post-recovery input, and the probes reduce the entropy over the
second action (``post_recovery_label``), considering first the entities the
recovery and its re-run name.

Hypotheses (``tier2_counterfactuals``) are richer than tier 1's one draw of
every other single variant: every single variant (the case's own included)
in ``TIER2_DRAWS`` random draws, so the same symptom can come from different
partners or targets, and every dataset v3 compound pair, all carrying the
case's distractors. Worlds identical to one already listed are dropped.
Each world is run first, and only those consistent with the run's input
are labelled. The probe menu is adaptive (``adaptive_probe_oracle``):
entities an earlier probe revealed can be probed next, so a fault behind a
failed read or outside the run can still be reached. A case still
undetermined after that is genuinely ambiguous and is kept, flagged.
Partner records are written for one hypothesis per distinct label, chosen
by a seeded hash; the oracle uses every hypothesis.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import partial
import json
import random
import re
import time
from typing import Any

from environments.support.fixtures import SupportEnvironment
from environments.support.generator import generate_world
from environments.support.maintenance import MAINTENANCE_VERB_TOOLS
from packages.action_gateway import GatedTool
from packages.action_space import PROBE_BUDGET, VERBS, Action, probe_gateway, recovery_gateway
from packages.contracts import ContractError, canonical_sha256
from packages.hetren_evidence import compact_evidence
from packages.support_evaluator.cases import COMPOUND_KIND
from packages.support_evaluator.compound import TIER2_COMPOUND_VARIANTS
from packages.support_evaluator.distractors import apply_distractors, inject_planned
from packages.support_evaluator.injectors import INJECTORS, InjectedCase, inject
from packages.support_evaluator.labeler import (
    RECOVERY_ORDER,
    CaseLabel,
    Hypothesis,
    ProbeLabel,
    RunLabel,
    _concrete_probes,
    _label_entropy,
    abstract,
    adaptive_probe_oracle,
    candidate_recoveries,
    label_run,
    outcome_checks,
    regression_holds,
    retry_failed_reads,
    unexplained_absences,
    verify_label,
    withhold_observation,
    world_checks,
)
from packages.support_evaluator.plan import PlannedCase
from packages.support_evaluator.sampling import run_agent_on


TIER2_MAX_RECOVERIES = 2
TIER2_DRAWS = 3
WORLD_EDITS = ("set_mapping", "restore_from_source")
RERUN_AFTER = ("rerun", "set_mapping", "restore_from_source")
STOP = Action("decide", "no_intervention", {}).canonical_payload()
_PLACEHOLDER = re.compile(r"\b[TACQ]#[0-9]+\b")
_DEAD_END = Action("decide", "abstain", {"reason": "no_verified_recovery"}).canonical_payload()


# Applying and verifying recoveries


@dataclass(frozen=True)
class AppliedRecovery:
    action: dict[str, object]
    records: tuple[dict[str, object], ...]
    changed: bool
    rerun: dict[str, Any] | None

    def compact_input(self, probe_records=()) -> dict[str, object]:
        """The ``recoveries`` entry ``compact_evidence`` expects."""
        return {"action": self.action, "records": list(self.records), "rerun": self.rerun,
                "probe_records": list(probe_records)}

    @property
    def failure(self) -> str | None:
        """Why the recovery's tool call failed (for example an unknown ID), or None."""
        for record in self.records:
            if record["stage"] == "authorized" and not record["payload"].get("allowed"):
                return f"denied: {record['payload'].get('reason')}"

            if record["stage"] == "observed" and record["status"] == "failed":
                error = record["payload"]["error"]
                return f"{error['type']}: {error['message']}"

        return None


def apply_recovery(environment: SupportEnvironment, ticket_id: str, behaviour: str, action: dict) -> AppliedRecovery:
    """Apply one recovery in place, through a gateway scoped to exactly that call."""
    parsed = Action(action["action"], action["verb"], action["args"])
    before = environment.state_sha256()
    records: tuple[dict[str, object], ...] = ()

    if parsed.verb != "rerun":
        spec = VERBS[parsed.verb]
        tool = GatedTool(parsed.verb, partial(MAINTENANCE_VERB_TOOLS[parsed.verb], environment),
                         spec.args_schema, spec.description)
        gateway = recovery_gateway([tool], environment.state_sha256, parsed)
        gateway.invoke(parsed.verb, parsed.args)
        records = tuple(r.canonical_payload() for r in gateway.records)

    changed = parsed.verb == "rerun" or environment.state_sha256() != before
    rerun = None

    if changed and parsed.verb in RERUN_AFTER:
        rerun = run_agent_on(environment, ticket_id, behaviour).evidence_payload()

    return AppliedRecovery(parsed.canonical_payload(), records, changed, rerun)


def sequence_verified(environment: SupportEnvironment, case: InjectedCase, behaviour: str) -> bool:
    return all(world_checks(environment, case.truth).values()) and regression_holds(environment.fork(), case, behaviour)


def _order(action: dict) -> tuple:
    return RECOVERY_ORDER[action["verb"]], canonical_sha256(action)


def _pair_key(first: dict, second: dict) -> tuple:
    return RECOVERY_ORDER[first["verb"]], RECOVERY_ORDER[second["verb"]], canonical_sha256(first), canonical_sha256(second)


def _first_steps(single: RunLabel) -> list[dict]:
    return sorted(
        (s.action for s in single.sandboxes if s.changed_state and s.action["verb"] in WORLD_EDITS),
        key=_order,
    )


# Pair search


def naive_pairs(case: InjectedCase, environment: SupportEnvironment, behaviour: str, single: RunLabel) -> list[tuple[dict, dict]]:
    """Every verified pair in tie-break order (the test oracle for ``search_pairs``)."""
    ticket_id = case.truth.target_ticket_id
    found = []

    for first in _first_steps(single):
        post = environment.fork()
        applied = apply_recovery(post, ticket_id, behaviour, first)

        for candidate in candidate_recoveries(post, applied.rerun, ticket_id):
            second = candidate.canonical_payload()
            sandbox = post.fork()

            if apply_recovery(sandbox, ticket_id, behaviour, second).changed and sequence_verified(sandbox, case, behaviour):
                found.append((first, second))

    return sorted(found, key=lambda pair: _pair_key(*pair))


def search_pairs(case: InjectedCase, environment: SupportEnvironment, behaviour: str, single: RunLabel) -> tuple[tuple[dict, dict] | None, int]:
    """The first verified pair in tie-break order, and the number of pairs tried."""
    ticket_id = case.truth.target_ticket_id
    target_ref = environment.get_ticket(ticket_id).customer_ref
    expected = case.truth.expected_account_id
    plans = []

    for first in _first_steps(single):
        post = environment.fork()
        applied = apply_recovery(post, ticket_id, behaviour, first)

        for candidate in candidate_recoveries(post, applied.rerun, ticket_id):
            second = candidate.canonical_payload()

            if second["verb"] in WORLD_EDITS and _order(second) < _order(first):
                continue

            if expected is not None:
                final = post.directory_entry(target_ref)

                if second["verb"] == "set_mapping" and second["args"]["customer_ref"] == target_ref:
                    final = second["args"]["account_id"]

                if final != expected:
                    continue

            plans.append((_pair_key(first, second), first, second, post))

    plans.sort(key=lambda plan: plan[0])
    tried = 0

    for _, first, second, post in plans:
        sandbox = post.fork()

        if not apply_recovery(sandbox, ticket_id, behaviour, second).changed:
            continue

        tried += 1

        if sequence_verified(sandbox, case, behaviour):
            return (first, second), tried

    return None, tried


# Sequence labels


@dataclass(frozen=True)
class SequenceLabel:
    single: RunLabel
    recoveries: tuple[dict[str, object], ...]
    decision: dict[str, object] | None
    rule: str
    pairs_tried: int
    seconds: float = 0.0

    @property
    def first(self) -> dict[str, object]:
        return self.recoveries[0] if self.recoveries else self.decision

    @property
    def targets(self) -> tuple[dict[str, object], ...]:
        """The episode's non-probe targets: recoveries, then ``STOP`` after a single one."""
        if not self.recoveries:
            return (self.decision,)

        return self.recoveries + ((STOP,) if len(self.recoveries) == 1 else ())

    def provenance_payload(self) -> dict[str, object]:
        return {
            "rule": self.rule,
            "recoveries": list(self.recoveries),
            "decision": self.decision,
            "targets": list(self.targets),
            "pairs_tried": self.pairs_tried,
        }


def label_sequence(case: InjectedCase, environment: SupportEnvironment, evidence: dict[str, Any], behaviour: str) -> SequenceLabel:
    started = time.perf_counter()
    single = label_run(case, environment, evidence, behaviour)

    def done(recoveries, decision, rule, tried=0):
        return SequenceLabel(single, tuple(recoveries), decision, rule, tried, time.perf_counter() - started)

    if single.rule != "no_verified_recovery":
        if single.label["action"] == "recover":
            return done([single.label], None, single.rule)

        return done([], single.label, single.rule)

    pair, tried = search_pairs(case, environment, behaviour, single)

    if pair is None:
        return done([], single.label, "no_verified_sequence", tried)

    return done(pair, None, "shortest_verified_sequence", tried)


def post_recovery_label(case: InjectedCase, environment: SupportEnvironment, behaviour: str) -> dict[str, object]:
    """The second action after a first recovery: stop, the smallest verified recovery, or a dead end."""
    if sequence_verified(environment, case, behaviour):
        return STOP

    ticket_id = case.truth.target_ticket_id

    for candidate in sorted(candidate_recoveries(environment, None, ticket_id), key=lambda c: _order(c.canonical_payload())):
        sandbox = environment.fork()

        if apply_recovery(sandbox, ticket_id, behaviour, candidate.canonical_payload()).changed and sequence_verified(sandbox, case, behaviour):
            return candidate.canonical_payload()

    return _DEAD_END


def verify_sequence(
    case: InjectedCase,
    environment: SupportEnvironment,
    evidence: dict[str, Any],
    behaviour: str,
    recoveries: list[dict] | tuple[dict, ...],
    decision: dict | None,
) -> bool:
    """Independently re-check a tier 2 episode's actions against execution.

    ``recoveries`` are the applied recoveries in order; ``decision`` is the
    closing decision, or None when the episode ended at its recovery limit.
    After a recovery only ``no_intervention`` (stop) can close an episode.
    """
    if not recoveries:
        if decision["verb"] == "abstain":
            label = label_sequence(case, environment, evidence, behaviour)
            return label.decision is not None and label.decision["verb"] == "abstain"

        return verify_label(case, environment, evidence, behaviour, decision)

    if len(recoveries) > TIER2_MAX_RECOVERIES or unexplained_absences(evidence):
        return False

    if decision is not None and decision["verb"] != "no_intervention":
        return False

    if all(outcome_checks(environment, case.truth).values()):
        return False

    persistent = any(r["status"] == "failed" for r in retry_failed_reads(environment, evidence))

    if persistent and any(action["verb"] != "rerun" for action in recoveries):
        return False

    sandbox = environment.fork()

    for action in recoveries:
        apply_recovery(sandbox, case.truth.target_ticket_id, behaviour, action)

    return sequence_verified(sandbox, case, behaviour)


# Tier 2 case labels


def _probe_gateway(environment: SupportEnvironment):
    return probe_gateway(
        [
            GatedTool(verb, partial(f, environment), VERBS[verb].args_schema, VERBS[verb].description)
            for verb, f in MAINTENANCE_VERB_TOOLS.items()
        ],
        environment.state_sha256,
    )


def _probe_steps(environment, make_input, probe_actions, final) -> tuple[list[dict], list[dict]]:
    """Steps (input before each probe with that probe, then ``final``) and the probe records.

    Probes run in a fork, as in episodes: a ``retry`` advances tool-error
    counters, which must not reach the state a recovery is applied to.
    """
    gateway = _probe_gateway(environment.fork())
    steps = []

    def records():
        return [r.canonical_payload() for r in gateway.records]

    for action in probe_actions:
        steps.append({"input": make_input(records()), "target": action})
        gateway.invoke(action["verb"], action["args"])

    steps.append({"input": make_input(records()), "target": final})
    return steps, records()


def _with_target(hypothesis: Hypothesis, target: dict) -> Hypothesis:
    return replace(hypothesis, label=replace(hypothesis.label, label=target))


def _translate(action: dict, source, target) -> dict | None:
    """``action`` written in ``source``'s world, renamed into ``target``'s; None if it names an unseen entity."""
    renamed = source.copy().apply(action["args"])

    try:
        args = {
            key: (target.concrete(value) if isinstance(value, str) and value[:2] in ("T#", "A#", "C#", "Q#") else value)
            for key, value in renamed.items()
        }
    except StopIteration:
        return None

    return {**action, "args": args}


@dataclass(frozen=True)
class _Phase2:
    hypothesis: Hypothesis
    applied: AppliedRecovery
    records: list
    abstracted: dict


def _probe_records(hypothesis: Hypothesis, probe_actions: list[dict], cache: dict) -> list[dict]:
    """The records of ``probe_actions`` run in a fork of ``hypothesis``'s world (shared through ``cache``)."""
    key = ("records", hypothesis.key, canonical_sha256(probe_actions))

    if key not in cache:
        gateway = _probe_gateway(hypothesis.environment.fork())

        for action in probe_actions:
            gateway.invoke(action["verb"], action["args"])

        cache[key] = [r.canonical_payload() for r in gateway.records]

    return cache[key]


def _after_first(hypothesis: Hypothesis, records: list[dict], first: dict, behaviour: str, cache: dict) -> _Phase2:
    """Apply ``first`` in ``hypothesis``'s world (after step 1's probe ``records``) and build its step 2 view.

    Probes never change the world, so the post-recovery state and its label
    depend only on the hypothesis and ``first``: ``cache`` shares them across
    the case's episodes (everything that uses the state forks it).
    """
    key = (hypothesis.key, canonical_sha256(first))

    if key not in cache:
        post = hypothesis.environment.fork()
        applied = apply_recovery(post, hypothesis.case.truth.target_ticket_id, behaviour, first)
        cache[key] = post, applied, post_recovery_label(hypothesis.case, post, behaviour)

    post, applied, label = cache[key]
    abstracted, renaming = abstract(compact_evidence(hypothesis.evidence, records, [applied.compact_input()]))
    return _Phase2(
        Hypothesis(hypothesis.key, hypothesis.case, post, hypothesis.evidence, renaming,
                   replace(hypothesis.label, label=label)),
        applied, records, abstracted,
    )


def _episode(actual: Hypothesis, consistent: list[Hypothesis], abstracted: dict, sequence: SequenceLabel,
             behaviour: str, cache: dict) -> tuple[list[dict], list[dict], bool]:
    """Steps, concrete probes and determinedness of one tier 2 episode seen from ``actual``.

    Both phases use the adaptive menu: probes may name entities earlier
    probes revealed, written with each hypothesis's extended renaming.
    """
    initial = _label_entropy(consistent)
    probes, determined, remaining = (
        adaptive_probe_oracle(actual, consistent, abstracted) if initial > 0 else ([], True, consistent)
    )
    probe_actions = _concrete_probes(next(h for h in remaining if h.key == actual.key).renaming, probes)

    if not sequence.recoveries:
        steps, _ = _probe_steps(actual.environment, lambda r: compact_evidence(actual.evidence, r), probe_actions, sequence.decision)
        return steps, probe_actions, determined

    first = sequence.recoveries[0]
    steps, _ = _probe_steps(actual.environment, lambda r: compact_evidence(actual.evidence, r), probe_actions, first)

    mine = _after_first(actual, _probe_records(actual, probe_actions, cache), first, behaviour, cache)
    second = sequence.targets[1]

    if mine.hypothesis.label.label != second:
        raise ContractError(f"{actual.key}: step 2 label {mine.hypothesis.label.label} differs from {second}")

    source = abstract(compact_evidence(actual.evidence, mine.records))[1]
    phase2 = [mine.hypothesis]

    for hypothesis in remaining:
        if hypothesis.key == actual.key:
            continue

        records = _probe_records(hypothesis, _concrete_probes(hypothesis.renaming, probes), cache)
        translated = _translate(first, source, abstract(compact_evidence(hypothesis.evidence, records))[1])

        if translated is None:
            continue

        theirs = _after_first(hypothesis, records, translated, behaviour, cache)

        if theirs.abstracted == mine.abstracted:
            phase2.append(theirs.hypothesis)

    budget = PROBE_BUDGET - len(probe_actions)
    latest = mine.abstracted["recoveries"][-1]
    prefer = tuple(dict.fromkeys(_PLACEHOLDER.findall(json.dumps([latest["action"], latest["rerun"]]))))
    probes2, determined2, remaining2 = (
        adaptive_probe_oracle(mine.hypothesis, phase2, mine.abstracted, budget, prefer)
        if _label_entropy(phase2) > 0 and budget > 0 else ([], _label_entropy(phase2) == 0, phase2)
    )
    probe_actions2 = _concrete_probes(next(h for h in remaining2 if h.key == actual.key).renaming, probes2)
    steps2, _ = _probe_steps(
        mine.hypothesis.environment,
        lambda r: compact_evidence(actual.evidence, mine.records, [mine.applied.compact_input(r)]),
        probe_actions2, second,
    )
    return steps + steps2, probe_actions + probe_actions2, determined and determined2


def _consistent_hypothesis(key, case, behaviour, abstracted):
    """The counterfactual's hypothesis and sequence label if its input matches, else None."""
    environment = SupportEnvironment(case.spec)
    evidence = run_agent_on(environment, case.truth.target_ticket_id, behaviour).evidence_payload()
    other, renaming = abstract(compact_evidence(evidence))

    if other != abstracted:
        return None

    sequence = label_sequence(case, environment, evidence, behaviour)
    return _with_target(Hypothesis(key, case, environment, evidence, renaming, sequence.single), sequence.first), sequence


def tier2_counterfactuals(planned: PlannedCase, actual: InjectedCase) -> list[tuple[str, InjectedCase]]:
    """Counterfactual worlds on the same ticket: single variants in several draws and every v3 compound pair.

    Draw 0 of a single variant uses tier 1's random stream for it; worlds
    identical to the actual world or to an earlier one are dropped.
    """
    world = generate_world(planned.world_seed)
    target = actual.truth.target_ticket_id
    seen = {actual.spec.world_sha256}
    choices = [(kind, variant, TIER2_DRAWS) for kind, (_, variants) in INJECTORS.items() for variant in variants]
    choices += [(COMPOUND_KIND, variant, 1) for variant in TIER2_COMPOUND_VARIANTS]
    worlds = []

    for kind, variant, draws in choices:
        for draw in range(draws):
            suffix = f":{draw}" if draw else ""

            try:
                case = inject(kind, world, random.Random(f"{planned.case_seed}:{kind}:{variant}{suffix}"), variant,
                              forced_ticket=target)
            except ContractError:
                continue

            if case.spec.world_sha256 not in seen:
                seen.add(case.spec.world_sha256)
                worlds.append((f"{kind}/{variant}" + (f"#{draw}" if draw else ""), case))

    return worlds


def _partner_choices(twin_id: str, others: list[Hypothesis], sequences: dict[str, SequenceLabel]) -> list[Hypothesis]:
    """One hypothesis per distinct label (the sequence written with its own placeholders).

    Within a label, the hypothesis with the smallest hash of the twin ID and
    its key is chosen, so no variant is systematically preferred by
    enumeration order; the chosen ones are returned in that hash order.
    """
    def rank(hypothesis: Hypothesis) -> str:
        return canonical_sha256({"twin": twin_id, "counterfactual": hypothesis.key})

    chosen: dict[str, Hypothesis] = {}

    for hypothesis in others:
        label = canonical_sha256(hypothesis.renaming.copy().apply(list(sequences[hypothesis.key].targets)))

        if label not in chosen or rank(hypothesis) < rank(chosen[label]):
            chosen[label] = hypothesis

    return sorted(chosen.values(), key=rank)


def label_case_tier2(planned: PlannedCase, evidence_transform=None) -> CaseLabel:
    """Label one planned case for tier 2: sequence label, two-phase probes, twin group and steps.

    Counterfactuals (``tier2_counterfactuals``) carry the case's distractors;
    they are run first and only those consistent with the run's input are
    labelled. The oracle uses every consistent hypothesis; partner records
    are written for one hypothesis per distinct label (``_partner_choices``).
    """
    if evidence_transform is None and planned.evidence_condition == "withheld":
        evidence_transform = withhold_observation

    started = time.perf_counter()
    actual_case, distractors = inject_planned(planned)
    world = generate_world(planned.world_seed)
    environment = SupportEnvironment(actual_case.spec)
    evidence = run_agent_on(environment, actual_case.truth.target_ticket_id, planned.behaviour).evidence_payload()

    if evidence_transform is not None:
        evidence = evidence_transform(evidence)

    abstracted, renaming = abstract(compact_evidence(evidence))
    sequence = label_sequence(actual_case, environment, evidence, planned.behaviour)

    if distractors:
        base, _ = inject_planned(replace(planned, distractors=0))
        base_environment = SupportEnvironment(base.spec)
        base_evidence = run_agent_on(base_environment, base.truth.target_ticket_id, planned.behaviour).evidence_payload()

        if evidence_transform is not None:
            base_evidence = evidence_transform(base_evidence)

        if label_sequence(base, base_environment, base_evidence, planned.behaviour).targets != sequence.targets:
            raise ContractError("distractors changed the label")
    actual = _with_target(Hypothesis("actual", actual_case, environment, evidence, renaming, sequence.single), sequence.first)
    consistent, sequences = [actual], {"actual": sequence}

    if sequence.single.rule != "unexplained_absence":
        seen = {actual_case.spec.world_sha256}

        for key, case in tier2_counterfactuals(planned, actual_case):
            with_distractors = apply_distractors(world, case, distractors)

            if with_distractors is None or with_distractors.spec.world_sha256 in seen:
                continue

            seen.add(with_distractors.spec.world_sha256)
            found = _consistent_hypothesis(key, with_distractors, planned.behaviour, abstracted)

            if found is not None:
                consistent.append(found[0])
                sequences[key] = found[1]

    initial = _label_entropy(consistent)
    cache: dict = {}
    steps, probe_actions, determined = _episode(actual, consistent, abstracted, sequence, planned.behaviour, cache)
    twin_id = None

    if initial > 0:
        twin_id = "twin-" + canonical_sha256(
            {
                "tier": 2,
                "world": world.world_sha256,
                "ticket": actual_case.truth.target_ticket_id,
                "behaviour": planned.behaviour,
                "evidence": abstracted,
            }
        )[:16]

    partners = []

    if twin_id is not None:
        for hypothesis in _partner_choices(twin_id, consistent[1:], sequences):
            partner_steps, _, _ = _episode(hypothesis, consistent, abstracted, sequences[hypothesis.key], planned.behaviour,
                                           cache)
            partners.append(
                {
                    "counterfactual": hypothesis.key,
                    "truth": hypothesis.case.truth.canonical_payload(),
                    "world_sha256": hypothesis.case.spec.world_sha256,
                    "rule": sequences[hypothesis.key].rule,
                    "steps": partner_steps,
                }
            )

    return CaseLabel(
        planned=planned,
        case=actual_case,
        run_label=sequence.single,
        probe_label=ProbeLabel(
            probes=tuple(probe_actions),
            determined=determined,
            consistent=tuple(h.key for h in consistent),
            initial_label_entropy=initial,
            twin_group_id=twin_id,
        ),
        seconds=time.perf_counter() - started,
        steps=tuple(steps),
        partners=tuple(partners),
        sequence=sequence,
    )


__all__ = [
    "STOP",
    "TIER2_DRAWS",
    "TIER2_MAX_RECOVERIES",
    "AppliedRecovery",
    "SequenceLabel",
    "apply_recovery",
    "label_case_tier2",
    "label_sequence",
    "naive_pairs",
    "post_recovery_label",
    "search_pairs",
    "sequence_verified",
    "tier2_counterfactuals",
    "verify_sequence",
]

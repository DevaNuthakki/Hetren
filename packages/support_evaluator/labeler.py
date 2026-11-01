"""Execution-based labels for Milestone 2 runs (evaluator side).

Run labels, in rule order:

1. ``unexplained_absence``: the evidence has a record gap, an allowed call
   with no attempted or observed stage, a finished call without gateway
   records, or SDK discrepancies -> ``insufficient_evidence`` with codes.
   A failed tool call is an observation, not an absence.
2. ``outcome_correct``: the target ticket is already in the expected queue
   and resolves to the expected account -> ``no_intervention``.
3. ``persistent_tool_error``: a read call that failed because the tool was
   unavailable still fails on the retry probe (run in a fork that copies
   error counters) -> only ``rerun`` is considered. Data errors ("unknown
   account_id") are observations, never retried.
4. Every candidate recovery runs in its own fork. ``set_mapping`` and
   ``restore_from_source`` are followed by re-running the task with the same
   behaviour; ``reroute`` is a final outcome fix; candidates that change
   nothing are discarded. A candidate verifies when the outcome is correct,
   the expected account's record matches its source with a canonical tier,
   the queue configuration matches the routing policy, and every regression
   ticket still routes correctly. ``smallest_verified_change`` picks, in
   order, rerun < reroute < set_mapping < restore_from_source; with nothing
   verified the label is ``abstain`` (``no_verified_recovery``).

Probe labels and twin groups come from simple counterfactual enumeration:
every case kind and variant is injected into the same base world on the
same ticket and run with the same behaviour. Worlds whose compact evidence
is equal up to renaming (``abstract``) are consistent with the run. If they
have different labels they form a twin group. The next probe is chosen by
expected information gain about the label (the planner's entropy, extended
to multi-valued probe outcomes), within the probe budget.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import partial
import json
import random
import re
import time
from typing import Any

from environments.support.fixtures import (
    CANONICAL_TIERS,
    SupportEnvironment,
    derive_routing,
)
from environments.support.generator import generate_world
from environments.support.maintenance import MAINTENANCE_VERB_TOOLS
from packages.action_gateway import GatedTool
from packages.action_space import PROBE_BUDGET, VERBS, Action, probe_gateway
from packages.contracts import ContractError, canonical_sha256
from packages.core.hetren_diagnosis.planner import entropy
from packages.hetren_evidence import compact_evidence
from packages.support_evaluator.cases import CaseTruth
from packages.support_evaluator.injectors import INJECTORS, InjectedCase, inject
from packages.support_evaluator.plan import PlannedCase
from packages.support_evaluator.sampling import run_agent_on


RECOVERY_ORDER = {"rerun": 0, "reroute": 1, "set_mapping": 2, "restore_from_source": 3}
READ_TOOLS = ("read_ticket", "lookup_account")


# Checks against the case truth


def outcome_checks(environment: SupportEnvironment, truth: CaseTruth) -> dict[str, bool]:
    ticket = environment.get_ticket(truth.target_ticket_id)
    checks = {"target_queue": ticket.queue_id == truth.expected_queue_id}

    if truth.expected_account_id is not None:
        checks["target_account"] = (
            environment.directory_entry(ticket.customer_ref) == truth.expected_account_id
        )

    return checks


def world_checks(environment: SupportEnvironment, truth: CaseTruth) -> dict[str, bool]:
    checks = outcome_checks(environment, truth)

    if truth.expected_account_id is not None and truth.expected_account_id in environment.account_ids():
        account = environment.get_account(truth.expected_account_id)
        source = environment.account_source(truth.expected_account_id)
        checks["account_record"] = (
            account.tier in CANONICAL_TIERS
            and (account.tier, account.version, account.updated_at)
            == (source.tier, source.version, source.updated_at)
        )

    queues = tuple(environment.get_queue(queue_id) for queue_id in environment.queue_ids())
    checks["queue_config"] = derive_routing(queues) == environment.routing_policy()
    return checks


def _expected_queue(case: InjectedCase, environment: SupportEnvironment, ticket_id: str) -> str:
    spec = case.spec
    ticket = next(t for t in spec.tickets if t.ticket_id == ticket_id)
    owner = dict(spec.directory)[ticket.customer_ref]
    sources = {s.account_id: s.tier for s in spec.account_sources}
    tier = sources.get(owner) or next(a.tier for a in spec.accounts if a.account_id == owner)
    return environment.routing_policy()[tier]


def regression_holds(environment: SupportEnvironment, case: InjectedCase, behaviour: str) -> bool:
    for ticket_id in case.truth.regression_ticket_ids:
        run_agent_on(environment, ticket_id, behaviour)

        if environment.get_ticket(ticket_id).queue_id != _expected_queue(case, environment, ticket_id):
            return False

    return True


# Evidence inspection


def unexplained_absences(evidence: dict[str, Any]) -> tuple[str, ...]:
    missing: list[str] = []
    records = evidence.get("stage_records") or []

    if [r["sequence"] for r in records] != list(range(len(records))):
        missing.append("stage_record_gap")

    grouped: dict[str, dict[str, dict[str, Any]]] = {}

    for record in records:
        grouped.setdefault(record["invocation_id"], {})[record["stage"]] = record

    for stages in grouped.values():
        authorized = stages.get("authorized")

        if authorized is None or authorized["status"] != "allowed":
            continue

        tool = authorized["tool_name"]

        if "attempted" not in stages:
            missing.append(f"attempted_stage_{tool}")

        if "observed" not in stages:
            missing.append(f"observation_{tool}")

    hooks = (evidence.get("sdk_evidence") or {}).get("hook_events") or []
    finished = [h["fields"]["tool_name"] for h in hooks if h["kind"] == "tool_end"]

    if len(finished) > len(grouped):
        missing.append("tool_records_missing")

    if (evidence.get("sdk_evidence") or {}).get("discrepancies"):
        missing.append("consistent_sdk_evidence")

    return tuple(dict.fromkeys(missing))


UNAVAILABLE_ERROR = "ToolUnavailableError"


def _failed_reads(evidence: dict[str, Any]) -> list[tuple[str, str]]:
    """Read calls that failed because the tool was unavailable.

    Data errors such as "unknown account_id" are observations about the
    world, not outages, so they are never retried.
    """
    failed = []

    for step in compact_evidence(evidence)["steps"]:
        if (
            step["tool"] in READ_TOOLS
            and step["outcome"] == "failed"
            and step["error"]["type"] == UNAVAILABLE_ERROR
        ):
            target = step["args"].get("ticket_id") or step["args"].get("account_id")

            if target is not None and (step["tool"], target) not in failed:
                failed.append((step["tool"], target))

    return failed


def retry_failed_reads(environment: SupportEnvironment, evidence: dict[str, Any]) -> tuple[dict[str, str], ...]:
    results = []

    for tool, target in _failed_reads(evidence):
        observation = MAINTENANCE_VERB_TOOLS["retry"](environment.fork(), tool=tool, target=target)
        results.append({"tool": tool, "target": target, "status": observation["status"]})

    return tuple(results)


# Candidates and sandboxes


def candidate_recoveries(
    environment: SupportEnvironment,
    evidence: dict[str, Any],
    target_ticket_id: str,
) -> list[Action]:
    ticket = environment.get_ticket(target_ticket_id)
    resolved = environment.directory_entry(ticket.customer_ref)
    refs = [ticket.customer_ref]

    if resolved is not None and resolved in environment.account_ids():
        refs.append(environment.get_account(resolved).customer_ref)

    accounts = environment.account_ids()
    candidates = [Action("recover", "rerun", {})]
    candidates += [
        Action("recover", "reroute", {"ticket_id": target_ticket_id, "queue_id": queue_id})
        for queue_id in environment.queue_ids()
        if queue_id != ticket.queue_id
    ]
    candidates += [
        Action("recover", "set_mapping", {"customer_ref": ref, "account_id": account_id})
        for ref in dict.fromkeys(refs)
        for account_id in accounts
        if environment.directory_entry(ref) != account_id
    ]
    candidates += [
        Action("recover", "restore_from_source", {"entity": "account", "id": account_id})
        for account_id in accounts
    ]
    return candidates


@dataclass(frozen=True)
class SandboxResult:
    action: dict[str, object]
    changed_state: bool
    checks: dict[str, bool]
    regression_ok: bool | None
    verified: bool

    def canonical_payload(self) -> dict[str, object]:
        return {
            "action": self.action,
            "changed_state": self.changed_state,
            "checks": self.checks,
            "regression_ok": self.regression_ok,
            "verified": self.verified,
        }


def run_sandbox(
    environment: SupportEnvironment,
    case: InjectedCase,
    behaviour: str,
    action: Action,
) -> SandboxResult:
    sandbox = environment.fork()
    before = sandbox.state_sha256()

    if action.verb == "rerun":
        changed = True
    else:
        MAINTENANCE_VERB_TOOLS[action.verb](sandbox, **action.args)
        changed = sandbox.state_sha256() != before

    if changed and action.verb in ("rerun", "set_mapping", "restore_from_source"):
        run_agent_on(sandbox, case.truth.target_ticket_id, behaviour)

    checks = world_checks(sandbox, case.truth) if changed else {}
    passed = changed and all(checks.values())
    regression = regression_holds(sandbox, case, behaviour) if passed else None

    return SandboxResult(
        action=action.canonical_payload(),
        changed_state=changed,
        checks=checks,
        regression_ok=regression,
        verified=bool(passed and regression),
    )


# Run labels


@dataclass(frozen=True)
class RunLabel:
    label: dict[str, object]
    rule: str
    label_set: tuple[dict[str, object], ...]
    outcome_checks: dict[str, bool]
    missing: tuple[str, ...]
    retry_results: tuple[dict[str, str], ...]
    sandboxes: tuple[SandboxResult, ...]
    seconds: float = 0.0

    @property
    def verb(self) -> str:
        return str(self.label["verb"])

    def provenance_payload(self) -> dict[str, object]:
        return {
            "rule": self.rule,
            "label": self.label,
            "label_set": list(self.label_set),
            "outcome_checks": self.outcome_checks,
            "missing": list(self.missing),
            "retry_results": list(self.retry_results),
            "sandboxes_run": len(self.sandboxes),
            "sandboxes_verified": sum(s.verified for s in self.sandboxes),
            "sandboxes": [s.canonical_payload() for s in self.sandboxes],
        }


def label_run(
    case: InjectedCase,
    environment: SupportEnvironment,
    evidence: dict[str, Any],
    behaviour: str,
) -> RunLabel:
    started = time.perf_counter()

    def done(label, rule, label_set=(), checks=None, missing=(), retries=(), sandboxes=()):
        return RunLabel(
            label=label, rule=rule, label_set=tuple(label_set),
            outcome_checks=checks or {}, missing=tuple(missing), retry_results=tuple(retries),
            sandboxes=tuple(sandboxes), seconds=time.perf_counter() - started,
        )

    missing = unexplained_absences(evidence)

    if missing:
        return done(
            Action("decide", "insufficient_evidence", {"missing": list(missing)}).canonical_payload(),
            "unexplained_absence", missing=missing,
        )

    checks = outcome_checks(environment, case.truth)

    if all(checks.values()):
        return done(Action("decide", "no_intervention", {}).canonical_payload(), "outcome_correct", checks=checks)

    retries = retry_failed_reads(environment, evidence)
    persistent = any(result["status"] == "failed" for result in retries)
    candidates = candidate_recoveries(environment, evidence, case.truth.target_ticket_id)

    if persistent:
        candidates = [action for action in candidates if action.verb == "rerun"]

    sandboxes = [run_sandbox(environment, case, behaviour, action) for action in candidates]
    verified = sorted(
        (s.action for s in sandboxes if s.verified),
        key=lambda action: (RECOVERY_ORDER[action["verb"]], canonical_sha256(action)),
    )

    if verified:
        rule = "persistent_tool_error" if persistent else "smallest_verified_change"
        return done(verified[0], rule, verified, checks, (), retries, sandboxes)

    rule = "persistent_tool_error" if persistent else "no_verified_recovery"
    return done(
        Action("decide", "abstain", {"reason": rule}).canonical_payload(),
        rule, (), checks, (), retries, sandboxes,
    )


def verify_label(
    case: InjectedCase,
    environment: SupportEnvironment,
    evidence: dict[str, Any],
    behaviour: str,
    label: dict[str, object],
) -> bool:
    """Independently re-check a proposed label against execution."""
    action = Action(label["action"], label["verb"], label["args"])
    missing = unexplained_absences(evidence)

    if action.verb == "insufficient_evidence":
        return bool(missing)

    if missing:
        return False

    outcome_ok = all(outcome_checks(environment, case.truth).values())

    if action.verb == "no_intervention":
        return outcome_ok

    if outcome_ok:
        return False

    persistent = any(r["status"] == "failed" for r in retry_failed_reads(environment, evidence))

    if action.kind == "recover":
        if persistent and action.verb != "rerun":
            return False

        return run_sandbox(environment, case, behaviour, action).verified

    if action.verb == "abstain":
        candidates = candidate_recoveries(environment, evidence, case.truth.target_ticket_id)

        if persistent:
            candidates = [c for c in candidates if c.verb == "rerun"]

        return not any(run_sandbox(environment, case, behaviour, c).verified for c in candidates)

    return False


# Renaming-invariant evidence and counterfactuals


_ID = re.compile(r"\b([TACQ])-[0-9A-Z]{3,12}\b")
_TIER = re.compile(r"\b(" + "|".join(CANONICAL_TIERS) + r")\b")
# Free-text labels whose wording follows tier or role (account names, queue
# names such as "Premium desk") would re-reveal identity the renaming removes.
_DROPPED_KEYS = frozenset({"display_name", "region", "name"})

# Timestamps and versions are renamed by value, so probe outcomes compare
# relations (working equals source, one time equals another) rather than
# the random values the generator draws independently of the case kind.
_RELATIONAL_KEYS = {"updated_at": "time", "at": "time", "version": "version"}


@dataclass
class Renaming:
    """Consistent ID -> placeholder mapping, in first-appearance order."""

    names: dict[str, str] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)

    def copy(self) -> "Renaming":
        return Renaming(dict(self.names), dict(self.counts))

    def _name(self, kind: str, value: str) -> str:
        if value not in self.names:
            self.counts[kind] = self.counts.get(kind, 0) + 1
            self.names[value] = f"{kind}#{self.counts[kind]}"

        return self.names[value]

    def text(self, value: str) -> str:
        value = _ID.sub(lambda m: self._name(m.group(1), m.group(0)), value)
        return _TIER.sub(lambda m: self._name("tier", m.group(0)), value)

    def apply(self, value: Any) -> Any:
        if isinstance(value, str):
            return self.text(value)

        if isinstance(value, dict):
            # Canonical tiers are renamed in keys too (e.g. the routing policy),
            # and visited in placeholder order rather than alphabetical order,
            # so neither key names nor the numbering of their values can
            # re-reveal tier identity the renaming removed.
            def order(item):
                key = item[0]
                if key not in CANONICAL_TIERS:
                    return (1, "")
                named = self.names.get(key)
                return (0, named if named is not None else "~")

            result = {}

            for key, item in sorted(value.items(), key=order):
                if key in _DROPPED_KEYS:
                    continue

                renamed = self._name("tier", key) if key in CANONICAL_TIERS else key

                if key in _RELATIONAL_KEYS and isinstance(item, (str, int)) and not isinstance(item, bool):
                    result[renamed] = self._name(_RELATIONAL_KEYS[key], f"{key}:{item}")
                elif key == "description" and isinstance(item, str):
                    # Queue descriptions are reduced to the tier they route;
                    # their wording templates differ per queue.
                    tiers = re.findall(r"(tier#[0-9]+)-tier", self.text(item))
                    result[renamed] = f"routes:{tiers[0]}" if tiers else "routes:none"
                else:
                    result[renamed] = self.apply(item)

            return result

        if isinstance(value, list):
            return [self.apply(item) for item in value]

        return value

    def concrete(self, placeholder: str) -> str:
        return next(value for value, name in self.names.items() if name == placeholder)


def abstract(compact: dict[str, Any]) -> tuple[dict[str, Any], Renaming]:
    renaming = Renaming()
    return renaming.apply(compact), renaming


@dataclass(frozen=True)
class Hypothesis:
    key: str
    case: InjectedCase
    environment: SupportEnvironment
    evidence: dict[str, Any]
    renaming: Renaming
    label: RunLabel

    @property
    def label_key(self) -> str:
        args = self.renaming.copy().apply(self.label.label["args"])
        return canonical_sha256({"verb": self.label.verb, "args": args})


def _hypothesis(key, case, behaviour) -> tuple[Hypothesis, dict[str, Any]]:
    environment = SupportEnvironment(case.spec)
    record = run_agent_on(environment, case.truth.target_ticket_id, behaviour)
    evidence = record.evidence_payload()
    abstracted, renaming = abstract(compact_evidence(evidence))
    label = label_run(case, environment, evidence, behaviour)
    return Hypothesis(key, case, environment, evidence, renaming, label), abstracted


def counterfactuals(planned: PlannedCase, actual: InjectedCase) -> list[tuple[str, InjectedCase]]:
    world = generate_world(planned.world_seed)
    worlds = []

    for kind, (_, variants) in INJECTORS.items():
        for variant in variants:
            if (kind, variant) == (planned.case_kind, planned.case_variant):
                continue

            try:
                case = inject(
                    kind, world, random.Random(f"{planned.case_seed}:{kind}:{variant}"),
                    variant, forced_ticket=actual.truth.target_ticket_id,
                )
            except ContractError:
                continue

            worlds.append((f"{kind}/{variant}", case))

    return worlds


# Probe oracle


def _probe_menu(renaming: Renaming, compact: dict[str, Any]) -> list[tuple[str, dict[str, str]]]:
    """Probes over the run's own entities, written with placeholders."""
    tickets = [n for n in renaming.names.values() if n.startswith("T#")]
    accounts = [n for n in renaming.names.values() if n.startswith("A#")]
    refs = [n for n in renaming.names.values() if n.startswith("C#")]
    queues = [n for n in renaming.names.values() if n.startswith("Q#")]
    # Queue and policy probes come first, so configuration evidence wins
    # ties against account history.
    menu: list[tuple[str, dict[str, str]]] = [("inspect", {"entity": "routing_policy"})]
    menu += [("inspect", {"entity": "queue", "id": queue}) for queue in queues[:2]]

    for ticket in tickets[:1]:
        menu.append(("inspect", {"entity": "ticket", "id": ticket}))

    for ref in refs[:2]:
        menu += [("resolve", {"customer_ref": ref}), ("find_owners", {"customer_ref": ref})]

    for account in accounts[:1]:
        menu += [
            ("inspect", {"entity": "account", "id": account}),
            ("compare_with_source", {"entity": "account", "id": account}),
            ("history", {"entity": "account", "id": account}),
        ]

    for step in compact["steps"]:
        if step["tool"] in READ_TOOLS and step["outcome"] == "failed" and step["error"]["type"] == UNAVAILABLE_ERROR:
            target = next(iter(step["args"].values()))
            menu.append(("retry", {"tool": step["tool"], "target": renaming.copy().text(target)}))

    return list(dict.fromkeys((verb, tuple(sorted(args.items()))) for verb, args in menu))


def _run_probe(hypothesis: Hypothesis, verb: str, args: tuple) -> str:
    concrete = {}

    for key, value in args:
        concrete[key] = (
            hypothesis.renaming.concrete(value) if value[:2] in ("T#", "A#", "C#", "Q#") else value
        )

    try:
        observation = MAINTENANCE_VERB_TOOLS[verb](hypothesis.environment.fork(), **concrete)
    except Exception as exc:
        observation = {"error": str(exc)}

    return canonical_sha256(hypothesis.renaming.copy().apply(observation))


def _label_entropy(hypotheses: list[Hypothesis]) -> float:
    counts: dict[str, int] = {}

    for hypothesis in hypotheses:
        counts[hypothesis.label_key] = counts.get(hypothesis.label_key, 0) + 1

    total = sum(counts.values())
    return entropy({key: count / total for key, count in counts.items()})


@dataclass(frozen=True)
class ProbeLabel:
    probes: tuple[dict[str, object], ...]
    determined: bool
    consistent: tuple[str, ...]
    initial_label_entropy: float
    twin_group_id: str | None


def probe_oracle(actual: Hypothesis, consistent: list[Hypothesis], abstracted: dict[str, Any]) -> tuple[list, bool]:
    remaining = list(consistent)
    menu = _probe_menu(actual.renaming, abstracted)
    chosen: list[tuple[str, tuple]] = []

    while _label_entropy(remaining) > 0 and len(chosen) < PROBE_BUDGET:
        best, best_gain = None, 0.0
        current = _label_entropy(remaining)

        for probe in menu:
            if probe in chosen:
                continue

            outcomes: dict[str, list[Hypothesis]] = {}

            for hypothesis in remaining:
                outcomes.setdefault(_run_probe(hypothesis, *probe), []).append(hypothesis)

            expected = sum(len(group) / len(remaining) * _label_entropy(group) for group in outcomes.values())
            gain = current - expected

            if gain > best_gain + 1e-12:
                best, best_gain = probe, gain

        if best is None:
            break

        chosen.append(best)
        observed = _run_probe(actual, *best)
        remaining = [h for h in remaining if _run_probe(h, *best) == observed]

    return chosen, _label_entropy(remaining) == 0


def withhold_observation(evidence: dict[str, Any]) -> dict[str, Any]:
    """Drop one tool call's attempted and observed records (the second call, or the only one)."""
    withheld = json.loads(json.dumps(evidence))
    invocations = list(dict.fromkeys(r["invocation_id"] for r in withheld["stage_records"]))

    if not invocations:
        return withheld

    target = invocations[1] if len(invocations) > 1 else invocations[0]
    withheld["stage_records"] = [
        r for r in withheld["stage_records"]
        if not (r["invocation_id"] == target and r["stage"] in ("attempted", "observed"))
    ]
    return withheld


@dataclass(frozen=True)
class CaseLabel:
    planned: PlannedCase
    case: InjectedCase
    run_label: RunLabel
    probe_label: ProbeLabel
    seconds: float
    steps: tuple[dict[str, object], ...] = ()
    partners: tuple[dict[str, object], ...] = ()

    def provenance_payload(self) -> dict[str, object]:
        return {
            "record_type": "SupportCaseLabel",
            "schema_version": 1,
            "case_kind": self.case.truth.case_kind,
            "case_variant": self.case.truth.case_variant,
            "behaviour": self.planned.behaviour,
            "run_label": self.run_label.provenance_payload(),
            "probe_label": {
                "probes": list(self.probe_label.probes),
                "determined": self.probe_label.determined,
                "consistent_hypotheses": list(self.probe_label.consistent),
                "initial_label_entropy": self.probe_label.initial_label_entropy,
                "twin_group_id": self.probe_label.twin_group_id,
            },
        }


def _concrete_probes(renaming: Renaming, probes) -> list[dict[str, object]]:
    actions = []

    for verb, args in probes:
        concrete = {
            key: (renaming.concrete(value) if value[:2] in ("T#", "A#", "C#", "Q#") else value)
            for key, value in args
        }
        actions.append(Action("probe", verb, concrete).canonical_payload())

    return actions


def _steps(environment, evidence, probe_actions, final_label) -> list[dict[str, object]]:
    """Training steps: the input before each probe with that probe, then the final label."""
    gateway = probe_gateway(
        [
            GatedTool(verb, partial(f, environment), VERBS[verb].args_schema, VERBS[verb].description)
            for verb, f in MAINTENANCE_VERB_TOOLS.items()
        ],
        environment.state_sha256,
    )
    steps = []

    for action in probe_actions:
        steps.append({"input": compact_evidence(evidence, [r.canonical_payload() for r in gateway.records]),
                      "target": action})
        gateway.invoke(action["verb"], action["args"])

    steps.append({"input": compact_evidence(evidence, [r.canonical_payload() for r in gateway.records]),
                  "target": final_label})
    return steps


def label_case(planned: PlannedCase, evidence_transform=None) -> CaseLabel:
    """Label one planned case: run label, probe label, twin group and steps.

    ``steps`` are the training examples: the compact input before each
    probe paired with that probe, then the input after all probes paired
    with the final label. Withheld-evidence cases get ``withhold_observation``
    unless another transform is given.
    """
    if evidence_transform is None and planned.evidence_condition == "withheld":
        evidence_transform = withhold_observation

    started = time.perf_counter()
    actual_case = inject(
        planned.case_kind, generate_world(planned.world_seed),
        random.Random(planned.case_seed), planned.case_variant,
    )
    environment = SupportEnvironment(actual_case.spec)
    record = run_agent_on(environment, actual_case.truth.target_ticket_id, planned.behaviour)
    evidence = record.evidence_payload()

    if evidence_transform is not None:
        evidence = evidence_transform(evidence)

    abstracted, renaming = abstract(compact_evidence(evidence))
    run_label = label_run(actual_case, environment, evidence, planned.behaviour)
    actual = Hypothesis("actual", actual_case, environment, evidence, renaming, run_label)

    consistent = [actual]

    if run_label.rule != "unexplained_absence":
        for key, case in counterfactuals(planned, actual_case):
            hypothesis, other = _hypothesis(key, case, planned.behaviour)

            if other == abstracted:
                consistent.append(hypothesis)

    initial = _label_entropy(consistent)
    probes, determined = probe_oracle(actual, consistent, abstracted) if initial > 0 else ([], True)
    twin_id = None

    if initial > 0:
        twin_id = "twin-" + canonical_sha256(
            {
                "world": generate_world(planned.world_seed).world_sha256,
                "ticket": actual_case.truth.target_ticket_id,
                "behaviour": planned.behaviour,
                "evidence": abstracted,
            }
        )[:16]

    probe_actions = _concrete_probes(renaming, probes)
    steps = _steps(environment, evidence, probe_actions, run_label.label)
    partners = []

    if twin_id is not None:
        # Counterfactual partners: the other consistent worlds, each with the
        # probe path the oracle takes from its own observations.
        for hypothesis in consistent[1:]:
            partner_probes, _ = probe_oracle(hypothesis, consistent, abstracted)
            partners.append(
                {
                    "counterfactual": hypothesis.key,
                    "truth": hypothesis.case.truth.canonical_payload(),
                    "world_sha256": hypothesis.case.spec.world_sha256,
                    "rule": hypothesis.label.rule,
                    "steps": _steps(
                        hypothesis.environment, hypothesis.evidence,
                        _concrete_probes(hypothesis.renaming, partner_probes), hypothesis.label.label,
                    ),
                }
            )

    return CaseLabel(
        planned=planned,
        case=actual_case,
        run_label=run_label,
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
    )


__all__ = [
    "CaseLabel",
    "ProbeLabel",
    "RECOVERY_ORDER",
    "RunLabel",
    "SandboxResult",
    "abstract",
    "candidate_recoveries",
    "label_case",
    "label_run",
    "outcome_checks",
    "unexplained_absences",
    "verify_label",
    "withhold_observation",
    "world_checks",
]

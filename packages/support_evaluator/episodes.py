"""Run a policy on dataset cases and score its final actions by execution.

A policy is a function from compact evidence (``compact-evidence-v1``) to one
action ``{"action", "verb", "args"}``. ``run_episode`` rebuilds a case's run,
gives the policy the same first input as the dataset's first step, executes
each probe through the probe gateway on a fork of the run's end state
(adding it to the input), and stops at the first decision or recovery, or
when the policy asks for more than ``PROBE_BUDGET`` probes.

``score`` checks the final action with the labeler's ``verify_label`` on the
unprobed end state: a decision must be the right one, and a recovery must be
verified by execution (not necessarily the label's smallest change). A
recovery whose tool call fails (an unknown ticket, queue, account or
customer reference, or any other environment error) is scored wrong in both
tiers, at either step, and the reason is recorded in ``recovery_failures``.

Tier 2 episodes (``max_recoveries`` 2) continue after a first recovery: the
harness applies it through a gateway scoped to exactly that call (and
re-runs the task where the verb calls for it), the policy sees the
``compact-evidence-v2`` input, may probe again on a fork of the new state
(the probe budget is shared), and gives a second recovery or
``no_intervention`` (stop). ``score`` then re-checks the whole sequence with
``verify_sequence``; any other decision after a recovery is scored wrong.
A policy run with ``max_recoveries=1`` on tier 2 (the frozen rules baseline)
ends at its first recovery, which counts as an implicit stop.

Metric definitions here are provisional until task 12 fixes them in
EVAL_PROTOCOL.md.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import partial
import json
from pathlib import Path
from typing import Any, Callable

from environments.support.fixtures import SupportEnvironment
from environments.support.maintenance import MAINTENANCE_VERB_TOOLS
from packages.action_gateway import GatedTool
from packages.action_space import PROBE_BUDGET, VERBS, parse_action, probe_gateway
from packages.contracts import ContractError
from packages.hetren_evidence import compact_evidence
from packages.support_evaluator.cases import COMPOUND_KIND, component_kinds
from packages.support_evaluator.distractors import inject_planned
from packages.support_evaluator.labeler import verify_label, withhold_observation
from packages.support_evaluator.plan import PlannedCase
from packages.support_evaluator.sampling import run_agent_on
from packages.support_evaluator.sequences import STOP, TIER2_MAX_RECOVERIES, apply_recovery, verify_sequence


Policy = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class PreparedCase:
    case_id: str
    planned: PlannedCase
    case: Any
    environment: SupportEnvironment
    evidence: dict[str, Any]
    label: dict[str, Any]
    max_recoveries: int = 1
    targets: tuple[dict[str, Any], ...] = ()  # tier 2: the label's non-probe targets in order


def prepare(visible: dict, evaluator: dict) -> PreparedCase:
    planned = PlannedCase(**evaluator["planned"])
    case, _ = inject_planned(planned)
    environment = SupportEnvironment(case.spec)
    evidence = run_agent_on(environment, case.truth.target_ticket_id, planned.behaviour).evidence_payload()

    if planned.evidence_condition == "withheld":
        evidence = withhold_observation(evidence)

    if compact_evidence(evidence) != visible["steps"][0]["input"]:
        raise ContractError(f"{visible['case_id']}: rebuilt input differs from the dataset")

    targets = tuple(step["target"] for step in visible["steps"] if step["target"]["action"] != "probe")
    max_recoveries = TIER2_MAX_RECOVERIES if evaluator.get("tier", 1) == 2 else 1
    return PreparedCase(visible["case_id"], planned, case, environment, evidence, visible["steps"][-1]["target"],
                        max_recoveries, targets if max_recoveries > 1 else ())


def _probe_gateway(environment: SupportEnvironment):
    return probe_gateway(
        [
            GatedTool(verb, partial(f, environment), VERBS[verb].args_schema, VERBS[verb].description)
            for verb, f in MAINTENANCE_VERB_TOOLS.items()
        ],
        environment.state_sha256,
    )


def run_episode(
    policy: Policy,
    prepared: PreparedCase,
    budget: int = PROBE_BUDGET,
    max_recoveries: int | None = None,
) -> dict[str, Any]:
    limit = prepared.max_recoveries if max_recoveries is None else max_recoveries
    working = prepared.environment.fork()
    gateways = [_probe_gateway(working.fork())]
    applied = []
    probes: list[dict[str, Any]] = []
    recoveries: list[dict[str, Any]] = []

    def records(gateway):
        return [r.canonical_payload() for r in gateway.records]

    def end(final, failure=None):
        return {"final": final, "recoveries": recoveries, "probes": probes, "failure": failure}

    while True:
        compact = compact_evidence(
            prepared.evidence, records(gateways[0]),
            [a.compact_input(records(g)) for a, g in zip(applied, gateways[1:])],
        )

        try:
            action = parse_action(policy(compact)).canonical_payload()
        except Exception as exc:
            return end(None, f"invalid_action:{type(exc).__name__}")

        if action["action"] == "decide":
            return end(action)

        if action["action"] == "recover":
            recoveries.append(action)

            if len(recoveries) == limit:
                return end(action)

            applied.append(apply_recovery(working, prepared.case.truth.target_ticket_id, prepared.planned.behaviour, action))
            gateways.append(_probe_gateway(working.fork()))
            continue

        if len(probes) == budget:
            return end(None, "probe_budget_exceeded")

        probes.append(action)
        gateways[-1].invoke(action["verb"], action["args"])


def recovery_failures(prepared: PreparedCase, recoveries: list[dict[str, Any]]) -> list[dict[str, object]]:
    """Apply the episode's recoveries in order on a fork; every one whose tool call fails."""
    sandbox = prepared.environment.fork()
    failures = []

    for step, action in enumerate(recoveries):
        applied = apply_recovery(sandbox, prepared.case.truth.target_ticket_id, prepared.planned.behaviour, action)

        if applied.failure is not None:
            failures.append({"step": step, "verb": action["verb"], "error": applied.failure})

    return failures


def score(prepared: PreparedCase, episode: dict[str, Any]) -> dict[str, Any]:
    final = episode["final"]
    label = prepared.label
    recoveries = episode.get("recoveries", [])
    correct = False
    row: dict[str, Any] = {}
    failures = recovery_failures(prepared, recoveries)

    if prepared.max_recoveries == 1:
        if final is not None and not failures:
            correct = verify_label(
                prepared.case, prepared.environment, prepared.evidence, prepared.planned.behaviour, final,
            )

        exact = final == label
    else:
        decision = final if final is not None and final["action"] == "decide" else None

        if final is not None and not failures:
            correct = verify_sequence(
                prepared.case, prepared.environment, prepared.evidence, prepared.planned.behaviour,
                recoveries, decision,
            )

        actions = list(recoveries) + (
            [decision] if decision is not None else [STOP] if final is not None and len(recoveries) < TIER2_MAX_RECOVERIES else []
        )
        label = prepared.targets[0]
        exact = actions == list(prepared.targets)
        row = {
            "label_targets": list(prepared.targets),
            "label_recoveries": sum(t["action"] == "recover" for t in prepared.targets),
        }

    return {
        "case_id": prepared.case_id,
        # A compound reads "compound:<kind>+<kind>", so per-family results keep pairs apart.
        "case_kind": (
            f"{COMPOUND_KIND}:" + "+".join(component_kinds(prepared.planned.case_kind, prepared.planned.case_variant))
            if prepared.planned.case_kind == COMPOUND_KIND else prepared.planned.case_kind
        ),
        "case_variant": prepared.planned.case_variant,
        "behaviour": prepared.planned.behaviour,
        "evidence_condition": prepared.planned.evidence_condition,
        "held_out": prepared.case.truth.held_out,
        "tier": 2 if prepared.max_recoveries > 1 else 1,
        "label": label,
        "final": final,
        "recoveries": list(recoveries),
        "failure": episode["failure"],
        "probes": episode["probes"],
        "correct": correct,
        "exact": exact,
        "recovery_failures": failures,
        **row,
    }


def _rate(numerator: int, denominator: int) -> dict[str, object]:
    return {"n": denominator, "k": numerator, "rate": round(numerator / denominator, 4) if denominator else None}


def summarize(rows: list[dict[str, Any]], tags: dict[str, dict] | None = None) -> dict[str, object]:
    """Provisional metrics (task 12 fixes the formulas)."""
    def label_kind(row):
        return row["label"]["action"], row["label"]["verb"]

    def first_action(row):
        # The policy's first non-probe action: in tier 2 a stop after a recovery is not a decision.
        return row["recoveries"][0] if row["recoveries"] else (row["final"] or {})

    recover = [r for r in rows if r["label"]["action"] == "recover"]
    healthy = [r for r in rows if label_kind(r) == ("decide", "no_intervention")]
    result: dict[str, object] = {
        "cases": len(rows),
        "decision_accuracy": _rate(sum(r["correct"] for r in rows), len(rows)),
        "exact_match": _rate(sum(r["exact"] for r in rows), len(rows)),
        "verified_recovery_rate": _rate(
            sum(r["correct"] and bool(r["recoveries"]) for r in recover), len(recover),
        ),
        "wrong_interventions_on_healthy": _rate(
            sum(bool(r["recoveries"]) for r in healthy), len(healthy),
        ),
        "mean_probes": round(sum(len(r["probes"]) for r in rows) / len(rows), 3) if rows else None,
        "mean_probes_on_healthy": round(sum(len(r["probes"]) for r in healthy) / len(healthy), 3) if healthy else None,
        "failures": dict(Counter(r["failure"] for r in rows if r["failure"])),
    }

    for verb in ("insufficient_evidence", "abstain", "no_intervention"):
        truth = [r for r in rows if label_kind(r) == ("decide", verb)]
        chosen = [r for r in rows if first_action(r).get("verb") == verb]
        result[verb] = {
            "recall": _rate(sum(r["correct"] for r in truth), len(truth)),
            "precision": _rate(sum(r["correct"] for r in chosen), len(chosen)),
        }

    tier2 = [r for r in rows if r["tier"] == 2]

    if tier2:
        fixed = [r for r in tier2 if r["label_recoveries"] >= 1]
        two = [r for r in tier2 if r["label_recoveries"] == 2]
        result["sequence"] = {
            "exact_sequence_match": _rate(sum(r["exact"] for r in tier2), len(tier2)),
            "longer_than_label": _rate(
                sum(r["correct"] and len(r["recoveries"]) > r["label_recoveries"] for r in fixed), len(fixed),
            ),
            "stopped_after_one_of_two": _rate(
                sum(len(r["recoveries"]) == 1 and (r["final"] or {}).get("action") in ("decide", "recover") for r in two),
                len(two),
            ),
        }

    by_family = defaultdict(list)

    for row in rows:
        by_family[row["case_kind"]].append(row)

    result["by_family"] = {
        kind: {
            "held_out": group[0]["held_out"],
            "decision_accuracy": _rate(sum(r["correct"] for r in group), len(group)),
            "mean_probes": round(sum(len(r["probes"]) for r in group) / len(group), 3),
        }
        for kind, group in sorted(by_family.items())
    }

    if tags is not None:
        result["slices"] = {
            name: _rate(sum(r["correct"] for r in group), len(group))
            for name, group in (
                ("compound", [r for r in rows if tags[r["case_id"]]["compound"]]),
                ("target_recent_faulty", [r for r in rows if tags[r["case_id"]]["target_recent"] and label_kind(r) != ("decide", "no_intervention")]),
            )
        }

        if tier2:
            # Tier 2: the planned compounds of two faults (``compound`` keeps its tier 1 meaning).
            result["slices"]["compound_pair"] = _rate(
                sum(r["correct"] for r in tier2 if tags[r["case_id"]]["compound_pair"]),
                sum(tags[r["case_id"]]["compound_pair"] for r in tier2),
            )

    return result


def evaluate(
    policy: Policy, dataset_dir: Path, split_file: Path, max_recoveries: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, object]]:
    """Score ``policy`` on a split's primaries; ``max_recoveries=1`` runs a single-recovery policy (rules v1) on tier 2."""
    dataset_dir = Path(dataset_dir)
    members = set(Path(split_file).read_text(encoding="utf-8").split())
    visible = map(json.loads, (dataset_dir / "hetren_visible.jsonl").open(encoding="utf-8"))
    evaluator = map(json.loads, (dataset_dir / "evaluator" / "cases.jsonl").open(encoding="utf-8"))
    tags = {t["case_id"]: t for t in map(json.loads, (dataset_dir / "evaluator" / "tags.jsonl").open(encoding="utf-8"))}
    rows = []

    for v, e in zip(visible, evaluator):
        if v["case_id"] not in members or e["role"] != "primary":
            continue

        prepared = prepare(v, e)
        rows.append(score(prepared, run_episode(policy, prepared, max_recoveries=max_recoveries)))

    return rows, summarize(rows, tags)


__all__ = [
    "Policy",
    "PreparedCase",
    "evaluate",
    "prepare",
    "recovery_failures",
    "run_episode",
    "score",
    "summarize",
]

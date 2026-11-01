"""Run a policy on dataset cases and score its final actions by execution.

A policy is a function from compact evidence (``compact-evidence-v1``) to one
action ``{"action", "verb", "args"}``. ``run_episode`` rebuilds a case's run,
gives the policy the same first input as the dataset's first step, executes
each probe through the probe gateway on a fork of the run's end state
(adding it to the input), and stops at the first decision or recovery, or
when the policy asks for more than ``PROBE_BUDGET`` probes.

``score`` checks the final action with the labeler's ``verify_label`` on the
unprobed end state: a decision must be the right one, and a recovery must be
verified by execution (not necessarily the label's smallest change).

Metric definitions here are provisional until task 12 fixes them in
EVAL_PROTOCOL.md.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import partial
import json
from pathlib import Path
import random
from typing import Any, Callable

from environments.support.fixtures import SupportEnvironment
from environments.support.generator import generate_world
from environments.support.maintenance import MAINTENANCE_VERB_TOOLS
from packages.action_gateway import GatedTool
from packages.action_space import PROBE_BUDGET, VERBS, parse_action, probe_gateway
from packages.contracts import ContractError
from packages.hetren_evidence import compact_evidence
from packages.support_evaluator.cases import HELD_OUT_KINDS
from packages.support_evaluator.injectors import inject
from packages.support_evaluator.labeler import verify_label, withhold_observation
from packages.support_evaluator.plan import PlannedCase
from packages.support_evaluator.sampling import run_agent_on


Policy = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class PreparedCase:
    case_id: str
    planned: PlannedCase
    case: Any
    environment: SupportEnvironment
    evidence: dict[str, Any]
    label: dict[str, Any]


def prepare(visible: dict, evaluator: dict) -> PreparedCase:
    planned = PlannedCase(**evaluator["planned"])
    case = inject(planned.case_kind, generate_world(planned.world_seed), random.Random(planned.case_seed), planned.case_variant)
    environment = SupportEnvironment(case.spec)
    evidence = run_agent_on(environment, case.truth.target_ticket_id, planned.behaviour).evidence_payload()

    if planned.evidence_condition == "withheld":
        evidence = withhold_observation(evidence)

    if compact_evidence(evidence) != visible["steps"][0]["input"]:
        raise ContractError(f"{visible['case_id']}: rebuilt input differs from the dataset")

    return PreparedCase(visible["case_id"], planned, case, environment, evidence, visible["steps"][-1]["target"])


def run_episode(policy: Policy, prepared: PreparedCase, budget: int = PROBE_BUDGET) -> dict[str, Any]:
    probe_env = prepared.environment.fork()
    gateway = probe_gateway(
        [
            GatedTool(verb, partial(f, probe_env), VERBS[verb].args_schema, VERBS[verb].description)
            for verb, f in MAINTENANCE_VERB_TOOLS.items()
        ],
        probe_env.state_sha256,
    )
    probes: list[dict[str, Any]] = []

    while True:
        compact = compact_evidence(prepared.evidence, [r.canonical_payload() for r in gateway.records])

        try:
            action = parse_action(policy(compact)).canonical_payload()
        except Exception as exc:
            return {"final": None, "probes": probes, "failure": f"invalid_action:{type(exc).__name__}"}

        if action["action"] != "probe":
            return {"final": action, "probes": probes, "failure": None}

        if len(probes) == budget:
            return {"final": None, "probes": probes, "failure": "probe_budget_exceeded"}

        probes.append(action)
        gateway.invoke(action["verb"], action["args"])


def score(prepared: PreparedCase, episode: dict[str, Any]) -> dict[str, Any]:
    final = episode["final"]
    label = prepared.label
    correct = False

    if final is not None:
        correct = verify_label(
            prepared.case, prepared.environment, prepared.evidence, prepared.planned.behaviour, final,
        )

    return {
        "case_id": prepared.case_id,
        "case_kind": prepared.planned.case_kind,
        "case_variant": prepared.planned.case_variant,
        "behaviour": prepared.planned.behaviour,
        "evidence_condition": prepared.planned.evidence_condition,
        "held_out": prepared.planned.case_kind in HELD_OUT_KINDS,
        "label": label,
        "final": final,
        "failure": episode["failure"],
        "probes": episode["probes"],
        "correct": correct,
        "exact": final == label,
    }


def _rate(numerator: int, denominator: int) -> dict[str, object]:
    return {"n": denominator, "k": numerator, "rate": round(numerator / denominator, 4) if denominator else None}


def summarize(rows: list[dict[str, Any]], tags: dict[str, dict] | None = None) -> dict[str, object]:
    """Provisional metrics (task 12 fixes the formulas)."""
    def label_kind(row):
        return row["label"]["action"], row["label"]["verb"]

    recover = [r for r in rows if r["label"]["action"] == "recover"]
    healthy = [r for r in rows if label_kind(r) == ("decide", "no_intervention")]
    result: dict[str, object] = {
        "cases": len(rows),
        "decision_accuracy": _rate(sum(r["correct"] for r in rows), len(rows)),
        "exact_match": _rate(sum(r["exact"] for r in rows), len(rows)),
        "verified_recovery_rate": _rate(
            sum(r["correct"] and (r["final"] or {}).get("action") == "recover" for r in recover), len(recover),
        ),
        "wrong_interventions_on_healthy": _rate(
            sum((r["final"] or {}).get("action") == "recover" for r in healthy), len(healthy),
        ),
        "mean_probes": round(sum(len(r["probes"]) for r in rows) / len(rows), 3) if rows else None,
        "mean_probes_on_healthy": round(sum(len(r["probes"]) for r in healthy) / len(healthy), 3) if healthy else None,
        "failures": dict(Counter(r["failure"] for r in rows if r["failure"])),
    }

    for verb in ("insufficient_evidence", "abstain", "no_intervention"):
        truth = [r for r in rows if label_kind(r) == ("decide", verb)]
        chosen = [r for r in rows if (r["final"] or {}).get("verb") == verb]
        result[verb] = {
            "recall": _rate(sum(r["correct"] for r in truth), len(truth)),
            "precision": _rate(sum(r["correct"] for r in chosen), len(chosen)),
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

    return result


def evaluate(policy: Policy, dataset_dir: Path, split_file: Path) -> tuple[list[dict[str, Any]], dict[str, object]]:
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
        rows.append(score(prepared, run_episode(policy, prepared)))

    return rows, summarize(rows, tags)


__all__ = [
    "Policy",
    "PreparedCase",
    "evaluate",
    "prepare",
    "run_episode",
    "score",
    "summarize",
]

"""Label recorded live runs (EVAL_PROTOCOL.md, "Live test split").

Each live run is replayed exactly from its captures on its world, rebuilt
from the evaluator's plan and checked against the exported spec. The final
label always comes from the live run's own evidence and final state.

Recovery verification and probe labels need an agent to re-run. For those,
the labeler uses every scripted behaviour whose compact evidence on the same
world equals the live run's. Categories:

- ``proxy_matched``: at least one behaviour matches and all matching
  behaviours give the same final label and probe sequence;
- ``final_label_only``: otherwise, when the final label needs no re-run
  (unexplained absence -> ``insufficient_evidence``, correct outcome ->
  ``no_intervention``); no probe-sequence label;
- ``excluded``: otherwise; reported separately, never in headline metrics.

Outputs (in the live test directory): ``evaluator/live_labels.jsonl`` and
``hetren_visible.jsonl`` (run ID and steps, the same step format as the
dataset; final-label-only and excluded runs have only the first input).
"""

from __future__ import annotations

from collections import Counter
from functools import partial
import hashlib
import json
import multiprocessing
from pathlib import Path
import random
from typing import Any

from environments.support.fixtures import SupportEnvironment, WorldSpec
from environments.support.generator import generate_world
from environments.support.tools import SUPPORT_TOOL_DESCRIPTIONS, SUPPORT_TOOL_SCHEMAS, SUPPORT_TOOLS
from packages.action_gateway import AllowListPolicy, GatedTool, ToolGateway
from packages.action_space import Action
from packages.contracts import ContractError, canonical_sha256
from packages.hetren_evidence import compact_evidence
from packages.integrations.openai_agents import (
    CaptureStore,
    ReplayModel,
    RunProvenance,
    RunStatus,
    gateway_function_tools,
    run_agent,
)
from packages.support_agent import BEHAVIOURS, LIVE_TEST_MODEL_SETTINGS, build_support_agent, task_message
from packages.support_evaluator.cases import HELD_OUT_KINDS, CaseTruth
from packages.support_evaluator.injectors import inject
from packages.support_evaluator.labeler import (
    Hypothesis,
    _concrete_probes,
    _hypothesis,
    _label_entropy,
    _steps,
    abstract,
    counterfactuals,
    label_run,
    outcome_checks,
    probe_oracle,
    unexplained_absences,
)
from packages.support_evaluator.live import LIVE_MAX_TURNS
from packages.support_evaluator.plan import PlannedCase
from packages.support_evaluator.sampling import run_agent_on


CATEGORIES = ("proxy_matched", "final_label_only", "excluded")
OUTPUT_LIMIT = LIVE_TEST_MODEL_SETTINGS.max_tokens
RE_RUN_RECOVERIES = ("rerun", "set_mapping", "restore_from_source")


def replay_live_run(spec: dict, case_spec: WorldSpec, captures: Path, model_id: str):
    environment = SupportEnvironment(case_spec)
    gateway = ToolGateway(
        tools=[
            GatedTool(name, partial(f, environment), SUPPORT_TOOL_SCHEMAS[name], SUPPORT_TOOL_DESCRIPTIONS[name])
            for name, f in SUPPORT_TOOLS.items()
        ],
        policy=AllowListPolicy(SUPPORT_TOOLS),
        state_sha256=environment.state_sha256,
    )
    model = ReplayModel(store=CaptureStore(captures), source_provenance=RunProvenance.LIVE, source_model_id=model_id)
    record = run_agent(
        agent=build_support_agent(
            environment=environment, tools=gateway_function_tools(gateway),
            model=model, model_settings=LIVE_TEST_MODEL_SETTINGS,
        ),
        task_input=task_message(spec["ticket_id"]), gateway=gateway,
        run_id=spec["run_id"], provenance=RunProvenance.REPLAY, max_turns=LIVE_MAX_TURNS,
    )

    if record.status is RunStatus.ERROR or len(model.used_capture_ids) != len(CaptureStore(captures).captures()):
        raise ContractError(f"{spec['run_id']}: live run does not replay exactly")

    return environment, record


def _proxy_label(planned, case, environment, evidence, abstracted, renaming, behaviour):
    """The labeler's run label and probe label with ``behaviour`` standing in for the live agent."""
    run_label = label_run(case, environment, evidence, behaviour)
    actual = Hypothesis("actual", case, environment, evidence, renaming, run_label)
    consistent = [actual]

    if run_label.rule != "unexplained_absence":
        for key, other_case in counterfactuals(planned, case):
            hypothesis, other = _hypothesis(key, other_case, behaviour)

            if other == abstracted:
                consistent.append(hypothesis)

    initial = _label_entropy(consistent)
    probes, determined = probe_oracle(actual, consistent, abstracted) if initial > 0 else ([], True)
    return {
        "label": run_label.label,
        "rule": run_label.rule,
        "probes": _concrete_probes(renaming, probes),
        "determined": determined,
        "consistent": [h.key for h in consistent],
        "initial_label_entropy": initial,
    }


def label_live_run(live_dir: str, run_id: str, model_id: str) -> dict[str, Any]:
    live_dir = Path(live_dir)
    spec = json.loads((live_dir / "specs" / f"{run_id}.json").read_text(encoding="utf-8"))
    row = next(
        r for r in map(json.loads, (live_dir / "evaluator" / "live_plan.jsonl").open(encoding="utf-8"))
        if r["run_id"] == run_id
    )
    planned = PlannedCase(**row["planned"])
    case = inject(planned.case_kind, generate_world(planned.world_seed), random.Random(planned.case_seed), planned.case_variant)

    if case.spec.canonical_payload() != spec["world"] or case.truth.canonical_payload() != row["truth"]:
        raise ContractError(f"{run_id}: rebuilt case does not match the exported spec")

    captures = live_dir / "captures" / run_id
    environment, record = replay_live_run(spec, case.spec, captures, model_id)
    evidence = record.evidence_payload()
    compact = compact_evidence(evidence)
    abstracted, renaming = abstract(compact)

    matching = []

    for behaviour in BEHAVIOURS:
        scripted_env = SupportEnvironment(case.spec)
        scripted = run_agent_on(scripted_env, spec["ticket_id"], behaviour)

        if compact_evidence(scripted.evidence_payload()) == compact:
            matching.append(behaviour)

    proxies = {b: _proxy_label(planned, case, environment, evidence, abstracted, renaming, b) for b in matching}
    distinct = {canonical_sha256({"label": p["label"], "probes": p["probes"]}) for p in proxies.values()}
    usage = [json.loads(path.read_text(encoding="utf-8"))["response"]["usage"] for path in sorted(captures.glob("capture-*.json"))]
    result: dict[str, Any] = {
        "run_id": run_id,
        "case_kind": planned.case_kind,
        "case_variant": planned.case_variant,
        "held_out": planned.case_kind in HELD_OUT_KINDS,
        "matching_behaviours": matching,
        "proxy_labels_agree": len(distinct) == 1,
        "calls": len(usage),
        "input_tokens": sum(u["input_tokens"] for u in usage),
        "output_tokens": sum(u["output_tokens"] for u in usage),
        "output_limit_calls": sum(u["output_tokens"] >= OUTPUT_LIMIT for u in usage),
        "outcome_checks": outcome_checks(environment, case.truth),
    }

    if matching and len(distinct) == 1:
        proxy = proxies[matching[0]]
        result.update(category="proxy_matched", **proxy)
        steps = _steps(environment, evidence, proxy["probes"], proxy["label"])
    else:
        missing = unexplained_absences(evidence)

        if missing:
            label, rule = Action("decide", "insufficient_evidence", {"missing": list(missing)}).canonical_payload(), "unexplained_absence"
        elif all(result["outcome_checks"].values()):
            label, rule = Action("decide", "no_intervention", {}).canonical_payload(), "outcome_correct"
        else:
            label, rule = None, None

        result.update(
            category="final_label_only" if label is not None else "excluded",
            label=label, rule=rule, probes=None, determined=None, consistent=None, initial_label_entropy=None,
            proxy_candidates={b: p["label"] for b, p in proxies.items()},
        )
        steps = [{"input": compact, "target": label}] if label is not None else [{"input": compact, "target": None}]

    return {"evaluator": result, "visible": {"run_id": run_id, "steps": steps}}


def _line(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"


def label_live(live_dir: Path, *, processes: int = 1, progress: bool = False) -> dict[str, object]:
    live_dir = Path(live_dir)
    ledger = json.loads((live_dir / "captures" / "ledger.json").read_text(encoding="utf-8"))
    run_ids = sorted(ledger["completed"])
    work = partial(label_live_run, str(live_dir), model_id=ledger["model"])
    results = {}

    if processes > 1:
        with multiprocessing.get_context("spawn").Pool(processes) as pool:
            for result in pool.imap_unordered(work, run_ids):
                results[result["evaluator"]["run_id"]] = result

                if progress:
                    print(f"labelled {len(results)}/{len(run_ids)}", flush=True)
    else:
        results = {run_id: work(run_id) for run_id in run_ids}

    evaluator = "".join(_line(results[r]["evaluator"]) for r in run_ids)
    visible = "".join(_line(results[r]["visible"]) for r in run_ids)
    (live_dir / "evaluator" / "live_labels.jsonl").write_text(evaluator, encoding="utf-8")
    (live_dir / "hetren_visible.jsonl").write_text(visible, encoding="utf-8")
    return {
        "runs": len(run_ids),
        "files": {
            "evaluator/live_labels.jsonl": hashlib.sha256(evaluator.encode("utf-8")).hexdigest(),
            "hetren_visible.jsonl": hashlib.sha256(visible.encode("utf-8")).hexdigest(),
        },
        "categories": dict(Counter(results[r]["evaluator"]["category"] for r in run_ids)),
    }


def confirmation_runs(labels: list[dict]) -> list[dict]:
    """Proxy-matched recovery labels whose confirmation re-runs the live agent."""
    return [
        row for row in labels
        if row["category"] == "proxy_matched"
        and row["label"]["action"] == "recover"
        and row["label"]["verb"] in RE_RUN_RECOVERIES
    ]


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Label recorded live test runs.")
    parser.add_argument("--live-dir", required=True, type=Path)
    parser.add_argument("--processes", type=int, default=1)
    args = parser.parse_args(argv)
    print(json.dumps(label_live(args.live_dir, processes=args.processes, progress=True), indent=2, sort_keys=True))
    return 0


__all__ = [
    "CATEGORIES",
    "OUTPUT_LIMIT",
    "confirmation_runs",
    "label_live",
    "label_live_run",
    "replay_live_run",
]


if __name__ == "__main__":
    raise SystemExit(main())

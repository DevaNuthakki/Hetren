"""The CLI accepts every recorded run of the support workflow and gives the model the input it was trained on.

Runs: the committed Milestone 1 live captures replayed through the support agent (clean and with the mapping
swap), and scripted runs of every case kind and behaviour in a cross plan (denied, failed and malformed calls
included). For each, the CLI's input equals ``compact_evidence`` of the run record, the input every dataset
step was built from.
"""

from __future__ import annotations

from collections import Counter
from functools import partial
from pathlib import Path

import pytest

from environments.support.faults import IdentifierMappingSwap, inject_fault
from environments.support.fixtures import SupportEnvironment
from environments.support.tools import SUPPORT_TOOL_DESCRIPTIONS, SUPPORT_TOOL_SCHEMAS, SUPPORT_TOOLS
from packages.action_gateway import AllowListPolicy, GatedTool, ToolGateway
from packages.hetren_cli import inputs
from packages.hetren_evidence import compact_evidence
from packages.integrations.openai_agents import (CaptureStore, ReplayModel, RunProvenance, gateway_function_tools,
                                                 run_agent)
from packages.support_agent import build_support_agent, task_message
from packages.support_evaluator.plan import cross_plan
from packages.support_evaluator.sampling import run_planned_case


FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "support_captures"
LIVE_MODEL = "gpt-4.1-mini-2025-04-14"


def _replay(run_dir: str, swap: bool) -> dict:
    environment = SupportEnvironment()

    if swap:
        inject_fault(environment, IdentifierMappingSwap("C-3103", "C-3104"))

    gateway = ToolGateway(
        tools=[GatedTool(name, partial(f, environment), SUPPORT_TOOL_SCHEMAS[name], SUPPORT_TOOL_DESCRIPTIONS[name])
               for name, f in SUPPORT_TOOLS.items()],
        policy=AllowListPolicy(SUPPORT_TOOLS), state_sha256=environment.state_sha256,
    )
    model = ReplayModel(store=CaptureStore(FIXTURES / run_dir), source_provenance=RunProvenance.LIVE,
                        source_model_id=LIVE_MODEL)
    record = run_agent(agent=build_support_agent(environment=environment, tools=gateway_function_tools(gateway),
                                                 model=model),
                       task_input=task_message("T-1003"), gateway=gateway, run_id=run_dir,
                       provenance=RunProvenance.REPLAY)
    return record.evidence_payload()


def test_the_cli_tools_are_the_support_workflow_tools():
    assert set(inputs.SUPPORT_TOOLS) == set(SUPPORT_TOOLS)


@pytest.mark.parametrize(("run_dir", "swap"), [("run-0001", False), ("run-0002", True)])
def test_replayed_live_runs_are_accepted_as_recorded(run_dir, swap):
    record = _replay(run_dir, swap)
    assert record["provenance"] == "replay"
    assert inputs.from_record(record) == compact_evidence(record)


def test_every_case_kind_and_behaviour_is_accepted():
    plans = cross_plan(per_cell=1, seed=7)
    outcomes = Counter()

    for planned in plans:
        record = run_planned_case(planned)[2].evidence_payload()
        compact = inputs.from_record(record)
        assert compact == compact_evidence(record), planned
        outcomes.update(step["outcome"] for step in compact["steps"])

    assert {"succeeded", "failed"} <= set(outcomes), outcomes


def test_denied_and_malformed_calls_are_accepted():
    from environments.support.generator import generate_world

    record = run_planned_case(cross_plan(per_cell=1, seed=7)[0])[2].evidence_payload()
    environment = SupportEnvironment(generate_world(3))
    gateway = ToolGateway(
        tools=[GatedTool(name, partial(f, environment), SUPPORT_TOOL_SCHEMAS[name], SUPPORT_TOOL_DESCRIPTIONS[name])
               for name, f in SUPPORT_TOOLS.items()],
        policy=AllowListPolicy(SUPPORT_TOOLS), state_sha256=environment.state_sha256,
    )
    gateway.invoke_raw("read_ticket", '{"ticket_id": "T-0')
    gateway.invoke("read_ticket", {"ticket_id": "T-0001"})
    record = {**record, "status": "error", "error": {"type": "ModelBehaviorError", "message_sha256": "0" * 64},
              "stage_records": [r.canonical_payload() for r in gateway.records]}

    compact = inputs.from_record(record)
    assert compact == compact_evidence(record)
    assert [step["outcome"] for step in compact["steps"]] == ["denied", "failed"]


DATASETS = Path(__file__).resolve().parents[2] / "artifacts" / "milestone-2"


@pytest.mark.parametrize("dataset", ["dataset-v2", "dataset-v3"])
def test_every_published_first_step_input_is_accepted(dataset):
    """Input checks only (no model runs): every visible line of the tier 1 and tier 2 datasets."""
    import json

    path = DATASETS / dataset / "hetren_visible.jsonl"

    if not path.exists():
        pytest.skip("datasets are gitignored; regenerated in the slow job")

    lines = 0

    for line in path.open(encoding="utf-8"):
        case = json.loads(line)
        assert inputs.from_compact(case) == case["steps"][0]["input"], case["case_id"]
        lines += 1

    assert lines > 1000

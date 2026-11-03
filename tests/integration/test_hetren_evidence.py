from functools import partial
import json
from pathlib import Path
import re

import pytest
import tiktoken

from environments.support.faults import IdentifierMappingSwap, inject_fault
from environments.support.fixtures import SupportEnvironment
from environments.support.generator import generate_world
from environments.support.tools import (
    SUPPORT_TOOL_DESCRIPTIONS,
    SUPPORT_TOOL_SCHEMAS,
    SUPPORT_TOOLS,
)
from packages.action_gateway import AllowListPolicy, GatedTool, ToolGateway
from packages.contracts import ContractError
from packages.hetren_evidence import (
    COMPACT_FORMAT,
    EVIDENCE_TOKEN_BUDGET,
    compact_evidence,
    render_evidence,
)
from packages.integrations.openai_agents import (
    CaptureStore,
    ReplayModel,
    RunProvenance,
    gateway_function_tools,
    run_agent,
)
from packages.support_agent import BEHAVIOURS, ScriptedSupportModel, build_support_agent, task_message
from packages.support_evaluator import assert_no_leaks, scan_case_content
from packages.support_evaluator.plan import cross_plan
from packages.support_evaluator.sampling import run_planned_case, sample_case


# Loaded at import: tiktoken fetches the public vocabulary file once and caches it.
ENCODING = tiktoken.get_encoding("o200k_base")
FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "support_captures"
LIVE_MODEL = "gpt-4.1-mini-2025-04-14"

FAULT_MARKERS = (
    "fault", "swap", "identifier_mapping", "inject", "stale", "drift",
    "misconfig", "corrupt", "broken",
)
SAMPLE = cross_plan(per_cell=1, seed=7)


def _gateway(environment):
    return ToolGateway(
        tools=[
            GatedTool(name, partial(f, environment), SUPPORT_TOOL_SCHEMAS[name], SUPPORT_TOOL_DESCRIPTIONS[name])
            for name, f in SUPPORT_TOOLS.items()
        ],
        policy=AllowListPolicy(SUPPORT_TOOLS),
        state_sha256=environment.state_sha256,
    )


def _run(environment, ticket_id, model, provenance, run_id="run-0001"):
    gateway = _gateway(environment)
    return run_agent(
        agent=build_support_agent(environment=environment, tools=gateway_function_tools(gateway), model=model),
        task_input=task_message(ticket_id), gateway=gateway, run_id=run_id, provenance=provenance,
    )


def _m1_environment(swap):
    environment = SupportEnvironment()

    if swap:
        inject_fault(environment, IdentifierMappingSwap("C-3103", "C-3104"))

    return environment


# What is kept and what is dropped


def test_compact_input_keeps_actions_and_observations_only():
    record = _run(_m1_environment(True), "T-1003", ScriptedSupportModel(), RunProvenance.SCRIPTED)
    compact = compact_evidence(record.evidence_payload())

    assert set(compact) == {"format", "task", "run", "steps", "discrepancies", "probes"}
    assert compact["format"] == COMPACT_FORMAT
    assert compact["run"] == {"status": "completed", "error_type": None}
    assert [(s["tool"], s["outcome"], s["changed_state"]) for s in compact["steps"]] == [
        ("read_ticket", "succeeded", False),
        ("lookup_account", "succeeded", False),
        ("route_ticket", "succeeded", True),
    ]
    assert compact["steps"][1]["observation"]["customer_ref"] == "C-3104"


def test_identifiers_hashes_provenance_and_final_message_are_dropped():
    record = _run(_m1_environment(True), "T-1003", ScriptedSupportModel("give_up"), RunProvenance.SCRIPTED)
    text = render_evidence(compact_evidence(record.evidence_payload()))

    assert re.search(r"[0-9a-f]{64}", text) is None
    for forbidden in (
        "model", "scripted", "give_up", "provenance", "capture", "call-0", "call_",
        "fc_", "run-0001", "recorded_at", "started_at", "openai", "sequence",
        "instructions", "support-agent", "I stopped",
    ):
        assert forbidden not in text, forbidden


def test_denied_failed_and_malformed_calls_keep_their_evidence():
    spec = generate_world(3)
    environment = SupportEnvironment(spec)
    gateway = _gateway(environment)
    gateway.invoke_raw("read_ticket", '{"ticket_id": "T-0')
    gateway.invoke("read_ticket", {"ticket_id": "T-0001"})
    evidence = {
        "record_type": "AgentRunRecord", "task_input": "Please handle support ticket T-0001.",
        "status": "error", "error": {"type": "ModelBehaviorError", "message_sha256": "0" * 64},
        "stage_records": [r.canonical_payload() for r in gateway.records],
        "sdk_evidence": {"discrepancies": [{"kind": "model_call_without_gateway_record"}]},
    }

    compact = compact_evidence(evidence)

    assert compact["steps"][0] == {
        "tool": "read_ticket", "args": {"raw_arguments": '{"ticket_id": "T-0'},
        "outcome": "denied", "reason": "arguments_not_json",
    }
    assert compact["steps"][1]["outcome"] == "failed"
    assert compact["steps"][1]["error"] == {"type": "ContractError", "message": "unknown ticket_id"}
    assert compact["run"] == {"status": "error", "error_type": "ModelBehaviorError"}
    assert compact["discrepancies"] == ["model_call_without_gateway_record"]


def test_compactor_requires_a_run_record_payload():
    with pytest.raises(ContractError):
        compact_evidence({"record_type": "Other"})


# Scripted, live and replayed runs look the same


@pytest.mark.parametrize(("run_dir", "swap"), [("run-0001", False), ("run-0002", True)])
def test_live_replay_and_equivalent_scripted_run_compact_identically(run_dir, swap):
    live = _run(
        _m1_environment(swap), "T-1003",
        ReplayModel(store=CaptureStore(FIXTURES / run_dir), source_provenance=RunProvenance.LIVE,
                    source_model_id=LIVE_MODEL),
        RunProvenance.REPLAY, run_dir,
    )
    scripted = _run(_m1_environment(swap), "T-1003", ScriptedSupportModel(), RunProvenance.SCRIPTED)

    assert live.evidence_payload() != scripted.evidence_payload()
    assert compact_evidence(live.evidence_payload()) == compact_evidence(scripted.evidence_payload())
    assert render_evidence(compact_evidence(live.evidence_payload())) == render_evidence(
        compact_evidence(scripted.evidence_payload())
    )


# Behaviour cannot be recovered beyond the actions it takes


@pytest.mark.parametrize("seed", range(4))
def test_all_behaviours_compact_identically_when_their_actions_match(seed):
    spec = generate_world(seed)

    for ticket in spec.tickets[:4]:
        texts = {
            render_evidence(
                compact_evidence(
                    _run(SupportEnvironment(spec), ticket.ticket_id, ScriptedSupportModel(b), RunProvenance.SCRIPTED)
                    .evidence_payload()
                )
            )
            for b in BEHAVIOURS
        }
        assert len(texts) == 1


def test_compact_input_is_a_function_of_the_actions_and_observations():
    for planned in SAMPLE[: len(SAMPLE) // 2]:
        by_steps: dict[str, set[str]] = {}

        for behaviour in BEHAVIOURS:
            variant = planned.__class__(**{**planned.__dict__, "behaviour": behaviour})
            _, _, record = run_planned_case(variant)
            compact = compact_evidence(record.evidence_payload())
            key = json.dumps(compact["steps"], sort_keys=True)
            by_steps.setdefault(key, set()).add(render_evidence(compact))

        assert all(len(texts) == 1 for texts in by_steps.values())


# Token budget


def _tokens(compact) -> int:
    return len(ENCODING.encode(render_evidence(compact)))


def test_every_step_fits_the_token_budget():
    sizes = [_tokens(step) for planned in SAMPLE for step in sample_case(planned).steps]

    assert len(sizes) == len(SAMPLE) * 5
    assert max(sizes) <= EVIDENCE_TOKEN_BUDGET, max(sizes)


def test_budget_test_would_catch_an_oversized_input():
    oversized = {"format": COMPACT_FORMAT, "task": "x " * 2000, "run": {}, "steps": [], "discrepancies": [], "probes": []}

    assert _tokens(oversized) > EVIDENCE_TOKEN_BUDGET


# Leakage and markers on the compacted input


def test_compact_inputs_are_clean_for_every_case_kind_and_behaviour():
    for planned in SAMPLE:
        sampled = sample_case(planned)

        for step in sampled.steps:
            text = render_evidence(step).lower()

            for marker in FAULT_MARKERS:
                assert marker not in text, (planned.case_kind, marker)

        assert_no_leaks(scan_case_content({"compact_steps": list(sampled.steps)}, sampled.case.truth))


def test_planted_leaks_in_compact_input_are_caught():
    sampled = sample_case(SAMPLE[0])
    step = json.loads(json.dumps(sampled.steps[-1]))
    step["probes"].append({"tool": "inspect", "args": {}, "outcome": "succeeded",
                           "observation": {"note": "source_matches_record"}})
    step["task"] = f"{step['task']} Expected {sampled.case.truth.expected_queue_id}."

    findings = scan_case_content({"compact": step}, sampled.case.truth)

    assert {f.kind for f in findings} >= {"sensitive_token", "answer_pair"}

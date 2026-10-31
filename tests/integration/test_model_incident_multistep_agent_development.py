"""A5-10G-B2: model capture / real local observation sequence, offline only."""

from dataclasses import replace
import json

import pytest

from packages.contracts import ContractError
from packages.engines.behavioral.incident_scenario_development import IncidentScenario
from packages.engines.behavioral.incident_multistep_runtime_development import (
    IncidentWorkflowAction, start_incident_workflow, advance_incident_workflow,
)
from packages.engines.behavioral.model_incident_multistep_agent_development import (
    build_observation_bound_request,
    run_captured_multistep_incident,
    run_injected_openai_multistep_incident,
)
from packages.model_capture import capture_json_response


def _scenario(service="payments", minimum=3):
    return IncidentScenario(
        scenario_id="observation-b2", target_service=service,
        minimum_severity=minimum,
        records=(
            ("INC-P001", "payments", 3),
            ("INC-P002", "payments", 6),
            ("INC-P003", "payments", 1),
            ("INC-A001", "auth", 2),
            ("INC-A002", "auth", 8),
            ("INC-N001", "notifications", 10),
        ),
    )


def _context(request):
    return json.loads(request.user_prompt.split("STATE_JSON=", 1)[1])


def _proposal(ctx, *, filter_tool="inclusive_severity_filter", threshold=None, service=None):
    phase = ctx["phase"]
    if phase == "ready":
        assert ctx["previous_observation"] is None
        return {"operation": "load_incidents"}
    if phase == "loaded":
        assert len(ctx["previous_observation"]["rows"]) == 6
        return {
            "operation": "scope_service",
            "service": ctx["task_goal"]["target_service"] if service is None else service,
        }
    if phase == "scoped":
        assert ctx["previous_observation"]["operation"] == "scope_service"
        return {
            "operation": "apply_filter", "filter_tool": filter_tool,
            "threshold": ctx["task_goal"]["minimum_severity"] if threshold is None else threshold,
        }
    assert phase == "filtered"
    assert ctx["previous_observation"]["operation"] == "apply_filter"
    return {"operation": "finalize"}


def _source(observed, *, filter_tool="inclusive_severity_filter", threshold=None, service=None):
    def capture_source(request):
        ctx = _context(request)
        observed.append((request, ctx))
        response = _proposal(ctx, filter_tool=filter_tool, threshold=threshold, service=service)
        return capture_json_response(request=request, raw_response_text=json.dumps(response))
    return capture_source


@pytest.mark.parametrize("service,minimum,expected", [
    ("payments", 3, ("INC-P001", "INC-P002")),
    ("auth", 2, ("INC-A001", "INC-A002")),
    ("notifications", 10, ("INC-N001",)),
    ("payments", 9, ()),
])
def test_real_observation_appears_in_next_model_request(service, minimum, expected):
    scenario = _scenario(service, minimum)
    observed = []
    run = run_captured_multistep_incident(
        scenario=scenario, model="offline-model", run_id="a510g-b2",
        capture_source=_source(observed),
    )
    assert run.status == "completed" and run.passed
    assert run.state.report.incident_ids == expected
    assert run.state.evaluation.expected_ids == expected
    assert len(run.decisions) == len(observed) == len(run.state.steps) == 4
    assert "INC-P001" not in observed[0][0].user_prompt
    assert observed[0][1]["previous_observation_sha256"] is None
    assert observed[1][1]["previous_observation"]["rows"] == [list(row) for row in scenario.records]
    for i, decision in enumerate(run.decisions):
        assert decision.request_sha256 == observed[i][0].request_sha256
        assert decision.workflow_before_sha256 == observed[i][1]["workflow_evidence_sha256"]
        assert decision.resulting_observation_sha256 == run.state.steps[i].observation.observation_sha256
        assert decision.action == run.state.steps[i].action
        assert decision.rejected_reason is None
        if i:
            assert decision.previous_observation_sha256 == run.decisions[i - 1].resulting_observation_sha256
        else:
            assert decision.previous_observation_sha256 is None
    assert len(run.execution_evidence_sha256) == 64
    assert "INC-P001" not in observed[0][0].user_prompt


@pytest.mark.parametrize("service,tool,threshold", [
    ("auth", "inclusive_severity_filter", 3),
    ("payments", "strict_severity_filter", 3),
    ("payments", "inclusive_severity_filter", 4),
])
def test_completed_workflow_may_fail_independent_evaluation(service, tool, threshold):
    seen = []
    run = run_captured_multistep_incident(
        scenario=_scenario(), model="offline-model", run_id="a510g-wrong",
        capture_source=_source(seen, service=service, filter_tool=tool, threshold=threshold),
    )
    assert run.status == "completed" and run.state.completed
    assert not run.passed and run.state.evaluation is not None
    assert not run.state.evaluation.passed
    assert len(seen) == 4


def test_budget_exhaustion_makes_no_extra_request():
    seen = []
    run = run_captured_multistep_incident(
        scenario=_scenario(), model="offline-model", run_id="a510g-budget",
        max_steps=2, capture_source=_source(seen),
    )
    assert run.status == "budget_exhausted" and not run.passed
    assert run.state.budget_exhausted and run.state.phase == "scoped"
    assert len(seen) == len(run.decisions) == 2
    assert run.state.report is None and run.state.evaluation is None


@pytest.mark.parametrize("invalid", [
    {"operation": "finalize"},
    {"operation": "load_incidents", "shell": "rm -rf"},
    {"operation": "load_incidents", "threshold": 3},
])
def test_illegal_or_extra_model_proposal_rejected_without_tool_execution(invalid):
    observed = []
    def source(request):
        observed.append(request)
        return capture_json_response(request=request, raw_response_text=json.dumps(invalid))
    run = run_captured_multistep_incident(
        scenario=_scenario(), model="offline-model", run_id="a510g-rejected",
        capture_source=source,
    )
    assert run.status == "rejected" and run.rejection_reason
    assert len(run.decisions) == len(observed) == 1
    assert run.decisions[0].action is None
    assert run.decisions[0].resulting_observation_sha256 is None
    assert run.state.steps == () and not run.passed


def test_illegal_model_action_after_loading_preserves_prior_observation():
    calls = []
    def source(request):
        ctx = _context(request)
        calls.append(ctx)
        proposal = {"operation": "load_incidents"} if len(calls) == 1 else {"operation": "finalize"}
        return capture_json_response(request=request, raw_response_text=json.dumps(proposal))
    run = run_captured_multistep_incident(
        scenario=_scenario(), model="offline-model", run_id="a510g-second-reject",
        capture_source=source,
    )
    assert run.status == "rejected" and len(run.state.steps) == 1
    assert len(run.decisions) == 2
    assert run.state.loaded_rows == _scenario().records
    assert run.decisions[1].previous_observation_sha256 == run.decisions[0].resulting_observation_sha256


def test_request_invalidates_cross_scenario_or_changed_observation_capture():
    first = _scenario()
    changed = replace(first, records=first.records + (("INC-P004", "payments", 9),))
    state_first = start_incident_workflow(scenario=first, run_id="a510g-identity")
    state_changed = start_incident_workflow(scenario=changed, run_id="a510g-identity")
    for action in [IncidentWorkflowAction("load_incidents")]:
        state_first = advance_incident_workflow(scenario=first, state=state_first, action=action)
        state_changed = advance_incident_workflow(scenario=changed, state=state_changed, action=action)
    request_first = build_observation_bound_request(scenario=first, state=state_first, model="offline-model")
    request_changed = build_observation_bound_request(scenario=changed, state=state_changed, model="offline-model")
    assert request_first.request_sha256 != request_changed.request_sha256
    assert _context(request_first)["previous_observation_sha256"] != _context(request_changed)["previous_observation_sha256"]

    old_capture = capture_json_response(
        request=request_first, raw_response_text=json.dumps({"operation": "scope_service", "service": "payments"}),
    )
    calls = []
    def source(request):
        calls.append(request)
        if len(calls) == 1:
            return capture_json_response(request=request, raw_response_text='{"operation":"load_incidents"}')
        return old_capture
    with pytest.raises(ContractError):
        run_captured_multistep_incident(
            scenario=changed, model="offline-model", run_id="a510g-identity",
            capture_source=source,
        )
    assert len(calls) == 2


def test_forged_resume_state_rejected_before_request():
    scenario = _scenario()
    state = start_incident_workflow(scenario=scenario, run_id="a510g-forged")
    state = advance_incident_workflow(
        scenario=scenario, state=state, action=IncidentWorkflowAction("load_incidents"),
    )
    with pytest.raises(ContractError, match="provenance"):
        build_observation_bound_request(
            scenario=scenario, state=replace(state, loaded_rows=()), model="offline-model",
        )
    with pytest.raises(ContractError, match="identity"):
        build_observation_bound_request(
            scenario=replace(scenario, minimum_severity=9), state=state,
            model="offline-model",
        )


def test_tampered_capture_and_non_callable_source_fail_closed():
    with pytest.raises(ContractError, match="capture source"):
        run_captured_multistep_incident(
            scenario=_scenario(), model="offline-model", run_id="a510g-none",
            capture_source=None,
        )
    def tampered(request):
        capture = capture_json_response(request=request, raw_response_text='{"operation":"load_incidents"}')
        return replace(capture, raw_response_text='{"operation":"finalize"}')
    with pytest.raises(ContractError):
        run_captured_multistep_incident(
            scenario=_scenario(), model="offline-model", run_id="a510g-tamper",
            capture_source=tampered,
        )


def test_equal_run_id_and_capture_policy_replay_deterministically():
    scenario = _scenario()
    one = run_captured_multistep_incident(
        scenario=scenario, model="offline-model", run_id="a510g-replay",
        capture_source=_source([]),
    )
    two = run_captured_multistep_incident(
        scenario=scenario, model="offline-model", run_id="a510g-replay",
        capture_source=_source([]),
    )
    different = run_captured_multistep_incident(
        scenario=scenario, model="offline-model", run_id="a510g-other",
        capture_source=_source([]),
    )
    assert one == two
    assert one.execution_evidence_sha256 == two.execution_evidence_sha256
    assert one.execution_evidence_sha256 != different.execution_evidence_sha256
    assert one.state.report == different.state.report


def test_completed_state_rejects_next_model_request():
    scenario = _scenario()
    run = run_captured_multistep_incident(
        scenario=scenario, model="offline-model", run_id="a510g-done",
        capture_source=_source([]),
    )
    with pytest.raises(ContractError, match="no decision"):
        build_observation_bound_request(
            scenario=scenario, state=run.state, model="offline-model",
        )


def test_injected_provider_shaped_transport_changes_request_after_each_observation():
    calls = []
    def fake_transport(endpoint, body, headers, timeout):
        payload = json.loads(body)
        assert endpoint == "https://api.openai.com/v1/responses"
        assert headers["Authorization"] == "Bearer synthetic-offline-key"
        assert payload["store"] is False and payload["stream"] is False
        assert timeout == 30.0
        # Provider payload contains the state prompt as an input item.
        # Use the request's input messages without hard-coding provider schema:
        prompts = json.dumps(payload)
        # The STATE_JSON payload is nested in the prompt JSON; decode it from
        # the request envelope by inspecting the messages recursively.
        def collect_strings(obj):
            if isinstance(obj, str):
                yield obj
            elif isinstance(obj, list):
                for item in obj:
                    yield from collect_strings(item)
            elif isinstance(obj, dict):
                for value in obj.values():
                    yield from collect_strings(value)
        matches = [s for s in collect_strings(payload) if "STATE_JSON=" in s]
        assert matches, prompts[:900]
        state = json.loads(matches[0].split("STATE_JSON=", 1)[1])
        calls.append(state)
        action = _proposal(state)
        return json.dumps({
            "id": f"resp_a510g_offline_{len(calls)}",
            "model": "offline-model", "status": "completed",
            "output": [{"type": "message", "role": "assistant", "content": [
                {"type": "output_text", "text": json.dumps(action)},
            ]}],
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        }).encode("utf-8")
    run = run_injected_openai_multistep_incident(
        scenario=_scenario(), model="offline-model", run_id="a510g-transport",
        api_key="synthetic-offline-key", transport=fake_transport,
    )
    assert run.status == "completed" and run.passed
    assert len(calls) == 4
    assert calls[0]["previous_observation"] is None
    assert calls[1]["previous_observation"]["rows"] == [list(row) for row in _scenario().records]
    assert "synthetic-offline-key" not in repr(run)
    assert "synthetic-offline-key" not in run.execution_evidence_sha256


def test_missing_provider_transport_rejected_without_network():
    with pytest.raises(ContractError, match="injected transport"):
        run_injected_openai_multistep_incident(
            scenario=_scenario(), model="offline-model", run_id="a510g-transport-none",
            api_key="synthetic-offline-key", transport=None,
        )


def test_limitations_do_not_claim_model_reasoning_or_research_authority():
    run = run_captured_multistep_incident(
        scenario=_scenario(), model="offline-model", run_id="a510g-limitations",
        capture_source=_source([]),
    )
    limitations = " ".join(run.limitations)
    assert "do not prove observation-dependent reasoning" in limitations
    assert "no independent scientific verification" in limitations
    assert "no live-model generalization" in limitations

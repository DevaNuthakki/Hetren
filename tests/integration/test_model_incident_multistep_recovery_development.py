"""A5-10G-B3: bounded offline resilience and synthetic tool failure recovery."""
from dataclasses import replace
import json

import pytest

from packages.contracts import ContractError
from packages.engines.behavioral.incident_scenario_development import IncidentScenario
from packages.engines.behavioral.model_incident_multistep_recovery_development import (
    InjectedToolFailure, build_recovery_bound_request,
    run_resilient_multistep_incident,
    run_injected_openai_resilient_multistep_incident,
)
from packages.engines.behavioral.incident_multistep_runtime_development import (
    IncidentWorkflowAction, start_incident_workflow, advance_incident_workflow,
)
from packages.model_capture import capture_json_response


def _scenario():
    return IncidentScenario(
        scenario_id="recovery-b3", target_service="payments", minimum_severity=3,
        records=(
            ("INC-P001", "payments", 3),
            ("INC-P002", "payments", 7),
            ("INC-P003", "payments", 1),
            ("INC-A001", "auth", 9),
        ),
    )


def _context(request):
    state_fragment = request.user_prompt.split("STATE_JSON=", 1)[1]
    state = json.loads(state_fragment.split("\nRECOVERY_JSON=", 1)[0])
    recovery = (
        None if "\nRECOVERY_JSON=" not in request.user_prompt
        else json.loads(request.user_prompt.split("\nRECOVERY_JSON=", 1)[1])
    )
    return state, recovery


def _proposal(state, recovery):
    phase = state["phase"]
    if phase == "ready":
        return {"operation": "load_incidents"}
    if phase == "loaded":
        return {"operation": "scope_service", "service": "payments"}
    if phase == "scoped":
        # Changed proposal after actual failure feedback; not after a retry timer.
        return {
            "operation": "apply_filter",
            "filter_tool": (
                "inclusive_severity_filter" if recovery is not None
                else "strict_severity_filter"
            ),
            "threshold": 3,
        }
    assert phase == "filtered"
    return {"operation": "finalize"}


def _source(seen, *, same_failed_action=False, invalid_recovery=False):
    def source(request):
        state, recovery = _context(request)
        seen.append((request, state, recovery))
        proposal = _proposal(state, recovery)
        if recovery and same_failed_action:
            proposal["filter_tool"] = "strict_severity_filter"
        if recovery and invalid_recovery:
            proposal = {"operation": "finalize"}
        return capture_json_response(request=request, raw_response_text=json.dumps(proposal))
    return source


def _fail_strict_once(seen):
    def injector(state, action):
        seen.append((state.phase, action))
        if action.operation == "apply_filter" and action.filter_tool == "strict_severity_filter":
            return InjectedToolFailure("temporarily_unavailable")
        return None
    return injector


def _run(*, seen=None, faults=None, **kwargs):
    seen = [] if seen is None else seen
    faults = [] if faults is None else faults
    return run_resilient_multistep_incident(
        scenario=_scenario(), model="offline-model", run_id="a510g-b3",
        capture_source=_source(seen), failure_injector=_fail_strict_once(faults),
        **kwargs,
    )


def test_failure_feedback_changes_next_model_action_and_recovers():
    calls, faults = [], []
    run = _run(seen=calls, faults=faults)
    assert run.status == "completed" and run.passed
    assert len(run.attempts) == len(calls) == 5
    assert len(run.state.steps) == 4 and len(run.injected_failures) == 1
    assert run.state.report.incident_ids == ("INC-P001", "INC-P002")
    assert run.state.evaluation.passed
    assert len(faults) == 5  # includes failed and recovered filter attempts
    failed, recovered = run.attempts[2:4]
    assert failed.action.filter_tool == "strict_severity_filter"
    assert not failed.executed and failed.injected_failure is not None
    assert failed.workflow_after_sha256 == failed.workflow_before_sha256
    assert failed.resulting_observation_sha256 is None
    assert recovered.action.filter_tool == "inclusive_severity_filter"
    assert recovered.executed and recovered.injected_failure is None
    assert recovered.previous_failure_sha256 == failed.injected_failure.observation_sha256
    assert recovered.workflow_before_sha256 == failed.workflow_before_sha256
    assert recovered.workflow_after_sha256 != recovered.workflow_before_sha256
    assert calls[2][2] is None
    assert calls[3][2]["failure_observation_sha256"] == failed.injected_failure.observation_sha256
    assert calls[3][2]["failure"]["origin"] == "synthetic_pre_execution_failure"
    assert calls[3][1]["previous_observation_sha256"] == calls[2][1]["previous_observation_sha256"]
    assert calls[3][0].request_sha256 != calls[2][0].request_sha256
    assert run.state.trace.events[-1].operation == "finalize"
    assert len(run.state.trace.events) == 4


def test_no_fault_completes_normally_but_wrong_tool_fails_evaluation():
    calls = []
    run = run_resilient_multistep_incident(
        scenario=_scenario(), model="offline-model", run_id="a510g-nofault",
        capture_source=_source(calls),
        max_attempts=4, max_recoveries=0,
    )
    assert run.status == "completed" and not run.passed
    assert len(run.attempts) == 4 and not run.injected_failures
    assert run.state.report.incident_ids == ("INC-P002",)
    assert run.state.evaluation.passed is False


def test_zero_failure_allowance_terminates_without_fake_execution():
    run = _run(max_recoveries=0)
    assert run.status == "recovery_exhausted" and not run.passed
    assert run.termination_reason == "injected_failure_budget_exhausted"
    assert len(run.attempts) == 3
    assert len(run.state.steps) == 2 and run.state.phase == "scoped"
    assert run.state.report is None
    assert not run.attempts[-1].executed



def test_distinct_second_filter_failure_exhausts_recovery_allowance():
    seen = []
    def always_fail_filter(state, action):
        if action.operation == "apply_filter":
            return InjectedToolFailure("synthetic_timeout")
        return None
    run = run_resilient_multistep_incident(
        scenario=_scenario(), model="offline-model", run_id="a510g-twofaults",
        capture_source=_source(seen), failure_injector=always_fail_filter,
        max_recoveries=1, max_attempts=6,
    )
    assert run.status == "recovery_exhausted" and not run.passed
    assert len(run.injected_failures) == 2
    assert len(run.attempts) == 4
    assert len(run.state.steps) == 2 and run.state.report is None
    assert run.attempts[2].action.filter_tool == "strict_severity_filter"
    assert run.attempts[3].action.filter_tool == "inclusive_severity_filter"
    assert all(not attempt.executed for attempt in run.attempts[2:])
    assert run.injected_failures[0].observation_sha256 != run.injected_failures[1].observation_sha256


def test_repeated_failed_action_terminates_without_second_execution():
    calls, faults = [], []
    run = run_resilient_multistep_incident(
        scenario=_scenario(), model="offline-model", run_id="a510g-loop",
        capture_source=_source(calls, same_failed_action=True),
        failure_injector=_fail_strict_once(faults), max_recoveries=2,
    )
    assert run.status == "rejected" and run.termination_reason == "repeated_failed_action"
    assert len(run.attempts) == 4 and len(run.injected_failures) == 1
    assert not run.attempts[-1].executed
    assert run.attempts[-1].rejection_reason == "repeated_failed_action"
    assert len(faults) == 3  # repeated action is blocked before fault hook
    assert run.state.phase == "scoped"


def test_invalid_recovery_proposal_is_rejected_before_tool():
    calls = []
    run = run_resilient_multistep_incident(
        scenario=_scenario(), model="offline-model", run_id="a510g-invalid",
        capture_source=_source(calls, invalid_recovery=True),
        failure_injector=_fail_strict_once([]),
    )
    assert run.status == "rejected" and not run.passed
    assert len(run.injected_failures) == 1
    assert len(run.state.steps) == 2
    assert run.attempts[-1].action is None and not run.attempts[-1].executed
    assert run.attempts[-1].rejection_reason


def test_attempt_budget_limits_retry_even_if_tool_failure_is_recoverable():
    run = _run(max_attempts=3, max_recoveries=1)
    assert run.status == "budget_exhausted"
    assert len(run.attempts) == 3 and len(run.injected_failures) == 1
    assert run.state.phase == "scoped" and len(run.state.steps) == 2
    assert not run.passed


def test_budget_prevents_finalization_after_successful_recovery():
    run = _run(max_attempts=4, max_recoveries=1)
    assert run.status == "budget_exhausted"
    assert len(run.attempts) == 4 and len(run.state.steps) == 3
    assert run.state.phase == "filtered"
    assert not run.passed and run.state.evaluation is None


def test_cross_scenario_recovery_observation_cannot_be_rebound():
    scenario = _scenario()
    state = start_incident_workflow(scenario=scenario, run_id="a510g-rebind")
    state = advance_incident_workflow(
        scenario=scenario, state=state, action=IncidentWorkflowAction("load_incidents"),
    )
    old = build_recovery_bound_request(
        scenario=scenario, state=state, model="offline-model", prior_failure=None,
    )
    assert old.request_sha256
    previous_failure = _run().injected_failures[0]
    with pytest.raises(ContractError, match="recovery observation"):
        build_recovery_bound_request(
            scenario=scenario, state=state, model="offline-model",
            prior_failure=previous_failure,
        )
    with pytest.raises(ContractError, match="identity"):
        changed = replace(scenario, minimum_severity=5)
        build_recovery_bound_request(
            scenario=changed, state=state, model="offline-model", prior_failure=None,
        )


def test_capture_for_pre_failure_request_cannot_replay_after_failure():
    earlier = []
    def source(request):
        state, recovery = _context(request)
        if state["phase"] != "scoped" or recovery is None:
            proposal = _proposal(state, recovery)
            cap = capture_json_response(request=request, raw_response_text=json.dumps(proposal))
            if state["phase"] == "scoped":
                earlier.append(cap)
            return cap
        return earlier[0]  # valid capture; WRONG recovery-bound request
    with pytest.raises(ContractError):
        run_resilient_multistep_incident(
            scenario=_scenario(), model="offline-model", run_id="a510g-stale",
            capture_source=source, failure_injector=_fail_strict_once([]),
        )


def test_capture_tampering_remains_fail_closed():
    def source(request):
        good = capture_json_response(request=request, raw_response_text='{"operation":"load_incidents"}')
        return replace(good, raw_response_text='{"operation":"finalize"}')
    with pytest.raises(ContractError):
        run_resilient_multistep_incident(
            scenario=_scenario(), model="offline-model", run_id="a510g-tampered",
            capture_source=source,
        )


def test_invalid_failure_injection_fails_loudly():
    def bad_injector(state, action):
        return "temporarily_unavailable" if action.operation == "apply_filter" else None
    with pytest.raises(ContractError, match="invalid injected failure"):
        run_resilient_multistep_incident(
            scenario=_scenario(), model="offline-model", run_id="a510g-badfault",
            capture_source=_source([]), failure_injector=bad_injector,
        )


def test_injection_outside_filter_boundary_is_forbidden():
    def bad_injector(state, action):
        return InjectedToolFailure("synthetic_timeout")
    with pytest.raises(ContractError, match="outside filter boundary"):
        run_resilient_multistep_incident(
            scenario=_scenario(), model="offline-model", run_id="a510g-badphase",
            capture_source=_source([]), failure_injector=bad_injector,
        )


@pytest.mark.parametrize("bad", [None, False, 1, "abc"])
def test_invalid_source_rejected_before_execution(bad):
    with pytest.raises(ContractError, match="capture source"):
        run_resilient_multistep_incident(
            scenario=_scenario(), model="offline-model", run_id="a510g-badsrc",
            capture_source=bad,
        )


@pytest.mark.parametrize("kwargs", [
    {"max_attempts": 0}, {"max_attempts": 13},
    {"max_attempts": True}, {"max_recoveries": -1},
    {"max_recoveries": 3}, {"max_recoveries": True},
])
def test_invalid_budget_fails_closed(kwargs):
    with pytest.raises(ContractError):
        run_resilient_multistep_incident(
            scenario=_scenario(), model="offline-model", run_id="a510g-badbudget",
            capture_source=_source([]), **kwargs,
        )


def test_recovery_evidence_deterministic_and_run_id_bound():
    one = _run()
    two = _run()
    changed = run_resilient_multistep_incident(
        scenario=_scenario(), model="offline-model", run_id="a510g-another",
        capture_source=_source([]), failure_injector=_fail_strict_once([]),
    )
    assert one == two
    assert one.execution_evidence_sha256 == two.execution_evidence_sha256
    assert one.execution_evidence_sha256 != changed.execution_evidence_sha256
    assert one.state.report == changed.state.report


def test_offline_provider_shaped_transport_recovers_without_live_https():
    calls = []
    def transport(endpoint, body, headers, timeout):
        assert endpoint == "https://api.openai.com/v1/responses"
        assert headers["Authorization"] == "Bearer synthetic-offline-key"
        assert timeout == 30.0
        payload = json.loads(body)
        assert payload["store"] is False and payload["stream"] is False
        def collect(obj):
            if isinstance(obj, str):
                yield obj
            elif isinstance(obj, dict):
                for value in obj.values():
                    yield from collect(value)
            elif isinstance(obj, list):
                for item in obj:
                    yield from collect(item)
        candidates = [x for x in collect(payload) if "STATE_JSON=" in x]
        assert candidates
        state, recovery = _context(type("Request", (), {"user_prompt": candidates[0]})())
        calls.append((state, recovery))
        return json.dumps({
            "id": f"resp_a510gb3_offline_{len(calls)}",
            "model": "offline-model", "status": "completed",
            "output": [{"type": "message", "role": "assistant", "content": [
                {"type": "output_text", "text": json.dumps(_proposal(state, recovery))},
            ]}],
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        }).encode("utf-8")
    run = run_injected_openai_resilient_multistep_incident(
        scenario=_scenario(), model="offline-model", run_id="a510g-provider",
        api_key="synthetic-offline-key", transport=transport,
        failure_injector=_fail_strict_once([]),
    )
    assert run.status == "completed" and run.passed
    assert len(calls) == 5 and calls[3][1] is not None
    assert "synthetic-offline-key" not in repr(run)
    assert "synthetic-offline-key" not in run.execution_evidence_sha256


def test_missing_offline_transport_refuses_default_network():
    with pytest.raises(ContractError, match="injected transport"):
        run_injected_openai_resilient_multistep_incident(
            scenario=_scenario(), model="offline-model", run_id="a510g-none",
            api_key="synthetic-offline-key", transport=None,
        )


def test_limitations_do_not_overclaim_recovery():
    run = _run()
    text = " ".join(run.limitations)
    assert "synthetic development-only" in text
    assert "not B1 AgentTrace" in text
    assert "no real external tool-failure recovery" in text
    assert "does not prove real-model reasoning" in text
    assert "no independent scientific verification" in text

"""A5-10H-B1: typed, evidence-bound capture-source interruption."""
from dataclasses import replace
import json

import pytest

from packages.contracts import ContractError
from packages.core.hetren_diagnosis.contracts import canonical_sha256
from packages.engines.behavioral.incident_scenario_development import IncidentScenario
from packages.engines.behavioral.model_incident_multistep_recovery_development import (
    CaptureSourceInterruption,
    InjectedToolFailure,
    ResilientMultistepIncidentRun,
    run_resilient_multistep_incident,
    run_injected_openai_resilient_multistep_incident,
)
from packages.model_capture import capture_json_response


def _scenario():
    return IncidentScenario(
        scenario_id="interruption-hb1", target_service="payments", minimum_severity=3,
        records=(("INC-P701", "payments", 3), ("INC-P702", "payments", 7),
                 ("INC-P703", "payments", 1), ("INC-A701", "auth", 9)),
    )


def _policy(request):
    raw = request.user_prompt.split("STATE_JSON=", 1)[1].split("\nRECOVERY_JSON=", 1)[0]
    phase = json.loads(raw)["phase"]
    if phase == "ready":
        action = {"operation": "load_incidents"}
    elif phase == "loaded":
        action = {"operation": "scope_service", "service": "payments"}
    elif phase == "scoped":
        action = {"operation": "apply_filter", "filter_tool": "inclusive_severity_filter",
                  "threshold": 3}
    else:
        assert phase == "filtered"
        action = {"operation": "finalize"}
    return capture_json_response(request=request, raw_response_text=json.dumps(action))


def _run(source, **kwargs):
    return run_resilient_multistep_incident(
        scenario=_scenario(), model="offline-model", run_id="a510h-b1",
        capture_source=source, **kwargs,
    )


def test_first_capture_interruption_returns_typed_zero_step_evidence():
    requests = []
    def source(request):
        requests.append(request.request_sha256)
        raise RuntimeError("sensitive-provider-error-do-not-keep")
    run = _run(source)
    assert run.status == "interrupted" and not run.passed
    assert run.termination_reason == "capture_source_interrupted"
    assert len(run.attempts) == len(run.state.steps) == 0
    assert len(run.state.trace.events) == 0 and run.state.report is None
    interruption = run.interruption
    assert isinstance(interruption, CaptureSourceInterruption)
    assert interruption.pending_request_sha256 == requests[0]
    assert interruption.workflow_before_sha256 == run.state.execution_evidence_sha256
    assert interruption.attempt_number == 1
    assert interruption.prior_success_observation_sha256 is None
    assert interruption.prior_failure_sha256 is None
    assert len(interruption.interruption_evidence_sha256) == 64
    assert "sensitive-provider-error" not in repr(run)
    assert "sensitive-provider-error" not in repr(interruption.canonical_payload())


def test_mid_run_interruption_retains_only_verified_executions():
    requests = []
    def source(request):
        requests.append(request.request_sha256)
        if len(requests) == 3:
            raise ConnectionError("secret-error")
        return _policy(request)
    run = _run(source)
    assert run.status == "interrupted" and not run.passed
    assert len(run.attempts) == len(run.state.steps) == 2
    assert len(run.state.trace.events) == 2
    assert all(item.executed for item in run.attempts)
    assert run.state.phase == "scoped" and run.state.report is None
    assert run.interruption.pending_request_sha256 == requests[-1]
    assert run.interruption.attempt_number == 3
    assert run.interruption.workflow_before_sha256 == run.state.execution_evidence_sha256
    assert run.interruption.prior_success_observation_sha256 == (
        run.state.steps[-1].observation.observation_sha256
    )


def test_interruption_after_failed_tool_keeps_failure_and_pending_binding():
    requests = []
    def source(request):
        requests.append(request)
        if len(requests) == 4:
            assert "RECOVERY_JSON=" in request.user_prompt
            raise TimeoutError("private timeout context")
        return _policy(request)
    def fault(state, action):
        if action.operation == "apply_filter":
            return InjectedToolFailure("synthetic_timeout")
        return None
    run = _run(source, failure_injector=fault)
    assert run.status == "interrupted" and not run.passed
    assert len(run.attempts) == 3
    assert len(run.state.steps) == 2 and run.state.phase == "scoped"
    failure = run.attempts[-1].injected_failure
    assert failure is not None and not run.attempts[-1].executed
    assert run.interruption.prior_failure_sha256 == failure.observation_sha256
    assert run.interruption.pending_request_sha256 == requests[-1].request_sha256
    assert run.interruption.workflow_before_sha256 == run.state.execution_evidence_sha256
    assert run.state.report is None


def test_success_retains_previous_fingerprint_schema():
    run = _run(_policy)
    assert run.status == "completed" and run.passed and run.interruption is None
    legacy = canonical_sha256({
        "record_type": "ResilientMultistepIncidentRun",
        "schema_version": 1, "development_only": True,
        "status": run.status, "termination_reason": run.termination_reason,
        "max_attempts": run.max_attempts, "max_recoveries": run.max_recoveries,
        "workflow_evidence_sha256": run.state.execution_evidence_sha256,
        "attempt_evidence_hashes": [a.attempt_evidence_sha256 for a in run.attempts],
        "passed": run.passed,
    })
    assert run.execution_evidence_sha256 == legacy


def test_same_interruption_replays_deterministically_without_exceptions_in_hash():
    def source1(request):
        raise OSError("private error one")
    def source2(request):
        raise OSError("private error two")
    first, second = _run(source1), _run(source2)
    assert first == second
    assert first.execution_evidence_sha256 == second.execution_evidence_sha256
    assert "private error" not in repr(first)


def test_contract_error_in_capture_source_remains_fail_closed():
    def source(request):
        raise ContractError("capture source contract violated")
    with pytest.raises(ContractError, match="contract violated"):
        _run(source)


def test_assertion_error_in_capture_source_is_not_masked():
    def source(request):
        raise AssertionError("developer invariant failed")
    with pytest.raises(AssertionError, match="invariant failed"):
        _run(source)


def test_keyboard_interrupt_not_masked():
    def source(request):
        raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        _run(source)


def test_capture_replay_integrity_failure_remains_fail_closed():
    saved = []
    def source(request):
        cap = _policy(request)
        saved.append(cap)
        if len(saved) == 2:
            return saved[0]
        return cap
    with pytest.raises(ContractError):
        _run(source)


def test_failure_does_not_turn_into_success_on_budget_boundary():
    def source(request):
        raise TimeoutError("down")
    run = _run(source, max_attempts=1)
    assert run.status == "interrupted" and not run.passed
    assert len(run.attempts) == 0 and run.interruption.attempt_number == 1


def test_typed_interruption_rejects_invalid_metadata_and_result_tampering():
    run = _run(lambda request: (_ for _ in ()).throw(RuntimeError("down")))
    with pytest.raises(ContractError):
        replace(run.interruption, attempt_number=0)
    with pytest.raises(ContractError):
        replace(run.interruption, pending_request_sha256="broken")
    with pytest.raises(ContractError):
        replace(run, status="completed")
    with pytest.raises(ContractError):
        replace(run, interruption=None)
    with pytest.raises(ContractError):
        replace(run, interruption=replace(run.interruption, workflow_before_sha256="a" * 64))


def test_offline_provider_transport_errors_preserve_partial_execution():
    count = [0]
    def transport(endpoint, body, headers, timeout):
        count[0] += 1
        assert endpoint == "https://api.openai.com/v1/responses"
        if count[0] == 3:
            raise TimeoutError("transport failure")
        data = json.loads(body)
        def find_strings(obj):
            if isinstance(obj, str):
                yield obj
            elif isinstance(obj, list):
                for item in obj:
                    yield from find_strings(item)
            elif isinstance(obj, dict):
                for val in obj.values():
                    yield from find_strings(val)
        prompts = [s for s in find_strings(data) if "STATE_JSON=" in s]
        assert len(prompts) == 1
        state = json.loads(prompts[0].split("STATE_JSON=", 1)[1].split("\nRECOVERY_JSON=", 1)[0])
        phase = state["phase"]
        action = ({"ready": {"operation": "load_incidents"},
                   "loaded": {"operation": "scope_service", "service": "payments"}}
                  .get(phase))
        assert action is not None
        return json.dumps({
            "id": f"resp_a510h_b1_{count[0]}", "model": "offline-model",
            "status": "completed",
            "output": [{"type": "message", "role": "assistant", "content": [
                {"type": "output_text", "text": json.dumps(action)},
            ]}],
            "usage": {"input_tokens": 8, "output_tokens": 4, "total_tokens": 12},
        }).encode()
    run = run_injected_openai_resilient_multistep_incident(
        scenario=_scenario(), model="offline-model", run_id="a510h-b1",
        api_key="offline-placeholder-key", transport=transport,
    )
    assert count[0] == 3
    assert run.status == "interrupted" and len(run.attempts) == 2
    assert len(run.state.steps) == 2 and not run.passed
    assert "offline-placeholder-key" not in repr(run)

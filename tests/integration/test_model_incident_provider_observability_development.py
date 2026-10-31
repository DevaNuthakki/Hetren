"""A5-10H-B2: provider usage and local capture duration are observed, not invented."""
from dataclasses import replace
import json

import pytest

from packages.contracts import ContractError
from packages.engines.behavioral.incident_scenario_development import IncidentScenario
from packages.engines.behavioral.model_incident_multistep_recovery_development import (
    InjectedToolFailure, run_resilient_multistep_incident,
)
from packages.engines.behavioral.model_incident_provider_observability_development import (
    CaptureCallObservation, ObservedResilientIncidentRun,
    run_observed_resilient_incident, run_injected_openai_observed_resilient_incident,
)
from packages.model_capture import capture_json_response


def _scenario():
    return IncidentScenario(
        scenario_id="h-b2-observability", target_service="payments",
        minimum_severity=3,
        records=(("INC-P801", "payments", 3), ("INC-P802", "payments", 8),
                 ("INC-P803", "payments", 1), ("INC-A801", "auth", 7)),
    )


def _choice(request, *, wrong=False, recover=False):
    context = json.loads(
        request.user_prompt.split("STATE_JSON=", 1)[1]
        .split("\nRECOVERY_JSON=", 1)[0]
    )
    phase = context["phase"]
    if phase == "ready":
        return {"operation": "load_incidents"}
    if phase == "loaded":
        return {"operation": "scope_service", "service": "payments"}
    if phase == "scoped":
        return {
            "operation": "apply_filter",
            "filter_tool": "strict_severity_filter" if wrong and not (
                recover and "\nRECOVERY_JSON=" in request.user_prompt
            ) else "inclusive_severity_filter",
            "threshold": 3,
        }
    assert phase == "filtered"
    return {"operation": "finalize"}


def _fixture(request):
    return capture_json_response(
        request=request, raw_response_text=json.dumps(_choice(request)),
    )


def _run(source=_fixture, **kwargs):
    return run_observed_resilient_incident(
        scenario=_scenario(), model="offline-model", run_id="a510h-b2",
        capture_source=source, **kwargs,
    )


def _transport(*, usage, failure_at=None, wrong=False, recover=False):
    calls = []
    def fake(endpoint, body, headers, timeout):
        calls.append((endpoint, body, headers, timeout))
        assert endpoint == "https://api.openai.com/v1/responses"
        assert headers["Authorization"] == "Bearer injected-synthetic-key"
        assert timeout == 30.0
        if failure_at == len(calls):
            raise TimeoutError("secret-synthetic-timeout")
        payload = json.loads(body)
        assert payload["store"] is False and payload["stream"] is False
        def strings(obj):
            if isinstance(obj, str):
                yield obj
            elif isinstance(obj, dict):
                for value in obj.values():
                    yield from strings(value)
            elif isinstance(obj, list):
                for value in obj:
                    yield from strings(value)
        prompts = [item for item in strings(payload) if "STATE_JSON=" in item]
        assert len(prompts) == 1
        prompt = prompts[0]
        context = json.loads(prompt.split("STATE_JSON=", 1)[1].split("\nRECOVERY_JSON=", 1)[0])
        phase = context["phase"]
        if phase == "ready":
            action = {"operation": "load_incidents"}
        elif phase == "loaded":
            action = {"operation": "scope_service", "service": "payments"}
        elif phase == "scoped":
            action = {"operation": "apply_filter", "filter_tool": (
                "inclusive_severity_filter" if recover and "\nRECOVERY_JSON=" in prompt
                else "strict_severity_filter" if wrong or recover
                else "inclusive_severity_filter"
            ), "threshold": 3}
        else:
            action = {"operation": "finalize"}
        response = {
            "id": f"resp_fake_{len(calls)}", "model": "offline-model",
            "status": "completed", "output": [{"type": "message", "role": "assistant",
            "content": [{"type": "output_text", "text": json.dumps(action)}]}],
        }
        if usage is not None:
            response["usage"] = usage
        return json.dumps(response).encode("utf-8")
    return fake, calls


def _provider_run(usage=None, **kwargs):
    fake, calls = _transport(usage=usage, **{
        key: kwargs.pop(key) for key in ("failure_at", "wrong", "recover") if key in kwargs
    })
    run = run_injected_openai_observed_resilient_incident(
        scenario=_scenario(), model="offline-model", run_id="a510h-b2",
        api_key="injected-synthetic-key", transport=fake, **kwargs,
    )
    return run, calls


def test_fixture_run_measures_local_calls_without_manufacturing_provider_usage():
    result = _run()
    assert result.run.status == "completed" and result.passed
    assert len(result.calls) == 4 and len(result.run.attempts) == 4
    assert all(call.origin == "offline_capture" for call in result.calls)
    assert all(call.elapsed_ns >= 0 for call in result.calls)
    assert all(call.elapsed_ms >= 0 for call in result.calls)
    assert all(call.input_tokens is None and call.total_tokens is None for call in result.calls)
    assert result.total_input_tokens is None
    assert result.total_output_tokens is None
    assert result.total_reported_tokens is None
    assert result.cost_usd is None
    assert result.local_capture_elapsed_ns == sum(call.elapsed_ns for call in result.calls)
    assert len(result.execution_evidence_sha256) == 64


def test_original_run_fingerprint_unchanged_by_observability_sidecar():
    original = run_resilient_multistep_incident(
        scenario=_scenario(), model="offline-model", run_id="a510h-b2",
        capture_source=_fixture,
    )
    observed = _run()
    assert observed.run == original
    assert observed.run.execution_evidence_sha256 == original.execution_evidence_sha256
    assert observed.execution_evidence_sha256 != original.execution_evidence_sha256


def test_provider_reported_counts_preserved_exactly_on_every_step():
    observed, calls = _provider_run({
        "input_tokens": 11, "output_tokens": 5, "total_tokens": 16,
    })
    assert observed.passed and len(calls) == len(observed.calls) == 4
    assert observed.total_input_tokens == 44
    assert observed.total_output_tokens == 20
    assert observed.total_reported_tokens == 64
    assert all(call.origin == "injected_provider_result" for call in observed.calls)
    assert all(call.reported_model == "offline-model" for call in observed.calls)
    assert all(call.provider_result_sha256 for call in observed.calls)
    assert all(call.capture_sha256 == attempt.capture_sha256 for call, attempt in zip(
        observed.calls, observed.run.attempts,
    ))
    assert observed.cost_usd is None
    assert "injected-synthetic-key" not in repr(observed)
    assert "injected-synthetic-key" not in repr(observed.calls)


def test_true_zero_token_report_is_not_confused_with_unknown():
    observed, _ = _provider_run({
        "input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
    })
    assert observed.total_input_tokens == 0
    assert observed.total_output_tokens == 0
    assert observed.total_reported_tokens == 0
    assert observed.cost_usd is None


def test_missing_provider_usage_kept_unknown_not_zero():
    observed, _ = _provider_run(None)
    assert observed.passed
    assert all(call.input_tokens is None for call in observed.calls)
    assert observed.total_input_tokens is None
    assert observed.total_output_tokens is None
    assert observed.total_reported_tokens is None


def test_partial_provider_usage_preserves_known_and_unknown_fields():
    observed, _ = _provider_run({"input_tokens": 7})
    assert observed.passed
    assert all(call.input_tokens == 7 for call in observed.calls)
    assert observed.total_input_tokens == 28
    assert observed.total_output_tokens is None
    assert observed.total_reported_tokens is None


def test_do_not_derive_provider_reported_total_from_input_plus_output():
    observed, _ = _provider_run({
        "input_tokens": 5, "output_tokens": 3, "total_tokens": 100,
    })
    assert observed.total_input_tokens == 20
    assert observed.total_output_tokens == 12
    assert observed.total_reported_tokens == 400


def test_injected_failure_leaves_per_call_usage_but_no_fake_tool_execution():
    fake, calls = _transport(usage={"input_tokens": 2, "output_tokens": 1,
                                    "total_tokens": 3}, recover=True)
    def injector(state, action):
        if action.operation == "apply_filter" and action.filter_tool == "strict_severity_filter":
            return InjectedToolFailure("temporarily_unavailable")
        return None
    observed = run_injected_openai_observed_resilient_incident(
        scenario=_scenario(), model="offline-model", run_id="a510h-b2",
        api_key="injected-synthetic-key", transport=fake,
        failure_injector=injector,
    )
    assert observed.passed and observed.run.status == "completed"
    assert len(observed.calls) == len(calls) == 5
    assert len(observed.run.state.steps) == 4
    assert len(observed.run.injected_failures) == 1
    assert not observed.run.attempts[2].executed
    assert observed.total_reported_tokens == 15
    assert observed.run.attempts[3].previous_failure_sha256


def test_provider_transport_error_keeps_partial_result_and_unknown_total():
    observed, calls = _provider_run(
        {"input_tokens": 9, "output_tokens": 2, "total_tokens": 11}, failure_at=3,
    )
    assert observed.run.status == "interrupted" and not observed.passed
    assert len(calls) == len(observed.calls) == 3
    assert len(observed.run.attempts) == len(observed.run.state.steps) == 2
    assert len(observed.run.state.trace.events) == 2
    assert observed.calls[-1].outcome == "interrupted"
    assert observed.calls[-1].origin == "capture_source_exception"
    assert observed.calls[-1].request_sha256 == observed.run.interruption.pending_request_sha256
    assert observed.calls[-1].input_tokens is None
    assert observed.total_input_tokens is None
    assert observed.total_reported_tokens is None
    assert "secret-synthetic-timeout" not in repr(observed)


def test_offline_capture_interruption_keeps_previous_call_evidence():
    seen = []
    def source(request):
        seen.append(request.request_sha256)
        if len(seen) == 2:
            raise OSError("private")
        return _fixture(request)
    observed = _run(source)
    assert observed.run.status == "interrupted"
    assert len(observed.calls) == 2 and len(observed.run.attempts) == 1
    assert observed.calls[0].origin == "offline_capture"
    assert observed.calls[1].origin == "capture_source_exception"
    assert observed.total_input_tokens is None
    assert "private" not in repr(observed)


def test_invalid_capture_source_return_type_fails_closed():
    with pytest.raises(ContractError, match="unsupported type"):
        _run(lambda request: {"made_up": "output"})


def test_stale_capture_is_never_accepted_as_observed_usage():
    saved = []
    def source(request):
        result = _fixture(request)
        saved.append(result)
        if len(saved) == 2:
            return saved[0]
        return result
    with pytest.raises(ContractError):
        _run(source)


def test_capture_integrity_tamper_fails_closed():
    def source(request):
        return replace(_fixture(request), raw_response_text='{"operation":"finalize"}')
    with pytest.raises(ContractError):
        _run(source)


def test_developer_contract_error_is_not_disguised_as_provider_interruption():
    def source(request):
        raise ContractError("contract violated")
    with pytest.raises(ContractError, match="contract violated"):
        _run(source)


def test_missing_injected_transport_never_defaults_to_https():
    with pytest.raises(ContractError, match="injected transport"):
        run_injected_openai_observed_resilient_incident(
            scenario=_scenario(), model="offline-model", run_id="a510h-b2",
            api_key="injected-synthetic-key", transport=None,
        )


def test_provider_negative_usage_metadata_is_rejected():
    fake, calls = _transport(usage={"input_tokens": -1})
    with pytest.raises(ContractError):
        run_injected_openai_observed_resilient_incident(
            scenario=_scenario(), model="offline-model", run_id="a510h-b2",
            api_key="injected-synthetic-key", transport=fake,
        )


def test_sidecar_rejects_missing_provider_call_or_tampered_binding():
    observed = _run()
    with pytest.raises(ContractError, match="do not match"):
        replace(observed, calls=observed.calls[:-1])
    with pytest.raises(ContractError, match="mismatch"):
        replace(observed, calls=(replace(observed.calls[0], request_sha256="a" * 64),
                                 *observed.calls[1:]))
    with pytest.raises(ContractError, match="mismatch"):
        replace(observed, calls=(replace(observed.calls[0], capture_sha256="b" * 64),
                                 *observed.calls[1:]))


def test_invalid_observation_provenance_and_metrics_fail_closed():
    original = _run().calls[0]
    with pytest.raises(ContractError):
        replace(original, input_tokens=0)
    with pytest.raises(ContractError):
        replace(original, elapsed_ns=-1)
    with pytest.raises(ContractError):
        replace(original, input_tokens=True)
    with pytest.raises(ContractError):
        replace(original, number=0)
    with pytest.raises(ContractError):
        replace(original, origin="injected_provider_result")
    with pytest.raises(ContractError):
        replace(original, outcome="interrupted")


def test_injected_call_latency_is_local_wall_time_not_server_latency():
    observed, _ = _provider_run({"input_tokens": 2, "output_tokens": 1})
    assert observed.local_capture_elapsed_ns == sum(call.elapsed_ns for call in observed.calls)
    assert all(call.elapsed_ms >= 0 for call in observed.calls)
    assert "not provider-side processing latency" in " ".join(observed.limitations)


def test_failed_evaluation_does_not_count_as_success_with_provider_usage():
    observed, _ = _provider_run({"input_tokens": 2, "output_tokens": 1,
                                 "total_tokens": 3}, wrong=True)
    assert observed.run.status == "completed" and not observed.passed
    assert len(observed.calls) == 4
    assert observed.total_reported_tokens == 12
    assert observed.cost_usd is None

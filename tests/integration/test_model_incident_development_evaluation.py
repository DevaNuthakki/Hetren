"""Synthetic offline controls for evidence-backed evaluation aggregates."""

from dataclasses import replace
import json

import pytest

from packages.contracts import ContractError
from packages.engines.behavioral.incident_scenario_development import IncidentScenario
from packages.engines.behavioral.model_incident_multistep_recovery_development import (
    InjectedToolFailure,
)
from packages.engines.behavioral.model_incident_provider_observability_development import (
    run_observed_resilient_incident,
    run_injected_openai_observed_resilient_incident,
)
from packages.engines.behavioral.model_incident_development_evaluation import (
    IncidentDevelopmentEvaluationInput,
    evaluate_incident_development_cases,
)
from packages.model_capture import capture_json_response


def scenario():
    return IncidentScenario(
        scenario_id="evaluation-c",
        target_service="payments",
        minimum_severity=3,
        records=(
            ("INC-001", "payments", 3),
            ("INC-002", "payments", 7),
            ("INC-003", "payments", 1),
            ("INC-004", "auth", 9),
        ),
    )


def observed_run(mode="correct"):
    seen = []

    def capture(request):
        seen.append(request)
        if mode == "interrupt" and len(seen) == 3:
            raise TimeoutError("private capture interruption")
        if mode == "after_failure_interrupt" and len(seen) == 4:
            raise TimeoutError("private capture interruption")

        prompt = request.user_prompt
        state = json.loads(
            prompt.split("STATE_JSON=", 1)[1].split("\nRECOVERY_JSON=", 1)[0]
        )
        phase = state["phase"]
        if phase == "ready":
            action = {"operation": "load_incidents"}
        elif phase == "loaded":
            action = {"operation": "scope_service", "service": "payments"}
        elif phase == "scoped":
            if mode == "reject":
                action = {"operation": "finalize"}
            else:
                strict = mode in (
                    "wrong", "recover", "repeat", "exhaust", "after_failure_interrupt",
                ) and not (
                    mode in ("recover", "after_failure_interrupt")
                    and "\nRECOVERY_JSON=" in prompt
                )
                action = {
                    "operation": "apply_filter",
                    "filter_tool": (
                        "strict_severity_filter" if strict
                        else "inclusive_severity_filter"
                    ),
                    "threshold": 3,
                }
        else:
            action = {"operation": "finalize"}
        return capture_json_response(
            request=request, raw_response_text=json.dumps(action),
        )

    def fault(state, action):
        if (
            mode in ("recover", "repeat", "exhaust", "after_failure_interrupt")
            and state.phase == "scoped"
            and action.filter_tool == "strict_severity_filter"
        ):
            return InjectedToolFailure("synthetic_timeout")
        return None

    return run_observed_resilient_incident(
        scenario=scenario(),
        model="offline",
        run_id="a510h-c",
        capture_source=capture,
        failure_injector=(
            fault if mode in ("recover", "repeat", "exhaust", "after_failure_interrupt")
            else None
        ),
        max_recoveries=0 if mode == "exhaust" else 1,
        max_attempts=2 if mode == "budget" else 6,
    )


def synthetic_provider_observed_run(usage_by_call):
    """Injected response fixtures only; never real provider usage."""
    calls = []

    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for nested in value.values():
                yield from strings(nested)
        elif isinstance(value, list):
            for nested in value:
                yield from strings(nested)

    def transport(endpoint, body, headers, timeout):
        calls.append(1)
        number = len(calls)

        assert endpoint == "https://api.openai.com/v1/responses"
        assert headers["Authorization"] == "Bearer synthetic-fixture-only"
        assert timeout == 30.0

        payload = json.loads(body)

        assert payload["store"] is False
        assert payload["stream"] is False
        assert payload["model"] == "offline"

        prompts = [
            value
            for value in strings(payload)
            if "STATE_JSON=" in value
        ]

        assert len(prompts) == 1

        context = json.loads(
            prompts[0].split("STATE_JSON=", 1)[1]
            .split("\nRECOVERY_JSON=", 1)[0]
        )

        phase = context["phase"]

        if phase == "ready":
            action = {"operation": "load_incidents"}
        elif phase == "loaded":
            action = {
                "operation": "scope_service",
                "service": "payments",
            }
        elif phase == "scoped":
            action = {
                "operation": "apply_filter",
                "filter_tool": "inclusive_severity_filter",
                "threshold": 3,
            }
        else:
            assert phase == "filtered"
            action = {"operation": "finalize"}

        response = {
            "id": f"resp_synthetic_evaluation_{number}",
            "model": "offline",
            "status": "completed",
            "output": [{
                "type": "message",
                "role": "assistant",
                "content": [{
                    "type": "output_text",
                    "text": json.dumps(action),
                }],
            }],
        }

        if number in usage_by_call:
            response["usage"] = usage_by_call[number]

        return json.dumps(response).encode("utf-8")

    observed = run_injected_openai_observed_resilient_incident(
        scenario=scenario(),
        model="offline",
        run_id="a510h-c",
        api_key="synthetic-fixture-only",
        transport=transport,
    )

    assert len(calls) == len(observed.calls)
    assert all(
        call.origin == "injected_provider_result"
        for call in observed.calls
    )

    return observed


def case(case_id, mode="correct", observed=None):
    return IncidentDevelopmentEvaluationInput(
        case_id=case_id,
        scenario=scenario(), model="offline",
        observed=observed if observed is not None else observed_run(mode),
    )


def evaluate(*cases):
    return evaluate_incident_development_cases(
        report_id="development-controls-c1", cases=tuple(cases),
    )


def test_eight_case_matrix_and_explicit_denominators():
    report = evaluate(
        case("correct", "correct"), case("wrong", "wrong"),
        case("recovery", "recover"), case("repeat", "repeat"),
        case("exhaust", "exhaust"), case("budget", "budget"),
        case("interrupt", "interrupt"), case("reject", "reject"),
    )
    summary = report.summary
    assert summary.denominator_cases == 8
    assert summary.correct_cases == 2
    assert summary.completed_cases == 3
    assert summary.completed_incorrect_cases == 1
    assert summary.rejected_cases == 2
    assert summary.interrupted_cases == 1
    assert summary.recovery_exhausted_cases == 1
    assert summary.budget_exhausted_cases == 1
    assert summary.cases_with_injected_failures == 3
    assert summary.recovered_correctly_cases == 1
    assert summary.repeated_failed_action_rejections == 1
    assert summary.interrupted_captures == 1
    assert summary.attempts == sum(item.attempts for item in report.cases)
    assert summary.executed_actions == sum(item.executed_actions for item in report.cases)
    assert report.canonical_payload()["dataset_kind"] == "synthetic_development"
    assert len(report.report_sha256) == 64


def test_completed_wrong_is_not_correct():
    result = evaluate(case("wrong", "wrong")).cases[0]
    assert result.completed and not result.correct
    assert result.attempts == 4 and result.executed_actions == 4


def test_failed_attempt_is_not_executed_and_recovery_counts_only_correct():
    result = evaluate(case("recovery", "recover")).cases[0]
    assert result.status == "completed" and result.correct
    assert result.injected_failures == 1 and result.recovered_correctly
    assert result.attempts == 5 and result.executed_actions == 4


def test_repeated_failed_action_is_not_called_general_retry_metric():
    result = evaluate(case("repeat", "repeat")).cases[0]
    assert result.status == "rejected"
    assert result.repeated_failed_action_rejections == 1
    assert not result.recovered_correctly


def test_interruption_after_failure_does_not_count_recovery():
    result = evaluate(case("interrupted", "after_failure_interrupt")).cases[0]
    assert result.status == "interrupted"
    assert result.injected_failures == 1
    assert result.interrupted_captures == 1
    assert not result.recovered_correctly
    assert result.capture_calls == result.attempts + 1


def test_unknown_token_usage_stays_unknown():
    report = evaluate(case("unknown"))
    score = report.cases[0]
    assert score.complete_reported_tokens is None
    assert score.known_call_token_sum is None
    assert report.summary.complete_reported_tokens is None
    assert report.summary.known_call_token_sum is None
    assert score.calls_without_reported_tokens == score.capture_calls
    assert score.local_capture_elapsed_ns >= 0


def test_partial_token_observation_not_reported_as_complete():
    observed = synthetic_provider_observed_run({
        1: {
            "input_tokens": 8,
            "output_tokens": 2,
            "total_tokens": 10,
        },
    })

    score = evaluate(
        case("partial", observed=observed)
    ).cases[0]

    assert score.calls_with_reported_tokens == 1
    assert score.calls_without_reported_tokens == 3
    assert score.known_call_token_sum == 10
    assert score.complete_reported_tokens is None


def test_offline_capture_rejects_fabricated_provider_usage():
    observed = observed_run()

    with pytest.raises(
        ContractError,
        match="offline capture cannot report provider usage",
    ):
        replace(
            observed.calls[0],
            input_tokens=8,
            output_tokens=2,
            total_tokens=10,
        )


def test_complete_provider_tokens_only_with_full_coverage():
    observed = synthetic_provider_observed_run({
        index: {
            "input_tokens": 4,
            "output_tokens": 1,
            "total_tokens": 5,
        }
        for index in range(1, 5)
    })

    score = evaluate(
        case("complete", observed=observed)
    ).cases[0]

    assert score.complete_reported_tokens == 5 * len(observed.calls)
    assert score.calls_without_reported_tokens == 0
    assert score.calls_with_reported_tokens == len(observed.calls)


def test_mixed_case_tokens_are_not_claimed_as_full_total():
    complete = synthetic_provider_observed_run({
        index: {
            "input_tokens": 2,
            "output_tokens": 1,
            "total_tokens": 3,
        }
        for index in range(1, 5)
    })

    report = evaluate(
        case("known", observed=complete),
        case("unknown", "wrong"),
    )

    assert (
        report.summary.known_call_token_sum
        == 3 * len(complete.calls)
    )
    assert report.summary.complete_reported_tokens is None


def test_same_evidence_produces_same_digest():
    inputs = (case("one"), case("two", "recover"))
    first = evaluate(*inputs)
    second = evaluate(*inputs)
    assert first.report_sha256 == second.report_sha256
    assert first.canonical_payload() == second.canonical_payload()
    assert first.report_sha256 != evaluate(inputs[1], inputs[0]).report_sha256


def test_duplicate_case_id_rejected():
    selected = case("same")
    with pytest.raises(ContractError):
        evaluate(selected, selected)


@pytest.mark.parametrize("inputs", [(), [], "invalid", (object(),)])
def test_invalid_case_collections_rejected(inputs):
    with pytest.raises(ContractError):
        evaluate_incident_development_cases(
            report_id="invalid-batch", cases=inputs,
        )


def test_invalid_identifiers_rejected():
    with pytest.raises(ContractError):
        replace(case("valid"), case_id="Wrong Case")
    with pytest.raises(ContractError):
        evaluate_incident_development_cases(
            report_id="report invalid", cases=(case("valid"),),
        )


def test_wrong_model_scenario_and_tampered_source_fail_closed():
    valid = case("verified")
    with pytest.raises(ContractError):
        evaluate(replace(valid, model="different-model"))
    with pytest.raises(ContractError):
        evaluate(replace(valid, scenario=replace(scenario(), scenario_id="other")))
    bad_state = replace(valid.observed.run.state, selected_rows=())
    bad_run = replace(valid.observed.run, state=bad_state)
    with pytest.raises(ContractError):
        evaluate(replace(valid, observed=replace(valid.observed, run=bad_run)))


def test_evidence_links_and_limitations():
    result = evaluate(case("good"))
    score = result.cases[0]
    assert len(score.case_evidence_sha256) == 64
    assert len(score.timeline_sha256) == 64
    assert score.observed_sha256 != score.timeline_sha256
    assert "synthetic" in result.limitations[0]
    assert "cost" in " ".join(result.limitations)

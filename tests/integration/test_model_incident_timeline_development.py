"""Offline regression controls for incident timeline reconstruction."""

from dataclasses import replace
import json

import pytest

from packages.contracts import ContractError
from packages.engines.behavioral.incident_scenario_development import (
    IncidentScenario,
)
from packages.engines.behavioral.model_incident_multistep_recovery_development import (
    InjectedToolFailure,
)
from packages.engines.behavioral.model_incident_provider_observability_development import (
    run_observed_resilient_incident,
)
from packages.engines.behavioral.model_incident_timeline_development import (
    reconstruct_incident_timeline,
)
from packages.model_capture import capture_json_response


def scenario():
    return IncidentScenario(
        scenario_id="timeline-b3",
        target_service="payments",
        minimum_severity=3,
        records=(
            ("INC-001", "payments", 3),
            ("INC-002", "payments", 7),
            ("INC-003", "payments", 1),
            ("INC-004", "auth", 9),
        ),
    )


def capture(request, *, wrong=False, recover=False):
    prompt = request.user_prompt

    context = json.loads(
        prompt.split("STATE_JSON=", 1)[1]
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
        strict = wrong and not (
            recover and "\nRECOVERY_JSON=" in prompt
        )

        action = {
            "operation": "apply_filter",
            "filter_tool": (
                "strict_severity_filter"
                if strict
                else "inclusive_severity_filter"
            ),
            "threshold": 3,
        }

    else:
        action = {"operation": "finalize"}

    return capture_json_response(
        request=request,
        raw_response_text=json.dumps(action),
    )


def run(
    *,
    wrong=False,
    recover=False,
    interrupt=None,
    max_recoveries=1,
    max_attempts=6,
    bad=False,
):
    seen = []

    def source(request):
        seen.append(request)

        if interrupt == len(seen):
            raise TimeoutError("private timeout")

        if bad and len(seen) == 3:
            return capture_json_response(
                request=request,
                raw_response_text='{"operation":"finalize"}',
            )

        return capture(
            request,
            wrong=wrong,
            recover=recover,
        )

    def fault(state, action):
        if (
            recover
            and state.phase == "scoped"
            and action.filter_tool == "strict_severity_filter"
        ):
            return InjectedToolFailure("synthetic_timeout")

        return None

    return run_observed_resilient_incident(
        scenario=scenario(),
        model="offline",
        run_id="a510h-b3",
        capture_source=source,
        failure_injector=fault if recover else None,
        max_recoveries=max_recoveries,
        max_attempts=max_attempts,
    )


def timeline(observed):
    return reconstruct_incident_timeline(
        scenario=scenario(),
        model="offline",
        observed=observed,
    )


def test_successful_execution_and_original_evidence():
    observed = run()
    previous_sha = observed.execution_evidence_sha256

    result = timeline(observed)

    assert [event.kind for event in result.events] == (
        ["tool_executed"] * 3 + ["workflow_finalized"]
    )

    assert result.status == "completed"
    assert result.passed

    assert result.recovery_sha256 == (
        observed.run.execution_evidence_sha256
    )

    assert result.original_trace_sha256 == (
        observed.run.state.trace.trace_sha256
    )

    assert observed.execution_evidence_sha256 == previous_sha
    assert len(result.execution_evidence_sha256) == 64


def test_completed_workflow_can_fail_evaluation():
    result = timeline(run(wrong=True))

    assert result.status == "completed"
    assert not result.passed
    assert result.events[-1].kind == "workflow_finalized"


def test_failure_never_advances_workflow():
    observed = run(wrong=True, recover=True)
    result = timeline(observed)

    assert result.passed

    assert [event.kind for event in result.events] == [
        "tool_executed",
        "tool_executed",
        "tool_failed",
        "tool_executed",
        "workflow_finalized",
    ]

    assert len(observed.run.state.trace.events) == 4

    assert (
        result.events[2].workflow_before_sha256
        == result.events[2].workflow_after_sha256
    )

    assert result.events[2].failure_sha256 is not None


def test_recovery_exhaustion():
    result = timeline(
        run(
            wrong=True,
            recover=True,
            max_recoveries=0,
        )
    )

    assert result.status == "recovery_exhausted"
    assert not result.passed
    assert result.events[-1].kind == "tool_failed"


def test_attempt_budget_exhaustion():
    result = timeline(run(max_attempts=2))

    assert result.status == "budget_exhausted"
    assert len(result.events) == 2
    assert not result.passed


def test_rejected_action_not_executed():
    result = timeline(run(bad=True))

    assert result.status == "rejected"
    assert not result.passed
    assert result.events[-1].kind == "action_rejected"


def test_interrupted_capture_not_executed():
    observed = run(interrupt=3)
    result = timeline(observed)

    assert result.status == "interrupted"
    assert not result.passed

    assert (
        result.events[-1].kind
        == "capture_interrupted"
    )

    assert result.events[-1].capture_sha256 is None

    assert (
        result.events[-1].workflow_before_sha256
        == result.events[-1].workflow_after_sha256
    )

    assert result.reported_total_tokens is None
    assert len(observed.run.state.steps) == 2


def test_interruption_after_failure():
    observed = run(
        wrong=True,
        recover=True,
        interrupt=4,
    )

    result = timeline(observed)

    assert result.status == "interrupted"

    assert [event.kind for event in result.events] == [
        "tool_executed",
        "tool_executed",
        "tool_failed",
        "capture_interrupted",
    ]


def test_tampered_request_rejected():
    observed = run()

    changed = replace(
        observed.run.attempts[0],
        request_sha256="a" * 64,
    )

    forged_run = replace(
        observed.run,
        attempts=(
            changed,
            *observed.run.attempts[1:],
        ),
    )

    with pytest.raises(ContractError):
        timeline(replace(observed, run=forged_run))


def test_reordered_attempts_rejected():
    observed = run()
    attempts = observed.run.attempts

    forged_run = replace(
        observed.run,
        attempts=(
            attempts[1],
            attempts[0],
            *attempts[2:],
        ),
    )

    with pytest.raises(ContractError):
        timeline(replace(observed, run=forged_run))


def test_tampered_final_state_rejected():
    observed = run()

    changed_state = replace(
        observed.run.state,
        selected_rows=(),
    )

    with pytest.raises(ContractError):
        timeline(
            replace(
                observed,
                run=replace(
                    observed.run,
                    state=changed_state,
                ),
            )
        )


def test_wrong_scenario_and_model_rejected():
    observed = run()

    with pytest.raises(ContractError):
        reconstruct_incident_timeline(
            scenario=scenario(),
            model="different-model",
            observed=observed,
        )

    other = replace(
        scenario(),
        scenario_id="different",
    )

    with pytest.raises(ContractError):
        reconstruct_incident_timeline(
            scenario=other,
            model="offline",
            observed=observed,
        )


def test_tampered_failure_evidence_rejected():
    observed = run(wrong=True, recover=True)
    attempts = observed.run.attempts
    failed = attempts[2]

    changed = replace(
        failed,
        injected_failure=replace(
            failed.injected_failure,
            failure_code="fabricated",
        ),
    )

    forged_run = replace(
        observed.run,
        attempts=(
            *attempts[:2],
            changed,
            *attempts[3:],
        ),
    )

    with pytest.raises(ContractError):
        timeline(replace(observed, run=forged_run))


def test_chronological_event_chain():
    result = timeline(
        run(
            wrong=True,
            recover=True,
        )
    )

    for index, event in enumerate(result.events):
        assert event.sequence == index + 1

        assert event.previous_event_sha256 == (
            None
            if index == 0
            else result.events[index - 1].event_sha256
        )

        assert len(event.event_sha256) == 64

    assert (
        result.execution_evidence_sha256
        != result.recovery_sha256
    )

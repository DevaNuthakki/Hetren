"""Offline tests for model-driven incident filtering and replay."""

from dataclasses import replace
import json

import pytest

from environments.agent.incident_triage import (
    IncidentFaultMode,
    expected_incident_ids,
    incident_triage_task_spec,
    run_configured_incident_triage,
    run_incident_triage,
)
from packages.contracts import ContractError
from packages.core.hetren_diagnosis.contracts import (
    ContractError as DiagnosisContractError,
    EventKind,
)
from packages.engines.behavioral.model_incident_triage_agent import (
    build_incident_triage_request,
    run_captured_incident_triage,
)
from packages.model_capture import capture_json_response


def _source(proposal, model="offline-model"):
    request = build_incident_triage_request(model=model)
    capture = capture_json_response(
        request=request,
        raw_response_text=json.dumps(proposal, sort_keys=True),
    )
    return request, capture


def _run(proposal, run_id="a510-replay"):
    request, capture = _source(proposal)
    run = run_captured_incident_triage(
        request=request,
        capture=capture,
        run_id=run_id,
    )
    assert run.request_sha256 == request.request_sha256
    assert run.capture_sha256 == capture.capture_sha256
    assert run.trace.run_id == run.run_id
    assert run.trace.events[0].kind is EventKind.DECISION
    return run


def test_existing_incident_task_contract():
    service, threshold, incidents = incident_triage_task_spec()
    assert service == "payments"
    assert threshold == 3
    assert len(incidents) == 5
    assert expected_incident_ids() == (
        "INC-1001", "INC-1002", "INC-1004",
    )


def test_configured_execution_matches_existing_fault_environment():
    modes = (
        (
            IncidentFaultMode.FILTER_TOOL_SELECTION,
            "strict_severity_filter",
            3,
        ),
        (
            IncidentFaultMode.THRESHOLD_TRANSFORMATION,
            "inclusive_severity_filter",
            4,
        ),
    )
    for mode, tool, threshold in modes:
        legacy = run_incident_triage(
            mode, run_id="a510-equivalence",
        )
        configured = run_configured_incident_triage(
            tool_name=tool,
            threshold=threshold,
            run_id="a510-equivalence",
        )
        assert configured == legacy
        assert (
            configured.execution_evidence_sha256
            == legacy.execution_evidence_sha256
        )


def test_valid_model_action_executes_correct_filter():
    run = _run({
        "tool": "inclusive_severity_filter",
        "threshold": 3,
    })
    assert run.status == "executed"
    assert run.rejection_reason is None
    assert run.passed
    assert run.environment_run.report.incident_ids == (
        expected_incident_ids()
    )
    assert run.environment_run.report.count == 3
    assert any(
        event.kind is EventKind.TOOL_CALL
        for event in run.trace.events
    )


@pytest.mark.parametrize(
    "proposal,expected_ids",
    [
        (
            {"tool": "strict_severity_filter", "threshold": 3},
            ("INC-1001", "INC-1004"),
        ),
        (
            {"tool": "inclusive_severity_filter", "threshold": 4},
            ("INC-1001", "INC-1004"),
        ),
        (
            {"tool": "inclusive_severity_filter", "threshold": 2},
            ("INC-1001", "INC-1002", "INC-1004", "INC-1005"),
        ),
    ],
)
def test_wrong_actions_execute_but_fail_independent_evaluation(
    proposal, expected_ids,
):
    run = _run(proposal)
    assert run.status == "executed"
    assert not run.passed
    assert run.environment_run.report.incident_ids == expected_ids
    assert run.environment_run.report.incident_ids != (
        expected_incident_ids()
    )


@pytest.mark.parametrize(
    "proposal,reason",
    [
        (
            {"tool": "shell", "threshold": 3},
            "unsupported_tool",
        ),
        (
            {"tool": "inclusive_severity_filter", "threshold": True},
            "invalid_threshold",
        ),
        (
            {"tool": "inclusive_severity_filter", "threshold": -1},
            "invalid_threshold",
        ),
        (
            {"tool": "inclusive_severity_filter", "threshold": 999},
            "invalid_threshold",
        ),
        (
            {"tool": "inclusive_severity_filter", "threshold": "3"},
            "invalid_threshold",
        ),
        (
            {"tool": "inclusive_severity_filter"},
            "invalid_proposal_shape",
        ),
        (
            {
                "tool": "inclusive_severity_filter",
                "threshold": 3,
                "incident_ids": ["INC-1001"],
            },
            "invalid_proposal_shape",
        ),
    ],
)
def test_invalid_model_actions_never_execute(proposal, reason):
    run = _run(proposal)
    assert run.status == "rejected"
    assert run.rejection_reason == reason
    assert run.environment_run is None
    assert not run.passed
    assert len(run.trace.events) == 2
    assert all(
        event.kind is not EventKind.TOOL_CALL
        for event in run.trace.events
    )


@pytest.mark.parametrize(
    "tool,threshold",
    [
        ("shell", 3),
        ("inclusive_severity_filter", True),
        ("inclusive_severity_filter", -1),
        ("inclusive_severity_filter", 999),
    ],
)
def test_configured_environment_rejects_invalid_inputs(
    tool, threshold,
):
    with pytest.raises(DiagnosisContractError):
        run_configured_incident_triage(
            tool_name=tool,
            threshold=threshold,
            run_id="a510-invalid",
        )


def test_capture_tampering_rejected_before_tool_execution():
    request, capture = _source({
        "tool": "strict_severity_filter",
        "threshold": 3,
    })
    tampered = replace(
        capture,
        raw_response_text=json.dumps({
            "tool": "inclusive_severity_filter",
            "threshold": 3,
        }),
    )
    with pytest.raises(ContractError):
        run_captured_incident_triage(
            request=request,
            capture=tampered,
            run_id="a510-tampered",
        )


def test_cross_request_capture_is_rejected():
    _, capture = _source({
        "tool": "inclusive_severity_filter",
        "threshold": 3,
    })
    different_request = build_incident_triage_request(
        model="another-offline-model",
    )
    with pytest.raises(ContractError):
        run_captured_incident_triage(
            request=different_request,
            capture=capture,
            run_id="a510-other",
        )


def test_replay_determinism_and_distinct_run_identity():
    proposal = {
        "tool": "inclusive_severity_filter",
        "threshold": 3,
    }

    first = _run(proposal, "a510-first")
    second = _run(proposal, "a510-first")
    third = _run(proposal, "a510-second")

    assert first == second
    assert (
        first.execution_evidence_sha256
        == second.execution_evidence_sha256
    )
    assert first.execution_evidence_sha256 != (
        third.execution_evidence_sha256
    )
    assert first.environment_run.trace.events


def test_task_request_is_bounded_and_uses_actual_fixture():
    request = build_incident_triage_request(
        model="offline-model",
    )
    assert request.provider == "openai"
    assert request.response_schema["required"] == [
        "tool", "threshold",
    ]
    assert request.response_schema["additionalProperties"] is False
    assert request.response_schema["properties"]["tool"]["enum"] == [
        "inclusive_severity_filter",
        "strict_severity_filter",
    ]
    assert "INC-1001" in request.user_prompt
    assert "INC-1005" in request.user_prompt
    assert request.generation_parameters == {}


def test_agent_exposes_no_shell_or_network_tool():
    tools = build_incident_triage_request(
        model="offline-model",
    ).response_schema["properties"]["tool"]["enum"]
    assert all(
        "shell" not in name
        and "filesystem" not in name
        and "network" not in name
        for name in tools
    )

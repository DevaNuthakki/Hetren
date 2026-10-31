"""Offline scenario-bound model actions and legacy parity tests."""

from dataclasses import replace
import json

import pytest

from environments.agent.incident_triage import (
    IncidentFaultMode,
    filter_incident_rows,
    run_configured_incident_triage,
    run_incident_triage,
)
from packages.contracts import ContractError
from packages.core.hetren_diagnosis.contracts import EventKind
from packages.engines.behavioral.incident_scenario_development import (
    IncidentScenario,
    build_scenario_incident_request,
    reference_expected_incident_ids,
)
from packages.engines.behavioral.model_incident_scenario_agent import (
    run_captured_scenario_incident,
)
from packages.model_capture import capture_json_response


def _payments():
    return IncidentScenario(
        scenario_id="payments-b2",
        target_service="payments",
        minimum_severity=3,
        records=(
            ("INC-P001", "payments", 3),
            ("INC-P002", "payments", 5),
            ("INC-P003", "payments", 2),
            ("INC-A001", "auth", 5),
        ),
    )


def _auth():
    return IncidentScenario(
        scenario_id="auth-b2",
        target_service="auth",
        minimum_severity=2,
        records=(
            ("INC-A101", "auth", 2),
            ("INC-A102", "auth", 1),
            ("INC-A103", "auth", 7),
            ("INC-P101", "payments", 8),
        ),
    )


def _notifications():
    return IncidentScenario(
        scenario_id="notifications-b2",
        target_service="notifications",
        minimum_severity=9,
        records=(
            ("INC-N101", "notifications", 1),
            ("INC-N102", "notifications", 4),
            ("INC-N103", "notifications", 6),
            ("INC-A201", "auth", 9),
        ),
    )


def _source(scenario, proposal):
    request = build_scenario_incident_request(
        scenario=scenario,
        model="offline-model",
    )
    capture = capture_json_response(
        request=request,
        raw_response_text=json.dumps(
            proposal, sort_keys=True,
        ),
    )
    return request, capture


def _run(scenario, proposal, run_id="a510fb2"):
    request, capture = _source(scenario, proposal)
    run = run_captured_scenario_incident(
        scenario=scenario,
        request=request,
        capture=capture,
        run_id=run_id,
    )

    assert run.scenario_sha256 == scenario.scenario_sha256
    assert run.request_sha256 == request.request_sha256
    assert run.capture_sha256 == capture.capture_sha256
    assert run.trace.run_id == run_id
    assert run.trace.events[0].kind is EventKind.DECISION

    return run


@pytest.mark.parametrize(
    "factory,threshold,expected",
    [
        (_payments, 3, ("INC-P001", "INC-P002")),
        (_auth, 2, ("INC-A101", "INC-A103")),
        (_notifications, 9, ()),
    ],
)
def test_correct_actions_execute_distinct_scenarios(
    factory, threshold, expected,
):
    scenario = factory()

    result = _run(scenario, {
        "tool": "inclusive_severity_filter",
        "threshold": threshold,
    })

    assert result.status == "executed"
    assert result.passed
    assert result.report.incident_ids == expected
    assert result.report.count == len(expected)
    assert result.evaluation.expected_ids == (
        reference_expected_incident_ids(scenario)
    )
    assert result.evaluation.passed
    assert len(result.trace.events) == 3
    assert result.trace.events[1].kind is EventKind.TOOL_CALL
    assert len(result.execution_evidence_sha256) == 64


@pytest.mark.parametrize(
    "scenario,proposal,actual",
    [
        (
            _payments(),
            {"tool": "strict_severity_filter", "threshold": 3},
            ("INC-P002",),
        ),
        (
            _auth(),
            {"tool": "inclusive_severity_filter", "threshold": 3},
            ("INC-A103",),
        ),
        (
            _auth(),
            {"tool": "strict_severity_filter", "threshold": 3},
            ("INC-A103",),
        ),
        (
            _payments(),
            {"tool": "inclusive_severity_filter", "threshold": 2},
            ("INC-P001", "INC-P002", "INC-P003"),
        ),
    ],
)
def test_incorrect_actions_execute_but_fail_reference_evaluation(
    scenario, proposal, actual,
):
    result = _run(scenario, proposal)

    assert result.status == "executed"
    assert not result.passed
    assert result.report.incident_ids == actual
    assert not result.evaluation.passed
    assert result.evaluation.expected_ids != actual
    assert result.trace.events[1].kind is EventKind.TOOL_CALL


@pytest.mark.parametrize(
    "proposal,reason",
    [
        ({"tool": "shell", "threshold": 3}, "unsupported_tool"),
        (
            {"tool": "inclusive_severity_filter", "threshold": True},
            "invalid_threshold",
        ),
        (
            {"tool": "inclusive_severity_filter", "threshold": -1},
            "invalid_threshold",
        ),
        (
            {"tool": "inclusive_severity_filter", "threshold": 11},
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
                "incident_ids": ["INC-FAKE"],
            },
            "invalid_proposal_shape",
        ),
    ],
)
def test_invalid_model_action_never_executes(proposal, reason):
    result = _run(_payments(), proposal)

    assert result.status == "rejected"
    assert result.rejection_reason == reason
    assert result.report is None
    assert result.evaluation is None
    assert not result.passed
    assert len(result.trace.events) == 2
    assert all(
        event.kind is not EventKind.TOOL_CALL
        for event in result.trace.events
    )


def test_cross_scenario_request_and_capture_rejected():
    scenario_a = _payments()
    scenario_b = _auth()

    request, capture = _source(
        scenario_a,
        {"tool": "inclusive_severity_filter", "threshold": 3},
    )

    with pytest.raises(ContractError, match="exact scenario"):
        run_captured_scenario_incident(
            scenario=scenario_b,
            request=request,
            capture=capture,
            run_id="a510-cross",
        )


def test_capture_tampering_rejected():
    scenario = _payments()

    request, capture = _source(
        scenario,
        {"tool": "strict_severity_filter", "threshold": 3},
    )

    changed = replace(
        capture,
        raw_response_text=json.dumps({
            "tool": "inclusive_severity_filter",
            "threshold": 3,
        }),
    )

    with pytest.raises(ContractError):
        run_captured_scenario_incident(
            scenario=scenario,
            request=request,
            capture=changed,
            run_id="a510-tamper",
        )


def test_changed_scenario_records_change_identity_and_result():
    original = _payments()
    altered = replace(
        original,
        records=original.records + (
            ("INC-P004", "payments", 7),
        ),
    )
    proposal = {
        "tool": "inclusive_severity_filter",
        "threshold": 3,
    }

    first = _run(original, proposal)
    second = _run(altered, proposal)

    assert first.scenario_sha256 != second.scenario_sha256
    assert first.request_sha256 != second.request_sha256
    assert first.execution_evidence_sha256 != (
        second.execution_evidence_sha256
    )
    assert first.report.incident_ids != second.report.incident_ids
    assert first.passed and second.passed


def test_identical_capture_is_deterministic():
    scenario = _payments()
    proposal = {
        "tool": "inclusive_severity_filter",
        "threshold": 3,
    }

    first = _run(scenario, proposal, run_id="a510-repeat")
    second = _run(scenario, proposal, run_id="a510-repeat")

    assert first == second
    assert first.execution_evidence_sha256 == (
        second.execution_evidence_sha256
    )


def test_run_identity_changes_execution_evidence():
    scenario = _auth()
    proposal = {
        "tool": "inclusive_severity_filter",
        "threshold": 2,
    }

    first = _run(scenario, proposal, run_id="a510-one")
    second = _run(scenario, proposal, run_id="a510-two")

    assert first.capture_sha256 == second.capture_sha256
    assert first.execution_evidence_sha256 != (
        second.execution_evidence_sha256
    )


def test_shared_filter_preserves_legacy_execution_bytes():
    examples = (
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

    for fault, tool, threshold in examples:
        legacy = run_incident_triage(
            fault,
            run_id="a510-legacy",
        )
        configured = run_configured_incident_triage(
            tool_name=tool,
            threshold=threshold,
            run_id="a510-legacy",
        )

        assert legacy == configured
        assert legacy.execution_evidence_sha256 == (
            configured.execution_evidence_sha256
        )


def test_shared_filter_enforces_service_scope_and_order():
    records = (
        ("INC-X001", "payments", 4),
        ("INC-X002", "auth", 9),
        ("INC-X003", "payments", 3),
        ("INC-X004", "payments", 5),
    )

    service_rows, selected = filter_incident_rows(
        records=records,
        target_service="payments",
        tool_name="inclusive_severity_filter",
        threshold=3,
    )

    assert tuple(row[0] for row in service_rows) == (
        "INC-X001", "INC-X003", "INC-X004",
    )
    assert tuple(row[0] for row in selected) == (
        "INC-X001", "INC-X003", "INC-X004",
    )


def test_evaluation_distinct_from_execution_completion():
    result = _run(_payments(), {
        "tool": "strict_severity_filter",
        "threshold": 3,
    })

    assert result.status == "executed"
    assert result.report is not None
    assert result.evaluation is not None
    assert not result.evaluation.passed


def test_result_does_not_claim_scientific_verification():
    result = _run(_payments(), {
        "tool": "inclusive_severity_filter",
        "threshold": 3,
    })

    limitations = " ".join(result.limitations)

    assert "synthetic development" in limitations
    assert "not fresh model inference" in limitations
    assert "no independent scientific verification" in limitations
    assert "no evidence of generalization" in limitations

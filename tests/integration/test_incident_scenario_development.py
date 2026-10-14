"""Independent development-oracle and scenario identity tests."""

from dataclasses import FrozenInstanceError, replace
import inspect

import pytest

from environments.agent.incident_triage import (
    TriageReport,
    expected_incident_ids,
    incident_triage_task_spec,
)
from packages.contracts import ContractError
from packages.engines.behavioral.incident_scenario_development import (
    ALLOWED_TOOLS,
    IncidentScenario,
    build_scenario_incident_request,
    evaluate_incident_scenario,
    reference_expected_incident_ids,
)


def _payments():
    return IncidentScenario(
        scenario_id="payments-dev",
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
        scenario_id="auth-dev",
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
        scenario_id="notifications-dev",
        target_service="notifications",
        minimum_severity=4,
        records=(
            ("INC-N101", "notifications", 1),
            ("INC-N102", "notifications", 4),
            ("INC-N103", "notifications", 6),
            ("INC-A201", "auth", 9),
        ),
    )


@pytest.mark.parametrize(
    "factory,expected",
    [
        (_payments, ("INC-P001", "INC-P002")),
        (_auth, ("INC-A101", "INC-A103")),
        (_notifications, ("INC-N102", "INC-N103")),
    ],
)
def test_distinct_development_scenarios_have_correct_oracle(
    factory, expected,
):
    scenario = factory()

    assert reference_expected_incident_ids(scenario) == expected

    report = TriageReport(
        service=scenario.target_service,
        incident_ids=expected,
        count=len(expected),
    )

    evaluation = evaluate_incident_scenario(
        scenario=scenario,
        report=report,
    )

    assert evaluation.passed
    assert evaluation.expected_ids == expected
    assert evaluation.scenario_sha256 == scenario.scenario_sha256
    assert len(evaluation.evaluation_evidence_sha256) == 64


def test_original_five_record_task_remains_consistent():
    service, threshold, records = incident_triage_task_spec()

    scenario = IncidentScenario(
        scenario_id="legacy-parity",
        target_service=service,
        minimum_severity=threshold,
        records=records,
    )

    assert reference_expected_incident_ids(scenario) == (
        expected_incident_ids()
    )


def test_oracle_catches_strict_filter_boundary_error():
    scenario = _payments()

    incorrect = TriageReport(
        service="payments",
        incident_ids=("INC-P002",),
        count=1,
    )

    evaluation = evaluate_incident_scenario(
        scenario=scenario,
        report=incorrect,
    )

    assert not evaluation.passed
    assert evaluation.expected_ids == (
        "INC-P001", "INC-P002",
    )


def test_oracle_detects_wrong_service_and_extra_incidents():
    scenario = _auth()

    reports = (
        TriageReport(
            "payments",
            ("INC-A101", "INC-A103"),
            2,
        ),
        TriageReport(
            "auth",
            ("INC-A101", "INC-A103", "INC-P101"),
            3,
        ),
        TriageReport(
            "auth",
            ("INC-A101", "INC-A103"),
            1,
        ),
    )

    assert all(
        not evaluate_incident_scenario(
            scenario=scenario,
            report=report,
        ).passed
        for report in reports
    )


def test_reference_oracle_can_correctly_return_empty_result():
    scenario = replace(
        _payments(),
        minimum_severity=9,
    )

    assert reference_expected_incident_ids(scenario) == ()

    evaluation = evaluate_incident_scenario(
        scenario=scenario,
        report=TriageReport("payments", (), 0),
    )

    assert evaluation.passed


def test_scenario_identity_binds_records_and_threshold():
    original = _payments()
    changed_threshold = replace(
        original,
        minimum_severity=4,
    )
    changed_records = replace(
        original,
        records=original.records + (
            ("INC-P004", "payments", 8),
        ),
    )

    assert original.scenario_sha256 != (
        changed_threshold.scenario_sha256
    )
    assert original.scenario_sha256 != (
        changed_records.scenario_sha256
    )


def test_model_request_binds_exact_scenario():
    first = _payments()
    second = _auth()

    first_request = build_scenario_incident_request(
        scenario=first,
        model="offline-model",
    )
    second_request = build_scenario_incident_request(
        scenario=second,
        model="offline-model",
    )

    assert first_request.provider == "openai"
    assert first_request.request_sha256 != (
        second_request.request_sha256
    )
    assert first.scenario_sha256 in first_request.user_prompt
    assert "INC-P001" in first_request.user_prompt
    assert "INC-A101" in second_request.user_prompt
    assert first_request.generation_parameters == {}


def test_request_changes_when_scenario_bytes_change():
    scenario = _payments()
    altered = replace(
        scenario,
        minimum_severity=5,
    )

    first = build_scenario_incident_request(
        scenario=scenario,
        model="offline-model",
    )
    second = build_scenario_incident_request(
        scenario=altered,
        model="offline-model",
    )

    assert first.request_sha256 != second.request_sha256


def test_schema_exposes_only_bounded_filter_actions():
    request = build_scenario_incident_request(
        scenario=_payments(),
        model="offline-model",
    )

    schema = request.response_schema

    assert schema["additionalProperties"] is False
    assert schema["required"] == ["tool", "threshold"]
    assert schema["properties"]["tool"]["enum"] == (
        list(ALLOWED_TOOLS)
    )
    assert schema["properties"]["threshold"]["maximum"] == 10

    assert not any(
        "shell" in value or "network" in value
        for value in ALLOWED_TOOLS
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"scenario_id": "INVALID NAME"},
        {"target_service": "Auth"},
        {"minimum_severity": True},
        {"minimum_severity": -1},
        {"minimum_severity": 11},
        {"records": (
            ("INC-P001", "payments", 3),
            ("INC-P001", "payments", 4),
        )},
        {"records": (
            ("INC-P001", "payments", True),
            ("INC-P002", "payments", 3),
        )},
        {"records": (
            ("INC-P001", "payments", 3),
            ("INC-P002", "payments", 11),
        )},
        {"records": (
            ("INC-A001", "auth", 3),
            ("INC-A002", "auth", 4),
        )},
        {"records": [
            ("INC-P001", "payments", 3),
            ("INC-P002", "payments", 4),
        ]},
    ],
)
def test_invalid_scenarios_fail_closed(changes):
    with pytest.raises(ContractError):
        replace(_payments(), **changes)


@pytest.mark.parametrize(
    "report",
    [
        TriageReport("payments", ("INC-P001",), True),
        TriageReport("payments", ["INC-P001"], 1),
        TriageReport(
            "payments",
            ("INC-P001", "INC-P001"),
            2,
        ),
        TriageReport("payments", ("unknown",), 1),
    ],
)
def test_malformed_reports_fail_closed(report):
    with pytest.raises(ContractError):
        evaluate_incident_scenario(
            scenario=_payments(),
            report=report,
        )


def test_scenario_is_immutable():
    scenario = _payments()

    with pytest.raises(FrozenInstanceError):
        scenario.minimum_severity = 5


def test_evaluation_evidence_changes_with_actual_report():
    scenario = _payments()

    correct = evaluate_incident_scenario(
        scenario=scenario,
        report=TriageReport(
            "payments",
            ("INC-P001", "INC-P002"),
            2,
        ),
    )

    wrong = evaluate_incident_scenario(
        scenario=scenario,
        report=TriageReport(
            "payments",
            ("INC-P002",),
            1,
        ),
    )

    assert correct.passed
    assert not wrong.passed
    assert correct.evaluation_evidence_sha256 != (
        wrong.evaluation_evidence_sha256
    )


def test_reference_evaluator_has_no_tool_or_repair_argument():
    parameters = inspect.signature(
        evaluate_incident_scenario
    ).parameters

    assert set(parameters) == {
        "scenario",
        "report",
    }


def test_oracle_claims_are_limited_to_development():
    scenario = _payments()

    evaluation = evaluate_incident_scenario(
        scenario=scenario,
        report=TriageReport(
            "payments",
            ("INC-P001", "INC-P002"),
            2,
        ),
    )

    limitations = " ".join(evaluation.limitations)

    assert "synthetic development scenario" in limitations
    assert "share task specification" in limitations
    assert "no independent scientific verification" in limitations
    assert "no live-model generalization" in limitations

"""A5-10F-B3 offline cross-scenario intervention evaluation."""

from dataclasses import replace
import json

import pytest

from packages.contracts import ContractError
from packages.core.hetren_diagnosis.contracts import DiagnosisStatus, InterventionKind
from packages.engines.behavioral.incident_scenario_development import (
    IncidentScenario, build_scenario_incident_request,
)
from packages.engines.behavioral.model_incident_candidate_development import (
    ScenarioCandidateCase, evaluate_diagnosed_incident_candidate_development,
)
from packages.engines.behavioral.model_incident_diagnosis_development import (
    diagnose_captured_incident_development,
)
from packages.engines.behavioral.model_incident_triage_agent import build_incident_triage_request
from packages.model_capture import capture_json_response


def _scenario(name, service, minimum, rows):
    return IncidentScenario(
        scenario_id=name, target_service=service,
        minimum_severity=minimum, records=rows,
    )


def _auth():
    return _scenario("auth-b3", "auth", 2, (
        ("INC-A101", "auth", 2), ("INC-A102", "auth", 7),
        ("INC-A103", "auth", 1), ("INC-P101", "payments", 8),
    ))


def _payments():
    return _scenario("payments-b3", "payments", 3, (
        ("INC-P201", "payments", 3), ("INC-P202", "payments", 5),
        ("INC-P203", "payments", 1), ("INC-A201", "auth", 9),
    ))


def _alerts():
    return _scenario("alerts-b3", "alerts", 4, (
        ("INC-L101", "alerts", 4), ("INC-L102", "alerts", 6),
        ("INC-L103", "alerts", 1), ("INC-A301", "auth", 10),
    ))


def _case(scenario, tool, threshold):
    request = build_scenario_incident_request(
        scenario=scenario, model="offline-model",
    )
    capture = capture_json_response(
        request=request,
        raw_response_text=json.dumps({"tool": tool, "threshold": threshold}, sort_keys=True),
    )
    return ScenarioCandidateCase(scenario, request, capture)


def _diagnosis(tool, threshold, budget=2):
    request = build_incident_triage_request(model="offline-model")
    capture = capture_json_response(
        request=request,
        raw_response_text=json.dumps({"tool": tool, "threshold": threshold}, sort_keys=True),
    )
    return diagnose_captured_incident_development(
        request=request, capture=capture, run_id="b3-source", budget_units=budget,
    )


def test_tool_fault_repairs_separate_scenario_and_preserves_control():
    diagnosis = _diagnosis("strict_severity_filter", 3)
    assert diagnosis.policy_result.policy_status is DiagnosisStatus.DIAGNOSED
    result = evaluate_diagnosed_incident_candidate_development(
        diagnosis=diagnosis,
        cases=(
            _case(_auth(), "strict_severity_filter", 2),
            _case(_payments(), "inclusive_severity_filter", 3),
        ),
    )
    assert result.intervention is InterventionKind.REPLACE_TOOL
    assert result.passed
    repaired, preserved = result.outcomes
    assert repaired.baseline.report.incident_ids == ("INC-A102",)
    assert repaired.candidate_report.incident_ids == ("INC-A101", "INC-A102")
    assert repaired.improves_failure
    assert preserved.baseline.passed and preserved.preserves_success
    assert preserved.candidate_report == preserved.baseline.report
    assert repaired.baseline.capture_sha256 != diagnosis.source_capture_sha256
    assert repaired.trace.run_id == repaired.run_id
    assert len(repaired.trace.events) == 3
    assert len(result.evidence_sha256) == 64



def test_correct_strict_control_preserved_by_observable_output():
    scenario = _scenario("quiet-b3", "quiet", 3, (
        ("INC-Q101", "quiet", 5), ("INC-Q102", "quiet", 7),
        ("INC-P401", "payments", 9),
    ))
    diagnosis = _diagnosis("strict_severity_filter", 3)
    result = evaluate_diagnosed_incident_candidate_development(
        diagnosis=diagnosis,
        cases=(
            _case(_auth(), "strict_severity_filter", 2),
            _case(scenario, "strict_severity_filter", 3),
        ),
    )
    assert result.passed
    control = result.outcomes[1]
    assert control.baseline.passed and control.preserves_success
    assert control.baseline.selected_tool == "strict_severity_filter"
    assert control.candidate_tool == "inclusive_severity_filter"
    assert control.candidate_report == control.baseline.report


def test_threshold_fault_restores_task_specific_threshold():
    diagnosis = _diagnosis("inclusive_severity_filter", 4)
    result = evaluate_diagnosed_incident_candidate_development(
        diagnosis=diagnosis,
        cases=(
            _case(_auth(), "inclusive_severity_filter", 3),
            _case(_payments(), "inclusive_severity_filter", 3),
            _case(_alerts(), "inclusive_severity_filter", 4),
        ),
    )
    assert result.intervention is InterventionKind.OVERRIDE_PARAMETER
    assert result.passed
    assert result.outcomes[0].candidate_threshold == 2
    assert result.outcomes[0].baseline.threshold == 3
    assert result.outcomes[0].improves_failure
    assert all(x.preserves_success for x in result.outcomes)


def test_compound_fault_fails_candidate_regression_gate():
    diagnosis = _diagnosis("strict_severity_filter", 3)
    result = evaluate_diagnosed_incident_candidate_development(
        diagnosis=diagnosis,
        cases=(
            _case(_auth(), "strict_severity_filter", 2),
            _case(_payments(), "inclusive_severity_filter", 3),
            _case(_alerts(), "strict_severity_filter", 5),
        ),
    )
    assert result.outcomes[0].improves_failure
    assert result.outcomes[1].preserves_success
    compound = result.outcomes[2]
    assert not compound.passed
    assert compound.candidate_tool == "inclusive_severity_filter"
    assert compound.candidate_threshold == 5
    assert compound.candidate_report.incident_ids == ("INC-L102",)
    assert not result.passed


def test_inconclusive_source_cannot_authorize_candidate():
    diagnosis = _diagnosis("strict_severity_filter", 4)
    assert diagnosis.policy_result.policy_status is DiagnosisStatus.INCONCLUSIVE
    with pytest.raises(ContractError, match="failed, diagnosed"):
        evaluate_diagnosed_incident_candidate_development(
            diagnosis=diagnosis,
            cases=(_case(_auth(), "strict_severity_filter", 2),
                   _case(_payments(), "inclusive_severity_filter", 3)),
        )


def test_budget_exhaustion_cannot_authorize_candidate():
    diagnosis = _diagnosis("inclusive_severity_filter", 4, budget=1)
    assert diagnosis.policy_result.policy_status is DiagnosisStatus.BUDGET_EXHAUSTED
    with pytest.raises(ContractError, match="failed, diagnosed"):
        evaluate_diagnosed_incident_candidate_development(
            diagnosis=diagnosis,
            cases=(_case(_auth(), "inclusive_severity_filter", 3),
                   _case(_payments(), "inclusive_severity_filter", 3)),
        )


def test_unsupported_action_rejected_before_candidate_execution():
    diagnosis = _diagnosis("strict_severity_filter", 3)
    with pytest.raises(ContractError, match="valid executed action"):
        evaluate_diagnosed_incident_candidate_development(
            diagnosis=diagnosis,
            cases=(_case(_auth(), "shell", 2),
                   _case(_payments(), "inclusive_severity_filter", 3)),
        )


def test_capture_from_different_scenario_fails_closed():
    diagnosis = _diagnosis("strict_severity_filter", 3)
    wrong = _case(_auth(), "strict_severity_filter", 2)
    swapped = ScenarioCandidateCase(_payments(), wrong.request, wrong.capture)
    with pytest.raises(ContractError, match="exact scenario"):
        evaluate_diagnosed_incident_candidate_development(
            diagnosis=diagnosis,
            cases=(swapped, _case(_alerts(), "inclusive_severity_filter", 4)),
        )


def test_capture_tampering_fails_closed():
    diagnosis = _diagnosis("strict_severity_filter", 3)
    original = _case(_auth(), "strict_severity_filter", 2)
    tampered = replace(
        original,
        capture=replace(original.capture, raw_response_text=json.dumps({
            "tool": "inclusive_severity_filter", "threshold": 2,
        })),
    )
    with pytest.raises(ContractError):
        evaluate_diagnosed_incident_candidate_development(
            diagnosis=diagnosis,
            cases=(tampered, _case(_payments(), "inclusive_severity_filter", 3)),
        )


def test_duplicate_scenario_is_rejected():
    diagnosis = _diagnosis("strict_severity_filter", 3)
    with pytest.raises(ContractError, match="duplicate candidate scenario"):
        evaluate_diagnosed_incident_candidate_development(
            diagnosis=diagnosis,
            cases=(_case(_auth(), "strict_severity_filter", 2),
                   _case(_auth(), "inclusive_severity_filter", 2)),
        )


def test_missing_passing_control_is_rejected():
    diagnosis = _diagnosis("strict_severity_filter", 3)
    with pytest.raises(ContractError, match="failing and passing"):
        evaluate_diagnosed_incident_candidate_development(
            diagnosis=diagnosis,
            cases=(_case(_auth(), "strict_severity_filter", 2),
                   _case(_payments(), "strict_severity_filter", 3)),
        )


def test_missing_failing_control_is_rejected():
    diagnosis = _diagnosis("strict_severity_filter", 3)
    with pytest.raises(ContractError, match="failing and passing"):
        evaluate_diagnosed_incident_candidate_development(
            diagnosis=diagnosis,
            cases=(_case(_auth(), "inclusive_severity_filter", 2),
                   _case(_payments(), "inclusive_severity_filter", 3)),
        )


def test_same_evidence_is_deterministic_and_ids_change_hash():
    diagnosis = _diagnosis("strict_severity_filter", 3)
    cases = (_case(_auth(), "strict_severity_filter", 2),
             _case(_payments(), "inclusive_severity_filter", 3))
    a = evaluate_diagnosed_incident_candidate_development(
        diagnosis=diagnosis, cases=cases, run_id="b3a",
    )
    b = evaluate_diagnosed_incident_candidate_development(
        diagnosis=diagnosis, cases=cases, run_id="b3a",
    )
    c = evaluate_diagnosed_incident_candidate_development(
        diagnosis=diagnosis, cases=cases, run_id="b3b",
    )
    assert a == b and a.evidence_sha256 == b.evidence_sha256
    assert a.evidence_sha256 != c.evidence_sha256
    assert a.outcomes[0].baseline.capture_sha256 == c.outcomes[0].baseline.capture_sha256


def test_claims_are_explicitly_development_only():
    diagnosis = _diagnosis("strict_severity_filter", 3)
    result = evaluate_diagnosed_incident_candidate_development(
        diagnosis=diagnosis,
        cases=(_case(_auth(), "strict_severity_filter", 2),
               _case(_payments(), "inclusive_severity_filter", 3)),
    )
    text = " ".join(result.limitations)
    assert "selected development cases" in text
    assert "not proof of model intent" in text
    assert "no independent scientific verification" in text
    assert "no automatic repair" in text

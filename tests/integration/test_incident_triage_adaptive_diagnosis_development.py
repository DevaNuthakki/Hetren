"""Adaptive development-policy acceptance tests."""

from dataclasses import fields

import pytest

from packages.core.hetren_diagnosis.contracts import (
    ContractError,
    DiagnosisStatus,
    Verdict,
)
from packages.core.hetren_diagnosis.open_set import (
    OpenSetReason,
)
from packages.engines.behavioral.incident_triage_adaptive_diagnosis_development import (
    run_adaptive_diagnosis_development,
)


@pytest.mark.parametrize(
    "scenario,cause,status,probes",
    [
        (
            "filter_tool_selection",
            "filter_tool_selection_fault",
            DiagnosisStatus.DIAGNOSED,
            1,
        ),
        (
            "threshold_transformation",
            "threshold_transformation_fault",
            DiagnosisStatus.DIAGNOSED,
            2,
        ),
        (
            "compound_fault",
            None,
            DiagnosisStatus.INCONCLUSIVE,
            2,
        ),
    ],
)
def test_adaptive_policy_executes_only_needed_probes(
    scenario, cause, status, probes
):
    result = run_adaptive_diagnosis_development(
        scenario, run_id=f"a56-{scenario}",
    )

    assert result.policy_status is status
    assert result.diagnosed_hypothesis_key == cause
    assert result.experiment_count == probes
    assert len(result.diagnostic_runs) == probes
    assert result.experiment_cost_units == probes

    assert not result.baseline_run.passed

    for sequence, (observation, run) in enumerate(
        zip(result.observations, result.diagnostic_runs)
    ):
        assert observation.sequence == sequence
        assert (
            observation.evidence_sha256
            == run.execution_evidence_sha256
        )
        assert observation.experiment_sha256 == (
            result.problem.experiments[sequence].experiment_sha256
        )
        assert observation.verdict is (
            Verdict.PASS if run.passed else Verdict.FAIL
        )

    if scenario == "compound_fault":
        assert (
            result.first_probe_decision.status
            is DiagnosisStatus.DIAGNOSED
        )
        assert (
            result.final_open_set_decision.reason
            is OpenSetReason.EVIDENCE_CONTRADICTION
        )
        assert result.diagnosed_hypothesis_key is None


@pytest.mark.parametrize(
    "scenario",
    ("threshold_transformation", "compound_fault"),
)
def test_insufficient_budget_never_certifies_ambiguous_cause(
    scenario,
):
    result = run_adaptive_diagnosis_development(
        scenario,
        run_id=f"a56-b-{scenario}",
        budget_units=1,
    )

    assert result.experiment_count == 1
    assert (
        result.policy_status
        is DiagnosisStatus.BUDGET_EXHAUSTED
    )
    assert (
        result.policy_reason
        == "falsification_budget_exhausted"
    )
    assert result.diagnosed_hypothesis_key is None
    assert result.final_open_set_decision is None


def test_one_probe_is_sufficient_for_known_filter_case():
    result = run_adaptive_diagnosis_development(
        "filter_tool_selection",
        run_id="a56-short",
        budget_units=1,
    )
    assert result.policy_status is DiagnosisStatus.DIAGNOSED
    assert result.experiment_cost_units == 1


def test_total_actual_probe_cost_is_five_for_three_pilot_cases():
    cases = (
        "filter_tool_selection",
        "threshold_transformation",
        "compound_fault",
    )
    results = [
        run_adaptive_diagnosis_development(
            case, run_id=f"a56-t-{case}",
        )
        for case in cases
    ]
    assert sum(result.experiment_count for result in results) == 5
    assert sum(result.experiment_cost_units for result in results) == 5
    assert [
        result.policy_status.name for result in results
    ] == [
        "DIAGNOSED",
        "DIAGNOSED",
        "INCONCLUSIVE",
    ]


@pytest.mark.parametrize(
    "scenario,run_id,budget",
    [
        ("unknown", "a56-bad-case", 2),
        ("filter_tool_selection", "../unsafe", 2),
        ("filter_tool_selection", "", 2),
        ("filter_tool_selection", "a56-bad-budget", 0),
        ("filter_tool_selection", "a56-bad-budget", True),
        ("filter_tool_selection", "a56-bad-budget", 3),
        ("filter_tool_selection", "x" * 33, 2),
    ],
)
def test_invalid_inputs_fail_closed(scenario, run_id, budget):
    with pytest.raises(ContractError):
        run_adaptive_diagnosis_development(
            scenario, run_id=run_id, budget_units=budget,
        )


def test_deterministic_repeated_execution():
    first = run_adaptive_diagnosis_development(
        "compound_fault", run_id="a56-repeat",
    )
    second = run_adaptive_diagnosis_development(
        "compound_fault", run_id="a56-repeat",
    )
    assert first == second


def test_no_repair_verification_or_authorization_result():
    result = run_adaptive_diagnosis_development(
        "compound_fault", run_id="a56-no-authority",
    )
    names = {field.name for field in fields(type(result))}
    assert names.isdisjoint({
        "repair",
        "approval",
        "verification_report",
        "eligibility",
        "deployment_authorized",
    })

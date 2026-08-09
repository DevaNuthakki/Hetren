from __future__ import annotations

import pytest

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.critical_number_mutation import (
    CRITICAL_NUMBER_EVALUATOR_MUTATIONS_V1,
    CRITICAL_NUMBER_MUTATION_SUITE_KEY,
    CRITICAL_NUMBER_MUTATION_SUITE_VERSION,
    ASRCriticalNumberEvaluatorMutation,
    apply_critical_number_evaluator_mutation,
    run_critical_number_evaluator_mutation,
    run_critical_number_evaluator_mutation_suite,
)
from hvee.packs.asr.critical_number_portfolio import (
    CRITICAL_NUMBER_FIDELITY_PORTFOLIO_V1,
    evaluate_critical_number_portfolio_case_observations,
)


@pytest.mark.parametrize(
    ("mutation", "expected_case"),
    [
        (
            ASRCriticalNumberEvaluatorMutation.OUTCOME_FALSE_PASS,
            "calibration.measurement.substitution",
        ),
        (
            ASRCriticalNumberEvaluatorMutation.PRESERVATION_FALSE_PASS,
            "calibration.measurement.substitution",
        ),
        (
            ASRCriticalNumberEvaluatorMutation.EQUIVALENCE_FALSE_FAILURE,
            "calibration.measurement.equivalence",
        ),
        (
            ASRCriticalNumberEvaluatorMutation.SUBSTITUTION_BLIND,
            "calibration.measurement.substitution",
        ),
        (
            ASRCriticalNumberEvaluatorMutation.OMISSION_BLIND,
            "holdout.measurement.omission",
        ),
        (
            ASRCriticalNumberEvaluatorMutation.INSERTION_BLIND,
            "holdout.measurement.insertion",
        ),
        (
            ASRCriticalNumberEvaluatorMutation.AMBIGUITY_BLIND,
            "holdout.ambiguous-date.insufficient",
        ),
        (
            ASRCriticalNumberEvaluatorMutation.NO_NUMBER_APPLICABILITY_BLIND,
            "calibration.no-number.not-applicable",
        ),
        (
            ASRCriticalNumberEvaluatorMutation.DETAILED_FINDINGS_BLIND,
            "calibration.measurement.substitution",
        ),
    ],
)
def test_each_mutant_is_killed_by_a_targeted_case(mutation, expected_case):
    result = run_critical_number_evaluator_mutation(
        portfolio=CRITICAL_NUMBER_FIDELITY_PORTFOLIO_V1,
        mutation=mutation,
    )

    assert result.killed is True
    assert result.changed_cases > 0
    assert expected_case in result.detected_case_ids


def test_full_mutation_suite_kills_every_defined_mutant():
    report = run_critical_number_evaluator_mutation_suite(
        CRITICAL_NUMBER_FIDELITY_PORTFOLIO_V1
    )

    assert report.suite_key == CRITICAL_NUMBER_MUTATION_SUITE_KEY
    assert report.suite_version == CRITICAL_NUMBER_MUTATION_SUITE_VERSION
    assert report.total_mutants == 9
    assert report.killed_mutants == 9
    assert report.survived_mutants == 0
    assert report.mutation_score == 1.0


def test_mutation_suite_identity_is_complete_and_unique():
    assert len(CRITICAL_NUMBER_EVALUATOR_MUTATIONS_V1) == 9
    assert len(set(CRITICAL_NUMBER_EVALUATOR_MUTATIONS_V1)) == 9


def test_mutation_preserves_scientific_identity_status_and_value_type():
    case = next(
        case
        for case in CRITICAL_NUMBER_FIDELITY_PORTFOLIO_V1.cases
        if case.case_id == "calibration.measurement.substitution"
    )
    original = evaluate_critical_number_portfolio_case_observations(case)
    mutated = apply_critical_number_evaluator_mutation(
        mutation=ASRCriticalNumberEvaluatorMutation.PRESERVATION_FALSE_PASS,
        observations=original,
    )

    original_identities = tuple(
        (
            observation.metric_key,
            observation.metric_version,
            observation.evaluator_key,
            observation.evaluator_version,
            observation.status,
            observation.value_type,
        )
        for observation in original
    )
    mutated_identities = tuple(
        (
            observation.metric_key,
            observation.metric_version,
            observation.evaluator_key,
            observation.evaluator_version,
            observation.status,
            observation.value_type,
        )
        for observation in mutated
    )

    assert mutated_identities == original_identities
    assert mutated != original


def test_invalid_mutation_type_is_rejected():
    case = CRITICAL_NUMBER_FIDELITY_PORTFOLIO_V1.cases[0]
    observations = evaluate_critical_number_portfolio_case_observations(case)

    with pytest.raises(
        HveeContractError,
        match="must be ASRCriticalNumberEvaluatorMutation",
    ):
        apply_critical_number_evaluator_mutation(
            mutation="broken",  # type: ignore[arg-type]
            observations=observations,
        )

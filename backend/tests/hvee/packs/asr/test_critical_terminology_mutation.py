from __future__ import annotations

from dataclasses import replace

import pytest

import hvee.packs.asr as asr
from hvee.core.contracts import (
    HveeContractError,
)
from hvee.packs.asr.critical_terminology_mutation import (
    CRITICAL_TERMINOLOGY_EVALUATOR_MUTATIONS_V1,
    CRITICAL_TERMINOLOGY_MUTATION_SUITE_KEY,
    CRITICAL_TERMINOLOGY_MUTATION_SUITE_VERSION,
    ASRCriticalTerminologyEvaluatorMutation,
    ASRCriticalTerminologyMutationReport,
    ASRCriticalTerminologyMutationResult,
    apply_critical_terminology_evaluator_mutation,
    run_critical_terminology_evaluator_mutation,
    run_critical_terminology_evaluator_mutation_suite,
)
from hvee.packs.asr.critical_terminology_portfolio import (
    CRITICAL_TERMINOLOGY_FIDELITY_PORTFOLIO_V1,
    evaluate_critical_terminology_portfolio_case_observations,
)


PORTFOLIO = (
    CRITICAL_TERMINOLOGY_FIDELITY_PORTFOLIO_V1
)
M = ASRCriticalTerminologyEvaluatorMutation


TARGET_CASES = (
    (
        M.OUTCOME_FALSE_PASS,
        "calibration.registered-term-substitution",
    ),
    (
        M.PRESERVATION_FALSE_PASS,
        "calibration.registered-term-substitution",
    ),
    (
        M.EQUIVALENCE_FALSE_FAILURE,
        "calibration.exact-postgresql",
    ),
    (
        M.SUBSTITUTION_BLIND,
        "calibration.registered-term-substitution",
    ),
    (
        M.OMISSION_BLIND,
        "calibration.reference-omission",
    ),
    (
        M.INSERTION_BLIND,
        "calibration.generated-insertion",
    ),
    (
        M.ORDERING_CHANGE_BLIND,
        "calibration.ordering-change",
    ),
    (
        M.NO_TERMINOLOGY_APPLICABILITY_BLIND,
        "regression.no-critical-terminology",
    ),
    (
        M.VOCABULARY_IDENTITY_BLIND,
        "calibration.exact-postgresql",
    ),
    (
        M.DETAILED_FINDINGS_BLIND,
        "calibration.registered-term-substitution",
    ),
)


def _case(case_id: str):
    return next(
        case
        for case in PORTFOLIO.cases
        if case.case_id == case_id
    )


@pytest.mark.parametrize(
    ("mutation", "case_id"),
    TARGET_CASES,
)
def test_each_mutant_is_killed_by_a_targeted_case(
    mutation,
    case_id,
):
    single_case_portfolio = replace(
        PORTFOLIO,
        cases=(
            _case(case_id),
        ),
    )

    result = (
        run_critical_terminology_evaluator_mutation(
            portfolio=single_case_portfolio,
            mutation=mutation,
        )
    )

    assert isinstance(
        result,
        ASRCriticalTerminologyMutationResult,
    )
    assert result.mutation == mutation
    assert result.changed_cases == 1
    assert result.detected_cases == 1
    assert result.killed is True
    assert result.changed_case_ids == (
        case_id,
    )
    assert result.detected_case_ids == (
        case_id,
    )


def test_full_mutation_suite_kills_every_defined_mutant():
    report = (
        run_critical_terminology_evaluator_mutation_suite(
            PORTFOLIO
        )
    )

    assert isinstance(
        report,
        ASRCriticalTerminologyMutationReport,
    )
    assert report.total_mutants == 10
    assert report.killed_mutants == 10
    assert report.survived_mutants == 0
    assert report.mutation_score == 1.0

    assert all(
        result.killed
        for result in report.results
    )


def test_mutation_suite_identity_is_complete_and_unique():
    assert (
        CRITICAL_TERMINOLOGY_MUTATION_SUITE_KEY
        == (
            "hetren.asr.critical-terminology-"
            "evaluator-mutation-suite.en-us"
        )
    )

    assert (
        CRITICAL_TERMINOLOGY_MUTATION_SUITE_VERSION
        == "1.0.0"
    )

    assert (
        CRITICAL_TERMINOLOGY_EVALUATOR_MUTATIONS_V1
        == tuple(
            ASRCriticalTerminologyEvaluatorMutation
        )
    )

    assert len(
        CRITICAL_TERMINOLOGY_EVALUATOR_MUTATIONS_V1
    ) == len(
        set(
            CRITICAL_TERMINOLOGY_EVALUATOR_MUTATIONS_V1
        )
    )


@pytest.mark.parametrize(
    ("mutation", "case_id"),
    TARGET_CASES,
)
def test_mutation_preserves_observation_contract(
    mutation,
    case_id,
):
    case = _case(
        case_id
    )

    observations = (
        evaluate_critical_terminology_portfolio_case_observations(
            case,
            profile=PORTFOLIO.profile,
        )
    )

    mutated = (
        apply_critical_terminology_evaluator_mutation(
            mutation=mutation,
            observations=observations,
        )
    )

    assert mutated != observations
    assert len(mutated) == len(
        observations
    )

    before = tuple(
        (
            observation.metric_key,
            observation.metric_version,
            observation.evaluator_key,
            observation.evaluator_version,
            observation.evaluation_type,
            observation.status,
            observation.value_type,
            observation.status_detail,
        )
        for observation in observations
    )

    after = tuple(
        (
            observation.metric_key,
            observation.metric_version,
            observation.evaluator_key,
            observation.evaluator_version,
            observation.evaluation_type,
            observation.status,
            observation.value_type,
            observation.status_detail,
        )
        for observation in mutated
    )

    assert after == before


def test_invalid_mutation_type_is_rejected():
    case = PORTFOLIO.cases[0]

    observations = (
        evaluate_critical_terminology_portfolio_case_observations(
            case,
            profile=PORTFOLIO.profile,
        )
    )

    with pytest.raises(
        HveeContractError,
        match="ASRCriticalTerminologyEvaluatorMutation",
    ):
        apply_critical_terminology_evaluator_mutation(
            mutation="not-a-mutation",
            observations=observations,
        )


def test_mutation_requires_a_passing_baseline():
    case = _case(
        "calibration.registered-term-substitution"
    )

    invalid_case = replace(
        case,
        expected_generated_count=999,
    )

    invalid_portfolio = replace(
        PORTFOLIO,
        cases=(
            invalid_case,
        ),
    )

    with pytest.raises(
        HveeContractError,
        match="passing baseline",
    ):
        run_critical_terminology_evaluator_mutation(
            portfolio=invalid_portfolio,
            mutation=M.OUTCOME_FALSE_PASS,
        )


def test_mutation_rejects_portfolio_with_no_effect():
    exact_case = _case(
        "calibration.exact-postgresql"
    )

    single_case_portfolio = replace(
        PORTFOLIO,
        cases=(
            exact_case,
        ),
    )

    with pytest.raises(
        HveeContractError,
        match="had no portfolio effect",
    ):
        run_critical_terminology_evaluator_mutation(
            portfolio=single_case_portfolio,
            mutation=M.SUBSTITUTION_BLIND,
        )


def test_public_asr_mutation_exports_are_available():
    expected = (
        "ASRCriticalTerminologyEvaluatorMutation",
        "ASRCriticalTerminologyMutationReport",
        "ASRCriticalTerminologyMutationResult",
        "CRITICAL_TERMINOLOGY_EVALUATOR_MUTATIONS_V1",
        "CRITICAL_TERMINOLOGY_MUTATION_SUITE_KEY",
        "CRITICAL_TERMINOLOGY_MUTATION_SUITE_VERSION",
        "apply_critical_terminology_evaluator_mutation",
        "run_critical_terminology_evaluator_mutation",
        "run_critical_terminology_evaluator_mutation_suite",
    )

    for name in expected:
        assert hasattr(
            asr,
            name,
        )


def test_generic_laboratory_preserves_public_mutation_result_type():
    result = (
        run_critical_terminology_evaluator_mutation(
            portfolio=PORTFOLIO,
            mutation=M.SUBSTITUTION_BLIND,
        )
    )

    assert type(result) is (
        ASRCriticalTerminologyMutationResult
    )


def test_generic_laboratory_preserves_public_mutation_report_type():
    report = (
        run_critical_terminology_evaluator_mutation_suite(
            PORTFOLIO
        )
    )

    assert type(report) is (
        ASRCriticalTerminologyMutationReport
    )
    assert report.total_mutants == 10
    assert report.killed_mutants == 10
    assert report.survived_mutants == 0
    assert report.mutation_score == 1.0


def test_v1_mutation_detection_counts_are_pinned():
    report = (
        run_critical_terminology_evaluator_mutation_suite(
            PORTFOLIO
        )
    )

    actual = {
        result.mutation: (
            result.changed_cases,
            result.detected_cases,
        )
        for result in report.results
    }

    assert actual == {
        M.OUTCOME_FALSE_PASS: (10, 10),
        M.PRESERVATION_FALSE_PASS: (10, 10),
        M.EQUIVALENCE_FALSE_FAILURE: (12, 12),
        M.SUBSTITUTION_BLIND: (2, 2),
        M.OMISSION_BLIND: (5, 5),
        M.INSERTION_BLIND: (2, 2),
        M.ORDERING_CHANGE_BLIND: (1, 1),
        M.NO_TERMINOLOGY_APPLICABILITY_BLIND: (2, 2),
        M.VOCABULARY_IDENTITY_BLIND: (24, 24),
        M.DETAILED_FINDINGS_BLIND: (22, 22),
    }

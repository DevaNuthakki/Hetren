from __future__ import annotations

from dataclasses import replace

import pytest

import hvee.packs.asr as asr_pack
from hvee.core.contracts import HveeContractError
from hvee.packs.asr.critical_identifier_mutation import (
    CRITICAL_IDENTIFIER_EVALUATOR_MUTATIONS_V1,
    CRITICAL_IDENTIFIER_MUTATION_SUITE_KEY,
    CRITICAL_IDENTIFIER_MUTATION_SUITE_VERSION,
    ASRCriticalIdentifierEvaluatorMutation,
    apply_critical_identifier_evaluator_mutation,
    run_critical_identifier_evaluator_mutation,
    run_critical_identifier_evaluator_mutation_suite,
)
from hvee.packs.asr.critical_identifier_portfolio import (
    CRITICAL_IDENTIFIER_FIDELITY_PORTFOLIO_V1,
    CRITICAL_IDENTIFIER_PORTFOLIO_KEY,
    CRITICAL_IDENTIFIER_PORTFOLIO_VERSION,
    ASRCriticalIdentifierPortfolioDefinition,
    evaluate_critical_identifier_portfolio_case_observations,
)


@pytest.mark.parametrize(
    ("mutation", "expected_case"),
    (
        (
            ASRCriticalIdentifierEvaluatorMutation
            .OUTCOME_FALSE_PASS,
            "calibration.confirmation-code.substitution",
        ),
        (
            ASRCriticalIdentifierEvaluatorMutation
            .PRESERVATION_FALSE_PASS,
            "calibration.confirmation-code.substitution",
        ),
        (
            ASRCriticalIdentifierEvaluatorMutation
            .EQUIVALENCE_FALSE_FAILURE,
            "calibration.confirmation-code.equivalence",
        ),
        (
            ASRCriticalIdentifierEvaluatorMutation
            .SUBSTITUTION_BLIND,
            "calibration.confirmation-code.substitution",
        ),
        (
            ASRCriticalIdentifierEvaluatorMutation
            .OMISSION_BLIND,
            "holdout.confirmation-code.omission",
        ),
        (
            ASRCriticalIdentifierEvaluatorMutation
            .INSERTION_BLIND,
            "holdout.confirmation-code.insertion",
        ),
        (
            ASRCriticalIdentifierEvaluatorMutation
            .ORDERING_CHANGE_BLIND,
            "holdout.ticket-id.ordering-change",
        ),
        (
            ASRCriticalIdentifierEvaluatorMutation
            .AMBIGUITY_BLIND,
            "holdout.reference-id.ambiguous",
        ),
        (
            ASRCriticalIdentifierEvaluatorMutation
            .NO_IDENTIFIER_APPLICABILITY_BLIND,
            "calibration.no-identifier.not-applicable",
        ),
        (
            ASRCriticalIdentifierEvaluatorMutation
            .DETAILED_FINDINGS_BLIND,
            "calibration.confirmation-code.substitution",
        ),
    ),
)
def test_each_mutant_is_killed_by_a_targeted_case(
    mutation,
    expected_case,
):
    result = run_critical_identifier_evaluator_mutation(
        portfolio=(
            CRITICAL_IDENTIFIER_FIDELITY_PORTFOLIO_V1
        ),
        mutation=mutation,
    )

    assert result.killed is True
    assert result.changed_cases > 0
    assert result.detected_cases > 0
    assert expected_case in result.detected_case_ids


def test_full_mutation_suite_kills_every_defined_mutant():
    report = (
        run_critical_identifier_evaluator_mutation_suite(
            CRITICAL_IDENTIFIER_FIDELITY_PORTFOLIO_V1
        )
    )

    assert (
        report.portfolio_key
        == CRITICAL_IDENTIFIER_PORTFOLIO_KEY
    )
    assert (
        report.portfolio_version
        == CRITICAL_IDENTIFIER_PORTFOLIO_VERSION
    )
    assert (
        report.suite_key
        == CRITICAL_IDENTIFIER_MUTATION_SUITE_KEY
    )
    assert (
        report.suite_version
        == CRITICAL_IDENTIFIER_MUTATION_SUITE_VERSION
    )

    assert report.total_mutants == 10
    assert report.killed_mutants == 10
    assert report.survived_mutants == 0
    assert report.mutation_score == 1.0


def test_mutation_suite_identity_is_complete_and_unique():
    assert (
        CRITICAL_IDENTIFIER_MUTATION_SUITE_KEY
        == (
            "hetren.asr."
            "critical-identifier-evaluator-mutation-suite.en-us"
        )
    )
    assert (
        CRITICAL_IDENTIFIER_MUTATION_SUITE_VERSION
        == "1.0.0"
    )

    assert (
        len(CRITICAL_IDENTIFIER_EVALUATOR_MUTATIONS_V1)
        == 10
    )
    assert len(
        set(CRITICAL_IDENTIFIER_EVALUATOR_MUTATIONS_V1)
    ) == 10


def test_mutation_preserves_scientific_identity_status_and_value_type():
    case = next(
        case
        for case in (
            CRITICAL_IDENTIFIER_FIDELITY_PORTFOLIO_V1.cases
        )
        if case.case_id
        == "calibration.confirmation-code.substitution"
    )

    original = (
        evaluate_critical_identifier_portfolio_case_observations(
            case
        )
    )

    mutated = (
        apply_critical_identifier_evaluator_mutation(
            mutation=(
                ASRCriticalIdentifierEvaluatorMutation
                .PRESERVATION_FALSE_PASS
            ),
            observations=original,
        )
    )

    original_identities = tuple(
        (
            observation.metric_key,
            observation.metric_version,
            observation.evaluator_key,
            observation.evaluator_version,
            observation.evaluation_type,
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
            observation.evaluation_type,
            observation.status,
            observation.value_type,
        )
        for observation in mutated
    )

    assert mutated_identities == original_identities
    assert mutated != original


def test_invalid_mutation_type_is_rejected():
    case = (
        CRITICAL_IDENTIFIER_FIDELITY_PORTFOLIO_V1
        .cases[0]
    )

    observations = (
        evaluate_critical_identifier_portfolio_case_observations(
            case
        )
    )

    with pytest.raises(
        HveeContractError,
        match=(
            "must be "
            "ASRCriticalIdentifierEvaluatorMutation"
        ),
    ):
        apply_critical_identifier_evaluator_mutation(
            mutation="broken",  # type: ignore[arg-type]
            observations=observations,
        )


def test_mutation_requires_a_passing_baseline():
    original_case = next(
        case
        for case in (
            CRITICAL_IDENTIFIER_FIDELITY_PORTFOLIO_V1.cases
        )
        if case.case_id
        == "calibration.confirmation-code.substitution"
    )

    forged_case = replace(
        original_case,
        expected_substitution_count=0,
    )

    portfolio = ASRCriticalIdentifierPortfolioDefinition(
        key=CRITICAL_IDENTIFIER_PORTFOLIO_KEY,
        version=CRITICAL_IDENTIFIER_PORTFOLIO_VERSION,
        cases=(forged_case,),
    )

    with pytest.raises(
        HveeContractError,
        match="requires a passing baseline",
    ):
        run_critical_identifier_evaluator_mutation(
            portfolio=portfolio,
            mutation=(
                ASRCriticalIdentifierEvaluatorMutation
                .OUTCOME_FALSE_PASS
            ),
        )


def test_mutation_rejects_portfolio_with_no_mutation_effect():
    no_identifier_case = next(
        case
        for case in (
            CRITICAL_IDENTIFIER_FIDELITY_PORTFOLIO_V1.cases
        )
        if case.case_id
        == "calibration.no-identifier.not-applicable"
    )

    portfolio = ASRCriticalIdentifierPortfolioDefinition(
        key=CRITICAL_IDENTIFIER_PORTFOLIO_KEY,
        version=CRITICAL_IDENTIFIER_PORTFOLIO_VERSION,
        cases=(no_identifier_case,),
    )

    with pytest.raises(
        HveeContractError,
        match="had no portfolio effect",
    ):
        run_critical_identifier_evaluator_mutation(
            portfolio=portfolio,
            mutation=(
                ASRCriticalIdentifierEvaluatorMutation
                .SUBSTITUTION_BLIND
            ),
        )


def test_public_asr_mutation_exports_are_available():
    expected_names = (
        "ASRCriticalIdentifierEvaluatorMutation",
        "ASRCriticalIdentifierMutationReport",
        "ASRCriticalIdentifierMutationResult",
        "CRITICAL_IDENTIFIER_EVALUATOR_MUTATIONS_V1",
        "CRITICAL_IDENTIFIER_MUTATION_SUITE_KEY",
        "CRITICAL_IDENTIFIER_MUTATION_SUITE_VERSION",
        "apply_critical_identifier_evaluator_mutation",
        "run_critical_identifier_evaluator_mutation",
        "run_critical_identifier_evaluator_mutation_suite",
    )

    for name in expected_names:
        assert hasattr(asr_pack, name)
        assert name in asr_pack.__all__
        assert asr_pack.__all__.count(name) == 1

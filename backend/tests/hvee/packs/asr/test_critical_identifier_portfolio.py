from __future__ import annotations

from collections import defaultdict
from dataclasses import replace

import pytest

import hvee.packs.asr as asr_pack
from hvee.core.contracts import HveeContractError
from hvee.packs.asr.critical_identifier_fidelity import (
    ASRCriticalIdentifierFidelityOutcome,
    ASRCriticalIdentifierType,
)
from hvee.packs.asr.critical_identifier_portfolio import (
    CRITICAL_IDENTIFIER_FIDELITY_PORTFOLIO_V1,
    CRITICAL_IDENTIFIER_PORTFOLIO_KEY,
    CRITICAL_IDENTIFIER_PORTFOLIO_VERSION,
    ASRCriticalIdentifierPortfolioOperation,
    ASRCriticalIdentifierPortfolioPartition,
    compare_critical_identifier_portfolio_case,
    evaluate_critical_identifier_portfolio_case_observations,
    run_critical_identifier_portfolio,
)


def test_complete_critical_identifier_portfolio_passes():
    report = run_critical_identifier_portfolio(
        CRITICAL_IDENTIFIER_FIDELITY_PORTFOLIO_V1
    )

    assert (
        report.portfolio_key
        == CRITICAL_IDENTIFIER_PORTFOLIO_KEY
    )
    assert (
        report.portfolio_version
        == CRITICAL_IDENTIFIER_PORTFOLIO_VERSION
    )
    assert report.total_cases == 42
    assert report.passed_cases == 42
    assert report.failed_cases == 0
    assert report.passed is True


def test_each_supported_type_has_full_error_matrix():
    operations_by_type = defaultdict(set)

    for case in (
        CRITICAL_IDENTIFIER_FIDELITY_PORTFOLIO_V1.cases
    ):
        if case.identifier_type is not None:
            operations_by_type[
                case.identifier_type
            ].add(case.operation)

    required_operations = {
        ASRCriticalIdentifierPortfolioOperation.EQUIVALENCE,
        ASRCriticalIdentifierPortfolioOperation.SUBSTITUTION,
        ASRCriticalIdentifierPortfolioOperation.OMISSION,
        ASRCriticalIdentifierPortfolioOperation.INSERTION,
    }

    supported_types = set(ASRCriticalIdentifierType)

    assert len(supported_types) == 8

    for identifier_type in supported_types:
        assert (
            required_operations
            <= operations_by_type[identifier_type]
        )


def test_portfolio_separates_development_partitions():
    cases = (
        CRITICAL_IDENTIFIER_FIDELITY_PORTFOLIO_V1.cases
    )

    partitions = {
        case.partition
        for case in cases
    }

    assert partitions == {
        ASRCriticalIdentifierPortfolioPartition.CALIBRATION,
        (
            ASRCriticalIdentifierPortfolioPartition
            .REGRESSION_HOLDOUT
        ),
    }

    assert all(
        (
            case.case_id.startswith("calibration.")
            if case.partition
            == (
                ASRCriticalIdentifierPortfolioPartition
                .CALIBRATION
            )
            else case.case_id.startswith("holdout.")
        )
        for case in cases
    )


def test_dangerous_cases_have_zero_false_passes():
    dangerous_operations = {
        ASRCriticalIdentifierPortfolioOperation.SUBSTITUTION,
        ASRCriticalIdentifierPortfolioOperation.OMISSION,
        ASRCriticalIdentifierPortfolioOperation.INSERTION,
        (
            ASRCriticalIdentifierPortfolioOperation
            .ORDERING_CHANGE
        ),
        (
            ASRCriticalIdentifierPortfolioOperation
            .DUPLICATE_OMISSION
        ),
        ASRCriticalIdentifierPortfolioOperation.TYPE_MISMATCH,
    }

    dangerous_cases = tuple(
        case
        for case in (
            CRITICAL_IDENTIFIER_FIDELITY_PORTFOLIO_V1.cases
        )
        if case.operation in dangerous_operations
    )

    assert dangerous_cases

    assert all(
        case.expected_outcome
        == (
            ASRCriticalIdentifierFidelityOutcome
            .NOT_PRESERVED
        )
        and case.expected_preserved is False
        for case in dangerous_cases
    )


def test_supported_equivalences_have_zero_false_failures():
    equivalence_cases = tuple(
        case
        for case in (
            CRITICAL_IDENTIFIER_FIDELITY_PORTFOLIO_V1.cases
        )
        if case.operation
        == (
            ASRCriticalIdentifierPortfolioOperation
            .EQUIVALENCE
        )
    )

    assert len(equivalence_cases) == 8

    assert all(
        case.expected_outcome
        == ASRCriticalIdentifierFidelityOutcome.PRESERVED
        and case.expected_preserved is True
        for case in equivalence_cases
    )


def test_uncertain_cases_never_claim_preservation():
    uncertain_operations = {
        ASRCriticalIdentifierPortfolioOperation.AMBIGUOUS,
        ASRCriticalIdentifierPortfolioOperation.UNSUPPORTED,
    }

    cases = tuple(
        case
        for case in (
            CRITICAL_IDENTIFIER_FIDELITY_PORTFOLIO_V1.cases
        )
        if case.operation in uncertain_operations
    )

    assert len(cases) == 5

    assert all(
        case.expected_outcome
        == (
            ASRCriticalIdentifierFidelityOutcome
            .INSUFFICIENT_EVIDENCE
        )
        and case.expected_preserved is None
        for case in cases
    )


def test_identifier_specific_regression_cases_are_pinned():
    case_ids = {
        case.case_id
        for case in (
            CRITICAL_IDENTIFIER_FIDELITY_PORTFOLIO_V1.cases
        )
    }

    required = {
        "holdout.ticket-id.ordering-change",
        "calibration.ticket-id.duplicate-control",
        "holdout.ticket-id.duplicate-omission",
        "calibration.no-identifier.not-applicable",
        "holdout.reference-id.ambiguous",
        "holdout.reference-id.grouped-unsupported",
        "holdout.confirmation-code.spoken-unsupported",
        "holdout.reference-id.underscore-unsupported",
        "holdout.reference-id.malformed-hyphen",
        "holdout.identifier-type.mismatch",
    }

    assert required <= case_ids


def test_case_ids_and_portfolio_identity_are_unique_and_versioned():
    portfolio = (
        CRITICAL_IDENTIFIER_FIDELITY_PORTFOLIO_V1
    )

    case_ids = tuple(
        case.case_id
        for case in portfolio.cases
    )

    assert len(case_ids) == len(set(case_ids))

    assert portfolio.key == (
        "hetren.asr."
        "critical-identifier-fidelity-portfolio.en-us"
    )
    assert portfolio.version == "1.0.0"


def test_comparison_rejects_scientific_identity_drift():
    case = (
        CRITICAL_IDENTIFIER_FIDELITY_PORTFOLIO_V1
        .cases[0]
    )

    observations = (
        evaluate_critical_identifier_portfolio_case_observations(
            case
        )
    )

    forged = (
        replace(
            observations[0],
            evaluator_version="9.9.9",
        ),
        *observations[1:],
    )

    with pytest.raises(
        HveeContractError,
        match="scientific identity changed",
    ):
        compare_critical_identifier_portfolio_case(
            case=case,
            observations=forged,
        )


def test_public_asr_portfolio_exports_are_available():
    expected_names = (
        "ASRCriticalIdentifierPortfolioCase",
        "ASRCriticalIdentifierPortfolioCaseResult",
        "ASRCriticalIdentifierPortfolioDefinition",
        "ASRCriticalIdentifierPortfolioOperation",
        "ASRCriticalIdentifierPortfolioPartition",
        "ASRCriticalIdentifierPortfolioReport",
        "CRITICAL_IDENTIFIER_FIDELITY_PORTFOLIO_V1",
        "CRITICAL_IDENTIFIER_PORTFOLIO_KEY",
        "CRITICAL_IDENTIFIER_PORTFOLIO_VERSION",
        "compare_critical_identifier_portfolio_case",
        "evaluate_critical_identifier_portfolio_case_observations",
        "run_critical_identifier_portfolio",
        "run_critical_identifier_portfolio_case",
    )

    for name in expected_names:
        assert hasattr(asr_pack, name)
        assert name in asr_pack.__all__
        assert asr_pack.__all__.count(name) == 1


@pytest.mark.parametrize(
    (
        "case_id",
        "metric_key",
        "corrupted_value",
        "expected_failed_check",
    ),
    (
        (
            "calibration.confirmation-code.substitution",
            (
                asr_pack
                .CRITICAL_IDENTIFIER_PRESERVED_METRIC
                .key
            ),
            True,
            "preserved_value",
        ),
        (
            "calibration.confirmation-code.equivalence",
            (
                asr_pack
                .CRITICAL_IDENTIFIER_PRESERVED_METRIC
                .key
            ),
            False,
            "preserved_value",
        ),
        (
            "calibration.confirmation-code.substitution",
            (
                asr_pack
                .CRITICAL_IDENTIFIER_SUBSTITUTION_COUNT_METRIC
                .key
            ),
            0,
            "substitution_count",
        ),
        (
            "holdout.ticket-id.ordering-change",
            (
                asr_pack
                .CRITICAL_IDENTIFIER_ORDERING_CHANGE_COUNT_METRIC
                .key
            ),
            0,
            "ordering_change_count",
        ),
        (
            "holdout.reference-id.ambiguous",
            (
                asr_pack
                .CRITICAL_IDENTIFIER_AMBIGUITY_COUNT_METRIC
                .key
            ),
            0,
            "ambiguity_count",
        ),
        (
            "calibration.no-identifier.not-applicable",
            (
                asr_pack
                .CRITICAL_IDENTIFIER_APPLICABLE_METRIC
                .key
            ),
            True,
            "applicable",
        ),
        (
            "calibration.confirmation-code.substitution",
            (
                asr_pack
                .CRITICAL_IDENTIFIER_FINDINGS_METRIC
                .key
            ),
            [],
            "reason:value_substitution",
        ),
    ),
)
def test_portfolio_detects_controlled_observation_corruption(
    case_id,
    metric_key,
    corrupted_value,
    expected_failed_check,
):
    case = next(
        case
        for case in (
            CRITICAL_IDENTIFIER_FIDELITY_PORTFOLIO_V1.cases
        )
        if case.case_id == case_id
    )

    observations = (
        evaluate_critical_identifier_portfolio_case_observations(
            case
        )
    )

    baseline = compare_critical_identifier_portfolio_case(
        case=case,
        observations=observations,
    )

    assert baseline.passed is True

    corrupted = tuple(
        (
            replace(
                observation,
                value=corrupted_value,
            )
            if observation.metric_key == metric_key
            else observation
        )
        for observation in observations
    )

    assert corrupted != observations

    result = compare_critical_identifier_portfolio_case(
        case=case,
        observations=corrupted,
    )

    assert result.passed is False
    assert expected_failed_check in result.failed_checks

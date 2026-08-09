from __future__ import annotations

from collections import defaultdict

from hvee.packs.asr.critical_number_fidelity import (
    ASRCriticalNumberFidelityOutcome,
    ASRCriticalNumberType,
)
from hvee.packs.asr.critical_number_portfolio import (
    CRITICAL_NUMBER_FIDELITY_PORTFOLIO_V1,
    CRITICAL_NUMBER_PORTFOLIO_KEY,
    CRITICAL_NUMBER_PORTFOLIO_VERSION,
    ASRCriticalNumberPortfolioOperation,
    ASRCriticalNumberPortfolioPartition,
    run_critical_number_portfolio,
)


def test_complete_critical_number_portfolio_passes():
    report = run_critical_number_portfolio(
        CRITICAL_NUMBER_FIDELITY_PORTFOLIO_V1
    )

    assert report.portfolio_key == CRITICAL_NUMBER_PORTFOLIO_KEY
    assert report.portfolio_version == CRITICAL_NUMBER_PORTFOLIO_VERSION
    assert report.total_cases == 29
    assert report.passed_cases == 29
    assert report.failed_cases == 0
    assert report.passed is True


def test_each_supported_type_has_full_error_matrix():
    operations_by_type = defaultdict(set)
    for case in CRITICAL_NUMBER_FIDELITY_PORTFOLIO_V1.cases:
        operations_by_type[case.numeric_type].add(case.operation)

    required_operations = {
        ASRCriticalNumberPortfolioOperation.EQUIVALENCE,
        ASRCriticalNumberPortfolioOperation.SUBSTITUTION,
        ASRCriticalNumberPortfolioOperation.OMISSION,
        ASRCriticalNumberPortfolioOperation.INSERTION,
    }
    supported_types = {
        ASRCriticalNumberType.CARDINAL_DECIMAL,
        ASRCriticalNumberType.PERCENTAGE,
        ASRCriticalNumberType.CURRENCY,
        ASRCriticalNumberType.MEASUREMENT,
        ASRCriticalNumberType.CLOCK_TIME,
        ASRCriticalNumberType.CALENDAR_DATE,
    }

    for numeric_type in supported_types:
        assert required_operations <= operations_by_type[numeric_type]


def test_portfolio_separates_calibration_and_regression_holdout_cases():
    partitions = {
        case.partition for case in CRITICAL_NUMBER_FIDELITY_PORTFOLIO_V1.cases
    }

    assert partitions == {
        ASRCriticalNumberPortfolioPartition.CALIBRATION,
        ASRCriticalNumberPortfolioPartition.REGRESSION_HOLDOUT,
    }
    assert all(
        case.case_id.startswith("calibration.")
        if case.partition == ASRCriticalNumberPortfolioPartition.CALIBRATION
        else case.case_id.startswith("holdout.")
        for case in CRITICAL_NUMBER_FIDELITY_PORTFOLIO_V1.cases
    )


def test_dangerous_cases_have_zero_false_passes():
    dangerous_operations = {
        ASRCriticalNumberPortfolioOperation.SUBSTITUTION,
        ASRCriticalNumberPortfolioOperation.OMISSION,
        ASRCriticalNumberPortfolioOperation.INSERTION,
    }

    dangerous_cases = tuple(
        case
        for case in CRITICAL_NUMBER_FIDELITY_PORTFOLIO_V1.cases
        if case.operation in dangerous_operations
    )

    assert dangerous_cases
    assert all(
        case.expected_outcome == ASRCriticalNumberFidelityOutcome.NOT_PRESERVED
        and case.expected_preserved is False
        for case in dangerous_cases
    )


def test_supported_equivalences_have_zero_false_failures():
    equivalence_cases = tuple(
        case
        for case in CRITICAL_NUMBER_FIDELITY_PORTFOLIO_V1.cases
        if case.operation == ASRCriticalNumberPortfolioOperation.EQUIVALENCE
    )

    assert len(equivalence_cases) == 6
    assert all(
        case.expected_outcome == ASRCriticalNumberFidelityOutcome.PRESERVED
        and case.expected_preserved is True
        for case in equivalence_cases
    )


def test_case_ids_and_portfolio_identity_are_unique_and_versioned():
    cases = CRITICAL_NUMBER_FIDELITY_PORTFOLIO_V1.cases
    case_ids = tuple(case.case_id for case in cases)

    assert len(case_ids) == len(set(case_ids))
    assert CRITICAL_NUMBER_FIDELITY_PORTFOLIO_V1.key == (
        "hetren.asr.critical-number-fidelity-portfolio.en-us"
    )
    assert CRITICAL_NUMBER_FIDELITY_PORTFOLIO_V1.version == "1.0.0"

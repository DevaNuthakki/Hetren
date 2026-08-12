from __future__ import annotations

from dataclasses import replace

import pytest

import hvee.packs.asr as asr
from hvee.core.contracts import (
    HveeContractError,
    ObservationStatus,
)
from hvee.packs.asr.critical_terminology_fidelity import (
    CRITICAL_TERMINOLOGY_OUTCOME_METRIC,
    CRITICAL_TERMINOLOGY_VOCABULARY_SHA256_METRIC,
    ASRCriticalTerminologyFidelityOutcome,
)
from hvee.packs.asr.critical_terminology_portfolio import (
    CRITICAL_TERMINOLOGY_FIDELITY_PORTFOLIO_V1,
    CRITICAL_TERMINOLOGY_PORTFOLIO_KEY,
    CRITICAL_TERMINOLOGY_PORTFOLIO_PROFILE_V1,
    CRITICAL_TERMINOLOGY_PORTFOLIO_VERSION,
    CRITICAL_TERMINOLOGY_PORTFOLIO_VOCABULARY_SHA256,
    ASRCriticalTerminologyPortfolioCaseResult,
    ASRCriticalTerminologyPortfolioOperation,
    ASRCriticalTerminologyPortfolioPartition,
    ASRCriticalTerminologyPortfolioReport,
    compare_critical_terminology_portfolio_case,
    evaluate_critical_terminology_portfolio_case_observations,
    run_critical_terminology_portfolio,
    run_critical_terminology_portfolio_case,
)


PORTFOLIO = (
    CRITICAL_TERMINOLOGY_FIDELITY_PORTFOLIO_V1
)
PROFILE = (
    CRITICAL_TERMINOLOGY_PORTFOLIO_PROFILE_V1
)


def test_complete_critical_terminology_portfolio_passes():
    report = run_critical_terminology_portfolio(
        PORTFOLIO
    )

    assert isinstance(
        report,
        ASRCriticalTerminologyPortfolioReport,
    )
    assert report.total_cases == 24
    assert report.passed_cases == 24
    assert report.failed_cases == 0
    assert report.passed is True


def test_portfolio_has_both_source_visible_partitions():
    partitions = {
        case.partition
        for case in PORTFOLIO.cases
    }

    assert partitions == {
        (
            ASRCriticalTerminologyPortfolioPartition
            .CALIBRATION
        ),
        (
            ASRCriticalTerminologyPortfolioPartition
            .REGRESSION_HOLDOUT
        ),
    }


def test_every_v1_operation_has_portfolio_evidence():
    operations = {
        case.operation
        for case in PORTFOLIO.cases
    }

    assert operations == set(
        ASRCriticalTerminologyPortfolioOperation
    )


def test_portfolio_identity_and_case_ids_are_stable():
    assert PORTFOLIO.key == (
        CRITICAL_TERMINOLOGY_PORTFOLIO_KEY
    )
    assert PORTFOLIO.version == (
        CRITICAL_TERMINOLOGY_PORTFOLIO_VERSION
    )

    case_ids = tuple(
        case.case_id
        for case in PORTFOLIO.cases
    )

    assert len(case_ids) == len(
        set(case_ids)
    )

    assert all(
        case_id
        and case_id == case_id.strip()
        for case_id in case_ids
    )


def test_portfolio_owns_one_exact_pinned_vocabulary():
    assert PORTFOLIO.profile is PROFILE

    assert PORTFOLIO.vocabulary_sha256 == (
        CRITICAL_TERMINOLOGY_PORTFOLIO_VOCABULARY_SHA256
    )

    assert len(
        PORTFOLIO.vocabulary_sha256
    ) == 64


def test_equivalence_cases_have_zero_false_failures():
    equivalence_cases = tuple(
        case
        for case in PORTFOLIO.cases
        if case.operation
        == (
            ASRCriticalTerminologyPortfolioOperation
            .EQUIVALENCE
        )
    )

    assert equivalence_cases

    for case in equivalence_cases:
        result = (
            run_critical_terminology_portfolio_case(
                case,
                profile=PROFILE,
            )
        )

        assert result.passed is True
        assert case.expected_outcome == (
            ASRCriticalTerminologyFidelityOutcome
            .PRESERVED
        )


def test_dangerous_error_cases_have_zero_false_passes():
    error_operations = {
        ASRCriticalTerminologyPortfolioOperation.SUBSTITUTION,
        ASRCriticalTerminologyPortfolioOperation.OMISSION,
        ASRCriticalTerminologyPortfolioOperation.INSERTION,
        (
            ASRCriticalTerminologyPortfolioOperation
            .ORDERING_CHANGE
        ),
        (
            ASRCriticalTerminologyPortfolioOperation
            .DUPLICATE_OMISSION
        ),
        (
            ASRCriticalTerminologyPortfolioOperation
            .UNREGISTERED_RENDERING
        ),
    }

    dangerous_cases = tuple(
        case
        for case in PORTFOLIO.cases
        if case.operation in error_operations
        or (
            case.operation
            == (
                ASRCriticalTerminologyPortfolioOperation
                .PUNCTUATION_CONTROL
            )
            and case.expected_outcome
            == (
                ASRCriticalTerminologyFidelityOutcome
                .NOT_PRESERVED
            )
        )
    )

    assert dangerous_cases

    for case in dangerous_cases:
        result = (
            run_critical_terminology_portfolio_case(
                case,
                profile=PROFILE,
            )
        )

        assert result.passed is True
        assert case.expected_preserved is False


def test_terminology_specific_regressions_are_pinned():
    case_ids = {
        case.case_id
        for case in PORTFOLIO.cases
    }

    required = {
        "regression.node-js-punctuation-loss",
        "regression.c-sharp-symbol-loss",
        "regression.longest-overlap-control",
        "regression.token-boundary-control",
        "regression.unregistered-phonetic-rendering",
        "regression.duplicate-omission",
        "regression.generated-only-k8s",
        "regression.multi-term-alias-preservation",
        "regression.mixed-substitution-and-match",
    }

    assert required <= case_ids


def test_not_applicable_case_pins_abstained_preservation():
    case = next(
        case
        for case in PORTFOLIO.cases
        if case.case_id
        == "regression.no-critical-terminology"
    )

    assert case.expected_applicable is False
    assert case.expected_preserved is None
    assert case.expected_preserved_status == (
        ObservationStatus.ABSTAINED
    )

    result = (
        run_critical_terminology_portfolio_case(
            case,
            profile=PROFILE,
        )
    )

    assert result.passed is True


def test_comparator_detects_outcome_corruption():
    case = next(
        case
        for case in PORTFOLIO.cases
        if case.case_id
        == "calibration.registered-term-substitution"
    )

    observations = list(
        evaluate_critical_terminology_portfolio_case_observations(
            case,
            profile=PROFILE,
        )
    )

    for index, observation in enumerate(
        observations
    ):
        if observation.metric_key == (
            CRITICAL_TERMINOLOGY_OUTCOME_METRIC.key
        ):
            observations[index] = replace(
                observation,
                value="preserved",
            )

    result = (
        compare_critical_terminology_portfolio_case(
            case=case,
            observations=tuple(
                observations
            ),
            profile=PROFILE,
        )
    )

    assert result.passed is False
    assert "outcome" in (
        result.failed_checks
    )


def test_comparator_detects_vocabulary_identity_corruption():
    case = PORTFOLIO.cases[0]

    observations = list(
        evaluate_critical_terminology_portfolio_case_observations(
            case,
            profile=PROFILE,
        )
    )

    for index, observation in enumerate(
        observations
    ):
        if observation.metric_key == (
            CRITICAL_TERMINOLOGY_VOCABULARY_SHA256_METRIC
            .key
        ):
            observations[index] = replace(
                observation,
                value=("0" * 64),
            )

    result = (
        compare_critical_terminology_portfolio_case(
            case=case,
            observations=tuple(
                observations
            ),
            profile=PROFILE,
        )
    )

    assert result.passed is False
    assert "vocabulary_sha256" in (
        result.failed_checks
    )


def test_comparator_rejects_scientific_identity_drift():
    case = PORTFOLIO.cases[0]

    observations = list(
        evaluate_critical_terminology_portfolio_case_observations(
            case,
            profile=PROFILE,
        )
    )

    observations[0] = replace(
        observations[0],
        evaluator_version="999.0.0",
    )

    with pytest.raises(
        HveeContractError,
        match="scientific identity changed",
    ):
        compare_critical_terminology_portfolio_case(
            case=case,
            observations=tuple(
                observations
            ),
            profile=PROFILE,
        )


def test_comparator_rejects_incomplete_metric_contract():
    case = PORTFOLIO.cases[0]

    observations = (
        evaluate_critical_terminology_portfolio_case_observations(
            case,
            profile=PROFILE,
        )
    )

    with pytest.raises(
        HveeContractError,
        match="complete metric contract",
    ):
        compare_critical_terminology_portfolio_case(
            case=case,
            observations=observations[:-1],
            profile=PROFILE,
        )


def test_comparator_pins_detailed_finding_signature():
    case = next(
        case
        for case in PORTFOLIO.cases
        if case.case_id
        == "calibration.registered-term-substitution"
    )

    observations = list(
        evaluate_critical_terminology_portfolio_case_observations(
            case,
            profile=PROFILE,
        )
    )

    from hvee.packs.asr.critical_terminology_fidelity import (
        CRITICAL_TERMINOLOGY_FINDINGS_METRIC,
    )

    for index, observation in enumerate(
        observations
    ):
        if observation.metric_key == (
            CRITICAL_TERMINOLOGY_FINDINGS_METRIC.key
        ):
            observations[index] = replace(
                observation,
                value=[],
            )

    result = (
        compare_critical_terminology_portfolio_case(
            case=case,
            observations=tuple(
                observations
            ),
            profile=PROFILE,
        )
    )

    assert result.passed is False
    assert "findings" in result.failed_checks


def test_case_runner_returns_public_result_type():
    result = (
        run_critical_terminology_portfolio_case(
            PORTFOLIO.cases[0],
            profile=PROFILE,
        )
    )

    assert type(result) is (
        ASRCriticalTerminologyPortfolioCaseResult
    )


def test_generic_laboratory_preserves_public_report_type():
    report = run_critical_terminology_portfolio(
        PORTFOLIO
    )

    assert type(report) is (
        ASRCriticalTerminologyPortfolioReport
    )
    assert report.total_cases == 24
    assert report.passed_cases == 24
    assert report.failed_cases == 0


def test_public_asr_portfolio_exports_are_available():
    expected = (
        "ASRCriticalTerminologyFindingExpectation",
        "ASRCriticalTerminologyPortfolioCase",
        "ASRCriticalTerminologyPortfolioCaseResult",
        "ASRCriticalTerminologyPortfolioDefinition",
        "ASRCriticalTerminologyPortfolioOperation",
        "ASRCriticalTerminologyPortfolioPartition",
        "ASRCriticalTerminologyPortfolioReport",
        "CRITICAL_TERMINOLOGY_FIDELITY_PORTFOLIO_V1",
        "CRITICAL_TERMINOLOGY_PORTFOLIO_KEY",
        "CRITICAL_TERMINOLOGY_PORTFOLIO_PROFILE_V1",
        "CRITICAL_TERMINOLOGY_PORTFOLIO_VERSION",
        "CRITICAL_TERMINOLOGY_PORTFOLIO_VOCABULARY_SHA256",
        "compare_critical_terminology_portfolio_case",
        "evaluate_critical_terminology_portfolio_case_observations",
        "run_critical_terminology_portfolio",
        "run_critical_terminology_portfolio_case",
    )

    for name in expected:
        assert hasattr(
            asr,
            name,
        )


def test_v1_portfolio_vocabulary_sha256_is_pinned():
    assert (
        CRITICAL_TERMINOLOGY_PORTFOLIO_VOCABULARY_SHA256
        == "f4b8923111d6497276549193f5126863ef37afadb93199b25f3749be257627e7"
    )

    assert (
        PORTFOLIO.vocabulary_sha256
        == "f4b8923111d6497276549193f5126863ef37afadb93199b25f3749be257627e7"
    )

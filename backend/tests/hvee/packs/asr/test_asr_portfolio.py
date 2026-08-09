from __future__ import annotations

import pytest

from hvee.core.contracts import (
    HveeContractError,
    MetricValueType,
)
from hvee.packs.asr.portfolio import (
    ASR_EVALUATION_PORTFOLIO_KEY,
    ASR_EVALUATION_PORTFOLIO_V1,
    ASR_EVALUATION_PORTFOLIO_VERSION,
    ASRPortfolioCase,
    ASRPortfolioDefinition,
    ASRPortfolioExpectedObservation,
    ASRPortfolioMutation,
)


def _case(
    case_id: str,
) -> ASRPortfolioCase:
    matches = [
        case
        for case
        in ASR_EVALUATION_PORTFOLIO_V1.cases
        if case.case_id == case_id
    ]

    assert len(matches) == 1
    return matches[0]


def _expected(
    case: ASRPortfolioCase,
    metric_key: str,
) -> object:
    matches = [
        expectation
        for expectation
        in case.expectations
        if expectation.metric_key == metric_key
    ]

    assert len(matches) == 1
    return matches[0].expected_value


def test_portfolio_v1_has_stable_identity_and_case_count():
    assert (
        ASR_EVALUATION_PORTFOLIO_V1.key
        == ASR_EVALUATION_PORTFOLIO_KEY
    )
    assert (
        ASR_EVALUATION_PORTFOLIO_V1.version
        == ASR_EVALUATION_PORTFOLIO_VERSION
    )
    assert len(
        ASR_EVALUATION_PORTFOLIO_V1.cases
    ) == 12


def test_portfolio_case_ids_are_unique():
    case_ids = [
        case.case_id
        for case
        in ASR_EVALUATION_PORTFOLIO_V1.cases
    ]

    assert len(case_ids) == len(
        set(case_ids)
    )


def test_portfolio_contains_controls_and_failures():
    mutations = {
        case.mutation
        for case
        in ASR_EVALUATION_PORTFOLIO_V1.cases
    }

    assert ASRPortfolioMutation.NONE in mutations
    assert (
        ASRPortfolioMutation
        .NORMALIZATION_EQUIVALENT
        in mutations
    )
    assert (
        ASRPortfolioMutation.MISSING_OUTPUT
        in mutations
    )
    assert (
        ASRPortfolioMutation.NUMERIC_REORDER
        in mutations
    )


def test_normalization_control_expects_zero_word_edits():
    case = _case(
        "control.normalization-equivalent"
    )

    assert _expected(
        case,
        "asr.exact-match.normalized-basic",
    ) is True

    assert _expected(
        case,
        "asr.substitutions.normalized-basic",
    ) == 0

    assert _expected(
        case,
        "asr.insertions.normalized-basic",
    ) == 0

    assert _expected(
        case,
        "asr.deletions.normalized-basic",
    ) == 0


def test_missing_output_has_explicit_integrity_ground_truth():
    case = _case(
        "mutation.missing-output"
    )

    assert _expected(
        case,
        "asr.generated-empty.normalized-basic",
    ) is True

    assert _expected(
        case,
        "asr.missing-output.normalized-basic",
    ) is True

    assert _expected(
        case,
        "asr.unexpected-output.normalized-basic",
    ) is False


def test_unexpected_output_is_not_named_hallucination():
    case = _case(
        "mutation.unexpected-output"
    )

    assert _expected(
        case,
        "asr.reference-empty.normalized-basic",
    ) is True

    assert _expected(
        case,
        "asr.unexpected-output.normalized-basic",
    ) is True

    assert "hallucination" in (
        case.description
    )
    assert "not proof" in (
        case.description
    )


def test_numeric_substitution_distinguishes_missing_and_unexpected():
    case = _case(
        "mutation.numeric-substitution"
    )

    assert _expected(
        case,
        "asr.numeric-token-sequence-match.digit-form",
    ) is False

    assert _expected(
        case,
        "asr.numeric-missing-count.digit-form",
    ) == 1

    assert _expected(
        case,
        "asr.numeric-unexpected-count.digit-form",
    ) == 1


def test_numeric_reorder_detects_order_without_multiset_loss():
    case = _case(
        "mutation.numeric-reorder"
    )

    assert _expected(
        case,
        "asr.numeric-token-sequence-match.digit-form",
    ) is False

    assert _expected(
        case,
        "asr.numeric-missing-count.digit-form",
    ) == 0

    assert _expected(
        case,
        "asr.numeric-unexpected-count.digit-form",
    ) == 0


def test_duplicate_expectation_identity_is_rejected():
    expectation = (
        ASRPortfolioExpectedObservation(
            metric_key="metric",
            metric_version="1",
            evaluator_key="evaluator",
            evaluator_version="1",
            value_type=MetricValueType.BOOLEAN,
            expected_value=True,
        )
    )

    with pytest.raises(
        HveeContractError,
        match="duplicate expectation",
    ):
        ASRPortfolioCase(
            case_id="duplicate",
            mutation=ASRPortfolioMutation.NONE,
            reference_text="a",
            generated_text="a",
            description="Duplicate expectation test.",
            expectations=(
                expectation,
                expectation,
            ),
            tags=("test",),
        )


def test_duplicate_case_ids_are_rejected():
    case = _case("control.exact")

    with pytest.raises(
        HveeContractError,
        match="case ids",
    ):
        ASRPortfolioDefinition(
            key="portfolio",
            version="1",
            cases=(
                case,
                case,
            ),
        )


def test_integer_expectation_rejects_boolean_value():
    with pytest.raises(
        HveeContractError,
        match="requires int",
    ):
        ASRPortfolioExpectedObservation(
            metric_key="metric",
            metric_version="1",
            evaluator_key="evaluator",
            evaluator_version="1",
            value_type=MetricValueType.INTEGER,
            expected_value=True,
        )

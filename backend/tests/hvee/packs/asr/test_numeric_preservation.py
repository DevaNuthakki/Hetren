import pytest

from hvee.core.contracts import (
    HveeContractError,
    MetricDirection,
    MetricValueType,
)
from hvee.core.validation import (
    validate_observation_contract,
)
from hvee.packs.asr import (
    ASRNumericPreservationEvaluation,
    DIGIT_FORM_NUMERIC_EXTRACTION,
    GENERATED_NUMERIC_TOKEN_COUNT_METRIC,
    MISSING_NUMERIC_TOKEN_COUNT_METRIC,
    NUMERIC_TOKEN_PRESERVATION_EVALUATOR,
    NUMERIC_TOKEN_SEQUENCE_MATCH_METRIC,
    REFERENCE_NUMERIC_TOKEN_COUNT_METRIC,
    UNEXPECTED_NUMERIC_TOKEN_COUNT_METRIC,
    build_numeric_preservation_observations,
    evaluate_numeric_preservation,
    extract_digit_form_numeric_tokens,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("no numbers here", ()),
        ("dose 15 mg", ("15",)),
        ("value 10.5", ("10.5",)),
        ("total 1,250", ("1,250",)),
        ("meet at 3:30", ("3:30",)),
        ("call 555-0123", ("555-0123",)),
        ("date 08/08/2026", ("08/08/2026",)),
        (
            "IDs 48217 and 900",
            ("48217", "900"),
        ),
        (
            "fullwidth １５ and ３：３０",
            ("15", "3:30"),
        ),
    ],
)
def test_digit_form_numeric_extraction_golden_vectors(
    text,
    expected,
):
    assert (
        extract_digit_form_numeric_tokens(text)
        == expected
    )


def test_extractor_requires_string():
    with pytest.raises(
        HveeContractError,
        match="requires a string",
    ):
        extract_digit_form_numeric_tokens(15)  # type: ignore[arg-type]


def test_exact_numeric_sequence_is_preserved():
    evaluation = evaluate_numeric_preservation(
        reference_text="dose 15 then 20",
        generated_text="dose 15 then 20",
    )

    assert evaluation.reference_tokens == (
        "15",
        "20",
    )
    assert evaluation.generated_tokens == (
        "15",
        "20",
    )
    assert evaluation.reference_count == 2
    assert evaluation.generated_count == 2
    assert evaluation.sequence_match is True
    assert evaluation.missing_count == 0
    assert evaluation.unexpected_count == 0


def test_numeric_substitution_is_missing_and_unexpected():
    evaluation = evaluate_numeric_preservation(
        reference_text="dose 15 mg",
        generated_text="dose 50 mg",
    )

    assert evaluation.sequence_match is False
    assert evaluation.missing_count == 1
    assert evaluation.unexpected_count == 1


def test_duplicate_numeric_tokens_use_multiset_counts():
    evaluation = evaluate_numeric_preservation(
        reference_text="15 then 15",
        generated_text="15",
    )

    assert evaluation.reference_count == 2
    assert evaluation.generated_count == 1
    assert evaluation.sequence_match is False
    assert evaluation.missing_count == 1
    assert evaluation.unexpected_count == 0


def test_reordered_numeric_tokens_fail_sequence_match_without_count_delta():
    evaluation = evaluate_numeric_preservation(
        reference_text="10 then 20",
        generated_text="20 then 10",
    )

    assert evaluation.sequence_match is False
    assert evaluation.missing_count == 0
    assert evaluation.unexpected_count == 0


def test_no_numeric_tokens_on_either_side_is_exact_sequence_match():
    evaluation = evaluate_numeric_preservation(
        reference_text="hello world",
        generated_text="hello there",
    )

    assert evaluation.reference_count == 0
    assert evaluation.generated_count == 0
    assert evaluation.sequence_match is True
    assert evaluation.missing_count == 0
    assert evaluation.unexpected_count == 0


def test_digit_form_comparison_is_intentionally_strict():
    evaluation = evaluate_numeric_preservation(
        reference_text="total 1,250",
        generated_text="total 1250",
    )

    assert evaluation.reference_tokens == (
        "1,250",
    )
    assert evaluation.generated_tokens == (
        "1250",
    )
    assert evaluation.sequence_match is False
    assert evaluation.missing_count == 1
    assert evaluation.unexpected_count == 1


def test_word_number_and_digit_are_not_semantically_equated():
    evaluation = evaluate_numeric_preservation(
        reference_text="dose fifteen",
        generated_text="dose 15",
    )

    assert evaluation.reference_tokens == ()
    assert evaluation.generated_tokens == (
        "15",
    )
    assert evaluation.sequence_match is False
    assert evaluation.missing_count == 0
    assert evaluation.unexpected_count == 1


def test_numeric_metric_contracts():
    assert (
        REFERENCE_NUMERIC_TOKEN_COUNT_METRIC.value_type
        == MetricValueType.INTEGER
    )
    assert (
        REFERENCE_NUMERIC_TOKEN_COUNT_METRIC.direction
        == MetricDirection.INFORMATIONAL
    )
    assert (
        GENERATED_NUMERIC_TOKEN_COUNT_METRIC.direction
        == MetricDirection.INFORMATIONAL
    )
    assert (
        NUMERIC_TOKEN_SEQUENCE_MATCH_METRIC.value_type
        == MetricValueType.BOOLEAN
    )
    assert (
        NUMERIC_TOKEN_SEQUENCE_MATCH_METRIC.direction
        == MetricDirection.HIGHER_IS_BETTER
    )
    assert (
        MISSING_NUMERIC_TOKEN_COUNT_METRIC.direction
        == MetricDirection.LOWER_IS_BETTER
    )
    assert (
        UNEXPECTED_NUMERIC_TOKEN_COUNT_METRIC.direction
        == MetricDirection.LOWER_IS_BETTER
    )


def test_builds_valid_numeric_preservation_observations():
    evaluation = evaluate_numeric_preservation(
        reference_text="dose 15",
        generated_text="dose 50",
    )

    observations = (
        build_numeric_preservation_observations(
            evaluation
        )
    )

    metrics = (
        REFERENCE_NUMERIC_TOKEN_COUNT_METRIC,
        GENERATED_NUMERIC_TOKEN_COUNT_METRIC,
        NUMERIC_TOKEN_SEQUENCE_MATCH_METRIC,
        MISSING_NUMERIC_TOKEN_COUNT_METRIC,
        UNEXPECTED_NUMERIC_TOKEN_COUNT_METRIC,
    )

    expected_values = (
        1,
        1,
        False,
        1,
        1,
    )

    assert len(observations) == 5

    for observation, metric, expected in zip(
        observations,
        metrics,
        expected_values,
        strict=True,
    ):
        assert observation.value == expected

        validate_observation_contract(
            metric=metric,
            evaluator=(
                NUMERIC_TOKEN_PRESERVATION_EVALUATOR
            ),
            observation=observation,
        )


def test_observation_builder_rejects_wrong_extraction_identity():
    evaluation = ASRNumericPreservationEvaluation(
        extraction_key="other.extractor",
        extraction_version="9.9.9",
        reference_tokens=("15",),
        generated_tokens=("15",),
        reference_count=1,
        generated_count=1,
        sequence_match=True,
        missing_count=0,
        unexpected_count=0,
    )

    with pytest.raises(
        HveeContractError,
        match="digit-form extraction profile",
    ):
        build_numeric_preservation_observations(
            evaluation
        )


def test_extraction_profile_is_versioned():
    assert DIGIT_FORM_NUMERIC_EXTRACTION.key == (
        "hetren.asr.numeric.digit-form"
    )
    assert (
        DIGIT_FORM_NUMERIC_EXTRACTION.version
        == "1.0.0"
    )

    assert (
        NUMERIC_TOKEN_PRESERVATION_EVALUATOR.key
        == "hetren.asr.numeric-preservation.digit-form"
    )
    assert (
        NUMERIC_TOKEN_PRESERVATION_EVALUATOR.version
        == "1.0.0"
    )

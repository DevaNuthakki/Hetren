import pytest

from hvee.core.contracts import (
    HveeContractError,
    MetricDirection,
    MetricValueType,
    ObservationStatus,
)
from hvee.core.validation import (
    validate_observation_contract,
)
from hvee.packs.asr import (
    ASRNormalizedTextEvaluation,
    EXACT_NORMALIZED_MATCH_METRIC,
    GENERATED_EMPTY_METRIC,
    MISSING_OUTPUT_METRIC,
    REFERENCE_EMPTY_METRIC,
    TRANSCRIPT_INTEGRITY_EVALUATOR,
    UNEXPECTED_OUTPUT_METRIC,
    build_transcript_integrity_observations,
    evaluate_normalized_transcript_pair,
    evaluate_transcript_integrity,
)


def _evaluate(
    reference_text: str,
    generated_text: str,
):
    normalized = evaluate_normalized_transcript_pair(
        reference_text=reference_text,
        generated_text=generated_text,
    )

    return evaluate_transcript_integrity(
        normalized
    )


def test_transcript_integrity_metrics_are_versioned():
    assert EXACT_NORMALIZED_MATCH_METRIC.key == (
        "asr.exact-match.normalized-basic"
    )
    assert (
        EXACT_NORMALIZED_MATCH_METRIC.version
        == "1.0.0"
    )
    assert (
        EXACT_NORMALIZED_MATCH_METRIC.value_type
        == MetricValueType.BOOLEAN
    )
    assert (
        EXACT_NORMALIZED_MATCH_METRIC.direction
        == MetricDirection.HIGHER_IS_BETTER
    )

    assert (
        REFERENCE_EMPTY_METRIC.direction
        == MetricDirection.INFORMATIONAL
    )
    assert (
        GENERATED_EMPTY_METRIC.direction
        == MetricDirection.INFORMATIONAL
    )
    assert (
        UNEXPECTED_OUTPUT_METRIC.direction
        == MetricDirection.LOWER_IS_BETTER
    )
    assert (
        MISSING_OUTPUT_METRIC.direction
        == MetricDirection.LOWER_IS_BETTER
    )


def test_transcript_integrity_evaluator_is_versioned():
    assert TRANSCRIPT_INTEGRITY_EVALUATOR.key == (
        "hetren.asr.transcript-integrity.normalized-basic"
    )
    assert (
        TRANSCRIPT_INTEGRITY_EVALUATOR.version
        == "1.0.0"
    )
    assert (
        TRANSCRIPT_INTEGRITY_EVALUATOR.evaluation_type
        == "asr"
    )


def test_normalization_equivalent_transcripts_exact_match():
    evaluation = _evaluate(
        "Hello, WORLD!",
        "hello world",
    )

    assert evaluation.exact_match is True
    assert evaluation.reference_empty is False
    assert evaluation.generated_empty is False
    assert evaluation.unexpected_output is False
    assert evaluation.missing_output is False


def test_empty_reference_with_output_is_unexpected_output():
    evaluation = _evaluate(
        " ... ",
        "hello there",
    )

    assert evaluation.reference_empty is True
    assert evaluation.generated_empty is False
    assert evaluation.exact_match is False
    assert evaluation.unexpected_output is True
    assert evaluation.missing_output is False


def test_nonempty_reference_with_empty_output_is_missing_output():
    evaluation = _evaluate(
        "expected speech",
        " !!! ",
    )

    assert evaluation.reference_empty is False
    assert evaluation.generated_empty is True
    assert evaluation.exact_match is False
    assert evaluation.unexpected_output is False
    assert evaluation.missing_output is True


def test_both_empty_is_exact_but_not_unexpected_or_missing():
    evaluation = _evaluate(
        " ... ",
        "   ",
    )

    assert evaluation.reference_empty is True
    assert evaluation.generated_empty is True
    assert evaluation.exact_match is True
    assert evaluation.unexpected_output is False
    assert evaluation.missing_output is False


def test_nonempty_mismatch_is_not_empty_output_failure():
    evaluation = _evaluate(
        "hello world",
        "goodbye world",
    )

    assert evaluation.exact_match is False
    assert evaluation.reference_empty is False
    assert evaluation.generated_empty is False
    assert evaluation.unexpected_output is False
    assert evaluation.missing_output is False


def test_integrity_rejects_wrong_normalization_identity():
    normalized = ASRNormalizedTextEvaluation(
        normalization_key="other.profile",
        normalization_version="9.9.9",
        normalized_reference="hello",
        normalized_generated="hello",
        wer=0.0,
        cer=0.0,
        substitutions=0,
        insertions=0,
        deletions=0,
    )

    with pytest.raises(
        HveeContractError,
        match="basic normalization profile",
    ):
        evaluate_transcript_integrity(
            normalized
        )


def test_integrity_builds_valid_boolean_observations():
    evaluation = _evaluate(
        "",
        "unexpected words",
    )

    observations = (
        build_transcript_integrity_observations(
            evaluation
        )
    )

    metrics = (
        EXACT_NORMALIZED_MATCH_METRIC,
        REFERENCE_EMPTY_METRIC,
        GENERATED_EMPTY_METRIC,
        UNEXPECTED_OUTPUT_METRIC,
        MISSING_OUTPUT_METRIC,
    )

    expected_values = (
        False,
        True,
        False,
        True,
        False,
    )

    assert len(observations) == 5

    for observation, metric, expected in zip(
        observations,
        metrics,
        expected_values,
        strict=True,
    ):
        assert (
            observation.status
            == ObservationStatus.SUCCESS
        )
        assert (
            observation.value_type
            == MetricValueType.BOOLEAN
        )
        assert observation.value is expected

        validate_observation_contract(
            metric=metric,
            evaluator=(
                TRANSCRIPT_INTEGRITY_EVALUATOR
            ),
            observation=observation,
        )


def test_unexpected_and_missing_output_are_mutually_exclusive():
    cases = (
        _evaluate("", ""),
        _evaluate("", "words"),
        _evaluate("words", ""),
        _evaluate("words", "different"),
    )

    for evaluation in cases:
        assert not (
            evaluation.unexpected_output
            and evaluation.missing_output
        )

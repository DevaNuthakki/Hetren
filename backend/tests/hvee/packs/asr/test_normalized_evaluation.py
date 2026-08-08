import pytest

from hvee.core.contracts import (
    MetricDirection,
    MetricValueType,
    ObservationStatus,
)
from hvee.packs.asr import (
    NORMALIZED_CER_EVALUATOR,
    NORMALIZED_CER_METRIC,
    NORMALIZED_DELETIONS_METRIC,
    NORMALIZED_INSERTIONS_METRIC,
    NORMALIZED_SUBSTITUTIONS_METRIC,
    NORMALIZED_WER_EVALUATOR,
    NORMALIZED_WER_METRIC,
    NORMALIZED_WORD_ALIGNMENT_EVALUATOR,
    build_normalized_error_observations,
    evaluate_normalized_transcript_pair,
    evaluate_transcript_pair,
)


def test_normalized_metric_identities_are_distinct():
    assert (
        NORMALIZED_WER_METRIC.key
        == "asr.wer.normalized-basic"
    )
    assert (
        NORMALIZED_CER_METRIC.key
        == "asr.cer.normalized-basic"
    )

    assert NORMALIZED_WER_METRIC.version == "1.0.0"
    assert NORMALIZED_CER_METRIC.version == "1.0.0"

    assert (
        NORMALIZED_WER_METRIC.direction
        == MetricDirection.LOWER_IS_BETTER
    )
    assert (
        NORMALIZED_CER_METRIC.direction
        == MetricDirection.LOWER_IS_BETTER
    )

    assert (
        NORMALIZED_WER_METRIC.value_type
        == MetricValueType.NUMBER
    )
    assert (
        NORMALIZED_CER_METRIC.value_type
        == MetricValueType.NUMBER
    )


def test_normalized_evaluator_identities_are_distinct():
    assert (
        NORMALIZED_WER_EVALUATOR.key
        == "hetren.asr.wer.normalized-basic"
    )
    assert (
        NORMALIZED_CER_EVALUATOR.key
        == "hetren.asr.cer.normalized-basic"
    )

    assert (
        NORMALIZED_WER_EVALUATOR.version
        == "1.0.0"
    )
    assert (
        NORMALIZED_CER_EVALUATOR.version
        == "1.0.0"
    )


def test_normalization_removes_case_and_punctuation_penalty():
    reference = "Hello, WORLD!"
    generated = "hello world"

    baseline = evaluate_transcript_pair(
        reference_text=reference,
        generated_text=generated,
    )

    normalized = evaluate_normalized_transcript_pair(
        reference_text=reference,
        generated_text=generated,
    )

    assert baseline.wer > 0.0
    assert baseline.cer > 0.0

    assert normalized.wer == 0.0
    assert normalized.cer == 0.0

    assert normalized.normalized_reference == (
        "hello world"
    )
    assert normalized.normalized_generated == (
        "hello world"
    )


def test_normalized_word_substitution_remains_real_error():
    evaluation = evaluate_normalized_transcript_pair(
        reference_text="Hello world.",
        generated_text="hello there",
    )

    assert evaluation.wer == pytest.approx(0.5)
    assert evaluation.substitutions == 1
    assert evaluation.insertions == 0
    assert evaluation.deletions == 0


def test_normalized_empty_pair_is_valid():
    evaluation = evaluate_normalized_transcript_pair(
        reference_text="...",
        generated_text="!!!",
    )

    assert evaluation.normalized_reference == ""
    assert evaluation.normalized_generated == ""
    assert evaluation.wer == 0.0
    assert evaluation.cer == 0.0


def test_normalized_silence_hallucination_is_detected():
    evaluation = evaluate_normalized_transcript_pair(
        reference_text="...",
        generated_text="hello",
    )

    assert evaluation.normalized_reference == ""
    assert evaluation.normalized_generated == "hello"
    assert evaluation.wer == pytest.approx(1.0)
    assert evaluation.insertions == 1


def test_normalized_observations_bind_exact_versions():
    evaluation = evaluate_normalized_transcript_pair(
        reference_text="Hello, world!",
        generated_text="hello world",
    )

    (
        wer_observation,
        cer_observation,
        substitutions_observation,
        insertions_observation,
        deletions_observation,
    ) = build_normalized_error_observations(
        evaluation
    )

    assert (
        wer_observation.metric_key
        == NORMALIZED_WER_METRIC.key
    )
    assert (
        wer_observation.metric_version
        == NORMALIZED_WER_METRIC.version
    )
    assert (
        wer_observation.evaluator_key
        == NORMALIZED_WER_EVALUATOR.key
    )
    assert (
        wer_observation.evaluator_version
        == NORMALIZED_WER_EVALUATOR.version
    )
    assert (
        wer_observation.status
        == ObservationStatus.SUCCESS
    )
    assert wer_observation.value == 0.0

    assert (
        cer_observation.metric_key
        == NORMALIZED_CER_METRIC.key
    )
    assert (
        cer_observation.metric_version
        == NORMALIZED_CER_METRIC.version
    )
    assert (
        cer_observation.evaluator_key
        == NORMALIZED_CER_EVALUATOR.key
    )
    assert (
        cer_observation.evaluator_version
        == NORMALIZED_CER_EVALUATOR.version
    )
    assert (
        cer_observation.status
        == ObservationStatus.SUCCESS
    )
    assert cer_observation.value == 0.0


def test_normalized_alignment_metrics_are_versioned_counts():
    assert (
        NORMALIZED_SUBSTITUTIONS_METRIC.key
        == "asr.substitutions.normalized-basic"
    )
    assert (
        NORMALIZED_INSERTIONS_METRIC.key
        == "asr.insertions.normalized-basic"
    )
    assert (
        NORMALIZED_DELETIONS_METRIC.key
        == "asr.deletions.normalized-basic"
    )

    for metric in (
        NORMALIZED_SUBSTITUTIONS_METRIC,
        NORMALIZED_INSERTIONS_METRIC,
        NORMALIZED_DELETIONS_METRIC,
    ):
        assert metric.version == "1.0.0"
        assert metric.value_type == MetricValueType.INTEGER
        assert (
            metric.direction
            == MetricDirection.LOWER_IS_BETTER
        )
        assert metric.unit == "count"


def test_normalized_alignment_observations_preserve_counts():
    evaluation = evaluate_normalized_transcript_pair(
        reference_text="one two three",
        generated_text="one four extra",
    )

    (
        _wer,
        _cer,
        substitutions,
        insertions,
        deletions,
    ) = build_normalized_error_observations(
        evaluation
    )

    assert substitutions.metric_key == (
        NORMALIZED_SUBSTITUTIONS_METRIC.key
    )
    assert insertions.metric_key == (
        NORMALIZED_INSERTIONS_METRIC.key
    )
    assert deletions.metric_key == (
        NORMALIZED_DELETIONS_METRIC.key
    )

    for observation in (
        substitutions,
        insertions,
        deletions,
    ):
        assert observation.evaluator_key == (
            NORMALIZED_WORD_ALIGNMENT_EVALUATOR.key
        )
        assert observation.evaluator_version == (
            NORMALIZED_WORD_ALIGNMENT_EVALUATOR.version
        )
        assert (
            observation.value_type
            == MetricValueType.INTEGER
        )

    assert substitutions.value == evaluation.substitutions
    assert insertions.value == evaluation.insertions
    assert deletions.value == evaluation.deletions

import pytest

from hvee.core.contracts import (
    MetricDirection,
    MetricValueType,
    ObservationStatus,
)
from hvee.packs.asr import (
    CER_EVALUATOR,
    CER_METRIC,
    WER_EVALUATOR,
    WER_METRIC,
    build_text_error_observations,
    evaluate_transcript_pair,
)


def test_asr_metric_definitions_are_versioned():
    assert WER_METRIC.key == "asr.wer"
    assert WER_METRIC.version == "1.0.0"
    assert WER_METRIC.evaluation_type == "asr"
    assert WER_METRIC.value_type == MetricValueType.NUMBER
    assert (
        WER_METRIC.direction
        == MetricDirection.LOWER_IS_BETTER
    )
    assert WER_METRIC.unit == "ratio"

    assert CER_METRIC.key == "asr.cer"
    assert CER_METRIC.version == "1.0.0"
    assert CER_METRIC.evaluation_type == "asr"
    assert CER_METRIC.value_type == MetricValueType.NUMBER
    assert (
        CER_METRIC.direction
        == MetricDirection.LOWER_IS_BETTER
    )
    assert CER_METRIC.unit == "ratio"


def test_asr_evaluator_versions_have_independent_identity():
    assert WER_EVALUATOR.key == "hetren.asr.wer"
    assert WER_EVALUATOR.version == "1.0.0"
    assert WER_EVALUATOR.evaluation_type == "asr"

    assert CER_EVALUATOR.key == "hetren.asr.cer"
    assert CER_EVALUATOR.version == "1.0.0"
    assert CER_EVALUATOR.evaluation_type == "asr"


def test_identical_transcripts_have_zero_error():
    evaluation = evaluate_transcript_pair(
        reference_text="hello world",
        generated_text="hello world",
    )

    assert evaluation.wer == 0.0
    assert evaluation.cer == 0.0
    assert evaluation.substitutions == 0
    assert evaluation.insertions == 0
    assert evaluation.deletions == 0


def test_word_substitution_preserves_legacy_jiwer_semantics():
    evaluation = evaluate_transcript_pair(
        reference_text="a b",
        generated_text="a c",
    )

    assert evaluation.wer == pytest.approx(0.5)
    assert evaluation.cer == pytest.approx(1 / 3)
    assert evaluation.substitutions == 1
    assert evaluation.insertions == 0
    assert evaluation.deletions == 0


def test_word_deletion_is_exposed_for_legacy_summary():
    evaluation = evaluate_transcript_pair(
        reference_text="hello world",
        generated_text="hello",
    )

    assert evaluation.wer == pytest.approx(0.5)
    assert evaluation.substitutions == 0
    assert evaluation.insertions == 0
    assert evaluation.deletions == 1


def test_text_evaluation_builds_versioned_observations():
    evaluation = evaluate_transcript_pair(
        reference_text="a b",
        generated_text="a c",
    )

    wer_observation, cer_observation = (
        build_text_error_observations(evaluation)
    )

    assert wer_observation.metric_key == WER_METRIC.key
    assert (
        wer_observation.metric_version
        == WER_METRIC.version
    )
    assert (
        wer_observation.evaluator_key
        == WER_EVALUATOR.key
    )
    assert (
        wer_observation.evaluator_version
        == WER_EVALUATOR.version
    )
    assert wer_observation.status == ObservationStatus.SUCCESS
    assert wer_observation.value_type == MetricValueType.NUMBER
    assert wer_observation.value == evaluation.wer

    assert cer_observation.metric_key == CER_METRIC.key
    assert (
        cer_observation.metric_version
        == CER_METRIC.version
    )
    assert (
        cer_observation.evaluator_key
        == CER_EVALUATOR.key
    )
    assert (
        cer_observation.evaluator_version
        == CER_EVALUATOR.version
    )
    assert cer_observation.status == ObservationStatus.SUCCESS
    assert cer_observation.value_type == MetricValueType.NUMBER
    assert cer_observation.value == evaluation.cer

from __future__ import annotations

from dataclasses import dataclass

from jiwer import cer as calculate_cer
from jiwer import process_words

from hvee.core.contracts import (
    EvaluatorVersion,
    MetricDefinition,
    MetricDirection,
    MetricValueType,
    Observation,
    ObservationStatus,
)
from hvee.packs.asr.normalization import (
    BASIC_TEXT_NORMALIZATION,
    normalize_text_basic,
)


NORMALIZED_METRIC_VERSION = "1.0.0"
NORMALIZED_EVALUATOR_VERSION = "1.0.0"


NORMALIZED_WER_METRIC = MetricDefinition(
    key="asr.wer.normalized-basic",
    version=NORMALIZED_METRIC_VERSION,
    evaluation_type="asr",
    value_type=MetricValueType.NUMBER,
    direction=MetricDirection.LOWER_IS_BETTER,
    unit="ratio",
    description=(
        "Word error rate after Hetren basic transcript "
        "normalization v1.0.0."
    ),
)

NORMALIZED_CER_METRIC = MetricDefinition(
    key="asr.cer.normalized-basic",
    version=NORMALIZED_METRIC_VERSION,
    evaluation_type="asr",
    value_type=MetricValueType.NUMBER,
    direction=MetricDirection.LOWER_IS_BETTER,
    unit="ratio",
    description=(
        "Character error rate after Hetren basic transcript "
        "normalization v1.0.0."
    ),
)


NORMALIZED_SUBSTITUTIONS_METRIC = MetricDefinition(
    key="asr.substitutions.normalized-basic",
    version=NORMALIZED_METRIC_VERSION,
    evaluation_type="asr",
    value_type=MetricValueType.INTEGER,
    direction=MetricDirection.LOWER_IS_BETTER,
    unit="count",
    description=(
        "Word substitutions after Hetren basic transcript "
        "normalization v1.0.0."
    ),
)

NORMALIZED_INSERTIONS_METRIC = MetricDefinition(
    key="asr.insertions.normalized-basic",
    version=NORMALIZED_METRIC_VERSION,
    evaluation_type="asr",
    value_type=MetricValueType.INTEGER,
    direction=MetricDirection.LOWER_IS_BETTER,
    unit="count",
    description=(
        "Word insertions after Hetren basic transcript "
        "normalization v1.0.0."
    ),
)

NORMALIZED_DELETIONS_METRIC = MetricDefinition(
    key="asr.deletions.normalized-basic",
    version=NORMALIZED_METRIC_VERSION,
    evaluation_type="asr",
    value_type=MetricValueType.INTEGER,
    direction=MetricDirection.LOWER_IS_BETTER,
    unit="count",
    description=(
        "Word deletions after Hetren basic transcript "
        "normalization v1.0.0."
    ),
)


NORMALIZED_WER_EVALUATOR = EvaluatorVersion(
    key="hetren.asr.wer.normalized-basic",
    version=NORMALIZED_EVALUATOR_VERSION,
    evaluation_type="asr",
    description=(
        "Hetren normalized WER evaluator using the basic "
        "transcript normalization profile v1.0.0."
    ),
)

NORMALIZED_CER_EVALUATOR = EvaluatorVersion(
    key="hetren.asr.cer.normalized-basic",
    version=NORMALIZED_EVALUATOR_VERSION,
    evaluation_type="asr",
    description=(
        "Hetren normalized CER evaluator using the basic "
        "transcript normalization profile v1.0.0."
    ),
)


NORMALIZED_WORD_ALIGNMENT_EVALUATOR = EvaluatorVersion(
    key="hetren.asr.word-alignment.normalized-basic",
    version=NORMALIZED_EVALUATOR_VERSION,
    evaluation_type="asr",
    description=(
        "Hetren normalized word-alignment evaluator producing "
        "substitution, insertion, and deletion counts using the "
        "basic transcript normalization profile v1.0.0."
    ),
)


@dataclass(frozen=True, slots=True)
class ASRNormalizedTextEvaluation:
    normalization_key: str
    normalization_version: str
    normalized_reference: str
    normalized_generated: str
    wer: float
    cer: float
    substitutions: int
    insertions: int
    deletions: int


def evaluate_normalized_transcript_pair(
    *,
    reference_text: str,
    generated_text: str,
) -> ASRNormalizedTextEvaluation:
    normalized_reference = normalize_text_basic(
        reference_text
    )
    normalized_generated = normalize_text_basic(
        generated_text
    )

    word_result = process_words(
        normalized_reference,
        normalized_generated,
    )

    return ASRNormalizedTextEvaluation(
        normalization_key=(
            BASIC_TEXT_NORMALIZATION.key
        ),
        normalization_version=(
            BASIC_TEXT_NORMALIZATION.version
        ),
        normalized_reference=normalized_reference,
        normalized_generated=normalized_generated,
        wer=float(word_result.wer),
        cer=float(
            calculate_cer(
                normalized_reference,
                normalized_generated,
            )
        ),
        substitutions=word_result.substitutions,
        insertions=word_result.insertions,
        deletions=word_result.deletions,
    )


def build_normalized_error_observations(
    evaluation: ASRNormalizedTextEvaluation,
) -> tuple[
    Observation,
    Observation,
    Observation,
    Observation,
    Observation,
]:
    wer_observation = Observation(
        metric_key=NORMALIZED_WER_METRIC.key,
        metric_version=NORMALIZED_WER_METRIC.version,
        evaluator_key=NORMALIZED_WER_EVALUATOR.key,
        evaluator_version=NORMALIZED_WER_EVALUATOR.version,
        evaluation_type="asr",
        status=ObservationStatus.SUCCESS,
        value_type=MetricValueType.NUMBER,
        value=evaluation.wer,
    )

    cer_observation = Observation(
        metric_key=NORMALIZED_CER_METRIC.key,
        metric_version=NORMALIZED_CER_METRIC.version,
        evaluator_key=NORMALIZED_CER_EVALUATOR.key,
        evaluator_version=NORMALIZED_CER_EVALUATOR.version,
        evaluation_type="asr",
        status=ObservationStatus.SUCCESS,
        value_type=MetricValueType.NUMBER,
        value=evaluation.cer,
    )

    substitutions_observation = Observation(
        metric_key=NORMALIZED_SUBSTITUTIONS_METRIC.key,
        metric_version=(
            NORMALIZED_SUBSTITUTIONS_METRIC.version
        ),
        evaluator_key=(
            NORMALIZED_WORD_ALIGNMENT_EVALUATOR.key
        ),
        evaluator_version=(
            NORMALIZED_WORD_ALIGNMENT_EVALUATOR.version
        ),
        evaluation_type="asr",
        status=ObservationStatus.SUCCESS,
        value_type=MetricValueType.INTEGER,
        value=evaluation.substitutions,
    )

    insertions_observation = Observation(
        metric_key=NORMALIZED_INSERTIONS_METRIC.key,
        metric_version=NORMALIZED_INSERTIONS_METRIC.version,
        evaluator_key=(
            NORMALIZED_WORD_ALIGNMENT_EVALUATOR.key
        ),
        evaluator_version=(
            NORMALIZED_WORD_ALIGNMENT_EVALUATOR.version
        ),
        evaluation_type="asr",
        status=ObservationStatus.SUCCESS,
        value_type=MetricValueType.INTEGER,
        value=evaluation.insertions,
    )

    deletions_observation = Observation(
        metric_key=NORMALIZED_DELETIONS_METRIC.key,
        metric_version=NORMALIZED_DELETIONS_METRIC.version,
        evaluator_key=(
            NORMALIZED_WORD_ALIGNMENT_EVALUATOR.key
        ),
        evaluator_version=(
            NORMALIZED_WORD_ALIGNMENT_EVALUATOR.version
        ),
        evaluation_type="asr",
        status=ObservationStatus.SUCCESS,
        value_type=MetricValueType.INTEGER,
        value=evaluation.deletions,
    )

    return (
        wer_observation,
        cer_observation,
        substitutions_observation,
        insertions_observation,
        deletions_observation,
    )

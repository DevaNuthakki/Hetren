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


ASR_EVALUATION_TYPE = "asr"
ASR_METRIC_VERSION = "1.0.0"
ASR_EVALUATOR_VERSION = "1.0.0"


WER_METRIC = MetricDefinition(
    key="asr.wer",
    version=ASR_METRIC_VERSION,
    evaluation_type=ASR_EVALUATION_TYPE,
    value_type=MetricValueType.NUMBER,
    direction=MetricDirection.LOWER_IS_BETTER,
    unit="ratio",
    description=(
        "Word error rate between reference and generated "
        "transcripts."
    ),
)

CER_METRIC = MetricDefinition(
    key="asr.cer",
    version=ASR_METRIC_VERSION,
    evaluation_type=ASR_EVALUATION_TYPE,
    value_type=MetricValueType.NUMBER,
    direction=MetricDirection.LOWER_IS_BETTER,
    unit="ratio",
    description=(
        "Character error rate between reference and generated "
        "transcripts."
    ),
)


WER_EVALUATOR = EvaluatorVersion(
    key="hetren.asr.wer",
    version=ASR_EVALUATOR_VERSION,
    evaluation_type=ASR_EVALUATION_TYPE,
    description=(
        "Hetren ASR word error evaluator using JiWER "
        "word-alignment semantics."
    ),
)

CER_EVALUATOR = EvaluatorVersion(
    key="hetren.asr.cer",
    version=ASR_EVALUATOR_VERSION,
    evaluation_type=ASR_EVALUATION_TYPE,
    description=(
        "Hetren ASR character error evaluator using JiWER "
        "character-error semantics."
    ),
)


@dataclass(frozen=True, slots=True)
class ASRTextEvaluation:
    wer: float
    cer: float
    substitutions: int
    insertions: int
    deletions: int


def evaluate_transcript_pair(
    *,
    reference_text: str,
    generated_text: str,
) -> ASRTextEvaluation:
    """
    Evaluate one ASR transcript pair.

    Version 1.0.0 intentionally preserves the transcript handling
    and JiWER behavior used by Hetren before the HVEE integration.
    """

    word_result = process_words(
        reference_text,
        generated_text,
    )

    return ASRTextEvaluation(
        wer=float(word_result.wer),
        cer=float(
            calculate_cer(
                reference_text,
                generated_text,
            )
        ),
        substitutions=word_result.substitutions,
        insertions=word_result.insertions,
        deletions=word_result.deletions,
    )


def build_text_error_observations(
    evaluation: ASRTextEvaluation,
) -> tuple[Observation, Observation]:
    wer_observation = Observation(
        metric_key=WER_METRIC.key,
        metric_version=WER_METRIC.version,
        evaluator_key=WER_EVALUATOR.key,
        evaluator_version=WER_EVALUATOR.version,
        evaluation_type=ASR_EVALUATION_TYPE,
        status=ObservationStatus.SUCCESS,
        value_type=MetricValueType.NUMBER,
        value=evaluation.wer,
    )

    cer_observation = Observation(
        metric_key=CER_METRIC.key,
        metric_version=CER_METRIC.version,
        evaluator_key=CER_EVALUATOR.key,
        evaluator_version=CER_EVALUATOR.version,
        evaluation_type=ASR_EVALUATION_TYPE,
        status=ObservationStatus.SUCCESS,
        value_type=MetricValueType.NUMBER,
        value=evaluation.cer,
    )

    return wer_observation, cer_observation

from __future__ import annotations

from dataclasses import dataclass

from hvee.core.contracts import (
    EvaluatorVersion,
    HveeContractError,
    MetricDefinition,
    MetricDirection,
    MetricValueType,
    Observation,
    ObservationStatus,
)
from hvee.packs.asr.evaluation import (
    ASR_EVALUATION_TYPE,
)
from hvee.packs.asr.normalization import (
    BASIC_TEXT_NORMALIZATION,
)
from hvee.packs.asr.normalized_evaluation import (
    ASRNormalizedTextEvaluation,
)


TRANSCRIPT_INTEGRITY_METRIC_VERSION = "1.0.0"
TRANSCRIPT_INTEGRITY_EVALUATOR_VERSION = "1.0.0"


EXACT_NORMALIZED_MATCH_METRIC = MetricDefinition(
    key="asr.exact-match.normalized-basic",
    version=TRANSCRIPT_INTEGRITY_METRIC_VERSION,
    evaluation_type=ASR_EVALUATION_TYPE,
    value_type=MetricValueType.BOOLEAN,
    direction=MetricDirection.HIGHER_IS_BETTER,
    description=(
        "Whether reference and generated transcripts are exactly "
        "equal after Hetren basic transcript normalization v1.0.0."
    ),
)


REFERENCE_EMPTY_METRIC = MetricDefinition(
    key="asr.reference-empty.normalized-basic",
    version=TRANSCRIPT_INTEGRITY_METRIC_VERSION,
    evaluation_type=ASR_EVALUATION_TYPE,
    value_type=MetricValueType.BOOLEAN,
    direction=MetricDirection.INFORMATIONAL,
    description=(
        "Whether the reference transcript is empty after Hetren "
        "basic transcript normalization v1.0.0."
    ),
)


GENERATED_EMPTY_METRIC = MetricDefinition(
    key="asr.generated-empty.normalized-basic",
    version=TRANSCRIPT_INTEGRITY_METRIC_VERSION,
    evaluation_type=ASR_EVALUATION_TYPE,
    value_type=MetricValueType.BOOLEAN,
    direction=MetricDirection.INFORMATIONAL,
    description=(
        "Whether the generated transcript is empty after Hetren "
        "basic transcript normalization v1.0.0."
    ),
)


UNEXPECTED_OUTPUT_METRIC = MetricDefinition(
    key="asr.unexpected-output.normalized-basic",
    version=TRANSCRIPT_INTEGRITY_METRIC_VERSION,
    evaluation_type=ASR_EVALUATION_TYPE,
    value_type=MetricValueType.BOOLEAN,
    direction=MetricDirection.LOWER_IS_BETTER,
    description=(
        "Whether normalized generated text is non-empty while the "
        "normalized reference is empty. This is a transcript-level "
        "unexpected-output signal and does not by itself prove an "
        "acoustic hallucination."
    ),
)


MISSING_OUTPUT_METRIC = MetricDefinition(
    key="asr.missing-output.normalized-basic",
    version=TRANSCRIPT_INTEGRITY_METRIC_VERSION,
    evaluation_type=ASR_EVALUATION_TYPE,
    value_type=MetricValueType.BOOLEAN,
    direction=MetricDirection.LOWER_IS_BETTER,
    description=(
        "Whether normalized generated text is empty while the "
        "normalized reference is non-empty."
    ),
)


TRANSCRIPT_INTEGRITY_EVALUATOR = EvaluatorVersion(
    key="hetren.asr.transcript-integrity.normalized-basic",
    version=TRANSCRIPT_INTEGRITY_EVALUATOR_VERSION,
    evaluation_type=ASR_EVALUATION_TYPE,
    description=(
        "Deterministic Hetren ASR transcript-integrity evaluator "
        "operating on the basic normalized transcript pair."
    ),
)


@dataclass(frozen=True, slots=True)
class ASRTranscriptIntegrityEvaluation:
    normalization_key: str
    normalization_version: str
    exact_match: bool
    reference_empty: bool
    generated_empty: bool
    unexpected_output: bool
    missing_output: bool


def evaluate_transcript_integrity(
    evaluation: ASRNormalizedTextEvaluation,
) -> ASRTranscriptIntegrityEvaluation:
    """
    Evaluate deterministic transcript-integrity conditions.

    The metric identities are explicitly bound to the Hetren basic
    normalization profile, so evidence produced using another
    normalization profile must use different metric/evaluator versions.
    """

    if (
        evaluation.normalization_key
        != BASIC_TEXT_NORMALIZATION.key
        or evaluation.normalization_version
        != BASIC_TEXT_NORMALIZATION.version
    ):
        raise HveeContractError(
            "ASR transcript-integrity evaluation requires "
            "the Hetren basic normalization profile v1.0.0"
        )

    reference_empty = (
        evaluation.normalized_reference == ""
    )
    generated_empty = (
        evaluation.normalized_generated == ""
    )

    return ASRTranscriptIntegrityEvaluation(
        normalization_key=(
            evaluation.normalization_key
        ),
        normalization_version=(
            evaluation.normalization_version
        ),
        exact_match=(
            evaluation.normalized_reference
            == evaluation.normalized_generated
        ),
        reference_empty=reference_empty,
        generated_empty=generated_empty,
        unexpected_output=(
            reference_empty
            and not generated_empty
        ),
        missing_output=(
            not reference_empty
            and generated_empty
        ),
    )


def _build_boolean_observation(
    *,
    metric: MetricDefinition,
    value: bool,
) -> Observation:
    return Observation(
        metric_key=metric.key,
        metric_version=metric.version,
        evaluator_key=(
            TRANSCRIPT_INTEGRITY_EVALUATOR.key
        ),
        evaluator_version=(
            TRANSCRIPT_INTEGRITY_EVALUATOR.version
        ),
        evaluation_type=ASR_EVALUATION_TYPE,
        status=ObservationStatus.SUCCESS,
        value_type=MetricValueType.BOOLEAN,
        value=value,
    )


def build_transcript_integrity_observations(
    evaluation: ASRTranscriptIntegrityEvaluation,
) -> tuple[
    Observation,
    Observation,
    Observation,
    Observation,
    Observation,
]:
    return (
        _build_boolean_observation(
            metric=EXACT_NORMALIZED_MATCH_METRIC,
            value=evaluation.exact_match,
        ),
        _build_boolean_observation(
            metric=REFERENCE_EMPTY_METRIC,
            value=evaluation.reference_empty,
        ),
        _build_boolean_observation(
            metric=GENERATED_EMPTY_METRIC,
            value=evaluation.generated_empty,
        ),
        _build_boolean_observation(
            metric=UNEXPECTED_OUTPUT_METRIC,
            value=evaluation.unexpected_output,
        ),
        _build_boolean_observation(
            metric=MISSING_OUTPUT_METRIC,
            value=evaluation.missing_output,
        ),
    )

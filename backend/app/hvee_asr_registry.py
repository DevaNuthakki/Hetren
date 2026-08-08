from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.hvee_models import (
    HveeEvaluatorVersion,
    HveeMetricDefinition,
)
from app.hvee_registry_service import (
    resolve_evaluator_version,
    resolve_metric_definition,
)
from hvee.packs.asr import (
    CER_EVALUATOR,
    CER_METRIC,
    WER_EVALUATOR,
    WER_METRIC,
)


@dataclass(frozen=True, slots=True)
class ASRTextErrorRegistry:
    wer_metric: HveeMetricDefinition
    wer_evaluator: HveeEvaluatorVersion
    cer_metric: HveeMetricDefinition
    cer_evaluator: HveeEvaluatorVersion


def resolve_asr_text_error_registry(
    db: Session,
) -> ASRTextErrorRegistry:
    """
    Resolve the canonical HVEE ASR WER/CER registry records.

    The caller owns the surrounding transaction.
    """

    wer_metric = resolve_metric_definition(
        db,
        WER_METRIC,
    )
    wer_evaluator = resolve_evaluator_version(
        db,
        WER_EVALUATOR,
    )
    cer_metric = resolve_metric_definition(
        db,
        CER_METRIC,
    )
    cer_evaluator = resolve_evaluator_version(
        db,
        CER_EVALUATOR,
    )

    return ASRTextErrorRegistry(
        wer_metric=wer_metric,
        wer_evaluator=wer_evaluator,
        cer_metric=cer_metric,
        cer_evaluator=cer_evaluator,
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
)


@dataclass(frozen=True, slots=True)
class ASRNormalizedTextErrorRegistry:
    wer_metric: HveeMetricDefinition
    wer_evaluator: HveeEvaluatorVersion
    cer_metric: HveeMetricDefinition
    cer_evaluator: HveeEvaluatorVersion
    substitutions_metric: HveeMetricDefinition
    insertions_metric: HveeMetricDefinition
    deletions_metric: HveeMetricDefinition
    word_alignment_evaluator: HveeEvaluatorVersion


def resolve_asr_normalized_text_error_registry(
    db: Session,
) -> ASRNormalizedTextErrorRegistry:
    """
    Resolve the canonical normalized-basic ASR registry records.

    Registry resolution participates in the caller's transaction and
    never commits independently.
    """

    wer_metric = resolve_metric_definition(
        db,
        NORMALIZED_WER_METRIC,
    )
    wer_evaluator = resolve_evaluator_version(
        db,
        NORMALIZED_WER_EVALUATOR,
    )

    cer_metric = resolve_metric_definition(
        db,
        NORMALIZED_CER_METRIC,
    )
    cer_evaluator = resolve_evaluator_version(
        db,
        NORMALIZED_CER_EVALUATOR,
    )

    substitutions_metric = resolve_metric_definition(
        db,
        NORMALIZED_SUBSTITUTIONS_METRIC,
    )
    insertions_metric = resolve_metric_definition(
        db,
        NORMALIZED_INSERTIONS_METRIC,
    )
    deletions_metric = resolve_metric_definition(
        db,
        NORMALIZED_DELETIONS_METRIC,
    )

    word_alignment_evaluator = resolve_evaluator_version(
        db,
        NORMALIZED_WORD_ALIGNMENT_EVALUATOR,
    )

    return ASRNormalizedTextErrorRegistry(
        wer_metric=wer_metric,
        wer_evaluator=wer_evaluator,
        cer_metric=cer_metric,
        cer_evaluator=cer_evaluator,
        substitutions_metric=substitutions_metric,
        insertions_metric=insertions_metric,
        deletions_metric=deletions_metric,
        word_alignment_evaluator=(
            word_alignment_evaluator
        ),
    )


from hvee.packs.asr import (
    EXACT_NORMALIZED_MATCH_METRIC,
    GENERATED_EMPTY_METRIC,
    MISSING_OUTPUT_METRIC,
    REFERENCE_EMPTY_METRIC,
    TRANSCRIPT_INTEGRITY_EVALUATOR,
    UNEXPECTED_OUTPUT_METRIC,
)


@dataclass(frozen=True, slots=True)
class ASRTranscriptIntegrityRegistry:
    exact_match_metric: HveeMetricDefinition
    reference_empty_metric: HveeMetricDefinition
    generated_empty_metric: HveeMetricDefinition
    unexpected_output_metric: HveeMetricDefinition
    missing_output_metric: HveeMetricDefinition
    evaluator: HveeEvaluatorVersion


def resolve_asr_transcript_integrity_registry(
    db: Session,
) -> ASRTranscriptIntegrityRegistry:
    """
    Resolve the canonical normalized-basic transcript-integrity
    metric and evaluator identities.

    Registry resolution participates in the caller-owned transaction
    and never commits independently.
    """

    exact_match_metric = resolve_metric_definition(
        db,
        EXACT_NORMALIZED_MATCH_METRIC,
    )
    reference_empty_metric = resolve_metric_definition(
        db,
        REFERENCE_EMPTY_METRIC,
    )
    generated_empty_metric = resolve_metric_definition(
        db,
        GENERATED_EMPTY_METRIC,
    )
    unexpected_output_metric = resolve_metric_definition(
        db,
        UNEXPECTED_OUTPUT_METRIC,
    )
    missing_output_metric = resolve_metric_definition(
        db,
        MISSING_OUTPUT_METRIC,
    )

    evaluator = resolve_evaluator_version(
        db,
        TRANSCRIPT_INTEGRITY_EVALUATOR,
    )

    return ASRTranscriptIntegrityRegistry(
        exact_match_metric=exact_match_metric,
        reference_empty_metric=reference_empty_metric,
        generated_empty_metric=generated_empty_metric,
        unexpected_output_metric=unexpected_output_metric,
        missing_output_metric=missing_output_metric,
        evaluator=evaluator,
    )

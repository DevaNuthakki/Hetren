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


from hvee.packs.asr import (
    GENERATED_NUMERIC_TOKEN_COUNT_METRIC,
    MISSING_NUMERIC_TOKEN_COUNT_METRIC,
    NUMERIC_TOKEN_PRESERVATION_EVALUATOR,
    NUMERIC_TOKEN_SEQUENCE_MATCH_METRIC,
    REFERENCE_NUMERIC_TOKEN_COUNT_METRIC,
    UNEXPECTED_NUMERIC_TOKEN_COUNT_METRIC,
)


@dataclass(frozen=True, slots=True)
class ASRNumericPreservationRegistry:
    reference_count_metric: HveeMetricDefinition
    generated_count_metric: HveeMetricDefinition
    sequence_match_metric: HveeMetricDefinition
    missing_count_metric: HveeMetricDefinition
    unexpected_count_metric: HveeMetricDefinition
    evaluator: HveeEvaluatorVersion


def resolve_asr_numeric_preservation_registry(
    db: Session,
) -> ASRNumericPreservationRegistry:
    """
    Resolve the canonical digit-form numeric-preservation registry.

    Registry resolution participates in the caller-owned transaction
    and never commits independently.
    """

    reference_count_metric = resolve_metric_definition(
        db,
        REFERENCE_NUMERIC_TOKEN_COUNT_METRIC,
    )

    generated_count_metric = resolve_metric_definition(
        db,
        GENERATED_NUMERIC_TOKEN_COUNT_METRIC,
    )

    sequence_match_metric = resolve_metric_definition(
        db,
        NUMERIC_TOKEN_SEQUENCE_MATCH_METRIC,
    )

    missing_count_metric = resolve_metric_definition(
        db,
        MISSING_NUMERIC_TOKEN_COUNT_METRIC,
    )

    unexpected_count_metric = resolve_metric_definition(
        db,
        UNEXPECTED_NUMERIC_TOKEN_COUNT_METRIC,
    )

    evaluator = resolve_evaluator_version(
        db,
        NUMERIC_TOKEN_PRESERVATION_EVALUATOR,
    )

    return ASRNumericPreservationRegistry(
        reference_count_metric=reference_count_metric,
        generated_count_metric=generated_count_metric,
        sequence_match_metric=sequence_match_metric,
        missing_count_metric=missing_count_metric,
        unexpected_count_metric=unexpected_count_metric,
        evaluator=evaluator,
    )


from hvee.packs.asr import (
    CRITICAL_NUMBER_AMBIGUITY_COUNT_METRIC,
    CRITICAL_NUMBER_APPLICABLE_METRIC,
    CRITICAL_NUMBER_FIDELITY_EVALUATOR,
    CRITICAL_NUMBER_FINDINGS_METRIC,
    CRITICAL_NUMBER_GENERATED_COUNT_METRIC,
    CRITICAL_NUMBER_INSERTION_COUNT_METRIC,
    CRITICAL_NUMBER_OMISSION_COUNT_METRIC,
    CRITICAL_NUMBER_OUTCOME_METRIC,
    CRITICAL_NUMBER_PRESERVED_METRIC,
    CRITICAL_NUMBER_REFERENCE_COUNT_METRIC,
    CRITICAL_NUMBER_SUBSTITUTION_COUNT_METRIC,
)


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberFidelityRegistry:
    applicable_metric: HveeMetricDefinition
    preserved_metric: HveeMetricDefinition
    outcome_metric: HveeMetricDefinition
    reference_count_metric: HveeMetricDefinition
    generated_count_metric: HveeMetricDefinition
    substitution_count_metric: HveeMetricDefinition
    omission_count_metric: HveeMetricDefinition
    insertion_count_metric: HveeMetricDefinition
    ambiguity_count_metric: HveeMetricDefinition
    findings_metric: HveeMetricDefinition
    evaluator: HveeEvaluatorVersion


def resolve_asr_critical_number_fidelity_registry(
    db: Session,
) -> ASRCriticalNumberFidelityRegistry:
    """
    Resolve the canonical en-US Critical Number Fidelity registry.

    Registry resolution participates in the caller-owned transaction
    and never commits independently.
    """

    applicable_metric = resolve_metric_definition(
        db,
        CRITICAL_NUMBER_APPLICABLE_METRIC,
    )
    preserved_metric = resolve_metric_definition(
        db,
        CRITICAL_NUMBER_PRESERVED_METRIC,
    )
    outcome_metric = resolve_metric_definition(
        db,
        CRITICAL_NUMBER_OUTCOME_METRIC,
    )
    reference_count_metric = resolve_metric_definition(
        db,
        CRITICAL_NUMBER_REFERENCE_COUNT_METRIC,
    )
    generated_count_metric = resolve_metric_definition(
        db,
        CRITICAL_NUMBER_GENERATED_COUNT_METRIC,
    )
    substitution_count_metric = resolve_metric_definition(
        db,
        CRITICAL_NUMBER_SUBSTITUTION_COUNT_METRIC,
    )
    omission_count_metric = resolve_metric_definition(
        db,
        CRITICAL_NUMBER_OMISSION_COUNT_METRIC,
    )
    insertion_count_metric = resolve_metric_definition(
        db,
        CRITICAL_NUMBER_INSERTION_COUNT_METRIC,
    )
    ambiguity_count_metric = resolve_metric_definition(
        db,
        CRITICAL_NUMBER_AMBIGUITY_COUNT_METRIC,
    )
    findings_metric = resolve_metric_definition(
        db,
        CRITICAL_NUMBER_FINDINGS_METRIC,
    )
    evaluator = resolve_evaluator_version(
        db,
        CRITICAL_NUMBER_FIDELITY_EVALUATOR,
    )

    return ASRCriticalNumberFidelityRegistry(
        applicable_metric=applicable_metric,
        preserved_metric=preserved_metric,
        outcome_metric=outcome_metric,
        reference_count_metric=reference_count_metric,
        generated_count_metric=generated_count_metric,
        substitution_count_metric=substitution_count_metric,
        omission_count_metric=omission_count_metric,
        insertion_count_metric=insertion_count_metric,
        ambiguity_count_metric=ambiguity_count_metric,
        findings_metric=findings_metric,
        evaluator=evaluator,
    )

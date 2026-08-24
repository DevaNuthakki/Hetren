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


from hvee.packs.asr import (
    CRITICAL_IDENTIFIER_AMBIGUITY_COUNT_METRIC,
    CRITICAL_IDENTIFIER_APPLICABLE_METRIC,
    CRITICAL_IDENTIFIER_FIDELITY_EVALUATOR,
    CRITICAL_IDENTIFIER_FINDINGS_METRIC,
    CRITICAL_IDENTIFIER_GENERATED_COUNT_METRIC,
    CRITICAL_IDENTIFIER_INSERTION_COUNT_METRIC,
    CRITICAL_IDENTIFIER_OMISSION_COUNT_METRIC,
    CRITICAL_IDENTIFIER_ORDERING_CHANGE_COUNT_METRIC,
    CRITICAL_IDENTIFIER_OUTCOME_METRIC,
    CRITICAL_IDENTIFIER_PRESERVED_METRIC,
    CRITICAL_IDENTIFIER_REFERENCE_COUNT_METRIC,
    CRITICAL_IDENTIFIER_SUBSTITUTION_COUNT_METRIC,
)


@dataclass(frozen=True, slots=True)
class ASRCriticalIdentifierFidelityRegistry:
    applicable_metric: HveeMetricDefinition
    preserved_metric: HveeMetricDefinition
    outcome_metric: HveeMetricDefinition
    reference_count_metric: HveeMetricDefinition
    generated_count_metric: HveeMetricDefinition
    substitution_count_metric: HveeMetricDefinition
    omission_count_metric: HveeMetricDefinition
    insertion_count_metric: HveeMetricDefinition
    ordering_change_count_metric: HveeMetricDefinition
    ambiguity_count_metric: HveeMetricDefinition
    findings_metric: HveeMetricDefinition
    evaluator: HveeEvaluatorVersion


def resolve_asr_critical_identifier_fidelity_registry(
    db: Session,
) -> ASRCriticalIdentifierFidelityRegistry:
    """
    Resolve canonical en-US Critical Identifier Fidelity registry records.

    Registry resolution participates in the caller-owned transaction and
    never commits independently.
    """

    applicable_metric = resolve_metric_definition(
        db,
        CRITICAL_IDENTIFIER_APPLICABLE_METRIC,
    )
    preserved_metric = resolve_metric_definition(
        db,
        CRITICAL_IDENTIFIER_PRESERVED_METRIC,
    )
    outcome_metric = resolve_metric_definition(
        db,
        CRITICAL_IDENTIFIER_OUTCOME_METRIC,
    )
    reference_count_metric = resolve_metric_definition(
        db,
        CRITICAL_IDENTIFIER_REFERENCE_COUNT_METRIC,
    )
    generated_count_metric = resolve_metric_definition(
        db,
        CRITICAL_IDENTIFIER_GENERATED_COUNT_METRIC,
    )
    substitution_count_metric = resolve_metric_definition(
        db,
        CRITICAL_IDENTIFIER_SUBSTITUTION_COUNT_METRIC,
    )
    omission_count_metric = resolve_metric_definition(
        db,
        CRITICAL_IDENTIFIER_OMISSION_COUNT_METRIC,
    )
    insertion_count_metric = resolve_metric_definition(
        db,
        CRITICAL_IDENTIFIER_INSERTION_COUNT_METRIC,
    )
    ordering_change_count_metric = resolve_metric_definition(
        db,
        CRITICAL_IDENTIFIER_ORDERING_CHANGE_COUNT_METRIC,
    )
    ambiguity_count_metric = resolve_metric_definition(
        db,
        CRITICAL_IDENTIFIER_AMBIGUITY_COUNT_METRIC,
    )
    findings_metric = resolve_metric_definition(
        db,
        CRITICAL_IDENTIFIER_FINDINGS_METRIC,
    )
    evaluator = resolve_evaluator_version(
        db,
        CRITICAL_IDENTIFIER_FIDELITY_EVALUATOR,
    )

    return ASRCriticalIdentifierFidelityRegistry(
        applicable_metric=applicable_metric,
        preserved_metric=preserved_metric,
        outcome_metric=outcome_metric,
        reference_count_metric=reference_count_metric,
        generated_count_metric=generated_count_metric,
        substitution_count_metric=substitution_count_metric,
        omission_count_metric=omission_count_metric,
        insertion_count_metric=insertion_count_metric,
        ordering_change_count_metric=ordering_change_count_metric,
        ambiguity_count_metric=ambiguity_count_metric,
        findings_metric=findings_metric,
        evaluator=evaluator,
    )

from hvee.packs.asr import (
    CRITICAL_TERMINOLOGY_APPLICABLE_METRIC,
    CRITICAL_TERMINOLOGY_FIDELITY_EVALUATOR,
    CRITICAL_TERMINOLOGY_FINDINGS_METRIC,
    CRITICAL_TERMINOLOGY_GENERATED_COUNT_METRIC,
    CRITICAL_TERMINOLOGY_INSERTION_COUNT_METRIC,
    CRITICAL_TERMINOLOGY_OMISSION_COUNT_METRIC,
    CRITICAL_TERMINOLOGY_ORDERING_CHANGE_COUNT_METRIC,
    CRITICAL_TERMINOLOGY_OUTCOME_METRIC,
    CRITICAL_TERMINOLOGY_PRESERVED_METRIC,
    CRITICAL_TERMINOLOGY_REFERENCE_COUNT_METRIC,
    CRITICAL_TERMINOLOGY_SUBSTITUTION_COUNT_METRIC,
    CRITICAL_TERMINOLOGY_VOCABULARY_SHA256_METRIC,
)


@dataclass(frozen=True, slots=True)
class ASRCriticalTerminologyFidelityRegistry:
    applicable_metric: HveeMetricDefinition
    preserved_metric: HveeMetricDefinition
    outcome_metric: HveeMetricDefinition
    vocabulary_sha256_metric: HveeMetricDefinition
    reference_count_metric: HveeMetricDefinition
    generated_count_metric: HveeMetricDefinition
    substitution_count_metric: HveeMetricDefinition
    omission_count_metric: HveeMetricDefinition
    insertion_count_metric: HveeMetricDefinition
    ordering_change_count_metric: HveeMetricDefinition
    findings_metric: HveeMetricDefinition
    evaluator: HveeEvaluatorVersion


def resolve_asr_critical_terminology_fidelity_registry(
    db: Session,
) -> ASRCriticalTerminologyFidelityRegistry:
    """
    Resolve canonical en-US Critical Terminology Fidelity registry rows.

    Registry resolution participates in the caller-owned transaction
    and never independently commits.
    """

    applicable_metric = resolve_metric_definition(
        db,
        CRITICAL_TERMINOLOGY_APPLICABLE_METRIC,
    )
    preserved_metric = resolve_metric_definition(
        db,
        CRITICAL_TERMINOLOGY_PRESERVED_METRIC,
    )
    outcome_metric = resolve_metric_definition(
        db,
        CRITICAL_TERMINOLOGY_OUTCOME_METRIC,
    )
    vocabulary_sha256_metric = resolve_metric_definition(
        db,
        CRITICAL_TERMINOLOGY_VOCABULARY_SHA256_METRIC,
    )
    reference_count_metric = resolve_metric_definition(
        db,
        CRITICAL_TERMINOLOGY_REFERENCE_COUNT_METRIC,
    )
    generated_count_metric = resolve_metric_definition(
        db,
        CRITICAL_TERMINOLOGY_GENERATED_COUNT_METRIC,
    )
    substitution_count_metric = resolve_metric_definition(
        db,
        CRITICAL_TERMINOLOGY_SUBSTITUTION_COUNT_METRIC,
    )
    omission_count_metric = resolve_metric_definition(
        db,
        CRITICAL_TERMINOLOGY_OMISSION_COUNT_METRIC,
    )
    insertion_count_metric = resolve_metric_definition(
        db,
        CRITICAL_TERMINOLOGY_INSERTION_COUNT_METRIC,
    )
    ordering_change_count_metric = resolve_metric_definition(
        db,
        CRITICAL_TERMINOLOGY_ORDERING_CHANGE_COUNT_METRIC,
    )
    findings_metric = resolve_metric_definition(
        db,
        CRITICAL_TERMINOLOGY_FINDINGS_METRIC,
    )
    evaluator = resolve_evaluator_version(
        db,
        CRITICAL_TERMINOLOGY_FIDELITY_EVALUATOR,
    )

    return ASRCriticalTerminologyFidelityRegistry(
        applicable_metric=applicable_metric,
        preserved_metric=preserved_metric,
        outcome_metric=outcome_metric,
        vocabulary_sha256_metric=(
            vocabulary_sha256_metric
        ),
        reference_count_metric=reference_count_metric,
        generated_count_metric=generated_count_metric,
        substitution_count_metric=substitution_count_metric,
        omission_count_metric=omission_count_metric,
        insertion_count_metric=insertion_count_metric,
        ordering_change_count_metric=(
            ordering_change_count_metric
        ),
        findings_metric=findings_metric,
        evaluator=evaluator,
    )


from hvee.packs.asr import (
    ASR_RELIABILITY_PROFILE_V1,
    ASRReliabilityProfileDefinition,
    verify_asr_reliability_profile_v1,
)


@dataclass(frozen=True, slots=True)
class ASRReliabilityProfileRegistry:
    """Persisted metric/evaluator rows bound to one profile identity."""

    profile_key: str
    profile_version: str
    profile_sha256: str
    metric_definitions: tuple[HveeMetricDefinition, ...]
    evaluator_versions: tuple[HveeEvaluatorVersion, ...]

    def metric_by_identity(
        self,
        *,
        key: str,
        version: str,
    ) -> HveeMetricDefinition:
        for metric in self.metric_definitions:
            if metric.key == key and metric.version == version:
                return metric

        raise KeyError(
            "metric identity is not registered by the ASR "
            "Reliability Profile"
        )

    def evaluator_by_identity(
        self,
        *,
        key: str,
        version: str,
    ) -> HveeEvaluatorVersion:
        for evaluator in self.evaluator_versions:
            if evaluator.key == key and evaluator.version == version:
                return evaluator

        raise KeyError(
            "evaluator identity is not registered by the ASR "
            "Reliability Profile"
        )


def resolve_asr_reliability_profile_registry(
    db: Session,
    *,
    profile: ASRReliabilityProfileDefinition = (
        ASR_RELIABILITY_PROFILE_V1
    ),
) -> ASRReliabilityProfileRegistry:
    """Resolve every canonical registry identity required by B10G.

    The profile remains source-versioned while its metric and evaluator
    identities use the existing conflict-safe persistence registry.  The
    caller owns the surrounding transaction; this function never commits.
    """

    verified = verify_asr_reliability_profile_v1(profile)

    metric_definitions = tuple(
        resolve_metric_definition(
            db,
            binding.metric,
        )
        for binding in verified.bindings
    )

    evaluator_versions = []
    evaluator_identities: set[tuple[str, str]] = set()

    for binding in verified.bindings:
        identity = binding.evaluator_identity

        if identity in evaluator_identities:
            continue

        evaluator_identities.add(identity)
        evaluator_versions.append(
            resolve_evaluator_version(
                db,
                binding.evaluator,
            )
        )

    return ASRReliabilityProfileRegistry(
        profile_key=verified.key,
        profile_version=verified.version,
        profile_sha256=verified.sha256,
        metric_definitions=metric_definitions,
        evaluator_versions=tuple(evaluator_versions),
    )

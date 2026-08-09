from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.hvee_asr_registry import (
    resolve_asr_text_error_registry,
)
from app.hvee_models import HveeObservation
from app.hvee_observation_service import (
    stage_hvee_observation,
)
from hvee.packs.asr import (
    ASRTextEvaluation,
    build_text_error_observations,
)


def stage_asr_text_error_observations(
    db: Session,
    *,
    evaluation_run: models.EvaluationRun,
    test_case: models.TestCase,
    evaluation: ASRTextEvaluation,
) -> tuple[HveeObservation, HveeObservation]:
    """
    Stage canonical WER and CER observations for one ASR result.

    Registry resolution and observation persistence participate in the
    caller's transaction. This function never commits.
    """

    registry = resolve_asr_text_error_registry(
        db
    )

    (
        wer_observation,
        cer_observation,
    ) = build_text_error_observations(
        evaluation
    )

    db_wer_observation = stage_hvee_observation(
        db,
        evaluation_run=evaluation_run,
        test_case=test_case,
        metric_definition=registry.wer_metric,
        evaluator_version=registry.wer_evaluator,
        observation=wer_observation,
    )

    db_cer_observation = stage_hvee_observation(
        db,
        evaluation_run=evaluation_run,
        test_case=test_case,
        metric_definition=registry.cer_metric,
        evaluator_version=registry.cer_evaluator,
        observation=cer_observation,
    )

    return (
        db_wer_observation,
        db_cer_observation,
    )


from app.hvee_asr_registry import (
    resolve_asr_normalized_text_error_registry,
)
from hvee.packs.asr import (
    ASRNormalizedTextEvaluation,
    build_normalized_error_observations,
)


def stage_asr_normalized_text_error_observations(
    db: Session,
    *,
    evaluation_run: models.EvaluationRun,
    test_case: models.TestCase,
    evaluation: ASRNormalizedTextEvaluation,
) -> tuple[
    HveeObservation,
    HveeObservation,
    HveeObservation,
    HveeObservation,
    HveeObservation,
]:
    """
    Stage normalized-basic ASR error observations.

    WER, CER, substitution, insertion, and deletion observations are
    staged in the caller's transaction. This function never commits.
    """

    registry = resolve_asr_normalized_text_error_registry(
        db
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

    db_wer_observation = stage_hvee_observation(
        db,
        evaluation_run=evaluation_run,
        test_case=test_case,
        metric_definition=registry.wer_metric,
        evaluator_version=registry.wer_evaluator,
        observation=wer_observation,
    )

    db_cer_observation = stage_hvee_observation(
        db,
        evaluation_run=evaluation_run,
        test_case=test_case,
        metric_definition=registry.cer_metric,
        evaluator_version=registry.cer_evaluator,
        observation=cer_observation,
    )

    db_substitutions_observation = stage_hvee_observation(
        db,
        evaluation_run=evaluation_run,
        test_case=test_case,
        metric_definition=(
            registry.substitutions_metric
        ),
        evaluator_version=(
            registry.word_alignment_evaluator
        ),
        observation=substitutions_observation,
    )

    db_insertions_observation = stage_hvee_observation(
        db,
        evaluation_run=evaluation_run,
        test_case=test_case,
        metric_definition=registry.insertions_metric,
        evaluator_version=(
            registry.word_alignment_evaluator
        ),
        observation=insertions_observation,
    )

    db_deletions_observation = stage_hvee_observation(
        db,
        evaluation_run=evaluation_run,
        test_case=test_case,
        metric_definition=registry.deletions_metric,
        evaluator_version=(
            registry.word_alignment_evaluator
        ),
        observation=deletions_observation,
    )

    return (
        db_wer_observation,
        db_cer_observation,
        db_substitutions_observation,
        db_insertions_observation,
        db_deletions_observation,
    )


from app.hvee_asr_registry import (
    resolve_asr_transcript_integrity_registry,
)
from hvee.packs.asr import (
    ASRTranscriptIntegrityEvaluation,
    build_transcript_integrity_observations,
)


def stage_asr_transcript_integrity_observations(
    db: Session,
    *,
    evaluation_run: models.EvaluationRun,
    test_case: models.TestCase,
    evaluation: ASRTranscriptIntegrityEvaluation,
) -> tuple[
    HveeObservation,
    HveeObservation,
    HveeObservation,
    HveeObservation,
    HveeObservation,
]:
    """
    Stage deterministic transcript-integrity observations.

    All five metrics are produced by one versioned evaluator and are
    staged in the caller-owned transaction. This function never
    commits.
    """

    registry = (
        resolve_asr_transcript_integrity_registry(
            db
        )
    )

    (
        exact_match_observation,
        reference_empty_observation,
        generated_empty_observation,
        unexpected_output_observation,
        missing_output_observation,
    ) = build_transcript_integrity_observations(
        evaluation
    )

    db_exact_match = stage_hvee_observation(
        db,
        evaluation_run=evaluation_run,
        test_case=test_case,
        metric_definition=(
            registry.exact_match_metric
        ),
        evaluator_version=registry.evaluator,
        observation=exact_match_observation,
    )

    db_reference_empty = stage_hvee_observation(
        db,
        evaluation_run=evaluation_run,
        test_case=test_case,
        metric_definition=(
            registry.reference_empty_metric
        ),
        evaluator_version=registry.evaluator,
        observation=reference_empty_observation,
    )

    db_generated_empty = stage_hvee_observation(
        db,
        evaluation_run=evaluation_run,
        test_case=test_case,
        metric_definition=(
            registry.generated_empty_metric
        ),
        evaluator_version=registry.evaluator,
        observation=generated_empty_observation,
    )

    db_unexpected_output = stage_hvee_observation(
        db,
        evaluation_run=evaluation_run,
        test_case=test_case,
        metric_definition=(
            registry.unexpected_output_metric
        ),
        evaluator_version=registry.evaluator,
        observation=unexpected_output_observation,
    )

    db_missing_output = stage_hvee_observation(
        db,
        evaluation_run=evaluation_run,
        test_case=test_case,
        metric_definition=(
            registry.missing_output_metric
        ),
        evaluator_version=registry.evaluator,
        observation=missing_output_observation,
    )

    return (
        db_exact_match,
        db_reference_empty,
        db_generated_empty,
        db_unexpected_output,
        db_missing_output,
    )


from app.hvee_asr_registry import (
    resolve_asr_numeric_preservation_registry,
)
from hvee.packs.asr import (
    ASRNumericPreservationEvaluation,
    build_numeric_preservation_observations,
)


def stage_asr_numeric_preservation_observations(
    db: Session,
    *,
    evaluation_run: models.EvaluationRun,
    test_case: models.TestCase,
    evaluation: ASRNumericPreservationEvaluation,
) -> tuple[
    HveeObservation,
    HveeObservation,
    HveeObservation,
    HveeObservation,
    HveeObservation,
]:
    """
    Stage deterministic digit-form numeric-preservation observations.

    The five metrics share one versioned evaluator and participate in
    the caller-owned transaction. This function never commits.
    """

    registry = (
        resolve_asr_numeric_preservation_registry(
            db
        )
    )

    (
        reference_count_observation,
        generated_count_observation,
        sequence_match_observation,
        missing_count_observation,
        unexpected_count_observation,
    ) = build_numeric_preservation_observations(
        evaluation
    )

    db_reference_count = stage_hvee_observation(
        db,
        evaluation_run=evaluation_run,
        test_case=test_case,
        metric_definition=(
            registry.reference_count_metric
        ),
        evaluator_version=registry.evaluator,
        observation=reference_count_observation,
    )

    db_generated_count = stage_hvee_observation(
        db,
        evaluation_run=evaluation_run,
        test_case=test_case,
        metric_definition=(
            registry.generated_count_metric
        ),
        evaluator_version=registry.evaluator,
        observation=generated_count_observation,
    )

    db_sequence_match = stage_hvee_observation(
        db,
        evaluation_run=evaluation_run,
        test_case=test_case,
        metric_definition=(
            registry.sequence_match_metric
        ),
        evaluator_version=registry.evaluator,
        observation=sequence_match_observation,
    )

    db_missing_count = stage_hvee_observation(
        db,
        evaluation_run=evaluation_run,
        test_case=test_case,
        metric_definition=(
            registry.missing_count_metric
        ),
        evaluator_version=registry.evaluator,
        observation=missing_count_observation,
    )

    db_unexpected_count = stage_hvee_observation(
        db,
        evaluation_run=evaluation_run,
        test_case=test_case,
        metric_definition=(
            registry.unexpected_count_metric
        ),
        evaluator_version=registry.evaluator,
        observation=unexpected_count_observation,
    )

    return (
        db_reference_count,
        db_generated_count,
        db_sequence_match,
        db_missing_count,
        db_unexpected_count,
    )


from app.hvee_asr_registry import (
    resolve_asr_critical_number_fidelity_registry,
)
from hvee.packs.asr import (
    ASRCriticalNumberFidelityEvaluation,
    build_critical_number_fidelity_observations,
)


def stage_asr_critical_number_fidelity_observations(
    db: Session,
    *,
    evaluation_run: models.EvaluationRun,
    test_case: models.TestCase,
    evaluation: ASRCriticalNumberFidelityEvaluation,
) -> tuple[HveeObservation, ...]:
    """
    Stage en-US Critical Number Fidelity observations.

    All ten observations share one versioned evaluator and retain the
    evaluator's explicit success, abstained, or unsupported status.
    They participate in the caller-owned transaction; this function
    never commits and does not enable shadow or release execution.
    """

    registry = (
        resolve_asr_critical_number_fidelity_registry(
            db
        )
    )
    observations = (
        build_critical_number_fidelity_observations(
            evaluation
        )
    )
    metric_definitions = (
        registry.applicable_metric,
        registry.preserved_metric,
        registry.outcome_metric,
        registry.reference_count_metric,
        registry.generated_count_metric,
        registry.substitution_count_metric,
        registry.omission_count_metric,
        registry.insertion_count_metric,
        registry.ambiguity_count_metric,
        registry.findings_metric,
    )

    return tuple(
        stage_hvee_observation(
            db,
            evaluation_run=evaluation_run,
            test_case=test_case,
            metric_definition=metric_definition,
            evaluator_version=registry.evaluator,
            observation=observation,
        )
        for metric_definition, observation in zip(
            metric_definitions,
            observations,
            strict=True,
        )
    )

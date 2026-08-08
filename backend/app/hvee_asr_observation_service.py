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

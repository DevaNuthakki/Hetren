from sqlalchemy.orm import Session

from app import models
from app.evaluation_provenance import (
    stage_evaluation_result_provenance,
)
from app.hvee_asr_observation_service import (
    stage_asr_normalized_text_error_observations,
    stage_asr_text_error_observations,
)
from hvee.packs.asr import (
    ASRTextEvaluation,
    evaluate_normalized_transcript_pair,
    evaluate_transcript_pair,
)


def build_quality_label(wer_score: float) -> str:
    if wer_score <= 0.05:
        return "excellent"
    if wer_score <= 0.15:
        return "good"
    if wer_score <= 0.30:
        return "needs_review"
    return "regression"


def _format_error_summary(
    evaluation: ASRTextEvaluation,
) -> str:
    return (
        f"WER={evaluation.wer:.3f}, "
        f"CER={evaluation.cer:.3f}. "
        f"Substitutions={evaluation.substitutions}, "
        f"insertions={evaluation.insertions}, "
        f"deletions={evaluation.deletions}."
    )


def build_error_summary(
    reference_text: str,
    generated_text: str,
) -> tuple[float, float, str]:
    evaluation = evaluate_transcript_pair(
        reference_text=reference_text,
        generated_text=generated_text,
    )

    return (
        evaluation.wer,
        evaluation.cer,
        _format_error_summary(evaluation),
    )


def stage_evaluation_result(
    db: Session,
    db_run: models.EvaluationRun,
    db_test_case: models.TestCase,
    generated_text: str,
    generated_file_path: str | None = None,
) -> models.EvaluationResult:
    """
    Stage one ASR result and its HVEE observations without committing.

    Callers own the surrounding transaction so legacy result state,
    HVEE observations, provenance, and coordinated runner state can
    either persist together or roll back together.
    """

    reference_text = db_test_case.reference_transcript

    evaluation = evaluate_transcript_pair(
        reference_text=reference_text,
        generated_text=generated_text,
    )

    normalized_evaluation = (
        evaluate_normalized_transcript_pair(
            reference_text=reference_text,
            generated_text=generated_text,
        )
    )

    error_summary = _format_error_summary(
        evaluation
    )

    quality_label = build_quality_label(
        evaluation.wer
    )

    db_result = models.EvaluationResult(
        run_id=db_run.id,
        test_case_id=db_test_case.id,
        generated_transcript=generated_text,
        generated_file_path=generated_file_path,
        wer=evaluation.wer,
        cer=evaluation.cer,
        quality_label=quality_label,
        error_summary=error_summary,
    )

    db.add(db_result)

    db_run.reference_transcript = reference_text
    db_run.generated_transcript = generated_text
    db_run.wer = evaluation.wer
    db_run.cer = evaluation.cer
    db_run.quality_label = quality_label
    db_run.error_summary = error_summary
    db_run.status = "evaluated"

    stage_asr_text_error_observations(
        db,
        evaluation_run=db_run,
        test_case=db_test_case,
        evaluation=evaluation,
    )

    stage_asr_normalized_text_error_observations(
        db,
        evaluation_run=db_run,
        test_case=db_test_case,
        evaluation=normalized_evaluation,
    )

    return db_result


def persist_evaluation_result(
    db: Session,
    db_run: models.EvaluationRun,
    db_test_case: models.TestCase,
    generated_text: str,
    generated_file_path: str | None = None,
    *,
    execution_mode: str,
    server_observed: dict[str, object] | None = None,
    external_reported: dict[str, object] | None = None,
    input_artifact_seal: (
        models.EvaluationInputArtifactSeal | None
    ) = None,
) -> models.EvaluationResult:
    """
    Persist a synchronous evaluation result, HVEE observations, and
    provenance atomically.
    """

    try:
        db_result = stage_evaluation_result(
            db=db,
            db_run=db_run,
            db_test_case=db_test_case,
            generated_text=generated_text,
            generated_file_path=generated_file_path,
        )

        # The result primary key is part of its integrity-verifiable
        # provenance. The same flush also validates staged HVEE rows.
        db.flush()

        stage_evaluation_result_provenance(
            db,
            result=db_result,
            evaluation_run=db_run,
            test_case=db_test_case,
            execution_mode=execution_mode,
            server_observed=server_observed,
            external_reported=external_reported,
            input_artifact_seal=input_artifact_seal,
        )

        db.flush()
        db.commit()

    except Exception:
        db.rollback()
        raise

    db.refresh(db_result)

    return db_result

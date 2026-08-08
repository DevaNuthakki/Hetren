from jiwer import cer as calculate_cer
from jiwer import process_words
from sqlalchemy.orm import Session

from app import models
from app.evaluation_provenance import (
    stage_evaluation_result_provenance,
)


def build_quality_label(wer_score: float) -> str:
    if wer_score <= 0.05:
        return "excellent"
    if wer_score <= 0.15:
        return "good"
    if wer_score <= 0.30:
        return "needs_review"
    return "regression"


def build_error_summary(
    reference_text: str,
    generated_text: str,
) -> tuple[float, float, str]:
    word_result = process_words(
        reference_text,
        generated_text,
    )
    wer_score = float(word_result.wer)
    cer_score = float(
        calculate_cer(
            reference_text,
            generated_text,
        )
    )

    summary = (
        f"WER={wer_score:.3f}, CER={cer_score:.3f}. "
        f"Substitutions={word_result.substitutions}, "
        f"insertions={word_result.insertions}, "
        f"deletions={word_result.deletions}."
    )

    return wer_score, cer_score, summary


def stage_evaluation_result(
    db: Session,
    db_run: models.EvaluationRun,
    db_test_case: models.TestCase,
    generated_text: str,
    generated_file_path: str | None = None,
) -> models.EvaluationResult:
    """
    Stage an evaluation result without committing the transaction.

    Callers that coordinate additional state changes can commit all
    related updates atomically.
    """
    reference_text = db_test_case.reference_transcript

    wer_score, cer_score, error_summary = (
        build_error_summary(
            reference_text=reference_text,
            generated_text=generated_text,
        )
    )
    quality_label = build_quality_label(wer_score)

    db_result = models.EvaluationResult(
        run_id=db_run.id,
        test_case_id=db_test_case.id,
        generated_transcript=generated_text,
        generated_file_path=generated_file_path,
        wer=wer_score,
        cer=cer_score,
        quality_label=quality_label,
        error_summary=error_summary,
    )

    db.add(db_result)

    db_run.reference_transcript = reference_text
    db_run.generated_transcript = generated_text
    db_run.wer = wer_score
    db_run.cer = cer_score
    db_run.quality_label = quality_label
    db_run.error_summary = error_summary
    db_run.status = "evaluated"

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
    Persist a synchronous evaluation result and its provenance atomically.

    The transaction is rolled back if either the result or provenance
    cannot be staged successfully.
    """
    try:
        db_result = stage_evaluation_result(
            db=db,
            db_run=db_run,
            db_test_case=db_test_case,
            generated_text=generated_text,
            generated_file_path=generated_file_path,
        )

        # The result primary key is part of its integrity-verifiable provenance.
        db.flush()

        stage_evaluation_result_provenance(
            db,
            result=db_result,
            evaluation_run=db_run,
            test_case=db_test_case,
            execution_mode=execution_mode,
            server_observed=server_observed,
            external_reported=external_reported,
            input_artifact_seal=(
                input_artifact_seal
            ),
        )

        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(db_result)

    return db_result

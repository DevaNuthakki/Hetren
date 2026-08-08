from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from app.evaluation_provenance import (
    stage_evaluation_run_with_manifest,
)
from app.evaluation_service import (
    persist_evaluation_result,
    stage_evaluation_result,
)
from app.hvee_models import (
    HveeEvaluatorVersion,
    HveeMetricDefinition,
    HveeObservation,
)
from hvee.packs.asr import (
    CER_EVALUATOR,
    CER_METRIC,
    EXACT_NORMALIZED_MATCH_METRIC,
    GENERATED_EMPTY_METRIC,
    MISSING_OUTPUT_METRIC,
    NORMALIZED_CER_EVALUATOR,
    NORMALIZED_CER_METRIC,
    NORMALIZED_DELETIONS_METRIC,
    NORMALIZED_INSERTIONS_METRIC,
    NORMALIZED_SUBSTITUTIONS_METRIC,
    NORMALIZED_WER_EVALUATOR,
    NORMALIZED_WER_METRIC,
    NORMALIZED_WORD_ALIGNMENT_EVALUATOR,
    REFERENCE_EMPTY_METRIC,
    TRANSCRIPT_INTEGRITY_EVALUATOR,
    UNEXPECTED_OUTPUT_METRIC,
    WER_EVALUATOR,
    WER_METRIC,
    evaluate_normalized_transcript_pair,
    evaluate_transcript_integrity,
)


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def configure_sqlite_connection(
        dbapi_connection,
        _connection_record,
    ) -> None:
        # Ensure nested SAVEPOINT work participates in the caller's
        # transaction instead of SQLite legacy transaction behavior.
        dbapi_connection.isolation_level = None

        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    @event.listens_for(engine, "begin")
    def emit_begin(connection) -> None:
        connection.exec_driver_sql("BEGIN")

    Base.metadata.create_all(engine)

    factory = sessionmaker(bind=engine)
    session = factory()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def build_resources(
    db: Session,
) -> tuple[
    models.EvaluationRun,
    models.TestCase,
]:
    project = models.Project(
        name="HVEE ASR dual-write project",
    )
    db.add(project)
    db.flush()

    dataset = models.Dataset(
        project_id=project.id,
        name="HVEE ASR dual-write dataset",
    )
    db.add(dataset)
    db.flush()

    test_case = models.TestCase(
        dataset_id=dataset.id,
        title="HVEE ASR dual-write case",
        reference_transcript="the quick brown fox",
    )
    db.add(test_case)
    db.flush()

    run = stage_evaluation_run_with_manifest(
        db,
        project_id=project.id,
        run_name="HVEE ASR dual-write run",
        model_name="requested-model",
    )

    return run, test_case


def observation_by_metric_key(
    db: Session,
) -> dict[str, HveeObservation]:
    observations = (
        db.query(HveeObservation)
        .all()
    )

    metric_by_id = {
        metric.id: metric.key
        for metric in (
            db.query(HveeMetricDefinition)
            .all()
        )
    }

    return {
        metric_by_id[
            observation.metric_definition_id
        ]: observation
        for observation in observations
    }


def test_synchronous_result_dual_writes_wer_and_cer(
    db: Session,
):
    run, test_case = build_resources(db)

    result = persist_evaluation_result(
        db=db,
        db_run=run,
        db_test_case=test_case,
        generated_text="the quick fox",
        execution_mode="uploaded_transcript",
    )

    observations = observation_by_metric_key(
        db
    )

    assert set(observations) == {
        WER_METRIC.key,
        CER_METRIC.key,
        NORMALIZED_WER_METRIC.key,
        NORMALIZED_CER_METRIC.key,
        NORMALIZED_SUBSTITUTIONS_METRIC.key,
        NORMALIZED_INSERTIONS_METRIC.key,
        NORMALIZED_DELETIONS_METRIC.key,
        EXACT_NORMALIZED_MATCH_METRIC.key,
        REFERENCE_EMPTY_METRIC.key,
        GENERATED_EMPTY_METRIC.key,
        UNEXPECTED_OUTPUT_METRIC.key,
        MISSING_OUTPUT_METRIC.key,
    }

    wer = observations[WER_METRIC.key]
    cer = observations[CER_METRIC.key]

    assert wer.evaluation_run_id == run.id
    assert wer.test_case_id == test_case.id
    assert wer.scope == "test_case"
    assert wer.status == "success"
    assert wer.value_type == "number"
    assert wer.number_value == result.wer

    assert cer.evaluation_run_id == run.id
    assert cer.test_case_id == test_case.id
    assert cer.scope == "test_case"
    assert cer.status == "success"
    assert cer.value_type == "number"
    assert cer.number_value == result.cer

    normalized_evaluation = (
        evaluate_normalized_transcript_pair(
            reference_text=test_case.reference_transcript,
            generated_text="the quick fox",
        )
    )

    normalized_wer = observations[
        NORMALIZED_WER_METRIC.key
    ]
    normalized_cer = observations[
        NORMALIZED_CER_METRIC.key
    ]
    substitutions = observations[
        NORMALIZED_SUBSTITUTIONS_METRIC.key
    ]
    insertions = observations[
        NORMALIZED_INSERTIONS_METRIC.key
    ]
    deletions = observations[
        NORMALIZED_DELETIONS_METRIC.key
    ]

    assert normalized_wer.value_type == "number"
    assert normalized_wer.number_value == pytest.approx(
        normalized_evaluation.wer
    )

    assert normalized_cer.value_type == "number"
    assert normalized_cer.number_value == pytest.approx(
        normalized_evaluation.cer
    )

    assert substitutions.value_type == "integer"
    assert substitutions.integer_value == (
        normalized_evaluation.substitutions
    )

    assert insertions.value_type == "integer"
    assert insertions.integer_value == (
        normalized_evaluation.insertions
    )

    assert deletions.value_type == "integer"
    assert deletions.integer_value == (
        normalized_evaluation.deletions
    )

    integrity_evaluation = (
        evaluate_transcript_integrity(
            normalized_evaluation
        )
    )

    exact_match = observations[
        EXACT_NORMALIZED_MATCH_METRIC.key
    ]
    reference_empty = observations[
        REFERENCE_EMPTY_METRIC.key
    ]
    generated_empty = observations[
        GENERATED_EMPTY_METRIC.key
    ]
    unexpected_output = observations[
        UNEXPECTED_OUTPUT_METRIC.key
    ]
    missing_output = observations[
        MISSING_OUTPUT_METRIC.key
    ]

    integrity_observations = (
        exact_match,
        reference_empty,
        generated_empty,
        unexpected_output,
        missing_output,
    )

    for observation in integrity_observations:
        assert observation.scope == "test_case"
        assert observation.status == "success"
        assert observation.value_type == "boolean"

    assert (
        exact_match.boolean_value
        is integrity_evaluation.exact_match
    )
    assert (
        reference_empty.boolean_value
        is integrity_evaluation.reference_empty
    )
    assert (
        generated_empty.boolean_value
        is integrity_evaluation.generated_empty
    )
    assert (
        unexpected_output.boolean_value
        is integrity_evaluation.unexpected_output
    )
    assert (
        missing_output.boolean_value
        is integrity_evaluation.missing_output
    )

    assert exact_match.boolean_value is False
    assert reference_empty.boolean_value is False
    assert generated_empty.boolean_value is False
    assert unexpected_output.boolean_value is False
    assert missing_output.boolean_value is False


def test_dual_write_resolves_canonical_registry_once(
    db: Session,
):
    run, first_case = build_resources(db)

    first = persist_evaluation_result(
        db=db,
        db_run=run,
        db_test_case=first_case,
        generated_text="the quick fox",
        execution_mode="uploaded_transcript",
    )

    second_case = models.TestCase(
        dataset_id=first_case.dataset_id,
        title="Second ASR case",
        reference_transcript="hello world",
    )
    db.add(second_case)
    db.commit()

    second = persist_evaluation_result(
        db=db,
        db_run=run,
        db_test_case=second_case,
        generated_text="hello there",
        execution_mode="uploaded_transcript",
    )

    assert first.id != second.id

    assert (
        db.query(HveeMetricDefinition).count()
        == 12
    )
    assert (
        db.query(HveeEvaluatorVersion).count()
        == 6
    )
    assert (
        db.query(HveeObservation).count()
        == 24
    )

    metrics = {
        (row.key, row.version)
        for row in db.query(
            HveeMetricDefinition
        ).all()
    }
    evaluators = {
        (row.key, row.version)
        for row in db.query(
            HveeEvaluatorVersion
        ).all()
    }

    assert metrics == {
        (WER_METRIC.key, WER_METRIC.version),
        (CER_METRIC.key, CER_METRIC.version),
        (
            NORMALIZED_WER_METRIC.key,
            NORMALIZED_WER_METRIC.version,
        ),
        (
            NORMALIZED_CER_METRIC.key,
            NORMALIZED_CER_METRIC.version,
        ),
        (
            NORMALIZED_SUBSTITUTIONS_METRIC.key,
            NORMALIZED_SUBSTITUTIONS_METRIC.version,
        ),
        (
            NORMALIZED_INSERTIONS_METRIC.key,
            NORMALIZED_INSERTIONS_METRIC.version,
        ),
        (
            NORMALIZED_DELETIONS_METRIC.key,
            NORMALIZED_DELETIONS_METRIC.version,
        ),
        (
            EXACT_NORMALIZED_MATCH_METRIC.key,
            EXACT_NORMALIZED_MATCH_METRIC.version,
        ),
        (
            REFERENCE_EMPTY_METRIC.key,
            REFERENCE_EMPTY_METRIC.version,
        ),
        (
            GENERATED_EMPTY_METRIC.key,
            GENERATED_EMPTY_METRIC.version,
        ),
        (
            UNEXPECTED_OUTPUT_METRIC.key,
            UNEXPECTED_OUTPUT_METRIC.version,
        ),
        (
            MISSING_OUTPUT_METRIC.key,
            MISSING_OUTPUT_METRIC.version,
        ),
    }

    assert evaluators == {
        (
            WER_EVALUATOR.key,
            WER_EVALUATOR.version,
        ),
        (
            CER_EVALUATOR.key,
            CER_EVALUATOR.version,
        ),
        (
            NORMALIZED_WER_EVALUATOR.key,
            NORMALIZED_WER_EVALUATOR.version,
        ),
        (
            NORMALIZED_CER_EVALUATOR.key,
            NORMALIZED_CER_EVALUATOR.version,
        ),
        (
            NORMALIZED_WORD_ALIGNMENT_EVALUATOR.key,
            NORMALIZED_WORD_ALIGNMENT_EVALUATOR.version,
        ),
        (
            TRANSCRIPT_INTEGRITY_EVALUATOR.key,
            TRANSCRIPT_INTEGRITY_EVALUATOR.version,
        ),
    }


def test_provenance_failure_rolls_back_entire_dual_write(
    db: Session,
):
    run, test_case = build_resources(db)

    # Preserve only setup resources. Everything created by the failed
    # evaluation must disappear in the rollback.
    db.commit()

    with pytest.raises(
        ValueError,
        match="Unsupported evaluation execution mode",
    ):
        persist_evaluation_result(
            db=db,
            db_run=run,
            db_test_case=test_case,
            generated_text="the quick fox",
            execution_mode="invalid_mode",
        )

    assert (
        db.query(models.EvaluationResult).count()
        == 0
    )
    assert (
        db.query(
            models.EvaluationResultProvenance
        ).count()
        == 0
    )
    assert (
        db.query(HveeObservation).count()
        == 0
    )
    assert (
        db.query(HveeMetricDefinition).count()
        == 0
    )
    assert (
        db.query(HveeEvaluatorVersion).count()
        == 0
    )

    db.refresh(run)
    assert run.status == "created"


def test_stage_dual_write_does_not_commit(
    db: Session,
):
    run, test_case = build_resources(db)
    db.commit()

    stage_evaluation_result(
        db=db,
        db_run=run,
        db_test_case=test_case,
        generated_text="the quick fox",
    )

    assert (
        db.query(HveeObservation).count()
        == 12
    )

    db.rollback()

    assert (
        db.query(models.EvaluationResult).count()
        == 0
    )
    assert (
        db.query(HveeObservation).count()
        == 0
    )
    assert (
        db.query(HveeMetricDefinition).count()
        == 0
    )
    assert (
        db.query(HveeEvaluatorVersion).count()
        == 0
    )

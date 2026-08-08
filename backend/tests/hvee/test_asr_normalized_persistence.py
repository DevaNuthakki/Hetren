from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from app.hvee_asr_observation_service import (
    stage_asr_normalized_text_error_observations,
)
from app.hvee_asr_registry import (
    resolve_asr_normalized_text_error_registry,
)
from app.hvee_models import (
    HveeEvaluatorVersion,
    HveeMetricDefinition,
    HveeObservation,
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
    evaluate_normalized_transcript_pair,
)


@pytest.fixture
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
        # Let SQLAlchemy control BEGIN so SAVEPOINT operations
        # always participate in the surrounding transaction.
        dbapi_connection.isolation_level = None

        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    @event.listens_for(engine, "begin")
    def emit_begin(connection) -> None:
        connection.exec_driver_sql("BEGIN")

    Base.metadata.create_all(engine)

    session_factory = sessionmaker(
        bind=engine
    )
    session = session_factory()

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
        name="Normalized ASR persistence project"
    )
    dataset = models.Dataset(
        project=project,
        name="Normalized ASR persistence dataset",
    )
    test_case = models.TestCase(
        dataset=dataset,
        title="Normalized ASR case",
        reference_transcript="Hello, WORLD!",
    )
    run = models.EvaluationRun(
        project=project,
        run_name="Normalized ASR run",
        evaluation_type="asr",
        model_name="test-model",
    )

    db.add_all(
        [
            project,
            dataset,
            test_case,
            run,
        ]
    )
    db.flush()

    return run, test_case


def test_normalized_registry_resolves_canonical_identities(
    db: Session,
):
    registry = (
        resolve_asr_normalized_text_error_registry(
            db
        )
    )

    assert {
        (
            registry.wer_metric.key,
            registry.wer_metric.version,
        ),
        (
            registry.cer_metric.key,
            registry.cer_metric.version,
        ),
        (
            registry.substitutions_metric.key,
            registry.substitutions_metric.version,
        ),
        (
            registry.insertions_metric.key,
            registry.insertions_metric.version,
        ),
        (
            registry.deletions_metric.key,
            registry.deletions_metric.version,
        ),
    } == {
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
    }

    assert {
        (
            registry.wer_evaluator.key,
            registry.wer_evaluator.version,
        ),
        (
            registry.cer_evaluator.key,
            registry.cer_evaluator.version,
        ),
        (
            registry.word_alignment_evaluator.key,
            registry.word_alignment_evaluator.version,
        ),
    } == {
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
    }

    assert (
        db.query(HveeMetricDefinition).count()
        == 5
    )
    assert (
        db.query(HveeEvaluatorVersion).count()
        == 3
    )


def test_normalized_registry_resolution_is_idempotent(
    db: Session,
):
    first = resolve_asr_normalized_text_error_registry(
        db
    )
    second = resolve_asr_normalized_text_error_registry(
        db
    )

    assert first.wer_metric.id == second.wer_metric.id
    assert first.cer_metric.id == second.cer_metric.id

    assert (
        first.substitutions_metric.id
        == second.substitutions_metric.id
    )
    assert (
        first.insertions_metric.id
        == second.insertions_metric.id
    )
    assert (
        first.deletions_metric.id
        == second.deletions_metric.id
    )

    assert (
        first.word_alignment_evaluator.id
        == second.word_alignment_evaluator.id
    )

    assert (
        db.query(HveeMetricDefinition).count()
        == 5
    )
    assert (
        db.query(HveeEvaluatorVersion).count()
        == 3
    )


def test_stages_five_normalized_observations(
    db: Session,
):
    run, test_case = build_resources(db)

    evaluation = evaluate_normalized_transcript_pair(
        reference_text=test_case.reference_transcript,
        generated_text="hello there",
    )

    observations = (
        stage_asr_normalized_text_error_observations(
            db,
            evaluation_run=run,
            test_case=test_case,
            evaluation=evaluation,
        )
    )

    db.flush()

    assert len(observations) == 5
    assert (
        db.query(HveeObservation).count()
        == 5
    )

    metrics_by_id = {
        metric.id: metric
        for metric in db.query(
            HveeMetricDefinition
        ).all()
    }

    observations_by_key = {
        metrics_by_id[
            observation.metric_definition_id
        ].key: observation
        for observation in observations
    }

    assert set(observations_by_key) == {
        NORMALIZED_WER_METRIC.key,
        NORMALIZED_CER_METRIC.key,
        NORMALIZED_SUBSTITUTIONS_METRIC.key,
        NORMALIZED_INSERTIONS_METRIC.key,
        NORMALIZED_DELETIONS_METRIC.key,
    }

    assert observations_by_key[
        NORMALIZED_WER_METRIC.key
    ].number_value == pytest.approx(
        evaluation.wer
    )

    assert observations_by_key[
        NORMALIZED_CER_METRIC.key
    ].number_value == pytest.approx(
        evaluation.cer
    )

    assert observations_by_key[
        NORMALIZED_SUBSTITUTIONS_METRIC.key
    ].integer_value == evaluation.substitutions

    assert observations_by_key[
        NORMALIZED_INSERTIONS_METRIC.key
    ].integer_value == evaluation.insertions

    assert observations_by_key[
        NORMALIZED_DELETIONS_METRIC.key
    ].integer_value == evaluation.deletions


def test_normalized_staging_does_not_commit(
    db: Session,
):
    run, test_case = build_resources(db)
    db.commit()

    evaluation = evaluate_normalized_transcript_pair(
        reference_text=test_case.reference_transcript,
        generated_text="hello there",
    )

    stage_asr_normalized_text_error_observations(
        db,
        evaluation_run=run,
        test_case=test_case,
        evaluation=evaluation,
    )

    assert (
        db.query(HveeObservation).count()
        == 5
    )

    db.rollback()

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

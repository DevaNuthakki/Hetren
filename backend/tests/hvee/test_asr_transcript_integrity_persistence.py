from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from app.hvee_asr_observation_service import (
    stage_asr_transcript_integrity_observations,
)
from app.hvee_asr_registry import (
    resolve_asr_transcript_integrity_registry,
)
from app.hvee_models import (
    HveeEvaluatorVersion,
    HveeMetricDefinition,
    HveeObservation,
)
from hvee.packs.asr import (
    EXACT_NORMALIZED_MATCH_METRIC,
    GENERATED_EMPTY_METRIC,
    MISSING_OUTPUT_METRIC,
    REFERENCE_EMPTY_METRIC,
    TRANSCRIPT_INTEGRITY_EVALUATOR,
    UNEXPECTED_OUTPUT_METRIC,
    evaluate_normalized_transcript_pair,
    evaluate_transcript_integrity,
)


def _sqlite_connection(
    dbapi_connection,
    _connection_record,
) -> None:
    dbapi_connection.isolation_level = None


def _sqlite_begin(connection) -> None:
    connection.exec_driver_sql("BEGIN")


def _build_engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )

    event.listen(
        engine,
        "connect",
        _sqlite_connection,
    )
    event.listen(
        engine,
        "begin",
        _sqlite_begin,
    )

    return engine


def _build_resources(
    db: Session,
    *,
    reference_text: str = "Hello, WORLD!",
) -> tuple[
    models.EvaluationRun,
    models.TestCase,
]:
    project = models.Project(
        name="Transcript integrity project",
    )
    dataset = models.Dataset(
        project=project,
        name="Transcript integrity dataset",
    )
    test_case = models.TestCase(
        dataset=dataset,
        title="Transcript integrity case",
        reference_transcript=reference_text,
    )
    run = models.EvaluationRun(
        project=project,
        run_name="Transcript integrity run",
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


def _evaluate(
    *,
    reference_text: str,
    generated_text: str,
):
    normalized = evaluate_normalized_transcript_pair(
        reference_text=reference_text,
        generated_text=generated_text,
    )

    return evaluate_transcript_integrity(
        normalized
    )


import pytest


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = _build_engine()

    Base.metadata.create_all(engine)

    factory = sessionmaker(bind=engine)
    session = factory()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_transcript_integrity_registry_resolves_canonical_identities(
    db: Session,
):
    registry = (
        resolve_asr_transcript_integrity_registry(
            db
        )
    )

    assert {
        (
            registry.exact_match_metric.key,
            registry.exact_match_metric.version,
        ),
        (
            registry.reference_empty_metric.key,
            registry.reference_empty_metric.version,
        ),
        (
            registry.generated_empty_metric.key,
            registry.generated_empty_metric.version,
        ),
        (
            registry.unexpected_output_metric.key,
            registry.unexpected_output_metric.version,
        ),
        (
            registry.missing_output_metric.key,
            registry.missing_output_metric.version,
        ),
    } == {
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

    assert (
        registry.evaluator.key,
        registry.evaluator.version,
    ) == (
        TRANSCRIPT_INTEGRITY_EVALUATOR.key,
        TRANSCRIPT_INTEGRITY_EVALUATOR.version,
    )

    assert (
        db.query(HveeMetricDefinition).count()
        == 5
    )
    assert (
        db.query(HveeEvaluatorVersion).count()
        == 1
    )


def test_transcript_integrity_registry_is_idempotent(
    db: Session,
):
    first = (
        resolve_asr_transcript_integrity_registry(
            db
        )
    )
    second = (
        resolve_asr_transcript_integrity_registry(
            db
        )
    )

    assert (
        first.exact_match_metric.id
        == second.exact_match_metric.id
    )
    assert (
        first.reference_empty_metric.id
        == second.reference_empty_metric.id
    )
    assert (
        first.generated_empty_metric.id
        == second.generated_empty_metric.id
    )
    assert (
        first.unexpected_output_metric.id
        == second.unexpected_output_metric.id
    )
    assert (
        first.missing_output_metric.id
        == second.missing_output_metric.id
    )
    assert (
        first.evaluator.id
        == second.evaluator.id
    )

    assert (
        db.query(HveeMetricDefinition).count()
        == 5
    )
    assert (
        db.query(HveeEvaluatorVersion).count()
        == 1
    )


def test_stages_five_boolean_integrity_observations(
    db: Session,
):
    run, test_case = _build_resources(
        db,
        reference_text=" ... ",
    )

    evaluation = _evaluate(
        reference_text=(
            test_case.reference_transcript
        ),
        generated_text="unexpected words",
    )

    observations = (
        stage_asr_transcript_integrity_observations(
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
        EXACT_NORMALIZED_MATCH_METRIC.key,
        REFERENCE_EMPTY_METRIC.key,
        GENERATED_EMPTY_METRIC.key,
        UNEXPECTED_OUTPUT_METRIC.key,
        MISSING_OUTPUT_METRIC.key,
    }

    expected_values = {
        EXACT_NORMALIZED_MATCH_METRIC.key: False,
        REFERENCE_EMPTY_METRIC.key: True,
        GENERATED_EMPTY_METRIC.key: False,
        UNEXPECTED_OUTPUT_METRIC.key: True,
        MISSING_OUTPUT_METRIC.key: False,
    }

    evaluator_ids = set()

    for metric_key, expected_value in (
        expected_values.items()
    ):
        observation = observations_by_key[
            metric_key
        ]

        assert observation.scope == "test_case"
        assert observation.status == "success"
        assert observation.value_type == "boolean"

        assert (
            observation.boolean_value
            is expected_value
        )

        assert observation.number_value is None
        assert observation.integer_value is None
        assert observation.string_value is None
        assert observation.json_value is None

        evaluator_ids.add(
            observation.evaluator_version_id
        )

    assert len(evaluator_ids) == 1

    evaluator = db.get(
        HveeEvaluatorVersion,
        evaluator_ids.pop(),
    )

    assert evaluator is not None
    assert (
        evaluator.key,
        evaluator.version,
    ) == (
        TRANSCRIPT_INTEGRITY_EVALUATOR.key,
        TRANSCRIPT_INTEGRITY_EVALUATOR.version,
    )


def test_transcript_integrity_staging_does_not_commit(
    db: Session,
):
    run, test_case = _build_resources(
        db,
        reference_text="expected words",
    )
    db.commit()

    evaluation = _evaluate(
        reference_text=(
            test_case.reference_transcript
        ),
        generated_text="",
    )

    stage_asr_transcript_integrity_observations(
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

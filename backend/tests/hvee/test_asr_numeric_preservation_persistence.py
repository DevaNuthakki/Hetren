from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from app.hvee_asr_observation_service import (
    stage_asr_numeric_preservation_observations,
)
from app.hvee_asr_registry import (
    resolve_asr_numeric_preservation_registry,
)
from app.hvee_models import (
    HveeEvaluatorVersion,
    HveeMetricDefinition,
    HveeObservation,
)
from hvee.packs.asr import (
    GENERATED_NUMERIC_TOKEN_COUNT_METRIC,
    MISSING_NUMERIC_TOKEN_COUNT_METRIC,
    NUMERIC_TOKEN_PRESERVATION_EVALUATOR,
    NUMERIC_TOKEN_SEQUENCE_MATCH_METRIC,
    REFERENCE_NUMERIC_TOKEN_COUNT_METRIC,
    UNEXPECTED_NUMERIC_TOKEN_COUNT_METRIC,
    evaluate_numeric_preservation,
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
    *,
    reference_text: str = "dose 15 mg",
) -> tuple[
    models.EvaluationRun,
    models.TestCase,
]:
    project = models.Project(
        name="Numeric preservation project",
    )

    dataset = models.Dataset(
        project=project,
        name="Numeric preservation dataset",
    )

    test_case = models.TestCase(
        dataset=dataset,
        title="Numeric preservation case",
        reference_transcript=reference_text,
    )

    run = models.EvaluationRun(
        project=project,
        run_name="Numeric preservation run",
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


def test_numeric_registry_resolves_canonical_identities(
    db: Session,
):
    registry = (
        resolve_asr_numeric_preservation_registry(
            db
        )
    )

    assert {
        (
            registry.reference_count_metric.key,
            registry.reference_count_metric.version,
        ),
        (
            registry.generated_count_metric.key,
            registry.generated_count_metric.version,
        ),
        (
            registry.sequence_match_metric.key,
            registry.sequence_match_metric.version,
        ),
        (
            registry.missing_count_metric.key,
            registry.missing_count_metric.version,
        ),
        (
            registry.unexpected_count_metric.key,
            registry.unexpected_count_metric.version,
        ),
    } == {
        (
            REFERENCE_NUMERIC_TOKEN_COUNT_METRIC.key,
            REFERENCE_NUMERIC_TOKEN_COUNT_METRIC.version,
        ),
        (
            GENERATED_NUMERIC_TOKEN_COUNT_METRIC.key,
            GENERATED_NUMERIC_TOKEN_COUNT_METRIC.version,
        ),
        (
            NUMERIC_TOKEN_SEQUENCE_MATCH_METRIC.key,
            NUMERIC_TOKEN_SEQUENCE_MATCH_METRIC.version,
        ),
        (
            MISSING_NUMERIC_TOKEN_COUNT_METRIC.key,
            MISSING_NUMERIC_TOKEN_COUNT_METRIC.version,
        ),
        (
            UNEXPECTED_NUMERIC_TOKEN_COUNT_METRIC.key,
            UNEXPECTED_NUMERIC_TOKEN_COUNT_METRIC.version,
        ),
    }

    assert (
        registry.evaluator.key,
        registry.evaluator.version,
    ) == (
        NUMERIC_TOKEN_PRESERVATION_EVALUATOR.key,
        NUMERIC_TOKEN_PRESERVATION_EVALUATOR.version,
    )

    assert (
        db.query(HveeMetricDefinition).count()
        == 5
    )

    assert (
        db.query(HveeEvaluatorVersion).count()
        == 1
    )


def test_numeric_registry_resolution_is_idempotent(
    db: Session,
):
    first = (
        resolve_asr_numeric_preservation_registry(
            db
        )
    )

    second = (
        resolve_asr_numeric_preservation_registry(
            db
        )
    )

    assert (
        first.reference_count_metric.id
        == second.reference_count_metric.id
    )
    assert (
        first.generated_count_metric.id
        == second.generated_count_metric.id
    )
    assert (
        first.sequence_match_metric.id
        == second.sequence_match_metric.id
    )
    assert (
        first.missing_count_metric.id
        == second.missing_count_metric.id
    )
    assert (
        first.unexpected_count_metric.id
        == second.unexpected_count_metric.id
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


def test_stages_five_numeric_preservation_observations(
    db: Session,
):
    run, test_case = build_resources(
        db,
        reference_text="dose 15 then 15",
    )

    evaluation = evaluate_numeric_preservation(
        reference_text=(
            test_case.reference_transcript
        ),
        generated_text="dose 15 then 50",
    )

    observations = (
        stage_asr_numeric_preservation_observations(
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
        REFERENCE_NUMERIC_TOKEN_COUNT_METRIC.key,
        GENERATED_NUMERIC_TOKEN_COUNT_METRIC.key,
        NUMERIC_TOKEN_SEQUENCE_MATCH_METRIC.key,
        MISSING_NUMERIC_TOKEN_COUNT_METRIC.key,
        UNEXPECTED_NUMERIC_TOKEN_COUNT_METRIC.key,
    }

    reference_count = observations_by_key[
        REFERENCE_NUMERIC_TOKEN_COUNT_METRIC.key
    ]
    generated_count = observations_by_key[
        GENERATED_NUMERIC_TOKEN_COUNT_METRIC.key
    ]
    sequence_match = observations_by_key[
        NUMERIC_TOKEN_SEQUENCE_MATCH_METRIC.key
    ]
    missing_count = observations_by_key[
        MISSING_NUMERIC_TOKEN_COUNT_METRIC.key
    ]
    unexpected_count = observations_by_key[
        UNEXPECTED_NUMERIC_TOKEN_COUNT_METRIC.key
    ]

    assert reference_count.value_type == "integer"
    assert reference_count.integer_value == 2

    assert generated_count.value_type == "integer"
    assert generated_count.integer_value == 2

    assert sequence_match.value_type == "boolean"
    assert sequence_match.boolean_value is False

    assert missing_count.value_type == "integer"
    assert missing_count.integer_value == 1

    assert unexpected_count.value_type == "integer"
    assert unexpected_count.integer_value == 1

    evaluator_ids = {
        observation.evaluator_version_id
        for observation in observations
    }

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
        NUMERIC_TOKEN_PRESERVATION_EVALUATOR.key,
        NUMERIC_TOKEN_PRESERVATION_EVALUATOR.version,
    )


def test_numeric_staging_does_not_commit(
    db: Session,
):
    run, test_case = build_resources(
        db,
        reference_text="invoice 48217",
    )

    db.commit()

    evaluation = evaluate_numeric_preservation(
        reference_text=(
            test_case.reference_transcript
        ),
        generated_text="invoice 48271",
    )

    stage_asr_numeric_preservation_observations(
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

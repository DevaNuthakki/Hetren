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
    stage_evaluation_result,
)
from app.hvee_models import (
    HveeMetricDefinition,
    HveeObservation,
)
from app.hvee_observation_evidence import (
    HveeObservationEvidenceError,
    build_test_case_observation_evidence_bundle,
    load_test_case_observation_evidence_records,
)
from hvee.core.observation_evidence import (
    verify_observation_evidence_bundle,
)
from hvee.packs.asr import (
    CER_METRIC,
    CRITICAL_NUMBER_METRICS,
    EXACT_NORMALIZED_MATCH_METRIC,
    GENERATED_EMPTY_METRIC,
    GENERATED_NUMERIC_TOKEN_COUNT_METRIC,
    MISSING_NUMERIC_TOKEN_COUNT_METRIC,
    MISSING_OUTPUT_METRIC,
    NORMALIZED_CER_METRIC,
    NORMALIZED_DELETIONS_METRIC,
    NORMALIZED_INSERTIONS_METRIC,
    NORMALIZED_SUBSTITUTIONS_METRIC,
    NORMALIZED_WER_METRIC,
    NUMERIC_TOKEN_SEQUENCE_MATCH_METRIC,
    REFERENCE_EMPTY_METRIC,
    REFERENCE_NUMERIC_TOKEN_COUNT_METRIC,
    UNEXPECTED_NUMERIC_TOKEN_COUNT_METRIC,
    UNEXPECTED_OUTPUT_METRIC,
    WER_METRIC,
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
) -> tuple[
    models.EvaluationRun,
    models.TestCase,
]:
    project = models.Project(
        name="Observation evidence project",
    )
    db.add(project)
    db.flush()

    dataset = models.Dataset(
        project_id=project.id,
        name="Observation evidence dataset",
    )
    db.add(dataset)
    db.flush()

    test_case = models.TestCase(
        dataset_id=dataset.id,
        title="Observation evidence case",
        reference_transcript=(
            "invoice 48217 total 1,250"
        ),
    )
    db.add(test_case)
    db.flush()

    run = stage_evaluation_run_with_manifest(
        db,
        project_id=project.id,
        run_name="Observation evidence run",
        model_name="test-model",
    )

    return run, test_case


def test_adapter_builds_bundle_from_all_27_asr_observations(
    db: Session,
):
    run, test_case = build_resources(db)

    stage_evaluation_result(
        db=db,
        db_run=run,
        db_test_case=test_case,
        generated_text=(
            "invoice 48271 total 1,250"
        ),
    )

    db.flush()

    records = (
        load_test_case_observation_evidence_records(
            db,
            evaluation_run_id=run.id,
            test_case_id=test_case.id,
        )
    )

    assert len(records) == 27

    bundle = (
        build_test_case_observation_evidence_bundle(
            db,
            evaluation_run_id=run.id,
            test_case_id=test_case.id,
        )
    )

    assert bundle["count"] == 27
    assert verify_observation_evidence_bundle(
        bundle
    )

    metric_keys = {
        observation["metric"]["key"]
        for observation in bundle[
            "observations"
        ]
    }

    assert metric_keys == {
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
        REFERENCE_NUMERIC_TOKEN_COUNT_METRIC.key,
        GENERATED_NUMERIC_TOKEN_COUNT_METRIC.key,
        NUMERIC_TOKEN_SEQUENCE_MATCH_METRIC.key,
        MISSING_NUMERIC_TOKEN_COUNT_METRIC.key,
        UNEXPECTED_NUMERIC_TOKEN_COUNT_METRIC.key,
        *(
            metric.key
            for metric in CRITICAL_NUMBER_METRICS
        ),
    }


def test_adapter_preserves_numeric_observation_values(
    db: Session,
):
    run, test_case = build_resources(db)

    stage_evaluation_result(
        db=db,
        db_run=run,
        db_test_case=test_case,
        generated_text=(
            "invoice 48271 total 1,250"
        ),
    )

    db.flush()

    bundle = (
        build_test_case_observation_evidence_bundle(
            db,
            evaluation_run_id=run.id,
            test_case_id=test_case.id,
        )
    )

    observations = {
        observation["metric"]["key"]:
            observation
        for observation in bundle[
            "observations"
        ]
    }

    assert observations[
        REFERENCE_NUMERIC_TOKEN_COUNT_METRIC.key
    ]["value"] == 2

    assert observations[
        GENERATED_NUMERIC_TOKEN_COUNT_METRIC.key
    ]["value"] == 2

    assert observations[
        NUMERIC_TOKEN_SEQUENCE_MATCH_METRIC.key
    ]["value"] is False

    assert observations[
        MISSING_NUMERIC_TOKEN_COUNT_METRIC.key
    ]["value"] == 1

    assert observations[
        UNEXPECTED_NUMERIC_TOKEN_COUNT_METRIC.key
    ]["value"] == 1


def test_adapter_excludes_database_registry_ids_and_timestamps(
    db: Session,
):
    run, test_case = build_resources(db)

    stage_evaluation_result(
        db=db,
        db_run=run,
        db_test_case=test_case,
        generated_text="invoice 48217 total 1,250",
    )

    db.flush()

    bundle = (
        build_test_case_observation_evidence_bundle(
            db,
            evaluation_run_id=run.id,
            test_case_id=test_case.id,
        )
    )

    serialized = str(bundle)

    assert "metric_definition_id" not in serialized
    assert "evaluator_version_id" not in serialized
    assert "created_at" not in serialized
    assert "observation_id" not in serialized


def test_adapter_excludes_run_scoped_observations(
    db: Session,
):
    run, test_case = build_resources(db)

    stage_evaluation_result(
        db=db,
        db_run=run,
        db_test_case=test_case,
        generated_text="invoice 48217 total 1,250",
    )

    db.flush()

    metric = (
        db.query(HveeMetricDefinition)
        .filter(
            HveeMetricDefinition.key
            == WER_METRIC.key,
        )
        .one()
    )

    test_case_observation = (
        db.query(HveeObservation)
        .filter(
            HveeObservation.evaluation_run_id
            == run.id,
            HveeObservation.test_case_id
            == test_case.id,
            HveeObservation.metric_definition_id
            == metric.id,
        )
        .one()
    )

    run_observation = HveeObservation(
        evaluation_run_id=run.id,
        test_case_id=None,
        metric_definition_id=(
            test_case_observation.metric_definition_id
        ),
        evaluator_version_id=(
            test_case_observation.evaluator_version_id
        ),
        evaluation_type="asr",
        scope="run",
        status="success",
        value_type="number",
        number_value=0.5,
    )

    db.add(run_observation)
    db.flush()

    bundle = (
        build_test_case_observation_evidence_bundle(
            db,
            evaluation_run_id=run.id,
            test_case_id=test_case.id,
        )
    )

    assert bundle["count"] == 27

    assert all(
        observation["scope"]
        == "test_case"
        for observation in bundle[
            "observations"
        ]
    )


def test_adapter_rejects_missing_observation_set(
    db: Session,
):
    run, test_case = build_resources(db)

    with pytest.raises(
        HveeObservationEvidenceError,
        match="no test-case observations",
    ):
        build_test_case_observation_evidence_bundle(
            db,
            evaluation_run_id=run.id,
            test_case_id=test_case.id,
        )


def test_adapter_rejects_registry_evaluation_type_mismatch(
    db: Session,
):
    run, test_case = build_resources(db)

    stage_evaluation_result(
        db=db,
        db_run=run,
        db_test_case=test_case,
        generated_text="invoice 48217 total 1,250",
    )

    db.flush()

    observation = (
        db.query(HveeObservation)
        .filter(
            HveeObservation.evaluation_run_id
            == run.id,
            HveeObservation.test_case_id
            == test_case.id,
        )
        .first()
    )

    assert observation is not None

    metric = db.get(
        HveeMetricDefinition,
        observation.metric_definition_id,
    )

    assert metric is not None

    metric.evaluation_type = "other"

    with pytest.raises(
        HveeObservationEvidenceError,
        match="evaluation types do not match",
    ):
        build_test_case_observation_evidence_bundle(
            db,
            evaluation_run_id=run.id,
            test_case_id=test_case.id,
        )

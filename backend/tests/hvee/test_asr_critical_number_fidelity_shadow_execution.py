from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from app.evaluation_provenance import (
    stage_evaluation_run_with_manifest,
    verify_evaluation_result_observation_binding,
    verify_evaluation_result_provenance,
)
from app.evaluation_service import (
    build_quality_label,
    persist_evaluation_result,
)
from app.hvee_models import (
    HveeDecision,
    HveeMatchedReleaseDecision,
    HveeMetricDefinition,
    HveeObservation,
)
from hvee.packs.asr import (
    CRITICAL_NUMBER_APPLICABLE_METRIC,
    CRITICAL_NUMBER_FINDINGS_METRIC,
    CRITICAL_NUMBER_METRICS,
    CRITICAL_NUMBER_OUTCOME_METRIC,
    CRITICAL_NUMBER_PRESERVED_METRIC,
    CRITICAL_NUMBER_SUBSTITUTION_COUNT_METRIC,
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
    reference_text: str,
) -> tuple[
    models.EvaluationRun,
    models.TestCase,
]:
    project = models.Project(
        name="Critical number shadow project",
    )
    db.add(project)
    db.flush()

    dataset = models.Dataset(
        project_id=project.id,
        name="Critical number shadow dataset",
    )
    db.add(dataset)
    db.flush()

    test_case = models.TestCase(
        dataset_id=dataset.id,
        title="Critical number shadow case",
        reference_transcript=reference_text,
    )
    db.add(test_case)
    db.flush()

    run = stage_evaluation_run_with_manifest(
        db,
        project_id=project.id,
        run_name="Critical number shadow run",
        model_name="test-model",
    )

    return run, test_case


def observations_by_metric_key(
    db: Session,
    *,
    evaluation_run_id: int,
    test_case_id: int,
) -> dict[str, HveeObservation]:
    observations = (
        db.query(HveeObservation)
        .filter(
            HveeObservation.evaluation_run_id
            == evaluation_run_id,
            HveeObservation.test_case_id
            == test_case_id,
        )
        .all()
    )
    metric_by_id = {
        metric.id: metric.key
        for metric in (
            db.query(HveeMetricDefinition).all()
        )
    }

    return {
        metric_by_id[
            observation.metric_definition_id
        ]: observation
        for observation in observations
    }


def test_shadow_execution_persists_and_seals_failure_evidence(
    db: Session,
):
    run, test_case = build_resources(
        db,
        reference_text="invoice 48217 total $1,250",
    )

    result = persist_evaluation_result(
        db=db,
        db_run=run,
        db_test_case=test_case,
        generated_text="invoice 48271 total $1,250",
        execution_mode="uploaded_transcript",
    )

    observations = observations_by_metric_key(
        db,
        evaluation_run_id=run.id,
        test_case_id=test_case.id,
    )
    critical_metric_keys = {
        metric.key
        for metric in CRITICAL_NUMBER_METRICS
    }

    assert len(observations) == 38
    assert critical_metric_keys <= set(observations)

    assert observations[
        CRITICAL_NUMBER_APPLICABLE_METRIC.key
    ].boolean_value is True
    assert observations[
        CRITICAL_NUMBER_PRESERVED_METRIC.key
    ].boolean_value is False
    assert observations[
        CRITICAL_NUMBER_OUTCOME_METRIC.key
    ].string_value == "not_preserved"
    assert observations[
        CRITICAL_NUMBER_SUBSTITUTION_COUNT_METRIC.key
    ].integer_value == 1

    findings = observations[
        CRITICAL_NUMBER_FINDINGS_METRIC.key
    ].json_value
    assert isinstance(findings, list)
    assert any(
        finding["finding_type"] == "substitution"
        for finding in findings
    )

    provenance = result.provenance
    assert provenance is not None
    assert provenance.provenance_payload[
        "hvee_observations"
    ]["count"] == 38
    assert verify_evaluation_result_provenance(
        provenance
    )
    assert verify_evaluation_result_observation_binding(
        db,
        provenance,
    )


def test_shadow_failure_does_not_change_release_behavior(
    db: Session,
):
    reference_text = (
        "please confirm invoice 48217 remains active before approving "
        "the scheduled shipment for tomorrow morning with the operations "
        "team after final review today"
    )
    generated_text = reference_text.replace(
        "48217",
        "48271",
    )
    run, test_case = build_resources(
        db,
        reference_text=reference_text,
    )

    result = persist_evaluation_result(
        db=db,
        db_run=run,
        db_test_case=test_case,
        generated_text=generated_text,
        execution_mode="uploaded_transcript",
    )

    observations = observations_by_metric_key(
        db,
        evaluation_run_id=run.id,
        test_case_id=test_case.id,
    )

    assert observations[
        CRITICAL_NUMBER_PRESERVED_METRIC.key
    ].boolean_value is False
    assert result.wer <= 0.05
    assert result.quality_label == "excellent"
    assert result.quality_label == build_quality_label(
        result.wer
    )
    assert run.quality_label == "excellent"

    assert db.query(models.ReleaseReport).count() == 0
    assert db.query(HveeDecision).count() == 0
    assert (
        db.query(HveeMatchedReleaseDecision).count()
        == 0
    )


@pytest.mark.parametrize(
    (
        "reference_text",
        "expected_applicable",
        "expected_status",
        "expected_outcome",
    ),
    [
        (
            "plain transcript without numeric evidence",
            False,
            "abstained",
            "not_applicable",
        ),
        (
            "ratio 1/2",
            True,
            "unsupported",
            "insufficient_evidence",
        ),
    ],
)
def test_shadow_execution_preserves_inconclusive_status(
    db: Session,
    reference_text: str,
    expected_applicable: bool,
    expected_status: str,
    expected_outcome: str,
):
    run, test_case = build_resources(
        db,
        reference_text=reference_text,
    )

    persist_evaluation_result(
        db=db,
        db_run=run,
        db_test_case=test_case,
        generated_text=reference_text,
        execution_mode="uploaded_transcript",
    )

    observations = observations_by_metric_key(
        db,
        evaluation_run_id=run.id,
        test_case_id=test_case.id,
    )

    applicable = observations[
        CRITICAL_NUMBER_APPLICABLE_METRIC.key
    ]
    preserved = observations[
        CRITICAL_NUMBER_PRESERVED_METRIC.key
    ]
    outcome = observations[
        CRITICAL_NUMBER_OUTCOME_METRIC.key
    ]

    assert applicable.boolean_value is expected_applicable
    assert preserved.status == expected_status
    assert preserved.boolean_value is None
    assert preserved.status_detail is not None
    assert outcome.string_value == expected_outcome

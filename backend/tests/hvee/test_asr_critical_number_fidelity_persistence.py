from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from app.hvee_asr_observation_service import (
    stage_asr_critical_number_fidelity_observations,
)
from app.hvee_asr_registry import (
    resolve_asr_critical_number_fidelity_registry,
)
from app.hvee_models import (
    HveeEvaluatorVersion,
    HveeMetricDefinition,
    HveeObservation,
)
from hvee.packs.asr import (
    CRITICAL_NUMBER_AMBIGUITY_COUNT_METRIC,
    CRITICAL_NUMBER_APPLICABLE_METRIC,
    CRITICAL_NUMBER_FIDELITY_EVALUATOR,
    CRITICAL_NUMBER_FINDINGS_METRIC,
    CRITICAL_NUMBER_GENERATED_COUNT_METRIC,
    CRITICAL_NUMBER_INSERTION_COUNT_METRIC,
    CRITICAL_NUMBER_METRICS,
    CRITICAL_NUMBER_OMISSION_COUNT_METRIC,
    CRITICAL_NUMBER_OUTCOME_METRIC,
    CRITICAL_NUMBER_PRESERVED_METRIC,
    CRITICAL_NUMBER_REFERENCE_COUNT_METRIC,
    CRITICAL_NUMBER_SUBSTITUTION_COUNT_METRIC,
    EN_US_CRITICAL_NUMBER_PROFILE,
    evaluate_critical_number_fidelity,
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
        name="Critical number persistence project",
    )
    dataset = models.Dataset(
        project=project,
        name="Critical number persistence dataset",
    )
    test_case = models.TestCase(
        dataset=dataset,
        title="Critical number persistence case",
        reference_transcript=reference_text,
    )
    run = models.EvaluationRun(
        project=project,
        run_name="Critical number persistence run",
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


def observations_by_key(
    db: Session,
    observations: tuple[HveeObservation, ...],
) -> dict[str, HveeObservation]:
    metric_keys = {
        metric.id: metric.key
        for metric in db.query(
            HveeMetricDefinition
        ).all()
    }

    return {
        metric_keys[
            observation.metric_definition_id
        ]: observation
        for observation in observations
    }


def test_critical_number_registry_resolves_canonical_identities(
    db: Session,
):
    registry = (
        resolve_asr_critical_number_fidelity_registry(
            db
        )
    )
    persisted_metrics = (
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

    assert {
        (metric.key, metric.version)
        for metric in persisted_metrics
    } == {
        (metric.key, metric.version)
        for metric in CRITICAL_NUMBER_METRICS
    }
    assert (
        registry.evaluator.key,
        registry.evaluator.version,
    ) == (
        CRITICAL_NUMBER_FIDELITY_EVALUATOR.key,
        CRITICAL_NUMBER_FIDELITY_EVALUATOR.version,
    )
    assert (
        db.query(HveeMetricDefinition).count()
        == 10
    )
    assert (
        db.query(HveeEvaluatorVersion).count()
        == 1
    )


def test_critical_number_registry_resolution_is_idempotent(
    db: Session,
):
    first = (
        resolve_asr_critical_number_fidelity_registry(
            db
        )
    )
    second = (
        resolve_asr_critical_number_fidelity_registry(
            db
        )
    )

    assert first.evaluator.id == second.evaluator.id
    assert (
        first.applicable_metric.id
        == second.applicable_metric.id
    )
    assert (
        first.preserved_metric.id
        == second.preserved_metric.id
    )
    assert (
        first.findings_metric.id
        == second.findings_metric.id
    )
    assert (
        db.query(HveeMetricDefinition).count()
        == 10
    )
    assert (
        db.query(HveeEvaluatorVersion).count()
        == 1
    )


def test_stages_complete_critical_number_evidence(
    db: Session,
):
    run, test_case = build_resources(
        db,
        reference_text="dose 5 mg now",
    )
    evaluation = evaluate_critical_number_fidelity(
        reference_text=test_case.reference_transcript,
        generated_text="dose 50 mg now",
        profile=EN_US_CRITICAL_NUMBER_PROFILE,
    )

    observations = (
        stage_asr_critical_number_fidelity_observations(
            db,
            evaluation_run=run,
            test_case=test_case,
            evaluation=evaluation,
        )
    )
    db.flush()

    assert len(observations) == 10
    assert db.query(HveeObservation).count() == 10

    by_key = observations_by_key(
        db,
        observations,
    )

    assert set(by_key) == {
        metric.key
        for metric in CRITICAL_NUMBER_METRICS
    }
    assert by_key[
        CRITICAL_NUMBER_APPLICABLE_METRIC.key
    ].boolean_value is True
    assert by_key[
        CRITICAL_NUMBER_PRESERVED_METRIC.key
    ].boolean_value is False
    assert by_key[
        CRITICAL_NUMBER_OUTCOME_METRIC.key
    ].string_value == "not_preserved"
    assert by_key[
        CRITICAL_NUMBER_REFERENCE_COUNT_METRIC.key
    ].integer_value == 1
    assert by_key[
        CRITICAL_NUMBER_GENERATED_COUNT_METRIC.key
    ].integer_value == 1
    assert by_key[
        CRITICAL_NUMBER_SUBSTITUTION_COUNT_METRIC.key
    ].integer_value == 1
    assert by_key[
        CRITICAL_NUMBER_OMISSION_COUNT_METRIC.key
    ].integer_value == 0
    assert by_key[
        CRITICAL_NUMBER_INSERTION_COUNT_METRIC.key
    ].integer_value == 0
    assert by_key[
        CRITICAL_NUMBER_AMBIGUITY_COUNT_METRIC.key
    ].integer_value == 0

    findings = by_key[
        CRITICAL_NUMBER_FINDINGS_METRIC.key
    ].json_value
    assert isinstance(findings, list)
    assert findings[0]["reason_code"] == (
        "value_substitution"
    )
    assert findings[0]["profile_key"] == (
        EN_US_CRITICAL_NUMBER_PROFILE.key
    )
    assert findings[0]["profile_version"] == (
        EN_US_CRITICAL_NUMBER_PROFILE.version
    )

    evaluator_ids = {
        observation.evaluator_version_id
        for observation in observations
    }
    assert len(evaluator_ids) == 1


def test_not_applicable_preserves_abstained_status(
    db: Session,
):
    run, test_case = build_resources(
        db,
        reference_text="hello world",
    )
    evaluation = evaluate_critical_number_fidelity(
        reference_text=test_case.reference_transcript,
        generated_text="hello there",
        profile=EN_US_CRITICAL_NUMBER_PROFILE,
    )

    observations = (
        stage_asr_critical_number_fidelity_observations(
            db,
            evaluation_run=run,
            test_case=test_case,
            evaluation=evaluation,
        )
    )
    db.flush()
    by_key = observations_by_key(
        db,
        observations,
    )

    applicable = by_key[
        CRITICAL_NUMBER_APPLICABLE_METRIC.key
    ]
    preserved = by_key[
        CRITICAL_NUMBER_PRESERVED_METRIC.key
    ]
    outcome = by_key[
        CRITICAL_NUMBER_OUTCOME_METRIC.key
    ]

    assert applicable.status == "success"
    assert applicable.boolean_value is False
    assert preserved.status == "abstained"
    assert preserved.boolean_value is None
    assert preserved.status_detail is not None
    assert outcome.status == "success"
    assert outcome.string_value == "not_applicable"


def test_unsupported_evidence_preserves_unsupported_status(
    db: Session,
):
    run, test_case = build_resources(
        db,
        reference_text="ratio 1/2",
    )
    evaluation = evaluate_critical_number_fidelity(
        reference_text=test_case.reference_transcript,
        generated_text="ratio 1/2",
        profile=EN_US_CRITICAL_NUMBER_PROFILE,
    )

    observations = (
        stage_asr_critical_number_fidelity_observations(
            db,
            evaluation_run=run,
            test_case=test_case,
            evaluation=evaluation,
        )
    )
    db.flush()
    by_key = observations_by_key(
        db,
        observations,
    )

    preserved = by_key[
        CRITICAL_NUMBER_PRESERVED_METRIC.key
    ]
    findings = by_key[
        CRITICAL_NUMBER_FINDINGS_METRIC.key
    ]

    assert preserved.status == "unsupported"
    assert preserved.boolean_value is None
    assert preserved.status_detail is not None
    assert findings.status == "success"
    assert isinstance(findings.json_value, list)
    assert any(
        finding["finding_type"] == "unsupported"
        for finding in findings.json_value
    )


def test_critical_number_staging_does_not_commit(
    db: Session,
):
    run, test_case = build_resources(
        db,
        reference_text="pay $5 now",
    )
    db.commit()

    evaluation = evaluate_critical_number_fidelity(
        reference_text=test_case.reference_transcript,
        generated_text="pay $50 now",
        profile=EN_US_CRITICAL_NUMBER_PROFILE,
    )
    stage_asr_critical_number_fidelity_observations(
        db,
        evaluation_run=run,
        test_case=test_case,
        evaluation=evaluation,
    )

    assert db.query(HveeObservation).count() == 10

    db.rollback()

    assert db.query(HveeObservation).count() == 0
    assert (
        db.query(HveeMetricDefinition).count()
        == 0
    )
    assert (
        db.query(HveeEvaluatorVersion).count()
        == 0
    )

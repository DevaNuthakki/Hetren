from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.critical_terminology_vocabulary_service import (
    CriticalTerminologyVocabularyIntegrityError,
    stage_critical_terminology_vocabulary_version,
)
from app.database import Base
from app.evaluation_provenance import (
    calculate_manifest_sha256,
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
    CRITICAL_TERMINOLOGY_APPLICABLE_METRIC,
    CRITICAL_TERMINOLOGY_FINDINGS_METRIC,
    CRITICAL_TERMINOLOGY_GENERATED_COUNT_METRIC,
    CRITICAL_TERMINOLOGY_INSERTION_COUNT_METRIC,
    CRITICAL_TERMINOLOGY_METRICS,
    CRITICAL_TERMINOLOGY_OMISSION_COUNT_METRIC,
    CRITICAL_TERMINOLOGY_ORDERING_CHANGE_COUNT_METRIC,
    CRITICAL_TERMINOLOGY_OUTCOME_METRIC,
    CRITICAL_TERMINOLOGY_PRESERVED_METRIC,
    CRITICAL_TERMINOLOGY_REFERENCE_COUNT_METRIC,
    CRITICAL_TERMINOLOGY_SUBSTITUTION_COUNT_METRIC,
    CRITICAL_TERMINOLOGY_VOCABULARY_SHA256_METRIC,
)


BASE_ASR_OBSERVATION_COUNT = 38
CRITICAL_TERMINOLOGY_OBSERVATION_COUNT = 11
CONFIGURED_ASR_OBSERVATION_COUNT = (
    BASE_ASR_OBSERVATION_COUNT
    + CRITICAL_TERMINOLOGY_OBSERVATION_COUNT
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


def terminology_terms() -> list[
    dict[str, object]
]:
    return [
        {
            "term_key": "cardiovex",
            "canonical_text": "Cardiovex",
            "accepted_surfaces": [
                "Cardiovex",
            ],
        },
        {
            "term_key": "neurodex",
            "canonical_text": "Neurodex",
            "accepted_surfaces": [
                "Neurodex",
            ],
        },
    ]


def create_project_context(
    db: Session,
    *,
    reference_text: str,
    configure_vocabulary: bool,
) -> tuple[
    models.User,
    models.Project,
    models.EvaluationRun,
    models.TestCase,
    models.CriticalTerminologyVocabularyVersion | None,
]:
    user = models.User(
        email="terminology-shadow@example.com",
    )
    db.add(user)
    db.flush()

    project = models.Project(
        name="Critical Terminology shadow project",
    )
    db.add(project)
    db.flush()

    dataset = models.Dataset(
        project_id=project.id,
        name="Critical Terminology shadow dataset",
    )
    db.add(dataset)
    db.flush()

    test_case = models.TestCase(
        dataset_id=dataset.id,
        title="Critical Terminology shadow case",
        reference_transcript=reference_text,
    )
    db.add(test_case)
    db.flush()

    vocabulary = None

    if configure_vocabulary:
        vocabulary = (
            stage_critical_terminology_vocabulary_version(
                db,
                project_id=project.id,
                created_by_user_id=user.id,
                terms=terminology_terms(),
            )
        )

    run = stage_evaluation_run_with_manifest(
        db,
        project_id=project.id,
        run_name="Critical Terminology shadow run",
        model_name="test-model",
    )

    return (
        user,
        project,
        run,
        test_case,
        vocabulary,
    )


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


def terminology_metric_keys() -> set[str]:
    return {
        metric.key
        for metric in CRITICAL_TERMINOLOGY_METRICS
    }


def test_unconfigured_run_retains_existing_38_observations(
    db: Session,
):
    (
        _,
        _,
        run,
        test_case,
        vocabulary,
    ) = create_project_context(
        db,
        reference_text=(
            "administer Cardiovex today"
        ),
        configure_vocabulary=False,
    )

    assert vocabulary is None

    result = persist_evaluation_result(
        db=db,
        db_run=run,
        db_test_case=test_case,
        generated_text=(
            "administer Neurodex today"
        ),
        execution_mode="uploaded_transcript",
    )

    observations = observations_by_metric_key(
        db,
        evaluation_run_id=run.id,
        test_case_id=test_case.id,
    )

    assert len(observations) == (
        BASE_ASR_OBSERVATION_COUNT
    )

    assert (
        terminology_metric_keys()
        .isdisjoint(observations)
    )

    assert result.provenance is not None

    assert result.provenance.provenance_payload[
        "hvee_observations"
    ]["count"] == BASE_ASR_OBSERVATION_COUNT

    assert verify_evaluation_result_provenance(
        result.provenance
    )

    assert verify_evaluation_result_observation_binding(
        db,
        result.provenance,
    )


def test_configured_run_persists_and_seals_all_49_observations(
    db: Session,
):
    (
        _,
        _,
        run,
        test_case,
        vocabulary,
    ) = create_project_context(
        db,
        reference_text=(
            "administer Cardiovex today"
        ),
        configure_vocabulary=True,
    )

    assert vocabulary is not None

    result = persist_evaluation_result(
        db=db,
        db_run=run,
        db_test_case=test_case,
        generated_text=(
            "administer Neurodex today"
        ),
        execution_mode="uploaded_transcript",
    )

    observations = observations_by_metric_key(
        db,
        evaluation_run_id=run.id,
        test_case_id=test_case.id,
    )

    terminology_keys = terminology_metric_keys()

    assert len(CRITICAL_TERMINOLOGY_METRICS) == (
        CRITICAL_TERMINOLOGY_OBSERVATION_COUNT
    )

    assert len(observations) == (
        CONFIGURED_ASR_OBSERVATION_COUNT
    )

    assert terminology_keys <= set(
        observations
    )

    assert observations[
        CRITICAL_TERMINOLOGY_APPLICABLE_METRIC.key
    ].boolean_value is True

    preserved = observations[
        CRITICAL_TERMINOLOGY_PRESERVED_METRIC.key
    ]

    assert preserved.status == "success"
    assert preserved.boolean_value is False

    assert observations[
        CRITICAL_TERMINOLOGY_OUTCOME_METRIC.key
    ].string_value == "not_preserved"

    assert observations[
        CRITICAL_TERMINOLOGY_VOCABULARY_SHA256_METRIC.key
    ].string_value == vocabulary.vocabulary_sha256

    assert observations[
        CRITICAL_TERMINOLOGY_REFERENCE_COUNT_METRIC.key
    ].integer_value == 1

    assert observations[
        CRITICAL_TERMINOLOGY_GENERATED_COUNT_METRIC.key
    ].integer_value == 1

    assert observations[
        CRITICAL_TERMINOLOGY_SUBSTITUTION_COUNT_METRIC.key
    ].integer_value == 1

    assert observations[
        CRITICAL_TERMINOLOGY_OMISSION_COUNT_METRIC.key
    ].integer_value == 0

    assert observations[
        CRITICAL_TERMINOLOGY_INSERTION_COUNT_METRIC.key
    ].integer_value == 0

    assert observations[
        CRITICAL_TERMINOLOGY_ORDERING_CHANGE_COUNT_METRIC.key
    ].integer_value == 0

    findings = observations[
        CRITICAL_TERMINOLOGY_FINDINGS_METRIC.key
    ].json_value

    assert isinstance(findings, list)
    assert findings

    assert all(
        finding["profile_key"]
        == vocabulary.profile_key
        and finding["profile_version"]
        == vocabulary.profile_version
        and finding["vocabulary_sha256"]
        == vocabulary.vocabulary_sha256
        for finding in findings
    )

    assert any(
        finding["finding_type"]
        == "substitution"
        for finding in findings
    )

    assert result.provenance is not None

    assert result.provenance.provenance_payload[
        "hvee_observations"
    ]["count"] == (
        CONFIGURED_ASR_OBSERVATION_COUNT
    )

    assert verify_evaluation_result_provenance(
        result.provenance
    )

    assert verify_evaluation_result_observation_binding(
        db,
        result.provenance,
    )


def test_run_pinned_to_revision_one_uses_it_after_revision_two_exists(
    db: Session,
):
    (
        user,
        project,
        run,
        test_case,
        first,
    ) = create_project_context(
        db,
        reference_text=(
            "administer Cardiovex today"
        ),
        configure_vocabulary=True,
    )

    assert first is not None
    assert first.revision == 1

    second = (
        stage_critical_terminology_vocabulary_version(
            db,
            project_id=project.id,
            created_by_user_id=user.id,
            terms=terminology_terms(),
        )
    )

    assert second.revision == 2
    assert second.profile_key == first.profile_key
    assert second.profile_version == "2"

    assert (
        second.vocabulary_sha256
        != first.vocabulary_sha256
    )

    persist_evaluation_result(
        db=db,
        db_run=run,
        db_test_case=test_case,
        generated_text=(
            "administer Neurodex today"
        ),
        execution_mode="uploaded_transcript",
    )

    observations = observations_by_metric_key(
        db,
        evaluation_run_id=run.id,
        test_case_id=test_case.id,
    )

    sha_observation = observations[
        CRITICAL_TERMINOLOGY_VOCABULARY_SHA256_METRIC.key
    ]

    assert sha_observation.string_value == (
        first.vocabulary_sha256
    )

    assert sha_observation.string_value != (
        second.vocabulary_sha256
    )

    findings = observations[
        CRITICAL_TERMINOLOGY_FINDINGS_METRIC.key
    ].json_value

    assert isinstance(findings, list)
    assert findings

    assert all(
        finding["profile_key"]
        == first.profile_key
        and finding["profile_version"] == "1"
        and finding["vocabulary_sha256"]
        == first.vocabulary_sha256
        for finding in findings
    )


def test_run_created_before_configuration_never_adopts_later_vocabulary(
    db: Session,
):
    (
        user,
        project,
        run,
        test_case,
        vocabulary,
    ) = create_project_context(
        db,
        reference_text=(
            "administer Cardiovex today"
        ),
        configure_vocabulary=False,
    )

    assert vocabulary is None

    stage_critical_terminology_vocabulary_version(
        db,
        project_id=project.id,
        created_by_user_id=user.id,
        terms=terminology_terms(),
    )

    result = persist_evaluation_result(
        db=db,
        db_run=run,
        db_test_case=test_case,
        generated_text=(
            "administer Neurodex today"
        ),
        execution_mode="uploaded_transcript",
    )

    observations = observations_by_metric_key(
        db,
        evaluation_run_id=run.id,
        test_case_id=test_case.id,
    )

    assert len(observations) == (
        BASE_ASR_OBSERVATION_COUNT
    )

    assert (
        terminology_metric_keys()
        .isdisjoint(observations)
    )

    assert result.provenance is not None

    assert result.provenance.provenance_payload[
        "hvee_observations"
    ]["count"] == BASE_ASR_OBSERVATION_COUNT


def test_terminology_failure_remains_evidence_only(
    db: Session,
):
    reference_text = (
        "please administer Cardiovex after the "
        "scheduled clinical review this afternoon "
        "and confirm the treatment record afterward"
    )

    generated_text = reference_text.replace(
        "Cardiovex",
        "Neurodex",
    )

    (
        _,
        _,
        run,
        test_case,
        vocabulary,
    ) = create_project_context(
        db,
        reference_text=reference_text,
        configure_vocabulary=True,
    )

    assert vocabulary is not None

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
        CRITICAL_TERMINOLOGY_PRESERVED_METRIC.key
    ].boolean_value is False

    assert result.quality_label == (
        build_quality_label(
            result.wer
        )
    )

    assert run.quality_label == (
        result.quality_label
    )

    assert (
        db.query(models.ReleaseReport).count()
        == 0
    )

    assert db.query(HveeDecision).count() == 0

    assert (
        db.query(
            HveeMatchedReleaseDecision
        ).count()
        == 0
    )


def test_corrupted_pinned_vocabulary_rolls_back_evaluation(
    db: Session,
):
    (
        _,
        _,
        run,
        test_case,
        vocabulary,
    ) = create_project_context(
        db,
        reference_text=(
            "administer Cardiovex today"
        ),
        configure_vocabulary=True,
    )

    assert vocabulary is not None

    # Persist the valid setup first so the later rollback is isolated
    # to the evaluation transaction.
    db.commit()

    vocabulary.vocabulary_sha256 = "0" * 64
    db.commit()

    result_count_before = (
        db.query(models.EvaluationResult).count()
    )

    observation_count_before = (
        db.query(HveeObservation).count()
    )

    provenance_count_before = (
        db.query(
            models.EvaluationResultProvenance
        ).count()
    )

    with pytest.raises(
        CriticalTerminologyVocabularyIntegrityError
    ):
        persist_evaluation_result(
            db=db,
            db_run=run,
            db_test_case=test_case,
            generated_text=(
                "administer Neurodex today"
            ),
            execution_mode="uploaded_transcript",
        )

    assert (
        db.query(models.EvaluationResult).count()
        == result_count_before
    )

    assert (
        db.query(HveeObservation).count()
        == observation_count_before
    )

    assert (
        db.query(
            models.EvaluationResultProvenance
        ).count()
        == provenance_count_before
    )

    db.refresh(run)

    assert run.status == "created"
    assert run.wer is None
    assert run.cer is None
    assert run.quality_label is None


def test_rehashed_tampered_run_binding_still_fails_closed(
    db: Session,
):
    (
        _,
        _,
        run,
        test_case,
        vocabulary,
    ) = create_project_context(
        db,
        reference_text=(
            "administer Cardiovex today"
        ),
        configure_vocabulary=True,
    )

    assert vocabulary is not None

    manifest = (
        db.query(models.EvaluationRunManifest)
        .filter(
            models.EvaluationRunManifest.run_id
            == run.id
        )
        .one()
    )

    manifest.manifest_payload = {
        **manifest.manifest_payload,
        "critical_terminology": {
            **manifest.manifest_payload[
                "critical_terminology"
            ],
            "revision": 999,
        },
    }

    # Rehash the outer manifest deliberately. This proves that the
    # evaluation checks the pinned vocabulary identity itself rather
    # than relying only on the outer manifest digest.
    manifest.manifest_sha256 = (
        calculate_manifest_sha256(
            manifest.manifest_payload
        )
    )

    db.commit()

    result_count_before = (
        db.query(models.EvaluationResult).count()
    )

    observation_count_before = (
        db.query(HveeObservation).count()
    )

    with pytest.raises(
        CriticalTerminologyVocabularyIntegrityError
    ):
        persist_evaluation_result(
            db=db,
            db_run=run,
            db_test_case=test_case,
            generated_text=(
                "administer Neurodex today"
            ),
            execution_mode="uploaded_transcript",
        )

    assert (
        db.query(models.EvaluationResult).count()
        == result_count_before
    )

    assert (
        db.query(HveeObservation).count()
        == observation_count_before
    )

from __future__ import annotations

import asyncio
from collections.abc import Generator
from dataclasses import dataclass

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.auth.dependencies import get_current_user
from app.critical_terminology_vocabulary_service import (
    stage_critical_terminology_vocabulary_version,
)
from app.database import Base, get_db
from app.evaluation_provenance import (
    LEGACY_EVALUATION_MANIFEST_SCHEMA_VERSION,
    calculate_manifest_sha256,
    stage_evaluation_run_with_manifest,
    verify_evaluation_run_manifest,
)
from app.evaluation_service import persist_evaluation_result
from app.hvee_models import (
    HveeMetricDefinition,
    HveeObservation,
)
from app.main import app
from hvee.packs.asr import (
    CRITICAL_IDENTIFIER_METRICS,
    CRITICAL_NUMBER_METRICS,
    CRITICAL_NUMBER_REFERENCE_COUNT_METRIC,
    CRITICAL_TERMINOLOGY_METRICS,
    CRITICAL_TERMINOLOGY_VOCABULARY_SHA256_METRIC,
)


@dataclass(frozen=True)
class EvaluatedContext:
    user: models.User
    organization: models.Organization
    project: models.Project
    dataset: models.Dataset
    test_case: models.TestCase
    run: models.EvaluationRun
    result: models.EvaluationResult
    vocabulary: (
        models.CriticalTerminologyVocabularyVersion | None
    )


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
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


def _request(
    db: Session,
    method: str,
    path: str,
    *,
    current_user: models.User | None = None,
):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    if current_user is not None:

        def override_current_user():
            return current_user

        app.dependency_overrides[
            get_current_user
        ] = override_current_user

    async def send_request():
        transport = ASGITransport(app=app)

        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(
                method,
                path,
            )

    try:
        return asyncio.run(send_request())
    finally:
        app.dependency_overrides.pop(
            get_db,
            None,
        )
        app.dependency_overrides.pop(
            get_current_user,
            None,
        )


def _terminology_terms() -> list[dict[str, object]]:
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


def _create_legacy_v1_run(
    db: Session,
    *,
    project: models.Project,
    suffix: str,
) -> models.EvaluationRun:
    run = models.EvaluationRun(
        project_id=project.id,
        run_name=f"Legacy semantic run {suffix}",
        evaluation_type="asr",
        model_name="legacy-asr",
        status="created",
    )
    db.add(run)
    db.flush()

    payload = {
        "schema_version": (
            LEGACY_EVALUATION_MANIFEST_SCHEMA_VERSION
        ),
        "evaluation_type": "asr",
        "run": {
            "id": run.id,
            "project_id": project.id,
            "name": run.run_name,
        },
        "model": {
            "name": run.model_name,
        },
        "evaluator": {
            "engine": "hetren",
            "contract_version": "asr-v1",
        },
    }

    manifest = models.EvaluationRunManifest(
        run_id=run.id,
        schema_version=(
            LEGACY_EVALUATION_MANIFEST_SCHEMA_VERSION
        ),
        evaluation_type="asr",
        manifest_payload=payload,
        manifest_sha256=calculate_manifest_sha256(
            payload
        ),
    )

    db.add(manifest)
    db.flush()

    assert verify_evaluation_run_manifest(
        manifest
    )

    return run


def _create_evaluated_context(
    db: Session,
    *,
    role: str = "owner",
    suffix: str,
    configure_vocabulary: bool = False,
    legacy_v1: bool = False,
) -> EvaluatedContext:
    user = models.User(
        email=f"{suffix}@example.com",
    )
    db.add(user)
    db.flush()

    organization = models.Organization(
        name=f"Semantic evidence org {suffix}",
    )
    db.add(organization)
    db.flush()

    db.add(
        models.OrganizationMembership(
            user_id=user.id,
            organization_id=organization.id,
            role=role,
        )
    )
    db.flush()

    project = models.Project(
        organization_id=organization.id,
        name=f"Semantic evidence project {suffix}",
    )
    db.add(project)
    db.flush()

    dataset = models.Dataset(
        project_id=project.id,
        name=f"Semantic evidence dataset {suffix}",
    )
    db.add(dataset)
    db.flush()

    test_case = models.TestCase(
        dataset_id=dataset.id,
        title=f"Semantic evidence case {suffix}",
        reference_transcript=(
            "administer Cardiovex today"
        ),
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
                terms=_terminology_terms(),
            )
        )

    if legacy_v1:
        run = _create_legacy_v1_run(
            db,
            project=project,
            suffix=suffix,
        )
    else:
        run = stage_evaluation_run_with_manifest(
            db,
            project_id=project.id,
            run_name=f"Semantic evidence run {suffix}",
            model_name="test-model",
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

    db.commit()

    return EvaluatedContext(
        user=user,
        organization=organization,
        project=project,
        dataset=dataset,
        test_case=test_case,
        run=run,
        result=result,
        vocabulary=vocabulary,
    )


def _family_metric_keys(
    payload: dict,
    family: str,
) -> list[str]:
    return [
        observation["metric_key"]
        for observation in payload[
            family
        ]["observations"]
    ]


def _find_observation(
    db: Session,
    *,
    context: EvaluatedContext,
    metric_key: str,
) -> HveeObservation:
    return (
        db.query(HveeObservation)
        .join(
            HveeMetricDefinition,
            HveeMetricDefinition.id
            == HveeObservation.metric_definition_id,
        )
        .filter(
            HveeObservation.evaluation_run_id
            == context.run.id,
            HveeObservation.test_case_id
            == context.test_case.id,
            HveeMetricDefinition.key
            == metric_key,
        )
        .one()
    )


def _assert_integrity_conflict(response) -> None:
    assert response.status_code == 409
    assert response.json() == {
        "detail": (
            "Semantic evidence integrity "
            "check failed"
        )
    }


def test_semantic_evidence_requires_authentication(
    db_session: Session,
) -> None:
    context = _create_evaluated_context(
        db_session,
        suffix="semantic-unauthenticated",
    )

    response = _request(
        db_session,
        "GET",
        (
            f"/results/{context.result.id}"
            "/semantic-evidence"
        ),
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Authentication is required."
    }


@pytest.mark.parametrize(
    "role",
    [
        "owner",
        "admin",
        "engineer",
        "viewer",
    ],
)
def test_product_read_roles_can_read_semantic_evidence(
    db_session: Session,
    role: str,
) -> None:
    context = _create_evaluated_context(
        db_session,
        role=role,
        suffix=f"semantic-read-{role}",
    )

    response = _request(
        db_session,
        "GET",
        (
            f"/results/{context.result.id}"
            "/semantic-evidence"
        ),
        current_user=context.user,
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["result_id"] == context.result.id
    assert (
        payload["evaluation_run_id"]
        == context.run.id
    )
    assert (
        payload["test_case_id"]
        == context.test_case.id
    )
    assert payload["evaluation_type"] == "asr"


def test_billing_admin_cannot_read_semantic_evidence(
    db_session: Session,
) -> None:
    context = _create_evaluated_context(
        db_session,
        role="billing_admin",
        suffix="semantic-billing-admin",
    )

    response = _request(
        db_session,
        "GET",
        (
            f"/results/{context.result.id}"
            "/semantic-evidence"
        ),
        current_user=context.user,
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": (
            "Evaluation result permission denied"
        )
    }


def test_other_tenant_semantic_evidence_is_hidden(
    db_session: Session,
) -> None:
    own = _create_evaluated_context(
        db_session,
        suffix="semantic-own-tenant",
    )
    other = _create_evaluated_context(
        db_session,
        suffix="semantic-other-tenant",
    )

    response = _request(
        db_session,
        "GET",
        (
            f"/results/{other.result.id}"
            "/semantic-evidence"
        ),
        current_user=own.user,
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Evaluation result not found"
    }


def test_unconfigured_run_returns_exact_number_and_identifier_evidence(
    db_session: Session,
) -> None:
    context = _create_evaluated_context(
        db_session,
        suffix="semantic-unconfigured",
        configure_vocabulary=False,
    )

    response = _request(
        db_session,
        "GET",
        (
            f"/results/{context.result.id}"
            "/semantic-evidence"
        ),
        current_user=context.user,
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["critical_number"]["status"] == (
        "available"
    )
    assert payload["critical_identifier"]["status"] == (
        "available"
    )
    assert payload["critical_terminology"]["status"] == (
        "not_configured"
    )

    assert _family_metric_keys(
        payload,
        "critical_number",
    ) == [
        metric.key
        for metric in CRITICAL_NUMBER_METRICS
    ]

    assert _family_metric_keys(
        payload,
        "critical_identifier",
    ) == [
        metric.key
        for metric in CRITICAL_IDENTIFIER_METRICS
    ]

    assert len(
        payload["critical_number"]["observations"]
    ) == 10

    assert len(
        payload["critical_identifier"]["observations"]
    ) == 11

    assert (
        payload["critical_terminology"][
            "observations"
        ]
        == []
    )


def test_configured_run_returns_exact_10_11_11_evidence_and_pinned_sha(
    db_session: Session,
) -> None:
    context = _create_evaluated_context(
        db_session,
        suffix="semantic-configured",
        configure_vocabulary=True,
    )

    response = _request(
        db_session,
        "GET",
        (
            f"/results/{context.result.id}"
            "/semantic-evidence"
        ),
        current_user=context.user,
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["critical_number"]["status"] == (
        "available"
    )
    assert payload["critical_identifier"]["status"] == (
        "available"
    )
    assert payload["critical_terminology"]["status"] == (
        "available"
    )

    assert len(
        payload["critical_number"]["observations"]
    ) == 10

    assert len(
        payload["critical_identifier"]["observations"]
    ) == 11

    assert len(
        payload["critical_terminology"]["observations"]
    ) == 11

    assert _family_metric_keys(
        payload,
        "critical_number",
    ) == [
        metric.key
        for metric in CRITICAL_NUMBER_METRICS
    ]

    assert _family_metric_keys(
        payload,
        "critical_identifier",
    ) == [
        metric.key
        for metric in CRITICAL_IDENTIFIER_METRICS
    ]

    assert _family_metric_keys(
        payload,
        "critical_terminology",
    ) == [
        metric.key
        for metric in CRITICAL_TERMINOLOGY_METRICS
    ]

    manifest = context.run.manifest
    assert manifest is not None

    pinned_sha = (
        manifest.manifest_payload[
            "critical_terminology"
        ]["vocabulary_sha256"]
    )

    vocabulary_observation = next(
        observation
        for observation in payload[
            "critical_terminology"
        ]["observations"]
        if observation["metric_key"]
        == (
            CRITICAL_TERMINOLOGY_VOCABULARY_SHA256_METRIC.key
        )
    )

    assert vocabulary_observation["status"] == (
        "success"
    )
    assert vocabulary_observation["value"] == (
        pinned_sha
    )


def test_legacy_v1_run_reports_legacy_terminology_unavailable(
    db_session: Session,
) -> None:
    context = _create_evaluated_context(
        db_session,
        suffix="semantic-legacy-v1",
        legacy_v1=True,
    )

    response = _request(
        db_session,
        "GET",
        (
            f"/results/{context.result.id}"
            "/semantic-evidence"
        ),
        current_user=context.user,
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["critical_number"]["status"] == (
        "available"
    )
    assert payload["critical_identifier"]["status"] == (
        "available"
    )
    assert payload["critical_terminology"] == {
        "status": "legacy_unavailable",
        "observations": [],
    }


def test_observation_value_tampering_fails_closed(
    db_session: Session,
) -> None:
    context = _create_evaluated_context(
        db_session,
        suffix="semantic-observation-tamper",
    )

    observation = _find_observation(
        db_session,
        context=context,
        metric_key=(
            CRITICAL_NUMBER_REFERENCE_COUNT_METRIC.key
        ),
    )

    assert observation.integer_value is not None

    observation.integer_value += 1
    db_session.commit()

    response = _request(
        db_session,
        "GET",
        (
            f"/results/{context.result.id}"
            "/semantic-evidence"
        ),
        current_user=context.user,
    )

    _assert_integrity_conflict(response)


def test_missing_semantic_observation_fails_closed(
    db_session: Session,
) -> None:
    context = _create_evaluated_context(
        db_session,
        suffix="semantic-missing-observation",
    )

    observation = _find_observation(
        db_session,
        context=context,
        metric_key=(
            CRITICAL_NUMBER_REFERENCE_COUNT_METRIC.key
        ),
    )

    db_session.delete(observation)
    db_session.commit()

    response = _request(
        db_session,
        "GET",
        (
            f"/results/{context.result.id}"
            "/semantic-evidence"
        ),
        current_user=context.user,
    )

    _assert_integrity_conflict(response)


def test_valid_rehashed_manifest_replacement_still_fails_closed(
    db_session: Session,
) -> None:
    context = _create_evaluated_context(
        db_session,
        suffix="semantic-manifest-replacement",
    )

    manifest = (
        db_session.query(
            models.EvaluationRunManifest
        )
        .filter(
            models.EvaluationRunManifest.run_id
            == context.run.id
        )
        .one()
    )

    original_sha = manifest.manifest_sha256

    manifest.manifest_payload = {
        **manifest.manifest_payload,
        "model": {
            "name": "tampered-but-rehashed-model",
        },
    }

    manifest.manifest_sha256 = (
        calculate_manifest_sha256(
            manifest.manifest_payload
        )
    )

    db_session.commit()

    assert manifest.manifest_sha256 != original_sha
    assert verify_evaluation_run_manifest(
        manifest
    )

    response = _request(
        db_session,
        "GET",
        (
            f"/results/{context.result.id}"
            "/semantic-evidence"
        ),
        current_user=context.user,
    )

    _assert_integrity_conflict(response)


def test_corrupted_run_pinned_vocabulary_fails_closed(
    db_session: Session,
) -> None:
    context = _create_evaluated_context(
        db_session,
        suffix="semantic-vocabulary-corrupt",
        configure_vocabulary=True,
    )

    assert context.vocabulary is not None

    context.vocabulary.vocabulary_sha256 = (
        "0" * 64
    )

    db_session.commit()

    response = _request(
        db_session,
        "GET",
        (
            f"/results/{context.result.id}"
            "/semantic-evidence"
        ),
        current_user=context.user,
    )

    _assert_integrity_conflict(response)


def test_semantic_evidence_get_performs_no_database_writes(
    db_session: Session,
) -> None:
    context = _create_evaluated_context(
        db_session,
        suffix="semantic-read-only",
        configure_vocabulary=True,
    )

    engine = db_session.get_bind()
    writes: list[str] = []

    def capture_statement(
        _conn,
        _cursor,
        statement,
        _parameters,
        _context,
        _executemany,
    ) -> None:
        normalized = statement.lstrip().upper()

        if normalized.startswith(
            (
                "INSERT ",
                "UPDATE ",
                "DELETE ",
            )
        ):
            writes.append(statement)

    event.listen(
        engine,
        "before_cursor_execute",
        capture_statement,
    )

    try:
        response = _request(
            db_session,
            "GET",
            (
                f"/results/{context.result.id}"
                "/semantic-evidence"
            ),
            current_user=context.user,
        )
    finally:
        event.remove(
            engine,
            "before_cursor_execute",
            capture_statement,
        )

    assert response.status_code == 200
    assert writes == []


def test_semantic_evidence_read_stays_pinned_after_new_vocabulary_revision(
    db_session: Session,
) -> None:
    context = _create_evaluated_context(
        db_session,
        suffix="semantic-read-pinned-revision",
        configure_vocabulary=True,
    )

    assert context.vocabulary is not None

    pinned_v1_sha = (
        context.vocabulary.vocabulary_sha256
    )

    vocabulary_v2 = (
        stage_critical_terminology_vocabulary_version(
            db_session,
            project_id=context.project.id,
            created_by_user_id=context.user.id,
            terms=[
                *_terminology_terms(),
                {
                    "term_key": "pulmovex",
                    "canonical_text": "Pulmovex",
                    "accepted_surfaces": [
                        "Pulmovex",
                    ],
                },
            ],
        )
    )

    db_session.commit()

    assert vocabulary_v2.revision == 2
    assert (
        vocabulary_v2.vocabulary_sha256
        != pinned_v1_sha
    )

    response = _request(
        db_session,
        "GET",
        (
            f"/results/{context.result.id}"
            "/semantic-evidence"
        ),
        current_user=context.user,
    )

    assert response.status_code == 200

    payload = response.json()

    vocabulary_observation = next(
        observation
        for observation in payload[
            "critical_terminology"
        ]["observations"]
        if observation["metric_key"]
        == (
            CRITICAL_TERMINOLOGY_VOCABULARY_SHA256_METRIC.key
        )
    )

    assert vocabulary_observation["value"] == (
        pinned_v1_sha
    )
    assert vocabulary_observation["value"] != (
        vocabulary_v2.vocabulary_sha256
    )

    manifest = context.run.manifest
    assert manifest is not None

    assert (
        manifest.manifest_payload[
            "critical_terminology"
        ]["revision"]
        == 1
    )
    assert (
        manifest.manifest_payload[
            "critical_terminology"
        ]["vocabulary_sha256"]
        == pinned_v1_sha
    )

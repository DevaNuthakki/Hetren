import asyncio
from collections.abc import Generator

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
from app.main import app


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(
        dbapi_connection,
        _connection_record,
    ) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)

    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _create_user(
    db: Session,
    *,
    email: str,
) -> models.User:
    user = models.User(
        email=email,
    )
    db.add(user)
    db.flush()

    return user


def _create_organization(
    db: Session,
    *,
    name: str,
) -> models.Organization:
    organization = models.Organization(
        name=name,
    )
    db.add(organization)
    db.flush()

    return organization


def _add_membership(
    db: Session,
    *,
    user: models.User,
    organization: models.Organization,
    role: str,
) -> None:
    db.add(
        models.OrganizationMembership(
            user_id=user.id,
            organization_id=organization.id,
            role=role,
        )
    )
    db.flush()


def _create_project(
    db: Session,
    *,
    organization: models.Organization,
    name: str = "Terminology project",
) -> models.Project:
    project = models.Project(
        organization_id=organization.id,
        name=name,
    )
    db.add(project)
    db.flush()

    return project


def _create_project_user_context(
    db: Session,
    *,
    role: str,
    suffix: str,
) -> tuple[
    models.User,
    models.Organization,
    models.Project,
]:
    user = _create_user(
        db,
        email=f"{suffix}-{role}@example.com",
    )

    organization = _create_organization(
        db,
        name=f"{suffix} organization",
    )

    _add_membership(
        db,
        user=user,
        organization=organization,
        role=role,
    )

    project = _create_project(
        db,
        organization=organization,
        name=f"{suffix} project",
    )

    db.commit()

    return user, organization, project


def _request(
    db: Session,
    method: str,
    path: str,
    *,
    current_user: models.User | None = None,
    json: dict | None = None,
):
    def override_get_db():
        yield db

    app.dependency_overrides[
        get_db
    ] = override_get_db

    if current_user is not None:

        def override_current_user():
            return current_user

        app.dependency_overrides[
            get_current_user
        ] = override_current_user

    async def send_request():
        transport = ASGITransport(
            app=app,
        )

        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(
                method,
                path,
                json=json,
            )

    try:
        return asyncio.run(
            send_request()
        )
    finally:
        app.dependency_overrides.pop(
            get_db,
            None,
        )
        app.dependency_overrides.pop(
            get_current_user,
            None,
        )


def _v1_payload() -> dict:
    return {
        "terms": [
            {
                "term_key": "cardiovex",
                "canonical_text": "Cardiovex",
                "accepted_surfaces": [
                    "Cardiovex",
                    "Cardio Vex",
                ],
            },
            {
                "term_key": "neurodex",
                "canonical_text": "Neurodex",
                "accepted_surfaces": [
                    "Neurodex",
                ],
            },
        ],
    }


def _v2_payload() -> dict:
    return {
        "terms": [
            *_v1_payload()["terms"],
            {
                "term_key": "zenthora",
                "canonical_text": "Zenthora",
                "accepted_surfaces": [
                    "Zenthora",
                ],
            },
        ],
    }


def _stage_vocabulary(
    db: Session,
    *,
    project: models.Project,
    user: models.User,
) -> models.CriticalTerminologyVocabularyVersion:
    vocabulary = (
        stage_critical_terminology_vocabulary_version(
            db,
            project_id=project.id,
            created_by_user_id=user.id,
            terms=_v1_payload()["terms"],
        )
    )

    db.commit()
    db.refresh(vocabulary)

    return vocabulary


@pytest.mark.parametrize(
    ("method", "suffix", "payload"),
    [
        (
            "POST",
            "",
            _v1_payload(),
        ),
        (
            "GET",
            "",
            None,
        ),
        (
            "GET",
            "/current",
            None,
        ),
        (
            "GET",
            "/1",
            None,
        ),
    ],
)
def test_vocabulary_routes_require_authentication(
    db_session: Session,
    method: str,
    suffix: str,
    payload: dict | None,
) -> None:
    organization = _create_organization(
        db_session,
        name="Authentication organization",
    )
    project = _create_project(
        db_session,
        organization=organization,
    )
    db_session.commit()

    response = _request(
        db_session,
        method,
        (
            f"/projects/{project.id}/"
            "critical-terminology-vocabularies"
            f"{suffix}"
        ),
        json=payload,
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
    ],
)
def test_write_roles_can_create_vocabulary(
    db_session: Session,
    role: str,
) -> None:
    user, _, project = (
        _create_project_user_context(
            db_session,
            role=role,
            suffix=f"write-{role}",
        )
    )

    response = _request(
        db_session,
        "POST",
        (
            f"/projects/{project.id}/"
            "critical-terminology-vocabularies"
        ),
        current_user=user,
        json=_v1_payload(),
    )

    assert response.status_code == 201

    payload = response.json()

    assert payload["project_id"] == project.id
    assert payload["revision"] == 1
    assert payload["profile_version"] == "1"
    assert payload["language"] == "en"
    assert payload["locale"] == "en-US"

    assert payload[
        "created_by_user_id"
    ] == user.id

    assert payload["terms"] == (
        _v1_payload()["terms"]
    )

    assert payload[
        "profile_key"
    ].startswith(
        "project-critical-terminology-"
    )

    assert len(
        payload["vocabulary_sha256"]
    ) == 64


def test_viewer_cannot_create_vocabulary(
    db_session: Session,
) -> None:
    user, _, project = (
        _create_project_user_context(
            db_session,
            role="viewer",
            suffix="viewer-write",
        )
    )

    response = _request(
        db_session,
        "POST",
        (
            f"/projects/{project.id}/"
            "critical-terminology-vocabularies"
        ),
        current_user=user,
        json=_v1_payload(),
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Project permission denied"
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
def test_read_roles_can_read_vocabulary(
    db_session: Session,
    role: str,
) -> None:
    reader, organization, project = (
        _create_project_user_context(
            db_session,
            role=role,
            suffix=f"read-{role}",
        )
    )

    writer = _create_user(
        db_session,
        email=(
            f"read-{role}-writer@example.com"
        ),
    )

    _add_membership(
        db_session,
        user=writer,
        organization=organization,
        role="owner",
    )

    db_session.commit()

    vocabulary = _stage_vocabulary(
        db_session,
        project=project,
        user=writer,
    )

    history = _request(
        db_session,
        "GET",
        (
            f"/projects/{project.id}/"
            "critical-terminology-vocabularies"
        ),
        current_user=reader,
    )

    assert history.status_code == 200
    assert len(history.json()) == 1
    assert (
        history.json()[0]["revision"]
        == 1
    )

    current = _request(
        db_session,
        "GET",
        (
            f"/projects/{project.id}/"
            "critical-terminology-vocabularies/"
            "current"
        ),
        current_user=reader,
    )

    assert current.status_code == 200
    assert (
        current.json()["id"]
        == vocabulary.id
    )

    exact = _request(
        db_session,
        "GET",
        (
            f"/projects/{project.id}/"
            "critical-terminology-vocabularies/1"
        ),
        current_user=reader,
    )

    assert exact.status_code == 200
    assert (
        exact.json()["id"]
        == vocabulary.id
    )


@pytest.mark.parametrize(
    ("method", "suffix", "payload"),
    [
        (
            "GET",
            "",
            None,
        ),
        (
            "GET",
            "/current",
            None,
        ),
        (
            "GET",
            "/1",
            None,
        ),
        (
            "POST",
            "",
            _v1_payload(),
        ),
    ],
)
def test_billing_admin_has_no_vocabulary_access(
    db_session: Session,
    method: str,
    suffix: str,
    payload: dict | None,
) -> None:
    user, _, project = (
        _create_project_user_context(
            db_session,
            role="billing_admin",
            suffix="billing",
        )
    )

    response = _request(
        db_session,
        method,
        (
            f"/projects/{project.id}/"
            "critical-terminology-vocabularies"
            f"{suffix}"
        ),
        current_user=user,
        json=payload,
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Project permission denied"
    }


@pytest.mark.parametrize(
    ("method", "suffix", "payload"),
    [
        (
            "GET",
            "",
            None,
        ),
        (
            "GET",
            "/current",
            None,
        ),
        (
            "GET",
            "/1",
            None,
        ),
        (
            "POST",
            "",
            _v1_payload(),
        ),
    ],
)
def test_cross_tenant_project_is_hidden(
    db_session: Session,
    method: str,
    suffix: str,
    payload: dict | None,
) -> None:
    user_org = _create_organization(
        db_session,
        name="User organization",
    )
    target_org = _create_organization(
        db_session,
        name="Target organization",
    )

    user = _create_user(
        db_session,
        email="cross-tenant@example.com",
    )

    _add_membership(
        db_session,
        user=user,
        organization=user_org,
        role="owner",
    )

    target_project = _create_project(
        db_session,
        organization=target_org,
        name="Hidden project",
    )

    db_session.commit()

    response = _request(
        db_session,
        method,
        (
            f"/projects/{target_project.id}/"
            "critical-terminology-vocabularies"
            f"{suffix}"
        ),
        current_user=user,
        json=payload,
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Project not found"
    }


def test_unconfigured_project_history_is_empty(
    db_session: Session,
) -> None:
    user, _, project = (
        _create_project_user_context(
            db_session,
            role="viewer",
            suffix="empty-history",
        )
    )

    response = _request(
        db_session,
        "GET",
        (
            f"/projects/{project.id}/"
            "critical-terminology-vocabularies"
        ),
        current_user=user,
    )

    assert response.status_code == 200
    assert response.json() == []


def test_unconfigured_project_current_is_not_found(
    db_session: Session,
) -> None:
    user, _, project = (
        _create_project_user_context(
            db_session,
            role="viewer",
            suffix="empty-current",
        )
    )

    response = _request(
        db_session,
        "GET",
        (
            f"/projects/{project.id}/"
            "critical-terminology-vocabularies/"
            "current"
        ),
        current_user=user,
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": (
            "Critical terminology vocabulary "
            "is not configured"
        )
    }


def test_missing_exact_revision_is_not_found(
    db_session: Session,
) -> None:
    user, _, project = (
        _create_project_user_context(
            db_session,
            role="viewer",
            suffix="missing-revision",
        )
    )

    response = _request(
        db_session,
        "GET",
        (
            f"/projects/{project.id}/"
            "critical-terminology-vocabularies/99"
        ),
        current_user=user,
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": (
            "Critical terminology vocabulary "
            "revision not found"
        )
    }


@pytest.mark.parametrize(
    "revision",
    [
        0,
        -1,
    ],
)
def test_revision_must_be_positive(
    db_session: Session,
    revision: int,
) -> None:
    user, _, project = (
        _create_project_user_context(
            db_session,
            role="viewer",
            suffix=f"revision-{revision}",
        )
    )

    response = _request(
        db_session,
        "GET",
        (
            f"/projects/{project.id}/"
            "critical-terminology-vocabularies/"
            f"{revision}"
        ),
        current_user=user,
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": (
            "Critical terminology vocabulary "
            "revision must be positive"
        )
    }


def test_vocabulary_revisions_are_immutable_and_current_advances(
    db_session: Session,
) -> None:
    user, _, project = (
        _create_project_user_context(
            db_session,
            role="owner",
            suffix="versioning",
        )
    )

    base = (
        f"/projects/{project.id}/"
        "critical-terminology-vocabularies"
    )

    first = _request(
        db_session,
        "POST",
        base,
        current_user=user,
        json=_v1_payload(),
    )

    assert first.status_code == 201

    first_payload = first.json()

    second = _request(
        db_session,
        "POST",
        base,
        current_user=user,
        json=_v2_payload(),
    )

    assert second.status_code == 201

    second_payload = second.json()

    assert first_payload["revision"] == 1
    assert second_payload["revision"] == 2

    assert (
        first_payload["profile_key"]
        == second_payload["profile_key"]
    )

    assert (
        first_payload["profile_version"]
        == "1"
    )

    assert (
        second_payload["profile_version"]
        == "2"
    )

    assert (
        first_payload["vocabulary_sha256"]
        != second_payload["vocabulary_sha256"]
    )

    exact_v1 = _request(
        db_session,
        "GET",
        f"{base}/1",
        current_user=user,
    )

    assert exact_v1.status_code == 200
    assert (
        exact_v1.json()["terms"]
        == _v1_payload()["terms"]
    )

    exact_v2 = _request(
        db_session,
        "GET",
        f"{base}/2",
        current_user=user,
    )

    assert exact_v2.status_code == 200
    assert (
        exact_v2.json()["terms"]
        == _v2_payload()["terms"]
    )

    current = _request(
        db_session,
        "GET",
        f"{base}/current",
        current_user=user,
    )

    assert current.status_code == 200
    assert current.json()["revision"] == 2

    history = _request(
        db_session,
        "GET",
        base,
        current_user=user,
    )

    assert history.status_code == 200

    assert [
        item["revision"]
        for item in history.json()
    ] == [1, 2]

    assert (
        history.json()[0]["terms"]
        == _v1_payload()["terms"]
    )

    assert (
        history.json()[1]["terms"]
        == _v2_payload()["terms"]
    )


def test_empty_vocabulary_request_is_rejected(
    db_session: Session,
) -> None:
    user, _, project = (
        _create_project_user_context(
            db_session,
            role="owner",
            suffix="empty-payload",
        )
    )

    response = _request(
        db_session,
        "POST",
        (
            f"/projects/{project.id}/"
            "critical-terminology-vocabularies"
        ),
        current_user=user,
        json={
            "terms": [],
        },
    )

    assert response.status_code == 422


def test_duplicate_normalized_surface_is_rejected(
    db_session: Session,
) -> None:
    user, _, project = (
        _create_project_user_context(
            db_session,
            role="owner",
            suffix="duplicate-surface",
        )
    )

    response = _request(
        db_session,
        "POST",
        (
            f"/projects/{project.id}/"
            "critical-terminology-vocabularies"
        ),
        current_user=user,
        json={
            "terms": [
                {
                    "term_key": "cardiovex",
                    "canonical_text": "Cardiovex",
                    "accepted_surfaces": [
                        "Cardiovex",
                        "CardioVex",
                    ],
                },
            ],
        },
    )

    assert response.status_code == 422

    assert (
        "accepted surfaces must be unique "
        "after normalization"
        in response.json()["detail"]
    )


def test_canonical_text_must_be_registered_surface(
    db_session: Session,
) -> None:
    user, _, project = (
        _create_project_user_context(
            db_session,
            role="owner",
            suffix="canonical-surface",
        )
    )

    response = _request(
        db_session,
        "POST",
        (
            f"/projects/{project.id}/"
            "critical-terminology-vocabularies"
        ),
        current_user=user,
        json={
            "terms": [
                {
                    "term_key": "cardiovex",
                    "canonical_text": "Cardiovex",
                    "accepted_surfaces": [
                        "Cardio Vex",
                    ],
                },
            ],
        },
    )

    assert response.status_code == 422

    assert (
        "canonical text must be an accepted surface"
        in response.json()["detail"]
    )


def test_term_extra_fields_are_rejected(
    db_session: Session,
) -> None:
    user, _, project = (
        _create_project_user_context(
            db_session,
            role="owner",
            suffix="term-extra",
        )
    )

    response = _request(
        db_session,
        "POST",
        (
            f"/projects/{project.id}/"
            "critical-terminology-vocabularies"
        ),
        current_user=user,
        json={
            "terms": [
                {
                    "term_key": "cardiovex",
                    "canonical_text": "Cardiovex",
                    "accepted_surfaces": [
                        "Cardiovex",
                    ],
                    "automatic_aliases": [
                        "CardioVex",
                    ],
                },
            ],
        },
    )

    assert response.status_code == 422


def test_server_owned_vocabulary_identity_cannot_be_supplied(
    db_session: Session,
) -> None:
    user, _, project = (
        _create_project_user_context(
            db_session,
            role="owner",
            suffix="server-owned",
        )
    )

    payload = _v1_payload()
    payload["revision"] = 99
    payload["profile_key"] = "attacker-controlled"

    response = _request(
        db_session,
        "POST",
        (
            f"/projects/{project.id}/"
            "critical-terminology-vocabularies"
        ),
        current_user=user,
        json=payload,
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "suffix",
    [
        "",
        "/current",
        "/1",
    ],
)
def test_tampered_persisted_vocabulary_fails_closed(
    db_session: Session,
    suffix: str,
) -> None:
    user, _, project = (
        _create_project_user_context(
            db_session,
            role="owner",
            suffix=(
                "tamper-"
                + suffix.replace("/", "-")
            ),
        )
    )

    vocabulary = _stage_vocabulary(
        db_session,
        project=project,
        user=user,
    )

    vocabulary.vocabulary_sha256 = "0" * 64
    db_session.commit()

    response = _request(
        db_session,
        "GET",
        (
            f"/projects/{project.id}/"
            "critical-terminology-vocabularies"
            f"{suffix}"
        ),
        current_user=user,
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": (
            "Critical terminology vocabulary "
            "integrity check failed"
        )
    }


def test_historical_vocabulary_has_no_update_or_delete_api(
    db_session: Session,
) -> None:
    schema = app.openapi()

    collection_path = (
        "/projects/{project_id}/"
        "critical-terminology-vocabularies"
    )

    exact_path = (
        "/projects/{project_id}/"
        "critical-terminology-vocabularies/"
        "{revision}"
    )

    collection_methods = {
        method
        for method in schema["paths"][
            collection_path
        ]
        if method
        in {
            "get",
            "post",
            "put",
            "patch",
            "delete",
        }
    }

    exact_methods = {
        method
        for method in schema["paths"][
            exact_path
        ]
        if method
        in {
            "get",
            "post",
            "put",
            "patch",
            "delete",
        }
    }

    assert collection_methods == {
        "get",
        "post",
    }

    assert exact_methods == {
        "get",
    }

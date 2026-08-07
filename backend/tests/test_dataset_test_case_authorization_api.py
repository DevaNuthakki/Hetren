import asyncio
from collections.abc import Generator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.auth.dependencies import get_current_user
from app.database import Base, get_db
from app.main import app


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
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
    email: str,
) -> models.User:
    user = models.User(email=email)
    db.add(user)
    db.flush()
    return user


def _create_organization(
    db: Session,
    name: str,
) -> models.Organization:
    organization = models.Organization(name=name)
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
    name: str,
    organization: models.Organization | None,
) -> models.Project:
    project = models.Project(
        name=name,
        organization=organization,
    )
    db.add(project)
    db.flush()
    return project


def _create_dataset(
    db: Session,
    *,
    project: models.Project,
    name: str = "Dataset",
) -> models.Dataset:
    dataset = models.Dataset(
        project_id=project.id,
        name=name,
    )
    db.add(dataset)
    db.flush()
    return dataset


def _create_test_case(
    db: Session,
    *,
    dataset: models.Dataset,
    title: str = "Test case",
) -> models.TestCase:
    test_case = models.TestCase(
        dataset_id=dataset.id,
        title=title,
        reference_transcript="reference transcript",
    )
    db.add(test_case)
    db.flush()
    return test_case


def _create_hierarchy(
    db: Session,
    *,
    email: str,
    role: str,
):
    user = _create_user(db, email)
    organization = _create_organization(
        db,
        f"{role} organization",
    )
    _add_membership(
        db,
        user=user,
        organization=organization,
        role=role,
    )
    project = _create_project(
        db,
        name=f"{role} project",
        organization=organization,
    )
    dataset = _create_dataset(
        db,
        project=project,
    )
    test_case = _create_test_case(
        db,
        dataset=dataset,
    )

    return (
        user,
        organization,
        project,
        dataset,
        test_case,
    )


def _request(
    db: Session,
    method: str,
    path: str,
    *,
    current_user: models.User | None = None,
    json: dict | None = None,
    data: dict[str, str] | None = None,
    files: dict | None = None,
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
                json=json,
                data=data,
                files=files,
            )

    try:
        return asyncio.run(send_request())
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(
            get_current_user,
            None,
        )


@pytest.mark.parametrize(
    "path",
    [
        "/projects/1/workflow-summary",
        "/projects/1/datasets",
        "/datasets/1",
        "/datasets/1/test-cases",
        "/test-cases/1",
    ],
)
def test_dataset_test_case_read_routes_require_authentication(
    db_session: Session,
    path: str,
) -> None:
    response = _request(
        db_session,
        "GET",
        path,
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Authentication is required."
    }


def test_dataset_creation_requires_authentication(
    db_session: Session,
) -> None:
    response = _request(
        db_session,
        "POST",
        "/projects/1/datasets",
        json={
            "name": "Unauthorized dataset",
            "description": None,
        },
    )

    assert response.status_code == 401


def test_test_case_creation_requires_authentication(
    db_session: Session,
) -> None:
    response = _request(
        db_session,
        "POST",
        "/datasets/1/test-cases",
        data={
            "title": "Unauthorized test case",
        },
        files={
            "audio_file": (
                "sample.wav",
                b"audio",
                "audio/wav",
            ),
            "reference_file": (
                "reference.txt",
                b"reference",
                "text/plain",
            ),
        },
    )

    assert response.status_code == 401


def test_viewer_can_read_dataset_and_test_case_hierarchy(
    db_session: Session,
) -> None:
    (
        user,
        _organization,
        project,
        dataset,
        test_case,
    ) = _create_hierarchy(
        db_session,
        email="viewer-hierarchy@example.com",
        role="viewer",
    )

    responses = [
        _request(
            db_session,
            "GET",
            f"/projects/{project.id}/workflow-summary",
            current_user=user,
        ),
        _request(
            db_session,
            "GET",
            f"/projects/{project.id}/datasets",
            current_user=user,
        ),
        _request(
            db_session,
            "GET",
            f"/datasets/{dataset.id}",
            current_user=user,
        ),
        _request(
            db_session,
            "GET",
            f"/datasets/{dataset.id}/test-cases",
            current_user=user,
        ),
        _request(
            db_session,
            "GET",
            f"/test-cases/{test_case.id}",
            current_user=user,
        ),
    ]

    assert all(
        response.status_code == 200
        for response in responses
    )

    assert responses[0].json()["project_id"] == project.id
    assert responses[1].json()[0]["id"] == dataset.id
    assert responses[2].json()["id"] == dataset.id
    assert responses[3].json()[0]["id"] == test_case.id
    assert responses[4].json()["id"] == test_case.id


def test_billing_admin_cannot_read_dataset_or_test_case_data(
    db_session: Session,
) -> None:
    (
        user,
        _organization,
        project,
        dataset,
        test_case,
    ) = _create_hierarchy(
        db_session,
        email="billing-hierarchy@example.com",
        role="billing_admin",
    )

    paths = [
        f"/projects/{project.id}/workflow-summary",
        f"/projects/{project.id}/datasets",
        f"/datasets/{dataset.id}",
        f"/datasets/{dataset.id}/test-cases",
        f"/test-cases/{test_case.id}",
    ]

    for path in paths:
        response = _request(
            db_session,
            "GET",
            path,
            current_user=user,
        )

        assert response.status_code == 403


def test_other_tenant_hierarchy_is_not_disclosed(
    db_session: Session,
) -> None:
    user = _create_user(
        db_session,
        "tenant-a-hierarchy@example.com",
    )
    own_org = _create_organization(
        db_session,
        "Tenant A",
    )
    _add_membership(
        db_session,
        user=user,
        organization=own_org,
        role="owner",
    )

    other_org = _create_organization(
        db_session,
        "Tenant B",
    )
    other_project = _create_project(
        db_session,
        name="Tenant B project",
        organization=other_org,
    )
    other_dataset = _create_dataset(
        db_session,
        project=other_project,
    )
    other_test_case = _create_test_case(
        db_session,
        dataset=other_dataset,
    )

    paths = [
        f"/projects/{other_project.id}/workflow-summary",
        f"/projects/{other_project.id}/datasets",
        f"/datasets/{other_dataset.id}",
        f"/datasets/{other_dataset.id}/test-cases",
        f"/test-cases/{other_test_case.id}",
    ]

    for path in paths:
        response = _request(
            db_session,
            "GET",
            path,
            current_user=user,
        )

        assert response.status_code == 404


def test_legacy_unowned_hierarchy_fails_closed(
    db_session: Session,
) -> None:
    user = _create_user(
        db_session,
        "legacy-reader@example.com",
    )
    own_org = _create_organization(
        db_session,
        "Owned organization",
    )
    _add_membership(
        db_session,
        user=user,
        organization=own_org,
        role="owner",
    )

    project = _create_project(
        db_session,
        name="Legacy project",
        organization=None,
    )
    dataset = _create_dataset(
        db_session,
        project=project,
    )
    test_case = _create_test_case(
        db_session,
        dataset=dataset,
    )

    paths = [
        f"/projects/{project.id}/workflow-summary",
        f"/projects/{project.id}/datasets",
        f"/datasets/{dataset.id}",
        f"/datasets/{dataset.id}/test-cases",
        f"/test-cases/{test_case.id}",
    ]

    for path in paths:
        response = _request(
            db_session,
            "GET",
            path,
            current_user=user,
        )

        assert response.status_code == 404


def test_missing_hierarchy_ids_fail_closed(
    db_session: Session,
) -> None:
    (
        user,
        _organization,
        _project,
        _dataset,
        _test_case,
    ) = _create_hierarchy(
        db_session,
        email="missing-reader@example.com",
        role="owner",
    )

    paths = [
        "/projects/999999/workflow-summary",
        "/projects/999999/datasets",
        "/datasets/999999",
        "/datasets/999999/test-cases",
        "/test-cases/999999",
    ]

    for path in paths:
        response = _request(
            db_session,
            "GET",
            path,
            current_user=user,
        )

        assert response.status_code == 404


@pytest.mark.parametrize(
    "role",
    [
        "owner",
        "admin",
        "engineer",
    ],
)
def test_write_roles_can_create_dataset(
    db_session: Session,
    role: str,
) -> None:
    (
        user,
        _organization,
        project,
        _dataset,
        _test_case,
    ) = _create_hierarchy(
        db_session,
        email=f"dataset-create-{role}@example.com",
        role=role,
    )

    response = _request(
        db_session,
        "POST",
        f"/projects/{project.id}/datasets",
        current_user=user,
        json={
            "name": "Authorized dataset",
            "description": "Tenant scoped",
        },
    )

    assert response.status_code == 200
    assert response.json()["project_id"] == project.id
    assert response.json()["name"] == "Authorized dataset"


@pytest.mark.parametrize(
    "role",
    [
        "viewer",
        "billing_admin",
    ],
)
def test_non_write_roles_cannot_create_dataset(
    db_session: Session,
    role: str,
) -> None:
    (
        user,
        _organization,
        project,
        _dataset,
        _test_case,
    ) = _create_hierarchy(
        db_session,
        email=f"dataset-denied-{role}@example.com",
        role=role,
    )

    response = _request(
        db_session,
        "POST",
        f"/projects/{project.id}/datasets",
        current_user=user,
        json={
            "name": "Forbidden dataset",
            "description": None,
        },
    )

    assert response.status_code == 403

    assert (
        db_session.query(models.Dataset)
        .filter(
            models.Dataset.name == "Forbidden dataset"
        )
        .count()
        == 0
    )


def test_other_or_missing_project_cannot_create_dataset(
    db_session: Session,
) -> None:
    user = _create_user(
        db_session,
        "dataset-outsider@example.com",
    )
    own_org = _create_organization(
        db_session,
        "Dataset own org",
    )
    other_org = _create_organization(
        db_session,
        "Dataset other org",
    )
    _add_membership(
        db_session,
        user=user,
        organization=own_org,
        role="owner",
    )
    other_project = _create_project(
        db_session,
        name="Other project",
        organization=other_org,
    )

    for project_id in (
        other_project.id,
        999999,
    ):
        response = _request(
            db_session,
            "POST",
            f"/projects/{project_id}/datasets",
            current_user=user,
            json={
                "name": "Hidden dataset",
                "description": None,
            },
        )

        assert response.status_code == 404


@pytest.mark.parametrize(
    "role",
    [
        "owner",
        "admin",
        "engineer",
    ],
)
def test_write_roles_can_create_test_case(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    role: str,
) -> None:
    monkeypatch.chdir(tmp_path)

    (
        user,
        _organization,
        _project,
        dataset,
        _test_case,
    ) = _create_hierarchy(
        db_session,
        email=f"test-case-create-{role}@example.com",
        role=role,
    )

    response = _request(
        db_session,
        "POST",
        f"/datasets/{dataset.id}/test-cases",
        current_user=user,
        data={
            "title": "Authorized upload",
        },
        files={
            "audio_file": (
                "sample.wav",
                b"audio-content",
                "audio/wav",
            ),
            "reference_file": (
                "reference.txt",
                b"hello world",
                "text/plain",
            ),
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["dataset_id"] == dataset.id
    assert payload["title"] == "Authorized upload"
    assert payload["reference_transcript"] == "hello world"

    audio_path = tmp_path / payload["audio_file_path"]
    reference_path = (
        tmp_path / payload["reference_file_path"]
    )

    assert audio_path.read_bytes() == b"audio-content"
    assert reference_path.read_text(
        encoding="utf-8"
    ) == "hello world"


@pytest.mark.parametrize(
    "role",
    [
        "viewer",
        "billing_admin",
    ],
)
def test_non_write_roles_cannot_create_test_case_or_files(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    role: str,
) -> None:
    monkeypatch.chdir(tmp_path)

    (
        user,
        _organization,
        _project,
        dataset,
        _test_case,
    ) = _create_hierarchy(
        db_session,
        email=f"test-case-denied-{role}@example.com",
        role=role,
    )

    response = _request(
        db_session,
        "POST",
        f"/datasets/{dataset.id}/test-cases",
        current_user=user,
        data={
            "title": "Forbidden upload",
        },
        files={
            "audio_file": (
                "sample.wav",
                b"secret-audio",
                "audio/wav",
            ),
            "reference_file": (
                "reference.txt",
                b"secret-reference",
                "text/plain",
            ),
        },
    )

    assert response.status_code == 403
    assert not (tmp_path / "uploads").exists()

    assert (
        db_session.query(models.TestCase)
        .filter(
            models.TestCase.title == "Forbidden upload"
        )
        .count()
        == 0
    )


def test_other_or_missing_dataset_cannot_create_files(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    user = _create_user(
        db_session,
        "test-case-outsider@example.com",
    )
    own_org = _create_organization(
        db_session,
        "Test case own org",
    )
    other_org = _create_organization(
        db_session,
        "Test case other org",
    )

    _add_membership(
        db_session,
        user=user,
        organization=own_org,
        role="owner",
    )

    other_project = _create_project(
        db_session,
        name="Other test case project",
        organization=other_org,
    )
    other_dataset = _create_dataset(
        db_session,
        project=other_project,
    )

    for dataset_id in (
        other_dataset.id,
        999999,
    ):
        response = _request(
            db_session,
            "POST",
            f"/datasets/{dataset_id}/test-cases",
            current_user=user,
            data={
                "title": "Hidden upload",
            },
            files={
                "audio_file": (
                    "sample.wav",
                    b"secret-audio",
                    "audio/wav",
                ),
                "reference_file": (
                    "reference.txt",
                    b"secret-reference",
                    "text/plain",
                ),
            },
        )

        assert response.status_code == 404

    assert not (tmp_path / "uploads").exists()

import asyncio
from collections.abc import Generator
from uuid import uuid4

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
        connection,
        _record,
    ) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)

    session_factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )
    db = session_factory()

    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _create_user(
    db: Session,
    *,
    email: str,
) -> models.User:
    user = models.User(email=email)
    db.add(user)
    db.flush()
    return user


def _create_organization(
    db: Session,
    *,
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
    organization: models.Organization | None,
    name: str,
) -> models.Project:
    project = models.Project(
        organization_id=(
            organization.id
            if organization is not None
            else None
        ),
        name=name,
    )
    db.add(project)
    db.flush()
    return project


def _create_queued_job(
    db: Session,
    *,
    project: models.Project,
) -> models.RunnerJob:
    job = models.RunnerJob(
        public_id=str(uuid4()),
        project_id=project.id,
        name=f"Authorization job {project.id}",
        job_type="asr_evaluation",
        status="queued",
        priority=0,
        required_capabilities=[],
        input_payload={},
        attempt_count=0,
        max_attempts=3,
    )
    db.add(job)
    db.flush()
    return job


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

        def override_get_current_user():
            return current_user

        app.dependency_overrides[
            get_current_user
        ] = override_get_current_user

    async def send():
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
        return asyncio.run(send())
    finally:
        app.dependency_overrides.pop(
            get_db,
            None,
        )
        app.dependency_overrides.pop(
            get_current_user,
            None,
        )


@pytest.mark.parametrize(
    "path",
    [
        "/projects/1/runner-operations",
        "/projects/1/runner-jobs/job-id/logs",
    ],
)
def test_runner_operations_require_human_authentication(
    db_session: Session,
    path: str,
) -> None:
    response = _request(
        db_session,
        "GET",
        path,
    )

    assert response.status_code == 401


@pytest.mark.parametrize(
    "role",
    [
        "owner",
        "admin",
        "engineer",
        "viewer",
    ],
)
def test_product_read_roles_can_view_runner_operations(
    db_session: Session,
    role: str,
) -> None:
    user = _create_user(
        db_session,
        email=f"runner-read-{role}@example.com",
    )
    organization = _create_organization(
        db_session,
        name=f"Runner {role} organization",
    )
    _add_membership(
        db_session,
        user=user,
        organization=organization,
        role=role,
    )
    project = _create_project(
        db_session,
        organization=organization,
        name=f"Runner {role} project",
    )
    job = _create_queued_job(
        db_session,
        project=project,
    )
    db_session.commit()

    snapshot = _request(
        db_session,
        "GET",
        f"/projects/{project.id}/runner-operations",
        current_user=user,
    )
    logs = _request(
        db_session,
        "GET",
        (
            f"/projects/{project.id}/runner-jobs/"
            f"{job.public_id}/logs"
        ),
        current_user=user,
    )

    assert snapshot.status_code == 200
    assert logs.status_code == 200

    assert snapshot.json()["project_id"] == project.id
    assert logs.json()["project_id"] == project.id
    assert logs.json()["job_public_id"] == job.public_id


def test_billing_admin_cannot_view_runner_operations(
    db_session: Session,
) -> None:
    user = _create_user(
        db_session,
        email="runner-billing@example.com",
    )
    organization = _create_organization(
        db_session,
        name="Runner billing organization",
    )
    _add_membership(
        db_session,
        user=user,
        organization=organization,
        role="billing_admin",
    )
    project = _create_project(
        db_session,
        organization=organization,
        name="Runner billing project",
    )
    job = _create_queued_job(
        db_session,
        project=project,
    )
    db_session.commit()

    for path in (
        f"/projects/{project.id}/runner-operations",
        (
            f"/projects/{project.id}/runner-jobs/"
            f"{job.public_id}/logs"
        ),
    ):
        response = _request(
            db_session,
            "GET",
            path,
            current_user=user,
        )

        assert response.status_code == 403


def test_other_tenant_runner_operations_are_hidden(
    db_session: Session,
) -> None:
    user = _create_user(
        db_session,
        email="runner-tenant-a@example.com",
    )
    own_organization = _create_organization(
        db_session,
        name="Runner tenant A",
    )
    _add_membership(
        db_session,
        user=user,
        organization=own_organization,
        role="owner",
    )

    other_organization = _create_organization(
        db_session,
        name="Runner tenant B",
    )
    other_project = _create_project(
        db_session,
        organization=other_organization,
        name="Runner tenant B project",
    )
    other_job = _create_queued_job(
        db_session,
        project=other_project,
    )
    db_session.commit()

    for path in (
        f"/projects/{other_project.id}/runner-operations",
        (
            f"/projects/{other_project.id}/runner-jobs/"
            f"{other_job.public_id}/logs"
        ),
    ):
        response = _request(
            db_session,
            "GET",
            path,
            current_user=user,
        )

        assert response.status_code == 404


def test_legacy_unowned_runner_project_fails_closed(
    db_session: Session,
) -> None:
    user = _create_user(
        db_session,
        email="runner-legacy@example.com",
    )
    own_organization = _create_organization(
        db_session,
        name="Runner owned organization",
    )
    _add_membership(
        db_session,
        user=user,
        organization=own_organization,
        role="owner",
    )

    legacy_project = _create_project(
        db_session,
        organization=None,
        name="Legacy runner project",
    )
    legacy_job = _create_queued_job(
        db_session,
        project=legacy_project,
    )
    db_session.commit()

    for path in (
        f"/projects/{legacy_project.id}/runner-operations",
        (
            f"/projects/{legacy_project.id}/runner-jobs/"
            f"{legacy_job.public_id}/logs"
        ),
    ):
        response = _request(
            db_session,
            "GET",
            path,
            current_user=user,
        )

        assert response.status_code == 404


def test_missing_runner_operations_project_is_hidden(
    db_session: Session,
) -> None:
    user = _create_user(
        db_session,
        email="runner-missing@example.com",
    )
    organization = _create_organization(
        db_session,
        name="Runner missing organization",
    )
    _add_membership(
        db_session,
        user=user,
        organization=organization,
        role="owner",
    )
    db_session.commit()

    for path in (
        "/projects/999999/runner-operations",
        "/projects/999999/runner-jobs/job-id/logs",
    ):
        response = _request(
            db_session,
            "GET",
            path,
            current_user=user,
        )

        assert response.status_code == 404


def test_job_public_id_remains_scoped_to_authorized_project(
    db_session: Session,
) -> None:
    user = _create_user(
        db_session,
        email="runner-job-scope@example.com",
    )
    organization = _create_organization(
        db_session,
        name="Runner job scope organization",
    )
    _add_membership(
        db_session,
        user=user,
        organization=organization,
        role="owner",
    )

    project_a = _create_project(
        db_session,
        organization=organization,
        name="Runner project A",
    )
    project_b = _create_project(
        db_session,
        organization=organization,
        name="Runner project B",
    )

    foreign_job = _create_queued_job(
        db_session,
        project=project_b,
    )
    db_session.commit()

    response = _request(
        db_session,
        "GET",
        (
            f"/projects/{project_a.id}/runner-jobs/"
            f"{foreign_job.public_id}/logs"
        ),
        current_user=user,
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Runner job not found in this project."
    }

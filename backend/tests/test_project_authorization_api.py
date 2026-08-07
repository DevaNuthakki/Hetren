import asyncio
from collections.abc import Generator

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
    ("method", "path", "payload"),
    [
        ("GET", "/projects", None),
        ("GET", "/projects/1", None),
        (
            "POST",
            "/projects",
            {
                "organization_id": 1,
                "name": "Unauthorized project",
                "description": None,
            },
        ),
    ],
)
def test_project_routes_require_authentication(
    db_session: Session,
    method: str,
    path: str,
    payload: dict | None,
) -> None:
    response = _request(
        db_session,
        method,
        path,
        json=payload,
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Authentication is required."
    }


def test_project_list_is_tenant_and_role_scoped(
    db_session: Session,
) -> None:
    user = _create_user(
        db_session,
        "multi-org-api@example.com",
    )

    owner_org = _create_organization(
        db_session,
        "Owner organization",
    )
    viewer_org = _create_organization(
        db_session,
        "Viewer organization",
    )
    billing_org = _create_organization(
        db_session,
        "Billing organization",
    )
    other_org = _create_organization(
        db_session,
        "Other organization",
    )

    _add_membership(
        db_session,
        user=user,
        organization=owner_org,
        role="owner",
    )
    _add_membership(
        db_session,
        user=user,
        organization=viewer_org,
        role="viewer",
    )
    _add_membership(
        db_session,
        user=user,
        organization=billing_org,
        role="billing_admin",
    )

    owner_project = _create_project(
        db_session,
        name="Owner project",
        organization=owner_org,
    )
    viewer_project = _create_project(
        db_session,
        name="Viewer project",
        organization=viewer_org,
    )

    _create_project(
        db_session,
        name="Billing-only project",
        organization=billing_org,
    )
    _create_project(
        db_session,
        name="Other tenant project",
        organization=other_org,
    )
    _create_project(
        db_session,
        name="Legacy project",
        organization=None,
    )

    response = _request(
        db_session,
        "GET",
        "/projects",
        current_user=user,
    )

    assert response.status_code == 200

    payload = response.json()

    assert {
        project["id"]
        for project in payload
    } == {
        owner_project.id,
        viewer_project.id,
    }

    assert {
        project["organization_id"]
        for project in payload
    } == {
        owner_org.id,
        viewer_org.id,
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
def test_product_read_roles_can_get_project(
    db_session: Session,
    role: str,
) -> None:
    user = _create_user(
        db_session,
        f"read-{role}@example.com",
    )
    organization = _create_organization(
        db_session,
        f"Read {role} organization",
    )
    _add_membership(
        db_session,
        user=user,
        organization=organization,
        role=role,
    )
    project = _create_project(
        db_session,
        name="Readable project",
        organization=organization,
    )

    response = _request(
        db_session,
        "GET",
        f"/projects/{project.id}",
        current_user=user,
    )

    assert response.status_code == 200
    assert response.json()["id"] == project.id
    assert (
        response.json()["organization_id"]
        == organization.id
    )


def test_billing_admin_get_project_is_forbidden(
    db_session: Session,
) -> None:
    user = _create_user(
        db_session,
        "billing-read@example.com",
    )
    organization = _create_organization(
        db_session,
        "Billing read organization",
    )
    _add_membership(
        db_session,
        user=user,
        organization=organization,
        role="billing_admin",
    )
    project = _create_project(
        db_session,
        name="Evaluation data",
        organization=organization,
    )

    response = _request(
        db_session,
        "GET",
        f"/projects/{project.id}",
        current_user=user,
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Project permission denied"
    }


def test_inaccessible_projects_are_not_disclosed(
    db_session: Session,
) -> None:
    user = _create_user(
        db_session,
        "tenant-a-api@example.com",
    )
    own_org = _create_organization(
        db_session,
        "Tenant A",
    )
    other_org = _create_organization(
        db_session,
        "Tenant B",
    )

    _add_membership(
        db_session,
        user=user,
        organization=own_org,
        role="owner",
    )

    other_project = _create_project(
        db_session,
        name="Tenant B project",
        organization=other_org,
    )
    legacy_project = _create_project(
        db_session,
        name="Legacy project",
        organization=None,
    )

    for project_id in (
        other_project.id,
        legacy_project.id,
        999999,
    ):
        response = _request(
            db_session,
            "GET",
            f"/projects/{project_id}",
            current_user=user,
        )

        assert response.status_code == 404
        assert response.json() == {
            "detail": "Project not found"
        }


@pytest.mark.parametrize(
    "role",
    [
        "owner",
        "admin",
        "engineer",
    ],
)
def test_product_write_roles_can_create_project(
    db_session: Session,
    role: str,
) -> None:
    user = _create_user(
        db_session,
        f"create-{role}@example.com",
    )
    organization = _create_organization(
        db_session,
        f"Create {role} organization",
    )
    _add_membership(
        db_session,
        user=user,
        organization=organization,
        role=role,
    )

    response = _request(
        db_session,
        "POST",
        "/projects",
        current_user=user,
        json={
            "organization_id": organization.id,
            "name": "Authorized project",
            "description": "Tenant-owned project",
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["organization_id"] == organization.id
    assert payload["name"] == "Authorized project"

    project = db_session.get(
        models.Project,
        payload["id"],
    )

    assert project is not None
    assert project.organization_id == organization.id


@pytest.mark.parametrize(
    "role",
    [
        "viewer",
        "billing_admin",
    ],
)
def test_non_write_roles_cannot_create_project(
    db_session: Session,
    role: str,
) -> None:
    user = _create_user(
        db_session,
        f"create-denied-{role}@example.com",
    )
    organization = _create_organization(
        db_session,
        f"Denied {role} organization",
    )
    _add_membership(
        db_session,
        user=user,
        organization=organization,
        role=role,
    )

    response = _request(
        db_session,
        "POST",
        "/projects",
        current_user=user,
        json={
            "organization_id": organization.id,
            "name": "Forbidden project",
            "description": None,
        },
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Organization permission denied"
    }

    assert (
        db_session.query(models.Project)
        .filter(
            models.Project.name == "Forbidden project"
        )
        .count()
        == 0
    )


def test_other_or_missing_organization_is_not_disclosed_on_create(
    db_session: Session,
) -> None:
    user = _create_user(
        db_session,
        "create-outsider@example.com",
    )
    own_org = _create_organization(
        db_session,
        "Own organization",
    )
    other_org = _create_organization(
        db_session,
        "Other organization",
    )

    _add_membership(
        db_session,
        user=user,
        organization=own_org,
        role="owner",
    )

    for organization_id in (
        other_org.id,
        999999,
    ):
        response = _request(
            db_session,
            "POST",
            "/projects",
            current_user=user,
            json={
                "organization_id": organization_id,
                "name": "Unauthorized tenant project",
                "description": None,
            },
        )

        assert response.status_code == 404
        assert response.json() == {
            "detail": "Organization not found"
        }

    assert (
        db_session.query(models.Project)
        .filter(
            models.Project.name
            == "Unauthorized tenant project"
        )
        .count()
        == 0
    )

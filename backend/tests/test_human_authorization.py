from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.auth.authorization import (
    PRODUCT_READ_ROLES,
    PRODUCT_WRITE_ROLES,
    OrganizationNotAccessibleError,
    OrganizationPermissionDeniedError,
    ProjectNotAccessibleError,
    ProjectPermissionDeniedError,
    authorize_organization,
    authorize_project,
    list_accessible_projects,
)
from app.database import Base


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
) -> models.OrganizationMembership:
    membership = models.OrganizationMembership(
        user_id=user.id,
        organization_id=organization.id,
        role=role,
    )
    db.add(membership)
    db.flush()
    return membership


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


@pytest.mark.parametrize(
    "role",
    sorted(PRODUCT_READ_ROLES),
)
def test_product_read_roles_can_access_project(
    db_session: Session,
    role: str,
) -> None:
    user = _create_user(
        db_session,
        f"{role}@example.com",
    )
    organization = _create_organization(
        db_session,
        f"{role} organization",
    )
    membership = _add_membership(
        db_session,
        user=user,
        organization=organization,
        role=role,
    )
    project = _create_project(
        db_session,
        name=f"{role} project",
        organization=organization,
    )

    access = authorize_project(
        db_session,
        user_id=user.id,
        project_id=project.id,
        required_roles=PRODUCT_READ_ROLES,
    )

    assert access.project is project
    assert access.membership is membership
    assert access.membership.role == role


def test_billing_admin_cannot_read_product_project(
    db_session: Session,
) -> None:
    user = _create_user(
        db_session,
        "billing@example.com",
    )
    organization = _create_organization(
        db_session,
        "Billing organization",
    )
    _add_membership(
        db_session,
        user=user,
        organization=organization,
        role="billing_admin",
    )
    project = _create_project(
        db_session,
        name="Protected evaluation project",
        organization=organization,
    )

    with pytest.raises(ProjectPermissionDeniedError):
        authorize_project(
            db_session,
            user_id=user.id,
            project_id=project.id,
            required_roles=PRODUCT_READ_ROLES,
        )


@pytest.mark.parametrize(
    "role",
    sorted(PRODUCT_WRITE_ROLES),
)
def test_product_write_roles_can_mutate_project(
    db_session: Session,
    role: str,
) -> None:
    user = _create_user(
        db_session,
        f"write-{role}@example.com",
    )
    organization = _create_organization(
        db_session,
        f"Write {role} organization",
    )
    _add_membership(
        db_session,
        user=user,
        organization=organization,
        role=role,
    )
    project = _create_project(
        db_session,
        name=f"Writable {role} project",
        organization=organization,
    )

    access = authorize_project(
        db_session,
        user_id=user.id,
        project_id=project.id,
        required_roles=PRODUCT_WRITE_ROLES,
    )

    assert access.project.id == project.id
    assert access.membership.role == role


@pytest.mark.parametrize(
    "role",
    [
        "viewer",
        "billing_admin",
    ],
)
def test_non_write_roles_cannot_mutate_project(
    db_session: Session,
    role: str,
) -> None:
    user = _create_user(
        db_session,
        f"readonly-{role}@example.com",
    )
    organization = _create_organization(
        db_session,
        f"Readonly {role} organization",
    )
    _add_membership(
        db_session,
        user=user,
        organization=organization,
        role=role,
    )
    project = _create_project(
        db_session,
        name="Readonly project",
        organization=organization,
    )

    with pytest.raises(ProjectPermissionDeniedError):
        authorize_project(
            db_session,
            user_id=user.id,
            project_id=project.id,
            required_roles=PRODUCT_WRITE_ROLES,
        )


def test_other_tenant_project_is_not_disclosed(
    db_session: Session,
) -> None:
    user = _create_user(
        db_session,
        "tenant-a@example.com",
    )
    own_organization = _create_organization(
        db_session,
        "Tenant A",
    )
    other_organization = _create_organization(
        db_session,
        "Tenant B",
    )

    _add_membership(
        db_session,
        user=user,
        organization=own_organization,
        role="owner",
    )

    other_project = _create_project(
        db_session,
        name="Tenant B project",
        organization=other_organization,
    )

    with pytest.raises(ProjectNotAccessibleError):
        authorize_project(
            db_session,
            user_id=user.id,
            project_id=other_project.id,
            required_roles=PRODUCT_READ_ROLES,
        )


def test_missing_project_and_other_tenant_use_same_error(
    db_session: Session,
) -> None:
    user = _create_user(
        db_session,
        "lookup@example.com",
    )
    own_organization = _create_organization(
        db_session,
        "Lookup organization",
    )
    other_organization = _create_organization(
        db_session,
        "Hidden organization",
    )

    _add_membership(
        db_session,
        user=user,
        organization=own_organization,
        role="owner",
    )

    hidden_project = _create_project(
        db_session,
        name="Hidden project",
        organization=other_organization,
    )

    with pytest.raises(ProjectNotAccessibleError):
        authorize_project(
            db_session,
            user_id=user.id,
            project_id=hidden_project.id,
            required_roles=PRODUCT_READ_ROLES,
        )

    with pytest.raises(ProjectNotAccessibleError):
        authorize_project(
            db_session,
            user_id=user.id,
            project_id=999999,
            required_roles=PRODUCT_READ_ROLES,
        )


def test_legacy_project_without_organization_fails_closed(
    db_session: Session,
) -> None:
    user = _create_user(
        db_session,
        "legacy@example.com",
    )
    organization = _create_organization(
        db_session,
        "Owned organization",
    )

    _add_membership(
        db_session,
        user=user,
        organization=organization,
        role="owner",
    )

    legacy_project = _create_project(
        db_session,
        name="Legacy project",
        organization=None,
    )

    with pytest.raises(ProjectNotAccessibleError):
        authorize_project(
            db_session,
            user_id=user.id,
            project_id=legacy_project.id,
            required_roles=PRODUCT_READ_ROLES,
        )


def test_list_accessible_projects_is_tenant_and_role_scoped(
    db_session: Session,
) -> None:
    user = _create_user(
        db_session,
        "multi-org@example.com",
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
        name="Billing project",
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

    projects = list_accessible_projects(
        db_session,
        user_id=user.id,
    )

    assert {
        project.id
        for project in projects
    } == {
        owner_project.id,
        viewer_project.id,
    }


def test_organization_write_authorization_uses_membership_role(
    db_session: Session,
) -> None:
    owner = _create_user(
        db_session,
        "org-owner@example.com",
    )
    viewer = _create_user(
        db_session,
        "org-viewer@example.com",
    )
    outsider = _create_user(
        db_session,
        "org-outsider@example.com",
    )
    organization = _create_organization(
        db_session,
        "Project creation organization",
    )

    _add_membership(
        db_session,
        user=owner,
        organization=organization,
        role="owner",
    )
    _add_membership(
        db_session,
        user=viewer,
        organization=organization,
        role="viewer",
    )

    owner_access = authorize_organization(
        db_session,
        user_id=owner.id,
        organization_id=organization.id,
        required_roles=PRODUCT_WRITE_ROLES,
    )

    assert owner_access.organization is organization
    assert owner_access.membership.role == "owner"

    with pytest.raises(
        OrganizationPermissionDeniedError
    ):
        authorize_organization(
            db_session,
            user_id=viewer.id,
            organization_id=organization.id,
            required_roles=PRODUCT_WRITE_ROLES,
        )

    with pytest.raises(
        OrganizationNotAccessibleError
    ):
        authorize_organization(
            db_session,
            user_id=outsider.id,
            organization_id=organization.id,
            required_roles=PRODUCT_WRITE_ROLES,
        )


@pytest.mark.parametrize(
    "required_roles",
    [
        set(),
        {"owner", "super_admin"},
    ],
)
def test_authorization_rejects_invalid_role_configuration(
    db_session: Session,
    required_roles: set[str],
) -> None:
    user = _create_user(
        db_session,
        "configuration@example.com",
    )
    organization = _create_organization(
        db_session,
        "Configuration organization",
    )
    _add_membership(
        db_session,
        user=user,
        organization=organization,
        role="owner",
    )
    project = _create_project(
        db_session,
        name="Configuration project",
        organization=organization,
    )

    with pytest.raises(ValueError):
        authorize_project(
            db_session,
            user_id=user.id,
            project_id=project.id,
            required_roles=required_roles,
        )

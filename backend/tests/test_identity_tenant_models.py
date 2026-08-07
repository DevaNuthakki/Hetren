from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import (
    Organization,
    OrganizationMembership,
    Project,
    User,
)


ALLOWED_ROLES = (
    "owner",
    "admin",
    "engineer",
    "viewer",
    "billing_admin",
)


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


def test_identity_tenant_relationships(
    db_session: Session,
) -> None:
    organization = Organization(name="Hetren Test Organization")
    user = User(
        email="owner@example.com",
        display_name="Test Owner",
    )
    membership = OrganizationMembership(
        organization=organization,
        user=user,
        role="owner",
    )
    owned_project = Project(
        name="Owned Project",
        organization=organization,
    )
    legacy_project = Project(name="Legacy Project")

    db_session.add_all(
        [
            organization,
            user,
            membership,
            owned_project,
            legacy_project,
        ]
    )
    db_session.commit()

    assert owned_project.organization_id == organization.id
    assert owned_project.organization is organization
    assert legacy_project.organization_id is None
    assert membership in organization.memberships
    assert membership in user.memberships
    assert owned_project in organization.projects


@pytest.mark.parametrize("role", ALLOWED_ROLES)
def test_supported_membership_roles_are_accepted(
    db_session: Session,
    role: str,
) -> None:
    organization = Organization(name=f"{role} organization")
    user = User(email=f"{role}@example.com")
    membership = OrganizationMembership(
        organization=organization,
        user=user,
        role=role,
    )

    db_session.add_all([organization, user, membership])
    db_session.commit()

    assert membership.id is not None
    assert membership.role == role


def test_invalid_membership_role_is_rejected(
    db_session: Session,
) -> None:
    organization = Organization(name="Invalid Role Organization")
    user = User(email="invalid-role@example.com")
    membership = OrganizationMembership(
        organization=organization,
        user=user,
        role="super_admin",
    )

    db_session.add_all([organization, user, membership])

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_duplicate_organization_membership_is_rejected(
    db_session: Session,
) -> None:
    organization = Organization(name="Duplicate Membership Organization")
    user = User(email="member@example.com")

    db_session.add_all([organization, user])
    db_session.flush()

    db_session.add(
        OrganizationMembership(
            organization_id=organization.id,
            user_id=user.id,
            role="engineer",
        )
    )
    db_session.commit()

    db_session.add(
        OrganizationMembership(
            organization_id=organization.id,
            user_id=user.id,
            role="viewer",
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


@pytest.mark.parametrize(
    "email",
    (
        "Owner@example.com",
        " owner@example.com ",
    ),
)
def test_non_normalized_email_is_rejected(
    db_session: Session,
    email: str,
) -> None:
    db_session.add(User(email=email))

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_duplicate_user_email_is_rejected(
    db_session: Session,
) -> None:
    db_session.add(User(email="duplicate@example.com"))
    db_session.commit()

    db_session.add(User(email="duplicate@example.com"))

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_organization_with_projects_cannot_be_deleted(
    db_session: Session,
) -> None:
    organization = Organization(name="Protected Organization")
    project = Project(
        name="Protected Project",
        organization=organization,
    )

    db_session.add_all([organization, project])
    db_session.commit()

    db_session.delete(organization)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()

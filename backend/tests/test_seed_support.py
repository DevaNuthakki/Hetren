from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from scripts.seed_support import (
    resolve_seed_organization_id,
)


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_preserves_existing_demo_organization(
    db: Session,
):
    first = models.Organization(name="First")
    second = models.Organization(name="Second")
    db.add_all([first, second])
    db.flush()

    db.add(
        models.Project(
            organization_id=second.id,
            name="Hetren Demo",
        )
    )
    db.flush()

    assert resolve_seed_organization_id(
        db,
        project_names=["Hetren Demo"],
    ) == second.id


def test_uses_single_organization_fallback(
    db: Session,
):
    organization = models.Organization(
        name="Only organization",
    )
    db.add(organization)
    db.flush()

    assert resolve_seed_organization_id(
        db,
        project_names=["Missing demo"],
    ) == organization.id


def test_rejects_missing_organization(
    db: Session,
):
    with pytest.raises(
        RuntimeError,
        match="No organization exists",
    ):
        resolve_seed_organization_id(
            db,
            project_names=["Hetren Demo"],
        )


def test_rejects_ambiguous_fallback(
    db: Session,
):
    db.add_all(
        [
            models.Organization(name="First"),
            models.Organization(name="Second"),
        ]
    )
    db.flush()

    with pytest.raises(
        RuntimeError,
        match="Multiple organizations exist",
    ):
        resolve_seed_organization_id(
            db,
            project_names=["Hetren Demo"],
        )


def test_rejects_conflicting_existing_ownership(
    db: Session,
):
    first = models.Organization(name="First")
    second = models.Organization(name="Second")
    db.add_all([first, second])
    db.flush()

    db.add_all(
        [
            models.Project(
                organization_id=first.id,
                name="Demo A",
            ),
            models.Project(
                organization_id=second.id,
                name="Demo B",
            ),
        ]
    )
    db.flush()

    with pytest.raises(
        RuntimeError,
        match="multiple organizations",
    ):
        resolve_seed_organization_id(
            db,
            project_names=[
                "Demo A",
                "Demo B",
            ],
        )

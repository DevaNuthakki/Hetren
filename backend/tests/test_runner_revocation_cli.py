from io import StringIO

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from app.runner_service import (
    issue_registration_token,
    register_runner,
)
from scripts.revoke_runner import run_cli


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(
        database_connection,
        _connection_record,
    ):
        cursor = database_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)

    factory = sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )

    try:
        yield factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def create_registered_runner(session_factory):
    with session_factory() as db:
        project = models.Project(
            name="Runner revocation CLI project",
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        issued = issue_registration_token(
            db,
            project_id=project.id,
        )
        registered = register_runner(
            db,
            registration_token=issued.token,
            name="CLI revocation runner",
        )

        return registered.runner.public_id


def test_cli_revokes_runner(
    session_factory,
):
    public_id = create_registered_runner(session_factory)
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_cli(
        [
            "--runner-public-id",
            public_id,
        ],
        session_factory=session_factory,
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert stderr.getvalue() == ""
    assert "Runner revoked successfully." in stdout.getvalue()
    assert public_id in stdout.getvalue()

    with session_factory() as db:
        runner = (
            db.query(models.Runner)
            .filter(models.Runner.public_id == public_id)
            .one()
        )

        assert runner.status == "revoked"
        assert runner.revoked_at is not None


def test_cli_rejects_unknown_runner(
    session_factory,
):
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_cli(
        [
            "--runner-public-id",
            "00000000-0000-0000-0000-000000000000",
        ],
        session_factory=session_factory,
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 2
    assert stdout.getvalue() == ""
    assert "was not found" in stderr.getvalue()

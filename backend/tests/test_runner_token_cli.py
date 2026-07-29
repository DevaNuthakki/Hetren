from io import StringIO

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from app.runner_security import (
    REGISTRATION_TOKEN_PREFIX,
    hash_registration_token,
)
from scripts.issue_runner_registration_token import run_cli


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


def create_project(session_factory) -> models.Project:
    with session_factory() as db:
        project = models.Project(
            name="Runner CLI project",
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return project


def extract_registration_token(output: str) -> str:
    prefix = "Registration token: "

    token_line = next(
        line
        for line in output.splitlines()
        if line.startswith(prefix)
    )

    return token_line.removeprefix(prefix)


def test_cli_issues_token_and_stores_only_hash(
    session_factory,
):
    project = create_project(session_factory)
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_cli(
        [
            "--project-id",
            str(project.id),
            "--label",
            "Local developer runner",
            "--ttl-minutes",
            "15",
        ],
        session_factory=session_factory,
        stdout=stdout,
        stderr=stderr,
    )

    output = stdout.getvalue()
    plaintext_token = extract_registration_token(output)

    assert exit_code == 0
    assert stderr.getvalue() == ""
    assert plaintext_token.startswith(
        REGISTRATION_TOKEN_PREFIX
    )
    assert output.count(plaintext_token) == 1

    with session_factory() as db:
        token_record = (
            db.query(models.RunnerRegistrationToken)
            .one()
        )

        assert token_record.project_id == project.id
        assert token_record.label == "Local developer runner"
        assert token_record.token_hash == (
            hash_registration_token(plaintext_token)
        )
        assert token_record.token_hash != plaintext_token


def test_cli_rejects_missing_project(
    session_factory,
):
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_cli(
        [
            "--project-id",
            "2147483647",
        ],
        session_factory=session_factory,
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 2
    assert stdout.getvalue() == ""
    assert "was not found" in stderr.getvalue()

    with session_factory() as db:
        assert (
            db.query(models.RunnerRegistrationToken).count()
            == 0
        )


def test_cli_uses_default_label_and_ttl(
    session_factory,
):
    project = create_project(session_factory)
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_cli(
        [
            "--project-id",
            str(project.id),
        ],
        session_factory=session_factory,
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert stderr.getvalue() == ""

    with session_factory() as db:
        token_record = (
            db.query(models.RunnerRegistrationToken)
            .one()
        )

        assert token_record.label == (
            "Runner registration token"
        )

        lifetime = (
            token_record.expires_at
            - token_record.created_at
        )

        assert lifetime.total_seconds() == pytest.approx(
            30 * 60,
            abs=1,
        )

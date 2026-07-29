from io import StringIO

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from app.runner_job_service import (
    RunnerJobCancellationUnavailableError,
    enqueue_job,
)
from scripts import cancel_runner_job as cancel_cli


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


def create_queued_job(session_factory) -> str:
    with session_factory() as db:
        project = models.Project(
            name="Runner job cancellation CLI project",
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        job = enqueue_job(
            db,
            project_id=project.id,
            name="CLI cancellation job",
            job_type="asr_evaluation",
        )

        return job.public_id


def test_cli_cancels_runner_job(
    session_factory,
):
    public_id = create_queued_job(session_factory)
    stdout = StringIO()
    stderr = StringIO()

    exit_code = cancel_cli.run_cli(
        [
            "--job-public-id",
            public_id,
        ],
        session_factory=session_factory,
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert stderr.getvalue() == ""
    assert "Runner job cancelled successfully." in (
        stdout.getvalue()
    )
    assert public_id in stdout.getvalue()

    with session_factory() as db:
        job = (
            db.query(models.RunnerJob)
            .filter(models.RunnerJob.public_id == public_id)
            .one()
        )

        assert job.status == "cancelled"
        assert job.cancelled_at is not None
        assert job.claim_token_hash is None
        assert job.lease_expires_at is None


def test_cli_rejects_unknown_runner_job(
    session_factory,
):
    stdout = StringIO()
    stderr = StringIO()

    exit_code = cancel_cli.run_cli(
        [
            "--job-public-id",
            "00000000-0000-0000-0000-000000000000",
        ],
        session_factory=session_factory,
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 2
    assert stdout.getvalue() == ""
    assert "was not found" in stderr.getvalue()


def test_cli_maps_unavailable_cancellation_to_exit_two(
    session_factory,
    monkeypatch,
):
    def reject_cancellation(_db, **_kwargs):
        raise RunnerJobCancellationUnavailableError(
            "Specific internal lifecycle state."
        )

    monkeypatch.setattr(
        cancel_cli,
        "cancel_job",
        reject_cancellation,
    )

    stdout = StringIO()
    stderr = StringIO()

    exit_code = cancel_cli.run_cli(
        [
            "--job-public-id",
            "00000000-0000-0000-0000-000000000001",
        ],
        session_factory=session_factory,
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 2
    assert stdout.getvalue() == ""
    assert "current state" not in stderr.getvalue()
    assert "Specific internal lifecycle state." in (
        stderr.getvalue()
    )

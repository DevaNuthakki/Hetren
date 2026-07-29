import argparse
from datetime import UTC, datetime, timedelta
from io import StringIO
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from app.runner_job_service import (
    MAX_EXPIRED_JOB_RECOVERY_BATCH,
    RunnerJobTransitionUnavailableError,
)
from app.runner_security import hash_job_claim_token
from app.runner_service import (
    issue_registration_token,
    register_runner,
)
from scripts import recover_expired_runner_jobs as recovery_cli


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


def create_expired_jobs(session_factory):
    with session_factory() as db:
        project = models.Project(
            name="Runner recovery CLI project",
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
            name="Recovery CLI runner",
            capabilities=["asr"],
        )

        now = datetime.now(UTC)
        claimed_at = now - timedelta(minutes=5)
        lease_expires_at = now - timedelta(minutes=1)

        retryable_job = models.RunnerJob(
            public_id=str(uuid4()),
            project_id=project.id,
            assigned_runner_id=registered.runner.id,
            name="Retryable expired CLI job",
            job_type="asr_evaluation",
            status="claimed",
            required_capabilities=["asr"],
            input_payload={"source": "cli-test"},
            attempt_count=1,
            max_attempts=3,
            claimed_at=claimed_at,
            lease_expires_at=lease_expires_at,
            claim_token_hash=hash_job_claim_token(
                "retryable-cli-claim"
            ),
        )

        exhausted_job = models.RunnerJob(
            public_id=str(uuid4()),
            project_id=project.id,
            assigned_runner_id=registered.runner.id,
            name="Exhausted expired CLI job",
            job_type="asr_evaluation",
            status="running",
            required_capabilities=["asr"],
            input_payload={"source": "cli-test"},
            attempt_count=3,
            max_attempts=3,
            claimed_at=claimed_at,
            lease_expires_at=lease_expires_at,
            claim_token_hash=hash_job_claim_token(
                "exhausted-cli-claim"
            ),
            started_at=claimed_at + timedelta(seconds=10),
        )

        db.add_all([retryable_job, exhausted_job])
        db.commit()

        return retryable_job.public_id, exhausted_job.public_id


def test_cli_recovers_expired_runner_jobs(
    session_factory,
):
    retryable_id, exhausted_id = create_expired_jobs(
        session_factory
    )
    stdout = StringIO()
    stderr = StringIO()

    exit_code = recovery_cli.run_cli(
        ["--limit", "10"],
        session_factory=session_factory,
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert stderr.getvalue() == ""

    output = stdout.getvalue()
    assert "Recovered jobs: 2" in output
    assert "Requeued jobs: 1" in output
    assert "Failed jobs: 1" in output

    with session_factory() as db:
        retryable = (
            db.query(models.RunnerJob)
            .filter(
                models.RunnerJob.public_id == retryable_id
            )
            .one()
        )
        exhausted = (
            db.query(models.RunnerJob)
            .filter(
                models.RunnerJob.public_id == exhausted_id
            )
            .one()
        )

        assert retryable.status == "queued"
        assert retryable.assigned_runner_id is None
        assert retryable.claim_token_hash is None

        assert exhausted.status == "failed"
        assert exhausted.failed_at is not None
        assert exhausted.claim_token_hash is None


def test_cli_reports_zero_when_no_jobs_are_expired(
    session_factory,
):
    stdout = StringIO()
    stderr = StringIO()

    exit_code = recovery_cli.run_cli(
        [],
        session_factory=session_factory,
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert stderr.getvalue() == ""
    assert "Recovered jobs: 0" in stdout.getvalue()
    assert "Requeued jobs: 0" in stdout.getvalue()
    assert "Failed jobs: 0" in stdout.getvalue()


@pytest.mark.parametrize(
    "value",
    [
        "0",
        "-1",
        str(MAX_EXPIRED_JOB_RECOVERY_BATCH + 1),
    ],
)
def test_recovery_limit_rejects_invalid_values(
    value: str,
):
    with pytest.raises(argparse.ArgumentTypeError):
        recovery_cli.recovery_limit(value)


def test_cli_maps_recovery_failure_to_exit_one(
    session_factory,
    monkeypatch,
):
    def reject_recovery(_db, **_kwargs):
        raise RunnerJobTransitionUnavailableError(
            "Internal recovery state."
        )

    monkeypatch.setattr(
        recovery_cli,
        "recover_expired_jobs",
        reject_recovery,
    )

    stdout = StringIO()
    stderr = StringIO()

    exit_code = recovery_cli.run_cli(
        [],
        session_factory=session_factory,
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 1
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == (
        "ERROR: Expired runner jobs could not be recovered.\n"
    )
    assert "internal recovery state" not in stderr.getvalue()

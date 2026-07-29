from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from app.runner_job_service import (
    DEFAULT_JOB_LEASE_DURATION,
    MAX_JOB_LEASE_DURATION,
    RunnerJobClaimUnavailableError,
    claim_next_job,
    verify_job_claim_ownership,
)
from app.runner_security import (
    JOB_CLAIM_TOKEN_PREFIX,
    hash_job_claim_token,
)
from app.runner_service import (
    RunnerAuthenticationError,
    issue_registration_token,
    register_runner,
)


@pytest.fixture
def db() -> Session:
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
    session = Session(bind=engine)

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def create_project(
    db: Session,
    name: str,
) -> models.Project:
    project = models.Project(name=name)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def create_registered_runner(
    db: Session,
    *,
    project: models.Project,
    name: str,
    capabilities: list[str],
):
    issued = issue_registration_token(
        db,
        project_id=project.id,
        label=f"{name} registration",
    )

    return register_runner(
        db,
        registration_token=issued.token,
        name=name,
        runner_version="0.1.0-test",
        capabilities=capabilities,
        system_info={"platform": "pytest"},
    )


def create_job(
    db: Session,
    *,
    project: models.Project,
    name: str,
    required_capabilities: list[str] | None = None,
    priority: int = 0,
    available_at: datetime | None = None,
    attempt_count: int = 0,
    max_attempts: int = 3,
) -> models.RunnerJob:
    job = models.RunnerJob(
        public_id=str(uuid4()),
        project_id=project.id,
        name=name,
        job_type="asr_evaluation",
        priority=priority,
        required_capabilities=required_capabilities or [],
        input_payload={"source": "pytest"},
        available_at=available_at or datetime.now(UTC),
        attempt_count=attempt_count,
        max_attempts=max_attempts,
    )

    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def test_claim_next_job_assigns_job_and_returns_claim_token(
    db: Session,
):
    project = create_project(db, "Claim job project")
    registered = create_registered_runner(
        db,
        project=project,
        name="Claim runner",
        capabilities=["asr", "cpu"],
    )

    claim_time = datetime(
        2026,
        7,
        29,
        14,
        0,
        tzinfo=UTC,
    )

    job = create_job(
        db,
        project=project,
        name="Compatible ASR job",
        required_capabilities=["asr"],
        available_at=claim_time - timedelta(minutes=1),
    )

    claimed = claim_next_job(
        db,
        credential=registered.credential,
        now=claim_time,
    )

    assert claimed is not None
    assert claimed.job.id == job.id
    assert claimed.claim_token.startswith(
        JOB_CLAIM_TOKEN_PREFIX
    )

    assert claimed.job.status == "claimed"
    assert claimed.job.assigned_runner_id == registered.runner.id
    assert claimed.job.attempt_count == 1

    assert claimed.job.claim_token_hash == hash_job_claim_token(
        claimed.claim_token
    )
    assert claimed.job.claim_token_hash != claimed.claim_token

    assert claimed.job.claimed_at is not None
    assert claimed.job.claimed_at.replace(tzinfo=UTC) == claim_time

    assert claimed.job.lease_expires_at is not None
    assert claimed.job.lease_expires_at.replace(
        tzinfo=UTC
    ) == claim_time + DEFAULT_JOB_LEASE_DURATION


def test_claim_next_job_selects_highest_priority_compatible_job(
    db: Session,
):
    project = create_project(db, "Priority project")
    registered = create_registered_runner(
        db,
        project=project,
        name="Priority runner",
        capabilities=["asr", "cpu"],
    )

    claim_time = datetime(
        2026,
        7,
        29,
        14,
        30,
        tzinfo=UTC,
    )

    incompatible = create_job(
        db,
        project=project,
        name="GPU job",
        required_capabilities=["gpu"],
        priority=100,
        available_at=claim_time - timedelta(minutes=5),
    )
    lower_priority = create_job(
        db,
        project=project,
        name="Lower priority ASR job",
        required_capabilities=["asr"],
        priority=10,
        available_at=claim_time - timedelta(minutes=10),
    )
    selected = create_job(
        db,
        project=project,
        name="Highest compatible ASR job",
        required_capabilities=["asr", "cpu"],
        priority=20,
        available_at=claim_time - timedelta(minutes=1),
    )

    claimed = claim_next_job(
        db,
        credential=registered.credential,
        now=claim_time,
    )

    assert claimed is not None
    assert claimed.job.id == selected.id

    db.refresh(incompatible)
    db.refresh(lower_priority)

    assert incompatible.status == "queued"
    assert lower_priority.status == "queued"


def test_claim_next_job_is_project_scoped(
    db: Session,
):
    runner_project = create_project(
        db,
        "Runner-owned project",
    )
    other_project = create_project(
        db,
        "Other project",
    )

    registered = create_registered_runner(
        db,
        project=runner_project,
        name="Project-scoped runner",
        capabilities=["asr"],
    )

    other_job = create_job(
        db,
        project=other_project,
        name="Other project job",
        required_capabilities=["asr"],
    )

    claimed = claim_next_job(
        db,
        credential=registered.credential,
    )

    assert claimed is None

    db.refresh(other_job)
    assert other_job.status == "queued"
    assert other_job.assigned_runner_id is None


def test_claim_next_job_ignores_unavailable_jobs(
    db: Session,
):
    project = create_project(db, "Unavailable jobs project")
    registered = create_registered_runner(
        db,
        project=project,
        name="Unavailable jobs runner",
        capabilities=["asr"],
    )

    claim_time = datetime(
        2026,
        7,
        29,
        15,
        0,
        tzinfo=UTC,
    )

    create_job(
        db,
        project=project,
        name="Future job",
        required_capabilities=["asr"],
        available_at=claim_time + timedelta(minutes=1),
    )
    create_job(
        db,
        project=project,
        name="Exhausted job",
        required_capabilities=["asr"],
        available_at=claim_time - timedelta(minutes=1),
        attempt_count=3,
        max_attempts=3,
    )
    create_job(
        db,
        project=project,
        name="Unsupported job",
        required_capabilities=["gpu"],
        available_at=claim_time - timedelta(minutes=1),
    )

    claimed = claim_next_job(
        db,
        credential=registered.credential,
        now=claim_time,
    )

    assert claimed is None


@pytest.mark.parametrize(
    "lease_duration",
    [
        timedelta(0),
        timedelta(seconds=-1),
        MAX_JOB_LEASE_DURATION + timedelta(seconds=1),
    ],
)
def test_claim_next_job_rejects_invalid_lease_duration(
    db: Session,
    lease_duration: timedelta,
):
    project = create_project(db, "Invalid lease project")
    registered = create_registered_runner(
        db,
        project=project,
        name=f"Lease runner {lease_duration}",
        capabilities=["asr"],
    )

    with pytest.raises(ValueError):
        claim_next_job(
            db,
            credential=registered.credential,
            lease_duration=lease_duration,
        )


def test_claim_next_job_rejects_invalid_runner_credential(
    db: Session,
):
    with pytest.raises(
        RunnerAuthenticationError,
        match="invalid or unavailable",
    ):
        claim_next_job(
            db,
            credential="ovrin_runner_invalid",
        )


def test_claim_next_job_rejects_revoked_runner(
    db: Session,
):
    project = create_project(db, "Revoked runner project")
    registered = create_registered_runner(
        db,
        project=project,
        name="Revoked claiming runner",
        capabilities=["asr"],
    )

    registered.runner.status = "revoked"
    registered.runner.revoked_at = datetime.now(UTC)
    db.commit()

    with pytest.raises(RunnerAuthenticationError):
        claim_next_job(
            db,
            credential=registered.credential,
        )


def test_verify_job_claim_ownership_accepts_valid_claim(
    db: Session,
):
    project = create_project(db, "Verify claim project")
    registered = create_registered_runner(
        db,
        project=project,
        name="Claim owner",
        capabilities=["asr"],
    )

    claim_time = datetime(
        2026,
        7,
        29,
        16,
        0,
        tzinfo=UTC,
    )

    create_job(
        db,
        project=project,
        name="Ownership job",
        required_capabilities=["asr"],
        available_at=claim_time,
    )

    claimed = claim_next_job(
        db,
        credential=registered.credential,
        now=claim_time,
    )

    assert claimed is not None

    verified = verify_job_claim_ownership(
        db,
        credential=registered.credential,
        job_public_id=claimed.job.public_id,
        claim_token=claimed.claim_token,
        now=claim_time + timedelta(minutes=1),
    )

    assert verified.id == claimed.job.id
    assert verified.assigned_runner_id == registered.runner.id


def test_verify_job_claim_ownership_accepts_running_job(
    db: Session,
):
    project = create_project(db, "Running claim project")
    registered = create_registered_runner(
        db,
        project=project,
        name="Running claim owner",
        capabilities=["asr"],
    )

    claim_time = datetime(
        2026,
        7,
        29,
        16,
        30,
        tzinfo=UTC,
    )

    create_job(
        db,
        project=project,
        name="Running ownership job",
        required_capabilities=["asr"],
        available_at=claim_time,
    )

    claimed = claim_next_job(
        db,
        credential=registered.credential,
        now=claim_time,
    )

    assert claimed is not None

    claimed.job.status = "running"
    claimed.job.started_at = claim_time + timedelta(seconds=10)
    db.commit()

    verified = verify_job_claim_ownership(
        db,
        credential=registered.credential,
        job_public_id=claimed.job.public_id,
        claim_token=claimed.claim_token,
        now=claim_time + timedelta(minutes=1),
    )

    assert verified.status == "running"


def test_verify_job_claim_ownership_rejects_wrong_token(
    db: Session,
):
    project = create_project(db, "Wrong claim token project")
    registered = create_registered_runner(
        db,
        project=project,
        name="Wrong token runner",
        capabilities=["asr"],
    )

    claim_time = datetime(
        2026,
        7,
        29,
        17,
        0,
        tzinfo=UTC,
    )

    create_job(
        db,
        project=project,
        name="Wrong token job",
        required_capabilities=["asr"],
        available_at=claim_time,
    )

    claimed = claim_next_job(
        db,
        credential=registered.credential,
        now=claim_time,
    )

    assert claimed is not None

    with pytest.raises(
        RunnerJobClaimUnavailableError,
        match="invalid or unavailable",
    ):
        verify_job_claim_ownership(
            db,
            credential=registered.credential,
            job_public_id=claimed.job.public_id,
            claim_token="ovrin_claim_wrong-token",
            now=claim_time + timedelta(minutes=1),
        )


def test_verify_job_claim_ownership_rejects_other_runner(
    db: Session,
):
    project = create_project(db, "Other runner claim project")
    owner = create_registered_runner(
        db,
        project=project,
        name="Claim owner runner",
        capabilities=["asr"],
    )
    other_runner = create_registered_runner(
        db,
        project=project,
        name="Other runner",
        capabilities=["asr"],
    )

    claim_time = datetime(
        2026,
        7,
        29,
        17,
        30,
        tzinfo=UTC,
    )

    create_job(
        db,
        project=project,
        name="Runner ownership job",
        required_capabilities=["asr"],
        available_at=claim_time,
    )

    claimed = claim_next_job(
        db,
        credential=owner.credential,
        now=claim_time,
    )

    assert claimed is not None

    with pytest.raises(
        RunnerJobClaimUnavailableError,
        match="invalid or unavailable",
    ):
        verify_job_claim_ownership(
            db,
            credential=other_runner.credential,
            job_public_id=claimed.job.public_id,
            claim_token=claimed.claim_token,
            now=claim_time + timedelta(minutes=1),
        )


def test_verify_job_claim_ownership_rejects_expired_lease(
    db: Session,
):
    project = create_project(db, "Expired claim project")
    registered = create_registered_runner(
        db,
        project=project,
        name="Expired claim runner",
        capabilities=["asr"],
    )

    claim_time = datetime(
        2026,
        7,
        29,
        18,
        0,
        tzinfo=UTC,
    )

    create_job(
        db,
        project=project,
        name="Expired claim job",
        required_capabilities=["asr"],
        available_at=claim_time,
    )

    claimed = claim_next_job(
        db,
        credential=registered.credential,
        lease_duration=timedelta(minutes=2),
        now=claim_time,
    )

    assert claimed is not None

    with pytest.raises(
        RunnerJobClaimUnavailableError,
        match="invalid or unavailable",
    ):
        verify_job_claim_ownership(
            db,
            credential=registered.credential,
            job_public_id=claimed.job.public_id,
            claim_token=claimed.claim_token,
            now=claim_time + timedelta(minutes=2),
        )

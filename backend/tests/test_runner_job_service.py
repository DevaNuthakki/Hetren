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
    MAX_EXPIRED_JOB_RECOVERY_BATCH,
    MAX_JOB_LEASE_DURATION,
    MAX_RUNNER_JOB_LOG_BATCH_SIZE,
    RunnerJobCancellationUnavailableError,
    RunnerJobClaimUnavailableError,
    RunnerJobNotFoundError,
    RunnerJobProjectNotFoundError,
    RunnerJobTransitionUnavailableError,
    append_job_logs,
    cancel_job,
    claim_next_job,
    complete_job,
    enqueue_job,
    fail_job,
    query_job_logs,
    recover_expired_jobs,
    renew_job_lease,
    start_job,
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


def test_start_job_transitions_claimed_job_to_running(
    db: Session,
):
    project = create_project(db, "Start job project")
    registered = create_registered_runner(
        db,
        project=project,
        name="Start job runner",
        capabilities=["asr"],
    )

    claim_time = datetime(
        2026,
        7,
        29,
        19,
        0,
        tzinfo=UTC,
    )
    start_time = claim_time + timedelta(minutes=1)

    create_job(
        db,
        project=project,
        name="Start transition job",
        required_capabilities=["asr"],
        available_at=claim_time,
    )

    claimed = claim_next_job(
        db,
        credential=registered.credential,
        now=claim_time,
    )

    assert claimed is not None
    original_claim_hash = claimed.job.claim_token_hash
    original_lease = claimed.job.lease_expires_at

    started = start_job(
        db,
        credential=registered.credential,
        job_public_id=claimed.job.public_id,
        claim_token=claimed.claim_token,
        now=start_time,
    )

    assert started.status == "running"
    assert started.started_at is not None
    assert started.started_at.replace(tzinfo=UTC) == start_time
    assert started.claim_token_hash == original_claim_hash
    assert started.lease_expires_at == original_lease


def test_start_job_rejects_already_running_job(
    db: Session,
):
    project = create_project(db, "Duplicate start project")
    registered = create_registered_runner(
        db,
        project=project,
        name="Duplicate start runner",
        capabilities=["asr"],
    )

    claim_time = datetime(
        2026,
        7,
        29,
        19,
        30,
        tzinfo=UTC,
    )

    create_job(
        db,
        project=project,
        name="Duplicate start job",
        required_capabilities=["asr"],
        available_at=claim_time,
    )

    claimed = claim_next_job(
        db,
        credential=registered.credential,
        now=claim_time,
    )
    assert claimed is not None

    start_job(
        db,
        credential=registered.credential,
        job_public_id=claimed.job.public_id,
        claim_token=claimed.claim_token,
        now=claim_time + timedelta(seconds=10),
    )

    with pytest.raises(
        RunnerJobTransitionUnavailableError,
        match="invalid or unavailable",
    ):
        start_job(
            db,
            credential=registered.credential,
            job_public_id=claimed.job.public_id,
            claim_token=claimed.claim_token,
            now=claim_time + timedelta(seconds=20),
        )


def test_complete_job_transitions_running_job_to_completed(
    db: Session,
):
    project = create_project(db, "Complete job project")
    registered = create_registered_runner(
        db,
        project=project,
        name="Complete job runner",
        capabilities=["asr"],
    )

    claim_time = datetime(
        2026,
        7,
        29,
        20,
        0,
        tzinfo=UTC,
    )
    start_time = claim_time + timedelta(seconds=10)
    completion_time = claim_time + timedelta(minutes=1)

    create_job(
        db,
        project=project,
        name="Complete transition job",
        required_capabilities=["asr"],
        available_at=claim_time,
    )

    claimed = claim_next_job(
        db,
        credential=registered.credential,
        now=claim_time,
    )
    assert claimed is not None

    start_job(
        db,
        credential=registered.credential,
        job_public_id=claimed.job.public_id,
        claim_token=claimed.claim_token,
        now=start_time,
    )

    completed = complete_job(
        db,
        credential=registered.credential,
        job_public_id=claimed.job.public_id,
        claim_token=claimed.claim_token,
        result_payload={
            "evaluation_run_id": 42,
            "status": "success",
        },
        now=completion_time,
    )

    assert completed.status == "completed"
    assert completed.completed_at is not None
    assert completed.completed_at.replace(
        tzinfo=UTC
    ) == completion_time

    assert completed.result_payload == {
        "evaluation_run_id": 42,
        "status": "success",
    }
    assert completed.error_message is None
    assert completed.lease_expires_at is None
    assert completed.claim_token_hash is None


def test_complete_job_rejects_job_that_has_not_started(
    db: Session,
):
    project = create_project(db, "Premature complete project")
    registered = create_registered_runner(
        db,
        project=project,
        name="Premature complete runner",
        capabilities=["asr"],
    )

    claim_time = datetime(
        2026,
        7,
        29,
        20,
        30,
        tzinfo=UTC,
    )

    create_job(
        db,
        project=project,
        name="Premature complete job",
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
        RunnerJobTransitionUnavailableError,
        match="invalid or unavailable",
    ):
        complete_job(
            db,
            credential=registered.credential,
            job_public_id=claimed.job.public_id,
            claim_token=claimed.claim_token,
            result_payload={"status": "success"},
            now=claim_time + timedelta(minutes=1),
        )


def test_fail_job_allows_failure_before_start(
    db: Session,
):
    project = create_project(db, "Pre-start failure project")
    registered = create_registered_runner(
        db,
        project=project,
        name="Pre-start failure runner",
        capabilities=["asr"],
    )

    claim_time = datetime(
        2026,
        7,
        29,
        21,
        0,
        tzinfo=UTC,
    )
    failure_time = claim_time + timedelta(seconds=30)

    create_job(
        db,
        project=project,
        name="Pre-start failure job",
        required_capabilities=["asr"],
        available_at=claim_time,
    )

    claimed = claim_next_job(
        db,
        credential=registered.credential,
        now=claim_time,
    )
    assert claimed is not None

    failed = fail_job(
        db,
        credential=registered.credential,
        job_public_id=claimed.job.public_id,
        claim_token=claimed.claim_token,
        error_message="  Model files could not be loaded.  ",
        now=failure_time,
    )

    assert failed.status == "failed"
    assert failed.started_at is None
    assert failed.failed_at is not None
    assert failed.failed_at.replace(tzinfo=UTC) == failure_time
    assert failed.error_message == (
        "Model files could not be loaded."
    )
    assert failed.lease_expires_at is None
    assert failed.claim_token_hash is None


def test_fail_job_allows_running_job_failure(
    db: Session,
):
    project = create_project(db, "Running failure project")
    registered = create_registered_runner(
        db,
        project=project,
        name="Running failure runner",
        capabilities=["asr"],
    )

    claim_time = datetime(
        2026,
        7,
        29,
        21,
        30,
        tzinfo=UTC,
    )
    start_time = claim_time + timedelta(seconds=10)
    failure_time = claim_time + timedelta(minutes=1)

    create_job(
        db,
        project=project,
        name="Running failure job",
        required_capabilities=["asr"],
        available_at=claim_time,
    )

    claimed = claim_next_job(
        db,
        credential=registered.credential,
        now=claim_time,
    )
    assert claimed is not None

    start_job(
        db,
        credential=registered.credential,
        job_public_id=claimed.job.public_id,
        claim_token=claimed.claim_token,
        now=start_time,
    )

    failed = fail_job(
        db,
        credential=registered.credential,
        job_public_id=claimed.job.public_id,
        claim_token=claimed.claim_token,
        error_message="ASR process exited with code 1.",
        now=failure_time,
    )

    assert failed.status == "failed"
    assert failed.started_at is not None
    assert failed.error_message == (
        "ASR process exited with code 1."
    )


def test_terminal_transition_invalidates_claim_token(
    db: Session,
):
    project = create_project(db, "Terminal claim project")
    registered = create_registered_runner(
        db,
        project=project,
        name="Terminal claim runner",
        capabilities=["asr"],
    )

    claim_time = datetime(
        2026,
        7,
        29,
        22,
        0,
        tzinfo=UTC,
    )

    create_job(
        db,
        project=project,
        name="Terminal claim job",
        required_capabilities=["asr"],
        available_at=claim_time,
    )

    claimed = claim_next_job(
        db,
        credential=registered.credential,
        now=claim_time,
    )
    assert claimed is not None

    start_job(
        db,
        credential=registered.credential,
        job_public_id=claimed.job.public_id,
        claim_token=claimed.claim_token,
        now=claim_time + timedelta(seconds=10),
    )

    complete_job(
        db,
        credential=registered.credential,
        job_public_id=claimed.job.public_id,
        claim_token=claimed.claim_token,
        result_payload={"status": "success"},
        now=claim_time + timedelta(minutes=1),
    )

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


def test_complete_job_rejects_non_json_result_payload(
    db: Session,
):
    project = create_project(db, "Invalid result project")
    registered = create_registered_runner(
        db,
        project=project,
        name="Invalid result runner",
        capabilities=["asr"],
    )

    with pytest.raises(
        ValueError,
        match="JSON-serializable",
    ):
        complete_job(
            db,
            credential=registered.credential,
            job_public_id=(
                "10000000-0000-0000-0000-000000000001"
            ),
            claim_token="ovrin_claim_test-token",
            result_payload={"invalid": object()},
        )


@pytest.mark.parametrize(
    "error_message",
    [
        "",
        "   ",
    ],
)
def test_fail_job_rejects_empty_error_message(
    db: Session,
    error_message: str,
):
    project = create_project(db, "Empty failure project")
    registered = create_registered_runner(
        db,
        project=project,
        name=f"Empty failure runner {len(error_message)}",
        capabilities=["asr"],
    )

    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        fail_job(
            db,
            credential=registered.credential,
            job_public_id=(
                "10000000-0000-0000-0000-000000000001"
            ),
            claim_token="ovrin_claim_test-token",
            error_message=error_message,
        )


def test_renew_job_lease_extends_claim_without_rotating_token(
    db: Session,
):
    project = create_project(db, "Lease renewal project")
    registered = create_registered_runner(
        db,
        project=project,
        name="Lease renewal runner",
        capabilities=["asr"],
    )

    claim_time = datetime(
        2026,
        7,
        29,
        23,
        0,
        tzinfo=UTC,
    )
    renewal_time = claim_time + timedelta(minutes=2)

    create_job(
        db,
        project=project,
        name="Lease renewal job",
        required_capabilities=["asr"],
        available_at=claim_time,
    )

    claimed = claim_next_job(
        db,
        credential=registered.credential,
        now=claim_time,
    )
    assert claimed is not None

    original_claim_hash = claimed.job.claim_token_hash

    renewed = renew_job_lease(
        db,
        credential=registered.credential,
        job_public_id=claimed.job.public_id,
        claim_token=claimed.claim_token,
        lease_duration=timedelta(minutes=10),
        now=renewal_time,
    )

    assert renewed.status == "claimed"
    assert renewed.claim_token_hash == original_claim_hash
    assert renewed.lease_expires_at is not None
    assert renewed.lease_expires_at.replace(
        tzinfo=UTC
    ) == renewal_time + timedelta(minutes=10)


def test_renew_job_lease_never_shortens_existing_lease(
    db: Session,
):
    project = create_project(db, "Lease preservation project")
    registered = create_registered_runner(
        db,
        project=project,
        name="Lease preservation runner",
        capabilities=["asr"],
    )

    claim_time = datetime(
        2026,
        7,
        29,
        23,
        30,
        tzinfo=UTC,
    )

    create_job(
        db,
        project=project,
        name="Long lease job",
        required_capabilities=["asr"],
        available_at=claim_time,
    )

    claimed = claim_next_job(
        db,
        credential=registered.credential,
        lease_duration=timedelta(minutes=30),
        now=claim_time,
    )
    assert claimed is not None

    original_expiry = claimed.job.lease_expires_at

    renewed = renew_job_lease(
        db,
        credential=registered.credential,
        job_public_id=claimed.job.public_id,
        claim_token=claimed.claim_token,
        lease_duration=timedelta(minutes=5),
        now=claim_time + timedelta(minutes=1),
    )

    assert renewed.lease_expires_at == original_expiry


def test_renew_job_lease_rejects_expired_claim(
    db: Session,
):
    project = create_project(db, "Expired renewal project")
    registered = create_registered_runner(
        db,
        project=project,
        name="Expired renewal runner",
        capabilities=["asr"],
    )

    claim_time = datetime(
        2026,
        7,
        30,
        0,
        0,
        tzinfo=UTC,
    )

    create_job(
        db,
        project=project,
        name="Expired renewal job",
        required_capabilities=["asr"],
        available_at=claim_time,
    )

    claimed = claim_next_job(
        db,
        credential=registered.credential,
        lease_duration=timedelta(minutes=1),
        now=claim_time,
    )
    assert claimed is not None

    with pytest.raises(
        RunnerJobClaimUnavailableError,
        match="invalid or unavailable",
    ):
        renew_job_lease(
            db,
            credential=registered.credential,
            job_public_id=claimed.job.public_id,
            claim_token=claimed.claim_token,
            now=claim_time + timedelta(minutes=1),
        )


def test_recover_expired_jobs_requeues_retryable_job(
    db: Session,
):
    project = create_project(db, "Retry recovery project")
    registered = create_registered_runner(
        db,
        project=project,
        name="Retry recovery runner",
        capabilities=["asr"],
    )

    claim_time = datetime(
        2026,
        7,
        30,
        0,
        30,
        tzinfo=UTC,
    )
    recovery_time = claim_time + timedelta(minutes=2)

    job = create_job(
        db,
        project=project,
        name="Retryable expired job",
        required_capabilities=["asr"],
        available_at=claim_time,
        attempt_count=0,
        max_attempts=3,
    )

    claimed = claim_next_job(
        db,
        credential=registered.credential,
        lease_duration=timedelta(minutes=1),
        now=claim_time,
    )
    assert claimed is not None

    summary = recover_expired_jobs(
        db,
        now=recovery_time,
    )

    assert summary.requeued_count == 1
    assert summary.failed_count == 0
    assert summary.recovered_count == 1

    recovered = db.get(models.RunnerJob, job.id)
    assert recovered is not None

    assert recovered.status == "queued"
    assert recovered.attempt_count == 1
    assert recovered.assigned_runner_id is None
    assert recovered.claimed_at is None
    assert recovered.started_at is None
    assert recovered.lease_expires_at is None
    assert recovered.claim_token_hash is None
    assert recovered.error_message is None
    assert recovered.available_at.replace(
        tzinfo=UTC
    ) == recovery_time


def test_recover_expired_jobs_fails_exhausted_running_job(
    db: Session,
):
    project = create_project(db, "Exhausted recovery project")
    registered = create_registered_runner(
        db,
        project=project,
        name="Exhausted recovery runner",
        capabilities=["asr"],
    )

    claim_time = datetime(
        2026,
        7,
        30,
        1,
        0,
        tzinfo=UTC,
    )
    start_time = claim_time + timedelta(seconds=10)
    recovery_time = claim_time + timedelta(minutes=2)

    job = create_job(
        db,
        project=project,
        name="Exhausted expired job",
        required_capabilities=["asr"],
        available_at=claim_time,
        attempt_count=2,
        max_attempts=3,
    )

    claimed = claim_next_job(
        db,
        credential=registered.credential,
        lease_duration=timedelta(minutes=1),
        now=claim_time,
    )
    assert claimed is not None
    assert claimed.job.attempt_count == 3

    start_job(
        db,
        credential=registered.credential,
        job_public_id=claimed.job.public_id,
        claim_token=claimed.claim_token,
        now=start_time,
    )

    summary = recover_expired_jobs(
        db,
        now=recovery_time,
    )

    assert summary.requeued_count == 0
    assert summary.failed_count == 1
    assert summary.recovered_count == 1

    recovered = db.get(models.RunnerJob, job.id)
    assert recovered is not None

    assert recovered.status == "failed"
    assert recovered.assigned_runner_id == (
        registered.runner.id
    )
    assert recovered.claimed_at is not None
    assert recovered.started_at is not None
    assert recovered.failed_at is not None
    assert recovered.failed_at.replace(
        tzinfo=UTC
    ) == recovery_time
    assert recovered.lease_expires_at is None
    assert recovered.claim_token_hash is None
    assert recovered.error_message == (
        "Runner job lease expired after maximum attempts."
    )


def test_recover_expired_jobs_ignores_unexpired_job(
    db: Session,
):
    project = create_project(db, "Unexpired recovery project")
    registered = create_registered_runner(
        db,
        project=project,
        name="Unexpired recovery runner",
        capabilities=["asr"],
    )

    claim_time = datetime(
        2026,
        7,
        30,
        1,
        30,
        tzinfo=UTC,
    )

    create_job(
        db,
        project=project,
        name="Unexpired claimed job",
        required_capabilities=["asr"],
        available_at=claim_time,
    )

    claimed = claim_next_job(
        db,
        credential=registered.credential,
        lease_duration=timedelta(minutes=10),
        now=claim_time,
    )
    assert claimed is not None

    summary = recover_expired_jobs(
        db,
        now=claim_time + timedelta(minutes=5),
    )

    assert summary.recovered_count == 0

    persisted = db.get(
        models.RunnerJob,
        claimed.job.id,
    )
    assert persisted is not None
    assert persisted.status == "claimed"
    assert persisted.claim_token_hash is not None


@pytest.mark.parametrize(
    "limit",
    [
        0,
        -1,
        MAX_EXPIRED_JOB_RECOVERY_BATCH + 1,
    ],
)
def test_recover_expired_jobs_rejects_invalid_limit(
    db: Session,
    limit: int,
):
    with pytest.raises(ValueError):
        recover_expired_jobs(
            db,
            limit=limit,
        )


def test_enqueue_job_creates_valid_queued_job(
    db: Session,
):
    project = create_project(db, "Enqueue project")
    available_at = datetime(
        2026,
        7,
        30,
        2,
        0,
        tzinfo=UTC,
    )

    job = enqueue_job(
        db,
        project_id=project.id,
        name="  ASR regression evaluation  ",
        job_type="ASR_EVALUATION",
        required_capabilities=["asr", "cpu", "asr"],
        input_payload={
            "evaluation_run_id": 42,
            "dataset_id": 7,
        },
        priority=25,
        available_at=available_at,
        max_attempts=5,
    )

    assert job.project_id == project.id
    assert job.name == "ASR regression evaluation"
    assert job.job_type == "asr_evaluation"
    assert job.status == "queued"
    assert job.priority == 25
    assert job.required_capabilities == ["asr", "cpu"]
    assert job.input_payload == {
        "evaluation_run_id": 42,
        "dataset_id": 7,
    }
    assert job.attempt_count == 0
    assert job.max_attempts == 5
    assert job.available_at.replace(
        tzinfo=UTC
    ) == available_at

    assert job.assigned_runner_id is None
    assert job.claimed_at is None
    assert job.lease_expires_at is None
    assert job.claim_token_hash is None


def test_enqueue_job_uses_safe_defaults(
    db: Session,
):
    project = create_project(db, "Enqueue defaults project")
    enqueued_at = datetime(
        2026,
        7,
        30,
        2,
        30,
        tzinfo=UTC,
    )

    job = enqueue_job(
        db,
        project_id=project.id,
        name="Default ASR job",
        job_type="asr_evaluation",
        now=enqueued_at,
    )

    assert job.priority == 0
    assert job.required_capabilities == []
    assert job.input_payload == {}
    assert job.max_attempts == 3
    assert job.available_at.replace(
        tzinfo=UTC
    ) == enqueued_at


def test_enqueue_job_rejects_missing_project(
    db: Session,
):
    with pytest.raises(
        RunnerJobProjectNotFoundError,
        match="was not found",
    ):
        enqueue_job(
            db,
            project_id=2_147_483_647,
            name="Missing project job",
            job_type="asr_evaluation",
        )


def test_enqueue_job_rejects_unsupported_type(
    db: Session,
):
    project = create_project(db, "Unsupported type project")

    with pytest.raises(
        ValueError,
        match="Unsupported runner job type",
    ):
        enqueue_job(
            db,
            project_id=project.id,
            name="Unsafe command job",
            job_type="shell_command",
            input_payload={
                "command": "arbitrary command",
            },
        )

    assert db.query(models.RunnerJob).count() == 0


def test_enqueue_job_rejects_non_json_input(
    db: Session,
):
    project = create_project(db, "Invalid input project")

    with pytest.raises(
        ValueError,
        match="JSON-serializable",
    ):
        enqueue_job(
            db,
            project_id=project.id,
            name="Invalid input job",
            job_type="asr_evaluation",
            input_payload={"invalid": object()},
        )


@pytest.mark.parametrize(
    ("priority", "max_attempts"),
    [
        (-1001, 3),
        (1001, 3),
        (0, 0),
        (0, 101),
    ],
)
def test_enqueue_job_rejects_invalid_limits(
    db: Session,
    priority: int,
    max_attempts: int,
):
    project = create_project(
        db,
        f"Invalid limits {priority} {max_attempts}",
    )

    with pytest.raises(ValueError):
        enqueue_job(
            db,
            project_id=project.id,
            name="Invalid limits job",
            job_type="asr_evaluation",
            priority=priority,
            max_attempts=max_attempts,
        )


def test_cancel_job_cancels_queued_job(
    db: Session,
):
    project = create_project(db, "Queued cancellation project")
    cancellation_time = datetime(
        2026,
        7,
        30,
        3,
        0,
        tzinfo=UTC,
    )

    job = enqueue_job(
        db,
        project_id=project.id,
        name="Queued cancellation job",
        job_type="asr_evaluation",
    )

    cancelled = cancel_job(
        db,
        job_public_id=job.public_id,
        now=cancellation_time,
    )

    assert cancelled.status == "cancelled"
    assert cancelled.cancelled_at is not None
    assert cancelled.cancelled_at.replace(
        tzinfo=UTC
    ) == cancellation_time
    assert cancelled.assigned_runner_id is None
    assert cancelled.claimed_at is None
    assert cancelled.started_at is None
    assert cancelled.claim_token_hash is None
    assert cancelled.lease_expires_at is None


def test_cancel_job_invalidates_claimed_job_token(
    db: Session,
):
    project = create_project(db, "Claimed cancellation project")
    registered = create_registered_runner(
        db,
        project=project,
        name="Claimed cancellation runner",
        capabilities=["asr"],
    )
    claim_time = datetime(
        2026,
        7,
        30,
        3,
        30,
        tzinfo=UTC,
    )

    create_job(
        db,
        project=project,
        name="Claimed cancellation job",
        required_capabilities=["asr"],
        available_at=claim_time,
    )

    claimed = claim_next_job(
        db,
        credential=registered.credential,
        now=claim_time,
    )
    assert claimed is not None

    cancelled = cancel_job(
        db,
        job_public_id=claimed.job.public_id,
        now=claim_time + timedelta(minutes=1),
    )

    assert cancelled.status == "cancelled"
    assert cancelled.assigned_runner_id == (
        registered.runner.id
    )
    assert cancelled.claimed_at is not None
    assert cancelled.claim_token_hash is None
    assert cancelled.lease_expires_at is None

    with pytest.raises(RunnerJobClaimUnavailableError):
        verify_job_claim_ownership(
            db,
            credential=registered.credential,
            job_public_id=cancelled.public_id,
            claim_token=claimed.claim_token,
            now=claim_time + timedelta(minutes=2),
        )


def test_cancel_job_preserves_running_history(
    db: Session,
):
    project = create_project(db, "Running cancellation project")
    registered = create_registered_runner(
        db,
        project=project,
        name="Running cancellation runner",
        capabilities=["asr"],
    )
    claim_time = datetime(
        2026,
        7,
        30,
        4,
        0,
        tzinfo=UTC,
    )
    start_time = claim_time + timedelta(seconds=10)

    create_job(
        db,
        project=project,
        name="Running cancellation job",
        required_capabilities=["asr"],
        available_at=claim_time,
    )

    claimed = claim_next_job(
        db,
        credential=registered.credential,
        now=claim_time,
    )
    assert claimed is not None

    start_job(
        db,
        credential=registered.credential,
        job_public_id=claimed.job.public_id,
        claim_token=claimed.claim_token,
        now=start_time,
    )

    cancelled = cancel_job(
        db,
        job_public_id=claimed.job.public_id,
        now=claim_time + timedelta(minutes=1),
    )

    assert cancelled.status == "cancelled"
    assert cancelled.assigned_runner_id == (
        registered.runner.id
    )
    assert cancelled.claimed_at is not None
    assert cancelled.started_at is not None
    assert cancelled.started_at.replace(
        tzinfo=UTC
    ) == start_time


def test_cancel_job_is_idempotent(
    db: Session,
):
    project = create_project(db, "Idempotent cancellation project")
    job = enqueue_job(
        db,
        project_id=project.id,
        name="Idempotent cancellation job",
        job_type="asr_evaluation",
    )

    first = cancel_job(
        db,
        job_public_id=job.public_id,
    )
    original_cancelled_at = first.cancelled_at

    second = cancel_job(
        db,
        job_public_id=job.public_id,
        now=datetime.now(UTC) + timedelta(hours=1),
    )

    assert second.status == "cancelled"
    assert second.cancelled_at == original_cancelled_at


def test_cancel_job_rejects_completed_job(
    db: Session,
):
    project = create_project(db, "Completed cancellation project")
    registered = create_registered_runner(
        db,
        project=project,
        name="Completed cancellation runner",
        capabilities=["asr"],
    )
    claim_time = datetime(
        2026,
        7,
        30,
        4,
        30,
        tzinfo=UTC,
    )

    create_job(
        db,
        project=project,
        name="Completed cancellation job",
        required_capabilities=["asr"],
        available_at=claim_time,
    )

    claimed = claim_next_job(
        db,
        credential=registered.credential,
        now=claim_time,
    )
    assert claimed is not None

    start_job(
        db,
        credential=registered.credential,
        job_public_id=claimed.job.public_id,
        claim_token=claimed.claim_token,
        now=claim_time + timedelta(seconds=10),
    )
    complete_job(
        db,
        credential=registered.credential,
        job_public_id=claimed.job.public_id,
        claim_token=claimed.claim_token,
        result_payload={"status": "success"},
        now=claim_time + timedelta(minutes=1),
    )

    with pytest.raises(
        RunnerJobCancellationUnavailableError,
        match="current state",
    ):
        cancel_job(
            db,
            job_public_id=claimed.job.public_id,
        )


def test_cancel_job_rejects_unknown_public_id(
    db: Session,
):
    with pytest.raises(
        RunnerJobNotFoundError,
        match="was not found",
    ):
        cancel_job(
            db,
            job_public_id=(
                "00000000-0000-0000-0000-000000000000"
            ),
        )


def test_append_job_logs_assigns_server_sequence_and_attempt(
    db: Session,
):
    project = create_project(
        db,
        "Structured log append project",
    )
    registered = create_registered_runner(
        db,
        project=project,
        name="Structured log runner",
        capabilities=["asr"],
    )

    claim_time = datetime(
        2026,
        7,
        29,
        22,
        0,
        tzinfo=UTC,
    )

    create_job(
        db,
        project=project,
        name="Structured log job",
        required_capabilities=["asr"],
        available_at=claim_time,
    )

    claimed = claim_next_job(
        db,
        credential=registered.credential,
        now=claim_time,
    )

    assert claimed is not None

    logs = append_job_logs(
        db,
        credential=registered.credential,
        job_public_id=claimed.job.public_id,
        claim_token=claimed.claim_token,
        entries=[
            {
                "level": "info",
                "event_type": "asr.started",
                "message": "Transcription started.",
                "context_payload": {
                    "audio_count": 3,
                },
            },
            {
                "level": "warning",
                "event_type": "asr.slow",
                "message": "Processing is slower than expected.",
                "context_payload": {
                    "elapsed_seconds": 12.5,
                },
            },
        ],
        now=claim_time + timedelta(minutes=1),
    )

    assert [log.sequence_number for log in logs] == [1, 2]
    assert [log.attempt_number for log in logs] == [1, 1]
    assert all(log.job_id == claimed.job.id for log in logs)
    assert all(
        log.runner_id == registered.runner.id
        for log in logs
    )
    assert logs[0].context_payload == {
        "audio_count": 3,
    }


def test_append_job_logs_continues_existing_sequence(
    db: Session,
):
    project = create_project(
        db,
        "Structured log sequence project",
    )
    registered = create_registered_runner(
        db,
        project=project,
        name="Sequence log runner",
        capabilities=["asr"],
    )
    claim_time = datetime(
        2026,
        7,
        29,
        22,
        30,
        tzinfo=UTC,
    )

    create_job(
        db,
        project=project,
        name="Sequence log job",
        required_capabilities=["asr"],
        available_at=claim_time,
    )

    claimed = claim_next_job(
        db,
        credential=registered.credential,
        now=claim_time,
    )
    assert claimed is not None

    first_batch = append_job_logs(
        db,
        credential=registered.credential,
        job_public_id=claimed.job.public_id,
        claim_token=claimed.claim_token,
        entries=[
            {
                "level": "info",
                "event_type": "job.first",
                "message": "First entry.",
            },
        ],
        now=claim_time + timedelta(seconds=10),
    )

    second_batch = append_job_logs(
        db,
        credential=registered.credential,
        job_public_id=claimed.job.public_id,
        claim_token=claimed.claim_token,
        entries=[
            {
                "level": "debug",
                "event_type": "job.second",
                "message": "Second entry.",
            },
        ],
        now=claim_time + timedelta(seconds=20),
    )

    assert first_batch[0].sequence_number == 1
    assert second_batch[0].sequence_number == 2


def test_append_job_logs_accepts_running_job(
    db: Session,
):
    project = create_project(
        db,
        "Running structured log project",
    )
    registered = create_registered_runner(
        db,
        project=project,
        name="Running log runner",
        capabilities=["asr"],
    )
    claim_time = datetime(
        2026,
        7,
        29,
        23,
        0,
        tzinfo=UTC,
    )

    create_job(
        db,
        project=project,
        name="Running structured log job",
        required_capabilities=["asr"],
        available_at=claim_time,
    )

    claimed = claim_next_job(
        db,
        credential=registered.credential,
        now=claim_time,
    )
    assert claimed is not None

    start_job(
        db,
        credential=registered.credential,
        job_public_id=claimed.job.public_id,
        claim_token=claimed.claim_token,
        now=claim_time + timedelta(seconds=10),
    )

    logs = append_job_logs(
        db,
        credential=registered.credential,
        job_public_id=claimed.job.public_id,
        claim_token=claimed.claim_token,
        entries=[
            {
                "level": "info",
                "event_type": "job.running",
                "message": "Job is running.",
            },
        ],
        now=claim_time + timedelta(seconds=20),
    )

    assert len(logs) == 1
    assert logs[0].attempt_number == 1


def test_append_job_logs_rejects_invalid_claim_without_writes(
    db: Session,
):
    project = create_project(
        db,
        "Invalid structured log claim project",
    )
    registered = create_registered_runner(
        db,
        project=project,
        name="Invalid claim log runner",
        capabilities=["asr"],
    )
    claim_time = datetime(
        2026,
        7,
        29,
        23,
        30,
        tzinfo=UTC,
    )

    create_job(
        db,
        project=project,
        name="Invalid claim structured log job",
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
        append_job_logs(
            db,
            credential=registered.credential,
            job_public_id=claimed.job.public_id,
            claim_token="ovrin_claim_wrong-token",
            entries=[
                {
                    "level": "info",
                    "event_type": "job.invalid",
                    "message": "This must not persist.",
                },
            ],
            now=claim_time + timedelta(minutes=1),
        )

    assert db.query(models.RunnerJobLog).count() == 0


def test_append_job_logs_validates_batch_atomically(
    db: Session,
):
    project = create_project(
        db,
        "Atomic structured log project",
    )
    registered = create_registered_runner(
        db,
        project=project,
        name="Atomic log runner",
        capabilities=["asr"],
    )
    claim_time = datetime(
        2026,
        7,
        30,
        0,
        0,
        tzinfo=UTC,
    )

    create_job(
        db,
        project=project,
        name="Atomic structured log job",
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
        ValueError,
        match="unsupported level",
    ):
        append_job_logs(
            db,
            credential=registered.credential,
            job_public_id=claimed.job.public_id,
            claim_token=claimed.claim_token,
            entries=[
                {
                    "level": "info",
                    "event_type": "job.valid",
                    "message": "Valid first entry.",
                },
                {
                    "level": "critical",
                    "event_type": "job.invalid",
                    "message": "Invalid second entry.",
                },
            ],
            now=claim_time + timedelta(minutes=1),
        )

    assert db.query(models.RunnerJobLog).count() == 0


def test_append_job_logs_rejects_oversized_batch(
    db: Session,
):
    entries = [
        {
            "level": "info",
            "event_type": "job.progress",
            "message": f"Progress entry {index}.",
        }
        for index in range(
            MAX_RUNNER_JOB_LOG_BATCH_SIZE + 1
        )
    ]

    with pytest.raises(
        ValueError,
        match="at most 100 entries",
    ):
        append_job_logs(
            db,
            credential="unused",
            job_public_id="unused",
            claim_token="unused",
            entries=entries,
        )

    assert db.query(models.RunnerJobLog).count() == 0


def test_query_job_logs_returns_ordered_cursor_page(
    db: Session,
):
    project = create_project(
        db,
        "Structured log pagination project",
    )
    registered = create_registered_runner(
        db,
        project=project,
        name="Structured log pagination runner",
        capabilities=["asr"],
    )
    claim_time = datetime(
        2026,
        7,
        30,
        1,
        0,
        tzinfo=UTC,
    )

    create_job(
        db,
        project=project,
        name="Structured log pagination job",
        required_capabilities=["asr"],
        available_at=claim_time,
    )

    claimed = claim_next_job(
        db,
        credential=registered.credential,
        now=claim_time,
    )
    assert claimed is not None

    append_job_logs(
        db,
        credential=registered.credential,
        job_public_id=claimed.job.public_id,
        claim_token=claimed.claim_token,
        entries=[
            {
                "level": "info",
                "event_type": "job.first",
                "message": "First log.",
            },
            {
                "level": "debug",
                "event_type": "job.second",
                "message": "Second log.",
            },
            {
                "level": "warning",
                "event_type": "job.third",
                "message": "Third log.",
            },
        ],
        now=claim_time + timedelta(seconds=10),
    )

    first_page = query_job_logs(
        db,
        credential=registered.credential,
        job_public_id=claimed.job.public_id,
        claim_token=claimed.claim_token,
        after_sequence=0,
        limit=2,
        now=claim_time + timedelta(seconds=20),
    )

    assert [
        job_log.sequence_number
        for job_log in first_page.logs
    ] == [1, 2]
    assert first_page.has_more is True
    assert first_page.next_after_sequence == 2

    second_page = query_job_logs(
        db,
        credential=registered.credential,
        job_public_id=claimed.job.public_id,
        claim_token=claimed.claim_token,
        after_sequence=first_page.next_after_sequence,
        limit=2,
        now=claim_time + timedelta(seconds=30),
    )

    assert [
        job_log.sequence_number
        for job_log in second_page.logs
    ] == [3]
    assert second_page.has_more is False
    assert second_page.next_after_sequence == 3


def test_query_job_logs_filters_by_level(
    db: Session,
):
    project = create_project(
        db,
        "Structured log level-filter project",
    )
    registered = create_registered_runner(
        db,
        project=project,
        name="Structured log level-filter runner",
        capabilities=["asr"],
    )
    claim_time = datetime(
        2026,
        7,
        30,
        1,
        30,
        tzinfo=UTC,
    )

    create_job(
        db,
        project=project,
        name="Structured log level-filter job",
        required_capabilities=["asr"],
        available_at=claim_time,
    )

    claimed = claim_next_job(
        db,
        credential=registered.credential,
        now=claim_time,
    )
    assert claimed is not None

    append_job_logs(
        db,
        credential=registered.credential,
        job_public_id=claimed.job.public_id,
        claim_token=claimed.claim_token,
        entries=[
            {
                "level": "info",
                "event_type": "job.started",
                "message": "Job started.",
            },
            {
                "level": "error",
                "event_type": "job.input.error",
                "message": "An input failed.",
            },
            {
                "level": "info",
                "event_type": "job.continued",
                "message": "Job continued.",
            },
        ],
        now=claim_time + timedelta(seconds=10),
    )

    page = query_job_logs(
        db,
        credential=registered.credential,
        job_public_id=claimed.job.public_id,
        claim_token=claimed.claim_token,
        level="ERROR",
        now=claim_time + timedelta(seconds=20),
    )

    assert len(page.logs) == 1
    assert page.logs[0].level == "error"
    assert page.logs[0].sequence_number == 2
    assert page.has_more is False


def test_query_job_logs_filters_across_execution_attempts(
    db: Session,
):
    project = create_project(
        db,
        "Structured log attempt-filter project",
    )
    registered = create_registered_runner(
        db,
        project=project,
        name="Structured log attempt-filter runner",
        capabilities=["asr"],
    )
    claim_time = datetime(
        2026,
        7,
        30,
        2,
        0,
        tzinfo=UTC,
    )

    create_job(
        db,
        project=project,
        name="Structured log attempt-filter job",
        required_capabilities=["asr"],
        available_at=claim_time,
        max_attempts=3,
    )

    first_claim = claim_next_job(
        db,
        credential=registered.credential,
        lease_duration=timedelta(minutes=1),
        now=claim_time,
    )
    assert first_claim is not None

    append_job_logs(
        db,
        credential=registered.credential,
        job_public_id=first_claim.job.public_id,
        claim_token=first_claim.claim_token,
        entries=[
            {
                "level": "warning",
                "event_type": "job.attempt.one",
                "message": "First attempt log.",
            },
        ],
        now=claim_time + timedelta(seconds=10),
    )

    recovery_time = claim_time + timedelta(minutes=2)

    recovery = recover_expired_jobs(
        db,
        now=recovery_time,
    )

    assert recovery.requeued_count == 1

    second_claim = claim_next_job(
        db,
        credential=registered.credential,
        now=recovery_time,
    )
    assert second_claim is not None
    assert second_claim.job.attempt_count == 2

    append_job_logs(
        db,
        credential=registered.credential,
        job_public_id=second_claim.job.public_id,
        claim_token=second_claim.claim_token,
        entries=[
            {
                "level": "info",
                "event_type": "job.attempt.two",
                "message": "Second attempt log.",
            },
        ],
        now=recovery_time + timedelta(seconds=10),
    )

    first_attempt_page = query_job_logs(
        db,
        credential=registered.credential,
        job_public_id=second_claim.job.public_id,
        claim_token=second_claim.claim_token,
        attempt_number=1,
        now=recovery_time + timedelta(seconds=20),
    )

    second_attempt_page = query_job_logs(
        db,
        credential=registered.credential,
        job_public_id=second_claim.job.public_id,
        claim_token=second_claim.claim_token,
        attempt_number=2,
        now=recovery_time + timedelta(seconds=30),
    )

    assert [
        log.attempt_number
        for log in first_attempt_page.logs
    ] == [1]

    assert [
        log.attempt_number
        for log in second_attempt_page.logs
    ] == [2]

    assert (
        first_attempt_page.logs[0].sequence_number
        < second_attempt_page.logs[0].sequence_number
    )


def test_query_job_logs_rejects_invalid_claim(
    db: Session,
):
    project = create_project(
        db,
        "Structured log invalid-query-claim project",
    )
    registered = create_registered_runner(
        db,
        project=project,
        name="Structured log invalid-query runner",
        capabilities=["asr"],
    )
    claim_time = datetime(
        2026,
        7,
        30,
        2,
        30,
        tzinfo=UTC,
    )

    create_job(
        db,
        project=project,
        name="Structured log invalid-query job",
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
        query_job_logs(
            db,
            credential=registered.credential,
            job_public_id=claimed.job.public_id,
            claim_token="ovrin_claim_wrong-token",
            now=claim_time + timedelta(seconds=10),
        )


def test_query_job_logs_rejects_terminal_job(
    db: Session,
):
    project = create_project(
        db,
        "Structured log terminal-query project",
    )
    registered = create_registered_runner(
        db,
        project=project,
        name="Structured log terminal-query runner",
        capabilities=["asr"],
    )
    claim_time = datetime(
        2026,
        7,
        30,
        3,
        0,
        tzinfo=UTC,
    )

    create_job(
        db,
        project=project,
        name="Structured log terminal-query job",
        required_capabilities=["asr"],
        available_at=claim_time,
    )

    claimed = claim_next_job(
        db,
        credential=registered.credential,
        now=claim_time,
    )
    assert claimed is not None

    start_job(
        db,
        credential=registered.credential,
        job_public_id=claimed.job.public_id,
        claim_token=claimed.claim_token,
        now=claim_time + timedelta(seconds=10),
    )

    complete_job(
        db,
        credential=registered.credential,
        job_public_id=claimed.job.public_id,
        claim_token=claimed.claim_token,
        result_payload={"status": "completed"},
        now=claim_time + timedelta(seconds=20),
    )

    with pytest.raises(
        RunnerJobClaimUnavailableError,
        match="invalid or unavailable",
    ):
        query_job_logs(
            db,
            credential=registered.credential,
            job_public_id=claimed.job.public_id,
            claim_token=claimed.claim_token,
            now=claim_time + timedelta(seconds=30),
        )


@pytest.mark.parametrize(
    ("query_arguments", "expected_message"),
    [
        (
            {"after_sequence": -1},
            "cursor must not be negative",
        ),
        (
            {"limit": 0},
            "limit must be at least one",
        ),
        (
            {"limit": 201},
            "limit must not exceed 200",
        ),
        (
            {"attempt_number": 0},
            "attempt filter must be at least one",
        ),
        (
            {"level": "critical"},
            "level filter is unsupported",
        ),
    ],
)
def test_query_job_logs_validates_query_controls(
    db: Session,
    query_arguments: dict[str, object],
    expected_message: str,
):
    with pytest.raises(
        ValueError,
        match=expected_message,
    ):
        query_job_logs(
            db,
            credential="unused",
            job_public_id="unused",
            claim_token="unused",
            **query_arguments,
        )


def test_query_job_logs_rejects_different_runner(
    db: Session,
):
    project = create_project(
        db,
        "Structured log runner-isolation project",
    )
    owning_runner = create_registered_runner(
        db,
        project=project,
        name="Structured log owning runner",
        capabilities=["asr"],
    )
    other_runner = create_registered_runner(
        db,
        project=project,
        name="Structured log unauthorized runner",
        capabilities=["asr"],
    )
    claim_time = datetime(
        2026,
        7,
        30,
        3,
        30,
        tzinfo=UTC,
    )

    create_job(
        db,
        project=project,
        name="Structured log runner-isolation job",
        required_capabilities=["asr"],
        available_at=claim_time,
    )

    claimed = claim_next_job(
        db,
        credential=owning_runner.credential,
        now=claim_time,
    )
    assert claimed is not None

    append_job_logs(
        db,
        credential=owning_runner.credential,
        job_public_id=claimed.job.public_id,
        claim_token=claimed.claim_token,
        entries=[
            {
                "level": "info",
                "event_type": "job.private",
                "message": "Only the owning runner may read this.",
            },
        ],
        now=claim_time + timedelta(seconds=10),
    )

    with pytest.raises(
        RunnerJobClaimUnavailableError,
        match="invalid or unavailable",
    ):
        query_job_logs(
            db,
            credential=other_runner.credential,
            job_public_id=claimed.job.public_id,
            claim_token=claimed.claim_token,
            now=claim_time + timedelta(seconds=20),
        )


def test_query_job_logs_returns_empty_page_without_cursor(
    db: Session,
):
    project = create_project(
        db,
        "Structured log empty-page project",
    )
    registered = create_registered_runner(
        db,
        project=project,
        name="Structured log empty-page runner",
        capabilities=["asr"],
    )
    claim_time = datetime(
        2026,
        7,
        30,
        4,
        0,
        tzinfo=UTC,
    )

    create_job(
        db,
        project=project,
        name="Structured log empty-page job",
        required_capabilities=["asr"],
        available_at=claim_time,
    )

    claimed = claim_next_job(
        db,
        credential=registered.credential,
        now=claim_time,
    )
    assert claimed is not None

    page = query_job_logs(
        db,
        credential=registered.credential,
        job_public_id=claimed.job.public_id,
        claim_token=claimed.claim_token,
        now=claim_time + timedelta(seconds=10),
    )

    assert page.logs == []
    assert page.has_more is False
    assert page.next_after_sequence is None

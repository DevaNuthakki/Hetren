import hashlib
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models


pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        os.getenv("RUN_POSTGRES_TESTS") != "1",
        reason=(
            "Set RUN_POSTGRES_TESTS=1 to run PostgreSQL "
            "integration tests."
        ),
    ),
]


def test_postgres_schema_is_at_alembic_head(
    postgres_test_engine: Engine,
):
    alembic_config = Config("alembic.ini")
    migration_head = ScriptDirectory.from_config(
        alembic_config
    ).get_current_head()

    with postgres_test_engine.connect() as connection:
        database_revision = connection.scalar(
            text("SELECT version_num FROM alembic_version")
        )

    assert database_revision == migration_head

    required_tables = {
        "alembic_version",
        "projects",
        "datasets",
        "test_cases",
        "evaluation_runs",
        "evaluation_results",
        "run_comparisons",
        "debug_cases",
        "release_policies",
        "release_reports",
        "runner_registration_tokens",
        "runners",
        "runner_jobs",
        "runner_job_logs",
        "hvee_metric_definitions",
        "hvee_evaluator_versions",
        "hvee_observations",
    }

    actual_tables = set(
        inspect(postgres_test_engine).get_table_names()
    )

    assert required_tables.issubset(actual_tables)


def test_postgres_returns_timezone_aware_timestamps(
    postgres_session: Session,
):
    project = models.Project(
        name="PostgreSQL timestamp test",
        description="Validates timezone-aware timestamps.",
    )

    postgres_session.add(project)
    postgres_session.flush()
    postgres_session.refresh(project)

    assert project.created_at is not None
    assert project.created_at.tzinfo is not None
    assert project.created_at.utcoffset() is not None


def test_postgres_enforces_foreign_keys(
    postgres_session: Session,
):
    invalid_dataset = models.Dataset(
        project_id=2_147_483_647,
        name="Invalid foreign-key dataset",
    )

    postgres_session.add(invalid_dataset)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


def test_postgres_enforces_one_release_report_per_comparison(
    postgres_session: Session,
):
    project = models.Project(
        name="Release-report uniqueness test",
    )
    postgres_session.add(project)
    postgres_session.flush()

    baseline_run = models.EvaluationRun(
        project_id=project.id,
        run_name="baseline",
        model_name="baseline-model",
        status="completed",
    )
    current_run = models.EvaluationRun(
        project_id=project.id,
        run_name="candidate",
        model_name="candidate-model",
        status="completed",
    )

    postgres_session.add_all(
        [baseline_run, current_run]
    )
    postgres_session.flush()

    comparison = models.RunComparison(
        baseline_run_id=baseline_run.id,
        current_run_id=current_run.id,
        comparison_status="no_significant_change",
    )

    postgres_session.add(comparison)
    postgres_session.flush()

    first_report = models.ReleaseReport(
        project_id=project.id,
        comparison_id=comparison.id,
        status="pass",
        severity="none",
        headline="Release passed",
        summary="No blocking regression detected.",
        recommendation="Proceed.",
        policy_snapshot={},
        checks=[],
    )

    postgres_session.add(first_report)
    postgres_session.flush()

    duplicate_report = models.ReleaseReport(
        project_id=project.id,
        comparison_id=comparison.id,
        status="pass",
        severity="none",
        headline="Duplicate report",
        summary="This record must be rejected.",
        recommendation="Do not persist.",
        policy_snapshot={},
        checks=[],
    )

    postgres_session.add(duplicate_report)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()

def _test_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _create_test_project(
    postgres_session: Session,
    suffix: str,
) -> models.Project:
    project = models.Project(
        name=f"Runner project {suffix}",
    )
    postgres_session.add(project)
    postgres_session.flush()
    return project


def _create_test_registration_token(
    postgres_session: Session,
    project_id: int,
    suffix: str,
) -> models.RunnerRegistrationToken:
    created_at = datetime.now(UTC)

    token = models.RunnerRegistrationToken(
        project_id=project_id,
        label=f"Registration token {suffix}",
        token_hash=_test_digest(f"registration:{suffix}"),
        created_at=created_at,
        expires_at=created_at + timedelta(hours=1),
    )

    postgres_session.add(token)
    postgres_session.flush()
    return token


def _build_test_runner(
    project_id: int,
    registration_token_id: int,
    suffix: str,
    *,
    name: str | None = None,
    status: str = "active",
    revoked_at: datetime | None = None,
) -> models.Runner:
    return models.Runner(
        project_id=project_id,
        registration_token_id=registration_token_id,
        public_id=f"runner-{_test_digest(suffix)[:29]}",
        name=name or f"Runner {suffix}",
        status=status,
        runner_version="0.1.0-test",
        capabilities=["asr"],
        system_info={"platform": "pytest"},
        credential_hash=_test_digest(f"credential:{suffix}"),
        revoked_at=revoked_at,
    )


def _build_test_runner_job(
    project_id: int,
    suffix: str,
    *,
    assigned_runner_id: int | None = None,
    status: str = "queued",
    attempt_count: int = 0,
    max_attempts: int = 3,
    claimed_at: datetime | None = None,
    lease_expires_at: datetime | None = None,
    claim_token_hash: str | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    failed_at: datetime | None = None,
    cancelled_at: datetime | None = None,
    result_payload: dict[str, object] | None = None,
    error_message: str | None = None,
) -> models.RunnerJob:
    return models.RunnerJob(
        public_id=f"job-{_test_digest(suffix)[:24]}",
        project_id=project_id,
        assigned_runner_id=assigned_runner_id,
        name=f"Runner job {suffix}",
        job_type="asr_evaluation",
        status=status,
        required_capabilities=["asr"],
        input_payload={"source": "pytest"},
        attempt_count=attempt_count,
        max_attempts=max_attempts,
        claimed_at=claimed_at,
        lease_expires_at=lease_expires_at,
        claim_token_hash=claim_token_hash,
        started_at=started_at,
        completed_at=completed_at,
        failed_at=failed_at,
        cancelled_at=cancelled_at,
        result_payload=result_payload,
        error_message=error_message,
    )


def test_postgres_runner_defaults_and_timestamps(
    postgres_session: Session,
):
    project = _create_test_project(
        postgres_session,
        "defaults",
    )
    token = _create_test_registration_token(
        postgres_session,
        project.id,
        "defaults",
    )

    runner = models.Runner(
        project_id=project.id,
        registration_token_id=token.id,
        public_id="runner-defaults",
        name="Runner defaults",
        credential_hash=_test_digest("credential:defaults"),
    )

    postgres_session.add(runner)
    postgres_session.flush()
    postgres_session.refresh(runner)

    assert runner.status == "active"
    assert runner.capabilities == []
    assert runner.system_info == {}
    assert runner.last_seen_at is None
    assert runner.revoked_at is None

    assert runner.created_at.tzinfo is not None
    assert runner.created_at.utcoffset() is not None
    assert runner.updated_at.tzinfo is not None
    assert runner.updated_at.utcoffset() is not None

    assert token.created_at.tzinfo is not None
    assert token.expires_at.tzinfo is not None
    assert token.consumed_at is None
    assert token.revoked_at is None


def test_postgres_enforces_registration_token_expiry(
    postgres_session: Session,
):
    project = _create_test_project(
        postgres_session,
        "invalid-expiry",
    )
    created_at = datetime.now(UTC)

    token = models.RunnerRegistrationToken(
        project_id=project.id,
        label="Invalid expiry",
        token_hash=_test_digest("registration:invalid-expiry"),
        created_at=created_at,
        expires_at=created_at,
    )

    postgres_session.add(token)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


def test_postgres_enforces_registration_token_lifecycle(
    postgres_session: Session,
):
    project = _create_test_project(
        postgres_session,
        "invalid-lifecycle",
    )
    created_at = datetime.now(UTC)

    token = models.RunnerRegistrationToken(
        project_id=project.id,
        label="Invalid lifecycle",
        token_hash=_test_digest(
            "registration:invalid-lifecycle"
        ),
        created_at=created_at,
        expires_at=created_at + timedelta(hours=1),
        consumed_at=created_at,
        revoked_at=created_at,
    )

    postgres_session.add(token)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


def test_postgres_enforces_unique_registration_token_hash(
    postgres_session: Session,
):
    first_project = _create_test_project(
        postgres_session,
        "token-hash-first",
    )
    second_project = _create_test_project(
        postgres_session,
        "token-hash-second",
    )
    created_at = datetime.now(UTC)
    shared_hash = _test_digest("registration:shared")

    first_token = models.RunnerRegistrationToken(
        project_id=first_project.id,
        label="First token",
        token_hash=shared_hash,
        created_at=created_at,
        expires_at=created_at + timedelta(hours=1),
    )
    postgres_session.add(first_token)
    postgres_session.flush()

    duplicate_token = models.RunnerRegistrationToken(
        project_id=second_project.id,
        label="Duplicate token",
        token_hash=shared_hash,
        created_at=created_at,
        expires_at=created_at + timedelta(hours=1),
    )
    postgres_session.add(duplicate_token)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


def test_postgres_enforces_runner_token_project_match(
    postgres_session: Session,
):
    token_project = _create_test_project(
        postgres_session,
        "token-owner",
    )
    runner_project = _create_test_project(
        postgres_session,
        "runner-owner",
    )
    token = _create_test_registration_token(
        postgres_session,
        token_project.id,
        "cross-project",
    )

    runner = _build_test_runner(
        project_id=runner_project.id,
        registration_token_id=token.id,
        suffix="cross-project",
    )
    postgres_session.add(runner)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


def test_postgres_enforces_unique_runner_name_per_project(
    postgres_session: Session,
):
    project = _create_test_project(
        postgres_session,
        "unique-name",
    )
    first_token = _create_test_registration_token(
        postgres_session,
        project.id,
        "unique-name-first",
    )
    second_token = _create_test_registration_token(
        postgres_session,
        project.id,
        "unique-name-second",
    )

    first_runner = _build_test_runner(
        project_id=project.id,
        registration_token_id=first_token.id,
        suffix="unique-name-first",
        name="Shared runner name",
    )
    postgres_session.add(first_runner)
    postgres_session.flush()

    duplicate_runner = _build_test_runner(
        project_id=project.id,
        registration_token_id=second_token.id,
        suffix="unique-name-second",
        name="Shared runner name",
    )
    postgres_session.add(duplicate_runner)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


def test_postgres_allows_one_runner_per_registration_token(
    postgres_session: Session,
):
    project = _create_test_project(
        postgres_session,
        "single-use-token",
    )
    token = _create_test_registration_token(
        postgres_session,
        project.id,
        "single-use-token",
    )

    first_runner = _build_test_runner(
        project_id=project.id,
        registration_token_id=token.id,
        suffix="single-use-first",
    )
    postgres_session.add(first_runner)
    postgres_session.flush()

    duplicate_runner = _build_test_runner(
        project_id=project.id,
        registration_token_id=token.id,
        suffix="single-use-second",
    )
    postgres_session.add(duplicate_runner)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


@pytest.mark.parametrize(
    ("status", "has_revocation_timestamp"),
    [
        ("active", True),
        ("revoked", False),
    ],
)
def test_postgres_enforces_runner_revocation_consistency(
    postgres_session: Session,
    status: str,
    has_revocation_timestamp: bool,
):
    project = _create_test_project(
        postgres_session,
        f"revocation-{status}-{has_revocation_timestamp}",
    )
    token = _create_test_registration_token(
        postgres_session,
        project.id,
        f"revocation-{status}-{has_revocation_timestamp}",
    )

    revoked_at = (
        datetime.now(UTC)
        if has_revocation_timestamp
        else None
    )

    runner = _build_test_runner(
        project_id=project.id,
        registration_token_id=token.id,
        suffix=f"revoke-{status}-{has_revocation_timestamp}",
        status=status,
        revoked_at=revoked_at,
    )
    postgres_session.add(runner)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


def test_postgres_runner_job_defaults_and_timestamps(
    postgres_session: Session,
):
    project = _create_test_project(
        postgres_session,
        "job-defaults",
    )

    job = models.RunnerJob(
        public_id="job-defaults",
        project_id=project.id,
        name="Runner job defaults",
        job_type="asr_evaluation",
    )

    postgres_session.add(job)
    postgres_session.flush()
    postgres_session.refresh(job)

    assert job.status == "queued"
    assert job.priority == 0
    assert job.required_capabilities == []
    assert job.input_payload == {}
    assert job.result_payload is None
    assert job.error_message is None

    assert job.attempt_count == 0
    assert job.max_attempts == 3

    assert job.assigned_runner_id is None
    assert job.claimed_at is None
    assert job.lease_expires_at is None
    assert job.claim_token_hash is None
    assert job.started_at is None
    assert job.completed_at is None
    assert job.failed_at is None
    assert job.cancelled_at is None

    assert job.available_at.tzinfo is not None
    assert job.available_at.utcoffset() is not None
    assert job.created_at.tzinfo is not None
    assert job.created_at.utcoffset() is not None
    assert job.updated_at.tzinfo is not None
    assert job.updated_at.utcoffset() is not None


def test_postgres_enforces_runner_job_project_match(
    postgres_session: Session,
):
    runner_project = _create_test_project(
        postgres_session,
        "job-runner-owner",
    )
    job_project = _create_test_project(
        postgres_session,
        "job-owner",
    )
    token = _create_test_registration_token(
        postgres_session,
        runner_project.id,
        "job-cross-project",
    )

    runner = _build_test_runner(
        project_id=runner_project.id,
        registration_token_id=token.id,
        suffix="job-cross-project",
    )

    postgres_session.add(runner)
    postgres_session.flush()

    claimed_at = datetime.now(UTC)

    job = _build_test_runner_job(
        project_id=job_project.id,
        assigned_runner_id=runner.id,
        suffix="cross-project",
        status="claimed",
        attempt_count=1,
        claimed_at=claimed_at,
        lease_expires_at=claimed_at + timedelta(minutes=5),
        claim_token_hash=_test_digest(
            "job-claim:cross-project"
        ),
    )

    postgres_session.add(job)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


@pytest.mark.parametrize(
    ("attempt_count", "max_attempts"),
    [
        (-1, 3),
        (0, 0),
        (4, 3),
    ],
)
def test_postgres_enforces_runner_job_attempt_counts(
    postgres_session: Session,
    attempt_count: int,
    max_attempts: int,
):
    project = _create_test_project(
        postgres_session,
        f"attempts-{attempt_count}-{max_attempts}",
    )

    job = _build_test_runner_job(
        project_id=project.id,
        suffix=f"attempts-{attempt_count}-{max_attempts}",
        attempt_count=attempt_count,
        max_attempts=max_attempts,
    )

    postgres_session.add(job)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


def test_postgres_rejects_unknown_runner_job_status(
    postgres_session: Session,
):
    project = _create_test_project(
        postgres_session,
        "unknown-job-status",
    )

    job = _build_test_runner_job(
        project_id=project.id,
        suffix="unknown-status",
        status="unknown",
    )

    postgres_session.add(job)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


@pytest.mark.parametrize(
    "job_status",
    [
        "claimed",
        "running",
        "completed",
        "failed",
        "cancelled",
    ],
)
def test_postgres_accepts_valid_runner_job_lifecycle(
    postgres_session: Session,
    job_status: str,
):
    project = _create_test_project(
        postgres_session,
        f"valid-job-{job_status}",
    )
    token = _create_test_registration_token(
        postgres_session,
        project.id,
        f"valid-job-{job_status}",
    )
    runner = _build_test_runner(
        project_id=project.id,
        registration_token_id=token.id,
        suffix=f"valid-job-{job_status}",
    )

    postgres_session.add(runner)
    postgres_session.flush()

    lifecycle_time = datetime.now(UTC)

    job_arguments: dict[str, object] = {
        "assigned_runner_id": runner.id,
        "status": job_status,
        "attempt_count": 1,
        "claimed_at": lifecycle_time,
    }

    if job_status in {"claimed", "running"}:
        job_arguments["lease_expires_at"] = (
            lifecycle_time + timedelta(minutes=5)
        )
        job_arguments["claim_token_hash"] = _test_digest(
            f"job-claim:valid-{job_status}"
        )

    if job_status in {
        "running",
        "completed",
        "failed",
        "cancelled",
    }:
        job_arguments["started_at"] = lifecycle_time

    if job_status == "completed":
        job_arguments["completed_at"] = lifecycle_time
        job_arguments["result_payload"] = {
            "status": "completed"
        }

    if job_status == "failed":
        job_arguments["failed_at"] = lifecycle_time
        job_arguments["error_message"] = (
            "Simulated runner failure."
        )

    if job_status == "cancelled":
        job_arguments["cancelled_at"] = lifecycle_time

    job = _build_test_runner_job(
        project_id=project.id,
        suffix=f"valid-{job_status}",
        **job_arguments,
    )

    postgres_session.add(job)
    postgres_session.flush()
    postgres_session.refresh(job)

    assert job.status == job_status


@pytest.mark.parametrize(
    "invalid_case",
    [
        "queued-with-assignment",
        "claimed-without-lease",
        "running-without-start",
        "completed-without-start",
        "failed-without-error",
        "cancelled-without-timestamp",
    ],
)
def test_postgres_enforces_runner_job_lifecycle(
    postgres_session: Session,
    invalid_case: str,
):
    project = _create_test_project(
        postgres_session,
        f"invalid-job-{invalid_case}",
    )
    token = _create_test_registration_token(
        postgres_session,
        project.id,
        f"invalid-job-{invalid_case}",
    )
    runner = _build_test_runner(
        project_id=project.id,
        registration_token_id=token.id,
        suffix=f"invalid-job-{invalid_case}",
    )

    postgres_session.add(runner)
    postgres_session.flush()

    lifecycle_time = datetime.now(UTC)
    job_arguments: dict[str, object]

    if invalid_case == "queued-with-assignment":
        job_arguments = {
            "assigned_runner_id": runner.id,
            "status": "queued",
        }
    elif invalid_case == "claimed-without-lease":
        job_arguments = {
            "assigned_runner_id": runner.id,
            "status": "claimed",
            "attempt_count": 1,
            "claimed_at": lifecycle_time,
            "claim_token_hash": _test_digest(
                "job-claim:missing-lease"
            ),
        }
    elif invalid_case == "running-without-start":
        job_arguments = {
            "assigned_runner_id": runner.id,
            "status": "running",
            "attempt_count": 1,
            "claimed_at": lifecycle_time,
            "lease_expires_at": (
                lifecycle_time + timedelta(minutes=5)
            ),
            "claim_token_hash": _test_digest(
                "job-claim:missing-start"
            ),
        }
    elif invalid_case == "completed-without-start":
        job_arguments = {
            "assigned_runner_id": runner.id,
            "status": "completed",
            "attempt_count": 1,
            "claimed_at": lifecycle_time,
            "completed_at": lifecycle_time,
            "result_payload": {"status": "completed"},
        }
    elif invalid_case == "failed-without-error":
        job_arguments = {
            "assigned_runner_id": runner.id,
            "status": "failed",
            "attempt_count": 1,
            "claimed_at": lifecycle_time,
            "started_at": lifecycle_time,
            "failed_at": lifecycle_time,
        }
    else:
        job_arguments = {
            "assigned_runner_id": runner.id,
            "status": "cancelled",
            "attempt_count": 1,
            "claimed_at": lifecycle_time,
            "started_at": lifecycle_time,
        }

    job = _build_test_runner_job(
        project_id=project.id,
        suffix=invalid_case,
        **job_arguments,
    )

    postgres_session.add(job)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


def _create_log_test_job(
    postgres_session: Session,
    *,
    project_id: int,
    runner_id: int,
    suffix: str,
) -> models.RunnerJob:
    lifecycle_time = datetime.now(UTC)

    job = models.RunnerJob(
        public_id=str(uuid4()),
        project_id=project_id,
        assigned_runner_id=runner_id,
        name=f"Structured log job {suffix}",
        job_type="asr_evaluation",
        status="running",
        required_capabilities=["asr"],
        input_payload={"source": "postgres-log-test"},
        attempt_count=1,
        max_attempts=3,
        claimed_at=lifecycle_time,
        lease_expires_at=(
            lifecycle_time + timedelta(minutes=5)
        ),
        claim_token_hash=_test_digest(
            f"structured-log-claim:{suffix}"
        ),
        started_at=lifecycle_time,
    )

    postgres_session.add(job)
    postgres_session.flush()
    return job


def _create_runner_job_log_context(
    postgres_session: Session,
    suffix: str,
) -> tuple[
    models.Project,
    models.Runner,
    models.RunnerJob,
]:
    project = _create_test_project(
        postgres_session,
        f"log-{suffix}",
    )
    token = _create_test_registration_token(
        postgres_session,
        project.id,
        f"log-{suffix}",
    )

    runner = models.Runner(
        project_id=project.id,
        registration_token_id=token.id,
        public_id=str(uuid4()),
        name=f"Structured log runner {suffix}",
        runner_version="0.1.0-test",
        capabilities=["asr"],
        system_info={"platform": "pytest"},
        credential_hash=_test_digest(
            f"structured-log-credential:{suffix}"
        ),
    )

    postgres_session.add(runner)
    postgres_session.flush()

    job = _create_log_test_job(
        postgres_session,
        project_id=project.id,
        runner_id=runner.id,
        suffix=suffix,
    )

    return project, runner, job


def _build_test_runner_job_log(
    *,
    project: models.Project,
    runner: models.Runner,
    job: models.RunnerJob,
    sequence_number: int = 1,
    attempt_number: int = 1,
    level: str = "info",
    event_type: str = "job.progress",
    message: str = "Runner job is progressing.",
    context_payload: dict[str, object] | None = None,
) -> models.RunnerJobLog:
    return models.RunnerJobLog(
        public_id=str(uuid4()),
        project_id=project.id,
        job_id=job.id,
        runner_id=runner.id,
        sequence_number=sequence_number,
        attempt_number=attempt_number,
        level=level,
        event_type=event_type,
        message=message,
        context_payload=(
            {}
            if context_payload is None
            else context_payload
        ),
    )


def test_postgres_persists_structured_runner_job_log(
    postgres_session: Session,
):
    project, runner, job = (
        _create_runner_job_log_context(
            postgres_session,
            "persistence",
        )
    )

    job_log = _build_test_runner_job_log(
        project=project,
        runner=runner,
        job=job,
        sequence_number=1,
        attempt_number=1,
        level="info",
        event_type="asr.transcription.started",
        message="ASR transcription started.",
        context_payload={
            "audio_count": 5,
            "model": "mock-local",
        },
    )

    postgres_session.add(job_log)
    postgres_session.flush()
    postgres_session.refresh(job_log)

    assert job_log.project_id == project.id
    assert job_log.job_id == job.id
    assert job_log.runner_id == runner.id
    assert job_log.sequence_number == 1
    assert job_log.attempt_number == 1
    assert job_log.level == "info"
    assert job_log.event_type == (
        "asr.transcription.started"
    )
    assert job_log.message == "ASR transcription started."
    assert job_log.context_payload == {
        "audio_count": 5,
        "model": "mock-local",
    }

    assert job_log.created_at.tzinfo is not None
    assert job_log.created_at.utcoffset() is not None


def test_postgres_allows_same_log_sequence_for_different_jobs(
    postgres_session: Session,
):
    project, runner, first_job = (
        _create_runner_job_log_context(
            postgres_session,
            "sequence-per-job",
        )
    )

    second_job = _create_log_test_job(
        postgres_session,
        project_id=project.id,
        runner_id=runner.id,
        suffix="sequence-second-job",
    )

    postgres_session.add_all(
        [
            _build_test_runner_job_log(
                project=project,
                runner=runner,
                job=first_job,
                sequence_number=1,
            ),
            _build_test_runner_job_log(
                project=project,
                runner=runner,
                job=second_job,
                sequence_number=1,
            ),
        ]
    )

    postgres_session.flush()


def test_postgres_rejects_duplicate_log_sequence_per_job(
    postgres_session: Session,
):
    project, runner, job = (
        _create_runner_job_log_context(
            postgres_session,
            "duplicate-sequence",
        )
    )

    first_log = _build_test_runner_job_log(
        project=project,
        runner=runner,
        job=job,
        sequence_number=1,
    )
    duplicate_log = _build_test_runner_job_log(
        project=project,
        runner=runner,
        job=job,
        sequence_number=1,
        message="Duplicate sequence.",
    )

    postgres_session.add(first_log)
    postgres_session.flush()

    postgres_session.add(duplicate_log)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


def test_postgres_enforces_log_job_project_ownership(
    postgres_session: Session,
):
    first_project, _, first_job = (
        _create_runner_job_log_context(
            postgres_session,
            "job-project-owner",
        )
    )
    second_project, second_runner, _ = (
        _create_runner_job_log_context(
            postgres_session,
            "job-project-other",
        )
    )

    invalid_log = _build_test_runner_job_log(
        project=second_project,
        runner=second_runner,
        job=first_job,
    )

    postgres_session.add(invalid_log)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()

    assert first_project.id != second_project.id


def test_postgres_enforces_log_runner_project_ownership(
    postgres_session: Session,
):
    first_project, _, first_job = (
        _create_runner_job_log_context(
            postgres_session,
            "runner-project-owner",
        )
    )
    _, second_runner, _ = (
        _create_runner_job_log_context(
            postgres_session,
            "runner-project-other",
        )
    )

    invalid_log = models.RunnerJobLog(
        public_id=str(uuid4()),
        project_id=first_project.id,
        job_id=first_job.id,
        runner_id=second_runner.id,
        sequence_number=1,
        attempt_number=1,
        level="info",
        event_type="job.progress",
        message="Invalid cross-project runner.",
        context_payload={},
    )

    postgres_session.add(invalid_log)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


@pytest.mark.parametrize(
    ("sequence_number", "attempt_number"),
    [
        (0, 1),
        (1, 0),
    ],
)
def test_postgres_enforces_positive_log_numbers(
    postgres_session: Session,
    sequence_number: int,
    attempt_number: int,
):
    project, runner, job = (
        _create_runner_job_log_context(
            postgres_session,
            f"positive-{sequence_number}-{attempt_number}",
        )
    )

    invalid_log = _build_test_runner_job_log(
        project=project,
        runner=runner,
        job=job,
        sequence_number=sequence_number,
        attempt_number=attempt_number,
    )

    postgres_session.add(invalid_log)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


def test_postgres_rejects_unknown_runner_job_log_level(
    postgres_session: Session,
):
    project, runner, job = (
        _create_runner_job_log_context(
            postgres_session,
            "invalid-level",
        )
    )

    invalid_log = _build_test_runner_job_log(
        project=project,
        runner=runner,
        job=job,
        level="critical",
    )

    postgres_session.add(invalid_log)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


@pytest.mark.parametrize(
    "message",
    [
        "",
        "x" * 10_001,
    ],
)
def test_postgres_enforces_runner_job_log_message_length(
    postgres_session: Session,
    message: str,
):
    project, runner, job = (
        _create_runner_job_log_context(
            postgres_session,
            f"message-{len(message)}",
        )
    )

    invalid_log = _build_test_runner_job_log(
        project=project,
        runner=runner,
        job=job,
        message=message,
    )

    postgres_session.add(invalid_log)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


def test_runner_job_log_is_deleted_with_parent_job(
    postgres_session: Session,
):
    project, runner, job = (
        _create_runner_job_log_context(
            postgres_session,
            "job-delete-cascade",
        )
    )

    job_log = _build_test_runner_job_log(
        project=project,
        runner=runner,
        job=job,
    )

    postgres_session.add(job_log)
    postgres_session.flush()

    log_id = job_log.id

    postgres_session.execute(
        text(
            "DELETE FROM runner_jobs "
            "WHERE id = :job_id"
        ),
        {"job_id": job.id},
    )
    postgres_session.flush()
    postgres_session.expire_all()

    assert (
        postgres_session.get(models.RunnerJobLog, log_id)
        is None
    )

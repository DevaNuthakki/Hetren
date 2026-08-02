from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from app import models


DEFAULT_OPERATIONS_JOB_LIMIT = 100
MAX_OPERATIONS_JOB_LIMIT = 200
DEFAULT_OPERATIONS_LOG_LIMIT = 100
MAX_OPERATIONS_LOG_LIMIT = 200


class RunnerOperationsServiceError(Exception):
    """Base error for runner operations reads."""


class RunnerOperationsProjectNotFoundError(
    RunnerOperationsServiceError
):
    """Raised when a project does not exist."""


class RunnerOperationsJobNotFoundError(
    RunnerOperationsServiceError
):
    """Raised when a project-scoped job does not exist."""


@dataclass(frozen=True)
class RunnerOperationsRunner:
    project_id: int
    public_id: str
    name: str
    status: str
    runner_version: str | None
    capabilities: tuple[str, ...]
    last_seen_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class RunnerOperationsJob:
    project_id: int
    public_id: str
    name: str
    job_type: str
    status: str
    priority: int
    required_capabilities: tuple[str, ...]
    assigned_runner_public_id: str | None
    assigned_runner_name: str | None
    attempt_count: int
    max_attempts: int
    error_message: str | None
    available_at: datetime
    claimed_at: datetime | None
    lease_expires_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    failed_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class RunnerOperationsSnapshot:
    project_id: int
    runners: tuple[RunnerOperationsRunner, ...]
    jobs: tuple[RunnerOperationsJob, ...]


@dataclass(frozen=True)
class RunnerOperationsLog:
    public_id: str
    sequence_number: int
    attempt_number: int
    level: str
    event_type: str
    message: str
    created_at: datetime


@dataclass(frozen=True)
class RunnerOperationsLogPage:
    project_id: int
    job_public_id: str
    logs: tuple[RunnerOperationsLog, ...]
    has_more: bool
    next_after_sequence: int | None


def _validate_project_id(project_id: int) -> int:
    if (
        isinstance(project_id, bool)
        or not isinstance(project_id, int)
        or project_id < 1
    ):
        raise ValueError("Project ID must be a positive integer.")

    return project_id


def _validate_limit(
    limit: int,
    *,
    maximum: int,
    field_name: str,
) -> int:
    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or limit < 1
        or limit > maximum
    ):
        raise ValueError(
            f"{field_name} must be between 1 and {maximum}."
        )

    return limit


def _validate_after_sequence(after_sequence: int) -> int:
    if (
        isinstance(after_sequence, bool)
        or not isinstance(after_sequence, int)
        or after_sequence < 0
    ):
        raise ValueError(
            "After sequence must be a non-negative integer."
        )

    return after_sequence


def _normalize_job_public_id(job_public_id: str) -> str:
    if not isinstance(job_public_id, str):
        raise ValueError("Runner job public ID must be text.")

    normalized = job_public_id.strip()

    if not normalized or len(normalized) > 36:
        raise ValueError(
            "Runner job public ID must contain between 1 and 36 "
            "characters."
        )

    return normalized


def _require_project(
    db: Session,
    *,
    project_id: int,
) -> None:
    project_exists = (
        db.query(models.Project.id)
        .filter(models.Project.id == project_id)
        .first()
    )

    if project_exists is None:
        raise RunnerOperationsProjectNotFoundError(
            f"Project {project_id} was not found."
        )


def get_project_runner_operations(
    db: Session,
    *,
    project_id: int,
    job_limit: int = DEFAULT_OPERATIONS_JOB_LIMIT,
) -> RunnerOperationsSnapshot:
    validated_project_id = _validate_project_id(project_id)
    validated_job_limit = _validate_limit(
        job_limit,
        maximum=MAX_OPERATIONS_JOB_LIMIT,
        field_name="Job limit",
    )

    _require_project(
        db,
        project_id=validated_project_id,
    )

    runners = (
        db.query(models.Runner)
        .filter(
            models.Runner.project_id
            == validated_project_id
        )
        .order_by(
            models.Runner.created_at.desc(),
            models.Runner.id.desc(),
        )
        .all()
    )

    jobs = (
        db.query(models.RunnerJob)
        .options(
            joinedload(
                models.RunnerJob.assigned_runner
            )
        )
        .filter(
            models.RunnerJob.project_id
            == validated_project_id
        )
        .order_by(
            models.RunnerJob.created_at.desc(),
            models.RunnerJob.id.desc(),
        )
        .limit(validated_job_limit)
        .all()
    )

    safe_runners = tuple(
        RunnerOperationsRunner(
            project_id=runner.project_id,
            public_id=runner.public_id,
            name=runner.name,
            status=runner.status,
            runner_version=runner.runner_version,
            capabilities=tuple(
                runner.capabilities or []
            ),
            last_seen_at=runner.last_seen_at,
            revoked_at=runner.revoked_at,
            created_at=runner.created_at,
            updated_at=runner.updated_at,
        )
        for runner in runners
    )

    safe_jobs = tuple(
        RunnerOperationsJob(
            project_id=job.project_id,
            public_id=job.public_id,
            name=job.name,
            job_type=job.job_type,
            status=job.status,
            priority=job.priority,
            required_capabilities=tuple(
                job.required_capabilities or []
            ),
            assigned_runner_public_id=(
                job.assigned_runner.public_id
                if job.assigned_runner is not None
                else None
            ),
            assigned_runner_name=(
                job.assigned_runner.name
                if job.assigned_runner is not None
                else None
            ),
            attempt_count=job.attempt_count,
            max_attempts=job.max_attempts,
            error_message=job.error_message,
            available_at=job.available_at,
            claimed_at=job.claimed_at,
            lease_expires_at=job.lease_expires_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            failed_at=job.failed_at,
            cancelled_at=job.cancelled_at,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )
        for job in jobs
    )

    return RunnerOperationsSnapshot(
        project_id=validated_project_id,
        runners=safe_runners,
        jobs=safe_jobs,
    )


def get_project_runner_job_logs(
    db: Session,
    *,
    project_id: int,
    job_public_id: str,
    after_sequence: int = 0,
    limit: int = DEFAULT_OPERATIONS_LOG_LIMIT,
) -> RunnerOperationsLogPage:
    validated_project_id = _validate_project_id(project_id)
    normalized_job_public_id = _normalize_job_public_id(
        job_public_id
    )
    validated_after_sequence = _validate_after_sequence(
        after_sequence
    )
    validated_limit = _validate_limit(
        limit,
        maximum=MAX_OPERATIONS_LOG_LIMIT,
        field_name="Log limit",
    )

    _require_project(
        db,
        project_id=validated_project_id,
    )

    job = (
        db.query(models.RunnerJob)
        .filter(
            models.RunnerJob.project_id
            == validated_project_id,
            models.RunnerJob.public_id
            == normalized_job_public_id,
        )
        .first()
    )

    if job is None:
        raise RunnerOperationsJobNotFoundError(
            "Runner job was not found in this project."
        )

    rows = (
        db.query(models.RunnerJobLog)
        .filter(
            models.RunnerJobLog.project_id
            == validated_project_id,
            models.RunnerJobLog.job_id == job.id,
            models.RunnerJobLog.sequence_number
            > validated_after_sequence,
        )
        .order_by(
            models.RunnerJobLog.sequence_number.asc()
        )
        .limit(validated_limit + 1)
        .all()
    )

    has_more = len(rows) > validated_limit
    selected_rows = rows[:validated_limit]

    safe_logs = tuple(
        RunnerOperationsLog(
            public_id=log.public_id,
            sequence_number=log.sequence_number,
            attempt_number=log.attempt_number,
            level=log.level,
            event_type=log.event_type,
            message=log.message,
            created_at=log.created_at,
        )
        for log in selected_rows
    )

    next_after_sequence = (
        safe_logs[-1].sequence_number
        if safe_logs
        else None
    )

    return RunnerOperationsLogPage(
        project_id=validated_project_id,
        job_public_id=normalized_job_public_id,
        logs=safe_logs,
        has_more=has_more,
        next_after_sequence=next_after_sequence,
    )

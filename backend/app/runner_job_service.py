import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.runner_security import (
    generate_job_claim_token,
    hash_job_claim_token,
    hash_runner_credential,
    verify_job_claim_token,
)
from app.runner_service import RunnerAuthenticationError


DEFAULT_JOB_LEASE_DURATION = timedelta(minutes=5)
MAX_JOB_LEASE_DURATION = timedelta(hours=1)
MAX_JOB_CLAIM_CANDIDATES = 50
MAX_EXPIRED_JOB_RECOVERY_BATCH = 1000

SUPPORTED_RUNNER_JOB_TYPES = frozenset(
    {
        "asr_evaluation",
    }
)
MIN_RUNNER_JOB_PRIORITY = -1000
MAX_RUNNER_JOB_PRIORITY = 1000
MAX_RUNNER_JOB_ATTEMPTS = 100
MAX_RUNNER_JOB_CAPABILITIES = 50
MAX_RUNNER_JOB_INPUT_BYTES = 262_144


class RunnerJobServiceError(Exception):
    """Base exception for runner-job coordination operations."""


class RunnerJobClaimConflictError(RunnerJobServiceError):
    """Raised when a selected job cannot be claimed."""


class RunnerJobClaimUnavailableError(RunnerJobServiceError):
    """Raised when claim ownership cannot be verified."""



class RunnerJobTransitionUnavailableError(
    RunnerJobServiceError
):
    """Raised when a job cannot perform a requested transition."""



class RunnerJobProjectNotFoundError(RunnerJobServiceError):
    """Raised when a runner job references a missing project."""


class RunnerJobNotFoundError(RunnerJobServiceError):
    """Raised when an administrative job lookup fails."""


class RunnerJobEnqueueConflictError(RunnerJobServiceError):
    """Raised when a runner job cannot be enqueued."""


class RunnerJobCancellationUnavailableError(
    RunnerJobServiceError
):
    """Raised when a runner job cannot be cancelled."""


@dataclass(frozen=True)
class ClaimedRunnerJob:
    claim_token: str
    job: models.RunnerJob



@dataclass(frozen=True)
class RunnerJobRecoverySummary:
    requeued_count: int
    failed_count: int

    @property
    def recovered_count(self) -> int:
        return self.requeued_count + self.failed_count


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)

    return value.astimezone(UTC)


def _resolve_now(value: datetime | None) -> datetime:
    if value is None:
        return _utc_now()

    return _as_utc(value)


def _validate_lease_duration(
    lease_duration: timedelta,
) -> timedelta:
    if lease_duration <= timedelta(0):
        raise ValueError(
            "Runner job lease duration must be greater than zero."
        )

    if lease_duration > MAX_JOB_LEASE_DURATION:
        raise ValueError(
            "Runner job lease duration must not exceed one hour."
        )

    return lease_duration



def _validate_recovery_limit(limit: int) -> int:
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise ValueError(
            "Runner job recovery limit must be an integer."
        )

    if limit < 1:
        raise ValueError(
            "Runner job recovery limit must be at least one."
        )

    if limit > MAX_EXPIRED_JOB_RECOVERY_BATCH:
        raise ValueError(
            "Runner job recovery limit must not exceed 1000."
        )

    return limit


def _capability_set(
    values: object,
) -> set[str] | None:
    if not isinstance(values, list):
        return None

    normalized: set[str] = set()

    for value in values:
        if not isinstance(value, str):
            return None

        capability = value.strip()

        if not capability:
            return None

        normalized.add(capability)

    return normalized


def _runner_supports_job(
    runner: models.Runner,
    job: models.RunnerJob,
) -> bool:
    runner_capabilities = _capability_set(
        runner.capabilities
    )
    required_capabilities = _capability_set(
        job.required_capabilities
    )

    if (
        runner_capabilities is None
        or required_capabilities is None
    ):
        return False

    return required_capabilities.issubset(
        runner_capabilities
    )


def _get_active_runner_for_update(
    db: Session,
    *,
    credential: str,
) -> models.Runner:
    if not credential:
        db.rollback()
        raise RunnerAuthenticationError(
            "Runner credential is invalid or unavailable."
        )

    credential_hash = hash_runner_credential(credential)

    runner = (
        db.query(models.Runner)
        .filter(
            models.Runner.credential_hash
            == credential_hash
        )
        .with_for_update()
        .first()
    )

    runner_is_unavailable = (
        runner is None
        or runner.status != "active"
        or runner.revoked_at is not None
    )

    if runner_is_unavailable:
        db.rollback()
        raise RunnerAuthenticationError(
            "Runner credential is invalid or unavailable."
        )

    return runner


def claim_next_job(
    db: Session,
    *,
    credential: str,
    lease_duration: timedelta = DEFAULT_JOB_LEASE_DURATION,
    now: datetime | None = None,
) -> ClaimedRunnerJob | None:
    """
    Atomically claim the next compatible queued job.

    The runner and candidate jobs are locked during selection. PostgreSQL
    uses SKIP LOCKED so concurrent runners cannot claim the same job.

    The plaintext claim token is returned once. Only its digest is stored.
    This operation owns its database transaction.
    """
    validated_lease_duration = _validate_lease_duration(
        lease_duration
    )
    claim_time = _resolve_now(now)

    runner = _get_active_runner_for_update(
        db,
        credential=credential,
    )

    candidate_jobs = (
        db.query(models.RunnerJob)
        .filter(
            models.RunnerJob.project_id
            == runner.project_id,
            models.RunnerJob.status == "queued",
            models.RunnerJob.available_at
            <= claim_time,
            models.RunnerJob.attempt_count
            < models.RunnerJob.max_attempts,
        )
        .order_by(
            models.RunnerJob.priority.desc(),
            models.RunnerJob.available_at.asc(),
            models.RunnerJob.id.asc(),
        )
        .with_for_update(skip_locked=True)
        .limit(MAX_JOB_CLAIM_CANDIDATES)
        .all()
    )

    selected_job = next(
        (
            job
            for job in candidate_jobs
            if _runner_supports_job(runner, job)
        ),
        None,
    )

    if selected_job is None:
        db.rollback()
        return None

    plaintext_claim_token = generate_job_claim_token()

    selected_job.status = "claimed"
    selected_job.assigned_runner_id = runner.id
    selected_job.claimed_at = claim_time
    selected_job.lease_expires_at = (
        claim_time + validated_lease_duration
    )
    selected_job.claim_token_hash = hash_job_claim_token(
        plaintext_claim_token
    )
    selected_job.attempt_count += 1

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise RunnerJobClaimConflictError(
            "Runner job could not be claimed."
        ) from exc

    db.refresh(selected_job)

    return ClaimedRunnerJob(
        claim_token=plaintext_claim_token,
        job=selected_job,
    )


def _normalize_result_payload(
    result_payload: dict[str, object] | None,
) -> dict[str, object]:
    if result_payload is None:
        return {}

    if not isinstance(result_payload, dict):
        raise ValueError(
            "Runner job result payload must be a JSON object."
        )

    try:
        json.dumps(result_payload)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Runner job result payload must contain "
            "JSON-serializable values."
        ) from exc

    return dict(result_payload)


def _normalize_error_message(error_message: str) -> str:
    if not isinstance(error_message, str):
        raise ValueError(
            "Runner job error message must be text."
        )

    normalized = error_message.strip()

    if not normalized:
        raise ValueError(
            "Runner job error message must not be empty."
        )

    if len(normalized) > 10_000:
        raise ValueError(
            "Runner job error message must be at most "
            "10000 characters."
        )

    return normalized


def _get_owned_job_claim_for_update(
    db: Session,
    *,
    credential: str,
    job_public_id: str,
    claim_token: str,
    now: datetime,
) -> models.RunnerJob:
    runner = _get_active_runner_for_update(
        db,
        credential=credential,
    )

    normalized_public_id = (
        job_public_id.strip()
        if isinstance(job_public_id, str)
        else ""
    )

    if (
        not normalized_public_id
        or len(normalized_public_id) > 36
        or not claim_token
    ):
        db.rollback()
        raise RunnerJobClaimUnavailableError(
            "Runner job claim is invalid or unavailable."
        )

    job = (
        db.query(models.RunnerJob)
        .filter(
            models.RunnerJob.public_id
            == normalized_public_id,
            models.RunnerJob.project_id
            == runner.project_id,
        )
        .with_for_update()
        .first()
    )

    claim_is_unavailable = (
        job is None
        or job.assigned_runner_id != runner.id
        or job.status not in {"claimed", "running"}
        or job.lease_expires_at is None
        or _as_utc(job.lease_expires_at) <= now
        or job.claim_token_hash is None
        or not verify_job_claim_token(
            claim_token,
            job.claim_token_hash,
        )
    )

    if claim_is_unavailable:
        db.rollback()
        raise RunnerJobClaimUnavailableError(
            "Runner job claim is invalid or unavailable."
        )

    return job


def _commit_job_transition(
    db: Session,
    *,
    job: models.RunnerJob,
) -> models.RunnerJob:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise RunnerJobTransitionUnavailableError(
            "Runner job transition is invalid or unavailable."
        ) from exc

    db.refresh(job)
    return job


def verify_job_claim_ownership(
    db: Session,
    *,
    credential: str,
    job_public_id: str,
    claim_token: str,
    now: datetime | None = None,
) -> models.RunnerJob:
    """
    Verify that an active runner owns a valid, unexpired job claim.

    Errors intentionally use one generic message so callers cannot inspect
    whether the job, assignment, claim token, or lease was invalid.
    """
    verification_time = _resolve_now(now)

    job = _get_owned_job_claim_for_update(
        db,
        credential=credential,
        job_public_id=job_public_id,
        claim_token=claim_token,
        now=verification_time,
    )

    db.commit()
    db.refresh(job)
    return job


def start_job(
    db: Session,
    *,
    credential: str,
    job_public_id: str,
    claim_token: str,
    now: datetime | None = None,
) -> models.RunnerJob:
    """
    Transition an owned job from claimed to running.

    The same claim token remains valid until the job reaches a terminal
    state or its lease expires.
    """
    start_time = _resolve_now(now)

    job = _get_owned_job_claim_for_update(
        db,
        credential=credential,
        job_public_id=job_public_id,
        claim_token=claim_token,
        now=start_time,
    )

    if job.status != "claimed":
        db.rollback()
        raise RunnerJobTransitionUnavailableError(
            "Runner job transition is invalid or unavailable."
        )

    job.status = "running"
    job.started_at = start_time

    return _commit_job_transition(
        db,
        job=job,
    )


def complete_job(
    db: Session,
    *,
    credential: str,
    job_public_id: str,
    claim_token: str,
    result_payload: dict[str, object] | None = None,
    now: datetime | None = None,
) -> models.RunnerJob:
    """
    Transition an owned running job to completed.

    Terminal transitions remove the stored claim digest and lease so the
    old claim token cannot be reused.
    """
    normalized_result = _normalize_result_payload(
        result_payload
    )
    completion_time = _resolve_now(now)

    job = _get_owned_job_claim_for_update(
        db,
        credential=credential,
        job_public_id=job_public_id,
        claim_token=claim_token,
        now=completion_time,
    )

    if job.status != "running":
        db.rollback()
        raise RunnerJobTransitionUnavailableError(
            "Runner job transition is invalid or unavailable."
        )

    job.status = "completed"
    job.completed_at = completion_time
    job.lease_expires_at = None
    job.claim_token_hash = None
    job.result_payload = normalized_result
    job.error_message = None

    return _commit_job_transition(
        db,
        job=job,
    )


def fail_job(
    db: Session,
    *,
    credential: str,
    job_public_id: str,
    claim_token: str,
    error_message: str,
    now: datetime | None = None,
) -> models.RunnerJob:
    """
    Transition an owned claimed or running job to failed.

    A job may fail before start when runner setup or input preparation
    cannot begin.
    """
    normalized_error = _normalize_error_message(
        error_message
    )
    failure_time = _resolve_now(now)

    job = _get_owned_job_claim_for_update(
        db,
        credential=credential,
        job_public_id=job_public_id,
        claim_token=claim_token,
        now=failure_time,
    )

    job.status = "failed"
    job.failed_at = failure_time
    job.lease_expires_at = None
    job.claim_token_hash = None
    job.result_payload = None
    job.error_message = normalized_error

    return _commit_job_transition(
        db,
        job=job,
    )


def renew_job_lease(
    db: Session,
    *,
    credential: str,
    job_public_id: str,
    claim_token: str,
    lease_duration: timedelta = DEFAULT_JOB_LEASE_DURATION,
    now: datetime | None = None,
) -> models.RunnerJob:
    """
    Renew an active claimed or running job lease.

    Renewing early never shortens an existing lease. The current claim
    token remains valid and is not rotated.
    """
    validated_duration = _validate_lease_duration(
        lease_duration
    )
    renewal_time = _resolve_now(now)

    job = _get_owned_job_claim_for_update(
        db,
        credential=credential,
        job_public_id=job_public_id,
        claim_token=claim_token,
        now=renewal_time,
    )

    requested_expiry = renewal_time + validated_duration
    current_expiry = _as_utc(job.lease_expires_at)

    job.lease_expires_at = max(
        current_expiry,
        requested_expiry,
    )

    return _commit_job_transition(
        db,
        job=job,
    )


def recover_expired_jobs(
    db: Session,
    *,
    now: datetime | None = None,
    limit: int = 100,
) -> RunnerJobRecoverySummary:
    """
    Recover jobs whose runner lease has expired.

    Jobs with attempts remaining return to the queue. Jobs that have
    exhausted their attempts become failed. SKIP LOCKED allows multiple
    recovery workers to run safely without processing the same rows.
    """
    validated_limit = _validate_recovery_limit(limit)
    recovery_time = _resolve_now(now)

    expired_jobs = (
        db.query(models.RunnerJob)
        .filter(
            models.RunnerJob.status.in_(
                ["claimed", "running"]
            ),
            models.RunnerJob.lease_expires_at.is_not(None),
            models.RunnerJob.lease_expires_at
            <= recovery_time,
        )
        .order_by(
            models.RunnerJob.lease_expires_at.asc(),
            models.RunnerJob.id.asc(),
        )
        .with_for_update(skip_locked=True)
        .limit(validated_limit)
        .all()
    )

    if not expired_jobs:
        db.rollback()
        return RunnerJobRecoverySummary(
            requeued_count=0,
            failed_count=0,
        )

    requeued_count = 0
    failed_count = 0

    for job in expired_jobs:
        job.lease_expires_at = None
        job.claim_token_hash = None
        job.result_payload = None

        if job.attempt_count < job.max_attempts:
            job.status = "queued"
            job.assigned_runner_id = None
            job.claimed_at = None
            job.started_at = None
            job.completed_at = None
            job.failed_at = None
            job.cancelled_at = None
            job.error_message = None
            job.available_at = recovery_time
            requeued_count += 1
        else:
            job.status = "failed"
            job.completed_at = None
            job.failed_at = recovery_time
            job.cancelled_at = None
            job.error_message = (
                "Runner job lease expired after maximum "
                "attempts."
            )
            failed_count += 1

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise RunnerJobTransitionUnavailableError(
            "Expired runner jobs could not be recovered."
        ) from exc

    return RunnerJobRecoverySummary(
        requeued_count=requeued_count,
        failed_count=failed_count,
    )


def _normalize_job_text(
    value: str,
    *,
    field_name: str,
    max_length: int,
) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be text.")

    normalized = value.strip()

    if not normalized:
        raise ValueError(f"{field_name} must not be empty.")

    if len(normalized) > max_length:
        raise ValueError(
            f"{field_name} must be at most "
            f"{max_length} characters."
        )

    return normalized


def _normalize_job_type(job_type: str) -> str:
    normalized = _normalize_job_text(
        job_type,
        field_name="Runner job type",
        max_length=100,
    ).lower()

    if normalized not in SUPPORTED_RUNNER_JOB_TYPES:
        supported_types = ", ".join(
            sorted(SUPPORTED_RUNNER_JOB_TYPES)
        )
        raise ValueError(
            "Unsupported runner job type. "
            f"Supported types: {supported_types}."
        )

    return normalized


def _normalize_required_capabilities(
    capabilities: list[str] | None,
) -> list[str]:
    if capabilities is None:
        return []

    if not isinstance(capabilities, list):
        raise ValueError(
            "Runner job capabilities must be a list."
        )

    if len(capabilities) > MAX_RUNNER_JOB_CAPABILITIES:
        raise ValueError(
            "Runner job capabilities must contain at most "
            "50 values."
        )

    normalized: list[str] = []

    for capability in capabilities:
        capability_name = _normalize_job_text(
            capability,
            field_name="Runner job capability",
            max_length=100,
        )

        if capability_name not in normalized:
            normalized.append(capability_name)

    return normalized


def _normalize_input_payload(
    input_payload: dict[str, object] | None,
) -> dict[str, object]:
    if input_payload is None:
        return {}

    if not isinstance(input_payload, dict):
        raise ValueError(
            "Runner job input payload must be a JSON object."
        )

    try:
        serialized = json.dumps(
            input_payload,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Runner job input payload must contain "
            "JSON-serializable values."
        ) from exc

    if len(serialized.encode("utf-8")) > MAX_RUNNER_JOB_INPUT_BYTES:
        raise ValueError(
            "Runner job input payload must not exceed "
            "262144 bytes."
        )

    return dict(input_payload)


def _validate_job_priority(priority: int) -> int:
    if isinstance(priority, bool) or not isinstance(priority, int):
        raise ValueError(
            "Runner job priority must be an integer."
        )

    if not (
        MIN_RUNNER_JOB_PRIORITY
        <= priority
        <= MAX_RUNNER_JOB_PRIORITY
    ):
        raise ValueError(
            "Runner job priority must be between "
            "-1000 and 1000."
        )

    return priority


def _validate_max_attempts(max_attempts: int) -> int:
    if (
        isinstance(max_attempts, bool)
        or not isinstance(max_attempts, int)
    ):
        raise ValueError(
            "Runner job maximum attempts must be an integer."
        )

    if not 1 <= max_attempts <= MAX_RUNNER_JOB_ATTEMPTS:
        raise ValueError(
            "Runner job maximum attempts must be between "
            "1 and 100."
        )

    return max_attempts


def enqueue_job(
    db: Session,
    *,
    project_id: int,
    name: str,
    job_type: str,
    required_capabilities: list[str] | None = None,
    input_payload: dict[str, object] | None = None,
    priority: int = 0,
    available_at: datetime | None = None,
    max_attempts: int = 3,
    now: datetime | None = None,
) -> models.RunnerJob:
    """
    Create a validated project-scoped runner job.

    Job types are explicitly allowlisted. Input payloads are stored as
    inert structured data; this operation does not execute commands,
    shell content, or user-provided code.
    """
    if (
        isinstance(project_id, bool)
        or not isinstance(project_id, int)
        or project_id < 1
    ):
        raise ValueError(
            "Runner job project ID must be a positive integer."
        )

    normalized_name = _normalize_job_text(
        name,
        field_name="Runner job name",
        max_length=200,
    )
    normalized_job_type = _normalize_job_type(job_type)
    normalized_capabilities = (
        _normalize_required_capabilities(
            required_capabilities
        )
    )
    normalized_input = _normalize_input_payload(
        input_payload
    )
    validated_priority = _validate_job_priority(priority)
    validated_max_attempts = _validate_max_attempts(
        max_attempts
    )

    enqueued_at = _resolve_now(now)
    availability_time = (
        enqueued_at
        if available_at is None
        else _as_utc(available_at)
    )

    project_exists = (
        db.query(models.Project.id)
        .filter(models.Project.id == project_id)
        .first()
    )

    if project_exists is None:
        db.rollback()
        raise RunnerJobProjectNotFoundError(
            f"Project {project_id} was not found."
        )

    job = models.RunnerJob(
        public_id=str(uuid4()),
        project_id=project_id,
        name=normalized_name,
        job_type=normalized_job_type,
        status="queued",
        priority=validated_priority,
        required_capabilities=normalized_capabilities,
        input_payload=normalized_input,
        attempt_count=0,
        max_attempts=validated_max_attempts,
        available_at=availability_time,
    )

    db.add(job)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise RunnerJobEnqueueConflictError(
            "Runner job could not be enqueued."
        ) from exc

    db.refresh(job)
    return job


def cancel_job(
    db: Session,
    *,
    job_public_id: str,
    now: datetime | None = None,
) -> models.RunnerJob:
    """
    Administratively cancel a queued, claimed, or running job.

    Cancellation invalidates an active claim token and lease. Existing
    runner assignment and start timestamps are preserved for audit
    history when the job had already been claimed.
    """
    normalized_public_id = _normalize_job_text(
        job_public_id,
        field_name="Runner job public ID",
        max_length=36,
    )
    cancellation_time = _resolve_now(now)

    job = (
        db.query(models.RunnerJob)
        .filter(
            models.RunnerJob.public_id
            == normalized_public_id
        )
        .with_for_update()
        .first()
    )

    if job is None:
        db.rollback()
        raise RunnerJobNotFoundError(
            f"Runner job {normalized_public_id!r} "
            "was not found."
        )

    if job.status == "cancelled":
        db.commit()
        db.refresh(job)
        return job

    if job.status in {"completed", "failed"}:
        db.rollback()
        raise RunnerJobCancellationUnavailableError(
            "Runner job cannot be cancelled from its "
            "current state."
        )

    job.status = "cancelled"
    job.cancelled_at = cancellation_time
    job.lease_expires_at = None
    job.claim_token_hash = None
    job.completed_at = None
    job.failed_at = None
    job.result_payload = None
    job.error_message = None

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise RunnerJobCancellationUnavailableError(
            "Runner job could not be cancelled."
        ) from exc

    db.refresh(job)
    return job

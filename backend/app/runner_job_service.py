import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

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


@dataclass(frozen=True)
class ClaimedRunnerJob:
    claim_token: str
    job: models.RunnerJob


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

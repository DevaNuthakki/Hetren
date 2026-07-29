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
    whether the job, runner assignment, claim token, or lease was invalid.
    This operation owns its database transaction.
    """
    verification_time = _resolve_now(now)

    runner = _get_active_runner_for_update(
        db,
        credential=credential,
    )

    normalized_public_id = job_public_id.strip()

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
        or _as_utc(job.lease_expires_at)
        <= verification_time
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

    db.commit()
    db.refresh(job)

    return job

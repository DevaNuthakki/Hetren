import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.runner_security import (
    generate_registration_token,
    generate_runner_credential,
    hash_registration_token,
    hash_runner_credential,
)


DEFAULT_REGISTRATION_TOKEN_TTL = timedelta(minutes=30)


class RunnerServiceError(Exception):
    """Base exception for runner-registration operations."""


class RunnerProjectNotFoundError(RunnerServiceError):
    """Raised when a runner operation references a missing project."""


class RegistrationTokenUnavailableError(RunnerServiceError):
    """Raised when a registration token cannot be used."""


class RunnerRegistrationConflictError(RunnerServiceError):
    """Raised when runner identity conflicts with an existing runner."""


class RunnerAuthenticationError(RunnerServiceError):
    """Raised when a runner credential cannot authenticate a runner."""


class RunnerNotFoundError(RunnerServiceError):
    """Raised when an administrative runner lookup fails."""


@dataclass(frozen=True)
class IssuedRegistrationToken:
    token: str
    record: models.RunnerRegistrationToken


@dataclass(frozen=True)
class RegisteredRunner:
    credential: str
    runner: models.Runner


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


def _normalize_required_text(
    value: str,
    *,
    field_name: str,
    max_length: int,
) -> str:
    normalized = value.strip()

    if not normalized:
        raise ValueError(f"{field_name} must not be empty.")

    if len(normalized) > max_length:
        raise ValueError(
            f"{field_name} must be at most {max_length} characters."
        )

    return normalized


def _normalize_optional_text(
    value: str | None,
    *,
    field_name: str,
    max_length: int,
) -> str | None:
    if value is None:
        return None

    normalized = value.strip()

    if not normalized:
        return None

    if len(normalized) > max_length:
        raise ValueError(
            f"{field_name} must be at most {max_length} characters."
        )

    return normalized


def _normalize_capabilities(
    capabilities: list[str] | None,
) -> list[str]:
    if capabilities is None:
        return []

    normalized: list[str] = []

    for capability in capabilities:
        if not isinstance(capability, str):
            raise ValueError(
                "Runner capabilities must contain only strings."
            )

        capability_name = capability.strip()

        if not capability_name:
            raise ValueError(
                "Runner capabilities must not contain empty values."
            )

        if len(capability_name) > 100:
            raise ValueError(
                "Each runner capability must be at most 100 characters."
            )

        if capability_name not in normalized:
            normalized.append(capability_name)

    return normalized


def _normalize_system_info(
    system_info: dict[str, object] | None,
) -> dict[str, object]:
    if system_info is None:
        return {}

    if not isinstance(system_info, dict):
        raise ValueError("Runner system_info must be a JSON object.")

    try:
        json.dumps(system_info)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Runner system_info must contain JSON-serializable values."
        ) from exc

    return dict(system_info)


def issue_registration_token(
    db: Session,
    *,
    project_id: int,
    label: str = "Runner registration token",
    ttl: timedelta = DEFAULT_REGISTRATION_TOKEN_TTL,
    now: datetime | None = None,
) -> IssuedRegistrationToken:
    """
    Create a one-time runner registration token.

    The plaintext token is returned once. Only its digest is persisted.
    This operation owns its database transaction.
    """
    if ttl <= timedelta(0):
        raise ValueError(
            "Registration token TTL must be greater than zero."
        )

    normalized_label = _normalize_required_text(
        label,
        field_name="Registration token label",
        max_length=200,
    )

    project_exists = (
        db.query(models.Project.id)
        .filter(models.Project.id == project_id)
        .first()
    )

    if project_exists is None:
        db.rollback()
        raise RunnerProjectNotFoundError(
            f"Project {project_id} was not found."
        )

    issued_at = _resolve_now(now)
    plaintext_token = generate_registration_token()

    token_record = models.RunnerRegistrationToken(
        project_id=project_id,
        label=normalized_label,
        token_hash=hash_registration_token(plaintext_token),
        created_at=issued_at,
        expires_at=issued_at + ttl,
    )

    db.add(token_record)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise

    db.refresh(token_record)

    return IssuedRegistrationToken(
        token=plaintext_token,
        record=token_record,
    )


def register_runner(
    db: Session,
    *,
    registration_token: str,
    name: str,
    runner_version: str | None = None,
    capabilities: list[str] | None = None,
    system_info: dict[str, object] | None = None,
    now: datetime | None = None,
) -> RegisteredRunner:
    """
    Atomically consume a one-time token and create a runner identity.

    The plaintext runner credential is returned once. Only its digest is
    persisted. This operation owns its database transaction.
    """
    normalized_name = _normalize_required_text(
        name,
        field_name="Runner name",
        max_length=200,
    )
    normalized_version = _normalize_optional_text(
        runner_version,
        field_name="Runner version",
        max_length=100,
    )
    normalized_capabilities = _normalize_capabilities(capabilities)
    normalized_system_info = _normalize_system_info(system_info)

    if not registration_token:
        raise RegistrationTokenUnavailableError(
            "Registration token is invalid or unavailable."
        )

    registration_token_hash = hash_registration_token(
        registration_token
    )
    registration_time = _resolve_now(now)

    token_record = (
        db.query(models.RunnerRegistrationToken)
        .filter(
            models.RunnerRegistrationToken.token_hash
            == registration_token_hash
        )
        .with_for_update()
        .first()
    )

    token_is_unavailable = (
        token_record is None
        or token_record.consumed_at is not None
        or token_record.revoked_at is not None
        or _as_utc(token_record.expires_at) <= registration_time
    )

    if token_is_unavailable:
        db.rollback()
        raise RegistrationTokenUnavailableError(
            "Registration token is invalid or unavailable."
        )

    plaintext_credential = generate_runner_credential()

    runner = models.Runner(
        project_id=token_record.project_id,
        registration_token_id=token_record.id,
        public_id=str(uuid4()),
        name=normalized_name,
        status="active",
        runner_version=normalized_version,
        capabilities=normalized_capabilities,
        system_info=normalized_system_info,
        credential_hash=hash_runner_credential(
            plaintext_credential
        ),
    )

    token_record.consumed_at = registration_time
    db.add(runner)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise RunnerRegistrationConflictError(
            "Runner registration conflicts with an existing runner."
        ) from exc

    db.refresh(runner)

    return RegisteredRunner(
        credential=plaintext_credential,
        runner=runner,
    )

def record_runner_heartbeat(
    db: Session,
    *,
    credential: str,
    runner_version: str | None = None,
    capabilities: list[str] | None = None,
    system_info: dict[str, object] | None = None,
    now: datetime | None = None,
) -> models.Runner:
    """
    Authenticate a runner and record its latest heartbeat.

    Optional metadata is updated only when supplied. This operation owns
    its database transaction.
    """
    if not credential:
        raise RunnerAuthenticationError(
            "Runner credential is invalid or unavailable."
        )

    credential_hash = hash_runner_credential(credential)
    heartbeat_time = _resolve_now(now)

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

    if runner_version is not None:
        runner.runner_version = _normalize_optional_text(
            runner_version,
            field_name="Runner version",
            max_length=100,
        )

    if capabilities is not None:
        normalized_capabilities = _normalize_capabilities(
            capabilities
        )

        if not set(normalized_capabilities).issubset(
            set(runner.capabilities or [])
        ):
            db.rollback()
            raise ValueError(
                "Runner heartbeat cannot grant new capabilities."
            )

        runner.capabilities = normalized_capabilities

    if system_info is not None:
        runner.system_info = _normalize_system_info(
            system_info
        )

    runner.last_seen_at = heartbeat_time

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise

    db.refresh(runner)
    return runner

def revoke_runner(
    db: Session,
    *,
    public_id: str,
    now: datetime | None = None,
) -> models.Runner:
    """
    Revoke a runner identity and invalidate its credential.

    The operation is idempotent: revoking an already-revoked runner
    preserves its original revocation timestamp.
    """
    normalized_public_id = _normalize_required_text(
        public_id,
        field_name="Runner public ID",
        max_length=36,
    )

    runner = (
        db.query(models.Runner)
        .filter(models.Runner.public_id == normalized_public_id)
        .with_for_update()
        .first()
    )

    if runner is None:
        db.rollback()
        raise RunnerNotFoundError(
            f"Runner {normalized_public_id!r} was not found."
        )

    if runner.status == "revoked":
        db.commit()
        db.refresh(runner)
        return runner

    runner.status = "revoked"
    runner.revoked_at = _resolve_now(now)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise

    db.refresh(runner)
    return runner

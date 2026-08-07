from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app import models
from app.auth.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)


@dataclass(frozen=True)
class IssuedTokenPair:
    access_token: str
    refresh_token: str


class InvalidCredentialsError(ValueError):
    """Raised when human login credentials cannot be accepted."""


class InvalidRefreshTokenError(ValueError):
    """Raised when a refresh token cannot be used."""


class RefreshTokenReuseError(InvalidRefreshTokenError):
    """Raised when a previously rotated refresh token is reused."""


# Verifying a real Argon2 hash even when the user does not exist helps avoid
# making valid-email discovery significantly cheaper than normal login.
_DUMMY_PASSWORD_HASH = hash_password(
    "hetren-dummy-password-for-authentication-timing"
)


def normalize_email(email: str) -> str:
    """Return the canonical email representation persisted by Hetren."""
    return email.strip().lower()


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)

    return value.astimezone(UTC)


def _create_access_token(
    *,
    user_id: int,
    secret_key: str,
    access_token_expire_minutes: int,
    issued_at: datetime,
) -> str:
    return create_access_token(
        user_id=user_id,
        secret_key=secret_key,
        expires_in=timedelta(
            minutes=access_token_expire_minutes,
        ),
        issued_at=issued_at,
    )


def _revoke_active_family(
    db: Session,
    *,
    family_id: str,
    revoked_at: datetime,
) -> None:
    db.execute(
        update(models.RefreshSession)
        .where(
            models.RefreshSession.family_id == family_id,
            models.RefreshSession.revoked_at.is_(None),
        )
        .values(revoked_at=revoked_at)
    )


def login(
    db: Session,
    *,
    email: str,
    password: str,
    secret_key: str,
    access_token_expire_minutes: int,
    refresh_token_expire_days: int,
) -> IssuedTokenPair:
    """Authenticate a human user and create a new refresh session."""
    normalized_email = normalize_email(email)

    user = db.scalar(
        select(models.User).where(
            models.User.email == normalized_email
        )
    )

    candidate_hash = (
        user.password_hash
        if user is not None and user.password_hash is not None
        else _DUMMY_PASSWORD_HASH
    )

    password_valid = verify_password(
        password,
        candidate_hash,
    )

    if (
        user is None
        or user.password_hash is None
        or not password_valid
        or not user.is_active
    ):
        raise InvalidCredentialsError(
            "Invalid email or password."
        )

    now = _utc_now()
    refresh_token = generate_refresh_token()

    refresh_session = models.RefreshSession(
        user_id=user.id,
        token_hash=hash_refresh_token(refresh_token),
        created_at=now,
        expires_at=(
            now
            + timedelta(
                days=refresh_token_expire_days,
            )
        ),
    )

    db.add(refresh_session)

    access_token = _create_access_token(
        user_id=user.id,
        secret_key=secret_key,
        access_token_expire_minutes=(
            access_token_expire_minutes
        ),
        issued_at=now,
    )

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return IssuedTokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
    )


def rotate_refresh_token(
    db: Session,
    *,
    refresh_token: str,
    secret_key: str,
    access_token_expire_minutes: int,
    refresh_token_expire_days: int,
) -> IssuedTokenPair:
    """
    Rotate one refresh token atomically.

    Reuse of an already-rotated token revokes the remaining active sessions
    in the same token family.
    """
    token_hash = hash_refresh_token(refresh_token)

    refresh_session = db.scalar(
        select(models.RefreshSession)
        .where(
            models.RefreshSession.token_hash
            == token_hash
        )
        .with_for_update()
    )

    if refresh_session is None:
        raise InvalidRefreshTokenError(
            "Refresh token is invalid or unavailable."
        )

    now = _utc_now()

    if refresh_session.revoked_at is not None:
        if refresh_session.replaced_by_session_id is not None:
            _revoke_active_family(
                db,
                family_id=refresh_session.family_id,
                revoked_at=now,
            )
            db.commit()

            raise RefreshTokenReuseError(
                "Refresh token is invalid or unavailable."
            )

        raise InvalidRefreshTokenError(
            "Refresh token is invalid or unavailable."
        )

    if _ensure_utc(refresh_session.expires_at) <= now:
        refresh_session.revoked_at = now
        db.commit()

        raise InvalidRefreshTokenError(
            "Refresh token is invalid or unavailable."
        )

    user = db.get(
        models.User,
        refresh_session.user_id,
    )

    if user is None or not user.is_active:
        _revoke_active_family(
            db,
            family_id=refresh_session.family_id,
            revoked_at=now,
        )
        db.commit()

        raise InvalidRefreshTokenError(
            "Refresh token is invalid or unavailable."
        )

    replacement_token = generate_refresh_token()
    replacement_session = models.RefreshSession(
        user_id=user.id,
        family_id=refresh_session.family_id,
        token_hash=hash_refresh_token(
            replacement_token
        ),
        created_at=now,
        expires_at=(
            now
            + timedelta(
                days=refresh_token_expire_days,
            )
        ),
    )

    db.add(replacement_session)

    try:
        db.flush()

        refresh_session.revoked_at = now
        refresh_session.replaced_by_session_id = (
            replacement_session.id
        )

        access_token = _create_access_token(
            user_id=user.id,
            secret_key=secret_key,
            access_token_expire_minutes=(
                access_token_expire_minutes
            ),
            issued_at=now,
        )

        db.commit()
    except Exception:
        db.rollback()
        raise

    return IssuedTokenPair(
        access_token=access_token,
        refresh_token=replacement_token,
    )


def logout(
    db: Session,
    *,
    refresh_token: str,
) -> None:
    """
    Revoke the presented refresh session.

    Unknown and already-revoked tokens are intentionally handled
    idempotently.
    """
    token_hash = hash_refresh_token(refresh_token)

    refresh_session = db.scalar(
        select(models.RefreshSession)
        .where(
            models.RefreshSession.token_hash
            == token_hash
        )
        .with_for_update()
    )

    if (
        refresh_session is None
        or refresh_session.revoked_at is not None
    ):
        return

    refresh_session.revoked_at = _utc_now()

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

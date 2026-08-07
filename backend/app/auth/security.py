import secrets
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any
from uuid import uuid4

import jwt
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError


ACCESS_TOKEN_ALGORITHM = "HS256"
ACCESS_TOKEN_ISSUER = "hetren-api"
ACCESS_TOKEN_AUDIENCE = "hetren-web"

REFRESH_TOKEN_PREFIX = "hetren_refresh_"
REFRESH_TOKEN_RANDOM_BYTES = 48

_password_hasher = PasswordHash.recommended()


class InvalidAccessTokenError(ValueError):
    """Raised when an access token fails validation."""


def hash_password(password: str) -> str:
    """Hash a password using the recommended Argon2id configuration."""
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password without exposing malformed-hash errors."""
    try:
        return _password_hasher.verify(password, password_hash)
    except (UnknownHashError, ValueError):
        return False


def create_access_token(
    *,
    user_id: int,
    secret_key: str,
    expires_in: timedelta,
    issued_at: datetime | None = None,
) -> str:
    """Create a signed, short-lived access token for one human user."""
    if user_id <= 0:
        raise ValueError("user_id must be a positive integer")

    now = issued_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("issued_at must be timezone-aware")

    now = now.astimezone(timezone.utc).replace(microsecond=0)

    payload: dict[str, object] = {
        "sub": str(user_id),
        "type": "access",
        "iss": ACCESS_TOKEN_ISSUER,
        "aud": ACCESS_TOKEN_AUDIENCE,
        "iat": now,
        "nbf": now,
        "exp": now + expires_in,
        "jti": uuid4().hex,
    }

    return jwt.encode(
        payload,
        secret_key,
        algorithm=ACCESS_TOKEN_ALGORITHM,
    )


def decode_access_token(
    *,
    token: str,
    secret_key: str,
) -> dict[str, Any]:
    """Validate an access token and return its trusted claims."""
    try:
        claims = jwt.decode(
            token,
            secret_key,
            algorithms=[ACCESS_TOKEN_ALGORITHM],
            audience=ACCESS_TOKEN_AUDIENCE,
            issuer=ACCESS_TOKEN_ISSUER,
            options={
                "require": [
                    "sub",
                    "type",
                    "iss",
                    "aud",
                    "iat",
                    "nbf",
                    "exp",
                    "jti",
                ],
                "strict_aud": True,
            },
        )
    except jwt.InvalidTokenError as exc:
        raise InvalidAccessTokenError("Invalid access token") from exc

    subject = claims.get("sub")
    if (
        not isinstance(subject, str)
        or not subject.isascii()
        or not subject.isdigit()
        or int(subject) <= 0
    ):
        raise InvalidAccessTokenError("Invalid access token")

    if claims.get("type") != "access":
        raise InvalidAccessTokenError("Invalid access token")

    token_identifier = claims.get("jti")
    if not isinstance(token_identifier, str) or not token_identifier:
        raise InvalidAccessTokenError("Invalid access token")

    return claims


def generate_refresh_token() -> str:
    """Generate a high-entropy opaque refresh token."""
    random_value = secrets.token_urlsafe(REFRESH_TOKEN_RANDOM_BYTES)
    return f"{REFRESH_TOKEN_PREFIX}{random_value}"


def hash_refresh_token(token: str) -> str:
    """Create the non-reversible value persisted for a refresh token."""
    return sha256(token.encode("utf-8")).hexdigest()

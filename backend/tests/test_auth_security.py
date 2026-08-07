from datetime import datetime, timedelta, timezone
from hashlib import sha256

import jwt
import pytest

from app.auth.security import (
    ACCESS_TOKEN_ALGORITHM,
    ACCESS_TOKEN_AUDIENCE,
    ACCESS_TOKEN_ISSUER,
    InvalidAccessTokenError,
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)


TEST_SECRET_KEY = (
    "hetren-test-only-authentication-secret-key-with-sufficient-length"
)


def _encode_access_payload(**overrides: object) -> str:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    payload: dict[str, object] = {
        "sub": "42",
        "type": "access",
        "iss": ACCESS_TOKEN_ISSUER,
        "aud": ACCESS_TOKEN_AUDIENCE,
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(minutes=15),
        "jti": "test-access-token-identifier",
    }
    payload.update(overrides)

    return jwt.encode(
        payload,
        TEST_SECRET_KEY,
        algorithm=ACCESS_TOKEN_ALGORITHM,
    )


def test_hash_password_uses_argon2_and_verifies_password() -> None:
    password = "Hetren-secure-password-123"

    password_hash = hash_password(password)

    assert password_hash.startswith("$argon2id$")
    assert password_hash != password
    assert verify_password(password, password_hash) is True
    assert verify_password("incorrect-password", password_hash) is False


def test_verify_password_rejects_malformed_hash() -> None:
    assert verify_password("any-password", "not-a-valid-password-hash") is False


def test_create_and_decode_access_token() -> None:
    issued_at = datetime.now(timezone.utc).replace(microsecond=0)

    token = create_access_token(
        user_id=42,
        secret_key=TEST_SECRET_KEY,
        expires_in=timedelta(minutes=15),
        issued_at=issued_at,
    )

    claims = decode_access_token(
        token=token,
        secret_key=TEST_SECRET_KEY,
    )

    assert claims["sub"] == "42"
    assert claims["type"] == "access"
    assert claims["iss"] == ACCESS_TOKEN_ISSUER
    assert claims["aud"] == ACCESS_TOKEN_AUDIENCE
    assert claims["iat"] == int(issued_at.timestamp())
    assert claims["nbf"] == int(issued_at.timestamp())
    assert claims["exp"] - claims["iat"] == 15 * 60
    assert isinstance(claims["jti"], str)
    assert len(claims["jti"]) >= 32


def test_access_tokens_receive_unique_identifiers() -> None:
    first_token = create_access_token(
        user_id=42,
        secret_key=TEST_SECRET_KEY,
        expires_in=timedelta(minutes=15),
    )
    second_token = create_access_token(
        user_id=42,
        secret_key=TEST_SECRET_KEY,
        expires_in=timedelta(minutes=15),
    )

    first_claims = decode_access_token(
        token=first_token,
        secret_key=TEST_SECRET_KEY,
    )
    second_claims = decode_access_token(
        token=second_token,
        secret_key=TEST_SECRET_KEY,
    )

    assert first_claims["jti"] != second_claims["jti"]


def test_decode_access_token_rejects_wrong_secret() -> None:
    token = _encode_access_payload()

    with pytest.raises(InvalidAccessTokenError):
        decode_access_token(
            token=token,
            secret_key="different-test-secret-key-with-sufficient-length",
        )


@pytest.mark.parametrize(
    ("claim", "invalid_value"),
    [
        ("type", "refresh"),
        ("sub", "not-a-user-id"),
        ("sub", "0"),
        ("sub", "-1"),
    ],
)
def test_decode_access_token_rejects_invalid_claims(
    claim: str,
    invalid_value: str,
) -> None:
    token = _encode_access_payload(**{claim: invalid_value})

    with pytest.raises(InvalidAccessTokenError):
        decode_access_token(
            token=token,
            secret_key=TEST_SECRET_KEY,
        )


def test_decode_access_token_rejects_expired_token() -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    token = _encode_access_payload(
        iat=now - timedelta(minutes=20),
        nbf=now - timedelta(minutes=20),
        exp=now - timedelta(minutes=5),
    )

    with pytest.raises(InvalidAccessTokenError):
        decode_access_token(
            token=token,
            secret_key=TEST_SECRET_KEY,
        )


def test_refresh_tokens_are_random_and_hashable() -> None:
    first_token = generate_refresh_token()
    second_token = generate_refresh_token()

    first_hash = hash_refresh_token(first_token)

    assert first_token.startswith("hetren_refresh_")
    assert second_token.startswith("hetren_refresh_")
    assert first_token != second_token
    assert len(first_token) >= 64
    assert first_hash == sha256(first_token.encode("utf-8")).hexdigest()
    assert len(first_hash) == 64
    assert first_token not in first_hash
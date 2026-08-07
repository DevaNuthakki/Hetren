import asyncio
import os
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.auth.cookies import (
    REFRESH_COOKIE_NAME,
    refresh_cookie_secure,
)
from app.auth.security import (
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
)
from app.config import get_settings
from app.database import get_db
from app.main import app


pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        os.getenv("RUN_POSTGRES_TESTS") != "1",
        reason=(
            "Set RUN_POSTGRES_TESTS=1 to run PostgreSQL "
            "authentication API tests."
        ),
    ),
]


TEST_PASSWORD = "correct-horse-battery-staple"


def _create_user(
    db: Session,
    *,
    email: str = "engineer@example.com",
    password: str | None = TEST_PASSWORD,
    is_active: bool = True,
) -> models.User:
    user = models.User(
        email=email,
        display_name="Hetren Engineer",
        password_hash=(
            hash_password(password)
            if password is not None
            else None
        ),
        is_active=is_active,
    )
    db.add(user)
    db.flush()
    db.refresh(user)
    return user


def _request(
    db: Session,
    method: str,
    path: str,
    *,
    json: dict | None = None,
    headers: dict[str, str] | None = None,
    origin: str | None = "http://localhost:5173",
):
    def override_get_db():
        yield db

    request_headers = dict(headers or {})

    if origin is not None:
        request_headers.setdefault(
            "Origin",
            origin,
        )

    async def send_request():
        transport = ASGITransport(app=app)

        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(
                method,
                path,
                json=json,
                headers=request_headers,
            )

    app.dependency_overrides[get_db] = override_get_db

    try:
        return asyncio.run(send_request())
    finally:
        app.dependency_overrides.pop(get_db, None)


def _refresh_cookie_headers(
    refresh_token: str,
) -> dict[str, str]:
    return {
        "Cookie": (
            f"{REFRESH_COOKIE_NAME}={refresh_token}"
        )
    }


def _login(
    db: Session,
    *,
    email: str = "engineer@example.com",
    password: str = TEST_PASSWORD,
):
    return _request(
        db,
        "POST",
        "/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )


def _get_refresh_cookie(response) -> str:
    token = response.cookies.get(
        REFRESH_COOKIE_NAME
    )
    assert token is not None
    return token


def test_auth_routes_are_registered() -> None:
    paths = app.openapi()["paths"]

    assert "/auth/login" in paths
    assert "/auth/refresh" in paths
    assert "/auth/logout" in paths
    assert "/auth/me" in paths


def test_refresh_cookie_secure_policy() -> None:
    assert refresh_cookie_secure("development") is False
    assert refresh_cookie_secure("test") is False
    assert refresh_cookie_secure("staging") is True
    assert refresh_cookie_secure("production") is True


def test_login_returns_access_token_and_protected_refresh_cookie(
    postgres_session: Session,
) -> None:
    user = _create_user(postgres_session)

    response = _login(
        postgres_session,
        email="  ENGINEER@EXAMPLE.COM  ",
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["token_type"] == "bearer"
    assert payload["access_token"]
    assert payload["access_token_expires_in_seconds"] > 0
    assert "refresh_token" not in payload

    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"

    set_cookie = response.headers["set-cookie"].lower()

    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie
    assert "path=/auth" in set_cookie
    assert "max-age=" in set_cookie

    settings = get_settings()

    if refresh_cookie_secure(settings.app_env):
        assert "secure" in set_cookie
    else:
        assert "secure" not in set_cookie

    refresh_token = _get_refresh_cookie(response)

    assert refresh_token.startswith(
        "hetren_refresh_"
    )

    refresh_session = postgres_session.scalar(
        select(models.RefreshSession).where(
            models.RefreshSession.user_id == user.id
        )
    )

    assert refresh_session is not None
    assert (
        refresh_session.token_hash
        == hash_refresh_token(refresh_token)
    )
    assert refresh_session.token_hash != refresh_token

    claims = decode_access_token(
        token=payload["access_token"],
        secret_key=(
            settings.auth_secret_key.get_secret_value()
        ),
    )

    assert claims["sub"] == str(user.id)


@pytest.mark.parametrize(
    ("email", "password"),
    [
        (
            "engineer@example.com",
            "wrong-password",
        ),
        (
            "missing@example.com",
            TEST_PASSWORD,
        ),
    ],
)
def test_login_uses_same_error_for_invalid_credentials(
    postgres_session: Session,
    email: str,
    password: str,
) -> None:
    _create_user(postgres_session)

    response = _login(
        postgres_session,
        email=email,
        password=password,
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Invalid email or password."
    }
    assert (
        response.cookies.get(REFRESH_COOKIE_NAME)
        is None
    )


def test_user_without_password_cannot_login(
    postgres_session: Session,
) -> None:
    _create_user(
        postgres_session,
        password=None,
    )

    response = _login(postgres_session)

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Invalid email or password."
    }


def test_inactive_user_cannot_login(
    postgres_session: Session,
) -> None:
    _create_user(
        postgres_session,
        is_active=False,
    )

    response = _login(postgres_session)

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Invalid email or password."
    }


def test_me_returns_only_authenticated_user_fields(
    postgres_session: Session,
) -> None:
    user = _create_user(postgres_session)

    login_response = _login(postgres_session)
    access_token = login_response.json()["access_token"]

    response = _request(
        postgres_session,
        "GET",
        "/auth/me",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["id"] == user.id
    assert payload["email"] == user.email
    assert payload["display_name"] == user.display_name
    assert payload["is_active"] is True
    assert "created_at" in payload

    assert "password_hash" not in payload
    assert "refresh_sessions" not in payload
    assert "memberships" not in payload


def test_me_rejects_missing_or_invalid_access_token(
    postgres_session: Session,
) -> None:
    missing = _request(
        postgres_session,
        "GET",
        "/auth/me",
    )
    invalid = _request(
        postgres_session,
        "GET",
        "/auth/me",
        headers={
            "Authorization": "Bearer definitely-not-a-jwt",
        },
    )

    assert missing.status_code == 401
    assert invalid.status_code == 401

    assert missing.headers["www-authenticate"] == "Bearer"
    assert invalid.headers["www-authenticate"] == "Bearer"


def test_me_rejects_user_disabled_after_token_issue(
    postgres_session: Session,
) -> None:
    user = _create_user(postgres_session)

    login_response = _login(postgres_session)
    access_token = login_response.json()["access_token"]

    user.is_active = False
    postgres_session.commit()

    response = _request(
        postgres_session,
        "GET",
        "/auth/me",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )

    assert response.status_code == 401


def test_refresh_requires_cookie(
    postgres_session: Session,
) -> None:
    response = _request(
        postgres_session,
        "POST",
        "/auth/refresh",
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": (
            "Refresh token is invalid or unavailable."
        )
    }


def test_refresh_rotates_cookie_and_links_sessions(
    postgres_session: Session,
) -> None:
    user = _create_user(postgres_session)

    login_response = _login(postgres_session)
    first_refresh_token = _get_refresh_cookie(
        login_response
    )

    first_session = postgres_session.scalar(
        select(models.RefreshSession).where(
            models.RefreshSession.token_hash
            == hash_refresh_token(first_refresh_token)
        )
    )
    assert first_session is not None

    first_session_id = first_session.id
    family_id = first_session.family_id

    response = _request(
        postgres_session,
        "POST",
        "/auth/refresh",
        headers=_refresh_cookie_headers(
            first_refresh_token
        ),
    )

    assert response.status_code == 200
    assert "refresh_token" not in response.json()

    second_refresh_token = _get_refresh_cookie(
        response
    )

    assert second_refresh_token != first_refresh_token
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"

    postgres_session.expire_all()

    first_session = postgres_session.get(
        models.RefreshSession,
        first_session_id,
    )
    second_session = postgres_session.scalar(
        select(models.RefreshSession).where(
            models.RefreshSession.token_hash
            == hash_refresh_token(second_refresh_token)
        )
    )

    assert first_session is not None
    assert second_session is not None

    assert first_session.revoked_at is not None
    assert (
        first_session.replaced_by_session_id
        == second_session.id
    )

    assert second_session.user_id == user.id
    assert second_session.family_id == family_id
    assert second_session.revoked_at is None


def test_refresh_token_reuse_revokes_active_family(
    postgres_session: Session,
) -> None:
    _create_user(postgres_session)

    login_response = _login(postgres_session)
    first_refresh_token = _get_refresh_cookie(
        login_response
    )

    rotation_response = _request(
        postgres_session,
        "POST",
        "/auth/refresh",
        headers=_refresh_cookie_headers(
            first_refresh_token
        ),
    )

    assert rotation_response.status_code == 200

    second_refresh_token = _get_refresh_cookie(
        rotation_response
    )

    replay_response = _request(
        postgres_session,
        "POST",
        "/auth/refresh",
        headers=_refresh_cookie_headers(
            first_refresh_token
        ),
    )

    assert replay_response.status_code == 401
    assert replay_response.json() == {
        "detail": (
            "Refresh token is invalid or unavailable."
        )
    }

    postgres_session.expire_all()

    second_session = postgres_session.scalar(
        select(models.RefreshSession).where(
            models.RefreshSession.token_hash
            == hash_refresh_token(second_refresh_token)
        )
    )

    assert second_session is not None
    assert second_session.revoked_at is not None

    second_response = _request(
        postgres_session,
        "POST",
        "/auth/refresh",
        headers=_refresh_cookie_headers(
            second_refresh_token
        ),
    )

    assert second_response.status_code == 401


def test_unknown_refresh_cookie_is_rejected(
    postgres_session: Session,
) -> None:
    response = _request(
        postgres_session,
        "POST",
        "/auth/refresh",
        headers=_refresh_cookie_headers(
            generate_refresh_token()
        ),
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": (
            "Refresh token is invalid or unavailable."
        )
    }


def test_logout_revokes_session_clears_cookie_and_is_idempotent(
    postgres_session: Session,
) -> None:
    _create_user(postgres_session)

    login_response = _login(postgres_session)
    refresh_token = _get_refresh_cookie(
        login_response
    )

    first_logout = _request(
        postgres_session,
        "POST",
        "/auth/logout",
        headers=_refresh_cookie_headers(
            refresh_token
        ),
    )

    assert first_logout.status_code == 204
    assert first_logout.content == b""

    delete_cookie = (
        first_logout.headers["set-cookie"].lower()
    )

    assert REFRESH_COOKIE_NAME in delete_cookie
    assert "path=/auth" in delete_cookie
    assert "max-age=0" in delete_cookie
    assert "httponly" in delete_cookie
    assert "samesite=lax" in delete_cookie

    postgres_session.expire_all()

    refresh_session = postgres_session.scalar(
        select(models.RefreshSession).where(
            models.RefreshSession.token_hash
            == hash_refresh_token(refresh_token)
        )
    )

    assert refresh_session is not None
    assert refresh_session.revoked_at is not None

    second_logout = _request(
        postgres_session,
        "POST",
        "/auth/logout",
        headers=_refresh_cookie_headers(
            refresh_token
        ),
    )

    assert second_logout.status_code == 204

    refresh_response = _request(
        postgres_session,
        "POST",
        "/auth/refresh",
        headers=_refresh_cookie_headers(
            refresh_token
        ),
    )

    assert refresh_response.status_code == 401


def test_logout_without_cookie_is_idempotent(
    postgres_session: Session,
) -> None:
    response = _request(
        postgres_session,
        "POST",
        "/auth/logout",
    )

    assert response.status_code == 204

    delete_cookie = (
        response.headers["set-cookie"].lower()
    )
    assert REFRESH_COOKIE_NAME in delete_cookie
    assert "max-age=0" in delete_cookie


def test_logout_unknown_cookie_is_idempotent(
    postgres_session: Session,
) -> None:
    response = _request(
        postgres_session,
        "POST",
        "/auth/logout",
        headers=_refresh_cookie_headers(
            generate_refresh_token()
        ),
    )

    assert response.status_code == 204


def test_expired_refresh_cookie_is_revoked_and_rejected(
    postgres_session: Session,
) -> None:
    user = _create_user(postgres_session)
    now = datetime.now(UTC)

    refresh_token = generate_refresh_token()
    refresh_session = models.RefreshSession(
        user_id=user.id,
        token_hash=hash_refresh_token(refresh_token),
        created_at=now - timedelta(days=2),
        expires_at=now - timedelta(days=1),
    )

    postgres_session.add(refresh_session)
    postgres_session.flush()

    refresh_session_id = refresh_session.id

    response = _request(
        postgres_session,
        "POST",
        "/auth/refresh",
        headers=_refresh_cookie_headers(
            refresh_token
        ),
    )

    assert response.status_code == 401

    postgres_session.expire_all()

    persisted_session = postgres_session.get(
        models.RefreshSession,
        refresh_session_id,
    )

    assert persisted_session is not None
    assert persisted_session.revoked_at is not None


def test_refresh_rejects_user_disabled_after_login(
    postgres_session: Session,
) -> None:
    user = _create_user(postgres_session)

    login_response = _login(postgres_session)
    refresh_token = _get_refresh_cookie(
        login_response
    )

    refresh_session = postgres_session.scalar(
        select(models.RefreshSession).where(
            models.RefreshSession.token_hash
            == hash_refresh_token(refresh_token)
        )
    )

    assert refresh_session is not None
    refresh_session_id = refresh_session.id

    user.is_active = False
    postgres_session.commit()

    response = _request(
        postgres_session,
        "POST",
        "/auth/refresh",
        headers=_refresh_cookie_headers(
            refresh_token
        ),
    )

    assert response.status_code == 401

    postgres_session.expire_all()

    persisted_session = postgres_session.get(
        models.RefreshSession,
        refresh_session_id,
    )

    assert persisted_session is not None
    assert persisted_session.revoked_at is not None


def test_refresh_replay_revokes_only_compromised_family(
    postgres_session: Session,
) -> None:
    _create_user(postgres_session)

    first_login = _login(postgres_session)
    first_family_token = _get_refresh_cookie(
        first_login
    )

    second_login = _login(postgres_session)
    independent_family_token = _get_refresh_cookie(
        second_login
    )

    independent_session = postgres_session.scalar(
        select(models.RefreshSession).where(
            models.RefreshSession.token_hash
            == hash_refresh_token(
                independent_family_token
            )
        )
    )

    assert independent_session is not None
    independent_session_id = independent_session.id

    rotation_response = _request(
        postgres_session,
        "POST",
        "/auth/refresh",
        headers=_refresh_cookie_headers(
            first_family_token
        ),
    )

    assert rotation_response.status_code == 200

    replay_response = _request(
        postgres_session,
        "POST",
        "/auth/refresh",
        headers=_refresh_cookie_headers(
            first_family_token
        ),
    )

    assert replay_response.status_code == 401

    postgres_session.expire_all()

    independent_session = postgres_session.get(
        models.RefreshSession,
        independent_session_id,
    )

    assert independent_session is not None
    assert independent_session.revoked_at is None

    independent_refresh = _request(
        postgres_session,
        "POST",
        "/auth/refresh",
        headers=_refresh_cookie_headers(
            independent_family_token
        ),
    )

    assert independent_refresh.status_code == 200



def test_refresh_rejects_missing_origin(
    postgres_session: Session,
) -> None:
    response = _request(
        postgres_session,
        "POST",
        "/auth/refresh",
        origin=None,
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Request origin is not allowed."
    }


def test_refresh_rejects_untrusted_origin(
    postgres_session: Session,
) -> None:
    response = _request(
        postgres_session,
        "POST",
        "/auth/refresh",
        origin="https://attacker.example",
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Request origin is not allowed."
    }


def test_logout_rejects_untrusted_origin(
    postgres_session: Session,
) -> None:
    response = _request(
        postgres_session,
        "POST",
        "/auth/logout",
        origin="https://attacker.example",
    )

    assert response.status_code == 403


def test_login_rejects_missing_origin(
    postgres_session: Session,
) -> None:
    _create_user(postgres_session)

    response = _request(
        postgres_session,
        "POST",
        "/auth/login",
        json={
            "email": "engineer@example.com",
            "password": TEST_PASSWORD,
        },
        origin=None,
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Request origin is not allowed."
    }
    assert response.cookies.get(REFRESH_COOKIE_NAME) is None


def test_login_rejects_untrusted_origin(
    postgres_session: Session,
) -> None:
    _create_user(postgres_session)

    response = _request(
        postgres_session,
        "POST",
        "/auth/login",
        json={
            "email": "engineer@example.com",
            "password": TEST_PASSWORD,
        },
        origin="https://attacker.example",
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Request origin is not allowed."
    }
    assert response.cookies.get(REFRESH_COOKIE_NAME) is None

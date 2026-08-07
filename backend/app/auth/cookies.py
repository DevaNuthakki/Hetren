from fastapi import Response


REFRESH_COOKIE_NAME = "hetren_refresh_token"
REFRESH_COOKIE_PATH = "/auth"
REFRESH_COOKIE_SAMESITE = "lax"


def refresh_cookie_secure(app_env: str) -> bool:
    """
    Require HTTPS-only refresh cookies outside local/test environments.
    """
    return app_env in {
        "staging",
        "production",
    }


def set_refresh_cookie(
    response: Response,
    *,
    refresh_token: str,
    max_age_seconds: int,
    secure: bool,
) -> None:
    """Store the refresh credential in a protected browser cookie."""
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=max_age_seconds,
        httponly=True,
        secure=secure,
        samesite=REFRESH_COOKIE_SAMESITE,
        path=REFRESH_COOKIE_PATH,
    )


def clear_refresh_cookie(
    response: Response,
    *,
    secure: bool,
) -> None:
    """Expire the browser refresh cookie using matching attributes."""
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        secure=secure,
        httponly=True,
        samesite=REFRESH_COOKIE_SAMESITE,
    )

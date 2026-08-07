from fastapi import (
    Depends,
    Header,
    HTTPException,
    status,
)
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from sqlalchemy.orm import Session

from app import models
from app.auth.security import (
    InvalidAccessTokenError,
    decode_access_token,
)
from app.config import get_settings
from app.database import get_db


human_bearer = HTTPBearer(auto_error=False)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication is required.",
        headers={
            "WWW-Authenticate": "Bearer",
        },
    )


def require_trusted_browser_origin(
    origin: str | None = Header(default=None),
) -> None:
    """
    Reject cookie-authenticated state changes from untrusted origins.

    Browsers control the Origin header, making this an additional CSRF
    boundary alongside SameSite refresh cookies.
    """
    settings = get_settings()

    if (
        origin is None
        or origin not in settings.cors_allowed_origins
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Request origin is not allowed.",
        )


def get_current_user(
    authorization: HTTPAuthorizationCredentials | None = Depends(
        human_bearer
    ),
    db: Session = Depends(get_db),
) -> models.User:
    """Validate a human bearer token and load its active user."""
    if (
        authorization is None
        or authorization.scheme.lower() != "bearer"
        or not authorization.credentials
    ):
        raise _unauthorized()

    settings = get_settings()

    try:
        claims = decode_access_token(
            token=authorization.credentials,
            secret_key=(
                settings.auth_secret_key.get_secret_value()
            ),
        )
    except InvalidAccessTokenError as exc:
        raise _unauthorized() from exc

    user_id = int(claims["sub"])
    user = db.get(
        models.User,
        user_id,
    )

    if user is None or not user.is_active:
        raise _unauthorized()

    return user

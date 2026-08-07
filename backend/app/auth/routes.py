from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    HTTPException,
    Response,
    status,
)
from sqlalchemy.orm import Session

from app import models
from app.auth.cookies import (
    REFRESH_COOKIE_NAME,
    clear_refresh_cookie,
    refresh_cookie_secure,
    set_refresh_cookie,
)
from app.auth.dependencies import (
    get_current_user,
    require_trusted_browser_origin,
)
from app.auth.schemas import (
    AccessTokenResponse,
    CurrentUserResponse,
    LoginRequest,
)
from app.auth.service import (
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    login,
    logout,
    rotate_refresh_token,
)
from app.config import get_settings
from app.database import get_db


router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


def _disable_token_response_caching(
    response: Response,
) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


def _refresh_cookie_max_age_seconds(
    refresh_token_expire_days: int,
) -> int:
    return refresh_token_expire_days * 24 * 60 * 60


def _invalid_refresh_token() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Refresh token is invalid or unavailable.",
    )


@router.post(
    "/login",
    response_model=AccessTokenResponse,
)
def login_endpoint(
    request: LoginRequest,
    response: Response,
    _: None = Depends(require_trusted_browser_origin),
    db: Session = Depends(get_db),
):
    settings = get_settings()

    try:
        tokens = login(
            db,
            email=request.email,
            password=request.password,
            secret_key=(
                settings.auth_secret_key.get_secret_value()
            ),
            access_token_expire_minutes=(
                settings.auth_access_token_expire_minutes
            ),
            refresh_token_expire_days=(
                settings.auth_refresh_token_expire_days
            ),
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        ) from exc

    set_refresh_cookie(
        response,
        refresh_token=tokens.refresh_token,
        max_age_seconds=_refresh_cookie_max_age_seconds(
            settings.auth_refresh_token_expire_days
        ),
        secure=refresh_cookie_secure(settings.app_env),
    )
    _disable_token_response_caching(response)

    return {
        "access_token": tokens.access_token,
        "token_type": "bearer",
        "access_token_expires_in_seconds": (
            settings.auth_access_token_expire_minutes
            * 60
        ),
    }


@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
)
def refresh_endpoint(
    response: Response,
    _: None = Depends(require_trusted_browser_origin),
    refresh_token: str | None = Cookie(
        default=None,
        alias=REFRESH_COOKIE_NAME,
    ),
    db: Session = Depends(get_db),
):
    if not refresh_token:
        raise _invalid_refresh_token()

    settings = get_settings()

    try:
        tokens = rotate_refresh_token(
            db,
            refresh_token=refresh_token,
            secret_key=(
                settings.auth_secret_key.get_secret_value()
            ),
            access_token_expire_minutes=(
                settings.auth_access_token_expire_minutes
            ),
            refresh_token_expire_days=(
                settings.auth_refresh_token_expire_days
            ),
        )
    except InvalidRefreshTokenError as exc:
        raise _invalid_refresh_token() from exc

    set_refresh_cookie(
        response,
        refresh_token=tokens.refresh_token,
        max_age_seconds=_refresh_cookie_max_age_seconds(
            settings.auth_refresh_token_expire_days
        ),
        secure=refresh_cookie_secure(settings.app_env),
    )
    _disable_token_response_caching(response)

    return {
        "access_token": tokens.access_token,
        "token_type": "bearer",
        "access_token_expires_in_seconds": (
            settings.auth_access_token_expire_minutes
            * 60
        ),
    }


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
)
def logout_endpoint(
    _: None = Depends(require_trusted_browser_origin),
    refresh_token: str | None = Cookie(
        default=None,
        alias=REFRESH_COOKIE_NAME,
    ),
    db: Session = Depends(get_db),
) -> Response:
    settings = get_settings()

    if refresh_token:
        logout(
            db,
            refresh_token=refresh_token,
        )

    response = Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )

    clear_refresh_cookie(
        response,
        secure=refresh_cookie_secure(settings.app_env),
    )

    return response


@router.get(
    "/me",
    response_model=CurrentUserResponse,
)
def current_user_endpoint(
    current_user: models.User = Depends(
        get_current_user
    ),
):
    return current_user

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from sqlalchemy.orm import Session

from app.database import get_db
from app.runner_schemas import (
    RunnerHeartbeatRequest,
    RunnerHeartbeatResponse,
    RunnerRegisterRequest,
    RunnerRegistrationResponse,
)
from app.runner_service import (
    RegistrationTokenUnavailableError,
    RunnerAuthenticationError,
    RunnerRegistrationConflictError,
    record_runner_heartbeat,
    register_runner,
)


router = APIRouter(
    prefix="/runners",
    tags=["runners"],
)


runner_bearer = HTTPBearer(auto_error=False)


def get_runner_credential(
    authorization: HTTPAuthorizationCredentials | None = Depends(
        runner_bearer
    ),
) -> str:
    if (
        authorization is None
        or authorization.scheme.lower() != "bearer"
        or not authorization.credentials
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Runner credential is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return authorization.credentials


@router.post(
    "/register",
    response_model=RunnerRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_runner_endpoint(
    request: RunnerRegisterRequest,
    db: Session = Depends(get_db),
):
    """
    Exchange a valid one-time registration token for a runner identity.

    The plaintext runner credential is returned only in this response.
    """
    try:
        registered = register_runner(
            db,
            registration_token=request.registration_token,
            name=request.name,
            runner_version=request.runner_version,
            capabilities=request.capabilities,
            system_info=request.system_info,
        )
    except RegistrationTokenUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Registration token is invalid or unavailable.",
        ) from exc
    except RunnerRegistrationConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Runner registration conflicts with an existing "
                "runner."
            ),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    return {
        "credential": registered.credential,
        "runner": registered.runner,
    }


@router.post(
    "/heartbeat",
    response_model=RunnerHeartbeatResponse,
)
def runner_heartbeat_endpoint(
    request: RunnerHeartbeatRequest,
    credential: str = Depends(get_runner_credential),
    db: Session = Depends(get_db),
):
    """Authenticate a runner and update its last-seen timestamp."""
    try:
        runner = record_runner_heartbeat(
            db,
            credential=credential,
            runner_version=request.runner_version,
            capabilities=request.capabilities,
            system_info=request.system_info,
        )
    except RunnerAuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Runner credential is invalid or unavailable.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    return {
        "status": "ok",
        "runner": runner,
    }

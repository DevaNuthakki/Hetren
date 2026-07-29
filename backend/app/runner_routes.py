from datetime import timedelta

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
    RunnerJobClaimRequest,
    RunnerJobClaimResponse,
    RunnerJobCompleteRequest,
    RunnerJobFailRequest,
    RunnerJobLeaseRenewalResponse,
    RunnerJobLogAppendRequest,
    RunnerJobLogAppendResponse,
    RunnerJobRenewRequest,
    RunnerJobStartRequest,
    RunnerJobTransitionResponse,
    RunnerRegisterRequest,
    RunnerRegistrationResponse,
)
from app.runner_job_service import (
    RunnerJobClaimConflictError,
    RunnerJobClaimUnavailableError,
    RunnerJobLogConflictError,
    RunnerJobTransitionUnavailableError,
    append_job_logs,
    claim_next_job,
    complete_job,
    fail_job,
    renew_job_lease,
    start_job,
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


@router.post(
    "/jobs/claim",
    response_model=RunnerJobClaimResponse,
)
def runner_job_claim_endpoint(
    request: RunnerJobClaimRequest,
    credential: str = Depends(get_runner_credential),
    db: Session = Depends(get_db),
):
    """Claim the next compatible queued job for a runner."""
    try:
        claimed = claim_next_job(
            db,
            credential=credential,
            lease_duration=timedelta(
                seconds=request.lease_seconds
            ),
        )
    except RunnerAuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Runner credential is invalid or unavailable.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except RunnerJobClaimConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runner job could not be claimed.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    if claimed is None:
        return {
            "status": "idle",
            "claim_token": None,
            "job": None,
        }

    return {
        "status": "claimed",
        "claim_token": claimed.claim_token,
        "job": claimed.job,
    }


@router.post(
    "/jobs/{job_public_id}/start",
    response_model=RunnerJobTransitionResponse,
)
def runner_job_start_endpoint(
    job_public_id: str,
    request: RunnerJobStartRequest,
    credential: str = Depends(get_runner_credential),
    db: Session = Depends(get_db),
):
    """Start a job owned by the authenticated runner."""
    try:
        job = start_job(
            db,
            credential=credential,
            job_public_id=job_public_id,
            claim_token=request.claim_token,
        )
    except RunnerAuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Runner credential is invalid or unavailable.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except RunnerJobClaimUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runner job claim is invalid or unavailable.",
        ) from exc
    except RunnerJobTransitionUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Runner job transition is invalid or "
                "unavailable."
            ),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    return {
        "status": "running",
        "job": job,
    }


@router.post(
    "/jobs/{job_public_id}/complete",
    response_model=RunnerJobTransitionResponse,
)
def runner_job_complete_endpoint(
    job_public_id: str,
    request: RunnerJobCompleteRequest,
    credential: str = Depends(get_runner_credential),
    db: Session = Depends(get_db),
):
    """Complete a running job owned by the authenticated runner."""
    try:
        job = complete_job(
            db,
            credential=credential,
            job_public_id=job_public_id,
            claim_token=request.claim_token,
            result_payload=request.result_payload,
        )
    except RunnerAuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Runner credential is invalid or unavailable.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except RunnerJobClaimUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runner job claim is invalid or unavailable.",
        ) from exc
    except RunnerJobTransitionUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Runner job transition is invalid or "
                "unavailable."
            ),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    return {
        "status": "completed",
        "job": job,
    }


@router.post(
    "/jobs/{job_public_id}/fail",
    response_model=RunnerJobTransitionResponse,
)
def runner_job_fail_endpoint(
    job_public_id: str,
    request: RunnerJobFailRequest,
    credential: str = Depends(get_runner_credential),
    db: Session = Depends(get_db),
):
    """Fail a claimed or running job owned by the runner."""
    try:
        job = fail_job(
            db,
            credential=credential,
            job_public_id=job_public_id,
            claim_token=request.claim_token,
            error_message=request.error_message,
        )
    except RunnerAuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Runner credential is invalid or unavailable.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except RunnerJobClaimUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runner job claim is invalid or unavailable.",
        ) from exc
    except RunnerJobTransitionUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Runner job transition is invalid or "
                "unavailable."
            ),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    return {
        "status": "failed",
        "job": job,
    }


@router.post(
    "/jobs/{job_public_id}/renew",
    response_model=RunnerJobLeaseRenewalResponse,
)
def runner_job_renew_endpoint(
    job_public_id: str,
    request: RunnerJobRenewRequest,
    credential: str = Depends(get_runner_credential),
    db: Session = Depends(get_db),
):
    """Renew an active job lease owned by the runner."""
    try:
        job = renew_job_lease(
            db,
            credential=credential,
            job_public_id=job_public_id,
            claim_token=request.claim_token,
            lease_duration=timedelta(
                seconds=request.lease_seconds
            ),
        )
    except RunnerAuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Runner credential is invalid or unavailable.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except RunnerJobClaimUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runner job claim is invalid or unavailable.",
        ) from exc
    except RunnerJobTransitionUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Runner job transition is invalid or "
                "unavailable."
            ),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    return {
        "status": "renewed",
        "job": job,
    }


@router.post(
    "/jobs/{job_public_id}/logs",
    response_model=RunnerJobLogAppendResponse,
    status_code=status.HTTP_201_CREATED,
)
def runner_job_log_append_endpoint(
    job_public_id: str,
    request: RunnerJobLogAppendRequest,
    credential: str = Depends(get_runner_credential),
    db: Session = Depends(get_db),
):
    """Append structured logs to an owned active runner job."""
    try:
        logs = append_job_logs(
            db,
            credential=credential,
            job_public_id=job_public_id,
            claim_token=request.claim_token,
            entries=[
                entry.model_dump()
                for entry in request.entries
            ],
        )
    except RunnerAuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Runner credential is invalid or unavailable.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except RunnerJobClaimUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runner job claim is invalid or unavailable.",
        ) from exc
    except RunnerJobLogConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runner job logs could not be appended.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    return {
        "status": "appended",
        "logs": logs,
    }

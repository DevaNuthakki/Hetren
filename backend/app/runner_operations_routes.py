from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.orm import Session

from app import models
from app.auth.authorization import (
    PRODUCT_READ_ROLES,
    ProjectNotAccessibleError,
    ProjectPermissionDeniedError,
    authorize_project,
)
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.runner_operations_service import (
    RunnerOperationsJobNotFoundError,
    RunnerOperationsProjectNotFoundError,
    get_project_runner_job_logs,
    get_project_runner_operations,
)
from app.runner_schemas import (
    RunnerOperationsLogPageResponse,
    RunnerOperationsSnapshotResponse,
)


router = APIRouter(
    tags=["runner operations"],
)



def _authorize_project_for_request(
    db: Session,
    *,
    current_user: models.User,
    project_id: int,
) -> None:
    """
    Require human product-data read access before exposing operations data.
    """
    try:
        authorize_project(
            db,
            user_id=current_user.id,
            project_id=project_id,
            required_roles=PRODUCT_READ_ROLES,
        )
    except ProjectNotAccessibleError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        ) from exc
    except ProjectPermissionDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Project permission denied.",
        ) from exc


@router.get(
    "/projects/{project_id}/runner-operations",
    response_model=RunnerOperationsSnapshotResponse,
)
def get_project_runner_operations_endpoint(
    project_id: int,
    job_limit: int = Query(
        default=100,
        ge=1,
        le=200,
    ),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return a safe, read-only runner and job overview for one project.

    Credentials, hashes, raw job payloads, system metadata, and log
    context are intentionally excluded.
    """
    _authorize_project_for_request(
        db,
        current_user=current_user,
        project_id=project_id,
    )

    try:
        return get_project_runner_operations(
            db,
            project_id=project_id,
            job_limit=job_limit,
        )
    except RunnerOperationsProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


@router.get(
    "/projects/{project_id}/runner-jobs/"
    "{job_public_id}/logs",
    response_model=RunnerOperationsLogPageResponse,
)
def get_project_runner_job_logs_endpoint(
    project_id: int,
    job_public_id: str,
    after_sequence: int = Query(
        default=0,
        ge=0,
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=200,
    ),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return safe ordered logs for one project-scoped runner job.

    Raw context payloads are intentionally excluded.
    """
    _authorize_project_for_request(
        db,
        current_user=current_user,
        project_id=project_id,
    )

    try:
        return get_project_runner_job_logs(
            db,
            project_id=project_id,
            job_public_id=job_public_id,
            after_sequence=after_sequence,
            limit=limit,
        )
    except RunnerOperationsProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        ) from exc
    except RunnerOperationsJobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Runner job not found in this project.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

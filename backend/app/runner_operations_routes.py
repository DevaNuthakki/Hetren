from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.orm import Session

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
    db: Session = Depends(get_db),
):
    """
    Return a safe, read-only runner and job overview for one project.

    Credentials, hashes, raw job payloads, system metadata, and log
    context are intentionally excluded.
    """
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
    db: Session = Depends(get_db),
):
    """
    Return safe ordered logs for one project-scoped runner job.

    Raw context payloads are intentionally excluded.
    """
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

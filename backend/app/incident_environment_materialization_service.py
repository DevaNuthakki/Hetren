"""Runner-job integration for Incident Mode environment materialization.

The job transports the already verified Incident Mode request to a
customer-controlled runner. It does not transport raw materialized
environment values.

The actual materialized context is produced runner-locally and remains
transient. Durable output contains only compatibility and materialization
evidence commitments.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.incident_runner_compatibility_service import (
    build_incident_replay_compatibility_request,
)
from app.runner_job_service import enqueue_job


INCIDENT_ENVIRONMENT_MATERIALIZATION_JOB_TYPE = (
    "incident_environment_materialization"
)

INCIDENT_ENVIRONMENT_MATERIALIZATION_REQUIRED_CAPABILITIES = (
    "asr",
    "incident_materialization",
    "incident_replay",
)


def enqueue_incident_environment_materialization_job(
    db: Session,
    *,
    project_id: int,
    name: str,
    intake_payload: object,
    expected_intake_sha256: object,
    replay_preparation_payload: object,
    expected_replay_preparation_sha256: object,
    environment_manifest_payload: object,
    expected_environment_manifest_sha256: object,
    priority: int = 0,
    max_attempts: int = 3,
) -> models.RunnerJob:
    request = build_incident_replay_compatibility_request(
        intake_payload=intake_payload,
        expected_intake_sha256=expected_intake_sha256,
        replay_preparation_payload=replay_preparation_payload,
        expected_replay_preparation_sha256=(
            expected_replay_preparation_sha256
        ),
        environment_manifest_payload=(
            environment_manifest_payload
        ),
        expected_environment_manifest_sha256=(
            expected_environment_manifest_sha256
        ),
    )

    return enqueue_job(
        db,
        project_id=project_id,
        name=name,
        job_type=(
            INCIDENT_ENVIRONMENT_MATERIALIZATION_JOB_TYPE
        ),
        required_capabilities=list(
            INCIDENT_ENVIRONMENT_MATERIALIZATION_REQUIRED_CAPABILITIES
        ),
        input_payload=request.payload,
        priority=priority,
        max_attempts=max_attempts,
    )


__all__ = [
    "INCIDENT_ENVIRONMENT_MATERIALIZATION_JOB_TYPE",
    "INCIDENT_ENVIRONMENT_MATERIALIZATION_REQUIRED_CAPABILITIES",
    "enqueue_incident_environment_materialization_job",
]

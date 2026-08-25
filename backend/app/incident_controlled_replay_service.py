"""Runner-job transport for Incident Mode controlled replay.

The server transports commitment-bound Incident Mode evidence to a
customer-controlled runner.

It does not transport:
- raw artifact bytes;
- raw transcripts;
- local filesystem paths;
- runner credentials; or
- qualification authority.

The customer runner independently reconstructs its compatibility
observation, reacquires artifacts through a runner-local provider, reverifies
their bytes, executes the bounded replay, and returns commitment-only
controlled-replay evidence through the generic runner completion path.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app import models
from app.runner_job_service import enqueue_job


INCIDENT_CONTROLLED_REPLAY_REQUEST_SCHEMA_VERSION = 1

INCIDENT_CONTROLLED_REPLAY_JOB_TYPE = (
    "incident_controlled_replay"
)

INCIDENT_CONTROLLED_REPLAY_REQUIRED_CAPABILITIES = (
    "asr",
    "incident_controlled_replay",
    "incident_materialization",
    "incident_replay",
)

_SHA256_PATTERN = re.compile(
    r"^[0-9a-f]{64}$"
)


class IncidentControlledReplayRequestError(
    ValueError
):
    """Controlled replay request is invalid."""


def _require_sha256(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or _SHA256_PATTERN.fullmatch(
            value
        )
        is None
    ):
        raise (
            IncidentControlledReplayRequestError(
                f"{name} must be lowercase SHA-256 hex."
            )
        )

    return value


def _require_payload(
    *,
    name: str,
    value: object,
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise (
            IncidentControlledReplayRequestError(
                f"{name} must be a JSON object."
            )
        )

    try:
        canonical = json.loads(
            json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            )
        )
    except (TypeError, ValueError) as exc:
        raise (
            IncidentControlledReplayRequestError(
                f"{name} must contain deterministic JSON."
            )
        ) from exc

    if not isinstance(canonical, dict):
        raise (
            IncidentControlledReplayRequestError(
                f"{name} must be a JSON object."
            )
        )

    return canonical


@dataclass(frozen=True, slots=True)
class IncidentControlledReplayRequest:
    payload: dict[str, object]

    intake_payload: dict[str, object]
    intake_sha256: str

    replay_preparation_payload: dict[str, object]
    replay_preparation_sha256: str

    environment_manifest_payload: dict[str, object]
    environment_manifest_sha256: str

    runner_compatibility_payload: dict[str, object]
    runner_compatibility_sha256: str

    environment_materialization_payload: dict[str, object]
    environment_materialization_sha256: str


def build_incident_controlled_replay_request(
    *,
    intake_payload: object,
    expected_intake_sha256: object,
    replay_preparation_payload: object,
    expected_replay_preparation_sha256: object,
    environment_manifest_payload: object,
    expected_environment_manifest_sha256: object,
    runner_compatibility_payload: object,
    expected_runner_compatibility_sha256: object,
    environment_materialization_payload: object,
    expected_environment_materialization_sha256: object,
) -> IncidentControlledReplayRequest:
    intake = _require_payload(
        name="incident intake",
        value=intake_payload,
    )

    replay_preparation = _require_payload(
        name="incident replay preparation",
        value=replay_preparation_payload,
    )

    environment_manifest = _require_payload(
        name="incident environment manifest",
        value=environment_manifest_payload,
    )

    runner_compatibility = _require_payload(
        name="incident runner compatibility",
        value=runner_compatibility_payload,
    )

    environment_materialization = _require_payload(
        name="incident environment materialization",
        value=environment_materialization_payload,
    )

    intake_sha256 = _require_sha256(
        name="incident intake SHA-256",
        value=expected_intake_sha256,
    )

    replay_preparation_sha256 = _require_sha256(
        name="incident replay preparation SHA-256",
        value=expected_replay_preparation_sha256,
    )

    environment_manifest_sha256 = _require_sha256(
        name="incident environment manifest SHA-256",
        value=expected_environment_manifest_sha256,
    )

    runner_compatibility_sha256 = _require_sha256(
        name="incident runner compatibility SHA-256",
        value=expected_runner_compatibility_sha256,
    )

    environment_materialization_sha256 = _require_sha256(
        name="incident environment materialization SHA-256",
        value=expected_environment_materialization_sha256,
    )

    payload = {
        "schema_version": (
            INCIDENT_CONTROLLED_REPLAY_REQUEST_SCHEMA_VERSION
        ),
        "type": "incident_controlled_replay_request",
        "evidence": {
            "intake": {
                "payload": intake,
                "sha256": intake_sha256,
            },
            "replay_preparation": {
                "payload": replay_preparation,
                "sha256": replay_preparation_sha256,
            },
            "environment_manifest": {
                "payload": environment_manifest,
                "sha256": environment_manifest_sha256,
            },
            "runner_compatibility": {
                "payload": runner_compatibility,
                "sha256": runner_compatibility_sha256,
            },
            "environment_materialization": {
                "payload": environment_materialization,
                "sha256": (
                    environment_materialization_sha256
                ),
            },
        },
    }

    return IncidentControlledReplayRequest(
        payload=payload,
        intake_payload=intake,
        intake_sha256=intake_sha256,
        replay_preparation_payload=(
            replay_preparation
        ),
        replay_preparation_sha256=(
            replay_preparation_sha256
        ),
        environment_manifest_payload=(
            environment_manifest
        ),
        environment_manifest_sha256=(
            environment_manifest_sha256
        ),
        runner_compatibility_payload=(
            runner_compatibility
        ),
        runner_compatibility_sha256=(
            runner_compatibility_sha256
        ),
        environment_materialization_payload=(
            environment_materialization
        ),
        environment_materialization_sha256=(
            environment_materialization_sha256
        ),
    )


def parse_incident_controlled_replay_request(
    payload: object,
) -> IncidentControlledReplayRequest:
    if not isinstance(payload, dict):
        raise IncidentControlledReplayRequestError(
            "Controlled replay request must be a JSON object."
        )

    if set(payload) != {
        "schema_version",
        "type",
        "evidence",
    }:
        raise IncidentControlledReplayRequestError(
            "Controlled replay request shape is invalid."
        )

    if (
        payload["schema_version"]
        != INCIDENT_CONTROLLED_REPLAY_REQUEST_SCHEMA_VERSION
        or payload["type"]
        != "incident_controlled_replay_request"
    ):
        raise IncidentControlledReplayRequestError(
            "Controlled replay request contract is invalid."
        )

    evidence = payload["evidence"]

    if (
        not isinstance(evidence, dict)
        or set(evidence)
        != {
            "intake",
            "replay_preparation",
            "environment_manifest",
            "runner_compatibility",
            "environment_materialization",
        }
    ):
        raise IncidentControlledReplayRequestError(
            "Controlled replay evidence envelope is invalid."
        )

    parsed: dict[
        str,
        tuple[dict[str, object], str],
    ] = {}

    for name, value in evidence.items():
        if (
            not isinstance(value, dict)
            or set(value)
            != {
                "payload",
                "sha256",
            }
        ):
            raise IncidentControlledReplayRequestError(
                "Controlled replay evidence item is invalid."
            )

        parsed[name] = (
            _require_payload(
                name=f"{name} payload",
                value=value["payload"],
            ),
            _require_sha256(
                name=f"{name} SHA-256",
                value=value["sha256"],
            ),
        )

    rebuilt = (
        build_incident_controlled_replay_request(
            intake_payload=parsed["intake"][0],
            expected_intake_sha256=parsed["intake"][1],
            replay_preparation_payload=(
                parsed["replay_preparation"][0]
            ),
            expected_replay_preparation_sha256=(
                parsed["replay_preparation"][1]
            ),
            environment_manifest_payload=(
                parsed["environment_manifest"][0]
            ),
            expected_environment_manifest_sha256=(
                parsed["environment_manifest"][1]
            ),
            runner_compatibility_payload=(
                parsed["runner_compatibility"][0]
            ),
            expected_runner_compatibility_sha256=(
                parsed["runner_compatibility"][1]
            ),
            environment_materialization_payload=(
                parsed["environment_materialization"][0]
            ),
            expected_environment_materialization_sha256=(
                parsed["environment_materialization"][1]
            ),
        )
    )

    if rebuilt.payload != payload:
        raise IncidentControlledReplayRequestError(
            "Controlled replay request is not canonical."
        )

    return rebuilt


def enqueue_incident_controlled_replay_job(
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
    runner_compatibility_payload: object,
    expected_runner_compatibility_sha256: object,
    environment_materialization_payload: object,
    expected_environment_materialization_sha256: object,
    priority: int = 0,
    max_attempts: int = 3,
) -> models.RunnerJob:
    request = (
        build_incident_controlled_replay_request(
            intake_payload=intake_payload,
            expected_intake_sha256=(
                expected_intake_sha256
            ),
            replay_preparation_payload=(
                replay_preparation_payload
            ),
            expected_replay_preparation_sha256=(
                expected_replay_preparation_sha256
            ),
            environment_manifest_payload=(
                environment_manifest_payload
            ),
            expected_environment_manifest_sha256=(
                expected_environment_manifest_sha256
            ),
            runner_compatibility_payload=(
                runner_compatibility_payload
            ),
            expected_runner_compatibility_sha256=(
                expected_runner_compatibility_sha256
            ),
            environment_materialization_payload=(
                environment_materialization_payload
            ),
            expected_environment_materialization_sha256=(
                expected_environment_materialization_sha256
            ),
        )
    )

    return enqueue_job(
        db,
        project_id=project_id,
        name=name,
        job_type=(
            INCIDENT_CONTROLLED_REPLAY_JOB_TYPE
        ),
        required_capabilities=list(
            INCIDENT_CONTROLLED_REPLAY_REQUIRED_CAPABILITIES
        ),
        input_payload=request.payload,
        priority=priority,
        max_attempts=max_attempts,
    )


__all__ = [
    "INCIDENT_CONTROLLED_REPLAY_JOB_TYPE",
    "INCIDENT_CONTROLLED_REPLAY_REQUEST_SCHEMA_VERSION",
    "INCIDENT_CONTROLLED_REPLAY_REQUIRED_CAPABILITIES",
    "IncidentControlledReplayRequest",
    "IncidentControlledReplayRequestError",
    "build_incident_controlled_replay_request",
    "enqueue_incident_controlled_replay_job",
    "parse_incident_controlled_replay_request",
]

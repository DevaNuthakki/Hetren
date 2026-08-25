"""Secure runner integration for Incident Mode compatibility evaluation.

This module connects the bounded Incident Mode evidence chain to Hetren's
existing runner-job platform.

It deliberately does not materialize an environment or execute replay.
The request envelope carries already-verified Incident Mode commitments to a
customer-controlled runner, where runner-local observations can later be
evaluated by the incident runner compatibility core.

The generic runner result path is used because compatibility evidence is not
an ASR transcription result and has no dedicated persistence authority.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app import models
from app.runner_job_service import enqueue_job
from hvee.core.contracts import HveeContractError
from hvee.core.incident_environment_manifest import (
    verify_incident_environment_manifest_bundle,
)
from hvee.core.incident_intake import (
    verify_incident_intake_bundle,
)
from hvee.core.incident_replay_preparation import (
    verify_incident_replay_preparation_bundle,
)
from hvee.core.incident_runner_compatibility import (
    IncidentRunnerCompatibilityBundle,
    IncidentRunnerEnvironmentObservation,
    build_incident_runner_compatibility_bundle,
)


INCIDENT_REPLAY_COMPATIBILITY_JOB_TYPE = (
    "incident_replay_compatibility"
)
INCIDENT_REPLAY_COMPATIBILITY_REQUEST_SCHEMA_VERSION = 1

INCIDENT_REPLAY_COMPATIBILITY_REQUIRED_CAPABILITIES = (
    "asr",
    "incident_replay",
)

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")

_REQUEST_TYPE = "incident_replay_compatibility_request"

_TOP_LEVEL_KEYS = {
    "schema_version",
    "type",
    "evidence",
}

_EVIDENCE_KEYS = {
    "incident_intake",
    "replay_preparation",
    "environment_manifest",
}

_EVIDENCE_ENTRY_KEYS = {
    "payload",
    "sha256",
}


def _require_sha256_hex(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or _SHA256_PATTERN.fullmatch(value) is None
    ):
        raise HveeContractError(
            f"{name} must be lowercase SHA-256 hex"
        )

    return value


def _canonical_json_value(
    value: object,
    *,
    name: str,
) -> object:
    try:
        serialized = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise HveeContractError(
            f"{name} must be deterministic JSON"
        ) from exc

    return json.loads(serialized)


def _require_payload(
    *,
    name: str,
    value: object,
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise HveeContractError(
            f"{name} must be a JSON object"
        )

    canonical = _canonical_json_value(
        value,
        name=name,
    )

    if not isinstance(canonical, dict):
        raise HveeContractError(
            f"{name} must be a JSON object"
        )

    return canonical


@dataclass(frozen=True, slots=True)
class IncidentReplayCompatibilityRequest:
    """Canonical verified input delivered to a customer runner."""

    intake_payload: dict[str, object]
    intake_sha256: str

    replay_preparation_payload: dict[str, object]
    replay_preparation_sha256: str

    environment_manifest_payload: dict[str, object]
    environment_manifest_sha256: str

    @property
    def payload(self) -> dict[str, object]:
        value = {
            "schema_version": (
                INCIDENT_REPLAY_COMPATIBILITY_REQUEST_SCHEMA_VERSION
            ),
            "type": _REQUEST_TYPE,
            "evidence": {
                "incident_intake": {
                    "payload": self.intake_payload,
                    "sha256": self.intake_sha256,
                },
                "replay_preparation": {
                    "payload": self.replay_preparation_payload,
                    "sha256": self.replay_preparation_sha256,
                },
                "environment_manifest": {
                    "payload": self.environment_manifest_payload,
                    "sha256": self.environment_manifest_sha256,
                },
            },
        }

        canonical = _canonical_json_value(
            value,
            name="incident replay compatibility request",
        )

        if not isinstance(canonical, dict):
            raise HveeContractError(
                "incident replay compatibility request "
                "must be a JSON object"
            )

        return canonical


def _verify_upstream_evidence(
    *,
    intake_payload: dict[str, object],
    intake_sha256: str,
    replay_preparation_payload: dict[str, object],
    replay_preparation_sha256: str,
    environment_manifest_payload: dict[str, object],
    environment_manifest_sha256: str,
) -> None:
    if not verify_incident_intake_bundle(
        payload=intake_payload,
        expected_sha256=intake_sha256,
    ):
        raise HveeContractError(
            "incident intake evidence failed verification"
        )

    if not verify_incident_replay_preparation_bundle(
        payload=replay_preparation_payload,
        expected_sha256=replay_preparation_sha256,
        intake_payload=intake_payload,
        expected_intake_sha256=intake_sha256,
    ):
        raise HveeContractError(
            "incident replay preparation failed verification"
        )

    if not verify_incident_environment_manifest_bundle(
        payload=environment_manifest_payload,
        expected_sha256=environment_manifest_sha256,
        intake_payload=intake_payload,
        expected_intake_sha256=intake_sha256,
        replay_preparation_payload=replay_preparation_payload,
        expected_replay_preparation_sha256=(
            replay_preparation_sha256
        ),
    ):
        raise HveeContractError(
            "incident environment manifest failed verification"
        )


def build_incident_replay_compatibility_request(
    *,
    intake_payload: object,
    expected_intake_sha256: object,
    replay_preparation_payload: object,
    expected_replay_preparation_sha256: object,
    environment_manifest_payload: object,
    expected_environment_manifest_sha256: object,
) -> IncidentReplayCompatibilityRequest:
    canonical_intake = _require_payload(
        name="incident intake payload",
        value=intake_payload,
    )
    canonical_preparation = _require_payload(
        name="incident replay preparation payload",
        value=replay_preparation_payload,
    )
    canonical_manifest = _require_payload(
        name="incident environment manifest payload",
        value=environment_manifest_payload,
    )

    intake_sha256 = _require_sha256_hex(
        name="incident intake SHA-256",
        value=expected_intake_sha256,
    )
    replay_preparation_sha256 = _require_sha256_hex(
        name="incident replay preparation SHA-256",
        value=expected_replay_preparation_sha256,
    )
    environment_manifest_sha256 = _require_sha256_hex(
        name="incident environment manifest SHA-256",
        value=expected_environment_manifest_sha256,
    )

    _verify_upstream_evidence(
        intake_payload=canonical_intake,
        intake_sha256=intake_sha256,
        replay_preparation_payload=canonical_preparation,
        replay_preparation_sha256=replay_preparation_sha256,
        environment_manifest_payload=canonical_manifest,
        environment_manifest_sha256=environment_manifest_sha256,
    )

    return IncidentReplayCompatibilityRequest(
        intake_payload=canonical_intake,
        intake_sha256=intake_sha256,
        replay_preparation_payload=canonical_preparation,
        replay_preparation_sha256=replay_preparation_sha256,
        environment_manifest_payload=canonical_manifest,
        environment_manifest_sha256=environment_manifest_sha256,
    )


def parse_incident_replay_compatibility_request(
    payload: object,
) -> IncidentReplayCompatibilityRequest:
    canonical = _require_payload(
        name="incident replay compatibility request",
        value=payload,
    )

    if set(canonical) != _TOP_LEVEL_KEYS:
        raise HveeContractError(
            "incident replay compatibility request shape is invalid"
        )

    if (
        canonical.get("schema_version")
        != INCIDENT_REPLAY_COMPATIBILITY_REQUEST_SCHEMA_VERSION
        or canonical.get("type") != _REQUEST_TYPE
    ):
        raise HveeContractError(
            "incident replay compatibility request identity is invalid"
        )

    evidence = canonical.get("evidence")

    if (
        not isinstance(evidence, dict)
        or set(evidence) != _EVIDENCE_KEYS
    ):
        raise HveeContractError(
            "incident replay compatibility evidence shape is invalid"
        )

    parsed: dict[str, tuple[dict[str, object], str]] = {}

    for key in sorted(_EVIDENCE_KEYS):
        entry = evidence.get(key)

        if (
            not isinstance(entry, dict)
            or set(entry) != _EVIDENCE_ENTRY_KEYS
        ):
            raise HveeContractError(
                f"{key} evidence entry shape is invalid"
            )

        parsed[key] = (
            _require_payload(
                name=f"{key} payload",
                value=entry.get("payload"),
            ),
            _require_sha256_hex(
                name=f"{key} SHA-256",
                value=entry.get("sha256"),
            ),
        )

    intake_payload, intake_sha256 = parsed[
        "incident_intake"
    ]
    preparation_payload, preparation_sha256 = parsed[
        "replay_preparation"
    ]
    manifest_payload, manifest_sha256 = parsed[
        "environment_manifest"
    ]

    _verify_upstream_evidence(
        intake_payload=intake_payload,
        intake_sha256=intake_sha256,
        replay_preparation_payload=preparation_payload,
        replay_preparation_sha256=preparation_sha256,
        environment_manifest_payload=manifest_payload,
        environment_manifest_sha256=manifest_sha256,
    )

    return IncidentReplayCompatibilityRequest(
        intake_payload=intake_payload,
        intake_sha256=intake_sha256,
        replay_preparation_payload=preparation_payload,
        replay_preparation_sha256=preparation_sha256,
        environment_manifest_payload=manifest_payload,
        environment_manifest_sha256=manifest_sha256,
    )


def evaluate_incident_replay_compatibility_request(
    *,
    request_payload: object,
    required_capabilities: list[str] | tuple[str, ...],
    observation: IncidentRunnerEnvironmentObservation,
) -> IncidentRunnerCompatibilityBundle:
    request = parse_incident_replay_compatibility_request(
        request_payload
    )

    return build_incident_runner_compatibility_bundle(
        intake_payload=request.intake_payload,
        expected_intake_sha256=request.intake_sha256,
        replay_preparation_payload=(
            request.replay_preparation_payload
        ),
        expected_replay_preparation_sha256=(
            request.replay_preparation_sha256
        ),
        environment_manifest_payload=(
            request.environment_manifest_payload
        ),
        expected_environment_manifest_sha256=(
            request.environment_manifest_sha256
        ),
        required_capabilities=required_capabilities,
        observation=observation,
    )


def enqueue_incident_replay_compatibility_job(
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
        environment_manifest_payload=environment_manifest_payload,
        expected_environment_manifest_sha256=(
            expected_environment_manifest_sha256
        ),
    )

    return enqueue_job(
        db,
        project_id=project_id,
        name=name,
        job_type=INCIDENT_REPLAY_COMPATIBILITY_JOB_TYPE,
        required_capabilities=list(
            INCIDENT_REPLAY_COMPATIBILITY_REQUIRED_CAPABILITIES
        ),
        input_payload=request.payload,
        priority=priority,
        max_attempts=max_attempts,
    )


__all__ = [
    "INCIDENT_REPLAY_COMPATIBILITY_JOB_TYPE",
    "INCIDENT_REPLAY_COMPATIBILITY_REQUEST_SCHEMA_VERSION",
    "INCIDENT_REPLAY_COMPATIBILITY_REQUIRED_CAPABILITIES",
    "IncidentReplayCompatibilityRequest",
    "build_incident_replay_compatibility_request",
    "enqueue_incident_replay_compatibility_job",
    "evaluate_incident_replay_compatibility_request",
    "parse_incident_replay_compatibility_request",
]

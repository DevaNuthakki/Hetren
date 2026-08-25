"""Tamper-evident Incident Mode controlled replay execution evidence.

This is the seventh bounded Incident Mode stage.

A successful bundle proves that:

1. the upstream Incident Mode environment materialization reverified;
2. the materialized environment was authorized and marked materialized;
3. every prepared replay artifact was reacquired and independently
   reverified by digest and byte length inside the customer runner;
4. the prepared replay operations through capture_replay_output were
   executed in their frozen order; and
5. a replay output commitment was captured.

This stage deliberately stops before compare_behavior_commitments.

Therefore successful controlled replay evidence does not mean that the
original incident was reproduced, a model failure was verified, a causal
explanation was established, a counterexample was confirmed, a contract
was promoted, a release gate was enabled, or qualification authority was
granted.

Raw artifact bytes, raw transcripts, transport traces, local file paths,
credentials, and environment variables are never persisted in this
evidence bundle.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from hvee.core.contracts import HveeContractError
from hvee.core.incident_environment_materialization import (
    verify_incident_environment_materialization_bundle,
)
from hvee.core.incident_runner_compatibility import (
    IncidentRunnerEnvironmentObservation,
)


INCIDENT_CONTROLLED_REPLAY_SCHEMA_VERSION = 1

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")

_EXECUTE_OPERATION = "execute_isolated_replay"
_CAPTURE_OPERATION = "capture_replay_output"
_COMPARE_OPERATION = "compare_behavior_commitments"

_CONTENT_BOUNDARY = {
    "raw_audio_embedded": False,
    "raw_transcript_embedded": False,
    "generated_transcript_commitment_embedded": True,
    "transport_trace_embedded": False,
    "artifact_bytes_embedded": False,
    "artifact_bytes_processed_inside_runner": True,
    "artifact_bytes_retained_in_evidence": False,
    "local_artifact_locator_embedded": False,
    "runner_credentials_embedded": False,
    "environment_variables_embedded": False,
    "hostnames_embedded": False,
    "network_addresses_embedded": False,
}

_EVIDENCE_BOUNDARY = {
    "incident_intake_verified": True,
    "replay_preparation_verified": True,
    "environment_manifest_verified": True,
    "runner_compatibility_verified": True,
    "environment_materialization_verified": True,
    "operator_authorization_granted": True,
    "environment_materialized": True,
    "artifact_bytes_reverified_for_replay": True,
    "replay_executed": True,
    "transcriptions_executed": True,
    "replay_output_captured": True,
    "behavior_commitments_compared": False,
    "reproduction_claimed": False,
    "model_failure_verified": False,
    "causal_explanation_claimed": False,
    "counterexample_confirmed": False,
    "contract_promoted": False,
    "blocking_release_gate_enabled": False,
    "qualification_authority": False,
}


def _require_sha256(
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


def _require_positive_integer(
    *,
    name: str,
    value: object,
) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value <= 0
    ):
        raise HveeContractError(
            f"{name} must be a positive integer"
        )

    return value


def _require_text(
    *,
    name: str,
    value: object,
) -> str:
    if not isinstance(value, str):
        raise HveeContractError(
            f"{name} must be text"
        )

    normalized = value.strip()

    if not normalized:
        raise HveeContractError(
            f"{name} must not be empty"
        )

    return normalized


def _optional_text(
    *,
    name: str,
    value: object,
) -> str | None:
    if value is None:
        return None

    return _require_text(
        name=name,
        value=value,
    )


def _canonical_json(
    value: object,
    *,
    name: str,
) -> str:
    try:
        return json.dumps(
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


def _canonical_json_value(
    value: object,
    *,
    name: str,
) -> object:
    return json.loads(
        _canonical_json(
            value,
            name=name,
        )
    )


def _calculate_sha256(
    value: object,
    *,
    name: str,
) -> str:
    return hashlib.sha256(
        _canonical_json(
            value,
            name=name,
        ).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class IncidentControlledReplayArtifactObservation:
    """One artifact independently reacquired and verified for replay."""

    kind: str
    reference_sha256: str
    expected_byte_length: int
    media_type: str
    observed_sha256: str
    observed_byte_length: int

    def __post_init__(self) -> None:
        kind = _require_text(
            name="controlled replay artifact kind",
            value=self.kind,
        )

        if kind not in {
            "source_audio",
            "transport_trace",
        }:
            raise HveeContractError(
                "controlled replay artifact kind is unsupported"
            )

        _require_sha256(
            name="controlled replay artifact reference",
            value=self.reference_sha256,
        )

        _require_positive_integer(
            name="controlled replay expected byte length",
            value=self.expected_byte_length,
        )

        _require_text(
            name="controlled replay artifact media type",
            value=self.media_type,
        )

        _require_sha256(
            name="controlled replay observed artifact SHA-256",
            value=self.observed_sha256,
        )

        _require_positive_integer(
            name="controlled replay observed byte length",
            value=self.observed_byte_length,
        )

    @property
    def identity(self) -> tuple[str, str]:
        return (
            self.kind,
            self.reference_sha256,
        )


@dataclass(frozen=True, slots=True)
class IncidentControlledReplayOutputObservation:
    """Commitment-only result captured after the bounded replay."""

    generated_transcript_sha256: str
    generated_transcript_utf8_bytes: int

    provider: str
    model_name: str

    device: str | None = None
    compute_type: str | None = None

    def __post_init__(self) -> None:
        _require_sha256(
            name="generated transcript SHA-256",
            value=self.generated_transcript_sha256,
        )

        _require_positive_integer(
            name="generated transcript UTF-8 bytes",
            value=self.generated_transcript_utf8_bytes,
        )

        _require_text(
            name="controlled replay provider",
            value=self.provider,
        )

        _require_text(
            name="controlled replay model",
            value=self.model_name,
        )

        _optional_text(
            name="controlled replay device",
            value=self.device,
        )

        _optional_text(
            name="controlled replay compute type",
            value=self.compute_type,
        )


@dataclass(frozen=True, slots=True)
class IncidentControlledReplayExecutionObservation:
    """What the runner actually completed before producing evidence."""

    completed_operations: tuple[str, ...]

    artifacts: tuple[
        IncidentControlledReplayArtifactObservation,
        ...
    ]

    output: IncidentControlledReplayOutputObservation

    def __post_init__(self) -> None:
        if (
            not isinstance(
                self.completed_operations,
                tuple,
            )
            or not self.completed_operations
        ):
            raise HveeContractError(
                "controlled replay completed operations "
                "must be a non-empty tuple"
            )

        normalized_operations = tuple(
            _require_text(
                name="controlled replay completed operation",
                value=value,
            )
            for value in self.completed_operations
        )

        if normalized_operations != self.completed_operations:
            raise HveeContractError(
                "controlled replay completed operations "
                "must already be canonical"
            )

        if not isinstance(self.artifacts, tuple):
            raise HveeContractError(
                "controlled replay artifacts must be a tuple"
            )

        if not all(
            isinstance(
                value,
                IncidentControlledReplayArtifactObservation,
            )
            for value in self.artifacts
        ):
            raise HveeContractError(
                "controlled replay artifact observations "
                "must be canonical"
            )

        ordered = tuple(
            sorted(
                self.artifacts,
                key=lambda value: value.identity,
            )
        )

        if ordered != self.artifacts:
            raise HveeContractError(
                "controlled replay artifact observations "
                "must already be canonical"
            )

        identities = tuple(
            value.identity
            for value in self.artifacts
        )

        if len(identities) != len(set(identities)):
            raise HveeContractError(
                "controlled replay artifact observations "
                "must be unique"
            )

        if not isinstance(
            self.output,
            IncidentControlledReplayOutputObservation,
        ):
            raise HveeContractError(
                "controlled replay output observation "
                "must be canonical"
            )


@dataclass(frozen=True, slots=True)
class IncidentControlledReplayBundle:
    payload: dict[str, object]
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.payload, dict):
            raise HveeContractError(
                "controlled replay payload must be a JSON object"
            )

        _require_sha256(
            name="controlled replay SHA-256",
            value=self.sha256,
        )


def calculate_incident_generated_transcript_sha256(
    transcript: str,
) -> str:
    if not isinstance(transcript, str):
        raise HveeContractError(
            "generated transcript must be text"
        )

    if not transcript.strip():
        raise HveeContractError(
            "generated transcript must not be empty"
        )

    return hashlib.sha256(
        transcript.encode("utf-8")
    ).hexdigest()


def _prepared_artifact_receipts(
    replay_preparation_payload: dict[str, object],
) -> tuple[dict[str, object], ...]:
    verification = replay_preparation_payload.get(
        "artifact_verification"
    )

    if not isinstance(verification, dict):
        raise HveeContractError(
            "controlled replay requires artifact verification"
        )

    if (
        verification.get(
            "all_referenced_artifacts_verified"
        )
        is not True
        or verification.get(
            "runner_custody_status"
        )
        != "verified"
    ):
        raise HveeContractError(
            "controlled replay requires verified artifact custody"
        )

    receipts = verification.get("receipts")

    if not isinstance(receipts, list):
        raise HveeContractError(
            "controlled replay artifact receipts are invalid"
        )

    normalized: list[dict[str, object]] = []

    for receipt in receipts:
        if (
            not isinstance(receipt, dict)
            or set(receipt)
            != {
                "kind",
                "reference_sha256",
                "expected_byte_length",
                "media_type",
                "observed_sha256",
                "observed_byte_length",
                "status",
            }
        ):
            raise HveeContractError(
                "controlled replay artifact receipt "
                "shape is invalid"
            )

        if receipt["status"] != "verified":
            raise HveeContractError(
                "controlled replay requires verified "
                "prepared artifact receipts"
            )

        kind = _require_text(
            name="prepared artifact kind",
            value=receipt["kind"],
        )

        reference = _require_sha256(
            name="prepared artifact reference",
            value=receipt["reference_sha256"],
        )

        expected_length = (
            _require_positive_integer(
                name="prepared artifact expected byte length",
                value=receipt["expected_byte_length"],
            )
        )

        observed = _require_sha256(
            name="prepared artifact observed SHA-256",
            value=receipt["observed_sha256"],
        )

        observed_length = (
            _require_positive_integer(
                name="prepared artifact observed byte length",
                value=receipt["observed_byte_length"],
            )
        )

        if (
            reference != observed
            or expected_length != observed_length
        ):
            raise HveeContractError(
                "prepared artifact receipt is not exact"
            )

        media_type = _require_text(
            name="prepared artifact media type",
            value=receipt["media_type"],
        )

        # Stage 2 verifies the complete incident evidence package.
        # Stage 7 independently reacquires only artifacts that are
        # inputs to controlled replay execution. Non-execution
        # evidence such as incident reports and reference
        # transcripts remains verified upstream but is not a
        # controlled-replay execution artifact.
        if kind in {
            "source_audio",
            "transport_trace",
        }:
            normalized.append(
                {
                    "kind": kind,
                    "reference_sha256": reference,
                    "expected_byte_length": expected_length,
                    "media_type": media_type,
                }
            )

    ordered = tuple(
        sorted(
            normalized,
            key=lambda value: (
                str(value["kind"]),
                str(value["reference_sha256"]),
            ),
        )
    )

    identities = tuple(
        (
            str(value["kind"]),
            str(value["reference_sha256"]),
        )
        for value in ordered
    )

    if len(identities) != len(set(identities)):
        raise HveeContractError(
            "prepared artifact receipts are ambiguous"
        )

    if not any(
        value["kind"] == "source_audio"
        for value in ordered
    ):
        raise HveeContractError(
            "controlled replay requires source audio"
        )

    return ordered


def _verify_execution_artifacts(
    *,
    prepared: tuple[dict[str, object], ...],
    observed: tuple[
        IncidentControlledReplayArtifactObservation,
        ...
    ],
) -> list[dict[str, object]]:
    expected_by_identity = {
        (
            str(value["kind"]),
            str(value["reference_sha256"]),
        ): value
        for value in prepared
    }

    observed_by_identity = {
        value.identity: value
        for value in observed
    }

    if set(expected_by_identity) != set(
        observed_by_identity
    ):
        raise HveeContractError(
            "controlled replay artifacts do not exactly "
            "cover prepared replay artifacts"
        )

    result: list[dict[str, object]] = []

    for identity in sorted(expected_by_identity):
        expected = expected_by_identity[identity]
        observation = observed_by_identity[identity]

        if (
            observation.reference_sha256
            != observation.observed_sha256
            or observation.expected_byte_length
            != observation.observed_byte_length
            or observation.reference_sha256
            != expected["reference_sha256"]
            or observation.expected_byte_length
            != expected["expected_byte_length"]
            or observation.media_type
            != expected["media_type"]
        ):
            raise HveeContractError(
                "controlled replay artifact "
                "reverification failed"
            )

        result.append(
            {
                "kind": observation.kind,
                "reference_sha256": (
                    observation.reference_sha256
                ),
                "expected_byte_length": (
                    observation.expected_byte_length
                ),
                "media_type": observation.media_type,
                "observed_sha256": (
                    observation.observed_sha256
                ),
                "observed_byte_length": (
                    observation.observed_byte_length
                ),
                "status": "verified",
            }
        )

    return result


def _required_execution_operations(
    replay_preparation_payload: dict[str, object],
) -> tuple[str, ...]:
    replay_plan = replay_preparation_payload.get(
        "replay_plan"
    )

    if not isinstance(replay_plan, dict):
        raise HveeContractError(
            "controlled replay requires a prepared replay plan"
        )

    if replay_plan.get("execution_started") is not False:
        raise HveeContractError(
            "prepared replay plan execution state changed"
        )

    steps = replay_plan.get("steps")

    if not isinstance(steps, list) or not steps:
        raise HveeContractError(
            "controlled replay steps are invalid"
        )

    operations: list[str] = []
    expected_ordinal = 1

    for step in steps:
        if (
            not isinstance(step, dict)
            or set(step)
            != {
                "ordinal",
                "operation",
                "input_commitment_sha256s",
                "status",
            }
        ):
            raise HveeContractError(
                "controlled replay step shape is invalid"
            )

        if step["ordinal"] != expected_ordinal:
            raise HveeContractError(
                "controlled replay step ordering changed"
            )

        expected_ordinal += 1

        if step["status"] != "planned":
            raise HveeContractError(
                "controlled replay requires planned steps"
            )

        operation = _require_text(
            name="controlled replay operation",
            value=step["operation"],
        )

        operations.append(operation)

    if _EXECUTE_OPERATION not in operations:
        raise HveeContractError(
            "controlled replay plan has no execution step"
        )

    if _CAPTURE_OPERATION not in operations:
        raise HveeContractError(
            "controlled replay plan has no output capture step"
        )

    if _COMPARE_OPERATION not in operations:
        raise HveeContractError(
            "controlled replay plan has no deferred comparison step"
        )

    execute_index = operations.index(
        _EXECUTE_OPERATION
    )
    capture_index = operations.index(
        _CAPTURE_OPERATION
    )
    compare_index = operations.index(
        _COMPARE_OPERATION
    )

    if not (
        execute_index < capture_index < compare_index
        and compare_index == len(operations) - 1
    ):
        raise HveeContractError(
            "controlled replay execution boundary changed"
        )

    return tuple(
        operations[: capture_index + 1]
    )


def _require_materialized_environment(
    payload: dict[str, object],
) -> None:
    materialization = payload.get(
        "materialization"
    )

    boundary = payload.get(
        "evidence_boundary"
    )

    if (
        not isinstance(materialization, dict)
        or materialization.get("status")
        != "materialized"
        or materialization.get(
            "environment_materialized"
        )
        is not True
    ):
        raise HveeContractError(
            "controlled replay requires a materialized environment"
        )

    if (
        not isinstance(boundary, dict)
        or boundary.get(
            "operator_authorization_granted"
        )
        is not True
        or boundary.get(
            "environment_materialized"
        )
        is not True
    ):
        raise HveeContractError(
            "controlled replay requires authorized "
            "materialization evidence"
        )


def _output_payload(
    output: IncidentControlledReplayOutputObservation,
) -> dict[str, object]:
    body = {
        "generated_transcript_sha256": (
            output.generated_transcript_sha256
        ),
        "generated_transcript_utf8_bytes": (
            output.generated_transcript_utf8_bytes
        ),
        "provider": output.provider,
        "model_name": output.model_name,
        "device": output.device,
        "compute_type": output.compute_type,
    }

    return {
        **body,
        "replay_output_sha256": _calculate_sha256(
            body,
            name="controlled replay output",
        ),
    }


def calculate_incident_controlled_replay_sha256(
    payload: dict[str, object],
) -> str:
    return _calculate_sha256(
        payload,
        name="incident controlled replay",
    )


def build_incident_controlled_replay_bundle(
    *,
    intake_payload: object,
    expected_intake_sha256: object,
    replay_preparation_payload: object,
    expected_replay_preparation_sha256: object,
    environment_manifest_payload: object,
    expected_environment_manifest_sha256: object,
    runner_compatibility_payload: object,
    expected_runner_compatibility_sha256: object,
    required_capabilities: list[str] | tuple[str, ...],
    compatibility_observation: (
        IncidentRunnerEnvironmentObservation
    ),
    environment_materialization_payload: object,
    expected_environment_materialization_sha256: object,
    execution_observation: (
        IncidentControlledReplayExecutionObservation
    ),
) -> IncidentControlledReplayBundle:
    intake_sha256 = _require_sha256(
        name="controlled replay intake SHA-256",
        value=expected_intake_sha256,
    )

    preparation_sha256 = _require_sha256(
        name="controlled replay preparation SHA-256",
        value=expected_replay_preparation_sha256,
    )

    manifest_sha256 = _require_sha256(
        name="controlled replay environment manifest SHA-256",
        value=expected_environment_manifest_sha256,
    )

    compatibility_sha256 = _require_sha256(
        name="controlled replay compatibility SHA-256",
        value=expected_runner_compatibility_sha256,
    )

    materialization_sha256 = _require_sha256(
        name="controlled replay materialization SHA-256",
        value=expected_environment_materialization_sha256,
    )

    if not isinstance(
        compatibility_observation,
        IncidentRunnerEnvironmentObservation,
    ):
        raise HveeContractError(
            "controlled replay compatibility observation "
            "must be canonical"
        )

    if not isinstance(
        execution_observation,
        IncidentControlledReplayExecutionObservation,
    ):
        raise HveeContractError(
            "controlled replay execution observation "
            "must be canonical"
        )

    upstream_payloads = (
        intake_payload,
        replay_preparation_payload,
        environment_manifest_payload,
        runner_compatibility_payload,
        environment_materialization_payload,
    )

    if not all(
        isinstance(value, dict)
        for value in upstream_payloads
    ):
        raise HveeContractError(
            "controlled replay upstream evidence "
            "must be JSON objects"
        )

    if not (
        verify_incident_environment_materialization_bundle(
            payload=environment_materialization_payload,
            expected_sha256=materialization_sha256,
            intake_payload=intake_payload,
            expected_intake_sha256=intake_sha256,
            replay_preparation_payload=(
                replay_preparation_payload
            ),
            expected_replay_preparation_sha256=(
                preparation_sha256
            ),
            environment_manifest_payload=(
                environment_manifest_payload
            ),
            expected_environment_manifest_sha256=(
                manifest_sha256
            ),
            runner_compatibility_payload=(
                runner_compatibility_payload
            ),
            expected_runner_compatibility_sha256=(
                compatibility_sha256
            ),
            required_capabilities=(
                required_capabilities
            ),
            compatibility_observation=(
                compatibility_observation
            ),
        )
    ):
        raise HveeContractError(
            "controlled replay materialization "
            "failed verification"
        )

    _require_materialized_environment(
        environment_materialization_payload
    )

    prepared_artifacts = (
        _prepared_artifact_receipts(
            replay_preparation_payload
        )
    )

    artifact_receipts = (
        _verify_execution_artifacts(
            prepared=prepared_artifacts,
            observed=(
                execution_observation.artifacts
            ),
        )
    )

    required_operations = (
        _required_execution_operations(
            replay_preparation_payload
        )
    )

    if (
        execution_observation.completed_operations
        != required_operations
    ):
        raise HveeContractError(
            "controlled replay completed operations "
            "do not match the frozen replay plan"
        )

    if (
        _COMPARE_OPERATION
        in execution_observation.completed_operations
    ):
        raise HveeContractError(
            "behavior commitment comparison belongs "
            "to reproduction evidence"
        )

    incident = intake_payload.get("incident")

    if not isinstance(incident, dict):
        raise HveeContractError(
            "controlled replay incident identity "
            "must be canonical"
        )

    output = _output_payload(
        execution_observation.output
    )

    payload: dict[str, object] = {
        "schema_version": (
            INCIDENT_CONTROLLED_REPLAY_SCHEMA_VERSION
        ),
        "type": "incident_controlled_replay",
        "evaluation_type": intake_payload[
            "evaluation_type"
        ],
        "incident": {
            "key": incident["key"],
            "version": incident["version"],
            "intake_sha256": intake_sha256,
            "replay_preparation_sha256": (
                preparation_sha256
            ),
            "environment_manifest_sha256": (
                manifest_sha256
            ),
            "runner_compatibility_sha256": (
                compatibility_sha256
            ),
            "environment_materialization_sha256": (
                materialization_sha256
            ),
        },
        "execution": {
            "status": "executed",
            "execution_scope": (
                "customer_controlled_runner"
            ),
            "completed_operations": list(
                execution_observation.completed_operations
            ),
            "deferred_operation": (
                _COMPARE_OPERATION
            ),
            "artifact_reverification": {
                "status": "verified",
                "count": len(
                    artifact_receipts
                ),
                "receipts": artifact_receipts,
            },
            "output": output,
        },
        "policy": {
            "prepared_plan_execution_required": True,
            "artifact_digest_reverification_required": True,
            "artifact_length_reverification_required": True,
            "temporary_runner_workspace_required": True,
            "behavior_comparison_deferred_to_reproduction_stage": True,
            "successful_execution_is_not_reproduction": True,
        },
        "content_boundary": dict(
            _CONTENT_BOUNDARY
        ),
        "evidence_boundary": dict(
            _EVIDENCE_BOUNDARY
        ),
    }

    canonical = _canonical_json_value(
        payload,
        name="incident controlled replay",
    )

    if not isinstance(canonical, dict):
        raise HveeContractError(
            "controlled replay evidence "
            "must be a JSON object"
        )

    return IncidentControlledReplayBundle(
        payload=canonical,
        sha256=(
            calculate_incident_controlled_replay_sha256(
                canonical
            )
        ),
    )


def _parse_execution_observation(
    payload: dict[str, object],
) -> IncidentControlledReplayExecutionObservation:
    execution = payload.get("execution")

    if not isinstance(execution, dict):
        raise HveeContractError(
            "controlled replay execution payload "
            "is invalid"
        )

    operations = execution.get(
        "completed_operations"
    )

    artifact_reverification = execution.get(
        "artifact_reverification"
    )

    output = execution.get("output")

    if not isinstance(operations, list):
        raise HveeContractError(
            "controlled replay completed operations "
            "are invalid"
        )

    if not isinstance(
        artifact_reverification,
        dict,
    ):
        raise HveeContractError(
            "controlled replay artifact evidence "
            "is invalid"
        )

    receipts = artifact_reverification.get(
        "receipts"
    )

    if not isinstance(receipts, list):
        raise HveeContractError(
            "controlled replay artifact receipts "
            "are invalid"
        )

    artifacts = []

    for receipt in receipts:
        if not isinstance(receipt, dict):
            raise HveeContractError(
                "controlled replay artifact receipt "
                "is invalid"
            )

        artifacts.append(
            IncidentControlledReplayArtifactObservation(
                kind=receipt["kind"],
                reference_sha256=(
                    receipt["reference_sha256"]
                ),
                expected_byte_length=(
                    receipt["expected_byte_length"]
                ),
                media_type=receipt["media_type"],
                observed_sha256=(
                    receipt["observed_sha256"]
                ),
                observed_byte_length=(
                    receipt["observed_byte_length"]
                ),
            )
        )

    if not isinstance(output, dict):
        raise HveeContractError(
            "controlled replay output evidence "
            "is invalid"
        )

    output_observation = (
        IncidentControlledReplayOutputObservation(
            generated_transcript_sha256=(
                output[
                    "generated_transcript_sha256"
                ]
            ),
            generated_transcript_utf8_bytes=(
                output[
                    "generated_transcript_utf8_bytes"
                ]
            ),
            provider=output["provider"],
            model_name=output["model_name"],
            device=output["device"],
            compute_type=output[
                "compute_type"
            ],
        )
    )

    return (
        IncidentControlledReplayExecutionObservation(
            completed_operations=tuple(
                operations
            ),
            artifacts=tuple(
                artifacts
            ),
            output=output_observation,
        )
    )


def verify_incident_controlled_replay_bundle(
    *,
    payload: object,
    expected_sha256: object,
    intake_payload: object,
    expected_intake_sha256: object,
    replay_preparation_payload: object,
    expected_replay_preparation_sha256: object,
    environment_manifest_payload: object,
    expected_environment_manifest_sha256: object,
    runner_compatibility_payload: object,
    expected_runner_compatibility_sha256: object,
    required_capabilities: list[str] | tuple[str, ...],
    compatibility_observation: (
        IncidentRunnerEnvironmentObservation
    ),
    environment_materialization_payload: object,
    expected_environment_materialization_sha256: object,
) -> bool:
    try:
        replay_sha256 = _require_sha256(
            name="expected controlled replay SHA-256",
            value=expected_sha256,
        )

        if not isinstance(payload, dict):
            return False

        observation = (
            _parse_execution_observation(
                payload
            )
        )

        rebuilt = (
            build_incident_controlled_replay_bundle(
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
                required_capabilities=(
                    required_capabilities
                ),
                compatibility_observation=(
                    compatibility_observation
                ),
                environment_materialization_payload=(
                    environment_materialization_payload
                ),
                expected_environment_materialization_sha256=(
                    expected_environment_materialization_sha256
                ),
                execution_observation=(
                    observation
                ),
            )
        )

        return (
            payload == rebuilt.payload
            and replay_sha256
            == rebuilt.sha256
            and (
                calculate_incident_controlled_replay_sha256(
                    payload
                )
                == replay_sha256
            )
        )

    except (
        HveeContractError,
        KeyError,
        TypeError,
        ValueError,
    ):
        return False


__all__ = [
    "INCIDENT_CONTROLLED_REPLAY_SCHEMA_VERSION",
    "IncidentControlledReplayArtifactObservation",
    "IncidentControlledReplayBundle",
    "IncidentControlledReplayExecutionObservation",
    "IncidentControlledReplayOutputObservation",
    "build_incident_controlled_replay_bundle",
    "calculate_incident_controlled_replay_sha256",
    "calculate_incident_generated_transcript_sha256",
    "verify_incident_controlled_replay_bundle",
]

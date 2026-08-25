"""Tamper-evident Incident Mode environment materialization evidence.

This is the sixth bounded Incident Mode stage.

It consumes already-verified Incident Mode evidence through runner
compatibility and records whether a customer-controlled runner actually
established the commitments required for controlled replay.

The durable evidence contains commitments only. It does not persist raw
runtime, audio, transport, credential, environment-variable, hostname,
network-address, or local-path values.

A materialized environment is still not replay execution. This stage does
not load the ASR model, transcribe audio, execute replay, claim reproduction,
prove model failure, promote a contract, change release policy, or grant
qualification authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum

from hvee.core.contracts import HveeContractError
from hvee.core.incident_runner_compatibility import (
    IncidentRunnerEnvironmentObservation,
    verify_incident_runner_compatibility_bundle,
)


INCIDENT_ENVIRONMENT_MATERIALIZATION_SCHEMA_VERSION = 1

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_REQUIREMENT_PATTERN = re.compile(
    r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$"
)

_OPERATOR_AUTHORIZATION_SCOPE = (
    "incident_environment_materialization"
)

_HOST_REQUIREMENT = "runtime.host_environment_sha256"

_ALLOWED_COMPATIBILITY_STATUSES = {
    "exact",
    "compatible",
}

_CONTENT_BOUNDARY = {
    "runtime_context_values_embedded": False,
    "audio_context_values_embedded": False,
    "transport_context_values_embedded": False,
    "environment_values_embedded": False,
    "materialized_value_commitments_embedded": True,
    "operator_identity_embedded": False,
    "operator_authorization_payload_embedded": False,
    "operator_authorization_commitment_embedded": True,
    "runner_credentials_embedded": False,
    "hostnames_embedded": False,
    "network_addresses_embedded": False,
    "environment_variables_embedded": False,
    "file_paths_embedded": False,
    "artifact_bytes_embedded": False,
    "model_output_embedded": False,
}

_BASE_EVIDENCE_BOUNDARY = {
    "incident_intake_verified": True,
    "replay_preparation_verified": True,
    "environment_manifest_verified": True,
    "runner_compatibility_verified": True,
    "runner_local_materialization_evaluated": True,
    "models_loaded": False,
    "replay_executed": False,
    "transcriptions_executed": False,
    "reproduction_claimed": False,
    "model_failure_verified": False,
    "causal_explanation_claimed": False,
    "counterexample_confirmed": False,
    "contract_promoted": False,
    "blocking_release_gate_enabled": False,
    "qualification_authority": False,
}


class IncidentEnvironmentMaterializationStatus(StrEnum):
    MATERIALIZED = "materialized"
    BLOCKED_COMPATIBILITY = "blocked_compatibility"
    BLOCKED_AUTHORIZATION = "blocked_authorization"
    BLOCKED_MISSING_OBSERVATION = (
        "blocked_missing_observation"
    )
    BLOCKED_MISMATCH = "blocked_mismatch"


class IncidentMaterializedRequirementStatus(StrEnum):
    MATCHED = "matched"
    PORTABLE_HOST = "portable_host"
    MISSING = "missing"
    MISMATCH = "mismatch"


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


def _require_optional_sha256_hex(
    *,
    name: str,
    value: object,
) -> str | None:
    if value is None:
        return None
    return _require_sha256_hex(
        name=name,
        value=value,
    )


def _require_requirement(
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or _REQUIREMENT_PATTERN.fullmatch(value) is None
    ):
        raise HveeContractError(
            "materialization requirement must be canonical"
        )
    return value


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
    canonical = _canonical_json(
        value,
        name=name,
    )
    return hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class IncidentOperatorAuthorization:
    """Commitment-only authorization evidence for materialization."""

    granted: bool
    authorization_sha256: str | None
    scope: str = _OPERATOR_AUTHORIZATION_SCOPE

    def __post_init__(self) -> None:
        if not isinstance(self.granted, bool):
            raise HveeContractError(
                "operator authorization grant must be boolean"
            )

        if self.scope != _OPERATOR_AUTHORIZATION_SCOPE:
            raise HveeContractError(
                "operator authorization scope is invalid"
            )

        digest = _require_optional_sha256_hex(
            name="operator authorization SHA-256",
            value=self.authorization_sha256,
        )

        if self.granted and digest is None:
            raise HveeContractError(
                "granted operator authorization requires "
                "an evidence commitment"
            )

        if not self.granted and digest is not None:
            raise HveeContractError(
                "denied operator authorization cannot carry "
                "a grant commitment"
            )


@dataclass(frozen=True, slots=True)
class IncidentMaterializedRequirementObservation:
    """One runner-local observed commitment."""

    requirement: str
    observed_commitment_sha256: str | None

    def __post_init__(self) -> None:
        _require_requirement(self.requirement)
        _require_optional_sha256_hex(
            name=(
                f"{self.requirement} observed materialization "
                "commitment"
            ),
            value=self.observed_commitment_sha256,
        )

    @property
    def identity(self) -> str:
        return self.requirement


@dataclass(frozen=True, slots=True)
class IncidentEnvironmentMaterializationBundle:
    payload: dict[str, object]
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.payload, dict):
            raise HveeContractError(
                "environment materialization payload "
                "must be a JSON object"
            )

        _require_sha256_hex(
            name="environment materialization SHA-256",
            value=self.sha256,
        )


def _canonical_observations(
    values: object,
) -> tuple[
    IncidentMaterializedRequirementObservation,
    ...
]:
    if not isinstance(values, (list, tuple)):
        raise HveeContractError(
            "materialization observations must be "
            "a list or tuple"
        )

    if not all(
        isinstance(
            value,
            IncidentMaterializedRequirementObservation,
        )
        for value in values
    ):
        raise HveeContractError(
            "materialization observations must be canonical"
        )

    ordered = tuple(
        sorted(
            values,
            key=lambda value: value.identity,
        )
    )

    identities = tuple(
        value.identity
        for value in ordered
    )

    if len(identities) != len(set(identities)):
        raise HveeContractError(
            "materialization requirement observations "
            "must be unique"
        )

    return ordered


def _require_compatibility_contract(
    payload: object,
) -> tuple[
    str,
    bool,
    list[dict[str, object]],
]:
    if not isinstance(payload, dict):
        raise HveeContractError(
            "runner compatibility payload must be "
            "a JSON object"
        )

    compatibility = payload.get("compatibility")

    if not isinstance(compatibility, dict):
        raise HveeContractError(
            "runner compatibility summary is invalid"
        )

    status = compatibility.get("status")
    ready = compatibility.get(
        "ready_for_materialization"
    )
    requirements = compatibility.get("requirements")

    if not isinstance(status, str):
        raise HveeContractError(
            "runner compatibility status is invalid"
        )

    if not isinstance(ready, bool):
        raise HveeContractError(
            "runner compatibility readiness is invalid"
        )

    if not isinstance(requirements, list):
        raise HveeContractError(
            "runner compatibility requirements are invalid"
        )

    normalized: list[dict[str, object]] = []

    for value in requirements:
        if (
            not isinstance(value, dict)
            or set(value)
            != {
                "requirement",
                "level",
                "expected_commitment_sha256",
                "observed_commitment_sha256",
            }
        ):
            raise HveeContractError(
                "runner compatibility requirement "
                "shape is invalid"
            )

        requirement = _require_requirement(
            value["requirement"]
        )

        expected = _require_optional_sha256_hex(
            name=(
                f"{requirement} expected compatibility "
                "commitment"
            ),
            value=value[
                "expected_commitment_sha256"
            ],
        )

        observed = _require_optional_sha256_hex(
            name=(
                f"{requirement} observed compatibility "
                "commitment"
            ),
            value=value[
                "observed_commitment_sha256"
            ],
        )

        level = value["level"]

        if level not in {
            "exact",
            "compatible",
            "unobserved",
            "unsupported",
        }:
            raise HveeContractError(
                "runner compatibility requirement "
                "level is invalid"
            )

        normalized.append(
            {
                "requirement": requirement,
                "level": level,
                "expected_commitment_sha256": expected,
                "observed_commitment_sha256": observed,
            }
        )

    requirements_sorted = sorted(
        normalized,
        key=lambda value: str(
            value["requirement"]
        ),
    )

    if normalized != requirements_sorted:
        raise HveeContractError(
            "runner compatibility requirements "
            "must already be canonical"
        )

    return (
        status,
        ready,
        normalized,
    )


def _required_expected_commitments(
    requirements: list[dict[str, object]],
) -> dict[str, str]:
    result: dict[str, str] = {}

    for value in requirements:
        expected = value[
            "expected_commitment_sha256"
        ]

        if expected is None:
            continue

        requirement = str(value["requirement"])

        if requirement in result:
            raise HveeContractError(
                "runner compatibility requirement "
                "identity is duplicated"
            )

        result[requirement] = str(expected)

    return result


def _evaluate_requirements(
    *,
    expected: dict[str, str],
    observations: tuple[
        IncidentMaterializedRequirementObservation,
        ...
    ],
) -> list[dict[str, object]]:
    observed_by_requirement = {
        value.requirement: (
            value.observed_commitment_sha256
        )
        for value in observations
    }

    unexpected = (
        set(observed_by_requirement)
        - set(expected)
    )

    if unexpected:
        raise HveeContractError(
            "materialization observation contains "
            "an unexpected requirement"
        )

    results: list[dict[str, object]] = []

    for requirement in sorted(expected):
        expected_digest = expected[requirement]
        observed_digest = observed_by_requirement.get(
            requirement
        )

        if observed_digest is None:
            status = (
                IncidentMaterializedRequirementStatus
                .MISSING
            )
        elif requirement == _HOST_REQUIREMENT:
            status = (
                IncidentMaterializedRequirementStatus
                .MATCHED
                if observed_digest == expected_digest
                else IncidentMaterializedRequirementStatus
                .PORTABLE_HOST
            )
        elif observed_digest == expected_digest:
            status = (
                IncidentMaterializedRequirementStatus
                .MATCHED
            )
        else:
            status = (
                IncidentMaterializedRequirementStatus
                .MISMATCH
            )

        results.append(
            {
                "requirement": requirement,
                "status": status.value,
                "expected_commitment_sha256": (
                    expected_digest
                ),
                "observed_commitment_sha256": (
                    observed_digest
                ),
            }
        )

    return results


def _materialization_status(
    *,
    compatibility_status: str,
    ready_for_materialization: bool,
    authorization: IncidentOperatorAuthorization,
    requirements: list[dict[str, object]],
) -> IncidentEnvironmentMaterializationStatus:
    if (
        not ready_for_materialization
        or compatibility_status
        not in _ALLOWED_COMPATIBILITY_STATUSES
    ):
        return (
            IncidentEnvironmentMaterializationStatus
            .BLOCKED_COMPATIBILITY
        )

    if not authorization.granted:
        return (
            IncidentEnvironmentMaterializationStatus
            .BLOCKED_AUTHORIZATION
        )

    statuses = {
        str(value["status"])
        for value in requirements
    }

    if (
        IncidentMaterializedRequirementStatus
        .MISMATCH.value
        in statuses
    ):
        return (
            IncidentEnvironmentMaterializationStatus
            .BLOCKED_MISMATCH
        )

    if (
        IncidentMaterializedRequirementStatus
        .MISSING.value
        in statuses
    ):
        return (
            IncidentEnvironmentMaterializationStatus
            .BLOCKED_MISSING_OBSERVATION
        )

    return (
        IncidentEnvironmentMaterializationStatus
        .MATERIALIZED
    )


def _blockers(
    *,
    status: IncidentEnvironmentMaterializationStatus,
    requirements: list[dict[str, object]],
) -> list[str]:
    blockers: list[str] = []

    if (
        status
        == IncidentEnvironmentMaterializationStatus
        .BLOCKED_COMPATIBILITY
    ):
        blockers.append(
            "runner_compatibility_not_ready"
        )

    if (
        status
        == IncidentEnvironmentMaterializationStatus
        .BLOCKED_AUTHORIZATION
    ):
        blockers.append(
            "operator_authorization_required"
        )

    for value in requirements:
        requirement_status = value["status"]

        if requirement_status == (
            IncidentMaterializedRequirementStatus
            .MISSING.value
        ):
            blockers.append(
                f"missing:{value['requirement']}"
            )
        elif requirement_status == (
            IncidentMaterializedRequirementStatus
            .MISMATCH.value
        ):
            blockers.append(
                f"mismatch:{value['requirement']}"
            )

    return sorted(blockers)


def _assemble_bundle(
    *,
    intake_payload: dict[str, object],
    intake_sha256: str,
    replay_preparation_sha256: str,
    environment_manifest_sha256: str,
    runner_compatibility_sha256: str,
    compatibility_payload: dict[str, object],
    authorization: IncidentOperatorAuthorization,
    observations: tuple[
        IncidentMaterializedRequirementObservation,
        ...
    ],
) -> IncidentEnvironmentMaterializationBundle:
    (
        compatibility_status,
        ready_for_materialization,
        compatibility_requirements,
    ) = _require_compatibility_contract(
        compatibility_payload
    )

    expected = _required_expected_commitments(
        compatibility_requirements
    )

    evaluated_requirements = (
        _evaluate_requirements(
            expected=expected,
            observations=observations,
        )
    )

    status = _materialization_status(
        compatibility_status=compatibility_status,
        ready_for_materialization=(
            ready_for_materialization
        ),
        authorization=authorization,
        requirements=evaluated_requirements,
    )

    incident = intake_payload.get("incident")

    if not isinstance(incident, dict):
        raise HveeContractError(
            "incident identity must be canonical"
        )

    observed_count = sum(
        value["observed_commitment_sha256"]
        is not None
        for value in evaluated_requirements
    )

    matched_count = sum(
        value["status"]
        in {
            IncidentMaterializedRequirementStatus
            .MATCHED.value,
            IncidentMaterializedRequirementStatus
            .PORTABLE_HOST.value,
        }
        for value in evaluated_requirements
    )

    materialized = (
        status
        == IncidentEnvironmentMaterializationStatus
        .MATERIALIZED
    )

    payload: dict[str, object] = {
        "schema_version": (
            INCIDENT_ENVIRONMENT_MATERIALIZATION_SCHEMA_VERSION
        ),
        "type": "incident_environment_materialization",
        "evaluation_type": intake_payload[
            "evaluation_type"
        ],
        "incident": {
            "key": incident["key"],
            "version": incident["version"],
            "intake_sha256": intake_sha256,
            "replay_preparation_sha256": (
                replay_preparation_sha256
            ),
            "environment_manifest_sha256": (
                environment_manifest_sha256
            ),
            "runner_compatibility_sha256": (
                runner_compatibility_sha256
            ),
        },
        "materialization": {
            "status": status.value,
            "environment_materialized": materialized,
            "operator_authorization": {
                "scope": authorization.scope,
                "granted": authorization.granted,
                "authorization_sha256": (
                    authorization.authorization_sha256
                ),
            },
            "required_count": len(
                evaluated_requirements
            ),
            "observed_count": observed_count,
            "matched_count": matched_count,
            "blockers": _blockers(
                status=status,
                requirements=evaluated_requirements,
            ),
            "requirements": evaluated_requirements,
        },
        "policy": {
            "portable_runtime_identity_required": True,
            "host_environment_identity_may_differ": True,
            "operator_authorization_required": True,
            "exact_runner_local_observation_required": True,
            "expected_values_cannot_substitute_for_observation": True,
            "raw_environment_values_not_durable": True,
        },
        "content_boundary": dict(
            _CONTENT_BOUNDARY
        ),
        "evidence_boundary": {
            **_BASE_EVIDENCE_BOUNDARY,
            "operator_authorization_granted": (
                authorization.granted
            ),
            "environment_materialized": materialized,
        },
    }

    canonical = _canonical_json_value(
        payload,
        name="incident environment materialization",
    )

    if not isinstance(canonical, dict):
        raise HveeContractError(
            "environment materialization "
            "must be a JSON object"
        )

    return IncidentEnvironmentMaterializationBundle(
        payload=canonical,
        sha256=(
            calculate_incident_environment_materialization_sha256(
                canonical
            )
        ),
    )


def calculate_incident_materialized_value_commitment(
    value: object,
) -> str:
    """Commit one runner-local materialized value without persisting it."""
    return _calculate_sha256(
        value,
        name="incident materialized value commitment",
    )


def calculate_incident_environment_materialization_sha256(
    payload: dict[str, object],
) -> str:
    return _calculate_sha256(
        payload,
        name="incident environment materialization",
    )


def build_incident_environment_materialization_bundle(
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
    authorization: IncidentOperatorAuthorization,
    materialization_observations: list[
        IncidentMaterializedRequirementObservation
    ]
    | tuple[
        IncidentMaterializedRequirementObservation,
        ...
    ],
) -> IncidentEnvironmentMaterializationBundle:
    intake_sha256 = _require_sha256_hex(
        name="incident intake SHA-256",
        value=expected_intake_sha256,
    )
    replay_preparation_sha256 = _require_sha256_hex(
        name="replay preparation SHA-256",
        value=expected_replay_preparation_sha256,
    )
    environment_manifest_sha256 = _require_sha256_hex(
        name="environment manifest SHA-256",
        value=expected_environment_manifest_sha256,
    )
    runner_compatibility_sha256 = _require_sha256_hex(
        name="runner compatibility SHA-256",
        value=expected_runner_compatibility_sha256,
    )

    if not isinstance(
        compatibility_observation,
        IncidentRunnerEnvironmentObservation,
    ):
        raise HveeContractError(
            "runner compatibility observation "
            "must be canonical"
        )

    if not isinstance(
        authorization,
        IncidentOperatorAuthorization,
    ):
        raise HveeContractError(
            "operator authorization must be canonical"
        )

    observations = _canonical_observations(
        materialization_observations
    )

    if (
        not isinstance(intake_payload, dict)
        or not isinstance(
            replay_preparation_payload,
            dict,
        )
        or not isinstance(
            environment_manifest_payload,
            dict,
        )
        or not isinstance(
            runner_compatibility_payload,
            dict,
        )
    ):
        raise HveeContractError(
            "Incident Mode upstream payloads "
            "must be JSON objects"
        )

    if not verify_incident_runner_compatibility_bundle(
        payload=runner_compatibility_payload,
        expected_sha256=runner_compatibility_sha256,
        intake_payload=intake_payload,
        expected_intake_sha256=intake_sha256,
        replay_preparation_payload=(
            replay_preparation_payload
        ),
        expected_replay_preparation_sha256=(
            replay_preparation_sha256
        ),
        environment_manifest_payload=(
            environment_manifest_payload
        ),
        expected_environment_manifest_sha256=(
            environment_manifest_sha256
        ),
        required_capabilities=required_capabilities,
        observation=compatibility_observation,
    ):
        raise HveeContractError(
            "incident runner compatibility "
            "failed verification"
        )

    return _assemble_bundle(
        intake_payload=intake_payload,
        intake_sha256=intake_sha256,
        replay_preparation_sha256=(
            replay_preparation_sha256
        ),
        environment_manifest_sha256=(
            environment_manifest_sha256
        ),
        runner_compatibility_sha256=(
            runner_compatibility_sha256
        ),
        compatibility_payload=(
            runner_compatibility_payload
        ),
        authorization=authorization,
        observations=observations,
    )


def _parse_authorization(
    value: object,
) -> IncidentOperatorAuthorization:
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "scope",
            "granted",
            "authorization_sha256",
        }
    ):
        raise HveeContractError(
            "operator authorization evidence "
            "shape is invalid"
        )

    return IncidentOperatorAuthorization(
        scope=value["scope"],
        granted=value["granted"],
        authorization_sha256=(
            value["authorization_sha256"]
        ),
    )


def _parse_materialization_observations(
    value: object,
) -> tuple[
    IncidentMaterializedRequirementObservation,
    ...
]:
    if not isinstance(value, list):
        raise HveeContractError(
            "materialization requirements "
            "must be a list"
        )

    observations = []

    for item in value:
        if (
            not isinstance(item, dict)
            or set(item)
            != {
                "requirement",
                "status",
                "expected_commitment_sha256",
                "observed_commitment_sha256",
            }
        ):
            raise HveeContractError(
                "materialization requirement "
                "shape is invalid"
            )

        observations.append(
            IncidentMaterializedRequirementObservation(
                requirement=item["requirement"],
                observed_commitment_sha256=(
                    item[
                        "observed_commitment_sha256"
                    ]
                ),
            )
        )

    return _canonical_observations(
        observations
    )


def verify_incident_environment_materialization_bundle(
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
) -> bool:
    try:
        materialization_sha256 = _require_sha256_hex(
            name="environment materialization SHA-256",
            value=expected_sha256,
        )

        if not isinstance(payload, dict):
            return False

        materialization = payload.get(
            "materialization"
        )

        if not isinstance(
            materialization,
            dict,
        ):
            return False

        authorization = _parse_authorization(
            materialization.get(
                "operator_authorization"
            )
        )

        observations = (
            _parse_materialization_observations(
                materialization.get(
                    "requirements"
                )
            )
        )

        rebuilt = (
            build_incident_environment_materialization_bundle(
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
                authorization=authorization,
                materialization_observations=(
                    observations
                ),
            )
        )

        return (
            payload == rebuilt.payload
            and materialization_sha256
            == rebuilt.sha256
            and (
                calculate_incident_environment_materialization_sha256(
                    payload
                )
                == materialization_sha256
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
    "INCIDENT_ENVIRONMENT_MATERIALIZATION_SCHEMA_VERSION",
    "IncidentEnvironmentMaterializationBundle",
    "IncidentEnvironmentMaterializationStatus",
    "IncidentMaterializedRequirementObservation",
    "IncidentMaterializedRequirementStatus",
    "IncidentOperatorAuthorization",
    "build_incident_environment_materialization_bundle",
    "calculate_incident_materialized_value_commitment",
    "calculate_incident_environment_materialization_sha256",
    "verify_incident_environment_materialization_bundle",
]

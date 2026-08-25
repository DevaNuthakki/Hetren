"""Tamper-evident Incident Mode environmental replay manifest.

This module is the third bounded Incident Mode stage.

It consumes:

1. a verified incident-intake payload; and
2. a verified, prepared incident-replay-preparation payload.

The manifest binds the runtime, audio, and transport context commitments
recorded at intake to the deterministic restore operations already present
in the replay plan.

The durable manifest deliberately does not duplicate the environmental
values themselves. Those values remain available only through the verified
incident intake inside the customer-controlled runner. The manifest records
their cryptographic commitments and the restoration contract.

Building or verifying this manifest does not mean that an environment was
materialized, a model was loaded, replay was executed, the incident was
reproduced, or a model failure was proven.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum

from hvee.core.contracts import HveeContractError
from hvee.core.incident_intake import (
    calculate_incident_context_sha256,
    verify_incident_intake_bundle,
)
from hvee.core.incident_replay_preparation import (
    verify_incident_replay_preparation_bundle,
)


INCIDENT_ENVIRONMENT_MANIFEST_SCHEMA_VERSION = 1

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")

_CONTEXT_RESTORE_OPERATIONS = (
    ("runtime", "restore_runtime_context"),
    ("audio", "restore_audio_context"),
    ("transport", "restore_transport_context"),
)

_CONTENT_BOUNDARY = {
    "runtime_context_values_embedded": False,
    "audio_context_values_embedded": False,
    "transport_context_values_embedded": False,
    "context_component_digests_embedded": True,
    "artifact_bytes_embedded": False,
    "transport_trace_embedded": False,
    "local_artifact_locator_embedded": False,
    "runner_local_context_materialization_required": True,
}

_EVIDENCE_BOUNDARY = {
    "incident_intake_verified": True,
    "replay_preparation_verified": True,
    "artifact_custody_verified": True,
    "replay_plan_prepared": True,
    "context_commitments_bound_to_restore_steps": True,
    "environment_manifest_built": True,
    "environment_materialized": False,
    "operator_authorization_granted": False,
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


class IncidentEnvironmentManifestStatus(StrEnum):
    READY = "ready"


def _require_sha256_hex(*, name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or _SHA256_PATTERN.fullmatch(value) is None
    ):
        raise HveeContractError(
            f"{name} must be lowercase SHA-256 hex"
        )
    return value


def _canonical_json(value: object, *, name: str) -> str:
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


def _canonical_json_value(value: object, *, name: str) -> object:
    return json.loads(
        _canonical_json(
            value,
            name=name,
        )
    )


def _calculate_sha256(value: object, *, name: str) -> str:
    canonical = _canonical_json(
        value,
        name=name,
    )
    return hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class IncidentEnvironmentManifestBundle:
    payload: dict[str, object]
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.payload, dict):
            raise HveeContractError(
                "incident environment manifest payload "
                "must be a JSON object"
            )
        _require_sha256_hex(
            name="incident environment manifest SHA-256",
            value=self.sha256,
        )


def _require_context(
    intake_payload: dict[str, object],
) -> dict[str, object]:
    context = intake_payload.get("context")
    if not isinstance(context, dict):
        raise HveeContractError(
            "incident environment context must be canonical"
        )

    expected_keys = {
        "runtime",
        "audio",
        "transport",
    }
    if not expected_keys.issubset(context):
        raise HveeContractError(
            "incident environment context is incomplete"
        )

    for component in expected_keys:
        if not isinstance(context[component], dict):
            raise HveeContractError(
                f"incident {component} context must be canonical"
            )

    return context


def _require_prepared_replay(
    replay_preparation_payload: dict[str, object],
) -> tuple[
    dict[str, object],
    dict[str, object],
]:
    preparation = replay_preparation_payload.get("preparation")
    replay_plan = replay_preparation_payload.get("replay_plan")
    verification = replay_preparation_payload.get(
        "artifact_verification"
    )

    if (
        not isinstance(preparation, dict)
        or not isinstance(replay_plan, dict)
        or not isinstance(verification, dict)
    ):
        raise HveeContractError(
            "environment manifest requires canonical replay preparation"
        )

    if (
        preparation.get("status") != "prepared"
        or preparation.get("replay_plan_prepared") is not True
        or replay_plan.get("execution_started") is not False
        or not isinstance(replay_plan.get("steps"), list)
        or verification.get(
            "all_referenced_artifacts_verified"
        )
        is not True
        or verification.get("runner_custody_status") != "verified"
    ):
        raise HveeContractError(
            "environment manifest requires a prepared replay plan"
        )

    _require_sha256_hex(
        name="incident replay plan SHA-256",
        value=replay_plan.get("sha256"),
    )
    _require_sha256_hex(
        name="incident artifact manifest SHA-256",
        value=verification.get("manifest_sha256"),
    )

    return replay_plan, verification


def _find_unique_replay_step(
    *,
    replay_plan: dict[str, object],
    operation: str,
) -> dict[str, object]:
    steps = replay_plan["steps"]
    if not isinstance(steps, list):
        raise HveeContractError(
            "incident replay steps must be canonical"
        )

    matches = [
        step
        for step in steps
        if isinstance(step, dict)
        and step.get("operation") == operation
    ]

    if len(matches) != 1:
        raise HveeContractError(
            f"replay plan requires exactly one {operation} step"
        )

    return matches[0]


def _context_component_binding(
    *,
    context: dict[str, object],
    replay_plan: dict[str, object],
    component: str,
    operation: str,
) -> dict[str, object]:
    component_payload = context[component]
    if not isinstance(component_payload, dict):
        raise HveeContractError(
            f"incident {component} context must be canonical"
        )

    component_sha256 = calculate_incident_context_sha256(
        component_payload
    )

    step = _find_unique_replay_step(
        replay_plan=replay_plan,
        operation=operation,
    )

    commitments = step.get("input_commitment_sha256s")
    if commitments != [component_sha256]:
        raise HveeContractError(
            f"{component} restore step is not bound "
            "to the incident context commitment"
        )

    ordinal = step.get("ordinal")
    if (
        not isinstance(ordinal, int)
        or isinstance(ordinal, bool)
        or ordinal <= 0
    ):
        raise HveeContractError(
            f"{component} restore step ordinal must be canonical"
        )

    return {
        "component": component,
        "sha256": component_sha256,
        "restore_operation": operation,
        "restore_step_ordinal": ordinal,
        "materialization_source": "verified_incident_intake",
    }


def _execution_context_binding(
    *,
    context_sha256: str,
    replay_plan: dict[str, object],
) -> dict[str, object]:
    step = _find_unique_replay_step(
        replay_plan=replay_plan,
        operation="execute_isolated_replay",
    )

    commitments = step.get("input_commitment_sha256s")
    if (
        not isinstance(commitments, list)
        or context_sha256 not in commitments
    ):
        raise HveeContractError(
            "isolated replay is not bound to "
            "the incident context commitment"
        )

    ordinal = step.get("ordinal")
    if (
        not isinstance(ordinal, int)
        or isinstance(ordinal, bool)
        or ordinal <= 0
    ):
        raise HveeContractError(
            "isolated replay step ordinal must be canonical"
        )

    return {
        "operation": "execute_isolated_replay",
        "context_sha256": context_sha256,
        "replay_step_ordinal": ordinal,
    }


def _assemble_manifest(
    *,
    intake_payload: dict[str, object],
    intake_sha256: str,
    replay_preparation_payload: dict[str, object],
    replay_preparation_sha256: str,
) -> IncidentEnvironmentManifestBundle:
    context = _require_context(intake_payload)
    replay_plan, artifact_verification = _require_prepared_replay(
        replay_preparation_payload
    )

    context_sha256 = _require_sha256_hex(
        name="incident context SHA-256",
        value=context.get("sha256"),
    )

    component_bindings = [
        _context_component_binding(
            context=context,
            replay_plan=replay_plan,
            component=component,
            operation=operation,
        )
        for component, operation in _CONTEXT_RESTORE_OPERATIONS
    ]

    execution_binding = _execution_context_binding(
        context_sha256=context_sha256,
        replay_plan=replay_plan,
    )

    incident = intake_payload.get("incident")
    if not isinstance(incident, dict):
        raise HveeContractError(
            "incident environment identity must be canonical"
        )

    replay_plan_sha256 = _require_sha256_hex(
        name="incident replay plan SHA-256",
        value=replay_plan.get("sha256"),
    )
    artifact_manifest_sha256 = _require_sha256_hex(
        name="incident artifact manifest SHA-256",
        value=artifact_verification.get("manifest_sha256"),
    )

    payload: dict[str, object] = {
        "schema_version": (
            INCIDENT_ENVIRONMENT_MANIFEST_SCHEMA_VERSION
        ),
        "type": "incident_environment_manifest",
        "evaluation_type": intake_payload["evaluation_type"],
        "incident": {
            "key": incident["key"],
            "version": incident["version"],
            "intake_sha256": intake_sha256,
            "context_sha256": context_sha256,
            "artifact_manifest_sha256": artifact_manifest_sha256,
            "replay_preparation_sha256": (
                replay_preparation_sha256
            ),
            "replay_plan_sha256": replay_plan_sha256,
        },
        "environment": {
            "status": IncidentEnvironmentManifestStatus.READY.value,
            "component_count": len(component_bindings),
            "context_components": component_bindings,
            "execution_binding": execution_binding,
            "restoration_source": "verified_incident_intake",
            "materialization_scope": "customer_controlled_runner",
            "operator_authorization_required": True,
            "materialization_started": False,
        },
        "content_boundary": dict(_CONTENT_BOUNDARY),
        "evidence_boundary": dict(_EVIDENCE_BOUNDARY),
    }

    canonical_payload = _canonical_json_value(
        payload,
        name="incident environment manifest",
    )
    if not isinstance(canonical_payload, dict):
        raise HveeContractError(
            "incident environment manifest must be a JSON object"
        )

    return IncidentEnvironmentManifestBundle(
        payload=canonical_payload,
        sha256=calculate_incident_environment_manifest_sha256(
            canonical_payload
        ),
    )


def calculate_incident_environment_manifest_sha256(
    payload: dict[str, object],
) -> str:
    return _calculate_sha256(
        payload,
        name="incident environment manifest",
    )


def build_incident_environment_manifest_bundle(
    *,
    intake_payload: object,
    expected_intake_sha256: object,
    replay_preparation_payload: object,
    expected_replay_preparation_sha256: object,
) -> IncidentEnvironmentManifestBundle:
    intake_sha256 = _require_sha256_hex(
        name="expected incident intake SHA-256",
        value=expected_intake_sha256,
    )
    replay_preparation_sha256 = _require_sha256_hex(
        name="expected replay preparation SHA-256",
        value=expected_replay_preparation_sha256,
    )

    if (
        not isinstance(intake_payload, dict)
        or not verify_incident_intake_bundle(
            payload=intake_payload,
            expected_sha256=intake_sha256,
        )
    ):
        raise HveeContractError(
            "incident intake evidence failed verification"
        )

    if (
        not isinstance(replay_preparation_payload, dict)
        or not verify_incident_replay_preparation_bundle(
            payload=replay_preparation_payload,
            expected_sha256=replay_preparation_sha256,
            intake_payload=intake_payload,
            expected_intake_sha256=intake_sha256,
        )
    ):
        raise HveeContractError(
            "incident replay preparation failed verification"
        )

    return _assemble_manifest(
        intake_payload=intake_payload,
        intake_sha256=intake_sha256,
        replay_preparation_payload=replay_preparation_payload,
        replay_preparation_sha256=replay_preparation_sha256,
    )


def verify_incident_environment_manifest_bundle(
    *,
    payload: object,
    expected_sha256: object,
    intake_payload: object,
    expected_intake_sha256: object,
    replay_preparation_payload: object,
    expected_replay_preparation_sha256: object,
) -> bool:
    try:
        manifest_sha256 = _require_sha256_hex(
            name="expected environment manifest SHA-256",
            value=expected_sha256,
        )

        rebuilt = build_incident_environment_manifest_bundle(
            intake_payload=intake_payload,
            expected_intake_sha256=expected_intake_sha256,
            replay_preparation_payload=replay_preparation_payload,
            expected_replay_preparation_sha256=(
                expected_replay_preparation_sha256
            ),
        )

        return (
            isinstance(payload, dict)
            and payload == rebuilt.payload
            and manifest_sha256 == rebuilt.sha256
            and calculate_incident_environment_manifest_sha256(
                payload
            )
            == manifest_sha256
        )
    except (
        HveeContractError,
        KeyError,
        TypeError,
        ValueError,
    ):
        return False


__all__ = [
    "INCIDENT_ENVIRONMENT_MANIFEST_SCHEMA_VERSION",
    "IncidentEnvironmentManifestBundle",
    "IncidentEnvironmentManifestStatus",
    "build_incident_environment_manifest_bundle",
    "calculate_incident_environment_manifest_sha256",
    "verify_incident_environment_manifest_bundle",
]

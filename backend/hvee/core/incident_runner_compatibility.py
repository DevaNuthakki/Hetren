"""Deterministic Incident Mode runner-environment compatibility evidence.

This module is the fourth bounded Incident Mode stage.

It consumes the already verified incident-intake, replay-preparation, and
environment-manifest evidence together with a runner-local compatibility
observation.

The purpose of this stage is to answer a narrow question:

    Is this runner capable of reconstructing the incident environment with
    enough fidelity to proceed toward materialization?

Compatibility is intentionally more expressive than a boolean:

* exact
* compatible
* unobserved
* unsupported

A host environment may legitimately differ when the portable execution
commitments remain fixed. This follows Hetren's existing cross-host
reproducibility policy.

This stage does not materialize an environment, load a model, execute replay,
claim reproduction, prove model failure, or grant qualification authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum

from hvee.core.contracts import HveeContractError
from hvee.core.incident_environment_manifest import (
    verify_incident_environment_manifest_bundle,
)
from hvee.core.incident_intake import (
    calculate_incident_context_sha256,
    verify_incident_intake_bundle,
)
from hvee.core.incident_replay_preparation import (
    verify_incident_replay_preparation_bundle,
)


INCIDENT_RUNNER_COMPATIBILITY_SCHEMA_VERSION = 1

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_CAPABILITY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,99}$")
_REQUIREMENT_PATTERN = re.compile(
    r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$"
)

_PORTABLE_RUNTIME_REQUIREMENTS = (
    "runtime.deployment_identity",
    "runtime.provider_identity",
    "runtime.model_identity",
    "runtime.model_artifact_sha256",
    "runtime.source_code_sha256",
    "runtime.configuration_sha256",
    "runtime.runtime_environment_sha256",
)

_HOST_RUNTIME_REQUIREMENT = "runtime.host_environment_sha256"

_AUDIO_REQUIREMENT_PATHS = (
    ("codec", "name", "audio.codec_name"),
    ("codec", "profile", "audio.codec_profile"),
    (None, "container_name", "audio.container_name"),
    (None, "sample_rate_hz", "audio.sample_rate_hz"),
    (None, "channel_count", "audio.channel_count"),
    (None, "bit_rate_bps", "audio.bit_rate_bps"),
    (None, "duration_ms", "audio.duration_ms"),
    (None, "variable_bit_rate", "audio.variable_bit_rate"),
    (
        None,
        "sample_rate_shift_observed",
        "audio.sample_rate_shift_observed",
    ),
    (
        "capture_processing",
        "automatic_gain_control",
        "audio.automatic_gain_control",
    ),
    (
        "capture_processing",
        "noise_suppression",
        "audio.noise_suppression",
    ),
    (
        "capture_processing",
        "echo_cancellation",
        "audio.echo_cancellation",
    ),
    (None, "input_device_class", "audio.input_device_class"),
)

_TRANSPORT_REQUIREMENT_PATHS = (
    (None, "kind", "transport.kind"),
    (None, "packet_loss_percent", "transport.packet_loss_percent"),
    (None, "network_jitter_ms", "transport.network_jitter_ms"),
    (None, "jitter_buffer_ms", "transport.jitter_buffer_ms"),
    (None, "round_trip_time_ms", "transport.round_trip_time_ms"),
    (
        None,
        "burst_loss_max_packets",
        "transport.burst_loss_max_packets",
    ),
    (None, "concealed_audio_ms", "transport.concealed_audio_ms"),
    (None, "codec_switch_count", "transport.codec_switch_count"),
    (
        None,
        "sample_rate_shift_count",
        "transport.sample_rate_shift_count",
    ),
)

_CONTENT_BOUNDARY = {
    "raw_audio_embedded": False,
    "raw_transcript_embedded": False,
    "model_output_embedded": False,
    "transport_trace_embedded": False,
    "environment_values_embedded": False,
    "environment_value_commitments_embedded": True,
    "runner_credentials_embedded": False,
    "hostnames_embedded": False,
    "network_addresses_embedded": False,
    "environment_variables_embedded": False,
    "file_paths_embedded": False,
}

_EVIDENCE_BOUNDARY = {
    "incident_intake_verified": True,
    "replay_preparation_verified": True,
    "environment_manifest_verified": True,
    "runner_compatibility_evaluated": True,
    "runner_environment_observed": True,
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


class IncidentCompatibilityLevel(StrEnum):
    EXACT = "exact"
    COMPATIBLE = "compatible"
    UNOBSERVED = "unobserved"
    UNSUPPORTED = "unsupported"


class IncidentRunnerCompatibilityStatus(StrEnum):
    EXACT = "exact"
    COMPATIBLE = "compatible"
    BLOCKED_UNOBSERVED = "blocked_unobserved"
    BLOCKED_UNSUPPORTED = "blocked_unsupported"


def _require_sha256_hex(*, name: str, value: object) -> str:
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
    return _require_sha256_hex(name=name, value=value)


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
    return json.loads(_canonical_json(value, name=name))


def _calculate_sha256(value: object, *, name: str) -> str:
    canonical = _canonical_json(value, name=name)
    return hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()


def _value_commitment(value: object) -> str:
    return _calculate_sha256(
        value,
        name="incident compatibility value commitment",
    )


def _canonical_text_tuple(
    values: object,
    *,
    name: str,
    pattern: re.Pattern[str],
) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        raise HveeContractError(
            f"{name} must be a list or tuple"
        )

    normalized: list[str] = []
    for value in values:
        if (
            not isinstance(value, str)
            or pattern.fullmatch(value) is None
        ):
            raise HveeContractError(
                f"{name} contains a noncanonical value"
            )
        if value not in normalized:
            normalized.append(value)

    return tuple(sorted(normalized))


@dataclass(frozen=True, slots=True)
class IncidentRunnerEnvironmentObservation:
    """Non-sensitive runner-local compatibility observation."""

    capabilities: tuple[str, ...]

    deployment_key: str | None = None
    deployment_version: str | None = None
    provider_key: str | None = None
    provider_version: str | None = None
    model_key: str | None = None
    model_version: str | None = None

    model_artifact_sha256: str | None = None
    source_code_sha256: str | None = None
    configuration_sha256: str | None = None
    runtime_environment_sha256: str | None = None
    host_environment_sha256: str | None = None

    exact_context_components: tuple[str, ...] = ()
    supported_materializations: tuple[str, ...] = ()
    unsupported_materializations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        capabilities = _canonical_text_tuple(
            self.capabilities,
            name="runner capabilities",
            pattern=_CAPABILITY_PATTERN,
        )
        if capabilities != self.capabilities:
            raise HveeContractError(
                "runner capabilities must already be canonical"
            )

        for name, value in (
            ("runner deployment key", self.deployment_key),
            ("runner deployment version", self.deployment_version),
            ("runner provider key", self.provider_key),
            ("runner provider version", self.provider_version),
            ("runner model key", self.model_key),
            ("runner model version", self.model_version),
        ):
            if value is not None and (
                not isinstance(value, str)
                or not value.strip()
                or value.strip() != value
            ):
                raise HveeContractError(
                    f"{name} must be canonical text or null"
                )

        for name, value in (
            (
                "runner model artifact SHA-256",
                self.model_artifact_sha256,
            ),
            ("runner source code SHA-256", self.source_code_sha256),
            (
                "runner configuration SHA-256",
                self.configuration_sha256,
            ),
            (
                "runner runtime environment SHA-256",
                self.runtime_environment_sha256,
            ),
            (
                "runner host environment SHA-256",
                self.host_environment_sha256,
            ),
        ):
            _require_optional_sha256_hex(
                name=name,
                value=value,
            )

        components = _canonical_text_tuple(
            self.exact_context_components,
            name="exact context components",
            pattern=re.compile(r"^(runtime|audio|transport)$"),
        )
        if components != self.exact_context_components:
            raise HveeContractError(
                "exact context components must already be canonical"
            )

        supported = _canonical_text_tuple(
            self.supported_materializations,
            name="supported materializations",
            pattern=_REQUIREMENT_PATTERN,
        )
        unsupported = _canonical_text_tuple(
            self.unsupported_materializations,
            name="unsupported materializations",
            pattern=_REQUIREMENT_PATTERN,
        )

        if supported != self.supported_materializations:
            raise HveeContractError(
                "supported materializations must already be canonical"
            )
        if unsupported != self.unsupported_materializations:
            raise HveeContractError(
                "unsupported materializations must already be canonical"
            )

        overlap = set(supported).intersection(unsupported)
        if overlap:
            raise HveeContractError(
                "a materialization requirement cannot be both "
                "supported and unsupported"
            )


@dataclass(frozen=True, slots=True)
class IncidentRunnerCompatibilityBundle:
    payload: dict[str, object]
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.payload, dict):
            raise HveeContractError(
                "runner compatibility payload must be a JSON object"
            )
        _require_sha256_hex(
            name="runner compatibility SHA-256",
            value=self.sha256,
        )


def _require_context(
    intake_payload: dict[str, object],
) -> dict[str, object]:
    context = intake_payload.get("context")
    if not isinstance(context, dict):
        raise HveeContractError(
            "incident compatibility context must be canonical"
        )

    for component in ("runtime", "audio", "transport"):
        if not isinstance(context.get(component), dict):
            raise HveeContractError(
                f"incident {component} context must be canonical"
            )

    return context


def _match_identity(
    *,
    key: str,
    expected: tuple[object, ...],
    observed: tuple[object, ...],
) -> dict[str, object]:
    expected_present = all(value is not None for value in expected)
    observed_present = all(value is not None for value in observed)

    if not expected_present:
        return {
            "requirement": key,
            "level": IncidentCompatibilityLevel.COMPATIBLE.value,
            "expected_commitment_sha256": None,
            "observed_commitment_sha256": None,
        }

    expected_commitment = _value_commitment(list(expected))

    if not observed_present:
        return {
            "requirement": key,
            "level": IncidentCompatibilityLevel.UNOBSERVED.value,
            "expected_commitment_sha256": expected_commitment,
            "observed_commitment_sha256": None,
        }

    observed_commitment = _value_commitment(list(observed))

    return {
        "requirement": key,
        "level": (
            IncidentCompatibilityLevel.EXACT.value
            if expected == observed
            else IncidentCompatibilityLevel.UNSUPPORTED.value
        ),
        "expected_commitment_sha256": expected_commitment,
        "observed_commitment_sha256": observed_commitment,
    }


def _match_digest(
    *,
    key: str,
    expected: object,
    observed: object,
    host_portable: bool = False,
) -> dict[str, object]:
    expected_digest = (
        None
        if expected is None
        else _require_sha256_hex(
            name=f"{key} expected SHA-256",
            value=expected,
        )
    )
    observed_digest = _require_optional_sha256_hex(
        name=f"{key} observed SHA-256",
        value=observed,
    )

    if expected_digest is None:
        return {
            "requirement": key,
            "level": IncidentCompatibilityLevel.COMPATIBLE.value,
            "expected_commitment_sha256": None,
            "observed_commitment_sha256": None,
        }

    if observed_digest is None:
        return {
            "requirement": key,
            "level": IncidentCompatibilityLevel.UNOBSERVED.value,
            "expected_commitment_sha256": expected_digest,
            "observed_commitment_sha256": None,
        }

    if observed_digest == expected_digest:
        level = IncidentCompatibilityLevel.EXACT
    elif host_portable:
        level = IncidentCompatibilityLevel.COMPATIBLE
    else:
        level = IncidentCompatibilityLevel.UNSUPPORTED

    return {
        "requirement": key,
        "level": level.value,
        "expected_commitment_sha256": expected_digest,
        "observed_commitment_sha256": observed_digest,
    }


def _nested_value(
    payload: dict[str, object],
    parent: str | None,
    field: str,
) -> object:
    if parent is None:
        return payload.get(field)

    nested = payload.get(parent)
    if not isinstance(nested, dict):
        raise HveeContractError(
            f"incident {parent} context must be canonical"
        )
    return nested.get(field)


def _materialization_requirement(
    *,
    key: str,
    value: object,
    exact_component: bool,
    observation: IncidentRunnerEnvironmentObservation,
) -> dict[str, object]:
    if value is None:
        return {
            "requirement": key,
            "level": IncidentCompatibilityLevel.COMPATIBLE.value,
            "expected_commitment_sha256": None,
            "observed_commitment_sha256": None,
        }

    expected_commitment = _value_commitment(value)

    if exact_component:
        return {
            "requirement": key,
            "level": IncidentCompatibilityLevel.EXACT.value,
            "expected_commitment_sha256": expected_commitment,
            "observed_commitment_sha256": expected_commitment,
        }

    if key in observation.unsupported_materializations:
        level = IncidentCompatibilityLevel.UNSUPPORTED
    elif key in observation.supported_materializations:
        level = IncidentCompatibilityLevel.COMPATIBLE
    else:
        level = IncidentCompatibilityLevel.UNOBSERVED

    return {
        "requirement": key,
        "level": level.value,
        "expected_commitment_sha256": expected_commitment,
        "observed_commitment_sha256": None,
    }


def _runtime_requirements(
    *,
    runtime: dict[str, object],
    observation: IncidentRunnerEnvironmentObservation,
) -> list[dict[str, object]]:
    deployment = runtime.get("deployment")
    provider = runtime.get("provider")
    model = runtime.get("model")

    if (
        not isinstance(deployment, dict)
        or not isinstance(provider, dict)
        or not isinstance(model, dict)
    ):
        raise HveeContractError(
            "incident runtime identity must be canonical"
        )

    values = [
        _match_identity(
            key="runtime.deployment_identity",
            expected=(
                deployment.get("key"),
                deployment.get("version"),
            ),
            observed=(
                observation.deployment_key,
                observation.deployment_version,
            ),
        ),
        _match_identity(
            key="runtime.provider_identity",
            expected=(
                provider.get("key"),
                provider.get("version"),
            ),
            observed=(
                observation.provider_key,
                observation.provider_version,
            ),
        ),
        _match_identity(
            key="runtime.model_identity",
            expected=(
                model.get("key"),
                model.get("version"),
            ),
            observed=(
                observation.model_key,
                observation.model_version,
            ),
        ),
        _match_digest(
            key="runtime.model_artifact_sha256",
            expected=model.get("artifact_sha256"),
            observed=observation.model_artifact_sha256,
        ),
        _match_digest(
            key="runtime.source_code_sha256",
            expected=runtime.get("source_code_sha256"),
            observed=observation.source_code_sha256,
        ),
        _match_digest(
            key="runtime.configuration_sha256",
            expected=runtime.get("configuration_sha256"),
            observed=observation.configuration_sha256,
        ),
        _match_digest(
            key="runtime.runtime_environment_sha256",
            expected=runtime.get("runtime_environment_sha256"),
            observed=observation.runtime_environment_sha256,
        ),
        _match_digest(
            key=_HOST_RUNTIME_REQUIREMENT,
            expected=runtime.get("host_environment_sha256"),
            observed=observation.host_environment_sha256,
            host_portable=True,
        ),
    ]

    assert tuple(
        value["requirement"]
        for value in values[:7]
    ) == _PORTABLE_RUNTIME_REQUIREMENTS

    return values


def _context_materialization_requirements(
    *,
    component: str,
    payload: dict[str, object],
    paths: tuple[tuple[str | None, str, str], ...],
    observation: IncidentRunnerEnvironmentObservation,
) -> list[dict[str, object]]:
    exact_component = (
        component in observation.exact_context_components
    )

    return [
        _materialization_requirement(
            key=requirement,
            value=_nested_value(
                payload,
                parent,
                field,
            ),
            exact_component=exact_component,
            observation=observation,
        )
        for parent, field, requirement in paths
    ]


def _capability_summary(
    *,
    required_capabilities: tuple[str, ...],
    observation: IncidentRunnerEnvironmentObservation,
) -> dict[str, object]:
    required = set(required_capabilities)
    observed = set(observation.capabilities)
    missing = tuple(sorted(required - observed))

    return {
        "required": list(required_capabilities),
        "observed": list(observation.capabilities),
        "missing": list(missing),
        "routing_compatible": not missing,
    }


def _aggregate_status(
    requirements: list[dict[str, object]],
    *,
    routing_compatible: bool,
) -> IncidentRunnerCompatibilityStatus:
    levels = {
        str(value["level"])
        for value in requirements
    }

    if not routing_compatible:
        return IncidentRunnerCompatibilityStatus.BLOCKED_UNSUPPORTED

    if IncidentCompatibilityLevel.UNSUPPORTED.value in levels:
        return IncidentRunnerCompatibilityStatus.BLOCKED_UNSUPPORTED

    if IncidentCompatibilityLevel.UNOBSERVED.value in levels:
        return IncidentRunnerCompatibilityStatus.BLOCKED_UNOBSERVED

    if levels == {IncidentCompatibilityLevel.EXACT.value}:
        return IncidentRunnerCompatibilityStatus.EXACT

    return IncidentRunnerCompatibilityStatus.COMPATIBLE


def _counts(
    requirements: list[dict[str, object]],
) -> dict[str, int]:
    return {
        f"{level.value}_count": sum(
            value["level"] == level.value
            for value in requirements
        )
        for level in IncidentCompatibilityLevel
    }


def _assemble_bundle(
    *,
    intake_payload: dict[str, object],
    intake_sha256: str,
    replay_preparation_sha256: str,
    environment_manifest_sha256: str,
    required_capabilities: tuple[str, ...],
    observation: IncidentRunnerEnvironmentObservation,
) -> IncidentRunnerCompatibilityBundle:
    context = _require_context(intake_payload)

    runtime = context["runtime"]
    audio = context["audio"]
    transport = context["transport"]

    if (
        not isinstance(runtime, dict)
        or not isinstance(audio, dict)
        or not isinstance(transport, dict)
    ):
        raise HveeContractError(
            "incident compatibility context is invalid"
        )

    requirements = [
        *_runtime_requirements(
            runtime=runtime,
            observation=observation,
        ),
        *_context_materialization_requirements(
            component="audio",
            payload=audio,
            paths=_AUDIO_REQUIREMENT_PATHS,
            observation=observation,
        ),
        *_context_materialization_requirements(
            component="transport",
            payload=transport,
            paths=_TRANSPORT_REQUIREMENT_PATHS,
            observation=observation,
        ),
    ]

    requirements = sorted(
        requirements,
        key=lambda value: str(value["requirement"]),
    )

    capabilities = _capability_summary(
        required_capabilities=required_capabilities,
        observation=observation,
    )
    status = _aggregate_status(
        requirements,
        routing_compatible=bool(
            capabilities["routing_compatible"]
        ),
    )

    incident = intake_payload.get("incident")
    if not isinstance(incident, dict):
        raise HveeContractError(
            "incident identity must be canonical"
        )

    payload: dict[str, object] = {
        "schema_version": (
            INCIDENT_RUNNER_COMPATIBILITY_SCHEMA_VERSION
        ),
        "type": "incident_runner_compatibility",
        "evaluation_type": intake_payload["evaluation_type"],
        "incident": {
            "key": incident["key"],
            "version": incident["version"],
            "intake_sha256": intake_sha256,
            "context_sha256": _require_sha256_hex(
                name="incident context SHA-256",
                value=context["sha256"],
            ),
            "replay_preparation_sha256": (
                replay_preparation_sha256
            ),
            "environment_manifest_sha256": (
                environment_manifest_sha256
            ),
        },
        "runner": {
            "capabilities": capabilities,
            "observation_sha256": _calculate_sha256(
                {
                    "capabilities": list(observation.capabilities),
                    "deployment": [
                        observation.deployment_key,
                        observation.deployment_version,
                    ],
                    "provider": [
                        observation.provider_key,
                        observation.provider_version,
                    ],
                    "model": [
                        observation.model_key,
                        observation.model_version,
                    ],
                    "model_artifact_sha256": (
                        observation.model_artifact_sha256
                    ),
                    "source_code_sha256": (
                        observation.source_code_sha256
                    ),
                    "configuration_sha256": (
                        observation.configuration_sha256
                    ),
                    "runtime_environment_sha256": (
                        observation.runtime_environment_sha256
                    ),
                    "host_environment_sha256": (
                        observation.host_environment_sha256
                    ),
                    "exact_context_components": list(
                        observation.exact_context_components
                    ),
                    "supported_materializations": list(
                        observation.supported_materializations
                    ),
                    "unsupported_materializations": list(
                        observation.unsupported_materializations
                    ),
                },
                name="incident runner compatibility observation",
            ),
        },
        "compatibility": {
            "status": status.value,
            "ready_for_materialization": status in {
                IncidentRunnerCompatibilityStatus.EXACT,
                IncidentRunnerCompatibilityStatus.COMPATIBLE,
            },
            "requirement_count": len(requirements),
            **_counts(requirements),
            "requirements": requirements,
        },
        "policy": {
            "portable_runtime_identity_required": True,
            "host_environment_identity_may_differ": True,
            "missing_observation_blocks_materialization": True,
            "unsupported_requirement_blocks_materialization": True,
        },
        "content_boundary": dict(_CONTENT_BOUNDARY),
        "evidence_boundary": dict(_EVIDENCE_BOUNDARY),
    }

    canonical_payload = _canonical_json_value(
        payload,
        name="incident runner compatibility",
    )
    if not isinstance(canonical_payload, dict):
        raise HveeContractError(
            "incident runner compatibility must be a JSON object"
        )

    return IncidentRunnerCompatibilityBundle(
        payload=canonical_payload,
        sha256=calculate_incident_runner_compatibility_sha256(
            canonical_payload
        ),
    )


def calculate_incident_runner_compatibility_sha256(
    payload: dict[str, object],
) -> str:
    return _calculate_sha256(
        payload,
        name="incident runner compatibility",
    )


def build_incident_runner_compatibility_bundle(
    *,
    intake_payload: object,
    expected_intake_sha256: object,
    replay_preparation_payload: object,
    expected_replay_preparation_sha256: object,
    environment_manifest_payload: object,
    expected_environment_manifest_sha256: object,
    required_capabilities: list[str] | tuple[str, ...],
    observation: IncidentRunnerEnvironmentObservation,
) -> IncidentRunnerCompatibilityBundle:
    intake_sha256 = _require_sha256_hex(
        name="expected incident intake SHA-256",
        value=expected_intake_sha256,
    )
    replay_preparation_sha256 = _require_sha256_hex(
        name="expected replay preparation SHA-256",
        value=expected_replay_preparation_sha256,
    )
    environment_manifest_sha256 = _require_sha256_hex(
        name="expected environment manifest SHA-256",
        value=expected_environment_manifest_sha256,
    )

    if not isinstance(observation, IncidentRunnerEnvironmentObservation):
        raise HveeContractError(
            "runner compatibility observation must be canonical"
        )

    normalized_capabilities = _canonical_text_tuple(
        required_capabilities,
        name="required runner capabilities",
        pattern=_CAPABILITY_PATTERN,
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

    if (
        not isinstance(environment_manifest_payload, dict)
        or not verify_incident_environment_manifest_bundle(
            payload=environment_manifest_payload,
            expected_sha256=environment_manifest_sha256,
            intake_payload=intake_payload,
            expected_intake_sha256=intake_sha256,
            replay_preparation_payload=replay_preparation_payload,
            expected_replay_preparation_sha256=(
                replay_preparation_sha256
            ),
        )
    ):
        raise HveeContractError(
            "incident environment manifest failed verification"
        )

    return _assemble_bundle(
        intake_payload=intake_payload,
        intake_sha256=intake_sha256,
        replay_preparation_sha256=replay_preparation_sha256,
        environment_manifest_sha256=environment_manifest_sha256,
        required_capabilities=normalized_capabilities,
        observation=observation,
    )


def verify_incident_runner_compatibility_bundle(
    *,
    payload: object,
    expected_sha256: object,
    intake_payload: object,
    expected_intake_sha256: object,
    replay_preparation_payload: object,
    expected_replay_preparation_sha256: object,
    environment_manifest_payload: object,
    expected_environment_manifest_sha256: object,
    required_capabilities: list[str] | tuple[str, ...],
    observation: IncidentRunnerEnvironmentObservation,
) -> bool:
    try:
        normalized_sha256 = _require_sha256_hex(
            name="expected runner compatibility SHA-256",
            value=expected_sha256,
        )

        rebuilt = build_incident_runner_compatibility_bundle(
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
            required_capabilities=required_capabilities,
            observation=observation,
        )

        return (
            isinstance(payload, dict)
            and payload == rebuilt.payload
            and normalized_sha256 == rebuilt.sha256
            and calculate_incident_runner_compatibility_sha256(
                payload
            )
            == normalized_sha256
        )
    except (
        HveeContractError,
        KeyError,
        TypeError,
        ValueError,
    ):
        return False


__all__ = [
    "INCIDENT_RUNNER_COMPATIBILITY_SCHEMA_VERSION",
    "IncidentCompatibilityLevel",
    "IncidentRunnerCompatibilityBundle",
    "IncidentRunnerCompatibilityStatus",
    "IncidentRunnerEnvironmentObservation",
    "build_incident_runner_compatibility_bundle",
    "calculate_incident_runner_compatibility_sha256",
    "verify_incident_runner_compatibility_bundle",
]

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace

import pytest

from hvee.core.contracts import HveeContractError
from hvee.core.incident_intake import (
    IncidentAffectedStage,
    IncidentArtifactKind,
    IncidentArtifactReference,
    IncidentAudioContext,
    IncidentClaim,
    IncidentProcessingState,
    IncidentRuntimeContext,
    IncidentSeverity,
    IncidentTransportContext,
    IncidentTransportKind,
    build_incident_intake_bundle,
    calculate_incident_context_sha256,
    calculate_incident_intake_sha256,
)
from hvee.core.incident_replay_preparation import (
    INCIDENT_REPLAY_PREPARATION_SCHEMA_VERSION,
    IncidentArtifactMaterial,
    IncidentArtifactVerification,
    IncidentArtifactVerificationStatus,
    IncidentReplayOperation,
    IncidentReplayPreparationBundle,
    IncidentReplayPreparationStatus,
    IncidentReplayStep,
    IncidentReplayStepStatus,
    IncidentRunnerCustodyStatus,
    build_incident_replay_preparation_bundle,
    calculate_incident_artifact_manifest_sha256,
    calculate_incident_replay_plan_sha256,
    calculate_incident_replay_preparation_sha256,
    verify_incident_replay_preparation_bundle,
)


_SOURCE_AUDIO_BYTES = (
    b"\x1aE\xdf\xa3incident-source-audio-opus-payload"
)
_TRANSPORT_TRACE_BYTES = (
    b'{"codec_switch_count":1,"packet_loss_percent":2.5}'
)
_INCIDENT_REPORT_BYTES = (
    b'{"reason_code":"dosage_value_changed","schema":1}'
)
_REFERENCE_TRANSCRIPT_BYTES = (
    b'{"commitment":"critical-number-reference"}'
)


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha(character: str) -> str:
    return character * 64


def _reference(
    kind: IncidentArtifactKind,
    content: bytes,
    media_type: str,
    **overrides,
) -> IncidentArtifactReference:
    values = {
        "kind": kind,
        "sha256": _sha_bytes(content),
        "byte_length": len(content),
        "media_type": media_type,
    }
    values.update(overrides)
    return IncidentArtifactReference(**values)


def _source_reference(**overrides) -> IncidentArtifactReference:
    return _reference(
        IncidentArtifactKind.SOURCE_AUDIO,
        _SOURCE_AUDIO_BYTES,
        "audio/webm",
        **overrides,
    )


def _transport_reference(**overrides) -> IncidentArtifactReference:
    return _reference(
        IncidentArtifactKind.TRANSPORT_TRACE,
        _TRANSPORT_TRACE_BYTES,
        "application/json",
        **overrides,
    )


def _report_reference(**overrides) -> IncidentArtifactReference:
    return _reference(
        IncidentArtifactKind.INCIDENT_REPORT,
        _INCIDENT_REPORT_BYTES,
        "application/json",
        **overrides,
    )


def _reference_transcript(
    **overrides,
) -> IncidentArtifactReference:
    return _reference(
        IncidentArtifactKind.REFERENCE_TRANSCRIPT,
        _REFERENCE_TRANSCRIPT_BYTES,
        "application/json",
        **overrides,
    )


def _material(
    reference: IncidentArtifactReference,
    content: bytes,
    **overrides,
) -> IncidentArtifactMaterial:
    values = {
        "kind": reference.kind,
        "reference_sha256": reference.sha256,
        "content": content,
    }
    values.update(overrides)
    return IncidentArtifactMaterial(**values)


def _runtime(**overrides) -> IncidentRuntimeContext:
    values = {
        "deployment_key": "medical_dictation_prod",
        "deployment_version": "2026.08.24",
        "provider_key": "faster_whisper",
        "provider_version": "1.1.0",
        "model_key": "large-v3-turbo",
        "model_version": "openai-whisper-large-v3-turbo",
        "model_artifact_sha256": _sha("4"),
        "source_code_sha256": _sha("5"),
        "configuration_sha256": _sha("6"),
        "runtime_environment_sha256": _sha("7"),
        "host_environment_sha256": _sha("8"),
    }
    values.update(overrides)
    return IncidentRuntimeContext(**values)


def _audio(**overrides) -> IncidentAudioContext:
    values = {
        "codec_name": "opus",
        "codec_profile": "fullband",
        "container_name": "webm",
        "sample_rate_hz": 48000,
        "channel_count": 1,
        "bit_rate_bps": 32000,
        "duration_ms": 4120,
        "variable_bit_rate": True,
        "sample_rate_shift_observed": False,
        "automatic_gain_control": IncidentProcessingState.ENABLED,
        "noise_suppression": IncidentProcessingState.ENABLED,
        "echo_cancellation": IncidentProcessingState.DISABLED,
        "input_device_class": "mobile_microphone",
    }
    values.update(overrides)
    return IncidentAudioContext(**values)


def _transport(**overrides) -> IncidentTransportContext:
    values = {
        "kind": IncidentTransportKind.WEBRTC,
        "packet_loss_percent": 2.5,
        "network_jitter_ms": 18.25,
        "jitter_buffer_ms": 60,
        "round_trip_time_ms": 84.5,
        "burst_loss_max_packets": 4,
        "concealed_audio_ms": 120,
        "codec_switch_count": 1,
        "sample_rate_shift_count": 0,
    }
    values.update(overrides)
    return IncidentTransportContext(**values)


def _claim(**overrides) -> IncidentClaim:
    values = {
        "key": "critical_number_mismatch",
        "version": "1.0.0",
        "reason_code": "dosage_value_changed",
        "severity": IncidentSeverity.CRITICAL,
        "affected_stage": IncidentAffectedStage.INFERENCE,
        "reporter_evidence_sha256": _sha("1"),
        "expected_behavior_commitment_sha256": _sha("2"),
        "observed_behavior_commitment_sha256": _sha("3"),
    }
    values.update(overrides)
    return IncidentClaim(**values)


def _intake(
    *,
    artifacts: tuple[IncidentArtifactReference, ...] | None = None,
    runtime: IncidentRuntimeContext | None = None,
    audio: IncidentAudioContext | None = None,
    transport: IncidentTransportContext | None = None,
    claim: IncidentClaim | None = None,
):
    if artifacts is None:
        artifacts = (
            _source_reference(),
            _transport_reference(),
            _report_reference(),
        )
    return build_incident_intake_bundle(
        evaluation_type="asr",
        incident_key="production_asr_incident",
        incident_version="1.0.0",
        source_event_commitment_sha256=_sha("c"),
        claim=claim or _claim(),
        runtime=runtime or _runtime(),
        audio=audio or _audio(),
        transport=transport or _transport(),
        artifacts=artifacts,
    )


def _materials(
    *,
    references: tuple[IncidentArtifactReference, ...] | None = None,
) -> tuple[IncidentArtifactMaterial, ...]:
    if references is None:
        references = (
            _source_reference(),
            _transport_reference(),
            _report_reference(),
        )
    contents = {
        IncidentArtifactKind.SOURCE_AUDIO: _SOURCE_AUDIO_BYTES,
        IncidentArtifactKind.TRANSPORT_TRACE: _TRANSPORT_TRACE_BYTES,
        IncidentArtifactKind.INCIDENT_REPORT: _INCIDENT_REPORT_BYTES,
        (
            IncidentArtifactKind.REFERENCE_TRANSCRIPT
        ): _REFERENCE_TRANSCRIPT_BYTES,
    }
    return tuple(
        _material(reference, contents[reference.kind])
        for reference in references
    )


def _preparation(
    *,
    intake=None,
    materials: tuple[IncidentArtifactMaterial, ...] | None = None,
) -> IncidentReplayPreparationBundle:
    intake = intake or _intake()
    if materials is None:
        materials = _materials()
    return build_incident_replay_preparation_bundle(
        intake_payload=intake.payload,
        expected_intake_sha256=intake.sha256,
        artifact_materials=materials,
    )




import copy

from hvee.core.contracts import HveeContractError
from hvee.core.incident_environment_manifest import (
    build_incident_environment_manifest_bundle,
    calculate_incident_environment_manifest_sha256,
    verify_incident_environment_manifest_bundle,
)


def _environment_manifest(
    *,
    intake=None,
    preparation=None,
):
    if intake is None:
        intake = _intake()
    if preparation is None:
        preparation = _preparation(intake=intake)

    return build_incident_environment_manifest_bundle(
        intake_payload=intake.payload,
        expected_intake_sha256=intake.sha256,
        replay_preparation_payload=preparation.payload,
        expected_replay_preparation_sha256=preparation.sha256,
    )




from hvee.core.incident_runner_compatibility import (
    IncidentCompatibilityLevel,
    IncidentRunnerCompatibilityStatus,
    IncidentRunnerEnvironmentObservation,
    build_incident_runner_compatibility_bundle,
    calculate_incident_runner_compatibility_sha256,
    verify_incident_runner_compatibility_bundle,
)


def _all_materialization_requirements():
    return tuple(
        sorted(
            {
                "audio.automatic_gain_control",
                "audio.bit_rate_bps",
                "audio.channel_count",
                "audio.codec_name",
                "audio.codec_profile",
                "audio.container_name",
                "audio.duration_ms",
                "audio.echo_cancellation",
                "audio.input_device_class",
                "audio.noise_suppression",
                "audio.sample_rate_hz",
                "audio.sample_rate_shift_observed",
                "audio.variable_bit_rate",
                "transport.burst_loss_max_packets",
                "transport.codec_switch_count",
                "transport.concealed_audio_ms",
                "transport.jitter_buffer_ms",
                "transport.kind",
                "transport.network_jitter_ms",
                "transport.packet_loss_percent",
                "transport.round_trip_time_ms",
                "transport.sample_rate_shift_count",
            }
        )
    )


def _runner_observation(**overrides):
    values = {
        "capabilities": ("asr", "incident_replay"),
        "deployment_key": _runtime().deployment_key,
        "deployment_version": _runtime().deployment_version,
        "provider_key": _runtime().provider_key,
        "provider_version": _runtime().provider_version,
        "model_key": _runtime().model_key,
        "model_version": _runtime().model_version,
        "model_artifact_sha256": _sha("4"),
        "source_code_sha256": _sha("5"),
        "configuration_sha256": _sha("6"),
        "runtime_environment_sha256": _sha("7"),
        "host_environment_sha256": _sha("8"),
        "exact_context_components": (),
        "supported_materializations": (
            _all_materialization_requirements()
        ),
        "unsupported_materializations": (),
    }
    values.update(overrides)
    return IncidentRunnerEnvironmentObservation(**values)


def _compatibility(
    *,
    intake=None,
    preparation=None,
    manifest=None,
    observation=None,
    required_capabilities=None,
):
    if intake is None:
        intake = _intake()
    if preparation is None:
        preparation = _preparation(intake=intake)
    if manifest is None:
        manifest = _environment_manifest(
            intake=intake,
            preparation=preparation,
        )
    if observation is None:
        observation = _runner_observation()
    if required_capabilities is None:
        required_capabilities = ["asr", "incident_replay"]

    return build_incident_runner_compatibility_bundle(
        intake_payload=intake.payload,
        expected_intake_sha256=intake.sha256,
        replay_preparation_payload=preparation.payload,
        expected_replay_preparation_sha256=preparation.sha256,
        environment_manifest_payload=manifest.payload,
        expected_environment_manifest_sha256=manifest.sha256,
        required_capabilities=required_capabilities,
        observation=observation,
    )


def test_runner_compatibility_binds_all_upstream_evidence():
    intake = _intake()
    preparation = _preparation(intake=intake)
    manifest = _environment_manifest(
        intake=intake,
        preparation=preparation,
    )
    bundle = _compatibility(
        intake=intake,
        preparation=preparation,
        manifest=manifest,
    )

    incident = bundle.payload["incident"]

    assert bundle.payload["schema_version"] == 1
    assert bundle.payload["type"] == "incident_runner_compatibility"
    assert incident["intake_sha256"] == intake.sha256
    assert incident["context_sha256"] == intake.context_sha256
    assert (
        incident["replay_preparation_sha256"]
        == preparation.sha256
    )
    assert (
        incident["environment_manifest_sha256"]
        == manifest.sha256
    )


def test_portable_runtime_identity_is_exact():
    bundle = _compatibility()

    requirements = {
        value["requirement"]: value
        for value in bundle.payload["compatibility"]["requirements"]
    }

    for key in (
        "runtime.deployment_identity",
        "runtime.provider_identity",
        "runtime.model_identity",
        "runtime.model_artifact_sha256",
        "runtime.source_code_sha256",
        "runtime.configuration_sha256",
        "runtime.runtime_environment_sha256",
        "runtime.host_environment_sha256",
    ):
        assert requirements[key]["level"] == (
            IncidentCompatibilityLevel.EXACT.value
        )


def test_different_host_environment_is_compatible():
    bundle = _compatibility(
        observation=_runner_observation(
            host_environment_sha256=_sha("9")
        )
    )

    requirements = {
        value["requirement"]: value
        for value in bundle.payload["compatibility"]["requirements"]
    }

    assert requirements[
        "runtime.host_environment_sha256"
    ]["level"] == IncidentCompatibilityLevel.COMPATIBLE.value

    assert bundle.payload["compatibility"]["status"] == (
        IncidentRunnerCompatibilityStatus.COMPATIBLE.value
    )
    assert (
        bundle.payload["compatibility"][
            "ready_for_materialization"
        ]
        is True
    )


def test_runtime_environment_mismatch_blocks_materialization():
    bundle = _compatibility(
        observation=_runner_observation(
            runtime_environment_sha256=_sha("9")
        )
    )

    requirements = {
        value["requirement"]: value
        for value in bundle.payload["compatibility"]["requirements"]
    }

    assert requirements[
        "runtime.runtime_environment_sha256"
    ]["level"] == IncidentCompatibilityLevel.UNSUPPORTED.value
    assert bundle.payload["compatibility"]["status"] == (
        IncidentRunnerCompatibilityStatus.BLOCKED_UNSUPPORTED.value
    )
    assert (
        bundle.payload["compatibility"][
            "ready_for_materialization"
        ]
        is False
    )


def test_missing_runtime_observation_blocks_as_unobserved():
    bundle = _compatibility(
        observation=_runner_observation(
            source_code_sha256=None
        )
    )

    requirements = {
        value["requirement"]: value
        for value in bundle.payload["compatibility"]["requirements"]
    }

    assert requirements[
        "runtime.source_code_sha256"
    ]["level"] == IncidentCompatibilityLevel.UNOBSERVED.value
    assert bundle.payload["compatibility"]["status"] == (
        IncidentRunnerCompatibilityStatus.BLOCKED_UNOBSERVED.value
    )


def test_supported_audio_and_transport_are_compatible():
    bundle = _compatibility()

    requirements = bundle.payload["compatibility"]["requirements"]

    materialization_levels = {
        value["level"]
        for value in requirements
        if value["requirement"].startswith(("audio.", "transport."))
        and value["expected_commitment_sha256"] is not None
    }

    assert materialization_levels == {
        IncidentCompatibilityLevel.COMPATIBLE.value
    }
    assert bundle.payload["compatibility"]["status"] == (
        IncidentRunnerCompatibilityStatus.COMPATIBLE.value
    )


def test_compatible_materialization_does_not_claim_observed_value():
    bundle = _compatibility()

    compatible_requirements = [
        value
        for value in bundle.payload["compatibility"]["requirements"]
        if value["requirement"].startswith(("audio.", "transport."))
        and value["expected_commitment_sha256"] is not None
        and value["level"] == IncidentCompatibilityLevel.COMPATIBLE.value
    ]

    assert compatible_requirements
    assert all(
        value["observed_commitment_sha256"] is None
        for value in compatible_requirements
    )


def test_exact_context_component_upgrades_requirements_to_exact():
    bundle = _compatibility(
        observation=_runner_observation(
            exact_context_components=("audio", "transport"),
            supported_materializations=(),
        )
    )

    requirements = [
        value
        for value in bundle.payload["compatibility"]["requirements"]
        if value["requirement"].startswith(("audio.", "transport."))
        and value["expected_commitment_sha256"] is not None
    ]

    assert requirements
    assert all(
        value["level"] == IncidentCompatibilityLevel.EXACT.value
        for value in requirements
    )


def test_explicit_unsupported_materialization_blocks():
    supported = set(_all_materialization_requirements())
    supported.remove("transport.codec_switch_count")

    bundle = _compatibility(
        observation=_runner_observation(
            supported_materializations=tuple(sorted(supported)),
            unsupported_materializations=(
                "transport.codec_switch_count",
            ),
        )
    )

    requirements = {
        value["requirement"]: value
        for value in bundle.payload["compatibility"]["requirements"]
    }

    assert requirements[
        "transport.codec_switch_count"
    ]["level"] == IncidentCompatibilityLevel.UNSUPPORTED.value
    assert bundle.payload["compatibility"]["status"] == (
        IncidentRunnerCompatibilityStatus.BLOCKED_UNSUPPORTED.value
    )


def test_unobserved_materialization_support_blocks():
    supported = set(_all_materialization_requirements())
    supported.remove("audio.noise_suppression")

    bundle = _compatibility(
        observation=_runner_observation(
            supported_materializations=tuple(sorted(supported)),
        )
    )

    requirements = {
        value["requirement"]: value
        for value in bundle.payload["compatibility"]["requirements"]
    }

    assert requirements[
        "audio.noise_suppression"
    ]["level"] == IncidentCompatibilityLevel.UNOBSERVED.value
    assert bundle.payload["compatibility"]["status"] == (
        IncidentRunnerCompatibilityStatus.BLOCKED_UNOBSERVED.value
    )


def test_missing_coarse_runner_capability_blocks():
    bundle = _compatibility(
        observation=_runner_observation(
            capabilities=("asr",)
        )
    )

    capabilities = bundle.payload["runner"]["capabilities"]

    assert capabilities["routing_compatible"] is False
    assert capabilities["missing"] == ["incident_replay"]
    assert bundle.payload["compatibility"]["status"] == (
        IncidentRunnerCompatibilityStatus.BLOCKED_UNSUPPORTED.value
    )


def test_compatibility_evidence_does_not_embed_environment_values():
    bundle = _compatibility()

    serialized = json.dumps(
        bundle.payload,
        sort_keys=True,
    )

    forbidden = (
        "2.5",
        "18.25",
        '"opus"',
        '"fullband"',
        '"prod-us"',
        '"faster-whisper"',
        '"large-v3-turbo"',
    )

    for value in forbidden:
        assert value not in serialized


def test_compatibility_hash_is_reproducible():
    bundle = _compatibility()

    assert calculate_incident_runner_compatibility_sha256(
        bundle.payload
    ) == bundle.sha256


def test_compatibility_verifier_accepts_exact_bundle():
    intake = _intake()
    preparation = _preparation(intake=intake)
    manifest = _environment_manifest(
        intake=intake,
        preparation=preparation,
    )
    observation = _runner_observation()
    bundle = _compatibility(
        intake=intake,
        preparation=preparation,
        manifest=manifest,
        observation=observation,
    )

    assert verify_incident_runner_compatibility_bundle(
        payload=bundle.payload,
        expected_sha256=bundle.sha256,
        intake_payload=intake.payload,
        expected_intake_sha256=intake.sha256,
        replay_preparation_payload=preparation.payload,
        expected_replay_preparation_sha256=preparation.sha256,
        environment_manifest_payload=manifest.payload,
        expected_environment_manifest_sha256=manifest.sha256,
        required_capabilities=["asr", "incident_replay"],
        observation=observation,
    )


def test_compatibility_verifier_rejects_tampering():
    intake = _intake()
    preparation = _preparation(intake=intake)
    manifest = _environment_manifest(
        intake=intake,
        preparation=preparation,
    )
    observation = _runner_observation()
    bundle = _compatibility(
        intake=intake,
        preparation=preparation,
        manifest=manifest,
        observation=observation,
    )

    tampered = copy.deepcopy(bundle.payload)
    tampered["compatibility"]["status"] = "exact"
    tampered_sha256 = (
        calculate_incident_runner_compatibility_sha256(
            tampered
        )
    )

    assert not verify_incident_runner_compatibility_bundle(
        payload=tampered,
        expected_sha256=tampered_sha256,
        intake_payload=intake.payload,
        expected_intake_sha256=intake.sha256,
        replay_preparation_payload=preparation.payload,
        expected_replay_preparation_sha256=preparation.sha256,
        environment_manifest_payload=manifest.payload,
        expected_environment_manifest_sha256=manifest.sha256,
        required_capabilities=["asr", "incident_replay"],
        observation=observation,
    )


def test_compatibility_does_not_claim_materialization_or_execution():
    boundary = _compatibility().payload["evidence_boundary"]

    assert boundary["runner_compatibility_evaluated"] is True
    assert boundary["environment_materialized"] is False
    assert boundary["operator_authorization_granted"] is False
    assert boundary["models_loaded"] is False
    assert boundary["replay_executed"] is False
    assert boundary["transcriptions_executed"] is False
    assert boundary["reproduction_claimed"] is False
    assert boundary["model_failure_verified"] is False
    assert boundary["contract_promoted"] is False
    assert boundary["qualification_authority"] is False


def test_observation_rejects_conflicting_materialization_claims():
    with pytest.raises(
        HveeContractError,
        match="both supported and unsupported",
    ):
        IncidentRunnerEnvironmentObservation(
            capabilities=("asr",),
            supported_materializations=("audio.codec_name",),
            unsupported_materializations=("audio.codec_name",),
        )


def test_upstream_context_change_changes_compatibility_identity():
    baseline_intake = _intake()
    baseline_preparation = _preparation(
        intake=baseline_intake
    )
    baseline_manifest = _environment_manifest(
        intake=baseline_intake,
        preparation=baseline_preparation,
    )
    baseline = _compatibility(
        intake=baseline_intake,
        preparation=baseline_preparation,
        manifest=baseline_manifest,
    )

    changed_intake = _intake(
        transport=replace(
            _transport(),
            packet_loss_percent=3.0,
        )
    )
    changed_preparation = _preparation(
        intake=changed_intake
    )
    changed_manifest = _environment_manifest(
        intake=changed_intake,
        preparation=changed_preparation,
    )
    changed = _compatibility(
        intake=changed_intake,
        preparation=changed_preparation,
        manifest=changed_manifest,
    )

    assert baseline_intake.context_sha256 != (
        changed_intake.context_sha256
    )
    assert baseline.sha256 != changed.sha256

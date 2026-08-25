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


def test_environment_manifest_binds_exact_upstream_evidence():
    intake = _intake()
    preparation = _preparation(intake=intake)
    bundle = _environment_manifest(
        intake=intake,
        preparation=preparation,
    )

    incident = bundle.payload["incident"]

    assert bundle.payload["schema_version"] == 1
    assert bundle.payload["type"] == "incident_environment_manifest"
    assert incident["intake_sha256"] == intake.sha256
    assert incident["context_sha256"] == intake.context_sha256
    assert (
        incident["artifact_manifest_sha256"]
        == preparation.artifact_manifest_sha256
    )
    assert (
        incident["replay_preparation_sha256"]
        == preparation.sha256
    )
    assert (
        incident["replay_plan_sha256"]
        == preparation.replay_plan_sha256
    )


def test_environment_components_bind_restore_steps():
    preparation = _preparation()
    bundle = _environment_manifest(
        preparation=preparation,
    )

    components = {
        value["component"]: value
        for value in bundle.payload["environment"][
            "context_components"
        ]
    }
    steps = {
        value["operation"]: value
        for value in preparation.payload["replay_plan"]["steps"]
    }

    expected = {
        "runtime": "restore_runtime_context",
        "audio": "restore_audio_context",
        "transport": "restore_transport_context",
    }

    assert set(components) == set(expected)

    for component, operation in expected.items():
        assert components[component]["restore_operation"] == operation
        assert components[component]["sha256"] == (
            steps[operation]["input_commitment_sha256s"][0]
        )
        assert components[component][
            "restore_step_ordinal"
        ] == steps[operation]["ordinal"]


def test_environment_manifest_binds_execution_context():
    intake = _intake()
    preparation = _preparation(intake=intake)
    bundle = _environment_manifest(
        intake=intake,
        preparation=preparation,
    )

    binding = bundle.payload["environment"]["execution_binding"]
    execution_step = next(
        value
        for value in preparation.payload["replay_plan"]["steps"]
        if value["operation"] == "execute_isolated_replay"
    )

    assert binding == {
        "operation": "execute_isolated_replay",
        "context_sha256": intake.context_sha256,
        "replay_step_ordinal": execution_step["ordinal"],
    }
    assert intake.context_sha256 in (
        execution_step["input_commitment_sha256s"]
    )


def test_environment_manifest_hash_is_independently_reproducible():
    bundle = _environment_manifest()

    assert calculate_incident_environment_manifest_sha256(
        bundle.payload
    ) == bundle.sha256


def test_environment_manifest_verifier_accepts_exact_bundle():
    intake = _intake()
    preparation = _preparation(intake=intake)
    bundle = _environment_manifest(
        intake=intake,
        preparation=preparation,
    )

    assert verify_incident_environment_manifest_bundle(
        payload=bundle.payload,
        expected_sha256=bundle.sha256,
        intake_payload=intake.payload,
        expected_intake_sha256=intake.sha256,
        replay_preparation_payload=preparation.payload,
        expected_replay_preparation_sha256=preparation.sha256,
    )


def test_environment_manifest_verifier_rejects_tampering():
    intake = _intake()
    preparation = _preparation(intake=intake)
    bundle = _environment_manifest(
        intake=intake,
        preparation=preparation,
    )

    tampered = copy.deepcopy(bundle.payload)
    tampered["environment"]["context_components"][0][
        "sha256"
    ] = _sha("f")

    tampered_sha256 = (
        calculate_incident_environment_manifest_sha256(
            tampered
        )
    )

    assert not verify_incident_environment_manifest_bundle(
        payload=tampered,
        expected_sha256=tampered_sha256,
        intake_payload=intake.payload,
        expected_intake_sha256=intake.sha256,
        replay_preparation_payload=preparation.payload,
        expected_replay_preparation_sha256=preparation.sha256,
    )


def test_environment_manifest_rejects_blocked_replay():
    intake = _intake()
    blocked = build_incident_replay_preparation_bundle(
        intake_payload=intake.payload,
        expected_intake_sha256=intake.sha256,
        artifact_materials=(),
    )

    with pytest.raises(
        HveeContractError,
        match="prepared replay plan",
    ):
        build_incident_environment_manifest_bundle(
            intake_payload=intake.payload,
            expected_intake_sha256=intake.sha256,
            replay_preparation_payload=blocked.payload,
            expected_replay_preparation_sha256=blocked.sha256,
        )


def test_environment_manifest_excludes_environment_values():
    bundle = _environment_manifest()

    serialized = json.dumps(
        bundle.payload,
        sort_keys=True,
    )

    forbidden = (
        "packet_loss_percent",
        "network_jitter_ms",
        "jitter_buffer_ms",
        "round_trip_time_ms",
        "burst_loss_max_packets",
        "concealed_audio_ms",
        "codec_switch_count",
        "sample_rate_shift_count",
        "automatic_gain_control",
        "noise_suppression",
        "echo_cancellation",
        "sample_rate_hz",
        "bit_rate_bps",
        "duration_ms",
        "model_artifact_sha256",
        "source_code_sha256",
        "configuration_sha256",
        "runtime_environment_sha256",
        "host_environment_sha256",
    )

    for value in forbidden:
        assert value not in serialized


def test_environment_manifest_content_boundary_is_explicit():
    boundary = _environment_manifest().payload[
        "content_boundary"
    ]

    assert boundary == {
        "runtime_context_values_embedded": False,
        "audio_context_values_embedded": False,
        "transport_context_values_embedded": False,
        "context_component_digests_embedded": True,
        "artifact_bytes_embedded": False,
        "transport_trace_embedded": False,
        "local_artifact_locator_embedded": False,
        "runner_local_context_materialization_required": True,
    }


def test_environment_manifest_does_not_claim_execution():
    bundle = _environment_manifest()
    environment = bundle.payload["environment"]
    boundary = bundle.payload["evidence_boundary"]

    assert environment["status"] == "ready"
    assert environment["operator_authorization_required"] is True
    assert environment["materialization_started"] is False

    assert boundary["environment_materialized"] is False
    assert boundary["operator_authorization_granted"] is False
    assert boundary["models_loaded"] is False
    assert boundary["replay_executed"] is False
    assert boundary["transcriptions_executed"] is False
    assert boundary["reproduction_claimed"] is False
    assert boundary["model_failure_verified"] is False
    assert boundary["qualification_authority"] is False


def test_context_change_changes_environment_manifest_identity():
    baseline_intake = _intake()
    baseline_preparation = _preparation(
        intake=baseline_intake
    )
    baseline = _environment_manifest(
        intake=baseline_intake,
        preparation=baseline_preparation,
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
    changed = _environment_manifest(
        intake=changed_intake,
        preparation=changed_preparation,
    )

    assert baseline_intake.context_sha256 != (
        changed_intake.context_sha256
    )
    assert baseline.sha256 != changed.sha256


def test_wrong_environment_manifest_digest_is_rejected():
    intake = _intake()
    preparation = _preparation(intake=intake)
    bundle = _environment_manifest(
        intake=intake,
        preparation=preparation,
    )

    assert not verify_incident_environment_manifest_bundle(
        payload=bundle.payload,
        expected_sha256=_sha("f"),
        intake_payload=intake.payload,
        expected_intake_sha256=intake.sha256,
        replay_preparation_payload=preparation.payload,
        expected_replay_preparation_sha256=preparation.sha256,
    )

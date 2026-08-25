from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace

import pytest

from hvee.core.contracts import HveeContractError
from hvee.core.incident_intake import (
    INCIDENT_INTAKE_SCHEMA_VERSION,
    IncidentAffectedStage,
    IncidentArtifactKind,
    IncidentArtifactReference,
    IncidentAudioContext,
    IncidentClaim,
    IncidentIntakeBundle,
    IncidentIntakeStatus,
    IncidentProcessingState,
    IncidentReproducibilityStatus,
    IncidentRuntimeContext,
    IncidentSeverity,
    IncidentTransportContext,
    IncidentTransportKind,
    build_incident_intake_bundle,
    calculate_incident_context_sha256,
    calculate_incident_intake_sha256,
    verify_incident_intake_bundle,
)


def _sha(character: str) -> str:
    return character * 64


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


def _source_audio() -> IncidentArtifactReference:
    return IncidentArtifactReference(
        kind=IncidentArtifactKind.SOURCE_AUDIO,
        sha256=_sha("9"),
        byte_length=84120,
        media_type="audio/webm",
    )


def _transport_trace() -> IncidentArtifactReference:
    return IncidentArtifactReference(
        kind=IncidentArtifactKind.TRANSPORT_TRACE,
        sha256=_sha("a"),
        byte_length=9201,
        media_type="application/json",
    )


def _incident_report() -> IncidentArtifactReference:
    return IncidentArtifactReference(
        kind=IncidentArtifactKind.INCIDENT_REPORT,
        sha256=_sha("b"),
        byte_length=1844,
        media_type="application/json",
    )


def _artifacts() -> tuple[IncidentArtifactReference, ...]:
    return (
        _transport_trace(),
        _source_audio(),
        _incident_report(),
    )


def _bundle(**overrides) -> IncidentIntakeBundle:
    values = {
        "evaluation_type": "asr",
        "incident_key": "production_asr_incident",
        "incident_version": "1.0.0",
        "source_event_commitment_sha256": _sha("c"),
        "claim": _claim(),
        "runtime": _runtime(),
        "audio": _audio(),
        "transport": _transport(),
        "artifacts": _artifacts(),
    }
    values.update(overrides)
    return build_incident_intake_bundle(**values)


@pytest.mark.parametrize(
    "value,field_name",
    (
        (_source_audio(), "byte_length"),
        (_claim(), "reason_code"),
        (_runtime(), "model_key"),
        (_audio(), "sample_rate_hz"),
        (_transport(), "packet_loss_percent"),
        (_bundle(), "sha256"),
    ),
)
def test_incident_contracts_are_frozen(value, field_name):
    with pytest.raises(FrozenInstanceError):
        setattr(value, field_name, None)


def test_builds_ready_webrtc_incident_intake():
    bundle = _bundle()
    payload = bundle.payload

    assert payload["schema_version"] == INCIDENT_INTAKE_SCHEMA_VERSION
    assert payload["type"] == "incident_intake"
    assert payload["evaluation_type"] == "asr"
    assert payload["incident"] == {
        "key": "production_asr_incident",
        "version": "1.0.0",
        "source_event_commitment_sha256": _sha("c"),
    }
    assert payload["intake"] == {
        "status": IncidentIntakeStatus.ACCEPTED_READY_FOR_REPLAY.value,
        "ready_for_replay": True,
        "missing_context_fields": [],
    }
    assert payload["reproducibility"] == {
        "status": IncidentReproducibilityStatus.NOT_ATTEMPTED.value,
        "replay_execution_count": 0,
        "same_host_verified": False,
        "cross_host_verified": False,
    }


def test_ready_intake_records_rich_webrtc_context():
    context = _bundle().payload["context"]

    assert context["audio"]["sample_rate_hz"] == 48000
    assert context["audio"]["variable_bit_rate"] is True
    assert context["audio"]["capture_processing"] == {
        "automatic_gain_control": "enabled",
        "noise_suppression": "enabled",
        "echo_cancellation": "disabled",
    }
    assert context["transport"] == {
        "kind": "webrtc",
        "packet_loss_percent": 2.5,
        "network_jitter_ms": 18.25,
        "jitter_buffer_ms": 60,
        "round_trip_time_ms": 84.5,
        "burst_loss_max_packets": 4,
        "concealed_audio_ms": 120,
        "codec_switch_count": 1,
        "sample_rate_shift_count": 0,
    }


def test_context_digest_is_independently_reproducible():
    bundle = _bundle()
    context = deepcopy(bundle.payload["context"])
    stored = context.pop("sha256")

    assert stored == bundle.context_sha256
    assert calculate_incident_context_sha256(context) == stored


def test_intake_digest_is_independently_reproducible():
    bundle = _bundle()

    assert calculate_incident_intake_sha256(
        bundle.payload
    ) == bundle.sha256


def test_accepts_incomplete_production_context_without_crashing():
    bundle = _bundle(
        runtime=IncidentRuntimeContext(),
        audio=IncidentAudioContext(),
        transport=IncidentTransportContext(
            kind=IncidentTransportKind.UNKNOWN
        ),
        artifacts=(),
    )

    assert bundle.payload["intake"] == {
        "status": "accepted_incomplete_context",
        "ready_for_replay": False,
        "missing_context_fields": [
            "artifact.source_audio",
            "audio.channel_count",
            "audio.codec_name",
            "audio.container_name",
            "audio.duration_ms",
            "audio.sample_rate_hz",
            "runtime.configuration_sha256",
            "runtime.deployment_identity",
            "runtime.host_environment_sha256",
            "runtime.model_artifact_sha256",
            "runtime.model_identity",
            "runtime.provider_identity",
            "runtime.runtime_environment_sha256",
            "runtime.source_code_sha256",
            "transport.kind",
        ],
    }


def test_webrtc_readiness_requires_ephemeral_transport_context():
    bundle = _bundle(
        audio=_audio(
            variable_bit_rate=None,
            sample_rate_shift_observed=None,
            automatic_gain_control=IncidentProcessingState.UNKNOWN,
            noise_suppression=IncidentProcessingState.UNKNOWN,
            echo_cancellation=IncidentProcessingState.UNKNOWN,
        ),
        transport=IncidentTransportContext(
            kind=IncidentTransportKind.WEBRTC
        ),
        artifacts=(_source_audio(),),
    )

    assert bundle.payload["intake"]["missing_context_fields"] == [
        "artifact.transport_trace",
        "audio.automatic_gain_control",
        "audio.echo_cancellation",
        "audio.noise_suppression",
        "audio.sample_rate_shift_observed",
        "audio.variable_bit_rate",
        "transport.burst_loss_max_packets",
        "transport.codec_switch_count",
        "transport.jitter_buffer_ms",
        "transport.network_jitter_ms",
        "transport.packet_loss_percent",
    ]


def test_local_file_is_ready_without_network_telemetry():
    bundle = _bundle(
        audio=_audio(
            variable_bit_rate=None,
            sample_rate_shift_observed=None,
            automatic_gain_control=IncidentProcessingState.UNKNOWN,
            noise_suppression=IncidentProcessingState.UNKNOWN,
            echo_cancellation=IncidentProcessingState.UNKNOWN,
        ),
        transport=IncidentTransportContext(
            kind=IncidentTransportKind.LOCAL_FILE
        ),
        artifacts=(_source_audio(),),
    )

    assert bundle.payload["intake"]["ready_for_replay"] is True
    assert bundle.payload["intake"]["missing_context_fields"] == []


def test_rtp_requires_transport_telemetry_but_not_browser_processing():
    bundle = _bundle(
        audio=_audio(
            automatic_gain_control=IncidentProcessingState.UNKNOWN,
            noise_suppression=IncidentProcessingState.UNKNOWN,
            echo_cancellation=IncidentProcessingState.UNKNOWN,
        ),
        transport=replace(
            _transport(),
            kind=IncidentTransportKind.RTP,
        ),
    )

    assert bundle.payload["intake"]["ready_for_replay"] is True


def test_artifact_input_order_does_not_change_evidence():
    forward = _bundle(artifacts=_artifacts())
    reverse = _bundle(artifacts=tuple(reversed(_artifacts())))

    assert forward.payload == reverse.payload
    assert forward.context_sha256 == reverse.context_sha256
    assert forward.sha256 == reverse.sha256


def test_artifacts_have_deterministic_canonical_order():
    kinds = [
        artifact["kind"]
        for artifact in _bundle().payload["context"]["artifacts"]
    ]

    assert kinds == sorted(kinds)


def test_bundle_detaches_mutable_artifact_input():
    artifacts = list(_artifacts())
    bundle = _bundle(artifacts=artifacts)
    original_payload = deepcopy(bundle.payload)

    artifacts.clear()

    assert bundle.payload == original_payload


def test_duplicate_artifact_identity_is_rejected():
    artifact = _source_audio()

    with pytest.raises(
        HveeContractError,
        match="artifact identities must be unique",
    ):
        _bundle(artifacts=(artifact, artifact))


def test_one_artifact_digest_cannot_have_multiple_roles():
    source = _source_audio()
    report = IncidentArtifactReference(
        kind=IncidentArtifactKind.INCIDENT_REPORT,
        sha256=source.sha256,
        byte_length=source.byte_length,
        media_type="application/json",
    )

    with pytest.raises(
        HveeContractError,
        match="digest cannot have multiple roles",
    ):
        _bundle(artifacts=(source, report))


@pytest.mark.parametrize(
    "kwargs",
    (
        {"kind": "source_audio"},
        {"sha256": "A" * 64},
        {"byte_length": 0},
        {"byte_length": True},
        {"media_type": "audio"},
        {"media_type": "Audio/WAV"},
        {"media_type": " audio/wav"},
    ),
)
def test_artifact_reference_rejects_noncanonical_values(kwargs):
    values = {
        "kind": IncidentArtifactKind.SOURCE_AUDIO,
        "sha256": _sha("d"),
        "byte_length": 1,
        "media_type": "audio/wav",
    }
    values.update(kwargs)

    with pytest.raises(HveeContractError):
        IncidentArtifactReference(**values)


@pytest.mark.parametrize(
    "kwargs",
    (
        {"key": "CriticalNumber"},
        {"version": " 1.0.0"},
        {"reason_code": "dosage value changed"},
        {"severity": "critical"},
        {"affected_stage": "inference"},
        {"reporter_evidence_sha256": "bad"},
    ),
)
def test_claim_rejects_noncanonical_values(kwargs):
    with pytest.raises(HveeContractError):
        _claim(**kwargs)


def test_claim_behavior_commitments_must_be_paired():
    with pytest.raises(
        HveeContractError,
        match="must be provided together",
    ):
        _claim(observed_behavior_commitment_sha256=None)


def test_claim_behavior_commitments_must_be_distinct():
    with pytest.raises(
        HveeContractError,
        match="must be distinct",
    ):
        _claim(observed_behavior_commitment_sha256=_sha("2"))


def test_claim_can_omit_both_behavior_commitments():
    claim = _claim(
        expected_behavior_commitment_sha256=None,
        observed_behavior_commitment_sha256=None,
    )

    assert claim.expected_behavior_commitment_sha256 is None
    assert claim.observed_behavior_commitment_sha256 is None


@pytest.mark.parametrize(
    "kwargs",
    (
        {"deployment_version": None},
        {"provider_key": None},
        {"model_version": None},
    ),
)
def test_runtime_identity_keys_and_versions_are_paired(kwargs):
    with pytest.raises(
        HveeContractError,
        match="must be provided together",
    ):
        _runtime(**kwargs)


def test_model_artifact_requires_model_identity():
    with pytest.raises(
        HveeContractError,
        match="requires model key and version",
    ):
        IncidentRuntimeContext(
            model_artifact_sha256=_sha("4")
        )


@pytest.mark.parametrize(
    "field_name",
    (
        "model_artifact_sha256",
        "source_code_sha256",
        "configuration_sha256",
        "runtime_environment_sha256",
        "host_environment_sha256",
    ),
)
def test_runtime_rejects_invalid_optional_digests(field_name):
    with pytest.raises(HveeContractError):
        _runtime(**{field_name: "bad"})


@pytest.mark.parametrize(
    "kwargs",
    (
        {"codec_name": "Opus"},
        {"codec_profile": " fullband"},
        {"container_name": "web m"},
        {"sample_rate_hz": 0},
        {"sample_rate_hz": True},
        {"channel_count": 33},
        {"bit_rate_bps": -1},
        {"duration_ms": 0},
        {"variable_bit_rate": 1},
        {"sample_rate_shift_observed": "false"},
        {"automatic_gain_control": "enabled"},
        {"input_device_class": "Mobile Microphone"},
    ),
)
def test_audio_context_rejects_invalid_values(kwargs):
    with pytest.raises(HveeContractError):
        _audio(**kwargs)


@pytest.mark.parametrize(
    "kwargs",
    (
        {"kind": "webrtc"},
        {"packet_loss_percent": -0.1},
        {"packet_loss_percent": 100.1},
        {"packet_loss_percent": True},
        {"network_jitter_ms": float("nan")},
        {"jitter_buffer_ms": -1},
        {"round_trip_time_ms": float("inf")},
        {"burst_loss_max_packets": -1},
        {"concealed_audio_ms": True},
        {"codec_switch_count": -1},
        {"sample_rate_shift_count": -1},
    ),
)
def test_transport_context_rejects_invalid_values(kwargs):
    with pytest.raises(HveeContractError):
        _transport(**kwargs)


@pytest.mark.parametrize(
    "field_name,value",
    (
        ("evaluation_type", "ASR"),
        ("incident_key", "production incident"),
        ("incident_version", " 1.0.0"),
        ("source_event_commitment_sha256", "bad"),
        ("claim", object()),
        ("runtime", object()),
        ("audio", object()),
        ("transport", object()),
        ("artifacts", object()),
    ),
)
def test_builder_rejects_noncanonical_inputs(field_name, value):
    with pytest.raises(HveeContractError):
        _bundle(**{field_name: value})


def test_verifier_accepts_exact_bundle():
    bundle = _bundle()

    assert verify_incident_intake_bundle(
        payload=bundle.payload,
        expected_sha256=bundle.sha256,
    )


def test_verifier_rejects_wrong_digest():
    bundle = _bundle()

    assert not verify_incident_intake_bundle(
        payload=bundle.payload,
        expected_sha256=_sha("f"),
    )


@pytest.mark.parametrize(
    "mutation",
    (
        lambda payload: payload["incident"].update(
            {"version": "2.0.0"}
        ),
        lambda payload: payload["claim"].update(
            {"reason_code": "different_reason"}
        ),
        lambda payload: payload["context"]["audio"].update(
            {"sample_rate_hz": 16000}
        ),
        lambda payload: payload["intake"].update(
            {"ready_for_replay": False}
        ),
        lambda payload: payload["reproducibility"].update(
            {"replay_execution_count": 1}
        ),
        lambda payload: payload["content_boundary"].update(
            {"raw_audio_embedded": True}
        ),
        lambda payload: payload["evidence_boundary"].update(
            {"reproduction_claimed": True}
        ),
    ),
)
def test_verifier_rejects_tampering(mutation):
    bundle = _bundle()
    tampered = deepcopy(bundle.payload)
    mutation(tampered)

    assert not verify_incident_intake_bundle(
        payload=tampered,
        expected_sha256=bundle.sha256,
    )


def test_verifier_rejects_recomputed_context_with_original_intake_digest():
    bundle = _bundle()
    tampered = deepcopy(bundle.payload)
    tampered["context"]["transport"]["packet_loss_percent"] = 9.0
    context = deepcopy(tampered["context"])
    context.pop("sha256")
    tampered["context"]["sha256"] = (
        calculate_incident_context_sha256(context)
    )
    assert not verify_incident_intake_bundle(
        payload=tampered,
        expected_sha256=bundle.sha256,
    )


def test_verifier_rejects_noncanonical_artifact_order():
    bundle = _bundle()
    tampered = deepcopy(bundle.payload)
    tampered["context"]["artifacts"].reverse()
    context = deepcopy(tampered["context"])
    context.pop("sha256")
    tampered["context"]["sha256"] = (
        calculate_incident_context_sha256(context)
    )
    tampered_sha256 = calculate_incident_intake_sha256(tampered)

    assert not verify_incident_intake_bundle(
        payload=tampered,
        expected_sha256=tampered_sha256,
    )


@pytest.mark.parametrize(
    "target",
    (
        "top",
        "incident",
        "claim",
        "context",
        "runtime",
        "audio",
        "transport",
        "artifact",
        "intake",
    ),
)
def test_verifier_rejects_extra_fields(target):
    bundle = _bundle()
    tampered = deepcopy(bundle.payload)

    targets = {
        "top": tampered,
        "incident": tampered["incident"],
        "claim": tampered["claim"],
        "context": tampered["context"],
        "runtime": tampered["context"]["runtime"],
        "audio": tampered["context"]["audio"],
        "transport": tampered["context"]["transport"],
        "artifact": tampered["context"]["artifacts"][0],
        "intake": tampered["intake"],
    }
    targets[target]["unexpected"] = True

    assert not verify_incident_intake_bundle(
        payload=tampered,
        expected_sha256=bundle.sha256,
    )


def test_verifier_rejects_unknown_nested_enum():
    bundle = _bundle()
    tampered = deepcopy(bundle.payload)
    tampered["context"]["transport"]["kind"] = "bluetooth"

    assert not verify_incident_intake_bundle(
        payload=tampered,
        expected_sha256=bundle.sha256,
    )


def test_content_boundary_is_explicit():
    assert _bundle().payload["content_boundary"] == {
        "raw_audio_embedded": False,
        "raw_transcript_embedded": False,
        "model_output_embedded": False,
        "transport_trace_embedded": False,
        "local_artifact_locator_embedded": False,
        "artifact_bytes_embedded": False,
        "artifacts_referenced_by_digest_only": True,
        "artifact_bytes_verified": False,
        "artifact_custody_verified": False,
    }


def test_evidence_boundary_is_explicit():
    assert _bundle().payload["evidence_boundary"] == {
        "reported_incident_recorded": True,
        "reporter_claim_verified": False,
        "context_completeness_assessed": True,
        "replay_executed": False,
        "reproduction_claimed": False,
        "model_failure_verified": False,
        "causal_explanation_claimed": False,
        "counterexample_confirmed": False,
        "contract_promoted": False,
        "blocking_release_gate_enabled": False,
        "qualification_authority": False,
    }


def _all_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        keys = set(value)
        for nested in value.values():
            keys.update(_all_keys(nested))
        return keys
    if isinstance(value, list):
        keys: set[str] = set()
        for nested in value:
            keys.update(_all_keys(nested))
        return keys
    return set()


def test_evidence_excludes_local_and_raw_identity_fields():
    payload = _bundle().payload
    forbidden_keys = {
        "database_id",
        "evaluation_run_id",
        "tenant_id",
        "customer_id",
        "local_path",
        "artifact_url",
        "timestamp",
        "occurred_at",
        "audio_bytes",
        "transcript_text",
        "model_output_text",
        "transport_trace_payload",
    }

    assert _all_keys(payload).isdisjoint(forbidden_keys)

    serialized = json.dumps(payload, sort_keys=True)
    assert "patient dosage is fifty milligrams" not in serialized
    assert "/Users/customer/private/incident.wav" not in serialized


def test_intake_never_claims_replay_or_reproduction():
    payload = _bundle().payload

    assert payload["reproducibility"]["status"] == "not_attempted"
    assert payload["reproducibility"]["replay_execution_count"] == 0
    assert payload["evidence_boundary"]["replay_executed"] is False
    assert payload["evidence_boundary"]["reproduction_claimed"] is False
    assert payload["claim"]["verified"] is False


def test_intake_has_no_release_or_qualification_authority():
    boundary = _bundle().payload["evidence_boundary"]

    assert boundary["blocking_release_gate_enabled"] is False
    assert boundary["qualification_authority"] is False
    assert boundary["contract_promoted"] is False


def test_bundle_rejects_invalid_payload_and_digests():
    with pytest.raises(HveeContractError):
        IncidentIntakeBundle(
            payload=[],
            context_sha256=_sha("1"),
            sha256=_sha("2"),
        )

    with pytest.raises(HveeContractError):
        IncidentIntakeBundle(
            payload={},
            context_sha256="bad",
            sha256=_sha("2"),
        )

    with pytest.raises(HveeContractError):
        IncidentIntakeBundle(
            payload={},
            context_sha256=_sha("1"),
            sha256="bad",
        )


def test_hash_helpers_reject_non_deterministic_json():
    with pytest.raises(HveeContractError):
        calculate_incident_context_sha256(
            {"packet_loss": float("nan")}
        )

    with pytest.raises(HveeContractError):
        calculate_incident_intake_sha256(
            {"unsupported": object()}
        )

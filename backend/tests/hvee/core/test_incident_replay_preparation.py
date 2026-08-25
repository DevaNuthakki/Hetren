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


@pytest.mark.parametrize(
    "value,field_name",
    (
        (
            _material(_source_reference(), _SOURCE_AUDIO_BYTES),
            "content",
        ),
        (
            IncidentArtifactVerification(
                kind=IncidentArtifactKind.SOURCE_AUDIO,
                reference_sha256=_source_reference().sha256,
                expected_byte_length=len(_SOURCE_AUDIO_BYTES),
                media_type="audio/webm",
                observed_sha256=_source_reference().sha256,
                observed_byte_length=len(_SOURCE_AUDIO_BYTES),
                status=IncidentArtifactVerificationStatus.VERIFIED,
            ),
            "status",
        ),
        (
            IncidentReplayStep(
                ordinal=1,
                operation=(
                    IncidentReplayOperation.VERIFY_INTAKE_COMMITMENT
                ),
                input_commitment_sha256s=(_sha("1"),),
            ),
            "ordinal",
        ),
        (_preparation(), "sha256"),
    ),
)
def test_replay_preparation_contracts_are_frozen(value, field_name):
    with pytest.raises(FrozenInstanceError):
        setattr(value, field_name, None)


def test_prepares_replay_after_all_artifacts_verify():
    bundle = _preparation()
    payload = bundle.payload

    assert (
        payload["schema_version"]
        == INCIDENT_REPLAY_PREPARATION_SCHEMA_VERSION
    )
    assert payload["type"] == "incident_replay_preparation"
    assert payload["evaluation_type"] == "asr"
    assert payload["preparation"] == {
        "status": IncidentReplayPreparationStatus.PREPARED.value,
        "replay_plan_prepared": True,
        "blockers": [],
    }


def test_preparation_binds_exact_incident_intake_and_context():
    intake = _intake()
    payload = _preparation(intake=intake).payload

    assert payload["incident"] == {
        "key": "production_asr_incident",
        "version": "1.0.0",
        "intake_sha256": intake.sha256,
        "context_sha256": intake.context_sha256,
    }


def test_verified_artifact_summary_is_explicit():
    verification = _preparation().payload["artifact_verification"]

    assert verification["status"] == "verified"
    assert verification["expected_count"] == 3
    assert verification["supplied_count"] == 3
    assert verification["verified_count"] == 3
    assert verification["missing_count"] == 0
    assert verification["mismatch_count"] == 0
    assert verification["unexpected_count"] == 0
    assert verification["all_referenced_artifacts_verified"] is True
    assert verification["runner_custody_status"] == (
        IncidentRunnerCustodyStatus.VERIFIED.value
    )


def test_receipts_record_digest_and_length_without_bytes():
    receipts = _preparation().payload["artifact_verification"][
        "receipts"
    ]
    source = next(
        value for value in receipts if value["kind"] == "source_audio"
    )

    assert source == {
        "kind": "source_audio",
        "reference_sha256": _sha_bytes(_SOURCE_AUDIO_BYTES),
        "expected_byte_length": len(_SOURCE_AUDIO_BYTES),
        "media_type": "audio/webm",
        "observed_sha256": _sha_bytes(_SOURCE_AUDIO_BYTES),
        "observed_byte_length": len(_SOURCE_AUDIO_BYTES),
        "status": "verified",
    }


def test_replay_plan_has_deterministic_operation_order():
    steps = _preparation().payload["replay_plan"]["steps"]

    assert [step["ordinal"] for step in steps] == list(
        range(1, 11)
    )
    assert [step["operation"] for step in steps] == [
        "verify_intake_commitment",
        "verify_artifact_manifest",
        "restore_runtime_context",
        "restore_audio_context",
        "restore_transport_context",
        "stage_source_audio",
        "stage_transport_trace",
        "execute_isolated_replay",
        "capture_replay_output",
        "compare_behavior_commitments",
    ]
    assert {step["status"] for step in steps} == {"planned"}


def test_plan_hash_is_independently_reproducible():
    bundle = _preparation()
    plan = bundle.payload["replay_plan"]

    assert calculate_incident_replay_plan_sha256(plan) == (
        bundle.replay_plan_sha256
    )


def test_manifest_hash_is_independently_reproducible():
    bundle = _preparation()
    verification = bundle.payload["artifact_verification"]

    assert calculate_incident_artifact_manifest_sha256(
        verification["receipts"]
    ) == bundle.artifact_manifest_sha256


def test_preparation_hash_is_independently_reproducible():
    bundle = _preparation()

    assert calculate_incident_replay_preparation_sha256(
        bundle.payload
    ) == bundle.sha256


def test_material_input_order_does_not_change_evidence():
    materials = _materials()
    forward = _preparation(materials=materials)
    reverse = _preparation(materials=tuple(reversed(materials)))

    assert forward.payload == reverse.payload
    assert forward.sha256 == reverse.sha256


def test_material_list_mutation_does_not_change_bundle():
    materials = list(_materials())
    intake = _intake()
    bundle = build_incident_replay_preparation_bundle(
        intake_payload=intake.payload,
        expected_intake_sha256=intake.sha256,
        artifact_materials=materials,
    )
    original = deepcopy(bundle.payload)

    materials.clear()

    assert bundle.payload == original


def test_same_length_corruption_is_rejected_as_digest_mismatch():
    references = (
        _source_reference(),
        _transport_reference(),
        _report_reference(),
    )
    corrupted = bytes([_SOURCE_AUDIO_BYTES[0] ^ 1]) + (
        _SOURCE_AUDIO_BYTES[1:]
    )
    materials = (
        _material(references[0], corrupted),
        _material(references[1], _TRANSPORT_TRACE_BYTES),
        _material(references[2], _INCIDENT_REPORT_BYTES),
    )

    bundle = _preparation(materials=materials)
    verification = bundle.payload["artifact_verification"]
    source = next(
        value
        for value in verification["receipts"]
        if value["kind"] == "source_audio"
    )

    assert source["status"] == "digest_mismatch"
    assert verification["mismatch_count"] == 1
    assert verification["runner_custody_status"] == "rejected"
    assert bundle.payload["preparation"]["status"] == (
        "blocked_artifact_verification"
    )
    assert bundle.payload["replay_plan"]["steps"] == []
    assert bundle.replay_plan_sha256 is None


def test_changed_length_and_digest_are_both_reported():
    references = (
        _source_reference(),
        _transport_reference(),
        _report_reference(),
    )
    materials = (
        _material(references[0], _SOURCE_AUDIO_BYTES + b"tamper"),
        _material(references[1], _TRANSPORT_TRACE_BYTES),
        _material(references[2], _INCIDENT_REPORT_BYTES),
    )

    receipt = next(
        value
        for value in _preparation(materials=materials).payload[
            "artifact_verification"
        ]["receipts"]
        if value["kind"] == "source_audio"
    )

    assert receipt["status"] == "digest_and_length_mismatch"


def test_length_only_mismatch_is_reported():
    source = _source_reference(
        byte_length=len(_SOURCE_AUDIO_BYTES) + 1
    )
    references = (source, _transport_reference(), _report_reference())
    intake = _intake(artifacts=references)
    materials = _materials(references=references)

    receipt = next(
        value
        for value in _preparation(
            intake=intake,
            materials=materials,
        ).payload["artifact_verification"]["receipts"]
        if value["kind"] == "source_audio"
    )

    assert receipt["status"] == "length_mismatch"


def test_missing_artifact_blocks_preparation():
    materials = tuple(
        value
        for value in _materials()
        if value.kind != IncidentArtifactKind.TRANSPORT_TRACE
    )
    bundle = _preparation(materials=materials)
    verification = bundle.payload["artifact_verification"]

    assert verification["missing_count"] == 1
    assert verification["runner_custody_status"] == "partial"
    assert any(
        value["status"] == "missing"
        for value in verification["receipts"]
    )
    assert bundle.payload["preparation"]["status"] == (
        "blocked_artifact_verification"
    )


def test_no_supplied_artifacts_does_not_establish_custody():
    bundle = _preparation(materials=())
    verification = bundle.payload["artifact_verification"]

    assert verification["runner_custody_status"] == "not_established"
    assert verification["missing_count"] == 3


def test_unexpected_artifact_blocks_preparation():
    unexpected_content = b"not-declared-at-intake"
    unexpected = IncidentArtifactMaterial(
        kind=IncidentArtifactKind.MODEL_OUTPUT,
        reference_sha256=_sha_bytes(unexpected_content),
        content=unexpected_content,
    )
    bundle = _preparation(materials=(*_materials(), unexpected))
    verification = bundle.payload["artifact_verification"]

    assert verification["unexpected_count"] == 1
    assert verification["runner_custody_status"] == "rejected"
    assert any(
        value["status"] == "unexpected"
        for value in verification["receipts"]
    )
    assert bundle.payload["preparation"]["status"] == (
        "blocked_artifact_verification"
    )


def test_wrong_reference_selector_is_missing_and_unexpected():
    source = _source_reference()
    wrong = replace(
        _material(source, _SOURCE_AUDIO_BYTES),
        reference_sha256=_sha("f"),
    )
    remaining = tuple(
        value
        for value in _materials()
        if value.kind != IncidentArtifactKind.SOURCE_AUDIO
    )
    verification = _preparation(
        materials=(wrong, *remaining)
    ).payload["artifact_verification"]

    assert verification["missing_count"] == 1
    assert verification["unexpected_count"] == 1


def test_incomplete_intake_blocks_even_when_available_artifact_verifies():
    source = _source_reference()
    intake = _intake(
        artifacts=(source,),
        runtime=IncidentRuntimeContext(),
        audio=IncidentAudioContext(),
        transport=IncidentTransportContext(
            kind=IncidentTransportKind.UNKNOWN
        ),
    )
    bundle = _preparation(
        intake=intake,
        materials=(_material(source, _SOURCE_AUDIO_BYTES),),
    )

    assert bundle.payload["artifact_verification"][
        "all_referenced_artifacts_verified"
    ] is True
    assert bundle.payload["preparation"]["status"] == (
        "blocked_incomplete_intake"
    )
    assert bundle.payload["preparation"]["blockers"]
    assert bundle.payload["replay_plan"]["steps"] == []


def test_multiple_source_audio_artifacts_are_ambiguous():
    second_bytes = b"second-source-audio"
    first = _source_reference()
    second = _reference(
        IncidentArtifactKind.SOURCE_AUDIO,
        second_bytes,
        "audio/webm",
    )
    references = (
        first,
        second,
        _transport_reference(),
        _report_reference(),
    )
    intake = _intake(artifacts=references)
    materials = (
        _material(first, _SOURCE_AUDIO_BYTES),
        _material(second, second_bytes),
        _material(_transport_reference(), _TRANSPORT_TRACE_BYTES),
        _material(_report_reference(), _INCIDENT_REPORT_BYTES),
    )
    bundle = _preparation(intake=intake, materials=materials)

    assert bundle.payload["artifact_verification"]["status"] == (
        "verified"
    )
    assert bundle.payload["preparation"]["status"] == (
        "blocked_ambiguous_artifact_roles"
    )
    assert bundle.payload["preparation"]["blockers"] == [
        "artifact_role.source_audio.count_2"
    ]


def test_local_file_plan_does_not_require_transport_trace_step():
    source = _source_reference()
    intake = _intake(
        artifacts=(source,),
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
    )
    bundle = _preparation(
        intake=intake,
        materials=(_material(source, _SOURCE_AUDIO_BYTES),),
    )
    operations = [
        value["operation"]
        for value in bundle.payload["replay_plan"]["steps"]
    ]

    assert bundle.payload["preparation"]["status"] == "prepared"
    assert "stage_transport_trace" not in operations
    assert len(operations) == 9


def test_comparison_step_uses_reported_behavior_commitments():
    step = _preparation().payload["replay_plan"]["steps"][-1]

    assert step["operation"] == "compare_behavior_commitments"
    assert step["input_commitment_sha256s"] == [
        _sha("1"),
        _sha("2"),
        _sha("3"),
    ]


def test_comparison_step_handles_absent_optional_commitments():
    intake = _intake(
        claim=_claim(
            expected_behavior_commitment_sha256=None,
            observed_behavior_commitment_sha256=None,
        )
    )
    step = _preparation(intake=intake).payload["replay_plan"][
        "steps"
    ][-1]

    assert step["input_commitment_sha256s"] == [_sha("1")]


def test_repeated_comparison_commitment_is_deduplicated():
    intake = _intake(
        claim=_claim(reporter_evidence_sha256=_sha("2"))
    )
    step = _preparation(intake=intake).payload["replay_plan"][
        "steps"
    ][-1]

    assert step["input_commitment_sha256s"] == [
        _sha("2"),
        _sha("3"),
    ]


@pytest.mark.parametrize(
    "kwargs",
    (
        {"kind": "source_audio"},
        {"reference_sha256": "bad"},
        {"content": bytearray(b"mutable")},
        {"content": "not-bytes"},
    ),
)
def test_artifact_material_rejects_noncanonical_values(kwargs):
    values = {
        "kind": IncidentArtifactKind.SOURCE_AUDIO,
        "reference_sha256": _source_reference().sha256,
        "content": _SOURCE_AUDIO_BYTES,
    }
    values.update(kwargs)

    with pytest.raises(HveeContractError):
        IncidentArtifactMaterial(**values)


def test_artifact_material_allows_empty_bytes_for_rejection_evidence():
    material = IncidentArtifactMaterial(
        kind=IncidentArtifactKind.SOURCE_AUDIO,
        reference_sha256=_source_reference().sha256,
        content=b"",
    )

    assert material.content == b""


def test_duplicate_material_identity_is_rejected():
    material = _material(_source_reference(), _SOURCE_AUDIO_BYTES)
    intake = _intake()

    with pytest.raises(
        HveeContractError,
        match="material identities must be unique",
    ):
        build_incident_replay_preparation_bundle(
            intake_payload=intake.payload,
            expected_intake_sha256=intake.sha256,
            artifact_materials=(material, material),
        )


@pytest.mark.parametrize("materials", (object(), [object()]))
def test_builder_rejects_noncanonical_material_collection(materials):
    intake = _intake()

    with pytest.raises(HveeContractError):
        build_incident_replay_preparation_bundle(
            intake_payload=intake.payload,
            expected_intake_sha256=intake.sha256,
            artifact_materials=materials,
        )


def test_builder_rejects_wrong_intake_digest():
    intake = _intake()

    with pytest.raises(
        HveeContractError,
        match="intake evidence failed verification",
    ):
        build_incident_replay_preparation_bundle(
            intake_payload=intake.payload,
            expected_intake_sha256=_sha("f"),
            artifact_materials=_materials(),
        )


def test_builder_rejects_tampered_intake_payload():
    intake = _intake()
    tampered = deepcopy(intake.payload)
    tampered["context"]["audio"]["sample_rate_hz"] = 16000

    with pytest.raises(
        HveeContractError,
        match="intake evidence failed verification",
    ):
        build_incident_replay_preparation_bundle(
            intake_payload=tampered,
            expected_intake_sha256=intake.sha256,
            artifact_materials=_materials(),
        )


@pytest.mark.parametrize("intake_payload", (None, [], "payload"))
def test_builder_rejects_non_object_intake(intake_payload):
    with pytest.raises(HveeContractError):
        build_incident_replay_preparation_bundle(
            intake_payload=intake_payload,
            expected_intake_sha256=_sha("1"),
            artifact_materials=(),
        )


@pytest.mark.parametrize(
    "kwargs",
    (
        {"ordinal": 0},
        {"ordinal": True},
        {"operation": "verify_intake_commitment"},
        {"input_commitment_sha256s": []},
        {"input_commitment_sha256s": ()},
        {"input_commitment_sha256s": ("bad",)},
        {
            "input_commitment_sha256s": (
                _sha("1"),
                _sha("1"),
            )
        },
        {"status": "planned"},
    ),
)
def test_replay_step_rejects_noncanonical_values(kwargs):
    values = {
        "ordinal": 1,
        "operation": IncidentReplayOperation.VERIFY_INTAKE_COMMITMENT,
        "input_commitment_sha256s": (_sha("1"),),
        "status": IncidentReplayStepStatus.PLANNED,
    }
    values.update(kwargs)

    with pytest.raises(HveeContractError):
        IncidentReplayStep(**values)


@pytest.mark.parametrize(
    "kwargs",
    (
        {"status": "verified"},
        {"reference_sha256": "bad"},
        {"expected_byte_length": 0},
        {"media_type": "audio"},
        {"observed_sha256": "bad"},
        {"observed_byte_length": -1},
    ),
)
def test_artifact_verification_rejects_noncanonical_values(kwargs):
    reference = _source_reference()
    values = {
        "kind": IncidentArtifactKind.SOURCE_AUDIO,
        "reference_sha256": reference.sha256,
        "expected_byte_length": reference.byte_length,
        "media_type": reference.media_type,
        "observed_sha256": reference.sha256,
        "observed_byte_length": reference.byte_length,
        "status": IncidentArtifactVerificationStatus.VERIFIED,
    }
    values.update(kwargs)

    with pytest.raises(HveeContractError):
        IncidentArtifactVerification(**values)


@pytest.mark.parametrize(
    "kwargs",
    (
        {"observed_sha256": None},
        {"observed_byte_length": None},
        {"expected_byte_length": None},
        {"media_type": None},
        {"status": IncidentArtifactVerificationStatus.MISSING},
        {"status": IncidentArtifactVerificationStatus.UNEXPECTED},
        {
            "status": (
                IncidentArtifactVerificationStatus.DIGEST_MISMATCH
            )
        },
    ),
)
def test_artifact_verification_rejects_contradictory_shape(kwargs):
    reference = _source_reference()
    values = {
        "kind": IncidentArtifactKind.SOURCE_AUDIO,
        "reference_sha256": reference.sha256,
        "expected_byte_length": reference.byte_length,
        "media_type": reference.media_type,
        "observed_sha256": reference.sha256,
        "observed_byte_length": reference.byte_length,
        "status": IncidentArtifactVerificationStatus.VERIFIED,
    }
    values.update(kwargs)

    with pytest.raises(HveeContractError):
        IncidentArtifactVerification(**values)


def test_verifier_accepts_exact_prepared_bundle():
    intake = _intake()
    bundle = _preparation(intake=intake)

    assert verify_incident_replay_preparation_bundle(
        payload=bundle.payload,
        expected_sha256=bundle.sha256,
        intake_payload=intake.payload,
        expected_intake_sha256=intake.sha256,
    )


def test_verifier_accepts_exact_blocked_bundle():
    intake = _intake()
    materials = tuple(
        value
        for value in _materials()
        if value.kind != IncidentArtifactKind.TRANSPORT_TRACE
    )
    bundle = _preparation(intake=intake, materials=materials)

    assert verify_incident_replay_preparation_bundle(
        payload=bundle.payload,
        expected_sha256=bundle.sha256,
        intake_payload=intake.payload,
        expected_intake_sha256=intake.sha256,
    )


def test_verifier_rejects_wrong_preparation_digest():
    intake = _intake()
    bundle = _preparation(intake=intake)

    assert not verify_incident_replay_preparation_bundle(
        payload=bundle.payload,
        expected_sha256=_sha("f"),
        intake_payload=intake.payload,
        expected_intake_sha256=intake.sha256,
    )


def test_verifier_rejects_wrong_intake_digest():
    intake = _intake()
    bundle = _preparation(intake=intake)

    assert not verify_incident_replay_preparation_bundle(
        payload=bundle.payload,
        expected_sha256=bundle.sha256,
        intake_payload=intake.payload,
        expected_intake_sha256=_sha("f"),
    )


@pytest.mark.parametrize(
    "mutation",
    (
        lambda payload: payload["incident"].update(
            {"version": "2.0.0"}
        ),
        lambda payload: payload["artifact_verification"].update(
            {"verified_count": 0}
        ),
        lambda payload: payload["artifact_verification"][
            "receipts"
        ][0].update({"observed_byte_length": 999}),
        lambda payload: payload["preparation"].update(
            {"status": "blocked_artifact_verification"}
        ),
        lambda payload: payload["replay_plan"]["steps"][0].update(
            {"ordinal": 2}
        ),
        lambda payload: payload["replay_plan"].update(
            {"execution_started": True}
        ),
        lambda payload: payload["content_boundary"].update(
            {"artifact_bytes_embedded": True}
        ),
        lambda payload: payload["evidence_boundary"].update(
            {"replay_executed": True}
        ),
    ),
)
def test_verifier_rejects_tampering(mutation):
    intake = _intake()
    bundle = _preparation(intake=intake)
    tampered = deepcopy(bundle.payload)
    mutation(tampered)

    assert not verify_incident_replay_preparation_bundle(
        payload=tampered,
        expected_sha256=bundle.sha256,
        intake_payload=intake.payload,
        expected_intake_sha256=intake.sha256,
    )


@pytest.mark.parametrize(
    "target",
    (
        "top",
        "incident",
        "artifact_verification",
        "receipt",
        "preparation",
        "replay_plan",
        "step",
        "content_boundary",
        "evidence_boundary",
    ),
)
def test_verifier_rejects_extra_fields(target):
    intake = _intake()
    bundle = _preparation(intake=intake)
    tampered = deepcopy(bundle.payload)
    targets = {
        "top": tampered,
        "incident": tampered["incident"],
        "artifact_verification": tampered["artifact_verification"],
        "receipt": tampered["artifact_verification"]["receipts"][0],
        "preparation": tampered["preparation"],
        "replay_plan": tampered["replay_plan"],
        "step": tampered["replay_plan"]["steps"][0],
        "content_boundary": tampered["content_boundary"],
        "evidence_boundary": tampered["evidence_boundary"],
    }
    targets[target]["unexpected"] = True

    assert not verify_incident_replay_preparation_bundle(
        payload=tampered,
        expected_sha256=bundle.sha256,
        intake_payload=intake.payload,
        expected_intake_sha256=intake.sha256,
    )


def test_verifier_rejects_recomputed_digest_after_receipt_forgery():
    intake = _intake()
    bundle = _preparation(intake=intake)
    tampered = deepcopy(bundle.payload)
    tampered["artifact_verification"]["receipts"][0][
        "reference_sha256"
    ] = _sha("e")
    tampered_sha256 = calculate_incident_replay_preparation_sha256(
        tampered
    )

    assert not verify_incident_replay_preparation_bundle(
        payload=tampered,
        expected_sha256=tampered_sha256,
        intake_payload=intake.payload,
        expected_intake_sha256=intake.sha256,
    )


def test_verifier_rejects_noncanonical_receipt_order():
    intake = _intake()
    bundle = _preparation(intake=intake)
    tampered = deepcopy(bundle.payload)
    tampered["artifact_verification"]["receipts"].reverse()
    tampered_sha256 = calculate_incident_replay_preparation_sha256(
        tampered
    )

    assert not verify_incident_replay_preparation_bundle(
        payload=tampered,
        expected_sha256=tampered_sha256,
        intake_payload=intake.payload,
        expected_intake_sha256=intake.sha256,
    )


def test_content_boundary_is_explicit():
    assert _preparation().payload["content_boundary"] == {
        "raw_audio_embedded": False,
        "raw_transcript_embedded": False,
        "model_output_embedded": False,
        "transport_trace_embedded": False,
        "local_artifact_locator_embedded": False,
        "artifact_bytes_embedded": False,
        "artifact_bytes_processed_inside_runner": True,
        "artifact_bytes_retained_in_evidence": False,
        "artifacts_referenced_by_digest_only": True,
    }


def test_evidence_boundary_is_explicit_for_prepared_plan():
    assert _preparation().payload["evidence_boundary"] == {
        "incident_intake_verified": True,
        "artifact_bytes_verified": True,
        "runner_custody_manifest_verified": True,
        "original_artifact_provenance_verified": False,
        "replay_plan_prepared": True,
        "operator_authorization_granted": False,
        "replay_executed": False,
        "transcriptions_executed": False,
        "models_loaded": False,
        "reproduction_claimed": False,
        "model_failure_verified": False,
        "causal_explanation_claimed": False,
        "counterexample_confirmed": False,
        "contract_promoted": False,
        "blocking_release_gate_enabled": False,
        "qualification_authority": False,
    }


def test_blocked_plan_does_not_claim_artifact_verification():
    boundary = _preparation(materials=()).payload["evidence_boundary"]

    assert boundary["artifact_bytes_verified"] is False
    assert boundary["runner_custody_manifest_verified"] is False
    assert boundary["replay_plan_prepared"] is False


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


def test_evidence_excludes_sensitive_content_and_locators():
    payload = _preparation().payload
    forbidden_keys = {
        "audio_bytes",
        "content",
        "local_path",
        "artifact_url",
        "timestamp",
        "occurred_at",
        "database_id",
        "tenant_id",
        "transcript_text",
        "model_output_text",
        "transport_trace_payload",
    }

    assert _all_keys(payload).isdisjoint(forbidden_keys)
    serialized = json.dumps(payload, sort_keys=True)
    assert _SOURCE_AUDIO_BYTES.hex() not in serialized
    assert "packet_loss_percent" not in serialized
    assert "/Users/customer/private/incident.webm" not in serialized


def test_preparation_never_claims_execution_or_reproduction():
    payload = _preparation().payload
    boundary = payload["evidence_boundary"]

    assert payload["replay_plan"]["execution_started"] is False
    assert boundary["operator_authorization_granted"] is False
    assert boundary["replay_executed"] is False
    assert boundary["transcriptions_executed"] is False
    assert boundary["models_loaded"] is False
    assert boundary["reproduction_claimed"] is False
    assert boundary["model_failure_verified"] is False


def test_preparation_has_no_release_or_qualification_authority():
    boundary = _preparation().payload["evidence_boundary"]

    assert boundary["contract_promoted"] is False
    assert boundary["blocking_release_gate_enabled"] is False
    assert boundary["qualification_authority"] is False


def test_runner_custody_does_not_claim_original_provenance():
    boundary = _preparation().payload["evidence_boundary"]

    assert boundary["runner_custody_manifest_verified"] is True
    assert boundary["original_artifact_provenance_verified"] is False


@pytest.mark.parametrize(
    "kwargs",
    (
        {"payload": []},
        {"artifact_manifest_sha256": "bad"},
        {"replay_plan_sha256": "bad"},
        {"sha256": "bad"},
    ),
)
def test_bundle_rejects_invalid_values(kwargs):
    values = {
        "payload": {},
        "artifact_manifest_sha256": _sha("1"),
        "replay_plan_sha256": _sha("2"),
        "sha256": _sha("3"),
    }
    values.update(kwargs)

    with pytest.raises(HveeContractError):
        IncidentReplayPreparationBundle(**values)


def test_bundle_allows_absent_plan_digest_when_blocked():
    bundle = IncidentReplayPreparationBundle(
        payload={},
        artifact_manifest_sha256=_sha("1"),
        replay_plan_sha256=None,
        sha256=_sha("3"),
    )

    assert bundle.replay_plan_sha256 is None


def test_hash_helpers_reject_non_deterministic_json():
    with pytest.raises(HveeContractError):
        calculate_incident_artifact_manifest_sha256(
            [{"length": float("nan")}]
        )
    with pytest.raises(HveeContractError):
        calculate_incident_replay_plan_sha256(
            {"unsupported": object()}
        )
    with pytest.raises(HveeContractError):
        calculate_incident_replay_preparation_sha256(
            {"unsupported": object()}
        )


def test_context_commitment_change_changes_replay_plan():
    baseline = _intake()
    changed = _intake(
        transport=replace(_transport(), packet_loss_percent=3.0)
    )
    baseline_plan = _preparation(intake=baseline)
    changed_plan = _preparation(intake=changed)

    assert baseline.context_sha256 != changed.context_sha256
    assert baseline_plan.replay_plan_sha256 != (
        changed_plan.replay_plan_sha256
    )


def test_intake_digest_change_changes_preparation_identity():
    baseline = _intake()
    changed = _intake(
        claim=_claim(reporter_evidence_sha256=_sha("d"))
    )

    assert calculate_incident_intake_sha256(baseline.payload) == (
        baseline.sha256
    )
    assert calculate_incident_context_sha256(
        {
            key: value
            for key, value in baseline.payload["context"].items()
            if key != "sha256"
        }
    ) == baseline.context_sha256
    assert _preparation(intake=baseline).sha256 != (
        _preparation(intake=changed).sha256
    )

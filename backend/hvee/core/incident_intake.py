"""Canonical, privacy-bounded intake evidence for one reported incident.

Incident intake records the portable commitments and production context that
may be used by a customer-controlled runner to attempt reconstruction later.
It deliberately does not embed raw audio, transcripts, model output,
transport traces, local paths, timestamps, or database identities.

Incomplete production telemetry is accepted and classified explicitly.  A
ready intake has enough declared context for a replay attempt, but readiness
does not mean that replay occurred, that the incident was reproduced, or that
the model caused the reported behavior.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from enum import StrEnum

from hvee.core.contracts import HveeContractError


INCIDENT_INTAKE_SCHEMA_VERSION = 1

_IDENTIFIER_PATTERN = re.compile(
    r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$"
)
_MEDIA_TYPE_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9!#$&^_.+-]*/"
    r"[a-z0-9][a-z0-9!#$&^_.+-]*$"
)

_CONTENT_BOUNDARY = {
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

_EVIDENCE_BOUNDARY = {
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


class IncidentIntakeStatus(StrEnum):
    ACCEPTED_READY_FOR_REPLAY = "accepted_ready_for_replay"
    ACCEPTED_INCOMPLETE_CONTEXT = "accepted_incomplete_context"


class IncidentReproducibilityStatus(StrEnum):
    NOT_ATTEMPTED = "not_attempted"


class IncidentArtifactKind(StrEnum):
    SOURCE_AUDIO = "source_audio"
    REFERENCE_TRANSCRIPT = "reference_transcript"
    MODEL_OUTPUT = "model_output"
    TRANSPORT_TRACE = "transport_trace"
    INCIDENT_REPORT = "incident_report"


class IncidentTransportKind(StrEnum):
    LOCAL_FILE = "local_file"
    WEBRTC = "webrtc"
    RTP = "rtp"
    SIP = "sip"
    UNKNOWN = "unknown"


class IncidentProcessingState(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    UNKNOWN = "unknown"


class IncidentSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentAffectedStage(StrEnum):
    CAPTURE = "capture"
    TRANSPORT = "transport"
    DECODING = "decoding"
    INFERENCE = "inference"
    POSTPROCESSING = "postprocessing"
    UNKNOWN = "unknown"


def _require_identifier(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or _IDENTIFIER_PATTERN.fullmatch(value) is None
    ):
        raise HveeContractError(
            f"{name} must be a canonical lowercase identifier"
        )

    return value


def _require_non_empty_string(
    *,
    name: str,
    value: object,
    max_length: int = 200,
) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > max_length
    ):
        raise HveeContractError(
            f"{name} must be a non-empty trimmed string "
            f"of at most {max_length} characters"
        )

    return value


def _require_optional_identifier(
    *,
    name: str,
    value: object,
) -> str | None:
    if value is None:
        return None

    return _require_identifier(
        name=name,
        value=value,
    )


def _require_optional_string(
    *,
    name: str,
    value: object,
    max_length: int = 200,
) -> str | None:
    if value is None:
        return None

    return _require_non_empty_string(
        name=name,
        value=value,
        max_length=max_length,
    )


def _require_sha256_hex(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(
            character not in "0123456789abcdef"
            for character in value
        )
    ):
        raise HveeContractError(
            f"{name} must be a lowercase SHA-256 hex digest"
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


def _require_optional_positive_integer(
    *,
    name: str,
    value: object,
) -> int | None:
    if value is None:
        return None

    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 1
    ):
        raise HveeContractError(
            f"{name} must be a positive integer when provided"
        )

    return value


def _require_optional_non_negative_integer(
    *,
    name: str,
    value: object,
) -> int | None:
    if value is None:
        return None

    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
    ):
        raise HveeContractError(
            f"{name} must be a non-negative integer when provided"
        )

    return value


def _require_optional_non_negative_number(
    *,
    name: str,
    value: object,
) -> int | float | None:
    if value is None:
        return None

    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) < 0.0
    ):
        raise HveeContractError(
            f"{name} must be a finite non-negative number when provided"
        )

    return value


def _require_optional_boolean(
    *,
    name: str,
    value: object,
) -> bool | None:
    if value is None:
        return None

    if not isinstance(value, bool):
        raise HveeContractError(
            f"{name} must be a boolean when provided"
        )

    return value


def _require_identity_pair(
    *,
    name: str,
    key: object,
    version: object,
) -> None:
    if (key is None) != (version is None):
        raise HveeContractError(
            f"{name} key and version must be provided together"
        )

    if key is not None:
        _require_identifier(
            name=f"{name} key",
            value=key,
        )
        _require_non_empty_string(
            name=f"{name} version",
            value=version,
            max_length=100,
        )


def _canonical_json_value(
    value: object,
    *,
    name: str,
) -> object:
    try:
        serialized = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return json.loads(serialized)
    except (TypeError, ValueError) as exc:
        raise HveeContractError(
            f"{name} must contain valid deterministic JSON"
        ) from exc


def _canonical_json(
    value: object,
    *,
    name: str,
) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise HveeContractError(
            f"{name} must contain valid deterministic JSON"
        ) from exc


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
class IncidentArtifactReference:
    kind: IncidentArtifactKind
    sha256: str
    byte_length: int
    media_type: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, IncidentArtifactKind):
            raise HveeContractError(
                "incident artifact kind must be canonical"
            )

        _require_sha256_hex(
            name="incident artifact SHA-256",
            value=self.sha256,
        )

        if (
            isinstance(self.byte_length, bool)
            or not isinstance(self.byte_length, int)
            or self.byte_length < 1
        ):
            raise HveeContractError(
                "incident artifact byte length must be positive"
            )

        normalized_media_type = _require_non_empty_string(
            name="incident artifact media type",
            value=self.media_type,
            max_length=128,
        )
        if _MEDIA_TYPE_PATTERN.fullmatch(normalized_media_type) is None:
            raise HveeContractError(
                "incident artifact media type must be canonical"
            )

    @property
    def identity(self) -> tuple[str, str, int, str]:
        return (
            self.kind.value,
            self.sha256,
            self.byte_length,
            self.media_type,
        )


@dataclass(frozen=True, slots=True)
class IncidentClaim:
    key: str
    version: str
    reason_code: str
    severity: IncidentSeverity
    affected_stage: IncidentAffectedStage
    reporter_evidence_sha256: str
    expected_behavior_commitment_sha256: str | None = None
    observed_behavior_commitment_sha256: str | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("incident claim key", self.key),
            ("incident reason code", self.reason_code),
        ):
            _require_identifier(
                name=name,
                value=value,
            )

        _require_non_empty_string(
            name="incident claim version",
            value=self.version,
            max_length=100,
        )

        if not isinstance(self.severity, IncidentSeverity):
            raise HveeContractError(
                "incident severity must be canonical"
            )
        if not isinstance(self.affected_stage, IncidentAffectedStage):
            raise HveeContractError(
                "incident affected stage must be canonical"
            )

        _require_sha256_hex(
            name="incident reporter evidence SHA-256",
            value=self.reporter_evidence_sha256,
        )

        expected = _require_optional_sha256_hex(
            name="expected behavior commitment SHA-256",
            value=self.expected_behavior_commitment_sha256,
        )
        observed = _require_optional_sha256_hex(
            name="observed behavior commitment SHA-256",
            value=self.observed_behavior_commitment_sha256,
        )

        if (expected is None) != (observed is None):
            raise HveeContractError(
                "expected and observed behavior commitments must "
                "be provided together"
            )
        if expected is not None and expected == observed:
            raise HveeContractError(
                "expected and observed behavior commitments "
                "must be distinct"
            )


@dataclass(frozen=True, slots=True)
class IncidentRuntimeContext:
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

    def __post_init__(self) -> None:
        for name, key, version in (
            (
                "incident deployment",
                self.deployment_key,
                self.deployment_version,
            ),
            (
                "incident provider",
                self.provider_key,
                self.provider_version,
            ),
            (
                "incident model",
                self.model_key,
                self.model_version,
            ),
        ):
            _require_identity_pair(
                name=name,
                key=key,
                version=version,
            )

        for name, value in (
            ("model artifact SHA-256", self.model_artifact_sha256),
            ("source code SHA-256", self.source_code_sha256),
            ("configuration SHA-256", self.configuration_sha256),
            (
                "runtime environment SHA-256",
                self.runtime_environment_sha256,
            ),
            (
                "host environment SHA-256",
                self.host_environment_sha256,
            ),
        ):
            _require_optional_sha256_hex(
                name=name,
                value=value,
            )

        if (
            self.model_artifact_sha256 is not None
            and self.model_key is None
        ):
            raise HveeContractError(
                "model artifact identity requires model key and version"
            )


@dataclass(frozen=True, slots=True)
class IncidentAudioContext:
    codec_name: str | None = None
    codec_profile: str | None = None
    container_name: str | None = None
    sample_rate_hz: int | None = None
    channel_count: int | None = None
    bit_rate_bps: int | None = None
    duration_ms: int | None = None
    variable_bit_rate: bool | None = None
    sample_rate_shift_observed: bool | None = None
    automatic_gain_control: IncidentProcessingState = (
        IncidentProcessingState.UNKNOWN
    )
    noise_suppression: IncidentProcessingState = (
        IncidentProcessingState.UNKNOWN
    )
    echo_cancellation: IncidentProcessingState = (
        IncidentProcessingState.UNKNOWN
    )
    input_device_class: str | None = None

    def __post_init__(self) -> None:
        _require_optional_identifier(
            name="audio codec name",
            value=self.codec_name,
        )
        _require_optional_string(
            name="audio codec profile",
            value=self.codec_profile,
            max_length=100,
        )
        _require_optional_identifier(
            name="audio container name",
            value=self.container_name,
        )
        _require_optional_identifier(
            name="audio input device class",
            value=self.input_device_class,
        )

        for name, value in (
            ("audio sample rate", self.sample_rate_hz),
            ("audio channel count", self.channel_count),
            ("audio bit rate", self.bit_rate_bps),
            ("audio duration", self.duration_ms),
        ):
            _require_optional_positive_integer(
                name=name,
                value=value,
            )

        if self.channel_count is not None and self.channel_count > 32:
            raise HveeContractError(
                "audio channel count cannot exceed 32"
            )

        _require_optional_boolean(
            name="audio variable bit rate flag",
            value=self.variable_bit_rate,
        )
        _require_optional_boolean(
            name="audio sample-rate-shift flag",
            value=self.sample_rate_shift_observed,
        )

        for name, value in (
            ("automatic gain control state", self.automatic_gain_control),
            ("noise suppression state", self.noise_suppression),
            ("echo cancellation state", self.echo_cancellation),
        ):
            if not isinstance(value, IncidentProcessingState):
                raise HveeContractError(
                    f"{name} must be canonical"
                )


@dataclass(frozen=True, slots=True)
class IncidentTransportContext:
    kind: IncidentTransportKind
    packet_loss_percent: int | float | None = None
    network_jitter_ms: int | float | None = None
    jitter_buffer_ms: int | float | None = None
    round_trip_time_ms: int | float | None = None
    burst_loss_max_packets: int | None = None
    concealed_audio_ms: int | None = None
    codec_switch_count: int | None = None
    sample_rate_shift_count: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, IncidentTransportKind):
            raise HveeContractError(
                "incident transport kind must be canonical"
            )

        packet_loss = _require_optional_non_negative_number(
            name="transport packet loss percent",
            value=self.packet_loss_percent,
        )
        if packet_loss is not None and float(packet_loss) > 100.0:
            raise HveeContractError(
                "transport packet loss percent cannot exceed 100"
            )

        for name, value in (
            ("transport network jitter", self.network_jitter_ms),
            ("transport jitter buffer", self.jitter_buffer_ms),
            ("transport round-trip time", self.round_trip_time_ms),
        ):
            _require_optional_non_negative_number(
                name=name,
                value=value,
            )

        for name, value in (
            (
                "transport maximum burst loss",
                self.burst_loss_max_packets,
            ),
            ("transport concealed audio", self.concealed_audio_ms),
            ("transport codec switch count", self.codec_switch_count),
            (
                "transport sample-rate-shift count",
                self.sample_rate_shift_count,
            ),
        ):
            _require_optional_non_negative_integer(
                name=name,
                value=value,
            )


@dataclass(frozen=True, slots=True)
class IncidentIntakeBundle:
    payload: dict[str, object]
    context_sha256: str
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.payload, dict):
            raise HveeContractError(
                "incident intake payload must be a JSON object"
            )

        _require_sha256_hex(
            name="incident context SHA-256",
            value=self.context_sha256,
        )
        _require_sha256_hex(
            name="incident intake SHA-256",
            value=self.sha256,
        )


def _artifact_payload(
    artifact: IncidentArtifactReference,
) -> dict[str, object]:
    return {
        "kind": artifact.kind.value,
        "sha256": artifact.sha256,
        "byte_length": artifact.byte_length,
        "media_type": artifact.media_type,
    }


def _canonical_artifacts(
    artifacts: object,
) -> tuple[IncidentArtifactReference, ...]:
    if not isinstance(artifacts, (list, tuple)):
        raise HveeContractError(
            "incident artifact references must be a list or tuple"
        )
    if not all(
        isinstance(artifact, IncidentArtifactReference)
        for artifact in artifacts
    ):
        raise HveeContractError(
            "incident artifact references must be canonical"
        )

    ordered = tuple(
        sorted(
            artifacts,
            key=lambda artifact: artifact.identity,
        )
    )
    identities = tuple(
        artifact.identity
        for artifact in ordered
    )
    digests = tuple(
        artifact.sha256
        for artifact in ordered
    )

    if len(identities) != len(set(identities)):
        raise HveeContractError(
            "incident artifact identities must be unique"
        )
    if len(digests) != len(set(digests)):
        raise HveeContractError(
            "one incident artifact digest cannot have multiple roles"
        )

    return ordered


def _claim_payload(
    claim: IncidentClaim,
) -> dict[str, object]:
    return {
        "key": claim.key,
        "version": claim.version,
        "reason_code": claim.reason_code,
        "severity": claim.severity.value,
        "affected_stage": claim.affected_stage.value,
        "reporter_evidence_sha256": claim.reporter_evidence_sha256,
        "expected_behavior_commitment_sha256": (
            claim.expected_behavior_commitment_sha256
        ),
        "observed_behavior_commitment_sha256": (
            claim.observed_behavior_commitment_sha256
        ),
        "verified": False,
    }


def _runtime_payload(
    runtime: IncidentRuntimeContext,
) -> dict[str, object]:
    return {
        "deployment": {
            "key": runtime.deployment_key,
            "version": runtime.deployment_version,
        },
        "provider": {
            "key": runtime.provider_key,
            "version": runtime.provider_version,
        },
        "model": {
            "key": runtime.model_key,
            "version": runtime.model_version,
            "artifact_sha256": runtime.model_artifact_sha256,
        },
        "source_code_sha256": runtime.source_code_sha256,
        "configuration_sha256": runtime.configuration_sha256,
        "runtime_environment_sha256": (
            runtime.runtime_environment_sha256
        ),
        "host_environment_sha256": runtime.host_environment_sha256,
    }


def _audio_payload(
    audio: IncidentAudioContext,
) -> dict[str, object]:
    return {
        "codec": {
            "name": audio.codec_name,
            "profile": audio.codec_profile,
        },
        "container_name": audio.container_name,
        "sample_rate_hz": audio.sample_rate_hz,
        "channel_count": audio.channel_count,
        "bit_rate_bps": audio.bit_rate_bps,
        "duration_ms": audio.duration_ms,
        "variable_bit_rate": audio.variable_bit_rate,
        "sample_rate_shift_observed": (
            audio.sample_rate_shift_observed
        ),
        "capture_processing": {
            "automatic_gain_control": (
                audio.automatic_gain_control.value
            ),
            "noise_suppression": audio.noise_suppression.value,
            "echo_cancellation": audio.echo_cancellation.value,
        },
        "input_device_class": audio.input_device_class,
    }


def _transport_payload(
    transport: IncidentTransportContext,
) -> dict[str, object]:
    return {
        "kind": transport.kind.value,
        "packet_loss_percent": transport.packet_loss_percent,
        "network_jitter_ms": transport.network_jitter_ms,
        "jitter_buffer_ms": transport.jitter_buffer_ms,
        "round_trip_time_ms": transport.round_trip_time_ms,
        "burst_loss_max_packets": transport.burst_loss_max_packets,
        "concealed_audio_ms": transport.concealed_audio_ms,
        "codec_switch_count": transport.codec_switch_count,
        "sample_rate_shift_count": transport.sample_rate_shift_count,
    }


def _missing_context_fields(
    *,
    runtime: IncidentRuntimeContext,
    audio: IncidentAudioContext,
    transport: IncidentTransportContext,
    artifacts: tuple[IncidentArtifactReference, ...],
) -> tuple[str, ...]:
    missing: set[str] = set()

    if not any(
        artifact.kind == IncidentArtifactKind.SOURCE_AUDIO
        for artifact in artifacts
    ):
        missing.add("artifact.source_audio")

    for field_name, available in (
        (
            "runtime.deployment_identity",
            runtime.deployment_key is not None,
        ),
        (
            "runtime.provider_identity",
            runtime.provider_key is not None,
        ),
        (
            "runtime.model_identity",
            runtime.model_key is not None,
        ),
        (
            "runtime.model_artifact_sha256",
            runtime.model_artifact_sha256 is not None,
        ),
        (
            "runtime.source_code_sha256",
            runtime.source_code_sha256 is not None,
        ),
        (
            "runtime.configuration_sha256",
            runtime.configuration_sha256 is not None,
        ),
        (
            "runtime.runtime_environment_sha256",
            runtime.runtime_environment_sha256 is not None,
        ),
        (
            "runtime.host_environment_sha256",
            runtime.host_environment_sha256 is not None,
        ),
        ("audio.codec_name", audio.codec_name is not None),
        ("audio.container_name", audio.container_name is not None),
        ("audio.sample_rate_hz", audio.sample_rate_hz is not None),
        ("audio.channel_count", audio.channel_count is not None),
        ("audio.duration_ms", audio.duration_ms is not None),
        (
            "transport.kind",
            transport.kind != IncidentTransportKind.UNKNOWN,
        ),
    ):
        if not available:
            missing.add(field_name)

    network_transport = transport.kind in {
        IncidentTransportKind.WEBRTC,
        IncidentTransportKind.RTP,
        IncidentTransportKind.SIP,
    }
    if network_transport:
        for field_name, available in (
            (
                "artifact.transport_trace",
                any(
                    artifact.kind
                    == IncidentArtifactKind.TRANSPORT_TRACE
                    for artifact in artifacts
                ),
            ),
            (
                "audio.variable_bit_rate",
                audio.variable_bit_rate is not None,
            ),
            (
                "audio.sample_rate_shift_observed",
                audio.sample_rate_shift_observed is not None,
            ),
            (
                "transport.packet_loss_percent",
                transport.packet_loss_percent is not None,
            ),
            (
                "transport.network_jitter_ms",
                transport.network_jitter_ms is not None,
            ),
            (
                "transport.jitter_buffer_ms",
                transport.jitter_buffer_ms is not None,
            ),
            (
                "transport.burst_loss_max_packets",
                transport.burst_loss_max_packets is not None,
            ),
            (
                "transport.codec_switch_count",
                transport.codec_switch_count is not None,
            ),
        ):
            if not available:
                missing.add(field_name)

    if transport.kind == IncidentTransportKind.WEBRTC:
        for field_name, state in (
            (
                "audio.automatic_gain_control",
                audio.automatic_gain_control,
            ),
            (
                "audio.noise_suppression",
                audio.noise_suppression,
            ),
            (
                "audio.echo_cancellation",
                audio.echo_cancellation,
            ),
        ):
            if state == IncidentProcessingState.UNKNOWN:
                missing.add(field_name)

    return tuple(sorted(missing))


def calculate_incident_context_sha256(
    context: dict[str, object],
) -> str:
    return _calculate_sha256(
        context,
        name="incident context",
    )


def calculate_incident_intake_sha256(
    payload: dict[str, object],
) -> str:
    return _calculate_sha256(
        payload,
        name="incident intake",
    )


def build_incident_intake_bundle(
    *,
    evaluation_type: str,
    incident_key: str,
    incident_version: str,
    source_event_commitment_sha256: str,
    claim: IncidentClaim,
    runtime: IncidentRuntimeContext,
    audio: IncidentAudioContext,
    transport: IncidentTransportContext,
    artifacts: list[IncidentArtifactReference]
    | tuple[IncidentArtifactReference, ...],
) -> IncidentIntakeBundle:
    normalized_evaluation_type = _require_identifier(
        name="incident evaluation type",
        value=evaluation_type,
    )
    normalized_incident_key = _require_identifier(
        name="incident key",
        value=incident_key,
    )
    normalized_incident_version = _require_non_empty_string(
        name="incident version",
        value=incident_version,
        max_length=100,
    )
    normalized_source_commitment = _require_sha256_hex(
        name="source event commitment SHA-256",
        value=source_event_commitment_sha256,
    )

    if not isinstance(claim, IncidentClaim):
        raise HveeContractError(
            "incident claim must be canonical"
        )
    if not isinstance(runtime, IncidentRuntimeContext):
        raise HveeContractError(
            "incident runtime context must be canonical"
        )
    if not isinstance(audio, IncidentAudioContext):
        raise HveeContractError(
            "incident audio context must be canonical"
        )
    if not isinstance(transport, IncidentTransportContext):
        raise HveeContractError(
            "incident transport context must be canonical"
        )

    ordered_artifacts = _canonical_artifacts(artifacts)
    context_body: dict[str, object] = {
        "runtime": _runtime_payload(runtime),
        "audio": _audio_payload(audio),
        "transport": _transport_payload(transport),
        "artifacts": [
            _artifact_payload(artifact)
            for artifact in ordered_artifacts
        ],
    }
    canonical_context = _canonical_json_value(
        context_body,
        name="incident context",
    )
    if not isinstance(canonical_context, dict):
        raise HveeContractError(
            "incident context must be a JSON object"
        )
    context_sha256 = calculate_incident_context_sha256(
        canonical_context
    )

    missing_fields = _missing_context_fields(
        runtime=runtime,
        audio=audio,
        transport=transport,
        artifacts=ordered_artifacts,
    )
    ready_for_replay = not missing_fields
    status = (
        IncidentIntakeStatus.ACCEPTED_READY_FOR_REPLAY
        if ready_for_replay
        else IncidentIntakeStatus.ACCEPTED_INCOMPLETE_CONTEXT
    )

    payload: dict[str, object] = {
        "schema_version": INCIDENT_INTAKE_SCHEMA_VERSION,
        "type": "incident_intake",
        "evaluation_type": normalized_evaluation_type,
        "incident": {
            "key": normalized_incident_key,
            "version": normalized_incident_version,
            "source_event_commitment_sha256": (
                normalized_source_commitment
            ),
        },
        "claim": _claim_payload(claim),
        "context": {
            **canonical_context,
            "sha256": context_sha256,
        },
        "intake": {
            "status": status.value,
            "ready_for_replay": ready_for_replay,
            "missing_context_fields": list(missing_fields),
        },
        "reproducibility": {
            "status": IncidentReproducibilityStatus.NOT_ATTEMPTED.value,
            "replay_execution_count": 0,
            "same_host_verified": False,
            "cross_host_verified": False,
        },
        "content_boundary": dict(_CONTENT_BOUNDARY),
        "evidence_boundary": dict(_EVIDENCE_BOUNDARY),
    }

    canonical_payload = _canonical_json_value(
        payload,
        name="incident intake",
    )
    if not isinstance(canonical_payload, dict):
        raise HveeContractError(
            "incident intake must be a JSON object"
        )

    return IncidentIntakeBundle(
        payload=canonical_payload,
        context_sha256=context_sha256,
        sha256=calculate_incident_intake_sha256(
            canonical_payload
        ),
    )


def _parse_claim(value: object) -> IncidentClaim:
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "key",
            "version",
            "reason_code",
            "severity",
            "affected_stage",
            "reporter_evidence_sha256",
            "expected_behavior_commitment_sha256",
            "observed_behavior_commitment_sha256",
            "verified",
        }
        or value.get("verified") is not False
    ):
        raise HveeContractError(
            "invalid incident claim shape"
        )

    return IncidentClaim(
        key=value.get("key"),
        version=value.get("version"),
        reason_code=value.get("reason_code"),
        severity=IncidentSeverity(value.get("severity")),
        affected_stage=IncidentAffectedStage(
            value.get("affected_stage")
        ),
        reporter_evidence_sha256=value.get(
            "reporter_evidence_sha256"
        ),
        expected_behavior_commitment_sha256=value.get(
            "expected_behavior_commitment_sha256"
        ),
        observed_behavior_commitment_sha256=value.get(
            "observed_behavior_commitment_sha256"
        ),
    )


def _parse_runtime(value: object) -> IncidentRuntimeContext:
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "deployment",
            "provider",
            "model",
            "source_code_sha256",
            "configuration_sha256",
            "runtime_environment_sha256",
            "host_environment_sha256",
        }
    ):
        raise HveeContractError(
            "invalid incident runtime context shape"
        )

    deployment = value.get("deployment")
    provider = value.get("provider")
    model = value.get("model")
    if (
        not isinstance(deployment, dict)
        or set(deployment) != {"key", "version"}
        or not isinstance(provider, dict)
        or set(provider) != {"key", "version"}
        or not isinstance(model, dict)
        or set(model) != {"key", "version", "artifact_sha256"}
    ):
        raise HveeContractError(
            "invalid incident runtime identity shape"
        )

    return IncidentRuntimeContext(
        deployment_key=deployment.get("key"),
        deployment_version=deployment.get("version"),
        provider_key=provider.get("key"),
        provider_version=provider.get("version"),
        model_key=model.get("key"),
        model_version=model.get("version"),
        model_artifact_sha256=model.get("artifact_sha256"),
        source_code_sha256=value.get("source_code_sha256"),
        configuration_sha256=value.get("configuration_sha256"),
        runtime_environment_sha256=value.get(
            "runtime_environment_sha256"
        ),
        host_environment_sha256=value.get(
            "host_environment_sha256"
        ),
    )


def _parse_audio(value: object) -> IncidentAudioContext:
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "codec",
            "container_name",
            "sample_rate_hz",
            "channel_count",
            "bit_rate_bps",
            "duration_ms",
            "variable_bit_rate",
            "sample_rate_shift_observed",
            "capture_processing",
            "input_device_class",
        }
    ):
        raise HveeContractError(
            "invalid incident audio context shape"
        )

    codec = value.get("codec")
    processing = value.get("capture_processing")
    if (
        not isinstance(codec, dict)
        or set(codec) != {"name", "profile"}
        or not isinstance(processing, dict)
        or set(processing)
        != {
            "automatic_gain_control",
            "noise_suppression",
            "echo_cancellation",
        }
    ):
        raise HveeContractError(
            "invalid incident audio codec or processing shape"
        )

    return IncidentAudioContext(
        codec_name=codec.get("name"),
        codec_profile=codec.get("profile"),
        container_name=value.get("container_name"),
        sample_rate_hz=value.get("sample_rate_hz"),
        channel_count=value.get("channel_count"),
        bit_rate_bps=value.get("bit_rate_bps"),
        duration_ms=value.get("duration_ms"),
        variable_bit_rate=value.get("variable_bit_rate"),
        sample_rate_shift_observed=value.get(
            "sample_rate_shift_observed"
        ),
        automatic_gain_control=IncidentProcessingState(
            processing.get("automatic_gain_control")
        ),
        noise_suppression=IncidentProcessingState(
            processing.get("noise_suppression")
        ),
        echo_cancellation=IncidentProcessingState(
            processing.get("echo_cancellation")
        ),
        input_device_class=value.get("input_device_class"),
    )


def _parse_transport(value: object) -> IncidentTransportContext:
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "kind",
            "packet_loss_percent",
            "network_jitter_ms",
            "jitter_buffer_ms",
            "round_trip_time_ms",
            "burst_loss_max_packets",
            "concealed_audio_ms",
            "codec_switch_count",
            "sample_rate_shift_count",
        }
    ):
        raise HveeContractError(
            "invalid incident transport context shape"
        )

    return IncidentTransportContext(
        kind=IncidentTransportKind(value.get("kind")),
        packet_loss_percent=value.get("packet_loss_percent"),
        network_jitter_ms=value.get("network_jitter_ms"),
        jitter_buffer_ms=value.get("jitter_buffer_ms"),
        round_trip_time_ms=value.get("round_trip_time_ms"),
        burst_loss_max_packets=value.get("burst_loss_max_packets"),
        concealed_audio_ms=value.get("concealed_audio_ms"),
        codec_switch_count=value.get("codec_switch_count"),
        sample_rate_shift_count=value.get("sample_rate_shift_count"),
    )


def _parse_artifact(value: object) -> IncidentArtifactReference:
    if (
        not isinstance(value, dict)
        or set(value)
        != {"kind", "sha256", "byte_length", "media_type"}
    ):
        raise HveeContractError(
            "invalid incident artifact reference shape"
        )

    return IncidentArtifactReference(
        kind=IncidentArtifactKind(value.get("kind")),
        sha256=value.get("sha256"),
        byte_length=value.get("byte_length"),
        media_type=value.get("media_type"),
    )


def verify_incident_intake_bundle(
    *,
    payload: object,
    expected_sha256: object,
) -> bool:
    try:
        if (
            not isinstance(payload, dict)
            or set(payload)
            != {
                "schema_version",
                "type",
                "evaluation_type",
                "incident",
                "claim",
                "context",
                "intake",
                "reproducibility",
                "content_boundary",
                "evidence_boundary",
            }
            or payload.get("schema_version")
            != INCIDENT_INTAKE_SCHEMA_VERSION
            or payload.get("type") != "incident_intake"
            or payload.get("content_boundary") != _CONTENT_BOUNDARY
            or payload.get("evidence_boundary") != _EVIDENCE_BOUNDARY
        ):
            return False

        incident = payload.get("incident")
        context = payload.get("context")
        intake = payload.get("intake")
        reproducibility = payload.get("reproducibility")
        if (
            not isinstance(incident, dict)
            or set(incident)
            != {
                "key",
                "version",
                "source_event_commitment_sha256",
            }
            or not isinstance(context, dict)
            or set(context)
            != {
                "runtime",
                "audio",
                "transport",
                "artifacts",
                "sha256",
            }
            or not isinstance(context.get("artifacts"), list)
            or not isinstance(intake, dict)
            or set(intake)
            != {
                "status",
                "ready_for_replay",
                "missing_context_fields",
            }
            or reproducibility
            != {
                "status": "not_attempted",
                "replay_execution_count": 0,
                "same_host_verified": False,
                "cross_host_verified": False,
            }
        ):
            return False

        claim = _parse_claim(payload.get("claim"))
        runtime = _parse_runtime(context.get("runtime"))
        audio = _parse_audio(context.get("audio"))
        transport = _parse_transport(context.get("transport"))
        artifacts = tuple(
            _parse_artifact(artifact)
            for artifact in context.get("artifacts", ())
        )

        rebuilt = build_incident_intake_bundle(
            evaluation_type=payload.get("evaluation_type"),
            incident_key=incident.get("key"),
            incident_version=incident.get("version"),
            source_event_commitment_sha256=incident.get(
                "source_event_commitment_sha256"
            ),
            claim=claim,
            runtime=runtime,
            audio=audio,
            transport=transport,
            artifacts=artifacts,
        )

        stored_context_sha256 = _require_sha256_hex(
            name="stored incident context SHA-256",
            value=context.get("sha256"),
        )
        normalized_expected_sha256 = _require_sha256_hex(
            name="expected incident intake SHA-256",
            value=expected_sha256,
        )

        return (
            payload == rebuilt.payload
            and stored_context_sha256 == rebuilt.context_sha256
            and normalized_expected_sha256 == rebuilt.sha256
        )

    except (
        HveeContractError,
        TypeError,
        ValueError,
    ):
        return False

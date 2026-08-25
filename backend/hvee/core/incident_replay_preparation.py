"""Tamper-evident artifact verification and replay preparation.

This module is the second bounded Incident Mode stage.  It consumes a
verified incident-intake bundle plus artifact bytes made available inside a
customer-controlled runner.  The bytes are checked against the digest and
length commitments recorded at intake, then discarded from the evidence.

A prepared replay plan is only a deterministic recipe.  It does not mean a
model was loaded, a transcription ran, the incident was reproduced, or the
reported model behavior was proven.  Original artifact provenance before the
runner boundary is also outside this evidence claim.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum

from hvee.core.contracts import HveeContractError
from hvee.core.incident_intake import (
    IncidentArtifactKind,
    calculate_incident_intake_sha256,
    verify_incident_intake_bundle,
)


INCIDENT_REPLAY_PREPARATION_SCHEMA_VERSION = 1

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
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
    "artifact_bytes_processed_inside_runner": True,
    "artifact_bytes_retained_in_evidence": False,
    "artifacts_referenced_by_digest_only": True,
}


class IncidentArtifactVerificationStatus(StrEnum):
    VERIFIED = "verified"
    MISSING = "missing"
    UNEXPECTED = "unexpected"
    DIGEST_MISMATCH = "digest_mismatch"
    LENGTH_MISMATCH = "length_mismatch"
    DIGEST_AND_LENGTH_MISMATCH = "digest_and_length_mismatch"


class IncidentArtifactVerificationSummaryStatus(StrEnum):
    VERIFIED = "verified"
    FAILED = "failed"


class IncidentRunnerCustodyStatus(StrEnum):
    VERIFIED = "verified"
    PARTIAL = "partial"
    REJECTED = "rejected"
    NOT_ESTABLISHED = "not_established"


class IncidentReplayPreparationStatus(StrEnum):
    PREPARED = "prepared"
    BLOCKED_INCOMPLETE_INTAKE = "blocked_incomplete_intake"
    BLOCKED_ARTIFACT_VERIFICATION = (
        "blocked_artifact_verification"
    )
    BLOCKED_AMBIGUOUS_ARTIFACT_ROLES = (
        "blocked_ambiguous_artifact_roles"
    )


class IncidentReplayOperation(StrEnum):
    VERIFY_INTAKE_COMMITMENT = "verify_intake_commitment"
    VERIFY_ARTIFACT_MANIFEST = "verify_artifact_manifest"
    RESTORE_RUNTIME_CONTEXT = "restore_runtime_context"
    RESTORE_AUDIO_CONTEXT = "restore_audio_context"
    RESTORE_TRANSPORT_CONTEXT = "restore_transport_context"
    STAGE_SOURCE_AUDIO = "stage_source_audio"
    STAGE_TRANSPORT_TRACE = "stage_transport_trace"
    EXECUTE_ISOLATED_REPLAY = "execute_isolated_replay"
    CAPTURE_REPLAY_OUTPUT = "capture_replay_output"
    COMPARE_BEHAVIOR_COMMITMENTS = (
        "compare_behavior_commitments"
    )


class IncidentReplayStepStatus(StrEnum):
    PLANNED = "planned"


def _require_sha256_hex(*, name: str, value: object) -> str:
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
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
    return _require_sha256_hex(name=name, value=value)


def _require_positive_integer(*, name: str, value: object) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 1
    ):
        raise HveeContractError(f"{name} must be a positive integer")
    return value


def _require_non_negative_integer(
    *,
    name: str,
    value: object,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
    ):
        raise HveeContractError(
            f"{name} must be a non-negative integer"
        )
    return value


def _require_optional_non_negative_integer(
    *,
    name: str,
    value: object,
) -> int | None:
    if value is None:
        return None
    return _require_non_negative_integer(name=name, value=value)


def _require_media_type(*, name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or _MEDIA_TYPE_PATTERN.fullmatch(value) is None
    ):
        raise HveeContractError(f"{name} must be canonical")
    return value


def _canonical_json(value: object, *, name: str) -> str:
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


def _canonical_json_value(value: object, *, name: str) -> object:
    return json.loads(_canonical_json(value, name=name))


def _calculate_sha256(value: object, *, name: str) -> str:
    canonical = _canonical_json(value, name=name)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class IncidentArtifactMaterial:
    """Ephemeral artifact bytes supplied inside the private runner."""

    kind: IncidentArtifactKind
    reference_sha256: str
    content: bytes

    def __post_init__(self) -> None:
        if not isinstance(self.kind, IncidentArtifactKind):
            raise HveeContractError(
                "incident artifact material kind must be canonical"
            )
        _require_sha256_hex(
            name="incident artifact material reference SHA-256",
            value=self.reference_sha256,
        )
        if not isinstance(self.content, bytes):
            raise HveeContractError(
                "incident artifact material content must be immutable bytes"
            )

    @property
    def identity(self) -> tuple[str, str]:
        return (self.kind.value, self.reference_sha256)


@dataclass(frozen=True, slots=True)
class IncidentArtifactVerification:
    kind: IncidentArtifactKind
    reference_sha256: str
    expected_byte_length: int | None
    media_type: str | None
    observed_sha256: str | None
    observed_byte_length: int | None
    status: IncidentArtifactVerificationStatus

    def __post_init__(self) -> None:
        if not isinstance(self.kind, IncidentArtifactKind):
            raise HveeContractError(
                "artifact verification kind must be canonical"
            )
        _require_sha256_hex(
            name="artifact verification reference SHA-256",
            value=self.reference_sha256,
        )
        if self.expected_byte_length is not None:
            _require_positive_integer(
                name="artifact verification expected byte length",
                value=self.expected_byte_length,
            )
        if self.media_type is not None:
            _require_media_type(
                name="artifact verification media type",
                value=self.media_type,
            )
        _require_optional_sha256_hex(
            name="artifact verification observed SHA-256",
            value=self.observed_sha256,
        )
        _require_optional_non_negative_integer(
            name="artifact verification observed byte length",
            value=self.observed_byte_length,
        )
        if not isinstance(
            self.status,
            IncidentArtifactVerificationStatus,
        ):
            raise HveeContractError(
                "artifact verification status must be canonical"
            )
        self._verify_status_shape()

    def _verify_status_shape(self) -> None:
        observed_present = self.observed_sha256 is not None
        if observed_present != (self.observed_byte_length is not None):
            raise HveeContractError(
                "observed artifact digest and length must be paired"
            )

        expected_present = self.expected_byte_length is not None
        if expected_present != (self.media_type is not None):
            raise HveeContractError(
                "expected artifact length and media type must be paired"
            )

        if self.status == IncidentArtifactVerificationStatus.MISSING:
            if not expected_present or observed_present:
                raise HveeContractError(
                    "missing artifact verification has invalid evidence"
                )
            return

        if self.status == IncidentArtifactVerificationStatus.UNEXPECTED:
            if expected_present or not observed_present:
                raise HveeContractError(
                    "unexpected artifact verification has invalid evidence"
                )
            return

        if not expected_present or not observed_present:
            raise HveeContractError(
                "matched artifact verification requires both identities"
            )

        digest_matches = self.observed_sha256 == self.reference_sha256
        length_matches = (
            self.observed_byte_length == self.expected_byte_length
        )
        expected_status = _verification_status(
            digest_matches=digest_matches,
            length_matches=length_matches,
        )
        if self.status != expected_status:
            raise HveeContractError(
                "artifact verification status contradicts observations"
            )

    @property
    def identity(self) -> tuple[str, str]:
        return (self.kind.value, self.reference_sha256)


@dataclass(frozen=True, slots=True)
class IncidentReplayStep:
    ordinal: int
    operation: IncidentReplayOperation
    input_commitment_sha256s: tuple[str, ...]
    status: IncidentReplayStepStatus = IncidentReplayStepStatus.PLANNED

    def __post_init__(self) -> None:
        _require_positive_integer(
            name="incident replay step ordinal",
            value=self.ordinal,
        )
        if not isinstance(self.operation, IncidentReplayOperation):
            raise HveeContractError(
                "incident replay operation must be canonical"
            )
        if (
            not isinstance(self.input_commitment_sha256s, tuple)
            or not self.input_commitment_sha256s
        ):
            raise HveeContractError(
                "incident replay step inputs must be a non-empty tuple"
            )
        for value in self.input_commitment_sha256s:
            _require_sha256_hex(
                name="incident replay step input commitment",
                value=value,
            )
        if len(self.input_commitment_sha256s) != len(
            set(self.input_commitment_sha256s)
        ):
            raise HveeContractError(
                "incident replay step inputs must be unique"
            )
        if not isinstance(self.status, IncidentReplayStepStatus):
            raise HveeContractError(
                "incident replay step status must be canonical"
            )


@dataclass(frozen=True, slots=True)
class IncidentReplayPreparationBundle:
    payload: dict[str, object]
    artifact_manifest_sha256: str
    replay_plan_sha256: str | None
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.payload, dict):
            raise HveeContractError(
                "incident replay preparation payload must be a JSON object"
            )
        _require_sha256_hex(
            name="incident artifact manifest SHA-256",
            value=self.artifact_manifest_sha256,
        )
        _require_optional_sha256_hex(
            name="incident replay plan SHA-256",
            value=self.replay_plan_sha256,
        )
        _require_sha256_hex(
            name="incident replay preparation SHA-256",
            value=self.sha256,
        )


def _verification_status(
    *,
    digest_matches: bool,
    length_matches: bool,
) -> IncidentArtifactVerificationStatus:
    if digest_matches and length_matches:
        return IncidentArtifactVerificationStatus.VERIFIED
    if digest_matches:
        return IncidentArtifactVerificationStatus.LENGTH_MISMATCH
    if length_matches:
        return IncidentArtifactVerificationStatus.DIGEST_MISMATCH
    return IncidentArtifactVerificationStatus.DIGEST_AND_LENGTH_MISMATCH


def _canonical_materials(
    materials: object,
) -> tuple[IncidentArtifactMaterial, ...]:
    if not isinstance(materials, (list, tuple)):
        raise HveeContractError(
            "incident artifact materials must be a list or tuple"
        )
    if not all(
        isinstance(material, IncidentArtifactMaterial)
        for material in materials
    ):
        raise HveeContractError(
            "incident artifact materials must be canonical"
        )

    ordered = tuple(sorted(materials, key=lambda value: value.identity))
    identities = tuple(value.identity for value in ordered)
    if len(identities) != len(set(identities)):
        raise HveeContractError(
            "incident artifact material identities must be unique"
        )
    return ordered


def _intake_artifact_references(
    intake_payload: dict[str, object],
) -> tuple[dict[str, object], ...]:
    context = intake_payload["context"]
    if not isinstance(context, dict):
        raise HveeContractError("incident context must be canonical")
    values = context["artifacts"]
    if not isinstance(values, list):
        raise HveeContractError(
            "incident artifact references must be canonical"
        )
    return tuple(values)


def _build_artifact_verifications(
    *,
    intake_payload: dict[str, object],
    materials: tuple[IncidentArtifactMaterial, ...],
) -> tuple[IncidentArtifactVerification, ...]:
    references = _intake_artifact_references(intake_payload)
    expected = {
        (
            str(reference["kind"]),
            str(reference["sha256"]),
        ): reference
        for reference in references
    }
    supplied = {material.identity: material for material in materials}

    verifications: list[IncidentArtifactVerification] = []
    for identity, reference in expected.items():
        material = supplied.get(identity)
        kind = IncidentArtifactKind(reference["kind"])
        reference_sha256 = _require_sha256_hex(
            name="incident artifact reference SHA-256",
            value=reference["sha256"],
        )
        expected_length = _require_positive_integer(
            name="incident artifact reference byte length",
            value=reference["byte_length"],
        )
        media_type = _require_media_type(
            name="incident artifact reference media type",
            value=reference["media_type"],
        )

        if material is None:
            verifications.append(
                IncidentArtifactVerification(
                    kind=kind,
                    reference_sha256=reference_sha256,
                    expected_byte_length=expected_length,
                    media_type=media_type,
                    observed_sha256=None,
                    observed_byte_length=None,
                    status=IncidentArtifactVerificationStatus.MISSING,
                )
            )
            continue

        observed_sha256 = hashlib.sha256(material.content).hexdigest()
        observed_length = len(material.content)
        verifications.append(
            IncidentArtifactVerification(
                kind=kind,
                reference_sha256=reference_sha256,
                expected_byte_length=expected_length,
                media_type=media_type,
                observed_sha256=observed_sha256,
                observed_byte_length=observed_length,
                status=_verification_status(
                    digest_matches=(
                        observed_sha256 == reference_sha256
                    ),
                    length_matches=(observed_length == expected_length),
                ),
            )
        )

    for identity, material in supplied.items():
        if identity in expected:
            continue
        verifications.append(
            IncidentArtifactVerification(
                kind=material.kind,
                reference_sha256=material.reference_sha256,
                expected_byte_length=None,
                media_type=None,
                observed_sha256=hashlib.sha256(
                    material.content
                ).hexdigest(),
                observed_byte_length=len(material.content),
                status=IncidentArtifactVerificationStatus.UNEXPECTED,
            )
        )

    return tuple(
        sorted(verifications, key=lambda value: value.identity)
    )


def _verification_payload(
    verification: IncidentArtifactVerification,
) -> dict[str, object]:
    return {
        "kind": verification.kind.value,
        "reference_sha256": verification.reference_sha256,
        "expected_byte_length": verification.expected_byte_length,
        "media_type": verification.media_type,
        "observed_sha256": verification.observed_sha256,
        "observed_byte_length": verification.observed_byte_length,
        "status": verification.status.value,
    }


def _step_payload(step: IncidentReplayStep) -> dict[str, object]:
    return {
        "ordinal": step.ordinal,
        "operation": step.operation.value,
        "input_commitment_sha256s": list(
            step.input_commitment_sha256s
        ),
        "status": step.status.value,
    }


def _artifact_counts(
    verifications: tuple[IncidentArtifactVerification, ...],
) -> dict[str, int]:
    statuses = [value.status for value in verifications]
    mismatch_statuses = {
        IncidentArtifactVerificationStatus.DIGEST_MISMATCH,
        IncidentArtifactVerificationStatus.LENGTH_MISMATCH,
        IncidentArtifactVerificationStatus.DIGEST_AND_LENGTH_MISMATCH,
    }
    return {
        "expected_count": sum(
            value.expected_byte_length is not None
            for value in verifications
        ),
        "supplied_count": sum(
            value.observed_sha256 is not None
            for value in verifications
        ),
        "verified_count": statuses.count(
            IncidentArtifactVerificationStatus.VERIFIED
        ),
        "missing_count": statuses.count(
            IncidentArtifactVerificationStatus.MISSING
        ),
        "mismatch_count": sum(
            status in mismatch_statuses for status in statuses
        ),
        "unexpected_count": statuses.count(
            IncidentArtifactVerificationStatus.UNEXPECTED
        ),
    }


def _all_artifacts_verified(
    verifications: tuple[IncidentArtifactVerification, ...],
) -> bool:
    expected = tuple(
        value
        for value in verifications
        if value.expected_byte_length is not None
    )
    return bool(expected) and all(
        value.status == IncidentArtifactVerificationStatus.VERIFIED
        for value in verifications
    )


def _runner_custody_status(
    verifications: tuple[IncidentArtifactVerification, ...],
) -> IncidentRunnerCustodyStatus:
    if _all_artifacts_verified(verifications):
        return IncidentRunnerCustodyStatus.VERIFIED

    statuses = {value.status for value in verifications}
    rejected = statuses.intersection(
        {
            IncidentArtifactVerificationStatus.UNEXPECTED,
            IncidentArtifactVerificationStatus.DIGEST_MISMATCH,
            IncidentArtifactVerificationStatus.LENGTH_MISMATCH,
            (
                IncidentArtifactVerificationStatus
                .DIGEST_AND_LENGTH_MISMATCH
            ),
        }
    )
    if rejected:
        return IncidentRunnerCustodyStatus.REJECTED
    if IncidentArtifactVerificationStatus.VERIFIED in statuses:
        return IncidentRunnerCustodyStatus.PARTIAL
    return IncidentRunnerCustodyStatus.NOT_ESTABLISHED


def _ambiguous_artifact_roles(
    intake_payload: dict[str, object],
) -> tuple[str, ...]:
    counts = {kind: 0 for kind in IncidentArtifactKind}
    for reference in _intake_artifact_references(intake_payload):
        counts[IncidentArtifactKind(reference["kind"])] += 1

    ambiguous = [
        f"artifact_role.{kind.value}.count_{count}"
        for kind, count in counts.items()
        if count > 1
    ]
    if counts[IncidentArtifactKind.SOURCE_AUDIO] == 0:
        ambiguous.append(
            "artifact_role.source_audio.requires_exactly_one"
        )
    return tuple(sorted(ambiguous))


def _artifact_blockers(
    verifications: tuple[IncidentArtifactVerification, ...],
) -> tuple[str, ...]:
    return tuple(
        sorted(
            "artifact."
            f"{value.kind.value}."
            f"{value.reference_sha256}."
            f"{value.status.value}"
            for value in verifications
            if value.status
            != IncidentArtifactVerificationStatus.VERIFIED
        )
    )


def _intake_missing_fields(
    intake_payload: dict[str, object],
) -> tuple[str, ...]:
    intake = intake_payload["intake"]
    if not isinstance(intake, dict):
        raise HveeContractError("incident intake status must be canonical")
    values = intake["missing_context_fields"]
    if not isinstance(values, list) or not all(
        isinstance(value, str) for value in values
    ):
        raise HveeContractError(
            "incident missing context fields must be canonical"
        )
    return tuple(f"intake.{value}" for value in values)


def _preparation_status(
    *,
    intake_payload: dict[str, object],
    verifications: tuple[IncidentArtifactVerification, ...],
    ambiguous_roles: tuple[str, ...],
) -> IncidentReplayPreparationStatus:
    intake = intake_payload["intake"]
    if not isinstance(intake, dict):
        raise HveeContractError("incident intake status must be canonical")
    if intake["ready_for_replay"] is not True:
        return IncidentReplayPreparationStatus.BLOCKED_INCOMPLETE_INTAKE
    if not _all_artifacts_verified(verifications):
        return (
            IncidentReplayPreparationStatus
            .BLOCKED_ARTIFACT_VERIFICATION
        )
    if ambiguous_roles:
        return (
            IncidentReplayPreparationStatus
            .BLOCKED_AMBIGUOUS_ARTIFACT_ROLES
        )
    return IncidentReplayPreparationStatus.PREPARED


def _reference_digest(
    *,
    intake_payload: dict[str, object],
    kind: IncidentArtifactKind,
) -> str | None:
    matches = [
        _require_sha256_hex(
            name=f"{kind.value} reference SHA-256",
            value=reference["sha256"],
        )
        for reference in _intake_artifact_references(intake_payload)
        if reference["kind"] == kind.value
    ]
    if not matches:
        return None
    if len(matches) != 1:
        raise HveeContractError(
            f"{kind.value} requires one unambiguous artifact"
        )
    return matches[0]


def _context_component_sha256(
    *,
    intake_payload: dict[str, object],
    component: str,
) -> str:
    context = intake_payload["context"]
    if not isinstance(context, dict):
        raise HveeContractError("incident context must be canonical")
    return _calculate_sha256(
        context[component],
        name=f"incident {component} context",
    )


def _build_replay_steps(
    *,
    intake_payload: dict[str, object],
    intake_sha256: str,
    artifact_manifest_sha256: str,
) -> tuple[IncidentReplayStep, ...]:
    context = intake_payload["context"]
    claim = intake_payload["claim"]
    if not isinstance(context, dict) or not isinstance(claim, dict):
        raise HveeContractError(
            "incident replay inputs must be canonical"
        )

    context_sha256 = _require_sha256_hex(
        name="incident context SHA-256",
        value=context["sha256"],
    )
    source_audio_sha256 = _reference_digest(
        intake_payload=intake_payload,
        kind=IncidentArtifactKind.SOURCE_AUDIO,
    )
    if source_audio_sha256 is None:
        raise HveeContractError(
            "prepared replay requires one source audio artifact"
        )
    transport_trace_sha256 = _reference_digest(
        intake_payload=intake_payload,
        kind=IncidentArtifactKind.TRANSPORT_TRACE,
    )

    values: list[
        tuple[IncidentReplayOperation, tuple[str, ...]]
    ] = [
        (
            IncidentReplayOperation.VERIFY_INTAKE_COMMITMENT,
            (intake_sha256,),
        ),
        (
            IncidentReplayOperation.VERIFY_ARTIFACT_MANIFEST,
            (artifact_manifest_sha256,),
        ),
        (
            IncidentReplayOperation.RESTORE_RUNTIME_CONTEXT,
            (
                _context_component_sha256(
                    intake_payload=intake_payload,
                    component="runtime",
                ),
            ),
        ),
        (
            IncidentReplayOperation.RESTORE_AUDIO_CONTEXT,
            (
                _context_component_sha256(
                    intake_payload=intake_payload,
                    component="audio",
                ),
            ),
        ),
        (
            IncidentReplayOperation.RESTORE_TRANSPORT_CONTEXT,
            (
                _context_component_sha256(
                    intake_payload=intake_payload,
                    component="transport",
                ),
            ),
        ),
        (
            IncidentReplayOperation.STAGE_SOURCE_AUDIO,
            (source_audio_sha256,),
        ),
    ]
    if transport_trace_sha256 is not None:
        values.append(
            (
                IncidentReplayOperation.STAGE_TRANSPORT_TRACE,
                (transport_trace_sha256,),
            )
        )

    execution_inputs = [context_sha256, source_audio_sha256]
    if transport_trace_sha256 is not None:
        execution_inputs.append(transport_trace_sha256)
    values.extend(
        [
            (
                IncidentReplayOperation.EXECUTE_ISOLATED_REPLAY,
                tuple(dict.fromkeys(execution_inputs)),
            ),
            (
                IncidentReplayOperation.CAPTURE_REPLAY_OUTPUT,
                (context_sha256,),
            ),
        ]
    )

    comparison_inputs = [
        _require_sha256_hex(
            name="reporter evidence SHA-256",
            value=claim["reporter_evidence_sha256"],
        )
    ]
    for field_name in (
        "expected_behavior_commitment_sha256",
        "observed_behavior_commitment_sha256",
    ):
        value = claim[field_name]
        if value is not None:
            comparison_inputs.append(
                _require_sha256_hex(
                    name=field_name.replace("_", " "),
                    value=value,
                )
            )
    values.append(
        (
            IncidentReplayOperation.COMPARE_BEHAVIOR_COMMITMENTS,
            tuple(dict.fromkeys(comparison_inputs)),
        )
    )

    return tuple(
        IncidentReplayStep(
            ordinal=index,
            operation=operation,
            input_commitment_sha256s=commitments,
        )
        for index, (operation, commitments) in enumerate(
            values,
            start=1,
        )
    )


def _evidence_boundary(
    *,
    artifacts_verified: bool,
    replay_prepared: bool,
) -> dict[str, bool]:
    return {
        "incident_intake_verified": True,
        "artifact_bytes_verified": artifacts_verified,
        "runner_custody_manifest_verified": artifacts_verified,
        "original_artifact_provenance_verified": False,
        "replay_plan_prepared": replay_prepared,
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


def _assemble_bundle(
    *,
    intake_payload: dict[str, object],
    intake_sha256: str,
    verifications: tuple[IncidentArtifactVerification, ...],
) -> IncidentReplayPreparationBundle:
    verification_payloads = [
        _verification_payload(value) for value in verifications
    ]
    manifest_body = {"receipts": verification_payloads}
    artifact_manifest_sha256 = _calculate_sha256(
        manifest_body,
        name="incident artifact custody manifest",
    )
    counts = _artifact_counts(verifications)
    artifacts_verified = _all_artifacts_verified(verifications)
    ambiguous_roles = _ambiguous_artifact_roles(intake_payload)
    status = _preparation_status(
        intake_payload=intake_payload,
        verifications=verifications,
        ambiguous_roles=ambiguous_roles,
    )
    replay_prepared = status == IncidentReplayPreparationStatus.PREPARED

    steps: tuple[IncidentReplayStep, ...] = ()
    if replay_prepared:
        steps = _build_replay_steps(
            intake_payload=intake_payload,
            intake_sha256=intake_sha256,
            artifact_manifest_sha256=artifact_manifest_sha256,
        )

    blockers = tuple(
        sorted(
            {
                *_intake_missing_fields(intake_payload),
                *_artifact_blockers(verifications),
                *ambiguous_roles,
            }
        )
    )
    step_payloads = [_step_payload(step) for step in steps]
    replay_plan_body: dict[str, object] = {
        "steps": step_payloads,
        "operator_authorization_required": True,
        "execution_started": False,
    }
    replay_plan_sha256 = (
        _calculate_sha256(
            replay_plan_body,
            name="incident replay plan",
        )
        if replay_prepared
        else None
    )

    incident = intake_payload["incident"]
    if not isinstance(incident, dict):
        raise HveeContractError("incident identity must be canonical")

    payload: dict[str, object] = {
        "schema_version": INCIDENT_REPLAY_PREPARATION_SCHEMA_VERSION,
        "type": "incident_replay_preparation",
        "evaluation_type": intake_payload["evaluation_type"],
        "incident": {
            "key": incident["key"],
            "version": incident["version"],
            "intake_sha256": intake_sha256,
            "context_sha256": intake_payload["context"]["sha256"],
        },
        "artifact_verification": {
            "status": (
                IncidentArtifactVerificationSummaryStatus.VERIFIED.value
                if artifacts_verified
                else IncidentArtifactVerificationSummaryStatus.FAILED.value
            ),
            **counts,
            "all_referenced_artifacts_verified": artifacts_verified,
            "runner_custody_status": _runner_custody_status(
                verifications
            ).value,
            "manifest_sha256": artifact_manifest_sha256,
            "receipts": verification_payloads,
        },
        "preparation": {
            "status": status.value,
            "replay_plan_prepared": replay_prepared,
            "blockers": list(blockers),
        },
        "replay_plan": {
            **replay_plan_body,
            "sha256": replay_plan_sha256,
        },
        "content_boundary": dict(_CONTENT_BOUNDARY),
        "evidence_boundary": _evidence_boundary(
            artifacts_verified=artifacts_verified,
            replay_prepared=replay_prepared,
        ),
    }
    canonical_payload = _canonical_json_value(
        payload,
        name="incident replay preparation",
    )
    if not isinstance(canonical_payload, dict):
        raise HveeContractError(
            "incident replay preparation must be a JSON object"
        )

    return IncidentReplayPreparationBundle(
        payload=canonical_payload,
        artifact_manifest_sha256=artifact_manifest_sha256,
        replay_plan_sha256=replay_plan_sha256,
        sha256=calculate_incident_replay_preparation_sha256(
            canonical_payload
        ),
    )


def calculate_incident_artifact_manifest_sha256(
    receipts: list[dict[str, object]],
) -> str:
    return _calculate_sha256(
        {"receipts": receipts},
        name="incident artifact custody manifest",
    )


def calculate_incident_replay_plan_sha256(
    replay_plan: dict[str, object],
) -> str:
    body = dict(replay_plan)
    body.pop("sha256", None)
    return _calculate_sha256(
        body,
        name="incident replay plan",
    )


def calculate_incident_replay_preparation_sha256(
    payload: dict[str, object],
) -> str:
    return _calculate_sha256(
        payload,
        name="incident replay preparation",
    )


def build_incident_replay_preparation_bundle(
    *,
    intake_payload: object,
    expected_intake_sha256: object,
    artifact_materials: list[IncidentArtifactMaterial]
    | tuple[IncidentArtifactMaterial, ...],
) -> IncidentReplayPreparationBundle:
    normalized_intake_sha256 = _require_sha256_hex(
        name="expected incident intake SHA-256",
        value=expected_intake_sha256,
    )
    if not isinstance(intake_payload, dict) or not (
        verify_incident_intake_bundle(
            payload=intake_payload,
            expected_sha256=normalized_intake_sha256,
        )
    ):
        raise HveeContractError(
            "incident intake evidence failed verification"
        )

    materials = _canonical_materials(artifact_materials)
    verifications = _build_artifact_verifications(
        intake_payload=intake_payload,
        materials=materials,
    )
    return _assemble_bundle(
        intake_payload=intake_payload,
        intake_sha256=normalized_intake_sha256,
        verifications=verifications,
    )


def _parse_verification(
    value: object,
) -> IncidentArtifactVerification:
    expected_keys = {
        "kind",
        "reference_sha256",
        "expected_byte_length",
        "media_type",
        "observed_sha256",
        "observed_byte_length",
        "status",
    }
    if not isinstance(value, dict) or set(value) != expected_keys:
        raise HveeContractError(
            "invalid incident artifact verification shape"
        )
    return IncidentArtifactVerification(
        kind=IncidentArtifactKind(value["kind"]),
        reference_sha256=value["reference_sha256"],
        expected_byte_length=value["expected_byte_length"],
        media_type=value["media_type"],
        observed_sha256=value["observed_sha256"],
        observed_byte_length=value["observed_byte_length"],
        status=IncidentArtifactVerificationStatus(value["status"]),
    )


def _receipts_cover_intake_references(
    *,
    intake_payload: dict[str, object],
    verifications: tuple[IncidentArtifactVerification, ...],
) -> bool:
    expected = {
        (str(value["kind"]), str(value["sha256"]))
        for value in _intake_artifact_references(intake_payload)
    }
    receipt_identities = [value.identity for value in verifications]
    if len(receipt_identities) != len(set(receipt_identities)):
        return False

    covered_expected = {
        value.identity
        for value in verifications
        if value.expected_byte_length is not None
    }
    if covered_expected != expected:
        return False

    return all(
        (
            value.identity in expected
            and value.status
            != IncidentArtifactVerificationStatus.UNEXPECTED
        )
        or (
            value.identity not in expected
            and value.status
            == IncidentArtifactVerificationStatus.UNEXPECTED
        )
        for value in verifications
    )


def verify_incident_replay_preparation_bundle(
    *,
    payload: object,
    expected_sha256: object,
    intake_payload: object,
    expected_intake_sha256: object,
) -> bool:
    try:
        normalized_expected_sha256 = _require_sha256_hex(
            name="expected replay preparation SHA-256",
            value=expected_sha256,
        )
        normalized_intake_sha256 = _require_sha256_hex(
            name="expected incident intake SHA-256",
            value=expected_intake_sha256,
        )
        if not isinstance(intake_payload, dict) or not (
            verify_incident_intake_bundle(
                payload=intake_payload,
                expected_sha256=normalized_intake_sha256,
            )
        ):
            return False
        if (
            not isinstance(payload, dict)
            or set(payload)
            != {
                "schema_version",
                "type",
                "evaluation_type",
                "incident",
                "artifact_verification",
                "preparation",
                "replay_plan",
                "content_boundary",
                "evidence_boundary",
            }
            or payload["schema_version"]
            != INCIDENT_REPLAY_PREPARATION_SCHEMA_VERSION
            or payload["type"] != "incident_replay_preparation"
            or payload["content_boundary"] != _CONTENT_BOUNDARY
        ):
            return False

        artifact_verification = payload["artifact_verification"]
        if (
            not isinstance(artifact_verification, dict)
            or set(artifact_verification)
            != {
                "status",
                "expected_count",
                "supplied_count",
                "verified_count",
                "missing_count",
                "mismatch_count",
                "unexpected_count",
                "all_referenced_artifacts_verified",
                "runner_custody_status",
                "manifest_sha256",
                "receipts",
            }
            or not isinstance(
                artifact_verification["receipts"],
                list,
            )
        ):
            return False

        verifications = tuple(
            _parse_verification(value)
            for value in artifact_verification["receipts"]
        )
        if tuple(
            sorted(verifications, key=lambda value: value.identity)
        ) != verifications:
            return False
        if not _receipts_cover_intake_references(
            intake_payload=intake_payload,
            verifications=verifications,
        ):
            return False

        rebuilt = _assemble_bundle(
            intake_payload=intake_payload,
            intake_sha256=normalized_intake_sha256,
            verifications=verifications,
        )
        return (
            payload == rebuilt.payload
            and normalized_expected_sha256 == rebuilt.sha256
            and calculate_incident_intake_sha256(intake_payload)
            == normalized_intake_sha256
        )
    except (
        HveeContractError,
        KeyError,
        TypeError,
        ValueError,
    ):
        return False

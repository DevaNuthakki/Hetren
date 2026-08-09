"""Private-evidence verification for Critical Number Fidelity v1.

The contracts in this module authenticate the already-sealed private-holdout
plan and blind-run receipt, maintain a caller-owned replay chain, and
independently recompute selectively disclosed commitments.  Private keys and
cryptographic implementations stay outside HVEE: callers sign and verify the
canonical bytes through explicit callbacks.

Successful verification is evidence-integrity evidence only.  It does not
issue certification, qualify the evaluator for production, change an official
release verdict, or enable Critical Number release enforcement.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.critical_number_assurance import (
    CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SHA256_V1,
    CRITICAL_NUMBER_ASSURANCE_PROFILE_KEY,
    CRITICAL_NUMBER_ASSURANCE_PROFILE_VERSION,
    ASRCriticalNumberAssuranceStatus,
    verify_critical_number_assurance_profile_v1,
)
from hvee.packs.asr.critical_number_fidelity import (
    CRITICAL_NUMBER_FIDELITY_EVALUATOR,
    EN_US_CRITICAL_NUMBER_PROFILE,
)
from hvee.packs.asr.critical_number_private_holdout import (
    ASRCriticalNumberPrivateHoldoutBlindRunBundle,
    ASRCriticalNumberPrivateHoldoutBlindRunDefinition,
    ASRCriticalNumberPrivateHoldoutCaseCommitment,
    ASRCriticalNumberPrivateHoldoutPlanBundle,
    ASRCriticalNumberPrivateHoldoutPlanDefinition,
    calculate_critical_number_private_commitment,
    calculate_critical_number_private_holdout_sha256,
    verify_critical_number_private_holdout_blind_run,
    verify_critical_number_private_holdout_plan,
)


CRITICAL_NUMBER_PRIVATE_EVIDENCE_ENVELOPE_SCHEMA_VERSION = 1
CRITICAL_NUMBER_PRIVATE_DISCLOSURE_SCHEMA_VERSION = 1
CRITICAL_NUMBER_PRIVATE_EVIDENCE_PROTOCOL_KEY = (
    "hetren.asr.critical-number-private-evidence-verification.en-us"
)
CRITICAL_NUMBER_PRIVATE_EVIDENCE_PROTOCOL_VERSION = "1.0.0"
CRITICAL_NUMBER_PRIVATE_EVIDENCE_SIGNATURE_ENCODING = "hex"
CRITICAL_NUMBER_PRIVATE_DISCLOSURE_SCHEME = (
    "sha256-canonical-json-private-disclosure-v1"
)

_IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_UTC_TIMESTAMP_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$"
)
_EXPECTED_EVALUATOR_IDENTITY = (
    "hetren.asr.critical-number-fidelity.en-us",
    "1.0.0",
    "asr",
)
_EXPECTED_PROFILE_IDENTITY = (
    "hetren.asr.critical-number-profile.en-us",
    "1.0.0",
    "en",
    "en-US",
)


class ASRCriticalNumberPrivateEvidenceArtifactType(StrEnum):
    PREREGISTERED_PLAN = "preregistered_private_holdout_plan"
    BLIND_RUN = "blind_private_holdout_run"
    DISCLOSURE_MANIFEST = "private_disclosure_manifest"


def _canonicalize_json_value(value: object, *, name: str) -> object:
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


def _canonical_json_bytes(value: object, *, name: str) -> bytes:
    canonical = _canonicalize_json_value(value, name=name)
    return json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _calculate_sha256(value: object, *, name: str) -> str:
    return hashlib.sha256(_canonical_json_bytes(value, name=name)).hexdigest()


def calculate_critical_number_private_evidence_sha256(payload: object) -> str:
    """Hash canonical private-evidence verification material."""

    return _calculate_sha256(
        payload,
        name="critical-number private-evidence payload",
    )


def calculate_critical_number_private_evaluator_output_commitment(
    *,
    payload: object,
    private_salt: str,
) -> str:
    """Commit an evaluator output using the holdout commitment domain."""

    return calculate_critical_number_private_commitment(
        payload=payload,
        private_salt=private_salt,
    )


def _require_sha256(*, name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise HveeContractError(f"{name} must be a lowercase SHA-256 hex digest")
    return value


def _require_identifier(*, name: str, value: object) -> str:
    if not isinstance(value, str) or not _IDENTIFIER_PATTERN.fullmatch(value):
        raise HveeContractError(f"{name} must be a canonical lowercase identifier")
    return value


def _require_version(*, name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > 100
    ):
        raise HveeContractError(f"{name} must be a non-empty, trimmed version")
    return value


def _require_positive_integer(*, name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise HveeContractError(f"{name} must be a positive integer")
    return value


def _require_utc_timestamp(*, name: str, value: object) -> str:
    if not isinstance(value, str) or not _UTC_TIMESTAMP_PATTERN.fullmatch(value):
        raise HveeContractError(f"{name} must be a canonical UTC timestamp")
    try:
        datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError as exc:
        raise HveeContractError(f"{name} must be a valid UTC timestamp") from exc
    return value


def _parse_utc_timestamp(value: str) -> datetime:
    _require_utc_timestamp(name="private-evidence timestamp", value=value)
    return datetime.fromisoformat(value.removesuffix("Z") + "+00:00")


def _require_private_salt(*, name: str, value: object) -> str:
    if not isinstance(value, str) or len(value.encode("utf-8")) < 32:
        raise HveeContractError(f"{name} must contain at least 32 UTF-8 bytes")
    return value


def _require_signature_hex(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 8192
        or len(value) % 2
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise HveeContractError(
            "private-evidence signature must be non-empty lowercase hex"
        )
    return value


def _require_exact_keys(
    *,
    name: str,
    value: object,
    keys: set[str],
) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise HveeContractError(f"{name} has an invalid schema")
    return value


def _require_v1_bindings() -> str:
    assurance = verify_critical_number_assurance_profile_v1()
    evaluator_identity = (
        CRITICAL_NUMBER_FIDELITY_EVALUATOR.key,
        CRITICAL_NUMBER_FIDELITY_EVALUATOR.version,
        CRITICAL_NUMBER_FIDELITY_EVALUATOR.evaluation_type,
    )
    if evaluator_identity != _EXPECTED_EVALUATOR_IDENTITY:
        raise HveeContractError("private-evidence evaluator identity changed")
    profile_identity = (
        EN_US_CRITICAL_NUMBER_PROFILE.key,
        EN_US_CRITICAL_NUMBER_PROFILE.version,
        EN_US_CRITICAL_NUMBER_PROFILE.language,
        EN_US_CRITICAL_NUMBER_PROFILE.locale,
    )
    if profile_identity != _EXPECTED_PROFILE_IDENTITY:
        raise HveeContractError("private-evidence profile identity changed")
    if assurance.sha256 != CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SHA256_V1:
        raise HveeContractError("private-evidence assurance binding changed")
    profile = assurance.payload.get("assurance_profile")
    if not isinstance(profile, dict) or profile.get("status") != (
        ASRCriticalNumberAssuranceStatus.EXPERIMENTAL.value
    ):
        raise HveeContractError(
            "private evidence requires the experimental assurance profile"
        )
    return assurance.sha256


def _bindings(assurance_sha256: str) -> dict[str, object]:
    return {
        "evaluator": {
            "key": CRITICAL_NUMBER_FIDELITY_EVALUATOR.key,
            "version": CRITICAL_NUMBER_FIDELITY_EVALUATOR.version,
            "evaluation_type": CRITICAL_NUMBER_FIDELITY_EVALUATOR.evaluation_type,
        },
        "evaluation_profile": {
            "key": EN_US_CRITICAL_NUMBER_PROFILE.key,
            "version": EN_US_CRITICAL_NUMBER_PROFILE.version,
            "language": EN_US_CRITICAL_NUMBER_PROFILE.language,
            "locale": EN_US_CRITICAL_NUMBER_PROFILE.locale,
        },
        "assurance_profile": {
            "key": CRITICAL_NUMBER_ASSURANCE_PROFILE_KEY,
            "version": CRITICAL_NUMBER_ASSURANCE_PROFILE_VERSION,
            "status": ASRCriticalNumberAssuranceStatus.EXPERIMENTAL.value,
            "sha256": assurance_sha256,
        },
    }


def _qualification_boundary() -> dict[str, object]:
    return {
        "evidence_integrity_verified": True,
        "evaluator_status": ASRCriticalNumberAssuranceStatus.EXPERIMENTAL.value,
        "certification_issued": False,
        "production_qualified": False,
        "release_enforcement_eligible": False,
        "official_release_verdict_modified": False,
    }


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberPrivateEvidenceSigner:
    key_id: str
    algorithm: str
    public_key_sha256: str

    def __post_init__(self) -> None:
        _require_identifier(name="private-evidence signer key id", value=self.key_id)
        _require_identifier(
            name="private-evidence signature algorithm",
            value=self.algorithm,
        )
        _require_sha256(
            name="private-evidence public-key fingerprint",
            value=self.public_key_sha256,
        )


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberPrivateEvidenceEnvelopeDefinition:
    chain_id: str
    envelope_id: str
    sequence_number: int
    issued_at_utc: str
    nonce_sha256: str
    previous_envelope_sha256: str | None
    signer: ASRCriticalNumberPrivateEvidenceSigner

    def __post_init__(self) -> None:
        _require_identifier(name="private-evidence chain id", value=self.chain_id)
        _require_identifier(
            name="private-evidence envelope id",
            value=self.envelope_id,
        )
        _require_positive_integer(
            name="private-evidence sequence number",
            value=self.sequence_number,
        )
        _require_utc_timestamp(
            name="private-evidence issued-at timestamp",
            value=self.issued_at_utc,
        )
        _require_sha256(
            name="private-evidence nonce",
            value=self.nonce_sha256,
        )
        if self.previous_envelope_sha256 is not None:
            _require_sha256(
                name="previous private-evidence envelope",
                value=self.previous_envelope_sha256,
            )
        if not isinstance(self.signer, ASRCriticalNumberPrivateEvidenceSigner):
            raise HveeContractError(
                "private-evidence envelope requires a signer identity"
            )


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberPrivateEvidenceEnvelopeBundle:
    payload: dict[str, object]
    sha256: str

    def __post_init__(self) -> None:
        canonical = _canonicalize_json_value(
            self.payload,
            name="critical-number private-evidence envelope",
        )
        if not isinstance(canonical, dict):
            raise HveeContractError("private-evidence envelope must be an object")
        _require_sha256(name="private-evidence envelope SHA-256", value=self.sha256)
        if calculate_critical_number_private_evidence_sha256(canonical) != self.sha256:
            raise HveeContractError(
                "private-evidence envelope SHA-256 does not match its payload"
            )


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberPrivateEvidenceReplayState:
    chain_id: str
    last_sequence_number: int = 0
    last_envelope_sha256: str | None = None
    last_issued_at_utc: str | None = None
    consumed_envelope_ids: tuple[str, ...] = ()
    consumed_nonce_sha256s: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_identifier(
            name="private-evidence replay chain id",
            value=self.chain_id,
        )
        if (
            isinstance(self.last_sequence_number, bool)
            or not isinstance(self.last_sequence_number, int)
            or self.last_sequence_number < 0
        ):
            raise HveeContractError(
                "private-evidence replay sequence must be a non-negative integer"
            )
        if self.last_sequence_number == 0:
            if (
                self.last_envelope_sha256 is not None
                or self.last_issued_at_utc is not None
            ):
                raise HveeContractError(
                    "empty replay state cannot contain a previous envelope"
                )
        else:
            _require_sha256(
                name="last private-evidence envelope",
                value=self.last_envelope_sha256,
            )
            _require_utc_timestamp(
                name="last private-evidence issued-at timestamp",
                value=self.last_issued_at_utc,
            )
        if (
            not isinstance(self.consumed_envelope_ids, tuple)
            or tuple(sorted(set(self.consumed_envelope_ids)))
            != self.consumed_envelope_ids
            or not all(
                isinstance(value, str) and _IDENTIFIER_PATTERN.fullmatch(value)
                for value in self.consumed_envelope_ids
            )
        ):
            raise HveeContractError(
                "consumed private-evidence envelope ids must be unique and sorted"
            )
        if (
            not isinstance(self.consumed_nonce_sha256s, tuple)
            or tuple(sorted(set(self.consumed_nonce_sha256s)))
            != self.consumed_nonce_sha256s
        ):
            raise HveeContractError(
                "consumed private-evidence nonces must be unique and sorted"
            )
        for value in self.consumed_nonce_sha256s:
            _require_sha256(name="consumed private-evidence nonce", value=value)
        if len(self.consumed_envelope_ids) != self.last_sequence_number or len(
            self.consumed_nonce_sha256s
        ) != self.last_sequence_number:
            raise HveeContractError(
                "private-evidence replay history must retain every sequence"
            )


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberPrivateEvidenceVerifiedEnvelope:
    envelope: ASRCriticalNumberPrivateEvidenceEnvelopeBundle
    artifact_type: ASRCriticalNumberPrivateEvidenceArtifactType
    artifact_sha256: str
    definition: ASRCriticalNumberPrivateEvidenceEnvelopeDefinition
    replay_state: ASRCriticalNumberPrivateEvidenceReplayState

    def __post_init__(self) -> None:
        if not isinstance(
            self.envelope,
            ASRCriticalNumberPrivateEvidenceEnvelopeBundle,
        ):
            raise HveeContractError("verified private evidence requires an envelope")
        if not isinstance(
            self.artifact_type,
            ASRCriticalNumberPrivateEvidenceArtifactType,
        ):
            raise HveeContractError("verified private evidence has invalid type")
        _require_sha256(
            name="verified private-evidence artifact",
            value=self.artifact_sha256,
        )
        if not isinstance(
            self.definition,
            ASRCriticalNumberPrivateEvidenceEnvelopeDefinition,
        ) or not isinstance(
            self.replay_state,
            ASRCriticalNumberPrivateEvidenceReplayState,
        ):
            raise HveeContractError(
                "verified private evidence requires definition and replay state"
            )


def _signer_snapshot(
    signer: ASRCriticalNumberPrivateEvidenceSigner,
) -> dict[str, object]:
    return {
        "key_id": signer.key_id,
        "algorithm": signer.algorithm,
        "public_key_sha256": signer.public_key_sha256,
    }


def _unsigned_envelope_payload(
    *,
    definition: ASRCriticalNumberPrivateEvidenceEnvelopeDefinition,
    artifact_type: ASRCriticalNumberPrivateEvidenceArtifactType,
    artifact_sha256: str,
) -> dict[str, object]:
    assurance_sha256 = _require_v1_bindings()
    return {
        "schema_version": CRITICAL_NUMBER_PRIVATE_EVIDENCE_ENVELOPE_SCHEMA_VERSION,
        "protocol": {
            "key": CRITICAL_NUMBER_PRIVATE_EVIDENCE_PROTOCOL_KEY,
            "version": CRITICAL_NUMBER_PRIVATE_EVIDENCE_PROTOCOL_VERSION,
            "artifact": "signed_evidence_envelope",
            "signature_encoding": (
                CRITICAL_NUMBER_PRIVATE_EVIDENCE_SIGNATURE_ENCODING
            ),
        },
        "chain": {
            "chain_id": definition.chain_id,
            "envelope_id": definition.envelope_id,
            "sequence_number": definition.sequence_number,
            "issued_at_utc": definition.issued_at_utc,
            "nonce_sha256": definition.nonce_sha256,
            "previous_envelope_sha256": definition.previous_envelope_sha256,
        },
        "artifact": {
            "type": artifact_type.value,
            "sha256": _require_sha256(
                name="private-evidence artifact",
                value=artifact_sha256,
            ),
        },
        "signer": _signer_snapshot(definition.signer),
        "bindings": _bindings(assurance_sha256),
        "qualification": _qualification_boundary(),
    }


def _build_envelope(
    *,
    definition: ASRCriticalNumberPrivateEvidenceEnvelopeDefinition,
    artifact_type: ASRCriticalNumberPrivateEvidenceArtifactType,
    artifact_sha256: str,
    sign: Callable[[bytes], bytes],
) -> ASRCriticalNumberPrivateEvidenceEnvelopeBundle:
    if not isinstance(
        definition,
        ASRCriticalNumberPrivateEvidenceEnvelopeDefinition,
    ):
        raise HveeContractError("private evidence requires an envelope definition")
    if not callable(sign):
        raise HveeContractError("private evidence requires a signing callback")
    unsigned = _unsigned_envelope_payload(
        definition=definition,
        artifact_type=artifact_type,
        artifact_sha256=artifact_sha256,
    )
    try:
        signature = sign(
            _canonical_json_bytes(unsigned, name="private-evidence signing payload")
        )
    except Exception as exc:
        raise HveeContractError("private-evidence signing callback failed") from exc
    if not isinstance(signature, bytes) or not signature or len(signature) > 4096:
        raise HveeContractError(
            "private-evidence signing callback must return 1-4096 bytes"
        )
    payload = {
        **unsigned,
        "signature": {
            "encoding": CRITICAL_NUMBER_PRIVATE_EVIDENCE_SIGNATURE_ENCODING,
            "value": signature.hex(),
        },
    }
    canonical = _canonicalize_json_value(
        payload,
        name="critical-number private-evidence envelope",
    )
    if not isinstance(canonical, dict):
        raise HveeContractError("private-evidence envelope must be an object")
    return ASRCriticalNumberPrivateEvidenceEnvelopeBundle(
        payload=canonical,
        sha256=calculate_critical_number_private_evidence_sha256(canonical),
    )


def _advance_replay_state(
    *,
    replay_state: ASRCriticalNumberPrivateEvidenceReplayState,
    envelope_sha256: str,
    definition: ASRCriticalNumberPrivateEvidenceEnvelopeDefinition,
) -> ASRCriticalNumberPrivateEvidenceReplayState:
    if replay_state.chain_id != definition.chain_id:
        raise HveeContractError("private-evidence replay chain does not match")
    if definition.sequence_number != replay_state.last_sequence_number + 1:
        raise HveeContractError("private-evidence sequence is missing or replayed")
    if definition.previous_envelope_sha256 != replay_state.last_envelope_sha256:
        raise HveeContractError("private-evidence envelope chain is broken")
    if definition.envelope_id in replay_state.consumed_envelope_ids:
        raise HveeContractError("private-evidence envelope id was already consumed")
    if definition.nonce_sha256 in replay_state.consumed_nonce_sha256s:
        raise HveeContractError("private-evidence nonce was already consumed")
    if (
        replay_state.last_issued_at_utc is not None
        and _parse_utc_timestamp(definition.issued_at_utc)
        <= _parse_utc_timestamp(replay_state.last_issued_at_utc)
    ):
        raise HveeContractError(
            "private-evidence issued-at timestamp must increase"
        )
    return ASRCriticalNumberPrivateEvidenceReplayState(
        chain_id=replay_state.chain_id,
        last_sequence_number=definition.sequence_number,
        last_envelope_sha256=envelope_sha256,
        last_issued_at_utc=definition.issued_at_utc,
        consumed_envelope_ids=tuple(
            sorted((*replay_state.consumed_envelope_ids, definition.envelope_id))
        ),
        consumed_nonce_sha256s=tuple(
            sorted((*replay_state.consumed_nonce_sha256s, definition.nonce_sha256))
        ),
    )


def _parse_and_verify_envelope(
    *,
    envelope: ASRCriticalNumberPrivateEvidenceEnvelopeBundle,
    expected_artifact_type: ASRCriticalNumberPrivateEvidenceArtifactType,
    expected_artifact_sha256: str,
    trusted_signer: ASRCriticalNumberPrivateEvidenceSigner,
    replay_state: ASRCriticalNumberPrivateEvidenceReplayState,
    verify_signature: Callable[[bytes, bytes], bool],
) -> ASRCriticalNumberPrivateEvidenceVerifiedEnvelope:
    if not isinstance(envelope, ASRCriticalNumberPrivateEvidenceEnvelopeBundle):
        raise HveeContractError("private evidence requires a sealed envelope")
    if calculate_critical_number_private_evidence_sha256(
        envelope.payload
    ) != envelope.sha256:
        raise HveeContractError("private-evidence envelope payload was mutated")
    if not isinstance(trusted_signer, ASRCriticalNumberPrivateEvidenceSigner):
        raise HveeContractError("private evidence requires a trusted signer")
    if not isinstance(replay_state, ASRCriticalNumberPrivateEvidenceReplayState):
        raise HveeContractError("private evidence requires replay state")
    if not callable(verify_signature):
        raise HveeContractError(
            "private evidence requires a signature-verification callback"
        )
    payload = _require_exact_keys(
        name="private-evidence envelope",
        value=_canonicalize_json_value(
            envelope.payload,
            name="supplied private-evidence envelope",
        ),
        keys={
            "schema_version",
            "protocol",
            "chain",
            "artifact",
            "signer",
            "bindings",
            "qualification",
            "signature",
        },
    )
    if payload["schema_version"] != (
        CRITICAL_NUMBER_PRIVATE_EVIDENCE_ENVELOPE_SCHEMA_VERSION
    ):
        raise HveeContractError("private-evidence envelope schema changed")
    expected_protocol = {
        "key": CRITICAL_NUMBER_PRIVATE_EVIDENCE_PROTOCOL_KEY,
        "version": CRITICAL_NUMBER_PRIVATE_EVIDENCE_PROTOCOL_VERSION,
        "artifact": "signed_evidence_envelope",
        "signature_encoding": CRITICAL_NUMBER_PRIVATE_EVIDENCE_SIGNATURE_ENCODING,
    }
    if payload["protocol"] != expected_protocol:
        raise HveeContractError("private-evidence envelope protocol changed")
    chain = _require_exact_keys(
        name="private-evidence envelope chain",
        value=payload["chain"],
        keys={
            "chain_id",
            "envelope_id",
            "sequence_number",
            "issued_at_utc",
            "nonce_sha256",
            "previous_envelope_sha256",
        },
    )
    signer_payload = _require_exact_keys(
        name="private-evidence signer",
        value=payload["signer"],
        keys={"key_id", "algorithm", "public_key_sha256"},
    )
    signer = ASRCriticalNumberPrivateEvidenceSigner(
        key_id=signer_payload["key_id"],
        algorithm=signer_payload["algorithm"],
        public_key_sha256=signer_payload["public_key_sha256"],
    )
    if signer != trusted_signer:
        raise HveeContractError("private-evidence signer is not trusted")
    previous = chain["previous_envelope_sha256"]
    if previous is not None:
        previous = _require_sha256(
            name="previous private-evidence envelope",
            value=previous,
        )
    definition = ASRCriticalNumberPrivateEvidenceEnvelopeDefinition(
        chain_id=chain["chain_id"],
        envelope_id=chain["envelope_id"],
        sequence_number=chain["sequence_number"],
        issued_at_utc=chain["issued_at_utc"],
        nonce_sha256=chain["nonce_sha256"],
        previous_envelope_sha256=previous,
        signer=signer,
    )
    artifact = _require_exact_keys(
        name="private-evidence envelope artifact",
        value=payload["artifact"],
        keys={"type", "sha256"},
    )
    if artifact["type"] != expected_artifact_type.value:
        raise HveeContractError("private-evidence artifact type does not match")
    artifact_sha256 = _require_sha256(
        name="private-evidence artifact",
        value=artifact["sha256"],
    )
    if artifact_sha256 != _require_sha256(
        name="expected private-evidence artifact",
        value=expected_artifact_sha256,
    ):
        raise HveeContractError("private-evidence artifact SHA-256 does not match")
    assurance_sha256 = _require_v1_bindings()
    if payload["bindings"] != _bindings(assurance_sha256):
        raise HveeContractError("private-evidence envelope bindings changed")
    if payload["qualification"] != _qualification_boundary():
        raise HveeContractError("private-evidence qualification boundary changed")
    signature_payload = _require_exact_keys(
        name="private-evidence signature",
        value=payload["signature"],
        keys={"encoding", "value"},
    )
    if signature_payload["encoding"] != (
        CRITICAL_NUMBER_PRIVATE_EVIDENCE_SIGNATURE_ENCODING
    ):
        raise HveeContractError("private-evidence signature encoding changed")
    signature_hex = _require_signature_hex(signature_payload["value"])
    unsigned = {key: value for key, value in payload.items() if key != "signature"}
    try:
        verified = verify_signature(
            _canonical_json_bytes(unsigned, name="private-evidence signing payload"),
            bytes.fromhex(signature_hex),
        )
    except Exception as exc:
        raise HveeContractError(
            "private-evidence signature-verification callback failed"
        ) from exc
    if verified is not True:
        raise HveeContractError("private-evidence signature is invalid")
    advanced = _advance_replay_state(
        replay_state=replay_state,
        envelope_sha256=envelope.sha256,
        definition=definition,
    )
    return ASRCriticalNumberPrivateEvidenceVerifiedEnvelope(
        envelope=envelope,
        artifact_type=expected_artifact_type,
        artifact_sha256=artifact_sha256,
        definition=definition,
        replay_state=advanced,
    )


def build_critical_number_private_holdout_plan_evidence_envelope(
    *,
    plan: ASRCriticalNumberPrivateHoldoutPlanBundle,
    plan_definition: ASRCriticalNumberPrivateHoldoutPlanDefinition,
    envelope_definition: ASRCriticalNumberPrivateEvidenceEnvelopeDefinition,
    sign: Callable[[bytes], bytes],
) -> ASRCriticalNumberPrivateEvidenceEnvelopeBundle:
    """Authenticate an exact preregistered plan as chain sequence one."""

    verified_plan = verify_critical_number_private_holdout_plan(
        payload=plan.payload,
        expected_sha256=plan.sha256,
        definition=plan_definition,
    )
    if envelope_definition.chain_id != plan_definition.run_id:
        raise HveeContractError("plan envelope chain must equal the holdout run id")
    if (
        envelope_definition.sequence_number != 1
        or envelope_definition.previous_envelope_sha256 is not None
    ):
        raise HveeContractError("plan envelope must start a new evidence chain")
    return _build_envelope(
        definition=envelope_definition,
        artifact_type=(
            ASRCriticalNumberPrivateEvidenceArtifactType.PREREGISTERED_PLAN
        ),
        artifact_sha256=verified_plan.sha256,
        sign=sign,
    )


def verify_critical_number_private_holdout_plan_evidence_envelope(
    *,
    plan: ASRCriticalNumberPrivateHoldoutPlanBundle,
    plan_definition: ASRCriticalNumberPrivateHoldoutPlanDefinition,
    envelope: ASRCriticalNumberPrivateEvidenceEnvelopeBundle,
    trusted_signer: ASRCriticalNumberPrivateEvidenceSigner,
    replay_state: ASRCriticalNumberPrivateEvidenceReplayState,
    verify_signature: Callable[[bytes, bytes], bool],
) -> ASRCriticalNumberPrivateEvidenceVerifiedEnvelope:
    """Verify the signed plan and consume chain sequence one."""

    verified_plan = verify_critical_number_private_holdout_plan(
        payload=plan.payload,
        expected_sha256=plan.sha256,
        definition=plan_definition,
    )
    verified = _parse_and_verify_envelope(
        envelope=envelope,
        expected_artifact_type=(
            ASRCriticalNumberPrivateEvidenceArtifactType.PREREGISTERED_PLAN
        ),
        expected_artifact_sha256=verified_plan.sha256,
        trusted_signer=trusted_signer,
        replay_state=replay_state,
        verify_signature=verify_signature,
    )
    if verified.definition.chain_id != plan_definition.run_id:
        raise HveeContractError("plan envelope chain does not match the run id")
    if (
        verified.definition.sequence_number != 1
        or verified.definition.previous_envelope_sha256 is not None
    ):
        raise HveeContractError("plan envelope is not chain sequence one")
    return verified


def build_critical_number_private_holdout_blind_run_evidence_envelope(
    *,
    plan: ASRCriticalNumberPrivateHoldoutPlanBundle,
    plan_definition: ASRCriticalNumberPrivateHoldoutPlanDefinition,
    run: ASRCriticalNumberPrivateHoldoutBlindRunBundle,
    run_definition: ASRCriticalNumberPrivateHoldoutBlindRunDefinition,
    plan_envelope: ASRCriticalNumberPrivateEvidenceEnvelopeBundle,
    envelope_definition: ASRCriticalNumberPrivateEvidenceEnvelopeDefinition,
    sign: Callable[[bytes], bytes],
) -> ASRCriticalNumberPrivateEvidenceEnvelopeBundle:
    """Authenticate the exact blind-run receipt after its plan envelope."""

    verified_run = verify_critical_number_private_holdout_blind_run(
        payload=run.payload,
        expected_sha256=run.sha256,
        plan=plan,
        plan_definition=plan_definition,
        run_definition=run_definition,
    )
    if envelope_definition.chain_id != plan_definition.run_id:
        raise HveeContractError("blind-run envelope chain must equal the run id")
    if (
        envelope_definition.sequence_number != 2
        or envelope_definition.previous_envelope_sha256 != plan_envelope.sha256
    ):
        raise HveeContractError(
            "blind-run envelope must follow the signed plan exactly"
        )
    return _build_envelope(
        definition=envelope_definition,
        artifact_type=ASRCriticalNumberPrivateEvidenceArtifactType.BLIND_RUN,
        artifact_sha256=verified_run.sha256,
        sign=sign,
    )


def verify_critical_number_private_holdout_blind_run_evidence_envelope(
    *,
    plan: ASRCriticalNumberPrivateHoldoutPlanBundle,
    plan_definition: ASRCriticalNumberPrivateHoldoutPlanDefinition,
    run: ASRCriticalNumberPrivateHoldoutBlindRunBundle,
    run_definition: ASRCriticalNumberPrivateHoldoutBlindRunDefinition,
    envelope: ASRCriticalNumberPrivateEvidenceEnvelopeBundle,
    verified_plan_envelope: ASRCriticalNumberPrivateEvidenceVerifiedEnvelope,
    trusted_signer: ASRCriticalNumberPrivateEvidenceSigner,
    verify_signature: Callable[[bytes, bytes], bool],
) -> ASRCriticalNumberPrivateEvidenceVerifiedEnvelope:
    """Verify the signed blind run and consume chain sequence two."""

    verified_run = verify_critical_number_private_holdout_blind_run(
        payload=run.payload,
        expected_sha256=run.sha256,
        plan=plan,
        plan_definition=plan_definition,
        run_definition=run_definition,
    )
    if (
        not isinstance(
            verified_plan_envelope,
            ASRCriticalNumberPrivateEvidenceVerifiedEnvelope,
        )
        or verified_plan_envelope.artifact_type
        != ASRCriticalNumberPrivateEvidenceArtifactType.PREREGISTERED_PLAN
        or verified_plan_envelope.artifact_sha256 != plan.sha256
    ):
        raise HveeContractError("blind-run verification requires its verified plan")
    verified = _parse_and_verify_envelope(
        envelope=envelope,
        expected_artifact_type=ASRCriticalNumberPrivateEvidenceArtifactType.BLIND_RUN,
        expected_artifact_sha256=verified_run.sha256,
        trusted_signer=trusted_signer,
        replay_state=verified_plan_envelope.replay_state,
        verify_signature=verify_signature,
    )
    if (
        verified.definition.chain_id != plan_definition.run_id
        or verified.definition.sequence_number != 2
        or verified.definition.previous_envelope_sha256
        != verified_plan_envelope.envelope.sha256
    ):
        raise HveeContractError("blind-run envelope does not follow its plan")
    return verified


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberPrivateEvidenceCaseDisclosure:
    case_token_payload: object
    case_token_private_salt: str
    case_payload: object
    case_payload_private_salt: str
    expected_result: object
    expected_result_private_salt: str
    provenance: object
    provenance_private_salt: str
    evaluator_output: object
    evaluator_output_private_salt: str

    def __post_init__(self) -> None:
        for name, value in (
            ("case-token", self.case_token_payload),
            ("case", self.case_payload),
            ("expected-result", self.expected_result),
            ("provenance", self.provenance),
            ("evaluator-output", self.evaluator_output),
        ):
            _canonicalize_json_value(
                value,
                name=f"private {name} disclosure",
            )
        for name, value in (
            ("case-token", self.case_token_private_salt),
            ("case", self.case_payload_private_salt),
            ("expected-result", self.expected_result_private_salt),
            ("provenance", self.provenance_private_salt),
            ("evaluator-output", self.evaluator_output_private_salt),
        ):
            _require_private_salt(name=f"private {name} disclosure salt", value=value)


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberPrivateEvidenceDisclosureDefinition:
    verification_id: str
    verification_version: str
    verifier_key_id: str
    verification_procedure_sha256: str
    verification_environment_sha256: str
    independence_attestation_sha256: str
    disclosures: tuple[ASRCriticalNumberPrivateEvidenceCaseDisclosure, ...]

    def __post_init__(self) -> None:
        _require_identifier(
            name="private disclosure verification id",
            value=self.verification_id,
        )
        _require_version(
            name="private disclosure verification version",
            value=self.verification_version,
        )
        _require_identifier(
            name="private disclosure verifier key id",
            value=self.verifier_key_id,
        )
        for name, value in (
            ("verification procedure", self.verification_procedure_sha256),
            ("verification environment", self.verification_environment_sha256),
            ("independence attestation", self.independence_attestation_sha256),
        ):
            _require_sha256(name=f"private {name} SHA-256", value=value)
        if (
            not isinstance(self.disclosures, tuple)
            or not self.disclosures
            or not all(
                isinstance(
                    disclosure,
                    ASRCriticalNumberPrivateEvidenceCaseDisclosure,
                )
                for disclosure in self.disclosures
            )
        ):
            raise HveeContractError("private evidence requires case disclosures")


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberPrivateEvidenceDisclosureManifestBundle:
    payload: dict[str, object]
    sha256: str

    def __post_init__(self) -> None:
        canonical = _canonicalize_json_value(
            self.payload,
            name="critical-number private disclosure manifest",
        )
        if not isinstance(canonical, dict):
            raise HveeContractError("private disclosure manifest must be an object")
        _require_sha256(
            name="private disclosure manifest SHA-256",
            value=self.sha256,
        )
        if calculate_critical_number_private_evidence_sha256(canonical) != self.sha256:
            raise HveeContractError(
                "private disclosure manifest SHA-256 does not match its payload"
            )


def _private_disclosure_content_address(
    disclosure: ASRCriticalNumberPrivateEvidenceCaseDisclosure,
) -> str:
    return calculate_critical_number_private_evidence_sha256(
        {
            "domain": CRITICAL_NUMBER_PRIVATE_EVIDENCE_PROTOCOL_KEY,
            "scheme": CRITICAL_NUMBER_PRIVATE_DISCLOSURE_SCHEME,
            "case_token_payload": disclosure.case_token_payload,
            "case_token_private_salt": disclosure.case_token_private_salt,
            "case_payload": disclosure.case_payload,
            "case_payload_private_salt": disclosure.case_payload_private_salt,
            "expected_result": disclosure.expected_result,
            "expected_result_private_salt": (
                disclosure.expected_result_private_salt
            ),
            "provenance": disclosure.provenance,
            "provenance_private_salt": disclosure.provenance_private_salt,
            "evaluator_output": disclosure.evaluator_output,
            "evaluator_output_private_salt": (
                disclosure.evaluator_output_private_salt
            ),
        }
    )


def _recompute_disclosure_entry(
    *,
    case: ASRCriticalNumberPrivateHoldoutCaseCommitment,
    execution: object,
    disclosure: ASRCriticalNumberPrivateEvidenceCaseDisclosure,
) -> dict[str, object]:
    case_token = calculate_critical_number_private_commitment(
        payload=disclosure.case_token_payload,
        private_salt=disclosure.case_token_private_salt,
    )
    if case_token != case.case_token:
        raise HveeContractError("private disclosure case token does not match")
    recomputed = {
        "case_payload": calculate_critical_number_private_commitment(
            payload=disclosure.case_payload,
            private_salt=disclosure.case_payload_private_salt,
        ),
        "expected_result": calculate_critical_number_private_commitment(
            payload=disclosure.expected_result,
            private_salt=disclosure.expected_result_private_salt,
        ),
        "provenance": calculate_critical_number_private_commitment(
            payload=disclosure.provenance,
            private_salt=disclosure.provenance_private_salt,
        ),
        "evaluator_output": (
            calculate_critical_number_private_evaluator_output_commitment(
                payload=disclosure.evaluator_output,
                private_salt=disclosure.evaluator_output_private_salt,
            )
        ),
    }
    expected = {
        "case_payload": case.case_payload_sha256,
        "expected_result": case.expected_result_sha256,
        "provenance": case.provenance_sha256,
        "evaluator_output": execution.evaluator_output_sha256,
    }
    for name in sorted(expected):
        if recomputed[name] != expected[name]:
            raise HveeContractError(
                f"private disclosure {name.replace('_', ' ')} does not match"
            )
    return {
        "case_token": case.case_token,
        "slice_keys": list(case.slice_keys),
        "execution_status": execution.status.value,
        "disclosure_sha256": _private_disclosure_content_address(disclosure),
        "commitments_recomputed": True,
    }


def build_critical_number_private_evidence_disclosure_manifest(
    *,
    plan: ASRCriticalNumberPrivateHoldoutPlanBundle,
    plan_definition: ASRCriticalNumberPrivateHoldoutPlanDefinition,
    run: ASRCriticalNumberPrivateHoldoutBlindRunBundle,
    run_definition: ASRCriticalNumberPrivateHoldoutBlindRunDefinition,
    verified_plan_envelope: ASRCriticalNumberPrivateEvidenceVerifiedEnvelope,
    verified_run_envelope: ASRCriticalNumberPrivateEvidenceVerifiedEnvelope,
    definition: ASRCriticalNumberPrivateEvidenceDisclosureDefinition,
) -> ASRCriticalNumberPrivateEvidenceDisclosureManifestBundle:
    """Recompute all revealed commitments and emit only content addresses."""

    verified_plan = verify_critical_number_private_holdout_plan(
        payload=plan.payload,
        expected_sha256=plan.sha256,
        definition=plan_definition,
    )
    verified_run = verify_critical_number_private_holdout_blind_run(
        payload=run.payload,
        expected_sha256=run.sha256,
        plan=plan,
        plan_definition=plan_definition,
        run_definition=run_definition,
    )
    if not isinstance(
        definition,
        ASRCriticalNumberPrivateEvidenceDisclosureDefinition,
    ):
        raise HveeContractError("private evidence requires a disclosure definition")
    if (
        verified_plan_envelope.artifact_type
        != ASRCriticalNumberPrivateEvidenceArtifactType.PREREGISTERED_PLAN
        or verified_plan_envelope.artifact_sha256 != verified_plan.sha256
        or verified_run_envelope.artifact_type
        != ASRCriticalNumberPrivateEvidenceArtifactType.BLIND_RUN
        or verified_run_envelope.artifact_sha256 != verified_run.sha256
        or verified_run_envelope.definition.previous_envelope_sha256
        != verified_plan_envelope.envelope.sha256
        or verified_run_envelope.replay_state.last_envelope_sha256
        != verified_run_envelope.envelope.sha256
    ):
        raise HveeContractError(
            "private disclosure requires the verified plan and blind-run chain"
        )
    if len(definition.disclosures) != len(plan_definition.cases):
        raise HveeContractError(
            "private disclosure must retain every preregistered case"
        )
    entries = tuple(
        _recompute_disclosure_entry(
            case=case,
            execution=execution,
            disclosure=disclosure,
        )
        for case, execution, disclosure in zip(
            plan_definition.cases,
            run_definition.executions,
            definition.disclosures,
            strict=True,
        )
    )
    disclosure_root = calculate_critical_number_private_evidence_sha256(
        {"scheme": CRITICAL_NUMBER_PRIVATE_DISCLOSURE_SCHEME, "cases": entries}
    )
    assurance_sha256 = _require_v1_bindings()
    payload = {
        "schema_version": CRITICAL_NUMBER_PRIVATE_DISCLOSURE_SCHEMA_VERSION,
        "protocol": {
            "key": CRITICAL_NUMBER_PRIVATE_EVIDENCE_PROTOCOL_KEY,
            "version": CRITICAL_NUMBER_PRIVATE_EVIDENCE_PROTOCOL_VERSION,
            "artifact": (
                ASRCriticalNumberPrivateEvidenceArtifactType.DISCLOSURE_MANIFEST.value
            ),
            "disclosure_scheme": CRITICAL_NUMBER_PRIVATE_DISCLOSURE_SCHEME,
        },
        "bindings": _bindings(assurance_sha256),
        "sealed_evidence": {
            "plan_sha256": verified_plan.sha256,
            "plan_envelope_sha256": verified_plan_envelope.envelope.sha256,
            "blind_run_sha256": verified_run.sha256,
            "blind_run_envelope_sha256": verified_run_envelope.envelope.sha256,
            "run_id": plan_definition.run_id,
        },
        "independent_verification": {
            "verification_id": definition.verification_id,
            "verification_version": definition.verification_version,
            "verifier_key_id": definition.verifier_key_id,
            "verification_procedure_sha256": (
                definition.verification_procedure_sha256
            ),
            "verification_environment_sha256": (
                definition.verification_environment_sha256
            ),
            "independence_attestation_sha256": (
                definition.independence_attestation_sha256
            ),
            "selected_case_count": len(plan_definition.cases),
            "verified_case_count": len(entries),
            "all_selected_cases_retained": True,
            "all_commitments_recomputed": True,
            "disclosure_root_sha256": disclosure_root,
            "cases": list(entries),
        },
        "confidentiality": {
            "private_case_content_in_artifact": False,
            "expected_results_in_artifact": False,
            "private_provenance_in_artifact": False,
            "evaluator_outputs_in_artifact": False,
            "private_salts_in_artifact": False,
            "content_addresses_only": True,
        },
        "qualification": _qualification_boundary(),
    }
    canonical = _canonicalize_json_value(
        payload,
        name="critical-number private disclosure manifest",
    )
    if not isinstance(canonical, dict):
        raise HveeContractError("private disclosure manifest must be an object")
    return ASRCriticalNumberPrivateEvidenceDisclosureManifestBundle(
        payload=canonical,
        sha256=calculate_critical_number_private_evidence_sha256(canonical),
    )


def verify_critical_number_private_evidence_disclosure_manifest(
    *,
    payload: object,
    expected_sha256: object,
    plan: ASRCriticalNumberPrivateHoldoutPlanBundle,
    plan_definition: ASRCriticalNumberPrivateHoldoutPlanDefinition,
    run: ASRCriticalNumberPrivateHoldoutBlindRunBundle,
    run_definition: ASRCriticalNumberPrivateHoldoutBlindRunDefinition,
    verified_plan_envelope: ASRCriticalNumberPrivateEvidenceVerifiedEnvelope,
    verified_run_envelope: ASRCriticalNumberPrivateEvidenceVerifiedEnvelope,
    definition: ASRCriticalNumberPrivateEvidenceDisclosureDefinition,
) -> ASRCriticalNumberPrivateEvidenceDisclosureManifestBundle:
    """Rebuild a disclosure manifest and require exact evidence equality."""

    expected_digest = _require_sha256(
        name="expected private disclosure manifest",
        value=expected_sha256,
    )
    supplied = _canonicalize_json_value(
        payload,
        name="supplied private disclosure manifest",
    )
    if not isinstance(supplied, dict):
        raise HveeContractError("supplied private disclosure must be an object")
    if calculate_critical_number_private_evidence_sha256(supplied) != expected_digest:
        raise HveeContractError(
            "supplied private disclosure does not match expected SHA-256"
        )
    rebuilt = build_critical_number_private_evidence_disclosure_manifest(
        plan=plan,
        plan_definition=plan_definition,
        run=run,
        run_definition=run_definition,
        verified_plan_envelope=verified_plan_envelope,
        verified_run_envelope=verified_run_envelope,
        definition=definition,
    )
    if supplied != rebuilt.payload or expected_digest != rebuilt.sha256:
        raise HveeContractError(
            "private disclosure does not match independently recomputed evidence"
        )
    return rebuilt


def build_critical_number_private_disclosure_evidence_envelope(
    *,
    manifest: ASRCriticalNumberPrivateEvidenceDisclosureManifestBundle,
    verified_run_envelope: ASRCriticalNumberPrivateEvidenceVerifiedEnvelope,
    envelope_definition: ASRCriticalNumberPrivateEvidenceEnvelopeDefinition,
    sign: Callable[[bytes], bytes],
) -> ASRCriticalNumberPrivateEvidenceEnvelopeBundle:
    """Authenticate the disclosure manifest as chain sequence three."""

    if not isinstance(
        manifest,
        ASRCriticalNumberPrivateEvidenceDisclosureManifestBundle,
    ):
        raise HveeContractError("private evidence requires a disclosure manifest")
    if (
        verified_run_envelope.artifact_type
        != ASRCriticalNumberPrivateEvidenceArtifactType.BLIND_RUN
        or envelope_definition.chain_id
        != verified_run_envelope.definition.chain_id
        or envelope_definition.sequence_number != 3
        or envelope_definition.previous_envelope_sha256
        != verified_run_envelope.envelope.sha256
    ):
        raise HveeContractError(
            "disclosure envelope must follow the verified blind run exactly"
        )
    return _build_envelope(
        definition=envelope_definition,
        artifact_type=(
            ASRCriticalNumberPrivateEvidenceArtifactType.DISCLOSURE_MANIFEST
        ),
        artifact_sha256=manifest.sha256,
        sign=sign,
    )


def verify_critical_number_private_disclosure_evidence_envelope(
    *,
    manifest: ASRCriticalNumberPrivateEvidenceDisclosureManifestBundle,
    envelope: ASRCriticalNumberPrivateEvidenceEnvelopeBundle,
    verified_run_envelope: ASRCriticalNumberPrivateEvidenceVerifiedEnvelope,
    trusted_signer: ASRCriticalNumberPrivateEvidenceSigner,
    verify_signature: Callable[[bytes, bytes], bool],
) -> ASRCriticalNumberPrivateEvidenceVerifiedEnvelope:
    """Verify the signed disclosure and consume chain sequence three."""

    if not isinstance(
        manifest,
        ASRCriticalNumberPrivateEvidenceDisclosureManifestBundle,
    ):
        raise HveeContractError("private evidence requires a disclosure manifest")
    if (
        verified_run_envelope.artifact_type
        != ASRCriticalNumberPrivateEvidenceArtifactType.BLIND_RUN
    ):
        raise HveeContractError("disclosure verification requires a blind run")
    verified = _parse_and_verify_envelope(
        envelope=envelope,
        expected_artifact_type=(
            ASRCriticalNumberPrivateEvidenceArtifactType.DISCLOSURE_MANIFEST
        ),
        expected_artifact_sha256=manifest.sha256,
        trusted_signer=trusted_signer,
        replay_state=verified_run_envelope.replay_state,
        verify_signature=verify_signature,
    )
    if (
        verified.definition.chain_id
        != verified_run_envelope.definition.chain_id
        or verified.definition.sequence_number != 3
        or verified.definition.previous_envelope_sha256
        != verified_run_envelope.envelope.sha256
    ):
        raise HveeContractError(
            "disclosure envelope does not follow the verified blind run"
        )
    return verified

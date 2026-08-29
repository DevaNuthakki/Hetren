"""Materialization commitments for the fresh Hetren ASR Run-04 corpus.

This module binds the frozen Run-04 allocation slots to opaque source,
speaker, rights, media, transcript, and measurement identities.  Raw audio,
raw transcripts, source paths, and personal speaker attributes are excluded.

A complete commitment can establish that the corpus contract is satisfied.
It still does not authorize ASR execution, prove legal rights, qualify an
evaluator, open the holdout, certify safety, or approve a release.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.run04_corpus_plan import (
    ASR_RUN04_CORPUS_PLAN_SHA256,
    ASRRun04Partition,
    ASRRun04ValidityClass,
    build_asr_run04_corpus_plan_v1,
)


ASR_RUN04_CORPUS_COMMITMENT_SCHEMA_VERSION = 1
ASR_RUN04_CORPUS_COMMITMENT_KEY = (
    "hetren.asr.run-04.corpus-commitment"
)
ASR_RUN04_CORPUS_COMMITMENT_VERSION = "1.0.0"


class ASRRun04RightsReviewStatus(StrEnum):
    """Recorded review state; approval is evidence, not legal advice."""

    APPROVED_FOR_DECLARED_USE = "approved_for_declared_use"
    PENDING_REVIEW = "pending_review"
    REJECTED = "rejected"


class ASRRun04AccentEvidenceKind(StrEnum):
    """Permitted origin of an optional accent-coverage label."""

    SOURCE_DECLARED = "source_declared"
    SPEAKER_DECLARED = "speaker_declared"
    NOT_PROVIDED = "not_provided"


class ASRRun04LabelCommitmentScheme(StrEnum):
    """Allowed transcript-label commitment construction."""

    HMAC_SHA256 = "hmac_sha256"


_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def _require_key(name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or _KEY_PATTERN.fullmatch(value) is None
    ):
        raise HveeContractError(
            f"{name} must be a canonical lowercase identifier"
        )
    return value


def _require_sha256(name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise HveeContractError(
            f"{name} must be a lowercase SHA-256 digest"
        )
    return value


def _optional_sha256(name: str, value: object) -> str | None:
    if value is None:
        return None
    return _require_sha256(name, value)


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise HveeContractError(
            "Run-04 corpus commitment must be canonical JSON"
        ) from error


def calculate_asr_run04_corpus_commitment_sha256(
    payload: object,
) -> str:
    """Return the canonical materialization-commitment identity."""

    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


@dataclass(frozen=True, slots=True)
class ASRRun04SpeakerBinding:
    """Opaque binding between one plan slot and one source speaker."""

    speaker_slot_key: str
    source_speaker_identity_sha256: str
    speaker_provenance_sha256: str
    rights_record_sha256: str
    rights_review_status: ASRRun04RightsReviewStatus
    accent_coverage_key: str | None
    accent_evidence_kind: ASRRun04AccentEvidenceKind
    demographic_record_sha256: str | None = None
    demographic_attributes_inferred: bool = False

    def __post_init__(self) -> None:
        _require_key("Run-04 speaker slot key", self.speaker_slot_key)
        _require_sha256(
            "Run-04 source speaker identity",
            self.source_speaker_identity_sha256,
        )
        _require_sha256(
            "Run-04 speaker provenance",
            self.speaker_provenance_sha256,
        )
        _require_sha256(
            "Run-04 speaker rights record",
            self.rights_record_sha256,
        )
        if not isinstance(
            self.rights_review_status,
            ASRRun04RightsReviewStatus,
        ):
            raise HveeContractError(
                "Run-04 rights review status must be canonical"
            )
        if not isinstance(
            self.accent_evidence_kind,
            ASRRun04AccentEvidenceKind,
        ):
            raise HveeContractError(
                "Run-04 accent evidence kind must be canonical"
            )
        if self.accent_evidence_kind == (
            ASRRun04AccentEvidenceKind.NOT_PROVIDED
        ):
            if self.accent_coverage_key is not None:
                raise HveeContractError(
                    "unprovided accent evidence cannot contain a label"
                )
        else:
            _require_key(
                "Run-04 accent coverage key",
                self.accent_coverage_key,
            )
        _optional_sha256(
            "Run-04 demographic record",
            self.demographic_record_sha256,
        )
        if self.demographic_attributes_inferred is not False:
            raise HveeContractError(
                "Run-04 speaker attributes cannot be inferred"
            )


@dataclass(frozen=True, slots=True)
class ASRRun04CaseBinding:
    """Opaque materialization record for one frozen case slot."""

    case_slot_key: str
    source_record_sha256: str
    rights_record_sha256: str
    rights_review_status: ASRRun04RightsReviewStatus
    scenario_metadata_sha256: str
    media_sha256: str
    media_byte_length: int
    media_duration_ms: int
    media_container_key: str
    reference_label_commitment_sha256: str | None
    reference_label_commitment_scheme: (
        ASRRun04LabelCommitmentScheme | None
    )
    acoustic_measurement_sha256: str | None
    invalid_disposition_sha256: str | None

    def __post_init__(self) -> None:
        _require_key("Run-04 case slot key", self.case_slot_key)
        for name, value in (
            ("source record", self.source_record_sha256),
            ("rights record", self.rights_record_sha256),
            ("scenario metadata", self.scenario_metadata_sha256),
            ("media", self.media_sha256),
        ):
            _require_sha256(f"Run-04 case {name}", value)
        if not isinstance(
            self.rights_review_status,
            ASRRun04RightsReviewStatus,
        ):
            raise HveeContractError(
                "Run-04 case rights review status must be canonical"
            )
        if (
            isinstance(self.media_byte_length, bool)
            or not isinstance(self.media_byte_length, int)
            or self.media_byte_length < 0
        ):
            raise HveeContractError(
                "Run-04 media byte length must be a non-negative integer"
            )
        if (
            isinstance(self.media_duration_ms, bool)
            or not isinstance(self.media_duration_ms, int)
            or self.media_duration_ms < 0
        ):
            raise HveeContractError(
                "Run-04 media duration must be a non-negative integer"
            )
        _require_key(
            "Run-04 media container key",
            self.media_container_key,
        )
        _optional_sha256(
            "Run-04 reference label commitment",
            self.reference_label_commitment_sha256,
        )
        if (
            self.reference_label_commitment_scheme is not None
            and not isinstance(
                self.reference_label_commitment_scheme,
                ASRRun04LabelCommitmentScheme,
            )
        ):
            raise HveeContractError(
                "Run-04 label commitment scheme must be canonical"
            )
        _optional_sha256(
            "Run-04 acoustic measurement",
            self.acoustic_measurement_sha256,
        )
        _optional_sha256(
            "Run-04 invalid disposition",
            self.invalid_disposition_sha256,
        )


@dataclass(frozen=True, slots=True)
class ASRRun04CorpusCommitmentBundle:
    """Canonical identity-only materialization commitment."""

    payload: dict[str, object]
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.payload, dict):
            raise HveeContractError(
                "Run-04 corpus commitment payload must be a JSON object"
            )
        _require_sha256("Run-04 corpus commitment SHA-256", self.sha256)


def _speaker_payload(
    *,
    binding: ASRRun04SpeakerBinding,
    partition: str,
    source_class: str,
) -> dict[str, object]:
    return {
        "speaker_slot_key": binding.speaker_slot_key,
        "partition": partition,
        "source_class": source_class,
        "source_speaker_identity_sha256": (
            binding.source_speaker_identity_sha256
        ),
        "speaker_provenance_sha256": binding.speaker_provenance_sha256,
        "rights_record_sha256": binding.rights_record_sha256,
        "rights_review_status": binding.rights_review_status.value,
        "accent_coverage_key": binding.accent_coverage_key,
        "accent_evidence_kind": binding.accent_evidence_kind.value,
        "demographic_record_sha256": (
            binding.demographic_record_sha256
        ),
        "demographic_attributes_inferred": False,
    }


def _case_payload(
    *,
    binding: ASRRun04CaseBinding,
    slot: dict[str, object],
) -> dict[str, object]:
    return {
        "case_slot_key": binding.case_slot_key,
        "ordinal": slot["ordinal"],
        "partition": slot["partition"],
        "validity_class": slot["validity_class"],
        "semantic_family": slot["semantic_family"],
        "acoustic_family": slot["acoustic_family"],
        "invalid_family": slot["invalid_family"],
        "speaker_slot_key": slot["speaker_slot_key"],
        "source_class": slot["source_class"],
        "source_record_sha256": binding.source_record_sha256,
        "rights_record_sha256": binding.rights_record_sha256,
        "rights_review_status": binding.rights_review_status.value,
        "scenario_metadata_sha256": binding.scenario_metadata_sha256,
        "media_sha256": binding.media_sha256,
        "media_byte_length": binding.media_byte_length,
        "media_duration_ms": binding.media_duration_ms,
        "media_container_key": binding.media_container_key,
        "reference_label_commitment_sha256": (
            binding.reference_label_commitment_sha256
        ),
        "reference_label_commitment_scheme": (
            binding.reference_label_commitment_scheme.value
            if binding.reference_label_commitment_scheme is not None
            else None
        ),
        "acoustic_measurement_sha256": (
            binding.acoustic_measurement_sha256
        ),
        "invalid_disposition_sha256": (
            binding.invalid_disposition_sha256
        ),
        "raw_audio_included": False,
        "raw_transcript_included": False,
        "model_output_included": False,
        "outcome_observed": False,
    }


def _validate_bindings(
    *,
    plan: dict[str, object],
    speaker_bindings: tuple[ASRRun04SpeakerBinding, ...],
    case_bindings: tuple[ASRRun04CaseBinding, ...],
) -> tuple[
    dict[str, dict[str, object]],
    dict[str, dict[str, object]],
]:
    plan_speakers = {
        str(item["key"]): item
        for item in plan["speaker_slots"]
        if isinstance(item, dict)
    }
    plan_cases = {
        str(item["key"]): item
        for item in plan["case_slots"]
        if isinstance(item, dict)
    }

    speaker_by_slot = {
        binding.speaker_slot_key: binding
        for binding in speaker_bindings
    }
    if len(speaker_by_slot) != len(speaker_bindings):
        raise HveeContractError(
            "Run-04 speaker bindings contain duplicate slot keys"
        )
    if set(speaker_by_slot) != set(plan_speakers):
        raise HveeContractError(
            "Run-04 must bind every frozen speaker slot exactly once"
        )
    if len({
        binding.source_speaker_identity_sha256
        for binding in speaker_bindings
    }) != len(speaker_bindings):
        raise HveeContractError(
            "Run-04 source speakers cannot overlap across slots"
        )

    case_by_slot = {
        binding.case_slot_key: binding for binding in case_bindings
    }
    if len(case_by_slot) != len(case_bindings):
        raise HveeContractError(
            "Run-04 case bindings contain duplicate slot keys"
        )
    if set(case_by_slot) != set(plan_cases):
        raise HveeContractError(
            "Run-04 must bind every frozen case slot exactly once"
        )
    if len({binding.media_sha256 for binding in case_bindings}) != len(
        case_bindings
    ):
        raise HveeContractError(
            "Run-04 materialized media identities must be unique"
        )

    for case_key, binding in case_by_slot.items():
        slot = plan_cases[case_key]
        if slot["validity_class"] == ASRRun04ValidityClass.VALID.value:
            if binding.media_byte_length <= 0:
                raise HveeContractError(
                    "valid Run-04 media must contain bytes"
                )
            if binding.media_duration_ms <= 0:
                raise HveeContractError(
                    "valid Run-04 media must have positive duration"
                )
            if binding.reference_label_commitment_sha256 is None:
                raise HveeContractError(
                    "valid Run-04 cases require transcript commitments"
                )
            if binding.reference_label_commitment_scheme != (
                ASRRun04LabelCommitmentScheme.HMAC_SHA256
            ):
                raise HveeContractError(
                    "valid Run-04 transcript labels require HMAC-SHA256"
                )
            if binding.acoustic_measurement_sha256 is None:
                raise HveeContractError(
                    "valid Run-04 cases require acoustic measurements"
                )
            if binding.invalid_disposition_sha256 is not None:
                raise HveeContractError(
                    "valid Run-04 cases cannot bind invalid dispositions"
                )
            speaker_key = str(slot["speaker_slot_key"])
            speaker = speaker_by_slot[speaker_key]
            if binding.rights_record_sha256 != (
                speaker.rights_record_sha256
            ):
                raise HveeContractError(
                    "Run-04 case rights must match its speaker record"
                )
            if binding.rights_review_status != (
                speaker.rights_review_status
            ):
                raise HveeContractError(
                    "Run-04 case rights status must match its speaker record"
                )
        else:
            if binding.reference_label_commitment_sha256 is not None:
                raise HveeContractError(
                    "invalid Run-04 cases cannot bind transcript labels"
                )
            if binding.reference_label_commitment_scheme is not None:
                raise HveeContractError(
                    "invalid Run-04 cases cannot bind label schemes"
                )
            if binding.acoustic_measurement_sha256 is not None:
                raise HveeContractError(
                    "invalid Run-04 cases cannot claim acoustic truth"
                )
            if binding.invalid_disposition_sha256 is None:
                raise HveeContractError(
                    "invalid Run-04 cases require disposition commitments"
                )
            if slot["invalid_family"] == "zero-byte-input":
                if binding.media_byte_length != 0:
                    raise HveeContractError(
                        "the zero-byte Run-04 slot must contain zero bytes"
                    )
                if binding.media_duration_ms != 0:
                    raise HveeContractError(
                        "the zero-byte Run-04 slot must have zero duration"
                    )

    return plan_speakers, plan_cases


def build_asr_run04_corpus_commitment_v1(
    *,
    speaker_bindings: tuple[ASRRun04SpeakerBinding, ...],
    case_bindings: tuple[ASRRun04CaseBinding, ...],
    accent_coverage_report_sha256: str,
    demographic_balance_report_sha256: str,
    rights_review_report_sha256: str,
    corpus_limitations_sha256: str,
) -> ASRRun04CorpusCommitmentBundle:
    """Bind all frozen slots to private identities without opening labels."""

    for name, value in (
        ("accent coverage report", accent_coverage_report_sha256),
        ("demographic balance report", demographic_balance_report_sha256),
        ("rights review report", rights_review_report_sha256),
        ("corpus limitations", corpus_limitations_sha256),
    ):
        _require_sha256(f"Run-04 {name}", value)

    if not isinstance(speaker_bindings, tuple):
        raise HveeContractError(
            "Run-04 speaker bindings must be an ordered tuple"
        )
    if not isinstance(case_bindings, tuple):
        raise HveeContractError(
            "Run-04 case bindings must be an ordered tuple"
        )

    plan_bundle = build_asr_run04_corpus_plan_v1()
    plan = plan_bundle.payload
    plan_speakers, plan_cases = _validate_bindings(
        plan=plan,
        speaker_bindings=speaker_bindings,
        case_bindings=case_bindings,
    )
    speaker_by_slot = {
        binding.speaker_slot_key: binding
        for binding in speaker_bindings
    }
    case_by_slot = {
        binding.case_slot_key: binding for binding in case_bindings
    }

    ordered_speakers = tuple(
        speaker_by_slot[str(item["key"])]
        for item in plan["speaker_slots"]
        if isinstance(item, dict)
    )
    ordered_cases = tuple(
        case_by_slot[str(item["key"])]
        for item in plan["case_slots"]
        if isinstance(item, dict)
    )

    partition_commitments: dict[str, str] = {}
    for partition in ASRRun04Partition:
        partition_payload = [
            _case_payload(
                binding=binding,
                slot=plan_cases[binding.case_slot_key],
            )
            for binding in ordered_cases
            if plan_cases[binding.case_slot_key]["partition"]
            == partition.value
        ]
        partition_commitments[partition.value] = hashlib.sha256(
            _canonical_json_bytes(partition_payload)
        ).hexdigest()

    rights_approved_count = sum(
        binding.rights_review_status
        == ASRRun04RightsReviewStatus.APPROVED_FOR_DECLARED_USE
        for binding in ordered_speakers
    )
    rights_rejected_count = sum(
        binding.rights_review_status
        == ASRRun04RightsReviewStatus.REJECTED
        for binding in ordered_speakers
    )
    rights_pending_count = (
        len(ordered_speakers)
        - rights_approved_count
        - rights_rejected_count
    )
    case_rights_approved_count = sum(
        binding.rights_review_status
        == ASRRun04RightsReviewStatus.APPROVED_FOR_DECLARED_USE
        for binding in ordered_cases
    )
    case_rights_rejected_count = sum(
        binding.rights_review_status
        == ASRRun04RightsReviewStatus.REJECTED
        for binding in ordered_cases
    )
    case_rights_pending_count = (
        len(ordered_cases)
        - case_rights_approved_count
        - case_rights_rejected_count
    )
    execution_ready = (
        rights_approved_count == len(ordered_speakers)
        and rights_rejected_count == 0
        and rights_pending_count == 0
        and case_rights_approved_count == len(ordered_cases)
        and case_rights_rejected_count == 0
        and case_rights_pending_count == 0
    )

    payload: dict[str, object] = {
        "schema_version": ASR_RUN04_CORPUS_COMMITMENT_SCHEMA_VERSION,
        "artifact": {
            "key": ASR_RUN04_CORPUS_COMMITMENT_KEY,
            "version": ASR_RUN04_CORPUS_COMMITMENT_VERSION,
            "type": "asr_run04_private_corpus_commitment",
        },
        "corpus_plan_sha256": ASR_RUN04_CORPUS_PLAN_SHA256,
        "speaker_bindings": [
            _speaker_payload(
                binding=binding,
                partition=str(
                    plan_speakers[binding.speaker_slot_key]["partition"]
                ),
                source_class=str(
                    plan_speakers[binding.speaker_slot_key]["source_class"]
                ),
            )
            for binding in ordered_speakers
        ],
        "case_bindings": [
            _case_payload(
                binding=binding,
                slot=plan_cases[binding.case_slot_key],
            )
            for binding in ordered_cases
        ],
        "partition_commitments": partition_commitments,
        "coverage_reports": {
            "accent_coverage_report_sha256": (
                accent_coverage_report_sha256
            ),
            "demographic_balance_report_sha256": (
                demographic_balance_report_sha256
            ),
            "rights_review_report_sha256": rights_review_report_sha256,
            "corpus_limitations_sha256": corpus_limitations_sha256,
            "demographic_attributes_inferred": False,
        },
        "materialization_report": {
            "speaker_binding_count": len(ordered_speakers),
            "case_binding_count": len(ordered_cases),
            "valid_case_count": sum(
                plan_cases[binding.case_slot_key]["validity_class"]
                == ASRRun04ValidityClass.VALID.value
                for binding in ordered_cases
            ),
            "invalid_case_count": sum(
                plan_cases[binding.case_slot_key]["validity_class"]
                == ASRRun04ValidityClass.INVALID.value
                for binding in ordered_cases
            ),
            "rights_approved_count": rights_approved_count,
            "rights_pending_count": rights_pending_count,
            "rights_rejected_count": rights_rejected_count,
            "case_rights_approved_count": case_rights_approved_count,
            "case_rights_pending_count": case_rights_pending_count,
            "case_rights_rejected_count": case_rights_rejected_count,
            "source_speaker_overlap_count": 0,
        },
        "content_boundary": {
            "raw_audio_included": False,
            "raw_transcript_included": False,
            "source_path_included": False,
            "personal_speaker_identifier_included": False,
            "speaker_attributes_inferred": False,
            "model_output_included": False,
            "evaluator_result_included": False,
            "opaque_commitments_only": True,
        },
        "evidence_boundary": {
            "fresh_corpus_materialized": True,
            "all_frozen_slots_bound": True,
            "rights_evidence_review_complete": execution_ready,
            "corpus_contract_satisfied": execution_ready,
            "ready_for_firewall_sealing": execution_ready,
            "holdout_membership_opened": False,
            "asr_execution_performed": False,
            "run04_execution_authorized": False,
            "run04_completed": False,
            "legal_advice_issued": False,
            "production_qualified": False,
        },
    }
    return ASRRun04CorpusCommitmentBundle(
        payload=payload,
        sha256=calculate_asr_run04_corpus_commitment_sha256(payload),
    )


def verify_asr_run04_corpus_commitment_v1(
    *,
    payload: object,
    expected_sha256: str,
    speaker_bindings: tuple[ASRRun04SpeakerBinding, ...],
    case_bindings: tuple[ASRRun04CaseBinding, ...],
    accent_coverage_report_sha256: str,
    demographic_balance_report_sha256: str,
    rights_review_report_sha256: str,
    corpus_limitations_sha256: str,
) -> bool:
    """Rebuild and verify a complete private corpus commitment."""

    try:
        expected = _require_sha256(
            "expected Run-04 corpus commitment SHA-256",
            expected_sha256,
        )
        if not isinstance(payload, dict):
            return False
        rebuilt = build_asr_run04_corpus_commitment_v1(
            speaker_bindings=speaker_bindings,
            case_bindings=case_bindings,
            accent_coverage_report_sha256=(
                accent_coverage_report_sha256
            ),
            demographic_balance_report_sha256=(
                demographic_balance_report_sha256
            ),
            rights_review_report_sha256=rights_review_report_sha256,
            corpus_limitations_sha256=corpus_limitations_sha256,
        )
        return (
            calculate_asr_run04_corpus_commitment_sha256(payload)
            == expected
            and payload == rebuilt.payload
            and expected == rebuilt.sha256
        )
    except (HveeContractError, TypeError, ValueError):
        return False


__all__ = [
    "ASR_RUN04_CORPUS_COMMITMENT_KEY",
    "ASR_RUN04_CORPUS_COMMITMENT_SCHEMA_VERSION",
    "ASR_RUN04_CORPUS_COMMITMENT_VERSION",
    "ASRRun04AccentEvidenceKind",
    "ASRRun04CaseBinding",
    "ASRRun04CorpusCommitmentBundle",
    "ASRRun04RightsReviewStatus",
    "ASRRun04LabelCommitmentScheme",
    "ASRRun04SpeakerBinding",
    "build_asr_run04_corpus_commitment_v1",
    "calculate_asr_run04_corpus_commitment_sha256",
    "verify_asr_run04_corpus_commitment_v1",
]

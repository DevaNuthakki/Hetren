"""Frozen allocation plan for the fresh Hetren ASR Run-04 corpus.

The plan fixes case slots, quotas, partitions, source classes, and speaker
separation before source audio is selected or any ASR outcome exists.  It is
not a corpus manifest: it contains no audio, transcript, source identity,
rights approval, evaluator result, or model output.

Building this artifact performs no transcription and grants no execution,
qualification, certification, production, or release authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.run04_protocol import (
    ASR_RUN04_ACOUSTIC_FAMILY_MINIMUMS,
    ASR_RUN04_INVALID_CASE_FAMILIES,
    ASR_RUN04_PARTITIONS,
    ASR_RUN04_SEMANTIC_FAMILY_QUOTAS,
    build_asr_run04_protocol_v1,
)


ASR_RUN04_CORPUS_PLAN_SCHEMA_VERSION = 1
ASR_RUN04_CORPUS_PLAN_KEY = "hetren.asr.run-04.corpus-plan"
ASR_RUN04_CORPUS_PLAN_VERSION = "1.0.0"
ASR_RUN04_CORPUS_PLAN_PREREQUISITE_COMMIT = (
    "f04efd1b07f6d09cc384f768a673c318cf705859"
)
ASR_RUN04_CORPUS_PLAN_SHA256 = (
    "99db3b3bd6f2e7ecf7bfcaab15c9505a"
    "dabb0c906c145bed96df1bd520c49860"
)


class ASRRun04Partition(StrEnum):
    """Run-04 evidence partitions."""

    DEVELOPMENT = "development"
    VALIDATION = "validation"
    SEALED_HOLDOUT = "sealed_holdout"


class ASRRun04ValidityClass(StrEnum):
    """Whether a slot requires valid or deliberately invalid media."""

    VALID = "valid"
    INVALID = "invalid"


class ASRRun04SourceClass(StrEnum):
    """Predeclared source class without asserting a real source identity."""

    HUMAN = "human"
    SYNTHETIC = "synthetic"
    INVALID_MEDIA = "invalid_media"


_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")


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
            "Run-04 corpus plan content must be canonical JSON"
        ) from error


def calculate_asr_run04_corpus_plan_sha256(payload: object) -> str:
    """Return the canonical allocation-plan identity."""

    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


@dataclass(frozen=True, slots=True)
class ASRRun04SpeakerSlot:
    """One partition-exclusive source-speaker slot."""

    key: str
    partition: ASRRun04Partition
    source_class: ASRRun04SourceClass

    def __post_init__(self) -> None:
        _require_key("Run-04 speaker slot key", self.key)
        if not isinstance(self.partition, ASRRun04Partition):
            raise HveeContractError(
                "Run-04 speaker partition must be canonical"
            )
        if self.source_class not in {
            ASRRun04SourceClass.HUMAN,
            ASRRun04SourceClass.SYNTHETIC,
        }:
            raise HveeContractError(
                "Run-04 speaker slots must be human or synthetic"
            )


@dataclass(frozen=True, slots=True)
class ASRRun04CaseSlot:
    """One outcome-free case slot in canonical execution order."""

    ordinal: int
    key: str
    partition: ASRRun04Partition
    validity_class: ASRRun04ValidityClass
    semantic_family: str | None
    acoustic_family: str | None
    invalid_family: str | None
    speaker_slot_key: str | None
    source_class: ASRRun04SourceClass

    def __post_init__(self) -> None:
        if (
            isinstance(self.ordinal, bool)
            or not isinstance(self.ordinal, int)
            or self.ordinal <= 0
        ):
            raise HveeContractError(
                "Run-04 case ordinal must be a positive integer"
            )
        _require_key("Run-04 case slot key", self.key)
        if not isinstance(self.partition, ASRRun04Partition):
            raise HveeContractError(
                "Run-04 case partition must be canonical"
            )
        if not isinstance(self.validity_class, ASRRun04ValidityClass):
            raise HveeContractError(
                "Run-04 validity class must be canonical"
            )
        if not isinstance(self.source_class, ASRRun04SourceClass):
            raise HveeContractError(
                "Run-04 source class must be canonical"
            )

        if self.validity_class == ASRRun04ValidityClass.VALID:
            if self.semantic_family not in (
                ASR_RUN04_SEMANTIC_FAMILY_QUOTAS
            ):
                raise HveeContractError(
                    "valid Run-04 slots require a registered semantic family"
                )
            if self.acoustic_family not in (
                ASR_RUN04_ACOUSTIC_FAMILY_MINIMUMS
            ):
                raise HveeContractError(
                    "valid Run-04 slots require a registered acoustic family"
                )
            if self.invalid_family is not None:
                raise HveeContractError(
                    "valid Run-04 slots cannot declare an invalid family"
                )
            if self.speaker_slot_key is None:
                raise HveeContractError(
                    "valid Run-04 slots require a speaker slot"
                )
            _require_key(
                "Run-04 case speaker slot key",
                self.speaker_slot_key,
            )
            if self.source_class not in {
                ASRRun04SourceClass.HUMAN,
                ASRRun04SourceClass.SYNTHETIC,
            }:
                raise HveeContractError(
                    "valid Run-04 slots require human or synthetic speech"
                )
            return

        if self.semantic_family is not None:
            raise HveeContractError(
                "invalid Run-04 slots cannot declare a semantic family"
            )
        if self.acoustic_family is not None:
            raise HveeContractError(
                "invalid Run-04 slots cannot declare an acoustic family"
            )
        if self.invalid_family not in ASR_RUN04_INVALID_CASE_FAMILIES:
            raise HveeContractError(
                "invalid Run-04 slots require a registered invalid family"
            )
        if self.speaker_slot_key is not None:
            raise HveeContractError(
                "invalid Run-04 slots cannot claim a speaker identity"
            )
        if self.source_class != ASRRun04SourceClass.INVALID_MEDIA:
            raise HveeContractError(
                "invalid Run-04 slots require the invalid-media source class"
            )


@dataclass(frozen=True, slots=True)
class ASRRun04CorpusPlanBundle:
    """Canonical, outcome-free Run-04 corpus allocation plan."""

    payload: dict[str, object]
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.payload, dict):
            raise HveeContractError(
                "Run-04 corpus plan payload must be a JSON object"
            )
        _require_sha256("Run-04 corpus plan SHA-256", self.sha256)


def _speaker_slots() -> tuple[ASRRun04SpeakerSlot, ...]:
    definitions = (
        (ASRRun04Partition.DEVELOPMENT, "dev", 4, 4),
        (ASRRun04Partition.VALIDATION, "val", 2, 2),
        (ASRRun04Partition.SEALED_HOLDOUT, "holdout", 2, 2),
    )
    slots: list[ASRRun04SpeakerSlot] = []
    for partition, prefix, human_count, synthetic_count in definitions:
        for index in range(1, human_count + 1):
            slots.append(
                ASRRun04SpeakerSlot(
                    key=f"run04.speaker.{prefix}.human.{index:02d}",
                    partition=partition,
                    source_class=ASRRun04SourceClass.HUMAN,
                )
            )
        for index in range(1, synthetic_count + 1):
            slots.append(
                ASRRun04SpeakerSlot(
                    key=f"run04.speaker.{prefix}.synthetic.{index:02d}",
                    partition=partition,
                    source_class=ASRRun04SourceClass.SYNTHETIC,
                )
            )
    return tuple(slots)


def _case_slots(
    speaker_slots: tuple[ASRRun04SpeakerSlot, ...],
) -> tuple[ASRRun04CaseSlot, ...]:
    semantic_families = tuple(
        sorted(ASR_RUN04_SEMANTIC_FAMILY_QUOTAS)
    )
    acoustic_families = tuple(
        sorted(ASR_RUN04_ACOUSTIC_FAMILY_MINIMUMS)
    )
    partition_definitions = (
        (ASRRun04Partition.DEVELOPMENT, "dev", 4),
        (ASRRun04Partition.VALIDATION, "val", 2),
        (ASRRun04Partition.SEALED_HOLDOUT, "holdout", 2),
    )
    invalid_allocations = {
        ASRRun04Partition.DEVELOPMENT: (
            ASR_RUN04_INVALID_CASE_FAMILIES[:4]
        ),
        ASRRun04Partition.VALIDATION: (
            ASR_RUN04_INVALID_CASE_FAMILIES[4:6]
        ),
        ASRRun04Partition.SEALED_HOLDOUT: (
            ASR_RUN04_INVALID_CASE_FAMILIES[6:]
        ),
    }

    cases: list[ASRRun04CaseSlot] = []
    ordinal = 1
    for partition, prefix, human_count in partition_definitions:
        partition_speakers = tuple(
            slot for slot in speaker_slots if slot.partition == partition
        )
        if len(partition_speakers) not in {4, 8}:
            raise HveeContractError(
                "Run-04 partition speaker allocation changed"
            )

        for semantic_index, semantic_family in enumerate(
            semantic_families
        ):
            for variant_index, speaker_slot in enumerate(
                partition_speakers
            ):
                acoustic_family = acoustic_families[
                    (semantic_index + variant_index)
                    % len(acoustic_families)
                ]
                cases.append(
                    ASRRun04CaseSlot(
                        ordinal=ordinal,
                        key=(
                            f"run04.{prefix}.valid."
                            f"{semantic_index + 1:02d}."
                            f"{variant_index + 1:02d}"
                        ),
                        partition=partition,
                        validity_class=ASRRun04ValidityClass.VALID,
                        semantic_family=semantic_family,
                        acoustic_family=acoustic_family,
                        invalid_family=None,
                        speaker_slot_key=speaker_slot.key,
                        source_class=(
                            ASRRun04SourceClass.HUMAN
                            if variant_index < human_count
                            else ASRRun04SourceClass.SYNTHETIC
                        ),
                    )
                )
                ordinal += 1

        for invalid_index, invalid_family in enumerate(
            invalid_allocations[partition],
            start=1,
        ):
            cases.append(
                ASRRun04CaseSlot(
                    ordinal=ordinal,
                    key=(
                        f"run04.{prefix}.invalid."
                        f"{invalid_index:02d}"
                    ),
                    partition=partition,
                    validity_class=ASRRun04ValidityClass.INVALID,
                    semantic_family=None,
                    acoustic_family=None,
                    invalid_family=invalid_family,
                    speaker_slot_key=None,
                    source_class=ASRRun04SourceClass.INVALID_MEDIA,
                )
            )
            ordinal += 1

    return tuple(cases)


def _validate_plan(
    *,
    speaker_slots: tuple[ASRRun04SpeakerSlot, ...],
    case_slots: tuple[ASRRun04CaseSlot, ...],
) -> None:
    if _COMMIT_PATTERN.fullmatch(
        ASR_RUN04_CORPUS_PLAN_PREREQUISITE_COMMIT
    ) is None:
        raise HveeContractError(
            "Run-04 corpus-plan prerequisite must be a full Git commit"
        )
    if len(speaker_slots) != 16:
        raise HveeContractError(
            "Run-04 corpus plan requires exactly 16 speaker slots"
        )
    if len({slot.key for slot in speaker_slots}) != len(speaker_slots):
        raise HveeContractError(
            "Run-04 speaker slot keys must be unique"
        )
    if sum(
        slot.source_class == ASRRun04SourceClass.HUMAN
        for slot in speaker_slots
    ) != 8:
        raise HveeContractError(
            "Run-04 corpus plan requires exactly eight human speaker slots"
        )
    if len(case_slots) != 136:
        raise HveeContractError(
            "Run-04 corpus plan requires exactly 136 case slots"
        )
    if tuple(slot.ordinal for slot in case_slots) != tuple(
        range(1, 137)
    ):
        raise HveeContractError(
            "Run-04 case ordinals must be continuous and ordered"
        )
    if len({slot.key for slot in case_slots}) != len(case_slots):
        raise HveeContractError(
            "Run-04 case slot keys must be unique"
        )

    expected_partition_counts = {
        item["key"]: (
            item["valid_case_count"],
            item["invalid_case_count"],
        )
        for item in ASR_RUN04_PARTITIONS
    }
    for partition in ASRRun04Partition:
        partition_cases = tuple(
            slot for slot in case_slots if slot.partition == partition
        )
        valid_count = sum(
            slot.validity_class == ASRRun04ValidityClass.VALID
            for slot in partition_cases
        )
        invalid_count = len(partition_cases) - valid_count
        if (valid_count, invalid_count) != expected_partition_counts[
            partition.value
        ]:
            raise HveeContractError(
                "Run-04 partition case allocation changed"
            )

    for family, expected_count in (
        ASR_RUN04_SEMANTIC_FAMILY_QUOTAS.items()
    ):
        if sum(
            slot.semantic_family == family for slot in case_slots
        ) != expected_count:
            raise HveeContractError(
                "Run-04 semantic-family allocation changed"
            )
    for family, minimum in ASR_RUN04_ACOUSTIC_FAMILY_MINIMUMS.items():
        if sum(
            slot.acoustic_family == family for slot in case_slots
        ) < minimum:
            raise HveeContractError(
                "Run-04 acoustic-family allocation changed"
            )
    if tuple(
        sorted(
            slot.invalid_family
            for slot in case_slots
            if slot.invalid_family is not None
        )
    ) != tuple(sorted(ASR_RUN04_INVALID_CASE_FAMILIES)):
        raise HveeContractError(
            "Run-04 invalid-family allocation changed"
        )

    speaker_by_key = {slot.key: slot for slot in speaker_slots}
    for case_slot in case_slots:
        if case_slot.speaker_slot_key is None:
            continue
        speaker_slot = speaker_by_key.get(case_slot.speaker_slot_key)
        if speaker_slot is None:
            raise HveeContractError(
                "Run-04 case references an unknown speaker slot"
            )
        if speaker_slot.partition != case_slot.partition:
            raise HveeContractError(
                "Run-04 speaker slots cannot cross partitions"
            )
        if speaker_slot.source_class != case_slot.source_class:
            raise HveeContractError(
                "Run-04 case source class differs from its speaker slot"
            )


def _speaker_payload(slot: ASRRun04SpeakerSlot) -> dict[str, object]:
    return {
        "key": slot.key,
        "partition": slot.partition.value,
        "source_class": slot.source_class.value,
        "actual_source_identity_bound": False,
        "rights_record_bound": False,
        "speaker_attributes_inferred": False,
    }


def _case_payload(slot: ASRRun04CaseSlot) -> dict[str, object]:
    return {
        "ordinal": slot.ordinal,
        "key": slot.key,
        "partition": slot.partition.value,
        "validity_class": slot.validity_class.value,
        "semantic_family": slot.semantic_family,
        "acoustic_family": slot.acoustic_family,
        "invalid_family": slot.invalid_family,
        "speaker_slot_key": slot.speaker_slot_key,
        "source_class": slot.source_class.value,
        "source_record_bound": False,
        "media_identity_bound": False,
        "reference_label_bound": False,
        "outcome_observed": False,
    }


def build_asr_run04_corpus_plan_v1() -> ASRRun04CorpusPlanBundle:
    """Build the exact fresh-corpus allocation without materializing it."""

    protocol = build_asr_run04_protocol_v1()
    speaker_slots = _speaker_slots()
    case_slots = _case_slots(speaker_slots)
    _validate_plan(
        speaker_slots=speaker_slots,
        case_slots=case_slots,
    )

    payload: dict[str, object] = {
        "schema_version": ASR_RUN04_CORPUS_PLAN_SCHEMA_VERSION,
        "artifact": {
            "key": ASR_RUN04_CORPUS_PLAN_KEY,
            "version": ASR_RUN04_CORPUS_PLAN_VERSION,
            "type": "asr_run04_outcome_free_corpus_allocation",
        },
        "prerequisite_commit": (
            ASR_RUN04_CORPUS_PLAN_PREREQUISITE_COMMIT
        ),
        "protocol_sha256": protocol.sha256,
        "allocation_strategy": {
            "semantic_family_order": list(
                sorted(ASR_RUN04_SEMANTIC_FAMILY_QUOTAS)
            ),
            "acoustic_family_order": list(
                sorted(ASR_RUN04_ACOUSTIC_FAMILY_MINIMUMS)
            ),
            "balanced_latin_rotation": True,
            "each_speaker_slot_valid_case_count": 8,
            "source_selected_after_plan_freeze": True,
        },
        "speaker_slots": [
            _speaker_payload(slot) for slot in speaker_slots
        ],
        "case_slots": [_case_payload(slot) for slot in case_slots],
        "allocation_report": {
            "total_case_count": len(case_slots),
            "valid_case_count": sum(
                slot.validity_class == ASRRun04ValidityClass.VALID
                for slot in case_slots
            ),
            "invalid_case_count": sum(
                slot.validity_class == ASRRun04ValidityClass.INVALID
                for slot in case_slots
            ),
            "distinct_speaker_slot_count": len(speaker_slots),
            "human_speaker_slot_count": sum(
                slot.source_class == ASRRun04SourceClass.HUMAN
                for slot in speaker_slots
            ),
            "synthetic_speaker_slot_count": sum(
                slot.source_class == ASRRun04SourceClass.SYNTHETIC
                for slot in speaker_slots
            ),
            "speaker_overlap_across_partitions": False,
        },
        "visibility_boundary": {
            "raw_audio_included": False,
            "raw_transcript_included": False,
            "source_identity_included": False,
            "rights_claim_included": False,
            "demographic_attributes_inferred": False,
            "model_output_included": False,
            "evaluator_result_included": False,
            "failure_label_included": False,
        },
        "evidence_boundary": {
            "allocation_plan_frozen": True,
            "fresh_corpus_materialized": False,
            "source_and_rights_records_bound": False,
            "partition_commitments_bound": False,
            "holdout_membership_sealed": False,
            "asr_execution_performed": False,
            "run04_execution_authorized": False,
            "run04_completed": False,
            "production_qualified": False,
        },
    }
    sha256 = calculate_asr_run04_corpus_plan_sha256(payload)
    if sha256 != ASR_RUN04_CORPUS_PLAN_SHA256:
        raise HveeContractError(
            "Run-04 corpus allocation plan identity changed"
        )
    return ASRRun04CorpusPlanBundle(
        payload=payload,
        sha256=sha256,
    )


def verify_asr_run04_corpus_plan_v1(
    *,
    payload: object,
    expected_sha256: str,
) -> bool:
    """Verify exact allocation-plan reconstruction and identity."""

    try:
        expected = _require_sha256(
            "expected Run-04 corpus plan SHA-256",
            expected_sha256,
        )
        if not isinstance(payload, dict):
            return False
        rebuilt = build_asr_run04_corpus_plan_v1()
        return (
            calculate_asr_run04_corpus_plan_sha256(payload) == expected
            and payload == rebuilt.payload
            and expected == rebuilt.sha256
        )
    except (HveeContractError, TypeError, ValueError):
        return False


__all__ = [
    "ASR_RUN04_CORPUS_PLAN_KEY",
    "ASR_RUN04_CORPUS_PLAN_PREREQUISITE_COMMIT",
    "ASR_RUN04_CORPUS_PLAN_SCHEMA_VERSION",
    "ASR_RUN04_CORPUS_PLAN_SHA256",
    "ASR_RUN04_CORPUS_PLAN_VERSION",
    "ASRRun04CaseSlot",
    "ASRRun04CorpusPlanBundle",
    "ASRRun04Partition",
    "ASRRun04SourceClass",
    "ASRRun04SpeakerSlot",
    "ASRRun04ValidityClass",
    "build_asr_run04_corpus_plan_v1",
    "calculate_asr_run04_corpus_plan_sha256",
    "verify_asr_run04_corpus_plan_v1",
]

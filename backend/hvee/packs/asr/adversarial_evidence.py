"""Adversarial ASR evidence contracts.

This module describes caller-declared speech/channel stress conditions for
development evaluation. It does not infer acoustic causes from transcripts,
infer speaker attributes, alter semantic evaluator methodology, issue
certification, qualify an evaluator for production, or modify release
authority.

The contract exists so later real-audio experiments can bind an audio asset
and its declared stress conditions to stable, deterministic evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum

from hvee.core.contracts import HveeContractError


ASR_ADVERSARIAL_EVIDENCE_SCHEMA_VERSION = 1
ASR_ADVERSARIAL_EVIDENCE_KEY = (
    "hetren.asr.adversarial-evidence.en-us"
)
ASR_ADVERSARIAL_EVIDENCE_VERSION = "1.0.0"


_IDENTIFIER_PATTERN = re.compile(
    r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$"
)


class ASRAdversarialChannel(StrEnum):
    """Declared recording/channel family."""

    CLEAN = "clean"
    TELEPHONY = "telephony"


class ASRAdversarialCodec(StrEnum):
    """Declared audio encoding family."""

    LINEAR_PCM = "linear_pcm"
    MULAW = "mulaw"
    ALAW = "alaw"
    LOSSY_COMPRESSED = "lossy_compressed"


class ASRAdversarialNoiseCondition(StrEnum):
    """Declared background-noise stress."""

    NONE = "none"
    MODERATE = "moderate"
    SEVERE_USABLE = "severe_usable"


class ASRAdversarialSpeakingRate(StrEnum):
    """Declared speaker-rate bucket."""

    SLOW = "slow"
    NORMAL = "normal"
    FAST = "fast"


class ASRAdversarialOverlapCondition(StrEnum):
    """Declared multi-speaker overlap condition."""

    NONE = "none"
    NON_CRITICAL = "non_critical"
    CRITICAL = "critical"


class ASRAdversarialDurationBucket(StrEnum):
    """Declared recording-duration bucket."""

    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


class ASRAdversarialLongContextPosition(StrEnum):
    """Location of critical material inside long-form context."""

    NONE = "none"
    EARLY = "early"
    MIDDLE = "middle"
    LATE = "late"


def _require_identifier(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or not _IDENTIFIER_PATTERN.fullmatch(value)
    ):
        raise HveeContractError(
            f"{name} must be a canonical lowercase identifier"
        )

    return value


def _require_non_empty_text(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or value != value.strip()
    ):
        raise HveeContractError(
            f"{name} must be non-empty trimmed text"
        )

    return value


def _require_sha256(
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
            f"{name} must be a lowercase SHA-256 digest"
        )

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


def _require_tags(
    tags: object,
) -> tuple[str, ...]:
    if (
        not isinstance(tags, tuple)
        or not tags
    ):
        raise HveeContractError(
            "adversarial case requires tags"
        )

    for tag in tags:
        _require_identifier(
            name="adversarial case tag",
            value=tag,
        )

    if tuple(sorted(set(tags))) != tags:
        raise HveeContractError(
            "adversarial case tags must be unique and sorted"
        )

    return tags


def _canonical_json(
    value: object,
) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise HveeContractError(
            "adversarial evidence must be deterministic JSON"
        ) from exc


def calculate_asr_adversarial_evidence_sha256(
    payload: object,
) -> str:
    """Hash canonical adversarial-evidence material."""

    return hashlib.sha256(
        _canonical_json(payload).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class ASRAdversarialCondition:
    """Caller-declared speech and channel stress metadata."""

    channel: ASRAdversarialChannel
    codec: ASRAdversarialCodec
    sample_rate_hz: int
    microphone_class: str
    noise: ASRAdversarialNoiseCondition
    speaking_rate: ASRAdversarialSpeakingRate
    speech_variety_key: str
    overlap: ASRAdversarialOverlapCondition
    duration: ASRAdversarialDurationBucket

    def __post_init__(self) -> None:
        for name, value, expected_type in (
            (
                "channel",
                self.channel,
                ASRAdversarialChannel,
            ),
            (
                "codec",
                self.codec,
                ASRAdversarialCodec,
            ),
            (
                "noise",
                self.noise,
                ASRAdversarialNoiseCondition,
            ),
            (
                "speaking rate",
                self.speaking_rate,
                ASRAdversarialSpeakingRate,
            ),
            (
                "overlap",
                self.overlap,
                ASRAdversarialOverlapCondition,
            ),
            (
                "duration",
                self.duration,
                ASRAdversarialDurationBucket,
            ),
        ):
            if not isinstance(value, expected_type):
                raise HveeContractError(
                    f"adversarial {name} requires "
                    "a versioned enum value"
                )

        if (
            isinstance(self.sample_rate_hz, bool)
            or not isinstance(
                self.sample_rate_hz,
                int,
            )
            or not 8_000
            <= self.sample_rate_hz
            <= 192_000
        ):
            raise HveeContractError(
                "adversarial sample rate must be "
                "8000..192000 Hz"
            )

        _require_identifier(
            name="adversarial microphone class",
            value=self.microphone_class,
        )

        _require_identifier(
            name="adversarial speech variety key",
            value=self.speech_variety_key,
        )

    @property
    def active_stress_count(self) -> int:
        return sum(
            (
                self.channel
                != ASRAdversarialChannel.CLEAN,
                self.codec
                != ASRAdversarialCodec.LINEAR_PCM,
                self.noise
                != ASRAdversarialNoiseCondition.NONE,
                self.speaking_rate
                != ASRAdversarialSpeakingRate.NORMAL,
                self.overlap
                != ASRAdversarialOverlapCondition.NONE,
                self.duration
                == ASRAdversarialDurationBucket.LONG,
            )
        )


@dataclass(frozen=True, slots=True)
class ASRAdversarialSemanticLoad:
    """Declared critical-semantic content carried by one case."""

    critical_number_count: int
    critical_identifier_count: int
    critical_terminology_count: int
    spoken_number_variation: bool
    multiple_critical_items: bool
    duplicate_critical_items: bool
    ordering_challenge: bool
    long_context_position: (
        ASRAdversarialLongContextPosition
    )
    control_case: bool = False

    def __post_init__(self) -> None:
        for name, value in (
            (
                "critical number count",
                self.critical_number_count,
            ),
            (
                "critical identifier count",
                self.critical_identifier_count,
            ),
            (
                "critical terminology count",
                self.critical_terminology_count,
            ),
        ):
            _require_non_negative_integer(
                name=f"adversarial {name}",
                value=value,
            )

        for name, value in (
            (
                "spoken-number variation",
                self.spoken_number_variation,
            ),
            (
                "multiple-critical-items",
                self.multiple_critical_items,
            ),
            (
                "duplicate-critical-items",
                self.duplicate_critical_items,
            ),
            (
                "ordering challenge",
                self.ordering_challenge,
            ),
            (
                "control case",
                self.control_case,
            ),
        ):
            if not isinstance(value, bool):
                raise HveeContractError(
                    f"adversarial {name} must be bool"
                )

        if not isinstance(
            self.long_context_position,
            ASRAdversarialLongContextPosition,
        ):
            raise HveeContractError(
                "adversarial long-context position "
                "requires a versioned enum value"
            )

        total = self.total_critical_items

        if total == 0 and not self.control_case:
            raise HveeContractError(
                "non-control adversarial case requires "
                "at least one critical item"
            )

        if (
            self.multiple_critical_items
            != (total > 1)
        ):
            raise HveeContractError(
                "multiple-critical-items metadata "
                "does not match declared counts"
            )

        if (
            self.spoken_number_variation
            and self.critical_number_count == 0
        ):
            raise HveeContractError(
                "spoken-number variation requires "
                "a critical number"
            )

        if (
            self.duplicate_critical_items
            and total < 2
        ):
            raise HveeContractError(
                "duplicate critical items require "
                "multiple declared critical items"
            )

        if (
            self.ordering_challenge
            and total < 2
        ):
            raise HveeContractError(
                "ordering challenge requires "
                "multiple declared critical items"
            )

    @property
    def total_critical_items(self) -> int:
        return (
            self.critical_number_count
            + self.critical_identifier_count
            + self.critical_terminology_count
        )

    @property
    def semantic_family_count(self) -> int:
        return sum(
            (
                self.critical_number_count > 0,
                self.critical_identifier_count > 0,
                self.critical_terminology_count > 0,
            )
        )


@dataclass(frozen=True, slots=True)
class ASRAdversarialCase:
    """One source-visible adversarial audio case definition."""

    case_id: str
    audio_asset_sha256: str
    reference_transcript: str
    condition: ASRAdversarialCondition
    semantic_load: ASRAdversarialSemanticLoad
    description: str
    tags: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_identifier(
            name="adversarial case id",
            value=self.case_id,
        )

        _require_sha256(
            name="adversarial audio asset",
            value=self.audio_asset_sha256,
        )

        _require_non_empty_text(
            name="adversarial reference transcript",
            value=self.reference_transcript,
        )

        _require_non_empty_text(
            name="adversarial case description",
            value=self.description,
        )

        if not isinstance(
            self.condition,
            ASRAdversarialCondition,
        ):
            raise HveeContractError(
                "adversarial case requires condition metadata"
            )

        if not isinstance(
            self.semantic_load,
            ASRAdversarialSemanticLoad,
        ):
            raise HveeContractError(
                "adversarial case requires semantic-load metadata"
            )

        _require_tags(self.tags)

        if (
            self.semantic_load.long_context_position
            != ASRAdversarialLongContextPosition.NONE
            and self.condition.duration
            != ASRAdversarialDurationBucket.LONG
        ):
            raise HveeContractError(
                "long-context position requires "
                "a long-duration case"
            )


@dataclass(frozen=True, slots=True)
class ASRAdversarialSuiteDefinition:
    """Versioned source-visible adversarial case suite."""

    key: str
    version: str
    cases: tuple[ASRAdversarialCase, ...]

    def __post_init__(self) -> None:
        if (
            self.key
            != ASR_ADVERSARIAL_EVIDENCE_KEY
            or self.version
            != ASR_ADVERSARIAL_EVIDENCE_VERSION
        ):
            raise HveeContractError(
                "adversarial evidence suite identity "
                "is unsupported"
            )

        if (
            not isinstance(self.cases, tuple)
            or not self.cases
            or not all(
                isinstance(
                    case,
                    ASRAdversarialCase,
                )
                for case in self.cases
            )
        ):
            raise HveeContractError(
                "adversarial evidence suite requires cases"
            )

        case_ids = tuple(
            case.case_id
            for case in self.cases
        )

        if tuple(sorted(case_ids)) != case_ids:
            raise HveeContractError(
                "adversarial cases must be ordered "
                "by case id"
            )

        if len(case_ids) != len(set(case_ids)):
            raise HveeContractError(
                "adversarial case ids must be unique"
            )

        audio_assets = tuple(
            case.audio_asset_sha256
            for case in self.cases
        )

        if len(audio_assets) != len(
            set(audio_assets)
        ):
            raise HveeContractError(
                "adversarial suite audio assets "
                "must be unique"
            )


@dataclass(frozen=True, slots=True)
class ASRAdversarialEvidenceBundle:
    """Deterministic non-certifying adversarial evidence manifest."""

    payload: dict[str, object]
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.payload,
            dict,
        ):
            raise HveeContractError(
                "adversarial evidence payload "
                "must be an object"
            )

        _require_sha256(
            name="adversarial evidence",
            value=self.sha256,
        )

        if (
            calculate_asr_adversarial_evidence_sha256(
                self.payload
            )
            != self.sha256
        ):
            raise HveeContractError(
                "adversarial evidence SHA-256 "
                "does not match its payload"
            )


def _case_payload(
    case: ASRAdversarialCase,
) -> dict[str, object]:
    condition = case.condition
    semantic = case.semantic_load

    return {
        "case_id": case.case_id,
        "audio_asset_sha256": (
            case.audio_asset_sha256
        ),
        "reference_transcript": (
            case.reference_transcript
        ),
        "condition": {
            "channel": condition.channel.value,
            "codec": condition.codec.value,
            "sample_rate_hz": (
                condition.sample_rate_hz
            ),
            "microphone_class": (
                condition.microphone_class
            ),
            "noise": condition.noise.value,
            "speaking_rate": (
                condition.speaking_rate.value
            ),
            "speech_variety_key": (
                condition.speech_variety_key
            ),
            "overlap": condition.overlap.value,
            "duration": condition.duration.value,
            "active_stress_count": (
                condition.active_stress_count
            ),
        },
        "semantic_load": {
            "critical_number_count": (
                semantic.critical_number_count
            ),
            "critical_identifier_count": (
                semantic.critical_identifier_count
            ),
            "critical_terminology_count": (
                semantic.critical_terminology_count
            ),
            "spoken_number_variation": (
                semantic.spoken_number_variation
            ),
            "multiple_critical_items": (
                semantic.multiple_critical_items
            ),
            "duplicate_critical_items": (
                semantic.duplicate_critical_items
            ),
            "ordering_challenge": (
                semantic.ordering_challenge
            ),
            "long_context_position": (
                semantic.long_context_position.value
            ),
            "control_case": (
                semantic.control_case
            ),
            "total_critical_items": (
                semantic.total_critical_items
            ),
            "semantic_family_count": (
                semantic.semantic_family_count
            ),
        },
        "description": case.description,
        "tags": list(case.tags),
    }


def _enum_coverage(
    *,
    cases: tuple[ASRAdversarialCase, ...],
    enum_type: type[StrEnum],
    value_getter,
) -> dict[str, int]:
    """Return deterministic coverage for every declared enum value."""

    return {
        enum_value.value: sum(
            value_getter(case) == enum_value
            for case in cases
        )
        for enum_value in enum_type
    }


def _string_coverage(
    values: tuple[str, ...],
) -> dict[str, int]:
    """Return deterministic counts for caller-declared string dimensions."""

    return {
        value: values.count(value)
        for value in sorted(set(values))
    }


def _coverage(
    cases: tuple[ASRAdversarialCase, ...],
) -> dict[str, object]:
    """Describe adversarial coverage without creating qualification gates."""

    return {
        "total_cases": len(cases),
        "audio": {
            "channel": _enum_coverage(
                cases=cases,
                enum_type=ASRAdversarialChannel,
                value_getter=lambda case: case.condition.channel,
            ),
            "codec": _enum_coverage(
                cases=cases,
                enum_type=ASRAdversarialCodec,
                value_getter=lambda case: case.condition.codec,
            ),
            "sample_rate_hz": _string_coverage(
                tuple(
                    str(case.condition.sample_rate_hz)
                    for case in cases
                )
            ),
            "microphone_class": _string_coverage(
                tuple(
                    case.condition.microphone_class
                    for case in cases
                )
            ),
            "noise": _enum_coverage(
                cases=cases,
                enum_type=ASRAdversarialNoiseCondition,
                value_getter=lambda case: case.condition.noise,
            ),
            "speaking_rate": _enum_coverage(
                cases=cases,
                enum_type=ASRAdversarialSpeakingRate,
                value_getter=lambda case: case.condition.speaking_rate,
            ),
            "speech_variety_key": _string_coverage(
                tuple(
                    case.condition.speech_variety_key
                    for case in cases
                )
            ),
            "overlap": _enum_coverage(
                cases=cases,
                enum_type=ASRAdversarialOverlapCondition,
                value_getter=lambda case: case.condition.overlap,
            ),
            "duration": _enum_coverage(
                cases=cases,
                enum_type=ASRAdversarialDurationBucket,
                value_getter=lambda case: case.condition.duration,
            ),
            "compound_stress_cases": sum(
                case.condition.active_stress_count >= 2
                for case in cases
            ),
        },
        "semantic": {
            "control_cases": sum(
                case.semantic_load.control_case
                for case in cases
            ),
            "critical_number_cases": sum(
                case.semantic_load.critical_number_count > 0
                for case in cases
            ),
            "critical_identifier_cases": sum(
                case.semantic_load.critical_identifier_count > 0
                for case in cases
            ),
            "critical_terminology_cases": sum(
                case.semantic_load.critical_terminology_count > 0
                for case in cases
            ),
            "spoken_number_variation_cases": sum(
                case.semantic_load.spoken_number_variation
                for case in cases
            ),
            "duplicate_critical_item_cases": sum(
                case.semantic_load.duplicate_critical_items
                for case in cases
            ),
            "ordering_challenge_cases": sum(
                case.semantic_load.ordering_challenge
                for case in cases
            ),
            "long_context_position": _enum_coverage(
                cases=cases,
                enum_type=ASRAdversarialLongContextPosition,
                value_getter=(
                    lambda case:
                    case.semantic_load.long_context_position
                ),
            ),
            "multi_family_cases": sum(
                case.semantic_load.semantic_family_count >= 2
                for case in cases
            ),
            "three_family_cases": sum(
                case.semantic_load.semantic_family_count == 3
                for case in cases
            ),
            "compound_adversarial_cases": sum(
                case.condition.active_stress_count >= 2
                and case.semantic_load.total_critical_items >= 2
                for case in cases
            ),
        },
    }


def build_asr_adversarial_evidence_v1(
    definition: ASRAdversarialSuiteDefinition,
) -> ASRAdversarialEvidenceBundle:
    """Build deterministic source-visible adversarial evidence metadata."""

    if not isinstance(
        definition,
        ASRAdversarialSuiteDefinition,
    ):
        raise HveeContractError(
            "adversarial evidence requires "
            "ASRAdversarialSuiteDefinition"
        )

    payload: dict[str, object] = {
        "schema_version": (
            ASR_ADVERSARIAL_EVIDENCE_SCHEMA_VERSION
        ),
        "artifact": {
            "key": ASR_ADVERSARIAL_EVIDENCE_KEY,
            "version": (
                ASR_ADVERSARIAL_EVIDENCE_VERSION
            ),
            "type": (
                "source_visible_adversarial_"
                "development_evidence"
            ),
        },
        "cases": [
            _case_payload(case)
            for case in definition.cases
        ],
        "coverage": _coverage(
            definition.cases
        ),
        "scientific_boundary": {
            "condition_metadata_caller_declared": True,
            "condition_metadata_independently_verified": False,
            "acoustic_cause_inferred_from_transcript": False,
            "speaker_attributes_inferred": False,
            "semantic_evaluator_methodology_modified": False,
            "development_evidence_only": True,
            "certification_issued": False,
            "production_qualified": False,
            "release_enforcement_eligible": False,
            "official_release_verdict_modified": False,
        },
    }

    return ASRAdversarialEvidenceBundle(
        payload=payload,
        sha256=(
            calculate_asr_adversarial_evidence_sha256(
                payload
            )
        ),
    )


def verify_asr_adversarial_evidence_v1(
    *,
    payload: object,
    expected_sha256: object,
    definition: ASRAdversarialSuiteDefinition,
) -> ASRAdversarialEvidenceBundle:
    """Require exact equality with a rebuilt v1 evidence manifest."""

    digest = _require_sha256(
        name="expected adversarial evidence",
        value=expected_sha256,
    )

    if not isinstance(payload, dict):
        raise HveeContractError(
            "supplied adversarial evidence "
            "must be an object"
        )

    supplied = ASRAdversarialEvidenceBundle(
        payload=payload,
        sha256=digest,
    )

    rebuilt = build_asr_adversarial_evidence_v1(
        definition
    )

    if (
        supplied.payload != rebuilt.payload
        or supplied.sha256 != rebuilt.sha256
    ):
        raise HveeContractError(
            "adversarial evidence does not "
            "match the v1 definition"
        )

    return rebuilt

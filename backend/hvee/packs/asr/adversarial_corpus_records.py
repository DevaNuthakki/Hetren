"""Deterministic source and transformation records for adversarial ASR audio.

These records commit to how development corpus assets are sourced or
generated. They do not adjudicate legal rights, infer speaker attributes,
certify acoustic diversity, qualify production behavior, or modify release
decisions.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from hvee.core.contracts import HveeContractError


ASR_ADVERSARIAL_CORPUS_RECORD_SCHEMA_VERSION = 1

ASR_ADVERSARIAL_CORPUS_PROVENANCE_RECORD_KEY = (
    "hetren.asr.adversarial-corpus-provenance-record.en-us"
)
ASR_ADVERSARIAL_CORPUS_RIGHTS_RECORD_KEY = (
    "hetren.asr.adversarial-corpus-rights-record.en-us"
)
ASR_ADVERSARIAL_CORPUS_TRANSFORMATION_RECORD_KEY = (
    "hetren.asr.adversarial-corpus-transformation-record.en-us"
)
ASR_ADVERSARIAL_CORPUS_GENERATION_PLAN_KEY = (
    "hetren.asr.adversarial-corpus-generation-plan.en-us"
)
ASR_ADVERSARIAL_CORPUS_DERIVATION_PLAN_KEY = (
    "hetren.asr.adversarial-corpus-derivation-plan.en-us"
)

ASR_ADVERSARIAL_CORPUS_RECORD_VERSION = "1.0.0"

_IDENTIFIER_PATTERN = re.compile(
    r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$"
)
_VERSION_PATTERN = re.compile(
    r"^[0-9]+\.[0-9]+\.[0-9]+$"
)
_SHA256_PATTERN = re.compile(
    r"^[0-9a-f]{64}$"
)
_PATH_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9._/-]*$"
)
_CODEC_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9_]*$"
)


def _canonical_json(
    value: object,
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
            "adversarial corpus record must contain "
            "valid deterministic JSON"
        ) from exc


def calculate_asr_adversarial_corpus_record_sha256(
    payload: object,
) -> str:
    return hashlib.sha256(
        _canonical_json(
            payload
        ).encode("utf-8")
    ).hexdigest()


def _require_identifier(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or _IDENTIFIER_PATTERN.fullmatch(
            value
        )
        is None
    ):
        raise HveeContractError(
            f"{name} must be a canonical lowercase identifier"
        )

    return value


def _require_version(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or _VERSION_PATTERN.fullmatch(
            value
        )
        is None
    ):
        raise HveeContractError(
            f"{name} must use semantic version text"
        )

    return value


def _require_sha256(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or _SHA256_PATTERN.fullmatch(
            value
        )
        is None
    ):
        raise HveeContractError(
            f"{name} must be a lowercase SHA-256 digest"
        )

    return value


def _require_positive_integer(
    *,
    name: str,
    value: object,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value <= 0
    ):
        raise HveeContractError(
            f"{name} must be a positive integer"
        )

    return value


def _require_relative_path(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\\" in value
        or value.startswith("/")
        or ".." in value.split("/")
        or "." in value.split("/")
        or _PATH_PATTERN.fullmatch(
            value
        )
        is None
    ):
        raise HveeContractError(
            f"{name} must be a canonical relative POSIX path"
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
            f"{name} must be non-empty canonical text"
        )

    return value


def _record_envelope(
    *,
    key: str,
    record_type: str,
    record: dict[str, object],
) -> dict[str, object]:
    return {
        "schema_version": (
            ASR_ADVERSARIAL_CORPUS_RECORD_SCHEMA_VERSION
        ),
        "artifact": {
            "key": key,
            "version": (
                ASR_ADVERSARIAL_CORPUS_RECORD_VERSION
            ),
            "type": record_type,
        },
        "record": record,
        "evidence_boundary": {
            "development_evidence_only": True,
            "rights_adjudicated": False,
            "speaker_attributes_inferred": False,
            "human_acoustic_diversity_established": False,
            "qualification_threshold_applied": False,
            "certification_issued": False,
            "production_qualified": False,
            "release_enforcement_eligible": False,
            "official_release_verdict_modified": False,
        },
    }


@dataclass(frozen=True, slots=True)
class ASRAdversarialCorpusProvenanceRecord:
    record_id: str
    case_id: str
    transcript_sha256: str
    generator_key: str
    generator_version: str
    generator_executable_sha256: str
    voice_key: str
    speed_wpm: int
    pitch: int
    amplitude: int
    platform_key: str

    def __post_init__(self) -> None:
        _require_identifier(
            name="provenance record id",
            value=self.record_id,
        )
        _require_identifier(
            name="provenance case id",
            value=self.case_id,
        )
        _require_sha256(
            name="provenance transcript",
            value=self.transcript_sha256,
        )
        _require_identifier(
            name="provenance generator key",
            value=self.generator_key,
        )
        _require_non_empty_text(
            name="provenance generator version",
            value=self.generator_version,
        )
        _require_sha256(
            name="provenance generator executable",
            value=self.generator_executable_sha256,
        )
        _require_identifier(
            name="provenance voice key",
            value=self.voice_key,
        )
        _require_identifier(
            name="provenance platform key",
            value=self.platform_key,
        )

        for name, value, lower, upper in (
            (
                "speed WPM",
                self.speed_wpm,
                80,
                450,
            ),
            (
                "pitch",
                self.pitch,
                0,
                99,
            ),
            (
                "amplitude",
                self.amplitude,
                0,
                200,
            ),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not lower <= value <= upper
            ):
                raise HveeContractError(
                    f"provenance {name} is outside "
                    "the supported deterministic range"
                )


@dataclass(frozen=True, slots=True)
class ASRAdversarialCorpusRightsRecord:
    record_id: str
    case_id: str
    source_package_key: str
    source_package_version: str
    packaged_copyright_sha256: str
    review_status: str
    development_use_only: bool

    def __post_init__(self) -> None:
        _require_identifier(
            name="rights record id",
            value=self.record_id,
        )
        _require_identifier(
            name="rights case id",
            value=self.case_id,
        )
        _require_identifier(
            name="rights source package key",
            value=self.source_package_key,
        )
        _require_non_empty_text(
            name="rights source package version",
            value=self.source_package_version,
        )
        _require_sha256(
            name="packaged copyright record",
            value=self.packaged_copyright_sha256,
        )

        if self.review_status != "not_adjudicated":
            raise HveeContractError(
                "rights review status must remain not_adjudicated"
            )

        if self.development_use_only is not True:
            raise HveeContractError(
                "synthetic corpus rights record must remain "
                "development-use-only"
            )


@dataclass(frozen=True, slots=True)
class ASRAdversarialCorpusTransformationRecord:
    record_id: str
    case_id: str
    parent_audio_sha256: str
    tool_key: str
    tool_version: str
    tool_environment_sha256: str
    argv: tuple[str, ...]
    output_relative_path: str
    expected_sample_rate_hz: int
    expected_channel_count: int
    expected_codec_name: str

    def __post_init__(self) -> None:
        _require_identifier(
            name="transformation record id",
            value=self.record_id,
        )
        _require_identifier(
            name="transformation case id",
            value=self.case_id,
        )
        _require_sha256(
            name="transformation parent audio",
            value=self.parent_audio_sha256,
        )
        _require_identifier(
            name="transformation tool key",
            value=self.tool_key,
        )
        _require_non_empty_text(
            name="transformation tool version",
            value=self.tool_version,
        )
        _require_sha256(
            name="transformation tool environment",
            value=self.tool_environment_sha256,
        )
        _require_relative_path(
            name="transformation output path",
            value=self.output_relative_path,
        )
        _require_positive_integer(
            name="transformation sample rate",
            value=self.expected_sample_rate_hz,
        )
        _require_positive_integer(
            name="transformation channel count",
            value=self.expected_channel_count,
        )

        if (
            not isinstance(self.expected_codec_name, str)
            or _CODEC_PATTERN.fullmatch(
                self.expected_codec_name
            )
            is None
        ):
            raise HveeContractError(
                "transformation codec name must be "
                "canonical lowercase text"
            )

        if (
            not isinstance(self.argv, tuple)
            or not self.argv
        ):
            raise HveeContractError(
                "transformation argv must be a non-empty tuple"
            )

        for argument in self.argv:
            if (
                not isinstance(argument, str)
                or not argument
                or "\x00" in argument
            ):
                raise HveeContractError(
                    "transformation argv contains "
                    "an invalid argument"
                )


@dataclass(frozen=True, slots=True)
class ASRAdversarialCorpusGenerationPlanEntry:
    case_id: str
    output_relative_path: str
    provenance_record_sha256: str
    rights_record_sha256: str
    transformation_record_sha256: str | None

    def __post_init__(self) -> None:
        _require_identifier(
            name="generation-plan case id",
            value=self.case_id,
        )
        _require_relative_path(
            name="generation-plan output path",
            value=self.output_relative_path,
        )
        _require_sha256(
            name="generation-plan provenance record",
            value=self.provenance_record_sha256,
        )
        _require_sha256(
            name="generation-plan rights record",
            value=self.rights_record_sha256,
        )

        if self.transformation_record_sha256 is not None:
            _require_sha256(
                name="generation-plan transformation record",
                value=self.transformation_record_sha256,
            )


@dataclass(frozen=True, slots=True)
class ASRAdversarialCorpusGenerationPlan:
    corpus_id: str
    corpus_version: str
    entries: tuple[
        ASRAdversarialCorpusGenerationPlanEntry,
        ...,
    ]

    def __post_init__(self) -> None:
        _require_identifier(
            name="generation-plan corpus id",
            value=self.corpus_id,
        )
        _require_version(
            name="generation-plan corpus version",
            value=self.corpus_version,
        )

        if (
            not isinstance(self.entries, tuple)
            or not self.entries
            or not all(
                isinstance(
                    entry,
                    ASRAdversarialCorpusGenerationPlanEntry,
                )
                for entry in self.entries
            )
        ):
            raise HveeContractError(
                "generation plan requires entries"
            )

        case_ids = tuple(
            entry.case_id
            for entry in self.entries
        )

        if case_ids != tuple(
            sorted(case_ids)
        ):
            raise HveeContractError(
                "generation-plan entries must be "
                "ordered by case id"
            )

        if len(case_ids) != len(
            set(case_ids)
        ):
            raise HveeContractError(
                "generation-plan case ids must be unique"
            )

        paths = tuple(
            entry.output_relative_path
            for entry in self.entries
        )

        if len(paths) != len(
            set(paths)
        ):
            raise HveeContractError(
                "generation-plan output paths must be unique"
            )


@dataclass(frozen=True, slots=True)
class ASRAdversarialCorpusDerivationPlanEntry:
    """One deterministic parent-to-derived asset binding."""

    case_id: str
    parent_case_id: str
    parent_relative_path: str
    parent_audio_sha256: str
    output_relative_path: str
    provenance_record_sha256: str
    rights_record_sha256: str
    transformation_record_sha256: str

    def __post_init__(self) -> None:
        _require_identifier(
            name="derivation-plan case id",
            value=self.case_id,
        )
        _require_identifier(
            name="derivation-plan parent case id",
            value=self.parent_case_id,
        )
        _require_relative_path(
            name="derivation-plan parent path",
            value=self.parent_relative_path,
        )
        _require_sha256(
            name="derivation-plan parent audio",
            value=self.parent_audio_sha256,
        )
        _require_relative_path(
            name="derivation-plan output path",
            value=self.output_relative_path,
        )
        _require_sha256(
            name="derivation-plan provenance record",
            value=self.provenance_record_sha256,
        )
        _require_sha256(
            name="derivation-plan rights record",
            value=self.rights_record_sha256,
        )
        _require_sha256(
            name="derivation-plan transformation record",
            value=self.transformation_record_sha256,
        )

        if self.case_id == self.parent_case_id:
            raise HveeContractError(
                "derived case id must differ from its parent case id"
            )

        if (
            self.output_relative_path
            == self.parent_relative_path
        ):
            raise HveeContractError(
                "derived output path must differ from its parent path"
            )


@dataclass(frozen=True, slots=True)
class ASRAdversarialCorpusDerivationPlan:
    """Versioned deterministic plan for corpus-to-corpus derivations."""

    corpus_id: str
    corpus_version: str
    parent_manifest_sha256: str
    entries: tuple[
        ASRAdversarialCorpusDerivationPlanEntry,
        ...,
    ]

    def __post_init__(self) -> None:
        _require_identifier(
            name="derivation-plan corpus id",
            value=self.corpus_id,
        )
        _require_version(
            name="derivation-plan corpus version",
            value=self.corpus_version,
        )
        _require_sha256(
            name="derivation-plan parent manifest",
            value=self.parent_manifest_sha256,
        )

        if (
            not isinstance(self.entries, tuple)
            or not self.entries
            or not all(
                isinstance(
                    entry,
                    ASRAdversarialCorpusDerivationPlanEntry,
                )
                for entry in self.entries
            )
        ):
            raise HveeContractError(
                "derivation plan requires entries"
            )

        case_ids = tuple(
            entry.case_id
            for entry in self.entries
        )

        if case_ids != tuple(
            sorted(case_ids)
        ):
            raise HveeContractError(
                "derivation-plan entries must be ordered by case id"
            )

        if len(case_ids) != len(
            set(case_ids)
        ):
            raise HveeContractError(
                "derivation-plan case ids must be unique"
            )

        output_paths = tuple(
            entry.output_relative_path
            for entry in self.entries
        )

        if len(output_paths) != len(
            set(output_paths)
        ):
            raise HveeContractError(
                "derivation-plan output paths must be unique"
            )


@dataclass(frozen=True, slots=True)
class ASRAdversarialCorpusRecordBundle:
    payload: dict[str, object]
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.payload,
            dict,
        ):
            raise HveeContractError(
                "corpus record payload must be an object"
            )

        _require_sha256(
            name="corpus record",
            value=self.sha256,
        )

        if (
            calculate_asr_adversarial_corpus_record_sha256(
                self.payload
            )
            != self.sha256
        ):
            raise HveeContractError(
                "corpus record SHA-256 does not "
                "match its payload"
            )


def _bundle(
    payload: dict[str, object],
) -> ASRAdversarialCorpusRecordBundle:
    return ASRAdversarialCorpusRecordBundle(
        payload=payload,
        sha256=(
            calculate_asr_adversarial_corpus_record_sha256(
                payload
            )
        ),
    )


def build_asr_adversarial_corpus_provenance_record_v1(
    record: ASRAdversarialCorpusProvenanceRecord,
) -> ASRAdversarialCorpusRecordBundle:
    if not isinstance(
        record,
        ASRAdversarialCorpusProvenanceRecord,
    ):
        raise HveeContractError(
            "provenance record type is invalid"
        )

    return _bundle(
        _record_envelope(
            key=(
                ASR_ADVERSARIAL_CORPUS_PROVENANCE_RECORD_KEY
            ),
            record_type=(
                "source_visible_adversarial_"
                "corpus_provenance_record"
            ),
            record={
                "record_id": record.record_id,
                "case_id": record.case_id,
                "source_kind": "synthetic_tts",
                "transcript_sha256": (
                    record.transcript_sha256
                ),
                "generator": {
                    "key": record.generator_key,
                    "version": record.generator_version,
                    "executable_sha256": (
                        record.generator_executable_sha256
                    ),
                    "voice_key": record.voice_key,
                    "speed_wpm": record.speed_wpm,
                    "pitch": record.pitch,
                    "amplitude": record.amplitude,
                    "platform_key": record.platform_key,
                },
            },
        )
    )


def build_asr_adversarial_corpus_rights_record_v1(
    record: ASRAdversarialCorpusRightsRecord,
) -> ASRAdversarialCorpusRecordBundle:
    if not isinstance(
        record,
        ASRAdversarialCorpusRightsRecord,
    ):
        raise HveeContractError(
            "rights record type is invalid"
        )

    return _bundle(
        _record_envelope(
            key=(
                ASR_ADVERSARIAL_CORPUS_RIGHTS_RECORD_KEY
            ),
            record_type=(
                "source_visible_adversarial_"
                "corpus_rights_record"
            ),
            record={
                "record_id": record.record_id,
                "case_id": record.case_id,
                "source_package": {
                    "key": record.source_package_key,
                    "version": (
                        record.source_package_version
                    ),
                    "packaged_copyright_sha256": (
                        record.packaged_copyright_sha256
                    ),
                },
                "review_status": record.review_status,
                "development_use_only": (
                    record.development_use_only
                ),
            },
        )
    )


def build_asr_adversarial_corpus_transformation_record_v1(
    record: ASRAdversarialCorpusTransformationRecord,
) -> ASRAdversarialCorpusRecordBundle:
    if not isinstance(
        record,
        ASRAdversarialCorpusTransformationRecord,
    ):
        raise HveeContractError(
            "transformation record type is invalid"
        )

    return _bundle(
        _record_envelope(
            key=(
                ASR_ADVERSARIAL_CORPUS_TRANSFORMATION_RECORD_KEY
            ),
            record_type=(
                "source_visible_adversarial_"
                "corpus_transformation_record"
            ),
            record={
                "record_id": record.record_id,
                "case_id": record.case_id,
                "parent_audio_sha256": (
                    record.parent_audio_sha256
                ),
                "tool": {
                    "key": record.tool_key,
                    "version": record.tool_version,
                    "environment_sha256": (
                        record.tool_environment_sha256
                    ),
                },
                "argv": list(
                    record.argv
                ),
                "expected_output": {
                    "relative_path": (
                        record.output_relative_path
                    ),
                    "sample_rate_hz": (
                        record.expected_sample_rate_hz
                    ),
                    "channel_count": (
                        record.expected_channel_count
                    ),
                    "codec_name": (
                        record.expected_codec_name
                    ),
                },
            },
        )
    )


def build_asr_adversarial_corpus_generation_plan_v1(
    plan: ASRAdversarialCorpusGenerationPlan,
) -> ASRAdversarialCorpusRecordBundle:
    if not isinstance(
        plan,
        ASRAdversarialCorpusGenerationPlan,
    ):
        raise HveeContractError(
            "generation plan type is invalid"
        )

    return _bundle(
        _record_envelope(
            key=(
                ASR_ADVERSARIAL_CORPUS_GENERATION_PLAN_KEY
            ),
            record_type=(
                "source_visible_adversarial_"
                "corpus_generation_plan"
            ),
            record={
                "corpus_id": plan.corpus_id,
                "corpus_version": plan.corpus_version,
                "entries": [
                    {
                        "case_id": entry.case_id,
                        "output_relative_path": (
                            entry.output_relative_path
                        ),
                        "provenance_record_sha256": (
                            entry.provenance_record_sha256
                        ),
                        "rights_record_sha256": (
                            entry.rights_record_sha256
                        ),
                        "transformation_record_sha256": (
                            entry.transformation_record_sha256
                        ),
                    }
                    for entry in plan.entries
                ],
            },
        )
    )


def build_asr_adversarial_corpus_derivation_plan_v1(
    plan: ASRAdversarialCorpusDerivationPlan,
) -> ASRAdversarialCorpusRecordBundle:
    """Build deterministic parent-to-derived corpus lineage evidence."""

    if not isinstance(
        plan,
        ASRAdversarialCorpusDerivationPlan,
    ):
        raise HveeContractError(
            "derivation plan type is invalid"
        )

    return _bundle(
        _record_envelope(
            key=(
                ASR_ADVERSARIAL_CORPUS_DERIVATION_PLAN_KEY
            ),
            record_type=(
                "source_visible_adversarial_"
                "corpus_derivation_plan"
            ),
            record={
                "corpus_id": plan.corpus_id,
                "corpus_version": plan.corpus_version,
                "parent_manifest_sha256": (
                    plan.parent_manifest_sha256
                ),
                "entries": [
                    {
                        "case_id": entry.case_id,
                        "parent_case_id": (
                            entry.parent_case_id
                        ),
                        "parent_relative_path": (
                            entry.parent_relative_path
                        ),
                        "parent_audio_sha256": (
                            entry.parent_audio_sha256
                        ),
                        "output_relative_path": (
                            entry.output_relative_path
                        ),
                        "provenance_record_sha256": (
                            entry.provenance_record_sha256
                        ),
                        "rights_record_sha256": (
                            entry.rights_record_sha256
                        ),
                        "transformation_record_sha256": (
                            entry.transformation_record_sha256
                        ),
                    }
                    for entry in plan.entries
                ],
            },
        )
    )


def _require_exact_keys(
    *,
    name: str,
    value: object,
    expected: set[str],
) -> dict[str, object]:
    if (
        not isinstance(value, dict)
        or set(value) != expected
    ):
        raise HveeContractError(
            f"{name} has an invalid schema"
        )

    return value


def _rebuild_record_bundle(
    payload: dict[str, object],
) -> ASRAdversarialCorpusRecordBundle:
    artifact = _require_exact_keys(
        name="corpus record artifact",
        value=payload.get("artifact"),
        expected={
            "key",
            "version",
            "type",
        },
    )

    if (
        artifact["version"]
        != ASR_ADVERSARIAL_CORPUS_RECORD_VERSION
    ):
        raise HveeContractError(
            "corpus record artifact version is unsupported"
        )

    record = payload.get(
        "record"
    )

    key = artifact["key"]
    artifact_type = artifact[
        "type"
    ]

    if (
        key
        == ASR_ADVERSARIAL_CORPUS_PROVENANCE_RECORD_KEY
    ):
        if (
            artifact_type
            != "source_visible_adversarial_"
            "corpus_provenance_record"
        ):
            raise HveeContractError(
                "corpus provenance artifact type is invalid"
            )

        provenance = _require_exact_keys(
            name="corpus provenance record",
            value=record,
            expected={
                "record_id",
                "case_id",
                "source_kind",
                "transcript_sha256",
                "generator",
            },
        )

        if provenance[
            "source_kind"
        ] != "synthetic_tts":
            raise HveeContractError(
                "corpus provenance source kind is unsupported"
            )

        generator = _require_exact_keys(
            name="corpus provenance generator",
            value=provenance[
                "generator"
            ],
            expected={
                "key",
                "version",
                "executable_sha256",
                "voice_key",
                "speed_wpm",
                "pitch",
                "amplitude",
                "platform_key",
            },
        )

        return (
            build_asr_adversarial_corpus_provenance_record_v1(
                ASRAdversarialCorpusProvenanceRecord(
                    record_id=provenance[
                        "record_id"
                    ],
                    case_id=provenance[
                        "case_id"
                    ],
                    transcript_sha256=provenance[
                        "transcript_sha256"
                    ],
                    generator_key=generator[
                        "key"
                    ],
                    generator_version=generator[
                        "version"
                    ],
                    generator_executable_sha256=(
                        generator[
                            "executable_sha256"
                        ]
                    ),
                    voice_key=generator[
                        "voice_key"
                    ],
                    speed_wpm=generator[
                        "speed_wpm"
                    ],
                    pitch=generator[
                        "pitch"
                    ],
                    amplitude=generator[
                        "amplitude"
                    ],
                    platform_key=generator[
                        "platform_key"
                    ],
                )
            )
        )

    if (
        key
        == ASR_ADVERSARIAL_CORPUS_RIGHTS_RECORD_KEY
    ):
        if (
            artifact_type
            != "source_visible_adversarial_"
            "corpus_rights_record"
        ):
            raise HveeContractError(
                "corpus rights artifact type is invalid"
            )

        rights = _require_exact_keys(
            name="corpus rights record",
            value=record,
            expected={
                "record_id",
                "case_id",
                "source_package",
                "review_status",
                "development_use_only",
            },
        )

        source_package = _require_exact_keys(
            name="corpus rights source package",
            value=rights[
                "source_package"
            ],
            expected={
                "key",
                "version",
                "packaged_copyright_sha256",
            },
        )

        return (
            build_asr_adversarial_corpus_rights_record_v1(
                ASRAdversarialCorpusRightsRecord(
                    record_id=rights[
                        "record_id"
                    ],
                    case_id=rights[
                        "case_id"
                    ],
                    source_package_key=(
                        source_package[
                            "key"
                        ]
                    ),
                    source_package_version=(
                        source_package[
                            "version"
                        ]
                    ),
                    packaged_copyright_sha256=(
                        source_package[
                            "packaged_copyright_sha256"
                        ]
                    ),
                    review_status=rights[
                        "review_status"
                    ],
                    development_use_only=rights[
                        "development_use_only"
                    ],
                )
            )
        )

    if (
        key
        == ASR_ADVERSARIAL_CORPUS_TRANSFORMATION_RECORD_KEY
    ):
        if (
            artifact_type
            != "source_visible_adversarial_"
            "corpus_transformation_record"
        ):
            raise HveeContractError(
                "corpus transformation artifact type is invalid"
            )

        transformation = _require_exact_keys(
            name="corpus transformation record",
            value=record,
            expected={
                "record_id",
                "case_id",
                "parent_audio_sha256",
                "tool",
                "argv",
                "expected_output",
            },
        )

        tool = _require_exact_keys(
            name="corpus transformation tool",
            value=transformation[
                "tool"
            ],
            expected={
                "key",
                "version",
                "environment_sha256",
            },
        )

        expected_output = _require_exact_keys(
            name="corpus transformation output",
            value=transformation[
                "expected_output"
            ],
            expected={
                "relative_path",
                "sample_rate_hz",
                "channel_count",
                "codec_name",
            },
        )

        argv = transformation[
            "argv"
        ]

        if not isinstance(
            argv,
            list,
        ):
            raise HveeContractError(
                "corpus transformation argv "
                "must be a JSON array"
            )

        return (
            build_asr_adversarial_corpus_transformation_record_v1(
                ASRAdversarialCorpusTransformationRecord(
                    record_id=transformation[
                        "record_id"
                    ],
                    case_id=transformation[
                        "case_id"
                    ],
                    parent_audio_sha256=(
                        transformation[
                            "parent_audio_sha256"
                        ]
                    ),
                    tool_key=tool[
                        "key"
                    ],
                    tool_version=tool[
                        "version"
                    ],
                    tool_environment_sha256=(
                        tool[
                            "environment_sha256"
                        ]
                    ),
                    argv=tuple(
                        argv
                    ),
                    output_relative_path=(
                        expected_output[
                            "relative_path"
                        ]
                    ),
                    expected_sample_rate_hz=(
                        expected_output[
                            "sample_rate_hz"
                        ]
                    ),
                    expected_channel_count=(
                        expected_output[
                            "channel_count"
                        ]
                    ),
                    expected_codec_name=(
                        expected_output[
                            "codec_name"
                        ]
                    ),
                )
            )
        )

    if (
        key
        == ASR_ADVERSARIAL_CORPUS_DERIVATION_PLAN_KEY
    ):
        if (
            artifact_type
            != "source_visible_adversarial_"
            "corpus_derivation_plan"
        ):
            raise HveeContractError(
                "corpus derivation-plan artifact type is invalid"
            )

        plan_record = _require_exact_keys(
            name="corpus derivation plan",
            value=record,
            expected={
                "corpus_id",
                "corpus_version",
                "parent_manifest_sha256",
                "entries",
            },
        )

        entries = plan_record[
            "entries"
        ]

        if not isinstance(
            entries,
            list,
        ):
            raise HveeContractError(
                "corpus derivation-plan entries "
                "must be a JSON array"
            )

        parsed_entries = []

        for entry in entries:
            normalized = _require_exact_keys(
                name="corpus derivation-plan entry",
                value=entry,
                expected={
                    "case_id",
                    "parent_case_id",
                    "parent_relative_path",
                    "parent_audio_sha256",
                    "output_relative_path",
                    "provenance_record_sha256",
                    "rights_record_sha256",
                    "transformation_record_sha256",
                },
            )

            parsed_entries.append(
                ASRAdversarialCorpusDerivationPlanEntry(
                    case_id=normalized[
                        "case_id"
                    ],
                    parent_case_id=normalized[
                        "parent_case_id"
                    ],
                    parent_relative_path=(
                        normalized[
                            "parent_relative_path"
                        ]
                    ),
                    parent_audio_sha256=(
                        normalized[
                            "parent_audio_sha256"
                        ]
                    ),
                    output_relative_path=(
                        normalized[
                            "output_relative_path"
                        ]
                    ),
                    provenance_record_sha256=(
                        normalized[
                            "provenance_record_sha256"
                        ]
                    ),
                    rights_record_sha256=(
                        normalized[
                            "rights_record_sha256"
                        ]
                    ),
                    transformation_record_sha256=(
                        normalized[
                            "transformation_record_sha256"
                        ]
                    ),
                )
            )

        return (
            build_asr_adversarial_corpus_derivation_plan_v1(
                ASRAdversarialCorpusDerivationPlan(
                    corpus_id=plan_record[
                        "corpus_id"
                    ],
                    corpus_version=plan_record[
                        "corpus_version"
                    ],
                    parent_manifest_sha256=(
                        plan_record[
                            "parent_manifest_sha256"
                        ]
                    ),
                    entries=tuple(
                        parsed_entries
                    ),
                )
            )
        )

    if (
        key
        == ASR_ADVERSARIAL_CORPUS_GENERATION_PLAN_KEY
    ):
        if (
            artifact_type
            != "source_visible_adversarial_"
            "corpus_generation_plan"
        ):
            raise HveeContractError(
                "corpus generation-plan artifact type is invalid"
            )

        plan_record = _require_exact_keys(
            name="corpus generation plan",
            value=record,
            expected={
                "corpus_id",
                "corpus_version",
                "entries",
            },
        )

        entries = plan_record[
            "entries"
        ]

        if not isinstance(
            entries,
            list,
        ):
            raise HveeContractError(
                "corpus generation-plan entries "
                "must be a JSON array"
            )

        parsed_entries = []

        for entry in entries:
            normalized = _require_exact_keys(
                name="corpus generation-plan entry",
                value=entry,
                expected={
                    "case_id",
                    "output_relative_path",
                    "provenance_record_sha256",
                    "rights_record_sha256",
                    "transformation_record_sha256",
                },
            )

            parsed_entries.append(
                ASRAdversarialCorpusGenerationPlanEntry(
                    case_id=normalized[
                        "case_id"
                    ],
                    output_relative_path=(
                        normalized[
                            "output_relative_path"
                        ]
                    ),
                    provenance_record_sha256=(
                        normalized[
                            "provenance_record_sha256"
                        ]
                    ),
                    rights_record_sha256=(
                        normalized[
                            "rights_record_sha256"
                        ]
                    ),
                    transformation_record_sha256=(
                        normalized[
                            "transformation_record_sha256"
                        ]
                    ),
                )
            )

        return (
            build_asr_adversarial_corpus_generation_plan_v1(
                ASRAdversarialCorpusGenerationPlan(
                    corpus_id=plan_record[
                        "corpus_id"
                    ],
                    corpus_version=plan_record[
                        "corpus_version"
                    ],
                    entries=tuple(
                        parsed_entries
                    ),
                )
            )
        )

    raise HveeContractError(
        "corpus record artifact key is unsupported"
    )


def verify_asr_adversarial_corpus_record_v1(
    *,
    payload: dict[str, object],
    expected_sha256: str,
) -> ASRAdversarialCorpusRecordBundle:
    _require_sha256(
        name="expected corpus record",
        value=expected_sha256,
    )

    if not isinstance(
        payload,
        dict,
    ):
        raise HveeContractError(
            "corpus record payload must be an object"
        )

    if set(payload) != {
        "schema_version",
        "artifact",
        "record",
        "evidence_boundary",
    }:
        raise HveeContractError(
            "corpus record envelope has an invalid schema"
        )

    if (
        calculate_asr_adversarial_corpus_record_sha256(
            payload
        )
        != expected_sha256
    ):
        raise HveeContractError(
            "corpus record verification failed"
        )

    if payload[
        "schema_version"
    ] != ASR_ADVERSARIAL_CORPUS_RECORD_SCHEMA_VERSION:
        raise HveeContractError(
            "corpus record schema version is unsupported"
        )

    boundary = payload[
        "evidence_boundary"
    ]

    required_negative_authority = {
        "development_evidence_only": True,
        "rights_adjudicated": False,
        "speaker_attributes_inferred": False,
        "human_acoustic_diversity_established": False,
        "qualification_threshold_applied": False,
        "certification_issued": False,
        "production_qualified": False,
        "release_enforcement_eligible": False,
        "official_release_verdict_modified": False,
    }

    if boundary != required_negative_authority:
        raise HveeContractError(
            "corpus record evidence boundary is invalid"
        )

    rebuilt = _rebuild_record_bundle(
        payload
    )

    if (
        rebuilt.payload != payload
        or rebuilt.sha256
        != expected_sha256
    ):
        raise HveeContractError(
            "corpus record canonical reconstruction failed"
        )

    return rebuilt


__all__ = [
    "ASR_ADVERSARIAL_CORPUS_DERIVATION_PLAN_KEY",
    "ASR_ADVERSARIAL_CORPUS_GENERATION_PLAN_KEY",
    "ASR_ADVERSARIAL_CORPUS_PROVENANCE_RECORD_KEY",
    "ASR_ADVERSARIAL_CORPUS_RECORD_SCHEMA_VERSION",
    "ASR_ADVERSARIAL_CORPUS_RECORD_VERSION",
    "ASR_ADVERSARIAL_CORPUS_RIGHTS_RECORD_KEY",
    "ASR_ADVERSARIAL_CORPUS_TRANSFORMATION_RECORD_KEY",
    "ASRAdversarialCorpusDerivationPlan",
    "ASRAdversarialCorpusDerivationPlanEntry",
    "ASRAdversarialCorpusGenerationPlan",
    "ASRAdversarialCorpusGenerationPlanEntry",
    "ASRAdversarialCorpusProvenanceRecord",
    "ASRAdversarialCorpusRecordBundle",
    "ASRAdversarialCorpusRightsRecord",
    "ASRAdversarialCorpusTransformationRecord",
    "build_asr_adversarial_corpus_derivation_plan_v1",
    "build_asr_adversarial_corpus_generation_plan_v1",
    "build_asr_adversarial_corpus_provenance_record_v1",
    "build_asr_adversarial_corpus_rights_record_v1",
    "build_asr_adversarial_corpus_transformation_record_v1",
    "calculate_asr_adversarial_corpus_record_sha256",
    "verify_asr_adversarial_corpus_record_v1",
]

"""Deterministic asset manifest for source-visible adversarial ASR corpora.

The corpus manifest binds real audio asset identities and media metadata to
the exact cases of a sealed adversarial suite.

The manifest does not inspect audio, infer speaker attributes, establish
that a declared acoustic condition is scientifically true, or perform ASR.
Those responsibilities belong to later application/tooling layers.

Provenance and rights records are represented by immutable commitments so
that source, consent/license, and transformation evidence can evolve without
embedding private or unstable external material into the core HVEE artifact.

This artifact is development evidence only. It does not apply qualification
thresholds, issue certification, authorize production use, or modify release
authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.adversarial_evidence import (
    ASR_ADVERSARIAL_EVIDENCE_KEY,
    ASR_ADVERSARIAL_EVIDENCE_VERSION,
    ASRAdversarialCodec,
    ASRAdversarialEvidenceBundle,
    ASRAdversarialSuiteDefinition,
    verify_asr_adversarial_evidence_v1,
)


ASR_ADVERSARIAL_CORPUS_MANIFEST_SCHEMA_VERSION = 1
ASR_ADVERSARIAL_CORPUS_MANIFEST_KEY = (
    "hetren.asr.adversarial-corpus-manifest.en-us"
)
ASR_ADVERSARIAL_CORPUS_MANIFEST_VERSION = "1.0.0"


_IDENTIFIER_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9._-]*$"
)
_VERSION_PATTERN = re.compile(
    r"^[0-9]+\.[0-9]+\.[0-9]+$"
)
_CODEC_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9._-]*$"
)


class ASRAdversarialCorpusProvenanceType(StrEnum):
    """Declared origin class for one corpus audio asset."""

    PURPOSE_RECORDED = "purpose_recorded"
    LICENSED_EXTERNAL = "licensed_external"
    SYNTHETIC_TTS = "synthetic_tts"
    DETERMINISTIC_DERIVATIVE = "deterministic_derivative"


def _require_identifier(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or _IDENTIFIER_PATTERN.fullmatch(value)
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
        or _VERSION_PATTERN.fullmatch(value)
        is None
    ):
        raise HveeContractError(
            f"{name} must be a semantic version"
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


def _require_relative_audio_path(
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\\" in value
    ):
        raise HveeContractError(
            "corpus audio path must be canonical relative POSIX text"
        )

    path = PurePosixPath(value)

    if (
        path.is_absolute()
        or ".." in path.parts
        or "." in path.parts
        or len(path.parts) < 2
    ):
        raise HveeContractError(
            "corpus audio path must remain inside the corpus root"
        )

    if str(path) != value:
        raise HveeContractError(
            "corpus audio path must be canonical"
        )

    return value


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
            "adversarial corpus manifest must contain "
            "valid deterministic JSON"
        ) from exc


def calculate_asr_adversarial_corpus_manifest_sha256(
    payload: object,
) -> str:
    """Hash canonical adversarial corpus manifest material."""

    return hashlib.sha256(
        _canonical_json(payload).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class ASRAdversarialCorpusAsset:
    """One immutable audio asset binding for one sealed suite case."""

    case_id: str
    relative_audio_path: str
    audio_asset_sha256: str
    byte_length: int
    duration_ms: int
    sample_rate_hz: int
    channel_count: int
    codec_name: str
    provenance_type: ASRAdversarialCorpusProvenanceType
    provenance_record_sha256: str
    rights_record_sha256: str
    transformation_record_sha256: str | None = None

    def __post_init__(self) -> None:
        _require_identifier(
            name="corpus case id",
            value=self.case_id,
        )
        _require_relative_audio_path(
            self.relative_audio_path
        )
        _require_sha256(
            name="corpus audio asset",
            value=self.audio_asset_sha256,
        )
        _require_positive_integer(
            name="corpus audio byte length",
            value=self.byte_length,
        )
        _require_positive_integer(
            name="corpus audio duration milliseconds",
            value=self.duration_ms,
        )
        _require_positive_integer(
            name="corpus audio sample rate",
            value=self.sample_rate_hz,
        )
        _require_positive_integer(
            name="corpus audio channel count",
            value=self.channel_count,
        )

        if (
            not isinstance(self.codec_name, str)
            or _CODEC_PATTERN.fullmatch(
                self.codec_name
            )
            is None
        ):
            raise HveeContractError(
                "corpus codec name must be canonical lowercase text"
            )

        if not isinstance(
            self.provenance_type,
            ASRAdversarialCorpusProvenanceType,
        ):
            raise HveeContractError(
                "corpus provenance type must be versioned"
            )

        _require_sha256(
            name="corpus provenance record",
            value=self.provenance_record_sha256,
        )
        _require_sha256(
            name="corpus rights record",
            value=self.rights_record_sha256,
        )

        if (
            self.provenance_type
            == ASRAdversarialCorpusProvenanceType
            .DETERMINISTIC_DERIVATIVE
        ):
            _require_sha256(
                name="corpus transformation record",
                value=self.transformation_record_sha256,
            )
        elif self.transformation_record_sha256 is not None:
            raise HveeContractError(
                "non-derivative corpus asset cannot contain "
                "a transformation record"
            )


@dataclass(frozen=True, slots=True)
class ASRAdversarialCorpusManifestDefinition:
    """Caller-owned corpus-to-suite binding."""

    corpus_id: str
    corpus_version: str
    suite_sha256: str
    assets: tuple[
        ASRAdversarialCorpusAsset,
        ...,
    ]

    def __post_init__(self) -> None:
        _require_identifier(
            name="adversarial corpus id",
            value=self.corpus_id,
        )
        _require_version(
            name="adversarial corpus version",
            value=self.corpus_version,
        )
        _require_sha256(
            name="adversarial corpus suite",
            value=self.suite_sha256,
        )

        if (
            not isinstance(self.assets, tuple)
            or not self.assets
            or not all(
                isinstance(
                    asset,
                    ASRAdversarialCorpusAsset,
                )
                for asset in self.assets
            )
        ):
            raise HveeContractError(
                "adversarial corpus manifest requires assets"
            )

        case_ids = tuple(
            asset.case_id
            for asset in self.assets
        )

        if tuple(sorted(case_ids)) != case_ids:
            raise HveeContractError(
                "adversarial corpus assets must "
                "be ordered by case id"
            )

        if len(case_ids) != len(set(case_ids)):
            raise HveeContractError(
                "adversarial corpus case ids must be unique"
            )

        paths = tuple(
            asset.relative_audio_path
            for asset in self.assets
        )

        if len(paths) != len(set(paths)):
            raise HveeContractError(
                "adversarial corpus audio paths must be unique"
            )

        digests = tuple(
            asset.audio_asset_sha256
            for asset in self.assets
        )

        if len(digests) != len(set(digests)):
            raise HveeContractError(
                "adversarial corpus audio assets must be unique"
            )


@dataclass(frozen=True, slots=True)
class ASRAdversarialCorpusManifestBundle:
    """Deterministic non-certifying adversarial corpus manifest."""

    payload: dict[str, object]
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.payload,
            dict,
        ):
            raise HveeContractError(
                "adversarial corpus manifest payload "
                "must be an object"
            )

        _require_sha256(
            name="adversarial corpus manifest",
            value=self.sha256,
        )

        if (
            calculate_asr_adversarial_corpus_manifest_sha256(
                self.payload
            )
            != self.sha256
        ):
            raise HveeContractError(
                "adversarial corpus manifest SHA-256 "
                "does not match its payload"
            )


def _codec_matches_declared_family(
    *,
    declared: ASRAdversarialCodec,
    codec_name: str,
) -> bool:
    linear_pcm = {
        "pcm_s16le",
        "pcm_s24le",
        "pcm_s32le",
        "pcm_f32le",
    }
    mulaw = {
        "pcm_mulaw",
    }
    alaw = {
        "pcm_alaw",
    }
    lossy = {
        "aac",
        "mp3",
        "opus",
        "vorbis",
    }

    if declared == ASRAdversarialCodec.LINEAR_PCM:
        return codec_name in linear_pcm

    if declared == ASRAdversarialCodec.MULAW:
        return codec_name in mulaw

    if declared == ASRAdversarialCodec.ALAW:
        return codec_name in alaw

    if declared == ASRAdversarialCodec.LOSSY_COMPRESSED:
        return codec_name in lossy

    return False


def _asset_payload(
    asset: ASRAdversarialCorpusAsset,
) -> dict[str, object]:
    return {
        "case_id": asset.case_id,
        "relative_audio_path": (
            asset.relative_audio_path
        ),
        "audio_asset_sha256": (
            asset.audio_asset_sha256
        ),
        "byte_length": asset.byte_length,
        "media": {
            "duration_ms": asset.duration_ms,
            "sample_rate_hz": (
                asset.sample_rate_hz
            ),
            "channel_count": (
                asset.channel_count
            ),
            "codec_name": asset.codec_name,
        },
        "provenance": {
            "type": asset.provenance_type.value,
            "provenance_record_sha256": (
                asset.provenance_record_sha256
            ),
            "rights_record_sha256": (
                asset.rights_record_sha256
            ),
            "transformation_record_sha256": (
                asset.transformation_record_sha256
            ),
        },
    }


def build_asr_adversarial_corpus_manifest_v1(
    definition: ASRAdversarialCorpusManifestDefinition,
    *,
    suite: ASRAdversarialSuiteDefinition,
    suite_evidence: ASRAdversarialEvidenceBundle,
) -> ASRAdversarialCorpusManifestBundle:
    """Bind corpus asset metadata to every sealed suite case exactly."""

    if not isinstance(
        definition,
        ASRAdversarialCorpusManifestDefinition,
    ):
        raise HveeContractError(
            "adversarial corpus manifest requires "
            "ASRAdversarialCorpusManifestDefinition"
        )

    if not isinstance(
        suite,
        ASRAdversarialSuiteDefinition,
    ):
        raise HveeContractError(
            "adversarial corpus manifest requires "
            "ASRAdversarialSuiteDefinition"
        )

    if not isinstance(
        suite_evidence,
        ASRAdversarialEvidenceBundle,
    ):
        raise HveeContractError(
            "adversarial corpus manifest requires "
            "sealed suite evidence"
        )

    verified_suite = (
        verify_asr_adversarial_evidence_v1(
            payload=suite_evidence.payload,
            expected_sha256=suite_evidence.sha256,
            definition=suite,
        )
    )

    if definition.suite_sha256 != verified_suite.sha256:
        raise HveeContractError(
            "adversarial corpus manifest does not bind "
            "the sealed suite"
        )

    expected_case_ids = tuple(
        case.case_id
        for case in suite.cases
    )

    actual_case_ids = tuple(
        asset.case_id
        for asset in definition.assets
    )

    if actual_case_ids != expected_case_ids:
        raise HveeContractError(
            "adversarial corpus manifest must retain "
            "every sealed suite case exactly"
        )

    assets_by_case = {
        asset.case_id: asset
        for asset in definition.assets
    }

    for case in suite.cases:
        asset = assets_by_case[
            case.case_id
        ]

        if (
            asset.audio_asset_sha256
            != case.audio_asset_sha256
        ):
            raise HveeContractError(
                "corpus audio SHA-256 does not match "
                "the sealed adversarial case"
            )

        if (
            asset.sample_rate_hz
            != case.condition.sample_rate_hz
        ):
            raise HveeContractError(
                "corpus sample rate does not match "
                "the sealed adversarial condition"
            )

        if not _codec_matches_declared_family(
            declared=case.condition.codec,
            codec_name=asset.codec_name,
        ):
            raise HveeContractError(
                "corpus codec does not match "
                "the sealed adversarial condition"
            )

    payload: dict[str, object] = {
        "schema_version": (
            ASR_ADVERSARIAL_CORPUS_MANIFEST_SCHEMA_VERSION
        ),
        "artifact": {
            "key": (
                ASR_ADVERSARIAL_CORPUS_MANIFEST_KEY
            ),
            "version": (
                ASR_ADVERSARIAL_CORPUS_MANIFEST_VERSION
            ),
            "type": (
                "source_visible_adversarial_"
                "corpus_manifest"
            ),
        },
        "suite": {
            "key": ASR_ADVERSARIAL_EVIDENCE_KEY,
            "version": (
                ASR_ADVERSARIAL_EVIDENCE_VERSION
            ),
            "sha256": verified_suite.sha256,
        },
        "corpus": {
            "corpus_id": definition.corpus_id,
            "corpus_version": (
                definition.corpus_version
            ),
            "asset_count": len(
                definition.assets
            ),
            "case_ids": list(
                actual_case_ids
            ),
            "assets": [
                _asset_payload(asset)
                for asset in definition.assets
            ],
        },
        "evidence_boundary": {
            "sealed_suite_reverified": True,
            "exact_suite_case_inventory_retained": True,
            "audio_content_present_in_manifest": False,
            "relative_paths_only": True,
            "filesystem_audio_verified_by_manifest": False,
            "media_metadata_measured_by_manifest": False,
            "asset_sha256_bound_to_suite": True,
            "sample_rate_metadata_bound_to_suite": True,
            "codec_family_metadata_bound_to_suite": True,
            "provenance_records_committed_not_embedded": True,
            "rights_records_committed_not_adjudicated": True,
            "acoustic_conditions_measured_by_manifest": False,
            "speaker_attributes_inferred_from_audio": False,
            "declared_speech_variety_is_not_demographic_inference": True,
            "development_evidence_only": True,
            "qualification_threshold_applied": False,
            "certification_issued": False,
            "production_qualified": False,
            "release_enforcement_eligible": False,
            "official_release_verdict_modified": False,
        },
    }

    return ASRAdversarialCorpusManifestBundle(
        payload=payload,
        sha256=(
            calculate_asr_adversarial_corpus_manifest_sha256(
                payload
            )
        ),
    )


def verify_asr_adversarial_corpus_manifest_v1(
    *,
    payload: object,
    expected_sha256: object,
    definition: ASRAdversarialCorpusManifestDefinition,
    suite: ASRAdversarialSuiteDefinition,
    suite_evidence: ASRAdversarialEvidenceBundle,
) -> ASRAdversarialCorpusManifestBundle:
    """Require exact equality with rebuilt v1 corpus evidence."""

    digest = _require_sha256(
        name="expected adversarial corpus manifest",
        value=expected_sha256,
    )

    if not isinstance(
        payload,
        dict,
    ):
        raise HveeContractError(
            "supplied adversarial corpus manifest "
            "must be an object"
        )

    supplied = (
        ASRAdversarialCorpusManifestBundle(
            payload=payload,
            sha256=digest,
        )
    )

    rebuilt = (
        build_asr_adversarial_corpus_manifest_v1(
            definition,
            suite=suite,
            suite_evidence=suite_evidence,
        )
    )

    if (
        supplied.payload != rebuilt.payload
        or supplied.sha256 != rebuilt.sha256
    ):
        raise HveeContractError(
            "adversarial corpus manifest "
            "does not match the v1 definition"
        )

    return rebuilt

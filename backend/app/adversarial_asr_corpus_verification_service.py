"""Filesystem verification for a sealed adversarial ASR corpus.

This application service verifies that actual corpus files match a sealed
Slice G corpus manifest.

The service owns filesystem access and an injected media-probe boundary.
It does not invoke ASR, persist database state, infer speaker attributes,
establish acoustic-condition truth, adjudicate legal rights, apply
qualification thresholds, issue certification, authorize production use,
or modify release authority.

Corpus paths are intentionally stricter than ordinary application artifact
paths: symlinked roots, intermediate components, and asset files are
rejected so a qualification corpus is a stable collection of direct files
rather than mutable filesystem indirections.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol

from app.content_hashing import (
    calculate_content_sha256,
)
from hvee.packs.asr import (
    ASRAdversarialCorpusManifestBundle,
    ASRAdversarialCorpusManifestDefinition,
    ASRAdversarialEvidenceBundle,
    ASRAdversarialSuiteDefinition,
    verify_asr_adversarial_corpus_manifest_v1,
)


ASR_ADVERSARIAL_CORPUS_VERIFICATION_SCHEMA_VERSION = 1
ASR_ADVERSARIAL_CORPUS_VERIFICATION_KEY = (
    "hetren.asr.adversarial-corpus-verification.en-us"
)
ASR_ADVERSARIAL_CORPUS_VERIFICATION_VERSION = "1.0.0"


_IDENTIFIER_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9._-]*$"
)
_CODEC_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9._-]*$"
)


class ASRAdversarialCorpusVerificationServiceError(
    ValueError
):
    """Raised when corpus filesystem verification cannot be trusted."""


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
        raise ASRAdversarialCorpusVerificationServiceError(
            f"{name} must be a canonical lowercase identifier."
        )

    return value


def _require_non_empty_string(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
    ):
        raise ASRAdversarialCorpusVerificationServiceError(
            f"{name} must be non-empty trimmed text."
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
        raise ASRAdversarialCorpusVerificationServiceError(
            f"{name} must be a lowercase SHA-256 digest."
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
        raise ASRAdversarialCorpusVerificationServiceError(
            f"{name} must be a positive integer."
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
        raise ASRAdversarialCorpusVerificationServiceError(
            "corpus verification evidence must contain "
            "deterministic JSON."
        ) from exc


def calculate_asr_adversarial_corpus_verification_sha256(
    payload: object,
) -> str:
    """Hash canonical corpus-verification evidence."""

    return hashlib.sha256(
        _canonical_json(payload).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class ASRAdversarialMeasuredMedia:
    """Normalized media facts returned by one media probe."""

    duration_ms: int
    sample_rate_hz: int
    channel_count: int
    codec_name: str

    def __post_init__(self) -> None:
        _require_positive_integer(
            name="measured media duration milliseconds",
            value=self.duration_ms,
        )
        _require_positive_integer(
            name="measured media sample rate",
            value=self.sample_rate_hz,
        )
        _require_positive_integer(
            name="measured media channel count",
            value=self.channel_count,
        )

        if (
            not isinstance(self.codec_name, str)
            or _CODEC_PATTERN.fullmatch(
                self.codec_name
            )
            is None
        ):
            raise ASRAdversarialCorpusVerificationServiceError(
                "measured media codec name must be "
                "canonical lowercase text."
            )


class ASRAdversarialMediaProbe(Protocol):
    """Injected deterministic media-inspection boundary."""

    probe_key: str
    probe_version: str
    probe_environment_sha256: str

    def probe(
        self,
        audio_path: Path,
    ) -> ASRAdversarialMeasuredMedia:
        ...


@dataclass(frozen=True, slots=True)
class ASRAdversarialCorpusVerifiedAsset:
    """Observed and matched filesystem/media facts for one corpus asset."""

    case_id: str
    relative_audio_path: str
    audio_asset_sha256: str
    byte_length: int
    duration_ms: int
    sample_rate_hz: int
    channel_count: int
    codec_name: str

    def __post_init__(self) -> None:
        _require_identifier(
            name="verified corpus case id",
            value=self.case_id,
        )
        _require_non_empty_string(
            name="verified relative audio path",
            value=self.relative_audio_path,
        )
        _require_sha256(
            name="verified corpus audio asset",
            value=self.audio_asset_sha256,
        )
        _require_positive_integer(
            name="verified corpus byte length",
            value=self.byte_length,
        )
        _require_positive_integer(
            name="verified corpus duration milliseconds",
            value=self.duration_ms,
        )
        _require_positive_integer(
            name="verified corpus sample rate",
            value=self.sample_rate_hz,
        )
        _require_positive_integer(
            name="verified corpus channel count",
            value=self.channel_count,
        )

        if (
            not isinstance(self.codec_name, str)
            or _CODEC_PATTERN.fullmatch(
                self.codec_name
            )
            is None
        ):
            raise ASRAdversarialCorpusVerificationServiceError(
                "verified corpus codec name must be "
                "canonical lowercase text."
            )


@dataclass(frozen=True, slots=True)
class ASRAdversarialCorpusVerificationEvidenceBundle:
    """Deterministic non-certifying filesystem verification evidence."""

    payload: dict[str, object]
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.payload,
            dict,
        ):
            raise ASRAdversarialCorpusVerificationServiceError(
                "corpus verification evidence payload "
                "must be an object."
            )

        _require_sha256(
            name="corpus verification evidence",
            value=self.sha256,
        )

        if (
            calculate_asr_adversarial_corpus_verification_sha256(
                self.payload
            )
            != self.sha256
        ):
            raise ASRAdversarialCorpusVerificationServiceError(
                "corpus verification evidence SHA-256 "
                "does not match its payload."
            )


@dataclass(frozen=True, slots=True)
class ASRAdversarialCorpusVerificationServiceResult:
    """In-memory result of verified corpus inspection."""

    assets: tuple[
        ASRAdversarialCorpusVerifiedAsset,
        ...,
    ]
    evidence: (
        ASRAdversarialCorpusVerificationEvidenceBundle
    )


def _resolve_corpus_root(
    corpus_root: str | Path,
) -> Path:
    if not isinstance(
        corpus_root,
        (str, Path),
    ):
        raise ASRAdversarialCorpusVerificationServiceError(
            "adversarial corpus root is invalid."
        )

    supplied = Path(
        corpus_root
    )

    # Qualification corpus roots are intentionally direct,
    # stable directories rather than symlink aliases.
    if supplied.is_symlink():
        raise ASRAdversarialCorpusVerificationServiceError(
            "adversarial corpus root cannot be a symlink."
        )

    try:
        root = supplied.resolve(
            strict=True
        )
    except (OSError, RuntimeError) as exc:
        raise ASRAdversarialCorpusVerificationServiceError(
            "adversarial corpus root is unavailable."
        ) from exc

    if not root.is_dir():
        raise ASRAdversarialCorpusVerificationServiceError(
            "adversarial corpus root must be a directory."
        )

    return root


def _resolve_asset_path(
    *,
    root: Path,
    relative_audio_path: str,
) -> Path:
    relative = PurePosixPath(
        relative_audio_path
    )

    current = root

    # Slice G already guarantees a canonical relative POSIX path.
    # Recheck every filesystem component for symlink indirection
    # before resolving the final path.
    for part in relative.parts:
        current = current / part

        if current.is_symlink():
            raise ASRAdversarialCorpusVerificationServiceError(
                "adversarial corpus asset path cannot "
                "contain symlinks."
            )

    try:
        resolved = current.resolve(
            strict=True
        )
    except (OSError, RuntimeError) as exc:
        raise ASRAdversarialCorpusVerificationServiceError(
            "adversarial corpus asset is unavailable."
        ) from exc

    if (
        not resolved.is_relative_to(root)
        or not resolved.is_file()
    ):
        raise ASRAdversarialCorpusVerificationServiceError(
            "adversarial corpus asset is unavailable."
        )

    return resolved


def _hash_asset(
    path: Path,
) -> tuple[str, int]:
    try:
        sha256, byte_length = (
            calculate_content_sha256(
                path
            )
        )
    except OSError as exc:
        raise ASRAdversarialCorpusVerificationServiceError(
            "adversarial corpus asset could not be read."
        ) from exc

    if byte_length <= 0:
        raise ASRAdversarialCorpusVerificationServiceError(
            "adversarial corpus asset must not be empty."
        )

    return (
        sha256,
        byte_length,
    )


def _validate_probe(
    probe: object,
) -> tuple[str, str, str]:
    if not callable(
        getattr(
            probe,
            "probe",
            None,
        )
    ):
        raise ASRAdversarialCorpusVerificationServiceError(
            "adversarial media probe is invalid."
        )

    probe_key = _require_identifier(
        name="media probe key",
        value=getattr(
            probe,
            "probe_key",
            None,
        ),
    )

    probe_version = _require_non_empty_string(
        name="media probe version",
        value=getattr(
            probe,
            "probe_version",
            None,
        ),
    )

    probe_environment_sha256 = _require_sha256(
        name="media probe environment",
        value=getattr(
            probe,
            "probe_environment_sha256",
            None,
        ),
    )

    return (
        probe_key,
        probe_version,
        probe_environment_sha256,
    )


def _asset_payload(
    asset: ASRAdversarialCorpusVerifiedAsset,
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
        "measured_media": {
            "duration_ms": asset.duration_ms,
            "sample_rate_hz": (
                asset.sample_rate_hz
            ),
            "channel_count": (
                asset.channel_count
            ),
            "codec_name": asset.codec_name,
        },
        "all_manifest_fields_matched": True,
    }


def verify_asr_adversarial_corpus(
    *,
    corpus_root: str | Path,
    definition: ASRAdversarialCorpusManifestDefinition,
    manifest: ASRAdversarialCorpusManifestBundle,
    suite: ASRAdversarialSuiteDefinition,
    suite_evidence: ASRAdversarialEvidenceBundle,
    media_probe: ASRAdversarialMediaProbe,
) -> ASRAdversarialCorpusVerificationServiceResult:
    """Verify every actual corpus file against its sealed Slice G manifest."""

    probe_key, probe_version, probe_environment_sha256 = (
        _validate_probe(
            media_probe
        )
    )

    verified_manifest = (
        verify_asr_adversarial_corpus_manifest_v1(
            payload=manifest.payload,
            expected_sha256=manifest.sha256,
            definition=definition,
            suite=suite,
            suite_evidence=suite_evidence,
        )
    )

    root = _resolve_corpus_root(
        corpus_root
    )

    verified_assets: list[
        ASRAdversarialCorpusVerifiedAsset
    ] = []

    for asset in definition.assets:
        path = _resolve_asset_path(
            root=root,
            relative_audio_path=(
                asset.relative_audio_path
            ),
        )

        pre_sha256, pre_byte_length = (
            _hash_asset(
                path
            )
        )

        if (
            pre_sha256
            != asset.audio_asset_sha256
            or pre_byte_length
            != asset.byte_length
        ):
            raise ASRAdversarialCorpusVerificationServiceError(
                "adversarial corpus asset content "
                "does not match the sealed manifest."
            )

        measured = media_probe.probe(
            path
        )

        if not isinstance(
            measured,
            ASRAdversarialMeasuredMedia,
        ):
            raise ASRAdversarialCorpusVerificationServiceError(
                "media probe returned an invalid result."
            )

        post_sha256, post_byte_length = (
            _hash_asset(
                path
            )
        )

        if (
            post_sha256 != pre_sha256
            or post_byte_length
            != pre_byte_length
        ):
            raise ASRAdversarialCorpusVerificationServiceError(
                "adversarial corpus asset changed "
                "during media verification."
            )

        if (
            measured.duration_ms
            != asset.duration_ms
        ):
            raise ASRAdversarialCorpusVerificationServiceError(
                "measured corpus duration does not "
                "match the sealed manifest."
            )

        if (
            measured.sample_rate_hz
            != asset.sample_rate_hz
        ):
            raise ASRAdversarialCorpusVerificationServiceError(
                "measured corpus sample rate does not "
                "match the sealed manifest."
            )

        if (
            measured.channel_count
            != asset.channel_count
        ):
            raise ASRAdversarialCorpusVerificationServiceError(
                "measured corpus channel count does not "
                "match the sealed manifest."
            )

        if (
            measured.codec_name
            != asset.codec_name
        ):
            raise ASRAdversarialCorpusVerificationServiceError(
                "measured corpus codec does not "
                "match the sealed manifest."
            )

        verified_assets.append(
            ASRAdversarialCorpusVerifiedAsset(
                case_id=asset.case_id,
                relative_audio_path=(
                    asset.relative_audio_path
                ),
                audio_asset_sha256=(
                    post_sha256
                ),
                byte_length=(
                    post_byte_length
                ),
                duration_ms=(
                    measured.duration_ms
                ),
                sample_rate_hz=(
                    measured.sample_rate_hz
                ),
                channel_count=(
                    measured.channel_count
                ),
                codec_name=(
                    measured.codec_name
                ),
            )
        )

    payload: dict[str, object] = {
        "schema_version": (
            ASR_ADVERSARIAL_CORPUS_VERIFICATION_SCHEMA_VERSION
        ),
        "artifact": {
            "key": (
                ASR_ADVERSARIAL_CORPUS_VERIFICATION_KEY
            ),
            "version": (
                ASR_ADVERSARIAL_CORPUS_VERIFICATION_VERSION
            ),
            "type": (
                "source_visible_adversarial_"
                "corpus_verification"
            ),
        },
        "bindings": {
            "suite_sha256": (
                definition.suite_sha256
            ),
            "corpus_manifest_sha256": (
                verified_manifest.sha256
            ),
        },
        "probe": {
            "key": probe_key,
            "version": probe_version,
            "environment_sha256": (
                probe_environment_sha256
            ),
        },
        "verification": {
            "corpus_id": (
                definition.corpus_id
            ),
            "corpus_version": (
                definition.corpus_version
            ),
            "asset_count": len(
                verified_assets
            ),
            "assets": [
                _asset_payload(asset)
                for asset in verified_assets
            ],
        },
        "verification_boundary": {
            "sealed_corpus_manifest_reverified": True,
            "corpus_root_resolved_strictly": True,
            "corpus_symlinks_rejected": True,
            "filesystem_audio_verified": True,
            "content_hashed_before_media_probe": True,
            "content_rehashed_after_media_probe": True,
            "mutation_during_media_probe_rejected": True,
            "media_metadata_measured": True,
            "all_manifest_fields_matched": True,
            "absolute_filesystem_paths_in_artifact": False,
            "raw_audio_in_artifact": False,
            "acoustic_noise_condition_verified": False,
            "speaking_rate_condition_verified": False,
            "speaker_overlap_condition_verified": False,
            "microphone_class_verified": False,
            "speech_variety_inferred_from_audio": False,
            "rights_record_legal_validity_verified": False,
            "development_evidence_only": True,
            "qualification_threshold_applied": False,
            "certification_issued": False,
            "production_qualified": False,
            "release_enforcement_eligible": False,
            "official_release_verdict_modified": False,
        },
    }

    evidence = (
        ASRAdversarialCorpusVerificationEvidenceBundle(
            payload=payload,
            sha256=(
                calculate_asr_adversarial_corpus_verification_sha256(
                    payload
                )
            ),
        )
    )

    return ASRAdversarialCorpusVerificationServiceResult(
        assets=tuple(
            verified_assets
        ),
        evidence=evidence,
    )

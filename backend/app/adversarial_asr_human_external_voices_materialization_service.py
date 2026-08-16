"""Secure materialization of the controlled VOiCES human ASR evidence.

The controlled VOiCES evidence remains outside the repository. This service
binds the source-visible controlled-capture contract to the independently
frozen external identity chain and verifies the currently retained 66 media
files before publishing trusted in-memory references.

The verification boundary:

- never downloads, copies, rewrites, or extracts source material,
- requires an absolute non-symlink evidence root,
- verifies the frozen external identity-chain commitment,
- requires canonical identity-chain JSON,
- verifies C6 selection, C7 materialization, C8 media verification, and
  C9 rights-evidence commitments,
- cross-binds selection -> manifest -> media report,
- reproduces the frozen media-observation digest,
- requires the exact materialization filesystem allowlist,
- rejects symlink path components and path escapes,
- rehashes every selected media file,
- re-resolves and rehashes commitments before publishing a result,
- returns absolute filesystem paths only in memory.

This service establishes external evidence and current-byte integrity only.
It does not independently verify spoken semantics, execute an ASR model,
adjudicate rights, establish broad human acoustic diversity, authorize
production use, enforce a release, or modify an official release verdict.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.adversarial_human_external_voices_controlled_v1 import (
    ASR_ADVERSARIAL_VOICES_CONTROLLED_SHA256,
    build_asr_adversarial_voices_controlled_v1,
)


_SHA256_PATTERN = re.compile(
    r"^[0-9a-f]{64}$"
)

ASR_ADVERSARIAL_VOICES_IDENTITY_CHAIN_SHA256 = (
    "8634bd69c092335c1c2c20d16ae8c01b"
    "3ee965e02c77938f8b32720db9a7e354"
)


class ASRAdversarialVOiCESMaterializationError(
    ValueError
):
    """Raised when controlled VOiCES evidence cannot be trusted."""


def _require_non_empty_text(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or not value.strip()
    ):
        raise ASRAdversarialVOiCESMaterializationError(
            f"{name} must be non-empty text."
        )

    return value


def _require_sha256(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or _SHA256_PATTERN.fullmatch(
            value
        )
        is None
    ):
        raise ASRAdversarialVOiCESMaterializationError(
            f"{name} must be a lowercase SHA-256."
        )

    return value


def _require_positive_integer(
    *,
    name: str,
    value: object,
) -> int:
    if (
        not isinstance(
            value,
            int,
        )
        or isinstance(
            value,
            bool,
        )
        or value <= 0
    ):
        raise ASRAdversarialVOiCESMaterializationError(
            f"{name} must be a positive integer."
        )

    return value


def _require_relative_path(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or not value
    ):
        raise ASRAdversarialVOiCESMaterializationError(
            f"{name} is invalid."
        )

    relative = PurePosixPath(
        value
    )

    if (
        relative.is_absolute()
        or ".." in relative.parts
        or "." in relative.parts
        or str(relative) != value
    ):
        raise ASRAdversarialVOiCESMaterializationError(
            f"{name} is invalid."
        )

    return value


def _require_source_key(
    *,
    name: str,
    value: object,
) -> tuple[int, int, int]:
    if (
        not isinstance(
            value,
            (list, tuple),
        )
        or len(value) != 3
    ):
        raise ASRAdversarialVOiCESMaterializationError(
            f"{name} is invalid."
        )

    normalized = []

    for part in value:
        if (
            not isinstance(
                part,
                int,
            )
            or isinstance(
                part,
                bool,
            )
            or part < 0
        ):
            raise ASRAdversarialVOiCESMaterializationError(
                f"{name} is invalid."
            )

        normalized.append(
            part
        )

    return (
        normalized[0],
        normalized[1],
        normalized[2],
    )


def _expect_mapping(
    *,
    name: str,
    value: object,
) -> dict[str, object]:
    if not isinstance(
        value,
        dict,
    ):
        raise ASRAdversarialVOiCESMaterializationError(
            f"{name} must be an object."
        )

    return value


def _expect_list(
    *,
    name: str,
    value: object,
) -> list[object]:
    if not isinstance(
        value,
        list,
    ):
        raise ASRAdversarialVOiCESMaterializationError(
            f"{name} must be a list."
        )

    return value


def _canonical_json_bytes(
    value: object,
) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode(
            "utf-8"
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ASRAdversarialVOiCESMaterializationError(
            "VOiCES evidence cannot be canonically serialized."
        ) from exc


@dataclass(
    frozen=True,
    slots=True,
)
class ASRAdversarialVOiCESMaterializationDefinition:
    """Exact commitments required to materialize one VOiCES evidence set."""

    controlled_contract_sha256: str

    identity_chain_relative_path: str
    identity_chain_sha256: str
    identity_chain_byte_length: int

    selection_relative_path: str
    selection_sha256: str
    selection_byte_length: int

    materialization_root_relative_path: str

    materialization_manifest_relative_path: str
    materialization_manifest_sha256: str
    materialization_manifest_byte_length: int

    media_report_relative_path: str
    media_report_sha256: str
    media_report_byte_length: int

    rights_manifest_relative_path: str
    rights_manifest_sha256: str
    rights_manifest_byte_length: int

    source_description_relative_path: str
    source_description_sha256: str
    source_description_byte_length: int

    rights_evidence_relative_path: str
    rights_evidence_sha256: str
    rights_evidence_byte_length: int

    terms_evidence_relative_path: str
    terms_evidence_sha256: str
    terms_evidence_byte_length: int

    observation_sha256: str

    expected_source_file_count: int
    expected_capture_file_count: int
    expected_total_file_count: int
    expected_total_bytes: int
    expected_captures_per_source: int
    expected_constant_angle_degrees: int
    expected_source_keys: tuple[
        tuple[int, int, int],
        ...,
    ]

    expected_docker_image_id: str
    expected_python_version: str
    expected_ffprobe_version: str

    def __post_init__(
        self,
    ) -> None:
        for name, value in (
            (
                "controlled VOiCES contract",
                self.controlled_contract_sha256,
            ),
            (
                "VOiCES identity chain",
                self.identity_chain_sha256,
            ),
            (
                "VOiCES selection",
                self.selection_sha256,
            ),
            (
                "VOiCES materialization manifest",
                self.materialization_manifest_sha256,
            ),
            (
                "VOiCES media report",
                self.media_report_sha256,
            ),
            (
                "VOiCES rights manifest",
                self.rights_manifest_sha256,
            ),
            (
                "VOiCES source description",
                self.source_description_sha256,
            ),
            (
                "VOiCES rights evidence",
                self.rights_evidence_sha256,
            ),
            (
                "VOiCES terms evidence",
                self.terms_evidence_sha256,
            ),
            (
                "VOiCES observation",
                self.observation_sha256,
            ),
        ):
            _require_sha256(
                name=name,
                value=value,
            )

        for name, value in (
            (
                "VOiCES identity chain relative path",
                self.identity_chain_relative_path,
            ),
            (
                "VOiCES selection relative path",
                self.selection_relative_path,
            ),
            (
                "VOiCES materialization root relative path",
                self.materialization_root_relative_path,
            ),
            (
                "VOiCES materialization manifest relative path",
                self.materialization_manifest_relative_path,
            ),
            (
                "VOiCES media report relative path",
                self.media_report_relative_path,
            ),
            (
                "VOiCES rights manifest relative path",
                self.rights_manifest_relative_path,
            ),
            (
                "VOiCES source description relative path",
                self.source_description_relative_path,
            ),
            (
                "VOiCES rights evidence relative path",
                self.rights_evidence_relative_path,
            ),
            (
                "VOiCES terms evidence relative path",
                self.terms_evidence_relative_path,
            ),
        ):
            _require_relative_path(
                name=name,
                value=value,
            )

        for name, value in (
            (
                "VOiCES identity chain byte length",
                self.identity_chain_byte_length,
            ),
            (
                "VOiCES selection byte length",
                self.selection_byte_length,
            ),
            (
                "VOiCES materialization manifest byte length",
                self.materialization_manifest_byte_length,
            ),
            (
                "VOiCES media report byte length",
                self.media_report_byte_length,
            ),
            (
                "VOiCES rights manifest byte length",
                self.rights_manifest_byte_length,
            ),
            (
                "VOiCES source description byte length",
                self.source_description_byte_length,
            ),
            (
                "VOiCES rights evidence byte length",
                self.rights_evidence_byte_length,
            ),
            (
                "VOiCES terms evidence byte length",
                self.terms_evidence_byte_length,
            ),
            (
                "expected VOiCES source file count",
                self.expected_source_file_count,
            ),
            (
                "expected VOiCES capture file count",
                self.expected_capture_file_count,
            ),
            (
                "expected VOiCES total file count",
                self.expected_total_file_count,
            ),
            (
                "expected VOiCES total byte length",
                self.expected_total_bytes,
            ),
            (
                "expected VOiCES captures per source",
                self.expected_captures_per_source,
            ),
            (
                "expected VOiCES constant angle",
                self.expected_constant_angle_degrees,
            ),
        ):
            _require_positive_integer(
                name=name,
                value=value,
            )

        if (
            self.expected_source_file_count
            + self.expected_capture_file_count
            != self.expected_total_file_count
        ):
            raise ASRAdversarialVOiCESMaterializationError(
                "expected VOiCES file counts are inconsistent."
            )

        if (
            not isinstance(
                self.expected_source_keys,
                tuple,
            )
            or len(
                self.expected_source_keys
            )
            != self.expected_source_file_count
        ):
            raise ASRAdversarialVOiCESMaterializationError(
                "expected VOiCES source keys are invalid."
            )

        normalized_source_keys = tuple(
            _require_source_key(
                name="expected VOiCES source key",
                value=value,
            )
            for value in self.expected_source_keys
        )

        if (
            len(
                set(
                    normalized_source_keys
                )
            )
            != len(
                normalized_source_keys
            )
        ):
            raise ASRAdversarialVOiCESMaterializationError(
                "expected VOiCES source keys must be unique."
            )

        for name, value in (
            (
                "expected VOiCES Docker image id",
                self.expected_docker_image_id,
            ),
            (
                "expected VOiCES Python version",
                self.expected_python_version,
            ),
            (
                "expected VOiCES ffprobe version",
                self.expected_ffprobe_version,
            ),
        ):
            _require_non_empty_text(
                name=name,
                value=value,
            )


@dataclass(
    frozen=True,
    slots=True,
)
class ASRAdversarialVOiCESMaterializedMedia:
    """One verified current external VOiCES media reference."""

    relative_path: str
    path: Path
    sha256: str
    byte_length: int
    kind: str
    source_key: tuple[int, int, int]
    codec_name: str
    sample_rate_hz: int
    channel_count: int
    bits_per_sample: int
    sample_width_bytes: int
    sample_count: int
    duration_seconds: str

    def __post_init__(
        self,
    ) -> None:
        _require_relative_path(
            name="materialized VOiCES media relative path",
            value=self.relative_path,
        )

        if (
            not isinstance(
                self.path,
                Path,
            )
            or not self.path.is_absolute()
        ):
            raise ASRAdversarialVOiCESMaterializationError(
                "materialized VOiCES media path "
                "must be an absolute Path."
            )

        _require_sha256(
            name="materialized VOiCES media",
            value=self.sha256,
        )

        for name, value in (
            (
                "materialized VOiCES media byte length",
                self.byte_length,
            ),
            (
                "materialized VOiCES sample rate",
                self.sample_rate_hz,
            ),
            (
                "materialized VOiCES channel count",
                self.channel_count,
            ),
            (
                "materialized VOiCES bits per sample",
                self.bits_per_sample,
            ),
            (
                "materialized VOiCES sample width",
                self.sample_width_bytes,
            ),
            (
                "materialized VOiCES sample count",
                self.sample_count,
            ),
        ):
            _require_positive_integer(
                name=name,
                value=value,
            )

        if self.kind not in {
            "source",
            "capture",
        }:
            raise ASRAdversarialVOiCESMaterializationError(
                "materialized VOiCES media kind is invalid."
            )

        _require_source_key(
            name="materialized VOiCES source key",
            value=self.source_key,
        )

        _require_non_empty_text(
            name="materialized VOiCES codec",
            value=self.codec_name,
        )

        _require_non_empty_text(
            name="materialized VOiCES duration",
            value=self.duration_seconds,
        )


@dataclass(
    frozen=True,
    slots=True,
)
class ASRAdversarialVOiCESMaterializedEvidence:
    """Trusted in-memory reference to the complete controlled evidence set."""

    controlled_contract_sha256: str
    identity_chain_sha256: str
    selection_sha256: str
    materialization_manifest_sha256: str
    media_report_sha256: str
    observation_sha256: str
    rights_manifest_sha256: str
    media: tuple[
        ASRAdversarialVOiCESMaterializedMedia,
        ...
    ]

    development_evidence_only: bool = True
    spoken_content_independently_verified: bool = False
    asr_execution_verified: bool = False
    rights_adjudicated: bool = False
    human_acoustic_diversity_established: bool = False
    microphone_type_diversity_established: bool = False
    live_human_in_room_diversity_established: bool = False
    production_qualified: bool = False
    release_enforcement_eligible: bool = False
    official_release_verdict_modified: bool = False

    def __post_init__(
        self,
    ) -> None:
        for name, value in (
            (
                "materialized VOiCES controlled contract",
                self.controlled_contract_sha256,
            ),
            (
                "materialized VOiCES identity chain",
                self.identity_chain_sha256,
            ),
            (
                "materialized VOiCES selection",
                self.selection_sha256,
            ),
            (
                "materialized VOiCES manifest",
                self.materialization_manifest_sha256,
            ),
            (
                "materialized VOiCES media report",
                self.media_report_sha256,
            ),
            (
                "materialized VOiCES observation",
                self.observation_sha256,
            ),
            (
                "materialized VOiCES rights manifest",
                self.rights_manifest_sha256,
            ),
        ):
            _require_sha256(
                name=name,
                value=value,
            )

        if (
            not isinstance(
                self.media,
                tuple,
            )
            or not self.media
            or any(
                not isinstance(
                    value,
                    ASRAdversarialVOiCESMaterializedMedia,
                )
                for value in self.media
            )
        ):
            raise ASRAdversarialVOiCESMaterializationError(
                "materialized VOiCES media collection is invalid."
            )

        authority = {
            "development_evidence_only": (
                self.development_evidence_only
            ),
            "spoken_content_independently_verified": (
                self.spoken_content_independently_verified
            ),
            "asr_execution_verified": (
                self.asr_execution_verified
            ),
            "rights_adjudicated": (
                self.rights_adjudicated
            ),
            "human_acoustic_diversity_established": (
                self.human_acoustic_diversity_established
            ),
            "microphone_type_diversity_established": (
                self.microphone_type_diversity_established
            ),
            "live_human_in_room_diversity_established": (
                self.live_human_in_room_diversity_established
            ),
            "production_qualified": (
                self.production_qualified
            ),
            "release_enforcement_eligible": (
                self.release_enforcement_eligible
            ),
            "official_release_verdict_modified": (
                self.official_release_verdict_modified
            ),
        }

        if authority[
            "development_evidence_only"
        ] is not True:
            raise ASRAdversarialVOiCESMaterializationError(
                "materialized VOiCES evidence must remain "
                "development-evidence-only."
            )

        for field_name in (
            "spoken_content_independently_verified",
            "asr_execution_verified",
            "rights_adjudicated",
            "human_acoustic_diversity_established",
            "microphone_type_diversity_established",
            "live_human_in_room_diversity_established",
            "production_qualified",
            "release_enforcement_eligible",
            "official_release_verdict_modified",
        ):
            if authority[
                field_name
            ] is not False:
                raise ASRAdversarialVOiCESMaterializationError(
                    "materialized VOiCES evidence cannot "
                    f"escalate {field_name}."
                )


def _resolve_evidence_root(
    evidence_root: str | Path,
) -> Path:
    if not isinstance(
        evidence_root,
        (str, Path),
    ):
        raise ASRAdversarialVOiCESMaterializationError(
            "VOiCES evidence root is invalid."
        )

    supplied = Path(
        evidence_root
    )

    if not supplied.is_absolute():
        raise ASRAdversarialVOiCESMaterializationError(
            "VOiCES evidence root must be absolute."
        )

    if supplied.is_symlink():
        raise ASRAdversarialVOiCESMaterializationError(
            "VOiCES evidence root cannot be a symlink."
        )

    try:
        resolved = supplied.resolve(
            strict=True
        )
    except (
        OSError,
        RuntimeError,
    ) as exc:
        raise ASRAdversarialVOiCESMaterializationError(
            "VOiCES evidence root is unavailable."
        ) from exc

    if not resolved.is_dir():
        raise ASRAdversarialVOiCESMaterializationError(
            "VOiCES evidence root must be a directory."
        )

    return resolved


def _resolve_relative_file(
    *,
    root: Path,
    relative_path: str,
    name: str,
) -> Path:
    relative = PurePosixPath(
        _require_relative_path(
            name=f"{name} relative path",
            value=relative_path,
        )
    )

    current = root

    for part in relative.parts:
        current = (
            current
            / part
        )

        if current.is_symlink():
            raise ASRAdversarialVOiCESMaterializationError(
                f"{name} path cannot contain symlinks."
            )

    try:
        resolved = current.resolve(
            strict=True
        )
    except (
        OSError,
        RuntimeError,
    ) as exc:
        raise ASRAdversarialVOiCESMaterializationError(
            f"{name} is unavailable."
        ) from exc

    if (
        not resolved.is_relative_to(
            root
        )
        or not resolved.is_file()
    ):
        raise ASRAdversarialVOiCESMaterializationError(
            f"{name} is unavailable."
        )

    return resolved


def _resolve_relative_directory(
    *,
    root: Path,
    relative_path: str,
    name: str,
) -> Path:
    relative = PurePosixPath(
        _require_relative_path(
            name=f"{name} relative path",
            value=relative_path,
        )
    )

    current = root

    for part in relative.parts:
        current = (
            current
            / part
        )

        if current.is_symlink():
            raise ASRAdversarialVOiCESMaterializationError(
                f"{name} path cannot contain symlinks."
            )

    try:
        resolved = current.resolve(
            strict=True
        )
    except (
        OSError,
        RuntimeError,
    ) as exc:
        raise ASRAdversarialVOiCESMaterializationError(
            f"{name} is unavailable."
        ) from exc

    if (
        not resolved.is_relative_to(
            root
        )
        or not resolved.is_dir()
    ):
        raise ASRAdversarialVOiCESMaterializationError(
            f"{name} is unavailable."
        )

    return resolved


def _read_file(
    *,
    path: Path,
    name: str,
) -> tuple[
    bytes,
    str,
    int,
]:
    digest = hashlib.sha256()
    pieces = []
    byte_length = 0

    try:
        with path.open(
            "rb"
        ) as stream:
            while True:
                chunk = stream.read(
                    1024 * 1024
                )

                if not chunk:
                    break

                pieces.append(
                    chunk
                )
                digest.update(
                    chunk
                )
                byte_length += len(
                    chunk
                )
    except OSError as exc:
        raise ASRAdversarialVOiCESMaterializationError(
            f"{name} could not be read."
        ) from exc

    if byte_length <= 0:
        raise ASRAdversarialVOiCESMaterializationError(
            f"{name} must not be empty."
        )

    return (
        b"".join(
            pieces
        ),
        digest.hexdigest(),
        byte_length,
    )


def _hash_file(
    *,
    path: Path,
    name: str,
) -> tuple[
    str,
    int,
]:
    digest = hashlib.sha256()
    byte_length = 0

    try:
        with path.open(
            "rb"
        ) as stream:
            while True:
                chunk = stream.read(
                    1024 * 1024
                )

                if not chunk:
                    break

                digest.update(
                    chunk
                )
                byte_length += len(
                    chunk
                )
    except OSError as exc:
        raise ASRAdversarialVOiCESMaterializationError(
            f"{name} could not be read."
        ) from exc

    if byte_length <= 0:
        raise ASRAdversarialVOiCESMaterializationError(
            f"{name} must not be empty."
        )

    return (
        digest.hexdigest(),
        byte_length,
    )


def _file_fingerprint(
    *,
    path: Path,
    name: str,
) -> tuple[
    int,
    int,
    int,
    int,
    int,
]:
    """Capture filesystem identity used by publication barriers."""

    try:
        metadata = path.stat()
    except OSError as exc:
        raise ASRAdversarialVOiCESMaterializationError(
            f"{name} filesystem identity could not be read."
        ) from exc

    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _load_committed_json(
    *,
    root: Path,
    relative_path: str,
    expected_sha256: str,
    expected_byte_length: int,
    name: str,
    require_canonical: bool = False,
) -> tuple[
    Path,
    dict[str, object],
]:
    path = _resolve_relative_file(
        root=root,
        relative_path=relative_path,
        name=name,
    )

    (
        raw,
        observed_sha256,
        observed_byte_length,
    ) = _read_file(
        path=path,
        name=name,
    )

    if (
        observed_sha256
        != expected_sha256
        or observed_byte_length
        != expected_byte_length
    ):
        raise ASRAdversarialVOiCESMaterializationError(
            f"{name} does not match its frozen commitment."
        )

    try:
        decoded = raw.decode(
            "utf-8",
            errors="strict",
        )
        payload = json.loads(
            decoded
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise ASRAdversarialVOiCESMaterializationError(
            f"{name} is not valid UTF-8 JSON."
        ) from exc

    payload = _expect_mapping(
        name=name,
        value=payload,
    )

    if (
        require_canonical
        and raw
        != _canonical_json_bytes(
            payload
        )
    ):
        raise ASRAdversarialVOiCESMaterializationError(
            f"{name} is not canonical JSON."
        )

    return (
        path,
        payload,
    )


def _expected_parent_directories(
    relative_files: set[str],
) -> set[str]:
    directories = set()

    for relative_path in relative_files:
        parent = PurePosixPath(
            relative_path
        ).parent

        while str(
            parent
        ) != ".":
            directories.add(
                parent.as_posix()
            )
            parent = parent.parent

    return directories


def _verify_exact_materialization_tree(
    *,
    materialization_root: Path,
    expected_media_paths: set[str],
) -> None:
    expected_files = (
        set(
            expected_media_paths
        )
        | {
            "manifest.json",
        }
    )

    expected_directories = (
        _expected_parent_directories(
            expected_files
        )
    )

    regular_files = set()
    directories = set()
    symlinks = set()
    other_entries = set()

    try:
        entries = list(
            materialization_root.rglob(
                "*"
            )
        )
    except OSError as exc:
        raise ASRAdversarialVOiCESMaterializationError(
            "VOiCES materialization tree could not be inspected."
        ) from exc

    for entry in entries:
        try:
            relative_path = (
                entry.relative_to(
                    materialization_root
                ).as_posix()
            )

            if entry.is_symlink():
                symlinks.add(
                    relative_path
                )
                continue

            if entry.is_file():
                regular_files.add(
                    relative_path
                )

            elif entry.is_dir():
                directories.add(
                    relative_path
                )

            else:
                other_entries.add(
                    relative_path
                )
        except OSError as exc:
            raise ASRAdversarialVOiCESMaterializationError(
                "VOiCES materialization tree changed "
                "during inspection."
            ) from exc

    if symlinks:
        raise ASRAdversarialVOiCESMaterializationError(
            "VOiCES materialization tree cannot contain symlinks."
        )

    if other_entries:
        raise ASRAdversarialVOiCESMaterializationError(
            "VOiCES materialization tree contains "
            "unsupported filesystem entries."
        )

    if regular_files != expected_files:
        raise ASRAdversarialVOiCESMaterializationError(
            "VOiCES materialization file allowlist changed."
        )

    if directories != expected_directories:
        raise ASRAdversarialVOiCESMaterializationError(
            "VOiCES materialization directory allowlist changed."
        )


def _media_records_by_path(
    *,
    records: object,
    collection_name: str,
) -> dict[
    str,
    dict[str, object],
]:
    values = _expect_list(
        name=collection_name,
        value=records,
    )

    result = {}

    for value in values:
        record = _expect_mapping(
            name=f"{collection_name} record",
            value=value,
        )

        relative_path = _require_relative_path(
            name=f"{collection_name} media path",
            value=record.get(
                "relative_path"
            ),
        )

        if relative_path in result:
            raise ASRAdversarialVOiCESMaterializationError(
                f"{collection_name} contains duplicate media paths."
            )

        result[
            relative_path
        ] = record

    return result


def _selection_media_paths(
    *,
    selection: dict[str, object],
    definition: ASRAdversarialVOiCESMaterializationDefinition,
) -> set[str]:
    summary = _expect_mapping(
        name="VOiCES selection summary",
        value=selection.get(
            "selection"
        ),
    )

    if (
        summary.get(
            "partition"
        )
        != "train"
    ):
        raise ASRAdversarialVOiCESMaterializationError(
            "VOiCES controlled selection partition changed."
        )

    selected_source_count = (
        _require_positive_integer(
            name="VOiCES selected source count",
            value=summary.get(
                "selected_source_count"
            ),
        )
    )

    selected_capture_count = (
        _require_positive_integer(
            name="VOiCES selected capture count",
            value=summary.get(
                "selected_capture_count"
            ),
        )
    )

    captures_per_source = (
        _require_positive_integer(
            name="VOiCES captures per source",
            value=summary.get(
                "captures_per_source"
            ),
        )
    )

    required_angle = (
        _require_positive_integer(
            name="VOiCES required constant angle",
            value=summary.get(
                "required_constant_angle_degrees"
            ),
        )
    )

    if (
        selected_source_count
        != definition.expected_source_file_count
        or selected_capture_count
        != definition.expected_capture_file_count
        or captures_per_source
        != definition.expected_captures_per_source
        or required_angle
        != definition.expected_constant_angle_degrees
    ):
        raise ASRAdversarialVOiCESMaterializationError(
            "VOiCES controlled selection summary changed."
        )

    source_keys = tuple(
        _require_source_key(
            name="VOiCES selected source key",
            value=value,
        )
        for value in _expect_list(
            name="VOiCES selected source keys",
            value=summary.get(
                "selected_source_keys"
            ),
        )
    )

    if source_keys != (
        definition.expected_source_keys
    ):
        raise ASRAdversarialVOiCESMaterializationError(
            "VOiCES controlled source selection changed."
        )

    sources = _expect_list(
        name="VOiCES selected sources",
        value=selection.get(
            "sources"
        ),
    )

    captures = _expect_list(
        name="VOiCES selected captures",
        value=selection.get(
            "captures"
        ),
    )

    if (
        len(
            sources
        )
        != definition.expected_source_file_count
        or len(
            captures
        )
        != definition.expected_capture_file_count
    ):
        raise ASRAdversarialVOiCESMaterializationError(
            "VOiCES selection population changed."
        )

    paths = set()
    capture_counts = Counter()

    for value in sources:
        source = _expect_mapping(
            name="VOiCES source record",
            value=value,
        )

        source_key = _require_source_key(
            name="VOiCES source record key",
            value=source.get(
                "source_key"
            ),
        )

        if source_key not in (
            definition.expected_source_keys
        ):
            raise ASRAdversarialVOiCESMaterializationError(
                "VOiCES source record is outside "
                "the controlled selection."
            )

        source_capture_count = (
            _require_positive_integer(
                name="VOiCES source capture count",
                value=source.get(
                    "capture_count"
                ),
            )
        )

        source_angle = (
            _require_positive_integer(
                name="VOiCES source constant angle",
                value=source.get(
                    "constant_angle_degrees"
                ),
            )
        )

        if (
            source_capture_count
            != definition.expected_captures_per_source
            or source_angle
            != definition.expected_constant_angle_degrees
        ):
            raise ASRAdversarialVOiCESMaterializationError(
                "VOiCES source capture commitment changed."
            )

        relative_path = _require_relative_path(
            name="VOiCES source path",
            value=source.get(
                "source_path"
            ),
        )

        if relative_path in paths:
            raise ASRAdversarialVOiCESMaterializationError(
                "VOiCES selection contains duplicate paths."
            )

        paths.add(
            relative_path
        )

    observed_capture_lattices = {
        source_key: set()
        for source_key in definition.expected_source_keys
    }

    for value in captures:
        capture = _expect_mapping(
            name="VOiCES capture record",
            value=value,
        )

        source_key = _require_source_key(
            name="VOiCES capture source key",
            value=capture.get(
                "source_key"
            ),
        )

        if source_key not in (
            definition.expected_source_keys
        ):
            raise ASRAdversarialVOiCESMaterializationError(
                "VOiCES capture is outside "
                "the controlled selection."
            )

        capture_angle = (
            _require_positive_integer(
                name="VOiCES capture angle",
                value=capture.get(
                    "degrees"
                ),
            )
        )

        if (
            capture_angle
            != definition.expected_constant_angle_degrees
        ):
            raise ASRAdversarialVOiCESMaterializationError(
                "VOiCES capture angle changed."
            )

        room = _require_non_empty_text(
            name="VOiCES capture room",
            value=capture.get(
                "room"
            ),
        )

        distractor = _require_non_empty_text(
            name="VOiCES capture distractor",
            value=capture.get(
                "distractor"
            ),
        )

        mic_id = _require_positive_integer(
            name="VOiCES capture microphone id",
            value=capture.get(
                "mic_id"
            ),
        )

        lattice_key = (
            room,
            distractor,
            mic_id,
        )

        observed_capture_lattices[
            source_key
        ].add(
            lattice_key
        )

        capture_counts[
            source_key
        ] += 1

        relative_path = _require_relative_path(
            name="VOiCES capture path",
            value=capture.get(
                "filename"
            ),
        )

        if relative_path in paths:
            raise ASRAdversarialVOiCESMaterializationError(
                "VOiCES selection contains duplicate paths."
            )

        paths.add(
            relative_path
        )

    for source_key in (
        definition.expected_source_keys
    ):
        if (
            capture_counts[
                source_key
            ]
            != definition.expected_captures_per_source
            or len(
                observed_capture_lattices[
                    source_key
                ]
            )
            != definition.expected_captures_per_source
        ):
            raise ASRAdversarialVOiCESMaterializationError(
                "VOiCES controlled capture lattice changed."
            )

    if len(
        paths
    ) != definition.expected_total_file_count:
        raise ASRAdversarialVOiCESMaterializationError(
            "VOiCES selection media count changed."
        )

    return paths


def _verify_chain(
    *,
    chain: dict[str, object],
    definition: ASRAdversarialVOiCESMaterializationDefinition,
) -> None:
    artifact = _expect_mapping(
        name="VOiCES identity-chain artifact",
        value=chain.get(
            "artifact"
        ),
    )

    if artifact != {
        "key": (
            "hetren.asr.voices-controlled-"
            "capture-identity-chain"
        ),
        "schema_version": 1,
        "version": "1.0.0",
    }:
        raise ASRAdversarialVOiCESMaterializationError(
            "VOiCES identity-chain artifact identity changed."
        )

    controlled = _expect_mapping(
        name="VOiCES identity-chain controlled selection",
        value=chain.get(
            "controlled_selection"
        ),
    )

    materialization = _expect_mapping(
        name="VOiCES identity-chain materialization",
        value=chain.get(
            "materialization"
        ),
    )

    media = _expect_mapping(
        name="VOiCES identity-chain media verification",
        value=chain.get(
            "media_verification"
        ),
    )

    rights = _expect_mapping(
        name="VOiCES identity-chain rights evidence",
        value=chain.get(
            "rights_evidence"
        ),
    )

    if (
        controlled.get(
            "sha256"
        )
        != definition.selection_sha256
        or materialization.get(
            "manifest_sha256"
        )
        != definition.materialization_manifest_sha256
        or media.get(
            "report_sha256"
        )
        != definition.media_report_sha256
        or media.get(
            "observation_sha256"
        )
        != definition.observation_sha256
        or rights.get(
            "manifest_sha256"
        )
        != definition.rights_manifest_sha256
    ):
        raise ASRAdversarialVOiCESMaterializationError(
            "VOiCES identity chain does not bind "
            "the expected evidence artifacts."
        )

    if (
        media.get(
            "docker_image_id"
        )
        != definition.expected_docker_image_id
        or media.get(
            "python_version"
        )
        != definition.expected_python_version
        or media.get(
            "ffprobe_version"
        )
        != definition.expected_ffprobe_version
    ):
        raise ASRAdversarialVOiCESMaterializationError(
            "VOiCES identity-chain toolchain changed."
        )

    boundary = _expect_mapping(
        name="VOiCES identity-chain evidence boundary",
        value=chain.get(
            "evidence_boundary"
        ),
    )

    positive_fields = (
        "external_development_evidence",
        "base_train_test_source_disjointness_verified",
        "controlled_capture_lattice_verified",
        "current_selected_media_bytes_verified",
        "media_probe_verified",
        "source_declared_transcripts_bound",
    )

    negative_fields = (
        "raw_audio_committed_to_repository",
        "spoken_content_independently_verified",
        "asr_execution_verified",
        "live_human_in_room_diversity_established",
        "microphone_type_diversity_established",
        "human_acoustic_diversity_established",
        "rights_adjudicated",
        "production_qualification",
        "release_enforcement",
        "official_release_verdict",
    )

    for field_name in positive_fields:
        if boundary.get(
            field_name
        ) is not True:
            raise ASRAdversarialVOiCESMaterializationError(
                "VOiCES identity-chain positive evidence "
                f"boundary changed: {field_name}."
            )

    for field_name in negative_fields:
        if boundary.get(
            field_name
        ) is not False:
            raise ASRAdversarialVOiCESMaterializationError(
                "VOiCES identity-chain authority "
                f"boundary changed: {field_name}."
            )


def _verify_cross_bindings(
    *,
    selection: dict[str, object],
    manifest: dict[str, object],
    report: dict[str, object],
    definition: ASRAdversarialVOiCESMaterializationDefinition,
) -> tuple[
    dict[str, dict[str, object]],
    dict[str, dict[str, object]],
]:
    selection_paths = _selection_media_paths(
        selection=selection,
        definition=definition,
    )

    manifest_selection = _expect_mapping(
        name="VOiCES manifest selection",
        value=manifest.get(
            "selection"
        ),
    )

    manifest_selection_sha256 = (
        _require_sha256(
            name="VOiCES manifest selection",
            value=manifest_selection.get(
                "sha256"
            ),
        )
    )

    manifest_selection_bytes = (
        _require_positive_integer(
            name="VOiCES manifest selection byte length",
            value=manifest_selection.get(
                "bytes"
            ),
        )
    )

    if (
        manifest_selection_sha256
        != definition.selection_sha256
        or manifest_selection_bytes
        != definition.selection_byte_length
    ):
        raise ASRAdversarialVOiCESMaterializationError(
            "VOiCES manifest selection binding changed."
        )

    materialization = _expect_mapping(
        name="VOiCES manifest materialization summary",
        value=manifest.get(
            "materialization"
        ),
    )

    manifest_source_file_count = (
        _require_positive_integer(
            name="VOiCES manifest source file count",
            value=materialization.get(
                "source_file_count"
            ),
        )
    )

    manifest_capture_file_count = (
        _require_positive_integer(
            name="VOiCES manifest capture file count",
            value=materialization.get(
                "capture_file_count"
            ),
        )
    )

    manifest_total_file_count = (
        _require_positive_integer(
            name="VOiCES manifest total file count",
            value=materialization.get(
                "total_file_count"
            ),
        )
    )

    manifest_total_bytes = (
        _require_positive_integer(
            name="VOiCES manifest total byte length",
            value=materialization.get(
                "total_bytes"
            ),
        )
    )

    if (
        manifest_source_file_count
        != definition.expected_source_file_count
        or manifest_capture_file_count
        != definition.expected_capture_file_count
        or manifest_total_file_count
        != definition.expected_total_file_count
        or manifest_total_bytes
        != definition.expected_total_bytes
    ):
        raise ASRAdversarialVOiCESMaterializationError(
            "VOiCES manifest materialization summary changed."
        )

    manifest_records = _media_records_by_path(
        records=manifest.get(
            "files"
        ),
        collection_name="VOiCES manifest files",
    )

    observations = _expect_list(
        name="VOiCES media observations",
        value=report.get(
            "observations"
        ),
    )

    report_records = _media_records_by_path(
        records=observations,
        collection_name="VOiCES media observations",
    )

    if (
        selection_paths
        != set(
            manifest_records
        )
        or set(
            manifest_records
        )
        != set(
            report_records
        )
    ):
        raise ASRAdversarialVOiCESMaterializationError(
            "VOiCES evidence media path sets disagree."
        )

    inputs = _expect_mapping(
        name="VOiCES media report inputs",
        value=report.get(
            "inputs"
        ),
    )

    if (
        inputs.get(
            "selection_sha256"
        )
        != definition.selection_sha256
        or inputs.get(
            "materialization_manifest_sha256"
        )
        != definition.materialization_manifest_sha256
    ):
        raise ASRAdversarialVOiCESMaterializationError(
            "VOiCES media report input binding changed."
        )

    verification = _expect_mapping(
        name="VOiCES media report verification",
        value=report.get(
            "verification"
        ),
    )

    report_source_file_count = (
        _require_positive_integer(
            name="VOiCES report source file count",
            value=verification.get(
                "source_file_count"
            ),
        )
    )

    report_capture_file_count = (
        _require_positive_integer(
            name="VOiCES report capture file count",
            value=verification.get(
                "capture_file_count"
            ),
        )
    )

    report_verified_file_count = (
        _require_positive_integer(
            name="VOiCES report verified file count",
            value=verification.get(
                "verified_file_count"
            ),
        )
    )

    report_total_bytes = (
        _require_positive_integer(
            name="VOiCES report total byte length",
            value=verification.get(
                "total_bytes"
            ),
        )
    )

    report_observation_sha256 = (
        _require_sha256(
            name="VOiCES report observation",
            value=verification.get(
                "observation_sha256"
            ),
        )
    )

    if (
        report_source_file_count
        != definition.expected_source_file_count
        or report_capture_file_count
        != definition.expected_capture_file_count
        or report_verified_file_count
        != definition.expected_total_file_count
        or report_total_bytes
        != definition.expected_total_bytes
        or verification.get(
            "controlled_condition_lattice_verified"
        )
        is not True
        or verification.get(
            "post_probe_hash_stability"
        )
        is not True
        or report_observation_sha256
        != definition.observation_sha256
    ):
        raise ASRAdversarialVOiCESMaterializationError(
            "VOiCES media verification summary changed."
        )

    observation_sha256 = hashlib.sha256(
        _canonical_json_bytes(
            observations
        )
    ).hexdigest()

    if (
        observation_sha256
        != definition.observation_sha256
    ):
        raise ASRAdversarialVOiCESMaterializationError(
            "VOiCES media observation identity changed."
        )

    for relative_path in sorted(
        selection_paths
    ):
        manifest_record = (
            manifest_records[
                relative_path
            ]
        )

        report_record = (
            report_records[
                relative_path
            ]
        )

        manifest_sha256 = _require_sha256(
            name="VOiCES manifest media",
            value=manifest_record.get(
                "sha256"
            ),
        )

        report_sha256 = _require_sha256(
            name="VOiCES report media",
            value=report_record.get(
                "sha256"
            ),
        )

        manifest_bytes = (
            _require_positive_integer(
                name="VOiCES manifest media byte length",
                value=manifest_record.get(
                    "bytes"
                ),
            )
        )

        report_bytes = (
            _require_positive_integer(
                name="VOiCES report media byte length",
                value=report_record.get(
                    "bytes"
                ),
            )
        )

        manifest_kind = _require_non_empty_text(
            name="VOiCES manifest media kind",
            value=manifest_record.get(
                "kind"
            ),
        )

        report_kind = _require_non_empty_text(
            name="VOiCES report media kind",
            value=report_record.get(
                "kind"
            ),
        )

        if (
            manifest_kind
            not in {
                "source",
                "capture",
            }
            or report_kind
            not in {
                "source",
                "capture",
            }
        ):
            raise ASRAdversarialVOiCESMaterializationError(
                "VOiCES media kind changed."
            )

        manifest_source_key = (
            _require_source_key(
                name="VOiCES manifest media source key",
                value=manifest_record.get(
                    "source_key"
                ),
            )
        )

        report_source_key = (
            _require_source_key(
                name="VOiCES report media source key",
                value=report_record.get(
                    "source_key"
                ),
            )
        )

        if (
            manifest_sha256
            != report_sha256
            or manifest_bytes
            != report_bytes
            or manifest_kind
            != report_kind
            or manifest_source_key
            != report_source_key
        ):
            raise ASRAdversarialVOiCESMaterializationError(
                "VOiCES manifest and media report disagree "
                f"for {relative_path}."
            )

        codec_name = _require_non_empty_text(
            name="VOiCES media codec",
            value=report_record.get(
                "codec_name"
            ),
        )

        sample_rate_hz = (
            _require_positive_integer(
                name="VOiCES media sample rate",
                value=report_record.get(
                    "sample_rate_hz"
                ),
            )
        )

        channel_count = (
            _require_positive_integer(
                name="VOiCES media channel count",
                value=report_record.get(
                    "channels"
                ),
            )
        )

        bits_per_sample = (
            _require_positive_integer(
                name="VOiCES media bits per sample",
                value=report_record.get(
                    "bits_per_sample"
                ),
            )
        )

        sample_width_bytes = (
            _require_positive_integer(
                name="VOiCES media sample width",
                value=report_record.get(
                    "sample_width_bytes"
                ),
            )
        )

        sample_count = _require_positive_integer(
            name="VOiCES media sample count",
            value=report_record.get(
                "sample_count"
            ),
        )

        _require_non_empty_text(
            name="VOiCES media duration",
            value=report_record.get(
                "duration_seconds"
            ),
        )

        if (
            codec_name != "pcm_s16le"
            or sample_rate_hz != 16_000
            or channel_count != 1
            or bits_per_sample != 16
            or sample_width_bytes != 2
        ):
            raise ASRAdversarialVOiCESMaterializationError(
                "VOiCES verified media format changed."
            )

    manifest_boundary = _expect_mapping(
        name="VOiCES manifest evidence boundary",
        value=manifest.get(
            "evidence_boundary"
        ),
    )

    if (
        manifest_boundary.get(
            "allowlist_only_materialization"
        )
        is not True
        or manifest_boundary.get(
            "source_archive_member_bytes_hashed"
        )
        is not True
        or manifest_boundary.get(
            "raw_audio_committed_to_repository"
        )
        is not False
        or manifest_boundary.get(
            "audio_semantics_verified"
        )
        is not False
        or manifest_boundary.get(
            "asr_execution_verified"
        )
        is not False
    ):
        raise ASRAdversarialVOiCESMaterializationError(
            "VOiCES materialization authority boundary changed."
        )

    report_boundary = _expect_mapping(
        name="VOiCES media-report evidence boundary",
        value=report.get(
            "evidence_boundary"
        ),
    )

    for field_name in (
        "external_development_evidence",
        "audio_bytes_verified",
        "media_probe_verified",
        "source_declared_transcripts_bound",
    ):
        if report_boundary.get(
            field_name
        ) is not True:
            raise ASRAdversarialVOiCESMaterializationError(
                "VOiCES media-report positive boundary changed."
            )

    for field_name in (
        "spoken_content_independently_verified",
        "asr_execution_verified",
        "live_human_in_room_diversity_established",
        "microphone_type_diversity_established",
        "production_qualification",
        "release_enforcement",
        "official_release_verdict",
    ):
        if report_boundary.get(
            field_name
        ) is not False:
            raise ASRAdversarialVOiCESMaterializationError(
                "VOiCES media-report authority boundary changed."
            )

    return (
        manifest_records,
        report_records,
    )


def _verify_current_media(
    *,
    materialization_root: Path,
    manifest_records: dict[str, dict[str, object]],
    report_records: dict[str, dict[str, object]],
    definition: ASRAdversarialVOiCESMaterializationDefinition,
) -> tuple[
    ASRAdversarialVOiCESMaterializedMedia,
    ...,
]:
    _verify_exact_materialization_tree(
        materialization_root=materialization_root,
        expected_media_paths=set(
            manifest_records
        ),
    )

    resolved_paths = {}
    pre_hashes = {}

    for relative_path in sorted(
        manifest_records
    ):
        path = _resolve_relative_file(
            root=materialization_root,
            relative_path=relative_path,
            name="VOiCES materialized media",
        )

        observed_sha256, observed_bytes = (
            _hash_file(
                path=path,
                name="VOiCES materialized media",
            )
        )

        record = manifest_records[
            relative_path
        ]

        if (
            observed_sha256
            != record.get(
                "sha256"
            )
            or observed_bytes
            != record.get(
                "bytes"
            )
        ):
            raise ASRAdversarialVOiCESMaterializationError(
                "VOiCES current media does not match "
                "the frozen materialization manifest."
            )

        resolved_paths[
            relative_path
        ] = path

        pre_hashes[
            relative_path
        ] = (
            observed_sha256,
            observed_bytes,
        )

    # Reject tree mutation before the publication pass.
    _verify_exact_materialization_tree(
        materialization_root=materialization_root,
        expected_media_paths=set(
            manifest_records
        ),
    )

    materialized = []
    publication_fingerprints = {}

    for relative_path in sorted(
        manifest_records
    ):
        post_path = _resolve_relative_file(
            root=materialization_root,
            relative_path=relative_path,
            name="VOiCES materialized media",
        )

        if (
            post_path
            != resolved_paths[
                relative_path
            ]
        ):
            raise ASRAdversarialVOiCESMaterializationError(
                "VOiCES media paths changed during verification."
            )

        before_hash_fingerprint = (
            _file_fingerprint(
                path=post_path,
                name="VOiCES materialized media",
            )
        )

        post_sha256, post_bytes = (
            _hash_file(
                path=post_path,
                name="VOiCES materialized media",
            )
        )

        # Re-resolve immediately after hashing. This catches a pathname
        # replacement or symlink substitution performed during the read.
        post_hash_path = _resolve_relative_file(
            root=materialization_root,
            relative_path=relative_path,
            name="VOiCES materialized media",
        )

        if post_hash_path != post_path:
            raise ASRAdversarialVOiCESMaterializationError(
                "VOiCES media paths changed during verification."
            )

        after_hash_fingerprint = (
            _file_fingerprint(
                path=post_hash_path,
                name="VOiCES materialized media",
            )
        )

        if (
            after_hash_fingerprint
            != before_hash_fingerprint
        ):
            raise ASRAdversarialVOiCESMaterializationError(
                "VOiCES media changed during verification; "
                "filesystem identity changed."
            )

        if (
            (
                post_sha256,
                post_bytes,
            )
            != pre_hashes[
                relative_path
            ]
        ):
            raise ASRAdversarialVOiCESMaterializationError(
                "VOiCES media changed during verification."
            )

        publication_fingerprints[
            relative_path
        ] = (
            after_hash_fingerprint
        )

        report_record = report_records[
            relative_path
        ]

        materialized_kind = (
            _require_non_empty_text(
                name="materialized VOiCES media kind",
                value=report_record.get(
                    "kind"
                ),
            )
        )

        if materialized_kind not in {
            "source",
            "capture",
        }:
            raise ASRAdversarialVOiCESMaterializationError(
                "materialized VOiCES media kind is invalid."
            )

        materialized_source_key = (
            _require_source_key(
                name="materialized VOiCES source key",
                value=report_record.get(
                    "source_key"
                ),
            )
        )

        materialized_codec = (
            _require_non_empty_text(
                name="materialized VOiCES codec",
                value=report_record.get(
                    "codec_name"
                ),
            )
        )

        materialized_sample_rate = (
            _require_positive_integer(
                name="materialized VOiCES sample rate",
                value=report_record.get(
                    "sample_rate_hz"
                ),
            )
        )

        materialized_channels = (
            _require_positive_integer(
                name="materialized VOiCES channel count",
                value=report_record.get(
                    "channels"
                ),
            )
        )

        materialized_bits = (
            _require_positive_integer(
                name="materialized VOiCES bits per sample",
                value=report_record.get(
                    "bits_per_sample"
                ),
            )
        )

        materialized_sample_width = (
            _require_positive_integer(
                name="materialized VOiCES sample width",
                value=report_record.get(
                    "sample_width_bytes"
                ),
            )
        )

        materialized_sample_count = (
            _require_positive_integer(
                name="materialized VOiCES sample count",
                value=report_record.get(
                    "sample_count"
                ),
            )
        )

        materialized_duration = (
            _require_non_empty_text(
                name="materialized VOiCES duration",
                value=report_record.get(
                    "duration_seconds"
                ),
            )
        )

        materialized.append(
            ASRAdversarialVOiCESMaterializedMedia(
                relative_path=relative_path,
                path=post_hash_path,
                sha256=post_sha256,
                byte_length=post_bytes,
                kind=materialized_kind,
                source_key=materialized_source_key,
                codec_name=materialized_codec,
                sample_rate_hz=materialized_sample_rate,
                channel_count=materialized_channels,
                bits_per_sample=materialized_bits,
                sample_width_bytes=materialized_sample_width,
                sample_count=materialized_sample_count,
                duration_seconds=materialized_duration,
            )
        )

    if (
        len(
            materialized
        )
        != definition.expected_total_file_count
        or sum(
            value.byte_length
            for value in materialized
        )
        != definition.expected_total_bytes
    ):
        raise ASRAdversarialVOiCESMaterializationError(
            "VOiCES materialized media population changed."
        )

    # Final whole-set publication barrier.
    #
    # An earlier file may have completed its second hash while later files
    # were still being verified. Re-resolve every pathname and compare its
    # filesystem identity to the identity captured immediately after that
    # file's publication hash.
    _verify_exact_materialization_tree(
        materialization_root=materialization_root,
        expected_media_paths=set(
            manifest_records
        ),
    )

    for relative_path in sorted(
        manifest_records
    ):
        final_path = _resolve_relative_file(
            root=materialization_root,
            relative_path=relative_path,
            name="VOiCES materialized media",
        )

        if (
            final_path
            != resolved_paths[
                relative_path
            ]
        ):
            raise ASRAdversarialVOiCESMaterializationError(
                "VOiCES media paths changed during verification."
            )

        final_fingerprint = (
            _file_fingerprint(
                path=final_path,
                name="VOiCES materialized media",
            )
        )

        if (
            final_fingerprint
            != publication_fingerprints[
                relative_path
            ]
        ):
            raise ASRAdversarialVOiCESMaterializationError(
                "VOiCES media changed during verification; "
                "filesystem identity changed."
            )

    return tuple(
        materialized
    )

def _materialize_asr_adversarial_voices_evidence(
    *,
    evidence_root: str | Path,
    definition: ASRAdversarialVOiCESMaterializationDefinition,
) -> ASRAdversarialVOiCESMaterializedEvidence:
    """Verify one complete externally retained controlled VOiCES evidence set."""

    if not isinstance(
        definition,
        ASRAdversarialVOiCESMaterializationDefinition,
    ):
        raise ASRAdversarialVOiCESMaterializationError(
            "VOiCES materialization definition is invalid."
        )

    try:
        controlled = (
            build_asr_adversarial_voices_controlled_v1()
        )
    except HveeContractError as exc:
        raise ASRAdversarialVOiCESMaterializationError(
            "controlled VOiCES contract failed "
            "canonical verification."
        ) from exc

    if (
        controlled.sha256
        != ASR_ADVERSARIAL_VOICES_CONTROLLED_SHA256
        or controlled.sha256
        != definition.controlled_contract_sha256
    ):
        raise ASRAdversarialVOiCESMaterializationError(
            "controlled VOiCES contract identity changed."
        )

    root = _resolve_evidence_root(
        evidence_root
    )

    chain_path, chain = (
        _load_committed_json(
            root=root,
            relative_path=(
                definition.identity_chain_relative_path
            ),
            expected_sha256=(
                definition.identity_chain_sha256
            ),
            expected_byte_length=(
                definition.identity_chain_byte_length
            ),
            name="VOiCES identity chain",
            require_canonical=True,
        )
    )

    selection_path, selection = (
        _load_committed_json(
            root=root,
            relative_path=(
                definition.selection_relative_path
            ),
            expected_sha256=(
                definition.selection_sha256
            ),
            expected_byte_length=(
                definition.selection_byte_length
            ),
            name="VOiCES controlled selection",
        )
    )

    manifest_path, manifest = (
        _load_committed_json(
            root=root,
            relative_path=(
                definition.materialization_manifest_relative_path
            ),
            expected_sha256=(
                definition.materialization_manifest_sha256
            ),
            expected_byte_length=(
                definition.materialization_manifest_byte_length
            ),
            name="VOiCES materialization manifest",
        )
    )

    report_path, report = (
        _load_committed_json(
            root=root,
            relative_path=(
                definition.media_report_relative_path
            ),
            expected_sha256=(
                definition.media_report_sha256
            ),
            expected_byte_length=(
                definition.media_report_byte_length
            ),
            name="VOiCES media verification report",
        )
    )

    rights_manifest_path, _rights_manifest = (
        _load_committed_json(
            root=root,
            relative_path=(
                definition.rights_manifest_relative_path
            ),
            expected_sha256=(
                definition.rights_manifest_sha256
            ),
            expected_byte_length=(
                definition.rights_manifest_byte_length
            ),
            name="VOiCES rights manifest",
        )
    )

    committed_non_json = []

    for (
        name,
        relative_path,
        expected_sha256,
        expected_byte_length,
    ) in (
        (
            "VOiCES source description",
            definition.source_description_relative_path,
            definition.source_description_sha256,
            definition.source_description_byte_length,
        ),
        (
            "VOiCES rights evidence",
            definition.rights_evidence_relative_path,
            definition.rights_evidence_sha256,
            definition.rights_evidence_byte_length,
        ),
        (
            "VOiCES terms evidence",
            definition.terms_evidence_relative_path,
            definition.terms_evidence_sha256,
            definition.terms_evidence_byte_length,
        ),
    ):
        path = _resolve_relative_file(
            root=root,
            relative_path=relative_path,
            name=name,
        )

        observed_sha256, observed_byte_length = (
            _hash_file(
                path=path,
                name=name,
            )
        )

        if (
            observed_sha256
            != expected_sha256
            or observed_byte_length
            != expected_byte_length
        ):
            raise ASRAdversarialVOiCESMaterializationError(
                f"{name} does not match its frozen commitment."
            )

        committed_non_json.append(
            (
                name,
                relative_path,
                path,
                expected_sha256,
                expected_byte_length,
            )
        )

    _verify_chain(
        chain=chain,
        definition=definition,
    )

    (
        manifest_records,
        report_records,
    ) = _verify_cross_bindings(
        selection=selection,
        manifest=manifest,
        report=report,
        definition=definition,
    )

    materialization_root = (
        _resolve_relative_directory(
            root=root,
            relative_path=(
                definition.materialization_root_relative_path
            ),
            name="VOiCES materialization root",
        )
    )

    media = _verify_current_media(
        materialization_root=materialization_root,
        manifest_records=manifest_records,
        report_records=report_records,
        definition=definition,
    )

    # Final commitment pass. No trusted result is published if a frozen
    # artifact or rights input changed while the 66 media files were checked.
    committed_json = (
        (
            "VOiCES identity chain",
            definition.identity_chain_relative_path,
            chain_path,
            definition.identity_chain_sha256,
            definition.identity_chain_byte_length,
        ),
        (
            "VOiCES controlled selection",
            definition.selection_relative_path,
            selection_path,
            definition.selection_sha256,
            definition.selection_byte_length,
        ),
        (
            "VOiCES materialization manifest",
            definition.materialization_manifest_relative_path,
            manifest_path,
            definition.materialization_manifest_sha256,
            definition.materialization_manifest_byte_length,
        ),
        (
            "VOiCES media verification report",
            definition.media_report_relative_path,
            report_path,
            definition.media_report_sha256,
            definition.media_report_byte_length,
        ),
        (
            "VOiCES rights manifest",
            definition.rights_manifest_relative_path,
            rights_manifest_path,
            definition.rights_manifest_sha256,
            definition.rights_manifest_byte_length,
        ),
    )

    committed_inputs = (
        committed_json
        + tuple(
            committed_non_json
        )
    )

    committed_publication_fingerprints = {}

    for (
        name,
        relative_path,
        pre_path,
        expected_sha256,
        expected_byte_length,
    ) in committed_inputs:
        post_path = _resolve_relative_file(
            root=root,
            relative_path=relative_path,
            name=name,
        )

        if post_path != pre_path:
            raise ASRAdversarialVOiCESMaterializationError(
                f"{name} path changed during verification."
            )

        before_hash_fingerprint = (
            _file_fingerprint(
                path=post_path,
                name=name,
            )
        )

        observed_sha256, observed_byte_length = (
            _hash_file(
                path=post_path,
                name=name,
            )
        )

        post_hash_path = _resolve_relative_file(
            root=root,
            relative_path=relative_path,
            name=name,
        )

        if post_hash_path != pre_path:
            raise ASRAdversarialVOiCESMaterializationError(
                f"{name} path changed during verification."
            )

        after_hash_fingerprint = (
            _file_fingerprint(
                path=post_hash_path,
                name=name,
            )
        )

        if (
            before_hash_fingerprint
            != after_hash_fingerprint
        ):
            raise ASRAdversarialVOiCESMaterializationError(
                f"{name} changed during verification; "
                "filesystem identity changed."
            )

        if (
            observed_sha256
            != expected_sha256
            or observed_byte_length
            != expected_byte_length
        ):
            raise ASRAdversarialVOiCESMaterializationError(
                f"{name} changed during verification."
            )

        committed_publication_fingerprints[
            relative_path
        ] = after_hash_fingerprint

    # Whole-set publication barrier for every frozen JSON/rights input.
    for (
        name,
        relative_path,
        pre_path,
        _expected_sha256,
        _expected_byte_length,
    ) in committed_inputs:
        final_path = _resolve_relative_file(
            root=root,
            relative_path=relative_path,
            name=name,
        )

        if final_path != pre_path:
            raise ASRAdversarialVOiCESMaterializationError(
                f"{name} path changed during verification."
            )

        final_fingerprint = (
            _file_fingerprint(
                path=final_path,
                name=name,
            )
        )

        if (
            final_fingerprint
            != committed_publication_fingerprints[
                relative_path
            ]
        ):
            raise ASRAdversarialVOiCESMaterializationError(
                f"{name} changed during verification; "
                "filesystem identity changed."
            )

    return ASRAdversarialVOiCESMaterializedEvidence(
        controlled_contract_sha256=(
            controlled.sha256
        ),
        identity_chain_sha256=(
            definition.identity_chain_sha256
        ),
        selection_sha256=(
            definition.selection_sha256
        ),
        materialization_manifest_sha256=(
            definition.materialization_manifest_sha256
        ),
        media_report_sha256=(
            definition.media_report_sha256
        ),
        observation_sha256=(
            definition.observation_sha256
        ),
        rights_manifest_sha256=(
            definition.rights_manifest_sha256
        ),
        media=media,
    )


def materialize_asr_adversarial_voices_controlled_v1(
    *,
    evidence_root: str | Path,
) -> ASRAdversarialVOiCESMaterializedEvidence:
    """Materialize the exact frozen I4d2 controlled VOiCES evidence."""

    definition = (
        ASRAdversarialVOiCESMaterializationDefinition(
            controlled_contract_sha256=(
                ASR_ADVERSARIAL_VOICES_CONTROLLED_SHA256
            ),
            identity_chain_relative_path=(
                "i4d2d2-identity-chain.json"
            ),
            identity_chain_sha256=(
                ASR_ADVERSARIAL_VOICES_IDENTITY_CHAIN_SHA256
            ),
            identity_chain_byte_length=3_749,
            selection_relative_path=(
                "i4d2c6-controlled-selection.json"
            ),
            selection_sha256=(
                "5919f15396171255f5ce5905e9cc26fe"
                "c8743df3e58a95c8d5649726f02c7c2e"
            ),
            selection_byte_length=50_056,
            materialization_root_relative_path=(
                "i4d2c7-materialized"
            ),
            materialization_manifest_relative_path=(
                "i4d2c7-materialized/manifest.json"
            ),
            materialization_manifest_sha256=(
                "de02c18cbf82e00ef1b3e9ff6be64dc7"
                "f74b156c51538a4499c992ff73a7886c"
            ),
            materialization_manifest_byte_length=33_458,
            media_report_relative_path=(
                "i4d2c8-media-verification/report.json"
            ),
            media_report_sha256=(
                "7d5f75110c241cc7d62335ce23b10838"
                "2bb4111cbe6bf30a5126e361888f733b"
            ),
            media_report_byte_length=30_829,
            rights_manifest_relative_path=(
                "i4d2c9-source-rights/manifest.json"
            ),
            rights_manifest_sha256=(
                "48d3464a9d7718b72db92e6ded490d9a"
                "0f99e373c38de00a91b7e38ee9a25cf7"
            ),
            rights_manifest_byte_length=1_271,
            source_description_relative_path=(
                "i4d2c9-source-rights/voices-readme.html"
            ),
            source_description_sha256=(
                "1723ea0f40bcacb8863047bdc6a3536f"
                "a0fb13a0335a07b167a9bdf3b7bb31d9"
            ),
            source_description_byte_length=81_061,
            rights_evidence_relative_path=(
                "i4d2c9-source-rights/"
                "voices-evaluation-plan.pdf"
            ),
            rights_evidence_sha256=(
                "61deed1d0090144a8ce4fbc6bc503312"
                "411e57c3ac3059ef0d5825a09fe01745"
            ),
            rights_evidence_byte_length=166_606,
            terms_evidence_relative_path=(
                "i4d2c9-source-rights/"
                "cc-by-4.0-legalcode.txt"
            ),
            terms_evidence_sha256=(
                "9ba9550ad48438d0836ddab3da480b3b"
                "69ffa0aac7b7878b5a0039e7ab429411"
            ),
            terms_evidence_byte_length=18_657,
            observation_sha256=(
                "69c2f06c099a8b209f42d2f22d61d6bf"
                "3397be1b2d378766b0a015a6f4fd8380"
            ),
            expected_source_file_count=2,
            expected_capture_file_count=64,
            expected_total_file_count=66,
            expected_total_bytes=21_318_330,
            expected_captures_per_source=32,
            expected_constant_angle_degrees=10,
            expected_source_keys=(
                (
                    652,
                    129742,
                    3,
                ),
                (
                    7850,
                    111771,
                    4,
                ),
            ),
            expected_docker_image_id=(
                "sha256:"
                "af012667333c1574425503e7840c1fa64"
                "a8a08ffcf28bfc7b11f79544d32e290"
            ),
            expected_python_version=(
                "Python 3.13.15"
            ),
            expected_ffprobe_version=(
                "ffprobe version 5.1.9-0+deb12u1 "
                "Copyright (c) 2007-2026 "
                "the FFmpeg developers"
            ),
        )
    )

    return (
        _materialize_asr_adversarial_voices_evidence(
            evidence_root=evidence_root,
            definition=definition,
        )
    )


__all__ = [
    "ASR_ADVERSARIAL_VOICES_IDENTITY_CHAIN_SHA256",
    "ASRAdversarialVOiCESMaterializationDefinition",
    "ASRAdversarialVOiCESMaterializationError",
    "ASRAdversarialVOiCESMaterializedEvidence",
    "ASRAdversarialVOiCESMaterializedMedia",
    "materialize_asr_adversarial_voices_controlled_v1",
]

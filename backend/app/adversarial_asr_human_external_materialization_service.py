"""Secure materialization of externally retained human ASR evidence.

Human/external audio used by Hetren may intentionally remain outside the
repository. This service turns an explicitly supplied external evidence root
into a verified in-memory source reference.

The materialization boundary:

- never downloads source material,
- never copies or rewrites source material,
- rejects symlink roots and symlink path components,
- requires canonical relative source paths,
- resolves files strictly inside the supplied evidence root,
- verifies audio and transcript content commitments,
- verifies expected audio byte length,
- measures committed media properties through an injected probe,
- re-resolves and rehashes both files after probing,
- rejects mutation that occurs during verification.

Absolute local filesystem paths are returned only in memory. They are not
source-visible qualification artifacts.

This service establishes filesystem/content integrity only. It does not
adjudicate rights, infer speaker attributes, establish acoustic diversity,
apply qualification thresholds, authorize production use, or modify release
authority.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol

from app.adversarial_asr_corpus_verification_service import (
    ASRAdversarialMeasuredMedia,
)
from hvee.core.contracts import HveeContractError
from hvee.packs.asr.adversarial_human_external_minilibrispeech_v1 import (
    ASR_ADVERSARIAL_MINILIBRISPEECH_SELECTION_SHA256,
    build_asr_adversarial_minilibrispeech_record_pair_v1,
    build_asr_adversarial_minilibrispeech_selection_v1,
    get_asr_adversarial_minilibrispeech_case_v1,
)


_SHA256_PATTERN = re.compile(
    r"^[0-9a-f]{64}$"
)

_CODEC_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9._-]*$"
)


class ASRAdversarialHumanExternalMaterializationError(
    ValueError
):
    """Raised when external human evidence cannot be trusted."""


class ASRAdversarialHumanExternalMediaProbe(
    Protocol
):
    """Injected deterministic media-inspection boundary."""

    def probe(
        self,
        audio_path: Path,
    ) -> ASRAdversarialMeasuredMedia:
        ...


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
        raise ASRAdversarialHumanExternalMaterializationError(
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
        raise ASRAdversarialHumanExternalMaterializationError(
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
        raise ASRAdversarialHumanExternalMaterializationError(
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
        raise ASRAdversarialHumanExternalMaterializationError(
            f"{name} is invalid."
        )

    relative = PurePosixPath(
        value
    )

    if (
        relative.is_absolute()
        or ".." in relative.parts
        or "." in relative.parts
        or len(relative.parts) < 2
        or str(relative) != value
    ):
        raise ASRAdversarialHumanExternalMaterializationError(
            f"{name} is invalid."
        )

    return value


@dataclass(frozen=True, slots=True)
class ASRAdversarialHumanExternalMaterializationDefinition:
    """Exact filesystem/content commitments for one external source."""

    case_id: str
    source_item_id: str
    audio_relative_path: str
    transcript_relative_path: str
    expected_audio_sha256: str
    expected_audio_byte_length: int
    expected_transcript_sha256: str
    expected_duration_ms: int
    expected_sample_rate_hz: int
    expected_channel_count: int
    expected_codec_name: str
    source_selection_sha256: str
    provenance_record_sha256: str
    rights_record_sha256: str

    def __post_init__(
        self,
    ) -> None:
        _require_non_empty_text(
            name="human external case id",
            value=self.case_id,
        )
        _require_non_empty_text(
            name="human external source item id",
            value=self.source_item_id,
        )

        _require_relative_path(
            name="human external audio relative path",
            value=self.audio_relative_path,
        )
        _require_relative_path(
            name="human external transcript relative path",
            value=self.transcript_relative_path,
        )

        if (
            self.audio_relative_path
            == self.transcript_relative_path
        ):
            raise ASRAdversarialHumanExternalMaterializationError(
                "human external audio and transcript paths "
                "must be distinct."
            )

        _require_sha256(
            name="expected human external audio",
            value=self.expected_audio_sha256,
        )
        _require_positive_integer(
            name="expected human external audio byte length",
            value=self.expected_audio_byte_length,
        )
        _require_sha256(
            name="expected human external transcript",
            value=self.expected_transcript_sha256,
        )
        _require_positive_integer(
            name="expected human external duration",
            value=self.expected_duration_ms,
        )
        _require_positive_integer(
            name="expected human external sample rate",
            value=self.expected_sample_rate_hz,
        )
        _require_positive_integer(
            name="expected human external channel count",
            value=self.expected_channel_count,
        )

        if (
            not isinstance(
                self.expected_codec_name,
                str,
            )
            or _CODEC_PATTERN.fullmatch(
                self.expected_codec_name
            )
            is None
        ):
            raise ASRAdversarialHumanExternalMaterializationError(
                "expected human external codec name "
                "must be canonical lowercase text."
            )

        _require_sha256(
            name="human external source selection",
            value=self.source_selection_sha256,
        )
        _require_sha256(
            name="human external provenance record",
            value=self.provenance_record_sha256,
        )
        _require_sha256(
            name="human external rights record",
            value=self.rights_record_sha256,
        )


@dataclass(frozen=True, slots=True)
class ASRAdversarialHumanExternalMaterializedSource:
    """Verified external human source reference held only in memory."""

    case_id: str
    source_item_id: str
    audio_path: Path
    transcript_path: Path
    reference_transcript: str
    audio_sha256: str
    audio_byte_length: int
    transcript_sha256: str
    transcript_byte_length: int
    duration_ms: int
    sample_rate_hz: int
    channel_count: int
    codec_name: str
    source_selection_sha256: str
    provenance_record_sha256: str
    rights_record_sha256: str
    development_evidence_only: bool = True
    rights_adjudicated: bool = False
    production_qualified: bool = False
    release_enforcement_eligible: bool = False

    def __post_init__(
        self,
    ) -> None:
        _require_non_empty_text(
            name="materialized human external case id",
            value=self.case_id,
        )
        _require_non_empty_text(
            name="materialized human external source item id",
            value=self.source_item_id,
        )

        for (
            name,
            path,
        ) in (
            (
                "materialized human external audio path",
                self.audio_path,
            ),
            (
                "materialized human external transcript path",
                self.transcript_path,
            ),
        ):
            if (
                not isinstance(
                    path,
                    Path,
                )
                or not path.is_absolute()
            ):
                raise ASRAdversarialHumanExternalMaterializationError(
                    f"{name} must be an absolute Path."
                )

        if self.audio_path == self.transcript_path:
            raise ASRAdversarialHumanExternalMaterializationError(
                "materialized human external audio and transcript "
                "paths must be distinct."
            )

        _require_non_empty_text(
            name="materialized human external transcript",
            value=self.reference_transcript,
        )

        _require_sha256(
            name="materialized human external audio",
            value=self.audio_sha256,
        )
        _require_positive_integer(
            name="materialized human external audio byte length",
            value=self.audio_byte_length,
        )
        _require_sha256(
            name="materialized human external transcript",
            value=self.transcript_sha256,
        )
        _require_positive_integer(
            name="materialized human external transcript byte length",
            value=self.transcript_byte_length,
        )
        _require_positive_integer(
            name="materialized human external duration",
            value=self.duration_ms,
        )
        _require_positive_integer(
            name="materialized human external sample rate",
            value=self.sample_rate_hz,
        )
        _require_positive_integer(
            name="materialized human external channel count",
            value=self.channel_count,
        )

        if (
            not isinstance(
                self.codec_name,
                str,
            )
            or _CODEC_PATTERN.fullmatch(
                self.codec_name
            )
            is None
        ):
            raise ASRAdversarialHumanExternalMaterializationError(
                "materialized human external codec name "
                "must be canonical lowercase text."
            )

        _require_sha256(
            name="materialized human external source selection",
            value=self.source_selection_sha256,
        )
        _require_sha256(
            name="materialized human external provenance record",
            value=self.provenance_record_sha256,
        )
        _require_sha256(
            name="materialized human external rights record",
            value=self.rights_record_sha256,
        )

        if self.development_evidence_only is not True:
            raise ASRAdversarialHumanExternalMaterializationError(
                "materialized human external source must remain "
                "development-evidence-only."
            )

        if self.rights_adjudicated is not False:
            raise ASRAdversarialHumanExternalMaterializationError(
                "materialized human external rights must remain "
                "not adjudicated."
            )

        if self.production_qualified is not False:
            raise ASRAdversarialHumanExternalMaterializationError(
                "materialized human external source must remain "
                "not production-qualified."
            )

        if self.release_enforcement_eligible is not False:
            raise ASRAdversarialHumanExternalMaterializationError(
                "materialized human external source must remain "
                "ineligible for release enforcement."
            )


def _resolve_evidence_root(
    evidence_root: str | Path,
) -> Path:
    if not isinstance(
        evidence_root,
        (str, Path),
    ):
        raise ASRAdversarialHumanExternalMaterializationError(
            "human external evidence root is invalid."
        )

    supplied = Path(
        evidence_root
    )

    if not supplied.is_absolute():
        raise ASRAdversarialHumanExternalMaterializationError(
            "human external evidence root must be absolute."
        )

    if supplied.is_symlink():
        raise ASRAdversarialHumanExternalMaterializationError(
            "human external evidence root cannot be a symlink."
        )

    try:
        resolved = supplied.resolve(
            strict=True
        )
    except (OSError, RuntimeError) as exc:
        raise ASRAdversarialHumanExternalMaterializationError(
            "human external evidence root is unavailable."
        ) from exc

    if not resolved.is_dir():
        raise ASRAdversarialHumanExternalMaterializationError(
            "human external evidence root must be a directory."
        )

    return resolved


def _resolve_direct_file(
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
            raise ASRAdversarialHumanExternalMaterializationError(
                f"{name} path cannot contain symlinks."
            )

    try:
        resolved = current.resolve(
            strict=True
        )
    except (OSError, RuntimeError) as exc:
        raise ASRAdversarialHumanExternalMaterializationError(
            f"{name} is unavailable."
        ) from exc

    if (
        not resolved.is_relative_to(
            root
        )
        or not resolved.is_file()
    ):
        raise ASRAdversarialHumanExternalMaterializationError(
            f"{name} is unavailable."
        )

    return resolved


def _hash_file(
    *,
    path: Path,
    name: str,
) -> tuple[str, int]:
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
        raise ASRAdversarialHumanExternalMaterializationError(
            f"{name} could not be read."
        ) from exc

    if byte_length <= 0:
        raise ASRAdversarialHumanExternalMaterializationError(
            f"{name} must not be empty."
        )

    return (
        digest.hexdigest(),
        byte_length,
    )


def _read_transcript(
    path: Path,
) -> tuple[
    str,
    str,
    int,
]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ASRAdversarialHumanExternalMaterializationError(
            "human external transcript could not be read."
        ) from exc

    if not raw:
        raise ASRAdversarialHumanExternalMaterializationError(
            "human external transcript must not be empty."
        )

    try:
        transcript = raw.decode(
            "utf-8"
        )
    except UnicodeDecodeError as exc:
        raise ASRAdversarialHumanExternalMaterializationError(
            "human external transcript must be valid UTF-8."
        ) from exc

    if not transcript.strip():
        raise ASRAdversarialHumanExternalMaterializationError(
            "human external transcript must contain text."
        )

    return (
        transcript,
        hashlib.sha256(
            raw
        ).hexdigest(),
        len(
            raw
        ),
    )


def materialize_asr_adversarial_human_external_source(
    *,
    evidence_root: str | Path,
    definition: (
        ASRAdversarialHumanExternalMaterializationDefinition
    ),
    media_probe: ASRAdversarialHumanExternalMediaProbe,
) -> ASRAdversarialHumanExternalMaterializedSource:
    """Verify one externally retained human source without modifying it."""

    if not isinstance(
        definition,
        ASRAdversarialHumanExternalMaterializationDefinition,
    ):
        raise ASRAdversarialHumanExternalMaterializationError(
            "human external materialization definition is invalid."
        )

    if not callable(
        getattr(
            media_probe,
            "probe",
            None,
        )
    ):
        raise ASRAdversarialHumanExternalMaterializationError(
            "human external media probe is invalid."
        )

    root = _resolve_evidence_root(
        evidence_root
    )

    audio_path = _resolve_direct_file(
        root=root,
        relative_path=(
            definition.audio_relative_path
        ),
        name="human external audio",
    )

    transcript_path = _resolve_direct_file(
        root=root,
        relative_path=(
            definition.transcript_relative_path
        ),
        name="human external transcript",
    )

    (
        pre_audio_sha256,
        pre_audio_byte_length,
    ) = _hash_file(
        path=audio_path,
        name="human external audio",
    )

    if (
        pre_audio_sha256
        != definition.expected_audio_sha256
        or pre_audio_byte_length
        != definition.expected_audio_byte_length
    ):
        raise ASRAdversarialHumanExternalMaterializationError(
            "human external audio does not match "
            "the committed source."
        )

    (
        reference_transcript,
        pre_transcript_sha256,
        pre_transcript_byte_length,
    ) = _read_transcript(
        transcript_path
    )

    if (
        pre_transcript_sha256
        != definition.expected_transcript_sha256
    ):
        raise ASRAdversarialHumanExternalMaterializationError(
            "human external transcript does not match "
            "the committed source."
        )

    measured = media_probe.probe(
        audio_path
    )

    if not isinstance(
        measured,
        ASRAdversarialMeasuredMedia,
    ):
        raise ASRAdversarialHumanExternalMaterializationError(
            "human external media probe returned "
            "an invalid result."
        )

    post_audio_path = _resolve_direct_file(
        root=root,
        relative_path=(
            definition.audio_relative_path
        ),
        name="human external audio",
    )

    post_transcript_path = _resolve_direct_file(
        root=root,
        relative_path=(
            definition.transcript_relative_path
        ),
        name="human external transcript",
    )

    if (
        post_audio_path != audio_path
        or post_transcript_path
        != transcript_path
    ):
        raise ASRAdversarialHumanExternalMaterializationError(
            "human external source paths changed "
            "during verification."
        )

    (
        post_audio_sha256,
        post_audio_byte_length,
    ) = _hash_file(
        path=post_audio_path,
        name="human external audio",
    )

    (
        post_reference_transcript,
        post_transcript_sha256,
        post_transcript_byte_length,
    ) = _read_transcript(
        post_transcript_path
    )

    if (
        post_audio_sha256
        != pre_audio_sha256
        or post_audio_byte_length
        != pre_audio_byte_length
    ):
        raise ASRAdversarialHumanExternalMaterializationError(
            "human external audio changed "
            "during media verification."
        )

    if (
        post_transcript_sha256
        != pre_transcript_sha256
        or post_transcript_byte_length
        != pre_transcript_byte_length
        or post_reference_transcript
        != reference_transcript
    ):
        raise ASRAdversarialHumanExternalMaterializationError(
            "human external transcript changed "
            "during media verification."
        )

    if (
        measured.duration_ms
        != definition.expected_duration_ms
    ):
        raise ASRAdversarialHumanExternalMaterializationError(
            "measured human external duration does not "
            "match the committed source."
        )

    if (
        measured.sample_rate_hz
        != definition.expected_sample_rate_hz
    ):
        raise ASRAdversarialHumanExternalMaterializationError(
            "measured human external sample rate does not "
            "match the committed source."
        )

    if (
        measured.channel_count
        != definition.expected_channel_count
    ):
        raise ASRAdversarialHumanExternalMaterializationError(
            "measured human external channel count does not "
            "match the committed source."
        )

    if (
        measured.codec_name
        != definition.expected_codec_name
    ):
        raise ASRAdversarialHumanExternalMaterializationError(
            "measured human external codec does not "
            "match the committed source."
        )

    return ASRAdversarialHumanExternalMaterializedSource(
        case_id=definition.case_id,
        source_item_id=definition.source_item_id,
        audio_path=audio_path,
        transcript_path=transcript_path,
        reference_transcript=(
            reference_transcript
        ),
        audio_sha256=(
            post_audio_sha256
        ),
        audio_byte_length=(
            post_audio_byte_length
        ),
        transcript_sha256=(
            post_transcript_sha256
        ),
        transcript_byte_length=(
            post_transcript_byte_length
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
        source_selection_sha256=(
            definition.source_selection_sha256
        ),
        provenance_record_sha256=(
            definition.provenance_record_sha256
        ),
        rights_record_sha256=(
            definition.rights_record_sha256
        ),
    )


def materialize_asr_adversarial_minilibrispeech_source_v1(
    *,
    evidence_root: str | Path,
    utterance_id: str,
    media_probe: ASRAdversarialHumanExternalMediaProbe,
) -> ASRAdversarialHumanExternalMaterializedSource:
    """Materialize one exact I4b Mini LibriSpeech source item."""

    try:
        selection = (
            build_asr_adversarial_minilibrispeech_selection_v1()
        )

        if (
            selection.sha256
            != ASR_ADVERSARIAL_MINILIBRISPEECH_SELECTION_SHA256
        ):
            raise HveeContractError(
                "Mini LibriSpeech selection identity changed"
            )

        case = (
            get_asr_adversarial_minilibrispeech_case_v1(
                utterance_id
            )
        )

        provenance, rights = (
            build_asr_adversarial_minilibrispeech_record_pair_v1(
                utterance_id
            )
        )
    except HveeContractError as exc:
        raise ASRAdversarialHumanExternalMaterializationError(
            "Mini LibriSpeech source definition failed "
            "canonical verification."
        ) from exc

    relative_root = (
        "selected/"
        + case.utterance_id
        + "/"
    )

    definition = (
        ASRAdversarialHumanExternalMaterializationDefinition(
            case_id=case.case_id,
            source_item_id=(
                case.utterance_id
            ),
            audio_relative_path=(
                relative_root
                + case.utterance_id
                + ".flac"
            ),
            transcript_relative_path=(
                relative_root
                + case.utterance_id
                + ".txt"
            ),
            expected_audio_sha256=(
                case.source_audio_sha256
            ),
            expected_audio_byte_length=(
                case.audio_bytes
            ),
            expected_transcript_sha256=(
                case.reference_transcript_sha256
            ),
            expected_duration_ms=(
                case.duration_ms
            ),
            expected_sample_rate_hz=(
                case.sample_rate_hz
            ),
            expected_channel_count=(
                case.channel_count
            ),
            expected_codec_name=(
                case.codec_name
            ),
            source_selection_sha256=(
                selection.sha256
            ),
            provenance_record_sha256=(
                provenance.sha256
            ),
            rights_record_sha256=(
                rights.sha256
            ),
        )
    )

    return materialize_asr_adversarial_human_external_source(
        evidence_root=evidence_root,
        definition=definition,
        media_probe=media_probe,
    )

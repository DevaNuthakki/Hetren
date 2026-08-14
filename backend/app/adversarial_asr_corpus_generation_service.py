"""Generate source-visible adversarial ASR synthetic corpus assets."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol

from app.adversarial_asr_espeak import (
    ASRAdversarialEspeak,
)
from hvee.core.contracts import HveeContractError
from hvee.packs.asr.adversarial_corpus_records import (
    ASR_ADVERSARIAL_CORPUS_GENERATION_PLAN_KEY,
    ASR_ADVERSARIAL_CORPUS_PROVENANCE_RECORD_KEY,
    ASR_ADVERSARIAL_CORPUS_RIGHTS_RECORD_KEY,
    verify_asr_adversarial_corpus_record_v1,
)


class ASRAdversarialCorpusGenerationError(
    ValueError
):
    """Raised when deterministic corpus generation cannot be proven."""


class _MediaProbe(Protocol):
    def probe(
        self,
        path: Path,
    ) -> object:
        ...


@dataclass(frozen=True, slots=True)
class ASRAdversarialGeneratedSource:
    case_id: str
    relative_audio_path: str
    audio_asset_sha256: str
    byte_length: int
    duration_ms: int
    sample_rate_hz: int
    channel_count: int
    codec_name: str
    provenance_record_sha256: str
    rights_record_sha256: str
    generator_environment_sha256: str
    development_evidence_only: bool = True


def _sha256(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while True:
            chunk = handle.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(
                chunk
            )

    return digest.hexdigest()


def _load_document(
    *,
    path: Path,
    corpus_root: Path,
) -> dict[str, object]:
    if path.is_symlink():
        raise ASRAdversarialCorpusGenerationError(
            "corpus source document cannot be a symlink"
        )

    try:
        resolved = path.resolve(
            strict=True
        )
    except OSError as exc:
        raise ASRAdversarialCorpusGenerationError(
            "corpus source document is missing"
        ) from exc

    try:
        resolved.relative_to(
            corpus_root
        )
    except ValueError as exc:
        raise ASRAdversarialCorpusGenerationError(
            "corpus source document escaped corpus root"
        ) from exc

    if not resolved.is_file():
        raise ASRAdversarialCorpusGenerationError(
            "corpus source document must be a regular file"
        )

    try:
        value = json.loads(
            resolved.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise ASRAdversarialCorpusGenerationError(
            "corpus source document is invalid"
        ) from exc

    if (
        not isinstance(value, dict)
        or set(value) != {
            "sha256",
            "payload",
        }
        or not isinstance(
            value["sha256"],
            str,
        )
        or not isinstance(
            value["payload"],
            dict,
        )
    ):
        raise ASRAdversarialCorpusGenerationError(
            "corpus source document envelope is invalid"
        )

    return value


def _verified_record(
    *,
    path: Path,
    corpus_root: Path,
):
    document = _load_document(
        path=path,
        corpus_root=corpus_root,
    )

    try:
        return (
            verify_asr_adversarial_corpus_record_v1(
                payload=document[
                    "payload"
                ],
                expected_sha256=document[
                    "sha256"
                ],
            )
        )
    except HveeContractError as exc:
        raise ASRAdversarialCorpusGenerationError(
            "corpus source record failed verification"
        ) from exc


def _artifact_key(
    bundle,
) -> str:
    artifact = bundle.payload.get(
        "artifact"
    )

    if not isinstance(
        artifact,
        dict,
    ):
        raise ASRAdversarialCorpusGenerationError(
            "corpus source record artifact is missing"
        )

    key = artifact.get(
        "key"
    )

    if not isinstance(
        key,
        str,
    ):
        raise ASRAdversarialCorpusGenerationError(
            "corpus source record artifact key is invalid"
        )

    return key


def _output_path(
    *,
    output_root: Path,
    relative_path: str,
) -> Path:
    relative = PurePosixPath(
        relative_path
    )

    root_resolved = output_root.resolve(
        strict=True
    )

    current = root_resolved

    for part in relative.parts[:-1]:
        current = (
            current
            / part
        )

        if current.is_symlink():
            raise ASRAdversarialCorpusGenerationError(
                "generated audio parent path "
                "cannot contain a symlink"
            )

        current.mkdir(
            exist_ok=True,
        )

        if (
            current.is_symlink()
            or not current.is_dir()
        ):
            raise ASRAdversarialCorpusGenerationError(
                "generated audio parent path "
                "must contain directories only"
            )

    parent_resolved = current.resolve(
        strict=True
    )

    try:
        parent_resolved.relative_to(
            root_resolved
        )
    except ValueError as exc:
        raise ASRAdversarialCorpusGenerationError(
            "generated audio path escaped output root"
        ) from exc

    final_path = (
        parent_resolved
        / relative.parts[-1]
    )

    if final_path.is_symlink():
        raise ASRAdversarialCorpusGenerationError(
            "generated audio output cannot be a symlink"
        )

    return final_path


def generate_asr_adversarial_synthetic_source_v1(
    *,
    corpus_root: Path,
    output_root: Path,
    case_id: str,
    synthesizer: ASRAdversarialEspeak,
    media_probe: _MediaProbe,
) -> ASRAdversarialGeneratedSource:
    if corpus_root.is_symlink():
        raise ASRAdversarialCorpusGenerationError(
            "adversarial corpus root cannot be a symlink"
        )

    try:
        corpus = corpus_root.resolve(
            strict=True
        )
    except OSError as exc:
        raise ASRAdversarialCorpusGenerationError(
            "adversarial corpus root is missing"
        ) from exc

    if not corpus.is_dir():
        raise ASRAdversarialCorpusGenerationError(
            "adversarial corpus root must be a directory"
        )

    if output_root.is_symlink():
        raise ASRAdversarialCorpusGenerationError(
            "generated corpus output root cannot be a symlink"
        )

    output_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    output = output_root.resolve(
        strict=True
    )

    if not output.is_dir():
        raise ASRAdversarialCorpusGenerationError(
            "generated corpus output root must be a directory"
        )

    plan = _verified_record(
        path=(
            corpus
            / "specification/generation-plan.json"
        ),
        corpus_root=corpus,
    )

    if (
        _artifact_key(
            plan
        )
        != ASR_ADVERSARIAL_CORPUS_GENERATION_PLAN_KEY
    ):
        raise ASRAdversarialCorpusGenerationError(
            "corpus generation plan has the wrong artifact type"
        )

    plan_record = plan.payload[
        "record"
    ]

    entries = plan_record[
        "entries"
    ]

    matching = [
        entry
        for entry in entries
        if entry[
            "case_id"
        ]
        == case_id
    ]

    if len(matching) != 1:
        raise ASRAdversarialCorpusGenerationError(
            "requested corpus case is not uniquely planned"
        )

    entry = matching[0]

    if (
        entry[
            "transformation_record_sha256"
        ]
        is not None
    ):
        raise ASRAdversarialCorpusGenerationError(
            "synthetic source generation cannot execute "
            "a derivative transformation entry"
        )

    provenance = _verified_record(
        path=(
            corpus
            / "records/provenance"
            / f"{case_id}.json"
        ),
        corpus_root=corpus,
    )
    rights = _verified_record(
        path=(
            corpus
            / "records/rights"
            / f"{case_id}.json"
        ),
        corpus_root=corpus,
    )

    if (
        _artifact_key(
            provenance
        )
        != ASR_ADVERSARIAL_CORPUS_PROVENANCE_RECORD_KEY
        or _artifact_key(
            rights
        )
        != ASR_ADVERSARIAL_CORPUS_RIGHTS_RECORD_KEY
    ):
        raise ASRAdversarialCorpusGenerationError(
            "corpus source records have invalid artifact types"
        )

    if (
        provenance.sha256
        != entry[
            "provenance_record_sha256"
        ]
        or rights.sha256
        != entry[
            "rights_record_sha256"
        ]
    ):
        raise ASRAdversarialCorpusGenerationError(
            "generation plan does not bind "
            "the committed source records"
        )

    provenance_record = (
        provenance.payload[
            "record"
        ]
    )
    rights_record = (
        rights.payload[
            "record"
        ]
    )

    if (
        provenance_record[
            "case_id"
        ]
        != case_id
        or rights_record[
            "case_id"
        ]
        != case_id
    ):
        raise ASRAdversarialCorpusGenerationError(
            "source records do not bind requested case"
        )

    generator = provenance_record[
        "generator"
    ]

    environment = (
        synthesizer.environment
    )

    if (
        provenance_record[
            "source_kind"
        ]
        != "synthetic_tts"
        or generator[
            "key"
        ]
        != "espeak-ng"
        or generator[
            "version"
        ]
        != environment.package_version
        or generator[
            "executable_sha256"
        ]
        != environment.executable_sha256
        or generator[
            "platform_key"
        ]
        != environment.platform_key
    ):
        raise ASRAdversarialCorpusGenerationError(
            "runtime synthetic-speech environment "
            "does not match committed provenance"
        )

    if (
        rights_record[
            "review_status"
        ]
        != "not_adjudicated"
        or rights_record[
            "development_use_only"
        ]
        is not True
    ):
        raise ASRAdversarialCorpusGenerationError(
            "source rights boundary is invalid"
        )

    transcript = (
        corpus
        / "specification/transcripts"
        / f"{case_id}.txt"
    )

    if transcript.is_symlink():
        raise ASRAdversarialCorpusGenerationError(
            "source transcript cannot be a symlink"
        )

    try:
        transcript_resolved = transcript.resolve(
            strict=True
        )
    except OSError as exc:
        raise ASRAdversarialCorpusGenerationError(
            "source transcript is missing"
        ) from exc

    try:
        transcript_resolved.relative_to(
            corpus
        )
    except ValueError as exc:
        raise ASRAdversarialCorpusGenerationError(
            "source transcript escaped corpus root"
        ) from exc

    if (
        _sha256(
            transcript_resolved
        )
        != provenance_record[
            "transcript_sha256"
        ]
    ):
        raise ASRAdversarialCorpusGenerationError(
            "source transcript SHA-256 "
            "does not match committed provenance"
        )

    final_path = _output_path(
        output_root=output,
        relative_path=entry[
            "output_relative_path"
        ],
    )

    with tempfile.TemporaryDirectory(
        dir=final_path.parent,
        prefix=".hetren-source-",
    ) as temporary_directory:
        temporary_path = (
            Path(
                temporary_directory
            )
            / "source.wav"
        )

        synthesizer.synthesize(
            transcript_path=transcript_resolved,
            output_path=temporary_path,
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
        )

        if (
            temporary_path.is_symlink()
            or not temporary_path.is_file()
        ):
            raise ASRAdversarialCorpusGenerationError(
                "generated source audio is invalid"
            )

        source_sha256 = _sha256(
            temporary_path
        )
        byte_length = (
            temporary_path.stat().st_size
        )

        if byte_length <= 0:
            raise ASRAdversarialCorpusGenerationError(
                "generated source audio is empty"
            )

        measured = media_probe.probe(
            temporary_path
        )

        if final_path.is_symlink():
            raise ASRAdversarialCorpusGenerationError(
                "generated source output cannot be a symlink"
            )

        if final_path.exists():
            if (
                not final_path.is_file()
                or _sha256(
                    final_path
                )
                != source_sha256
                or final_path.stat().st_size
                != byte_length
            ):
                raise ASRAdversarialCorpusGenerationError(
                    "existing generated source does not match "
                    "the deterministic output"
                )
        else:
            try:
                os.link(
                    temporary_path,
                    final_path,
                    follow_symlinks=False,
                )
            except FileExistsError:
                if (
                    final_path.is_symlink()
                    or not final_path.is_file()
                    or _sha256(
                        final_path
                    )
                    != source_sha256
                    or final_path.stat().st_size
                    != byte_length
                ):
                    raise ASRAdversarialCorpusGenerationError(
                        "concurrent generated source publication "
                        "did not match deterministic output"
                    )

    if (
        final_path.is_symlink()
        or not final_path.is_file()
        or _sha256(
            final_path
        )
        != source_sha256
        or final_path.stat().st_size
        != byte_length
    ):
        raise ASRAdversarialCorpusGenerationError(
            "generated source audio changed "
            "during publication"
        )

    measured_after_publish = (
        media_probe.probe(
            final_path
        )
    )

    for name in (
        "duration_ms",
        "sample_rate_hz",
        "channel_count",
        "codec_name",
    ):
        if (
            getattr(
                measured,
                name,
            )
            != getattr(
                measured_after_publish,
                name,
            )
        ):
            raise ASRAdversarialCorpusGenerationError(
                "generated media metadata changed "
                "during publication"
            )

    return ASRAdversarialGeneratedSource(
        case_id=case_id,
        relative_audio_path=entry[
            "output_relative_path"
        ],
        audio_asset_sha256=source_sha256,
        byte_length=byte_length,
        duration_ms=measured.duration_ms,
        sample_rate_hz=measured.sample_rate_hz,
        channel_count=measured.channel_count,
        codec_name=measured.codec_name,
        provenance_record_sha256=(
            provenance.sha256
        ),
        rights_record_sha256=(
            rights.sha256
        ),
        generator_environment_sha256=(
            environment.environment_sha256
        ),
    )


__all__ = [
    "ASRAdversarialCorpusGenerationError",
    "ASRAdversarialGeneratedSource",
    "generate_asr_adversarial_synthetic_source_v1",
]

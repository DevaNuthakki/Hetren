"""Deterministic publication of adversarial ASR audio derivatives.

This application service binds:
- an immutable generated source asset;
- a source-visible derivative plan;
- a source-visible transformation record;
- an injected deterministic audio transformer;
- an injected deterministic media probe.

It generates into a temporary location, verifies content and media facts,
and atomically publishes the derivative as a direct file.

The service does not perform ASR, infer speaker/acoustic attributes,
adjudicate rights, apply qualification thresholds, issue certification,
authorize production use, or modify release authority.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol

from app.adversarial_asr_corpus_verification_service import (
    ASRAdversarialMeasuredMedia,
    ASRAdversarialMediaProbe,
)
from app.adversarial_asr_ffmpeg import (
    ASRAdversarialFFmpegTransformResult,
)
from app.content_hashing import (
    calculate_content_sha256,
)
from hvee.packs.asr.adversarial_corpus_records import (
    ASRAdversarialCorpusRecordBundle,
    verify_asr_adversarial_corpus_record_v1,
)


class ASRAdversarialCorpusDerivativeError(
    ValueError
):
    """Raised when a deterministic derivative cannot be trusted."""


class ASRAdversarialAudioTransformer(
    Protocol
):
    tool_key: str
    reported_version: str
    transform_environment_sha256: str
    recipe_argv: tuple[str, ...]

    def transform_pcm16k(
        self,
        *,
        input_path: Path,
        output_path: Path,
    ) -> ASRAdversarialFFmpegTransformResult:
        ...


@dataclass(frozen=True, slots=True)
class ASRAdversarialGeneratedDerivative:
    """Verified facts for one generated derivative."""

    case_id: str
    source_relative_path: str
    output_relative_path: str
    parent_audio_sha256: str
    audio_asset_sha256: str
    byte_length: int
    duration_ms: int
    sample_rate_hz: int
    channel_count: int
    codec_name: str
    provenance_record_sha256: str
    rights_record_sha256: str
    transformation_record_sha256: str
    transformer_environment_sha256: str
    development_evidence_only: bool = True


def _require_case_id(
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
    ):
        raise ASRAdversarialCorpusDerivativeError(
            "derivative case id is invalid."
        )

    return value


def _relative_path(
    value: object,
) -> PurePosixPath:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\\" in value
    ):
        raise ASRAdversarialCorpusDerivativeError(
            "derivative relative path is invalid."
        )

    path = PurePosixPath(
        value
    )

    if (
        path.is_absolute()
        or ".." in path.parts
        or "." in path.parts
        or len(path.parts) < 2
        or str(path) != value
    ):
        raise ASRAdversarialCorpusDerivativeError(
            "derivative relative path is invalid."
        )

    return path


def _resolve_existing_root(
    root: str | Path,
    *,
    name: str,
) -> Path:
    if not isinstance(
        root,
        (str, Path),
    ):
        raise ASRAdversarialCorpusDerivativeError(
            f"{name} is invalid."
        )

    supplied = Path(
        root
    )

    if supplied.is_symlink():
        raise ASRAdversarialCorpusDerivativeError(
            f"{name} cannot be a symlink."
        )

    try:
        resolved = supplied.resolve(
            strict=True
        )
    except (OSError, RuntimeError) as exc:
        raise ASRAdversarialCorpusDerivativeError(
            f"{name} is unavailable."
        ) from exc

    if not resolved.is_dir():
        raise ASRAdversarialCorpusDerivativeError(
            f"{name} must be a directory."
        )

    return resolved


def _resolve_direct_file(
    *,
    root: Path,
    relative_path: str,
    name: str,
) -> Path:
    relative = _relative_path(
        relative_path
    )

    current = root

    for part in relative.parts:
        current = (
            current
            / part
        )

        if current.is_symlink():
            raise ASRAdversarialCorpusDerivativeError(
                f"{name} path cannot contain symlinks."
            )

    try:
        resolved = current.resolve(
            strict=True
        )
    except (OSError, RuntimeError) as exc:
        raise ASRAdversarialCorpusDerivativeError(
            f"{name} is unavailable."
        ) from exc

    if (
        not resolved.is_relative_to(
            root
        )
        or not resolved.is_file()
    ):
        raise ASRAdversarialCorpusDerivativeError(
            f"{name} is unavailable."
        )

    return resolved


def _ensure_output_path(
    *,
    generated_root: Path,
    relative_path: str,
) -> Path:
    relative = _relative_path(
        relative_path
    )

    current = generated_root

    for part in relative.parts[:-1]:
        current = (
            current
            / part
        )

        if current.is_symlink():
            raise ASRAdversarialCorpusDerivativeError(
                "derivative output path cannot contain symlinks."
            )

        if current.exists():
            if not current.is_dir():
                raise ASRAdversarialCorpusDerivativeError(
                    "derivative output parent must be a directory."
                )
            continue

        try:
            current.mkdir()
        except FileExistsError:
            pass
        except OSError as exc:
            raise ASRAdversarialCorpusDerivativeError(
                "derivative output parent could not be created."
            ) from exc

        if (
            current.is_symlink()
            or not current.is_dir()
        ):
            raise ASRAdversarialCorpusDerivativeError(
                "derivative output path cannot contain symlinks."
            )

    destination = (
        generated_root
        / Path(
            *relative.parts
        )
    )

    try:
        resolved_parent = (
            destination.parent.resolve(
                strict=True
            )
        )
    except (OSError, RuntimeError) as exc:
        raise ASRAdversarialCorpusDerivativeError(
            "derivative output parent is unavailable."
        ) from exc

    if not resolved_parent.is_relative_to(
        generated_root
    ):
        raise ASRAdversarialCorpusDerivativeError(
            "derivative output escapes generated root."
        )

    if destination.is_symlink():
        raise ASRAdversarialCorpusDerivativeError(
            "derivative output cannot be a symlink."
        )

    return destination


def _hash(
    path: Path,
) -> tuple[str, int]:
    try:
        sha256, byte_length = (
            calculate_content_sha256(
                path
            )
        )
    except OSError as exc:
        raise ASRAdversarialCorpusDerivativeError(
            "derivative audio could not be read."
        ) from exc

    if byte_length <= 0:
        raise ASRAdversarialCorpusDerivativeError(
            "derivative audio must not be empty."
        )

    return (
        sha256,
        byte_length,
    )


def _load_record(
    *,
    corpus_root: Path,
    relative_path: str,
) -> ASRAdversarialCorpusRecordBundle:
    path = _resolve_direct_file(
        root=corpus_root,
        relative_path=relative_path,
        name="derivative record",
    )

    try:
        document = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise ASRAdversarialCorpusDerivativeError(
            "derivative record could not be loaded."
        ) from exc

    if (
        not isinstance(document, dict)
        or set(document)
        != {
            "payload",
            "sha256",
        }
    ):
        raise ASRAdversarialCorpusDerivativeError(
            "derivative record document is invalid."
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
    except (TypeError, ValueError) as exc:
        raise ASRAdversarialCorpusDerivativeError(
            "derivative record verification failed."
        ) from exc


def _entry_for_case(
    *,
    bundle: ASRAdversarialCorpusRecordBundle,
    case_id: str,
    name: str,
) -> dict[str, object]:
    try:
        entries = bundle.payload[
            "record"
        ]["entries"]
    except (KeyError, TypeError) as exc:
        raise ASRAdversarialCorpusDerivativeError(
            f"{name} is invalid."
        ) from exc

    if not isinstance(
        entries,
        list,
    ):
        raise ASRAdversarialCorpusDerivativeError(
            f"{name} is invalid."
        )

    matches = [
        entry
        for entry in entries
        if (
            isinstance(entry, dict)
            and entry.get(
                "case_id"
            )
            == case_id
        )
    ]

    if len(matches) != 1:
        raise ASRAdversarialCorpusDerivativeError(
            f"{name} must contain exactly one matching case."
        )

    return matches[0]


def _probe_and_require(
    *,
    probe: ASRAdversarialMediaProbe,
    path: Path,
    expected: dict[str, object],
) -> ASRAdversarialMeasuredMedia:
    try:
        measured = probe.probe(
            path
        )
    except Exception as exc:
        raise ASRAdversarialCorpusDerivativeError(
            "derivative media verification failed."
        ) from exc

    if not isinstance(
        measured,
        ASRAdversarialMeasuredMedia,
    ):
        raise ASRAdversarialCorpusDerivativeError(
            "derivative media probe returned invalid evidence."
        )

    if (
        measured.sample_rate_hz
        != expected[
            "sample_rate_hz"
        ]
        or measured.channel_count
        != expected[
            "channel_count"
        ]
        or measured.codec_name
        != expected[
            "codec_name"
        ]
    ):
        raise ASRAdversarialCorpusDerivativeError(
            "derivative media does not match "
            "the transformation record."
        )

    return measured


def generate_asr_adversarial_derivative_v1(
    *,
    corpus_root: str | Path,
    generated_root: str | Path,
    case_id: str,
    transformer: ASRAdversarialAudioTransformer,
    probe: ASRAdversarialMediaProbe,
) -> ASRAdversarialGeneratedDerivative:
    case_id = _require_case_id(
        case_id
    )

    corpus = _resolve_existing_root(
        corpus_root,
        name="adversarial corpus root",
    )

    generated = _resolve_existing_root(
        generated_root,
        name="adversarial generated root",
    )

    source_plan = _load_record(
        corpus_root=corpus,
        relative_path=(
            "specification/generation-plan.json"
        ),
    )

    derivative_plan = _load_record(
        corpus_root=corpus,
        relative_path=(
            "specification/derivative-plan.json"
        ),
    )

    source_entry = _entry_for_case(
        bundle=source_plan,
        case_id=case_id,
        name="source generation plan",
    )

    derivative_entry = _entry_for_case(
        bundle=derivative_plan,
        case_id=case_id,
        name="derivative generation plan",
    )

    transformation_sha256 = (
        derivative_entry.get(
            "transformation_record_sha256"
        )
    )

    if not isinstance(
        transformation_sha256,
        str,
    ):
        raise ASRAdversarialCorpusDerivativeError(
            "derivative plan requires a transformation commitment."
        )

    transformation = _load_record(
        corpus_root=corpus,
        relative_path=(
            "records/transformations/"
            f"{case_id}.json"
        ),
    )

    if (
        transformation.sha256
        != transformation_sha256
    ):
        raise ASRAdversarialCorpusDerivativeError(
            "derivative transformation commitment does not match."
        )

    if (
        source_entry.get(
            "transformation_record_sha256"
        )
        is not None
    ):
        raise ASRAdversarialCorpusDerivativeError(
            "source generation plan unexpectedly contains "
            "a transformation."
        )

    for field in (
        "provenance_record_sha256",
        "rights_record_sha256",
    ):
        if (
            source_entry.get(
                field
            )
            != derivative_entry.get(
                field
            )
        ):
            raise ASRAdversarialCorpusDerivativeError(
                "derivative provenance/rights binding does not "
                "match the source."
            )

    transform_record = (
        transformation.payload[
            "record"
        ]
    )

    if (
        transform_record.get(
            "case_id"
        )
        != case_id
    ):
        raise ASRAdversarialCorpusDerivativeError(
            "transformation case does not match."
        )

    expected_output = (
        transform_record.get(
            "expected_output"
        )
    )

    if not isinstance(
        expected_output,
        dict,
    ):
        raise ASRAdversarialCorpusDerivativeError(
            "transformation expected output is invalid."
        )

    if (
        derivative_entry.get(
            "output_relative_path"
        )
        != expected_output.get(
            "relative_path"
        )
    ):
        raise ASRAdversarialCorpusDerivativeError(
            "derivative output path does not match "
            "the transformation record."
        )

    tool = transform_record.get(
        "tool"
    )

    if not isinstance(
        tool,
        dict,
    ):
        raise ASRAdversarialCorpusDerivativeError(
            "transformation tool identity is invalid."
        )

    if (
        getattr(
            transformer,
            "tool_key",
            None,
        )
        != tool.get(
            "key"
        )
        or getattr(
            transformer,
            "reported_version",
            None,
        )
        != tool.get(
            "version"
        )
        or getattr(
            transformer,
            "transform_environment_sha256",
            None,
        )
        != tool.get(
            "environment_sha256"
        )
        or list(
            getattr(
                transformer,
                "recipe_argv",
                (),
            )
        )
        != transform_record.get(
            "argv"
        )
    ):
        raise ASRAdversarialCorpusDerivativeError(
            "runtime transformer does not match "
            "the committed transformation record."
        )

    source_relative_path = (
        source_entry.get(
            "output_relative_path"
        )
    )

    if not isinstance(
        source_relative_path,
        str,
    ):
        raise ASRAdversarialCorpusDerivativeError(
            "source output path is invalid."
        )

    source = _resolve_direct_file(
        root=generated,
        relative_path=source_relative_path,
        name="generated source audio",
    )

    (
        observed_parent_sha256,
        observed_parent_byte_length,
    ) = _hash(
        source
    )

    if (
        observed_parent_sha256
        != transform_record.get(
            "parent_audio_sha256"
        )
    ):
        raise ASRAdversarialCorpusDerivativeError(
            "generated source does not match "
            "the transformation parent commitment."
        )

    output_relative_path = (
        derivative_entry[
            "output_relative_path"
        ]
    )

    destination = _ensure_output_path(
        generated_root=generated,
        relative_path=output_relative_path,
    )

    with tempfile.TemporaryDirectory(
        prefix=".hetren-derivative-",
        dir=destination.parent,
    ) as temporary_directory:
        temporary_output = (
            Path(
                temporary_directory
            )
            / destination.name
        )

        try:
            transform_result = (
                transformer.transform_pcm16k(
                    input_path=source,
                    output_path=temporary_output,
                )
            )
        except Exception as exc:
            raise ASRAdversarialCorpusDerivativeError(
                "deterministic derivative transformation failed."
            ) from exc

        if not isinstance(
            transform_result,
            ASRAdversarialFFmpegTransformResult,
        ):
            raise ASRAdversarialCorpusDerivativeError(
                "transformer returned invalid derivative evidence."
            )

        if (
            transform_result.parent_audio_sha256
            != observed_parent_sha256
            or transform_result.parent_byte_length
            != observed_parent_byte_length
        ):
            raise ASRAdversarialCorpusDerivativeError(
                "transformer parent evidence does not match "
                "the generated source."
            )

        (
            temporary_sha256,
            temporary_byte_length,
        ) = _hash(
            temporary_output
        )

        if (
            temporary_sha256
            != transform_result.output_audio_sha256
            or temporary_byte_length
            != transform_result.output_byte_length
        ):
            raise ASRAdversarialCorpusDerivativeError(
                "transformer output evidence does not match "
                "the generated derivative."
            )

        temporary_media = _probe_and_require(
            probe=probe,
            path=temporary_output,
            expected=expected_output,
        )

        if destination.exists():
            if (
                destination.is_symlink()
                or not destination.is_file()
            ):
                raise ASRAdversarialCorpusDerivativeError(
                    "existing derivative output is invalid."
                )

            (
                existing_sha256,
                existing_byte_length,
            ) = _hash(
                destination
            )

            if (
                existing_sha256
                != temporary_sha256
                or existing_byte_length
                != temporary_byte_length
            ):
                raise ASRAdversarialCorpusDerivativeError(
                    "existing derivative output conflicts "
                    "with deterministic generation."
                )
        else:
            try:
                os.link(
                    temporary_output,
                    destination,
                    follow_symlinks=False,
                )
            except FileExistsError:
                if (
                    destination.is_symlink()
                    or not destination.is_file()
                ):
                    raise ASRAdversarialCorpusDerivativeError(
                        "concurrent derivative publication "
                        "created an invalid output."
                    )

                (
                    existing_sha256,
                    existing_byte_length,
                ) = _hash(
                    destination
                )

                if (
                    existing_sha256
                    != temporary_sha256
                    or existing_byte_length
                    != temporary_byte_length
                ):
                    raise ASRAdversarialCorpusDerivativeError(
                        "concurrent derivative publication conflict."
                    )
            except OSError as exc:
                raise ASRAdversarialCorpusDerivativeError(
                    "derivative output could not be published."
                ) from exc

    (
        published_sha256,
        published_byte_length,
    ) = _hash(
        destination
    )

    published_media = _probe_and_require(
        probe=probe,
        path=destination,
        expected=expected_output,
    )

    if (
        published_sha256
        != temporary_sha256
        or published_byte_length
        != temporary_byte_length
        or published_media
        != temporary_media
    ):
        raise ASRAdversarialCorpusDerivativeError(
            "published derivative changed after verification."
        )

    return ASRAdversarialGeneratedDerivative(
        case_id=case_id,
        source_relative_path=(
            source_relative_path
        ),
        output_relative_path=(
            output_relative_path
        ),
        parent_audio_sha256=(
            observed_parent_sha256
        ),
        audio_asset_sha256=(
            published_sha256
        ),
        byte_length=(
            published_byte_length
        ),
        duration_ms=(
            published_media.duration_ms
        ),
        sample_rate_hz=(
            published_media.sample_rate_hz
        ),
        channel_count=(
            published_media.channel_count
        ),
        codec_name=(
            published_media.codec_name
        ),
        provenance_record_sha256=(
            derivative_entry[
                "provenance_record_sha256"
            ]
        ),
        rights_record_sha256=(
            derivative_entry[
                "rights_record_sha256"
            ]
        ),
        transformation_record_sha256=(
            transformation.sha256
        ),
        transformer_environment_sha256=(
            transformer.transform_environment_sha256
        ),
    )

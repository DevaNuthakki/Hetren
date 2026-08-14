"""Deterministic FFmpeg transformation adapter for adversarial ASR audio.

This adapter applies one source-visible, fixed transformation recipe:
normalize an existing audio source to 16 kHz mono PCM signed 16-bit WAV.

Security and reproducibility properties:
- caller supplies one explicit absolute FFmpeg executable path;
- executable bytes are SHA-256 committed;
- executable bytes are reverified around every invocation;
- tool version output is committed;
- transformation recipe uses fixed argv with explicit placeholders;
- subprocess invocation uses shell=False;
- stdin is disabled;
- locale is fixed;
- stdout/stderr use bounded temporary files;
- raw stderr and absolute media paths are never durable evidence;
- input audio identity is verified unchanged across transformation;
- existing outputs are never overwritten by this adapter.

This module does not perform ASR, infer acoustic conditions, adjudicate
rights, apply qualification thresholds, issue certification, authorize
production use, or modify release authority.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from app.content_hashing import (
    calculate_content_sha256,
)


ASR_ADVERSARIAL_FFMPEG_SCHEMA_VERSION = 1
ASR_ADVERSARIAL_FFMPEG_KEY = (
    "hetren.ffmpeg-audio-transform"
)
ASR_ADVERSARIAL_FFMPEG_VERSION = "1.0.0"
ASR_ADVERSARIAL_FFMPEG_TOOL_KEY = "ffmpeg"

ASR_ADVERSARIAL_FFMPEG_PCM16K_RECIPE_KEY = (
    "pcm-s16le-mono-16000-v1"
)

ASR_ADVERSARIAL_FFMPEG_PCM16K_ARGV = (
    "-hide_banner",
    "-loglevel",
    "error",
    "-nostdin",
    "-n",
    "-i",
    "{input}",
    "-map_metadata",
    "-1",
    "-ar",
    "16000",
    "-ac",
    "1",
    "-c:a",
    "pcm_s16le",
    "{output}",
)

ASR_ADVERSARIAL_FFMPEG_PCM8K_RECIPE_KEY = (
    "pcm-s16le-mono-8000-v1"
)
ASR_ADVERSARIAL_FFMPEG_PCM8K_ARGV = (
    "-hide_banner",
    "-loglevel",
    "error",
    "-nostdin",
    "-n",
    "-i",
    "{input}",
    "-map_metadata",
    "-1",
    "-ar",
    "8000",
    "-ac",
    "1",
    "-c:a",
    "pcm_s16le",
    "{output}",
)

ASR_ADVERSARIAL_FFMPEG_MULAW8K_RECIPE_KEY = (
    "pcm-mulaw-mono-8000-v1"
)
ASR_ADVERSARIAL_FFMPEG_MULAW8K_ARGV = (
    "-hide_banner",
    "-loglevel",
    "error",
    "-nostdin",
    "-n",
    "-i",
    "{input}",
    "-map_metadata",
    "-1",
    "-ar",
    "8000",
    "-ac",
    "1",
    "-c:a",
    "pcm_mulaw",
    "{output}",
)

ASR_ADVERSARIAL_FFMPEG_ALAW8K_RECIPE_KEY = (
    "pcm-alaw-mono-8000-v1"
)
ASR_ADVERSARIAL_FFMPEG_ALAW8K_ARGV = (
    "-hide_banner",
    "-loglevel",
    "error",
    "-nostdin",
    "-n",
    "-i",
    "{input}",
    "-map_metadata",
    "-1",
    "-ar",
    "8000",
    "-ac",
    "1",
    "-c:a",
    "pcm_alaw",
    "{output}",
)

ASR_ADVERSARIAL_FFMPEG_NOISE_MODERATE_RECIPE_KEY = (
    "white-noise-multi-number-id-moderate-16000-v1"
)

ASR_ADVERSARIAL_FFMPEG_NOISE_MODERATE_ARGV = (
    "-hide_banner",
    "-loglevel",
    "error",
    "-nostdin",
    "-n",
    "-filter_complex_threads",
    "1",
    "-i",
    "{input}",
    "-filter_complex",
    (
        "anoisesrc="
        "sample_rate=16000:"
        "amplitude=1:"
        "color=white:"
        "seed=39039"
        "[noise];"
        "[noise]"
        "volume=0.050141109355923044:"
        "precision=double"
        "[scaled_noise];"
        "[0:a][scaled_noise]"
        "amix="
        "inputs=2:"
        "duration=first:"
        "dropout_transition=0:"
        "normalize=0"
        "[mixed]"
    ),
    "-map",
    "[mixed]",
    "-map_metadata",
    "-1",
    "-ar",
    "16000",
    "-ac",
    "1",
    "-threads",
    "1",
    "-c:a",
    "pcm_s16le",
    "{output}",
)

ASR_ADVERSARIAL_FFMPEG_NOISE_SEVERE_USABLE_RECIPE_KEY = (
    "white-noise-multi-number-id-severe-usable-16000-v1"
)

ASR_ADVERSARIAL_FFMPEG_NOISE_SEVERE_USABLE_ARGV = (
    "-hide_banner",
    "-loglevel",
    "error",
    "-nostdin",
    "-n",
    "-filter_complex_threads",
    "1",
    "-i",
    "{input}",
    "-filter_complex",
    (
        "anoisesrc="
        "sample_rate=16000:"
        "amplitude=1:"
        "color=white:"
        "seed=39039"
        "[noise];"
        "[noise]"
        "volume=0.089164902364147938:"
        "precision=double"
        "[scaled_noise];"
        "[0:a][scaled_noise]"
        "amix="
        "inputs=2:"
        "duration=first:"
        "dropout_transition=0:"
        "normalize=0"
        "[mixed]"
    ),
    "-map",
    "[mixed]",
    "-map_metadata",
    "-1",
    "-ar",
    "16000",
    "-ac",
    "1",
    "-threads",
    "1",
    "-c:a",
    "pcm_s16le",
    "{output}",
)

_RECIPE_KEY_PATTERN = re.compile(
    r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$"
)
_CODEC_NAME_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9_]*$"
)

DEFAULT_FFMPEG_TIMEOUT_SECONDS = 30.0
DEFAULT_FFMPEG_MAX_OUTPUT_BYTES = 256 * 1024


class ASRAdversarialFFmpegError(ValueError):
    """Raised when deterministic FFmpeg transformation cannot be trusted."""


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
        raise ASRAdversarialFFmpegError(
            "FFmpeg environment must contain deterministic JSON."
        ) from exc


def _sha256_bytes(
    value: bytes,
) -> str:
    return hashlib.sha256(
        value
    ).hexdigest()


def _require_positive_number(
    *,
    name: str,
    value: object,
) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(
            value,
            (int, float),
        )
        or value <= 0
    ):
        raise ASRAdversarialFFmpegError(
            f"{name} must be positive."
        )

    return float(value)


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
        raise ASRAdversarialFFmpegError(
            f"{name} must be a positive integer."
        )

    return value


def _resolve_executable(
    executable_path: str | Path,
) -> Path:
    if not isinstance(
        executable_path,
        (str, Path),
    ):
        raise ASRAdversarialFFmpegError(
            "FFmpeg executable path is invalid."
        )

    supplied = Path(
        executable_path
    )

    if not supplied.is_absolute():
        raise ASRAdversarialFFmpegError(
            "FFmpeg executable path must be absolute."
        )

    try:
        resolved = supplied.resolve(
            strict=True
        )
    except (OSError, RuntimeError) as exc:
        raise ASRAdversarialFFmpegError(
            "FFmpeg executable is unavailable."
        ) from exc

    if (
        not resolved.is_file()
        or not os.access(
            resolved,
            os.X_OK,
        )
    ):
        raise ASRAdversarialFFmpegError(
            "FFmpeg executable is unavailable."
        )

    return resolved


def _hash_file(
    path: Path,
) -> tuple[str, int]:
    try:
        sha256, byte_length = (
            calculate_content_sha256(
                path
            )
        )
    except OSError as exc:
        raise ASRAdversarialFFmpegError(
            "FFmpeg content identity could not be read."
        ) from exc

    if byte_length <= 0:
        raise ASRAdversarialFFmpegError(
            "FFmpeg content identity cannot be empty."
        )

    return (
        sha256,
        byte_length,
    )


def _resolve_input(
    audio_path: Path,
) -> Path:
    if not isinstance(
        audio_path,
        Path,
    ):
        raise ASRAdversarialFFmpegError(
            "FFmpeg audio input path is invalid."
        )

    if not audio_path.is_absolute():
        raise ASRAdversarialFFmpegError(
            "FFmpeg audio input path must be absolute."
        )

    if audio_path.is_symlink():
        raise ASRAdversarialFFmpegError(
            "FFmpeg audio input cannot be a symlink."
        )

    try:
        resolved = audio_path.resolve(
            strict=True
        )
    except (OSError, RuntimeError) as exc:
        raise ASRAdversarialFFmpegError(
            "FFmpeg audio input is unavailable."
        ) from exc

    if not resolved.is_file():
        raise ASRAdversarialFFmpegError(
            "FFmpeg audio input is unavailable."
        )

    return resolved


def _resolve_output(
    output_path: Path,
) -> Path:
    if not isinstance(
        output_path,
        Path,
    ):
        raise ASRAdversarialFFmpegError(
            "FFmpeg audio output path is invalid."
        )

    if not output_path.is_absolute():
        raise ASRAdversarialFFmpegError(
            "FFmpeg audio output path must be absolute."
        )

    if (
        output_path.is_symlink()
        or output_path.exists()
    ):
        raise ASRAdversarialFFmpegError(
            "FFmpeg audio output must not already exist."
        )

    parent = output_path.parent

    if parent.is_symlink():
        raise ASRAdversarialFFmpegError(
            "FFmpeg audio output parent cannot be a symlink."
        )

    try:
        resolved_parent = parent.resolve(
            strict=True
        )
    except (OSError, RuntimeError) as exc:
        raise ASRAdversarialFFmpegError(
            "FFmpeg audio output parent is unavailable."
        ) from exc

    if not resolved_parent.is_dir():
        raise ASRAdversarialFFmpegError(
            "FFmpeg audio output parent must be a directory."
        )

    return (
        resolved_parent
        / output_path.name
    )


@dataclass(frozen=True, slots=True)
class ASRAdversarialFFmpegRecipe:
    """One explicit deterministic FFmpeg audio recipe."""

    recipe_key: str
    argv: tuple[str, ...]
    sample_rate_hz: int
    channel_count: int
    codec_name: str

    def __post_init__(self) -> None:
        if (
            not isinstance(
                self.recipe_key,
                str,
            )
            or _RECIPE_KEY_PATTERN.fullmatch(
                self.recipe_key
            )
            is None
        ):
            raise ASRAdversarialFFmpegError(
                "FFmpeg recipe key must be canonical lowercase text."
            )

        if (
            not isinstance(
                self.argv,
                tuple,
            )
            or not self.argv
        ):
            raise ASRAdversarialFFmpegError(
                "FFmpeg recipe argv must be a non-empty tuple."
            )

        for argument in self.argv:
            if (
                not isinstance(
                    argument,
                    str,
                )
                or not argument
                or "\x00" in argument
            ):
                raise ASRAdversarialFFmpegError(
                    "FFmpeg recipe argv contains an invalid argument."
                )

        if self.argv.count(
            "{input}"
        ) != 1:
            raise ASRAdversarialFFmpegError(
                "FFmpeg recipe requires exactly one input placeholder."
            )

        if self.argv.count(
            "{output}"
        ) != 1:
            raise ASRAdversarialFFmpegError(
                "FFmpeg recipe requires exactly one output placeholder."
            )

        _require_positive_integer(
            name="FFmpeg recipe sample rate",
            value=self.sample_rate_hz,
        )

        _require_positive_integer(
            name="FFmpeg recipe channel count",
            value=self.channel_count,
        )

        if (
            not isinstance(
                self.codec_name,
                str,
            )
            or _CODEC_NAME_PATTERN.fullmatch(
                self.codec_name
            )
            is None
        ):
            raise ASRAdversarialFFmpegError(
                "FFmpeg recipe codec name must be "
                "canonical lowercase text."
            )


ASR_ADVERSARIAL_FFMPEG_PCM16K_RECIPE = (
    ASRAdversarialFFmpegRecipe(
        recipe_key=(
            ASR_ADVERSARIAL_FFMPEG_PCM16K_RECIPE_KEY
        ),
        argv=(
            ASR_ADVERSARIAL_FFMPEG_PCM16K_ARGV
        ),
        sample_rate_hz=16_000,
        channel_count=1,
        codec_name="pcm_s16le",
    )
)

ASR_ADVERSARIAL_FFMPEG_PCM8K_RECIPE = (
    ASRAdversarialFFmpegRecipe(
        recipe_key=(
            ASR_ADVERSARIAL_FFMPEG_PCM8K_RECIPE_KEY
        ),
        argv=(
            ASR_ADVERSARIAL_FFMPEG_PCM8K_ARGV
        ),
        sample_rate_hz=8_000,
        channel_count=1,
        codec_name="pcm_s16le",
    )
)

ASR_ADVERSARIAL_FFMPEG_MULAW8K_RECIPE = (
    ASRAdversarialFFmpegRecipe(
        recipe_key=(
            ASR_ADVERSARIAL_FFMPEG_MULAW8K_RECIPE_KEY
        ),
        argv=(
            ASR_ADVERSARIAL_FFMPEG_MULAW8K_ARGV
        ),
        sample_rate_hz=8_000,
        channel_count=1,
        codec_name="pcm_mulaw",
    )
)

ASR_ADVERSARIAL_FFMPEG_ALAW8K_RECIPE = (
    ASRAdversarialFFmpegRecipe(
        recipe_key=(
            ASR_ADVERSARIAL_FFMPEG_ALAW8K_RECIPE_KEY
        ),
        argv=(
            ASR_ADVERSARIAL_FFMPEG_ALAW8K_ARGV
        ),
        sample_rate_hz=8_000,
        channel_count=1,
        codec_name="pcm_alaw",
    )
)

ASR_ADVERSARIAL_FFMPEG_NOISE_MODERATE_RECIPE = (
    ASRAdversarialFFmpegRecipe(
        recipe_key=(
            ASR_ADVERSARIAL_FFMPEG_NOISE_MODERATE_RECIPE_KEY
        ),
        argv=(
            ASR_ADVERSARIAL_FFMPEG_NOISE_MODERATE_ARGV
        ),
        sample_rate_hz=16_000,
        channel_count=1,
        codec_name="pcm_s16le",
    )
)

ASR_ADVERSARIAL_FFMPEG_NOISE_SEVERE_USABLE_RECIPE = (
    ASRAdversarialFFmpegRecipe(
        recipe_key=(
            ASR_ADVERSARIAL_FFMPEG_NOISE_SEVERE_USABLE_RECIPE_KEY
        ),
        argv=(
            ASR_ADVERSARIAL_FFMPEG_NOISE_SEVERE_USABLE_ARGV
        ),
        sample_rate_hz=16_000,
        channel_count=1,
        codec_name="pcm_s16le",
    )
)


@dataclass(frozen=True, slots=True)
class ASRAdversarialFFmpegTransformResult:
    """Observed content identities around one deterministic transformation."""

    parent_audio_sha256: str
    parent_byte_length: int
    output_audio_sha256: str
    output_byte_length: int


class ASRAdversarialFFmpeg:
    """Concrete deterministic 16 kHz PCM transformer backed by FFmpeg."""

    transformer_key = (
        ASR_ADVERSARIAL_FFMPEG_KEY
    )
    transformer_version = (
        ASR_ADVERSARIAL_FFMPEG_VERSION
    )
    tool_key = (
        ASR_ADVERSARIAL_FFMPEG_TOOL_KEY
    )
    recipe_key = (
        ASR_ADVERSARIAL_FFMPEG_PCM16K_RECIPE_KEY
    )
    recipe_argv = (
        ASR_ADVERSARIAL_FFMPEG_PCM16K_ARGV
    )

    def __init__(
        self,
        *,
        executable_path: str | Path,
        timeout_seconds: float = (
            DEFAULT_FFMPEG_TIMEOUT_SECONDS
        ),
        max_output_bytes: int = (
            DEFAULT_FFMPEG_MAX_OUTPUT_BYTES
        ),
        recipe: ASRAdversarialFFmpegRecipe | None = None,
    ) -> None:
        if recipe is None:
            selected_recipe = (
                ASR_ADVERSARIAL_FFMPEG_PCM16K_RECIPE
            )
        elif isinstance(
            recipe,
            ASRAdversarialFFmpegRecipe,
        ):
            selected_recipe = recipe
        else:
            raise ASRAdversarialFFmpegError(
                "FFmpeg recipe is invalid."
            )

        self._recipe = selected_recipe

        # Preserve the original public attributes used by the
        # I2 derivative service and committed transformation records.
        self.recipe_key = (
            selected_recipe.recipe_key
        )
        self.recipe_argv = (
            selected_recipe.argv
        )

        self._timeout_seconds = (
            _require_positive_number(
                name="FFmpeg timeout",
                value=timeout_seconds,
            )
        )

        self._max_output_bytes = (
            _require_positive_integer(
                name="FFmpeg maximum output bytes",
                value=max_output_bytes,
            )
        )

        self._executable_path = (
            _resolve_executable(
                executable_path
            )
        )

        (
            self._executable_sha256,
            _executable_byte_length,
        ) = _hash_file(
            self._executable_path
        )

        version_output = self._run_tool(
            ("-version",)
        )

        self._reported_version = (
            self._parse_version_output(
                version_output
            )
        )

        self._transform_environment_payload = {
            "schema_version": (
                ASR_ADVERSARIAL_FFMPEG_SCHEMA_VERSION
            ),
            "adapter": {
                "key": self.transformer_key,
                "version": (
                    self.transformer_version
                ),
            },
            "tool": {
                "key": self.tool_key,
                "reported_version": (
                    self._reported_version
                ),
                "executable_sha256": (
                    self._executable_sha256
                ),
                "version_output_sha256": (
                    _sha256_bytes(
                        version_output
                    )
                ),
            },
            "transformation": {
                "recipe_key": self.recipe_key,
                "argv": list(
                    self.recipe_argv
                ),
                "sample_rate_hz": (
                    self._recipe.sample_rate_hz
                ),
                "channel_count": (
                    self._recipe.channel_count
                ),
                "codec_name": (
                    self._recipe.codec_name
                ),
                "metadata_policy": (
                    "strip-input-metadata-v1"
                ),
            },
            "process": {
                "shell": False,
                "locale": "C",
                "stdin": "disabled",
                "stdout_stderr_memory_capture": False,
                "timeout_seconds": (
                    self._timeout_seconds
                ),
                "max_output_bytes": (
                    self._max_output_bytes
                ),
            },
        }

        self.transform_environment_sha256 = (
            hashlib.sha256(
                _canonical_json(
                    self._transform_environment_payload
                ).encode("utf-8")
            ).hexdigest()
        )

    @property
    def recipe(
        self,
    ) -> ASRAdversarialFFmpegRecipe:
        return self._recipe

    @property
    def reported_version(
        self,
    ) -> str:
        return self._reported_version

    @property
    def executable_sha256(
        self,
    ) -> str:
        return self._executable_sha256

    @property
    def transform_environment_payload(
        self,
    ) -> dict[str, object]:
        return deepcopy(
            self._transform_environment_payload
        )

    def _verify_executable_unchanged(
        self,
    ) -> None:
        current_sha256, _byte_length = (
            _hash_file(
                self._executable_path
            )
        )

        if (
            current_sha256
            != self._executable_sha256
        ):
            raise ASRAdversarialFFmpegError(
                "FFmpeg executable changed "
                "after environment verification."
            )

    def _run_tool(
        self,
        arguments: tuple[str, ...],
    ) -> bytes:
        self._verify_executable_unchanged()

        command = [
            str(
                self._executable_path
            ),
            *arguments,
        ]

        controlled_environment = {
            "LC_ALL": "C",
            "LANG": "C",
        }

        with tempfile.TemporaryFile() as stdout_file:
            with tempfile.TemporaryFile() as stderr_file:
                try:
                    completed = subprocess.run(
                        command,
                        stdin=subprocess.DEVNULL,
                        stdout=stdout_file,
                        stderr=stderr_file,
                        timeout=(
                            self._timeout_seconds
                        ),
                        check=False,
                        shell=False,
                        env=controlled_environment,
                    )
                except subprocess.TimeoutExpired as exc:
                    raise ASRAdversarialFFmpegError(
                        "FFmpeg execution timed out."
                    ) from exc
                except OSError as exc:
                    raise ASRAdversarialFFmpegError(
                        "FFmpeg execution failed."
                    ) from exc

                stdout_file.flush()
                stderr_file.flush()

                stdout_size = stdout_file.seek(
                    0,
                    os.SEEK_END,
                )
                stderr_size = stderr_file.seek(
                    0,
                    os.SEEK_END,
                )

                if (
                    stdout_size
                    > self._max_output_bytes
                    or stderr_size
                    > self._max_output_bytes
                ):
                    raise ASRAdversarialFFmpegError(
                        "FFmpeg output exceeded "
                        "the configured limit."
                    )

                if completed.returncode != 0:
                    raise ASRAdversarialFFmpegError(
                        "FFmpeg execution failed."
                    )

                stdout_file.seek(
                    0
                )
                output = stdout_file.read()

        self._verify_executable_unchanged()

        return output

    def _parse_version_output(
        self,
        output: bytes,
    ) -> str:
        try:
            text = output.decode(
                "utf-8",
                errors="strict",
            )
        except UnicodeDecodeError as exc:
            raise ASRAdversarialFFmpegError(
                "FFmpeg version output is not valid UTF-8."
            ) from exc

        lines = text.splitlines()

        if not lines:
            raise ASRAdversarialFFmpegError(
                "FFmpeg version output is invalid."
            )

        first_line = lines[0].strip()
        prefix = "ffmpeg version "

        if not first_line.startswith(
            prefix
        ):
            raise ASRAdversarialFFmpegError(
                "Configured executable is not FFmpeg."
            )

        remainder = first_line[
            len(prefix):
        ]

        if not remainder:
            raise ASRAdversarialFFmpegError(
                "FFmpeg reported version is invalid."
            )

        reported_version = remainder.split(
            maxsplit=1
        )[0]

        if (
            not reported_version
            or len(reported_version) > 200
            or any(
                character.isspace()
                for character in reported_version
            )
        ):
            raise ASRAdversarialFFmpegError(
                "FFmpeg reported version is invalid."
            )

        return reported_version

    def transform(
        self,
        *,
        input_path: Path,
        output_path: Path,
    ) -> ASRAdversarialFFmpegTransformResult:
        source = _resolve_input(
            input_path
        )
        destination = _resolve_output(
            output_path
        )

        (
            parent_sha256,
            parent_byte_length,
        ) = _hash_file(
            source
        )

        arguments = tuple(
            (
                str(source)
                if argument == "{input}"
                else str(destination)
                if argument == "{output}"
                else argument
            )
            for argument
            in self.recipe_argv
        )

        self._run_tool(
            arguments
        )

        if (
            destination.is_symlink()
            or not destination.is_file()
        ):
            raise ASRAdversarialFFmpegError(
                "FFmpeg transformation output is unavailable."
            )

        (
            output_sha256,
            output_byte_length,
        ) = _hash_file(
            destination
        )

        (
            parent_sha256_after,
            parent_byte_length_after,
        ) = _hash_file(
            source
        )

        if (
            parent_sha256_after
            != parent_sha256
            or parent_byte_length_after
            != parent_byte_length
        ):
            raise ASRAdversarialFFmpegError(
                "FFmpeg transformation input changed "
                "during execution."
            )

        return (
            ASRAdversarialFFmpegTransformResult(
                parent_audio_sha256=(
                    parent_sha256
                ),
                parent_byte_length=(
                    parent_byte_length
                ),
                output_audio_sha256=(
                    output_sha256
                ),
                output_byte_length=(
                    output_byte_length
                ),
            )
        )

    def transform_pcm16k(
        self,
        *,
        input_path: Path,
        output_path: Path,
    ) -> ASRAdversarialFFmpegTransformResult:
        """Run the frozen I2 PCM16K transformation only."""

        if (
            self._recipe
            != ASR_ADVERSARIAL_FFMPEG_PCM16K_RECIPE
        ):
            raise ASRAdversarialFFmpegError(
                "transform_pcm16k requires the "
                "frozen PCM16K recipe."
            )

        return self.transform(
            input_path=input_path,
            output_path=output_path,
        )


__all__ = [
    "ASR_ADVERSARIAL_FFMPEG_ALAW8K_ARGV",
    "ASR_ADVERSARIAL_FFMPEG_ALAW8K_RECIPE",
    "ASR_ADVERSARIAL_FFMPEG_ALAW8K_RECIPE_KEY",
    "ASR_ADVERSARIAL_FFMPEG_KEY",
    "ASR_ADVERSARIAL_FFMPEG_MULAW8K_ARGV",
    "ASR_ADVERSARIAL_FFMPEG_NOISE_MODERATE_ARGV",
    "ASR_ADVERSARIAL_FFMPEG_NOISE_MODERATE_RECIPE",
    "ASR_ADVERSARIAL_FFMPEG_NOISE_MODERATE_RECIPE_KEY",
    "ASR_ADVERSARIAL_FFMPEG_NOISE_SEVERE_USABLE_ARGV",
    "ASR_ADVERSARIAL_FFMPEG_NOISE_SEVERE_USABLE_RECIPE",
    "ASR_ADVERSARIAL_FFMPEG_NOISE_SEVERE_USABLE_RECIPE_KEY",
    "ASR_ADVERSARIAL_FFMPEG_MULAW8K_RECIPE",
    "ASR_ADVERSARIAL_FFMPEG_MULAW8K_RECIPE_KEY",
    "ASR_ADVERSARIAL_FFMPEG_PCM16K_ARGV",
    "ASR_ADVERSARIAL_FFMPEG_PCM16K_RECIPE",
    "ASR_ADVERSARIAL_FFMPEG_PCM16K_RECIPE_KEY",
    "ASR_ADVERSARIAL_FFMPEG_PCM8K_ARGV",
    "ASR_ADVERSARIAL_FFMPEG_PCM8K_RECIPE",
    "ASR_ADVERSARIAL_FFMPEG_PCM8K_RECIPE_KEY",
    "ASR_ADVERSARIAL_FFMPEG_SCHEMA_VERSION",
    "ASR_ADVERSARIAL_FFMPEG_TOOL_KEY",
    "ASR_ADVERSARIAL_FFMPEG_VERSION",
    "ASRAdversarialFFmpeg",
    "ASRAdversarialFFmpegError",
    "ASRAdversarialFFmpegRecipe",
    "ASRAdversarialFFmpegTransformResult",
    "DEFAULT_FFMPEG_MAX_OUTPUT_BYTES",
    "DEFAULT_FFMPEG_TIMEOUT_SECONDS",
]

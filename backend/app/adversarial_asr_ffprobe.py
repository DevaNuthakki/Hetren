"""Deterministic FFprobe adapter for adversarial ASR corpus verification.

The adapter converts one actual media file into the normalized media facts
consumed by the Slice H1 corpus-verification service.

Security and reproducibility properties:
- caller supplies one explicit executable path;
- the executable is resolved to an absolute regular executable file;
- executable bytes are SHA-256 committed;
- executable bytes are reverified before and after every invocation;
- subprocess invocation uses a fixed argument list with shell=False;
- stdin is disabled;
- locale is fixed;
- execution has a timeout;
- stdout/stderr are redirected to temporary files rather than accumulated
  unbounded in Python memory;
- oversized tool output is rejected before it is loaded;
- stderr and absolute paths are never included in durable evidence;
- FFprobe JSON is strictly validated and normalized deterministically.

This module does not perform ASR, persist database state, infer acoustic
conditions, adjudicate legal rights, apply qualification thresholds, issue
certification, authorize production use, or modify release authority.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from copy import deepcopy
from decimal import (
    Decimal,
    InvalidOperation,
    ROUND_HALF_UP,
)
from pathlib import Path

from app.adversarial_asr_corpus_verification_service import (
    ASRAdversarialMeasuredMedia,
)
from app.content_hashing import (
    calculate_content_sha256,
)


ASR_ADVERSARIAL_FFPROBE_SCHEMA_VERSION = 1
ASR_ADVERSARIAL_FFPROBE_KEY = (
    "hetren.ffprobe-media-probe"
)
ASR_ADVERSARIAL_FFPROBE_VERSION = "1.0.0"

ASR_ADVERSARIAL_FFPROBE_DURATION_POLICY = (
    "decimal-seconds-to-milliseconds-round-half-up-v1"
)

DEFAULT_FFPROBE_TIMEOUT_SECONDS = 10.0
DEFAULT_FFPROBE_MAX_OUTPUT_BYTES = 256 * 1024

_CODEC_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9._-]*$"
)


class ASRAdversarialFFprobeError(ValueError):
    """Raised when FFprobe media evidence cannot be trusted."""


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
        raise ASRAdversarialFFprobeError(
            "FFprobe environment must contain "
            "deterministic JSON."
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
        raise ASRAdversarialFFprobeError(
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
        raise ASRAdversarialFFprobeError(
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
        raise ASRAdversarialFFprobeError(
            "FFprobe executable path is invalid."
        )

    supplied = Path(
        executable_path
    )

    if not supplied.is_absolute():
        raise ASRAdversarialFFprobeError(
            "FFprobe executable path must be absolute."
        )

    try:
        resolved = supplied.resolve(
            strict=True
        )
    except (OSError, RuntimeError) as exc:
        raise ASRAdversarialFFprobeError(
            "FFprobe executable is unavailable."
        ) from exc

    if (
        not resolved.is_file()
        or not os.access(
            resolved,
            os.X_OK,
        )
    ):
        raise ASRAdversarialFFprobeError(
            "FFprobe executable is unavailable."
        )

    return resolved


def _hash_file(
    path: Path,
) -> str:
    try:
        digest, byte_length = (
            calculate_content_sha256(
                path
            )
        )
    except OSError as exc:
        raise ASRAdversarialFFprobeError(
            "FFprobe executable could not be read."
        ) from exc

    if byte_length <= 0:
        raise ASRAdversarialFFprobeError(
            "FFprobe executable must not be empty."
        )

    return digest


def _reject_json_constant(
    value: str,
):
    raise ValueError(
        f"unsupported JSON constant: {value}"
    )


def _normalize_duration_ms(
    value: object,
) -> int:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
    ):
        raise ASRAdversarialFFprobeError(
            "FFprobe duration is invalid."
        )

    try:
        seconds = Decimal(
            value
        )
    except InvalidOperation as exc:
        raise ASRAdversarialFFprobeError(
            "FFprobe duration is invalid."
        ) from exc

    if (
        not seconds.is_finite()
        or seconds <= 0
    ):
        raise ASRAdversarialFFprobeError(
            "FFprobe duration is invalid."
        )

    milliseconds = (
        seconds
        * Decimal("1000")
    ).quantize(
        Decimal("1"),
        rounding=ROUND_HALF_UP,
    )

    normalized = int(
        milliseconds
    )

    if normalized <= 0:
        raise ASRAdversarialFFprobeError(
            "FFprobe duration is invalid."
        )

    return normalized


def _parse_probe_payload(
    text: str,
) -> ASRAdversarialMeasuredMedia:
    try:
        payload = json.loads(
            text,
            parse_constant=(
                _reject_json_constant
            ),
        )
    except (
        json.JSONDecodeError,
        ValueError,
    ) as exc:
        raise ASRAdversarialFFprobeError(
            "FFprobe returned invalid JSON."
        ) from exc

    if (
        not isinstance(payload, dict)
        or set(payload)
        != {
            "programs",
            "streams",
            "format",
        }
    ):
        raise ASRAdversarialFFprobeError(
            "FFprobe returned an invalid media schema."
        )

    programs = payload[
        "programs"
    ]

    if programs != []:
        raise ASRAdversarialFFprobeError(
            "FFprobe media must not contain "
            "program metadata."
        )

    streams = payload[
        "streams"
    ]
    format_payload = payload[
        "format"
    ]

    if (
        not isinstance(streams, list)
        or len(streams) != 1
        or not isinstance(
            streams[0],
            dict,
        )
    ):
        raise ASRAdversarialFFprobeError(
            "FFprobe media must contain "
            "exactly one stream."
        )

    stream = streams[0]

    if set(stream) != {
        "codec_type",
        "codec_name",
        "sample_rate",
        "channels",
    }:
        raise ASRAdversarialFFprobeError(
            "FFprobe returned an invalid stream schema."
        )

    if stream[
        "codec_type"
    ] != "audio":
        raise ASRAdversarialFFprobeError(
            "FFprobe media stream must be audio."
        )

    codec_name = stream[
        "codec_name"
    ]

    if (
        not isinstance(codec_name, str)
        or _CODEC_PATTERN.fullmatch(
            codec_name
        )
        is None
    ):
        raise ASRAdversarialFFprobeError(
            "FFprobe codec name is invalid."
        )

    sample_rate_raw = stream[
        "sample_rate"
    ]

    if (
        not isinstance(
            sample_rate_raw,
            str,
        )
        or not sample_rate_raw.isdigit()
    ):
        raise ASRAdversarialFFprobeError(
            "FFprobe sample rate is invalid."
        )

    sample_rate_hz = int(
        sample_rate_raw
    )

    _require_positive_integer(
        name="FFprobe sample rate",
        value=sample_rate_hz,
    )

    channel_count = (
        _require_positive_integer(
            name="FFprobe channel count",
            value=stream[
                "channels"
            ],
        )
    )

    if (
        not isinstance(
            format_payload,
            dict,
        )
        or set(
            format_payload
        )
        != {
            "duration",
        }
    ):
        raise ASRAdversarialFFprobeError(
            "FFprobe returned an invalid format schema."
        )

    duration_ms = (
        _normalize_duration_ms(
            format_payload[
                "duration"
            ]
        )
    )

    return ASRAdversarialMeasuredMedia(
        duration_ms=duration_ms,
        sample_rate_hz=sample_rate_hz,
        channel_count=channel_count,
        codec_name=codec_name,
    )


class ASRAdversarialFFprobe:
    """Concrete deterministic media probe backed by FFprobe."""

    probe_key = (
        ASR_ADVERSARIAL_FFPROBE_KEY
    )
    probe_version = (
        ASR_ADVERSARIAL_FFPROBE_VERSION
    )

    def __init__(
        self,
        *,
        executable_path: str | Path,
        timeout_seconds: float = (
            DEFAULT_FFPROBE_TIMEOUT_SECONDS
        ),
        max_output_bytes: int = (
            DEFAULT_FFPROBE_MAX_OUTPUT_BYTES
        ),
    ):
        self._timeout_seconds = (
            _require_positive_number(
                name="FFprobe timeout",
                value=timeout_seconds,
            )
        )

        self._max_output_bytes = (
            _require_positive_integer(
                name="FFprobe maximum output bytes",
                value=max_output_bytes,
            )
        )

        self._executable_path = (
            _resolve_executable(
                executable_path
            )
        )

        self._executable_sha256 = (
            _hash_file(
                self._executable_path
            )
        )

        version_output = (
            self._run_tool(
                ("-version",)
            )
        )

        self._reported_version = (
            self._parse_version_output(
                version_output
            )
        )

        self._probe_environment_payload = {
            "schema_version": (
                ASR_ADVERSARIAL_FFPROBE_SCHEMA_VERSION
            ),
            "adapter": {
                "key": self.probe_key,
                "version": (
                    self.probe_version
                ),
            },
            "tool": {
                "name": "ffprobe",
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
            "normalization": {
                "duration_ms_policy": (
                    ASR_ADVERSARIAL_FFPROBE_DURATION_POLICY
                ),
                "sample_rate": (
                    "strict-positive-decimal-integer-string-v1"
                ),
                "channel_count": (
                    "strict-positive-json-integer-v1"
                ),
                "codec_name": (
                    "strict-canonical-ffprobe-token-v1"
                ),
                "stream_policy": (
                    "exactly-one-audio-stream-no-programs-v1"
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

        self.probe_environment_sha256 = (
            hashlib.sha256(
                _canonical_json(
                    self._probe_environment_payload
                ).encode("utf-8")
            ).hexdigest()
        )

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
    def probe_environment_payload(
        self,
    ) -> dict[str, object]:
        return deepcopy(
            self._probe_environment_payload
        )

    def _verify_executable_unchanged(
        self,
    ) -> None:
        current_sha256 = _hash_file(
            self._executable_path
        )

        if (
            current_sha256
            != self._executable_sha256
        ):
            raise ASRAdversarialFFprobeError(
                "FFprobe executable changed "
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
                    raise ASRAdversarialFFprobeError(
                        "FFprobe execution timed out."
                    ) from exc
                except OSError as exc:
                    raise ASRAdversarialFFprobeError(
                        "FFprobe execution failed."
                    ) from exc

                stdout_file.flush()
                stderr_file.flush()

                stdout_size = (
                    stdout_file.seek(
                        0,
                        os.SEEK_END,
                    )
                )
                stderr_size = (
                    stderr_file.seek(
                        0,
                        os.SEEK_END,
                    )
                )

                if (
                    stdout_size
                    > self._max_output_bytes
                    or stderr_size
                    > self._max_output_bytes
                ):
                    raise ASRAdversarialFFprobeError(
                        "FFprobe output exceeded "
                        "the configured limit."
                    )

                if completed.returncode != 0:
                    raise ASRAdversarialFFprobeError(
                        "FFprobe execution failed."
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
            raise ASRAdversarialFFprobeError(
                "FFprobe version output "
                "is not valid UTF-8."
            ) from exc

        lines = text.splitlines()

        if not lines:
            raise ASRAdversarialFFprobeError(
                "FFprobe version output is invalid."
            )

        first_line = lines[0].strip()
        prefix = "ffprobe version "

        if not first_line.startswith(
            prefix
        ):
            raise ASRAdversarialFFprobeError(
                "Configured executable is not FFprobe."
            )

        remainder = first_line[
            len(prefix):
        ]

        if not remainder:
            raise ASRAdversarialFFprobeError(
                "FFprobe reported version is invalid."
            )

        reported_version = remainder.split(
            maxsplit=1
        )[0]

        if (
            not reported_version
            or len(reported_version) > 200
            or any(
                character.isspace()
                for character
                in reported_version
            )
        ):
            raise ASRAdversarialFFprobeError(
                "FFprobe reported version is invalid."
            )

        return reported_version

    def probe(
        self,
        audio_path: Path,
    ) -> ASRAdversarialMeasuredMedia:
        if not isinstance(
            audio_path,
            Path,
        ):
            raise ASRAdversarialFFprobeError(
                "FFprobe audio path is invalid."
            )

        try:
            resolved = audio_path.resolve(
                strict=True
            )
        except (OSError, RuntimeError) as exc:
            raise ASRAdversarialFFprobeError(
                "FFprobe audio input is unavailable."
            ) from exc

        if not resolved.is_file():
            raise ASRAdversarialFFprobeError(
                "FFprobe audio input is unavailable."
            )

        output = self._run_tool(
            (
                "-v",
                "error",
                "-show_entries",
                (
                    "stream="
                    "codec_type,"
                    "codec_name,"
                    "sample_rate,"
                    "channels:"
                    "format=duration"
                ),
                "-of",
                "json",
                str(resolved),
            )
        )

        try:
            text = output.decode(
                "utf-8",
                errors="strict",
            )
        except UnicodeDecodeError as exc:
            raise ASRAdversarialFFprobeError(
                "FFprobe media output "
                "is not valid UTF-8."
            ) from exc

        return _parse_probe_payload(
            text
        )

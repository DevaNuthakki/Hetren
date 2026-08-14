"""Pinned eSpeak-NG source adapter for adversarial ASR corpus generation.

The adapter establishes the identity of the configured synthetic-speech
tool and executes it without a shell. It makes no claim that synthetic
speech establishes real human speaker, accent, microphone, or natural
conversation coverage.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ASR_ADVERSARIAL_ESPEAK_ADAPTER_KEY = (
    "hetren.espeak-ng-synthetic-speech"
)
ASR_ADVERSARIAL_ESPEAK_ADAPTER_VERSION = "1.0.0"

_MAX_TOOL_OUTPUT_BYTES = 64 * 1024
_TOOL_TIMEOUT_SECONDS = 20


class ASRAdversarialEspeakError(ValueError):
    """Raised when the pinned synthetic-speech adapter is invalid."""


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


def _canonical_sha256(
    value: object,
) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")

    return hashlib.sha256(
        encoded
    ).hexdigest()


def _controlled_environment() -> dict[str, str]:
    return {
        "LC_ALL": "C",
        "LANG": "C",
    }


def _require_executable(
    path: Path,
) -> Path:
    if not path.is_absolute():
        raise ASRAdversarialEspeakError(
            "synthetic-speech executable path "
            "must be absolute"
        )

    if path.is_symlink():
        raise ASRAdversarialEspeakError(
            "synthetic-speech executable "
            "cannot be a symlink"
        )

    try:
        resolved = path.resolve(
            strict=True
        )
    except OSError as exc:
        raise ASRAdversarialEspeakError(
            "synthetic-speech executable "
            "does not exist"
        ) from exc

    if (
        not resolved.is_file()
        or not os.access(
            resolved,
            os.X_OK,
        )
    ):
        raise ASRAdversarialEspeakError(
            "synthetic-speech executable "
            "must be an executable regular file"
        )

    return resolved


def _run_tool(
    command: list[str],
    *,
    timeout_seconds: int = _TOOL_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[bytes]:
    try:
        completed = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
            shell=False,
            env=_controlled_environment(),
        )
    except subprocess.TimeoutExpired as exc:
        raise ASRAdversarialEspeakError(
            "synthetic-speech tool timed out"
        ) from exc
    except OSError as exc:
        raise ASRAdversarialEspeakError(
            "synthetic-speech tool could not execute"
        ) from exc

    if (
        len(completed.stdout)
        > _MAX_TOOL_OUTPUT_BYTES
        or len(completed.stderr)
        > _MAX_TOOL_OUTPUT_BYTES
    ):
        raise ASRAdversarialEspeakError(
            "synthetic-speech tool output "
            "exceeded the allowed size"
        )

    if completed.returncode != 0:
        raise ASRAdversarialEspeakError(
            "synthetic-speech tool failed"
        )

    return completed


def _platform_key() -> str:
    machine = platform.machine().lower()

    if (
        sys.platform == "linux"
        and machine in {
            "x86_64",
            "amd64",
        }
    ):
        return "linux-amd64"

    raise ASRAdversarialEspeakError(
        "synthetic-speech platform "
        "is unsupported"
    )


@dataclass(frozen=True, slots=True)
class ASRAdversarialEspeakEnvironment:
    adapter_key: str
    adapter_version: str
    package_version: str
    reported_version: str
    executable_sha256: str
    platform_key: str
    environment_sha256: str


class ASRAdversarialEspeak:
    """Deterministic adapter around one explicit eSpeak-NG executable."""

    def __init__(
        self,
        *,
        executable_path: Path,
        dpkg_query_path: Path,
    ) -> None:
        self._executable = (
            _require_executable(
                executable_path
            )
        )
        self._dpkg_query = (
            _require_executable(
                dpkg_query_path
            )
        )

        before = _sha256(
            self._executable
        )

        version_result = _run_tool(
            [
                str(
                    self._executable
                ),
                "--version",
            ]
        )

        try:
            version_output = (
                version_result.stdout
                .decode(
                    "utf-8",
                    errors="strict",
                )
                .strip()
            )
        except UnicodeDecodeError as exc:
            raise ASRAdversarialEspeakError(
                "synthetic-speech version output "
                "is not UTF-8"
            ) from exc

        first_line = (
            version_output.splitlines()[0]
            if version_output
            else ""
        )

        prefix = (
            "eSpeak NG text-to-speech: "
        )

        if not first_line.startswith(
            prefix
        ):
            raise ASRAdversarialEspeakError(
                "synthetic-speech version "
                "output is invalid"
            )

        package_result = _run_tool(
            [
                str(
                    self._dpkg_query
                ),
                "-W",
                "-f=${Version}",
                "espeak-ng",
            ]
        )

        try:
            package_version = (
                package_result.stdout
                .decode(
                    "utf-8",
                    errors="strict",
                )
                .strip()
            )
        except UnicodeDecodeError as exc:
            raise ASRAdversarialEspeakError(
                "synthetic-speech package "
                "version is not UTF-8"
            ) from exc

        if not package_version:
            raise ASRAdversarialEspeakError(
                "synthetic-speech package "
                "version is missing"
            )

        after = _sha256(
            self._executable
        )

        if before != after:
            raise ASRAdversarialEspeakError(
                "synthetic-speech executable "
                "changed during identity verification"
            )

        platform_key = (
            _platform_key()
        )

        environment_payload = {
            "adapter": {
                "key": (
                    ASR_ADVERSARIAL_ESPEAK_ADAPTER_KEY
                ),
                "version": (
                    ASR_ADVERSARIAL_ESPEAK_ADAPTER_VERSION
                ),
            },
            "tool": {
                "package_version": package_version,
                "reported_version": first_line,
                "executable_sha256": before,
            },
            "platform_key": platform_key,
            "process": {
                "shell": False,
                "stdin": "disabled",
                "locale": "C",
            },
        }

        self.environment = (
            ASRAdversarialEspeakEnvironment(
                adapter_key=(
                    ASR_ADVERSARIAL_ESPEAK_ADAPTER_KEY
                ),
                adapter_version=(
                    ASR_ADVERSARIAL_ESPEAK_ADAPTER_VERSION
                ),
                package_version=package_version,
                reported_version=first_line,
                executable_sha256=before,
                platform_key=platform_key,
                environment_sha256=(
                    _canonical_sha256(
                        environment_payload
                    )
                ),
            )
        )

    def synthesize(
        self,
        *,
        transcript_path: Path,
        output_path: Path,
        voice_key: str,
        speed_wpm: int,
        pitch: int,
        amplitude: int,
    ) -> None:
        if (
            not transcript_path.is_absolute()
            or not output_path.is_absolute()
        ):
            raise ASRAdversarialEspeakError(
                "synthetic-speech input and output "
                "paths must be absolute"
            )

        if transcript_path.is_symlink():
            raise ASRAdversarialEspeakError(
                "synthetic-speech transcript "
                "cannot be a symlink"
            )

        try:
            transcript = (
                transcript_path.resolve(
                    strict=True
                )
            )
        except OSError as exc:
            raise ASRAdversarialEspeakError(
                "synthetic-speech transcript "
                "does not exist"
            ) from exc

        if not transcript.is_file():
            raise ASRAdversarialEspeakError(
                "synthetic-speech transcript "
                "must be a regular file"
            )

        if (
            output_path.is_symlink()
            or output_path.exists()
        ):
            raise ASRAdversarialEspeakError(
                "synthetic-speech output path "
                "must not already exist"
            )

        if (
            output_path.parent.is_symlink()
            or not output_path.parent.is_dir()
        ):
            raise ASRAdversarialEspeakError(
                "synthetic-speech output parent "
                "must be an existing directory"
            )

        executable_before = (
            _sha256(
                self._executable
            )
        )

        if (
            executable_before
            != self.environment.executable_sha256
        ):
            raise ASRAdversarialEspeakError(
                "synthetic-speech executable "
                "identity changed"
            )

        _run_tool(
            [
                str(
                    self._executable
                ),
                "-v",
                voice_key,
                "-s",
                str(
                    speed_wpm
                ),
                "-p",
                str(
                    pitch
                ),
                "-a",
                str(
                    amplitude
                ),
                "-w",
                str(
                    output_path
                ),
                "-f",
                str(
                    transcript
                ),
            ]
        )

        executable_after = (
            _sha256(
                self._executable
            )
        )

        if (
            executable_after
            != executable_before
        ):
            raise ASRAdversarialEspeakError(
                "synthetic-speech executable "
                "changed during generation"
            )

        if (
            not output_path.is_file()
            or output_path.is_symlink()
            or output_path.stat().st_size <= 0
        ):
            raise ASRAdversarialEspeakError(
                "synthetic-speech output "
                "was not created safely"
            )


__all__ = [
    "ASR_ADVERSARIAL_ESPEAK_ADAPTER_KEY",
    "ASR_ADVERSARIAL_ESPEAK_ADAPTER_VERSION",
    "ASRAdversarialEspeak",
    "ASRAdversarialEspeakEnvironment",
    "ASRAdversarialEspeakError",
]

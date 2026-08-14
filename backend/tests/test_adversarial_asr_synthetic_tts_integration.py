"""Pinned synthetic-speech generation integration tests.

These tests establish development evidence for the deterministic
eSpeak-NG source-generation pipeline used by the adversarial ASR
corpus. They do not establish human speaker, accent, microphone,
or natural-conversation coverage.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

import pytest

from app.adversarial_asr_ffprobe import (
    ASRAdversarialFFprobe,
)


REAL_MEDIA_TEST_ENV = (
    "HETREN_REAL_MEDIA_INTEGRATION"
)

ESPEAK_PATH = Path(
    "/usr/bin/espeak-ng"
)
FFMPEG_PATH = Path(
    "/usr/bin/ffmpeg"
)
FFPROBE_PATH = Path(
    "/usr/bin/ffprobe"
)
DPKG_QUERY_PATH = Path(
    "/usr/bin/dpkg-query"
)

ESPEAK_PACKAGE_VERSION = (
    "1.51+dfsg-10+deb12u2"
)
ESPEAK_EXECUTABLE_SHA256 = (
    "0a2f26e328f1dd4cec926987d3dc22bf"
    "841879132fd3aa497dd4fcad0d4d77a3"
)
ESPEAK_COPYRIGHT_SHA256 = (
    "bf721eede49d50f84bd2c50f96888629"
    "ced572b66ad4087c7a224c4a5e1193bb"
)

VOICE_KEY = "en-us"
SPEED_WPM = 150
PITCH = 50
AMPLITUDE = 100

REFERENCE_TRANSCRIPT = (
    "Administer Cardiovex 250 milligrams. "
    "Confirmation code AB-7391. "
    "Account number 408-221."
)

REFERENCE_TRANSCRIPT_SHA256 = (
    "cb85655794bc5b0c2a5d5d5c1626b0e"
    "3b208bc28ecfce4aa3275ed73ea2e6744"
)

EXPECTED_SOURCE_SHA256 = (
    "d1fe44656a114a0e66fb6ea950ae4217"
    "d31691486842f4421eff8317cc6ab440"
)

EXPECTED_NORMALIZED_SHA256 = (
    "f97e1d36b87676aaacf4dbd8059fa8fe"
    "f2d323d23cfb8468aa22426f05dbd3b3"
)


pytestmark = pytest.mark.skipif(
    os.environ.get(
        REAL_MEDIA_TEST_ENV
    )
    != "1",
    reason=(
        "pinned synthetic-speech integration "
        "runs only in the Hetren media environment"
    ),
)


def _sha256(
    path: Path,
) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def _controlled_environment() -> dict[str, str]:
    return {
        "LC_ALL": "C",
        "LANG": "C",
    }


def _run_checked(
    command: list[str],
    *,
    timeout_seconds: int = 20,
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
        raise AssertionError(
            "Pinned synthetic-speech tool invocation "
            "timed out."
        ) from exc

    assert completed.returncode == 0, (
        "Pinned synthetic-speech tool invocation failed."
    )

    return completed


def _synthesize(
    *,
    transcript_path: Path,
    output_path: Path,
) -> None:
    _run_checked(
        [
            str(ESPEAK_PATH),
            "-v",
            VOICE_KEY,
            "-s",
            str(SPEED_WPM),
            "-p",
            str(PITCH),
            "-a",
            str(AMPLITUDE),
            "-w",
            str(output_path),
            "-f",
            str(transcript_path),
        ]
    )


def _normalize(
    *,
    source_path: Path,
    output_path: Path,
) -> None:
    _run_checked(
        [
            str(FFMPEG_PATH),
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-y",
            "-i",
            str(source_path),
            "-map_metadata",
            "-1",
            "-ar",
            "16000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(output_path),
        ]
    )


def test_pinned_synthetic_speech_tool_identity():
    assert ESPEAK_PATH.is_file()
    assert FFMPEG_PATH.is_file()
    assert FFPROBE_PATH.is_file()
    assert DPKG_QUERY_PATH.is_file()

    assert (
        _sha256(
            ESPEAK_PATH
        )
        == ESPEAK_EXECUTABLE_SHA256
    )

    copyright_path = Path(
        "/usr/share/doc/espeak-ng/copyright"
    )

    assert copyright_path.is_file()

    assert (
        _sha256(
            copyright_path
        )
        == ESPEAK_COPYRIGHT_SHA256
    )

    for package in (
        "espeak-ng",
        "espeak-ng-data",
        "libespeak-ng1",
    ):
        completed = _run_checked(
            [
                str(DPKG_QUERY_PATH),
                "-W",
                "-f=${Version}",
                package,
            ]
        )

        assert (
            completed.stdout
            .decode("utf-8")
            .strip()
            == ESPEAK_PACKAGE_VERSION
        )

    version = _run_checked(
        [
            str(ESPEAK_PATH),
            "--version",
        ]
    )

    assert (
        version.stdout
        .decode("utf-8")
        .startswith(
            "eSpeak NG text-to-speech: 1.51"
        )
    )


def test_synthetic_source_and_normalization_are_repeatable(
    tmp_path: Path,
):
    transcript_path = (
        tmp_path
        / "transcript.txt"
    )

    transcript_path.write_text(
        REFERENCE_TRANSCRIPT + "\n",
        encoding="utf-8",
    )

    assert (
        _sha256(
            transcript_path
        )
        == REFERENCE_TRANSCRIPT_SHA256
    )

    source_a = (
        tmp_path
        / "source-a.wav"
    )
    source_b = (
        tmp_path
        / "source-b.wav"
    )

    _synthesize(
        transcript_path=transcript_path,
        output_path=source_a,
    )
    _synthesize(
        transcript_path=transcript_path,
        output_path=source_b,
    )

    assert (
        source_a.read_bytes()
        == source_b.read_bytes()
    )

    assert (
        _sha256(
            source_a
        )
        == EXPECTED_SOURCE_SHA256
    )

    assert (
        _sha256(
            source_b
        )
        == EXPECTED_SOURCE_SHA256
    )

    normalized_a = (
        tmp_path
        / "normalized-a.wav"
    )
    normalized_b = (
        tmp_path
        / "normalized-b.wav"
    )

    _normalize(
        source_path=source_a,
        output_path=normalized_a,
    )
    _normalize(
        source_path=source_b,
        output_path=normalized_b,
    )

    assert (
        normalized_a.read_bytes()
        == normalized_b.read_bytes()
    )

    assert (
        _sha256(
            normalized_a
        )
        == EXPECTED_NORMALIZED_SHA256
    )

    assert (
        _sha256(
            normalized_b
        )
        == EXPECTED_NORMALIZED_SHA256
    )

    probe = ASRAdversarialFFprobe(
        executable_path=FFPROBE_PATH,
    )

    measured = probe.probe(
        normalized_a
    )

    assert measured.sample_rate_hz == 16_000
    assert measured.channel_count == 1
    assert measured.codec_name == "pcm_s16le"

    assert measured.duration_ms == 12_604

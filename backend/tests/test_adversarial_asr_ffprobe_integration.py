"""Real pinned FFmpeg/FFprobe integration tests.

These tests are intentionally opt-in outside the Hetren media container.
CI explicitly enables them inside the pinned media-tool environment.
"""

from __future__ import annotations

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
EXPECTED_FFPROBE_VERSION = (
    "5.1.9-0+deb12u1"
)
FFPROBE_PATH = Path(
    "/usr/bin/ffprobe"
)
FFMPEG_PATH = Path(
    "/usr/bin/ffmpeg"
)


pytestmark = pytest.mark.skipif(
    os.environ.get(
        REAL_MEDIA_TEST_ENV
    )
    != "1",
    reason=(
        "real pinned media integration "
        "is enabled only in the Hetren "
        "media environment"
    ),
)


def _generate_pcm_fixture(
    output_path: Path,
) -> None:
    command = [
        str(FFMPEG_PATH),
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=1000:duration=1",
        "-ar",
        "16000",
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        str(output_path),
    ]

    controlled_environment = {
        "LC_ALL": "C",
        "LANG": "C",
    }

    try:
        completed = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
            shell=False,
            env=controlled_environment,
        )
    except subprocess.TimeoutExpired as exc:
        raise AssertionError(
            "Pinned FFmpeg fixture generation timed out."
        ) from exc

    assert completed.returncode == 0, (
        "Pinned FFmpeg could not generate "
        "the integration fixture."
    )


def test_pinned_ffprobe_measures_real_pcm_audio(
    tmp_path: Path,
):
    assert FFPROBE_PATH.is_file()
    assert FFMPEG_PATH.is_file()

    audio_path = (
        tmp_path
        / "hetren-real-media-fixture.wav"
    )

    _generate_pcm_fixture(
        audio_path
    )

    probe = ASRAdversarialFFprobe(
        executable_path=FFPROBE_PATH,
    )

    measured = probe.probe(
        audio_path
    )

    assert probe.reported_version == (
        EXPECTED_FFPROBE_VERSION
    )

    assert measured.duration_ms == 1000
    assert measured.sample_rate_hz == 16000
    assert measured.channel_count == 1
    assert measured.codec_name == "pcm_s16le"


def test_pinned_probe_environment_is_stable_for_same_binary():
    first = ASRAdversarialFFprobe(
        executable_path=FFPROBE_PATH,
    )
    second = ASRAdversarialFFprobe(
        executable_path=FFPROBE_PATH,
    )

    assert (
        first.executable_sha256
        == second.executable_sha256
    )

    assert (
        first.probe_environment_sha256
        == second.probe_environment_sha256
    )

    assert (
        first.reported_version
        == EXPECTED_FFPROBE_VERSION
    )

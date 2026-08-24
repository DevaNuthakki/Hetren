"""Contract tests for deterministic adversarial ASR lossy recipes."""

from __future__ import annotations

from pathlib import Path

from app.adversarial_asr_ffmpeg import (
    ASR_ADVERSARIAL_FFMPEG_AAC_M4A_CBR32_ARGV,
    ASR_ADVERSARIAL_FFMPEG_AAC_M4A_CBR32_RECIPE,
    ASR_ADVERSARIAL_FFMPEG_AAC_M4A_CBR32_RECIPE_KEY,
    ASR_ADVERSARIAL_FFMPEG_MP3_CBR32_ARGV,
    ASR_ADVERSARIAL_FFMPEG_MP3_CBR32_RECIPE,
    ASR_ADVERSARIAL_FFMPEG_MP3_CBR32_RECIPE_KEY,
    ASRAdversarialFFmpeg,
)


def _value_after(
    argv: tuple[str, ...],
    key: str,
) -> str:
    index = argv.index(
        key
    )

    return argv[
        index + 1
    ]


def test_lossy_recipes_have_exact_media_contract():
    assert (
        ASR_ADVERSARIAL_FFMPEG_MP3_CBR32_RECIPE
        .sample_rate_hz
        == 16_000
    )

    assert (
        ASR_ADVERSARIAL_FFMPEG_MP3_CBR32_RECIPE
        .channel_count
        == 1
    )

    assert (
        ASR_ADVERSARIAL_FFMPEG_MP3_CBR32_RECIPE
        .codec_name
        == "mp3"
    )

    assert (
        ASR_ADVERSARIAL_FFMPEG_AAC_M4A_CBR32_RECIPE
        .sample_rate_hz
        == 16_000
    )

    assert (
        ASR_ADVERSARIAL_FFMPEG_AAC_M4A_CBR32_RECIPE
        .channel_count
        == 1
    )

    assert (
        ASR_ADVERSARIAL_FFMPEG_AAC_M4A_CBR32_RECIPE
        .codec_name
        == "aac"
    )


def test_lossy_recipe_keys_are_frozen():
    assert (
        ASR_ADVERSARIAL_FFMPEG_MP3_CBR32_RECIPE_KEY
        == (
            "lossy-mp3-cbr32-"
            "multi-number-id-16000-v1"
        )
    )

    assert (
        ASR_ADVERSARIAL_FFMPEG_AAC_M4A_CBR32_RECIPE_KEY
        == (
            "lossy-aac-m4a-cbr32-"
            "multi-number-id-16000-v1"
        )
    )


def test_lossy_recipes_have_exact_placeholder_contract():
    for argv in (
        ASR_ADVERSARIAL_FFMPEG_MP3_CBR32_ARGV,
        ASR_ADVERSARIAL_FFMPEG_AAC_M4A_CBR32_ARGV,
    ):
        assert argv.count(
            "{input}"
        ) == 1

        assert argv.count(
            "{output}"
        ) == 1


def test_lossy_recipes_preserve_non_overwrite_security():
    for argv in (
        ASR_ADVERSARIAL_FFMPEG_MP3_CBR32_ARGV,
        ASR_ADVERSARIAL_FFMPEG_AAC_M4A_CBR32_ARGV,
    ):
        assert "-n" in argv
        assert "-y" not in argv


def test_lossy_recipes_freeze_common_media_controls():
    for argv in (
        ASR_ADVERSARIAL_FFMPEG_MP3_CBR32_ARGV,
        ASR_ADVERSARIAL_FFMPEG_AAC_M4A_CBR32_ARGV,
    ):
        assert (
            _value_after(
                argv,
                "-map",
            )
            == "0:a:0"
        )

        assert (
            _value_after(
                argv,
                "-map_metadata",
            )
            == "-1"
        )

        assert "-vn" in argv

        assert (
            _value_after(
                argv,
                "-ac",
            )
            == "1"
        )

        assert (
            _value_after(
                argv,
                "-ar",
            )
            == "16000"
        )

        assert (
            _value_after(
                argv,
                "-threads",
            )
            == "1"
        )

        assert (
            _value_after(
                argv,
                "-b:a",
            )
            == "32k"
        )


def test_mp3_recipe_freezes_encoder_and_muxer_controls():
    argv = (
        ASR_ADVERSARIAL_FFMPEG_MP3_CBR32_ARGV
    )

    assert (
        _value_after(
            argv,
            "-c:a",
        )
        == "libmp3lame"
    )

    assert (
        _value_after(
            argv,
            "-abr",
        )
        == "0"
    )

    assert (
        _value_after(
            argv,
            "-reservoir",
        )
        == "1"
    )

    assert (
        _value_after(
            argv,
            "-joint_stereo",
        )
        == "0"
    )

    assert (
        _value_after(
            argv,
            "-id3v2_version",
        )
        == "3"
    )

    assert (
        _value_after(
            argv,
            "-write_id3v1",
        )
        == "0"
    )

    assert (
        _value_after(
            argv,
            "-write_xing",
        )
        == "0"
    )

    assert (
        _value_after(
            argv,
            "-f",
        )
        == "mp3"
    )


def test_aac_m4a_recipe_freezes_encoder_controls():
    argv = (
        ASR_ADVERSARIAL_FFMPEG_AAC_M4A_CBR32_ARGV
    )

    assert (
        _value_after(
            argv,
            "-c:a",
        )
        == "aac"
    )

    expected = {
        "-aac_coder": "twoloop",
        "-aac_ms": "0",
        "-aac_is": "1",
        "-aac_pns": "1",
        "-aac_tns": "1",
        "-aac_ltp": "0",
        "-aac_pred": "0",
        "-aac_pce": "0",
    }

    for key, value in expected.items():
        assert (
            _value_after(
                argv,
                key,
            )
            == value
        )


def test_aac_m4a_recipe_freezes_muxer_controls():
    argv = (
        ASR_ADVERSARIAL_FFMPEG_AAC_M4A_CBR32_ARGV
    )

    expected = {
        "-movflags": "+faststart",
        "-use_editlist": "1",
        "-write_btrt": "0",
        "-write_prft": "0",
        "-movie_timescale": "1000",
        "-f": "ipod",
    }

    for key, value in expected.items():
        assert (
            _value_after(
                argv,
                key,
            )
            == value
        )


def test_lossy_recipe_environments_are_distinct(
    tmp_path: Path,
):
    executable = (
        tmp_path
        / "ffmpeg"
    )

    executable.write_text(
        """#!/bin/sh
set -eu

if [ "${1:-}" = "-version" ]; then
    printf '%s\\n' \
      'ffmpeg version 5.1.9-test Copyright fake'
    exit 0
fi

output=''

for argument in "$@"; do
    output="$argument"
done

printf '%s' 'deterministic-output' > "$output"
""",
        encoding="utf-8",
    )

    executable.chmod(
        0o755
    )

    mp3 = ASRAdversarialFFmpeg(
        executable_path=executable,
        recipe=(
            ASR_ADVERSARIAL_FFMPEG_MP3_CBR32_RECIPE
        ),
    )

    aac = ASRAdversarialFFmpeg(
        executable_path=executable,
        recipe=(
            ASR_ADVERSARIAL_FFMPEG_AAC_M4A_CBR32_RECIPE
        ),
    )

    assert (
        mp3.transform_environment_sha256
        != aac.transform_environment_sha256
    )

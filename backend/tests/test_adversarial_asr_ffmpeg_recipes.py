"""Tests for explicit deterministic adversarial ASR FFmpeg recipes."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.adversarial_asr_ffmpeg import (
    ASR_ADVERSARIAL_FFMPEG_ALAW8K_RECIPE,
    ASR_ADVERSARIAL_FFMPEG_MULAW8K_RECIPE,
    ASR_ADVERSARIAL_FFMPEG_PCM16K_ARGV,
    ASR_ADVERSARIAL_FFMPEG_PCM16K_RECIPE,
    ASR_ADVERSARIAL_FFMPEG_PCM16K_RECIPE_KEY,
    ASR_ADVERSARIAL_FFMPEG_PCM8K_RECIPE,
    ASRAdversarialFFmpeg,
    ASRAdversarialFFmpegError,
    ASRAdversarialFFmpegRecipe,
)


def _make_executable(
    path: Path,
) -> Path:
    path.write_text(
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

    path.chmod(
        0o755
    )

    return path


def _adapter(
    tmp_path: Path,
    *,
    recipe=None,
) -> ASRAdversarialFFmpeg:
    return ASRAdversarialFFmpeg(
        executable_path=_make_executable(
            tmp_path
            / "ffmpeg"
        ),
        recipe=recipe,
    )


def _source(
    tmp_path: Path,
) -> Path:
    path = (
        tmp_path
        / "source.wav"
    )

    path.write_bytes(
        b"source-audio"
    )

    return path


def test_default_recipe_remains_frozen_pcm16k(
    tmp_path: Path,
):
    adapter = _adapter(
        tmp_path
    )

    assert (
        adapter.recipe
        == ASR_ADVERSARIAL_FFMPEG_PCM16K_RECIPE
    )
    assert (
        adapter.recipe_key
        == ASR_ADVERSARIAL_FFMPEG_PCM16K_RECIPE_KEY
    )
    assert (
        adapter.recipe_argv
        == ASR_ADVERSARIAL_FFMPEG_PCM16K_ARGV
    )

    transformation = (
        adapter.transform_environment_payload[
            "transformation"
        ]
    )

    assert transformation == {
        "recipe_key": (
            ASR_ADVERSARIAL_FFMPEG_PCM16K_RECIPE_KEY
        ),
        "argv": list(
            ASR_ADVERSARIAL_FFMPEG_PCM16K_ARGV
        ),
        "sample_rate_hz": 16_000,
        "channel_count": 1,
        "codec_name": "pcm_s16le",
        "metadata_policy": (
            "strip-input-metadata-v1"
        ),
    }


@pytest.mark.parametrize(
    (
        "recipe",
        "sample_rate_hz",
        "codec_name",
    ),
    (
        (
            ASR_ADVERSARIAL_FFMPEG_PCM8K_RECIPE,
            8_000,
            "pcm_s16le",
        ),
        (
            ASR_ADVERSARIAL_FFMPEG_MULAW8K_RECIPE,
            8_000,
            "pcm_mulaw",
        ),
        (
            ASR_ADVERSARIAL_FFMPEG_ALAW8K_RECIPE,
            8_000,
            "pcm_alaw",
        ),
    ),
)
def test_explicit_recipe_is_bound_into_environment(
    tmp_path: Path,
    recipe: ASRAdversarialFFmpegRecipe,
    sample_rate_hz: int,
    codec_name: str,
):
    adapter = _adapter(
        tmp_path,
        recipe=recipe,
    )

    transformation = (
        adapter.transform_environment_payload[
            "transformation"
        ]
    )

    assert (
        transformation["recipe_key"]
        == recipe.recipe_key
    )
    assert (
        transformation["argv"]
        == list(
            recipe.argv
        )
    )
    assert (
        transformation["sample_rate_hz"]
        == sample_rate_hz
    )
    assert (
        transformation["channel_count"]
        == 1
    )
    assert (
        transformation["codec_name"]
        == codec_name
    )


def test_recipe_environment_identities_are_distinct(
    tmp_path: Path,
):
    executable = _make_executable(
        tmp_path
        / "ffmpeg"
    )

    identities = {
        ASRAdversarialFFmpeg(
            executable_path=executable,
            recipe=recipe,
        ).transform_environment_sha256
        for recipe in (
            ASR_ADVERSARIAL_FFMPEG_PCM16K_RECIPE,
            ASR_ADVERSARIAL_FFMPEG_PCM8K_RECIPE,
            ASR_ADVERSARIAL_FFMPEG_MULAW8K_RECIPE,
            ASR_ADVERSARIAL_FFMPEG_ALAW8K_RECIPE,
        )
    }

    assert len(
        identities
    ) == 4


def test_generic_transform_supports_explicit_recipe(
    tmp_path: Path,
):
    adapter = _adapter(
        tmp_path,
        recipe=(
            ASR_ADVERSARIAL_FFMPEG_MULAW8K_RECIPE
        ),
    )

    source = _source(
        tmp_path
    )

    output = (
        tmp_path
        / "output.wav"
    )

    result = adapter.transform(
        input_path=source,
        output_path=output,
    )

    assert (
        output.read_bytes()
        == b"deterministic-output"
    )
    assert (
        result.parent_byte_length
        == len(
            b"source-audio"
        )
    )
    assert (
        result.output_byte_length
        == len(
            b"deterministic-output"
        )
    )


def test_legacy_pcm16k_method_rejects_non_pcm16k_recipe(
    tmp_path: Path,
):
    adapter = _adapter(
        tmp_path,
        recipe=(
            ASR_ADVERSARIAL_FFMPEG_MULAW8K_RECIPE
        ),
    )

    with pytest.raises(
        ASRAdversarialFFmpegError,
        match="requires the frozen PCM16K recipe",
    ):
        adapter.transform_pcm16k(
            input_path=_source(
                tmp_path
            ),
            output_path=(
                tmp_path
                / "output.wav"
            ),
        )


@pytest.mark.parametrize(
    "kwargs",
    (
        {
            "recipe_key": "Bad Recipe",
            "argv": (
                "-i",
                "{input}",
                "{output}",
            ),
            "sample_rate_hz": 8_000,
            "channel_count": 1,
            "codec_name": "pcm_mulaw",
        },
        {
            "recipe_key": "bad-input-v1",
            "argv": (
                "-i",
                "literal.wav",
                "{output}",
            ),
            "sample_rate_hz": 8_000,
            "channel_count": 1,
            "codec_name": "pcm_mulaw",
        },
        {
            "recipe_key": "bad-output-v1",
            "argv": (
                "-i",
                "{input}",
                "literal.wav",
            ),
            "sample_rate_hz": 8_000,
            "channel_count": 1,
            "codec_name": "pcm_mulaw",
        },
        {
            "recipe_key": "bad-codec-v1",
            "argv": (
                "-i",
                "{input}",
                "{output}",
            ),
            "sample_rate_hz": 8_000,
            "channel_count": 1,
            "codec_name": "PCM MULAW",
        },
    ),
)
def test_invalid_recipe_contract_is_rejected(
    kwargs: dict[str, object],
):
    with pytest.raises(
        ASRAdversarialFFmpegError
    ):
        ASRAdversarialFFmpegRecipe(
            **kwargs,
        )

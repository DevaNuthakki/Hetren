"""Deterministic media recipes for Hetren ASR Brutal Validation v1.

These recipes create development-only acoustic stress derivatives from
the already sealed ``control.clean-critical`` corpus case.

They deliberately keep the spoken content fixed while varying only the
audio channel/codec/noise conditions.

Important scientific boundary:

The fixed white-noise coefficients below are inherited from Hetren's
existing deterministic development stress methodology. Because the
parent audio here differs from the previously calibrated
``clean.multi-number-id`` parent, these recipes DO NOT claim an exact
numeric SNR tier for the resulting Brutal-v1 assets.

They provide deterministic acoustic stress only. They do not perform
ASR, evaluate fidelity, qualify a model, certify a release, or enable a
release gate.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.adversarial_asr_ffmpeg import (
    ASRAdversarialFFmpegRecipe,
)


ASR_BRUTAL_MEDIA_SCHEMA_VERSION = 1

ASR_BRUTAL_MEDIA_KEY = (
    "hetren.asr.brutal-media"
)

ASR_BRUTAL_MEDIA_VERSION = "1.0.0"


ASR_BRUTAL_MEDIA_PARENT_CASE_ID = (
    "control.clean-critical"
)

ASR_BRUTAL_MEDIA_PARENT_RELATIVE_PATH = (
    "clean/control.clean-critical.wav"
)

ASR_BRUTAL_MEDIA_PARENT_SHA256 = (
    "f97e1d36b87676aaacf4dbd8059fa8fe"
    "f2d323d23cfb8468aa22426f05dbd3b3"
)

ASR_BRUTAL_MEDIA_PARENT_BYTE_LENGTH = 403_394


ASR_BRUTAL_TERMINOLOGY_TELEPHONY_NOISE_CASE_ID = (
    "brutal.terminology.telephony-noise"
)

ASR_BRUTAL_COMPOUND_TELEPHONY_NOISE_CASE_ID = (
    "brutal.compound-critical.telephony-noise"
)


ASR_BRUTAL_TERMINOLOGY_TELEPHONY_NOISE_OUTPUT = (
    "brutal/"
    "brutal.terminology.telephony-noise.wav"
)

ASR_BRUTAL_COMPOUND_TELEPHONY_NOISE_OUTPUT = (
    "brutal/"
    "brutal.compound-critical.telephony-noise.wav"
)


# Reuse Hetren's deterministic white-noise seed so the two Brutal
# derivatives form a controlled severity pair.
ASR_BRUTAL_MEDIA_NOISE_SEED = 39039

# These coefficients are source-visible and frozen. They are not
# interpreted as exact SNR claims for control.clean-critical.
ASR_BRUTAL_MEDIA_NOISE_LEVEL_ONE = (
    "0.050141109355923044"
)

ASR_BRUTAL_MEDIA_NOISE_LEVEL_TWO = (
    "0.089164902364147938"
)


def _noise_filter(
    *,
    volume: str,
) -> str:
    return (
        "anoisesrc="
        "sample_rate=16000:"
        "amplitude=1:"
        "color=white:"
        f"seed={ASR_BRUTAL_MEDIA_NOISE_SEED}"
        "[noise];"
        "[noise]"
        f"volume={volume}:"
        "precision=double"
        "[scaled_noise];"
        "[0:a][scaled_noise]"
        "amix="
        "inputs=2:"
        "duration=first:"
        "dropout_transition=0:"
        "normalize=0"
        "[mixed]"
    )


ASR_BRUTAL_TERMINOLOGY_TELEPHONY_NOISE_ARGV = (
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
    _noise_filter(
        volume=ASR_BRUTAL_MEDIA_NOISE_LEVEL_ONE,
    ),
    "-map",
    "[mixed]",
    "-map_metadata",
    "-1",
    "-ar",
    "8000",
    "-ac",
    "1",
    "-threads",
    "1",
    "-c:a",
    "pcm_s16le",
    "{output}",
)


ASR_BRUTAL_COMPOUND_TELEPHONY_NOISE_ARGV = (
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
    _noise_filter(
        volume=ASR_BRUTAL_MEDIA_NOISE_LEVEL_TWO,
    ),
    "-map",
    "[mixed]",
    "-map_metadata",
    "-1",
    "-ar",
    "8000",
    "-ac",
    "1",
    "-threads",
    "1",
    "-c:a",
    "pcm_mulaw",
    "{output}",
)


ASR_BRUTAL_TERMINOLOGY_TELEPHONY_NOISE_RECIPE = (
    ASRAdversarialFFmpegRecipe(
        recipe_key=(
            "brutal-terminology-telephony-noise-"
            "pcm8k-v1"
        ),
        argv=(
            ASR_BRUTAL_TERMINOLOGY_TELEPHONY_NOISE_ARGV
        ),
        sample_rate_hz=8_000,
        channel_count=1,
        codec_name="pcm_s16le",
    )
)


ASR_BRUTAL_COMPOUND_TELEPHONY_NOISE_RECIPE = (
    ASRAdversarialFFmpegRecipe(
        recipe_key=(
            "brutal-compound-critical-telephony-noise-"
            "mulaw8k-v1"
        ),
        argv=(
            ASR_BRUTAL_COMPOUND_TELEPHONY_NOISE_ARGV
        ),
        sample_rate_hz=8_000,
        channel_count=1,
        codec_name="pcm_mulaw",
    )
)


@dataclass(frozen=True, slots=True)
class ASRBrutalMediaExpectation:
    """Frozen identity of one verified Brutal-v1 media derivative."""

    case_id: str
    output_relative_path: str
    recipe_key: str
    transform_environment_sha256: str
    audio_asset_sha256: str
    byte_length: int
    duration_ms: int
    sample_rate_hz: int
    channel_count: int
    codec_name: str


ASR_BRUTAL_TERMINOLOGY_TELEPHONY_NOISE_EXPECTATION = (
    ASRBrutalMediaExpectation(
        case_id=(
            ASR_BRUTAL_TERMINOLOGY_TELEPHONY_NOISE_CASE_ID
        ),
        output_relative_path=(
            ASR_BRUTAL_TERMINOLOGY_TELEPHONY_NOISE_OUTPUT
        ),
        recipe_key=(
            ASR_BRUTAL_TERMINOLOGY_TELEPHONY_NOISE_RECIPE
            .recipe_key
        ),
        transform_environment_sha256=(
            "6ca9a73b8cccce4f79cd0146aac31692"
            "4e0df6bf12b2dd78c3d99e4f55463329"
        ),
        audio_asset_sha256=(
            "7c7968447c134e1f97187c010761a187"
            "a67d4803ec5ff6614683d8f784e94e94"
        ),
        byte_length=201_736,
        duration_ms=12_604,
        sample_rate_hz=8_000,
        channel_count=1,
        codec_name="pcm_s16le",
    )
)


ASR_BRUTAL_COMPOUND_TELEPHONY_NOISE_EXPECTATION = (
    ASRBrutalMediaExpectation(
        case_id=(
            ASR_BRUTAL_COMPOUND_TELEPHONY_NOISE_CASE_ID
        ),
        output_relative_path=(
            ASR_BRUTAL_COMPOUND_TELEPHONY_NOISE_OUTPUT
        ),
        recipe_key=(
            ASR_BRUTAL_COMPOUND_TELEPHONY_NOISE_RECIPE
            .recipe_key
        ),
        transform_environment_sha256=(
            "e60e9fbc09783de7d5238c7675be54db"
            "a5aa93487adba904b5e9fbb486e895a4"
        ),
        audio_asset_sha256=(
            "c1867d7d183ab3dc5a29784a0cf4854"
            "e2958bffe91c7390a657420be7222aeaa"
        ),
        byte_length=100_922,
        duration_ms=12_604,
        sample_rate_hz=8_000,
        channel_count=1,
        codec_name="pcm_mulaw",
    )
)


ASR_BRUTAL_MEDIA_EXPECTATIONS_V1 = (
    ASR_BRUTAL_TERMINOLOGY_TELEPHONY_NOISE_EXPECTATION,
    ASR_BRUTAL_COMPOUND_TELEPHONY_NOISE_EXPECTATION,
)


def get_asr_brutal_media_expectation_v1(
    case_id: str,
) -> ASRBrutalMediaExpectation:
    """Return the exact frozen media expectation for one Brutal-v1 case."""

    matches = tuple(
        expectation
        for expectation
        in ASR_BRUTAL_MEDIA_EXPECTATIONS_V1
        if expectation.case_id == case_id
    )

    if len(matches) != 1:
        raise ValueError(
            "unknown ASR Brutal-v1 media case"
        )

    return matches[0]



__all__ = [
    "ASRBrutalMediaExpectation",
    "ASR_BRUTAL_COMPOUND_TELEPHONY_NOISE_EXPECTATION",
    "ASR_BRUTAL_MEDIA_EXPECTATIONS_V1",
    "ASR_BRUTAL_TERMINOLOGY_TELEPHONY_NOISE_EXPECTATION",
    "get_asr_brutal_media_expectation_v1",
    "ASR_BRUTAL_COMPOUND_TELEPHONY_NOISE_ARGV",
    "ASR_BRUTAL_COMPOUND_TELEPHONY_NOISE_CASE_ID",
    "ASR_BRUTAL_COMPOUND_TELEPHONY_NOISE_OUTPUT",
    "ASR_BRUTAL_COMPOUND_TELEPHONY_NOISE_RECIPE",
    "ASR_BRUTAL_MEDIA_KEY",
    "ASR_BRUTAL_MEDIA_NOISE_LEVEL_ONE",
    "ASR_BRUTAL_MEDIA_NOISE_LEVEL_TWO",
    "ASR_BRUTAL_MEDIA_NOISE_SEED",
    "ASR_BRUTAL_MEDIA_PARENT_BYTE_LENGTH",
    "ASR_BRUTAL_MEDIA_PARENT_CASE_ID",
    "ASR_BRUTAL_MEDIA_PARENT_RELATIVE_PATH",
    "ASR_BRUTAL_MEDIA_PARENT_SHA256",
    "ASR_BRUTAL_MEDIA_SCHEMA_VERSION",
    "ASR_BRUTAL_MEDIA_VERSION",
    "ASR_BRUTAL_TERMINOLOGY_TELEPHONY_NOISE_ARGV",
    "ASR_BRUTAL_TERMINOLOGY_TELEPHONY_NOISE_CASE_ID",
    "ASR_BRUTAL_TERMINOLOGY_TELEPHONY_NOISE_OUTPUT",
    "ASR_BRUTAL_TERMINOLOGY_TELEPHONY_NOISE_RECIPE",
]

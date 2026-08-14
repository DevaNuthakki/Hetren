"""Contract tests for calibrated deterministic adversarial noise recipes."""

from __future__ import annotations

from app.adversarial_asr_ffmpeg import (
    ASR_ADVERSARIAL_FFMPEG_NOISE_MODERATE_ARGV,
    ASR_ADVERSARIAL_FFMPEG_NOISE_MODERATE_RECIPE,
    ASR_ADVERSARIAL_FFMPEG_NOISE_MODERATE_RECIPE_KEY,
    ASR_ADVERSARIAL_FFMPEG_NOISE_SEVERE_USABLE_ARGV,
    ASR_ADVERSARIAL_FFMPEG_NOISE_SEVERE_USABLE_RECIPE,
    ASR_ADVERSARIAL_FFMPEG_NOISE_SEVERE_USABLE_RECIPE_KEY,
)


MODERATE_GAIN_LITERAL = (
    "0.050141109355923044"
)

SEVERE_USABLE_GAIN_LITERAL = (
    "0.089164902364147938"
)


def _filter_graph(
    argv: tuple[str, ...],
) -> str:
    index = argv.index(
        "-filter_complex"
    )

    return argv[
        index + 1
    ]


def test_noise_recipes_have_exact_output_contract():
    for recipe in (
        ASR_ADVERSARIAL_FFMPEG_NOISE_MODERATE_RECIPE,
        ASR_ADVERSARIAL_FFMPEG_NOISE_SEVERE_USABLE_RECIPE,
    ):
        assert (
            recipe.sample_rate_hz
            == 16_000
        )

        assert (
            recipe.channel_count
            == 1
        )

        assert (
            recipe.codec_name
            == "pcm_s16le"
        )


def test_noise_recipes_have_exact_placeholder_contract():
    for argv in (
        ASR_ADVERSARIAL_FFMPEG_NOISE_MODERATE_ARGV,
        ASR_ADVERSARIAL_FFMPEG_NOISE_SEVERE_USABLE_ARGV,
    ):
        assert argv.count(
            "{input}"
        ) == 1

        assert argv.count(
            "{output}"
        ) == 1


def test_noise_recipes_freeze_seed_and_noise_family():
    for argv in (
        ASR_ADVERSARIAL_FFMPEG_NOISE_MODERATE_ARGV,
        ASR_ADVERSARIAL_FFMPEG_NOISE_SEVERE_USABLE_ARGV,
    ):
        graph = _filter_graph(
            argv
        )

        assert (
            "anoisesrc="
            "sample_rate=16000:"
            "amplitude=1:"
            "color=white:"
            "seed=39039"
            in graph
        )


def test_noise_recipes_disable_amix_normalization():
    for argv in (
        ASR_ADVERSARIAL_FFMPEG_NOISE_MODERATE_ARGV,
        ASR_ADVERSARIAL_FFMPEG_NOISE_SEVERE_USABLE_ARGV,
    ):
        graph = _filter_graph(
            argv
        )

        assert (
            "amix="
            "inputs=2:"
            "duration=first:"
            "dropout_transition=0:"
            "normalize=0"
            in graph
        )


def test_noise_recipes_freeze_determinism_controls():
    for argv in (
        ASR_ADVERSARIAL_FFMPEG_NOISE_MODERATE_ARGV,
        ASR_ADVERSARIAL_FFMPEG_NOISE_SEVERE_USABLE_ARGV,
    ):
        assert (
            "-filter_complex_threads"
            in argv
        )

        assert (
            argv[
                argv.index(
                    "-filter_complex_threads"
                )
                + 1
            ]
            == "1"
        )

        assert (
            "-threads"
            in argv
        )

        assert (
            argv[
                argv.index(
                    "-threads"
                )
                + 1
            ]
            == "1"
        )


def test_moderate_recipe_freezes_calibrated_gain():
    graph = _filter_graph(
        ASR_ADVERSARIAL_FFMPEG_NOISE_MODERATE_ARGV
    )

    assert (
        f"volume={MODERATE_GAIN_LITERAL}:"
        "precision=double"
        in graph
    )

    assert (
        ASR_ADVERSARIAL_FFMPEG_NOISE_MODERATE_RECIPE_KEY
        == (
            "white-noise-multi-number-id-"
            "moderate-16000-v1"
        )
    )


def test_severe_usable_recipe_freezes_calibrated_gain():
    graph = _filter_graph(
        ASR_ADVERSARIAL_FFMPEG_NOISE_SEVERE_USABLE_ARGV
    )

    assert (
        f"volume={SEVERE_USABLE_GAIN_LITERAL}:"
        "precision=double"
        in graph
    )

    assert (
        ASR_ADVERSARIAL_FFMPEG_NOISE_SEVERE_USABLE_RECIPE_KEY
        == (
            "white-noise-multi-number-id-"
            "severe-usable-16000-v1"
        )
    )


def test_noise_recipes_are_distinct():
    assert (
        ASR_ADVERSARIAL_FFMPEG_NOISE_MODERATE_RECIPE
        != ASR_ADVERSARIAL_FFMPEG_NOISE_SEVERE_USABLE_RECIPE
    )

    assert (
        ASR_ADVERSARIAL_FFMPEG_NOISE_MODERATE_ARGV
        != ASR_ADVERSARIAL_FFMPEG_NOISE_SEVERE_USABLE_ARGV
    )

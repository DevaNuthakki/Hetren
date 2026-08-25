from app.adversarial_asr_brutal_media import (
    ASR_BRUTAL_COMPOUND_TELEPHONY_NOISE_EXPECTATION,
    ASR_BRUTAL_MEDIA_EXPECTATIONS_V1,
    ASR_BRUTAL_TERMINOLOGY_TELEPHONY_NOISE_EXPECTATION,
    ASR_BRUTAL_COMPOUND_TELEPHONY_NOISE_ARGV,
    ASR_BRUTAL_COMPOUND_TELEPHONY_NOISE_RECIPE,
    ASR_BRUTAL_MEDIA_NOISE_LEVEL_ONE,
    ASR_BRUTAL_MEDIA_NOISE_LEVEL_TWO,
    ASR_BRUTAL_MEDIA_NOISE_SEED,
    ASR_BRUTAL_MEDIA_PARENT_BYTE_LENGTH,
    ASR_BRUTAL_MEDIA_PARENT_CASE_ID,
    ASR_BRUTAL_MEDIA_PARENT_SHA256,
    ASR_BRUTAL_TERMINOLOGY_TELEPHONY_NOISE_ARGV,
    ASR_BRUTAL_TERMINOLOGY_TELEPHONY_NOISE_RECIPE,
)


def test_parent_identity_is_exact():
    assert ASR_BRUTAL_MEDIA_PARENT_CASE_ID == (
        "control.clean-critical"
    )

    assert ASR_BRUTAL_MEDIA_PARENT_SHA256 == (
        "f97e1d36b87676aaacf4dbd8059fa8fe"
        "f2d323d23cfb8468aa22426f05dbd3b3"
    )

    assert ASR_BRUTAL_MEDIA_PARENT_BYTE_LENGTH == 403_394


def test_noise_pair_uses_same_deterministic_seed():
    assert ASR_BRUTAL_MEDIA_NOISE_SEED == 39039

    first = (
        ASR_BRUTAL_TERMINOLOGY_TELEPHONY_NOISE_ARGV[
            ASR_BRUTAL_TERMINOLOGY_TELEPHONY_NOISE_ARGV.index(
                "-filter_complex"
            )
            + 1
        ]
    )

    second = (
        ASR_BRUTAL_COMPOUND_TELEPHONY_NOISE_ARGV[
            ASR_BRUTAL_COMPOUND_TELEPHONY_NOISE_ARGV.index(
                "-filter_complex"
            )
            + 1
        ]
    )

    assert "seed=39039" in first
    assert "seed=39039" in second


def test_noise_pair_uses_distinct_frozen_levels():
    assert (
        ASR_BRUTAL_MEDIA_NOISE_LEVEL_ONE
        != ASR_BRUTAL_MEDIA_NOISE_LEVEL_TWO
    )

    first = (
        ASR_BRUTAL_TERMINOLOGY_TELEPHONY_NOISE_ARGV[
            ASR_BRUTAL_TERMINOLOGY_TELEPHONY_NOISE_ARGV.index(
                "-filter_complex"
            )
            + 1
        ]
    )

    second = (
        ASR_BRUTAL_COMPOUND_TELEPHONY_NOISE_ARGV[
            ASR_BRUTAL_COMPOUND_TELEPHONY_NOISE_ARGV.index(
                "-filter_complex"
            )
            + 1
        ]
    )

    assert ASR_BRUTAL_MEDIA_NOISE_LEVEL_ONE in first
    assert ASR_BRUTAL_MEDIA_NOISE_LEVEL_TWO in second


def test_first_recipe_is_telephony_rate_linear_pcm():
    recipe = (
        ASR_BRUTAL_TERMINOLOGY_TELEPHONY_NOISE_RECIPE
    )

    assert recipe.sample_rate_hz == 8_000
    assert recipe.channel_count == 1
    assert recipe.codec_name == "pcm_s16le"

    assert "-ar" in recipe.argv
    assert "8000" in recipe.argv
    assert "pcm_s16le" in recipe.argv


def test_second_recipe_is_stronger_mulaw_telephony():
    recipe = (
        ASR_BRUTAL_COMPOUND_TELEPHONY_NOISE_RECIPE
    )

    assert recipe.sample_rate_hz == 8_000
    assert recipe.channel_count == 1
    assert recipe.codec_name == "pcm_mulaw"

    assert "-ar" in recipe.argv
    assert "8000" in recipe.argv
    assert "pcm_mulaw" in recipe.argv


def test_recipes_do_not_embed_absolute_paths():
    for recipe in (
        ASR_BRUTAL_TERMINOLOGY_TELEPHONY_NOISE_RECIPE,
        ASR_BRUTAL_COMPOUND_TELEPHONY_NOISE_RECIPE,
    ):
        assert "{input}" in recipe.argv
        assert "{output}" in recipe.argv

        assert not any(
            value.startswith("/")
            for value in recipe.argv
        )


def test_recipes_never_overwrite_existing_output():
    for recipe in (
        ASR_BRUTAL_TERMINOLOGY_TELEPHONY_NOISE_RECIPE,
        ASR_BRUTAL_COMPOUND_TELEPHONY_NOISE_RECIPE,
    ):
        assert "-n" in recipe.argv
        assert "-y" not in recipe.argv

def test_frozen_media_expectations_are_exact():
    first = (
        ASR_BRUTAL_TERMINOLOGY_TELEPHONY_NOISE_EXPECTATION
    )

    second = (
        ASR_BRUTAL_COMPOUND_TELEPHONY_NOISE_EXPECTATION
    )

    assert first.transform_environment_sha256 == (
        "6ca9a73b8cccce4f79cd0146aac31692"
        "4e0df6bf12b2dd78c3d99e4f55463329"
    )

    assert first.audio_asset_sha256 == (
        "7c7968447c134e1f97187c010761a187"
        "a67d4803ec5ff6614683d8f784e94e94"
    )

    assert first.byte_length == 201_736
    assert first.duration_ms == 12_604
    assert first.sample_rate_hz == 8_000
    assert first.channel_count == 1
    assert first.codec_name == "pcm_s16le"

    assert second.transform_environment_sha256 == (
        "e60e9fbc09783de7d5238c7675be54db"
        "a5aa93487adba904b5e9fbb486e895a4"
    )

    assert second.audio_asset_sha256 == (
        "c1867d7d183ab3dc5a29784a0cf4854"
        "e2958bffe91c7390a657420be7222aeaa"
    )

    assert second.byte_length == 100_922
    assert second.duration_ms == 12_604
    assert second.sample_rate_hz == 8_000
    assert second.channel_count == 1
    assert second.codec_name == "pcm_mulaw"


def test_frozen_media_expectations_are_unique():
    case_ids = tuple(
        expectation.case_id
        for expectation
        in ASR_BRUTAL_MEDIA_EXPECTATIONS_V1
    )

    audio_hashes = tuple(
        expectation.audio_asset_sha256
        for expectation
        in ASR_BRUTAL_MEDIA_EXPECTATIONS_V1
    )

    assert len(case_ids) == 2
    assert len(case_ids) == len(set(case_ids))
    assert len(audio_hashes) == len(set(audio_hashes))


def test_frozen_expectations_match_recipes():
    first = (
        ASR_BRUTAL_TERMINOLOGY_TELEPHONY_NOISE_EXPECTATION
    )

    second = (
        ASR_BRUTAL_COMPOUND_TELEPHONY_NOISE_EXPECTATION
    )

    assert (
        first.recipe_key
        == ASR_BRUTAL_TERMINOLOGY_TELEPHONY_NOISE_RECIPE.recipe_key
    )

    assert (
        first.sample_rate_hz
        == ASR_BRUTAL_TERMINOLOGY_TELEPHONY_NOISE_RECIPE.sample_rate_hz
    )

    assert (
        first.codec_name
        == ASR_BRUTAL_TERMINOLOGY_TELEPHONY_NOISE_RECIPE.codec_name
    )

    assert (
        second.recipe_key
        == ASR_BRUTAL_COMPOUND_TELEPHONY_NOISE_RECIPE.recipe_key
    )

    assert (
        second.sample_rate_hz
        == ASR_BRUTAL_COMPOUND_TELEPHONY_NOISE_RECIPE.sample_rate_hz
    )

    assert (
        second.codec_name
        == ASR_BRUTAL_COMPOUND_TELEPHONY_NOISE_RECIPE.codec_name
    )

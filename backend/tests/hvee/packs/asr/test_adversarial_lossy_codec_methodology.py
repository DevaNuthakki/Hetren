from __future__ import annotations

import copy

import pytest

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.adversarial_evidence import (
    ASRAdversarialCodec,
)
from hvee.packs.asr.adversarial_lossy_codec_methodology import (
    ASR_ADVERSARIAL_LOSSY_CODEC_V1_BITRATE_BPS,
    ASR_ADVERSARIAL_LOSSY_CODEC_V1_PARENT_SAMPLE_COUNT,
    ASR_ADVERSARIAL_LOSSY_CODEC_V1_REPRODUCIBILITY_RUNS,
    build_asr_adversarial_lossy_codec_methodology_v1,
    verify_asr_adversarial_lossy_codec_methodology_v1,
)


def _profiles_by_key() -> dict[
    str,
    dict[str, object],
]:
    bundle = (
        build_asr_adversarial_lossy_codec_methodology_v1()
    )

    profiles = bundle.payload[
        "methodology"
    ][
        "profiles"
    ]

    return {
        profile[
            "profile_key"
        ]: profile
        for profile in profiles
    }


def test_lossy_codec_methodology_v1_is_deterministic():
    first = (
        build_asr_adversarial_lossy_codec_methodology_v1()
    )

    second = (
        build_asr_adversarial_lossy_codec_methodology_v1()
    )

    assert first == second
    assert first.sha256 == second.sha256
    assert len(first.sha256) == 64


def test_lossy_codec_methodology_v1_uses_lossy_semantic_family():
    bundle = (
        build_asr_adversarial_lossy_codec_methodology_v1()
    )

    assert bundle.payload[
        "methodology"
    ][
        "semantic_family"
    ] == (
        ASRAdversarialCodec
        .LOSSY_COMPRESSED
        .value
    )


def test_lossy_codec_methodology_v1_freezes_reference_parent():
    bundle = (
        build_asr_adversarial_lossy_codec_methodology_v1()
    )

    parent = bundle.payload[
        "methodology"
    ][
        "reference_parent"
    ]

    assert parent == {
        "audio_sha256": (
            "23f9af39d01afe47e932bd061467bd0b"
            "5f49dc8bf520c2a8296a4556c54f1297"
        ),
        "sample_count": 110_241,
        "sample_rate_hz": 16_000,
        "channel_count": 1,
    }

    assert (
        ASR_ADVERSARIAL_LOSSY_CODEC_V1_PARENT_SAMPLE_COUNT
        == 110_241
    )


def test_lossy_codec_methodology_v1_freezes_reproducibility_policy():
    bundle = (
        build_asr_adversarial_lossy_codec_methodology_v1()
    )

    reproducibility = bundle.payload[
        "methodology"
    ][
        "reproducibility"
    ]

    assert reproducibility == {
        "independent_container_runs": 3,
        "encoded_byte_identity_required": True,
        "decoded_byte_identity_required": True,
        "metadata_policy_key": (
            "strip-input-metadata-v1"
        ),
        "thread_count": 1,
        "duration_policy_key": (
            "container-duration-and-decoded-sample-count-bound-v1"
        ),
        "decoded_sample_count_must_equal_parent": False,
    }

    assert (
        ASR_ADVERSARIAL_LOSSY_CODEC_V1_REPRODUCIBILITY_RUNS
        == 3
    )


def test_lossy_codec_methodology_v1_freezes_pinned_libraries():
    bundle = (
        build_asr_adversarial_lossy_codec_methodology_v1()
    )

    libraries = bundle.payload[
        "methodology"
    ][
        "toolchain"
    ][
        "libraries"
    ]

    assert [
        library[
            "package_name"
        ]
        for library in libraries
    ] == [
        "libavcodec59",
        "libavformat59",
        "libavutil57",
        "libmp3lame0",
        "libswresample4",
    ]

    assert {
        library[
            "package_name"
        ]: library[
            "sha256"
        ]
        for library in libraries
    } == {
        "libavcodec59": (
            "4af5d9cffe2721f5c2cabf35d63c5c6a"
            "039b400df5721aaedf69995e37bd2a0d"
        ),
        "libavformat59": (
            "28aadd0a03e3e83d3aa6d4797b6a8569"
            "c15e09a5f49e6d71ff4866180871de8d"
        ),
        "libavutil57": (
            "c46ee8987cacb9f9af711f676cc98bb6d"
            "465a340566dad9c678d21baa26e2c9d"
        ),
        "libmp3lame0": (
            "33aec7029d42a903d0a127c549021c4e8"
            "86273d29e97422b6f5b7fc6d49b8d1b"
        ),
        "libswresample4": (
            "8858da6d309d6f62d89bc78a541112b1b"
            "d62ad0ae714ecc54aa61c14219e73b4"
        ),
    }


def test_lossy_codec_methodology_v1_has_only_product_profiles():
    profiles = _profiles_by_key()

    assert tuple(
        sorted(
            profiles
        )
    ) == (
        "aac-m4a-cbr32",
        "mp3-cbr32",
    )

    for profile in profiles.values():
        assert (
            profile[
                "declared_codec_family"
            ]
            == ASRAdversarialCodec
            .LOSSY_COMPRESSED
            .value
        )

        assert (
            profile[
                "product_ingestion_supported"
            ]
            is True
        )

        assert (
            profile[
                "bitrate_bps"
            ]
            == ASR_ADVERSARIAL_LOSSY_CODEC_V1_BITRATE_BPS
        )


def test_lossy_codec_methodology_v1_freezes_aac_m4a_observation():
    profile = _profiles_by_key()[
        "aac-m4a-cbr32"
    ]

    assert profile[
        "codec_name"
    ] == "aac"

    assert profile[
        "container_key"
    ] == "ipod"

    assert profile[
        "output_extension"
    ] == ".m4a"

    assert profile[
        "encoder_key"
    ] == "aac"

    assert profile[
        "reference_observation"
    ] == {
        "encoded_sha256": (
            "1f303beee42f35d86f920487fbbb67e8"
            "70576f7278a1d3b6bd97a7bd6e67fb09"
        ),
        "encoded_byte_length": 28_701,
        "decoded_sha256": (
            "0ff95374a2f6c66b85aa77371df5baf8"
            "e935a33b2935896c538dcf4fb431eb1e"
        ),
        "decoded_sample_count": 110_592,
        "decoded_sample_delta": 351,
        "probe_duration_ms": 6_891,
    }


def test_lossy_codec_methodology_v1_freezes_mp3_observation():
    profile = _profiles_by_key()[
        "mp3-cbr32"
    ]

    assert profile[
        "codec_name"
    ] == "mp3"

    assert profile[
        "container_key"
    ] == "mp3"

    assert profile[
        "output_extension"
    ] == ".mp3"

    assert profile[
        "encoder_key"
    ] == "libmp3lame"

    assert profile[
        "reference_observation"
    ] == {
        "encoded_sha256": (
            "938fc367f744dee780d57c8b7e64f9dd"
            "781fe1e8599abbe4bb0987b8f844d2f3"
        ),
        "encoded_byte_length": 27_981,
        "decoded_sha256": (
            "f6b6bd6ecc25d752dbca6bbc1fff6de8"
            "fa68bdc970c21b78a7a876599f3da222"
        ),
        "decoded_sample_count": 111_744,
        "decoded_sample_delta": 1_503,
        "probe_duration_ms": 6_984,
    }


def test_lossy_codec_methodology_v1_freezes_encoder_controls():
    profiles = _profiles_by_key()

    aac = profiles[
        "aac-m4a-cbr32"
    ]

    mp3 = profiles[
        "mp3-cbr32"
    ]

    assert aac[
        "encoder_controls"
    ] == [
        {
            "name": "aac_coder",
            "value": "twoloop",
        },
        {
            "name": "aac_ms",
            "value": False,
        },
        {
            "name": "aac_is",
            "value": True,
        },
        {
            "name": "aac_pns",
            "value": True,
        },
        {
            "name": "aac_tns",
            "value": True,
        },
        {
            "name": "aac_ltp",
            "value": False,
        },
        {
            "name": "aac_pred",
            "value": False,
        },
        {
            "name": "aac_pce",
            "value": False,
        },
    ]

    assert mp3[
        "encoder_controls"
    ] == [
        {
            "name": "abr",
            "value": False,
        },
        {
            "name": "reservoir",
            "value": True,
        },
        {
            "name": "joint_stereo",
            "value": False,
        },
    ]


def test_lossy_codec_methodology_v1_keeps_boundary_explicit():
    bundle = (
        build_asr_adversarial_lossy_codec_methodology_v1()
    )

    assert bundle.payload[
        "scientific_boundary"
    ] == {
        "current_product_ingestion_extensions_only": True,
        "adts_aac_qualification_claimed": False,
        "opus_qualification_claimed": False,
        "lossy_codec_quality_standard_claimed": False,
        "encoder_delay_padding_treated_as_failure": False,
        "cross_platform_reproducibility_established": False,
        "development_evidence_only": True,
        "certification_issued": False,
        "production_qualified": False,
        "release_enforcement_eligible": False,
    }


def test_lossy_codec_methodology_v1_verifies_canonically():
    bundle = (
        build_asr_adversarial_lossy_codec_methodology_v1()
    )

    verified = (
        verify_asr_adversarial_lossy_codec_methodology_v1(
            payload=copy.deepcopy(
                bundle.payload
            ),
            expected_sha256=(
                bundle.sha256
            ),
        )
    )

    assert verified == bundle


@pytest.mark.parametrize(
    "mutation",
    (
        "bitrate",
        "encoded_hash",
        "sample_delta",
        "library_hash",
        "control",
        "boundary",
    ),
)
def test_lossy_codec_methodology_v1_rejects_tampering(
    mutation: str,
):
    bundle = (
        build_asr_adversarial_lossy_codec_methodology_v1()
    )

    payload = copy.deepcopy(
        bundle.payload
    )

    if mutation == "bitrate":
        payload[
            "methodology"
        ][
            "profiles"
        ][0][
            "bitrate_bps"
        ] = 31_999

    elif mutation == "encoded_hash":
        payload[
            "methodology"
        ][
            "profiles"
        ][0][
            "reference_observation"
        ][
            "encoded_sha256"
        ] = "0" * 64

    elif mutation == "sample_delta":
        payload[
            "methodology"
        ][
            "profiles"
        ][0][
            "reference_observation"
        ][
            "decoded_sample_delta"
        ] = 350

    elif mutation == "library_hash":
        payload[
            "methodology"
        ][
            "toolchain"
        ][
            "libraries"
        ][0][
            "sha256"
        ] = "0" * 64

    elif mutation == "control":
        payload[
            "methodology"
        ][
            "profiles"
        ][1][
            "encoder_controls"
        ][0][
            "value"
        ] = True

    elif mutation == "boundary":
        payload[
            "scientific_boundary"
        ][
            "opus_qualification_claimed"
        ] = True

    else:
        raise AssertionError(
            mutation
        )

    with pytest.raises(
        HveeContractError,
        match=(
            "lossy codec methodology verification failed"
        ),
    ):
        verify_asr_adversarial_lossy_codec_methodology_v1(
            payload=payload,
            expected_sha256=(
                bundle.sha256
            ),
        )


def test_lossy_codec_methodology_v1_rejects_wrong_digest():
    bundle = (
        build_asr_adversarial_lossy_codec_methodology_v1()
    )

    with pytest.raises(
        HveeContractError,
        match=(
            "lossy codec methodology verification failed"
        ),
    ):
        verify_asr_adversarial_lossy_codec_methodology_v1(
            payload=bundle.payload,
            expected_sha256=(
                "0" * 64
            ),
        )


def test_lossy_codec_methodology_v1_digest_is_frozen():
    bundle = (
        build_asr_adversarial_lossy_codec_methodology_v1()
    )

    assert (
        bundle.sha256
        == (
            "db2d0f0181be5a0bb1beda58cf2099dc"
            "72fbcebaf5eebd1d40d5c554b9817496"
        )
    )

    assert bundle.payload[
        "artifact"
    ] == {
        "schema_version": 1,
        "key": (
            "hetren.asr."
            "adversarial-lossy-codec-methodology.en-us"
        ),
        "version": "1.0.0",
        "type": (
            "adversarial_lossy_codec_methodology"
        ),
    }

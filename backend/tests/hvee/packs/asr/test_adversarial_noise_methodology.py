from __future__ import annotations

import copy

import pytest

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.adversarial_evidence import (
    ASRAdversarialNoiseCondition,
)
from hvee.packs.asr.adversarial_noise_methodology import (
    ASR_ADVERSARIAL_NOISE_V1_MODERATE_SNR_MILLIDB,
    ASR_ADVERSARIAL_NOISE_V1_SEVERE_USABLE_SNR_MILLIDB,
    ASR_ADVERSARIAL_NOISE_V1_SNR_TOLERANCE_MILLIDB,
    build_asr_adversarial_noise_methodology_v1,
    verify_asr_adversarial_noise_methodology_v1,
)


def test_noise_methodology_v1_is_deterministic():
    first = (
        build_asr_adversarial_noise_methodology_v1()
    )

    second = (
        build_asr_adversarial_noise_methodology_v1()
    )

    assert first == second

    assert first.sha256 == second.sha256

    assert len(
        first.sha256
    ) == 64


def test_noise_methodology_v1_has_exact_numeric_tiers():
    bundle = (
        build_asr_adversarial_noise_methodology_v1()
    )

    methodology = bundle.payload[
        "methodology"
    ]

    assert methodology[
        "tiers"
    ] == [
        {
            "condition": (
                ASRAdversarialNoiseCondition
                .MODERATE
                .value
            ),
            "target_snr_millidb": (
                ASR_ADVERSARIAL_NOISE_V1_MODERATE_SNR_MILLIDB
            ),
        },
        {
            "condition": (
                ASRAdversarialNoiseCondition
                .SEVERE_USABLE
                .value
            ),
            "target_snr_millidb": (
                ASR_ADVERSARIAL_NOISE_V1_SEVERE_USABLE_SNR_MILLIDB
            ),
        },
    ]

    assert (
        ASR_ADVERSARIAL_NOISE_V1_MODERATE_SNR_MILLIDB
        == 10_000
    )

    assert (
        ASR_ADVERSARIAL_NOISE_V1_SEVERE_USABLE_SNR_MILLIDB
        == 5_000
    )

    assert (
        ASR_ADVERSARIAL_NOISE_V1_SNR_TOLERANCE_MILLIDB
        == 100
    )


def test_noise_methodology_v1_freezes_deterministic_noise_source():
    bundle = (
        build_asr_adversarial_noise_methodology_v1()
    )

    noise = bundle.payload[
        "methodology"
    ][
        "noise"
    ]

    assert noise == {
        "family": "white",
        "generator_key": (
            "ffmpeg.anoisesrc"
        ),
        "seed": 39_039,
        "sample_rate_hz": 16_000,
        "channel_count": 1,
    }


def test_noise_methodology_v1_disables_amix_normalization():
    bundle = (
        build_asr_adversarial_noise_methodology_v1()
    )

    mixing = bundle.payload[
        "methodology"
    ][
        "mixing"
    ]

    assert mixing == {
        "mixer_key": "ffmpeg.amix",
        "normalize": False,
        "duration_key": "first",
        "dropout_transition_milliseconds": 0,
        "volume_precision_key": "double",
        "clipping_policy_key": "reject",
    }


def test_noise_methodology_v1_keeps_scientific_boundary_explicit():
    bundle = (
        build_asr_adversarial_noise_methodology_v1()
    )

    assert bundle.payload[
        "scientific_boundary"
    ] == {
        "synthetic_white_noise_only": True,
        "natural_environmental_noise_represented": False,
        "universal_noise_severity_standard_claimed": False,
        "development_evidence_only": True,
        "certification_issued": False,
        "production_qualified": False,
        "release_enforcement_eligible": False,
    }


def test_noise_methodology_v1_verifies_canonically():
    bundle = (
        build_asr_adversarial_noise_methodology_v1()
    )

    verified = (
        verify_asr_adversarial_noise_methodology_v1(
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
        "snr",
        "seed",
        "normalize",
        "boundary",
    ),
)
def test_noise_methodology_v1_rejects_tampering(
    mutation: str,
):
    bundle = (
        build_asr_adversarial_noise_methodology_v1()
    )

    payload = copy.deepcopy(
        bundle.payload
    )

    if mutation == "snr":
        payload[
            "methodology"
        ][
            "tiers"
        ][0][
            "target_snr_millidb"
        ] = 9_999

    elif mutation == "seed":
        payload[
            "methodology"
        ][
            "noise"
        ][
            "seed"
        ] = 39_040

    elif mutation == "normalize":
        payload[
            "methodology"
        ][
            "mixing"
        ][
            "normalize"
        ] = True

    elif mutation == "boundary":
        payload[
            "scientific_boundary"
        ][
            "natural_environmental_noise_represented"
        ] = True

    else:
        raise AssertionError(
            mutation
        )

    with pytest.raises(
        HveeContractError,
        match=(
            "noise methodology verification failed"
        ),
    ):
        verify_asr_adversarial_noise_methodology_v1(
            payload=payload,
            expected_sha256=(
                bundle.sha256
            ),
        )


def test_noise_methodology_v1_rejects_wrong_digest():
    bundle = (
        build_asr_adversarial_noise_methodology_v1()
    )

    with pytest.raises(
        HveeContractError,
        match=(
            "noise methodology verification failed"
        ),
    ):
        verify_asr_adversarial_noise_methodology_v1(
            payload=bundle.payload,
            expected_sha256=(
                "0" * 64
            ),
        )

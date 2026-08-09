from __future__ import annotations

import pytest

from hvee.core.contracts import HveeContractError
from hvee.core.paired_assurance import (
    PairedIntervalMethod,
    PairedIntervalPolicy,
)
from hvee.packs.asr.release_assurance_policy import (
    ASR_MATCHED_RELEASE_ASSURANCE_POLICY_KEY,
    ASR_MATCHED_RELEASE_ASSURANCE_POLICY_VERSION,
    ASRMatchedReleaseAssurancePolicyV1,
)


def _interval() -> PairedIntervalPolicy:
    return PairedIntervalPolicy(
        method=(
            PairedIntervalMethod
            .BOOTSTRAP_PERCENTILE_V1
        ),
        confidence_level=0.95,
        minimum_usable_pairs=20,
        resamples=5000,
        random_seed=12345,
    )


def test_policy_has_stable_versioned_identity():
    policy = (
        ASRMatchedReleaseAssurancePolicyV1(
            interval=_interval(),
            normalized_wer_noninferiority_margin=(
                0.01
            ),
            normalized_cer_noninferiority_margin=(
                0.005
            ),
        )
    )

    assert policy.key == (
        ASR_MATCHED_RELEASE_ASSURANCE_POLICY_KEY
    )
    assert policy.version == (
        ASR_MATCHED_RELEASE_ASSURANCE_POLICY_VERSION
    )

    assert (
        policy
        .normalized_wer_noninferiority_margin
        == 0.01
    )
    assert (
        policy
        .normalized_cer_noninferiority_margin
        == 0.005
    )


def test_policy_can_enable_only_wer():
    policy = (
        ASRMatchedReleaseAssurancePolicyV1(
            interval=_interval(),
            normalized_wer_noninferiority_margin=(
                0.01
            ),
            normalized_cer_noninferiority_margin=None,
        )
    )

    assert (
        policy
        .normalized_wer_noninferiority_margin
        == 0.01
    )
    assert (
        policy
        .normalized_cer_noninferiority_margin
        is None
    )


def test_policy_can_enable_only_cer():
    policy = (
        ASRMatchedReleaseAssurancePolicyV1(
            interval=_interval(),
            normalized_wer_noninferiority_margin=None,
            normalized_cer_noninferiority_margin=(
                0.005
            ),
        )
    )

    assert (
        policy
        .normalized_wer_noninferiority_margin
        is None
    )
    assert (
        policy
        .normalized_cer_noninferiority_margin
        == 0.005
    )


def test_policy_rejects_all_metrics_disabled():
    with pytest.raises(
        HveeContractError,
        match="at least one metric",
    ):
        ASRMatchedReleaseAssurancePolicyV1(
            interval=_interval(),
            normalized_wer_noninferiority_margin=None,
            normalized_cer_noninferiority_margin=None,
        )


@pytest.mark.parametrize(
    "margin",
    [
        -0.01,
        float("inf"),
        float("nan"),
        True,
    ],
)
def test_invalid_wer_margin_is_rejected(
    margin,
):
    with pytest.raises(
        HveeContractError,
        match="WER",
    ):
        ASRMatchedReleaseAssurancePolicyV1(
            interval=_interval(),
            normalized_wer_noninferiority_margin=margin,
            normalized_cer_noninferiority_margin=None,
        )


@pytest.mark.parametrize(
    "margin",
    [
        -0.01,
        float("inf"),
        float("nan"),
        True,
    ],
)
def test_invalid_cer_margin_is_rejected(
    margin,
):
    with pytest.raises(
        HveeContractError,
        match="CER",
    ):
        ASRMatchedReleaseAssurancePolicyV1(
            interval=_interval(),
            normalized_wer_noninferiority_margin=None,
            normalized_cer_noninferiority_margin=margin,
        )


def test_policy_requires_interval_contract():
    with pytest.raises(
        HveeContractError,
        match="PairedIntervalPolicy",
    ):
        ASRMatchedReleaseAssurancePolicyV1(
            interval=object(),  # type: ignore[arg-type]
            normalized_wer_noninferiority_margin=0.01,
            normalized_cer_noninferiority_margin=None,
        )

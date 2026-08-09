from __future__ import annotations

import pytest

from hvee.core.contracts import HveeContractError
from hvee.core.paired_assurance import (
    PairedIntervalMethod,
    PairedIntervalPolicy,
)


def _policy() -> PairedIntervalPolicy:
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


def test_explicit_paired_interval_policy():
    policy = _policy()

    assert policy.method == (
        PairedIntervalMethod
        .BOOTSTRAP_PERCENTILE_V1
    )
    assert policy.confidence_level == 0.95
    assert policy.minimum_usable_pairs == 20
    assert policy.resamples == 5000
    assert policy.random_seed == 12345


@pytest.mark.parametrize(
    "confidence_level",
    [
        0.0,
        1.0,
        -0.1,
        1.1,
        float("inf"),
        float("nan"),
        True,
    ],
)
def test_invalid_confidence_level_is_rejected(
    confidence_level,
):
    with pytest.raises(
        HveeContractError,
        match="confidence level",
    ):
        PairedIntervalPolicy(
            method=(
                PairedIntervalMethod
                .BOOTSTRAP_PERCENTILE_V1
            ),
            confidence_level=confidence_level,
            minimum_usable_pairs=2,
            resamples=100,
            random_seed=1,
        )


@pytest.mark.parametrize(
    "minimum",
    [
        0,
        1,
        -1,
        True,
    ],
)
def test_minimum_pairs_below_two_is_rejected(
    minimum,
):
    with pytest.raises(
        HveeContractError,
        match="minimum usable pairs",
    ):
        PairedIntervalPolicy(
            method=(
                PairedIntervalMethod
                .BOOTSTRAP_PERCENTILE_V1
            ),
            confidence_level=0.95,
            minimum_usable_pairs=minimum,
            resamples=100,
            random_seed=1,
        )


@pytest.mark.parametrize(
    "resamples",
    [
        0,
        -1,
        True,
    ],
)
def test_invalid_resample_count_is_rejected(
    resamples,
):
    with pytest.raises(
        HveeContractError,
        match="resamples",
    ):
        PairedIntervalPolicy(
            method=(
                PairedIntervalMethod
                .BOOTSTRAP_PERCENTILE_V1
            ),
            confidence_level=0.95,
            minimum_usable_pairs=2,
            resamples=resamples,
            random_seed=1,
        )


@pytest.mark.parametrize(
    "seed",
    [
        -1,
        2**64,
        True,
    ],
)
def test_invalid_seed_is_rejected(seed):
    with pytest.raises(
        HveeContractError,
        match="random seed",
    ):
        PairedIntervalPolicy(
            method=(
                PairedIntervalMethod
                .BOOTSTRAP_PERCENTILE_V1
            ),
            confidence_level=0.95,
            minimum_usable_pairs=2,
            resamples=100,
            random_seed=seed,
        )


def test_invalid_method_type_is_rejected():
    with pytest.raises(
        HveeContractError,
        match="interval method",
    ):
        PairedIntervalPolicy(
            method="bootstrap",  # type: ignore[arg-type]
            confidence_level=0.95,
            minimum_usable_pairs=2,
            resamples=100,
            random_seed=1,
        )

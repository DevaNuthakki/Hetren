from __future__ import annotations

import math
from dataclasses import dataclass

from hvee.core.contracts import HveeContractError
from hvee.core.paired_assurance import (
    PairedIntervalPolicy,
)


ASR_MATCHED_RELEASE_ASSURANCE_POLICY_KEY = (
    "hetren.asr.matched-release-assurance"
)
ASR_MATCHED_RELEASE_ASSURANCE_POLICY_VERSION = (
    "1.0.0"
)


def _validate_optional_margin(
    *,
    name: str,
    value: float | None,
) -> None:
    if value is None:
        return

    if (
        isinstance(value, bool)
        or not isinstance(
            value,
            (int, float),
        )
        or not math.isfinite(
            float(value)
        )
        or float(value) < 0.0
    ):
        raise HveeContractError(
            f"{name} must be a finite "
            "non-negative number or null"
        )


@dataclass(frozen=True, slots=True)
class ASRMatchedReleaseAssurancePolicyV1:
    """
    Explicit statistical-assurance configuration for matched ASR runs.

    A non-inferiority margin represents the largest positive
    candidate-minus-baseline mean delta that the corresponding
    lower-is-better metric may tolerate.

    Example only:

        margin = 0.01

    means the policy would eventually ask whether evidence supports
    that the candidate's mean normalized error is not worse than the
    baseline by more than 0.01.

    This contract deliberately provides no default confidence level,
    sample requirement, bootstrap configuration, or quality margin.

    It does not calculate statistics and does not produce a verdict.
    """

    interval: PairedIntervalPolicy

    normalized_wer_noninferiority_margin: (
        float | None
    )
    normalized_cer_noninferiority_margin: (
        float | None
    )

    @property
    def key(self) -> str:
        return (
            ASR_MATCHED_RELEASE_ASSURANCE_POLICY_KEY
        )

    @property
    def version(self) -> str:
        return (
            ASR_MATCHED_RELEASE_ASSURANCE_POLICY_VERSION
        )

    def __post_init__(self) -> None:
        if not isinstance(
            self.interval,
            PairedIntervalPolicy,
        ):
            raise HveeContractError(
                "ASR matched release assurance "
                "requires PairedIntervalPolicy"
            )

        _validate_optional_margin(
            name=(
                "normalized WER "
                "non-inferiority margin"
            ),
            value=(
                self
                .normalized_wer_noninferiority_margin
            ),
        )

        _validate_optional_margin(
            name=(
                "normalized CER "
                "non-inferiority margin"
            ),
            value=(
                self
                .normalized_cer_noninferiority_margin
            ),
        )

        if (
            self
            .normalized_wer_noninferiority_margin
            is None
            and self
            .normalized_cer_noninferiority_margin
            is None
        ):
            raise HveeContractError(
                "ASR matched release assurance "
                "must enable at least one metric"
            )

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from hvee.core.contracts import HveeContractError


class PairedIntervalMethod(StrEnum):
    """
    Versioned statistical interval methods supported by HVEE.

    Portfolio/release policies bind the exact method identity so a
    later statistical implementation cannot silently replace the
    scientific procedure used by an existing policy.
    """

    BOOTSTRAP_PERCENTILE_V1 = (
        "paired_bootstrap_percentile_v1"
    )


@dataclass(frozen=True, slots=True)
class PairedIntervalPolicy:
    """
    Explicit configuration for paired uncertainty estimation.

    No defaults are provided. A caller must deliberately choose every
    statistical setting so release semantics are never determined by
    hidden library defaults.

    This contract configures an interval method only. It does not
    calculate an interval or produce a release verdict.
    """

    method: PairedIntervalMethod
    confidence_level: float
    minimum_usable_pairs: int
    resamples: int
    random_seed: int

    def __post_init__(self) -> None:
        if not isinstance(
            self.method,
            PairedIntervalMethod,
        ):
            raise HveeContractError(
                "paired interval method must be "
                "PairedIntervalMethod"
            )

        if (
            isinstance(
                self.confidence_level,
                bool,
            )
            or not isinstance(
                self.confidence_level,
                (int, float),
            )
            or not math.isfinite(
                float(
                    self.confidence_level
                )
            )
            or not (
                0.0
                < float(
                    self.confidence_level
                )
                < 1.0
            )
        ):
            raise HveeContractError(
                "confidence level must be a finite "
                "number strictly between 0 and 1"
            )

        if (
            isinstance(
                self.minimum_usable_pairs,
                bool,
            )
            or not isinstance(
                self.minimum_usable_pairs,
                int,
            )
            or self.minimum_usable_pairs < 2
        ):
            raise HveeContractError(
                "minimum usable pairs must be "
                "an integer of at least 2"
            )

        if (
            isinstance(
                self.resamples,
                bool,
            )
            or not isinstance(
                self.resamples,
                int,
            )
            or self.resamples < 1
        ):
            raise HveeContractError(
                "bootstrap resamples must be "
                "a positive integer"
            )

        if (
            isinstance(
                self.random_seed,
                bool,
            )
            or not isinstance(
                self.random_seed,
                int,
            )
            or self.random_seed < 0
            or self.random_seed
            > (2**64 - 1)
        ):
            raise HveeContractError(
                "bootstrap random seed must be "
                "an unsigned 64-bit integer"
            )

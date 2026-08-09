from __future__ import annotations

import hashlib
import math
import statistics
from dataclasses import dataclass
from enum import StrEnum

from hvee.core.contracts import HveeContractError
from hvee.core.decision import (
    EvidenceAssessment,
    IntegrityAssessment,
)
from hvee.core.matched_evidence import (
    MatchedObservationCohort,
)
from hvee.core.paired_assurance import (
    PairedIntervalMethod,
    PairedIntervalPolicy,
)


class PairedIntervalReason(StrEnum):
    READY = "ready"
    INTEGRITY_INVALID = "integrity_invalid"
    COHORT_INCOMPLETE = "cohort_incomplete"
    MINIMUM_PAIRS_NOT_MET = (
        "minimum_pairs_not_met"
    )


@dataclass(frozen=True, slots=True)
class PairedMeanDeltaInterval:
    """
    Statistical assurance result for one matched numeric cohort.

    Delta is always:

        candidate - baseline

    READY means the exact declared cohort is complete, evidence
    integrity is valid, and the explicit minimum-pair requirement is
    satisfied.

    Non-ready results intentionally contain no confidence interval.
    Missing/incomplete evidence is never silently discarded to produce
    an apparently stronger assurance result.
    """

    method: PairedIntervalMethod
    confidence_level: float
    minimum_usable_pairs: int
    resamples: int
    random_seed: int

    total_cases: int
    usable_pairs: int

    integrity: IntegrityAssessment
    evidence: EvidenceAssessment
    reason: PairedIntervalReason

    mean_delta: float | None
    lower_bound: float | None
    upper_bound: float | None

    def __post_init__(self) -> None:
        if not isinstance(
            self.method,
            PairedIntervalMethod,
        ):
            raise HveeContractError(
                "paired interval result requires "
                "PairedIntervalMethod"
            )

        if not isinstance(
            self.integrity,
            IntegrityAssessment,
        ):
            raise HveeContractError(
                "paired interval integrity must be "
                "IntegrityAssessment"
            )

        if not isinstance(
            self.evidence,
            EvidenceAssessment,
        ):
            raise HveeContractError(
                "paired interval evidence must be "
                "EvidenceAssessment"
            )

        if not isinstance(
            self.reason,
            PairedIntervalReason,
        ):
            raise HveeContractError(
                "paired interval reason must be "
                "PairedIntervalReason"
            )

        for name, value in (
            ("total cases", self.total_cases),
            ("usable pairs", self.usable_pairs),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
            ):
                raise HveeContractError(
                    f"{name} must be a non-negative integer"
                )

        if self.usable_pairs > self.total_cases:
            raise HveeContractError(
                "usable pairs cannot exceed total cases"
            )

        numeric_values = (
            self.mean_delta,
            self.lower_bound,
            self.upper_bound,
        )

        if self.reason == PairedIntervalReason.READY:
            if (
                self.integrity
                != IntegrityAssessment.VALID
                or self.evidence
                != EvidenceAssessment.SUFFICIENT
            ):
                raise HveeContractError(
                    "ready paired interval requires "
                    "valid and sufficient evidence"
                )

            for value in numeric_values:
                if (
                    isinstance(value, bool)
                    or not isinstance(
                        value,
                        (int, float),
                    )
                    or not math.isfinite(
                        float(value)
                    )
                ):
                    raise HveeContractError(
                        "ready paired interval requires "
                        "finite interval statistics"
                    )

            assert self.lower_bound is not None
            assert self.upper_bound is not None

            if (
                self.lower_bound
                > self.upper_bound
            ):
                raise HveeContractError(
                    "paired interval lower bound "
                    "cannot exceed upper bound"
                )

            return

        if any(
            value is not None
            for value
            in numeric_values
        ):
            raise HveeContractError(
                "non-ready paired interval cannot "
                "contain interval statistics"
            )

        if (
            self.reason
            == PairedIntervalReason.INTEGRITY_INVALID
        ):
            if (
                self.integrity
                != IntegrityAssessment.INVALID
                or self.evidence
                != EvidenceAssessment.INSUFFICIENT
            ):
                raise HveeContractError(
                    "integrity-invalid interval result "
                    "requires invalid integrity and "
                    "insufficient evidence"
                )
        else:
            if (
                self.integrity
                != IntegrityAssessment.VALID
                or self.evidence
                != EvidenceAssessment.INSUFFICIENT
            ):
                raise HveeContractError(
                    "non-ready valid-integrity interval "
                    "requires insufficient evidence"
                )

    @property
    def ready(self) -> bool:
        return (
            self.reason
            == PairedIntervalReason.READY
        )


def _percentile(
    sorted_values: tuple[float, ...],
    probability: float,
) -> float:
    """
    Deterministic linear-interpolated empirical quantile.

    The exact quantile rule is part of
    paired_bootstrap_percentile_v1 semantics.
    """

    if not sorted_values:
        raise HveeContractError(
            "percentile requires at least one value"
        )

    if not (
        0.0 <= probability <= 1.0
    ):
        raise HveeContractError(
            "percentile probability must be "
            "between 0 and 1"
        )

    if len(sorted_values) == 1:
        return sorted_values[0]

    position = (
        (len(sorted_values) - 1)
        * probability
    )

    lower_index = math.floor(position)
    upper_index = math.ceil(position)

    lower_value = sorted_values[
        lower_index
    ]
    upper_value = sorted_values[
        upper_index
    ]

    if lower_index == upper_index:
        return lower_value

    fraction = position - lower_index

    return (
        lower_value
        + fraction
        * (
            upper_value
            - lower_value
        )
    )


_BOOTSTRAP_V1_DOMAIN = (
    b"hetren.paired_bootstrap_percentile_v1\\0"
)


def _deterministic_bootstrap_index(
    *,
    count: int,
    random_seed: int,
    resample_index: int,
    draw_index: int,
) -> int:
    """
    Produce one deterministic unbiased bootstrap index.

    SHA-256 counter material is used instead of a runtime PRNG so the
    resampling procedure is explicitly defined by the HVEE method
    version rather than by Python's random implementation.

    Rejection sampling avoids modulo bias when mapping the 256-bit
    digest space onto the cohort index range.
    """

    if count < 1:
        raise HveeContractError(
            "bootstrap index requires positive count"
        )

    limit = (
        (1 << 256)
        - ((1 << 256) % count)
    )

    attempt = 0

    while True:
        material = b":".join(
            (
                _BOOTSTRAP_V1_DOMAIN,
                str(random_seed).encode("ascii"),
                str(resample_index).encode("ascii"),
                str(draw_index).encode("ascii"),
                str(attempt).encode("ascii"),
            )
        )

        value = int.from_bytes(
            hashlib.sha256(
                material
            ).digest(),
            byteorder="big",
            signed=False,
        )

        if value < limit:
            return value % count

        attempt += 1


def _paired_bootstrap_mean_deltas(
    *,
    deltas: tuple[float, ...],
    resamples: int,
    random_seed: int,
) -> tuple[float, ...]:
    """
    Bootstrap the paired mean delta.

    Pairing is already represented by each delta. Resampling therefore
    samples matched test-case deltas with replacement rather than
    independently resampling baseline and candidate observations.

    Bootstrap indices are generated by the deterministic SHA-256
    procedure defined by paired_bootstrap_percentile_v1.
    """

    if not deltas:
        raise HveeContractError(
            "paired bootstrap requires "
            "at least one delta"
        )

    count = len(deltas)

    bootstrap_means: list[float] = []

    for resample_index in range(
        resamples
    ):
        sample = tuple(
            deltas[
                _deterministic_bootstrap_index(
                    count=count,
                    random_seed=random_seed,
                    resample_index=resample_index,
                    draw_index=draw_index,
                )
            ]
            for draw_index
            in range(count)
        )

        mean = float(
            statistics.fmean(
                sample
            )
        )

        if not math.isfinite(mean):
            raise HveeContractError(
                "paired bootstrap produced "
                "a non-finite mean"
            )

        bootstrap_means.append(mean)

    return tuple(
        sorted(
            bootstrap_means
        )
    )


def calculate_paired_mean_delta_interval(
    *,
    cohort: MatchedObservationCohort,
    policy: PairedIntervalPolicy,
) -> PairedMeanDeltaInterval:
    """
    Calculate a deterministic paired percentile-bootstrap interval.

    The procedure is intentionally conservative about evidence:

    1. Invalid cohort integrity -> no interval.
    2. Incomplete declared cohort -> no interval.
    3. Fewer usable pairs than explicitly required -> no interval.
    4. Otherwise bootstrap the mean candidate-minus-baseline delta.

    This function does not interpret metric direction and does not
    produce a release verdict.
    """

    if not isinstance(
        cohort,
        MatchedObservationCohort,
    ):
        raise HveeContractError(
            "paired interval requires "
            "MatchedObservationCohort"
        )

    if not isinstance(
        policy,
        PairedIntervalPolicy,
    ):
        raise HveeContractError(
            "paired interval requires "
            "PairedIntervalPolicy"
        )

    common = {
        "method": policy.method,
        "confidence_level": (
            policy.confidence_level
        ),
        "minimum_usable_pairs": (
            policy.minimum_usable_pairs
        ),
        "resamples": policy.resamples,
        "random_seed": policy.random_seed,
        "total_cases": cohort.total_cases,
        "usable_pairs": cohort.usable_pairs,
    }

    if not cohort.integrity_valid:
        return PairedMeanDeltaInterval(
            **common,
            integrity=(
                IntegrityAssessment.INVALID
            ),
            evidence=(
                EvidenceAssessment.INSUFFICIENT
            ),
            reason=(
                PairedIntervalReason
                .INTEGRITY_INVALID
            ),
            mean_delta=None,
            lower_bound=None,
            upper_bound=None,
        )

    if not cohort.complete:
        return PairedMeanDeltaInterval(
            **common,
            integrity=(
                IntegrityAssessment.VALID
            ),
            evidence=(
                EvidenceAssessment.INSUFFICIENT
            ),
            reason=(
                PairedIntervalReason
                .COHORT_INCOMPLETE
            ),
            mean_delta=None,
            lower_bound=None,
            upper_bound=None,
        )

    if (
        cohort.usable_pairs
        < policy.minimum_usable_pairs
    ):
        return PairedMeanDeltaInterval(
            **common,
            integrity=(
                IntegrityAssessment.VALID
            ),
            evidence=(
                EvidenceAssessment.INSUFFICIENT
            ),
            reason=(
                PairedIntervalReason
                .MINIMUM_PAIRS_NOT_MET
            ),
            mean_delta=None,
            lower_bound=None,
            upper_bound=None,
        )

    if policy.method != (
        PairedIntervalMethod
        .BOOTSTRAP_PERCENTILE_V1
    ):
        raise HveeContractError(
            "unsupported paired interval method"
        )

    deltas = cohort.deltas

    if len(deltas) != cohort.usable_pairs:
        raise HveeContractError(
            "paired interval delta count "
            "does not match usable-pair count"
        )

    if any(
        not math.isfinite(delta)
        for delta
        in deltas
    ):
        raise HveeContractError(
            "paired interval requires "
            "finite matched deltas"
        )

    mean_delta = float(
        statistics.fmean(
            deltas
        )
    )

    bootstrap_means = (
        _paired_bootstrap_mean_deltas(
            deltas=deltas,
            resamples=policy.resamples,
            random_seed=policy.random_seed,
        )
    )

    alpha = (
        1.0
        - policy.confidence_level
    )

    lower_bound = _percentile(
        bootstrap_means,
        alpha / 2.0,
    )

    upper_bound = _percentile(
        bootstrap_means,
        1.0 - alpha / 2.0,
    )

    return PairedMeanDeltaInterval(
        **common,
        integrity=IntegrityAssessment.VALID,
        evidence=EvidenceAssessment.SUFFICIENT,
        reason=PairedIntervalReason.READY,
        mean_delta=mean_delta,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
    )

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

from hvee.core.contracts import (
    HveeContractError,
)
from hvee.core.matched_evidence import (
    MatchedObservationCohort,
)


@dataclass(frozen=True, slots=True)
class PairedDescriptiveStatistics:
    """
    Descriptive statistics for one matched numeric observation cohort.

    Statistics are calculated only over explicitly usable matched
    pairs. Missing, unavailable, invalid, and duplicate pairs are
    never silently treated as usable observations: their exclusion is
    represented by total/usable/incomplete counts plus the cohort's
    completeness and integrity state.

    Delta is always:

        candidate - baseline

    The core deliberately reports candidate-lower/candidate-higher
    rather than "improved"/"regressed". Metric direction belongs to
    the domain/policy layer.

    Exact equality is used for the unchanged count. No arbitrary
    tolerance or practical-equivalence margin is introduced here.
    """

    total_cases: int
    usable_pairs: int
    incomplete_pairs: int

    complete: bool
    integrity_valid: bool

    baseline_mean: float | None
    candidate_mean: float | None

    mean_delta: float | None
    median_delta: float | None
    minimum_delta: float | None
    maximum_delta: float | None

    candidate_lower_count: int
    candidate_higher_count: int
    unchanged_count: int

    def __post_init__(self) -> None:
        for name, value in (
            ("total cases", self.total_cases),
            ("usable pairs", self.usable_pairs),
            (
                "incomplete pairs",
                self.incomplete_pairs,
            ),
            (
                "candidate lower count",
                self.candidate_lower_count,
            ),
            (
                "candidate higher count",
                self.candidate_higher_count,
            ),
            (
                "unchanged count",
                self.unchanged_count,
            ),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
            ):
                raise HveeContractError(
                    f"{name} must be a non-negative integer"
                )

        if (
            self.usable_pairs
            + self.incomplete_pairs
            != self.total_cases
        ):
            raise HveeContractError(
                "usable and incomplete pair counts "
                "must account for the complete cohort"
            )

        if (
            self.candidate_lower_count
            + self.candidate_higher_count
            + self.unchanged_count
            != self.usable_pairs
        ):
            raise HveeContractError(
                "delta direction counts must account "
                "for every usable pair"
            )

        if not isinstance(
            self.complete,
            bool,
        ):
            raise HveeContractError(
                "complete must be boolean"
            )

        if not isinstance(
            self.integrity_valid,
            bool,
        ):
            raise HveeContractError(
                "integrity_valid must be boolean"
            )

        numeric_values = (
            self.baseline_mean,
            self.candidate_mean,
            self.mean_delta,
            self.median_delta,
            self.minimum_delta,
            self.maximum_delta,
        )

        if self.usable_pairs == 0:
            if any(
                value is not None
                for value
                in numeric_values
            ):
                raise HveeContractError(
                    "zero usable pairs cannot contain "
                    "descriptive numeric statistics"
                )
            return

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
                    "descriptive numeric statistics "
                    "must be finite when usable pairs exist"
                )

        assert self.minimum_delta is not None
        assert self.maximum_delta is not None

        if (
            self.minimum_delta
            > self.maximum_delta
        ):
            raise HveeContractError(
                "minimum delta cannot exceed maximum delta"
            )


def summarize_matched_observation_cohort(
    cohort: MatchedObservationCohort,
) -> PairedDescriptiveStatistics:
    """
    Summarize one matched numeric cohort without inference.

    This function intentionally performs no:
    - hypothesis testing;
    - confidence-interval calculation;
    - minimum-sample enforcement;
    - multiplicity correction;
    - release-policy evaluation;
    - missing-data imputation.

    It is therefore descriptive evidence only.
    """

    if not isinstance(
        cohort,
        MatchedObservationCohort,
    ):
        raise HveeContractError(
            "paired statistics require "
            "MatchedObservationCohort"
        )

    usable_pairs = tuple(
        pair
        for pair
        in cohort.pairs
        if pair.usable
    )

    if not usable_pairs:
        return PairedDescriptiveStatistics(
            total_cases=cohort.total_cases,
            usable_pairs=0,
            incomplete_pairs=(
                cohort.incomplete_pairs
            ),
            complete=cohort.complete,
            integrity_valid=(
                cohort.integrity_valid
            ),
            baseline_mean=None,
            candidate_mean=None,
            mean_delta=None,
            median_delta=None,
            minimum_delta=None,
            maximum_delta=None,
            candidate_lower_count=0,
            candidate_higher_count=0,
            unchanged_count=0,
        )

    baseline_values: list[float] = []
    candidate_values: list[float] = []
    deltas: list[float] = []

    candidate_lower_count = 0
    candidate_higher_count = 0
    unchanged_count = 0

    for pair in usable_pairs:
        baseline_value = pair.baseline.value
        candidate_value = pair.candidate.value
        delta = pair.delta

        if (
            baseline_value is None
            or candidate_value is None
            or delta is None
        ):
            raise HveeContractError(
                "usable matched pair is missing "
                "its numeric values"
            )

        values = (
            baseline_value,
            candidate_value,
            delta,
        )

        if any(
            not math.isfinite(float(value))
            for value
            in values
        ):
            raise HveeContractError(
                "paired statistics require "
                "finite numeric values"
            )

        baseline_values.append(
            float(baseline_value)
        )
        candidate_values.append(
            float(candidate_value)
        )
        deltas.append(
            float(delta)
        )

        if candidate_value < baseline_value:
            candidate_lower_count += 1
        elif candidate_value > baseline_value:
            candidate_higher_count += 1
        else:
            unchanged_count += 1

    return PairedDescriptiveStatistics(
        total_cases=cohort.total_cases,
        usable_pairs=len(usable_pairs),
        incomplete_pairs=(
            cohort.incomplete_pairs
        ),
        complete=cohort.complete,
        integrity_valid=(
            cohort.integrity_valid
        ),
        baseline_mean=float(
            statistics.fmean(
                baseline_values
            )
        ),
        candidate_mean=float(
            statistics.fmean(
                candidate_values
            )
        ),
        mean_delta=float(
            statistics.fmean(
                deltas
            )
        ),
        median_delta=float(
            statistics.median(
                deltas
            )
        ),
        minimum_delta=min(deltas),
        maximum_delta=max(deltas),
        candidate_lower_count=(
            candidate_lower_count
        ),
        candidate_higher_count=(
            candidate_higher_count
        ),
        unchanged_count=unchanged_count,
    )

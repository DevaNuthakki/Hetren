from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from hvee.core.decision import DecisionVerdict


PLANNER_KEY = "hetren.behavioral.multi-objective-uncertainty-aware-planner"
PLANNER_VERSION = "1.0.0"


class MultiObjectivePlannerError(ValueError):
    """Raised when planner inputs violate the frozen pure-core contract."""


class MultiObjectiveSelectionReason(str, Enum):
    GRID_EXHAUSTED = "grid_exhausted"
    STRUCTURAL_CENTER_BOOTSTRAP = "structural_center_bootstrap"
    UNIQUE_STRUCTURAL_NONDOMINATED = "unique_structural_nondominated"
    UNIQUE_INFORMATION_NONDOMINATED = "unique_information_nondominated"
    DETERMINISTIC_REPRODUCIBILITY_TIE_BREAK = "deterministic_reproducibility_tie_break"


@dataclass(frozen=True, order=True)
class OpposingInterval:
    left_index: int
    right_index: int

    @property
    def ambiguity_mass(self) -> int:
        return self.right_index - self.left_index - 1


@dataclass(frozen=True)
class MultiObjectiveCandidateRecord:
    candidate_index: int

    coverage_gain: int

    guaranteed_boundary_ambiguity_reduction: int
    worst_case_boundary_ambiguity_expansion: int

    outcome_boundary_mass_separation: int
    outcome_interval_symmetric_difference_count: int

    pass_boundary_ambiguity: int
    fail_boundary_ambiguity: int


@dataclass(frozen=True)
class MultiObjectivePlannerDecision:
    candidate_count: int
    observed_count: int
    remaining_candidate_count: int

    selected_candidate_index: int | None
    selection_reason: MultiObjectiveSelectionReason

    primary_frontier_candidate_indices: tuple[int, ...]
    uncertainty_frontier_candidate_indices: tuple[int, ...]

    unresolved_action_ambiguity: bool

    candidate_records: tuple[
        MultiObjectiveCandidateRecord,
        ...,
    ]

    @property
    def terminal(self) -> bool:
        return self.selection_reason is MultiObjectiveSelectionReason.GRID_EXHAUSTED


def _validate_candidate_count(
    candidate_count: int,
) -> int:
    if (
        isinstance(
            candidate_count,
            bool,
        )
        or not isinstance(
            candidate_count,
            int,
        )
        or candidate_count < 2
    ):
        raise MultiObjectivePlannerError("candidate_count must be an integer >= 2")

    return candidate_count


def _validate_verdict(
    verdict: DecisionVerdict,
) -> DecisionVerdict:
    if not isinstance(
        verdict,
        DecisionVerdict,
    ) or verdict not in (
        DecisionVerdict.PASS,
        DecisionVerdict.FAIL,
    ):
        raise MultiObjectivePlannerError(
            "observed verdict must be a DecisionVerdict PASS or FAIL"
        )

    return verdict


def _normalize_observations(
    *,
    candidate_count: int,
    observations: Mapping[
        int,
        DecisionVerdict,
    ],
) -> dict[
    int,
    DecisionVerdict,
]:
    if not isinstance(
        observations,
        Mapping,
    ):
        raise MultiObjectivePlannerError("observations must be a mapping")

    normalized: dict[
        int,
        DecisionVerdict,
    ] = {}

    for index, verdict in observations.items():
        if (
            isinstance(
                index,
                bool,
            )
            or not isinstance(
                index,
                int,
            )
            or index < 0
            or index >= candidate_count
        ):
            raise MultiObjectivePlannerError(
                "observation index is outside candidate grid"
            )

        normalized[index] = _validate_verdict(verdict)

    return dict(sorted(normalized.items()))


def coverage_distance_mass(
    *,
    candidate_count: int,
    observed_indices: set[int] | frozenset[int],
) -> int:
    candidate_count = _validate_candidate_count(candidate_count)

    normalized = set(observed_indices)

    if not normalized:
        raise MultiObjectivePlannerError(
            "coverage distance mass requires at least one observed candidate"
        )

    for index in normalized:
        if (
            isinstance(
                index,
                bool,
            )
            or not isinstance(
                index,
                int,
            )
            or index < 0
            or index >= candidate_count
        ):
            raise MultiObjectivePlannerError("observed index is outside candidate grid")

    return sum(
        min(abs(candidate - observed) for observed in normalized)
        for candidate in range(candidate_count)
        if candidate not in normalized
    )


def opposing_intervals(
    observations: Mapping[
        int,
        DecisionVerdict,
    ],
) -> tuple[
    OpposingInterval,
    ...,
]:
    ordered = sorted(observations)

    intervals: list[OpposingInterval] = []

    for left, right in zip(
        ordered,
        ordered[1:],
    ):
        if right - left > 1 and observations[left] is not observations[right]:
            intervals.append(
                OpposingInterval(
                    left_index=left,
                    right_index=right,
                )
            )

    return tuple(intervals)


def boundary_ambiguity_mass(
    observations: Mapping[
        int,
        DecisionVerdict,
    ],
) -> int:
    return sum(interval.ambiguity_mass for interval in opposing_intervals(observations))


def _branch_observations(
    *,
    observations: Mapping[
        int,
        DecisionVerdict,
    ],
    candidate_index: int,
    verdict: DecisionVerdict,
) -> dict[
    int,
    DecisionVerdict,
]:
    branch = dict(observations)

    branch[candidate_index] = verdict

    return dict(sorted(branch.items()))


def build_multi_objective_candidate_record(
    *,
    candidate_count: int,
    observations: Mapping[
        int,
        DecisionVerdict,
    ],
    candidate_index: int,
) -> MultiObjectiveCandidateRecord:
    candidate_count = _validate_candidate_count(candidate_count)

    observed = _normalize_observations(
        candidate_count=(candidate_count),
        observations=(observations),
    )

    if not observed:
        raise MultiObjectivePlannerError(
            "candidate scoring requires at least one observation"
        )

    if (
        isinstance(
            candidate_index,
            bool,
        )
        or not isinstance(
            candidate_index,
            int,
        )
        or candidate_index < 0
        or candidate_index >= candidate_count
    ):
        raise MultiObjectivePlannerError("candidate_index is outside candidate grid")

    if candidate_index in observed:
        raise MultiObjectivePlannerError("candidate_index must be unobserved")

    observed_indices = set(observed)

    coverage_before = coverage_distance_mass(
        candidate_count=(candidate_count),
        observed_indices=(observed_indices),
    )

    coverage_after = coverage_distance_mass(
        candidate_count=(candidate_count),
        observed_indices={
            *observed_indices,
            candidate_index,
        },
    )

    coverage_gain = coverage_before - coverage_after

    boundary_before = boundary_ambiguity_mass(observed)

    pass_branch = _branch_observations(
        observations=observed,
        candidate_index=(candidate_index),
        verdict=(DecisionVerdict.PASS),
    )

    fail_branch = _branch_observations(
        observations=observed,
        candidate_index=(candidate_index),
        verdict=(DecisionVerdict.FAIL),
    )

    pass_boundary = boundary_ambiguity_mass(pass_branch)

    fail_boundary = boundary_ambiguity_mass(fail_branch)

    worst_boundary = max(
        pass_boundary,
        fail_boundary,
    )

    guaranteed_reduction = max(
        0,
        boundary_before - worst_boundary,
    )

    worst_case_expansion = max(
        0,
        worst_boundary - boundary_before,
    )

    pass_intervals = set(opposing_intervals(pass_branch))

    fail_intervals = set(opposing_intervals(fail_branch))

    outcome_boundary_mass_separation = abs(pass_boundary - fail_boundary)

    outcome_interval_symmetric_difference_count = len(
        pass_intervals.symmetric_difference(fail_intervals)
    )

    return MultiObjectiveCandidateRecord(
        candidate_index=(candidate_index),
        coverage_gain=(coverage_gain),
        guaranteed_boundary_ambiguity_reduction=(guaranteed_reduction),
        worst_case_boundary_ambiguity_expansion=(worst_case_expansion),
        outcome_boundary_mass_separation=(outcome_boundary_mass_separation),
        outcome_interval_symmetric_difference_count=(
            outcome_interval_symmetric_difference_count
        ),
        pass_boundary_ambiguity=(pass_boundary),
        fail_boundary_ambiguity=(fail_boundary),
    )


def structural_candidate_dominates(
    left: MultiObjectiveCandidateRecord,
    right: MultiObjectiveCandidateRecord,
) -> bool:
    weak = (
        left.coverage_gain >= right.coverage_gain
        and left.guaranteed_boundary_ambiguity_reduction
        >= right.guaranteed_boundary_ambiguity_reduction
        and left.worst_case_boundary_ambiguity_expansion
        <= right.worst_case_boundary_ambiguity_expansion
    )

    strict = (
        left.coverage_gain > right.coverage_gain
        or left.guaranteed_boundary_ambiguity_reduction
        > right.guaranteed_boundary_ambiguity_reduction
        or left.worst_case_boundary_ambiguity_expansion
        < right.worst_case_boundary_ambiguity_expansion
    )

    return weak and strict


def information_candidate_dominates(
    left: MultiObjectiveCandidateRecord,
    right: MultiObjectiveCandidateRecord,
) -> bool:
    weak = (
        left.outcome_boundary_mass_separation >= right.outcome_boundary_mass_separation
        and left.outcome_interval_symmetric_difference_count
        >= right.outcome_interval_symmetric_difference_count
    )

    strict = (
        left.outcome_boundary_mass_separation > right.outcome_boundary_mass_separation
        or left.outcome_interval_symmetric_difference_count
        > right.outcome_interval_symmetric_difference_count
    )

    return weak and strict


def _pareto_frontier(
    records: tuple[
        MultiObjectiveCandidateRecord,
        ...,
    ],
    dominates,
) -> tuple[
    MultiObjectiveCandidateRecord,
    ...,
]:
    return tuple(
        record
        for record in records
        if not any(
            dominates(
                other,
                record,
            )
            for other in records
            if (other.candidate_index != record.candidate_index)
        )
    )


def build_behavioral_multi_objective_uncertainty_aware_decision(
    *,
    candidate_count: int,
    observations: Mapping[
        int,
        DecisionVerdict,
    ],
) -> MultiObjectivePlannerDecision:
    candidate_count = _validate_candidate_count(candidate_count)

    observed = _normalize_observations(
        candidate_count=(candidate_count),
        observations=(observations),
    )

    unobserved = tuple(
        index for index in range(candidate_count) if index not in observed
    )

    if not unobserved:
        return MultiObjectivePlannerDecision(
            candidate_count=(candidate_count),
            observed_count=(len(observed)),
            remaining_candidate_count=0,
            selected_candidate_index=None,
            selection_reason=(MultiObjectiveSelectionReason.GRID_EXHAUSTED),
            primary_frontier_candidate_indices=(),
            uncertainty_frontier_candidate_indices=(),
            unresolved_action_ambiguity=False,
            candidate_records=(),
        )

    if not observed:
        selected = candidate_count // 2

        return MultiObjectivePlannerDecision(
            candidate_count=(candidate_count),
            observed_count=0,
            remaining_candidate_count=(candidate_count),
            selected_candidate_index=(selected),
            selection_reason=(
                MultiObjectiveSelectionReason.STRUCTURAL_CENTER_BOOTSTRAP
            ),
            primary_frontier_candidate_indices=(selected,),
            uncertainty_frontier_candidate_indices=(selected,),
            unresolved_action_ambiguity=False,
            candidate_records=(),
        )

    records = tuple(
        build_multi_objective_candidate_record(
            candidate_count=(candidate_count),
            observations=(observed),
            candidate_index=(candidate),
        )
        for candidate in unobserved
    )

    primary = _pareto_frontier(
        records,
        structural_candidate_dominates,
    )

    if not primary:
        raise MultiObjectivePlannerError("structural Pareto frontier must not be empty")

    if len(primary) == 1:
        selected = primary[0].candidate_index

        return MultiObjectivePlannerDecision(
            candidate_count=(candidate_count),
            observed_count=(len(observed)),
            remaining_candidate_count=(len(unobserved)),
            selected_candidate_index=(selected),
            selection_reason=(
                MultiObjectiveSelectionReason.UNIQUE_STRUCTURAL_NONDOMINATED
            ),
            primary_frontier_candidate_indices=(selected,),
            uncertainty_frontier_candidate_indices=(selected,),
            unresolved_action_ambiguity=False,
            candidate_records=records,
        )

    uncertainty = _pareto_frontier(
        primary,
        information_candidate_dominates,
    )

    if not uncertainty:
        raise MultiObjectivePlannerError(
            "uncertainty Pareto frontier must not be empty"
        )

    primary_indices = tuple(record.candidate_index for record in primary)

    uncertainty_indices = tuple(record.candidate_index for record in uncertainty)

    if len(uncertainty) == 1:
        selected = uncertainty[0].candidate_index

        reason = MultiObjectiveSelectionReason.UNIQUE_INFORMATION_NONDOMINATED

        unresolved = False

    else:
        selected = min(uncertainty_indices)

        reason = MultiObjectiveSelectionReason.DETERMINISTIC_REPRODUCIBILITY_TIE_BREAK

        unresolved = True

    return MultiObjectivePlannerDecision(
        candidate_count=(candidate_count),
        observed_count=(len(observed)),
        remaining_candidate_count=(len(unobserved)),
        selected_candidate_index=(selected),
        selection_reason=(reason),
        primary_frontier_candidate_indices=(primary_indices),
        uncertainty_frontier_candidate_indices=(uncertainty_indices),
        unresolved_action_ambiguity=(unresolved),
        candidate_records=records,
    )


__all__ = [
    "PLANNER_KEY",
    "PLANNER_VERSION",
    "MultiObjectiveCandidateRecord",
    "MultiObjectivePlannerDecision",
    "MultiObjectivePlannerError",
    "MultiObjectiveSelectionReason",
    "OpposingInterval",
    "boundary_ambiguity_mass",
    "build_behavioral_multi_objective_uncertainty_aware_decision",
    "build_multi_objective_candidate_record",
    "coverage_distance_mass",
    "information_candidate_dominates",
    "opposing_intervals",
    "structural_candidate_dominates",
]

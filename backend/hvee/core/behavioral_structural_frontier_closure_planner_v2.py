from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum
import hashlib
import json


PLANNER_KEY = "behavioral_structural_frontier_closure_planner_v2"
PLANNER_VERSION = "2.0.0-candidate-family-v1"


class StructuralFrontierPlannerError(ValueError):
    pass


class StructuralPlannerVariant(str, Enum):
    V2A_BALANCED_FRONTIER_CLOSURE = "V2A_BALANCED_FRONTIER_CLOSURE"
    V2B_CLOSURE_WITH_COVERAGE_FLOOR = "V2B_CLOSURE_WITH_COVERAGE_FLOOR"
    V2C_FAILURE_FRONTIER_STRUCTURAL = "V2C_FAILURE_FRONTIER_STRUCTURAL"


class StructuralActionClass(str, Enum):
    GLOBAL_FRONTIER_EXPLORE = "GLOBAL_FRONTIER_EXPLORE"
    BOUNDARY_BRACKET_REFINE = "BOUNDARY_BRACKET_REFINE"
    BOUNDARY_CLOSE = "BOUNDARY_CLOSE"
    FAILURE_FRONTIER_EXPAND = "FAILURE_FRONTIER_EXPAND"
    COMPONENT_CONSOLIDATE = "COMPONENT_CONSOLIDATE"
    COMPLETE = "COMPLETE"


@dataclass(frozen=True, order=True)
class StructuralIndexInterval:
    left_index: int
    right_index: int

    @property
    def length(self) -> int:
        return self.right_index - self.left_index + 1


@dataclass(frozen=True)
class StructuralOpposingBracket:
    left_index: int
    right_index: int
    left_verdict: str
    right_verdict: str

    @property
    def width(self) -> int:
        return self.right_index - self.left_index


@dataclass(frozen=True)
class StructuralActionCandidates:
    global_frontier_indices: tuple[int, ...]
    boundary_close_indices: tuple[int, ...]
    boundary_refine_indices: tuple[int, ...]
    failure_frontier_indices: tuple[int, ...]
    component_consolidate_indices: tuple[int, ...]


@dataclass(frozen=True)
class StructuralFrontierPlannerDecision:
    planner_key: str
    planner_version: str
    variant: StructuralPlannerVariant
    candidate_count: int
    observed_count: int
    remaining_candidate_count: int
    selected_candidate_index: int | None
    action_class: StructuralActionClass
    selection_phase: str
    observed_components: tuple[StructuralIndexInterval, ...]
    unobserved_intervals: tuple[StructuralIndexInterval, ...]
    opposing_brackets: tuple[StructuralOpposingBracket, ...]
    action_candidates: StructuralActionCandidates


def _jsonable(value: object) -> object:
    if isinstance(value, Enum):
        return value.value

    if is_dataclass(value) and not isinstance(value, type):
        return _jsonable(asdict(value))

    if isinstance(value, dict):
        return {
            str(key): _jsonable(item)
            for key, item in sorted(
                value.items(),
                key=lambda pair: str(pair[0]),
            )
        }

    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]

    if isinstance(value, list):
        return [_jsonable(item) for item in value]

    return value


def calculate_behavioral_structural_frontier_closure_decision_sha256(
    decision: StructuralFrontierPlannerDecision,
) -> str:
    payload = _jsonable(decision)

    data = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")

    return hashlib.sha256(data).hexdigest()


def _normalize_verdict(value: object) -> str:
    token: object = value

    if not isinstance(token, str):
        token = getattr(
            value,
            "value",
            None,
        )

    if not isinstance(token, str):
        raise StructuralFrontierPlannerError(
            "verdict must be pass/fail text or expose a string .value"
        )

    normalized = token.strip().lower()

    aliases = {
        "p": "pass",
        "pass": "pass",
        "f": "fail",
        "fail": "fail",
    }

    if normalized not in aliases:
        raise StructuralFrontierPlannerError("verdict must normalize to pass or fail")

    return aliases[normalized]


def _normalize_observations(
    *,
    candidate_count: int,
    observations: Mapping[int, object],
) -> dict[int, str]:
    if (
        isinstance(candidate_count, bool)
        or not isinstance(candidate_count, int)
        or candidate_count <= 0
    ):
        raise StructuralFrontierPlannerError(
            "candidate_count must be a positive integer"
        )

    if not isinstance(observations, Mapping):
        raise StructuralFrontierPlannerError("observations must be a mapping")

    normalized: dict[int, str] = {}

    for index, verdict in observations.items():
        if isinstance(index, bool) or not isinstance(index, int):
            raise StructuralFrontierPlannerError("observation index must be an integer")

        if not 0 <= index < candidate_count:
            raise StructuralFrontierPlannerError("observation index out of range")

        normalized[index] = _normalize_verdict(verdict)

    if len(normalized) > candidate_count:
        raise StructuralFrontierPlannerError(
            "observation count exceeds candidate count"
        )

    return dict(sorted(normalized.items()))


def _components_from_indices(
    indices: set[int] | frozenset[int],
) -> tuple[StructuralIndexInterval, ...]:
    if not indices:
        return ()

    ordered = sorted(indices)

    components: list[StructuralIndexInterval] = []

    left = ordered[0]
    right = ordered[0]

    for index in ordered[1:]:
        if index == right + 1:
            right = index
            continue

        components.append(
            StructuralIndexInterval(
                left_index=left,
                right_index=right,
            )
        )

        left = index
        right = index

    components.append(
        StructuralIndexInterval(
            left_index=left,
            right_index=right,
        )
    )

    return tuple(components)


def observed_components(
    *,
    observations: Mapping[int, object],
) -> tuple[StructuralIndexInterval, ...]:
    return _components_from_indices(set(observations))


def unobserved_intervals(
    *,
    candidate_count: int,
    observations: Mapping[int, object],
) -> tuple[StructuralIndexInterval, ...]:
    normalized = _normalize_observations(
        candidate_count=candidate_count,
        observations=observations,
    )

    unobserved = {index for index in range(candidate_count) if index not in normalized}

    return _components_from_indices(unobserved)


def opposing_brackets(
    *,
    candidate_count: int,
    observations: Mapping[int, object],
) -> tuple[StructuralOpposingBracket, ...]:
    normalized = _normalize_observations(
        candidate_count=candidate_count,
        observations=observations,
    )

    ordered = tuple(normalized.items())

    brackets: list[StructuralOpposingBracket] = []

    for (
        left_index,
        left_verdict,
    ), (
        right_index,
        right_verdict,
    ) in zip(
        ordered,
        ordered[1:],
    ):
        if left_verdict == right_verdict:
            continue

        brackets.append(
            StructuralOpposingBracket(
                left_index=left_index,
                right_index=right_index,
                left_verdict=left_verdict,
                right_verdict=right_verdict,
            )
        )

    return tuple(brackets)


def _midpoint(
    interval: StructuralIndexInterval,
) -> int:
    return (interval.left_index + interval.right_index) // 2


def _containing_interval_length(
    *,
    candidate_index: int,
    intervals: tuple[StructuralIndexInterval, ...],
) -> int:
    for interval in intervals:
        if interval.left_index <= candidate_index <= interval.right_index:
            return interval.length

    raise StructuralFrontierPlannerError(
        "candidate is not inside an unobserved interval"
    )


def _global_frontier_candidates(
    intervals: tuple[StructuralIndexInterval, ...],
) -> tuple[int, ...]:
    ranked = sorted(
        intervals,
        key=lambda interval: (
            -interval.length,
            interval.left_index,
            interval.right_index,
        ),
    )

    return tuple(_midpoint(interval) for interval in ranked)


def _boundary_candidates(
    brackets: tuple[StructuralOpposingBracket, ...],
) -> tuple[
    tuple[int, ...],
    tuple[int, ...],
]:
    close_candidates: list[tuple[int, int, int]] = []

    refine_candidates: list[tuple[int, int, int]] = []

    for bracket in brackets:
        if bracket.width <= 1:
            continue

        candidate = (bracket.left_index + bracket.right_index) // 2

        if bracket.width == 2:
            close_candidates.append(
                (
                    bracket.width,
                    bracket.left_index,
                    candidate,
                )
            )

        else:
            refine_candidates.append(
                (
                    bracket.width,
                    bracket.left_index,
                    candidate,
                )
            )

    close_candidates.sort(
        key=lambda value: (
            value[0],
            value[1],
            value[2],
        )
    )

    refine_candidates.sort(
        key=lambda value: (
            value[0],
            value[1],
            value[2],
        )
    )

    return (
        tuple(value[2] for value in close_candidates),
        tuple(value[2] for value in refine_candidates),
    )


def _failure_frontier_candidates(
    *,
    candidate_count: int,
    observations: Mapping[int, str],
    intervals: tuple[StructuralIndexInterval, ...],
) -> tuple[int, ...]:
    candidates: set[int] = set()

    for index, verdict in observations.items():
        if verdict != "fail":
            continue

        for candidate in (
            index - 1,
            index + 1,
        ):
            if 0 <= candidate < candidate_count and candidate not in observations:
                candidates.add(candidate)

    ranked = sorted(
        candidates,
        key=lambda candidate: (
            -_containing_interval_length(
                candidate_index=candidate,
                intervals=intervals,
            ),
            candidate,
        ),
    )

    return tuple(ranked)


def _component_consolidate_candidates(
    *,
    candidate_count: int,
    observations: Mapping[int, str],
    intervals: tuple[StructuralIndexInterval, ...],
) -> tuple[int, ...]:
    candidates: list[tuple[int, int, int]] = []

    for interval in intervals:
        if interval.left_index == 0:
            continue

        if interval.right_index == candidate_count - 1:
            continue

        if (
            interval.left_index - 1 not in observations
            or interval.right_index + 1 not in observations
        ):
            continue

        candidate = _midpoint(interval)

        candidates.append(
            (
                interval.length,
                interval.left_index,
                candidate,
            )
        )

    candidates.sort(
        key=lambda value: (
            value[0],
            value[1],
            value[2],
        )
    )

    return tuple(value[2] for value in candidates)


def _build_action_candidates(
    *,
    candidate_count: int,
    observations: Mapping[int, str],
    intervals: tuple[StructuralIndexInterval, ...],
    brackets: tuple[StructuralOpposingBracket, ...],
) -> StructuralActionCandidates:
    (
        boundary_close,
        boundary_refine,
    ) = _boundary_candidates(brackets)

    return StructuralActionCandidates(
        global_frontier_indices=(_global_frontier_candidates(intervals)),
        boundary_close_indices=(boundary_close),
        boundary_refine_indices=(boundary_refine),
        failure_frontier_indices=(
            _failure_frontier_candidates(
                candidate_count=candidate_count,
                observations=observations,
                intervals=intervals,
            )
        ),
        component_consolidate_indices=(
            _component_consolidate_candidates(
                candidate_count=candidate_count,
                observations=observations,
                intervals=intervals,
            )
        ),
    )


def _first(
    values: tuple[int, ...],
) -> int | None:
    if not values:
        return None

    return values[0]


def _select_from_priority(
    *,
    candidates: StructuralActionCandidates,
    priority: tuple[StructuralActionClass, ...],
) -> tuple[
    int,
    StructuralActionClass,
]:
    mapping = {
        StructuralActionClass.GLOBAL_FRONTIER_EXPLORE: (
            candidates.global_frontier_indices
        ),
        StructuralActionClass.BOUNDARY_BRACKET_REFINE: (
            candidates.boundary_refine_indices
        ),
        StructuralActionClass.BOUNDARY_CLOSE: (candidates.boundary_close_indices),
        StructuralActionClass.FAILURE_FRONTIER_EXPAND: (
            candidates.failure_frontier_indices
        ),
        StructuralActionClass.COMPONENT_CONSOLIDATE: (
            candidates.component_consolidate_indices
        ),
    }

    for action in priority:
        selected = _first(mapping[action])

        if selected is not None:
            return (
                selected,
                action,
            )

    raise StructuralFrontierPlannerError(
        "remaining candidates exist but scheduler produced no action"
    )


def _priority_for_variant(
    *,
    variant: StructuralPlannerVariant,
    observed_count: int,
    has_boundary_close: bool,
) -> tuple[
    str,
    tuple[StructuralActionClass, ...],
]:
    if has_boundary_close:
        return (
            "HARD_BOUNDARY_CLOSE",
            (
                StructuralActionClass.BOUNDARY_CLOSE,
                StructuralActionClass.BOUNDARY_BRACKET_REFINE,
                StructuralActionClass.COMPONENT_CONSOLIDATE,
                StructuralActionClass.GLOBAL_FRONTIER_EXPLORE,
                StructuralActionClass.FAILURE_FRONTIER_EXPAND,
            ),
        )

    if variant == StructuralPlannerVariant.V2A_BALANCED_FRONTIER_CLOSURE:
        if observed_count % 2 == 0:
            return (
                "BALANCED_LOCAL_PHASE",
                (
                    StructuralActionClass.BOUNDARY_BRACKET_REFINE,
                    StructuralActionClass.COMPONENT_CONSOLIDATE,
                    StructuralActionClass.GLOBAL_FRONTIER_EXPLORE,
                ),
            )

        return (
            "BALANCED_GLOBAL_PHASE",
            (
                StructuralActionClass.GLOBAL_FRONTIER_EXPLORE,
                StructuralActionClass.BOUNDARY_BRACKET_REFINE,
                StructuralActionClass.COMPONENT_CONSOLIDATE,
            ),
        )

    if variant == StructuralPlannerVariant.V2B_CLOSURE_WITH_COVERAGE_FLOOR:
        if observed_count % 3 == 0:
            return (
                "COVERAGE_FLOOR_PHASE",
                (
                    StructuralActionClass.GLOBAL_FRONTIER_EXPLORE,
                    StructuralActionClass.BOUNDARY_BRACKET_REFINE,
                    StructuralActionClass.COMPONENT_CONSOLIDATE,
                ),
            )

        return (
            "CLOSURE_PRIORITY_PHASE",
            (
                StructuralActionClass.BOUNDARY_BRACKET_REFINE,
                StructuralActionClass.COMPONENT_CONSOLIDATE,
                StructuralActionClass.GLOBAL_FRONTIER_EXPLORE,
            ),
        )

    phase = observed_count % 3

    if phase == 0:
        return (
            "FAILURE_FRONTIER_PHASE",
            (
                StructuralActionClass.FAILURE_FRONTIER_EXPAND,
                StructuralActionClass.BOUNDARY_BRACKET_REFINE,
                StructuralActionClass.COMPONENT_CONSOLIDATE,
                StructuralActionClass.GLOBAL_FRONTIER_EXPLORE,
            ),
        )

    if phase == 1:
        return (
            "STRUCTURAL_CLOSURE_PHASE",
            (
                StructuralActionClass.BOUNDARY_BRACKET_REFINE,
                StructuralActionClass.FAILURE_FRONTIER_EXPAND,
                StructuralActionClass.COMPONENT_CONSOLIDATE,
                StructuralActionClass.GLOBAL_FRONTIER_EXPLORE,
            ),
        )

    return (
        "STRUCTURAL_GLOBAL_PHASE",
        (
            StructuralActionClass.GLOBAL_FRONTIER_EXPLORE,
            StructuralActionClass.FAILURE_FRONTIER_EXPAND,
            StructuralActionClass.BOUNDARY_BRACKET_REFINE,
            StructuralActionClass.COMPONENT_CONSOLIDATE,
        ),
    )


def build_behavioral_structural_frontier_closure_decision(
    *,
    candidate_count: int,
    observations: Mapping[int, object],
    variant: StructuralPlannerVariant,
) -> StructuralFrontierPlannerDecision:
    if not isinstance(
        variant,
        StructuralPlannerVariant,
    ):
        raise StructuralFrontierPlannerError(
            "variant must be a StructuralPlannerVariant"
        )

    normalized = _normalize_observations(
        candidate_count=candidate_count,
        observations=observations,
    )

    observed_count = len(normalized)

    remaining = candidate_count - observed_count

    components = observed_components(observations=normalized)

    intervals = unobserved_intervals(
        candidate_count=candidate_count,
        observations=normalized,
    )

    brackets = opposing_brackets(
        candidate_count=candidate_count,
        observations=normalized,
    )

    action_candidates = _build_action_candidates(
        candidate_count=candidate_count,
        observations=normalized,
        intervals=intervals,
        brackets=brackets,
    )

    if remaining == 0:
        return StructuralFrontierPlannerDecision(
            planner_key=PLANNER_KEY,
            planner_version=PLANNER_VERSION,
            variant=variant,
            candidate_count=candidate_count,
            observed_count=observed_count,
            remaining_candidate_count=0,
            selected_candidate_index=None,
            action_class=(StructuralActionClass.COMPLETE),
            selection_phase="COMPLETE",
            observed_components=components,
            unobserved_intervals=intervals,
            opposing_brackets=brackets,
            action_candidates=action_candidates,
        )

    (
        phase,
        priority,
    ) = _priority_for_variant(
        variant=variant,
        observed_count=observed_count,
        has_boundary_close=bool(action_candidates.boundary_close_indices),
    )

    (
        selected,
        action_class,
    ) = _select_from_priority(
        candidates=action_candidates,
        priority=priority,
    )

    if selected in normalized:
        raise StructuralFrontierPlannerError("scheduler selected an observed candidate")

    if not 0 <= selected < candidate_count:
        raise StructuralFrontierPlannerError(
            "scheduler selected an out-of-range candidate"
        )

    return StructuralFrontierPlannerDecision(
        planner_key=PLANNER_KEY,
        planner_version=PLANNER_VERSION,
        variant=variant,
        candidate_count=candidate_count,
        observed_count=observed_count,
        remaining_candidate_count=remaining,
        selected_candidate_index=selected,
        action_class=action_class,
        selection_phase=phase,
        observed_components=components,
        unobserved_intervals=intervals,
        opposing_brackets=brackets,
        action_candidates=action_candidates,
    )


__all__ = [
    "PLANNER_KEY",
    "PLANNER_VERSION",
    "StructuralActionCandidates",
    "StructuralActionClass",
    "StructuralFrontierPlannerDecision",
    "StructuralFrontierPlannerError",
    "StructuralIndexInterval",
    "StructuralOpposingBracket",
    "StructuralPlannerVariant",
    "build_behavioral_structural_frontier_closure_decision",
    "calculate_behavioral_structural_frontier_closure_decision_sha256",
    "observed_components",
    "opposing_brackets",
    "unobserved_intervals",
]

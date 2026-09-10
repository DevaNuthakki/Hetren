from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
import hashlib
import math
import random

from hvee.core.adaptive_scenario_search import (
    AdaptiveScenarioObservation,
    build_adaptive_scenario_search_bundle,
)
from hvee.core.contracts import HveeContractError
from hvee.core.decision import DecisionVerdict
from hvee.core.failure_family_investigator import (
    FailureFamilyObservation,
    FailureFamilyObservationSource,
    FailureFamilySearchMode,
    build_failure_family_investigator_bundle,
)
from hvee.core.neighborhood_generation import (
    NeighborhoodCandidate,
    NeighborhoodMutationDirection,
    NeighborhoodObservation,
    build_neighborhood_generation_bundle,
)
from hvee.core.run05_non_monotonic_qualification_design import (
    GLOBAL_BUDGETS,
    INCIDENT_ADDITIONAL_BUDGETS,
    RANDOM_BASELINE_SEEDS,
    build_run05_non_monotonic_qualification_design_bundle,
)


RUN05_NON_MONOTONIC_BENCHMARK_SCHEMA_VERSION = 1

Oracle = Callable[[int], DecisionVerdict]


class Run05GlobalStrategy(str, Enum):
    HETREN_GENERALIZED = "hetren_generalized"
    SEQUENTIAL_GRID = "sequential_grid"
    SEEDED_RANDOM = "seeded_random"
    FARTHEST_GAP_COVERAGE = "farthest_gap_coverage"
    CURRENT_ADAPTIVE_V1 = "current_adaptive_v1"


class Run05IncidentStrategy(str, Enum):
    HETREN_GENERALIZED = "hetren_generalized"
    SYMMETRIC_LINEAR_EXPANSION = "symmetric_linear_expansion"
    BIDIRECTIONAL_EXPONENTIAL_BISECTION = "bidirectional_exponential_bisection"
    EXISTING_NEIGHBORHOOD_ORDERED = "existing_neighborhood_ordered"


class Run05DevelopmentVerdict(str, Enum):
    SUPERIOR = "superior"
    TIE = "tie"
    MIXED = "mixed"
    INFERIOR = "inferior"


@dataclass(frozen=True)
class Run05StrategyTrace:
    task: str
    strategy: str
    candidate_count: int
    maximum_evaluations: int
    observations: tuple[
        tuple[int, str],
        ...,
    ]
    terminal_status: str
    seed: int | None = None
    incident_index: int | None = None

    @property
    def evaluation_count(self) -> int:
        return len(self.observations)


def _sha(
    *parts: object,
) -> str:
    return hashlib.sha256(
        "|".join(str(part) for part in parts).encode("utf-8")
    ).hexdigest()


def _candidate_count(
    value: object,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value not in GLOBAL_BUDGETS
    ):
        raise HveeContractError(
            "Run-05 candidate count must use " "a frozen benchmark grid"
        )

    return value


def _global_budget(
    *,
    candidate_count: int,
    budget: object,
) -> int:
    if (
        isinstance(budget, bool)
        or not isinstance(budget, int)
        or budget not in GLOBAL_BUDGETS[candidate_count]
    ):
        raise HveeContractError(
            "global budget must be one of " "the frozen Run-05 budgets"
        )

    return budget


def _incident_budget(
    *,
    candidate_count: int,
    budget: object,
) -> int:
    if (
        isinstance(budget, bool)
        or not isinstance(budget, int)
        or budget not in INCIDENT_ADDITIONAL_BUDGETS[candidate_count]
    ):
        raise HveeContractError(
            "incident budget must be one of " "the frozen Run-05 budgets"
        )

    return budget


def _verdict(
    value: object,
) -> DecisionVerdict:
    if value not in {
        DecisionVerdict.PASS,
        DecisionVerdict.FAIL,
    }:
        raise HveeContractError("Run-05 oracle must return PASS or FAIL")

    return value


def _trace_payload(
    observations: list[
        tuple[
            int,
            DecisionVerdict,
        ]
    ],
) -> tuple[
    tuple[int, str],
    ...,
]:
    return tuple(
        (
            index,
            verdict.value,
        )
        for index, verdict in observations
    )


def _farthest_unobserved(
    *,
    candidate_count: int,
    observed: set[int],
) -> int | None:
    unobserved = [index for index in range(candidate_count) if index not in observed]

    if not unobserved:
        return None

    if not observed:
        return candidate_count // 2

    ranked = []

    for index in unobserved:
        distance = min(abs(index - prior) for prior in observed)

        ranked.append(
            (
                -distance,
                index,
            )
        )

    return min(ranked)[1]


def _failure_observation(
    *,
    sequence: int,
    candidate_index: int,
    verdict: DecisionVerdict,
    source: FailureFamilyObservationSource,
) -> FailureFamilyObservation:
    return FailureFamilyObservation(
        sequence=sequence,
        candidate_index=(candidate_index),
        verdict=verdict,
        source=source,
        cost_units=(
            0 if source == FailureFamilyObservationSource.INCIDENT_ANCHOR else 1
        ),
        scenario_sha256=_sha(
            "run05",
            "failure-family",
            "scenario",
            source.value,
            sequence,
            candidate_index,
        ),
        result_provenance_sha256=_sha(
            "run05",
            "failure-family",
            "result",
            source.value,
            sequence,
            candidate_index,
        ),
        observation_evidence_sha256=_sha(
            "run05",
            "failure-family",
            "observation",
            source.value,
            sequence,
            candidate_index,
        ),
        decision_evidence_sha256=_sha(
            "run05",
            "failure-family",
            "decision",
            source.value,
            sequence,
            candidate_index,
        ),
        counterexample_evidence_sha256=(
            _sha(
                "run05",
                "failure-family",
                "counterexample",
                source.value,
                sequence,
                candidate_index,
            )
            if verdict == DecisionVerdict.FAIL
            else None
        ),
    )


def _adaptive_observation(
    *,
    sequence: int,
    candidate_index: int,
    verdict: DecisionVerdict,
) -> AdaptiveScenarioObservation:
    return AdaptiveScenarioObservation(
        sequence=sequence,
        candidate_index=(candidate_index),
        scenario_sha256=_sha(
            "run05",
            "adaptive",
            "scenario",
            sequence,
            candidate_index,
        ),
        verdict=verdict,
        result_provenance_sha256=_sha(
            "run05",
            "adaptive",
            "result",
            sequence,
            candidate_index,
        ),
        observation_evidence_sha256=_sha(
            "run05",
            "adaptive",
            "observation",
            sequence,
            candidate_index,
        ),
        decision_evidence_sha256=_sha(
            "run05",
            "adaptive",
            "decision",
            sequence,
            candidate_index,
        ),
        counterexample_evidence_sha256=(
            _sha(
                "run05",
                "adaptive",
                "counterexample",
                sequence,
                candidate_index,
            )
            if verdict == DecisionVerdict.FAIL
            else None
        ),
    )


def run_run05_global_strategy(
    *,
    strategy: Run05GlobalStrategy,
    candidate_count: int,
    maximum_evaluations: int,
    oracle: Oracle,
    seed: int | None = None,
) -> Run05StrategyTrace:
    candidate_count = _candidate_count(candidate_count)

    maximum_evaluations = _global_budget(
        candidate_count=(candidate_count),
        budget=(maximum_evaluations),
    )

    if not isinstance(
        strategy,
        Run05GlobalStrategy,
    ):
        raise HveeContractError("invalid Run-05 global strategy")

    if strategy == Run05GlobalStrategy.SEEDED_RANDOM:
        if (
            isinstance(seed, bool)
            or not isinstance(seed, int)
            or seed not in RANDOM_BASELINE_SEEDS
        ):
            raise HveeContractError("seeded random requires " "a frozen Run-05 seed")

    elif seed is not None:
        raise HveeContractError("non-random strategy cannot " "receive random seed")

    if strategy == Run05GlobalStrategy.SEQUENTIAL_GRID:
        observations = []

        for index in range(maximum_evaluations):
            observations.append(
                (
                    index,
                    _verdict(oracle(index)),
                )
            )

        return Run05StrategyTrace(
            task="global",
            strategy=(strategy.value),
            candidate_count=(candidate_count),
            maximum_evaluations=(maximum_evaluations),
            observations=(_trace_payload(observations)),
            terminal_status=(
                "grid_exhausted"
                if maximum_evaluations == candidate_count
                else "budget_exhausted"
            ),
        )

    if strategy == Run05GlobalStrategy.SEEDED_RANDOM:
        order = list(range(candidate_count))

        random.Random(seed).shuffle(order)

        observations = []

        for index in order[:maximum_evaluations]:
            observations.append(
                (
                    index,
                    _verdict(oracle(index)),
                )
            )

        return Run05StrategyTrace(
            task="global",
            strategy=(strategy.value),
            candidate_count=(candidate_count),
            maximum_evaluations=(maximum_evaluations),
            observations=(_trace_payload(observations)),
            terminal_status=(
                "grid_exhausted"
                if maximum_evaluations == candidate_count
                else "budget_exhausted"
            ),
            seed=seed,
        )

    if strategy == Run05GlobalStrategy.FARTHEST_GAP_COVERAGE:
        observations = []
        observed: set[int] = set()

        while len(observations) < maximum_evaluations:
            index = _farthest_unobserved(
                candidate_count=(candidate_count),
                observed=observed,
            )

            if index is None:
                break

            verdict = _verdict(oracle(index))

            observations.append(
                (
                    index,
                    verdict,
                )
            )

            observed.add(index)

        return Run05StrategyTrace(
            task="global",
            strategy=(strategy.value),
            candidate_count=(candidate_count),
            maximum_evaluations=(maximum_evaluations),
            observations=(_trace_payload(observations)),
            terminal_status=(
                "grid_exhausted"
                if len(observations) == candidate_count
                else "budget_exhausted"
            ),
        )

    if strategy == Run05GlobalStrategy.CURRENT_ADAPTIVE_V1:
        native: list[AdaptiveScenarioObservation] = []

        observations = []

        while True:
            bundle = build_adaptive_scenario_search_bundle(
                evaluation_type="synthetic",
                search_key=("hetren.run05.current.adaptive"),
                search_version="1.0.0",
                boundary_key=("hetren.run05.current.adaptive.boundary"),
                boundary_version="1.0.0",
                axis_key="synthetic.index",
                axis_version="1.0.0",
                axis_unit="index",
                candidate_values=tuple(
                    float(index) for index in range(candidate_count)
                ),
                invariant_parameters={
                    "benchmark": ("run05_non_monotonic"),
                },
                maximum_observations=(maximum_evaluations),
                observations=tuple(native),
            )

            proposal = bundle.payload["outcome"]["next_proposal"]

            if proposal is None:
                return Run05StrategyTrace(
                    task="global",
                    strategy=(strategy.value),
                    candidate_count=(candidate_count),
                    maximum_evaluations=(maximum_evaluations),
                    observations=(_trace_payload(observations)),
                    terminal_status=(bundle.payload["search"]["status"]),
                )

            index = proposal["candidate_index"]

            verdict = _verdict(oracle(index))

            sequence = len(native) + 1

            native.append(
                _adaptive_observation(
                    sequence=sequence,
                    candidate_index=(index),
                    verdict=verdict,
                )
            )

            observations.append(
                (
                    index,
                    verdict,
                )
            )

    if strategy == Run05GlobalStrategy.HETREN_GENERALIZED:
        native: list[FailureFamilyObservation] = []

        observations = []

        while True:
            bundle = build_failure_family_investigator_bundle(
                mode=(FailureFamilySearchMode.GLOBAL),
                evaluation_type="synthetic",
                investigator_key=("hetren.run05.generalized.global"),
                investigator_version="1.0.0",
                boundary_key=("hetren.run05.generalized.boundary"),
                boundary_version="1.0.0",
                axis_key="synthetic.index",
                axis_version="1.0.0",
                axis_unit="index",
                candidate_values=tuple(
                    float(index) for index in range(candidate_count)
                ),
                invariant_parameters={
                    "benchmark": ("run05_non_monotonic"),
                },
                maximum_evaluations=(maximum_evaluations),
                observations=tuple(native),
            )

            proposal = bundle.payload["outcome"]["next_proposal"]

            if proposal is None:
                return Run05StrategyTrace(
                    task="global",
                    strategy=(strategy.value),
                    candidate_count=(candidate_count),
                    maximum_evaluations=(maximum_evaluations),
                    observations=(_trace_payload(observations)),
                    terminal_status=(bundle.payload["investigator"]["status"]),
                )

            index = proposal["candidate_index"]

            verdict = _verdict(oracle(index))

            sequence = len(native) + 1

            native.append(
                _failure_observation(
                    sequence=sequence,
                    candidate_index=(index),
                    verdict=verdict,
                    source=(FailureFamilyObservationSource.EVALUATION),
                )
            )

            observations.append(
                (
                    index,
                    verdict,
                )
            )

    raise HveeContractError("unsupported Run-05 global strategy")


def _symmetric_order(
    *,
    candidate_count: int,
    incident_index: int,
) -> tuple[int, ...]:
    order = []

    for distance in range(
        1,
        candidate_count,
    ):
        lower = incident_index - distance

        upper = incident_index + distance

        if lower >= 0:
            order.append(lower)

        if upper < candidate_count:
            order.append(upper)

    return tuple(order)


def _side_index(
    *,
    incident_index: int,
    side: str,
    distance: int,
) -> int:
    if side == "left":
        return incident_index - distance

    if side == "right":
        return incident_index + distance

    raise HveeContractError("invalid incident side")


def _side_max_distance(
    *,
    candidate_count: int,
    incident_index: int,
    side: str,
) -> int:
    if side == "left":
        return incident_index

    if side == "right":
        return candidate_count - 1 - incident_index

    raise HveeContractError("invalid incident side")


def _side_observations_by_distance(
    *,
    candidate_count: int,
    incident_index: int,
    side: str,
    observed: dict[
        int,
        DecisionVerdict,
    ],
) -> dict[
    int,
    DecisionVerdict,
]:
    maximum_distance = _side_max_distance(
        candidate_count=(candidate_count),
        incident_index=(incident_index),
        side=side,
    )

    result = {}

    for distance in range(
        1,
        maximum_distance + 1,
    ):
        index = _side_index(
            incident_index=(incident_index),
            side=side,
            distance=distance,
        )

        if index in observed:
            result[distance] = observed[index]

    return result


def _side_complete(
    *,
    candidate_count: int,
    incident_index: int,
    side: str,
    observed: dict[
        int,
        DecisionVerdict,
    ],
) -> bool:
    maximum_distance = _side_max_distance(
        candidate_count=(candidate_count),
        incident_index=(incident_index),
        side=side,
    )

    if maximum_distance == 0:
        return True

    by_distance = _side_observations_by_distance(
        candidate_count=(candidate_count),
        incident_index=(incident_index),
        side=side,
        observed=observed,
    )

    passing_distances = sorted(
        distance
        for distance, verdict in by_distance.items()
        if verdict == DecisionVerdict.PASS
    )

    if passing_distances:
        nearest_pass = passing_distances[0]

        return all(
            by_distance.get(distance) == DecisionVerdict.FAIL
            for distance in range(
                1,
                nearest_pass,
            )
        )

    return all(
        by_distance.get(distance) == DecisionVerdict.FAIL
        for distance in range(
            1,
            maximum_distance + 1,
        )
    )


def _next_exponential_side_candidate(
    *,
    candidate_count: int,
    incident_index: int,
    side: str,
    observed: dict[
        int,
        DecisionVerdict,
    ],
) -> int | None:
    if _side_complete(
        candidate_count=(candidate_count),
        incident_index=(incident_index),
        side=side,
        observed=observed,
    ):
        return None

    maximum_distance = _side_max_distance(
        candidate_count=(candidate_count),
        incident_index=(incident_index),
        side=side,
    )

    by_distance = _side_observations_by_distance(
        candidate_count=(candidate_count),
        incident_index=(incident_index),
        side=side,
        observed=observed,
    )

    passing_distances = sorted(
        distance
        for distance, verdict in by_distance.items()
        if verdict == DecisionVerdict.PASS
    )

    if passing_distances:
        nearest_pass = passing_distances[0]

        known_fail_distances = [
            0,
            *[
                distance
                for distance, verdict in by_distance.items()
                if (distance < nearest_pass and verdict == DecisionVerdict.FAIL)
            ],
        ]

        nearest_fail = max(known_fail_distances)

        if nearest_pass - nearest_fail > 1:
            distance = (nearest_fail + nearest_pass) // 2

            index = _side_index(
                incident_index=(incident_index),
                side=side,
                distance=distance,
            )

            if index not in observed:
                return index

        for distance in range(
            1,
            nearest_pass,
        ):
            index = _side_index(
                incident_index=(incident_index),
                side=side,
                distance=distance,
            )

            if index not in observed:
                return index

        return None

    if not by_distance:
        return _side_index(
            incident_index=(incident_index),
            side=side,
            distance=1,
        )

    farthest_observed = max(by_distance)

    exponential_distance = min(
        maximum_distance,
        max(
            1,
            farthest_observed * 2,
        ),
    )

    exponential_index = _side_index(
        incident_index=(incident_index),
        side=side,
        distance=(exponential_distance),
    )

    if exponential_index not in observed:
        return exponential_index

    for distance in range(
        1,
        maximum_distance + 1,
    ):
        index = _side_index(
            incident_index=(incident_index),
            side=side,
            distance=distance,
        )

        if index not in observed:
            return index

    return None


def _run_exponential_incident(
    *,
    candidate_count: int,
    incident_index: int,
    maximum_evaluations: int,
    oracle: Oracle,
) -> Run05StrategyTrace:
    observed: dict[
        int,
        DecisionVerdict,
    ] = {incident_index: (DecisionVerdict.FAIL)}

    observations = []
    next_side = "left"

    while len(observations) < maximum_evaluations:
        left_candidate = _next_exponential_side_candidate(
            candidate_count=(candidate_count),
            incident_index=(incident_index),
            side="left",
            observed=observed,
        )

        right_candidate = _next_exponential_side_candidate(
            candidate_count=(candidate_count),
            incident_index=(incident_index),
            side="right",
            observed=observed,
        )

        if left_candidate is None and right_candidate is None:
            break

        choices = (
            (
                "left",
                left_candidate,
            ),
            (
                "right",
                right_candidate,
            ),
        )

        if next_side == "right":
            choices = (
                choices[1],
                choices[0],
            )

        selected_side = None
        selected_index = None

        for side, index in choices:
            if index is not None:
                selected_side = side
                selected_index = index
                break

        if selected_side is None or selected_index is None:
            raise HveeContractError(
                "exponential incident planner " "could not make progress"
            )

        if selected_index in observed:
            raise HveeContractError(
                "exponential incident planner " "proposed duplicate evaluation"
            )

        verdict = _verdict(oracle(selected_index))

        observed[selected_index] = verdict

        observations.append(
            (
                selected_index,
                verdict,
            )
        )

        next_side = "right" if selected_side == "left" else "left"

    complete = _side_complete(
        candidate_count=(candidate_count),
        incident_index=(incident_index),
        side="left",
        observed=observed,
    ) and _side_complete(
        candidate_count=(candidate_count),
        incident_index=(incident_index),
        side="right",
        observed=observed,
    )

    return Run05StrategyTrace(
        task="incident",
        strategy=(Run05IncidentStrategy.BIDIRECTIONAL_EXPONENTIAL_BISECTION.value),
        candidate_count=(candidate_count),
        maximum_evaluations=(maximum_evaluations),
        observations=(_trace_payload(observations)),
        terminal_status=(
            "incident_region_characterized" if complete else "budget_exhausted"
        ),
        incident_index=(incident_index),
    )


def _run_existing_neighborhood(
    *,
    candidate_count: int,
    incident_index: int,
    maximum_evaluations: int,
    oracle: Oracle,
) -> Run05StrategyTrace:
    grid_order = _symmetric_order(
        candidate_count=(candidate_count),
        incident_index=(incident_index),
    )

    candidates = []

    for ordinal, grid_index in enumerate(
        grid_order,
        start=1,
    ):
        direction = (
            NeighborhoodMutationDirection.LOWER
            if grid_index < incident_index
            else NeighborhoodMutationDirection.UPPER
        )

        candidates.append(
            NeighborhoodCandidate(
                key=(f"run05_candidate_{ordinal:03d}"),
                version="1.0.0",
                dimension_key="synthetic_axis",
                generator_key=("run05_incident_symmetric_order"),
                generator_version="1.0.0",
                direction=direction,
                ordinal_distance=(abs(grid_index - incident_index)),
                specification_sha256=_sha(
                    "run05",
                    "neighborhood",
                    "candidate",
                    ordinal,
                    grid_index,
                ),
            )
        )

    native: list[NeighborhoodObservation] = []

    observations = []

    while True:
        bundle = build_neighborhood_generation_bundle(
            evaluation_type="synthetic",
            neighborhood_key=("hetren.run05.existing.neighborhood"),
            neighborhood_version="1.0.0",
            source_scenario_sha256=_sha(
                "run05",
                "incident",
                "source-scenario",
                incident_index,
            ),
            source_counterexample_evidence_sha256=_sha(
                "run05",
                "incident",
                "source-counterexample",
                incident_index,
            ),
            source_minimal_reduction_sha256=_sha(
                "run05",
                "incident",
                "source-reduction",
                incident_index,
            ),
            candidates=tuple(candidates),
            maximum_observations=(maximum_evaluations),
            observations=tuple(native),
        )

        proposal = bundle.payload["outcome"]["next_proposal"]

        if proposal is None:
            return Run05StrategyTrace(
                task="incident",
                strategy=(Run05IncidentStrategy.EXISTING_NEIGHBORHOOD_ORDERED.value),
                candidate_count=(candidate_count),
                maximum_evaluations=(maximum_evaluations),
                observations=(_trace_payload(observations)),
                terminal_status=(bundle.payload["neighborhood"]["status"]),
                incident_index=(incident_index),
            )

        candidate_ordinal = proposal["candidate"]["index"]

        if (
            isinstance(
                candidate_ordinal,
                bool,
            )
            or not isinstance(
                candidate_ordinal,
                int,
            )
            or candidate_ordinal < 0
            or candidate_ordinal >= len(grid_order)
        ):
            raise HveeContractError(
                "Neighborhood proposal returned " "invalid candidate index"
            )

        grid_index = grid_order[candidate_ordinal]

        verdict = _verdict(oracle(grid_index))

        sequence = len(native) + 1

        native.append(
            NeighborhoodObservation(
                sequence=sequence,
                candidate_index=(candidate_ordinal),
                scenario_sha256=_sha(
                    "run05",
                    "neighborhood",
                    "scenario",
                    sequence,
                    grid_index,
                ),
                verdict=verdict,
                result_provenance_sha256=_sha(
                    "run05",
                    "neighborhood",
                    "result",
                    sequence,
                    grid_index,
                ),
                observation_evidence_sha256=_sha(
                    "run05",
                    "neighborhood",
                    "observation",
                    sequence,
                    grid_index,
                ),
                decision_evidence_sha256=_sha(
                    "run05",
                    "neighborhood",
                    "decision",
                    sequence,
                    grid_index,
                ),
                counterexample_evidence_sha256=(
                    _sha(
                        "run05",
                        "neighborhood",
                        "counterexample",
                        sequence,
                        grid_index,
                    )
                    if verdict == DecisionVerdict.FAIL
                    else None
                ),
            )
        )

        observations.append(
            (
                grid_index,
                verdict,
            )
        )


def run_run05_incident_strategy(
    *,
    strategy: Run05IncidentStrategy,
    candidate_count: int,
    incident_index: int,
    maximum_additional_evaluations: int,
    oracle: Oracle,
) -> Run05StrategyTrace:
    candidate_count = _candidate_count(candidate_count)

    maximum_additional_evaluations = _incident_budget(
        candidate_count=(candidate_count),
        budget=(maximum_additional_evaluations),
    )

    if (
        isinstance(
            incident_index,
            bool,
        )
        or not isinstance(
            incident_index,
            int,
        )
        or incident_index < 0
        or incident_index >= candidate_count
    ):
        raise HveeContractError("invalid Run-05 incident index")

    if not isinstance(
        strategy,
        Run05IncidentStrategy,
    ):
        raise HveeContractError("invalid Run-05 incident strategy")

    # The incident anchor is pre-existing confirmed
    # evidence under the frozen Run-05 contract.
    # Do not call the oracle for the anchor and do not
    # charge an evaluation for it.

    if strategy == Run05IncidentStrategy.SYMMETRIC_LINEAR_EXPANSION:
        order = _symmetric_order(
            candidate_count=(candidate_count),
            incident_index=(incident_index),
        )

        observations = []

        for index in order[:maximum_additional_evaluations]:
            observations.append(
                (
                    index,
                    _verdict(oracle(index)),
                )
            )

        return Run05StrategyTrace(
            task="incident",
            strategy=(strategy.value),
            candidate_count=(candidate_count),
            maximum_evaluations=(maximum_additional_evaluations),
            observations=(_trace_payload(observations)),
            terminal_status=(
                "grid_exhausted"
                if len(observations) == candidate_count - 1
                else "budget_exhausted"
            ),
            incident_index=(incident_index),
        )

    if strategy == Run05IncidentStrategy.BIDIRECTIONAL_EXPONENTIAL_BISECTION:
        return _run_exponential_incident(
            candidate_count=(candidate_count),
            incident_index=(incident_index),
            maximum_evaluations=(maximum_additional_evaluations),
            oracle=oracle,
        )

    if strategy == Run05IncidentStrategy.EXISTING_NEIGHBORHOOD_ORDERED:
        return _run_existing_neighborhood(
            candidate_count=(candidate_count),
            incident_index=(incident_index),
            maximum_evaluations=(maximum_additional_evaluations),
            oracle=oracle,
        )

    if strategy == Run05IncidentStrategy.HETREN_GENERALIZED:
        native: list[FailureFamilyObservation] = [
            _failure_observation(
                sequence=0,
                candidate_index=(incident_index),
                verdict=(DecisionVerdict.FAIL),
                source=(FailureFamilyObservationSource.INCIDENT_ANCHOR),
            )
        ]

        observations = []

        while True:
            bundle = build_failure_family_investigator_bundle(
                mode=(FailureFamilySearchMode.INCIDENT_ANCHORED),
                evaluation_type="synthetic",
                investigator_key=("hetren.run05.generalized.incident"),
                investigator_version="1.0.0",
                boundary_key=("hetren.run05.generalized.incident.boundary"),
                boundary_version="1.0.0",
                axis_key="synthetic.index",
                axis_version="1.0.0",
                axis_unit="index",
                candidate_values=tuple(
                    float(index) for index in range(candidate_count)
                ),
                invariant_parameters={
                    "benchmark": ("run05_non_monotonic"),
                },
                maximum_evaluations=(maximum_additional_evaluations),
                observations=tuple(native),
            )

            proposal = bundle.payload["outcome"]["next_proposal"]

            if proposal is None:
                return Run05StrategyTrace(
                    task="incident",
                    strategy=(strategy.value),
                    candidate_count=(candidate_count),
                    maximum_evaluations=(maximum_additional_evaluations),
                    observations=(_trace_payload(observations)),
                    terminal_status=(bundle.payload["investigator"]["status"]),
                    incident_index=(incident_index),
                )

            index = proposal["candidate_index"]

            verdict = _verdict(oracle(index))

            sequence = len(observations) + 1

            native.append(
                _failure_observation(
                    sequence=sequence,
                    candidate_index=(index),
                    verdict=verdict,
                    source=(FailureFamilyObservationSource.EVALUATION),
                )
            )

            observations.append(
                (
                    index,
                    verdict,
                )
            )

    raise HveeContractError("unsupported Run-05 incident strategy")


def _validate_pattern(
    *,
    pattern: object,
    candidate_count: int,
) -> str:
    if (
        not isinstance(
            pattern,
            str,
        )
        or len(pattern) != candidate_count
        or any(
            value
            not in {
                "P",
                "F",
            }
            for value in pattern
        )
    ):
        raise HveeContractError("invalid Run-05 scorer pattern")

    return pattern


def _true_failure_islands(
    pattern: str,
) -> tuple[
    tuple[int, int],
    ...,
]:
    islands = []
    index = 0

    while index < len(pattern):
        if pattern[index] != "F":
            index += 1
            continue

        lower = index

        while index + 1 < len(pattern) and pattern[index + 1] == "F":
            index += 1

        islands.append(
            (
                lower,
                index,
            )
        )

        index += 1

    return tuple(islands)


def _true_boundaries(
    pattern: str,
) -> tuple[
    tuple[int, int],
    ...,
]:
    return tuple(
        (
            index,
            index + 1,
        )
        for index in range(len(pattern) - 1)
        if pattern[index] != pattern[index + 1]
    )


def _validated_observations(
    *,
    trace: Run05StrategyTrace,
    pattern: str,
) -> list[
    tuple[
        int,
        DecisionVerdict,
    ]
]:
    if len(trace.observations) > trace.maximum_evaluations:
        raise HveeContractError("trace exceeds frozen evaluation budget")

    seen = set()
    result = []

    for (
        index,
        verdict_value,
    ) in trace.observations:
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
            or index >= trace.candidate_count
            or index in seen
        ):
            raise HveeContractError("invalid or repeated trace index")

        seen.add(index)

        try:
            verdict = DecisionVerdict(verdict_value)

        except ValueError as exc:
            raise HveeContractError("invalid trace verdict") from exc

        expected = (
            DecisionVerdict.FAIL if pattern[index] == "F" else DecisionVerdict.PASS
        )

        if verdict != expected:
            raise HveeContractError(
                "trace verdict disagrees " "with scorer ground truth"
            )

        result.append(
            (
                index,
                verdict,
            )
        )

    return result


def score_run05_global_trace(
    *,
    trace: Run05StrategyTrace,
    pattern: str,
) -> dict[str, float]:
    if trace.task != "global":
        raise HveeContractError("global scorer requires global trace")

    pattern = _validate_pattern(
        pattern=pattern,
        candidate_count=(trace.candidate_count),
    )

    observations = _validated_observations(
        trace=trace,
        pattern=pattern,
    )

    first_failure = None

    for sequence, (
        _index,
        verdict,
    ) in enumerate(
        observations,
        start=1,
    ):
        if verdict == DecisionVerdict.FAIL:
            first_failure = sequence
            break

    failure_discovered = first_failure is not None

    first_failure_cost = (
        first_failure if first_failure is not None else trace.maximum_evaluations + 1
    )

    islands = _true_failure_islands(pattern)

    touched = sum(
        any(
            (lower <= index <= upper) and verdict == DecisionVerdict.FAIL
            for index, verdict in observations
        )
        for lower, upper in islands
    )

    island_recall = touched / len(islands) if islands else 1.0

    observed_map = dict(observations)

    true_boundaries = _true_boundaries(pattern)

    observed_boundary_count = sum(
        (lower in observed_map and upper in observed_map)
        for lower, upper in true_boundaries
    )

    boundary_recall = (
        observed_boundary_count / len(true_boundaries) if true_boundaries else 1.0
    )

    return {
        "failure_discovery_rate": (1.0 if failure_discovered else 0.0),
        "experiments_to_first_failure": float(first_failure_cost),
        "failure_island_recall": float(island_recall),
        "boundary_recall": float(boundary_recall),
    }


def _incident_ground_truth(
    *,
    pattern: str,
    incident_index: int,
) -> tuple[int, int]:
    if (
        incident_index < 0
        or incident_index >= len(pattern)
        or pattern[incident_index] != "F"
    ):
        raise HveeContractError(
            "incident scorer anchor must " "be a true failing index"
        )

    lower = incident_index

    while lower > 0 and pattern[lower - 1] == "F":
        lower -= 1

    upper = incident_index

    while upper + 1 < len(pattern) and pattern[upper + 1] == "F":
        upper += 1

    return (
        lower,
        upper,
    )


def _incident_exact_at_prefix(
    *,
    pattern: str,
    incident_index: int,
    observations: list[
        tuple[
            int,
            DecisionVerdict,
        ]
    ],
) -> bool:
    lower, upper = _incident_ground_truth(
        pattern=pattern,
        incident_index=(incident_index),
    )

    observed = {incident_index: (DecisionVerdict.FAIL)}

    observed.update(dict(observations))

    for index in range(
        lower,
        upper + 1,
    ):
        if observed.get(index) != DecisionVerdict.FAIL:
            return False

    if lower > 0 and observed.get(lower - 1) != DecisionVerdict.PASS:
        return False

    if upper + 1 < len(pattern) and observed.get(upper + 1) != DecisionVerdict.PASS:
        return False

    return True


def score_run05_incident_trace(
    *,
    trace: Run05StrategyTrace,
    pattern: str,
) -> dict[str, float]:
    if trace.task != "incident" or trace.incident_index is None:
        raise HveeContractError("incident scorer requires " "incident trace and anchor")

    pattern = _validate_pattern(
        pattern=pattern,
        candidate_count=(trace.candidate_count),
    )

    observations = _validated_observations(
        trace=trace,
        pattern=pattern,
    )

    # Ground-truth scorer validation only.
    # This does not become a strategy-visible
    # evaluation and does not alter trace cost.
    _incident_ground_truth(
        pattern=pattern,
        incident_index=(trace.incident_index),
    )

    exact_cost = None

    for prefix_length in range(len(observations) + 1):
        if _incident_exact_at_prefix(
            pattern=pattern,
            incident_index=(trace.incident_index),
            observations=(observations[:prefix_length]),
        ):
            exact_cost = prefix_length
            break

    return {
        "incident_region_exactness": (1.0 if exact_cost is not None else 0.0),
        "additional_evaluations_to_exact_characterization": float(
            exact_cost if exact_cost is not None else trace.maximum_evaluations + 1
        ),
    }


def calculate_run05_normalized_auc(
    *,
    candidate_count: int,
    budgets: list[int] | tuple[int, ...],
    values: list[float] | tuple[float, ...],
    incident: bool,
) -> float:
    candidate_count = _candidate_count(candidate_count)

    expected = (
        INCIDENT_ADDITIONAL_BUDGETS[candidate_count]
        if incident
        else GLOBAL_BUDGETS[candidate_count]
    )

    if tuple(budgets) != tuple(expected):
        raise HveeContractError(
            "AUC budgets do not match " "frozen Run-05 precommitment"
        )

    if len(values) != len(expected):
        raise HveeContractError("AUC value count does not " "match frozen budgets")

    normalized = []

    for value in values:
        if isinstance(
            value,
            bool,
        ) or not isinstance(
            value,
            (
                int,
                float,
            ),
        ):
            raise HveeContractError("AUC values must be numeric")

        numeric = float(value)

        if not math.isfinite(numeric) or numeric < 0.0 or numeric > 1.0:
            raise HveeContractError("AUC values must lie " "between zero and one")

        normalized.append(numeric)

    denominator = candidate_count - 1 if incident else candidate_count

    x_values = [
        0.0,
        *[budget / denominator for budget in expected],
    ]

    y_values = [
        0.0,
        *normalized,
    ]

    area = 0.0

    for index in range(len(x_values) - 1):
        width = x_values[index + 1] - x_values[index]

        area += width * (y_values[index] + y_values[index + 1]) / 2.0

    if area < -1e-15 or area > 1.0 + 1e-15:
        raise HveeContractError("normalized AUC is " "outside expected bounds")

    return min(
        1.0,
        max(
            0.0,
            area,
        ),
    )


def aggregate_run05_metric(
    values: list[float] | tuple[float, ...],
) -> float:
    if not values:
        raise HveeContractError("metric aggregation requires values")

    normalized = []

    for value in values:
        if isinstance(
            value,
            bool,
        ) or not isinstance(
            value,
            (
                int,
                float,
            ),
        ):
            raise HveeContractError("metric values must be numeric")

        numeric = float(value)

        if not math.isfinite(numeric):
            raise HveeContractError("metric values must be finite")

        normalized.append(numeric)

    return sum(normalized) / len(normalized)


def classify_run05_development_verdict(
    *,
    task_key: str,
    hetren_metrics: dict[
        str,
        float,
    ],
    baseline_metrics: dict[
        str,
        dict[
            str,
            float,
        ],
    ],
) -> dict[str, object]:
    design = build_run05_non_monotonic_qualification_design_bundle().payload

    task = next(
        (item for item in design["tasks"] if item["key"] == task_key),
        None,
    )

    if task is None:
        raise HveeContractError("unknown Run-05 task")

    if not baseline_metrics:
        raise HveeContractError("Run-05 verdict requires " "predeclared baselines")

    primary_metrics = tuple(task["primary_metrics"])

    scoring = design["scoring_contract"]

    higher = set(scoring["higher_is_better_metrics"])

    lower = set(scoring["lower_is_better_metrics"])

    tolerance = float(scoring["numeric_comparison_tolerance"])

    comparisons = {}
    better_count = 0
    worse_count = 0

    for metric in primary_metrics:
        if metric not in hetren_metrics:
            raise HveeContractError(f"Hetren metric missing: {metric}")

        baseline_values = []

        for (
            strategy,
            metrics,
        ) in baseline_metrics.items():
            if metric not in metrics:
                raise HveeContractError(
                    f"baseline metric missing: " f"{strategy}:{metric}"
                )

            baseline_values.append(
                (
                    strategy,
                    float(metrics[metric]),
                )
            )

        if metric in higher:
            strongest_value = max(
                value
                for (
                    _strategy,
                    value,
                ) in baseline_values
            )

        elif metric in lower:
            strongest_value = min(
                value
                for (
                    _strategy,
                    value,
                ) in baseline_values
            )

        else:
            raise HveeContractError(f"metric orientation " f"missing: {metric}")

        strongest_strategies = sorted(
            strategy
            for (
                strategy,
                value,
            ) in baseline_values
            if abs(value - strongest_value) <= tolerance
        )

        hetren_value = float(hetren_metrics[metric])

        if metric in higher:
            if hetren_value > strongest_value + tolerance:
                relation = "better"
                better_count += 1

            elif hetren_value < strongest_value - tolerance:
                relation = "worse"
                worse_count += 1

            else:
                relation = "equal"

        else:
            if hetren_value < strongest_value - tolerance:
                relation = "better"
                better_count += 1

            elif hetren_value > strongest_value + tolerance:
                relation = "worse"
                worse_count += 1

            else:
                relation = "equal"

        comparisons[metric] = {
            "hetren": (hetren_value),
            "strongest_baseline_value": (strongest_value),
            "strongest_baseline_strategies": (strongest_strategies),
            "relation": (relation),
        }

    if better_count > 0 and worse_count == 0:
        verdict = Run05DevelopmentVerdict.SUPERIOR

    elif better_count == 0 and worse_count == 0:
        verdict = Run05DevelopmentVerdict.TIE

    elif better_count > 0 and worse_count > 0:
        verdict = Run05DevelopmentVerdict.MIXED

    else:
        verdict = Run05DevelopmentVerdict.INFERIOR

    return {
        "task_key": (task_key),
        "verdict": (verdict.value),
        "better_primary_metric_count": (better_count),
        "worse_primary_metric_count": (worse_count),
        "comparisons": (comparisons),
        "evidence_boundary": {
            "development_result_only": (True),
            "statistical_generalization_established": (False),
            "real_ai_generalization_established": (False),
            "behavioral_performance_qualified": (False),
        },
    }

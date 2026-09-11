from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
import hashlib
import random

from hvee.core.adaptive_scenario_search import (
    AdaptiveScenarioObservation,
    build_adaptive_scenario_search_bundle,
)
from hvee.core.contracts import HveeContractError
from hvee.core.decision import DecisionVerdict
from hvee.core.run05_non_monotonic_benchmark import (
    _farthest_unobserved,
)


Oracle = Callable[[int], DecisionVerdict]


class BehavioralQualificationComparatorStrategy(str, Enum):
    SEQUENTIAL_GRID = "sequential_grid"
    SEEDED_RANDOM = "seeded_random"
    FARTHEST_GAP_COVERAGE = "farthest_gap_coverage"
    CURRENT_ADAPTIVE_V1 = "current_adaptive_v1"


@dataclass(frozen=True)
class BehavioralQualificationComparatorTrace:
    strategy: str
    candidate_count: int
    maximum_evaluations: int
    observations: tuple[
        tuple[int, str],
        ...,
    ]
    terminal_status: str
    seed: int | None = None

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
        isinstance(
            value,
            bool,
        )
        or not isinstance(
            value,
            int,
        )
        or value < 2
    ):
        raise HveeContractError(
            "qualification comparator candidate_count must be an integer >= 2"
        )

    return value


def _maximum_evaluations(
    value: object,
    *,
    candidate_count: int,
) -> int:
    if (
        isinstance(
            value,
            bool,
        )
        or not isinstance(
            value,
            int,
        )
        or value < 1
        or value > candidate_count
    ):
        raise HveeContractError(
            "qualification comparator maximum_evaluations must lie "
            "between 1 and candidate_count"
        )

    return value


def _strategy(
    value: object,
) -> BehavioralQualificationComparatorStrategy:
    if not isinstance(
        value,
        BehavioralQualificationComparatorStrategy,
    ):
        raise HveeContractError(
            "qualification comparator strategy must use the strict enum"
        )

    return value


def _seed(
    value: object,
    *,
    strategy: BehavioralQualificationComparatorStrategy,
) -> int | None:
    if strategy is BehavioralQualificationComparatorStrategy.SEEDED_RANDOM:
        if (
            isinstance(
                value,
                bool,
            )
            or not isinstance(
                value,
                int,
            )
            or value < 0
        ):
            raise HveeContractError(
                "seeded random comparator requires a non-negative integer seed"
            )

        return value

    if value is not None:
        raise HveeContractError("non-random comparator must not receive a random seed")

    return None


def _oracle_verdict(
    oracle: Oracle,
    candidate_index: int,
) -> DecisionVerdict:
    if not callable(oracle):
        raise HveeContractError("qualification comparator oracle must be callable")

    value = oracle(candidate_index)

    if not isinstance(
        value,
        DecisionVerdict,
    ) or value not in (
        DecisionVerdict.PASS,
        DecisionVerdict.FAIL,
    ):
        raise HveeContractError(
            "qualification comparator oracle must return strict PASS or FAIL"
        )

    return value


def _trace(
    *,
    strategy: BehavioralQualificationComparatorStrategy,
    candidate_count: int,
    maximum_evaluations: int,
    observations: list[
        tuple[
            int,
            DecisionVerdict,
        ]
    ],
    terminal_status: str,
    seed: int | None,
) -> BehavioralQualificationComparatorTrace:
    seen: set[int] = set()

    normalized = []

    for candidate_index, verdict in observations:
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
            or candidate_index in seen
        ):
            raise HveeContractError(
                "qualification comparator produced invalid or duplicate candidate"
            )

        if not isinstance(
            verdict,
            DecisionVerdict,
        ) or verdict not in (
            DecisionVerdict.PASS,
            DecisionVerdict.FAIL,
        ):
            raise HveeContractError("qualification comparator produced invalid verdict")

        seen.add(candidate_index)

        normalized.append(
            (
                candidate_index,
                verdict.value,
            )
        )

    if len(normalized) > maximum_evaluations:
        raise HveeContractError("qualification comparator exceeded evaluation budget")

    return BehavioralQualificationComparatorTrace(
        strategy=(strategy.value),
        candidate_count=(candidate_count),
        maximum_evaluations=(maximum_evaluations),
        observations=tuple(normalized),
        terminal_status=(terminal_status),
        seed=seed,
    )


def _adaptive_observation(
    *,
    sequence: int,
    candidate_index: int,
    verdict: DecisionVerdict,
) -> AdaptiveScenarioObservation:
    namespace = "behavioral_qualification_comparator"

    return AdaptiveScenarioObservation(
        sequence=sequence,
        candidate_index=(candidate_index),
        scenario_sha256=_sha(
            namespace,
            "adaptive",
            "scenario",
            sequence,
            candidate_index,
        ),
        verdict=verdict,
        result_provenance_sha256=_sha(
            namespace,
            "adaptive",
            "result",
            sequence,
            candidate_index,
        ),
        observation_evidence_sha256=_sha(
            namespace,
            "adaptive",
            "observation",
            sequence,
            candidate_index,
        ),
        decision_evidence_sha256=_sha(
            namespace,
            "adaptive",
            "decision",
            sequence,
            candidate_index,
        ),
        counterexample_evidence_sha256=(
            _sha(
                namespace,
                "adaptive",
                "counterexample",
                sequence,
                candidate_index,
            )
            if verdict is DecisionVerdict.FAIL
            else None
        ),
    )


def run_behavioral_qualification_comparator(
    *,
    strategy: BehavioralQualificationComparatorStrategy,
    candidate_count: int,
    maximum_evaluations: int,
    oracle: Oracle,
    seed: int | None = None,
) -> BehavioralQualificationComparatorTrace:
    normalized_strategy = _strategy(strategy)

    normalized_candidate_count = _candidate_count(candidate_count)

    normalized_maximum_evaluations = _maximum_evaluations(
        maximum_evaluations,
        candidate_count=(normalized_candidate_count),
    )

    normalized_seed = _seed(
        seed,
        strategy=(normalized_strategy),
    )

    if not callable(oracle):
        raise HveeContractError("qualification comparator oracle must be callable")

    if normalized_strategy is BehavioralQualificationComparatorStrategy.SEQUENTIAL_GRID:
        observations = []

        for candidate_index in range(normalized_maximum_evaluations):
            observations.append(
                (
                    candidate_index,
                    _oracle_verdict(
                        oracle,
                        candidate_index,
                    ),
                )
            )

        return _trace(
            strategy=(normalized_strategy),
            candidate_count=(normalized_candidate_count),
            maximum_evaluations=(normalized_maximum_evaluations),
            observations=(observations),
            terminal_status=(
                "grid_exhausted"
                if normalized_maximum_evaluations == normalized_candidate_count
                else "budget_exhausted"
            ),
            seed=None,
        )

    if normalized_strategy is BehavioralQualificationComparatorStrategy.SEEDED_RANDOM:
        order = list(range(normalized_candidate_count))

        random.Random(normalized_seed).shuffle(order)

        observations = []

        for candidate_index in order[:normalized_maximum_evaluations]:
            observations.append(
                (
                    candidate_index,
                    _oracle_verdict(
                        oracle,
                        candidate_index,
                    ),
                )
            )

        return _trace(
            strategy=(normalized_strategy),
            candidate_count=(normalized_candidate_count),
            maximum_evaluations=(normalized_maximum_evaluations),
            observations=(observations),
            terminal_status=(
                "grid_exhausted"
                if normalized_maximum_evaluations == normalized_candidate_count
                else "budget_exhausted"
            ),
            seed=(normalized_seed),
        )

    if (
        normalized_strategy
        is BehavioralQualificationComparatorStrategy.FARTHEST_GAP_COVERAGE
    ):
        observations = []
        observed: set[int] = set()

        while len(observations) < normalized_maximum_evaluations:
            candidate_index = _farthest_unobserved(
                candidate_count=(normalized_candidate_count),
                observed=observed,
            )

            if candidate_index is None:
                break

            if candidate_index in observed:
                raise HveeContractError(
                    "farthest-gap comparator produced duplicate candidate"
                )

            verdict = _oracle_verdict(
                oracle,
                candidate_index,
            )

            observations.append(
                (
                    candidate_index,
                    verdict,
                )
            )

            observed.add(candidate_index)

        return _trace(
            strategy=(normalized_strategy),
            candidate_count=(normalized_candidate_count),
            maximum_evaluations=(normalized_maximum_evaluations),
            observations=(observations),
            terminal_status=(
                "grid_exhausted"
                if len(observations) == normalized_candidate_count
                else "budget_exhausted"
            ),
            seed=None,
        )

    if (
        normalized_strategy
        is BehavioralQualificationComparatorStrategy.CURRENT_ADAPTIVE_V1
    ):
        native: list[AdaptiveScenarioObservation] = []

        observations = []

        observed_indices: set[int] = set()

        while True:
            bundle = build_adaptive_scenario_search_bundle(
                evaluation_type=("synthetic"),
                search_key=("hetren.run05.current.adaptive"),
                search_version=("1.0.0"),
                boundary_key=("hetren.run05.current.adaptive.boundary"),
                boundary_version=("1.0.0"),
                axis_key=("synthetic.index"),
                axis_version=("1.0.0"),
                axis_unit=("index"),
                candidate_values=tuple(
                    float(index) for index in range(normalized_candidate_count)
                ),
                invariant_parameters={
                    "benchmark": ("run05_non_monotonic"),
                },
                maximum_observations=(normalized_maximum_evaluations),
                observations=tuple(native),
            )

            try:
                proposal = bundle.payload["outcome"]["next_proposal"]

                terminal_status = bundle.payload["search"]["status"]

            except (
                KeyError,
                TypeError,
            ) as exc:
                raise HveeContractError(
                    "adaptive comparator returned invalid native bundle"
                ) from exc

            if proposal is None:
                return _trace(
                    strategy=(normalized_strategy),
                    candidate_count=(normalized_candidate_count),
                    maximum_evaluations=(normalized_maximum_evaluations),
                    observations=(observations),
                    terminal_status=(terminal_status),
                    seed=None,
                )

            try:
                candidate_index = proposal["candidate_index"]

            except (
                KeyError,
                TypeError,
            ) as exc:
                raise HveeContractError(
                    "adaptive comparator proposal is invalid"
                ) from exc

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
                or candidate_index >= normalized_candidate_count
                or candidate_index in observed_indices
            ):
                raise HveeContractError(
                    "adaptive comparator produced invalid or duplicate candidate"
                )

            verdict = _oracle_verdict(
                oracle,
                candidate_index,
            )

            sequence = len(native) + 1

            native.append(
                _adaptive_observation(
                    sequence=(sequence),
                    candidate_index=(candidate_index),
                    verdict=(verdict),
                )
            )

            observations.append(
                (
                    candidate_index,
                    verdict,
                )
            )

            observed_indices.add(candidate_index)

    raise HveeContractError("unsupported qualification comparator strategy")


__all__ = [
    "BehavioralQualificationComparatorStrategy",
    "BehavioralQualificationComparatorTrace",
    "run_behavioral_qualification_comparator",
]

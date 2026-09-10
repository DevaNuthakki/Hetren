from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math
import random

from hvee.core.adaptive_scenario_search import (
    AdaptiveScenarioObservation,
    build_adaptive_scenario_search_bundle,
)
from hvee.core.contracts import HveeContractError
from hvee.core.decision import DecisionVerdict


BEHAVIORAL_QUALIFICATION_SCHEMA_VERSION = 1


class QualificationStrategy(str, Enum):
    HETREN_ADAPTIVE = "hetren_adaptive"
    SEQUENTIAL_GRID = "sequential_grid"
    SEEDED_RANDOM = "seeded_random"
    BRACKET_BISECTION = "bracket_bisection"


class SyntheticBoundaryDirection(str, Enum):
    PASS_TO_FAIL = "pass_to_fail"
    FAIL_TO_PASS = "fail_to_pass"


@dataclass(frozen=True)
class SyntheticBoundaryProblem:
    key: str
    candidate_count: int
    transition_index: int
    maximum_observations: int
    direction: SyntheticBoundaryDirection

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not self.key or len(self.key) > 160:
            raise HveeContractError(
                "qualification problem key must be a "
                "non-empty string of at most 160 characters"
            )

        if (
            isinstance(self.candidate_count, bool)
            or not isinstance(self.candidate_count, int)
            or self.candidate_count < 3
        ):
            raise HveeContractError(
                "qualification candidate_count must be " "an integer of at least three"
            )

        if (
            isinstance(self.transition_index, bool)
            or not isinstance(self.transition_index, int)
            or self.transition_index < 1
            or self.transition_index >= self.candidate_count
        ):
            raise HveeContractError(
                "qualification transition_index must " "describe an interior boundary"
            )

        if (
            isinstance(self.maximum_observations, bool)
            or not isinstance(self.maximum_observations, int)
            or self.maximum_observations < 2
            or self.maximum_observations > self.candidate_count
        ):
            raise HveeContractError(
                "qualification maximum_observations must "
                "be between two and candidate_count"
            )

        if not isinstance(
            self.direction,
            SyntheticBoundaryDirection,
        ):
            raise HveeContractError(
                "qualification direction must be " "SyntheticBoundaryDirection"
            )


@dataclass(frozen=True)
class BehavioralQualificationBundle:
    payload: dict[str, object]
    sha256: str


@dataclass(frozen=True)
class _StrategyProblem:
    key: str
    candidate_count: int
    maximum_observations: int


_BoundaryOracle = Callable[
    [int],
    DecisionVerdict,
]


def _canonical_sha256(
    value: object,
) -> str:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise HveeContractError(
            "qualification evidence must be canonical JSON"
        ) from exc

    return hashlib.sha256(encoded).hexdigest()


def _evidence_sha256(
    *parts: object,
) -> str:
    return _canonical_sha256(list(parts))


def _require_sha256(
    value: object,
    *,
    field: str,
) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise HveeContractError(f"{field} must be SHA-256 hex")

    try:
        int(
            value,
            16,
        )
    except ValueError as exc:
        raise HveeContractError(f"{field} must be SHA-256 hex") from exc

    return value.lower()


def _normalize_random_seeds(
    value: list[int] | tuple[int, ...],
) -> tuple[int, ...]:
    if (
        not isinstance(
            value,
            (list, tuple),
        )
        or not value
    ):
        raise HveeContractError(
            "qualification random seeds must be " "a non-empty sequence"
        )

    seeds: list[int] = []

    for seed in value:
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
            raise HveeContractError(
                "qualification random seeds must " "be non-negative integers"
            )

        if seed in seeds:
            raise HveeContractError("qualification random seeds must be unique")

        seeds.append(seed)

    return tuple(seeds)


def _normalize_problems(
    problems: list[SyntheticBoundaryProblem] | tuple[SyntheticBoundaryProblem, ...],
) -> tuple[SyntheticBoundaryProblem, ...]:
    if (
        not isinstance(
            problems,
            (list, tuple),
        )
        or not problems
    ):
        raise HveeContractError(
            "qualification problems must be " "a non-empty sequence"
        )

    normalized: list[SyntheticBoundaryProblem] = []

    seen_keys: set[str] = set()

    for problem in problems:
        if not isinstance(
            problem,
            SyntheticBoundaryProblem,
        ):
            raise HveeContractError(
                "qualification problems must contain " "SyntheticBoundaryProblem values"
            )

        if problem.key in seen_keys:
            raise HveeContractError("qualification problem keys must be unique")

        seen_keys.add(problem.key)

        normalized.append(problem)

    return tuple(normalized)


def _oracle_verdict(
    *,
    problem: SyntheticBoundaryProblem,
    candidate_index: int,
) -> DecisionVerdict:
    if (
        isinstance(candidate_index, bool)
        or not isinstance(candidate_index, int)
        or candidate_index < 0
        or candidate_index >= problem.candidate_count
    ):
        raise HveeContractError(
            "qualification candidate index is outside " "the problem grid"
        )

    before_transition = candidate_index < problem.transition_index

    if problem.direction == SyntheticBoundaryDirection.PASS_TO_FAIL:
        return DecisionVerdict.PASS if before_transition else DecisionVerdict.FAIL

    return DecisionVerdict.FAIL if before_transition else DecisionVerdict.PASS


def _build_boundary_oracle(
    *,
    problem: SyntheticBoundaryProblem,
) -> _BoundaryOracle:
    def oracle(
        candidate_index: int,
    ) -> DecisionVerdict:
        return _oracle_verdict(
            problem=problem,
            candidate_index=candidate_index,
        )

    return oracle


def _adjacent_observed_boundary(
    observed: dict[
        int,
        DecisionVerdict,
    ],
) -> (
    tuple[
        int,
        int,
    ]
    | None
):
    indices = sorted(observed)

    for lower, upper in zip(
        indices,
        indices[1:],
    ):
        if upper - lower == 1 and observed[lower] != observed[upper]:
            return (
                lower,
                upper,
            )

    return None


def _smallest_observed_bracket(
    observed: dict[
        int,
        DecisionVerdict,
    ],
) -> (
    tuple[
        int,
        int,
    ]
    | None
):
    ordered = sorted(observed)

    candidates: list[tuple[int, int, int]] = []

    for lower, upper in zip(
        ordered,
        ordered[1:],
    ):
        if observed[lower] != observed[upper]:
            candidates.append(
                (
                    upper - lower,
                    lower,
                    upper,
                )
            )

    if not candidates:
        return None

    _gap, lower, upper = min(candidates)

    return (
        lower,
        upper,
    )


def _largest_unresolved_gap_midpoint(
    observed: dict[
        int,
        DecisionVerdict,
    ],
) -> int | None:
    ordered = sorted(observed)

    gaps = [
        (
            upper - lower,
            lower,
            upper,
        )
        for lower, upper in zip(
            ordered,
            ordered[1:],
        )
        if upper - lower > 1
    ]

    if not gaps:
        return None

    largest_gap = max(gap for gap, _lower, _upper in gaps)

    _gap, lower, upper = min(item for item in gaps if item[0] == largest_gap)

    return (lower + upper) // 2


def _next_bisection_candidate(
    *,
    candidate_count: int,
    observed: dict[
        int,
        DecisionVerdict,
    ],
) -> tuple[
    int | None,
    str | None,
]:
    if not observed:
        return (
            0,
            "initial_lower",
        )

    if len(observed) == 1:
        upper = candidate_count - 1

        if upper not in observed:
            return (
                upper,
                "initial_upper",
            )

        if 0 not in observed:
            return (
                0,
                "initial_lower",
            )

    bracket = _smallest_observed_bracket(observed)

    if bracket is not None:
        lower, upper = bracket

        if upper - lower == 1:
            return (
                None,
                None,
            )

        midpoint = (lower + upper) // 2

        return (
            midpoint,
            "refine_observed_bracket",
        )

    midpoint = _largest_unresolved_gap_midpoint(observed)

    if midpoint is None:
        return (
            None,
            None,
        )

    return (
        midpoint,
        "explore_largest_gap",
    )


def _boundary_payload(
    *,
    observed: dict[
        int,
        DecisionVerdict,
    ],
) -> dict[str, object] | None:
    boundary = _adjacent_observed_boundary(observed)

    if boundary is None:
        return None

    lower, upper = boundary

    return {
        "lower_candidate_index": lower,
        "lower_verdict": (observed[lower].value),
        "upper_candidate_index": upper,
        "upper_verdict": (observed[upper].value),
    }


def _build_run_payload(
    *,
    problem: _StrategyProblem,
    strategy: QualificationStrategy,
    random_seed: int | None,
    proposal_indices: list[int],
    proposal_reasons: list[str],
    observed: dict[
        int,
        DecisionVerdict,
    ],
    terminal_status: str,
) -> dict[str, object]:
    boundary = _boundary_payload(observed=observed)

    success = boundary is not None

    return {
        "problem_key": (problem.key),
        "strategy": (strategy.value),
        "random_seed": (random_seed),
        "maximum_observations": (problem.maximum_observations),
        "observation_count": (len(observed)),
        "cost_units_consumed": (len(observed)),
        "success": (success),
        "terminal_status": (terminal_status),
        "proposal_indices": list(proposal_indices),
        "proposal_reasons": list(proposal_reasons),
        "observed_boundary": (boundary),
    }


def _baseline_terminal_status(
    *,
    problem: _StrategyProblem,
    observed: dict[
        int,
        DecisionVerdict,
    ],
) -> str:
    if _adjacent_observed_boundary(observed) is not None:
        return "boundary_bracketed"

    if len(observed) >= problem.maximum_observations:
        return "budget_exhausted"

    if len(observed) == problem.candidate_count:
        return "candidate_grid_exhausted"

    return "stopped_without_boundary"


def _run_sequential_grid(
    *,
    problem: _StrategyProblem,
    oracle: _BoundaryOracle,
) -> dict[str, object]:
    observed: dict[
        int,
        DecisionVerdict,
    ] = {}

    proposals: list[int] = []
    reasons: list[str] = []

    for candidate_index in range(problem.candidate_count):
        if len(observed) >= problem.maximum_observations:
            break

        proposals.append(candidate_index)

        reasons.append("declared_grid_order")

        observed[candidate_index] = oracle(candidate_index)

        if _adjacent_observed_boundary(observed) is not None:
            break

    return _build_run_payload(
        problem=problem,
        strategy=(QualificationStrategy.SEQUENTIAL_GRID),
        random_seed=None,
        proposal_indices=proposals,
        proposal_reasons=reasons,
        observed=observed,
        terminal_status=(
            _baseline_terminal_status(
                problem=problem,
                observed=observed,
            )
        ),
    )


def _run_seeded_random(
    *,
    problem: _StrategyProblem,
    oracle: _BoundaryOracle,
    seed: int,
) -> dict[str, object]:
    order = list(range(problem.candidate_count))

    generator = random.Random(seed)

    generator.shuffle(order)

    observed: dict[
        int,
        DecisionVerdict,
    ] = {}

    proposals: list[int] = []
    reasons: list[str] = []

    for candidate_index in order:
        if len(observed) >= problem.maximum_observations:
            break

        proposals.append(candidate_index)

        reasons.append("seeded_random_without_replacement")

        observed[candidate_index] = oracle(candidate_index)

        if _adjacent_observed_boundary(observed) is not None:
            break

    return _build_run_payload(
        problem=problem,
        strategy=(QualificationStrategy.SEEDED_RANDOM),
        random_seed=seed,
        proposal_indices=proposals,
        proposal_reasons=reasons,
        observed=observed,
        terminal_status=(
            _baseline_terminal_status(
                problem=problem,
                observed=observed,
            )
        ),
    )


def _run_bracket_bisection(
    *,
    problem: _StrategyProblem,
    oracle: _BoundaryOracle,
) -> dict[str, object]:
    observed: dict[
        int,
        DecisionVerdict,
    ] = {}

    proposals: list[int] = []
    reasons: list[str] = []

    while len(observed) < problem.maximum_observations:
        if _adjacent_observed_boundary(observed) is not None:
            break

        (
            candidate_index,
            reason,
        ) = _next_bisection_candidate(
            candidate_count=(problem.candidate_count),
            observed=observed,
        )

        if candidate_index is None:
            break

        if candidate_index in observed:
            raise HveeContractError(
                "bracket bisection proposed " "an already observed candidate"
            )

        proposals.append(candidate_index)

        reasons.append(reason or "unknown")

        observed[candidate_index] = oracle(candidate_index)

    return _build_run_payload(
        problem=problem,
        strategy=(QualificationStrategy.BRACKET_BISECTION),
        random_seed=None,
        proposal_indices=proposals,
        proposal_reasons=reasons,
        observed=observed,
        terminal_status=(
            _baseline_terminal_status(
                problem=problem,
                observed=observed,
            )
        ),
    )


def _run_hetren_adaptive(
    *,
    problem: _StrategyProblem,
    oracle: _BoundaryOracle,
) -> dict[str, object]:
    observations: list[AdaptiveScenarioObservation] = []

    proposal_indices: list[int] = []
    proposal_reasons: list[str] = []

    candidate_values = tuple(float(index) for index in range(problem.candidate_count))

    final_bundle = None

    while True:
        bundle = build_adaptive_scenario_search_bundle(
            evaluation_type=("synthetic"),
            search_key=("hetren.qualification.adaptive"),
            search_version="1.0.0",
            boundary_key=("hetren.qualification.boundary"),
            boundary_version="1.0.0",
            axis_key=("synthetic.candidate_index"),
            axis_version="1.0.0",
            axis_unit="index",
            candidate_values=(candidate_values),
            invariant_parameters={
                "oracle_class": ("synthetic_monotonic_boundary"),
            },
            maximum_observations=(problem.maximum_observations),
            observations=tuple(observations),
        )

        final_bundle = bundle

        proposal = bundle.payload["outcome"]["next_proposal"]

        if proposal is None:
            break

        candidate_index = proposal["candidate_index"]

        if not isinstance(
            candidate_index,
            int,
        ) or isinstance(
            candidate_index,
            bool,
        ):
            raise HveeContractError(
                "Hetren adaptive proposal candidate " "index is invalid"
            )

        if candidate_index in {
            observation.candidate_index for observation in observations
        }:
            raise HveeContractError(
                "Hetren adaptive proposed an " "already observed candidate"
            )

        verdict = oracle(candidate_index)

        sequence = len(observations) + 1

        scenario_sha256 = _evidence_sha256(
            "qualification-scenario",
            problem.key,
            candidate_index,
        )

        counterexample_sha256 = None

        if verdict == DecisionVerdict.FAIL:
            counterexample_sha256 = _evidence_sha256(
                "qualification-counterexample",
                problem.key,
                candidate_index,
                sequence,
            )

        observations.append(
            AdaptiveScenarioObservation(
                sequence=sequence,
                candidate_index=(candidate_index),
                scenario_sha256=(scenario_sha256),
                verdict=verdict,
                result_provenance_sha256=(
                    _evidence_sha256(
                        "qualification-result",
                        problem.key,
                        candidate_index,
                        sequence,
                    )
                ),
                observation_evidence_sha256=(
                    _evidence_sha256(
                        "qualification-observation",
                        problem.key,
                        candidate_index,
                        sequence,
                    )
                ),
                decision_evidence_sha256=(
                    _evidence_sha256(
                        "qualification-decision",
                        problem.key,
                        candidate_index,
                        sequence,
                    )
                ),
                counterexample_evidence_sha256=(counterexample_sha256),
            )
        )

        proposal_indices.append(candidate_index)

        reason = proposal.get("reason")

        if not isinstance(
            reason,
            str,
        ):
            raise HveeContractError("Hetren adaptive proposal reason " "is invalid")

        proposal_reasons.append(reason)

    if final_bundle is None:
        raise HveeContractError(
            "Hetren adaptive qualification " "did not construct a state"
        )

    observed = {
        observation.candidate_index: (observation.verdict)
        for observation in observations
    }

    status = final_bundle.payload["search"]["status"]

    if not isinstance(
        status,
        str,
    ):
        raise HveeContractError("Hetren adaptive terminal status is invalid")

    return _build_run_payload(
        problem=problem,
        strategy=(QualificationStrategy.HETREN_ADAPTIVE),
        random_seed=None,
        proposal_indices=(proposal_indices),
        proposal_reasons=(proposal_reasons),
        observed=observed,
        terminal_status=status,
    )


def _strategy_summary(
    *,
    runs: list[dict[str, object]],
    strategy: QualificationStrategy,
) -> dict[str, object]:
    selected = [run for run in runs if (run["strategy"] == strategy.value)]

    if not selected:
        raise HveeContractError("qualification strategy has no runs")

    successful = [run for run in selected if run["success"] is True]

    run_count = len(selected)

    success_count = len(successful)

    observation_counts = [int(run["observation_count"]) for run in selected]

    successful_counts = [int(run["observation_count"]) for run in successful]

    return {
        "run_count": (run_count),
        "success_count": (success_count),
        "failure_count": (run_count - success_count),
        "success_rate": (success_count / run_count),
        "mean_observation_count": (sum(observation_counts) / run_count),
        "mean_observations_on_success": (
            (sum(successful_counts) / success_count) if success_count else None
        ),
        "minimum_observation_count": (min(observation_counts)),
        "maximum_observation_count": (max(observation_counts)),
    }


def calculate_behavioral_qualification_sha256(
    payload: dict[str, object],
) -> str:
    if not isinstance(
        payload,
        dict,
    ):
        raise HveeContractError("qualification payload must be an object")

    return _canonical_sha256(payload)


def build_behavioral_qualification_bundle(
    *,
    problems: list[SyntheticBoundaryProblem] | tuple[SyntheticBoundaryProblem, ...],
    random_seeds: list[int] | tuple[int, ...],
) -> BehavioralQualificationBundle:
    normalized_problems = _normalize_problems(problems)

    normalized_seeds = _normalize_random_seeds(random_seeds)

    runs: list[dict[str, object]] = []

    for problem in normalized_problems:
        strategy_problem = _StrategyProblem(
            key=problem.key,
            candidate_count=(problem.candidate_count),
            maximum_observations=(problem.maximum_observations),
        )

        oracle = _build_boundary_oracle(problem=problem)

        runs.append(
            _run_hetren_adaptive(
                problem=strategy_problem,
                oracle=oracle,
            )
        )

        runs.append(
            _run_sequential_grid(
                problem=strategy_problem,
                oracle=oracle,
            )
        )

        runs.append(
            _run_bracket_bisection(
                problem=strategy_problem,
                oracle=oracle,
            )
        )

        for seed in normalized_seeds:
            runs.append(
                _run_seeded_random(
                    problem=strategy_problem,
                    oracle=oracle,
                    seed=seed,
                )
            )

    summaries = {
        strategy.value: (
            _strategy_summary(
                runs=runs,
                strategy=strategy,
            )
        )
        for strategy in (
            QualificationStrategy.HETREN_ADAPTIVE,
            QualificationStrategy.SEQUENTIAL_GRID,
            QualificationStrategy.SEEDED_RANDOM,
            QualificationStrategy.BRACKET_BISECTION,
        )
    }

    problem_payloads = [
        {
            "key": problem.key,
            "candidate_count": (problem.candidate_count),
            "transition_index": (problem.transition_index),
            "maximum_observations": (problem.maximum_observations),
            "direction": (problem.direction.value),
        }
        for problem in normalized_problems
    ]

    payload: dict[str, object] = {
        "schema_version": (BEHAVIORAL_QUALIFICATION_SCHEMA_VERSION),
        "type": ("behavioral_qualification_harness"),
        "benchmark_contract": {
            "problem_class": ("synthetic_monotonic_ordered_boundary"),
            "success_definition": (
                "opposite verdicts observed on adjacent " "candidate indices"
            ),
            "cost_unit": ("one oracle evaluation"),
            "same_problem_per_strategy": (True),
            "same_budget_per_problem": (True),
            "hidden_transition_withheld_from_strategy": (True),
            "hidden_oracle_parameters_structurally_separated": (True),
            "sampling_without_replacement": (True),
            "sequential_grid_order": ("ascending_candidate_index"),
            "random_seeds": list(normalized_seeds),
            "random_seed_policy": ("predeclared_deterministic"),
            "strong_comparator": ("bracket_bisection"),
            "hetren_policy": ("existing_adaptive_scenario_search"),
            "benchmark_specific_hetren_tuning": (False),
            "failed_runs_preserved": (True),
        },
        "problems": (problem_payloads),
        "runs": (runs),
        "strategy_summary": (summaries),
        "evidence_boundary": {
            "behavioral_performance_qualified": (False),
            "closed_loop_engine_overhead_qualified": (False),
            "generalization_to_real_ai_established": (False),
            "model_inference_performed": (False),
            "production_qualified": (False),
            "random_baseline_multi_seeded": (True),
            "strong_bisection_comparator_present": (True),
            "synthetic_methodology_executed": (True),
        },
    }

    return BehavioralQualificationBundle(
        payload=payload,
        sha256=(calculate_behavioral_qualification_sha256(payload)),
    )


def verify_behavioral_qualification_bundle(
    *,
    payload: object,
    expected_sha256: object,
) -> bool:
    try:
        expected_sha256 = _require_sha256(
            expected_sha256,
            field=("expected qualification SHA-256"),
        )

        if not isinstance(
            payload,
            dict,
        ):
            return False

        if set(payload) != {
            "schema_version",
            "type",
            "benchmark_contract",
            "problems",
            "runs",
            "strategy_summary",
            "evidence_boundary",
        }:
            return False

        if payload["schema_version"] != BEHAVIORAL_QUALIFICATION_SCHEMA_VERSION:
            return False

        if payload["type"] != "behavioral_qualification_harness":
            return False

        benchmark_contract = payload["benchmark_contract"]

        problem_payloads = payload["problems"]

        if not isinstance(
            benchmark_contract,
            dict,
        ):
            return False

        if not isinstance(
            problem_payloads,
            list,
        ):
            return False

        seeds = benchmark_contract.get("random_seeds")

        if not isinstance(
            seeds,
            list,
        ):
            return False

        problems: list[SyntheticBoundaryProblem] = []

        for item in problem_payloads:
            if not isinstance(
                item,
                dict,
            ) or set(item) != {
                "key",
                "candidate_count",
                "transition_index",
                "maximum_observations",
                "direction",
            }:
                return False

            problems.append(
                SyntheticBoundaryProblem(
                    key=item["key"],
                    candidate_count=(item["candidate_count"]),
                    transition_index=(item["transition_index"]),
                    maximum_observations=(item["maximum_observations"]),
                    direction=(SyntheticBoundaryDirection(item["direction"])),
                )
            )

        rebuilt = build_behavioral_qualification_bundle(
            problems=problems,
            random_seeds=seeds,
        )

    except (
        HveeContractError,
        KeyError,
        TypeError,
        ValueError,
    ):
        return False

    if rebuilt.payload != payload:
        return False

    if rebuilt.sha256 != expected_sha256:
        return False

    return True

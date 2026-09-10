from __future__ import annotations

from copy import deepcopy
import inspect

import pytest

from hvee.core import behavioral_qualification as qualification_module

from hvee.core.behavioral_qualification import (
    BehavioralQualificationBundle,
    QualificationStrategy,
    SyntheticBoundaryDirection,
    SyntheticBoundaryProblem,
    build_behavioral_qualification_bundle,
    calculate_behavioral_qualification_sha256,
    verify_behavioral_qualification_bundle,
)
from hvee.core.contracts import HveeContractError


def _problem(
    *,
    key="problem",
    candidate_count=17,
    transition_index=8,
    maximum_observations=None,
    direction=(SyntheticBoundaryDirection.PASS_TO_FAIL),
):
    if maximum_observations is None:
        maximum_observations = candidate_count

    return SyntheticBoundaryProblem(
        key=key,
        candidate_count=candidate_count,
        transition_index=transition_index,
        maximum_observations=(maximum_observations),
        direction=direction,
    )


def _bundle(
    problems=None,
    seeds=(7, 11, 19),
):
    if problems is None:
        problems = (_problem(),)

    return build_behavioral_qualification_bundle(
        problems=problems,
        random_seeds=seeds,
    )


def _runs(
    bundle,
    strategy,
):
    return [
        run for run in bundle.payload["runs"] if run["strategy"] == (strategy.value)
    ]


def test_builds_reverifiable_qualification_bundle():
    bundle = _bundle()

    assert isinstance(
        bundle,
        BehavioralQualificationBundle,
    )

    assert verify_behavioral_qualification_bundle(
        payload=bundle.payload,
        expected_sha256=bundle.sha256,
    )


def test_all_four_strategies_are_present():
    bundle = _bundle()

    strategies = {run["strategy"] for run in bundle.payload["runs"]}

    assert strategies == {
        "hetren_adaptive",
        "sequential_grid",
        "seeded_random",
        "bracket_bisection",
    }


@pytest.mark.parametrize(
    (
        "candidate_count",
        "transition_index",
        "expected_observations",
    ),
    [
        (
            5,
            1,
            4,
        ),
        (
            5,
            2,
            4,
        ),
        (
            5,
            3,
            4,
        ),
        (
            9,
            1,
            5,
        ),
        (
            9,
            4,
            5,
        ),
        (
            9,
            7,
            5,
        ),
        (
            17,
            1,
            6,
        ),
        (
            17,
            8,
            6,
        ),
        (
            17,
            15,
            6,
        ),
    ],
)
def test_hetren_matches_strong_bisection_on_probe_cases(
    candidate_count,
    transition_index,
    expected_observations,
):
    problem = _problem(
        key=(f"probe-{candidate_count}-" f"{transition_index}"),
        candidate_count=(candidate_count),
        transition_index=(transition_index),
    )

    bundle = _bundle(
        problems=(problem,),
        seeds=(3,),
    )

    hetren = _runs(
        bundle,
        QualificationStrategy.HETREN_ADAPTIVE,
    )[0]

    bisection = _runs(
        bundle,
        QualificationStrategy.BRACKET_BISECTION,
    )[0]

    assert hetren["success"] is True

    assert bisection["success"] is True

    assert hetren["observation_count"] == expected_observations

    assert bisection["observation_count"] == expected_observations

    assert hetren["proposal_indices"] == bisection["proposal_indices"]


@pytest.mark.parametrize(
    "direction",
    [
        SyntheticBoundaryDirection.PASS_TO_FAIL,
        SyntheticBoundaryDirection.FAIL_TO_PASS,
    ],
)
def test_both_monotonic_directions_are_supported(
    direction,
):
    problem = _problem(
        key=f"direction-{direction.value}",
        candidate_count=17,
        transition_index=8,
        direction=direction,
    )

    bundle = _bundle(
        problems=(problem,),
        seeds=(5,),
    )

    hetren = _runs(
        bundle,
        QualificationStrategy.HETREN_ADAPTIVE,
    )[0]

    bisection = _runs(
        bundle,
        QualificationStrategy.BRACKET_BISECTION,
    )[0]

    assert hetren["success"] is True

    assert bisection["success"] is True

    assert hetren["observation_count"] == bisection["observation_count"] == 6


def test_sequential_grid_is_not_assumed_to_always_be_worse():
    problem = _problem(
        candidate_count=17,
        transition_index=1,
    )

    bundle = _bundle(
        problems=(problem,),
        seeds=(7,),
    )

    hetren = _runs(
        bundle,
        QualificationStrategy.HETREN_ADAPTIVE,
    )[0]

    sequential = _runs(
        bundle,
        QualificationStrategy.SEQUENTIAL_GRID,
    )[0]

    assert sequential["observation_count"] == 2

    assert hetren["observation_count"] == 6

    assert sequential["observation_count"] < hetren["observation_count"]


def test_hetren_beats_sequential_grid_on_central_large_grid():
    problem = _problem(
        candidate_count=17,
        transition_index=8,
    )

    bundle = _bundle(
        problems=(problem,),
        seeds=(7,),
    )

    hetren = _runs(
        bundle,
        QualificationStrategy.HETREN_ADAPTIVE,
    )[0]

    sequential = _runs(
        bundle,
        QualificationStrategy.SEQUENTIAL_GRID,
    )[0]

    assert hetren["observation_count"] == 6

    assert sequential["observation_count"] == 9

    assert hetren["observation_count"] < sequential["observation_count"]


def test_seeded_random_is_reproducible():
    problem = _problem(
        candidate_count=17,
        transition_index=8,
    )

    first = _bundle(
        problems=(problem,),
        seeds=(
            7,
            11,
            19,
        ),
    )

    second = _bundle(
        problems=(problem,),
        seeds=(
            7,
            11,
            19,
        ),
    )

    first_random = _runs(
        first,
        QualificationStrategy.SEEDED_RANDOM,
    )

    second_random = _runs(
        second,
        QualificationStrategy.SEEDED_RANDOM,
    )

    assert first_random == second_random


def test_different_random_seeds_create_distinct_orders():
    problem = _problem(
        candidate_count=17,
        transition_index=8,
    )

    bundle = _bundle(
        problems=(problem,),
        seeds=(
            7,
            11,
        ),
    )

    random_runs = _runs(
        bundle,
        QualificationStrategy.SEEDED_RANDOM,
    )

    assert len(random_runs) == 2

    assert random_runs[0]["proposal_indices"] != random_runs[1]["proposal_indices"]


def test_tight_budget_preserves_non_discovery():
    problem = _problem(
        candidate_count=17,
        transition_index=8,
        maximum_observations=5,
    )

    bundle = _bundle(
        problems=(problem,),
        seeds=(7,),
    )

    hetren = _runs(
        bundle,
        QualificationStrategy.HETREN_ADAPTIVE,
    )[0]

    bisection = _runs(
        bundle,
        QualificationStrategy.BRACKET_BISECTION,
    )[0]

    assert hetren["success"] is False

    assert bisection["success"] is False

    assert hetren["terminal_status"] == "budget_exhausted"

    assert bisection["terminal_status"] == "budget_exhausted"

    assert hetren["observation_count"] == 5

    assert bisection["observation_count"] == 5


def test_every_run_respects_exact_problem_budget():
    problems = (
        _problem(
            key="p5",
            candidate_count=5,
            transition_index=2,
            maximum_observations=4,
        ),
        _problem(
            key="p9",
            candidate_count=9,
            transition_index=4,
            maximum_observations=5,
        ),
    )

    bundle = _bundle(
        problems=problems,
        seeds=(2, 3),
    )

    budgets = {problem.key: (problem.maximum_observations) for problem in problems}

    for run in bundle.payload["runs"]:
        budget = budgets[run["problem_key"]]

        assert run["maximum_observations"] == budget

        assert run["observation_count"] <= budget

        assert run["cost_units_consumed"] == run["observation_count"]


def test_hidden_transition_is_not_present_in_strategy_run_payload():
    bundle = _bundle()

    for run in bundle.payload["runs"]:
        assert "transition_index" not in run

        assert "direction" not in run


def test_benchmark_contract_declares_strong_comparator():
    bundle = _bundle()

    contract = bundle.payload["benchmark_contract"]

    assert contract["strong_comparator"] == "bracket_bisection"

    assert contract["benchmark_specific_hetren_tuning"] is False

    assert contract["hidden_transition_withheld_from_strategy"] is True


def test_claim_boundary_remains_methodology_only():
    bundle = _bundle()

    boundary = bundle.payload["evidence_boundary"]

    assert boundary["synthetic_methodology_executed"] is True

    assert boundary["strong_bisection_comparator_present"] is True

    assert boundary["behavioral_performance_qualified"] is False

    assert boundary["closed_loop_engine_overhead_qualified"] is False

    assert boundary["generalization_to_real_ai_established"] is False

    assert boundary["model_inference_performed"] is False


def test_strategy_summary_preserves_failures():
    problem = _problem(
        candidate_count=17,
        transition_index=8,
        maximum_observations=5,
    )

    bundle = _bundle(
        problems=(problem,),
        seeds=(7,),
    )

    summary = bundle.payload["strategy_summary"]["hetren_adaptive"]

    assert summary["run_count"] == 1

    assert summary["success_count"] == 0

    assert summary["failure_count"] == 1

    assert summary["success_rate"] == 0.0

    assert summary["mean_observations_on_success"] is None


def test_random_summary_counts_all_predeclared_seeds():
    problems = (
        _problem(
            key="one",
            candidate_count=9,
            transition_index=4,
        ),
        _problem(
            key="two",
            candidate_count=17,
            transition_index=8,
        ),
    )

    seeds = (
        7,
        11,
        19,
    )

    bundle = _bundle(
        problems=problems,
        seeds=seeds,
    )

    summary = bundle.payload["strategy_summary"]["seeded_random"]

    assert summary["run_count"] == len(problems) * len(seeds)


def test_bundle_is_deterministic():
    problems = (
        _problem(
            key="one",
            candidate_count=9,
            transition_index=3,
        ),
        _problem(
            key="two",
            candidate_count=17,
            transition_index=12,
            direction=(SyntheticBoundaryDirection.FAIL_TO_PASS),
        ),
    )

    first = _bundle(
        problems=problems,
        seeds=(
            7,
            11,
        ),
    )

    second = _bundle(
        problems=problems,
        seeds=(
            7,
            11,
        ),
    )

    assert first.payload == second.payload

    assert first.sha256 == second.sha256


def test_verifier_rejects_recomputed_summary_tampering():
    bundle = _bundle()

    tampered = deepcopy(bundle.payload)

    tampered["strategy_summary"]["hetren_adaptive"]["success_rate"] = 0.123

    recomputed = calculate_behavioral_qualification_sha256(tampered)

    assert not (
        verify_behavioral_qualification_bundle(
            payload=tampered,
            expected_sha256=recomputed,
        )
    )


@pytest.mark.parametrize(
    "candidate_count",
    [
        0,
        1,
        2,
    ],
)
def test_problem_rejects_too_small_candidate_grid(
    candidate_count,
):
    with pytest.raises(
        HveeContractError,
        match="at least three",
    ):
        _problem(
            candidate_count=(candidate_count),
            transition_index=1,
            maximum_observations=2,
        )


@pytest.mark.parametrize(
    "transition_index",
    [
        0,
        17,
        18,
    ],
)
def test_problem_rejects_non_interior_transition(
    transition_index,
):
    with pytest.raises(
        HveeContractError,
        match="interior boundary",
    ):
        _problem(
            candidate_count=17,
            transition_index=(transition_index),
        )


def test_duplicate_problem_keys_fail_closed():
    first = _problem(key="duplicate")

    second = _problem(
        key="duplicate",
        transition_index=9,
    )

    with pytest.raises(
        HveeContractError,
        match="keys must be unique",
    ):
        _bundle(
            problems=(
                first,
                second,
            ),
        )


def test_duplicate_random_seeds_fail_closed():
    with pytest.raises(
        HveeContractError,
        match="seeds must be unique",
    ):
        _bundle(
            seeds=(
                7,
                7,
            ),
        )


def test_strategy_surface_structurally_excludes_hidden_oracle_parameters():
    field_names = set(qualification_module._StrategyProblem.__dataclass_fields__)

    assert field_names == {
        "key",
        "candidate_count",
        "maximum_observations",
    }

    strategy_functions = (
        qualification_module._run_hetren_adaptive,
        qualification_module._run_sequential_grid,
        qualification_module._run_seeded_random,
        qualification_module._run_bracket_bisection,
    )

    for strategy_function in strategy_functions:
        parameters = inspect.signature(strategy_function).parameters

        assert "transition_index" not in parameters

        assert "direction" not in parameters

        assert "oracle" in parameters


def test_benchmark_contract_records_structural_oracle_separation():
    bundle = _bundle()

    contract = bundle.payload["benchmark_contract"]

    assert contract["hidden_transition_withheld_from_strategy"] is True

    assert contract["hidden_oracle_parameters_structurally_separated"] is True

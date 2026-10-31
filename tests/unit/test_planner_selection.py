import math

import pytest

from packages.core.hetren_diagnosis.contracts import (
    ContractError,
    DiagnosisStatus,
    Experiment,
    InterventionKind,
    RationaleCode,
    Verdict,
)

from packages.core.hetren_diagnosis.planner import (
    PLANNER_KEY,
    PLANNER_VERSION,
    information_gain_per_cost,
    initial_posterior,
    rank_eligible_experiments,
    select_active_experiment,
)

from test_diagnosis_contract import make_problem


def test_rank_orders_by_information_gain_per_cost():
    problem = make_problem()
    posterior = initial_posterior(problem)

    ranked = rank_eligible_experiments(
        problem,
        posterior,
        remaining_budget=3,
    )

    assert [item[0].key for item in ranked] == [
        "e1",
        "e2",
    ]

    assert ranked[0][2] > ranked[1][2]


def test_budget_excludes_experiments_that_do_not_fit():
    problem = make_problem()
    posterior = initial_posterior(problem)

    ranked = rank_eligible_experiments(
        problem,
        posterior,
        remaining_budget=1,
    )

    assert [item[0].key for item in ranked] == [
        "e1",
    ]


def test_excluded_experiment_is_not_a_candidate():
    problem = make_problem()
    posterior = initial_posterior(problem)

    ranked = rank_eligible_experiments(
        problem,
        posterior,
        remaining_budget=3,
        excluded_experiment_keys=frozenset({"e1"}),
    )

    assert [item[0].key for item in ranked] == [
        "e2",
    ]


def test_candidate_keys_are_sorted_even_when_ranking_is_not_lexical():
    problem = make_problem()
    posterior = initial_posterior(problem)

    decision = select_active_experiment(
        problem,
        posterior,
        remaining_budget=3,
    )

    assert decision.candidate_experiment_keys == (
        "e1",
        "e2",
    )


def test_active_decision_selects_best_experiment():
    problem = make_problem()
    posterior = initial_posterior(problem)

    decision = select_active_experiment(
        problem,
        posterior,
        remaining_budget=3,
    )

    assert decision.planner_key == PLANNER_KEY
    assert decision.planner_version == PLANNER_VERSION

    assert decision.experiment_key == "e1"
    assert decision.status is DiagnosisStatus.ACTIVE
    assert (
        decision.rationale
        is RationaleCode.INFORMATION_GAIN_PER_COST
    )

    assert decision.problem_sha256 == problem.problem_sha256

    assert math.isclose(
        decision.expected_information_gain,
        1.0,
        abs_tol=1e-12,
    )

    assert math.isclose(
        decision.score_per_cost,
        information_gain_per_cost(
            posterior,
            problem.experiments[0],
        ),
        abs_tol=1e-12,
    )


def test_selection_is_deterministic_for_identical_inputs():
    problem = make_problem()
    posterior = initial_posterior(problem)

    decisions = [
        select_active_experiment(
            problem,
            posterior,
            remaining_budget=3,
        )
        for _ in range(10)
    ]

    assert len(
        {
            (
                decision.experiment_key,
                decision.candidate_experiment_keys,
                decision.expected_information_gain,
                decision.score_per_cost,
            )
            for decision in decisions
        }
    ) == 1


def test_equal_score_uses_higher_information_gain():
    problem = make_problem()
    posterior = initial_posterior(problem)

    high_gain = Experiment(
        "a-high-gain",
        InterventionKind.REPLAY,
        "step-high",
        1,
        (
            ("h1", Verdict.FAIL),
            ("h2", Verdict.PASS),
        ),
    )

    lower_gain = Experiment(
        "b-lower-gain",
        InterventionKind.REPLAY,
        "step-low",
        1,
        (
            ("h1", Verdict.PASS),
            ("h2", Verdict.PASS),
        ),
    )

    modified_problem = problem.__class__(
        trace=problem.trace,
        hypotheses=problem.hypotheses,
        experiments=(
            lower_gain,
            high_gain,
        ),
        budget_units=problem.budget_units,
    )

    ranked = rank_eligible_experiments(
        modified_problem,
        posterior,
        remaining_budget=3,
    )

    assert ranked[0][0].key == "a-high-gain"


def test_equal_score_and_gain_uses_lower_cost():
    problem = make_problem()
    posterior = initial_posterior(problem)

    cheap = Experiment(
        "a-cheap",
        InterventionKind.REPLAY,
        "step-cheap",
        1,
        (
            ("h1", Verdict.FAIL),
            ("h2", Verdict.PASS),
        ),
    )

    expensive = Experiment(
        "b-expensive",
        InterventionKind.REPLAY,
        "step-expensive",
        2,
        (
            ("h1", Verdict.FAIL),
            ("h2", Verdict.PASS),
        ),
    )

    modified_problem = problem.__class__(
        trace=problem.trace,
        hypotheses=problem.hypotheses,
        experiments=(
            expensive,
            cheap,
        ),
        budget_units=problem.budget_units,
    )

    ranked = rank_eligible_experiments(
        modified_problem,
        posterior,
        remaining_budget=3,
    )

    assert ranked[0][0].key == "a-cheap"


def test_no_eligible_experiment_is_rejected_for_active_selection():
    problem = make_problem()
    posterior = initial_posterior(problem)

    with pytest.raises(ContractError):
        select_active_experiment(
            problem,
            posterior,
            remaining_budget=0,
        )

def test_candidate_keys_are_sorted_independently_of_ranking_order():
    problem = make_problem()
    posterior = initial_posterior(problem)

    high_gain = Experiment(
        "z-high",
        InterventionKind.REPLAY,
        "step-high",
        1,
        (
            ("h1", Verdict.FAIL),
            ("h2", Verdict.PASS),
        ),
    )

    low_gain = Experiment(
        "a-low",
        InterventionKind.REPLAY,
        "step-low",
        1,
        (
            ("h1", Verdict.PASS),
            ("h2", Verdict.PASS),
        ),
    )

    modified_problem = problem.__class__(
        trace=problem.trace,
        hypotheses=problem.hypotheses,
        experiments=(
            high_gain,
            low_gain,
        ),
        budget_units=problem.budget_units,
    )

    decision = select_active_experiment(
        modified_problem,
        posterior,
        remaining_budget=3,
    )

    assert decision.experiment_key == "z-high"
    assert decision.candidate_experiment_keys == (
        "a-low",
        "z-high",
    )


def test_equal_score_gain_and_cost_use_lexicographic_key():
    problem = make_problem()
    posterior = initial_posterior(problem)

    later_key = Experiment(
        "b-later",
        InterventionKind.REPLAY,
        "step-b",
        1,
        (
            ("h1", Verdict.FAIL),
            ("h2", Verdict.PASS),
        ),
    )

    earlier_key = Experiment(
        "a-earlier",
        InterventionKind.REPLAY,
        "step-a",
        1,
        (
            ("h1", Verdict.FAIL),
            ("h2", Verdict.PASS),
        ),
    )

    modified_problem = problem.__class__(
        trace=problem.trace,
        hypotheses=problem.hypotheses,
        experiments=(
            later_key,
            earlier_key,
        ),
        budget_units=problem.budget_units,
    )

    ranked = rank_eligible_experiments(
        modified_problem,
        posterior,
        remaining_budget=3,
    )

    assert ranked[0][0].key == "a-earlier"
    assert ranked[1][0].key == "b-later"

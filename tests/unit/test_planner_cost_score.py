import math

from packages.core.hetren_diagnosis.contracts import (
    Experiment,
    InterventionKind,
    Verdict,
)

from packages.core.hetren_diagnosis.planner import (
    expected_information_gain,
    information_gain_per_cost,
    initial_posterior,
)

from test_diagnosis_contract import make_problem


def test_information_gain_per_cost_divides_eig_by_cost():
    problem = make_problem()

    experiment = problem.experiments[0]
    posterior = initial_posterior(problem)

    gain = expected_information_gain(
        posterior,
        experiment,
    )

    score = information_gain_per_cost(
        posterior,
        experiment,
    )

    assert math.isclose(
        score,
        gain / experiment.cost_units,
        abs_tol=1e-12,
    )


def test_more_expensive_equally_informative_experiment_has_lower_score():
    problem = make_problem()
    posterior = initial_posterior(problem)

    cheap = Experiment(
        "cheap",
        InterventionKind.REPLAY,
        "step-cheap",
        1,
        (
            ("h1", Verdict.FAIL),
            ("h2", Verdict.PASS),
        ),
    )

    expensive = Experiment(
        "expensive",
        InterventionKind.REPLAY,
        "step-expensive",
        2,
        (
            ("h1", Verdict.FAIL),
            ("h2", Verdict.PASS),
        ),
    )

    cheap_score = information_gain_per_cost(
        posterior,
        cheap,
    )

    expensive_score = information_gain_per_cost(
        posterior,
        expensive,
    )

    assert math.isclose(
        expected_information_gain(
            posterior,
            cheap,
        ),
        expected_information_gain(
            posterior,
            expensive,
        ),
        abs_tol=1e-12,
    )

    assert cheap_score > expensive_score


def test_zero_information_experiment_has_zero_cost_adjusted_score():
    problem = make_problem()
    posterior = initial_posterior(problem)

    experiment = Experiment(
        "uninformative",
        InterventionKind.REPLAY,
        "step-uninformative",
        3,
        (
            ("h1", Verdict.PASS),
            ("h2", Verdict.PASS),
        ),
    )

    score = information_gain_per_cost(
        posterior,
        experiment,
    )

    assert math.isclose(
        score,
        0.0,
        abs_tol=1e-12,
    )

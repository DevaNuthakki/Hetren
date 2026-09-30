import math

from packages.core.hetren_diagnosis.contracts import (
    Experiment,
    InterventionKind,
    Verdict,
)

from packages.core.hetren_diagnosis.planner import (
    entropy,
    expected_information_gain,
    initial_posterior,
)

from test_diagnosis_contract import (
    make_experiments,
    make_problem,
)


def test_perfectly_discriminating_experiment_has_one_bit_eig():
    problem = make_problem()
    experiment = make_experiments()[0]

    posterior = initial_posterior(problem)

    gain = expected_information_gain(
        posterior,
        experiment,
    )

    assert math.isclose(
        gain,
        1.0,
        abs_tol=1e-12,
    )


def test_uninformative_experiment_has_zero_eig():
    problem = make_problem()

    experiment = Experiment(
        "e-uninformative",
        InterventionKind.REPLAY,
        "step-uninformative",
        1,
        (
            ("h1", Verdict.PASS),
            ("h2", Verdict.PASS),
        ),
    )

    posterior = initial_posterior(problem)

    gain = expected_information_gain(
        posterior,
        experiment,
    )

    assert math.isclose(
        gain,
        0.0,
        abs_tol=1e-12,
    )


def test_eig_cannot_exceed_current_entropy():
    problem = make_problem()
    experiment = make_experiments()[0]

    posterior = initial_posterior(problem)

    gain = expected_information_gain(
        posterior,
        experiment,
    )

    current_entropy = entropy(posterior)

    assert gain >= 0.0
    assert gain <= current_entropy + 1e-12


def test_eig_of_zero_entropy_state_is_zero():
    problem = make_problem()
    experiment = make_experiments()[0]

    certain_posterior = {
        "h1": 1.0,
        "h2": 0.0,
    }

    gain = expected_information_gain(
        certain_posterior,
        experiment,
    )

    assert math.isclose(
        gain,
        0.0,
        abs_tol=1e-12,
    )


def test_eig_is_based_on_current_posterior():
    problem = make_problem()
    experiment = make_experiments()[0]

    skewed_posterior = {
        "h1": 0.75,
        "h2": 0.25,
    }

    gain = expected_information_gain(
        skewed_posterior,
        experiment,
    )

    expected_entropy = (
        -0.75 * math.log2(0.75)
        -0.25 * math.log2(0.25)
    )

    assert math.isclose(
        gain,
        expected_entropy,
        abs_tol=1e-12,
    )

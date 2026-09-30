import math

import pytest

from packages.core.hetren_diagnosis.contracts import ContractError, Verdict
from packages.core.hetren_diagnosis.planner import (
    apply_observation,
    entropy,
    initial_posterior,
    outcome_probability,
    posterior_after_observation,
)

from test_diagnosis_contract import (
    make_experiments,
    make_observation,
    make_problem,
)


def test_initial_posterior_preserves_hypothesis_priors():
    problem = make_problem()

    posterior = initial_posterior(problem)

    assert posterior == {
        "h1": 0.5,
        "h2": 0.5,
    }

    assert math.isclose(
        sum(posterior.values()),
        1.0,
    )


def test_entropy_of_uniform_two_hypothesis_distribution_is_one_bit():
    value = entropy(
        {
            "h1": 0.5,
            "h2": 0.5,
        }
    )

    assert math.isclose(value, 1.0, abs_tol=1e-12)


def test_entropy_of_certain_distribution_is_zero():
    value = entropy(
        {
            "h1": 1.0,
            "h2": 0.0,
        }
    )

    assert math.isclose(value, 0.0, abs_tol=1e-12)


def test_entropy_is_never_negative():
    value = entropy(
        {
            "h1": 0.7,
            "h2": 0.3,
        }
    )

    assert value >= 0.0


def test_experiment_outcome_probabilities_form_distribution():
    problem = make_problem()
    experiment = make_experiments()[0]
    posterior = initial_posterior(problem)

    probability_pass = outcome_probability(
        posterior,
        experiment,
        Verdict.PASS,
    )

    probability_fail = outcome_probability(
        posterior,
        experiment,
        Verdict.FAIL,
    )

    assert math.isclose(probability_pass, 0.5)
    assert math.isclose(probability_fail, 0.5)
    assert math.isclose(
        probability_pass + probability_fail,
        1.0,
    )


def test_fail_observation_eliminates_inconsistent_hypothesis():
    problem = make_problem()
    experiment = make_experiments()[0]
    posterior = initial_posterior(problem)

    updated = posterior_after_observation(
        posterior,
        experiment,
        Verdict.FAIL,
    )

    assert updated["h1"] == 1.0
    assert updated["h2"] == 0.0
    assert math.isclose(sum(updated.values()), 1.0)


def test_pass_observation_eliminates_inconsistent_hypothesis():
    problem = make_problem()
    experiment = make_experiments()[0]
    posterior = initial_posterior(problem)

    updated = posterior_after_observation(
        posterior,
        experiment,
        Verdict.PASS,
    )

    assert updated["h1"] == 0.0
    assert updated["h2"] == 1.0
    assert math.isclose(sum(updated.values()), 1.0)


def test_impossible_observation_is_rejected():
    problem = make_problem()
    experiment = make_experiments()[0]

    certain_h1 = {
        "h1": 1.0,
        "h2": 0.0,
    }

    with pytest.raises(ContractError):
        posterior_after_observation(
            certain_h1,
            experiment,
            Verdict.PASS,
        )


def test_apply_observation_accepts_matching_experiment_digest():
    problem = make_problem()
    experiment = make_experiments()[0]
    observation = make_observation(
        verdict=Verdict.FAIL,
    )

    updated = apply_observation(
        initial_posterior(problem),
        experiment,
        observation,
    )

    assert updated["h1"] == 1.0
    assert updated["h2"] == 0.0


def test_apply_observation_rejects_wrong_experiment_key():
    problem = make_problem()
    experiment = make_experiments()[1]
    observation = make_observation(
        verdict=Verdict.FAIL,
    )

    with pytest.raises(ContractError):
        apply_observation(
            initial_posterior(problem),
            experiment,
            observation,
        )


def test_apply_observation_rejects_wrong_experiment_digest():
    problem = make_problem()
    experiment = make_experiments()[0]

    observation = make_observation(
        verdict=Verdict.FAIL,
    )

    forged = observation.__class__(
        sequence=observation.sequence,
        experiment_key=observation.experiment_key,
        experiment_sha256="1" * 64,
        verdict=observation.verdict,
        actual_cost_units=observation.actual_cost_units,
        evidence_sha256=observation.evidence_sha256,
        counterexample_sha256=observation.counterexample_sha256,
    )

    with pytest.raises(ContractError):
        apply_observation(
            initial_posterior(problem),
            experiment,
            forged,
        )

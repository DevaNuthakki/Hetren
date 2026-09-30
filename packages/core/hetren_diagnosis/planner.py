from __future__ import annotations

from collections.abc import Mapping

import math

from .contracts import (
    ContractError,
    DiagnosisProblem,
    DiagnosisStatus,
    Experiment,
    Observation,
    PlannerDecision,
    RationaleCode,
    Verdict,
)


_EPSILON = 1e-12


def _validate_distribution(
    distribution: Mapping[str, float],
    *,
    expected_keys: set[str] | None = None,
) -> dict[str, float]:
    """Validate a finite probability distribution."""
    if expected_keys is not None:
        if set(distribution) != expected_keys:
            raise ContractError(
                "probability distribution keys must exactly "
                "match hypothesis keys"
            )

    result: dict[str, float] = {}

    for key, probability in distribution.items():
        if (
            isinstance(probability, bool)
            or not isinstance(probability, (int, float))
            or not math.isfinite(probability)
            or probability < 0.0
        ):
            raise ContractError(
                f"probability for {key!r} must be finite "
                "and non-negative"
            )

        result[key] = float(probability)

    total = sum(result.values())

    if not math.isfinite(total) or total <= 0.0:
        raise ContractError(
            "probability mass must be positive"
        )

    if not math.isclose(
        total,
        1.0,
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        raise ContractError(
            "probabilities must sum to one"
        )

    return result


def initial_posterior(
    problem: DiagnosisProblem,
) -> dict[str, float]:
    """
    Construct the initial diagnostic belief state from
    the hypothesis priors.
    """
    return {
        hypothesis.key: float(hypothesis.prior_probability)
        for hypothesis in problem.hypotheses
    }


def entropy(
    distribution: Mapping[str, float],
) -> float:
    """
    Shannon entropy measured in bits.

        H(P) = -sum p(h) log2 p(h)

    Zero-probability hypotheses contribute zero.
    """
    probabilities = _validate_distribution(distribution)

    value = 0.0

    for probability in probabilities.values():
        if probability == 0.0:
            continue

        value -= probability * math.log2(probability)

    return value


def outcome_probability(
    posterior: Mapping[str, float],
    experiment: Experiment,
    verdict: Verdict,
) -> float:
    """
    Compute the probability of an experiment outcome under
    the current diagnostic belief state.

    P07.1 uses deterministic experiment predictions: each
    hypothesis predicts exactly one PASS or FAIL outcome.
    """
    predictions = dict(experiment.predicted_verdicts)

    probabilities = _validate_distribution(
        posterior,
        expected_keys=set(predictions),
    )

    return sum(
        probability
        for hypothesis_key, probability in probabilities.items()
        if predictions[hypothesis_key] is verdict
    )


def posterior_after_observation(
    posterior: Mapping[str, float],
    experiment: Experiment,
    verdict: Verdict,
) -> dict[str, float]:
    """
    Update the diagnostic belief state after observing an
    experiment result.

    Under the deterministic P07.1 model, hypotheses predicting
    the observed verdict retain their relative probability;
    hypotheses predicting the opposite verdict receive zero.
    """
    predictions = dict(experiment.predicted_verdicts)

    probabilities = _validate_distribution(
        posterior,
        expected_keys=set(predictions),
    )

    surviving_mass = sum(
        probability
        for hypothesis_key, probability in probabilities.items()
        if predictions[hypothesis_key] is verdict
    )

    if surviving_mass <= _EPSILON:
        raise ContractError(
            "observation is impossible under the current posterior"
        )

    updated: dict[str, float] = {}

    for hypothesis_key, probability in probabilities.items():
        if predictions[hypothesis_key] is verdict:
            updated[hypothesis_key] = (
                probability / surviving_mass
            )
        else:
            updated[hypothesis_key] = 0.0

    return updated


def apply_observation(
    posterior: Mapping[str, float],
    experiment: Experiment,
    observation: Observation,
) -> dict[str, float]:
    """
    Apply a verified observation to the diagnostic belief state.

    The observation must identify the same experiment and carry
    the experiment's exact SHA-256 digest.
    """
    if observation.experiment_key != experiment.key:
        raise ContractError(
            "observation experiment key does not match experiment"
        )

    if (
        observation.experiment_sha256
        != experiment.experiment_sha256
    ):
        raise ContractError(
            "observation experiment digest does not match "
            "experiment definition"
        )

    return posterior_after_observation(
        posterior,
        experiment,
        observation.verdict,
    )


def expected_information_gain(
    posterior: Mapping[str, float],
    experiment: Experiment,
) -> float:
    """
    Compute the expected information gain of an experiment.

        EIG(E)
          = H(P)
          - sum_o P(o | E) H(P | o, E)

    The result is measured in bits.

    P07.1 uses deterministic PASS/FAIL predictions for each
    hypothesis, so the possible outcomes are Verdict.PASS
    and Verdict.FAIL.
    """
    predictions = dict(experiment.predicted_verdicts)

    probabilities = _validate_distribution(
        posterior,
        expected_keys=set(predictions),
    )

    prior_entropy = entropy(probabilities)

    expected_posterior_entropy = 0.0

    for verdict in (Verdict.PASS, Verdict.FAIL):
        probability = outcome_probability(
            probabilities,
            experiment,
            verdict,
        )

        if probability <= _EPSILON:
            continue

        updated = posterior_after_observation(
            probabilities,
            experiment,
            verdict,
        )

        expected_posterior_entropy += (
            probability * entropy(updated)
        )

    information_gain = (
        prior_entropy
        - expected_posterior_entropy
    )

    if information_gain < -_EPSILON:
        raise ContractError(
            "expected information gain cannot be negative"
        )

    if information_gain > prior_entropy + _EPSILON:
        raise ContractError(
            "expected information gain cannot exceed "
            "current entropy"
        )

    if abs(information_gain) <= _EPSILON:
        return 0.0

    if abs(information_gain - prior_entropy) <= _EPSILON:
        return prior_entropy

    return information_gain


def information_gain_per_cost(
    posterior: Mapping[str, float],
    experiment: Experiment,
) -> float:
    """
    Compute expected information gained per unit experiment cost.

        score(E) = EIG(E) / Cost(E)

    This is a local utility for comparing currently available
    experiments. It is not a claim of globally optimal
    sequential diagnosis.
    """
    gain = expected_information_gain(
        posterior,
        experiment,
    )

    if experiment.cost_units <= 0:
        raise ContractError(
            "experiment cost must be positive"
        )

    return gain / experiment.cost_units


PLANNER_KEY = "information_gain_per_cost"
PLANNER_VERSION = "0.1.0"


def rank_eligible_experiments(
    problem: DiagnosisProblem,
    posterior: Mapping[str, float],
    *,
    remaining_budget: int,
    excluded_experiment_keys: frozenset[str] = frozenset(),
) -> tuple[tuple[Experiment, float, float], ...]:
    """
    Rank currently executable experiments.

    Ranking order:

    1. highest information gain per unit cost;
    2. highest raw expected information gain;
    3. lowest execution cost;
    4. lexicographically smallest experiment key.

    Only experiments that fit within the remaining budget and have
    not already been excluded are eligible.

    This is a deterministic myopic selection policy. It does not
    claim globally optimal sequential diagnosis.
    """
    if (
        isinstance(remaining_budget, bool)
        or not isinstance(remaining_budget, int)
        or remaining_budget < 0
    ):
        raise ContractError(
            "remaining_budget must be a non-negative integer"
        )

    if not isinstance(
        excluded_experiment_keys,
        frozenset,
    ):
        raise ContractError(
            "excluded_experiment_keys must be a frozenset"
        )

    ranked = []

    for experiment in problem.experiments:
        if experiment.key in excluded_experiment_keys:
            continue

        if experiment.cost_units > remaining_budget:
            continue

        gain = expected_information_gain(
            posterior,
            experiment,
        )

        score = information_gain_per_cost(
            posterior,
            experiment,
        )

        ranked.append(
            (
                experiment,
                gain,
                score,
            )
        )

    ranked.sort(
        key=lambda item: (
            -item[2],
            -item[1],
            item[0].cost_units,
            item[0].key,
        )
    )

    return tuple(ranked)


def select_active_experiment(
    problem: DiagnosisProblem,
    posterior: Mapping[str, float],
    *,
    remaining_budget: int,
    excluded_experiment_keys: frozenset[str] = frozenset(),
) -> PlannerDecision:
    """
    Produce an ACTIVE PlannerDecision for the best currently
    eligible experiment.

    Terminal states are deliberately handled elsewhere.
    """
    ranked = rank_eligible_experiments(
        problem,
        posterior,
        remaining_budget=remaining_budget,
        excluded_experiment_keys=excluded_experiment_keys,
    )

    if not ranked:
        raise ContractError(
            "no eligible experiment is available"
        )

    candidates = tuple(
        sorted(
            experiment.key
            for experiment, _, _ in ranked
        )
    )

    selected, gain, score = ranked[0]

    return PlannerDecision(
        planner_key=PLANNER_KEY,
        planner_version=PLANNER_VERSION,
        candidate_experiment_keys=candidates,
        experiment_key=selected.key,
        expected_information_gain=gain,
        score_per_cost=score,
        rationale=RationaleCode.INFORMATION_GAIN_PER_COST,
        status=DiagnosisStatus.ACTIVE,
        problem_sha256=problem.problem_sha256,
    )

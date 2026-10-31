from __future__ import annotations

from collections.abc import Sequence

from .contracts import (
    ContractError,
    DiagnosisProblem,
    DiagnosisStatus,
    Observation,
    PlannerDecision,
    RationaleCode,
)
from .planner import (
    PLANNER_KEY,
    PLANNER_VERSION,
    apply_observation,
    initial_posterior,
    rank_eligible_experiments,
)


_EPSILON = 1e-12


def _is_diagnosed(
    posterior: dict[str, float],
) -> bool:
    """
    A diagnosis is complete when exactly one hypothesis
    retains non-negligible posterior probability.
    """
    surviving = sum(
        probability > _EPSILON
        for probability in posterior.values()
    )

    return surviving == 1


def replay_observations(
    problem: DiagnosisProblem,
    observations: Sequence[Observation] = (),
) -> dict[str, float]:
    """
    Reconstruct the current posterior by replaying observations
    in their required sequence.

    This function is deliberately deterministic and side-effect free.
    """
    posterior = initial_posterior(problem)

    experiments_by_key = {
        experiment.key: experiment
        for experiment in problem.experiments
    }

    seen_experiments: set[str] = set()
    spent_cost_units = 0

    for expected_sequence, observation in enumerate(observations):
        if not isinstance(observation, Observation):
            raise ContractError(
                "observations must contain Observation instances"
            )

        if observation.sequence != expected_sequence:
            raise ContractError(
                "observation sequences must be contiguous "
                "starting at zero"
            )

        experiment = experiments_by_key.get(
            observation.experiment_key
        )

        if experiment is None:
            raise ContractError(
                "observation references an unknown experiment"
            )

        if observation.experiment_key in seen_experiments:
            raise ContractError(
                "an experiment cannot be observed more than once"
            )

        spent_cost_units += observation.actual_cost_units

        if spent_cost_units > problem.budget_units:
            raise ContractError(
                "observation costs exceed diagnosis budget"
            )

        posterior = apply_observation(
            posterior,
            experiment,
            observation,
        )

        seen_experiments.add(
            observation.experiment_key
        )

    return posterior


def remaining_budget_units(
    problem: DiagnosisProblem,
    observations: Sequence[Observation] = (),
) -> int:
    """
    Compute remaining budget from actual observation costs.
    """
    spent = 0

    for observation in observations:
        if not isinstance(observation, Observation):
            raise ContractError(
                "observations must contain Observation instances"
            )

        spent += observation.actual_cost_units

    remaining = problem.budget_units - spent

    if remaining < 0:
        raise ContractError(
            "observation costs exceed diagnosis budget"
        )

    return remaining


def select_next_decision(
    problem: DiagnosisProblem,
    observations: Sequence[Observation] = (),
) -> PlannerDecision:
    """
    Produce the next sequential diagnosis decision.

    Lifecycle order:

    1. Replay observations.
    2. Determine remaining actual-cost budget.
    3. Diagnose if only one hypothesis remains.
    4. Rank currently executable experiments.
    5. Report budget exhaustion when none remain.
    6. Report inconclusive when the best experiment has
       effectively zero expected information gain.
    7. Otherwise return the deterministic ACTIVE decision.
    """
    observations = tuple(observations)

    posterior = replay_observations(
        problem,
        observations,
    )

    remaining_budget = remaining_budget_units(
        problem,
        observations,
    )

    excluded_experiment_keys = frozenset(
        observation.experiment_key
        for observation in observations
    )

    if _is_diagnosed(posterior):
        return PlannerDecision(
            planner_key=PLANNER_KEY,
            planner_version=PLANNER_VERSION,
            candidate_experiment_keys=(),
            experiment_key=None,
            expected_information_gain=0.0,
            score_per_cost=0.0,
            rationale=RationaleCode.COMPLETE,
            status=DiagnosisStatus.DIAGNOSED,
            problem_sha256=problem.problem_sha256,
        )

    if remaining_budget == 0:
        return PlannerDecision(
            planner_key=PLANNER_KEY,
            planner_version=PLANNER_VERSION,
            candidate_experiment_keys=(),
            experiment_key=None,
            expected_information_gain=0.0,
            score_per_cost=0.0,
            rationale=RationaleCode.BUDGET_EXHAUSTED,
            status=DiagnosisStatus.BUDGET_EXHAUSTED,
            problem_sha256=problem.problem_sha256,
        )

    ranked = rank_eligible_experiments(
        problem,
        posterior,
        remaining_budget=remaining_budget,
        excluded_experiment_keys=excluded_experiment_keys,
    )

    candidate_keys = tuple(
        sorted(
            experiment.key
            for experiment, _, _ in ranked
        )
    )

    if not ranked:
        return PlannerDecision(
            planner_key=PLANNER_KEY,
            planner_version=PLANNER_VERSION,
            candidate_experiment_keys=(),
            experiment_key=None,
            expected_information_gain=0.0,
            score_per_cost=0.0,
            rationale=RationaleCode.BUDGET_EXHAUSTED,
            status=DiagnosisStatus.BUDGET_EXHAUSTED,
            problem_sha256=problem.problem_sha256,
        )

    selected, gain, score = ranked[0]

    if gain <= _EPSILON:
        return PlannerDecision(
            planner_key=PLANNER_KEY,
            planner_version=PLANNER_VERSION,
            candidate_experiment_keys=candidate_keys,
            experiment_key=None,
            expected_information_gain=0.0,
            score_per_cost=0.0,
            rationale=RationaleCode.INFORMATION_GAIN_PER_COST,
            status=DiagnosisStatus.INCONCLUSIVE,
            problem_sha256=problem.problem_sha256,
        )

    rationale = (
        RationaleCode.BOOTSTRAP
        if not observations
        else RationaleCode.INFORMATION_GAIN_PER_COST
    )

    return PlannerDecision(
        planner_key=PLANNER_KEY,
        planner_version=PLANNER_VERSION,
        candidate_experiment_keys=candidate_keys,
        experiment_key=selected.key,
        expected_information_gain=gain,
        score_per_cost=score,
        rationale=rationale,
        status=DiagnosisStatus.ACTIVE,
        problem_sha256=problem.problem_sha256,
    )

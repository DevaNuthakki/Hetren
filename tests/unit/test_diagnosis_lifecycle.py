import math

import pytest

from packages.core.hetren_diagnosis.contracts import (
    AgentTrace,
    ContractError,
    DiagnosisProblem,
    DiagnosisStatus,
    EventKind,
    Experiment,
    Hypothesis,
    InterventionKind,
    Observation,
    RationaleCode,
    TraceEvent,
    Verdict,
)
from packages.core.hetren_diagnosis.lifecycle import (
    remaining_budget_units,
    replay_observations,
    select_next_decision,
)


DIGEST = "0" * 64


def make_event(sequence: int = 0) -> TraceEvent:
    return TraceEvent(
        sequence=sequence,
        kind=EventKind.TOOL_CALL,
        component="planner",
        operation="search",
        input_sha256=DIGEST,
        output_sha256=DIGEST,
        state_before_sha256=DIGEST,
        state_after_sha256=DIGEST,
    )


def make_two_hypothesis_problem():
    return DiagnosisProblem(
        trace=AgentTrace(
            "run-lifecycle",
            (make_event(),),
        ),
        hypotheses=(
            Hypothesis(
                "h1",
                "tool selection fault",
                0.5,
            ),
            Hypothesis(
                "h2",
                "parameter transformation fault",
                0.5,
            ),
        ),
        experiments=(
            Experiment(
                "e1",
                InterventionKind.REPLAY,
                "step-0",
                1,
                (
                    ("h1", Verdict.FAIL),
                    ("h2", Verdict.PASS),
                ),
            ),
            Experiment(
                "e2",
                InterventionKind.OVERRIDE_PARAMETER,
                "step-1",
                2,
                (
                    ("h1", Verdict.PASS),
                    ("h2", Verdict.FAIL),
                ),
            ),
        ),
        budget_units=3,
    )


def make_three_hypothesis_problem():
    return DiagnosisProblem(
        trace=AgentTrace(
            "run-lifecycle-3",
            (make_event(),),
        ),
        hypotheses=(
            Hypothesis("h1", "fault one", 1 / 3),
            Hypothesis("h2", "fault two", 1 / 3),
            Hypothesis("h3", "fault three", 1 / 3),
        ),
        experiments=(
            Experiment(
                "e1",
                InterventionKind.REPLAY,
                "step-0",
                1,
                (
                    ("h1", Verdict.PASS),
                    ("h2", Verdict.PASS),
                    ("h3", Verdict.FAIL),
                ),
            ),
            Experiment(
                "e2",
                InterventionKind.OVERRIDE_PARAMETER,
                "step-1",
                1,
                (
                    ("h1", Verdict.PASS),
                    ("h2", Verdict.FAIL),
                    ("h3", Verdict.PASS),
                ),
            ),
        ),
        budget_units=2,
    )


def observation_for(
    problem,
    experiment_key,
    verdict,
    *,
    sequence=0,
    actual_cost_units=1,
):
    experiment = next(
        experiment
        for experiment in problem.experiments
        if experiment.key == experiment_key
    )

    return Observation(
        sequence=sequence,
        experiment_key=experiment.key,
        experiment_sha256=experiment.experiment_sha256,
        verdict=verdict,
        actual_cost_units=actual_cost_units,
        evidence_sha256=DIGEST,
    )


def test_empty_history_bootstraps_active_selection():
    problem = make_two_hypothesis_problem()

    decision = select_next_decision(problem)

    assert decision.status is DiagnosisStatus.ACTIVE
    assert decision.rationale is RationaleCode.BOOTSTRAP
    assert decision.experiment_key == "e1"
    assert decision.candidate_experiment_keys == (
        "e1",
        "e2",
    )


def test_observation_reconstructs_posterior():
    problem = make_two_hypothesis_problem()

    observation = observation_for(
        problem,
        "e1",
        Verdict.FAIL,
    )

    posterior = replay_observations(
        problem,
        (observation,),
    )

    assert posterior == {
        "h1": 1.0,
        "h2": 0.0,
    }


def test_diagnosed_state_has_no_next_experiment():
    problem = make_two_hypothesis_problem()

    observation = observation_for(
        problem,
        "e1",
        Verdict.FAIL,
    )

    decision = select_next_decision(
        problem,
        (observation,),
    )

    assert decision.status is DiagnosisStatus.DIAGNOSED
    assert decision.rationale is RationaleCode.COMPLETE
    assert decision.experiment_key is None
    assert decision.expected_information_gain == 0.0
    assert decision.score_per_cost == 0.0


def test_previous_experiment_is_excluded_from_next_candidates():
    problem = make_three_hypothesis_problem()

    observation = observation_for(
        problem,
        "e1",
        Verdict.PASS,
    )

    decision = select_next_decision(
        problem,
        (observation,),
    )

    assert decision.status is DiagnosisStatus.ACTIVE
    assert decision.experiment_key == "e2"
    assert decision.candidate_experiment_keys == ("e2",)
    assert decision.rationale is RationaleCode.INFORMATION_GAIN_PER_COST


def test_actual_cost_controls_remaining_budget():
    problem = make_two_hypothesis_problem()

    observation = observation_for(
        problem,
        "e1",
        Verdict.PASS,
        actual_cost_units=2,
    )

    assert remaining_budget_units(
        problem,
        (observation,),
    ) == 1


def test_actual_cost_exhaustion_does_not_override_diagnosis():
    problem = make_two_hypothesis_problem()

    observation = observation_for(
        problem,
        "e1",
        Verdict.PASS,
        actual_cost_units=3,
    )

    assert remaining_budget_units(
        problem,
        (observation,),
    ) == 0

    assert replay_observations(
        problem,
        (observation,),
    ) == {
        "h1": 0.0,
        "h2": 1.0,
    }

    decision = select_next_decision(
        problem,
        (observation,),
    )

    assert decision.status is DiagnosisStatus.DIAGNOSED
    assert decision.rationale is RationaleCode.COMPLETE
    assert decision.experiment_key is None
    assert decision.candidate_experiment_keys == ()
    assert decision.expected_information_gain == 0.0
    assert decision.score_per_cost == 0.0


def test_zero_information_experiment_is_inconclusive():
    problem = DiagnosisProblem(
        trace=AgentTrace(
            "run-inconclusive",
            (make_event(),),
        ),
        hypotheses=(
            Hypothesis("h1", "fault one", 0.5),
            Hypothesis("h2", "fault two", 0.5),
        ),
        experiments=(
            Experiment(
                "e1",
                InterventionKind.REPLAY,
                "step-0",
                1,
                (
                    ("h1", Verdict.PASS),
                    ("h2", Verdict.PASS),
                ),
            ),
        ),
        budget_units=1,
    )

    decision = select_next_decision(problem)

    assert decision.status is DiagnosisStatus.INCONCLUSIVE
    assert decision.rationale is RationaleCode.INFORMATION_GAIN_PER_COST
    assert decision.experiment_key is None
    assert decision.candidate_experiment_keys == ("e1",)


def test_zero_budget_reports_exhaustion_when_posterior_remains_ambiguous():
    problem = DiagnosisProblem(
        trace=AgentTrace(
            "run-zero-budget-ambiguous",
            (make_event(),),
        ),
        hypotheses=(
            Hypothesis(
                "h1",
                "fault one",
                0.5,
            ),
            Hypothesis(
                "h2",
                "fault two",
                0.5,
            ),
        ),
        experiments=(
            Experiment(
                "e1",
                InterventionKind.REPLAY,
                "step-0",
                1,
                (
                    (
                        "h1",
                        Verdict.PASS,
                    ),
                    (
                        "h2",
                        Verdict.PASS,
                    ),
                ),
            ),
        ),
        budget_units=1,
    )

    observation = observation_for(
        problem,
        "e1",
        Verdict.PASS,
        actual_cost_units=1,
    )

    assert remaining_budget_units(
        problem,
        (observation,),
    ) == 0

    assert replay_observations(
        problem,
        (observation,),
    ) == {
        "h1": 0.5,
        "h2": 0.5,
    }

    decision = select_next_decision(
        problem,
        (observation,),
    )

    assert (
        decision.status
        is DiagnosisStatus.BUDGET_EXHAUSTED
    )
    assert (
        decision.rationale
        is RationaleCode.BUDGET_EXHAUSTED
    )
    assert decision.experiment_key is None
    assert decision.candidate_experiment_keys == ()
    assert decision.expected_information_gain == 0.0
    assert decision.score_per_cost == 0.0


def test_observation_sequences_must_be_contiguous():
    problem = make_two_hypothesis_problem()

    observation = observation_for(
        problem,
        "e1",
        Verdict.PASS,
        sequence=1,
    )

    with pytest.raises(ContractError):
        select_next_decision(
            problem,
            (observation,),
        )


def test_experiment_cannot_be_observed_twice():
    problem = make_two_hypothesis_problem()

    first = observation_for(
        problem,
        "e1",
        Verdict.PASS,
        sequence=0,
    )

    second = observation_for(
        problem,
        "e1",
        Verdict.FAIL,
        sequence=1,
    )

    with pytest.raises(ContractError):
        select_next_decision(
            problem,
            (first, second),
        )


def test_unknown_observation_experiment_is_rejected():
    problem = make_two_hypothesis_problem()

    observation = Observation(
        sequence=0,
        experiment_key="does-not-exist",
        experiment_sha256=DIGEST,
        verdict=Verdict.FAIL,
        actual_cost_units=1,
        evidence_sha256=DIGEST,
    )

    with pytest.raises(ContractError):
        select_next_decision(
            problem,
            (observation,),
        )


def test_observation_cost_cannot_exceed_total_budget():
    problem = make_two_hypothesis_problem()

    observation = observation_for(
        problem,
        "e1",
        Verdict.PASS,
        actual_cost_units=4,
    )

    with pytest.raises(ContractError):
        select_next_decision(
            problem,
            (observation,),
        )


def test_lifecycle_decision_is_deterministic():
    problem = make_two_hypothesis_problem()

    first = select_next_decision(problem)
    second = select_next_decision(problem)

    assert first == second


def test_diagnosed_decision_preserves_problem_identity():
    problem = make_two_hypothesis_problem()

    observation = observation_for(
        problem,
        "e1",
        Verdict.FAIL,
    )

    decision = select_next_decision(
        problem,
        (observation,),
    )

    assert decision.problem_sha256 == problem.problem_sha256


def test_remaining_budget_rejects_over_budget_history():
    problem = make_two_hypothesis_problem()

    observation = observation_for(
        problem,
        "e1",
        Verdict.PASS,
        actual_cost_units=4,
    )

    with pytest.raises(ContractError):
        remaining_budget_units(
            problem,
            (observation,),
        )


def test_three_hypothesis_update_preserves_probability_mass():
    problem = make_three_hypothesis_problem()

    observation = observation_for(
        problem,
        "e1",
        Verdict.PASS,
    )

    posterior = replay_observations(
        problem,
        (observation,),
    )

    assert math.isclose(
        sum(posterior.values()),
        1.0,
        abs_tol=1e-12,
    )
    assert posterior["h1"] == 0.5
    assert posterior["h2"] == 0.5
    assert posterior["h3"] == 0.0

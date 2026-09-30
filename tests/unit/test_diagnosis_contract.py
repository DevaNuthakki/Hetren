from dataclasses import FrozenInstanceError

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
    PlannerDecision,
    RationaleCode,
    TraceEvent,
    Verdict,
    canonical_sha256,
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


def make_hypotheses():
    return (
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
    )


def make_experiments():
    return (
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
    )


def make_problem():
    return DiagnosisProblem(
        trace=AgentTrace(
            "run-1",
            (make_event(),),
        ),
        hypotheses=make_hypotheses(),
        experiments=make_experiments(),
        budget_units=3,
    )


def make_observation(
    *,
    verdict=Verdict.FAIL,
    counterexample_sha256=None,
):
    experiment = make_experiments()[0]

    return Observation(
        sequence=0,
        experiment_key=experiment.key,
        experiment_sha256=experiment.experiment_sha256,
        verdict=verdict,
        actual_cost_units=1,
        evidence_sha256=DIGEST,
        counterexample_sha256=counterexample_sha256,
    )


def test_trace_sequences_are_contiguous():
    AgentTrace(
        "run-1",
        (make_event(0), make_event(1)),
    )

    with pytest.raises(ContractError):
        AgentTrace(
            "run-1",
            (make_event(0), make_event(2)),
        )


def test_trace_has_deterministic_digest():
    trace_a = AgentTrace(
        "run-1",
        (make_event(),),
    )

    trace_b = AgentTrace(
        "run-1",
        (make_event(),),
    )

    assert trace_a.trace_sha256 == trace_b.trace_sha256


def test_experiment_has_deterministic_definition_digest():
    experiments_a = make_experiments()
    experiments_b = make_experiments()

    assert (
        experiments_a[0].experiment_sha256
        == experiments_b[0].experiment_sha256
    )


def test_problem_contains_no_ground_truth():
    fields = DiagnosisProblem.__dataclass_fields__

    assert "true_hypothesis" not in fields
    assert "ground_truth" not in fields


def test_experiments_must_cover_every_hypothesis():
    with pytest.raises(ContractError):
        DiagnosisProblem(
            trace=AgentTrace(
                "run-1",
                (make_event(),),
            ),
            hypotheses=make_hypotheses(),
            experiments=(
                Experiment(
                    "e1",
                    InterventionKind.REPLAY,
                    "step-0",
                    1,
                    (("h1", Verdict.FAIL),),
                ),
            ),
            budget_units=1,
        )


def test_failed_observation_does_not_require_counterexample():
    observation = make_observation(
        verdict=Verdict.FAIL,
    )

    assert observation.counterexample_sha256 is None


def test_optional_counterexample_must_be_valid_digest():
    observation = make_observation(
        verdict=Verdict.FAIL,
        counterexample_sha256=DIGEST,
    )

    assert observation.counterexample_sha256 == DIGEST


def test_observation_requires_experiment_digest():
    with pytest.raises(ContractError):
        Observation(
            sequence=0,
            experiment_key="e1",
            experiment_sha256="invalid",
            verdict=Verdict.FAIL,
            actual_cost_units=1,
            evidence_sha256=DIGEST,
        )


def test_active_decision_requires_selected_candidate():
    with pytest.raises(ContractError):
        PlannerDecision(
            planner_key="portfolio-information-gain",
            planner_version="1.0.0",
            candidate_experiment_keys=("e1", "e2"),
            experiment_key=None,
            expected_information_gain=0.0,
            score_per_cost=0.0,
            rationale=RationaleCode.INFORMATION_GAIN_PER_COST,
            status=DiagnosisStatus.ACTIVE,
            problem_sha256=DIGEST,
        )


def test_selected_experiment_must_be_in_candidate_set():
    with pytest.raises(ContractError):
        PlannerDecision(
            planner_key="portfolio-information-gain",
            planner_version="1.0.0",
            candidate_experiment_keys=("e1",),
            experiment_key="e2",
            expected_information_gain=1.0,
            score_per_cost=1.0,
            rationale=RationaleCode.INFORMATION_GAIN_PER_COST,
            status=DiagnosisStatus.ACTIVE,
            problem_sha256=DIGEST,
        )


def test_terminal_decision_cannot_select_experiment():
    decision = PlannerDecision(
        planner_key="portfolio-information-gain",
        planner_version="1.0.0",
        candidate_experiment_keys=("e1", "e2"),
        experiment_key=None,
        expected_information_gain=0.0,
        score_per_cost=0.0,
        rationale=RationaleCode.COMPLETE,
        status=DiagnosisStatus.DIAGNOSED,
        problem_sha256=DIGEST,
    )

    assert decision.experiment_key is None


def test_contract_objects_are_immutable():
    event = make_event()

    with pytest.raises(FrozenInstanceError):
        event.component = "mutated"


def test_canonical_hash_is_mapping_order_invariant():
    assert canonical_sha256(
        {"b": 2, "a": 1}
    ) == canonical_sha256(
        {"a": 1, "b": 2}
    )


def test_problem_is_valid():
    problem = make_problem()

    assert problem.budget_units == 3
    assert len(problem.hypotheses) == 2
    assert len(problem.experiments) == 2
    assert len(problem.problem_sha256) == 64


def test_failed_observation_can_carry_counterexample_evidence():
    observation = make_observation(
        verdict=Verdict.FAIL,
        counterexample_sha256=DIGEST,
    )

    assert observation.verdict is Verdict.FAIL


def test_problem_hash_is_deterministic():
    assert (
        make_problem().problem_sha256
        == make_problem().problem_sha256
    )


if __name__ == "__main__":
    pytest.main()

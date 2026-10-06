"""Integration tests for the first executable diagnosis slice."""

import inspect

import pytest

import packages.engines.behavioral.deterministic_tool_agent as fixture
from packages.core.hetren_diagnosis.contracts import (
    ContractError,
    DiagnosisStatus,
    EventKind,
    InterventionKind,
    Verdict,
)
from packages.core.hetren_diagnosis.lifecycle import (
    select_next_decision,
)
from packages.engines.behavioral.deterministic_tool_agent import (
    FaultMode,
    build_diagnosis_problem,
    run_diagnosis_demo,
    run_tool_agent,
)


@pytest.mark.parametrize(
    "fault_mode",
    (
        FaultMode.TOOL_SELECTION,
        FaultMode.PARAMETER_TRANSFORMATION,
    ),
)
def test_both_latent_faults_produce_same_visible_baseline_failure(
    fault_mode,
):
    run = run_tool_agent(
        fault_mode,
        run_id=f"baseline-{fault_mode.value}",
    )

    assert run.output == 2
    assert run.expected_output == 12
    assert run.passed is False


def test_execution_trace_contains_real_controlled_agent_events():
    run = run_tool_agent(
        FaultMode.TOOL_SELECTION,
        run_id="trace-test",
    )

    assert tuple(
        event.sequence
        for event in run.trace.events
    ) == (0, 1, 2, 3)

    assert tuple(
        event.kind
        for event in run.trace.events
    ) == (
        EventKind.DECISION,
        EventKind.TOOL_CALL,
        EventKind.TOOL_RESULT,
        EventKind.TERMINATION,
    )

    assert run.trace.run_id == "trace-test"
    assert len(run.trace.trace_sha256) == 64


def test_controlled_execution_is_deterministic():
    first = run_tool_agent(
        FaultMode.PARAMETER_TRANSFORMATION,
        run_id="deterministic-run",
    )

    second = run_tool_agent(
        FaultMode.PARAMETER_TRANSFORMATION,
        run_id="deterministic-run",
    )

    assert first == second
    assert (
        first.trace.trace_sha256
        == second.trace.trace_sha256
    )
    assert (
        first.execution_evidence_sha256
        == second.execution_evidence_sha256
    )


def test_existing_planner_selects_discriminating_real_experiment():
    baseline = run_tool_agent(
        FaultMode.TOOL_SELECTION,
        run_id="planner-baseline",
    )

    problem = build_diagnosis_problem(
        baseline.trace
    )

    decision = select_next_decision(problem)

    assert decision.status is DiagnosisStatus.ACTIVE
    assert decision.experiment_key == "e1-replace-tool"
    assert decision.candidate_experiment_keys == (
        "e1-replace-tool",
        "e2-override-parameter",
    )


@pytest.mark.parametrize(
    (
        "fault_mode",
        "expected_hypothesis",
        "expected_verdict",
    ),
    (
        (
            FaultMode.TOOL_SELECTION,
            "tool_selection_fault",
            Verdict.PASS,
        ),
        (
            FaultMode.PARAMETER_TRANSFORMATION,
            "parameter_transformation_fault",
            Verdict.FAIL,
        ),
    ),
)
def test_actual_intervention_drives_correct_diagnosis(
    fault_mode,
    expected_hypothesis,
    expected_verdict,
):
    result = run_diagnosis_demo(
        fault_mode,
        run_id=f"diagnosis-{fault_mode.value}",
    )

    assert (
        result.initial_decision.status
        is DiagnosisStatus.ACTIVE
    )

    assert (
        result.experiment_result.observation.verdict
        is expected_verdict
    )

    assert (
        result.final_decision.status
        is DiagnosisStatus.DIAGNOSED
    )

    assert (
        result.diagnosed_hypothesis_key
        == expected_hypothesis
    )

    posterior = dict(result.posterior)

    assert posterior[expected_hypothesis] == 1.0

    other = (
        "parameter_transformation_fault"
        if expected_hypothesis
        == "tool_selection_fault"
        else "tool_selection_fault"
    )

    assert posterior[other] == 0.0


def test_observation_evidence_is_derived_from_executed_run():
    result = run_diagnosis_demo(
        FaultMode.TOOL_SELECTION,
        run_id="evidence-run",
    )

    observation = (
        result.experiment_result.observation
    )

    agent_run = (
        result.experiment_result.agent_run
    )

    assert (
        observation.evidence_sha256
        == agent_run.execution_evidence_sha256
    )

    assert observation.counterexample_sha256 is None


def test_failed_diagnostic_execution_preserves_counterexample():
    result = run_diagnosis_demo(
        FaultMode.PARAMETER_TRANSFORMATION,
        run_id="counterexample-run",
    )

    observation = (
        result.experiment_result.observation
    )

    assert observation.verdict is Verdict.FAIL
    assert observation.counterexample_sha256 is not None
    assert len(observation.counterexample_sha256) == 64


@pytest.mark.parametrize(
    (
        "fault_mode",
        "expected_hypothesis",
    ),
    (
        (
            FaultMode.TOOL_SELECTION,
            "tool_selection_fault",
        ),
        (
            FaultMode.PARAMETER_TRANSFORMATION,
            "parameter_transformation_fault",
        ),
    ),
)
def test_real_observation_matches_preregistered_prediction(
    fault_mode,
    expected_hypothesis,
):
    result = run_diagnosis_demo(
        fault_mode,
        run_id=f"prediction-{fault_mode.value}",
    )

    selected_key = (
        result.initial_decision.experiment_key
    )

    experiment = next(
        experiment
        for experiment in result.problem.experiments
        if experiment.key == selected_key
    )

    predicted = dict(
        experiment.predicted_verdicts
    )

    assert (
        predicted[expected_hypothesis]
        is result.experiment_result.observation.verdict
    )


def test_unsupported_intervention_is_rejected():
    with pytest.raises(ContractError):
        run_tool_agent(
            FaultMode.TOOL_SELECTION,
            run_id="unsupported-intervention",
            intervention=InterventionKind.REMOVE_STEP,
        )


def test_fixture_has_no_external_or_nondeterministic_runtime_dependency():
    source = inspect.getsource(fixture)

    forbidden = (
        "import random",
        "from random",
        "import socket",
        "from socket",
        "import subprocess",
        "from subprocess",
        "import requests",
        "import httpx",
        "time.time",
        "datetime.now",
    )

    for token in forbidden:
        assert token not in source

"""Integration tests for the multi-step incident-triage diagnosis slice."""

import inspect
from pathlib import Path

import pytest

from environments.agent.incident_triage import (
    IncidentFaultMode,
    expected_incident_ids,
    run_incident_triage,
)
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
from packages.engines.behavioral.incident_triage_diagnosis import (
    build_diagnosis_problem,
    execute_selected_experiment,
    run_diagnosis_demo,
)


@pytest.mark.parametrize(
    "fault_mode",
    (
        IncidentFaultMode.FILTER_TOOL_SELECTION,
        IncidentFaultMode.THRESHOLD_TRANSFORMATION,
    ),
)
def test_both_latent_faults_produce_same_visible_baseline_report(
    fault_mode,
):
    run = run_incident_triage(
        fault_mode,
        run_id=f"baseline-{fault_mode.value}",
    )

    assert run.report.incident_ids == (
        "INC-1001",
        "INC-1004",
    )
    assert run.report.count == 2
    assert run.passed is False


def test_workflow_trace_contains_real_multi_step_events():
    run = run_incident_triage(
        IncidentFaultMode.FILTER_TOOL_SELECTION,
        run_id="trace-test",
    )

    assert tuple(
        event.sequence
        for event in run.trace.events
    ) == tuple(range(10))

    assert tuple(
        event.kind
        for event in run.trace.events
    ) == (
        EventKind.TOOL_CALL,
        EventKind.TOOL_RESULT,
        EventKind.TOOL_CALL,
        EventKind.TOOL_RESULT,
        EventKind.DECISION,
        EventKind.TOOL_CALL,
        EventKind.TOOL_RESULT,
        EventKind.TOOL_CALL,
        EventKind.TOOL_RESULT,
        EventKind.TERMINATION,
    )

    assert len(run.trace.trace_sha256) == 64


def test_existing_planner_selects_real_discriminating_experiment():
    baseline = run_incident_triage(
        IncidentFaultMode.FILTER_TOOL_SELECTION,
        run_id="planner-test",
    )

    problem = build_diagnosis_problem(
        baseline.trace
    )

    decision = select_next_decision(
        problem
    )

    assert problem.budget_units == 2

    assert (
        decision.status
        is DiagnosisStatus.ACTIVE
    )

    assert (
        decision.experiment_key
        == "e1-replace-filter-tool"
    )

    assert (
        decision.candidate_experiment_keys
        == (
            "e1-replace-filter-tool",
            "e2-override-threshold",
        )
    )


@pytest.mark.parametrize(
    (
        "fault_mode",
        "expected_hypothesis",
        "expected_verdict",
    ),
    (
        (
            IncidentFaultMode.FILTER_TOOL_SELECTION,
            "filter_tool_selection_fault",
            Verdict.PASS,
        ),
        (
            IncidentFaultMode.THRESHOLD_TRANSFORMATION,
            "threshold_transformation_fault",
            Verdict.FAIL,
        ),
    ),
)
def test_actual_intervention_drives_correct_workflow_diagnosis(
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

    posterior = dict(
        result.posterior
    )

    assert posterior[expected_hypothesis] == 1.0

    other = (
        "threshold_transformation_fault"
        if expected_hypothesis
        == "filter_tool_selection_fault"
        else "filter_tool_selection_fault"
    )

    assert posterior[other] == 0.0


@pytest.mark.parametrize(
    (
        "fault_mode",
        "expected_verdict",
        "has_counterexample",
    ),
    (
        (
            IncidentFaultMode.FILTER_TOOL_SELECTION,
            Verdict.PASS,
            False,
        ),
        (
            IncidentFaultMode.THRESHOLD_TRANSFORMATION,
            Verdict.FAIL,
            True,
        ),
    ),
)
def test_observation_evidence_is_from_executed_workflow(
    fault_mode,
    expected_verdict,
    has_counterexample,
):
    result = run_diagnosis_demo(
        fault_mode,
        run_id=f"evidence-{fault_mode.value}",
    )

    observation = (
        result.experiment_result.observation
    )

    agent_run = (
        result.experiment_result.agent_run
    )

    assert observation.verdict is expected_verdict

    assert (
        observation.evidence_sha256
        == agent_run.execution_evidence_sha256
    )

    assert (
        observation.counterexample_sha256
        is not None
    ) is has_counterexample

    if has_counterexample:
        assert (
            len(
                observation.counterexample_sha256
            )
            == 64
        )


def test_wrong_interventions_remain_failing_negative_controls():
    wrong_for_tool_fault = run_incident_triage(
        IncidentFaultMode.FILTER_TOOL_SELECTION,
        run_id="wrong-tool-fix",
        intervention=(
            InterventionKind.OVERRIDE_PARAMETER
        ),
    )

    wrong_for_threshold_fault = run_incident_triage(
        IncidentFaultMode.THRESHOLD_TRANSFORMATION,
        run_id="wrong-threshold-fix",
        intervention=(
            InterventionKind.REPLACE_TOOL
        ),
    )

    assert wrong_for_tool_fault.passed is False
    assert wrong_for_threshold_fault.passed is False

    with pytest.raises(ContractError):
        run_incident_triage(
            IncidentFaultMode.FILTER_TOOL_SELECTION,
            run_id="unsupported",
            intervention=(
                InterventionKind.REMOVE_STEP
            ),
        )


def test_incident_diagnosis_is_deterministic():
    first = run_diagnosis_demo(
        IncidentFaultMode.THRESHOLD_TRANSFORMATION,
        run_id="deterministic",
    )

    second = run_diagnosis_demo(
        IncidentFaultMode.THRESHOLD_TRANSFORMATION,
        run_id="deterministic",
    )

    assert first == second

    assert (
        first.experiment_result.agent_run
        == second.experiment_result.agent_run
    )

    assert (
        first.experiment_result.observation
        == second.experiment_result.observation
    )


def test_fixture_has_no_external_runtime_or_prediction_copy_shortcut():
    environment_source = Path(
        "environments/agent/incident_triage.py"
    ).read_text(encoding="utf-8")

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
        assert token not in environment_source

    diagnostic_source = inspect.getsource(
        execute_selected_experiment
    )

    assert "predicted_verdicts" not in diagnostic_source
    assert "diagnostic_run.passed" in diagnostic_source
    assert (
        "execution_evidence_sha256"
        in diagnostic_source
    )

    assert expected_incident_ids() == (
        "INC-1001",
        "INC-1002",
        "INC-1004",
    )

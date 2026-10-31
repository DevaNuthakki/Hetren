
"""A5-10G-B1 deterministic multi-step contract tests; no model inference."""

from dataclasses import FrozenInstanceError, replace

import pytest

from packages.contracts import ContractError
from packages.core.hetren_diagnosis.contracts import EventKind
from packages.engines.behavioral.incident_scenario_development import (
    IncidentScenario, reference_expected_incident_ids,
)
from packages.engines.behavioral.incident_multistep_runtime_development import (
    IncidentWorkflowAction,
    advance_incident_workflow,
    start_incident_workflow,
)


def _scenario(service="payments", threshold=3):
    return IncidentScenario(
        scenario_id="multistep-development",
        target_service=service,
        minimum_severity=threshold,
        records=(
            ("INC-P001", "payments", 3),
            ("INC-P002", "payments", 6),
            ("INC-P003", "payments", 1),
            ("INC-A001", "auth", 2),
            ("INC-A002", "auth", 8),
            ("INC-N001", "notifications", 10),
        ),
    )


def _actions(service="payments", tool="inclusive_severity_filter", threshold=3):
    return (
        IncidentWorkflowAction("load_incidents"),
        IncidentWorkflowAction("scope_service", service=service),
        IncidentWorkflowAction("apply_filter", filter_tool=tool, threshold=threshold),
        IncidentWorkflowAction("finalize"),
    )


def _execute(scenario, actions=None, *, run_id="a510g-b1", budget=4):
    state = start_incident_workflow(
        scenario=scenario, run_id=run_id, max_steps=budget,
    )
    for action in actions if actions is not None else _actions(
        scenario.target_service, threshold=scenario.minimum_severity,
    ):
        state = advance_incident_workflow(
            scenario=scenario, state=state, action=action,
        )
    return state


@pytest.mark.parametrize("service,threshold,expected", [
    ("payments", 3, ("INC-P001", "INC-P002")),
    ("auth", 2, ("INC-A001", "INC-A002")),
    ("notifications", 10, ("INC-N001",)),
    ("payments", 9, ()),
])
def test_four_step_execution_uses_real_scenario_and_oracle(
    service, threshold, expected,
):
    scenario = _scenario(service, threshold)
    state = _execute(scenario)
    assert state.completed and state.passed
    assert state.phase == "completed"
    assert state.steps_used == 4
    assert state.remaining_steps == 0
    assert state.report.incident_ids == expected
    assert state.evaluation.expected_ids == expected
    assert reference_expected_incident_ids(scenario) == expected
    assert state.trace.run_id == state.run_id
    assert [step.event.sequence for step in state.steps] == list(range(4))
    assert [step.event.kind for step in state.steps] == [
        EventKind.TOOL_CALL, EventKind.TOOL_CALL,
        EventKind.TOOL_CALL, EventKind.TERMINATION,
    ]
    assert len(state.execution_evidence_sha256) == 64


def test_records_only_observable_after_load_action():
    scenario = _scenario()
    start = start_incident_workflow(scenario=scenario, run_id="a510g-loading")
    assert start.phase == "ready"
    assert start.loaded_rows == ()
    assert start.steps == ()
    assert len(start.trace.events) == 0
    loaded = advance_incident_workflow(
        scenario=scenario, state=start,
        action=IncidentWorkflowAction("load_incidents"),
    )
    assert loaded.steps[-1].observation.rows == scenario.records
    assert loaded.steps[-1].observation.report is None
    assert start.loaded_rows == ()
    assert loaded.loaded_rows == scenario.records


def test_observation_is_made_available_after_each_dependency():
    scenario = _scenario()
    state = start_incident_workflow(scenario=scenario, run_id="a510g-deps")
    observations = []
    for action in _actions():
        state = advance_incident_workflow(
            scenario=scenario, state=state, action=action,
        )
        observations.append(state.steps[-1].observation)
    assert len(observations[0].rows) == 6
    assert len(observations[1].rows) == 3
    assert tuple(x[0] for x in observations[2].rows) == (
        "INC-P001", "INC-P002",
    )
    assert observations[3].report == state.report
    assert observations[3].evaluation_passed is True
    assert observations[3].evaluation_sha256 == (
        state.evaluation.evaluation_evidence_sha256
    )
    for previous, current in zip(state.trace.events, state.trace.events[1:]):
        assert previous.state_after_sha256 == current.state_before_sha256
    for step in state.steps:
        assert step.event.output_sha256 == step.observation.observation_sha256


@pytest.mark.parametrize("service,tool,threshold", [
    ("auth", "inclusive_severity_filter", 3),
    ("payments", "strict_severity_filter", 3),
    ("payments", "inclusive_severity_filter", 4),
    ("notifications", "inclusive_severity_filter", 3),
])
def test_execution_completion_and_evaluation_are_separate(
    service, tool, threshold,
):
    scenario = _scenario("payments", 3)
    state = _execute(scenario, _actions(service, tool, threshold))
    assert state.completed
    assert state.report is not None
    assert state.evaluation is not None
    assert not state.evaluation.passed
    assert not state.passed
    assert state.steps[-1].observation.evaluation_passed is False


@pytest.mark.parametrize("invalid", [
    ("finalize", None, None, None),
    ("apply_filter", None, "inclusive_severity_filter", 3),
    ("scope_service", "payments", None, None),
])
def test_out_of_order_actions_are_rejected_without_state_mutation(invalid):
    scenario = _scenario()
    state = start_incident_workflow(scenario=scenario, run_id="a510g-order")
    operation, service, tool, threshold = invalid
    action = IncidentWorkflowAction(
        operation, service=service, filter_tool=tool, threshold=threshold,
    )
    original_hash = state.execution_evidence_sha256
    with pytest.raises(ContractError, match="illegal or repeated"):
        advance_incident_workflow(scenario=scenario, state=state, action=action)
    assert state.execution_evidence_sha256 == original_hash
    assert not state.steps


def test_repeated_and_post_completion_actions_are_rejected():
    scenario = _scenario()
    loaded = _execute(scenario, _actions()[:1])
    with pytest.raises(ContractError, match="illegal or repeated"):
        advance_incident_workflow(
            scenario=scenario, state=loaded,
            action=IncidentWorkflowAction("load_incidents"),
        )
    finished = _execute(scenario, budget=6)
    with pytest.raises(ContractError, match="illegal or repeated"):
        advance_incident_workflow(
            scenario=scenario, state=finished,
            action=IncidentWorkflowAction("finalize"),
        )


def test_budget_exhaustion_stops_unfinished_workflow():
    scenario = _scenario()
    state = _execute(scenario, _actions()[:2], budget=2)
    assert state.budget_exhausted
    assert not state.completed
    assert state.remaining_steps == 0
    with pytest.raises(ContractError, match="budget exhausted"):
        advance_incident_workflow(
            scenario=scenario, state=state, action=_actions()[2],
        )
    assert state.steps_used == 2


@pytest.mark.parametrize("operation,service,tool,threshold", [
    ("shell", None, None, None),
    ("load_incidents", None, None, 3),
    ("finalize", "payments", None, None),
    ("scope_service", "UNKNOWN", None, None),
    ("scope_service", "payments", None, 3),
    ("apply_filter", None, "shell", 3),
    ("apply_filter", None, "inclusive_severity_filter", True),
    ("apply_filter", None, "inclusive_severity_filter", -1),
    ("apply_filter", None, "inclusive_severity_filter", 11),
    ("apply_filter", "payments", "inclusive_severity_filter", 3),
])
def test_invalid_action_parameters_fail_closed(operation, service, tool, threshold):
    with pytest.raises(ContractError):
        IncidentWorkflowAction(
            operation, service=service, filter_tool=tool, threshold=threshold,
        )


@pytest.mark.parametrize("budget", [0, True, -1, 9, 2.5])
def test_invalid_budget_rejected(budget):
    with pytest.raises(ContractError):
        start_incident_workflow(
            scenario=_scenario(), run_id="a510g-budget", max_steps=budget,
        )


def test_changing_scenario_identity_rejects_resume():
    scenario = _scenario()
    state = _execute(scenario, _actions()[:1])
    altered = replace(scenario, minimum_severity=5)
    with pytest.raises(ContractError, match="scenario identity"):
        advance_incident_workflow(
            scenario=altered, state=state, action=_actions()[1],
        )


def test_forged_resume_history_is_rejected():
    scenario = _scenario()
    state = _execute(scenario, _actions()[:2])
    forged = replace(state, selected_service="auth")
    with pytest.raises(ContractError, match="state provenance"):
        advance_incident_workflow(
            scenario=scenario, state=forged, action=_actions()[2],
        )
    changed_event = replace(state.steps[0].event, operation="forged_tool")
    altered_step = replace(state.steps[0], event=changed_event)
    forged_trace = replace(state, steps=(altered_step,) + state.steps[1:])
    with pytest.raises(ContractError, match="state provenance"):
        advance_incident_workflow(
            scenario=scenario, state=forged_trace, action=_actions()[2],
        )


def test_replay_is_deterministic_but_run_identity_changes_evidence():
    scenario = _scenario()
    left = _execute(scenario, run_id="a510g-repeat")
    same = _execute(scenario, run_id="a510g-repeat")
    different = _execute(scenario, run_id="a510g-other")
    assert left == same
    assert left.execution_evidence_sha256 == same.execution_evidence_sha256
    assert left.execution_evidence_sha256 != different.execution_evidence_sha256
    assert left.report == different.report


def test_action_and_state_are_immutable_and_claims_limited():
    state = _execute(_scenario())
    with pytest.raises(FrozenInstanceError):
        state.phase = "ready"
    with pytest.raises(FrozenInstanceError):
        state.steps[0].action.operation = "finalize"
    limitations = " ".join(state.limitations)
    assert "externally supplied" in limitations
    assert "no observation-dependent model policy" in limitations
    assert "no independent scientific verification" in limitations
    assert "no live provider inference" in limitations

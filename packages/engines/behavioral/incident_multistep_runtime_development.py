
"""A5-10G-B1: bounded, immutable incident investigation workflow.

Development-only deterministic coordinator. It does not call a model and
cannot establish observation-dependent model behavior. Subsequent increments
may supply model-selected actions in response to these observations.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import re

from environments.agent.incident_triage import TriageReport, filter_incident_rows
from packages.contracts import ContractError
from packages.core.hetren_diagnosis.contracts import (
    AgentTrace, EventKind, TraceEvent, canonical_sha256,
)
from packages.engines.behavioral.incident_scenario_development import (
    ALLOWED_TOOLS, MAX_SEVERITY, IncidentScenario,
    IncidentScenarioEvaluation, evaluate_incident_scenario,
)

_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,47}")
_SERVICE = re.compile(r"[a-z][a-z0-9_-]{0,23}")
_TRANSITIONS = {
    "ready": ("load_incidents", "loaded"),
    "loaded": ("scope_service", "scoped"),
    "scoped": ("apply_filter", "filtered"),
    "filtered": ("finalize", "completed"),
}


@dataclass(frozen=True)
class IncidentWorkflowAction:
    """One explicitly bounded, externally supplied workflow action."""

    operation: str
    service: str | None = None
    filter_tool: str | None = None
    threshold: int | None = None

    def __post_init__(self) -> None:
        if type(self.operation) is not str:
            raise ContractError("invalid workflow operation")
        if self.operation in ("load_incidents", "finalize"):
            if any(x is not None for x in (
                self.service, self.filter_tool, self.threshold,
            )):
                raise ContractError("unexpected workflow action parameters")
        elif self.operation == "scope_service":
            if (
                type(self.service) is not str
                or _SERVICE.fullmatch(self.service) is None
                or self.filter_tool is not None
                or self.threshold is not None
            ):
                raise ContractError("invalid scope_service parameters")
        elif self.operation == "apply_filter":
            if (
                self.service is not None
                or type(self.filter_tool) is not str
                or self.filter_tool not in ALLOWED_TOOLS
                or type(self.threshold) is not int
                or not 0 <= self.threshold <= MAX_SEVERITY
            ):
                raise ContractError("invalid apply_filter parameters")
        else:
            raise ContractError("unsupported workflow operation")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "operation": self.operation,
            "service": self.service,
            "filter_tool": self.filter_tool,
            "threshold": self.threshold,
        }


@dataclass(frozen=True)
class IncidentWorkflowObservation:
    """Immutable output available for the NEXT external decision."""

    scenario_sha256: str
    operation: str
    phase_after: str
    rows: tuple[tuple[str, str, int], ...]
    report: TriageReport | None
    evaluation_sha256: str | None
    evaluation_passed: bool | None

    def canonical_payload(self) -> dict[str, object]:
        return {
            "scenario_sha256": self.scenario_sha256,
            "operation": self.operation,
            "phase_after": self.phase_after,
            "rows": [list(row) for row in self.rows],
            "report": (
                None if self.report is None
                else self.report.canonical_payload()
            ),
            "evaluation_sha256": self.evaluation_sha256,
            "evaluation_passed": self.evaluation_passed,
        }

    @property
    def observation_sha256(self) -> str:
        return canonical_sha256(self.canonical_payload())


@dataclass(frozen=True)
class IncidentWorkflowStep:
    action: IncidentWorkflowAction
    observation: IncidentWorkflowObservation
    event: TraceEvent


@dataclass(frozen=True)
class IncidentWorkflowState:
    """Reconstructable state; every supplied state is replay-validated."""

    run_id: str
    scenario_sha256: str
    max_steps: int
    phase: str
    loaded_rows: tuple[tuple[str, str, int], ...] = ()
    selected_service: str | None = None
    scoped_rows: tuple[tuple[str, str, int], ...] = ()
    selected_rows: tuple[tuple[str, str, int], ...] = ()
    filter_tool: str | None = None
    threshold: int | None = None
    report: TriageReport | None = None
    evaluation: IncidentScenarioEvaluation | None = None
    steps: tuple[IncidentWorkflowStep, ...] = ()

    @property
    def steps_used(self) -> int:
        return len(self.steps)

    @property
    def remaining_steps(self) -> int:
        return self.max_steps - self.steps_used

    @property
    def budget_exhausted(self) -> bool:
        return self.remaining_steps == 0 and self.phase != "completed"

    @property
    def completed(self) -> bool:
        return self.phase == "completed"

    @property
    def passed(self) -> bool:
        return bool(self.completed and self.evaluation and self.evaluation.passed)

    @property
    def trace(self) -> AgentTrace:
        return AgentTrace(
            run_id=self.run_id,
            events=tuple(step.event for step in self.steps),
        )

    @property
    def execution_evidence_sha256(self) -> str:
        return canonical_sha256({
            "record_type": "IncidentWorkflowDevelopmentExecution",
            "schema_version": 1,
            "development_only": True,
            "state": _summary(self),
            "actions": [step.action.canonical_payload() for step in self.steps],
            "observation_hashes": [
                step.observation.observation_sha256 for step in self.steps
            ],
            "trace_sha256": self.trace.trace_sha256,
            "passed": self.passed,
        })

    @property
    def limitations(self) -> tuple[str, ...]:
        return (
            "deterministic synthetic development workflow",
            "actions are externally supplied, not model-generated here",
            "no observation-dependent model policy evaluated",
            "no live provider inference",
            "no independent scientific verification",
            "no deployment authorization",
        )


def _summary(state: IncidentWorkflowState) -> dict[str, object]:
    """State boundary excludes history so event hashes chain exactly."""
    return {
        "run_id": state.run_id,
        "scenario_sha256": state.scenario_sha256,
        "max_steps": state.max_steps,
        "phase": state.phase,
        "loaded_rows": [list(row) for row in state.loaded_rows],
        "selected_service": state.selected_service,
        "scoped_rows": [list(row) for row in state.scoped_rows],
        "selected_rows": [list(row) for row in state.selected_rows],
        "filter_tool": state.filter_tool,
        "threshold": state.threshold,
        "report_sha256": None if state.report is None else state.report.report_sha256,
        "evaluation_sha256": (
            None if state.evaluation is None
            else state.evaluation.evaluation_evidence_sha256
        ),
    }


def start_incident_workflow(
    *, scenario: IncidentScenario, run_id: str, max_steps: int = 4,
) -> IncidentWorkflowState:
    """Start without exposing scenario records to the decision maker."""
    if not isinstance(scenario, IncidentScenario):
        raise ContractError("scenario must be an IncidentScenario")
    if type(run_id) is not str or _RUN_ID.fullmatch(run_id) is None:
        raise ContractError("invalid workflow run_id")
    if type(max_steps) is not int or not 1 <= max_steps <= 8:
        raise ContractError("workflow max_steps must be between 1 and 8")
    return IncidentWorkflowState(
        run_id=run_id, scenario_sha256=scenario.scenario_sha256,
        max_steps=max_steps, phase="ready",
    )


def _advance_validated(
    scenario: IncidentScenario,
    state: IncidentWorkflowState,
    action: IncidentWorkflowAction,
) -> IncidentWorkflowState:
    """Private pure transition; caller must validate prior history first."""
    if state.remaining_steps <= 0:
        raise ContractError("workflow budget exhausted")
    allowed = _TRANSITIONS.get(state.phase)
    if allowed is None or allowed[0] != action.operation:
        raise ContractError("illegal or repeated workflow transition")

    phase_after = allowed[1]
    changes: dict[str, object] = {"phase": phase_after}
    rows: tuple[tuple[str, str, int], ...] = ()
    report = None
    evaluation = None

    if action.operation == "load_incidents":
        rows = scenario.records
        changes["loaded_rows"] = rows
    elif action.operation == "scope_service":
        rows = tuple(
            record for record in state.loaded_rows
            if record[1] == action.service
        )
        changes.update(selected_service=action.service, scoped_rows=rows)
    elif action.operation == "apply_filter":
        assert state.selected_service is not None
        _, rows = filter_incident_rows(
            records=state.scoped_rows,
            target_service=state.selected_service,
            tool_name=action.filter_tool,
            threshold=action.threshold,
        )
        changes.update(
            selected_rows=rows,
            filter_tool=action.filter_tool,
            threshold=action.threshold,
        )
    else:
        assert action.operation == "finalize"
        assert state.selected_service is not None
        rows = state.selected_rows
        report = TriageReport(
            service=state.selected_service,
            incident_ids=tuple(record[0] for record in rows),
            count=len(rows),
        )
        evaluation = evaluate_incident_scenario(
            scenario=scenario, report=report,
        )
        changes.update(report=report, evaluation=evaluation)

    changed = replace(state, **changes)
    observation = IncidentWorkflowObservation(
        scenario_sha256=scenario.scenario_sha256,
        operation=action.operation,
        phase_after=phase_after,
        rows=rows,
        report=report,
        evaluation_sha256=(
            None if evaluation is None else evaluation.evaluation_evidence_sha256
        ),
        evaluation_passed=None if evaluation is None else evaluation.passed,
    )
    event = TraceEvent(
        sequence=state.steps_used,
        kind=(EventKind.TERMINATION if phase_after == "completed" else EventKind.TOOL_CALL),
        component="incident_multistep_development",
        operation=action.operation,
        input_sha256=canonical_sha256({
            "scenario_sha256": scenario.scenario_sha256,
            "action": action.canonical_payload(),
        }),
        output_sha256=observation.observation_sha256,
        state_before_sha256=canonical_sha256(_summary(state)),
        state_after_sha256=canonical_sha256(_summary(changed)),
    )
    return replace(
        changed,
        steps=state.steps + (IncidentWorkflowStep(action, observation, event),),
    )


def advance_incident_workflow(
    *, scenario: IncidentScenario, state: IncidentWorkflowState,
    action: IncidentWorkflowAction,
) -> IncidentWorkflowState:
    """Advance once, rejecting changed scenarios and forged resume history.

    Model decisions are NOT generated by this function. For an external
    policy, consume state.steps[-1].observation before supplying next action.
    """
    if not isinstance(scenario, IncidentScenario):
        raise ContractError("invalid incident scenario")
    if not isinstance(state, IncidentWorkflowState):
        raise ContractError("invalid incident workflow state")
    if not isinstance(action, IncidentWorkflowAction):
        raise ContractError("invalid incident workflow action")
    if state.scenario_sha256 != scenario.scenario_sha256:
        raise ContractError("workflow scenario identity mismatch")

    reconstructed = start_incident_workflow(
        scenario=scenario, run_id=state.run_id, max_steps=state.max_steps,
    )
    for prior in state.steps:
        reconstructed = _advance_validated(scenario, reconstructed, prior.action)
    if reconstructed != state:
        raise ContractError("workflow state provenance mismatch")

    return _advance_validated(scenario, state, action)

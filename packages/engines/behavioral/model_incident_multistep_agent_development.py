"""A5-10G-B2: evidence-bound observation-conditioned incident agent.

A capture source is called separately for each request, AFTER the previous
local tool has returned its actual observation. The source can be a fixture or
an explicitly injected, offline provider transport. Recorded responses are
not evidence that a real model used those observations or generalized.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Callable

from packages.contracts import ContractError
from packages.core.hetren_diagnosis.contracts import canonical_sha256
from packages.engines.behavioral.incident_scenario_development import (
    ALLOWED_TOOLS, MAX_SEVERITY, IncidentScenario,
)
from packages.engines.behavioral.incident_multistep_runtime_development import (
    IncidentWorkflowAction, IncidentWorkflowState,
    start_incident_workflow, advance_incident_workflow,
)
from packages.model_capture import ModelCapture, ModelRequest, replay_json_capture
from packages.openai_responses import Transport, call_openai_responses

CaptureSource = Callable[[ModelRequest], ModelCapture]
_OPERATIONS = {
    "ready": "load_incidents",
    "loaded": "scope_service",
    "scoped": "apply_filter",
    "filtered": "finalize",
}


def _validate_state(*, scenario: IncidentScenario, state: IncidentWorkflowState) -> None:
    """Reconstruct each step before entrusting its observation to a request."""
    if not isinstance(scenario, IncidentScenario) or not isinstance(state, IncidentWorkflowState):
        raise ContractError("invalid incident scenario or workflow state")
    if state.scenario_sha256 != scenario.scenario_sha256:
        raise ContractError("workflow scenario identity mismatch")
    rebuilt = start_incident_workflow(
        scenario=scenario, run_id=state.run_id, max_steps=state.max_steps,
    )
    for historical in state.steps:
        rebuilt = advance_incident_workflow(
            scenario=scenario, state=rebuilt, action=historical.action,
        )
    if rebuilt != state:
        raise ContractError("workflow state provenance mismatch")


def _phase_schema(phase: str) -> dict[str, object]:
    operation = _OPERATIONS[phase]
    properties: dict[str, object] = {"operation": {"type": "string", "enum": [operation]}}
    required = ["operation"]
    if phase == "loaded":
        properties["service"] = {"type": "string"}
        required.append("service")
    elif phase == "scoped":
        properties["filter_tool"] = {"type": "string", "enum": list(ALLOWED_TOOLS)}
        properties["threshold"] = {"type": "integer", "minimum": 0, "maximum": MAX_SEVERITY}
        required.extend(("filter_tool", "threshold"))
    return {
        "type": "object", "properties": properties,
        "required": required, "additionalProperties": False,
    }


def _request_context(*, scenario: IncidentScenario, state: IncidentWorkflowState) -> dict[str, object]:
    previous = state.steps[-1].observation if state.steps else None
    # Do NOT reveal scenario.records on the initial request. These records
    # become visible only after an executed load_incidents action.
    return {
        "development_only": True,
        "run_id": state.run_id,
        "scenario_id": scenario.scenario_id,
        "scenario_sha256": scenario.scenario_sha256,
        "task_goal": {
            "target_service": scenario.target_service,
            "minimum_severity": scenario.minimum_severity,
        },
        "phase": state.phase,
        "step_index": state.steps_used,
        "remaining_steps": state.remaining_steps,
        "workflow_evidence_sha256": state.execution_evidence_sha256,
        "previous_observation_sha256": (
            None if previous is None else previous.observation_sha256
        ),
        "previous_observation": (
            None if previous is None else previous.canonical_payload()
        ),
        "required_next_operation": _OPERATIONS[state.phase],
    }


def build_observation_bound_request(
    *, scenario: IncidentScenario, state: IncidentWorkflowState, model: str,
) -> ModelRequest:
    """Construct one request from an authentic state and latest tool output."""
    _validate_state(scenario=scenario, state=state)
    if state.completed or state.remaining_steps == 0:
        raise ContractError("no decision permitted after completion or budget exhaustion")
    if state.phase not in _OPERATIONS:
        raise ContractError("unknown workflow phase")
    context = _request_context(scenario=scenario, state=state)
    return ModelRequest(
        provider="openai", model=model,
        system_prompt=(
            "You are a bounded incident investigation planner. "
            "Choose only the single required next action, according to the "
            "observed tool output and current workflow phase. "
            "Do not fabricate tool results or incident records."
        ),
        user_prompt=(
            "Select the next bounded action based on this exact workflow state. "
            "STATE_JSON=" + json.dumps(context, sort_keys=True, separators=(",", ":"))
        ),
        response_schema_name="hetren_incident_workflow_action_v1",
        response_schema=_phase_schema(state.phase),
        generation_parameters={},
    )


def _action_from_proposal(phase: str, proposal: object) -> IncidentWorkflowAction:
    """Fail closed on extras, missing keys, type confusion or illegal phase."""
    if type(proposal) is not dict:
        raise ContractError("model workflow proposal must be an object")
    expected = {"operation"}
    if phase == "loaded":
        expected.add("service")
    elif phase == "scoped":
        expected.update(("filter_tool", "threshold"))
    if set(proposal) != expected:
        raise ContractError("invalid workflow proposal shape")
    if proposal.get("operation") != _OPERATIONS[phase]:
        raise ContractError("illegal workflow model operation")
    return IncidentWorkflowAction(
        operation=proposal["operation"],
        service=proposal.get("service"),
        filter_tool=proposal.get("filter_tool"),
        threshold=proposal.get("threshold"),
    )


@dataclass(frozen=True)
class CapturedWorkflowDecision:
    """One captured request/action linked to preceding and resulting evidence."""
    request_sha256: str
    capture_sha256: str
    proposal_sha256: str
    phase_before: str
    workflow_before_sha256: str
    previous_observation_sha256: str | None
    action: IncidentWorkflowAction | None
    workflow_after_sha256: str
    resulting_observation_sha256: str | None
    rejected_reason: str | None

    @property
    def decision_evidence_sha256(self) -> str:
        return canonical_sha256({
            "record_type": "CapturedWorkflowDecision",
            "request_sha256": self.request_sha256,
            "capture_sha256": self.capture_sha256,
            "proposal_sha256": self.proposal_sha256,
            "phase_before": self.phase_before,
            "workflow_before_sha256": self.workflow_before_sha256,
            "previous_observation_sha256": self.previous_observation_sha256,
            "action": None if self.action is None else self.action.canonical_payload(),
            "workflow_after_sha256": self.workflow_after_sha256,
            "resulting_observation_sha256": self.resulting_observation_sha256,
            "rejected_reason": self.rejected_reason,
        })


@dataclass(frozen=True)
class CapturedMultistepIncidentRun:
    state: IncidentWorkflowState
    decisions: tuple[CapturedWorkflowDecision, ...]
    status: str
    rejection_reason: str | None

    @property
    def passed(self) -> bool:
        return self.status == "completed" and self.state.passed

    @property
    def execution_evidence_sha256(self) -> str:
        return canonical_sha256({
            "record_type": "CapturedMultistepIncidentRun",
            "schema_version": 1,
            "development_only": True,
            "status": self.status,
            "rejection_reason": self.rejection_reason,
            "state_evidence_sha256": self.state.execution_evidence_sha256,
            "decision_evidence": [item.decision_evidence_sha256 for item in self.decisions],
            "passed": self.passed,
        })

    @property
    def limitations(self) -> tuple[str, ...]:
        return (
            "synthetic development-only multi-step scenario",
            "capture provenance does not authenticate model identity",
            "injected model decisions do not prove observation-dependent reasoning",
            "request context contains real previous tool observations",
            "no independent scientific verification",
            "no live-model generalization established",
            "no deployment or repair authorization",
        )


def run_captured_multistep_incident(
    *, scenario: IncidentScenario, model: str, run_id: str,
    capture_source: CaptureSource, max_steps: int = 4,
) -> CapturedMultistepIncidentRun:
    """Iteratively request captures and execute each validated local action.

    A source is called with ONLY the just-constructed ModelRequest; the next
    source invocation occurs strictly after actual local tool execution.
    Invalid structured proposals are recorded as rejected, without executing
    the illegal step. Unverifiable captures raise, instead of being accepted.
    """
    if not callable(capture_source):
        raise ContractError("explicit capture source is required")
    state = start_incident_workflow(scenario=scenario, run_id=run_id, max_steps=max_steps)
    decisions = []
    while not state.completed and state.remaining_steps:
        request = build_observation_bound_request(scenario=scenario, state=state, model=model)
        capture = capture_source(request)
        # Always validate original capture/request pair before interpreting it.
        proposal = replay_json_capture(request=request, capture=capture)
        proposal_sha = canonical_sha256(proposal)
        last = state.steps[-1].observation if state.steps else None
        previous_hash = None if last is None else last.observation_sha256
        before_hash = state.execution_evidence_sha256
        reason = None
        action = None
        next_state = state
        try:
            action = _action_from_proposal(state.phase, proposal)
            next_state = advance_incident_workflow(
                scenario=scenario, state=state, action=action,
            )
        except ContractError as exc:
            reason = str(exc)
            action = None  # A rejected operation is never credited as executed.
        after = next_state.steps[-1].observation if next_state != state else None
        decisions.append(CapturedWorkflowDecision(
            request_sha256=request.request_sha256,
            capture_sha256=capture.capture_sha256,
            proposal_sha256=proposal_sha,
            phase_before=state.phase,
            workflow_before_sha256=before_hash,
            previous_observation_sha256=previous_hash,
            action=action,
            workflow_after_sha256=next_state.execution_evidence_sha256,
            resulting_observation_sha256=(
                None if after is None else after.observation_sha256
            ),
            rejected_reason=reason,
        ))
        if reason is not None:
            return CapturedMultistepIncidentRun(
                state=state, decisions=tuple(decisions),
                status="rejected", rejection_reason=reason,
            )
        state = next_state
    return CapturedMultistepIncidentRun(
        state=state, decisions=tuple(decisions),
        status="completed" if state.completed else "budget_exhausted",
        rejection_reason=None,
    )


def run_injected_openai_multistep_incident(
    *, scenario: IncidentScenario, model: str, run_id: str,
    api_key: str, transport: Transport, max_steps: int = 4,
) -> CapturedMultistepIncidentRun:
    """Provider-shaped offline end-to-end path; no default live transport."""
    if not callable(transport):
        raise ContractError("injected transport is required")

    def source(request: ModelRequest) -> ModelCapture:
        return call_openai_responses(
            request=request, api_key=api_key, transport=transport,
        ).capture

    return run_captured_multistep_incident(
        scenario=scenario, model=model, run_id=run_id,
        capture_source=source, max_steps=max_steps,
    )

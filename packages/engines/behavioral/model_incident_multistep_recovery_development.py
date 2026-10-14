"""A5-10G-B3: bounded recovery from simulated incident-tool unavailability.

Offline development only. Failure injection deliberately occurs before local tool
execution, preventing accidental duplicate side effects. Actual filtering still
uses the validated B1 coordinator. This does not demonstrate that any real
provider or external tool recovers from failures.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Callable

from packages.contracts import ContractError
from packages.core.hetren_diagnosis.contracts import canonical_sha256
from packages.engines.behavioral.incident_scenario_development import IncidentScenario
from packages.engines.behavioral.incident_multistep_runtime_development import (
    IncidentWorkflowAction, IncidentWorkflowState,
    advance_incident_workflow, start_incident_workflow,
)
from packages.engines.behavioral.model_incident_multistep_agent_development import (
    CaptureSource, _action_from_proposal, build_observation_bound_request,
)
from packages.model_capture import ModelCapture, ModelRequest, replay_json_capture
from packages.openai_responses import Transport, call_openai_responses


@dataclass(frozen=True)
class InjectedToolFailure:
    """An explicitly simulated, allowlisted pre-execution tool failure."""
    code: str

    def __post_init__(self) -> None:
        if type(self.code) is not str or self.code not in (
            "temporarily_unavailable", "synthetic_timeout",
        ):
            raise ContractError("unsupported injected tool-failure code")


FaultInjector = Callable[[IncidentWorkflowState, IncidentWorkflowAction], InjectedToolFailure | None]


@dataclass(frozen=True)
class RecoveryObservation:
    """Recorded failure for a subsequent decision at the same workflow phase."""
    scenario_sha256: str
    workflow_before_sha256: str
    failed_action_sha256: str
    failure_code: str
    attempt_number: int
    prior_success_observation_sha256: str | None
    origin: str = "synthetic_pre_execution_failure"

    def canonical_payload(self) -> dict[str, object]:
        return {
            "record_type": "RecoveryObservation",
            "development_only": True,
            "scenario_sha256": self.scenario_sha256,
            "workflow_before_sha256": self.workflow_before_sha256,
            "failed_action_sha256": self.failed_action_sha256,
            "failure_code": self.failure_code,
            "attempt_number": self.attempt_number,
            "prior_success_observation_sha256": self.prior_success_observation_sha256,
            "origin": self.origin,
        }

    @property
    def observation_sha256(self) -> str:
        return canonical_sha256(self.canonical_payload())


@dataclass(frozen=True)
class RecoveryAttempt:
    """Captures decision provenance, including attempts that never execute."""
    number: int
    request_sha256: str
    capture_sha256: str
    proposal_sha256: str
    workflow_before_sha256: str
    previous_tool_observation_sha256: str | None
    previous_failure_sha256: str | None
    action: IncidentWorkflowAction | None
    executed: bool
    workflow_after_sha256: str
    resulting_observation_sha256: str | None
    injected_failure: RecoveryObservation | None
    rejection_reason: str | None

    @property
    def attempt_evidence_sha256(self) -> str:
        return canonical_sha256({
            "record_type": "RecoveryAttempt",
            "development_only": True,
            "number": self.number,
            "request_sha256": self.request_sha256,
            "capture_sha256": self.capture_sha256,
            "proposal_sha256": self.proposal_sha256,
            "workflow_before_sha256": self.workflow_before_sha256,
            "previous_tool_observation_sha256": self.previous_tool_observation_sha256,
            "previous_failure_sha256": self.previous_failure_sha256,
            "action": None if self.action is None else self.action.canonical_payload(),
            "executed": self.executed,
            "workflow_after_sha256": self.workflow_after_sha256,
            "resulting_observation_sha256": self.resulting_observation_sha256,
            "injected_failure_sha256": (
                None if self.injected_failure is None
                else self.injected_failure.observation_sha256
            ),
            "rejection_reason": self.rejection_reason,
        })


@dataclass(frozen=True)
class CaptureSourceInterruption:
    """Immutable evidence for a pending capture call that did not complete.

    Never contains exception messages, credentials or fabricated tool results.
    An interrupted capture is NOT an executed or counted model action.
    """
    workflow_before_sha256: str
    pending_request_sha256: str
    attempt_number: int
    prior_success_observation_sha256: str | None
    prior_failure_sha256: str | None
    origin: str = "capture_source_exception"

    def __post_init__(self) -> None:
        if type(self.attempt_number) is not int or not 1 <= self.attempt_number <= 12:
            raise ContractError("invalid interrupted attempt number")
        if self.origin != "capture_source_exception":
            raise ContractError("invalid interruption origin")
        for name in ("workflow_before_sha256", "pending_request_sha256"):
            value = getattr(self, name)
            if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
                raise ContractError("invalid required interruption fingerprint")
        for name in ("prior_success_observation_sha256", "prior_failure_sha256"):
            value = getattr(self, name)
            if value is not None and (
                type(value) is not str
                or re.fullmatch(r"[0-9a-f]{64}", value) is None
            ):
                raise ContractError("invalid optional interruption fingerprint")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "record_type": "CaptureSourceInterruption",
            "schema_version": 1,
            "development_only": True,
            "workflow_before_sha256": self.workflow_before_sha256,
            "pending_request_sha256": self.pending_request_sha256,
            "attempt_number": self.attempt_number,
            "prior_success_observation_sha256": self.prior_success_observation_sha256,
            "prior_failure_sha256": self.prior_failure_sha256,
            "origin": self.origin,
        }

    @property
    def interruption_evidence_sha256(self) -> str:
        return canonical_sha256(self.canonical_payload())


@dataclass(frozen=True)
class ResilientMultistepIncidentRun:
    state: IncidentWorkflowState
    attempts: tuple[RecoveryAttempt, ...]
    status: str
    termination_reason: str | None
    max_attempts: int
    max_recoveries: int
    interruption: CaptureSourceInterruption | None = None

    def __post_init__(self) -> None:
        interrupted = self.status == "interrupted"
        if interrupted != (self.interruption is not None):
            raise ContractError("interruption status requires matching evidence")
        if self.interruption is not None:
            evidence = self.interruption
            previous = self.state.steps[-1].observation if self.state.steps else None
            previous_sha = None if previous is None else previous.observation_sha256
            last_fault = self.attempts[-1].injected_failure if self.attempts else None
            failure_sha = None if last_fault is None else last_fault.observation_sha256
            if (
                self.termination_reason != "capture_source_interrupted"
                or self.state.completed
                or evidence.workflow_before_sha256 != self.state.execution_evidence_sha256
                or evidence.attempt_number != len(self.attempts) + 1
                or evidence.prior_success_observation_sha256 != previous_sha
                or evidence.prior_failure_sha256 != failure_sha
            ):
                raise ContractError("inconsistent partial-run interruption evidence")

    @property
    def passed(self) -> bool:
        return self.status == "completed" and self.state.passed

    @property
    def injected_failures(self) -> tuple[RecoveryObservation, ...]:
        return tuple(
            item.injected_failure for item in self.attempts
            if item.injected_failure is not None
        )

    @property
    def execution_evidence_sha256(self) -> str:
        payload = {
            "record_type": "ResilientMultistepIncidentRun",
            "schema_version": 1,
            "development_only": True,
            "status": self.status,
            "termination_reason": self.termination_reason,
            "max_attempts": self.max_attempts,
            "max_recoveries": self.max_recoveries,
            "workflow_evidence_sha256": self.state.execution_evidence_sha256,
            "attempt_evidence_hashes": [
                item.attempt_evidence_sha256 for item in self.attempts
            ],
            "passed": self.passed,
        }
        if self.interruption is not None:
            payload["capture_interruption_sha256"] = (
                self.interruption.interruption_evidence_sha256
            )
        return canonical_sha256(payload)

    @property
    def limitations(self) -> tuple[str, ...]:
        return (
            "synthetic development-only failure injection",
            "simulated failures occur before local tool execution",
            "failure observations are in attempt evidence, not B1 AgentTrace",
            "captures do not authenticate real model identity",
            "offline replanning does not prove real-model reasoning",
            "no real external tool-failure recovery demonstrated",
            "no independent scientific verification",
            "no deployment authorization",
        )


def build_recovery_bound_request(
    *, scenario: IncidentScenario, state: IncidentWorkflowState,
    model: str, prior_failure: RecoveryObservation | None,
) -> ModelRequest:
    """Use verified B2 request; bind a simulated failure into a new digest."""
    base = build_observation_bound_request(
        scenario=scenario, state=state, model=model,
    )
    if prior_failure is None:
        return base
    if not isinstance(prior_failure, RecoveryObservation):
        raise ContractError("invalid recovery observation")
    previous = state.steps[-1].observation if state.steps else None
    previous_hash = None if previous is None else previous.observation_sha256
    if (
        prior_failure.scenario_sha256 != scenario.scenario_sha256
        or prior_failure.workflow_before_sha256 != state.execution_evidence_sha256
        or prior_failure.prior_success_observation_sha256 != previous_hash
        or prior_failure.origin != "synthetic_pre_execution_failure"
    ):
        raise ContractError("recovery observation does not bind to workflow")
    return ModelRequest(
        provider=base.provider, model=base.model,
        system_prompt=base.system_prompt,
        user_prompt=(
            base.user_prompt + "\nRECOVERY_JSON="
            + json.dumps({
                "failure": prior_failure.canonical_payload(),
                "failure_observation_sha256": prior_failure.observation_sha256,
                "instruction": (
                    "Previous attempt failed before tool execution. "
                    "Choose a permitted action using this failure feedback; "
                    "do not repeat the same failed action."
                ),
            }, sort_keys=True, separators=(",", ":"))
        ),
        response_schema_name=base.response_schema_name,
        response_schema=base.response_schema,
        generation_parameters=base.generation_parameters,
    )


def run_resilient_multistep_incident(
    *, scenario: IncidentScenario, model: str, run_id: str,
    capture_source: CaptureSource,
    failure_injector: FaultInjector | None = None,
    max_steps: int = 4, max_attempts: int = 6, max_recoveries: int = 1,
) -> ResilientMultistepIncidentRun:
    """Recover only from injected pre-execution tool unavailability.

    Invalid proposals, capture tampering and provider failures remain fail-closed.
    Neither a rejected nor a repeated failed action can be credited as executed.
    """
    if not callable(capture_source):
        raise ContractError("explicit capture source is required")
    if failure_injector is not None and not callable(failure_injector):
        raise ContractError("failure injector must be callable")
    if type(max_attempts) is not int or not 1 <= max_attempts <= 12:
        raise ContractError("max_attempts must be between 1 and 12")
    if type(max_recoveries) is not int or not 0 <= max_recoveries <= 2:
        raise ContractError("max_recoveries must be between 0 and 2")
    state = start_incident_workflow(
        scenario=scenario, run_id=run_id, max_steps=max_steps,
    )
    attempts: list[RecoveryAttempt] = []
    pending_failure: RecoveryObservation | None = None
    last_failed_action: IncidentWorkflowAction | None = None
    failure_count = 0

    def result(
        status: str, reason: str | None = None,
        *, interruption: CaptureSourceInterruption | None = None,
    ) -> ResilientMultistepIncidentRun:
        return ResilientMultistepIncidentRun(
            state=state, attempts=tuple(attempts), status=status,
            termination_reason=reason, max_attempts=max_attempts,
            max_recoveries=max_recoveries, interruption=interruption,
        )

    while not state.completed and state.remaining_steps and len(attempts) < max_attempts:
        request = build_recovery_bound_request(
            scenario=scenario, state=state, model=model,
            prior_failure=pending_failure,
        )
        try:
            capture = capture_source(request)
        except (ContractError, AssertionError):
            # Do not turn a violated contract or developer invariant into a
            # benign provider interruption. Both remain fail-closed.
            raise
        except Exception:
            # Capture-source failure is an interrupted RUN, not a valid action.
            # Intentionally omit exception messages and secrets from evidence.
            previous = state.steps[-1].observation if state.steps else None
            prior_fault = pending_failure
            return result(
                "interrupted", "capture_source_interrupted",
                interruption=CaptureSourceInterruption(
                    workflow_before_sha256=state.execution_evidence_sha256,
                    pending_request_sha256=request.request_sha256,
                    attempt_number=len(attempts) + 1,
                    prior_success_observation_sha256=(
                        None if previous is None else previous.observation_sha256
                    ),
                    prior_failure_sha256=(
                        None if prior_fault is None else prior_fault.observation_sha256
                    ),
                ),
            )
        # Cryptographic request binding; mismatched or tampered captures raise.
        proposal = replay_json_capture(request=request, capture=capture)
        before = state.execution_evidence_sha256
        previous = state.steps[-1].observation if state.steps else None
        previous_hash = None if previous is None else previous.observation_sha256
        attempt_number = len(attempts) + 1
        action: IncidentWorkflowAction | None = None
        injected_failure: RecoveryObservation | None = None
        rejection: str | None = None
        executed = False
        next_state = state

        try:
            action = _action_from_proposal(state.phase, proposal)
            if pending_failure is not None and action == last_failed_action:
                rejection = "repeated_failed_action"
            elif failure_injector is not None:
                fault = failure_injector(state, action)
                if fault is not None:
                    if not isinstance(fault, InjectedToolFailure):
                        raise ContractError("invalid injected failure result")
                    # Failures are only injected at the local filtering boundary.
                    if state.phase != "scoped" or action.operation != "apply_filter":
                        raise ContractError("fault injection outside filter boundary")
                    injected_failure = RecoveryObservation(
                        scenario_sha256=scenario.scenario_sha256,
                        workflow_before_sha256=before,
                        failed_action_sha256=canonical_sha256(action.canonical_payload()),
                        failure_code=fault.code,
                        attempt_number=attempt_number,
                        prior_success_observation_sha256=previous_hash,
                    )
            if rejection is None and injected_failure is None:
                next_state = advance_incident_workflow(
                    scenario=scenario, state=state, action=action,
                )
                executed = True
        except ContractError as exc:
            # Invalid model actions are rejected; invalid injected fault
            # configurations MUST surface as errors, not model rejections.
            if action is not None:
                raise
            rejection = str(exc)

        resulting_observation = (
            next_state.steps[-1].observation if executed else None
        )
        attempts.append(RecoveryAttempt(
            number=attempt_number,
            request_sha256=request.request_sha256,
            capture_sha256=capture.capture_sha256,
            proposal_sha256=canonical_sha256(proposal),
            workflow_before_sha256=before,
            previous_tool_observation_sha256=previous_hash,
            previous_failure_sha256=(
                None if pending_failure is None else pending_failure.observation_sha256
            ),
            action=action,
            executed=executed,
            workflow_after_sha256=next_state.execution_evidence_sha256,
            resulting_observation_sha256=(
                None if resulting_observation is None
                else resulting_observation.observation_sha256
            ),
            injected_failure=injected_failure,
            rejection_reason=rejection,
        ))
        if rejection is not None:
            return result("rejected", rejection)
        if injected_failure is not None:
            failure_count += 1
            if failure_count > max_recoveries:
                return result("recovery_exhausted", "injected_failure_budget_exhausted")
            pending_failure = injected_failure
            last_failed_action = action
            # Do not change workflow state: failure happened pre-execution.
            continue
        state = next_state
        pending_failure = None
        last_failed_action = None

    if state.completed:
        return result("completed")
    return result("budget_exhausted", "attempt_or_workflow_budget_exhausted")


def run_injected_openai_resilient_multistep_incident(
    *, scenario: IncidentScenario, model: str, run_id: str,
    api_key: str, transport: Transport,
    failure_injector: FaultInjector | None = None,
    max_steps: int = 4, max_attempts: int = 6, max_recoveries: int = 1,
) -> ResilientMultistepIncidentRun:
    """Provider-shaped offline transport only; None never calls live HTTPS."""
    if not callable(transport):
        raise ContractError("injected transport is required")

    def source(request: ModelRequest) -> ModelCapture:
        return call_openai_responses(
            request=request, api_key=api_key, transport=transport,
        ).capture

    return run_resilient_multistep_incident(
        scenario=scenario, model=model, run_id=run_id,
        capture_source=source, failure_injector=failure_injector,
        max_steps=max_steps, max_attempts=max_attempts,
        max_recoveries=max_recoveries,
    )

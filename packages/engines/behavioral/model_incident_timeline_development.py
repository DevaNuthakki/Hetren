"""Read-only chronological reconstruction of synthetic incident evidence."""

from __future__ import annotations

from dataclasses import dataclass

from packages.contracts import ContractError
from packages.core.hetren_diagnosis.contracts import canonical_sha256
from packages.engines.behavioral.incident_scenario_development import IncidentScenario
from packages.engines.behavioral.incident_multistep_runtime_development import (
    advance_incident_workflow,
    start_incident_workflow,
)
from packages.engines.behavioral.model_incident_multistep_recovery_development import (
    RecoveryObservation,
    build_recovery_bound_request,
)
from packages.engines.behavioral.model_incident_provider_observability_development import (
    ObservedResilientIncidentRun,
)


@dataclass(frozen=True)
class IncidentTimelineEvent:
    sequence: int
    kind: str
    request_sha256: str
    capture_sha256: str | None
    source_evidence_sha256: str
    provider_observation_sha256: str
    workflow_before_sha256: str
    workflow_after_sha256: str
    resulting_observation_sha256: str | None
    failure_sha256: str | None
    trace_event_sha256: str | None
    previous_event_sha256: str | None

    def canonical_payload(self) -> dict[str, object]:
        return {
            "record_type": "IncidentTimelineEvent",
            "schema_version": 1,
            "development_only": True,
            "sequence": self.sequence,
            "kind": self.kind,
            "request_sha256": self.request_sha256,
            "capture_sha256": self.capture_sha256,
            "source_evidence_sha256": self.source_evidence_sha256,
            "provider_observation_sha256": self.provider_observation_sha256,
            "workflow_before_sha256": self.workflow_before_sha256,
            "workflow_after_sha256": self.workflow_after_sha256,
            "resulting_observation_sha256": self.resulting_observation_sha256,
            "failure_sha256": self.failure_sha256,
            "trace_event_sha256": self.trace_event_sha256,
            "previous_event_sha256": self.previous_event_sha256,
        }

    @property
    def event_sha256(self) -> str:
        return canonical_sha256(self.canonical_payload())


@dataclass(frozen=True)
class ReconstructedIncidentTimeline:
    scenario_sha256: str
    recovery_sha256: str
    observed_sha256: str
    workflow_sha256: str
    original_trace_sha256: str
    status: str
    passed: bool
    events: tuple[IncidentTimelineEvent, ...]
    reported_total_tokens: int | None
    local_capture_elapsed_ns: int

    @property
    def execution_evidence_sha256(self) -> str:
        return canonical_sha256({
            "record_type": "ReconstructedIncidentTimeline",
            "schema_version": 1,
            "development_only": True,
            "scenario_sha256": self.scenario_sha256,
            "recovery_sha256": self.recovery_sha256,
            "observed_sha256": self.observed_sha256,
            "workflow_sha256": self.workflow_sha256,
            "original_trace_sha256": self.original_trace_sha256,
            "status": self.status,
            "passed": self.passed,
            "event_hashes": [
                event.event_sha256 for event in self.events
            ],
            "reported_total_tokens": self.reported_total_tokens,
            "local_capture_elapsed_ns": self.local_capture_elapsed_ns,
        })

    @property
    def limitations(self) -> tuple[str, ...]:
        return (
            "synthetic development evidence, not a live-model outcome",
            "raw capture contents are not retained in this derived view",
            "hashes attest local consistency, not provider identity",
            "reported token counts may be unknown",
            "no independent scientific verification",
        )


def reconstruct_incident_timeline(
    *,
    scenario: IncidentScenario,
    model: str,
    observed: ObservedResilientIncidentRun,
) -> ReconstructedIncidentTimeline:
    """Validate and join existing records without changing them."""

    if not isinstance(scenario, IncidentScenario):
        raise ContractError("timeline requires exact incident scenario")
    if type(model) is not str or not model:
        raise ContractError("timeline requires model identifier")
    if not isinstance(observed, ObservedResilientIncidentRun):
        raise ContractError("timeline requires observed recovery evidence")

    run = observed.run

    if run.state.scenario_sha256 != scenario.scenario_sha256:
        raise ContractError("timeline scenario identity mismatch")

    if (
        type(run.attempts) is not tuple
        or type(observed.calls) is not tuple
        or len(observed.calls)
        != len(run.attempts) + int(run.interruption is not None)
        or len(run.attempts) > run.max_attempts
    ):
        raise ContractError("timeline attempt or call counts invalid")

    state = start_incident_workflow(
        scenario=scenario,
        run_id=run.state.run_id,
        max_steps=run.state.max_steps,
    )

    events: list[IncidentTimelineEvent] = []
    prior_failure: RecoveryObservation | None = None
    last_failed_action = None
    failure_count = 0
    executed_event_hashes = []

    def add_event(
        *,
        kind,
        call,
        source_sha,
        before,
        after,
        resulting=None,
        failure=None,
        step_sha=None,
    ):
        previous = (
            None if not events
            else events[-1].event_sha256
        )

        events.append(IncidentTimelineEvent(
            sequence=len(events) + 1,
            kind=kind,
            request_sha256=call.request_sha256,
            capture_sha256=call.capture_sha256,
            source_evidence_sha256=source_sha,
            provider_observation_sha256=call.observation_sha256,
            workflow_before_sha256=before,
            workflow_after_sha256=after,
            resulting_observation_sha256=resulting,
            failure_sha256=failure,
            trace_event_sha256=step_sha,
            previous_event_sha256=previous,
        ))

    for index, attempt in enumerate(run.attempts):
        call = observed.calls[index]

        if (
            attempt.number != index + 1
            or call.number != index + 1
            or call.outcome != "captured"
            or call.request_sha256 != attempt.request_sha256
            or call.capture_sha256 != attempt.capture_sha256
            or state.completed
            or state.remaining_steps == 0
            or failure_count > run.max_recoveries
        ):
            raise ContractError(
                "timeline invalid attempt ordering or provider binding"
            )

        request = build_recovery_bound_request(
            scenario=scenario,
            state=state,
            model=model,
            prior_failure=prior_failure,
        )

        before = state.execution_evidence_sha256
        previous_observation = (
            None if not state.steps
            else state.steps[-1].observation.observation_sha256
        )
        previous_failure = (
            None if prior_failure is None
            else prior_failure.observation_sha256
        )

        if (
            attempt.request_sha256 != request.request_sha256
            or attempt.workflow_before_sha256 != before
            or attempt.previous_tool_observation_sha256
            != previous_observation
            or attempt.previous_failure_sha256 != previous_failure
        ):
            raise ContractError(
                "timeline request or prior observation mismatch"
            )

        kind = ""
        next_state = state
        resulting = None
        failure = None
        step_sha = None

        if attempt.executed:
            if (
                attempt.action is None
                or attempt.rejection_reason is not None
                or attempt.injected_failure is not None
            ):
                raise ContractError(
                    "executed attempt has conflicting evidence"
                )

            next_state = advance_incident_workflow(
                scenario=scenario,
                state=state,
                action=attempt.action,
            )

            resulting = (
                next_state.steps[-1].observation.observation_sha256
            )
            step_sha = canonical_sha256(
                next_state.steps[-1].event.canonical_payload()
            )
            executed_event_hashes.append(step_sha)

            kind = (
                "workflow_finalized" if next_state.completed
                else "tool_executed"
            )

        elif attempt.injected_failure is not None:
            fault = attempt.injected_failure

            if (
                attempt.action is None
                or attempt.rejection_reason is not None
                or not isinstance(fault, RecoveryObservation)
                or fault.origin != "synthetic_pre_execution_failure"
                or fault.scenario_sha256 != scenario.scenario_sha256
                or fault.attempt_number != attempt.number
                or fault.workflow_before_sha256 != before
                or fault.failed_action_sha256
                != canonical_sha256(attempt.action.canonical_payload())
                or fault.prior_success_observation_sha256
                != previous_observation
            ):
                raise ContractError(
                    "timeline invalid injected failure provenance"
                )

            failure = fault.observation_sha256
            kind = "tool_failed"
            failure_count += 1
            prior_failure = fault
            last_failed_action = attempt.action

        else:
            if attempt.rejection_reason is None:
                raise ContractError(
                    "attempt neither executed, failed nor rejected"
                )

            if attempt.action is not None and (
                attempt.rejection_reason != "repeated_failed_action"
                or prior_failure is None
                or attempt.action != last_failed_action
            ):
                raise ContractError(
                    "unsupported action rejection provenance"
                )

            kind = "action_rejected"

        after = next_state.execution_evidence_sha256

        if (
            attempt.workflow_after_sha256 != after
            or attempt.resulting_observation_sha256 != resulting
        ):
            raise ContractError(
                "timeline tool execution/result mismatch"
            )

        add_event(
            kind=kind,
            call=call,
            source_sha=attempt.attempt_evidence_sha256,
            before=before,
            after=after,
            resulting=resulting,
            failure=failure,
            step_sha=step_sha,
        )

        state = next_state

        if attempt.executed:
            prior_failure = None
            last_failed_action = None

        if (
            kind == "action_rejected"
            and index != len(run.attempts) - 1
        ):
            raise ContractError(
                "timeline contains action after rejection"
            )

    if run.interruption is not None:
        interruption = run.interruption
        call = observed.calls[-1]

        request = build_recovery_bound_request(
            scenario=scenario,
            state=state,
            model=model,
            prior_failure=prior_failure,
        )

        expected_previous = (
            None if not state.steps
            else state.steps[-1].observation.observation_sha256
        )
        expected_failure = (
            None if prior_failure is None
            else prior_failure.observation_sha256
        )

        if (
            run.status != "interrupted"
            or call.outcome != "interrupted"
            or call.number != len(run.attempts) + 1
            or call.request_sha256 != request.request_sha256
            or interruption.pending_request_sha256
            != request.request_sha256
            or interruption.workflow_before_sha256
            != state.execution_evidence_sha256
            or interruption.attempt_number != call.number
            or interruption.prior_success_observation_sha256
            != expected_previous
            or interruption.prior_failure_sha256
            != expected_failure
            or state.completed
            or len(run.attempts) >= run.max_attempts
        ):
            raise ContractError(
                "timeline interrupted capture binding mismatch"
            )

        current = state.execution_evidence_sha256

        add_event(
            kind="capture_interrupted",
            call=call,
            source_sha=interruption.interruption_evidence_sha256,
            before=current,
            after=current,
        )

    if state != run.state:
        raise ContractError(
            "timeline final workflow state does not match replay"
        )

    expected_status = (
        "interrupted" if run.interruption is not None
        else "rejected" if (
            run.attempts
            and run.attempts[-1].rejection_reason is not None
        )
        else "recovery_exhausted" if failure_count > run.max_recoveries
        else "completed" if state.completed
        else "budget_exhausted"
    )

    if (
        expected_status != run.status
        or run.passed != (
            run.status == "completed" and state.passed
        )
        or run.state.trace.events
        != tuple(step.event for step in state.steps)
        or len(executed_event_hashes) != len(state.steps)
        or (
            run.status == "budget_exhausted"
            and state.remaining_steps > 0
            and len(run.attempts) < run.max_attempts
        )
    ):
        raise ContractError(
            "timeline terminal status or B1 trace mismatch"
        )

    if (
        run.status == "interrupted"
        and run.termination_reason != "capture_source_interrupted"
    ):
        raise ContractError(
            "timeline interruption termination mismatch"
        )

    if (
        run.status == "recovery_exhausted"
        and run.termination_reason
        != "injected_failure_budget_exhausted"
    ):
        raise ContractError("timeline recovery limit mismatch")

    if (
        run.status == "budget_exhausted"
        and run.termination_reason
        != "attempt_or_workflow_budget_exhausted"
    ):
        raise ContractError("timeline attempt budget mismatch")

    if (
        run.status == "completed"
        and run.termination_reason is not None
    ):
        raise ContractError(
            "timeline completed run has termination reason"
        )

    if run.status == "rejected" and (
        not run.attempts
        or run.termination_reason
        != run.attempts[-1].rejection_reason
    ):
        raise ContractError("timeline rejection reason mismatch")

    return ReconstructedIncidentTimeline(
        scenario_sha256=scenario.scenario_sha256,
        recovery_sha256=run.execution_evidence_sha256,
        observed_sha256=observed.execution_evidence_sha256,
        workflow_sha256=state.execution_evidence_sha256,
        original_trace_sha256=state.trace.trace_sha256,
        status=run.status,
        passed=run.passed,
        events=tuple(events),
        reported_total_tokens=observed.total_reported_tokens,
        local_capture_elapsed_ns=observed.local_capture_elapsed_ns,
    )

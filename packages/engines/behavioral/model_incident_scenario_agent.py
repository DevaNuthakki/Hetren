"""Scenario-bound model incident execution, offline development only.

Recorded model actions select allowlisted local filtering tools.
The selected tool executes over the exact specified scenario.

The reference evaluator uses the scenario's written task
requirements, not the model's proposed tool or intervention.

Captures are not fresh model inference or independent scientific
verification.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from environments.agent.incident_triage import (
    TriageReport,
    filter_incident_rows,
)
from packages.contracts import ContractError
from packages.core.hetren_diagnosis.contracts import (
    AgentTrace,
    EventKind,
    TraceEvent,
    canonical_sha256,
)
from packages.engines.behavioral.incident_scenario_development import (
    ALLOWED_TOOLS,
    MAX_SEVERITY,
    IncidentScenario,
    IncidentScenarioEvaluation,
    build_scenario_incident_request,
    evaluate_incident_scenario,
)
from packages.model_capture import (
    ModelCapture,
    ModelRequest,
    replay_json_capture,
)


@dataclass(frozen=True)
class CapturedScenarioIncidentRun:
    """A scenario-bound captured action and its actual execution."""

    run_id: str
    scenario_sha256: str
    request_sha256: str
    capture_sha256: str
    proposal_sha256: str
    status: str
    rejection_reason: str | None
    selected_tool: str | None
    threshold: int | None
    report: TriageReport | None
    evaluation: IncidentScenarioEvaluation | None
    trace: AgentTrace

    @property
    def passed(self) -> bool:
        return (
            self.status == "executed"
            and self.evaluation is not None
            and self.evaluation.passed
        )

    @property
    def execution_evidence_sha256(self) -> str:
        return canonical_sha256({
            "record_type": "CapturedScenarioIncidentRun",
            "schema_version": 1,
            "development_only": True,
            "run_id": self.run_id,
            "scenario_sha256": self.scenario_sha256,
            "request_sha256": self.request_sha256,
            "capture_sha256": self.capture_sha256,
            "proposal_sha256": self.proposal_sha256,
            "status": self.status,
            "rejection_reason": self.rejection_reason,
            "selected_tool": self.selected_tool,
            "threshold": self.threshold,
            "report_sha256": (
                None if self.report is None
                else self.report.report_sha256
            ),
            "evaluation_sha256": (
                None if self.evaluation is None
                else self.evaluation.evaluation_evidence_sha256
            ),
            "trace_sha256": self.trace.trace_sha256,
            "passed": self.passed,
        })

    @property
    def limitations(self) -> tuple[str, ...]:
        return (
            "synthetic development incident scenario",
            "replayed model action, not fresh model inference",
            "actual local filtering, not external incident telemetry",
            "reference oracle is separately implemented software",
            "no independent scientific verification",
            "no evidence of generalization by a live model",
            "no deployment or repair authorization",
        )


def _rejection_reason(proposal: object) -> str | None:
    if type(proposal) is not dict:
        return "proposal_not_object"

    if set(proposal) != {"tool", "threshold"}:
        return "invalid_proposal_shape"

    if (
        type(proposal["tool"]) is not str
        or proposal["tool"] not in ALLOWED_TOOLS
    ):
        return "unsupported_tool"

    value = proposal["threshold"]

    if (
        type(value) is not int
        or not 0 <= value <= MAX_SEVERITY
    ):
        return "invalid_threshold"

    return None


def _event(
    *,
    sequence: int,
    kind: EventKind,
    operation: str,
    input_payload: object,
    output_payload: object,
    before: object,
    after: object,
) -> TraceEvent:
    return TraceEvent(
        sequence=sequence,
        kind=kind,
        component="model_incident_scenario",
        operation=operation,
        input_sha256=canonical_sha256(input_payload),
        output_sha256=canonical_sha256(output_payload),
        state_before_sha256=canonical_sha256(before),
        state_after_sha256=canonical_sha256(after),
    )


def run_captured_scenario_incident(
    *,
    scenario: IncidentScenario,
    request: ModelRequest,
    capture: ModelCapture,
    run_id: str,
) -> CapturedScenarioIncidentRun:
    """Validate one captured proposal and execute the actual local tool."""
    if not isinstance(scenario, IncidentScenario):
        raise ContractError("invalid incident scenario")

    if (
        type(run_id) is not str
        or re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.-]{0,47}",
            run_id,
        ) is None
    ):
        raise ContractError("invalid scenario run_id")

    if not isinstance(request, ModelRequest):
        raise ContractError("invalid model request")

    trusted = build_scenario_incident_request(
        scenario=scenario,
        model=request.model,
    )

    if request.request_sha256 != trusted.request_sha256:
        raise ContractError(
            "model request does not match the exact scenario"
        )

    proposal = replay_json_capture(
        request=request,
        capture=capture,
    )

    proposal_sha = canonical_sha256(proposal)
    reason = _rejection_reason(proposal)
    scenario_sha = scenario.scenario_sha256

    state_start = {
        "phase": "captured",
        "scenario_sha256": scenario_sha,
        "request_sha256": request.request_sha256,
        "capture_sha256": capture.capture_sha256,
    }
    state_replayed = {
        "phase": "proposal_replayed",
        "scenario_sha256": scenario_sha,
        "proposal_sha256": proposal_sha,
    }

    events = [
        _event(
            sequence=0,
            kind=EventKind.DECISION,
            operation="replay_scenario_action",
            input_payload=state_start,
            output_payload=proposal,
            before=state_start,
            after=state_replayed,
        )
    ]

    tool = None
    threshold = None
    report = None
    evaluation = None

    if reason is not None:
        status = "rejected"
        events.append(
            _event(
                sequence=1,
                kind=EventKind.TERMINATION,
                operation="reject_scenario_action",
                input_payload=proposal,
                output_payload={"reason": reason},
                before=state_replayed,
                after={
                    "phase": "rejected",
                    "reason": reason,
                },
            )
        )
    else:
        tool = proposal["tool"]
        threshold = proposal["threshold"]
        status = "executed"

        service_rows, selected = filter_incident_rows(
            records=scenario.records,
            target_service=scenario.target_service,
            tool_name=tool,
            threshold=threshold,
        )

        report = TriageReport(
            service=scenario.target_service,
            incident_ids=tuple(row[0] for row in selected),
            count=len(selected),
        )

        state_executed = {
            "phase": "tool_executed",
            "scenario_sha256": scenario_sha,
            "report_sha256": report.report_sha256,
        }

        events.append(
            _event(
                sequence=1,
                kind=EventKind.TOOL_CALL,
                operation=tool,
                input_payload={
                    "scenario_sha256": scenario_sha,
                    "tool": tool,
                    "threshold": threshold,
                    "service_row_ids": [
                        row[0] for row in service_rows
                    ],
                },
                output_payload=report.canonical_payload(),
                before=state_replayed,
                after=state_executed,
            )
        )

        evaluation = evaluate_incident_scenario(
            scenario=scenario,
            report=report,
        )

        if (
            evaluation.scenario_sha256 != scenario_sha
            or evaluation.report != report
        ):
            raise ContractError(
                "scenario execution and evaluation evidence disagree"
            )

        events.append(
            _event(
                sequence=2,
                kind=EventKind.TERMINATION,
                operation="evaluate_scenario_report",
                input_payload=report.canonical_payload(),
                output_payload={
                    "evaluation_sha256":
                        evaluation.evaluation_evidence_sha256,
                    "passed": evaluation.passed,
                },
                before=state_executed,
                after={
                    "phase": "evaluated",
                    "passed": evaluation.passed,
                    "scenario_sha256": scenario_sha,
                },
            )
        )

    trace = AgentTrace(
        run_id=run_id,
        events=tuple(events),
    )

    return CapturedScenarioIncidentRun(
        run_id=run_id,
        scenario_sha256=scenario_sha,
        request_sha256=request.request_sha256,
        capture_sha256=capture.capture_sha256,
        proposal_sha256=proposal_sha,
        status=status,
        rejection_reason=reason,
        selected_tool=tool,
        threshold=threshold,
        report=report,
        evaluation=evaluation,
        trace=trace,
    )

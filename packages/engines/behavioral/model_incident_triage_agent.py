"""Captured model-proposed incident triage using real local filters.

A recorded structured proposal selects one allowlisted severity
filter and a bounded threshold. The incident environment executes
the action and evaluates its result against the fixed task.

No tool output is accepted from the model itself. Offline replay
is development evidence, not fresh provider inference or scientific
generalization.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import re

from environments.agent.incident_triage import (
    IncidentTriageRun,
    expected_incident_ids,
    incident_triage_task_spec,
    run_configured_incident_triage,
)
from packages.contracts import ContractError
from packages.core.hetren_diagnosis.contracts import (
    AgentTrace,
    EventKind,
    TraceEvent,
    canonical_sha256,
)
from packages.model_capture import (
    ModelCapture,
    ModelRequest,
    replay_json_capture,
)


_ALLOWED_TOOLS = (
    "inclusive_severity_filter",
    "strict_severity_filter",
)

_SYSTEM_PROMPT = (
    "You are a bounded incident-triage tool planner. "
    "Choose one provided severity-filter tool and its integer "
    "threshold. Return only the structured action requested by "
    "the response schema. Never invent incident IDs or tool results."
)


def build_incident_triage_request(
    *,
    model: str,
) -> ModelRequest:
    """Build a task-bound structured model request."""
    service, threshold, incidents = incident_triage_task_spec()

    max_severity = max(row[2] for row in incidents)

    schema = {
        "type": "object",
        "properties": {
            "tool": {
                "type": "string",
                "enum": list(_ALLOWED_TOOLS),
            },
            "threshold": {
                "type": "integer",
                "minimum": 0,
                "maximum": max_severity,
            },
        },
        "required": ["tool", "threshold"],
        "additionalProperties": False,
    }

    rows = "\n".join(
        f"{incident_id}: service={record_service}, severity={severity}"
        for incident_id, record_service, severity in incidents
    )

    prompt = (
        f"Investigate service={service}. Select incidents whose "
        f"severity is greater than or equal to {threshold}.\n"
        f"Available incident records:\n{rows}\n"
        "Choose exactly one filter tool and integer threshold. "
        "Do not return incident IDs, counts, or fabricated results."
    )

    return ModelRequest(
        provider="openai",
        model=model,
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=prompt,
        response_schema_name="hetren_incident_triage_action_v1",
        response_schema=schema,
        generation_parameters={},
    )


@dataclass(frozen=True)
class CapturedIncidentTriageRun:
    """Model proposal plus independently executed local workflow."""

    run_id: str
    request_sha256: str
    capture_sha256: str
    proposal_sha256: str
    status: str
    rejection_reason: str | None
    selected_tool: str | None
    threshold: int | None
    environment_run: IncidentTriageRun | None
    trace: AgentTrace

    @property
    def passed(self) -> bool:
        return (
            self.status == "executed"
            and self.environment_run is not None
            and self.environment_run.passed
        )

    @property
    def execution_evidence_sha256(self) -> str:
        return canonical_sha256({
            "record_type": "CapturedIncidentTriageRun",
            "run_id": self.run_id,
            "request_sha256": self.request_sha256,
            "capture_sha256": self.capture_sha256,
            "proposal_sha256": self.proposal_sha256,
            "status": self.status,
            "rejection_reason": self.rejection_reason,
            "selected_tool": self.selected_tool,
            "threshold": self.threshold,
            "environment_evidence_sha256": (
                None if self.environment_run is None
                else self.environment_run.execution_evidence_sha256
            ),
            "trace_sha256": self.trace.trace_sha256,
            "passed": self.passed,
        })


def _rejection_reason(proposal: object) -> str | None:
    if type(proposal) is not dict:
        return "proposal_not_object"

    if set(proposal) != {"tool", "threshold"}:
        return "invalid_proposal_shape"

    if (
        type(proposal["tool"]) is not str
        or proposal["tool"] not in _ALLOWED_TOOLS
    ):
        return "unsupported_tool"

    _, _, incidents = incident_triage_task_spec()
    max_severity = max(row[2] for row in incidents)
    value = proposal["threshold"]

    if (
        type(value) is not int
        or value < 0
        or value > max_severity
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
        component="model_incident_triage",
        operation=operation,
        input_sha256=canonical_sha256(input_payload),
        output_sha256=canonical_sha256(output_payload),
        state_before_sha256=canonical_sha256(before),
        state_after_sha256=canonical_sha256(after),
    )


def run_captured_incident_triage(
    *,
    request: ModelRequest,
    capture: ModelCapture,
    run_id: str,
) -> CapturedIncidentTriageRun:
    """Replay a captured action, validate it, then execute locally."""
    if (
        type(run_id) is not str
        or re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.-]{0,47}",
            run_id,
        ) is None
    ):
        raise ContractError("invalid model incident run_id")

    if not isinstance(request, ModelRequest):
        raise ContractError("request must be a ModelRequest")

    trusted = build_incident_triage_request(model=request.model)

    if request.request_sha256 != trusted.request_sha256:
        raise ContractError("untrusted incident task request")

    # This verifies the original request/capture binding and
    # rejects tampered recorded model responses.
    proposal = replay_json_capture(
        request=request,
        capture=capture,
    )

    proposal_hash = canonical_sha256(proposal)
    reason = _rejection_reason(proposal)

    before = {
        "phase": "captured",
        "request_sha256": request.request_sha256,
        "capture_sha256": capture.capture_sha256,
    }
    after = {
        "phase": "proposal_replayed",
        "proposal_sha256": proposal_hash,
    }

    events = [
        _event(
            sequence=0,
            kind=EventKind.DECISION,
            operation="replay_captured_action",
            input_payload=before,
            output_payload=proposal,
            before=before,
            after=after,
        )
    ]

    environment_run = None
    tool = None
    threshold = None

    if reason is not None:
        status = "rejected"
        events.append(
            _event(
                sequence=1,
                kind=EventKind.TERMINATION,
                operation="reject_invalid_proposal",
                input_payload=proposal,
                output_payload={"reason": reason},
                before=after,
                after={"phase": "rejected", "reason": reason},
            )
        )
    else:
        tool = proposal["tool"]
        threshold = proposal["threshold"]
        status = "executed"

        environment_run = run_configured_incident_triage(
            tool_name=tool,
            threshold=threshold,
            run_id=run_id,
        )

        # Retain original environment event content and hashes.
        # Only reindex the sequence after the model-decision event.
        events.extend(
            replace(event, sequence=index + 1)
            for index, event in enumerate(
                environment_run.trace.events
            )
        )

    trace = AgentTrace(
        run_id=run_id,
        events=tuple(events),
    )

    return CapturedIncidentTriageRun(
        run_id=run_id,
        request_sha256=request.request_sha256,
        capture_sha256=capture.capture_sha256,
        proposal_sha256=proposal_hash,
        status=status,
        rejection_reason=reason,
        selected_tool=tool,
        threshold=threshold,
        environment_run=environment_run,
        trace=trace,
    )

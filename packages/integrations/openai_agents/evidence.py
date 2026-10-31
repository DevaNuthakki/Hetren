"""Map SDK hook and span evidence into Hetren records.

Authority
---------
Gateway stage records are authoritative for actions, arguments,
observations, and state. Hook events and spans add model-call and timing
context. ``reconcile`` compares the views invocation by invocation and
returns every disagreement as a structured ``Discrepancy``; nothing is
silently resolved in favour of either side.

Outputs
-------
- ``build_run_trace``: one ``AgentTrace`` interleaving model calls (from
  hooks) with gateway stage events, ending in a termination event.
- ``build_execution_record``: an ``ExecutionRecord`` whose references bind
  the run's inputs, outputs, traces, and manifest by digest.

All fields are codes, names, ordinals, and digests. No free-text summaries
are written into these records.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from importlib.metadata import version

from packages.action_gateway import ToolStageRecord
from packages.contracts import (
    ContractError,
    ExecutionRecord,
    ExecutionStatus,
    canonical_sha256,
)
from packages.core.hetren_diagnosis.contracts import (
    AgentTrace,
    EventKind,
    TraceEvent,
)
from packages.integrations.openai_agents.hooks import (
    HookEvent,
    HookKind,
    text_sha256,
)
from packages.integrations.openai_agents.tools import result_text_from_records
from packages.integrations.openai_agents.tracing import SpanRecord


SENSITIVE_DATA_CAPTURE = False


class DiscrepancyKind:
    MODEL_CALL_WITHOUT_GATEWAY_RECORD = "model_call_without_gateway_record"
    GATEWAY_RECORD_WITHOUT_MODEL_CALL = "gateway_record_without_model_call"
    TOOL_NAME_MISMATCH = "tool_name_mismatch"
    ARGUMENTS_MISMATCH = "arguments_mismatch"
    TOOL_START_MISMATCH = "tool_start_mismatch"
    TOOL_RESULT_MISMATCH = "tool_result_mismatch"
    SPAN_COUNT_MISMATCH = "span_count_mismatch"
    SPAN_NAME_MISMATCH = "span_name_mismatch"
    SPAN_ERROR_MISMATCH = "span_error_mismatch"
    SPAN_CONTENT_CAPTURED = "span_content_captured"
    TRACE_MISSING = "trace_missing"


@dataclass(frozen=True)
class Discrepancy:
    kind: str
    position: int | None
    fields: dict[str, object]

    def canonical_payload(self) -> dict[str, object]:
        return {"kind": self.kind, "position": self.position, "fields": self.fields}


@dataclass(frozen=True)
class SdkEvidence:
    hook_events: tuple[HookEvent, ...]
    spans: tuple[SpanRecord, ...]
    discrepancies: tuple[Discrepancy, ...]
    sensitive_data_capture: bool = SENSITIVE_DATA_CAPTURE

    def canonical_payload(self) -> dict[str, object]:
        """Hashable SDK evidence; timing lives in ``timing_payload``."""
        return {
            "record_type": "SdkEvidence",
            "schema_version": 1,
            "sensitive_data_capture": self.sensitive_data_capture,
            "hook_events": [event.canonical_payload() for event in self.hook_events],
            "spans": [span.canonical_payload() for span in self.spans],
            "discrepancies": [item.canonical_payload() for item in self.discrepancies],
        }

    def timing_payload(self) -> dict[str, object]:
        return {
            "hook_events": [
                {"sequence": event.sequence, "recorded_at": event.recorded_at}
                for event in self.hook_events
            ],
            "spans": [span.timing_payload() for span in self.spans],
        }

    @property
    def evidence_sha256(self) -> str:
        return canonical_sha256(self.canonical_payload())


@dataclass(frozen=True)
class _Invocation:
    invocation_id: str
    tool_name: str
    arguments_sha256: str
    records: tuple[ToolStageRecord, ...]

    @property
    def attempted(self) -> bool:
        return any(record.stage.value == "observed" for record in self.records)

    @property
    def result_sha256(self) -> str:
        return text_sha256(result_text_from_records(self.records))


def _invocations(stage_records: tuple[ToolStageRecord, ...]) -> list[_Invocation]:
    grouped: dict[str, list[ToolStageRecord]] = {}

    for record in stage_records:
        grouped.setdefault(record.invocation_id, []).append(record)

    return [
        _Invocation(
            invocation_id=invocation_id,
            tool_name=records[0].tool_name,
            arguments_sha256=records[0].arguments_sha256,
            records=tuple(records),
        )
        for invocation_id, records in grouped.items()
    ]


def _hook_fields(events: tuple[HookEvent, ...], kind: HookKind) -> list[dict[str, object]]:
    return [event.fields for event in events if event.kind is kind]


def reconcile(
    stage_records: tuple[ToolStageRecord, ...],
    hook_events: tuple[HookEvent, ...],
    spans: tuple[SpanRecord, ...],
) -> tuple[Discrepancy, ...]:
    invocations = _invocations(stage_records)
    found: list[Discrepancy] = []

    model_calls = [
        call
        for fields in _hook_fields(hook_events, HookKind.LLM_END)
        for call in fields["tool_calls"]
    ]

    for position in range(max(len(model_calls), len(invocations))):
        call = model_calls[position] if position < len(model_calls) else None
        invocation = invocations[position] if position < len(invocations) else None

        if invocation is None:
            found.append(Discrepancy(
                DiscrepancyKind.MODEL_CALL_WITHOUT_GATEWAY_RECORD, position,
                {"tool_name": call["tool_name"], "tool_call_id": call["tool_call_id"]},
            ))
            continue

        if call is None:
            found.append(Discrepancy(
                DiscrepancyKind.GATEWAY_RECORD_WITHOUT_MODEL_CALL, position,
                {"tool_name": invocation.tool_name, "invocation_id": invocation.invocation_id},
            ))
            continue

        if call["tool_name"] != invocation.tool_name:
            found.append(Discrepancy(
                DiscrepancyKind.TOOL_NAME_MISMATCH, position,
                {"model_tool_name": call["tool_name"], "gateway_tool_name": invocation.tool_name},
            ))

        if call["arguments_sha256"] != invocation.arguments_sha256:
            found.append(Discrepancy(
                DiscrepancyKind.ARGUMENTS_MISMATCH, position,
                {
                    "model_arguments_sha256": call["arguments_sha256"],
                    "gateway_arguments_sha256": invocation.arguments_sha256,
                },
            ))

    tool_starts = _hook_fields(hook_events, HookKind.TOOL_START)
    tool_ends = _hook_fields(hook_events, HookKind.TOOL_END)

    for position, invocation in enumerate(invocations):
        start = tool_starts[position] if position < len(tool_starts) else None

        if start is None or (
            start["tool_name"] != invocation.tool_name
            or start["arguments_sha256"] != invocation.arguments_sha256
        ):
            found.append(Discrepancy(
                DiscrepancyKind.TOOL_START_MISMATCH, position,
                {"invocation_id": invocation.invocation_id, "hook_present": start is not None},
            ))

        end = tool_ends[position] if position < len(tool_ends) else None

        if end is not None and end["result_sha256"] != invocation.result_sha256:
            found.append(Discrepancy(
                DiscrepancyKind.TOOL_RESULT_MISMATCH, position,
                {
                    "invocation_id": invocation.invocation_id,
                    "hook_result_sha256": end["result_sha256"],
                    "gateway_result_sha256": invocation.result_sha256,
                },
            ))

    if not spans:
        found.append(Discrepancy(DiscrepancyKind.TRACE_MISSING, None, {}))
        return tuple(found)

    function_spans = [span for span in spans if span.span_type == "function"]

    if len(function_spans) != len(invocations):
        found.append(Discrepancy(
            DiscrepancyKind.SPAN_COUNT_MISMATCH, None,
            {"function_spans": len(function_spans), "gateway_invocations": len(invocations)},
        ))

    for position, (span, invocation) in enumerate(zip(function_spans, invocations)):
        if span.name != invocation.tool_name:
            found.append(Discrepancy(
                DiscrepancyKind.SPAN_NAME_MISMATCH, position,
                {"span_name": span.name, "gateway_tool_name": invocation.tool_name},
            ))

        if span.error_present:
            found.append(Discrepancy(
                DiscrepancyKind.SPAN_ERROR_MISMATCH, position,
                {"invocation_id": invocation.invocation_id, "span_error_sha256": span.error_sha256},
            ))

    for span in spans:
        if span.content_captured:
            found.append(Discrepancy(
                DiscrepancyKind.SPAN_CONTENT_CAPTURED, span.ordinal,
                {"span_type": span.span_type},
            ))

    return tuple(found)


def build_run_trace(
    *,
    run_id: str,
    stage_records: tuple[ToolStageRecord, ...],
    hook_events: tuple[HookEvent, ...],
    initial_state_sha256: str,
    final_state_sha256: str,
    task_input_sha256: str,
    final_output_sha256: str,
    status_code: str,
) -> AgentTrace:
    """Interleave model calls with gateway stage events in run order."""
    invocations = _invocations(stage_records)
    events: list[TraceEvent] = []
    state = initial_state_sha256
    next_invocation = 0
    pending_input: str | None = None

    def append(event: TraceEvent) -> None:
        events.append(replace(event, sequence=len(events)))

    def append_invocation(invocation: _Invocation) -> str:
        for record in invocation.records:
            append(record.to_trace_event())

        return invocation.records[-1].state_after_sha256

    for hook in hook_events:
        if hook.kind is HookKind.LLM_START:
            pending_input = str(hook.fields["input_sha256"])
        elif hook.kind is HookKind.LLM_END:
            append(TraceEvent(
                sequence=0,
                kind=EventKind.DECISION,
                component="model",
                operation=f"model_call:{hook.fields['turn']}",
                input_sha256=pending_input or canonical_sha256({}),
                output_sha256=str(hook.fields["output_sha256"]),
                state_before_sha256=state,
                state_after_sha256=state,
            ))
        elif hook.kind is HookKind.TOOL_START and next_invocation < len(invocations):
            state = append_invocation(invocations[next_invocation])
            next_invocation += 1

    for invocation in invocations[next_invocation:]:
        state = append_invocation(invocation)

    append(TraceEvent(
        sequence=0,
        kind=EventKind.TERMINATION,
        component="agent",
        operation=f"run:{status_code}",
        input_sha256=task_input_sha256,
        output_sha256=final_output_sha256,
        state_before_sha256=state,
        state_after_sha256=final_state_sha256,
    ))

    return AgentTrace(run_id=run_id, events=tuple(events))


@dataclass(frozen=True)
class ExecutionScope:
    """Bindings supplied by the caller for an ExecutionRecord."""

    tenant_id: str
    project_id: str
    goal_contract_id: str
    goal_contract_sha256: str
    system_snapshot_id: str
    system_snapshot_sha256: str
    method_proposal_id: str
    method_proposal_sha256: str
    environment_reference: str | None = None


_EXECUTION_STATUS = {
    "completed": ExecutionStatus.COMPLETED,
    "max_turns_exceeded": ExecutionStatus.FAILED,
    "error": ExecutionStatus.FAILED,
}


def run_manifest(record: object) -> dict[str, object]:
    return {
        "record_type": "AgentRunManifest",
        "schema_version": 1,
        "run_id": record.run_id,
        "provenance": record.provenance.value,
        "model_id": record.model_id,
        "agent_name": record.agent_name,
        "instructions_sha256": record.instructions_sha256,
        "tool_definitions_sha256": record.tool_definitions_sha256,
        "sdk_versions": {
            "openai": version("openai"),
            "openai-agents": version("openai-agents"),
        },
        "sensitive_data_capture": record.sdk_evidence.sensitive_data_capture,
    }


def build_execution_record(record: object, scope: ExecutionScope) -> ExecutionRecord:
    if not isinstance(scope, ExecutionScope):
        raise ContractError("scope must be an ExecutionScope")

    status = _EXECUTION_STATUS[record.status.value]
    output_references = [f"final_state:sha256:{record.final_state_sha256}"]

    if record.final_message is not None:
        output_references.append(
            f"final_message:sha256:{text_sha256(record.final_message)}"
        )

    limitations = list(record.limitations) + [
        "sdk spans and hooks are context; gateway stage records are authoritative "
        "for actions and state",
    ]

    if record.sdk_evidence.discrepancies:
        limitations.append(
            "sdk evidence disagrees with gateway records; see discrepancies"
        )

    return ExecutionRecord(
        tenant_id=scope.tenant_id,
        project_id=scope.project_id,
        execution_id=record.run_id,
        goal_contract_id=scope.goal_contract_id,
        goal_contract_sha256=scope.goal_contract_sha256,
        system_snapshot_id=scope.system_snapshot_id,
        system_snapshot_sha256=scope.system_snapshot_sha256,
        method_proposal_id=scope.method_proposal_id,
        method_proposal_sha256=scope.method_proposal_sha256,
        runner_id="openai-agents-sdk",
        runner_version=version("openai-agents"),
        environment_reference=scope.environment_reference,
        execution_manifest_reference=(
            f"manifest:sha256:{canonical_sha256(run_manifest(record))}"
        ),
        status=status,
        exit_code=None,
        termination_reason=(
            None if status is ExecutionStatus.COMPLETED else record.status.value
        ),
        input_references=(
            f"task_input:sha256:{text_sha256(record.task_input)}",
            f"instructions:sha256:{record.instructions_sha256}",
            f"tool_definitions:sha256:{record.tool_definitions_sha256}",
        ),
        output_references=tuple(output_references),
        trace_references=(
            f"stage_records:sha256:{record.stage_records_sha256}",
            f"run_trace:sha256:{record.run_trace().trace_sha256}",
            f"sdk_evidence:sha256:{record.sdk_evidence.evidence_sha256}",
        ),
        limitations=tuple(limitations),
    )


__all__ = [
    "Discrepancy",
    "DiscrepancyKind",
    "ExecutionScope",
    "SENSITIVE_DATA_CAPTURE",
    "SdkEvidence",
    "build_execution_record",
    "build_run_trace",
    "reconcile",
    "run_manifest",
]

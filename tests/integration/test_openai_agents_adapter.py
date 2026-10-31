from dataclasses import replace
from functools import partial
import json
import re
import socket

import pytest
from agents.tracing import get_trace_provider
from agents.tracing.processors import BackendSpanExporter, BatchTraceProcessor

from environments.support.faults import IdentifierMappingSwap, inject_fault
from environments.support.fixtures import SupportEnvironment
from environments.support.tools import (
    SUPPORT_TOOL_DESCRIPTIONS,
    SUPPORT_TOOL_SCHEMAS,
    SUPPORT_TOOLS,
)
from packages.action_gateway import AllowListPolicy, GatedTool, ToolGateway
from packages.contracts import ExecutionStatus, canonical_sha256
from packages.core.hetren_diagnosis.contracts import EventKind
from packages.integrations.openai_agents import (
    DiscrepancyKind,
    ExecutionScope,
    HookKind,
    RunProvenance,
    RunStatus,
    SENSITIVE_DATA_CAPTURE,
    build_execution_record,
    gateway_function_tools,
    install_local_tracing,
    reconcile,
    run_agent,
    run_manifest,
)
import packages.integrations.openai_agents.tools as bridge
from packages.integrations.openai_agents.tracing import SpanCollector
from packages.support_agent import ScriptedSupportModel, build_support_agent, task_message
from packages.support_evaluator import (
    EXAMPLES,
    assert_no_leaks,
    fault,
    scan_agent_outputs,
    scan_content,
)


AGENT_TOOLS = ("read_ticket", "lookup_account", "route_ticket")

SCOPE = ExecutionScope(
    tenant_id="tenant-dev",
    project_id="project-support",
    goal_contract_id="goal-0001",
    goal_contract_sha256="a" * 64,
    system_snapshot_id="snapshot-0001",
    system_snapshot_sha256="b" * 64,
    method_proposal_id="proposal-0001",
    method_proposal_sha256="c" * 64,
    environment_reference="env-support-synthetic",
)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("network access attempted in an offline test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


@pytest.fixture
def export_calls(monkeypatch):
    calls = []

    monkeypatch.setattr(
        BackendSpanExporter, "export", lambda self, items: calls.append(("export", items)),
    )
    for name in ("on_trace_start", "on_trace_end", "on_span_start", "on_span_end"):
        monkeypatch.setattr(
            BatchTraceProcessor, name,
            lambda self, item, _name=name: calls.append((_name, item)),
        )

    return calls


def _run(environment, ticket_id, *, model=None, run_id="run-0001", max_turns=10):
    gateway = ToolGateway(
        tools=[
            GatedTool(
                name, partial(SUPPORT_TOOLS[name], environment),
                SUPPORT_TOOL_SCHEMAS[name], SUPPORT_TOOL_DESCRIPTIONS[name],
            )
            for name in AGENT_TOOLS
        ],
        policy=AllowListPolicy(AGENT_TOOLS),
        state_sha256=environment.state_sha256,
    )
    agent = build_support_agent(
        environment=environment, tools=gateway_function_tools(gateway),
        model=model or ScriptedSupportModel(),
    )
    return run_agent(
        agent=agent, task_input=task_message(ticket_id), gateway=gateway,
        run_id=run_id, provenance=RunProvenance.SCRIPTED, max_turns=max_turns,
    )


def _kinds(record) -> list[str]:
    return [item.kind for item in record.sdk_evidence.discrepancies]


# Local tracing only


def test_local_processor_replaces_the_default_exporter(export_calls):
    provider = get_trace_provider()
    processor = install_local_tracing()

    assert provider._multi_processor._processors == (processor,)  # pinned SDK internals

    record = _run(SupportEnvironment(), "T-1001")

    assert provider._multi_processor._processors == (processor,)
    assert export_calls == []
    assert record.sdk_evidence.spans
    assert processor.unrouted_spans == 0


def test_sensitive_data_capture_is_off_and_recorded():
    record = _run(SupportEnvironment(), "T-1001")

    assert SENSITIVE_DATA_CAPTURE is False
    assert record.sdk_evidence.sensitive_data_capture is False
    assert run_manifest(record)["sensitive_data_capture"] is False
    assert not any(span.content_captured for span in record.sdk_evidence.spans)


def test_captured_span_content_would_be_flagged():
    collector = SpanCollector()
    collector.end({
        "id": "span_1", "parent_id": None, "error": None,
        "span_data": {"type": "function", "name": "read_ticket", "input": "{...}", "output": None},
    })
    spans = collector.records()

    assert spans[0].content_captured is True
    kinds = [item.kind for item in reconcile((), (), spans)]
    assert DiscrepancyKind.SPAN_CONTENT_CAPTURED in kinds


# Clean runs


def test_clean_run_has_consistent_hooks_spans_and_gateway_records():
    record = _run(SupportEnvironment(), "T-1003")

    assert record.sdk_evidence.discrepancies == ()
    assert [event.kind for event in record.sdk_evidence.hook_events] == (
        [HookKind.AGENT_START]
        + [HookKind.LLM_START, HookKind.LLM_END, HookKind.TOOL_START, HookKind.TOOL_END] * 3
        + [HookKind.LLM_START, HookKind.LLM_END, HookKind.AGENT_END]
    )
    spans = record.sdk_evidence.spans
    assert [span.name for span in spans if span.span_type == "function"] == list(AGENT_TOOLS)
    assert [span.span_type for span in spans if span.parent_ordinal is None] == ["custom"]


def test_identical_runs_hash_identically_despite_ids_and_timestamps():
    first = _run(SupportEnvironment(), "T-1003")
    second = _run(SupportEnvironment(), "T-1003")

    assert first.record_sha256 == second.record_sha256
    assert first.run_trace().trace_sha256 == second.run_trace().trace_sha256
    timing = first.timing_payload()
    assert all(event["recorded_at"] for event in timing["hook_events"])
    assert all(span["started_at"] and span["ended_at"] for span in timing["spans"])
    assert "started_at" not in json.dumps(first.canonical_payload())


def test_run_trace_interleaves_model_calls_with_gateway_stages():
    record = _run(SupportEnvironment(), "T-1003")
    trace = record.run_trace()
    events = trace.events

    assert [event.sequence for event in events] == list(range(len(events)))
    assert [event.operation for event in events if event.component == "model"] == [
        "model_call:1", "model_call:2", "model_call:3", "model_call:4",
    ]
    assert events[0].component == "model"
    assert events[1].operation == "proposed:proposed"
    assert events[-1].kind is EventKind.TERMINATION
    assert events[-1].operation == "run:completed"
    assert events[0].state_before_sha256 == record.initial_state_sha256
    assert events[-1].state_after_sha256 == record.final_state_sha256

    gateway_events = [event for event in events if event.component in AGENT_TOOLS]
    assert len(gateway_events) == len(record.stage_records)

    for previous, current in zip(events, events[1:]):
        assert current.state_before_sha256 == previous.state_after_sha256


def test_malformed_arguments_agree_between_hooks_and_gateway():
    class Malformed(ScriptedSupportModel):
        def decide(self, system_instructions, input_items):
            decision = super().decide(system_instructions, input_items)
            if getattr(decision, "name", None) == "read_ticket":
                return decision.model_copy(update={"arguments": '{"ticket_id": "T-1003"'})
            return decision

    record = _run(SupportEnvironment(), "T-1003", model=Malformed())

    assert record.stage_records[1].payload["reason"] == "arguments_not_json"
    assert record.sdk_evidence.discrepancies == ()


# Disagreements are recorded, not resolved


def test_tool_call_rejected_by_the_sdk_is_recorded_as_a_discrepancy():
    class Rogue(ScriptedSupportModel):
        def decide(self, system_instructions, input_items):
            return self._call(1, "delete_ticket", {"ticket_id": "T-1001"})

    record = _run(SupportEnvironment(), "T-1001", model=Rogue())

    assert record.status is RunStatus.ERROR
    assert record.error["type"] == "ModelBehaviorError"
    assert record.stage_records == ()
    (item,) = record.sdk_evidence.discrepancies
    assert item.canonical_payload() == {
        "kind": DiscrepancyKind.MODEL_CALL_WITHOUT_GATEWAY_RECORD,
        "position": 0,
        "fields": {"tool_name": "delete_ticket", "tool_call_id": "call_scripted_1"},
    }


def test_result_altered_after_the_gateway_is_a_discrepancy(monkeypatch):
    original = bridge.tool_result_text

    def altered(result):
        text = original(result)
        return text.replace("enterprise", "standard") if result.tool_name == "lookup_account" else text

    monkeypatch.setattr(bridge, "tool_result_text", altered)

    record = _run(SupportEnvironment(), "T-1003")

    assert _kinds(record) == [DiscrepancyKind.TOOL_RESULT_MISMATCH]
    assert record.sdk_evidence.discrepancies[0].position == 1
    assert record.final_message == "Routed T-1003 to Q-GENERAL."


def test_missing_or_partial_sdk_evidence_is_a_discrepancy():
    record = _run(SupportEnvironment(), "T-1003")
    hooks = record.sdk_evidence.hook_events
    spans = record.sdk_evidence.spans

    without_trace = [item.kind for item in reconcile(record.stage_records, hooks, ())]
    assert DiscrepancyKind.TRACE_MISSING in without_trace

    dropped_start = tuple(
        event for event in hooks if not (event.kind is HookKind.TOOL_START and event.fields["tool_name"] == "route_ticket")
    )
    assert DiscrepancyKind.TOOL_START_MISMATCH in [
        item.kind for item in reconcile(record.stage_records, dropped_start, spans)
    ]

    fewer_spans = tuple(span for span in spans if span.name != "lookup_account")
    assert DiscrepancyKind.SPAN_COUNT_MISMATCH in [
        item.kind for item in reconcile(record.stage_records, hooks, fewer_spans)
    ]

    errored = tuple(
        replace(span, error_present=True, error_sha256="d" * 64) if span.name == "read_ticket" else span
        for span in spans
    )
    assert DiscrepancyKind.SPAN_ERROR_MISMATCH in [
        item.kind for item in reconcile(record.stage_records, hooks, errored)
    ]

    assert DiscrepancyKind.GATEWAY_RECORD_WITHOUT_MODEL_CALL in [
        item.kind
        for item in reconcile(
            record.stage_records,
            tuple(event for event in hooks if event.kind is not HookKind.LLM_END),
            spans,
        )
    ]


# ExecutionRecord mapping


def test_execution_record_binds_inputs_outputs_and_traces():
    record = _run(SupportEnvironment(), "T-1003")

    execution = build_execution_record(record, SCOPE)

    assert execution.execution_id == "run-0001"
    assert execution.status is ExecutionStatus.COMPLETED
    assert execution.termination_reason is None
    assert execution.runner_id == "openai-agents-sdk"
    assert execution.runner_version == "0.24.0"
    assert execution.trace_references == (
        f"stage_records:sha256:{record.stage_records_sha256}",
        f"run_trace:sha256:{record.run_trace().trace_sha256}",
        f"sdk_evidence:sha256:{record.sdk_evidence.evidence_sha256}",
    )
    assert execution.execution_manifest_reference == (
        f"manifest:sha256:{canonical_sha256(run_manifest(record))}"
    )
    assert f"final_state:sha256:{record.final_state_sha256}" in execution.output_references
    assert build_execution_record(record, SCOPE).execution_sha256 == execution.execution_sha256


def test_abnormal_runs_map_to_failed_execution_with_reason_codes():
    class Looping(ScriptedSupportModel):
        def decide(self, system_instructions, input_items):
            return self._call(self.turns, "read_ticket", {"ticket_id": "T-1003"})

    record = _run(SupportEnvironment(), "T-1003", model=Looping(), max_turns=2)
    execution = build_execution_record(record, SCOPE)

    assert execution.status is ExecutionStatus.FAILED
    assert execution.termination_reason == "max_turns_exceeded"


def test_discrepancies_are_carried_into_execution_limitations():
    class Rogue(ScriptedSupportModel):
        def decide(self, system_instructions, input_items):
            return self._call(1, "delete_ticket", {"ticket_id": "T-1001"})

    execution = build_execution_record(_run(SupportEnvironment(), "T-1001", model=Rogue()), SCOPE)

    assert execution.termination_reason == "error"
    assert "sdk evidence disagrees with gateway records; see discrepancies" in execution.limitations


# Structured records and leakage on every new surface


_IDENTIFIER = re.compile(r"\b(?:T|A|C|Q)-[0-9A-Z]{4,12}\b")


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _strings(item)


def _adapter_surfaces(record) -> dict[str, object]:
    return {
        "sdk_evidence": record.sdk_evidence.canonical_payload(),
        "timing": record.timing_payload(),
        "run_trace": record.run_trace().canonical_payload(),
        "execution_record": build_execution_record(record, SCOPE).canonical_payload(),
        "manifest": run_manifest(record),
        "run_record": record.evidence_payload(),
    }


@pytest.mark.parametrize("example_name", sorted(EXAMPLES))
def test_adapter_surfaces_contain_no_evaluator_content(example_name):
    spec = EXAMPLES[example_name]
    environment = SupportEnvironment()

    if spec.fault_id is not None:
        inject_fault(environment, IdentifierMappingSwap(**fault(spec.fault_id).parameters))

    record = _run(environment, spec.target_ticket_id)

    assert_no_leaks(scan_content(_adapter_surfaces(record)))
    assert_no_leaks(scan_agent_outputs({"agent_output": record.agent_output_payload()}))


@pytest.mark.parametrize("example_name", sorted(EXAMPLES))
def test_adapter_records_hold_no_free_text_combining_identifiers(example_name):
    spec = EXAMPLES[example_name]
    environment = SupportEnvironment()

    if spec.fault_id is not None:
        inject_fault(environment, IdentifierMappingSwap(**fault(spec.fault_id).parameters))

    record = _run(environment, spec.target_ticket_id)

    for surface, value in _adapter_surfaces(record).items():
        for text in _strings(value):
            assert len(set(_IDENTIFIER.findall(text))) <= 1, (surface, text)

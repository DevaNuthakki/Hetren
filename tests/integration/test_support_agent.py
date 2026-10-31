from functools import partial
import json
import socket

import pytest
from openai.types.responses import ResponseFunctionToolCall

from environments.support.faults import IdentifierMappingSwap, inject_fault
from environments.support.fixtures import SupportEnvironment
from environments.support.tools import (
    SUPPORT_TOOL_DESCRIPTIONS,
    SUPPORT_TOOL_SCHEMAS,
    SUPPORT_TOOLS,
)
from packages.action_gateway import AllowListPolicy, GatedTool, StageStatus, ToolGateway
from packages.contracts import ContractError
from packages.integrations.openai_agents import (
    RunProvenance,
    RunStatus,
    gateway_function_tools,
    run_agent,
)
from packages.integrations.run_ids import RunIdAllocator
from packages.support_agent import (
    ScriptedSupportModel,
    build_support_agent,
    support_instructions,
    task_message,
)
from packages.support_evaluator import (
    EXAMPLES,
    NEUTRAL_RUN_ID,
    assert_no_leaks,
    fault,
    scan_agent_outputs,
    scan_content,
    scan_identifiers,
)


AGENT_TOOLS = ("read_ticket", "lookup_account", "route_ticket")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("network access attempted in an offline test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def _gateway(environment, allowed=AGENT_TOOLS) -> ToolGateway:
    return ToolGateway(
        tools=[
            GatedTool(
                name,
                partial(SUPPORT_TOOLS[name], environment),
                SUPPORT_TOOL_SCHEMAS[name],
                SUPPORT_TOOL_DESCRIPTIONS[name],
            )
            for name in AGENT_TOOLS
        ],
        policy=AllowListPolicy(allowed),
        state_sha256=environment.state_sha256,
    )


def _run(environment, ticket_id, *, model=None, allowed=AGENT_TOOLS, run_id="run-0001", max_turns=10):
    gateway = _gateway(environment, allowed)
    agent = build_support_agent(
        environment=environment,
        tools=gateway_function_tools(gateway),
        model=model or ScriptedSupportModel(),
    )
    return run_agent(
        agent=agent, task_input=task_message(ticket_id), gateway=gateway,
        run_id=run_id, provenance=RunProvenance.SCRIPTED, max_turns=max_turns,
    )


def _calls(record) -> list[tuple[str, str]]:
    return [
        (r.tool_name, r.status.value) for r in record.stage_records
        if r.stage.value in ("authorized", "observed")
    ]


# Instructions


def test_instructions_list_queues_from_the_environment():
    instructions = support_instructions(SupportEnvironment())

    assert "- Q-PRIORITY (Priority support): Tickets from enterprise-tier accounts." in instructions
    assert "- Q-GENERAL (General support): Tickets from standard-tier accounts." in instructions
    assert "- Q-TRIAGE (Manual triage):" in instructions


# Scripted runs


@pytest.mark.parametrize(
    ("ticket_id", "queue_id"),
    [
        ("T-1001", "Q-PRIORITY"),
        ("T-1002", "Q-GENERAL"),
        ("T-1003", "Q-PRIORITY"),
        ("T-1004", "Q-GENERAL"),
        ("T-1005", "Q-PRIORITY"),
    ],
)
def test_clean_runs_route_by_account_tier(ticket_id, queue_id):
    environment = SupportEnvironment()

    record = _run(environment, ticket_id)

    assert record.status is RunStatus.COMPLETED
    assert record.provenance is RunProvenance.SCRIPTED
    assert record.final_message == f"Routed {ticket_id} to {queue_id}."
    assert _calls(record) == [
        ("read_ticket", "allowed"), ("read_ticket", "succeeded"),
        ("lookup_account", "allowed"), ("lookup_account", "succeeded"),
        ("route_ticket", "allowed"), ("route_ticket", "succeeded"),
    ]
    assert environment.get_ticket(ticket_id).queue_id == queue_id


def test_scripted_runs_are_deterministic():
    first = _run(SupportEnvironment(), "T-1003")
    second = _run(SupportEnvironment(), "T-1003")

    assert first.record_sha256 == second.record_sha256


def test_corrupted_mapping_leads_to_a_wrong_but_consistent_route():
    environment = SupportEnvironment()
    inject_fault(environment, IdentifierMappingSwap("C-3103", "C-3104"))

    record = _run(environment, "T-1003")

    assert record.status is RunStatus.COMPLETED
    assert record.final_message == "Routed T-1003 to Q-GENERAL."
    observations = [
        r.payload["observation"] for r in record.stage_records
        if r.stage.value == "observed"
    ]
    assert observations[0]["customer_ref"] == "C-3103"
    assert observations[1]["customer_ref"] == "C-3104"


def test_denied_route_stops_the_agent_without_state_change():
    environment = SupportEnvironment()
    start = environment.state_sha256()

    record = _run(environment, "T-1003", allowed=("read_ticket", "lookup_account"))

    assert record.final_message == (
        "I could not complete the request: route_ticket returned tool_not_allowed."
    )
    assert _calls(record)[-1] == ("route_ticket", "denied")
    assert environment.state_sha256() == start


def test_unknown_ticket_is_a_recorded_failure():
    record = _run(SupportEnvironment(), "T-9999")

    assert _calls(record) == [("read_ticket", "allowed"), ("read_ticket", "failed")]
    assert record.final_message == (
        "I could not complete the request: read_ticket returned ContractError."
    )


class MalformedArgumentsModel(ScriptedSupportModel):
    def decide(self, system_instructions, input_items):
        decision = super().decide(system_instructions, input_items)

        if isinstance(decision, ResponseFunctionToolCall) and decision.name == "read_ticket":
            return decision.model_copy(update={"arguments": '{"ticket_id": "T-1003"'})

        return decision


def test_malformed_tool_call_from_the_model_is_recorded():
    record = _run(SupportEnvironment(), "T-1003", model=MalformedArgumentsModel())

    proposed, authorized = record.stage_records[:2]
    assert proposed.payload == {"arguments": {"raw_arguments": '{"ticket_id": "T-1003"'}}
    assert authorized.status is StageStatus.DENIED
    assert authorized.payload["reason"] == "arguments_not_json"
    assert record.final_message.endswith("returned arguments_not_json.")


class LoopingModel(ScriptedSupportModel):
    def decide(self, system_instructions, input_items):
        return self._call(self.turns, "read_ticket", {"ticket_id": "T-1003"})


def test_max_turns_is_recorded_with_its_evidence():
    record = _run(SupportEnvironment(), "T-1003", model=LoopingModel(), max_turns=3)

    assert record.status is RunStatus.MAX_TURNS_EXCEEDED
    assert record.final_message is None
    assert [r.invocation_id for r in record.stage_records if r.stage.value == "observed"] == [
        "call-0001", "call-0002", "call-0003",
    ]


def test_scripted_model_cannot_be_recorded_as_live_or_replay():
    environment = SupportEnvironment()
    gateway = _gateway(environment)
    agent = build_support_agent(
        environment=environment, tools=gateway_function_tools(gateway),
        model=ScriptedSupportModel(),
    )

    for declared in (RunProvenance.LIVE, RunProvenance.REPLAY):
        with pytest.raises(ContractError, match="provenance"):
            run_agent(
                agent=agent, task_input=task_message("T-1003"), gateway=gateway,
                run_id="run-0001", provenance=declared,
            )


# Leakage on every surface produced so far


@pytest.mark.parametrize("example_name", sorted(EXAMPLES))
def test_run_surfaces_contain_no_evaluator_content(example_name):
    spec = EXAMPLES[example_name]
    environment = SupportEnvironment()

    if spec.fault_id is not None:
        inject_fault(environment, IdentifierMappingSwap(**fault(spec.fault_id).parameters))

    run_id = RunIdAllocator(start=7).allocate()
    record = _run(environment, spec.target_ticket_id, run_id=run_id)

    agent_inputs = {
        "instructions": support_instructions(environment),
        "task_input": record.task_input,
        "tool_definitions": list(record.tool_definitions),
    }
    assert_no_leaks(scan_content(agent_inputs))
    assert_no_leaks(scan_content({"run_record": record.evidence_payload()}))
    assert_no_leaks(scan_agent_outputs({"agent_output": record.agent_output_payload()}))
    assert_no_leaks(scan_identifiers("run_id", [record.run_id], NEUTRAL_RUN_ID))
    assert record.run_id == "run-0007"


def test_final_message_alone_would_trip_the_input_pair_check():
    record = _run(SupportEnvironment(), "T-1003")

    assert scan_content({"final_message": record.final_message}) != ()
    assert "final_message" not in json.dumps(record.evidence_payload())

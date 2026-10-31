"""The agent, Hetren and the leakage checks work unchanged in generated worlds."""

from functools import partial
import json
import socket

import pytest

from environments.support.fixtures import SupportEnvironment
from environments.support.generator import generate_world
from environments.support.tools import (
    SUPPORT_TOOL_DESCRIPTIONS,
    SUPPORT_TOOL_SCHEMAS,
    SUPPORT_TOOLS,
)
from packages.action_gateway import AllowListPolicy, GatedTool, ToolGateway
from packages.integrations.openai_agents import (
    RunProvenance,
    RunStatus,
    gateway_function_tools,
    run_agent,
)
from packages.support_agent import (
    ScriptedSupportModel,
    build_support_agent,
    support_instructions,
    task_message,
)
from packages.support_evaluator import assert_no_leaks, scan_content
from packages.support_recovery import DiagnosisOutcome, diagnose


FAULT_MARKERS = ("fault", "swap", "identifier_mapping", "inject")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("network access attempted in an offline test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def _run(environment, ticket_id):
    gateway = ToolGateway(
        tools=[
            GatedTool(
                name, partial(function, environment),
                SUPPORT_TOOL_SCHEMAS[name], SUPPORT_TOOL_DESCRIPTIONS[name],
            )
            for name, function in SUPPORT_TOOLS.items()
        ],
        policy=AllowListPolicy(SUPPORT_TOOLS),
        state_sha256=environment.state_sha256,
    )
    return run_agent(
        agent=build_support_agent(
            environment=environment, tools=gateway_function_tools(gateway),
            model=ScriptedSupportModel(),
        ),
        task_input=task_message(ticket_id), gateway=gateway,
        run_id="run-0001", provenance=RunProvenance.SCRIPTED,
    )


def _expected_queue(spec, ticket):
    account_id = dict(spec.directory)[ticket.customer_ref]
    tier = next(account.tier for account in spec.accounts if account.account_id == account_id)
    return next(queue.queue_id for queue in spec.queues if f"{tier}-tier" in queue.description)


@pytest.mark.parametrize("seed", range(6))
def test_scripted_agent_routes_every_ticket_correctly_in_generated_worlds(seed):
    spec = generate_world(seed, accounts=5, tickets=6)

    for ticket in spec.tickets:
        environment = SupportEnvironment(spec)
        record = _run(environment, ticket.ticket_id)

        assert record.status is RunStatus.COMPLETED
        assert record.sdk_evidence.discrepancies == ()
        assert environment.get_ticket(ticket.ticket_id).queue_id == _expected_queue(spec, ticket)
        assert diagnose(record.evidence_payload()).outcome is DiagnosisOutcome.HEALTHY


@pytest.mark.parametrize("seed", range(10))
def test_rendered_instructions_and_tool_outputs_carry_no_fault_markers(seed):
    spec = generate_world(seed)
    environment = SupportEnvironment(spec)
    record = _run(environment, spec.tickets[0].ticket_id)

    surfaces = json.dumps(
        {
            "instructions": support_instructions(environment),
            "stage_records": [r.canonical_payload() for r in record.stage_records],
        }
    ).lower()

    for marker in FAULT_MARKERS:
        assert marker not in surfaces, marker

    assert_no_leaks(scan_content({"instructions": support_instructions(environment)}))

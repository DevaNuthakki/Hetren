"""Run planned cases with scripted agents and build compact inputs per step.

Used to measure input size and to check leakage on the exact text a model
will see. A step is the compact input after 0, 1, ... probes; the probe
sequence here is a fixed, generic one (ticket, directory, owners, source),
not an oracle policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial

from environments.support.fixtures import SupportEnvironment
from environments.support.generator import generate_world
from environments.support.maintenance import MAINTENANCE_VERB_TOOLS
from environments.support.tools import (
    SUPPORT_TOOL_DESCRIPTIONS,
    SUPPORT_TOOL_SCHEMAS,
    SUPPORT_TOOLS,
)
import random

from packages.action_gateway import AllowListPolicy, GatedTool, ToolGateway
from packages.action_space import PROBE_BUDGET, VERBS, probe_gateway
from packages.hetren_evidence import compact_evidence
from packages.integrations.openai_agents import (
    RunProvenance,
    RunRecord,
    gateway_function_tools,
    run_agent,
)
from packages.support_agent import ScriptedSupportModel, build_support_agent, task_message
from packages.support_evaluator.injectors import InjectedCase, inject
from packages.support_evaluator.plan import PlannedCase


@dataclass(frozen=True)
class SampledCase:
    planned: PlannedCase
    case: InjectedCase
    record: RunRecord
    steps: tuple[dict[str, object], ...]


def run_agent_on(
    environment: SupportEnvironment,
    ticket_id: str,
    behaviour: str,
    run_id: str = "run-0001",
) -> RunRecord:
    """Run the scripted agent with one behaviour on an existing environment."""
    gateway = ToolGateway(
        tools=[
            GatedTool(name, partial(f, environment), SUPPORT_TOOL_SCHEMAS[name], SUPPORT_TOOL_DESCRIPTIONS[name])
            for name, f in SUPPORT_TOOLS.items()
        ],
        policy=AllowListPolicy(SUPPORT_TOOLS),
        state_sha256=environment.state_sha256,
    )
    return run_agent(
        agent=build_support_agent(
            environment=environment, tools=gateway_function_tools(gateway),
            model=ScriptedSupportModel(behaviour),
        ),
        task_input=task_message(ticket_id), gateway=gateway,
        run_id=run_id, provenance=RunProvenance.SCRIPTED,
    )


def run_planned_case(planned: PlannedCase) -> tuple[InjectedCase, SupportEnvironment, RunRecord]:
    case = inject(
        planned.case_kind, generate_world(planned.world_seed),
        random.Random(planned.case_seed), planned.case_variant,
    )
    environment = SupportEnvironment(case.spec)
    record = run_agent_on(environment, case.truth.target_ticket_id, planned.behaviour)
    return case, environment, record


def _generic_probes(environment: SupportEnvironment, ticket_id: str) -> list[tuple[str, dict[str, object]]]:
    ticket = environment.get_ticket(ticket_id)
    account_id = environment.directory_entry(ticket.customer_ref)
    probes: list[tuple[str, dict[str, object]]] = [
        ("inspect", {"entity": "ticket", "id": ticket_id}),
        ("resolve", {"customer_ref": ticket.customer_ref}),
        ("find_owners", {"customer_ref": ticket.customer_ref}),
    ]

    if account_id is not None and account_id in environment.account_ids():
        probes.append(("compare_with_source", {"entity": "account", "id": account_id}))
    else:
        probes.append(("inspect", {"entity": "routing_policy"}))

    return probes[:PROBE_BUDGET]


def sample_case(planned: PlannedCase) -> SampledCase:
    case, environment, record = run_planned_case(planned)
    gateway = probe_gateway(
        [
            GatedTool(verb, partial(f, environment), VERBS[verb].args_schema, VERBS[verb].description)
            for verb, f in MAINTENANCE_VERB_TOOLS.items()
        ],
        environment.state_sha256,
    )
    evidence = record.evidence_payload()
    steps = [compact_evidence(evidence)]

    for verb, args in _generic_probes(environment, case.truth.target_ticket_id):
        gateway.invoke(verb, args)
        steps.append(
            compact_evidence(evidence, [r.canonical_payload() for r in gateway.records])
        )

    return SampledCase(planned, case, record, tuple(steps))


__all__ = [
    "SampledCase",
    "run_agent_on",
    "run_planned_case",
    "sample_case",
]

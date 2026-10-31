"""Run an SDK agent against a fresh ``ToolGateway`` and return a RunRecord.

Preconditions checked before the run:

- the declared provenance matches the agent's model object;
- the gateway has recorded nothing yet (one gateway per run);
- the agent's tools are exactly the gateway's tools, so every tool call is
  staged by the gateway.

SDK tracing is disabled here. The local trace processor that maps SDK spans
into Hetren evidence without exporting anything is added separately.
"""

from __future__ import annotations

from agents import Agent, RunConfig, Runner
from agents.exceptions import MaxTurnsExceeded

from packages.action_gateway import ToolGateway
from packages.contracts import (
    ContractError,
    canonical_sha256,
)
from packages.integrations.openai_agents.provenance import (
    RunProvenance,
    RunRecord,
    RunStatus,
    model_identity,
    model_provenance,
)


DEFAULT_LIMITATIONS = (
    "the run record does not establish that the agent's decisions are correct",
    "tool observations describe the environment as the gateway saw it",
)


def run_agent(
    *,
    agent: Agent,
    task_input: str,
    gateway: ToolGateway,
    run_id: str,
    provenance: RunProvenance,
    max_turns: int = 10,
    limitations: tuple[str, ...] = DEFAULT_LIMITATIONS,
) -> RunRecord:
    if not isinstance(provenance, RunProvenance):
        raise ContractError("provenance must be a RunProvenance")

    if model_provenance(agent.model) is not provenance:
        raise ContractError("declared provenance does not match the agent's model")

    if gateway.records:
        raise ContractError("gateway must be fresh for each run")

    agent_tools = sorted(tool.name for tool in agent.tools)

    if agent_tools != list(gateway.tool_names()):
        raise ContractError("agent tools must be exactly the gateway's tools")

    if not isinstance(agent.instructions, str):
        raise ContractError("agent instructions must be static text")

    status = RunStatus.COMPLETED
    error: dict[str, str] | None = None
    final_message: str | None = None

    try:
        result = Runner.run_sync(
            agent,
            task_input,
            max_turns=max_turns,
            run_config=RunConfig(tracing_disabled=True),
        )
    except MaxTurnsExceeded:
        status = RunStatus.MAX_TURNS_EXCEEDED
    except Exception as exc:
        status = RunStatus.ERROR
        error = {"type": type(exc).__name__, "message": str(exc)}
    else:
        if result.final_output is not None:
            final_message = str(result.final_output)

    return RunRecord(
        run_id=run_id,
        provenance=provenance,
        model_id=model_identity(agent.model),
        agent_name=agent.name,
        instructions_sha256=canonical_sha256({"instructions": agent.instructions}),
        task_input=task_input,
        tool_definitions=gateway.tool_definitions(),
        stage_records=gateway.records,
        status=status,
        error=error,
        final_message=final_message,
        limitations=limitations,
    )


__all__ = [
    "DEFAULT_LIMITATIONS",
    "run_agent",
]

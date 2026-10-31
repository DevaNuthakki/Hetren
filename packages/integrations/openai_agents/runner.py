"""Run an SDK agent against a fresh ``ToolGateway`` and return a RunRecord.

Preconditions checked before the run:

- the declared provenance matches the agent's model object;
- the gateway has recorded nothing yet (one gateway per run);
- the agent's tools are exactly the gateway's tools, so every tool call is
  staged by the gateway;
- a LIVE run sets ``model_settings.store=False``, so the provider does not
  retain responses.

A replay miss, capture version mismatch, or capture conflict is an
infrastructure failure, not agent behaviour, so ``ReplayMissError``,
``ReplayVersionError`` and ``CaptureConflictError`` propagate instead of
being recorded as a run error.

Tracing goes only to the local processor (``install_local_tracing``) with
``trace_include_sensitive_data=False``; see ``tracing.py`` for why. Hook
events and spans are reconciled against the gateway's stage records and
any disagreement is stored in the record.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from agents import Agent, RunConfig, Runner, gen_trace_id
from agents.exceptions import MaxTurnsExceeded

from packages.action_gateway import ToolGateway
from packages.contracts import (
    ContractError,
    canonical_sha256,
)
from packages.integrations.openai_agents.evidence import (
    SENSITIVE_DATA_CAPTURE,
    SdkEvidence,
    reconcile,
)
from packages.integrations.openai_agents.hooks import (
    EvidenceHooks,
    text_sha256,
)
from packages.integrations.openai_agents.provenance import (
    RunProvenance,
    RunRecord,
    RunStatus,
    model_identity,
    model_provenance,
)
from packages.integrations.openai_agents.replay import (
    CaptureConflictError,
    ReplayMissError,
    ReplayVersionError,
)
from packages.integrations.openai_agents.tracing import install_local_tracing


DEFAULT_LIMITATIONS = (
    "the run record does not establish that the agent's decisions are correct",
    "tool observations describe the environment as the gateway saw it",
)

WORKFLOW_NAME = "hetren-agent-run"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_agent(
    *,
    agent: Agent,
    task_input: str,
    gateway: ToolGateway,
    run_id: str,
    provenance: RunProvenance,
    max_turns: int = 10,
    limitations: tuple[str, ...] = DEFAULT_LIMITATIONS,
    clock: Callable[[], str] | None = _utc_now,
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

    model_settings = {
        key: value
        for key, value in agent.model_settings.to_json_dict().items()
        if value is not None
    }

    if provenance is RunProvenance.LIVE and model_settings.get("store") is not False:
        raise ContractError("live runs require model_settings.store=False")

    processor = install_local_tracing()
    trace_id = gen_trace_id()
    hooks = EvidenceHooks(clock=clock)
    initial_state = gateway.current_state_sha256()

    status = RunStatus.COMPLETED
    error: dict[str, str] | None = None
    final_message: str | None = None

    processor.begin(trace_id)

    try:
        result = Runner.run_sync(
            agent,
            task_input,
            max_turns=max_turns,
            hooks=hooks,
            run_config=RunConfig(
                trace_id=trace_id,
                workflow_name=WORKFLOW_NAME,
                trace_include_sensitive_data=SENSITIVE_DATA_CAPTURE,
            ),
        )
    except MaxTurnsExceeded:
        status = RunStatus.MAX_TURNS_EXCEEDED
    except (ReplayMissError, ReplayVersionError, CaptureConflictError):
        raise
    except Exception as exc:
        status = RunStatus.ERROR
        error = {"type": type(exc).__name__, "message_sha256": text_sha256(str(exc))}
    else:
        if result.final_output is not None:
            final_message = str(result.final_output)
    finally:
        spans = processor.finish(trace_id).records()

    stage_records = gateway.records

    return RunRecord(
        run_id=run_id,
        provenance=provenance,
        source_provenance=getattr(agent.model, "hetren_source_provenance", None),
        model_id=model_identity(agent.model),
        model_settings=model_settings,
        agent_name=agent.name,
        instructions_sha256=canonical_sha256({"instructions": agent.instructions}),
        task_input=task_input,
        tool_definitions=gateway.tool_definitions(),
        initial_state_sha256=initial_state,
        final_state_sha256=gateway.current_state_sha256(),
        stage_records=stage_records,
        sdk_evidence=SdkEvidence(
            hook_events=hooks.events,
            spans=spans,
            discrepancies=reconcile(stage_records, hooks.events, spans),
        ),
        replay_capture_ids=tuple(getattr(agent.model, "used_capture_ids", ())),
        recorded_capture_ids=tuple(getattr(agent.model, "recorded_capture_ids", ())),
        status=status,
        error=error,
        final_message=final_message,
        limitations=limitations,
    )


__all__ = [
    "DEFAULT_LIMITATIONS",
    "WORKFLOW_NAME",
    "run_agent",
]

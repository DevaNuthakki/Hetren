"""Permission scopes for executing actions.

The harness supplies plain world tools (``GatedTool``), named after the verbs
they implement, plus an opaque ``state_sha256``. These helpers build the
gateways with fixed policies:

- probes: ``AllowListPolicy`` over the probe verbs only;
- a recovery: ``AllOfPolicy(AllowListPolicy({verb}), ExactCallsPolicy(call))``,
  so a recovery gateway can make exactly the one proposed call.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from packages.action_gateway import (
    AllOfPolicy,
    AllowListPolicy,
    ExactCallsPolicy,
    GatedTool,
    ToolGateway,
)
from packages.contracts import ContractError
from packages.action_space.actions import Action
from packages.action_space.catalog import PROBE_VERBS, WORLD_RECOVERY_VERBS


def _select(tools: Sequence[GatedTool], names: Sequence[str]) -> list[GatedTool]:
    selected = [tool for tool in tools if tool.name in names]

    if sorted(tool.name for tool in selected) != sorted(names):
        raise ContractError(f"tools must include exactly {sorted(names)}")

    return selected


def probe_gateway(
    tools: Sequence[GatedTool],
    state_sha256: Callable[[], str],
) -> ToolGateway:
    return ToolGateway(
        tools=_select(tools, PROBE_VERBS),
        policy=AllowListPolicy(PROBE_VERBS),
        state_sha256=state_sha256,
    )


def recovery_gateway(
    tools: Sequence[GatedTool],
    state_sha256: Callable[[], str],
    action: Action,
) -> ToolGateway:
    if action.kind != "recover" or action.verb not in WORLD_RECOVERY_VERBS:
        raise ContractError("a recovery gateway needs a world recovery action")

    return ToolGateway(
        tools=_select(tools, (action.verb,)),
        policy=AllOfPolicy(
            AllowListPolicy({action.verb}),
            ExactCallsPolicy([(action.verb, action.args)]),
        ),
        state_sha256=state_sha256,
    )


__all__ = [
    "probe_gateway",
    "recovery_gateway",
]

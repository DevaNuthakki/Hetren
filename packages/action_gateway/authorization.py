"""Authorization policies for gated tool invocations.

A policy sees only the proposal: invocation id, tool name and arguments. It
returns an allow/deny decision with a short reason code. The gateway fails
closed: a policy that raises, or returns anything but an
``AuthorizationDecision``, is recorded as a denial.

A decision records what the policy reported. It is not deployment approval
and does not establish that the proposed action is correct.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import re
from typing import Protocol

from packages.contracts import ContractError


_REASON = re.compile(r"[a-z][a-z0-9_]{0,63}")


@dataclass(frozen=True)
class ToolProposal:
    invocation_id: str
    tool_name: str
    arguments: dict[str, object]


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    reason: str
    policy_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.allowed, bool):
            raise ContractError("allowed must be a bool")

        for name in ("reason", "policy_id"):
            value = getattr(self, name)

            if (
                not isinstance(value, str)
                or _REASON.fullmatch(value) is None
            ):
                raise ContractError(
                    f"{name} must be a lowercase reason code"
                )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "policy_id": self.policy_id,
        }


class AuthorizationPolicy(Protocol):
    def authorize(
        self,
        proposal: ToolProposal,
    ) -> AuthorizationDecision: ...


class AllowAllPolicy:
    policy_id = "allow_all"

    def authorize(
        self,
        proposal: ToolProposal,
    ) -> AuthorizationDecision:
        return AuthorizationDecision(True, "allowed", self.policy_id)


class AllowListPolicy:
    """Allow only the named tools; deny everything else."""

    policy_id = "allow_list"

    def __init__(self, allowed_tools: Iterable[str]) -> None:
        self._allowed_tools = frozenset(allowed_tools)

    @property
    def allowed_tools(self) -> frozenset[str]:
        return self._allowed_tools

    def authorize(
        self,
        proposal: ToolProposal,
    ) -> AuthorizationDecision:
        if proposal.tool_name in self._allowed_tools:
            return AuthorizationDecision(True, "tool_allowed", self.policy_id)

        return AuthorizationDecision(False, "tool_not_allowed", self.policy_id)


__all__ = [
    "AllowAllPolicy",
    "AllowListPolicy",
    "AuthorizationDecision",
    "AuthorizationPolicy",
    "ToolProposal",
]

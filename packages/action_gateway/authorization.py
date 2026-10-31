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

from packages.contracts import ContractError, canonical_sha256


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


class ExactCallsPolicy:
    """Allow only exact (tool name, arguments) pairs; deny everything else.

    Used to bind a write tool to a frozen plan: even an allowed tool can only
    make the calls the plan names.
    """

    policy_id = "exact_calls"

    def __init__(self, calls: Iterable[tuple[str, dict[str, object]]]) -> None:
        self._calls = frozenset(
            (tool_name, canonical_sha256(arguments)) for tool_name, arguments in calls
        )

    def authorize(
        self,
        proposal: ToolProposal,
    ) -> AuthorizationDecision:
        if (proposal.tool_name, canonical_sha256(proposal.arguments)) in self._calls:
            return AuthorizationDecision(True, "call_in_scope", self.policy_id)

        return AuthorizationDecision(False, "call_outside_scope", self.policy_id)


class AllOfPolicy:
    """Allow only when every policy allows; the first denial is reported."""

    policy_id = "all_of"

    def __init__(self, *policies: AuthorizationPolicy) -> None:
        if not policies:
            raise ContractError("AllOfPolicy needs at least one policy")

        self._policies = policies

    def authorize(
        self,
        proposal: ToolProposal,
    ) -> AuthorizationDecision:
        decision = AuthorizationDecision(True, "all_allowed", self.policy_id)

        for policy in self._policies:
            decision = policy.authorize(proposal)

            if not isinstance(decision, AuthorizationDecision) or not decision.allowed:
                return decision

        return AuthorizationDecision(True, "all_allowed", self.policy_id)


__all__ = [
    "AllOfPolicy",
    "AllowAllPolicy",
    "AllowListPolicy",
    "ExactCallsPolicy",
    "AuthorizationDecision",
    "AuthorizationPolicy",
    "ToolProposal",
]

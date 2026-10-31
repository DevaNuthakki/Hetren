"""Generic gated tool execution with staged evidence.

``ToolGateway`` wraps plain tool functions and their JSON schemas. It knows
nothing about any particular environment: the caller supplies the tools, an
authorization policy, and a ``state_sha256`` callable for the state the tools
act on.

Gate order for one invocation:

1. PROPOSED is always recorded.
2. The gateway denies unknown tools and schema-invalid arguments itself;
   otherwise the policy decides. AUTHORIZED records the decision.
3. Only an allowed call records ATTEMPTED and then OBSERVED.

A tool exception, or an observation that is not a JSON object, becomes a
FAILED observation rather than an exception, and the after-state hash shows
whether anything changed.

``invoke_raw`` accepts the model's argument text unparsed. Text that is not a
JSON object is recorded as PROPOSED (with the raw text) and AUTHORIZED denied
with reason ``arguments_not_json``, so malformed calls remain evidence.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
import json

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from packages.contracts import (
    ContractError,
    canonical_sha256,
)
from packages.action_gateway.authorization import (
    AuthorizationDecision,
    AuthorizationPolicy,
    ToolProposal,
)
from packages.action_gateway.stages import (
    StageStatus,
    ToolStage,
    ToolStageRecord,
    json_object,
)


_GATEWAY_POLICY_ID = "gateway"


@dataclass(frozen=True)
class GatedTool:
    name: str
    function: Callable[..., object]
    schema: dict[str, object]
    description: str

    def __post_init__(self) -> None:
        if not callable(self.function):
            raise ContractError("tool function must be callable")

        if not isinstance(self.description, str) or not self.description.strip():
            raise ContractError("tool description must be non-empty text")

        schema = json_object(self.schema, "tool schema")

        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as exc:
            raise ContractError("tool schema is not a valid JSON schema") from exc

        object.__setattr__(self, "schema", schema)

    def definition(self) -> dict[str, object]:
        """Model-facing definition: name, description and schema only."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.schema,
        }


@dataclass(frozen=True)
class ToolInvocationResult:
    invocation_id: str
    tool_name: str
    status: StageStatus
    observation: dict[str, object] | None
    error: dict[str, object] | None
    records: tuple[ToolStageRecord, ...]


class ToolGateway:
    def __init__(
        self,
        *,
        tools: Iterable[GatedTool],
        policy: AuthorizationPolicy,
        state_sha256: Callable[[], str],
        clock: Callable[[], str] | None = None,
    ) -> None:
        self._tools: dict[str, GatedTool] = {}

        for tool in tools:
            if not isinstance(tool, GatedTool):
                raise ContractError("tools must be GatedTool instances")

            if tool.name in self._tools:
                raise ContractError("tool names must be unique")

            self._tools[tool.name] = tool

        if not callable(state_sha256):
            raise ContractError("state_sha256 must be callable")

        self._policy = policy
        self._state_sha256 = state_sha256
        self._clock = clock
        self._records: list[ToolStageRecord] = []
        self._invocations = 0

    @property
    def records(self) -> tuple[ToolStageRecord, ...]:
        return tuple(self._records)

    def tool_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))

    def tool_definitions(self) -> tuple[dict[str, object], ...]:
        return tuple(
            self._tools[name].definition()
            for name in sorted(self._tools)
        )

    def _record(
        self,
        *,
        invocation_id: str,
        tool_name: str,
        stage: ToolStage,
        status: StageStatus,
        arguments_sha256: str,
        payload: dict[str, object],
        state_before_sha256: str,
        state_after_sha256: str | None = None,
    ) -> ToolStageRecord:
        record = ToolStageRecord(
            sequence=len(self._records),
            invocation_id=invocation_id,
            tool_name=tool_name,
            stage=stage,
            status=status,
            arguments_sha256=arguments_sha256,
            payload=payload,
            state_before_sha256=state_before_sha256,
            state_after_sha256=(
                state_before_sha256
                if state_after_sha256 is None
                else state_after_sha256
            ),
            recorded_at=None if self._clock is None else self._clock(),
        )
        self._records.append(record)
        return record

    def _decide(
        self,
        proposal: ToolProposal,
    ) -> AuthorizationDecision:
        tool = self._tools.get(proposal.tool_name)

        if tool is None:
            return AuthorizationDecision(False, "unknown_tool", _GATEWAY_POLICY_ID)

        if not Draft202012Validator(tool.schema).is_valid(proposal.arguments):
            return AuthorizationDecision(
                False, "arguments_schema_invalid", _GATEWAY_POLICY_ID,
            )

        try:
            decision = self._policy.authorize(proposal)
        except Exception:
            return AuthorizationDecision(False, "policy_error", _GATEWAY_POLICY_ID)

        if not isinstance(decision, AuthorizationDecision):
            return AuthorizationDecision(
                False, "policy_invalid_decision", _GATEWAY_POLICY_ID,
            )

        return decision

    def invoke_raw(
        self,
        tool_name: str,
        raw_arguments: str,
    ) -> ToolInvocationResult:
        """Invoke from unparsed argument text, recording malformed input."""
        if not isinstance(raw_arguments, str):
            raise ContractError("raw_arguments must be text")

        try:
            parsed = json.loads(raw_arguments) if raw_arguments.strip() else {}
        except json.JSONDecodeError:
            parsed = None

        if isinstance(parsed, dict):
            try:
                return self.invoke(tool_name, parsed)
            except ContractError:
                pass

        return self._invoke(
            tool_name,
            {"raw_arguments": raw_arguments},
            forced_denial="arguments_not_json",
        )

    def invoke(
        self,
        tool_name: str,
        arguments: dict[str, object],
    ) -> ToolInvocationResult:
        return self._invoke(tool_name, arguments)

    def _invoke(
        self,
        tool_name: str,
        arguments: dict[str, object],
        *,
        forced_denial: str | None = None,
    ) -> ToolInvocationResult:
        arguments = json_object(arguments, "arguments")
        arguments_sha256 = canonical_sha256(arguments)
        self._invocations += 1
        invocation_id = f"call-{self._invocations:04d}"
        first_sequence = len(self._records)

        common = {
            "invocation_id": invocation_id,
            "tool_name": tool_name,
            "arguments_sha256": arguments_sha256,
        }

        self._record(
            **common,
            stage=ToolStage.PROPOSED,
            status=StageStatus.PROPOSED,
            payload={"arguments": arguments},
            state_before_sha256=self._state_sha256(),
        )

        decision = (
            AuthorizationDecision(False, forced_denial, _GATEWAY_POLICY_ID)
            if forced_denial is not None
            else self._decide(ToolProposal(invocation_id, tool_name, arguments))
        )

        self._record(
            **common,
            stage=ToolStage.AUTHORIZED,
            status=(
                StageStatus.ALLOWED if decision.allowed else StageStatus.DENIED
            ),
            payload=decision.canonical_payload(),
            state_before_sha256=self._state_sha256(),
        )

        if not decision.allowed:
            return ToolInvocationResult(
                invocation_id=invocation_id,
                tool_name=tool_name,
                status=StageStatus.DENIED,
                observation=None,
                error=None,
                records=tuple(self._records[first_sequence:]),
            )

        state_before = self._state_sha256()

        self._record(
            **common,
            stage=ToolStage.ATTEMPTED,
            status=StageStatus.STARTED,
            payload={},
            state_before_sha256=state_before,
        )

        observation: dict[str, object] | None = None
        error: dict[str, object] | None = None

        try:
            raw = self._tools[tool_name].function(**arguments)
        except Exception as exc:
            error = {"type": type(exc).__name__, "message": str(exc)}
        else:
            try:
                observation = json_object(raw, "observation")
            except ContractError:
                error = {
                    "type": "InvalidObservation",
                    "message": "tool returned a non-JSON-object observation",
                }

        succeeded = error is None

        self._record(
            **common,
            stage=ToolStage.OBSERVED,
            status=StageStatus.SUCCEEDED if succeeded else StageStatus.FAILED,
            payload=(
                {"observation": observation} if succeeded else {"error": error}
            ),
            state_before_sha256=state_before,
            state_after_sha256=self._state_sha256(),
        )

        return ToolInvocationResult(
            invocation_id=invocation_id,
            tool_name=tool_name,
            status=StageStatus.SUCCEEDED if succeeded else StageStatus.FAILED,
            observation=observation,
            error=error,
            records=tuple(self._records[first_sequence:]),
        )


__all__ = [
    "GatedTool",
    "ToolGateway",
    "ToolInvocationResult",
]

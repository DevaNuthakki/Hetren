"""SDK lifecycle hooks recorded as structured evidence.

``EvidenceHooks`` records agent, model-call, and tool lifecycle events in
order. Fields are codes, names, counts, and hashes only: no free-text
summaries and no tool arguments, observations, or model text. Those live in
gateway stage records (actions and state) and the run record (task input and
final message), which remain the authority.

Hook events give Hetren what gateway records cannot: the model calls between
tool calls, and the tool calls the model emitted, including ones the SDK
rejected before any tool, and therefore the gateway, saw them.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
import json
from typing import Any

from agents import RunHooks

from packages.action_gateway import raw_arguments_object
from packages.contracts import canonical_sha256


class HookKind(StrEnum):
    AGENT_START = "agent_start"
    LLM_START = "llm_start"
    LLM_END = "llm_end"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    AGENT_END = "agent_end"


@dataclass(frozen=True)
class HookEvent:
    sequence: int
    kind: HookKind
    fields: dict[str, object]
    recorded_at: str | None = None

    def canonical_payload(self) -> dict[str, object]:
        """Hashable content; ``recorded_at`` is deliberately excluded."""
        return {
            "sequence": self.sequence,
            "kind": self.kind.value,
            "fields": self.fields,
        }


def _plain(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)

    return str(value)


def items_sha256(items: Any) -> str:
    return canonical_sha256(
        json.loads(json.dumps(items, default=_plain, sort_keys=True))
    )


def arguments_sha256(raw_arguments: str) -> str:
    """Same digest the gateway records for this raw argument text."""
    arguments, _ = raw_arguments_object(raw_arguments)
    return canonical_sha256(arguments)


def text_sha256(text: str) -> str:
    return canonical_sha256({"text": text})


class EvidenceHooks(RunHooks):
    def __init__(self, clock: Callable[[], str] | None = None) -> None:
        self._clock = clock
        self._events: list[HookEvent] = []
        self._turns = 0

    @property
    def events(self) -> tuple[HookEvent, ...]:
        return tuple(self._events)

    def _record(self, kind: HookKind, fields: dict[str, object]) -> None:
        self._events.append(
            HookEvent(
                sequence=len(self._events),
                kind=kind,
                fields=fields,
                recorded_at=None if self._clock is None else self._clock(),
            )
        )

    async def on_agent_start(self, context: Any, agent: Any) -> None:
        self._record(HookKind.AGENT_START, {"agent_name": agent.name})

    async def on_llm_start(
        self, context: Any, agent: Any, system_prompt: Any, input_items: Any,
    ) -> None:
        self._turns += 1
        self._record(
            HookKind.LLM_START,
            {
                "turn": self._turns,
                "system_prompt_sha256": (
                    None if system_prompt is None else text_sha256(str(system_prompt))
                ),
                "input_item_count": len(input_items),
                "input_sha256": items_sha256(input_items),
            },
        )

    async def on_llm_end(self, context: Any, agent: Any, response: Any) -> None:
        tool_calls = []
        output_types = []

        for item in response.output:
            item_type = getattr(item, "type", type(item).__name__)
            output_types.append(item_type)

            if item_type == "function_call":
                tool_calls.append(
                    {
                        "tool_call_id": item.call_id,
                        "tool_name": item.name,
                        "arguments_sha256": arguments_sha256(item.arguments),
                    }
                )

        self._record(
            HookKind.LLM_END,
            {
                "turn": self._turns,
                "output_types": output_types,
                "tool_calls": tool_calls,
                "output_sha256": items_sha256(response.output),
            },
        )

    async def on_tool_start(self, context: Any, agent: Any, tool: Any) -> None:
        self._record(
            HookKind.TOOL_START,
            {
                "tool_call_id": getattr(context, "tool_call_id", None),
                "tool_name": tool.name,
                "arguments_sha256": arguments_sha256(
                    getattr(context, "tool_arguments", "") or ""
                ),
            },
        )

    async def on_tool_end(self, context: Any, agent: Any, tool: Any, result: Any) -> None:
        self._record(
            HookKind.TOOL_END,
            {
                "tool_call_id": getattr(context, "tool_call_id", None),
                "tool_name": tool.name,
                "result_sha256": text_sha256(str(result)),
            },
        )

    async def on_agent_end(self, context: Any, agent: Any, output: Any) -> None:
        self._record(
            HookKind.AGENT_END,
            {
                "final_output_present": output is not None,
                "final_output_sha256": None if output is None else text_sha256(str(output)),
            },
        )


__all__ = [
    "EvidenceHooks",
    "HookEvent",
    "HookKind",
    "arguments_sha256",
    "items_sha256",
    "text_sha256",
]

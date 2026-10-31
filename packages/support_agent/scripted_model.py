"""Deterministic scripted model for offline support-agent runs.

``ScriptedSupportModel`` implements the SDK ``Model`` interface without any
network access. Each turn it reads the transcript the SDK passes in and
decides the next step the way the instructions describe:

read_ticket -> lookup_account -> route_ticket -> one-sentence reply.

It chooses the queue by matching the looked-up account tier against the
queue guide in the system instructions, and it trusts every observation as
given. It has no access to faults or expected outcomes, so a corrupted
identifier mapping leads it to a wrong but internally consistent route.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
import json
import re
from typing import Any

from agents import Model, ModelResponse, Usage
from openai.types.responses import (
    ResponseFunctionToolCall,
    ResponseOutputMessage,
    ResponseOutputText,
)

from packages.integrations.openai_agents.provenance import RunProvenance


_TICKET_ID = re.compile(r"\bT-[0-9]{4}\b")
_QUEUE_LINE = re.compile(r"^- (Q-[A-Z]{3,12}) \(([^)]*)\): (.+)$", re.MULTILINE)


def _field(item: Any, name: str) -> Any:
    if isinstance(item, dict):
        return item.get(name)

    return getattr(item, name, None)


def _user_text(input_items: str | list[Any]) -> str:
    if isinstance(input_items, str):
        return input_items

    parts = []

    for item in input_items:
        if _field(item, "role") == "user":
            content = _field(item, "content")

            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                parts.extend(
                    str(_field(part, "text")) for part in content
                    if _field(part, "text") is not None
                )

    return "\n".join(parts)


def _tool_results(input_items: str | list[Any]) -> list[tuple[str, dict[str, Any]]]:
    """(tool name, parsed result) pairs in transcript order."""
    if isinstance(input_items, str):
        return []

    names: dict[str, str] = {}
    results: list[tuple[str, dict[str, Any]]] = []

    for item in input_items:
        kind = _field(item, "type")

        if kind == "function_call":
            names[str(_field(item, "call_id"))] = str(_field(item, "name"))
        elif kind == "function_call_output":
            call_id = str(_field(item, "call_id"))
            output = _field(item, "output")

            try:
                parsed = json.loads(output) if isinstance(output, str) else {}
            except json.JSONDecodeError:
                parsed = {"error": {"type": "UnparseableToolOutput"}}

            results.append((names.get(call_id, "unknown"), parsed))

    return results


class ScriptedSupportModel(Model):
    hetren_provenance = RunProvenance.SCRIPTED
    hetren_model_id = "scripted-support-model-v1"

    def __init__(self) -> None:
        self.turns = 0

    def _call(self, call_number: int, name: str, arguments: dict[str, str]) -> ResponseFunctionToolCall:
        return ResponseFunctionToolCall(
            type="function_call",
            id=f"fc_scripted_{call_number}",
            call_id=f"call_scripted_{call_number}",
            name=name,
            arguments=json.dumps(arguments, sort_keys=True),
            status="completed",
        )

    def _reply(self, text: str) -> ResponseOutputMessage:
        return ResponseOutputMessage(
            type="message",
            id=f"msg_scripted_{self.turns}",
            role="assistant",
            status="completed",
            content=[ResponseOutputText(type="output_text", text=text, annotations=[])],
        )

    def decide(
        self,
        system_instructions: str | None,
        input_items: str | list[Any],
    ) -> ResponseFunctionToolCall | ResponseOutputMessage:
        results = _tool_results(input_items)
        call_number = len(results) + 1
        done = {name: result for name, result in results}

        for name, result in results:
            if "error" in result or "denied" in result:
                reason = result.get("denied") or result.get("error", {}).get("type")
                return self._reply(f"I could not complete the request: {name} returned {reason}.")

        match = _TICKET_ID.search(_user_text(input_items))

        if match is None:
            return self._reply("I could not find a ticket ID in the request.")

        ticket_id = match.group(0)

        if "read_ticket" not in done:
            return self._call(call_number, "read_ticket", {"ticket_id": ticket_id})

        ticket = done["read_ticket"]["observation"]

        if "lookup_account" not in done:
            return self._call(call_number, "lookup_account", {"account_id": ticket["account_id"]})

        tier = str(done["lookup_account"]["observation"]["tier"]).casefold()

        if "route_ticket" not in done:
            for queue_id, _name, description in _QUEUE_LINE.findall(system_instructions or ""):
                if f"{tier}-tier" in description.casefold():
                    return self._call(
                        call_number, "route_ticket", {"ticket_id": ticket_id, "queue_id": queue_id},
                    )

            return self._reply(f"No queue matches the {tier} tier for {ticket_id}.")

        routed = done["route_ticket"]["observation"]
        return self._reply(f"Routed {routed['ticket_id']} to {routed['queue_id']}.")

    async def get_response(
        self,
        system_instructions: str | None,
        input: str | list[Any],
        model_settings: Any,
        tools: list[Any],
        output_schema: Any,
        handoffs: list[Any],
        tracing: Any,
        *,
        previous_response_id: str | None,
        conversation_id: str | None,
        prompt: Any,
    ) -> ModelResponse:
        self.turns += 1
        return ModelResponse(
            output=[self.decide(system_instructions, input)],
            usage=Usage(),
            response_id=None,
        )

    def stream_response(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        raise NotImplementedError("ScriptedSupportModel does not stream")


__all__ = [
    "ScriptedSupportModel",
]

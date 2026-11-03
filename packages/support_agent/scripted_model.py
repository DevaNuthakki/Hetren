"""Deterministic scripted model for offline support-agent runs.

``ScriptedSupportModel`` implements the SDK ``Model`` interface without any
network access. Each turn it reads the transcript the SDK passes in and
decides the next step the way the instructions describe:

read_ticket -> lookup_account -> route_ticket -> one-sentence reply.

It chooses the queue by matching the looked-up account tier against the
queue guide in the system instructions. It has no access to faults or
expected outcomes.

Behaviours (independent of any fault; the dataset crosses every behaviour
with every case kind):

- ``trust`` (default): trusts every observation, ignores ticket text, and
  stops at the first failed or denied call. This is the Milestone 1 model,
  unchanged, including its model ID.
- ``retry``: like ``trust``, but repeats a failed call once before stopping.
- ``give_up``: like ``trust``, but also stops when the account does not name
  the ticket's customer, or when no queue matches the account tier.
- ``follow_text``: like ``trust``, but routes by a tier the ticket body
  claims, if it claims one.
- ``case_sensitive``: like ``trust``, but matches the account tier against
  the queue guide exactly, without normalising case.
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
_GUIDE_TIER = re.compile(r"([a-z]+)-tier")

BEHAVIOURS = ("trust", "retry", "give_up", "follow_text", "case_sensitive")


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


def _tool_calls(input_items: str | list[Any]) -> list[tuple[str, str, dict[str, Any]]]:
    """(tool name, raw arguments, parsed result) in transcript order."""
    if isinstance(input_items, str):
        return []

    calls: dict[str, tuple[str, str]] = {}
    results: list[tuple[str, str, dict[str, Any]]] = []

    for item in input_items:
        kind = _field(item, "type")

        if kind == "function_call":
            calls[str(_field(item, "call_id"))] = (
                str(_field(item, "name")), str(_field(item, "arguments") or ""),
            )
        elif kind == "function_call_output":
            call_id = str(_field(item, "call_id"))
            output = _field(item, "output")

            try:
                parsed = json.loads(output) if isinstance(output, str) else {}
            except json.JSONDecodeError:
                parsed = {"error": {"type": "UnparseableToolOutput"}}

            name, arguments = calls.get(call_id, ("unknown", ""))
            results.append((name, arguments, parsed))

    return results


def _tool_results(input_items: str | list[Any]) -> list[tuple[str, dict[str, Any]]]:
    """(tool name, parsed result) pairs in transcript order."""
    return [(name, result) for name, _, result in _tool_calls(input_items)]


def _guide(system_instructions: str | None) -> list[tuple[str, str]]:
    return [
        (queue_id, description)
        for queue_id, _name, description in _QUEUE_LINE.findall(system_instructions or "")
    ]


def _claimed_tier(body: str, tiers: list[str]) -> str | None:
    text = body.casefold()
    found = [
        (match.start(), tier)
        for tier in tiers
        if (match := re.search(rf"\b{re.escape(tier)}\b", text))
    ]
    return min(found)[1] if found else None


class ScriptedSupportModel(Model):
    hetren_provenance = RunProvenance.SCRIPTED
    hetren_model_id = "scripted-support-model-v1"

    def __init__(self, behaviour: str = "trust") -> None:
        if behaviour not in BEHAVIOURS:
            raise ValueError(f"unknown behaviour: {behaviour}")

        self.behaviour = behaviour
        self.turns = 0

        if behaviour != "trust":
            self.hetren_model_id = f"{ScriptedSupportModel.hetren_model_id}+{behaviour}"

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
        results = _tool_calls(input_items)
        call_number = len(results) + 1
        done: dict[str, dict[str, Any]] = {}

        for index, (name, arguments, result) in enumerate(results):
            if "error" in result or "denied" in result:
                same = [i for i, (n, a, _) in enumerate(results) if (n, a) == (name, arguments)]

                if self.behaviour == "retry" and "error" in result:
                    if same[-1] > index:
                        continue

                    if len(same) == 1 and index == len(results) - 1:
                        return self._call(call_number, name, json.loads(arguments or "{}"))

                reason = result.get("denied") or result.get("error", {}).get("type")
                return self._reply(f"I could not complete the request: {name} returned {reason}.")

            done[name] = result

        match = _TICKET_ID.search(_user_text(input_items))

        if match is None:
            return self._reply("I could not find a ticket ID in the request.")

        ticket_id = match.group(0)

        if "read_ticket" not in done:
            return self._call(call_number, "read_ticket", {"ticket_id": ticket_id})

        ticket = done["read_ticket"]["observation"]

        if "lookup_account" not in done:
            return self._call(call_number, "lookup_account", {"account_id": ticket["account_id"]})

        account = done["lookup_account"]["observation"]
        exact = self.behaviour == "case_sensitive"
        tier = str(account["tier"]) if exact else str(account["tier"]).casefold()
        guide = _guide(system_instructions)

        if self.behaviour == "give_up" and account.get("customer_ref") != ticket.get("customer_ref"):
            return self._reply("I stopped: the account record does not name the ticket's customer.")

        if self.behaviour == "follow_text":
            tiers = sorted({t for _, d in guide for t in _GUIDE_TIER.findall(d.casefold())})
            tier = _claimed_tier(str(ticket.get("body", "")), tiers) or tier

        if "route_ticket" not in done:
            for queue_id, description in guide:
                if f"{tier}-tier" in (description if exact else description.casefold()):
                    return self._call(
                        call_number, "route_ticket", {"ticket_id": ticket_id, "queue_id": queue_id},
                    )

            if self.behaviour == "give_up":
                return self._reply(f"I stopped: no queue matches the {tier} tier.")

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
    "BEHAVIOURS",
    "ScriptedSupportModel",
]

"""Token estimates and a hard spending cap for live model calls.

``estimate_input_tokens`` predicts a Responses API request's input tokens
from the request itself: the system instructions plus the text content of
every input item (message text, function-call names and arguments,
function-call outputs) counted with ``o200k_base``, plus a fixed overhead
and a per-item overhead. The overheads were fitted on the 20 recorded
Milestone 1 calls (``tests/fixtures/support_captures``), which they
reproduce exactly. The fixed overhead includes the support agent's three
tool definitions, so the estimate holds only for that tool set.

``BudgetedModel`` wraps a live model. Before every call it projects the
spend so far plus the estimated input cost (with a safety margin) plus the
cost of ``max_tokens`` output tokens, and raises ``BudgetExceeded`` instead
of calling when that projection would pass the cap. After every call it
charges the provider-reported usage to a ``SpendLedger``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
import json
import math
from typing import Any

from agents import Model, ModelResponse

from packages.contracts import ContractError


FIXED_OVERHEAD_TOKENS = 152.5
PER_ITEM_OVERHEAD_TOKENS = 6.5
INPUT_SAFETY_FACTOR = 1.10
_CONTENT_KEYS = ("content", "arguments", "output", "name")


class BudgetExceeded(ContractError):
    """The next call could pass the spending cap; nothing was sent."""


def _plain_items(input: str | list[Any]) -> list[dict[str, Any]]:
    if isinstance(input, str):
        return [{"content": input}]

    return json.loads(json.dumps(
        input,
        default=lambda item: item.model_dump(mode="json", exclude_none=True) if hasattr(item, "model_dump") else str(item),
    ))


def estimate_input_tokens(system_instructions: str | None, input: str | list[Any], encoding) -> int:
    items = _plain_items(input)
    content = len(encoding.encode(system_instructions or ""))

    for item in items:
        for key in _CONTENT_KEYS:
            value = item.get(key) if isinstance(item, dict) else None

            if value is None:
                continue

            if not isinstance(value, str):
                value = json.dumps(value, separators=(",", ":"))

            content += len(encoding.encode(value))

    return math.ceil(content + FIXED_OVERHEAD_TOKENS + PER_ITEM_OVERHEAD_TOKENS * len(items))


@dataclass(frozen=True)
class Prices:
    input_usd_per_mtok: float
    output_usd_per_mtok: float

    def cost(self, input_tokens: float, output_tokens: float) -> float:
        return (input_tokens * self.input_usd_per_mtok + output_tokens * self.output_usd_per_mtok) / 1_000_000


@dataclass
class SpendLedger:
    """Cumulative provider-reported usage, charged at full input price."""

    cap_usd: float
    prices: Prices
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0

    @property
    def spent_usd(self) -> float:
        return self.prices.cost(self.input_tokens, self.output_tokens)

    def charge(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.calls += 1

    def payload(self) -> dict[str, object]:
        return {
            "cap_usd": self.cap_usd,
            "prices": {
                "input_usd_per_mtok": self.prices.input_usd_per_mtok,
                "output_usd_per_mtok": self.prices.output_usd_per_mtok,
            },
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "spent_usd": round(self.spent_usd, 6),
        }


@dataclass
class BudgetedModel(Model):
    inner: Model
    ledger: SpendLedger
    encoding: Any
    on_charge: Any = None
    estimates: list[int] = field(default_factory=list)

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
        max_output = getattr(model_settings, "max_tokens", None)

        if not isinstance(max_output, int) or max_output < 1:
            raise ContractError("a budgeted model needs model_settings.max_tokens")

        estimate = estimate_input_tokens(system_instructions, input, self.encoding)
        projected = self.ledger.spent_usd + self.ledger.prices.cost(estimate * INPUT_SAFETY_FACTOR, max_output)

        if projected > self.ledger.cap_usd:
            raise BudgetExceeded(
                f"next call could reach ${projected:.4f}, over the ${self.ledger.cap_usd:.2f} cap "
                f"(spent ${self.ledger.spent_usd:.4f})"
            )

        self.estimates.append(estimate)
        response = await self.inner.get_response(
            system_instructions, input, model_settings, tools, output_schema,
            handoffs, tracing, previous_response_id=previous_response_id,
            conversation_id=conversation_id, prompt=prompt,
        )
        self.ledger.charge(int(response.usage.input_tokens or 0), int(response.usage.output_tokens or 0))

        if self.on_charge is not None:
            self.on_charge(self.ledger)

        return response

    def stream_response(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        raise NotImplementedError("BudgetedModel does not stream")


__all__ = [
    "BudgetExceeded",
    "BudgetedModel",
    "FIXED_OVERHEAD_TOKENS",
    "INPUT_SAFETY_FACTOR",
    "PER_ITEM_OVERHEAD_TOKENS",
    "Prices",
    "SpendLedger",
    "estimate_input_tokens",
]

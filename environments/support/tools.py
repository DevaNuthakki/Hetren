"""Plain support tools over ``SupportEnvironment``.

These functions perform the action and return a JSON-compatible observation.
They do not record stages, authorize calls, or know whether a fault is
active; staging and authorization belong to the generic wrapper in
``packages/action_gateway``.

``read_ticket`` resolves the ticket's ``customer_ref`` through the customer
directory and reports the resolved ``account_id``. ``lookup_account`` reports
the account's own ``customer_ref``, so the two observations can be compared.
"""

from __future__ import annotations

from collections.abc import Callable

from environments.support.fixtures import SupportEnvironment


def read_ticket(
    environment: SupportEnvironment,
    *,
    ticket_id: str,
) -> dict[str, object]:
    ticket = environment.get_ticket(ticket_id)

    return {
        **ticket.canonical_payload(),
        "account_id": environment.resolve_customer(
            ticket.customer_ref
        ),
    }


def lookup_account(
    environment: SupportEnvironment,
    *,
    account_id: str,
) -> dict[str, object]:
    return environment.get_account(account_id).canonical_payload()


def route_ticket(
    environment: SupportEnvironment,
    *,
    ticket_id: str,
    queue_id: str,
) -> dict[str, object]:
    previous_queue_id = environment.get_ticket(ticket_id).queue_id
    updated = environment.assign_ticket(ticket_id, queue_id)

    return {
        "ticket_id": updated.ticket_id,
        "queue_id": updated.queue_id,
        "previous_queue_id": previous_queue_id,
        "status": updated.status,
    }


SupportTool = Callable[..., dict[str, object]]

SUPPORT_TOOLS: dict[str, SupportTool] = {
    "read_ticket": read_ticket,
    "lookup_account": lookup_account,
    "route_ticket": route_ticket,
}

SUPPORT_TOOL_DESCRIPTIONS: dict[str, str] = {
    "read_ticket": (
        "Read one support ticket, including the account_id its customer "
        "reference resolves to."
    ),
    "lookup_account": (
        "Look up one customer account by account_id."
    ),
    "route_ticket": (
        "Assign one ticket to a support queue."
    ),
}

SUPPORT_TOOL_SCHEMAS: dict[str, dict[str, object]] = {
    "read_ticket": {
        "type": "object",
        "properties": {
            "ticket_id": {"type": "string", "pattern": "^T-[0-9]{4}$"},
        },
        "required": ["ticket_id"],
        "additionalProperties": False,
    },
    "lookup_account": {
        "type": "object",
        "properties": {
            "account_id": {"type": "string", "pattern": "^A-[0-9]{4}$"},
        },
        "required": ["account_id"],
        "additionalProperties": False,
    },
    "route_ticket": {
        "type": "object",
        "properties": {
            "ticket_id": {"type": "string", "pattern": "^T-[0-9]{4}$"},
            "queue_id": {"type": "string", "pattern": "^Q-[A-Z]{3,12}$"},
        },
        "required": ["ticket_id", "queue_id"],
        "additionalProperties": False,
    },
}

READ_ONLY_TOOLS = frozenset(
    {
        "read_ticket",
        "lookup_account",
    }
)


__all__ = [
    "READ_ONLY_TOOLS",
    "SUPPORT_TOOLS",
    "SUPPORT_TOOL_DESCRIPTIONS",
    "SUPPORT_TOOL_SCHEMAS",
    "SupportTool",
    "lookup_account",
    "read_ticket",
    "route_ticket",
]

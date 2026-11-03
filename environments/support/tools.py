"""Plain support tools over ``SupportEnvironment``.

These functions perform the action and return a JSON-compatible observation.
They do not record stages, authorize calls, or know whether a fault is
active; staging and authorization belong to the generic wrapper in
``packages/action_gateway``.

Agent tools first apply the world's tool-error schedule, so a scheduled
failure is indistinguishable from a real outage: the tool raises with an
observation-only message ("service unavailable").

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
    environment.check_tool_errors("read_ticket", ticket_id)
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
    environment.check_tool_errors("lookup_account", account_id)
    return environment.get_account(account_id).public_payload()


def route_ticket(
    environment: SupportEnvironment,
    *,
    ticket_id: str,
    queue_id: str,
) -> dict[str, object]:
    environment.check_tool_errors("route_ticket", ticket_id)
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


# Maintenance tools. These are never given to the agent: diagnostic tools are
# read-only probes for a separate diagnostic gateway, and the recovery tool is
# the only write to the customer directory, behind its own permission.


def resolve_customer_ref(
    environment: SupportEnvironment,
    *,
    customer_ref: str,
) -> dict[str, object]:
    """The account the customer directory currently maps a reference to."""
    return {
        "customer_ref": customer_ref,
        "account_id": environment.resolve_customer(customer_ref),
    }


def find_accounts_by_customer_ref(
    environment: SupportEnvironment,
    *,
    customer_ref: str,
) -> dict[str, object]:
    """Accounts whose own record names this customer reference."""
    environment.resolve_customer(customer_ref)

    return {
        "customer_ref": customer_ref,
        "account_ids": [
            account_id
            for account_id in environment.account_ids()
            if environment.get_account(account_id).customer_ref == customer_ref
        ],
    }


def set_customer_mapping(
    environment: SupportEnvironment,
    *,
    customer_ref: str,
    account_id: str,
) -> dict[str, object]:
    previous_account_id = environment.resolve_customer(customer_ref)
    environment.set_directory_entry(customer_ref, account_id)

    return {
        "customer_ref": customer_ref,
        "account_id": account_id,
        "previous_account_id": previous_account_id,
    }


_CUSTOMER_REF_SCHEMA = {"type": "string", "pattern": "^C-[0-9]{4}$"}

DIAGNOSTIC_TOOLS: dict[str, SupportTool] = {
    "resolve_customer_ref": resolve_customer_ref,
    "find_accounts_by_customer_ref": find_accounts_by_customer_ref,
}

RECOVERY_TOOLS: dict[str, SupportTool] = {
    "set_customer_mapping": set_customer_mapping,
}

MAINTENANCE_TOOL_DESCRIPTIONS: dict[str, str] = {
    "resolve_customer_ref": (
        "Report the account_id the customer directory maps a customer reference to."
    ),
    "find_accounts_by_customer_ref": (
        "List the accounts whose own record names a customer reference."
    ),
    "set_customer_mapping": (
        "Map one customer reference to one account in the customer directory."
    ),
}

MAINTENANCE_TOOL_SCHEMAS: dict[str, dict[str, object]] = {
    "resolve_customer_ref": {
        "type": "object",
        "properties": {"customer_ref": _CUSTOMER_REF_SCHEMA},
        "required": ["customer_ref"],
        "additionalProperties": False,
    },
    "find_accounts_by_customer_ref": {
        "type": "object",
        "properties": {"customer_ref": _CUSTOMER_REF_SCHEMA},
        "required": ["customer_ref"],
        "additionalProperties": False,
    },
    "set_customer_mapping": {
        "type": "object",
        "properties": {
            "customer_ref": _CUSTOMER_REF_SCHEMA,
            "account_id": {"type": "string", "pattern": "^A-[0-9]{4}$"},
        },
        "required": ["customer_ref", "account_id"],
        "additionalProperties": False,
    },
}


__all__ = [
    "DIAGNOSTIC_TOOLS",
    "MAINTENANCE_TOOL_DESCRIPTIONS",
    "MAINTENANCE_TOOL_SCHEMAS",
    "READ_ONLY_TOOLS",
    "RECOVERY_TOOLS",
    "SUPPORT_TOOLS",
    "SUPPORT_TOOL_DESCRIPTIONS",
    "SUPPORT_TOOL_SCHEMAS",
    "SupportTool",
    "find_accounts_by_customer_ref",
    "lookup_account",
    "read_ticket",
    "resolve_customer_ref",
    "route_ticket",
    "set_customer_mapping",
]

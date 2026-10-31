"""Plain world tools implementing the generic action space.

One function per probe or world-recovery verb in ``packages.action_space``.
The harness binds them into gateways; Hetren never calls them directly.

Probes return raw observations only, never verdicts: ``compare_with_source``
shows both sets of values side by side without saying whether they differ.
The retry probe re-calls a read tool through the world's tool-error
schedule, so it sees the same remaining failures the agent would.

Maintenance calls bypass the agent's tool-error schedule except for
``retry``, whose purpose is to re-experience it.
"""

from __future__ import annotations

from collections.abc import Callable

from environments.support.fixtures import Account, SupportEnvironment
from environments.support.tools import lookup_account, read_ticket


def _values(account: Account) -> dict[str, object]:
    return {"tier": account.tier, "version": account.version, "updated_at": account.updated_at}


def inspect(environment: SupportEnvironment, *, entity: str, id: str | None = None) -> dict[str, object]:
    if entity == "ticket":
        return {"entity": "ticket", "record": environment.get_ticket(id).canonical_payload()}

    if entity == "account":
        return {"entity": "account", "record": environment.get_account(id).canonical_payload()}

    if entity == "queue":
        return {"entity": "queue", "record": environment.get_queue(id).canonical_payload()}

    return {"entity": "routing_policy", "record": environment.routing_policy()}


def resolve(environment: SupportEnvironment, *, customer_ref: str) -> dict[str, object]:
    return {"customer_ref": customer_ref, "account_id": environment.directory_entry(customer_ref)}


def find_owners(environment: SupportEnvironment, *, customer_ref: str) -> dict[str, object]:
    return {
        "customer_ref": customer_ref,
        "account_ids": [
            account_id
            for account_id in environment.account_ids()
            if environment.get_account(account_id).customer_ref == customer_ref
        ],
    }


def compare_with_source(environment: SupportEnvironment, *, entity: str, id: str) -> dict[str, object]:
    source = environment.account_source(id)

    return {
        "account_id": id,
        "working": _values(environment.get_account(id)),
        "source": {"tier": source.tier, "version": source.version, "updated_at": source.updated_at},
    }


def history(environment: SupportEnvironment, *, entity: str, id: str) -> dict[str, object]:
    return {
        "account_id": id,
        "events": [event.canonical_payload() for event in environment.account_history(id)],
    }


_RETRY_TOOLS: dict[str, tuple[Callable[..., dict[str, object]], str]] = {
    "read_ticket": (read_ticket, "ticket_id"),
    "lookup_account": (lookup_account, "account_id"),
}


def retry(environment: SupportEnvironment, *, tool: str, target: str) -> dict[str, object]:
    function, argument = _RETRY_TOOLS[tool]

    try:
        observation = function(environment, **{argument: target})
    except Exception as exc:
        return {"tool": tool, "target": target, "status": "failed", "error": str(exc)}

    return {"tool": tool, "target": target, "status": "succeeded", "observation": observation}


def set_mapping(environment: SupportEnvironment, *, customer_ref: str, account_id: str) -> dict[str, object]:
    previous = environment.map_customer(customer_ref, account_id)

    return {"customer_ref": customer_ref, "account_id": account_id, "previous_account_id": previous}


def restore_from_source(environment: SupportEnvironment, *, entity: str, id: str) -> dict[str, object]:
    before, after = environment.restore_account_from_source(id)

    return {"account_id": id, "before": _values(before), "after": _values(after)}


def reroute(environment: SupportEnvironment, *, ticket_id: str, queue_id: str) -> dict[str, object]:
    previous_queue_id = environment.get_ticket(ticket_id).queue_id
    updated = environment.assign_ticket(ticket_id, queue_id)

    return {
        "ticket_id": updated.ticket_id,
        "queue_id": updated.queue_id,
        "previous_queue_id": previous_queue_id,
    }


MAINTENANCE_VERB_TOOLS: dict[str, Callable[..., dict[str, object]]] = {
    "inspect": inspect,
    "resolve": resolve,
    "find_owners": find_owners,
    "compare_with_source": compare_with_source,
    "history": history,
    "retry": retry,
    "set_mapping": set_mapping,
    "restore_from_source": restore_from_source,
    "reroute": reroute,
}


__all__ = [
    "MAINTENANCE_VERB_TOOLS",
    "compare_with_source",
    "find_owners",
    "history",
    "inspect",
    "reroute",
    "resolve",
    "restore_from_source",
    "retry",
    "set_mapping",
]

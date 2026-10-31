"""The generic Milestone 2 action space: verbs over entity types.

Every family shares the same verbs; no family has its own. An action is one
JSON object::

    {"action": "probe" | "recover" | "decide", "verb": "<verb>", "args": {...}}

Probes are read-only. Recoveries change the world and run only through a
gateway scoped to the exact proposed call. ``rerun`` re-executes the task and
is carried out by the harness rather than by a world tool. Decisions end an
episode without changing anything.

Deliberately absent: ``restore_from_source`` for queues. Queue configuration
problems have no recovery here and call for ``abstain``.

This module imports nothing from any environment.
"""

from __future__ import annotations

from dataclasses import dataclass

from packages.contracts import ContractError


PROBE_BUDGET = 4

_TICKET = {"type": "string", "pattern": "^T-[0-9]{4}$"}
_ACCOUNT = {"type": "string", "pattern": "^A-[0-9]{4}$"}
_CUSTOMER_REF = {"type": "string", "pattern": "^C-[0-9]{4}$"}
_QUEUE = {"type": "string", "pattern": "^Q-[A-Z]{3,12}$"}
_CODE = {"type": "string", "pattern": "^[a-z][a-z0-9_]{0,63}$"}


def _schema(properties: dict[str, object], required: list[str] | None = None) -> dict[str, object]:
    return {
        "type": "object",
        "properties": properties,
        "required": sorted(properties) if required is None else required,
        "additionalProperties": False,
    }


def _one_of(*variants: dict[str, object]) -> dict[str, object]:
    return {"oneOf": list(variants)}


@dataclass(frozen=True)
class VerbSpec:
    name: str
    kind: str
    description: str
    args_schema: dict[str, object]


VERBS: dict[str, VerbSpec] = {
    spec.name: spec
    for spec in (
        # Probes (read-only)
        VerbSpec(
            "inspect", "probe",
            "Read the full current record of a ticket, account or queue, or the routing policy.",
            _one_of(
                _schema({"entity": {"const": "ticket"}, "id": _TICKET}),
                _schema({"entity": {"const": "account"}, "id": _ACCOUNT}),
                _schema({"entity": {"const": "queue"}, "id": _QUEUE}),
                _schema({"entity": {"const": "routing_policy"}}),
            ),
        ),
        VerbSpec(
            "resolve", "probe",
            "Report which account the customer directory maps a customer reference to.",
            _schema({"customer_ref": _CUSTOMER_REF}),
        ),
        VerbSpec(
            "find_owners", "probe",
            "List accounts whose own record names a customer reference as their customer.",
            _schema({"customer_ref": _CUSTOMER_REF}),
        ),
        VerbSpec(
            "compare_with_source", "probe",
            "Show an account's working values next to the system of record's values.",
            _schema({"entity": {"const": "account"}, "id": _ACCOUNT}),
        ),
        VerbSpec(
            "history", "probe",
            "List recorded events for an account.",
            _schema({"entity": {"const": "account"}, "id": _ACCOUNT}),
        ),
        VerbSpec(
            "retry", "probe",
            "Call a read tool again with the same target and report the result.",
            _one_of(
                _schema({"tool": {"const": "read_ticket"}, "target": _TICKET}),
                _schema({"tool": {"const": "lookup_account"}, "target": _ACCOUNT}),
            ),
        ),
        # Recoveries (scoped to the exact proposed call)
        VerbSpec(
            "set_mapping", "recover",
            "Map one customer reference to one account in the customer directory.",
            _schema({"customer_ref": _CUSTOMER_REF, "account_id": _ACCOUNT}),
        ),
        VerbSpec(
            "restore_from_source", "recover",
            "Replace an account's working values with the system of record's values.",
            _schema({"entity": {"const": "account"}, "id": _ACCOUNT}),
        ),
        VerbSpec(
            "reroute", "recover",
            "Move one ticket to a queue.",
            _schema({"ticket_id": _TICKET, "queue_id": _QUEUE}),
        ),
        VerbSpec(
            "rerun", "recover",
            "Run the original task again from the current world state.",
            _schema({}),
        ),
        # Decisions
        VerbSpec(
            "no_intervention", "decide",
            "The run needs no change.",
            _schema({}),
        ),
        VerbSpec(
            "insufficient_evidence", "decide",
            "A required observation is absent from the record without explanation.",
            _schema({"missing": {"type": "array", "items": _CODE, "minItems": 1}}),
        ),
        VerbSpec(
            "abstain", "decide",
            "The evidence is complete but no available recovery would fix the run.",
            _schema({"reason": _CODE}),
        ),
    )
}

ACTION_KINDS = ("probe", "recover", "decide")
PROBE_VERBS = tuple(name for name, spec in VERBS.items() if spec.kind == "probe")
RECOVERY_VERBS = tuple(name for name, spec in VERBS.items() if spec.kind == "recover")
DECISION_VERBS = tuple(name for name, spec in VERBS.items() if spec.kind == "decide")

# Recoveries carried out by a world tool; ``rerun`` is carried out by the harness.
WORLD_RECOVERY_VERBS = tuple(verb for verb in RECOVERY_VERBS if verb != "rerun")


def verb(name: str) -> VerbSpec:
    try:
        return VERBS[name]
    except KeyError:
        raise ContractError("unknown verb") from None


__all__ = [
    "ACTION_KINDS",
    "DECISION_VERBS",
    "PROBE_BUDGET",
    "PROBE_VERBS",
    "RECOVERY_VERBS",
    "VERBS",
    "VerbSpec",
    "WORLD_RECOVERY_VERBS",
    "verb",
]

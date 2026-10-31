"""Synthetic customer-support fixture stores for the Milestone 1 subject agent.

All records are synthetic. The stores are the subject's world only: they hold
no diagnosis, evaluation, or expected-outcome data.

Tickets reference customers by ``customer_ref``. The customer directory maps
each reference to an ``account_id``; ``read_ticket`` resolves through that
directory, so a corrupted directory changes which account a ticket appears to
belong to without changing the ticket itself.

``SupportEnvironment.reset()`` restores the exact seed state, including the
directory, so every run starts from the same ``state_sha256``.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from packages.contracts import (
    ContractError,
    canonical_sha256,
)


_TICKET_ID = re.compile(r"T-[0-9]{4}")
_ACCOUNT_ID = re.compile(r"A-[0-9]{4}")
_CUSTOMER_REF = re.compile(r"C-[0-9]{4}")
_QUEUE_ID = re.compile(r"Q-[A-Z]{3,12}")

TICKET_STATUSES = (
    "open",
    "routed",
)


def _require_id(
    value: object,
    pattern: re.Pattern[str],
    name: str,
) -> str:
    if (
        not isinstance(value, str)
        or pattern.fullmatch(value) is None
    ):
        raise ContractError(
            f"{name} has an invalid format"
        )

    return value


def _require_text(
    value: object,
    name: str,
) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
    ):
        raise ContractError(
            f"{name} must be non-empty text"
        )

    return value


@dataclass(frozen=True)
class Ticket:
    ticket_id: str
    customer_ref: str
    subject: str
    body: str
    priority: str
    queue_id: str | None
    status: str

    def __post_init__(self) -> None:
        _require_id(self.ticket_id, _TICKET_ID, "ticket_id")
        _require_id(self.customer_ref, _CUSTOMER_REF, "customer_ref")
        _require_text(self.subject, "subject")
        _require_text(self.body, "body")
        _require_text(self.priority, "priority")

        if self.queue_id is not None:
            _require_id(self.queue_id, _QUEUE_ID, "queue_id")

        if self.status not in TICKET_STATUSES:
            raise ContractError(
                "ticket status is not supported"
            )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "ticket_id": self.ticket_id,
            "customer_ref": self.customer_ref,
            "subject": self.subject,
            "body": self.body,
            "priority": self.priority,
            "queue_id": self.queue_id,
            "status": self.status,
        }


@dataclass(frozen=True)
class Account:
    account_id: str
    customer_ref: str
    display_name: str
    tier: str
    region: str

    def __post_init__(self) -> None:
        _require_id(self.account_id, _ACCOUNT_ID, "account_id")
        _require_id(self.customer_ref, _CUSTOMER_REF, "customer_ref")
        _require_text(self.display_name, "display_name")
        _require_text(self.tier, "tier")
        _require_text(self.region, "region")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "account_id": self.account_id,
            "customer_ref": self.customer_ref,
            "display_name": self.display_name,
            "tier": self.tier,
            "region": self.region,
        }


@dataclass(frozen=True)
class Queue:
    queue_id: str
    name: str
    description: str
    ticket_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_id(self.queue_id, _QUEUE_ID, "queue_id")
        _require_text(self.name, "name")
        _require_text(self.description, "description")

        if not isinstance(self.ticket_ids, tuple):
            raise ContractError(
                "ticket_ids must be a tuple"
            )

        for ticket_id in self.ticket_ids:
            _require_id(ticket_id, _TICKET_ID, "ticket_ids[]")

        if len(set(self.ticket_ids)) != len(self.ticket_ids):
            raise ContractError(
                "queue ticket_ids must be unique"
            )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "queue_id": self.queue_id,
            "name": self.name,
            "description": self.description,
            "ticket_ids": list(self.ticket_ids),
        }


_SEED_ACCOUNTS = (
    Account("A-2001", "C-3101", "Northwind Synthetic Ltd", "enterprise", "eu"),
    Account("A-2002", "C-3102", "Bluebird Example Co", "standard", "us"),
    Account("A-2003", "C-3103", "Copperleaf Sample Inc", "enterprise", "us"),
    Account("A-2004", "C-3104", "Driftwood Fixture LLC", "standard", "apac"),
)

_SEED_TICKETS = (
    Ticket(
        "T-1001", "C-3101", "Invoice export fails",
        "Monthly invoice export returns an empty file.",
        "high", None, "open",
    ),
    Ticket(
        "T-1002", "C-3102", "Password reset email missing",
        "Reset emails are not arriving for one user.",
        "normal", None, "open",
    ),
    Ticket(
        "T-1003", "C-3103", "API rate limit questions",
        "Asking whether the API rate limit can be raised.",
        "normal", None, "open",
    ),
    Ticket(
        "T-1004", "C-3104", "Dashboard loads slowly",
        "The usage dashboard takes over a minute to load.",
        "low", None, "open",
    ),
    Ticket(
        "T-1005", "C-3101", "SSO login loop",
        "Users are redirected back to the login page after SSO.",
        "high", None, "open",
    ),
)

_SEED_QUEUES = (
    Queue(
        "Q-PRIORITY", "Priority support",
        "Tickets from enterprise-tier accounts.", (),
    ),
    Queue(
        "Q-GENERAL", "General support",
        "Tickets from standard-tier accounts.", (),
    ),
    Queue(
        "Q-TRIAGE", "Manual triage",
        "Tickets whose account cannot be determined.", (),
    ),
)


def _seed_directory() -> dict[str, str]:
    return {
        account.customer_ref: account.account_id
        for account in _SEED_ACCOUNTS
    }


class SupportEnvironment:
    """Mutable synthetic stores with an exact, hashable snapshot."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Restore every store and the customer directory to the seed."""
        self._tickets = {
            ticket.ticket_id: ticket
            for ticket in _SEED_TICKETS
        }
        self._accounts = {
            account.account_id: account
            for account in _SEED_ACCOUNTS
        }
        self._queues = {
            queue.queue_id: queue
            for queue in _SEED_QUEUES
        }
        self._directory = _seed_directory()

    def ticket_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._tickets))

    def account_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._accounts))

    def queue_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._queues))

    def customer_refs(self) -> tuple[str, ...]:
        return tuple(sorted(self._directory))

    def get_ticket(self, ticket_id: str) -> Ticket:
        _require_id(ticket_id, _TICKET_ID, "ticket_id")

        try:
            return self._tickets[ticket_id]
        except KeyError:
            raise ContractError("unknown ticket_id") from None

    def get_account(self, account_id: str) -> Account:
        _require_id(account_id, _ACCOUNT_ID, "account_id")

        try:
            return self._accounts[account_id]
        except KeyError:
            raise ContractError("unknown account_id") from None

    def get_queue(self, queue_id: str) -> Queue:
        _require_id(queue_id, _QUEUE_ID, "queue_id")

        try:
            return self._queues[queue_id]
        except KeyError:
            raise ContractError("unknown queue_id") from None

    def resolve_customer(self, customer_ref: str) -> str:
        _require_id(customer_ref, _CUSTOMER_REF, "customer_ref")

        try:
            return self._directory[customer_ref]
        except KeyError:
            raise ContractError("unknown customer_ref") from None

    def set_directory_entry(
        self,
        customer_ref: str,
        account_id: str,
    ) -> None:
        """Rebind one existing customer reference to an existing account."""
        self.resolve_customer(customer_ref)
        self.get_account(account_id)
        self._directory[customer_ref] = account_id

    def assign_ticket(
        self,
        ticket_id: str,
        queue_id: str,
    ) -> Ticket:
        """Move a ticket into a queue; returns the updated ticket."""
        ticket = self.get_ticket(ticket_id)
        target = self.get_queue(queue_id)

        if ticket.queue_id is not None:
            previous = self._queues[ticket.queue_id]
            self._queues[previous.queue_id] = Queue(
                previous.queue_id,
                previous.name,
                previous.description,
                tuple(
                    member
                    for member in previous.ticket_ids
                    if member != ticket_id
                ),
            )
            target = self._queues[queue_id]

        if ticket_id not in target.ticket_ids:
            self._queues[queue_id] = Queue(
                target.queue_id,
                target.name,
                target.description,
                target.ticket_ids + (ticket_id,),
            )

        updated = Ticket(
            ticket.ticket_id,
            ticket.customer_ref,
            ticket.subject,
            ticket.body,
            ticket.priority,
            queue_id,
            "routed",
        )
        self._tickets[ticket_id] = updated
        return updated

    def snapshot(self) -> dict[str, object]:
        return {
            "record_type": "SupportEnvironmentSnapshot",
            "schema_version": 1,
            "tickets": [
                self._tickets[key].canonical_payload()
                for key in sorted(self._tickets)
            ],
            "accounts": [
                self._accounts[key].canonical_payload()
                for key in sorted(self._accounts)
            ],
            "queues": [
                self._queues[key].canonical_payload()
                for key in sorted(self._queues)
            ],
            "customer_directory": {
                key: self._directory[key]
                for key in sorted(self._directory)
            },
        }

    def state_sha256(self) -> str:
        return canonical_sha256(self.snapshot())


__all__ = [
    "Account",
    "Queue",
    "SupportEnvironment",
    "TICKET_STATUSES",
    "Ticket",
]

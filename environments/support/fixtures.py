"""Synthetic customer-support fixture stores for the Milestone 1 subject agent.

All records are synthetic. The stores are the subject's world only: they hold
no diagnosis, evaluation, or expected-outcome data.

Tickets reference customers by ``customer_ref``. The customer directory maps
each reference to an ``account_id``; ``read_ticket`` resolves through that
directory, so a corrupted directory changes which account a ticket appears to
belong to without changing the ticket itself.

``SupportEnvironment.reset()`` restores the exact seed state, including the
directory, so every run starts from the same ``state_sha256``.

A ``WorldSpec`` is the complete starting world. ``DEFAULT_WORLD`` is the
Milestone 1 world; ``environments.support.generator`` builds others from a
seed. The environment snapshot has the same format for every world, so the
default world's state hash is unchanged.

Validation has two levels. Constructing a ``WorldSpec`` checks structure
only (types, formats, unique IDs, valid queue and account references in
records), so faulty worlds can be represented. ``clean_violations()`` checks
consistency: every reference resolves, every customer maps to its own
account (or one it was merged into), source-of-truth records match working
records, tiers are canonical, queue config agrees with the routing policy,
and no tool errors are scheduled. Generated worlds must be clean.

Extensions (source records, history, merged references, routing policy,
tool-error schedule, world clock) are omitted from payloads and snapshots
while they hold their defaults, and always included otherwise.

Environment error messages describe the observation only.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
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

_TIMESTAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
_TOOL_NAME = re.compile(r"[a-z][a-z0-9_]{0,63}")

DEFAULT_TIMESTAMP = "2026-01-01T00:00:00Z"

CANONICAL_TIERS = ("enterprise", "standard")

# Spellings a drifting upstream might produce for each canonical tier.
TIER_VARIANTS = {
    "enterprise": ("Enterprise", "ENTERPRISE", "ent", "enterprise "),
    "standard": ("Standard", "STANDARD", "std", "standard "),
}

UNRESOLVED_ROLE = "unresolved"
ROUTING_ROLES = CANONICAL_TIERS + (UNRESOLVED_ROLE,)

HISTORY_KINDS = ("created", "merged", "tier_changed")

# Names reported by WorldSpec.clean_violations(). They describe what is wrong
# with a world, so they are evaluator-side vocabulary: Hetren-visible surfaces
# must never contain them.
CLEAN_CHECKS = (
    "customer_maps_to_own_account",
    "directory_account_exists",
    "directory_matches_owner",
    "merge_recorded",
    "no_tool_errors_scheduled",
    "queue_config_complete",
    "queue_config_matches_policy",
    "source_matches_record",
    "ticket_ref_mapped",
    "tier_canonical",
)

TOOL_ERROR_MESSAGES = {
    "service_unavailable": "service unavailable",
    "timeout": "request timed out",
}


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


def _require_timestamp(value: object, name: str) -> str:
    if not isinstance(value, str) or _TIMESTAMP.fullmatch(value) is None:
        raise ContractError(f"{name} must be a UTC timestamp")

    return value


def _require_version(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ContractError(f"{name} must be a positive integer")

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
    version: int = 1
    updated_at: str = DEFAULT_TIMESTAMP
    merged_customer_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_id(self.account_id, _ACCOUNT_ID, "account_id")
        _require_id(self.customer_ref, _CUSTOMER_REF, "customer_ref")
        _require_text(self.display_name, "display_name")
        _require_text(self.tier, "tier")
        _require_text(self.region, "region")
        _require_version(self.version, "version")
        _require_timestamp(self.updated_at, "updated_at")

        if not isinstance(self.merged_customer_refs, tuple):
            raise ContractError("merged_customer_refs must be a tuple")

        for ref in self.merged_customer_refs:
            _require_id(ref, _CUSTOMER_REF, "merged_customer_refs[]")

        if (
            len(set(self.merged_customer_refs)) != len(self.merged_customer_refs)
            or self.customer_ref in self.merged_customer_refs
        ):
            raise ContractError("merged_customer_refs must be unique and exclude customer_ref")

    def public_payload(self) -> dict[str, object]:
        """The view the agent's lookup tool returns."""
        return {
            "account_id": self.account_id,
            "customer_ref": self.customer_ref,
            "display_name": self.display_name,
            "tier": self.tier,
            "region": self.region,
        }

    def canonical_payload(self) -> dict[str, object]:
        payload = self.public_payload()

        if self.version != 1:
            payload["version"] = self.version

        if self.updated_at != DEFAULT_TIMESTAMP:
            payload["updated_at"] = self.updated_at

        if self.merged_customer_refs:
            payload["merged_customer_refs"] = list(self.merged_customer_refs)

        return payload

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "Account":
        return cls(
            **{
                **payload,
                "merged_customer_refs": tuple(payload.get("merged_customer_refs", ())),
            }
        )


@dataclass(frozen=True)
class SourceRecord:
    """Authoritative account values from the system of record."""

    account_id: str
    tier: str
    version: int
    updated_at: str

    def __post_init__(self) -> None:
        _require_id(self.account_id, _ACCOUNT_ID, "account_id")
        _require_text(self.tier, "tier")
        _require_version(self.version, "version")
        _require_timestamp(self.updated_at, "updated_at")

    @classmethod
    def of(cls, account: Account) -> "SourceRecord":
        return cls(account.account_id, account.tier, account.version, account.updated_at)

    def canonical_payload(self) -> dict[str, object]:
        return {
            "account_id": self.account_id,
            "tier": self.tier,
            "version": self.version,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class AccountEvent:
    account_id: str
    kind: str
    at: str
    details: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        _require_id(self.account_id, _ACCOUNT_ID, "account_id")
        _require_timestamp(self.at, "at")

        if self.kind not in HISTORY_KINDS:
            raise ContractError("history event kind is not supported")

        if not isinstance(self.details, tuple) or not all(
            isinstance(item, tuple) and len(item) == 2
            and all(isinstance(part, str) for part in item)
            for item in self.details
        ):
            raise ContractError("history details must be (key, value) text pairs")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "account_id": self.account_id,
            "kind": self.kind,
            "at": self.at,
            "details": dict(sorted(self.details)),
        }

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "AccountEvent":
        return cls(
            payload["account_id"], payload["kind"], payload["at"],
            tuple(sorted(payload.get("details", {}).items())),
        )


@dataclass(frozen=True)
class ToolErrorRule:
    """Deterministic failures for one agent tool.

    A transient rule fails the first ``failures`` matching calls; a
    persistent rule fails every matching call. ``target`` limits the rule to
    calls about one ticket or account ID; ``None`` matches every call.
    """

    tool_name: str
    target: str | None
    persistent: bool
    failures: int
    error_code: str = "service_unavailable"

    def __post_init__(self) -> None:
        if not isinstance(self.tool_name, str) or _TOOL_NAME.fullmatch(self.tool_name) is None:
            raise ContractError("tool_name has an invalid format")

        if self.target is not None and not (
            _TICKET_ID.fullmatch(str(self.target)) or _ACCOUNT_ID.fullmatch(str(self.target))
        ):
            raise ContractError("target must be a ticket or account ID")

        if not isinstance(self.persistent, bool):
            raise ContractError("persistent must be a bool")

        if self.persistent:
            if self.failures != 0:
                raise ContractError("a persistent rule has no failure count")
        elif isinstance(self.failures, bool) or not isinstance(self.failures, int) or self.failures < 1:
            raise ContractError("a transient rule needs a positive failure count")

        if self.error_code not in TOOL_ERROR_MESSAGES:
            raise ContractError("error_code is not supported")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "tool_name": self.tool_name,
            "target": self.target,
            "persistent": self.persistent,
            "failures": self.failures,
            "error_code": self.error_code,
        }


class ToolUnavailableError(RuntimeError):
    """A tool call could not be served (observation-only message)."""


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


def derive_routing(queues: tuple[Queue, ...]) -> dict[str, str] | None:
    """Routing implied by queue descriptions, or None if not one queue per role."""
    routing: dict[str, str] = {}

    for role in ROUTING_ROLES:
        if role == UNRESOLVED_ROLE:
            matches = [q.queue_id for q in queues if "-tier" not in q.description]
        else:
            matches = [q.queue_id for q in queues if f"{role}-tier" in q.description]

        if len(matches) != 1:
            return None

        routing[role] = matches[0]

    return routing


@dataclass(frozen=True)
class WorldSpec:
    """A complete, structurally valid starting world.

    ``generator`` records how a generated world was made (name, version,
    seed, size); it is ``None`` for the Milestone 1 default world. It is part
    of the spec's identity but never of the environment snapshot.

    ``account_sources`` lists only explicit source-of-truth records; an
    account without one has a source equal to its working record.
    ``routing_policy`` is ``None`` when the policy is the one implied by the
    queue descriptions.
    """

    tickets: tuple[Ticket, ...]
    accounts: tuple[Account, ...]
    queues: tuple[Queue, ...]
    directory: tuple[tuple[str, str], ...]
    generator: dict[str, object] | None = None
    account_sources: tuple[SourceRecord, ...] = ()
    account_history: tuple[AccountEvent, ...] = ()
    routing_policy: tuple[tuple[str, str], ...] | None = None
    tool_errors: tuple[ToolErrorRule, ...] = ()
    as_of: str = DEFAULT_TIMESTAMP

    def __post_init__(self) -> None:
        for name, kind in (("tickets", Ticket), ("accounts", Account), ("queues", Queue)):
            values = getattr(self, name)

            if not isinstance(values, tuple) or not values:
                raise ContractError(f"{name} must be a non-empty tuple")

            if not all(isinstance(value, kind) for value in values):
                raise ContractError(f"{name} must hold {kind.__name__} records")

        for name, kind in (
            ("account_sources", SourceRecord),
            ("account_history", AccountEvent),
            ("tool_errors", ToolErrorRule),
        ):
            values = getattr(self, name)

            if not isinstance(values, tuple) or not all(isinstance(v, kind) for v in values):
                raise ContractError(f"{name} must be a tuple of {kind.__name__}")

        if not isinstance(self.directory, tuple):
            raise ContractError("directory must be a tuple of pairs")

        for entry in self.directory:
            if not isinstance(entry, tuple) or len(entry) != 2:
                raise ContractError("directory must be a tuple of pairs")

            _require_id(entry[0], _CUSTOMER_REF, "directory customer_ref")
            _require_id(entry[1], _ACCOUNT_ID, "directory account_id")

        _require_timestamp(self.as_of, "as_of")

        ticket_ids = [ticket.ticket_id for ticket in self.tickets]
        account_ids = [account.account_id for account in self.accounts]
        queue_ids = [queue.queue_id for queue in self.queues]
        refs = [ref for ref, _ in self.directory]
        source_ids = [source.account_id for source in self.account_sources]

        for name, values in (
            ("ticket_id", ticket_ids), ("account_id", account_ids),
            ("queue_id", queue_ids), ("directory customer_ref", refs),
            ("source account_id", source_ids),
        ):
            if len(set(values)) != len(values):
                raise ContractError(f"{name} values must be unique")

        for ticket in self.tickets:
            if ticket.queue_id is not None and ticket.queue_id not in queue_ids:
                raise ContractError("ticket is assigned to an unknown queue")

        for queue in self.queues:
            for ticket_id in queue.ticket_ids:
                if ticket_id not in ticket_ids:
                    raise ContractError("queue holds an unknown ticket")

        for record in self.account_sources + self.account_history:
            if record.account_id not in account_ids:
                raise ContractError("record refers to an unknown account")

        if self.routing_policy is not None:
            if not isinstance(self.routing_policy, tuple):
                raise ContractError("routing_policy must be a tuple of pairs")

            roles = [role for role, _ in self.routing_policy]

            if sorted(roles) != sorted(ROUTING_ROLES):
                raise ContractError("routing_policy must name each routing role once")

            for _, queue_id in self.routing_policy:
                if queue_id not in queue_ids:
                    raise ContractError("routing_policy refers to an unknown queue")

    def clean_violations(self) -> tuple[dict[str, str], ...]:
        """Consistency problems; an empty result means the world is clean."""
        violations: list[dict[str, str]] = []
        directory = dict(self.directory)
        accounts = {account.account_id: account for account in self.accounts}
        merged_events = {
            (event.account_id, dict(event.details).get("customer_ref"))
            for event in self.account_history if event.kind == "merged"
        }

        for ref, account_id in sorted(directory.items()):
            account = accounts.get(account_id)

            if account is None:
                violations.append({"check": "directory_account_exists", "customer_ref": ref})
            elif ref != account.customer_ref and ref not in account.merged_customer_refs:
                violations.append({"check": "directory_matches_owner", "customer_ref": ref})

        for ticket in self.tickets:
            if ticket.customer_ref not in directory:
                violations.append({"check": "ticket_ref_mapped", "ticket_id": ticket.ticket_id})

        for account in self.accounts:
            if directory.get(account.customer_ref) != account.account_id:
                violations.append({"check": "customer_maps_to_own_account", "account_id": account.account_id})

            for ref in account.merged_customer_refs:
                if directory.get(ref) != account.account_id or (account.account_id, ref) not in merged_events:
                    violations.append({"check": "merge_recorded", "account_id": account.account_id})

            if account.tier not in CANONICAL_TIERS:
                violations.append({"check": "tier_canonical", "account_id": account.account_id})

        for source in self.account_sources:
            if source != SourceRecord.of(accounts[source.account_id]):
                violations.append({"check": "source_matches_record", "account_id": source.account_id})

        derived = derive_routing(self.queues)

        if derived is None:
            violations.append({"check": "queue_config_complete"})
        elif self.routing_policy is not None and dict(self.routing_policy) != derived:
            violations.append({"check": "queue_config_matches_policy"})

        if self.tool_errors:
            violations.append({"check": "no_tool_errors_scheduled"})

        if any(violation["check"] not in CLEAN_CHECKS for violation in violations):
            raise ContractError("clean check name is not registered")

        return tuple(violations)

    @property
    def is_clean(self) -> bool:
        return not self.clean_violations()

    def require_clean(self) -> None:
        violations = self.clean_violations()

        if violations:
            checks = sorted({violation["check"] for violation in violations})
            raise ContractError(f"world is not clean: {', '.join(checks)}")

    def canonical_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "record_type": "SupportWorldSpec",
            "schema_version": 1,
            "generator": self.generator,
            "tickets": [ticket.canonical_payload() for ticket in self.tickets],
            "accounts": [account.canonical_payload() for account in self.accounts],
            "queues": [queue.canonical_payload() for queue in self.queues],
            "directory": {ref: account_id for ref, account_id in sorted(self.directory)},
        }
        payload.update(self.extension_payload())
        return payload

    def extension_payload(self) -> dict[str, object]:
        """Non-default extensions only; shared by spec payloads and snapshots."""
        extensions: dict[str, object] = {}

        if self.account_sources:
            extensions["account_sources"] = [
                source.canonical_payload()
                for source in sorted(self.account_sources, key=lambda item: item.account_id)
            ]

        if self.account_history:
            extensions["account_history"] = [
                event.canonical_payload() for event in self.account_history
            ]

        if self.routing_policy is not None:
            extensions["routing_policy"] = dict(sorted(self.routing_policy))

        if self.tool_errors:
            extensions["tool_errors"] = [rule.canonical_payload() for rule in self.tool_errors]

        if self.as_of != DEFAULT_TIMESTAMP:
            extensions["as_of"] = self.as_of

        return extensions

    @property
    def world_sha256(self) -> str:
        return canonical_sha256(self.canonical_payload())

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "WorldSpec":
        if payload.get("record_type") != "SupportWorldSpec" or payload.get("schema_version") != 1:
            raise ContractError("unsupported world spec payload")

        policy = payload.get("routing_policy")

        return cls(
            tickets=tuple(Ticket(**item) for item in payload["tickets"]),
            accounts=tuple(Account.from_payload(item) for item in payload["accounts"]),
            queues=tuple(
                Queue(**{**item, "ticket_ids": tuple(item["ticket_ids"])})
                for item in payload["queues"]
            ),
            directory=tuple(sorted(payload["directory"].items())),
            generator=payload["generator"],
            account_sources=tuple(SourceRecord(**item) for item in payload.get("account_sources", ())),
            account_history=tuple(AccountEvent.from_payload(item) for item in payload.get("account_history", ())),
            routing_policy=None if policy is None else tuple(sorted(policy.items())),
            tool_errors=tuple(ToolErrorRule(**item) for item in payload.get("tool_errors", ())),
            as_of=payload.get("as_of", DEFAULT_TIMESTAMP),
        )


DEFAULT_WORLD = WorldSpec(
    tickets=_SEED_TICKETS,
    accounts=_SEED_ACCOUNTS,
    queues=_SEED_QUEUES,
    directory=tuple(sorted(_seed_directory().items())),
)


class SupportEnvironment:
    """Mutable synthetic stores with an exact, hashable snapshot."""

    def __init__(self, spec: WorldSpec = DEFAULT_WORLD) -> None:
        if not isinstance(spec, WorldSpec):
            raise ContractError("spec must be a WorldSpec")

        self._spec = spec
        self.reset()

    @property
    def spec(self) -> WorldSpec:
        return self._spec

    def reset(self) -> None:
        """Restore every store and the customer directory to the spec."""
        self._tickets = {
            ticket.ticket_id: ticket
            for ticket in self._spec.tickets
        }
        self._accounts = {
            account.account_id: account
            for account in self._spec.accounts
        }
        self._queues = {
            queue.queue_id: queue
            for queue in self._spec.queues
        }
        self._directory = dict(self._spec.directory)
        self._sources = {
            account.account_id: SourceRecord.of(account) for account in self._spec.accounts
        }
        self._sources.update(
            {source.account_id: source for source in self._spec.account_sources}
        )
        self._tool_error_calls = [0] * len(self._spec.tool_errors)

    def fork(self) -> "SupportEnvironment":
        """An independent copy of the current state, for sandboxed execution.

        Includes the tool-error call counters, so a call in the fork sees the
        same remaining scheduled failures it would see here. Changes to either
        environment never affect the other.
        """
        copy = SupportEnvironment(self._spec)
        copy._tickets = dict(self._tickets)
        copy._accounts = dict(self._accounts)
        copy._queues = dict(self._queues)
        copy._directory = dict(self._directory)
        copy._sources = dict(self._sources)
        copy._tool_error_calls = list(self._tool_error_calls)
        return copy

    def tool_error_calls(self) -> tuple[int, ...]:
        """Runtime call counters per tool-error rule (not part of the snapshot)."""
        return tuple(self._tool_error_calls)

    def directory_entry(self, customer_ref: str) -> str | None:
        """The account a reference maps to, or None if it is not in the directory."""
        _require_id(customer_ref, _CUSTOMER_REF, "customer_ref")
        return self._directory.get(customer_ref)

    def map_customer(self, customer_ref: str, account_id: str) -> str | None:
        """Map a reference (existing or not) to an existing account; returns the previous account."""
        _require_id(customer_ref, _CUSTOMER_REF, "customer_ref")
        self.get_account(account_id)
        previous = self._directory.get(customer_ref)
        self._directory[customer_ref] = account_id
        return previous

    def restore_account_from_source(self, account_id: str) -> tuple[Account, Account]:
        """Replace an account's tier, version and timestamp with its source record."""
        before = self.get_account(account_id)
        source = self._sources[account_id]
        after = replace(before, tier=source.tier, version=source.version, updated_at=source.updated_at)
        self._accounts[account_id] = after
        return before, after

    def account_source(self, account_id: str) -> SourceRecord:
        self.get_account(account_id)
        return self._sources[account_id]

    def account_history(self, account_id: str) -> tuple[AccountEvent, ...]:
        self.get_account(account_id)
        return tuple(
            event for event in self._spec.account_history if event.account_id == account_id
        )

    def routing_policy(self) -> dict[str, str] | None:
        """The authoritative routing policy (explicit, or implied by the spec's queues)."""
        if self._spec.routing_policy is not None:
            return dict(self._spec.routing_policy)

        return derive_routing(self._spec.queues)

    def check_tool_errors(self, tool_name: str, target: str | None) -> None:
        """Apply the spec's tool-error schedule to one agent tool call.

        Call counters are runtime bookkeeping, not world state, so they are
        not part of the snapshot; ``reset`` clears them.
        """
        for index, rule in enumerate(self._spec.tool_errors):
            if rule.tool_name != tool_name or rule.target not in (None, target):
                continue

            self._tool_error_calls[index] += 1

            if rule.persistent or self._tool_error_calls[index] <= rule.failures:
                raise ToolUnavailableError(TOOL_ERROR_MESSAGES[rule.error_code])

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
            **self._spec.extension_payload(),
        }

    def state_sha256(self) -> str:
        return canonical_sha256(self.snapshot())


__all__ = [
    "Account",
    "AccountEvent",
    "CANONICAL_TIERS",
    "CLEAN_CHECKS",
    "DEFAULT_TIMESTAMP",
    "DEFAULT_WORLD",
    "HISTORY_KINDS",
    "Queue",
    "ROUTING_ROLES",
    "SourceRecord",
    "SupportEnvironment",
    "TICKET_STATUSES",
    "TIER_VARIANTS",
    "TOOL_ERROR_MESSAGES",
    "Ticket",
    "ToolErrorRule",
    "ToolUnavailableError",
    "UNRESOLVED_ROLE",
    "WorldSpec",
    "derive_routing",
]

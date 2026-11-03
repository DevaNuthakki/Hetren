"""Seeded generator for varied, clean support worlds.

``generate_world(seed)`` returns a validated ``WorldSpec``: random IDs,
synthetic account names, a tier mix with at least one account per tier,
three queues (one per role) with names and descriptions drawn from pools,
and tickets whose text comes from a shared issue pool. Generated worlds are
clean: every customer reference maps to the account that names it. Faults are
applied later by the injectors.

Determinism: one ``random.Random(seed)`` drives every choice, in a fixed
order. ``GENERATOR_VERSION`` changes whenever that order or a pool changes,
and every spec records the generator name, version, seed and size.

Account history is independent of any fault: every account gets a random
version and ``updated_at``, and about ``RECENT_CHANGE_PROBABILITY`` of them
were changed recently (within ``RECENT_DAYS`` of the world's fixed
``as_of``), with a matching ``tier_changed`` event. Faults and look-alikes
are layered on top, so timestamps, versions and recent changes carry no
information about the case kind.

Pools hold only synthetic text. Queue descriptions always say
``<tier>-tier`` so the routing rule stays expressible; the triage queue's
description never names a tier.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import random

from packages.contracts import ContractError

from environments.support.fixtures import (
    Account,
    AccountEvent,
    Queue,
    Ticket,
    WorldSpec,
)


GENERATOR_NAME = "support-world-generator"
GENERATOR_VERSION = 3

WORLD_AS_OF = "2026-06-01T00:00:00Z"
HISTORY_START = "2025-01-01T00:00:00Z"
RECENT_DAYS = 30
RECENT_MARGIN_DAYS = 3
RECENT_CHANGE_PROBABILITY = 0.3
TRUE_CLAIM_PROBABILITY = 0.25

_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def parse_time(value: str) -> datetime:
    return datetime.strptime(value, _TIME_FORMAT).replace(tzinfo=timezone.utc)


def format_time(value: datetime) -> str:
    return value.strftime(_TIME_FORMAT)


def random_time(rng: random.Random, start: str, end: str) -> str:
    """A whole-hour time strictly after ``start`` and strictly before ``end``."""
    low, high = parse_time(start), parse_time(end)
    hours = int((high - low).total_seconds() // 3600)

    if hours < 2:
        raise ContractError("time window is too small")

    return format_time(low + timedelta(hours=rng.randrange(1, hours)))

TIERS = ("enterprise", "standard")
TIER_WEIGHTS = (0.4, 0.6)
PRIORITIES = ("low", "normal", "high")
REGIONS = ("eu", "us", "apac", "latam")

_NAME_FIRST = (
    "Amber", "Birch", "Cobalt", "Dune", "Ember", "Fjord", "Granite", "Harbor",
    "Indigo", "Juniper", "Kestrel", "Lumen", "Maple", "Nimbus", "Onyx", "Pine",
    "Quartz", "Rowan", "Saffron", "Tidal", "Umber", "Vale", "Willow", "Zephyr",
)
_NAME_SECOND = (
    "Analytics", "Bakery", "Cargo", "Designs", "Energy", "Foods", "Goods",
    "Health", "Imports", "Labs", "Media", "Networks", "Outfitters", "Partners",
    "Robotics", "Studios", "Textiles", "Ventures", "Works",
)
_NAME_SUFFIX = ("Ltd", "Inc", "Co", "LLC", "GmbH", "Sample Group", "Fixture Ltd")

_QUEUE_IDS = {
    "priority": ("Q-PREMIUM", "Q-ENTERPRISE", "Q-GOLD", "Q-VIP"),
    "general": ("Q-STANDARD", "Q-BASIC", "Q-COMMON", "Q-MAIN"),
    "triage": ("Q-TRIAGE", "Q-MANUAL", "Q-REVIEW", "Q-HOLD"),
}
_QUEUE_NAMES = {
    "priority": ("Priority support", "Premium desk", "Enterprise desk"),
    "general": ("General support", "Standard desk", "Main desk"),
    "triage": ("Manual triage", "Account review", "Holding queue"),
}
_TIER_DESCRIPTIONS = (
    "Tickets from {tier}-tier accounts.",
    "Handles requests from {tier}-tier customers.",
    "Support queue for {tier}-tier accounts.",
)
_TRIAGE_DESCRIPTIONS = (
    "Tickets whose account cannot be determined.",
    "Requests that need a manual account review.",
    "Tickets without a confirmed account.",
)
_ROLE_TIER = {"priority": "enterprise", "general": "standard"}

_ISSUES = (
    ("Invoice export fails", "Monthly invoice export returns an empty file."),
    ("Password reset email missing", "Reset emails are not arriving for one user."),
    ("API rate limit questions", "Asking whether the API rate limit can be raised."),
    ("Dashboard loads slowly", "The usage dashboard takes over a minute to load."),
    ("SSO login loop", "Users are redirected back to the login page after SSO."),
    ("Webhook deliveries delayed", "Webhook events arrive several minutes late."),
    ("CSV import rejects file", "The CSV import reports an invalid header row."),
    ("Seat count incorrect", "The admin page shows fewer seats than purchased."),
    ("Report totals mismatch", "Weekly report totals differ from the dashboard."),
    ("Mobile app crashes on launch", "The app closes immediately after opening."),
    ("Two-factor codes rejected", "Valid authenticator codes are not accepted."),
    ("Data retention question", "Asking how long deleted records are kept."),
    ("Search returns no results", "Searching by order number finds nothing."),
    ("Email notifications duplicated", "Each alert email is sent twice."),
    ("Timezone shown incorrectly", "Timestamps display in the wrong timezone."),
    ("Cannot remove a user", "Removing a former employee returns an error."),
)

# Customer claims about their own tier. Every generated world puts a true
# claim (the account's real tier) on about TRUE_CLAIM_PROBABILITY of its
# tickets, so a claim by itself never signals a problem; only a false claim,
# injected by the misleading-text fault, does.
CLAIM_TEXTS = (
    "We are on the {tier} plan, please handle this accordingly.",
    "As a {tier}-tier customer we expect a fast response.",
    "Our account is {tier}; please route this to the right team.",
)

def strip_claims(body: str) -> str:
    """The ticket body without any appended tier claim."""
    for template in CLAIM_TEXTS:
        prefix = template.split("{tier}")[0]
        position = body.find(" " + prefix)

        if position >= 0:
            body = body[:position]

    return body


MAX_ACCOUNTS = 60
MAX_TICKETS = 200


def _unique_numbers(rng: random.Random, count: int) -> list[int]:
    return rng.sample(range(1000, 10000), count)


def _account_names(rng: random.Random, count: int) -> list[str]:
    names: list[str] = []

    while len(names) < count:
        name = f"{rng.choice(_NAME_FIRST)} {rng.choice(_NAME_SECOND)} {rng.choice(_NAME_SUFFIX)}"

        if name not in names:
            names.append(name)

    return names


def generate_world(seed: int, *, accounts: int = 8, tickets: int = 12) -> WorldSpec:
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ContractError("seed must be a non-negative integer")

    if not 2 <= accounts <= MAX_ACCOUNTS:
        raise ContractError(f"accounts must be between 2 and {MAX_ACCOUNTS}")

    if not 1 <= tickets <= MAX_TICKETS:
        raise ContractError(f"tickets must be between 1 and {MAX_TICKETS}")

    rng = random.Random(seed)

    account_numbers = _unique_numbers(rng, accounts)
    customer_numbers = _unique_numbers(rng, accounts)
    ticket_numbers = _unique_numbers(rng, tickets)

    tiers = list(TIERS) + rng.choices(TIERS, weights=TIER_WEIGHTS, k=accounts - len(TIERS))
    rng.shuffle(tiers)
    names = _account_names(rng, accounts)

    account_records = tuple(
        Account(
            account_id=f"A-{account_numbers[index]}",
            customer_ref=f"C-{customer_numbers[index]}",
            display_name=names[index],
            tier=tiers[index],
            region=rng.choice(REGIONS),
        )
        for index in range(accounts)
    )

    queue_records = []

    for role in ("priority", "general", "triage"):
        description = (
            rng.choice(_TRIAGE_DESCRIPTIONS)
            if role == "triage"
            else rng.choice(_TIER_DESCRIPTIONS).format(tier=_ROLE_TIER[role])
        )
        queue_records.append(
            Queue(
                queue_id=rng.choice(_QUEUE_IDS[role]),
                name=rng.choice(_QUEUE_NAMES[role]),
                description=description,
                ticket_ids=(),
            )
        )

    owners = [account.customer_ref for account in account_records]
    rng.shuffle(owners)
    ticket_refs = owners[:tickets] + rng.choices(
        [account.customer_ref for account in account_records],
        k=max(0, tickets - len(owners)),
    )

    ticket_records = []
    tier_of = {account.customer_ref: account.tier for account in account_records}

    for index in range(tickets):
        subject, body = rng.choice(_ISSUES)

        if rng.random() < TRUE_CLAIM_PROBABILITY:
            body = f"{body} {rng.choice(CLAIM_TEXTS).format(tier=tier_of[ticket_refs[index]])}"

        ticket_records.append(
            Ticket(
                ticket_id=f"T-{ticket_numbers[index]}",
                customer_ref=ticket_refs[index],
                subject=subject,
                body=body,
                priority=rng.choice(PRIORITIES),
                queue_id=None,
                status="open",
            )
        )

    as_of = parse_time(WORLD_AS_OF)
    recent_start = format_time(as_of - timedelta(days=RECENT_DAYS))
    # Recent changes stop a few days before as_of, so a fault or look-alike
    # layered on top always has room for a later change.
    recent_end = format_time(as_of - timedelta(days=RECENT_MARGIN_DAYS))
    old_end = format_time(as_of - timedelta(days=2 * RECENT_DAYS))
    dated_accounts = []
    history = []

    for account in account_records:
        version = rng.randint(1, 4)

        if rng.random() < RECENT_CHANGE_PROBABILITY:
            updated_at = random_time(rng, recent_start, recent_end)
            version += 1
            history.append(
                AccountEvent(account.account_id, "tier_changed", updated_at, (("tier", account.tier),))
            )
        else:
            updated_at = random_time(rng, HISTORY_START, old_end)

        dated_accounts.append(
            Account(
                account.account_id, account.customer_ref, account.display_name,
                account.tier, account.region, version, updated_at,
            )
        )

    account_records = tuple(dated_accounts)

    spec = WorldSpec(
        tickets=tuple(ticket_records),
        accounts=account_records,
        queues=tuple(queue_records),
        directory=tuple(sorted((a.customer_ref, a.account_id) for a in account_records)),
        generator={
            "name": GENERATOR_NAME,
            "version": GENERATOR_VERSION,
            "seed": seed,
            "accounts": accounts,
            "tickets": tickets,
        },
        account_history=tuple(history),
        as_of=WORLD_AS_OF,
    )
    spec.require_clean()
    return spec


__all__ = [
    "CLAIM_TEXTS",
    "RECENT_CHANGE_PROBABILITY",
    "TRUE_CLAIM_PROBABILITY",
    "RECENT_DAYS",
    "RECENT_MARGIN_DAYS",
    "WORLD_AS_OF",
    "format_time",
    "parse_time",
    "random_time",
    "strip_claims",
    "GENERATOR_NAME",
    "GENERATOR_VERSION",
    "MAX_ACCOUNTS",
    "MAX_TICKETS",
    "PRIORITIES",
    "REGIONS",
    "TIERS",
    "generate_world",
]

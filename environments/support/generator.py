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

Pools hold only synthetic text. Queue descriptions always say
``<tier>-tier`` so the routing rule stays expressible; the triage queue's
description never names a tier.
"""

from __future__ import annotations

import random

from packages.contracts import ContractError

from environments.support.fixtures import (
    Account,
    Queue,
    Ticket,
    WorldSpec,
)


GENERATOR_NAME = "support-world-generator"
GENERATOR_VERSION = 1

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

    for index in range(tickets):
        subject, body = rng.choice(_ISSUES)
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

    return WorldSpec(
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
    )


__all__ = [
    "GENERATOR_NAME",
    "GENERATOR_VERSION",
    "MAX_ACCOUNTS",
    "MAX_TICKETS",
    "PRIORITIES",
    "REGIONS",
    "TIERS",
    "generate_world",
]

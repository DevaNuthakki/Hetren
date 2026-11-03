"""Compound faults (dataset v3, tier 2): two injections on one target ticket.

Both injectors run on the same clean world with the same target ticket, and
their changes are merged three ways against that clean world, field by
field: entities (tickets, accounts, queues) by ID, the directory by
reference, source records by account, history and tool-error rules as
additions, and the routing policy as a whole. Two different changes to the
same field are a conflict, and the pair does not apply to that world
(``ContractError``).

The merged world's correct outcome is recomputed rather than taken from
either truth (``expected_outcome``): the true owner comes from the clean
directory, a deleted owner means the policy's ``unresolved`` queue, and the
true tier is the owner's source record when one exists. On every single
injection this reproduces the injector's own truth (tested).

Compound truths use ``case_kind = "compound"`` and a variant that names both
components, ``"<kind>.<variant>+<kind>.<variant>"`` in ``CASE_KINDS`` order.
"""

from __future__ import annotations

from dataclasses import fields, replace
import random

from environments.support.fixtures import WorldSpec
from packages.contracts import ContractError
from packages.support_evaluator.cases import (
    CASE_KINDS,
    COMPOUND_KIND,
    FAMILIES,
    LOOKALIKES,
    CaseTruth,
    compound_variant,
    parse_compound,
)
from packages.support_evaluator.injectors import INJECTORS, InjectedCase, _policy


_ENTITY_KEYS = {"tickets": "ticket_id", "accounts": "account_id", "queues": "queue_id"}


def _merge_records(clean, a, b, key, name):
    """Field-level three-way merge of records keyed by ``key`` (deletions allowed)."""
    base = {getattr(r, key): r for r in clean}
    left = {getattr(r, key): r for r in a}
    right = {getattr(r, key): r for r in b}
    merged = []

    for record_id in dict.fromkeys(list(base) + list(left) + list(right)):
        original, x, y = base.get(record_id), left.get(record_id), right.get(record_id)

        if original is None:
            if x is not None and y is not None and x != y:
                raise ContractError(f"conflicting new {name} {record_id}")
            merged.append(x or y)
            continue

        if x is None or y is None:
            if (x is None and y not in (None, original)) or (y is None and x not in (None, original)):
                raise ContractError(f"{name} {record_id} deleted and changed")
            continue

        changes = {}

        for field in fields(original):
            before, va, vb = (getattr(r, field.name) for r in (original, x, y))

            if va != before and vb != before and va != vb:
                raise ContractError(f"conflicting change to {name} {record_id}.{field.name}")

            changes[field.name] = va if va != before else vb

        merged.append(replace(original, **changes))

    return tuple(merged)


def _merge_mapping(clean, a, b, name):
    base, left, right = dict(clean), dict(a), dict(b)
    merged = {}

    for key in dict.fromkeys(list(base) + list(left) + list(right)):
        original, x, y = base.get(key), left.get(key), right.get(key)
        in_x, in_y = key in left, key in right

        if key in base:
            x_changed = (not in_x) or x != original
            y_changed = (not in_y) or y != original

            if x_changed and y_changed and (in_x, x) != (in_y, y):
                raise ContractError(f"conflicting change to {name} {key}")

            keep, value = (in_x, x) if x_changed else (in_y, y)
        else:
            if in_x and in_y and x != y:
                raise ContractError(f"conflicting new {name} {key}")

            keep, value = (True, x if in_x else y)

        if keep:
            merged[key] = value

    return merged


def _added(clean, spec):
    return tuple(item for item in spec if item not in clean)


def merge_specs(clean: WorldSpec, a: WorldSpec, b: WorldSpec) -> WorldSpec:
    changes = {
        name: _merge_records(getattr(clean, name), getattr(a, name), getattr(b, name), key, name)
        for name, key in _ENTITY_KEYS.items()
    }
    directory = _merge_mapping(clean.directory, a.directory, b.directory, "directory")
    sources = _merge_records(clean.account_sources, a.account_sources, b.account_sources, "account_id", "source")
    policies = {p for p in (a.routing_policy, b.routing_policy) if p != clean.routing_policy}

    if len(policies) > 1:
        raise ContractError("conflicting routing policies")

    accounts = {account.account_id for account in changes["accounts"]}
    history = clean.account_history + _added(clean.account_history, a.account_history) + tuple(
        event for event in _added(clean.account_history, b.account_history)
        if event not in a.account_history
    )

    return replace(
        clean,
        **changes,
        directory=tuple(sorted(directory.items())),
        account_sources=tuple(s for s in sources if s.account_id in accounts),
        account_history=tuple(e for e in history if e.account_id in accounts),
        routing_policy=next(iter(policies), clean.routing_policy),
        tool_errors=clean.tool_errors + _added(clean.tool_errors, a.tool_errors) + tuple(
            rule for rule in _added(clean.tool_errors, b.tool_errors) if rule not in a.tool_errors
        ),
    )


def expected_outcome(clean: WorldSpec, spec: WorldSpec, ticket_id: str) -> tuple[str, str | None]:
    """Correct queue and account for ``ticket_id`` in ``spec`` (a fault world built from ``clean``)."""
    ticket = next(t for t in clean.tickets if t.ticket_id == ticket_id)
    owner = dict(clean.directory)[ticket.customer_ref]
    policy = _policy(spec)
    account = next((a for a in spec.accounts if a.account_id == owner), None)

    if account is None:
        return policy["unresolved"], None

    source = next((s for s in spec.account_sources if s.account_id == owner), None)
    clean_tier = next(a.tier for a in clean.accounts if a.account_id == owner)
    return policy[source.tier if source is not None else clean_tier], owner


def affected(clean: WorldSpec, spec: WorldSpec) -> tuple[set[str], set[str], set[str]]:
    """References, accounts and tickets that ``spec`` changes relative to ``clean``."""
    base_dir, new_dir = dict(clean.directory), dict(spec.directory)
    refs = {ref for ref in set(base_dir) | set(new_dir) if base_dir.get(ref) != new_dir.get(ref)}
    accounts = {account for ref in refs for account in (base_dir.get(ref), new_dir.get(ref)) if account}
    base_accounts = {a.account_id: a for a in clean.accounts}
    accounts |= {a.account_id for a in spec.accounts if base_accounts.get(a.account_id) != a}
    accounts |= set(base_accounts) - {a.account_id for a in spec.accounts}
    accounts |= {s.account_id for s in _added(clean.account_sources, spec.account_sources)}
    accounts |= {e.account_id for e in _added(clean.account_history, spec.account_history)}
    base_tickets = {t.ticket_id: t for t in clean.tickets}
    tickets = {t.ticket_id for t in spec.tickets if base_tickets.get(t.ticket_id) != t}

    for rule in _added(clean.tool_errors, spec.tool_errors):
        (accounts if rule.target and rule.target.startswith("A-") else tickets).add(rule.target)

    refs |= {base_accounts[a].customer_ref for a in accounts if a in base_accounts}
    return refs, accounts, tickets


def regression_tickets(clean: WorldSpec, spec: WorldSpec, rng: random.Random, target: str, count: int = 2) -> tuple[str, ...]:
    refs, accounts, tickets = affected(clean, spec)
    directory = dict(spec.directory)
    candidates = sorted(
        t.ticket_id for t in spec.tickets
        if t.ticket_id != target and t.ticket_id not in tickets
        and t.customer_ref not in refs and directory.get(t.customer_ref) not in accounts
    )
    return tuple(sorted(rng.sample(candidates, min(count, len(candidates)))))


def inject_compound(world: WorldSpec, rng: random.Random, variant: str, forced_ticket: str | None = None) -> InjectedCase:
    (kind_a, variant_a), (kind_b, variant_b) = parse_compound(variant)
    a = INJECTORS[kind_a][0](world, rng, variant_a, forced_ticket)
    b = INJECTORS[kind_b][0](world, rng, variant_b, a.truth.target_ticket_id)
    spec = merge_specs(world, a.spec, b.spec)
    ticket_id = a.truth.target_ticket_id
    queue, account = expected_outcome(world, spec, ticket_id)

    return InjectedCase(spec, CaseTruth(
        case_kind=COMPOUND_KIND,
        case_variant=compound_variant((kind_a, variant_a), (kind_b, variant_b)),
        target_ticket_id=ticket_id,
        expected_queue_id=queue,
        expected_account_id=account,
        remedy_if_wrong=a.truth.remedy_if_wrong,
        remedy_if_wrong_arguments=a.truth.remedy_if_wrong_arguments + b.truth.remedy_if_wrong_arguments,
        world_changes=a.truth.world_changes + b.truth.world_changes,
        regression_ticket_ids=regression_tickets(world, spec, rng, ticket_id),
    ))


def compound_variants(kinds: tuple[str, ...]) -> tuple[str, ...]:
    """Every unordered pair of distinct kinds, crossed with their variants."""
    ordered = [k for k in CASE_KINDS if k in kinds]
    return tuple(
        compound_variant((a, va), (b, vb))
        for i, a in enumerate(ordered) for b in ordered[i + 1:]
        for va in INJECTORS[a][1] for vb in INJECTORS[b][1]
    )


# Dataset v3 pairs: every pair of families and look-alikes except two look-alikes.
TIER2_COMPOUND_VARIANTS = tuple(
    variant for variant in compound_variants(tuple(FAMILIES) + LOOKALIKES)
    if not {kind for kind, _ in parse_compound(variant)} <= set(LOOKALIKES)
)


__all__ = [
    "TIER2_COMPOUND_VARIANTS",
    "affected",
    "compound_variants",
    "expected_outcome",
    "inject_compound",
    "merge_specs",
    "regression_tickets",
]

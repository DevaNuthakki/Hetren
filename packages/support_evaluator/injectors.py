"""Fault injectors and healthy look-alikes for Milestone 2 cases.

Each injector takes a clean world and an ``random.Random``, chooses its own
targets, and returns the changed world plus an evaluator-side ``CaseTruth``.
Injected worlds are structurally valid; fault worlds are not clean, and
look-alikes may or may not be. Only the evaluator side imports this module.

Behaviour-dependent kinds (F3, F4, F7 and every look-alike) change the world
in a way that only some agents mishandle; whether a given run went wrong is
decided from its outcome, not here. ``remedy_if_wrong`` is therefore never
``no_intervention``: a look-alike run that went wrong (for example an agent
that stopped on a legitimate merge) needs its outcome fixed.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
import random

from environments.support.fixtures import (
    TIER_VARIANTS,
    Account,
    AccountEvent,
    SourceRecord,
    ToolErrorRule,
    WorldSpec,
    derive_routing,
)
from datetime import timedelta

from environments.support.generator import (
    CLAIM_TEXTS,
    RECENT_DAYS,
    RECENT_MARGIN_DAYS,
    format_time,
    parse_time,
    random_time,
    strip_claims,
)
from packages.contracts import ContractError
from packages.support_evaluator.cases import CASE_KINDS, COMPOUND_KIND, CaseTruth


@dataclass(frozen=True)
class InjectedCase:
    spec: WorldSpec
    truth: CaseTruth


def _policy(spec: WorldSpec) -> dict[str, str]:
    if spec.routing_policy is not None:
        return dict(spec.routing_policy)

    policy = derive_routing(spec.queues)

    if policy is None:
        raise ContractError("world has no complete routing policy")

    return policy


def _other_tier(tier: str) -> str:
    return "standard" if tier == "enterprise" else "enterprise"


def _tickets_of(spec: WorldSpec, customer_ref: str) -> list:
    return [ticket for ticket in spec.tickets if ticket.customer_ref == customer_ref]


def _pick_account(spec: WorldSpec, rng: random.Random, candidates=None) -> Account:
    pool = [
        account for account in (candidates or spec.accounts)
        if _tickets_of(spec, account.customer_ref)
    ]

    if not pool:
        raise ContractError("no account with tickets to target")

    return rng.choice(pool)


def _pick_ticket(spec: WorldSpec, rng: random.Random, account: Account):
    return rng.choice(_tickets_of(spec, account.customer_ref))


def _pick_target(spec: WorldSpec, rng: random.Random, forced_ticket: str | None):
    """Target account and ticket; ``forced_ticket`` pins the ticket (no random draws)."""
    if forced_ticket is None:
        account = _pick_account(spec, rng)
        return account, _pick_ticket(spec, rng, account)

    ticket = next((t for t in spec.tickets if t.ticket_id == forced_ticket), None)

    if ticket is None:
        raise ContractError("forced ticket is not in the world")

    owner_id = dict(spec.directory)[ticket.customer_ref]
    return next(a for a in spec.accounts if a.account_id == owner_id), ticket


def _with_account(spec: WorldSpec, account_id: str, **changes) -> WorldSpec:
    return replace(
        spec,
        accounts=tuple(
            replace(account, **changes) if account.account_id == account_id else account
            for account in spec.accounts
        ),
    )


def _with_directory(spec: WorldSpec, directory: dict[str, str]) -> WorldSpec:
    return replace(spec, directory=tuple(sorted(directory.items())))


def _unused_ref(spec: WorldSpec, rng: random.Random) -> str:
    used = {ref for ref, _ in spec.directory} | {
        ref for account in spec.accounts
        for ref in (account.customer_ref, *account.merged_customer_refs)
    }

    while True:
        ref = f"C-{rng.randrange(1000, 10000)}"

        if ref not in used:
            return ref


def _change_time(rng: random.Random, world: WorldSpec, after: str) -> str:
    """A change time after ``after`` (the account's own last update) and before ``as_of``."""
    return random_time(rng, after, world.as_of)


def _regression(
    spec: WorldSpec,
    rng: random.Random,
    *,
    target_ticket_id: str,
    affected_refs: set[str],
    affected_accounts: set[str],
    count: int = 2,
) -> tuple[str, ...]:
    directory = dict(spec.directory)
    candidates = sorted(
        ticket.ticket_id for ticket in spec.tickets
        if ticket.ticket_id != target_ticket_id
        and ticket.customer_ref not in affected_refs
        and directory.get(ticket.customer_ref) not in affected_accounts
    )
    return tuple(sorted(rng.sample(candidates, min(count, len(candidates)))))


def _truth(**fields) -> CaseTruth:
    fields.setdefault("remedy_if_wrong_arguments", ())
    return CaseTruth(**fields)


# F1


def mapping_swap(world: WorldSpec, rng: random.Random, variant: str, forced_ticket: str | None = None) -> InjectedCase:
    policy = _policy(world)
    target, ticket = _pick_target(world, rng, forced_ticket)
    other = rng.choice([a for a in world.accounts if a.tier != target.tier])
    directory = dict(world.directory)

    if variant == "swap":
        moves = {target.customer_ref: other.account_id, other.customer_ref: target.account_id}
        owners = [target, other]
    elif variant == "redirect":
        moves = {target.customer_ref: other.account_id}
        owners = [target]
    elif variant == "nway":
        third = rng.choice([a for a in world.accounts if a.account_id not in (target.account_id, other.account_id)])
        moves = {
            target.customer_ref: other.account_id,
            other.customer_ref: third.account_id,
            third.customer_ref: target.account_id,
        }
        owners = [target, other, third]
    else:
        raise ContractError("unknown variant")

    spec = _with_directory(world, {**directory, **moves})

    return InjectedCase(spec, _truth(
        case_kind="mapping_swap", case_variant=variant,
        target_ticket_id=ticket.ticket_id,
        expected_queue_id=policy[target.tier], expected_account_id=target.account_id,
        remedy_if_wrong="set_mapping",
        remedy_if_wrong_arguments=tuple(
            {"customer_ref": owner.customer_ref, "account_id": owner.account_id} for owner in owners
        ),
        world_changes=tuple(
            {"entity": "directory", "customer_ref": ref, "before": directory[ref], "after": account_id}
            for ref, account_id in sorted(moves.items())
        ),
        regression_ticket_ids=_regression(
            spec, rng, target_ticket_id=ticket.ticket_id,
            affected_refs=set(moves), affected_accounts=set(moves.values()),
        ),
    ))


# F2


def stale_account_record(world: WorldSpec, rng: random.Random, variant: str, forced_ticket: str | None = None) -> InjectedCase:
    policy = _policy(world)
    target, ticket = _pick_target(world, rng, forced_ticket)
    new_tier = _other_tier(target.tier)
    changed_at = _change_time(rng, world, target.updated_at)
    spec = replace(
        world,
        account_sources=world.account_sources + (
            SourceRecord(target.account_id, new_tier, target.version + 1, changed_at),
        ),
        account_history=world.account_history + (
            AccountEvent(target.account_id, "tier_changed", changed_at, (("tier", new_tier),)),
        ),
    )

    return InjectedCase(spec, _truth(
        case_kind="stale_account_record", case_variant=variant,
        target_ticket_id=ticket.ticket_id,
        expected_queue_id=policy[new_tier], expected_account_id=target.account_id,
        remedy_if_wrong="restore_from_source",
        remedy_if_wrong_arguments=({"entity": "account", "id": target.account_id},),
        world_changes=({
            "entity": "account_source", "account_id": target.account_id,
            "field": "tier", "working": target.tier, "source": new_tier,
        },),
        regression_ticket_ids=_regression(
            spec, rng, target_ticket_id=ticket.ticket_id,
            affected_refs={target.customer_ref}, affected_accounts={target.account_id},
        ),
    ))


# F3 and the transient look-alike


def _error_case(world, rng, *, kind, variant, persistent, remedy_if_wrong, forced_ticket=None):
    policy = _policy(world)
    target, ticket = _pick_target(world, rng, forced_ticket)
    # Only read tools fail, so a read-only retry probe can tell transient
    # from persistent errors without changing anything.
    tool_name = "lookup_account" if kind == "transient_error_retried" else rng.choice(
        ("read_ticket", "lookup_account")
    )
    rule_target = target.account_id if tool_name == "lookup_account" else ticket.ticket_id
    rule = ToolErrorRule(
        tool_name, rule_target, persistent, 0 if persistent else 1,
        rng.choice(("service_unavailable", "timeout")),
    )
    spec = replace(world, tool_errors=world.tool_errors + (rule,))

    return InjectedCase(spec, _truth(
        case_kind=kind, case_variant=variant,
        target_ticket_id=ticket.ticket_id,
        expected_queue_id=policy[target.tier], expected_account_id=target.account_id,
        remedy_if_wrong=remedy_if_wrong,
        world_changes=({"entity": "tool_errors", **rule.canonical_payload()},),
        regression_ticket_ids=_regression(
            spec, rng, target_ticket_id=ticket.ticket_id,
            affected_refs={target.customer_ref}, affected_accounts={target.account_id},
        ),
    ))


def mishandled_tool_error(world: WorldSpec, rng: random.Random, variant: str, forced_ticket: str | None = None) -> InjectedCase:
    if variant not in ("transient", "persistent"):
        raise ContractError("unknown variant")

    persistent = variant == "persistent"
    return _error_case(
        world, rng, kind="mishandled_tool_error", variant=variant,
        persistent=persistent, remedy_if_wrong="abstain" if persistent else "rerun",
        forced_ticket=forced_ticket,
    )


def transient_error_retried(world: WorldSpec, rng: random.Random, variant: str, forced_ticket: str | None = None) -> InjectedCase:
    return _error_case(
        world, rng, kind="transient_error_retried", variant=variant,
        persistent=False, remedy_if_wrong="rerun",
        forced_ticket=forced_ticket,
    )


# F4


def misleading_ticket_text(world: WorldSpec, rng: random.Random, variant: str, forced_ticket: str | None = None) -> InjectedCase:
    if variant not in ("claim_false", "claim_true"):
        raise ContractError("unknown variant")

    policy = _policy(world)
    target, ticket = _pick_target(world, rng, forced_ticket)
    claimed = target.tier if variant == "claim_true" else _other_tier(target.tier)
    claim = rng.choice(CLAIM_TEXTS).format(tier=claimed)
    spec = replace(
        world,
        tickets=tuple(
            replace(t, body=f"{strip_claims(t.body)} {claim}") if t.ticket_id == ticket.ticket_id else t
            for t in world.tickets
        ),
    )
    expected = policy[target.tier]

    return InjectedCase(spec, _truth(
        case_kind="misleading_ticket_text", case_variant=variant,
        target_ticket_id=ticket.ticket_id,
        expected_queue_id=expected, expected_account_id=target.account_id,
        remedy_if_wrong="reroute",
        remedy_if_wrong_arguments=({"ticket_id": ticket.ticket_id, "queue_id": expected},),
        world_changes=({
            "entity": "ticket_text", "ticket_id": ticket.ticket_id,
            "claimed_tier": claimed, "true_tier": target.tier,
        },),
        regression_ticket_ids=_regression(
            spec, rng, target_ticket_id=ticket.ticket_id,
            affected_refs=set(), affected_accounts=set(),
        ),
    ))


# F5


def missing_account(world: WorldSpec, rng: random.Random, variant: str, forced_ticket: str | None = None) -> InjectedCase:
    policy = _policy(world)
    target, ticket = _pick_target(world, rng, forced_ticket)
    directory = dict(world.directory)

    if variant == "unmapped_ref":
        del directory[target.customer_ref]
        spec = _with_directory(world, directory)
        truth_fields = dict(
            expected_queue_id=policy[target.tier], expected_account_id=target.account_id,
            remedy_if_wrong="set_mapping",
            remedy_if_wrong_arguments=({"customer_ref": target.customer_ref, "account_id": target.account_id},),
            world_changes=({"entity": "directory", "customer_ref": target.customer_ref,
                            "before": target.account_id, "after": None},),
        )
    elif variant == "deleted_account":
        if len(world.accounts) < 3:
            raise ContractError("world is too small to delete an account")

        spec = replace(
            world,
            accounts=tuple(a for a in world.accounts if a.account_id != target.account_id),
            account_sources=tuple(s for s in world.account_sources if s.account_id != target.account_id),
            account_history=tuple(e for e in world.account_history if e.account_id != target.account_id),
        )
        truth_fields = dict(
            expected_queue_id=policy["unresolved"], expected_account_id=None,
            remedy_if_wrong="reroute",
            remedy_if_wrong_arguments=({"ticket_id": ticket.ticket_id, "queue_id": policy["unresolved"]},),
            world_changes=({"entity": "account", "account_id": target.account_id, "after": None},),
        )
    else:
        raise ContractError("unknown variant")

    return InjectedCase(spec, _truth(
        case_kind="missing_account", case_variant=variant,
        target_ticket_id=ticket.ticket_id,
        regression_ticket_ids=_regression(
            spec, rng, target_ticket_id=ticket.ticket_id,
            affected_refs={target.customer_ref}, affected_accounts={target.account_id},
        ),
        **truth_fields,
    ))


# F6 (held out)


def queue_misconfiguration(world: WorldSpec, rng: random.Random, variant: str, forced_ticket: str | None = None) -> InjectedCase:
    policy = _policy(world)
    target, ticket = _pick_target(world, rng, forced_ticket)
    priority, general = policy["enterprise"], policy["standard"]
    descriptions = {q.queue_id: q.description for q in world.queues}
    swapped = {priority: descriptions[general], general: descriptions[priority]}
    spec = replace(
        world,
        queues=tuple(
            replace(q, description=swapped.get(q.queue_id, q.description)) for q in world.queues
        ),
        routing_policy=tuple(sorted(policy.items())),
    )

    return InjectedCase(spec, _truth(
        case_kind="queue_misconfiguration", case_variant=variant,
        target_ticket_id=ticket.ticket_id,
        expected_queue_id=policy[target.tier], expected_account_id=target.account_id,
        remedy_if_wrong="abstain",
        world_changes=tuple(
            {"entity": "queue_config", "queue_id": queue_id,
             "before": descriptions[queue_id], "after": description}
            for queue_id, description in sorted(swapped.items())
        ),
        regression_ticket_ids=(),
    ))


# F7 (held out)


_DRIFT_INDEX = {"case": 0, "abbreviation": 2, "whitespace": 3}


def tier_format_drift(world: WorldSpec, rng: random.Random, variant: str, forced_ticket: str | None = None) -> InjectedCase:
    if variant not in _DRIFT_INDEX:
        raise ContractError("unknown variant")

    policy = _policy(world)
    target, ticket = _pick_target(world, rng, forced_ticket)
    drifted = TIER_VARIANTS[target.tier][_DRIFT_INDEX[variant]]
    spec = replace(
        _with_account(world, target.account_id, tier=drifted),
        account_sources=world.account_sources + (SourceRecord.of(target),),
    )

    return InjectedCase(spec, _truth(
        case_kind="tier_format_drift", case_variant=variant,
        target_ticket_id=ticket.ticket_id,
        expected_queue_id=policy[target.tier], expected_account_id=target.account_id,
        remedy_if_wrong="restore_from_source",
        remedy_if_wrong_arguments=({"entity": "account", "id": target.account_id},),
        world_changes=({
            "entity": "account", "account_id": target.account_id,
            "field": "tier", "before": target.tier, "after": drifted,
        },),
        regression_ticket_ids=_regression(
            spec, rng, target_ticket_id=ticket.ticket_id,
            affected_refs={target.customer_ref}, affected_accounts={target.account_id},
        ),
    ))


# Look-alikes


def merged_account(world: WorldSpec, rng: random.Random, variant: str, forced_ticket: str | None = None) -> InjectedCase:
    policy = _policy(world)
    target, ticket = _pick_target(world, rng, forced_ticket)
    old_ref = _unused_ref(world, rng)
    merged_at = _change_time(rng, world, target.updated_at)
    spec = replace(
        _with_directory(
            _with_account(
                world, target.account_id,
                merged_customer_refs=target.merged_customer_refs + (old_ref,),
            ),
            {**dict(world.directory), old_ref: target.account_id},
        ),
        tickets=tuple(
            replace(t, customer_ref=old_ref) if t.ticket_id == ticket.ticket_id else t
            for t in world.tickets
        ),
        account_history=world.account_history + (
            AccountEvent(target.account_id, "merged", merged_at, (("customer_ref", old_ref),)),
        ),
    )

    return InjectedCase(spec, _truth(
        case_kind="merged_account", case_variant=variant,
        target_ticket_id=ticket.ticket_id,
        expected_queue_id=policy[target.tier], expected_account_id=target.account_id,
        remedy_if_wrong="reroute",
        remedy_if_wrong_arguments=({"ticket_id": ticket.ticket_id, "queue_id": policy[target.tier]},),
        world_changes=({
            "entity": "merge", "account_id": target.account_id,
            "merged_customer_ref": old_ref, "ticket_id": ticket.ticket_id,
        },),
        regression_ticket_ids=_regression(
            spec, rng, target_ticket_id=ticket.ticket_id,
            affected_refs={old_ref}, affected_accounts=set(),
        ),
    ))


def _recently_changed(world: WorldSpec, account: Account) -> bool:
    """The generator's notion of a recent tier change (consistent with its source)."""
    window_start = parse_time(world.as_of) - timedelta(days=RECENT_DAYS)
    return any(
        event.account_id == account.account_id
        and event.kind == "tier_changed"
        and event.at == account.updated_at
        and parse_time(event.at) >= window_start
        for event in world.account_history
    )


def recent_tier_change(world: WorldSpec, rng: random.Random, variant: str, forced_ticket: str | None = None) -> InjectedCase:
    """A healthy world whose target account had a recent, consistent tier change.

    Recent changes come from the generator, independently of case kind, so
    this look-alike adds nothing to history. Without a forced ticket it picks
    an account the generator already changed recently; only if a world has
    none does it convert one exactly as the generator would (one event, source
    consistent). With a forced ticket on an account without a recent change it
    does not apply, so counterfactual enumeration never manufactures a history
    difference.
    """
    policy = _policy(world)
    changes: tuple[dict[str, object], ...] = ()
    spec = world

    if forced_ticket is not None:
        target, ticket = _pick_target(world, rng, forced_ticket)

        if not _recently_changed(world, target):
            raise ContractError("target account has no recent tier change")
    else:
        recent = [a for a in world.accounts if _recently_changed(world, a) and _tickets_of(world, a.customer_ref)]

        if recent:
            target = rng.choice(recent)
            ticket = _pick_ticket(world, rng, target)
        else:
            target, ticket = _pick_target(world, rng, None)
            as_of = parse_time(world.as_of)
            changed_at = random_time(
                rng,
                format_time(as_of - timedelta(days=RECENT_DAYS)),
                format_time(as_of - timedelta(days=RECENT_MARGIN_DAYS)),
            )
            spec = replace(
                _with_account(world, target.account_id, version=target.version + 1, updated_at=changed_at),
                account_history=world.account_history + (
                    AccountEvent(target.account_id, "tier_changed", changed_at, (("tier", target.tier),)),
                ),
            )
            changes = ({"entity": "account_history", "account_id": target.account_id, "event": "tier_changed"},)

    return InjectedCase(spec, _truth(
        case_kind="recent_tier_change", case_variant=variant,
        target_ticket_id=ticket.ticket_id,
        expected_queue_id=policy[target.tier], expected_account_id=target.account_id,
        remedy_if_wrong="reroute",
        remedy_if_wrong_arguments=({"ticket_id": ticket.ticket_id, "queue_id": policy[target.tier]},),
        world_changes=changes,
        regression_ticket_ids=_regression(
            spec, rng, target_ticket_id=ticket.ticket_id,
            affected_refs={target.customer_ref}, affected_accounts={target.account_id},
        ),
    ))


def clean_world(world: WorldSpec, rng: random.Random, variant: str, forced_ticket: str | None = None) -> InjectedCase:
    policy = _policy(world)
    target, ticket = _pick_target(world, rng, forced_ticket)

    return InjectedCase(world, _truth(
        case_kind="clean_world", case_variant=variant,
        target_ticket_id=ticket.ticket_id,
        expected_queue_id=policy[target.tier], expected_account_id=target.account_id,
        remedy_if_wrong="reroute",
        remedy_if_wrong_arguments=({"ticket_id": ticket.ticket_id, "queue_id": policy[target.tier]},),
        world_changes=(),
        regression_ticket_ids=_regression(
            world, rng, target_ticket_id=ticket.ticket_id,
            affected_refs=set(), affected_accounts=set(),
        ),
    ))


INJECTORS: dict[str, tuple[Callable[..., InjectedCase], tuple[str, ...]]] = {
    "mapping_swap": (mapping_swap, ("swap", "redirect", "nway")),
    "stale_account_record": (stale_account_record, ("default",)),
    "mishandled_tool_error": (mishandled_tool_error, ("transient", "persistent")),
    "misleading_ticket_text": (misleading_ticket_text, ("claim_false", "claim_true")),
    "missing_account": (missing_account, ("unmapped_ref", "deleted_account")),
    "queue_misconfiguration": (queue_misconfiguration, ("description_swap",)),
    "tier_format_drift": (tier_format_drift, ("case", "abbreviation", "whitespace")),
    "merged_account": (merged_account, ("default",)),
    "recent_tier_change": (recent_tier_change, ("default",)),
    "transient_error_retried": (transient_error_retried, ("default",)),
    "clean_world": (clean_world, ("default",)),
}

assert set(INJECTORS) == set(CASE_KINDS)


def inject(
    kind: str,
    world: WorldSpec,
    rng: random.Random,
    variant: str | None = None,
    forced_ticket: str | None = None,
) -> InjectedCase:
    if kind == COMPOUND_KIND:
        from packages.support_evaluator.compound import inject_compound

        world.require_clean()
        return inject_compound(world, rng, variant, forced_ticket)

    try:
        injector, variants = INJECTORS[kind]
    except KeyError:
        raise ContractError("unknown case kind") from None

    world.require_clean()
    chosen = rng.choice(variants) if variant is None else variant

    if chosen not in variants:
        raise ContractError("unknown variant")

    return injector(world, rng, chosen, forced_ticket)


__all__ = [
    "INJECTORS",
    "InjectedCase",
    "inject",
]

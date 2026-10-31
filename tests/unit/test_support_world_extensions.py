from dataclasses import replace
from functools import partial
import json

import pytest

from environments.support.fixtures import (
    CANONICAL_TIERS,
    DEFAULT_TIMESTAMP,
    DEFAULT_WORLD,
    TIER_VARIANTS,
    AccountEvent,
    SourceRecord,
    SupportEnvironment,
    ToolErrorRule,
    ToolUnavailableError,
    WorldSpec,
    derive_routing,
)
from environments.support.generator import generate_world
from environments.support.tools import (
    SUPPORT_TOOL_DESCRIPTIONS,
    SUPPORT_TOOL_SCHEMAS,
    SUPPORT_TOOLS,
    lookup_account,
    read_ticket,
    route_ticket,
)
from packages.action_gateway import AllowAllPolicy, GatedTool, StageStatus, ToolGateway
from packages.contracts import ContractError


M1_STATE_SHA256 = "5c8e1bc9bf26ec05ca4d27582e061592545e2758da893e1fab38f2b3eee5c82b"
DEFAULT_WORLD_SHA256 = "d53b7319dabab431dc8f802c498e9345960a26dd8a9cf36bc7d293249b354ad5"

FAULT_MARKERS = (
    "fault", "swap", "identifier_mapping", "inject", "stale", "drift",
    "misconfig", "corrupt", "broken",
)


def _with_account(spec, index, **changes):
    accounts = list(spec.accounts)
    accounts[index] = replace(accounts[index], **changes)
    return replace(spec, accounts=tuple(accounts))


def _checks(spec) -> set[str]:
    return {violation["check"] for violation in spec.clean_violations()}


# Two validation levels


def test_default_and_generated_worlds_are_clean():
    assert DEFAULT_WORLD.is_clean
    assert all(generate_world(seed).is_clean for seed in range(20))


def _faulty_worlds():
    base = generate_world(0)
    a, b = base.accounts[0], base.accounts[1]
    directory = dict(base.directory)
    swapped = {**directory, a.customer_ref: b.account_id, b.customer_ref: a.account_id}
    queue_ids = [queue.queue_id for queue in base.queues]
    derived = derive_routing(base.queues)

    return {
        "dangling_directory_entry": (
            replace(base, directory=tuple(sorted({**directory, a.customer_ref: "A-0001"}.items()))),
            {"directory_account_exists", "customer_maps_to_own_account"},
        ),
        "unmapped_ticket_ref": (
            replace(base, directory=tuple(sorted(
                (ref, acc) for ref, acc in directory.items()
                if ref != base.tickets[0].customer_ref
            ))),
            {"ticket_ref_mapped", "customer_maps_to_own_account"},
        ),
        "swapped_mapping": (
            replace(base, directory=tuple(sorted(swapped.items()))),
            {"directory_matches_owner", "customer_maps_to_own_account"},
        ),
        "source_differs_from_record": (
            replace(base, account_sources=(
                SourceRecord(a.account_id, "standard" if a.tier == "enterprise" else "enterprise",
                             a.version + 1, "2026-03-01T00:00:00Z"),
            )),
            {"source_matches_record"},
        ),
        "noncanonical_tier": (
            _with_account(base, 0, tier=TIER_VARIANTS[a.tier][0]),
            {"tier_canonical"},
        ),
        "queue_config_disagrees_with_policy": (
            replace(base, routing_policy=tuple(sorted({
                **derived, "enterprise": derived["standard"], "standard": derived["enterprise"],
            }.items()))),
            {"queue_config_matches_policy"},
        ),
        "incomplete_queue_config": (
            replace(base, queues=(
                replace(base.queues[0], description="Tickets from standard-tier accounts."),
            ) + base.queues[1:]),
            {"queue_config_complete"},
        ),
        "tool_errors_scheduled": (
            replace(base, tool_errors=(ToolErrorRule("lookup_account", None, False, 1),)),
            {"no_tool_errors_scheduled"},
        ),
        "merge_without_history": (
            replace(
                _with_account(base, 0, merged_customer_refs=("C-0042",)),
                directory=tuple(sorted({**directory, "C-0042": a.account_id}.items())),
            ),
            {"merge_recorded"},
        ),
    } | {"_queue_ids": (None, set(queue_ids))}


@pytest.mark.parametrize(
    "name", [name for name in _faulty_worlds() if not name.startswith("_")],
)
def test_faulty_worlds_are_structurally_valid_but_not_clean(name):
    spec, expected_checks = _faulty_worlds()[name]

    assert isinstance(spec, WorldSpec)
    assert _checks(spec) == expected_checks
    assert not spec.is_clean

    with pytest.raises(ContractError, match="world is not clean"):
        spec.require_clean()

    SupportEnvironment(spec)
    assert WorldSpec.from_payload(json.loads(json.dumps(spec.canonical_payload()))) == spec


def test_legitimate_merge_is_clean():
    base = generate_world(0)
    a = base.accounts[0]
    merged = replace(
        _with_account(base, 0, merged_customer_refs=("C-0042",)),
        directory=tuple(sorted({**dict(base.directory), "C-0042": a.account_id}.items())),
        account_history=(
            AccountEvent(a.account_id, "merged", "2026-02-01T00:00:00Z", (("customer_ref", "C-0042"),)),
        ),
    )

    assert merged.is_clean


def test_recent_tier_change_is_clean():
    base = generate_world(0)
    a = base.accounts[0]
    new_tier = "standard" if a.tier == "enterprise" else "enterprise"
    changed = _with_account(base, 0, tier=new_tier, version=2, updated_at="2026-03-01T00:00:00Z")
    changed = replace(
        changed,
        account_sources=(SourceRecord(a.account_id, new_tier, 2, "2026-03-01T00:00:00Z"),),
        account_history=(
            AccountEvent(a.account_id, "tier_changed", "2026-03-01T00:00:00Z", (("tier", new_tier),)),
        ),
    )

    assert changed.is_clean


@pytest.mark.parametrize(
    "build",
    [
        lambda s: _with_account(s, 0, version=0),
        lambda s: _with_account(s, 0, updated_at="yesterday"),
        lambda s: _with_account(s, 0, merged_customer_refs=(s.accounts[0].customer_ref,)),
        lambda s: _with_account(s, 0, merged_customer_refs=("C-0042", "C-0042")),
        lambda s: replace(s, account_sources=(SourceRecord("A-0001", "standard", 1, DEFAULT_TIMESTAMP),)),
        lambda s: replace(s, account_sources=(SourceRecord.of(s.accounts[0]),) * 2),
        lambda s: replace(s, account_history=(AccountEvent("A-0001", "created", DEFAULT_TIMESTAMP),)),
        lambda s: replace(s, routing_policy=(("enterprise", s.queues[0].queue_id),)),
        lambda s: replace(s, routing_policy=tuple((r, "Q-MISSING") for r in ("enterprise", "standard", "unresolved"))),
        lambda s: replace(s, directory=(("C-1", "A-0001"),)),
        lambda s: replace(s, tool_errors=("not a rule",)),
        lambda s: replace(s, as_of="soon"),
    ],
)
def test_structural_validation_still_rejects_malformed_worlds(build):
    with pytest.raises(ContractError):
        build(generate_world(0))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"tool_name": "Lookup", "target": None, "persistent": False, "failures": 1},
        {"tool_name": "lookup_account", "target": "C-1234", "persistent": False, "failures": 1},
        {"tool_name": "lookup_account", "target": None, "persistent": False, "failures": 0},
        {"tool_name": "lookup_account", "target": None, "persistent": True, "failures": 2},
        {"tool_name": "lookup_account", "target": None, "persistent": False, "failures": 1, "error_code": "other"},
    ],
)
def test_invalid_tool_error_rules_are_rejected(kwargs):
    with pytest.raises(ContractError):
        ToolErrorRule(**kwargs)


def test_history_events_validate_kind_and_details():
    with pytest.raises(ContractError):
        AccountEvent("A-1234", "renamed", DEFAULT_TIMESTAMP)
    with pytest.raises(ContractError):
        AccountEvent("A-1234", "merged", DEFAULT_TIMESTAMP, (("customer_ref",),))


# Snapshot: defaults omitted, non-defaults always included


def test_milestone_1_hashes_stay_pinned():
    assert SupportEnvironment().state_sha256() == M1_STATE_SHA256
    assert DEFAULT_WORLD.world_sha256 == DEFAULT_WORLD_SHA256
    assert DEFAULT_WORLD.extension_payload() == {}
    snapshot = SupportEnvironment().snapshot()
    assert set(snapshot) == {
        "record_type", "schema_version", "tickets", "accounts", "queues", "customer_directory",
    }
    assert all(set(account) == {"account_id", "customer_ref", "display_name", "tier", "region"}
               for account in snapshot["accounts"])


def _first_account(spec):
    return spec.accounts[0]


NON_DEFAULT = {
    "account_version": (
        lambda s: _with_account(s, 0, version=2),
        lambda snap: snap["accounts"][0].get("version") == 2,
    ),
    "account_updated_at": (
        lambda s: _with_account(s, 0, updated_at="2026-02-02T00:00:00Z"),
        lambda snap: snap["accounts"][0].get("updated_at") == "2026-02-02T00:00:00Z",
    ),
    "merged_customer_refs": (
        lambda s: _with_account(s, 0, merged_customer_refs=("C-0042",)),
        lambda snap: snap["accounts"][0].get("merged_customer_refs") == ["C-0042"],
    ),
    "account_sources": (
        lambda s: replace(s, account_sources=(SourceRecord.of(_first_account(s)),)),
        lambda snap: len(snap.get("account_sources", [])) == 1,
    ),
    "account_history": (
        lambda s: replace(s, account_history=(
            AccountEvent(_first_account(s).account_id, "created", DEFAULT_TIMESTAMP),
        )),
        lambda snap: snap.get("account_history", [{}])[0].get("kind") == "created",
    ),
    "routing_policy": (
        lambda s: replace(s, routing_policy=tuple(sorted(derive_routing(s.queues).items()))),
        lambda snap: set(snap.get("routing_policy", {})) == {"enterprise", "standard", "unresolved"},
    ),
    "tool_errors": (
        lambda s: replace(s, tool_errors=(ToolErrorRule("read_ticket", None, True, 0),)),
        lambda snap: snap.get("tool_errors", [{}])[0].get("persistent") is True,
    ),
    "as_of": (
        lambda s: replace(s, as_of="2026-06-30T12:00:00Z"),
        lambda snap: snap.get("as_of") == "2026-06-30T12:00:00Z",
    ),
}


@pytest.mark.parametrize("name", sorted(NON_DEFAULT))
def test_non_default_values_are_in_the_snapshot_and_its_hash(name):
    build, present = NON_DEFAULT[name]
    spec = build(DEFAULT_WORLD)
    environment = SupportEnvironment(spec)

    assert present(environment.snapshot())
    assert environment.state_sha256() != M1_STATE_SHA256
    assert spec.world_sha256 != DEFAULT_WORLD_SHA256
    assert WorldSpec.from_payload(json.loads(json.dumps(spec.canonical_payload()))) == spec


def test_every_extension_together_round_trips_and_is_hashed():
    spec = DEFAULT_WORLD

    for build, _ in NON_DEFAULT.values():
        spec = build(spec)

    restored = WorldSpec.from_payload(json.loads(json.dumps(spec.canonical_payload())))

    assert restored == spec
    assert restored.world_sha256 == spec.world_sha256
    assert len({SupportEnvironment(spec).state_sha256(), M1_STATE_SHA256}) == 2


def test_explicit_default_values_are_treated_as_defaults():
    explicit = _with_account(DEFAULT_WORLD, 0, version=1, updated_at=DEFAULT_TIMESTAMP)

    assert SupportEnvironment(explicit).state_sha256() == M1_STATE_SHA256


# Source records, history and routing policy accessors


def test_sources_history_and_policy_accessors():
    base = generate_world(1)
    a = base.accounts[0]
    source = SourceRecord(a.account_id, a.tier, a.version + 1, "2026-04-01T00:00:00Z")
    event = AccountEvent(a.account_id, "created", "2025-12-01T00:00:00Z")
    environment = SupportEnvironment(replace(base, account_sources=(source,), account_history=(event,)))

    assert environment.account_source(a.account_id) == source
    other = base.accounts[1]
    assert environment.account_source(other.account_id) == SourceRecord.of(other)
    assert environment.account_history(a.account_id) == (event,)
    assert environment.account_history(other.account_id) == ()
    assert environment.routing_policy() == derive_routing(base.queues)

    with pytest.raises(ContractError, match="unknown account_id"):
        environment.account_source("A-0001")


def test_routing_policy_is_fixed_even_if_queue_config_changes():
    base = generate_world(1)
    environment = SupportEnvironment(base)
    policy = environment.routing_policy()
    queue = environment.get_queue(policy["enterprise"])
    environment._queues[queue.queue_id] = replace(queue, description="Tickets from standard-tier accounts.")

    assert environment.routing_policy() == policy


def test_derive_routing_requires_one_queue_per_role():
    base = generate_world(1)
    assert set(derive_routing(base.queues)) == {"enterprise", "standard", "unresolved"}
    assert derive_routing(base.queues[:2]) is None


def test_agent_lookup_view_hides_extensions():
    spec = _with_account(
        DEFAULT_WORLD, 2, version=3, updated_at="2026-02-02T00:00:00Z", merged_customer_refs=("C-0042",),
    )
    observation = lookup_account(SupportEnvironment(spec), account_id=spec.accounts[2].account_id)

    assert set(observation) == {"account_id", "customer_ref", "display_name", "tier", "region"}


def test_tier_variants_are_noncanonical_spellings_of_canonical_tiers():
    assert set(TIER_VARIANTS) == set(CANONICAL_TIERS)

    for tier, variants in TIER_VARIANTS.items():
        abbreviation = {"enterprise": "ent", "standard": "std"}[tier]
        assert variants and all(
            v != tier and v.strip().casefold() in (tier, abbreviation) for v in variants
        )


# Tool-error schedule


def _gateway(environment):
    return ToolGateway(
        tools=[
            GatedTool(name, partial(f, environment), SUPPORT_TOOL_SCHEMAS[name], SUPPORT_TOOL_DESCRIPTIONS[name])
            for name, f in SUPPORT_TOOLS.items()
        ],
        policy=AllowAllPolicy(),
        state_sha256=environment.state_sha256,
    )


def test_transient_errors_fail_a_fixed_number_of_calls_then_succeed():
    base = generate_world(2)
    account_id = base.accounts[0].account_id
    environment = SupportEnvironment(
        replace(base, tool_errors=(ToolErrorRule("lookup_account", None, False, 2),))
    )

    for _ in range(2):
        with pytest.raises(ToolUnavailableError, match="^service unavailable$"):
            lookup_account(environment, account_id=account_id)

    assert lookup_account(environment, account_id=account_id)["account_id"] == account_id

    environment.reset()
    with pytest.raises(ToolUnavailableError):
        lookup_account(environment, account_id=account_id)


def test_persistent_errors_always_fail_and_targets_filter_calls():
    base = generate_world(2)
    target, other = base.tickets[0].ticket_id, base.tickets[1].ticket_id
    environment = SupportEnvironment(
        replace(base, tool_errors=(ToolErrorRule("read_ticket", target, True, 0, "timeout"),))
    )

    for _ in range(5):
        with pytest.raises(ToolUnavailableError, match="^request timed out$"):
            read_ticket(environment, ticket_id=target)

    assert read_ticket(environment, ticket_id=other)["ticket_id"] == other


def test_error_schedule_is_deterministic_across_environments():
    spec = replace(generate_world(3), tool_errors=(ToolErrorRule("read_ticket", None, False, 1),))

    def outcomes():
        environment = SupportEnvironment(spec)
        results = []
        for ticket in spec.tickets[:3]:
            try:
                read_ticket(environment, ticket_id=ticket.ticket_id)
                results.append("ok")
            except ToolUnavailableError:
                results.append("error")
        return results

    assert outcomes() == outcomes() == ["error", "ok", "ok"]


def test_scheduled_errors_are_recorded_as_failed_observations_without_state_change():
    base = generate_world(4)
    ticket_id = base.tickets[0].ticket_id
    queue_id = base.queues[0].queue_id
    environment = SupportEnvironment(
        replace(base, tool_errors=(ToolErrorRule("route_ticket", ticket_id, False, 1),))
    )
    gateway = _gateway(environment)
    start = environment.state_sha256()

    failed = gateway.invoke("route_ticket", {"ticket_id": ticket_id, "queue_id": queue_id})

    assert failed.status is StageStatus.FAILED
    assert failed.error == {"type": "ToolUnavailableError", "message": "service unavailable"}
    assert failed.records[-1].state_before_sha256 == failed.records[-1].state_after_sha256 == start

    retried = gateway.invoke("route_ticket", {"ticket_id": ticket_id, "queue_id": queue_id})
    assert retried.status is StageStatus.SUCCEEDED


# Observation-only messages and the no-marker scan


def _everything_visible(spec):
    environment = SupportEnvironment(spec)
    outputs, messages = [], []

    for ticket in spec.tickets:
        for call in (
            lambda: read_ticket(environment, ticket_id=ticket.ticket_id),
            lambda: route_ticket(environment, ticket_id=ticket.ticket_id, queue_id=spec.queues[0].queue_id),
        ):
            try:
                outputs.append(call())
            except Exception as exc:
                messages.append(f"{type(exc).__name__}: {exc}")

    for account in spec.accounts:
        try:
            outputs.append(lookup_account(environment, account_id=account.account_id))
        except Exception as exc:
            messages.append(f"{type(exc).__name__}: {exc}")

    for bad in ("T-0001", "A-0001"):
        for call in (lambda: read_ticket(environment, ticket_id=bad), lambda: lookup_account(environment, account_id=bad)):
            try:
                call()
            except Exception as exc:
                messages.append(f"{type(exc).__name__}: {exc}")

    return environment, outputs, messages


def _all_extensions_world():
    spec = generate_world(5)

    for build, _ in NON_DEFAULT.values():
        spec = build(spec)

    a = spec.accounts[1]
    return replace(
        _with_account(spec, 1, tier=TIER_VARIANTS[a.tier][1]),
        directory=tuple(sorted({**dict(spec.directory), spec.accounts[2].customer_ref: "A-0001"}.items())),
        tool_errors=(
            ToolErrorRule("lookup_account", None, False, 1),
            ToolErrorRule("read_ticket", spec.tickets[0].ticket_id, True, 0, "timeout"),
        ),
    )


def test_environment_messages_describe_observations_only():
    _, _, messages = _everything_visible(_all_extensions_world())

    assert messages
    assert set(messages) <= {
        "ToolUnavailableError: service unavailable",
        "ToolUnavailableError: request timed out",
        "ContractError: unknown ticket_id",
        "ContractError: unknown account_id",
        "ContractError: unknown customer_ref",
        "ContractError: ticket_id has an invalid format",
        "ContractError: account_id has an invalid format",
    }


def test_new_fields_and_tool_outputs_carry_no_fault_markers():
    spec = _all_extensions_world()
    environment, outputs, messages = _everything_visible(spec)
    surfaces = json.dumps(
        {
            "spec": spec.canonical_payload(),
            "snapshot": environment.snapshot(),
            "outputs": outputs,
            "messages": messages,
            "violations": list(spec.clean_violations()),
        }
    ).lower()

    for marker in FAULT_MARKERS:
        assert marker not in surfaces, marker

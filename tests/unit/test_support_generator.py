from dataclasses import FrozenInstanceError, replace
import json

import pytest

from environments.support.fixtures import (
    DEFAULT_WORLD,
    Account,
    SupportEnvironment,
    WorldSpec,
)
from environments.support.generator import (
    GENERATOR_NAME,
    GENERATOR_VERSION,
    MAX_ACCOUNTS,
    MAX_TICKETS,
    generate_world,
)
from environments.support.tools import find_accounts_by_customer_ref, read_ticket
from packages.contracts import ContractError


M1_STATE_SHA256 = "5c8e1bc9bf26ec05ca4d27582e061592545e2758da893e1fab38f2b3eee5c82b"
DEFAULT_WORLD_SHA256 = "d53b7319dabab431dc8f802c498e9345960a26dd8a9cf36bc7d293249b354ad5"

# Drift guards: these change only when GENERATOR_VERSION should change.
PINNED_WORLDS = {
    0: "2d172fbeacf2fb85ed4f237c94f258addba26ae9fe2beb6b7b07c08538a37c4f",
    1: "31bbf4980c34d635b834be8979b153fa1b1ac1ba9e24b9bd1aadec1c6630f46e",
}

FAULT_MARKERS = ("fault", "swap", "identifier_mapping", "inject")


# The Milestone 1 world stays the default


def test_default_world_is_the_milestone_1_world():
    assert SupportEnvironment().spec is DEFAULT_WORLD
    assert SupportEnvironment().state_sha256() == M1_STATE_SHA256
    assert SupportEnvironment(DEFAULT_WORLD).state_sha256() == M1_STATE_SHA256
    assert DEFAULT_WORLD.world_sha256 == DEFAULT_WORLD_SHA256
    assert DEFAULT_WORLD.generator is None


def test_snapshot_format_is_the_same_for_every_world():
    default_keys = set(SupportEnvironment().snapshot())
    generated = SupportEnvironment(generate_world(3)).snapshot()

    assert set(generated) == default_keys
    assert "generator" not in json.dumps(generated)


def test_reset_restores_the_environment_spec():
    environment = SupportEnvironment(generate_world(5))
    start = environment.state_sha256()
    ticket_id = environment.ticket_ids()[0]
    queue_id = environment.queue_ids()[0]

    environment.assign_ticket(ticket_id, queue_id)
    assert environment.state_sha256() != start

    environment.reset()
    assert environment.state_sha256() == start


# Determinism and identity


@pytest.mark.parametrize("seed", sorted(PINNED_WORLDS))
def test_generated_worlds_are_pinned(seed):
    assert generate_world(seed).world_sha256 == PINNED_WORLDS[seed]


def test_same_seed_same_world_and_different_seeds_differ():
    assert generate_world(42) == generate_world(42)
    hashes = {generate_world(seed).world_sha256 for seed in range(50)}
    assert len(hashes) == 50


def test_generator_metadata_is_recorded():
    spec = generate_world(9, accounts=5, tickets=7)

    assert spec.generator == {
        "name": GENERATOR_NAME, "version": GENERATOR_VERSION,
        "seed": 9, "accounts": 5, "tickets": 7,
    }
    assert (len(spec.accounts), len(spec.tickets), len(spec.queues)) == (5, 7, 3)


def test_spec_round_trips_through_json():
    spec = generate_world(11)
    restored = WorldSpec.from_payload(json.loads(json.dumps(spec.canonical_payload())))

    assert restored == spec
    assert restored.world_sha256 == spec.world_sha256
    assert WorldSpec.from_payload(DEFAULT_WORLD.canonical_payload()) == DEFAULT_WORLD


def test_specs_are_immutable():
    spec = generate_world(0)

    with pytest.raises(FrozenInstanceError):
        spec.tickets = ()  # type: ignore[misc]


# Validity of generated worlds


@pytest.mark.parametrize("seed", range(25))
def test_generated_worlds_are_clean_and_routable(seed):
    spec = generate_world(seed)
    environment = SupportEnvironment(spec)

    assert {account.tier for account in spec.accounts} == {"enterprise", "standard"}

    for account in spec.accounts:
        assert environment.resolve_customer(account.customer_ref) == account.account_id
        assert find_accounts_by_customer_ref(environment, customer_ref=account.customer_ref)[
            "account_ids"
        ] == [account.account_id]

    matches = {
        tier: [queue.queue_id for queue in spec.queues if f"{tier}-tier" in queue.description]
        for tier in ("enterprise", "standard")
    }
    assert all(len(queue_ids) == 1 for queue_ids in matches.values())
    triage = [queue for queue in spec.queues if "-tier" not in queue.description]
    assert len(triage) == 1

    for ticket in spec.tickets:
        assert read_ticket(environment, ticket_id=ticket.ticket_id)["account_id"] in {
            account.account_id for account in spec.accounts
        }


def test_every_account_gets_a_ticket_when_there_are_enough_tickets():
    spec = generate_world(2, accounts=6, tickets=10)

    assert {ticket.customer_ref for ticket in spec.tickets} == {
        account.customer_ref for account in spec.accounts
    }


def test_generated_worlds_vary_across_seeds():
    specs = [generate_world(seed) for seed in range(40)]

    assert len({spec.queues[0].queue_id for spec in specs}) >= 3
    assert len({queue.description for spec in specs for queue in spec.queues}) >= 6
    assert len({ticket.subject for spec in specs for ticket in spec.tickets}) >= 12
    assert len({account.display_name for spec in specs for account in spec.accounts}) >= 200
    targets = {spec.tickets[0].ticket_id for spec in specs}
    assert len(targets) == 40


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"seed": -1}, "seed"),
        ({"seed": True}, "seed"),
        ({"seed": 0, "accounts": 1}, "accounts"),
        ({"seed": 0, "accounts": MAX_ACCOUNTS + 1}, "accounts"),
        ({"seed": 0, "tickets": 0}, "tickets"),
        ({"seed": 0, "tickets": MAX_TICKETS + 1}, "tickets"),
    ],
)
def test_invalid_generator_arguments_are_rejected(kwargs, message):
    seed = kwargs.pop("seed")

    with pytest.raises(ContractError, match=message):
        generate_world(seed, **kwargs)


def test_generated_worlds_carry_no_fault_markers():
    for seed in range(10):
        text = json.dumps(generate_world(seed).canonical_payload()).lower()

        for marker in FAULT_MARKERS:
            assert marker not in text, (seed, marker)


# WorldSpec validation


def test_world_spec_rejects_structurally_invalid_worlds():
    spec = generate_world(0)
    first, second = spec.accounts[0], spec.accounts[1]

    invalid = [
        lambda: replace(spec, accounts=spec.accounts + (first,)),
        lambda: replace(spec, directory=spec.directory + ((first.customer_ref, first.account_id),)),
        lambda: replace(spec, tickets=(replace(spec.tickets[0], queue_id="Q-MISSING"),) + spec.tickets[1:]),
        lambda: replace(spec, queues=(replace(spec.queues[0], ticket_ids=("T-0001",)),) + spec.queues[1:]),
        lambda: replace(spec, tickets=()),
        lambda: replace(spec, accounts=(first, second, "not an account")),
    ]

    for build in invalid:
        with pytest.raises(ContractError):
            build()

    with pytest.raises(ContractError):
        SupportEnvironment("not a spec")  # type: ignore[arg-type]

    assert isinstance(first, Account)

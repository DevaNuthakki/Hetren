"""Compound faults: merging two injections on one target, and their labels.

- The recomputed outcome reproduces every single injector's truth.
- Conflicting changes to the same field reject the pair.
- Compound worlds keep both faults, label by execution (both an ``abstain``
  pair and a pair with a smallest verified fix), and leak nothing.
"""

import random
import socket

import pytest

from environments.support.fixtures import SupportEnvironment
from environments.support.generator import generate_world
from packages.contracts import ContractError
from packages.hetren_evidence import compact_evidence
from packages.support_evaluator import scan_case_content
from packages.support_evaluator.cases import (
    COMPOUND_KIND,
    compound_variant,
    is_held_out,
    parse_compound,
)
from packages.support_evaluator.compound import affected, compound_variants, expected_outcome
from packages.support_evaluator.injectors import INJECTORS, inject
from packages.support_evaluator.labeler import label_run
from packages.support_evaluator.sampling import run_agent_on


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("network access attempted in an offline test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def _applying(variant, seeds=range(40)):
    for seed in seeds:
        world = generate_world(7000 + seed)

        try:
            return world, inject(COMPOUND_KIND, world, random.Random(seed), variant)
        except ContractError:
            continue

    raise AssertionError(f"{variant} never applies")


def test_recomputed_outcome_matches_every_single_injection():
    for seed in range(20):
        world = generate_world(seed)

        for kind, (_, variants) in INJECTORS.items():
            for variant in variants:
                try:
                    case = inject(kind, world, random.Random(seed), variant)
                except ContractError:
                    continue

                outcome = expected_outcome(world, case.spec, case.truth.target_ticket_id)
                assert outcome == (case.truth.expected_queue_id, case.truth.expected_account_id), (kind, variant)


def test_variant_names_are_canonical_and_held_out_follows_components():
    variant = compound_variant(("stale_account_record", "default"), ("mapping_swap", "swap"))

    assert variant == "mapping_swap.swap+stale_account_record.default"
    assert parse_compound(variant) == (("mapping_swap", "swap"), ("stale_account_record", "default"))
    assert is_held_out(COMPOUND_KIND, "mapping_swap.swap+queue_misconfiguration.description_swap")
    assert not is_held_out(COMPOUND_KIND, variant)

    with pytest.raises(ContractError):
        parse_compound("stale_account_record.default+mapping_swap.swap")

    with pytest.raises(ContractError):
        compound_variant(("mapping_swap", "swap"), ("mapping_swap", "redirect"))


def test_conflicting_changes_to_the_same_reference_reject_the_pair():
    world = generate_world(3)

    with pytest.raises(ContractError, match="conflicting"):
        for seed in range(20):
            inject(COMPOUND_KIND, world, random.Random(seed), "mapping_swap.redirect+missing_account.unmapped_ref")


def test_compound_worlds_keep_both_faults_and_spare_regression_tickets():
    world, case = _applying("mapping_swap.swap+stale_account_record.default")
    refs, accounts, tickets = affected(world, case.spec)
    entities = {change["entity"] for change in case.truth.world_changes}

    assert entities == {"directory", "account_source"}
    assert dict(case.spec.directory) != dict(world.directory)
    assert len(case.spec.account_sources) == len(world.account_sources) + 1
    assert case.truth.regression_ticket_ids

    for ticket_id in case.truth.regression_ticket_ids:
        ticket = next(t for t in case.spec.tickets if t.ticket_id == ticket_id)
        assert ticket.customer_ref not in refs and ticket_id not in tickets


@pytest.mark.parametrize(
    ("variant", "behaviour", "verb"),
    [
        # Fixing the mapping still routes on the stale tier: no single action verifies.
        ("mapping_swap.swap+stale_account_record.default", "trust", "abstain"),
        # The retrying agent survives the transient error, so set_mapping alone verifies.
        ("mapping_swap.swap+transient_error_retried.default", "retry", "set_mapping"),
        # The transient error is used up by the run; restoring the record verifies.
        ("stale_account_record.default+transient_error_retried.default", "retry", "restore_from_source"),
    ],
)
def test_compound_labels_come_from_execution(variant, behaviour, verb):
    _, case = _applying(variant)
    environment = SupportEnvironment(case.spec)
    evidence = run_agent_on(environment, case.truth.target_ticket_id, behaviour).evidence_payload()

    assert label_run(case, environment, evidence, behaviour).verb == verb
    assert scan_case_content({"steps": [{"input": compact_evidence(evidence)}]}, case.truth) == ()


def test_every_training_pair_type_has_variants():
    variants = compound_variants(tuple(INJECTORS))
    pairs = {tuple(kind for kind, _ in parse_compound(v)) for v in variants}

    assert ("mapping_swap", "stale_account_record") in pairs
    assert all(a != b for a, b in pairs)
    assert len(variants) == len(set(variants))

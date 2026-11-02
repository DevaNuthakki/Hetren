"""Distractors: irrelevant inconsistencies away from the target (tier 2).

- They never touch the target's chain or regression tickets, keep the
  case's own fault and outcome, and leave labels unchanged by execution.
- F6 is never a distractor; F7 only in held-out cases.
- Tier 1 records and labelling are unchanged.
"""

from collections import Counter
from dataclasses import replace
import random
import socket

import pytest

from environments.support.fixtures import SupportEnvironment
from environments.support.generator import generate_world
from packages.contracts import ContractError
from packages.support_agent import BEHAVIOURS
from packages.support_evaluator import scan_case_content
from packages.support_evaluator.cases import CaseTruth
from packages.support_evaluator.compound import affected, merge_specs
from packages.support_evaluator.distractors import apply_distractors, draw_distractors, inject_planned
from packages.support_evaluator.injectors import inject
from packages.support_evaluator.labeler import label_case
from packages.support_evaluator.plan import PlannedCase, planned_payload
from packages.support_evaluator.sampling import run_agent_on
from packages.support_evaluator.sequences import label_case_tier2, label_sequence


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("network access attempted in an offline test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def _planned(kind, variant, count, seeds=range(7000, 7040), behaviour="trust"):
    for seed in seeds:
        planned = PlannedCase(kind, variant, behaviour, seed, seed - 7000, "complete", count)

        try:
            return planned, inject_planned(planned)
        except ContractError:
            continue

    raise AssertionError(f"{kind} {variant} never fits {count} distractors")


@pytest.mark.parametrize(("kind", "variant"), [
    ("mapping_swap", "swap"),
    ("stale_account_record", "default"),
    ("compound", "mapping_swap.swap+stale_account_record.default"),
])
def test_distractors_keep_the_own_fault_and_spare_the_target_chain(kind, variant):
    planned, (case, distractors) = _planned(kind, variant, 2)
    base, none = inject_planned(replace(planned, distractors=0))
    clean = generate_world(planned.world_seed)
    truth = case.truth

    assert none == () and len(distractors) == 2
    assert replace(truth, distractor_changes=()) == base.truth
    assert [d["kind"] for d in truth.distractor_changes] == [d.kind for d in distractors]
    assert case.spec == merge_specs(clean, merge_specs(clean, base.spec, distractors[0].spec), distractors[1].spec)

    protected_tickets = {truth.target_ticket_id, *truth.regression_ticket_ids}
    protected_refs = {t.customer_ref for t in clean.tickets if t.ticket_id in protected_tickets}
    protected_accounts = {dict(clean.directory).get(ref) for ref in protected_refs} | {truth.expected_account_id}

    for distractor in distractors:
        refs, accounts, tickets = affected(clean, distractor.spec)
        assert not refs & protected_refs and not accounts & protected_accounts
        assert not tickets & protected_tickets


@pytest.mark.parametrize(("kind", "variant"), [
    ("mapping_swap", "swap"),
    ("missing_account", "unmapped_ref"),
    ("mishandled_tool_error", "persistent"),
    ("recent_tier_change", "default"),
    ("compound", "mapping_swap.swap+stale_account_record.default"),
])
def test_labels_are_unchanged_by_execution(kind, variant):
    planned, (case, _) = _planned(kind, variant, 2)
    base, _ = inject_planned(replace(planned, distractors=0))

    for behaviour in BEHAVIOURS:
        labels = []

        for c in (base, case):
            environment = SupportEnvironment(c.spec)
            evidence = run_agent_on(environment, c.truth.target_ticket_id, behaviour).evidence_payload()
            labels.append(label_sequence(c, environment, evidence, behaviour).targets)

        assert labels[0] == labels[1], behaviour


def test_f6_is_never_a_distractor_and_f7_only_in_held_out_cases():
    seen = {False: Counter(), True: Counter()}

    for seed in range(30):
        world = generate_world(7000 + seed)

        for kind, variant in (("stale_account_record", "default"), ("tier_format_drift", "case")):
            try:
                case = inject(kind, world, random.Random(seed), variant)
                _, distractors = draw_distractors(world, case, random.Random(f"{seed}:distractors"), 2)
            except ContractError:
                continue

            seen[case.truth.held_out].update(d.kind for d in distractors)

    assert "queue_misconfiguration" not in seen[False] | seen[True]
    assert "tier_format_drift" not in seen[False] and seen[True]["tier_format_drift"]


def test_counterfactuals_get_the_same_distractors_or_are_skipped():
    planned, (case, distractors) = _planned("mapping_swap", "swap", 1)
    clean = generate_world(planned.world_seed)
    other = inject("stale_account_record", clean, random.Random(1), "default", forced_ticket=case.truth.target_ticket_id)
    applied = apply_distractors(clean, other, distractors)

    if applied is not None:
        assert applied.truth.distractor_changes == case.truth.distractor_changes
        assert replace(applied.truth, distractor_changes=()) == other.truth


def test_tier1_records_are_unchanged_and_tier1_labelling_refuses_distractors():
    planned = PlannedCase("mapping_swap", "swap", "trust", 7000, 0)
    truth = inject_planned(planned)[0].truth

    assert "distractors" not in planned_payload(planned) and "distractor_changes" not in truth.canonical_payload()
    assert PlannedCase(**planned_payload(planned)) == planned
    assert CaseTruth.from_payload(truth.canonical_payload()) == truth

    with pytest.raises(ContractError, match="tier 2"):
        label_case(replace(planned, distractors=1))


@pytest.mark.slow
def test_tier2_labels_with_distractors_are_leak_free():
    planned, (case, _) = _planned("compound", "mapping_swap.swap+stale_account_record.default", 2)
    labelled = label_case_tier2(planned)
    payload = planned_payload(planned)

    assert payload["distractors"] == 2 and PlannedCase(**payload) == planned
    assert labelled.case.truth == case.truth
    assert scan_case_content({"steps": labelled.steps}, labelled.case.truth) == ()

    for partner in labelled.partners:
        assert scan_case_content({"steps": partner["steps"]}, labelled.case.truth) == ()

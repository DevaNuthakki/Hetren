"""The tier 2 (dataset v3) plan: balanced slots and per-slot seed streams."""

from collections import Counter
from itertools import islice

import pytest

from packages.contracts import ContractError
from packages.support_agent import BEHAVIOURS
from packages.support_evaluator import dataset, distractors
from packages.support_evaluator.cases import COMPOUND_KIND, HELD_OUT_KINDS, is_held_out, parse_compound
from packages.support_evaluator.plan import (
    TIER2_HELD_OUT_PAIRS,
    TIER2_PAIRS,
    TIER2_SINGLE_KINDS,
    TIER2_WORLD_SEEDS,
    slot_candidates,
    tier2_slots,
)


def _group(slot):
    if slot.case_kind != COMPOUND_KIND:
        return slot.case_kind

    return tuple(kind for kind, _ in parse_compound(slot.case_variant))


def test_plan_sizes_and_groups():
    slots = tier2_slots(7)

    assert len(TIER2_PAIRS) == 25 and len(TIER2_HELD_OUT_PAIRS) == 10 and len(TIER2_SINGLE_KINDS) == 8
    assert len(slots) == 25 * 5 * 8 + 10 * 5 * 8 + 8 * 5 * 16
    held_out = [s for s in slots if is_held_out(s.case_kind, s.case_variant)]
    assert len(held_out) == 400 and all(s.case_kind == COMPOUND_KIND for s in held_out)
    assert not any(k in HELD_OUT_KINDS for s in slots if s.case_kind != COMPOUND_KIND for k in [s.case_kind])
    assert set(Counter(_group(s) for s in slots).values()) == {40, 80}


def test_behaviour_withheld_and_distractors_are_balanced_within_every_cell():
    slots = tier2_slots(7)
    cells = Counter((_group(s), s.behaviour) for s in slots)
    assert set(b for _, b in cells) == set(BEHAVIOURS)

    for (group, behaviour), size in cells.items():
        cell = [s for s in slots if (_group(s), s.behaviour) == (group, behaviour)]
        assert sum(s.evidence_condition == "withheld" for s in cell) == size // 8
        assert Counter(s.distractors for s in cell) == Counter(i % 3 for i in range(size))

    variants = Counter(s.case_variant for s in slots if _group(s) == ("mapping_swap", "stale_account_record"))
    assert max(variants.values()) - min(variants.values()) <= 5  # variants cycle evenly per cell


def test_plan_is_reproducible_and_seeded():
    assert tier2_slots(7) == tier2_slots(7)
    assert tier2_slots(7) != tier2_slots(8)


def test_each_slot_has_its_own_reproducible_seed_stream_in_the_v3_range():
    slots = tier2_slots(7)
    first = list(islice(slot_candidates(slots[3], 7, 3), 5))

    assert first == list(islice(slot_candidates(slots[3], 7, 3), 5))
    assert first[0].world_seed != next(slot_candidates(slots[4], 7, 4)).world_seed
    assert all(TIER2_WORLD_SEEDS[0] <= p.world_seed < TIER2_WORLD_SEEDS[1] for p in first)
    assert all((p.case_kind, p.case_variant, p.behaviour, p.evidence_condition, p.distractors)
               == (slots[3].case_kind, slots[3].case_variant, slots[3].behaviour,
                   slots[3].evidence_condition, slots[3].distractors) for p in first)


def test_only_injection_redraws_and_labelling_errors_stop_the_build(monkeypatch):
    slot = tier2_slots(7)[0]
    calls = []

    def inject(planned):
        calls.append(planned)
        if len(calls) == 1:
            raise ContractError("conflicting change to directory C-0001")
        return None, ()

    monkeypatch.setattr(distractors, "inject_planned", inject)
    monkeypatch.setattr(dataset, "label_planned", lambda planned, labeller, extra: (planned, extra))
    planned, extra = dataset.label_slot(slot, 7, 0)

    assert planned == calls[1] and extra["redraws"] == [
        {"world_seed": calls[0].world_seed, "case_seed": calls[0].case_seed,
         "reason": "conflicting change to directory C-0001"},
    ]

    # A labelling error is not a redraw: it stops the build.
    def fails(planned):
        raise ContractError("distractors changed the label")

    monkeypatch.setattr(dataset, "label_planned", lambda planned, labeller, extra: fails(planned))
    with pytest.raises(ContractError, match="changed the label"):
        dataset.label_slot(slot, 7, 0)

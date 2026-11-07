"""The checkpoint-selection subset and score of Amendment 1: proportional
allocation by largest remainder, a seeded draw, and S = ½(A₁ + A₂) − W with W
pooled over the healthy runs of both tiers. The validation data is
gitignored, so the committed lists are checked against a fresh draw only
where it exists."""

from pathlib import Path

import pytest

from packages.support_evaluator.selection_subset import SOURCES, allocate, build, draw, selection_score


ROOT = Path(__file__).resolve().parents[2]
SUBSET = ROOT / "docs" / "milestone-3" / "selection-subset-v1"


def test_places_go_to_the_largest_remainders_and_ties_to_the_first_name():
    assert allocate({"a": 5, "b": 3, "c": 2}, 5) == {"a": 3, "b": 1, "c": 1}  # 2.5, 1.5, 1.0
    assert allocate({"x": 1, "y": 1, "z": 1}, 2) == {"x": 1, "y": 1, "z": 0}
    assert sum(allocate({k: 7 + i for i, k in enumerate("abcdefgh")}, 37).values()) == 37


def test_the_draw_is_seeded_and_follows_the_allocation():
    kinds = {f"case-{i:03d}": ("one" if i < 30 else "two") for i in range(50)}
    chosen, quota = draw(kinds, 10, tier=1)

    assert quota == {"one": 6, "two": 4} and chosen == sorted(chosen) == draw(kinds, 10, tier=1)[0]
    assert sum(kinds[c] == "one" for c in chosen) == 6
    assert draw(kinds, 10, tier=2)[0] != chosen  # each tier has its own stream


def _row(correct, label="no_intervention", action="decide", recoveries=()):
    return {"correct": correct, "exact": correct, "label": {"action": action, "verb": label}, "final": None,
            "recoveries": list(recoveries), "failure": None, "case_id": "c", "tier": 1}


def test_the_score_is_mean_accuracy_minus_the_pooled_wrong_intervention_rate():
    tier1 = [_row(True), _row(False, recoveries=[{"verb": "rerun"}]), _row(True, "rerun", "recover", [{}]), _row(False)]
    tier2 = [_row(True), _row(True)]
    score = selection_score(tier1, tier2)

    assert score["A1"]["rate"] == 0.5 and score["A2"]["rate"] == 1.0
    assert (score["W"]["k"], score["W"]["n"]) == (1, 5)  # healthy runs of both tiers, pooled
    assert score["S"] == round(0.75 - 0.2, 4)


@pytest.mark.skipif(not all((ROOT / d / "evaluator" / "cases.jsonl").exists() for d, _ in SOURCES.values()),
                    reason="datasets are gitignored")
def test_the_committed_lists_are_a_fresh_draw():
    lists, _ = build()

    for tier, ids in lists.items():
        assert (SUBSET / f"tier{tier}.txt").read_text(encoding="utf-8").split() == ids

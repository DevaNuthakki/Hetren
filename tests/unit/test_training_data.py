"""The Milestone 3 training data follows Amendment 1: examples kept once,
conflicting inputs dropped, targets in the prompt's key order, capped
square-root weights. The datasets are gitignored, so the full build is
checked against the committed manifest only where they exist."""

import json
from pathlib import Path

import pytest

from packages.support_evaluator.training_data import (
    SOURCES, build, deduplicate, step_kind, target_text, verb_weights,
)


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "docs" / "milestone-3" / "train-v1.manifest.json"


def _example(user, verb, tier=1, action="decide"):
    return {"tier": tier, "user": user, "verb": verb, "target": target_text({"action": action, "verb": verb, "args": {}})}


def test_targets_keep_the_prompt_examples_key_order():
    text = target_text({"args": {"id": "T-1", "entity": "ticket"}, "verb": "inspect", "action": "probe"})

    assert text == '{"action": "probe", "verb": "inspect", "args": {"id": "T-1", "entity": "ticket"}}'


def test_step_kinds_mark_steps_after_a_recovery():
    assert step_kind({"input": {"format": "compact-evidence-v1"}, "target": {"action": "probe"}}) == "probe"
    assert step_kind({"input": {"format": "compact-evidence-v2"}, "target": {"action": "decide"}}) == "post_recovery_decide"


def test_duplicates_are_kept_once_and_conflicting_inputs_dropped_entirely():
    rows = [
        _example("a", "no_intervention"), _example("a", "no_intervention"),  # duplicate
        _example("b", "abstain"), _example("b", "abstain"), _example("b", "insufficient_evidence"),  # conflict
        _example("b", "abstain", tier=2),  # same input in the other tier is a different input
    ]
    kept, removed = deduplicate(rows)

    assert [(r["tier"], r["user"]) for r in kept] == [(1, "a"), (2, "b")]
    assert removed == {"duplicates": 1, "conflicting_inputs": 1, "conflicting_examples": 2}


def test_weights_are_capped_square_roots_of_the_median_ratio_and_never_below_one():
    rows = [_example(str(i), "common") for i in range(400)] + [_example(f"m{i}", "middle") for i in range(100)] \
        + [_example(f"r{i}", "rare") for i in range(25)] + [_example("x", "very_rare")]
    weights = verb_weights(rows)  # median of (400, 100, 25, 1) is 62.5

    assert weights["common"] == weights["middle"] == 1.0
    assert weights["rare"] == pytest.approx((62.5 / 25) ** 0.5)
    assert weights["very_rare"] == 3.0


@pytest.mark.skipif(not all((ROOT / d / "hetren_visible.jsonl").exists() for d, _ in SOURCES.values()),
                    reason="datasets are gitignored")
def test_the_build_matches_the_committed_manifest(tmp_path):
    assert build(tmp_path) == json.loads(MANIFEST.read_text(encoding="utf-8"))

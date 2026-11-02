"""Dataset v3 (tier 2) on a tiny plan: layout, leakage, reproducible slots,
splits with held-out compounds, the token budget and episodes."""

import json

import pytest
import tiktoken

from packages.hetren_baselines import rules_policy
from packages.hetren_evidence import TIER2_EVIDENCE_TOKEN_BUDGET, render_evidence
from packages.support_evaluator.audit import label_of, load_dataset, scan_dataset, shortcut_audit
from packages.support_evaluator.cases import COMPOUND_KIND, is_held_out
from packages.support_evaluator.dataset import build_dataset_tier2, label_slot, record_line
from packages.support_evaluator.episodes import prepare, run_episode, score
from packages.support_evaluator.plan import TIER2_WORLD_SEEDS, tier2_slots
from packages.support_evaluator.splits import HELD_OUT_PARTNER, build_splits


# Builds and labels datasets; runs in the slow CI job.
pytestmark = pytest.mark.slow


ENCODING = tiktoken.get_encoding("o200k_base")
SEED = 11
GROUPS = {
    "pairs": (("mapping_swap", "stale_account_record"),),
    "held_out_pairs": (("queue_misconfiguration", "mapping_swap"),),
    "single_kinds": ("merged_account",),
}
PER_CELL = {"compound": 1, "held_out": 1, "single": 2}
WITHHELD = {"compound": 0, "held_out": 0, "single": 1}


@pytest.fixture(scope="module")
def tiny(tmp_path_factory):
    directory = tmp_path_factory.mktemp("dataset") / "v3"
    result = build_dataset_tier2(directory, seed=SEED, per_cell=PER_CELL, withheld_per_cell=WITHHELD,
                                 processes=4, **GROUPS)
    return directory, result


def test_layout_counts_and_tier(tiny):
    directory, result = tiny
    visible, evaluator = load_dataset(directory)
    manifest = result["manifest"]

    assert manifest["plan"]["tier"] == 2 and manifest["counts"]["primary_cases"] == 20
    assert manifest["counts"]["records"] == len(visible)
    assert all(case["tier"] == 2 for case in evaluator)

    for case in evaluator:
        if case["role"] == "primary":
            assert "sequence_label" in case and isinstance(case["redraws"], list)
            assert TIER2_WORLD_SEEDS[0] <= case["planned"]["world_seed"] < TIER2_WORLD_SEEDS[1]
        else:
            assert "redraws" not in case


def test_every_visible_record_passes_leakage_and_marker_scans(tiny):
    report = scan_dataset(*load_dataset(tiny[0]))

    assert report["leak_findings"] == [] and report["marker_findings"] == []
    assert report["non_neutral_ids"] == [] and report["unexpected_visible_keys"] == []


def test_a_slot_relabels_to_identical_records(tiny):
    directory, _ = tiny
    slots = tier2_slots(SEED, PER_CELL, WITHHELD, **GROUPS)
    partial = {}

    for line in directory.with_name(directory.name + ".partial.jsonl").open(encoding="utf-8"):
        row = json.loads(line)
        partial[row.pop("plan_index")] = row

    for index in (0, len(slots) - 1):
        again = label_slot(slots[index], SEED, index)
        strip = lambda r: record_line({**r, "labeling_seconds": None}) if "labeling_seconds" in r else record_line(r)
        assert strip(again["primary"]) == strip(partial[index]["primary"])
        assert [record_line(p) for p in again["partners"]] == [record_line(p) for p in partial[index]["partners"]]


def test_splits_put_held_out_compounds_only_in_test_held_out(tiny, tmp_path):
    directory, _ = tiny
    manifest = build_splits(directory, tmp_path / "splits", seed=3, validation_fraction=0.3, test_fraction=0.3)
    _, evaluator = load_dataset(directory)
    by_id = {case["case_id"]: case for case in evaluator}
    dropped = dict(line.split("\t") for line in (tmp_path / "splits" / "dropped.tsv").read_text().splitlines())

    for split in ("train", "validation", "test_in_distribution", "test_held_out"):
        for case_id in (tmp_path / "splits" / f"{split}.txt").read_text().split():
            case = by_id[case_id]
            held_out = is_held_out(case["truth"]["case_kind"], case["truth"]["case_variant"])

            # Held-out primaries go to test_held_out with all their partners;
            # nothing held out appears anywhere else.
            if case["role"] == "primary":
                assert held_out == (split == "test_held_out"), case_id
            elif split != "test_held_out":
                assert not held_out, case_id

    assert manifest["counts"]["test_held_out"]["primary_cases"] == 5
    assert all(reason in (HELD_OUT_PARTNER, "seed reserved for held-out") for reason in dropped.values())


def test_inputs_fit_the_tier2_token_budget(tiny):
    visible, _ = load_dataset(tiny[0])
    largest = max(len(ENCODING.encode(render_evidence(s["input"]))) for r in visible for s in r["steps"])
    assert largest <= TIER2_EVIDENCE_TOKEN_BUDGET


def test_episodes_rebuild_tier2_records_and_replay_their_labels(tiny):
    visible, evaluator = load_dataset(tiny[0])

    for record, case in zip(visible, evaluator):
        if case["role"] != "primary":
            continue

        prepared = prepare(record, case)
        queue = [s["target"] for s in record["steps"]]
        row = score(prepared, run_episode(lambda compact: queue.pop(0), prepared))
        assert row["correct"] and row["exact"] and row["tier"] == 2, case["case_id"]
        score(prepared, run_episode(rules_policy, prepared, max_recoveries=1))  # frozen rules v1 runs


def test_tags_and_shortcut_audit_use_the_whole_label(tiny):
    directory, _ = tiny
    visible, evaluator = load_dataset(directory)
    tags = [json.loads(line) for line in (directory / "evaluator" / "tags.jsonl").open(encoding="utf-8")]
    primaries = [(r, c) for r, c in zip(visible, evaluator) if c["role"] == "primary"]

    assert len(tags) == len(primaries)

    for tag, (record, case) in zip(tags, primaries):
        assert tag["recoveries"] == sum(s["target"]["action"] == "recover" for s in record["steps"])
        assert tag["distractors"] == case["planned"].get("distractors", 0)
        assert tag["held_out"] == is_held_out(case["truth"]["case_kind"], case["truth"]["case_variant"])
        assert tag["compound_pair"] == (case["truth"]["case_kind"] == COMPOUND_KIND)

    assert any(">" in label_of(r) for r, _ in primaries)  # a two-step label: recovery, then stop or recovery
    assert {r.feature for r in shortcut_audit(visible, evaluator, ENCODING)} >= {"ticket_text", "input_tokens"}

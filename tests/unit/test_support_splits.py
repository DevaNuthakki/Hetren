"""Split assignment rules, and the committed frozen split files.

The committed lists live in ``docs/milestone-2/splits-v1``; the dataset they
index is gitignored, so the second group of tests checks only the files
against their own manifest and the dataset manifest.
"""

from collections import defaultdict
import hashlib
import json
from pathlib import Path

from packages.support_evaluator.splits import (
    DROPPED_FILE,
    HELD_OUT_PARTNER,
    SEED_RESERVED,
    SPLITS,
    assign_splits,
)


ROOT = Path(__file__).resolve().parents[2]
SPLIT_DIR = ROOT / "docs" / "milestone-2" / "splits-v1"
DATASET_MANIFEST = ROOT / "docs" / "milestone-2" / "dataset-v2.manifest.json"


def primary(case_id, kind, world_seed, group=None):
    return {
        "case_id": case_id, "role": "primary", "twin_group_id": group,
        "planned": {"case_kind": kind, "world_seed": world_seed},
    }


def partner(case_id, of, counterfactual, group):
    return {
        "case_id": case_id, "role": "partner", "primary_case_id": of,
        "counterfactual": counterfactual, "twin_group_id": group,
    }


def synthetic():
    cases = []

    for i in range(200):
        kind = ("mapping_swap", "recent_tier_change", "queue_misconfiguration")[i % 3]
        cases.append(primary(f"p{i}", kind, world_seed=i, group=f"g{i}"))
        cases.append(partner(f"q{i}", f"p{i}", "queue_misconfiguration/0", f"g{i}"))
        cases.append(partner(f"r{i}", f"p{i}", "clean_world/0", f"g{i}"))

    # A non-held-out case sharing a world with a held-out one, with a partner.
    cases.append(primary("shared", "mapping_swap", world_seed=2, group="gs"))
    cases.append(partner("shared-partner", "shared", "clean_world/0", "gs"))
    return cases


def assign(cases, seed=0):
    return assign_splits(cases, seed=seed, validation_fraction=0.2, test_fraction=0.2)


def test_held_out_test_contains_exactly_the_held_out_families():
    cases = synthetic()
    split_of, dropped = assign(cases)
    by_id = {c["case_id"]: c for c in cases}

    for case_id, split in split_of.items():
        case = by_id[case_id]

        if case["role"] == "primary":
            assert (split == "test_held_out") == (case["planned"]["case_kind"] == "queue_misconfiguration"), case_id
        elif case["counterfactual"].startswith("queue_misconfiguration"):
            assert split == "test_held_out", case_id

    assert dropped["shared"] == dropped["shared-partner"] == SEED_RESERVED
    assert {c for c, reason in dropped.items() if reason == HELD_OUT_PARTNER} == {
        f"q{i}" for i in range(200) if split_of[f"p{i}"] != "test_held_out"
    }
    assert set(split_of) | set(dropped) == set(by_id)
    assert not set(split_of) & set(dropped)


def test_partners_follow_their_primary_and_worlds_do_not_cross_splits():
    cases = synthetic()
    split_of, _ = assign(cases)
    seeds = defaultdict(set)

    for case in cases:
        if case["case_id"] not in split_of:
            continue

        if case["role"] == "partner":
            assert split_of[case["case_id"]] == split_of[case["primary_case_id"]]
        else:
            seeds[case["planned"]["world_seed"]].add(split_of[case["case_id"]])

    assert all(len(splits) == 1 for splits in seeds.values())
    assert set(split_of.values()) == set(SPLITS)


def test_assignment_is_deterministic_and_seeded():
    cases = synthetic()
    first, _ = assign(cases)

    assert assign(cases)[0] == first
    assert assign(cases, seed=1)[0] != first


def test_committed_split_files_match_their_manifest():
    manifest = json.loads((SPLIT_DIR / "manifest.json").read_text(encoding="utf-8"))
    dataset = json.loads(DATASET_MANIFEST.read_text(encoding="utf-8"))
    members = {}

    for name, digest in manifest["files"].items():
        data = (SPLIT_DIR / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == digest, name
        lines = data.decode("utf-8").splitlines()
        members[name] = [line.split("\t")[0] for line in lines]

        if name == DROPPED_FILE:
            assert {line.split("\t")[1] for line in lines} <= {HELD_OUT_PARTNER, SEED_RESERVED}

    assert manifest["dataset"]["files"] == dataset["files"]
    assert manifest["dataset"]["plan"] == dataset["plan"]

    ids = [case_id for ids in members.values() for case_id in ids]
    assert len(ids) == len(set(ids)) == dataset["counts"]["records"]

    for split in SPLITS:
        counts = manifest["counts"][split]
        assert len(members[f"{split}.txt"]) == counts["primary_cases"] + counts["partner_records"]

    assert set(manifest["counts"]["test_held_out"]["by_kind"]) == {"queue_misconfiguration", "tier_format_drift"}
    kept_primaries = sum(manifest["counts"][s]["primary_cases"] for s in SPLITS)
    assert 0 <= dataset["counts"]["primary_cases"] - kept_primaries <= manifest["dropped"].get(SEED_RESERVED, 0)

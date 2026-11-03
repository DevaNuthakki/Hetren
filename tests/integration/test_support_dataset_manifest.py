"""The committed dataset manifests reproduce: re-labelling sampled cases from
the recorded plan yields byte-identical records.

The data itself is gitignored (``artifacts/milestone-2/dataset-v2`` and
``dataset-v3``); these tests need only the manifests.
"""

import hashlib
import json
from multiprocessing import get_context
from pathlib import Path

import pytest

from environments.support.generator import GENERATOR_NAME, GENERATOR_VERSION
from packages.support_evaluator.dataset import (
    DATASET_FORMAT,
    DATASET_FORMAT_VERSION,
    label_planned,
    label_slot,
    record_line,
)
from packages.support_evaluator.plan import cross_plan, tier2_slots


# Builds and labels datasets; runs in the slow CI job.
pytestmark = pytest.mark.slow


DOCS = Path(__file__).resolve().parents[2] / "docs" / "milestone-2"
MANIFEST = DOCS / "dataset-v2.manifest.json"
MANIFEST_V3 = DOCS / "dataset-v3.manifest.json"


@pytest.fixture(scope="module")
def manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def plan(manifest):
    parameters = manifest["plan"]
    kinds = None if parameters["kinds"] == "default" else tuple(parameters["kinds"])
    return cross_plan(
        parameters["per_cell"], parameters["seed"],
        kinds=kinds, withheld_per_cell=parameters["withheld_per_cell"],
    )


def test_manifest_matches_the_current_code(manifest, plan):
    assert (manifest["format"], manifest["format_version"]) == (DATASET_FORMAT, DATASET_FORMAT_VERSION)
    assert manifest["generator"] == {"name": GENERATOR_NAME, "version": GENERATOR_VERSION}
    assert manifest["counts"]["primary_cases"] == len(plan)
    assert set(manifest["files"]) == {"hetren_visible.jsonl", "evaluator/cases.jsonl", "evaluator/tags.jsonl"}
    positions = [entry["position"] for entry in manifest["sample"]]
    assert positions.count(0) >= 8 and any(p > 0 for p in positions)


def _check_sample_entry(entry, result):
    record = [result["primary"], *result["partners"]][entry["position"]]
    extra = {"primary_case_id": entry["primary_case_id"]} if entry["position"] else {}

    visible_line = record_line({"case_id": entry["case_id"], **record["visible"]})
    evaluator_line = record_line({"case_id": entry["case_id"], **record["evaluator"], **extra})

    assert hashlib.sha256(visible_line.encode("utf-8")).hexdigest() == entry["visible_line_sha256"], entry["case_id"]
    assert hashlib.sha256(evaluator_line.encode("utf-8")).hexdigest() == entry["evaluator_line_sha256"], entry["case_id"]


def test_regenerated_sample_records_match_the_manifest_hashes(manifest, plan):
    for entry in manifest["sample"]:
        _check_sample_entry(entry, label_planned(plan[entry["plan_index"]]))


def _label_v3_slot(item):
    slot, seed, index = item
    return label_slot(slot, seed, index)


def test_v3_manifest_sample_relabels_from_the_tier2_plan():
    manifest = json.loads(MANIFEST_V3.read_text(encoding="utf-8"))
    seed = manifest["plan"]["seed"]
    slots = tier2_slots(seed)

    assert manifest["plan"]["tier"] == 2 and manifest["counts"]["primary_cases"] == len(slots)
    assert (manifest["format"], manifest["format_version"]) == (DATASET_FORMAT, DATASET_FORMAT_VERSION)
    assert manifest["generator"] == {"name": GENERATOR_NAME, "version": GENERATOR_VERSION}

    # Tier 2 slots take up to ~100 s each to label; label them in parallel.
    entries = manifest["sample"]
    with get_context("spawn").Pool(4) as pool:
        results = pool.map(_label_v3_slot, [(slots[e["plan_index"]], seed, e["plan_index"]) for e in entries], chunksize=1)

    for entry, result in zip(entries, results):
        _check_sample_entry(entry, result)

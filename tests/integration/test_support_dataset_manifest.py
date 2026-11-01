"""The committed dataset manifest reproduces: re-labelling sampled cases from
the recorded plan yields byte-identical records.

The data itself is gitignored (``artifacts/milestone-2/dataset-v1``); this
test needs only the manifest.
"""

import hashlib
import json
from pathlib import Path

import pytest

from environments.support.generator import GENERATOR_NAME, GENERATOR_VERSION
from packages.support_evaluator.dataset import (
    DATASET_FORMAT,
    DATASET_FORMAT_VERSION,
    label_planned,
    record_line,
)
from packages.support_evaluator.plan import cross_plan


# Builds and labels datasets; runs in the slow CI job.
pytestmark = pytest.mark.slow


MANIFEST = Path(__file__).resolve().parents[2] / "docs" / "milestone-2" / "dataset-v2.manifest.json"


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


def test_regenerated_sample_records_match_the_manifest_hashes(manifest, plan):
    for entry in manifest["sample"]:
        result = label_planned(plan[entry["plan_index"]])
        record = [result["primary"], *result["partners"]][entry["position"]]
        extra = {"primary_case_id": entry["primary_case_id"]} if entry["position"] else {}

        visible_line = record_line({"case_id": entry["case_id"], **record["visible"]})
        evaluator_line = record_line({"case_id": entry["case_id"], **record["evaluator"], **extra})

        assert hashlib.sha256(visible_line.encode("utf-8")).hexdigest() == entry["visible_line_sha256"], entry["case_id"]
        assert hashlib.sha256(evaluator_line.encode("utf-8")).hexdigest() == entry["evaluator_line_sha256"], entry["case_id"]

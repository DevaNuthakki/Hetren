"""The rules v1 runner: the same rows as scoring each case directly,
resumable, and refusing to mix metadata."""

import argparse
import json

import pytest

from packages.hetren_baselines import rules_policy
from packages.support_evaluator.dataset import build_dataset
from packages.support_evaluator.episodes import prepare, run_episode, score
from packages.support_evaluator.rules_baseline import run_rules


# Builds and labels a dataset; runs in the slow CI job.
pytestmark = pytest.mark.slow

METADATA = {"policy": "rules", "rules_policy_version": 1, "max_recoveries": 1, "commit": "test"}


@pytest.fixture(scope="module")
def tiny(tmp_path_factory):
    directory = tmp_path_factory.mktemp("dataset") / "v2"
    build_dataset(directory, per_cell=1, seed=5, processes=1, kinds=("mapping_swap", "stale_account_record"))
    pairs = [(json.loads(v), json.loads(e)) for v, e in zip((directory / "hetren_visible.jsonl").open(),
                                                           (directory / "evaluator" / "cases.jsonl").open())]
    primaries = [(v, e) for v, e in pairs if e["role"] == "primary"]
    split = directory / "test_in_distribution.txt"
    split.write_text("".join(v["case_id"] + "\n" for v, _ in primaries))
    return directory, split, primaries


def _args(directory, split, out):
    return argparse.Namespace(dataset=directory, split=split, live=None, out=out, processes=2)


def test_rows_equal_direct_scoring_and_resume(tiny, tmp_path):
    directory, split, primaries = tiny
    assert run_rules(_args(directory, split, tmp_path), METADATA) == 0

    rows = [json.loads(line) for line in (tmp_path / "rows-tier1-test_in_distribution.jsonl").open()]
    direct = []

    for v, e in primaries:
        prepared = prepare(v, e)
        direct.append(score(prepared, run_episode(rules_policy, prepared, max_recoveries=1)))

    assert rows == [json.loads(json.dumps(r, sort_keys=True)) for r in direct]
    summary = json.loads((tmp_path / "summary-tier1-test_in_distribution.json").read_text())
    assert summary["cases"] == len(primaries)

    # A restart scores nothing again; different metadata is refused.
    assert run_rules(_args(directory, split, tmp_path), METADATA) == 0
    assert len((tmp_path / "rows-tier1-test_in_distribution.jsonl").read_text().splitlines()) == len(primaries)
    assert run_rules(_args(directory, split, tmp_path), {**METADATA, "rules_policy_version": 2}) == 2

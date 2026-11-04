"""A candidate checkpoint's subset evaluation, offline (fake generator, no
GPU): the fp16 smoke test first, then the subset cases of both tiers through
the small model runner, ``selection.json`` with S and every output's hash,
and a restart that resumes without new calls. A failed smoke test stops
before the subset run."""

import json
import shutil

import pytest

from packages.support_evaluator import checkpoint_selection as selection
from packages.support_evaluator.checkpoint_selection import evaluate, validate
from packages.support_evaluator.dataset import build_dataset
from packages.support_evaluator.local_model_baseline import EXIT_SMOKE_FAILED
from packages.support_evaluator.selection_subset import SOURCES
from tests.integration.test_local_model_baseline import LabelReplay, METADATA, no_network  # noqa: F401


# Builds and labels a dataset; runs in the slow CI job.
pytestmark = pytest.mark.slow

CANDIDATE = {"checkpoint": "checkpoint-0528", "step": 528, "state_sha256": "s", "adapter_sha256": "a"}


@pytest.fixture(scope="module")
def tiny(tmp_path_factory):
    """Faulty and healthy primaries (W needs at least one healthy run)."""
    directory = tmp_path_factory.mktemp("dataset") / "v2"
    build_dataset(directory, per_cell=1, seed=5, processes=1, kinds=("mapping_swap", "transient_error_retried"))
    visible = [json.loads(line) for line in (directory / "hetren_visible.jsonl").open(encoding="utf-8")]
    evaluator = [json.loads(line) for line in (directory / "evaluator" / "cases.jsonl").open(encoding="utf-8")]
    return directory, [v for v, e in zip(visible, evaluator) if e["role"] == "primary"]


@pytest.fixture
def subset(tiny, tmp_path):
    """Both tiers' sources point at the tiny dataset; the subset lists split its primaries."""
    directory, primaries = tiny
    root = tmp_path / "root"

    for tier in (1, 2):
        shutil.copytree(directory, root / SOURCES[tier][0])

    lists = tmp_path / "subset"
    lists.mkdir()
    half = len(primaries) // 2
    (lists / "tier1.txt").write_text("".join(v["case_id"] + "\n" for v in primaries[:half]), encoding="utf-8")
    (lists / "tier2.txt").write_text("".join(v["case_id"] + "\n" for v in primaries[half:]), encoding="utf-8")
    return root, lists, {1: half, 2: len(primaries) - half}, primaries


def test_smoke_then_subset_then_score_and_resume(subset, tmp_path):
    root, lists, sizes, primaries = subset
    out = tmp_path / "out"
    model = LabelReplay(primaries)

    assert evaluate(CANDIDATE, out, model, METADATA, root=root, subset_dir=lists, sizes=sizes) == 0

    result = json.loads((out / "selection.json").read_text(encoding="utf-8"))
    assert result["S"] == 1.0 and result["A1"]["rate"] == result["A2"]["rate"] == 1.0  # the labels themselves
    assert result["cases"] == {"tier1": sizes[1], "tier2": sizes[2]} and result["checkpoint"] == "checkpoint-0528"
    assert result["calls"]["non_finite"] == 0 and result["metadata"]["candidate"] == CANDIDATE
    assert {"smoke-tier1-tier1/smoke_report.json", "smoke-tier1-tier2/smoke_report.json", "rows-tier1-tier1.jsonl",
            "rows-tier1-tier2.jsonl", "calls.jsonl", "metadata.json"} <= set(result["files"])

    calls = len(model.prompts)
    assert evaluate(CANDIDATE, out, model, METADATA, root=root, subset_dir=lists, sizes=sizes) == 0
    assert len(model.prompts) == calls  # resumed: nothing re-run
    assert json.loads((out / "selection.json").read_text(encoding="utf-8"))["S"] == 1.0


def test_a_failed_smoke_test_stops_before_the_subset_run(subset, tmp_path):
    root, lists, sizes, primaries = subset
    out = tmp_path / "out"

    assert evaluate(CANDIDATE, out, LabelReplay(primaries, finite=False), METADATA, root=root, subset_dir=lists,
                    sizes=sizes) == EXIT_SMOKE_FAILED
    assert not list(out.glob("rows-*.jsonl")) and not (out / "selection.json").exists()


CHOICE = {"chosen": "checkpoint-0528", "S": 0.7, "state_sha256": "s", "adapter_sha256": "a"}


@pytest.fixture
def validation(tiny, tmp_path):
    """Tier 1's source and validation split point at the tiny dataset and all its primaries."""
    directory, primaries = tiny
    root = tmp_path / "root"
    shutil.copytree(directory, root / SOURCES[1][0])
    split = root / SOURCES[1][1]
    split.parent.mkdir(parents=True)
    split.write_text("".join(v["case_id"] + "\n" for v in primaries), encoding="utf-8")
    return root, primaries


def test_the_chosen_checkpoint_runs_the_full_validation_split_smoke_test_first(validation, tmp_path):
    root, primaries = validation
    out = tmp_path / "tier1"

    assert validate(CANDIDATE, CHOICE, 1, out, LabelReplay(primaries), METADATA, root=root,
                    sizes={1: len(primaries)}) == 0

    result = json.loads((out / "validation-tier1.json").read_text(encoding="utf-8"))
    assert result["cases"] == len(primaries) and result["decision_accuracy"]["rate"] == 1.0
    assert result["wrong_interventions_on_healthy"]["k"] == 0 and set(result["monitoring"]) == {
        "insufficient_evidence_precision", "abstain_recall"}
    assert "smoke-tier1-validation/smoke_report.json" in result["files"] and "rows-tier1-validation.jsonl" in result["files"]


def test_only_the_chosen_checkpoint_runs_on_full_validation(validation, tmp_path):
    root, primaries = validation
    model = LabelReplay(primaries)

    assert validate({**CANDIDATE, "adapter_sha256": "b"}, CHOICE, 1, tmp_path / "tier1", model, METADATA, root=root,
                    sizes={1: len(primaries)}) == 2
    assert not model.prompts


def test_the_chosen_checkpoint_runs_a_test_split_once_and_prints_no_result(validation, tmp_path, capsys):
    root, primaries = validation
    splits = {"tier1-test_held_out": ({"dataset": SOURCES[1][0], "split": SOURCES[1][1]}, len(primaries))}
    model = LabelReplay(primaries)
    out = tmp_path / "test"

    assert selection.test_split(CANDIDATE, CHOICE, "tier1-test_held_out", out, model, METADATA, root=root,
                                splits=splits) == 0
    assert "complete" in capsys.readouterr().out.splitlines()[-1]
    assert json.loads((out / "metadata.json").read_text(encoding="utf-8"))["test_split"] == "tier1-test_held_out"
    assert not (out / "smoke-tier1-validation").exists()  # no smoke test on test splits

    calls = len(model.prompts)
    assert selection.test_split(CANDIDATE, CHOICE, "tier1-test_held_out", out, model, METADATA, root=root,
                                splits=splits) == 0
    assert len(model.prompts) == calls  # a restart only completes the same split

    other = LabelReplay(primaries)
    assert selection.test_split({**CANDIDATE, "state_sha256": "t"}, CHOICE, "tier1-test_held_out", tmp_path / "other",
                                other, METADATA, root=root, splits=splits) == 2
    assert not other.prompts


def test_another_adapter_cannot_resume_the_same_output(subset, tmp_path):
    root, lists, sizes, primaries = subset
    out = tmp_path / "out"
    evaluate(CANDIDATE, out, LabelReplay(primaries), METADATA, root=root, subset_dir=lists, sizes=sizes)

    assert evaluate({**CANDIDATE, "adapter_sha256": "b"}, out, LabelReplay(primaries), METADATA, root=root,
                    subset_dir=lists, sizes=sizes) == 2

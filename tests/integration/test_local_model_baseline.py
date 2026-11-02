"""The small model baseline runner, fully offline (fake generator, no GPU).

- Runs episodes with the shared prompt, logs every call with its fp16
  checks, records metadata, writes rows and a summary, and resumes.
- Refuses to resume with different settings; a generation error stops the
  run without scoring the episode.
- The fp16 smoke test passes only when every call's logits are finite and
  no reply is empty.
"""

import argparse
import json
import socket

import pytest

from packages.hetren_baselines.local_model import Generation, library_versions
from packages.hetren_baselines.prompt import system_prompt
from packages.hetren_evidence import render_evidence
from packages.support_evaluator import local_model_baseline as runner
from packages.support_evaluator.dataset import build_dataset


# Builds and labels a dataset; runs in the slow CI job.
pytestmark = pytest.mark.slow


METADATA = {"model": "fake", "revision": "0", "dtype": "float16", "max_new_tokens": 128, "decoding": "greedy",
            "libraries": {"python": "3"}}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("network access attempted in an offline test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


@pytest.fixture(scope="module")
def tiny(tmp_path_factory):
    directory = tmp_path_factory.mktemp("dataset") / "v2"
    build_dataset(directory, per_cell=1, seed=5, processes=1, kinds=("mapping_swap",))
    visible = [json.loads(line) for line in (directory / "hetren_visible.jsonl").open(encoding="utf-8")]
    evaluator = [json.loads(line) for line in (directory / "evaluator" / "cases.jsonl").open(encoding="utf-8")]
    primaries = [v for v, e in zip(visible, evaluator) if e["role"] == "primary"]
    split = directory / "split.txt"
    split.write_text("".join(v["case_id"] + "\n" for v in primaries), encoding="utf-8")
    return directory, split, primaries


def _args(directory, split, out, smoke=None):
    return argparse.Namespace(dataset=directory, split=split, out=out, smoke=smoke, limit=None)


class LabelReplay:
    """A fake model that answers every step input with the label's action."""

    def __init__(self, primaries, finite=True, text=None):
        self.answers = {render_evidence(s["input"]): s["target"] for v in primaries for s in v["steps"]}
        self.prompts = []
        self.finite = finite
        self.text = text

    def __call__(self, system, user):
        self.prompts.append((system, user))
        text = self.text if self.text is not None else json.dumps(self.answers[user])
        return Generation(text=text, prompt_tokens=1800, new_tokens=30, finite=self.finite, at_limit=False)


def test_scores_logs_and_resumes(tiny, tmp_path):
    directory, split, primaries = tiny
    model = LabelReplay(primaries)

    assert runner.run_baseline(_args(directory, split, tmp_path), model, METADATA) == 0

    steps = sum(len(v["steps"]) for v in primaries)
    assert len(model.prompts) == steps and all(system == system_prompt(1) for system, _ in model.prompts)
    rows = [json.loads(line) for line in (tmp_path / "rows-tier1.jsonl").open(encoding="utf-8")]
    assert len(rows) == len(primaries) and all(r["correct"] and r["exact"] for r in rows)
    calls = [json.loads(line) for line in (tmp_path / "calls.jsonl").open(encoding="utf-8")]
    assert len(calls) == steps and all(c["finite"] and not c["discarded"] for c in calls)
    assert json.loads((tmp_path / "metadata.json").read_text())["prompt_version"] == 1
    assert (tmp_path / "summary-tier1.json").exists()

    # A restart scores nothing again; different settings are refused.
    assert runner.run_baseline(_args(directory, split, tmp_path), model, METADATA) == 0
    assert len(model.prompts) == steps
    assert runner.run_baseline(_args(directory, split, tmp_path), model, {**METADATA, "dtype": "float32"}) == 2


def test_generation_errors_stop_without_scoring(tiny, tmp_path):
    directory, split, _ = tiny

    def fails(system, user):
        raise RuntimeError("CUDA out of memory")

    assert runner.run_baseline(_args(directory, split, tmp_path), fails, METADATA) == runner.EXIT_GENERATION_ERROR
    assert not (tmp_path / "rows-tier1.jsonl").exists()


def test_smoke_passes_on_finite_logits_and_reports_parse_failures(tiny, tmp_path):
    directory, split, primaries = tiny

    assert runner.run_baseline(_args(directory, split, tmp_path, smoke=3), LabelReplay(primaries), METADATA) == 0
    report = json.loads((tmp_path / "smoke-tier1" / "smoke_report.json").read_text())
    assert report["cases"] == 3 and report["fp16_ok"] and report["non_finite_calls"] == 0

    # Unparsable replies are the untrained model's failures, not a precision failure.
    garbled = LabelReplay(primaries, text="I think the ticket is fine.")
    assert runner.run_baseline(_args(directory, split, tmp_path / "garbled", smoke=3), garbled, METADATA) == 0
    report = json.loads((tmp_path / "garbled" / "smoke-tier1" / "smoke_report.json").read_text())
    assert report["fp16_ok"] and report["invalid_action_episodes"] == 3


@pytest.mark.parametrize("model_kwargs", [{"finite": False}, {"text": ""}])
def test_smoke_fails_on_non_finite_logits_or_empty_replies(tiny, tmp_path, model_kwargs):
    directory, split, primaries = tiny
    model = LabelReplay(primaries, **model_kwargs)

    assert runner.run_baseline(_args(directory, split, tmp_path, smoke=3), model, METADATA) == runner.EXIT_SMOKE_FAILED
    assert not json.loads((tmp_path / "smoke-tier1" / "smoke_report.json").read_text())["fp16_ok"]


def test_library_versions_need_no_gpu_libraries():
    versions = library_versions()
    assert "python" in versions and "torch" in versions

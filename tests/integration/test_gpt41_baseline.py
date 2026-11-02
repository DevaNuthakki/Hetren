"""The gpt-4.1 baseline runner, fully offline (fake Responses API, no network).

- Refuses to start without ``--confirm-live``, a positive cap and a key.
- Runs episodes with the shared prompt, logs every call, keeps a ledger,
  writes scored rows and a summary, and resumes without repeating calls.
- Stops before a call that could pass the cap, and on API errors, without
  scoring the episode.
"""

import argparse
import json
import socket
from types import SimpleNamespace

import pytest
import tiktoken

from packages.hetren_baselines.prompt import action_text, system_prompt
from packages.hetren_evidence import render_evidence
from packages.support_evaluator import gpt41_baseline
from packages.support_evaluator.dataset import build_dataset


# Builds and labels a dataset; runs in the slow CI job.
pytestmark = pytest.mark.slow


ENCODING = tiktoken.get_encoding("o200k_base")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("network access attempted in an offline test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def _script():
    return gpt41_baseline


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


def _args(directory, split, out, max_usd=5.0, **extra):
    return argparse.Namespace(
        dataset=directory, split=split, out=out, model="gpt-4.1-2025-04-14", max_usd=max_usd, limit=None,
        input_usd_per_mtok=2.0, output_usd_per_mtok=8.0, confirm_live=True, **extra,
    )


class LabelReplay:
    """A fake Responses API that answers every step input with the label's action."""

    def __init__(self, primaries):
        self.answers = {render_evidence(s["input"]): s["target"] for v in primaries for s in v["steps"]}
        self.requests = []

    def __call__(self, **request):
        self.requests.append(request)
        reply = "```json\n" + json.dumps(self.answers[request["input"]]) + "\n```"
        usage = SimpleNamespace(input_tokens=1500, output_tokens=30, input_tokens_details=SimpleNamespace(cached_tokens=1024))
        return SimpleNamespace(output_text=reply, usage=usage)


def test_refuses_without_confirmation_cap_or_key(tmp_path, monkeypatch, capsys):
    script = _script()
    base = ["--dataset", str(tmp_path), "--split", str(tmp_path), "--out", str(tmp_path / "out")]

    assert script.main(base + ["--max-usd", "1"]) == 2
    assert script.main(base + ["--confirm-live"]) == 2
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert script.main(base + ["--confirm-live", "--max-usd", "1"]) == 2
    assert not (tmp_path / "out").exists()


def test_scores_logs_and_resumes(tiny, tmp_path):
    directory, split, primaries = tiny
    script = _script()
    fake = LabelReplay(primaries)

    assert script.run_baseline(_args(directory, split, tmp_path), fake, ENCODING) == 0

    steps = sum(len(v["steps"]) for v in primaries)
    assert len(fake.requests) == steps
    assert all(r["instructions"] == system_prompt(1) and r["store"] is False and r["temperature"] == 0
               and r["max_output_tokens"] == 128 for r in fake.requests)

    rows = [json.loads(line) for line in (tmp_path / "rows-tier1.jsonl").open(encoding="utf-8")]
    assert len(rows) == len(primaries) and all(r["correct"] and r["exact"] for r in rows)
    ledger = json.loads((tmp_path / "ledger.json").read_text(encoding="utf-8"))
    assert ledger["spend"]["calls"] == steps and ledger["spend"]["input_tokens"] == 1500 * steps
    calls = [json.loads(line) for line in (tmp_path / "calls.jsonl").open(encoding="utf-8")]
    assert len(calls) == steps and not any(c["discarded"] or c["at_output_limit"] for c in calls)
    assert json.loads((tmp_path / "summary-tier1.json").read_text())["decision_accuracy"]["k"] == len(primaries)

    # A restart scores nothing again.
    assert script.run_baseline(_args(directory, split, tmp_path), fake, ENCODING) == 0
    assert len(fake.requests) == steps


def test_stops_before_a_call_that_could_pass_the_cap(tiny, tmp_path):
    directory, split, primaries = tiny
    script = _script()
    fake = LabelReplay(primaries)

    # One call costs at most about (1,700 input x 1.1) at $2/M + 128 output at $8/M = $0.0048.
    assert script.run_baseline(_args(directory, split, tmp_path, max_usd=0.004), fake, ENCODING) == script.EXIT_BUDGET
    assert fake.requests == [] and not (tmp_path / "rows-tier1.jsonl").exists()


def test_api_errors_stop_without_scoring(tiny, tmp_path):
    directory, split, _ = tiny
    script = _script()

    def fails(**request):
        raise ConnectionError("service unavailable")

    assert script.run_baseline(_args(directory, split, tmp_path), fails, ENCODING) == script.EXIT_API_ERROR
    assert not (tmp_path / "rows-tier1.jsonl").exists()


def test_action_text_strips_one_fence_only():
    assert action_text('  {"a": 1}\n') == '{"a": 1}'
    assert action_text('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert action_text('```\n{"a": 1}\n```') == '{"a": 1}'
    assert action_text('Answer: {"a": 1}') == 'Answer: {"a": 1}'

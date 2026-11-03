"""The gpt-4.1 baseline runner, fully offline (fake Responses API, no network).

- Refuses to start without ``--confirm-live``, a positive cap and a key.
- Runs episodes with the shared prompt, logs every call, keeps a ledger,
  writes scored rows and a summary, and resumes without repeating calls.
- Stops before a call that could pass the cap, and on API errors, without
  scoring the episode.
"""

import argparse
import json
import shutil
import socket
from types import SimpleNamespace

import pytest
import tiktoken

from packages.hetren_baselines.prompt import action_text, system_prompt
from packages.hetren_evidence import render_evidence
from packages.support_evaluator import case_sources, gpt41_baseline
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

    rows = [json.loads(line) for line in (tmp_path / "rows-tier1-split.jsonl").open(encoding="utf-8")]
    assert len(rows) == len(primaries) and all(r["correct"] and r["exact"] for r in rows)
    ledger = json.loads((tmp_path / "ledger.json").read_text(encoding="utf-8"))
    assert ledger["spend"]["calls"] == steps and ledger["spend"]["input_tokens"] == 1500 * steps
    calls = [json.loads(line) for line in (tmp_path / "calls.jsonl").open(encoding="utf-8")]
    assert len(calls) == steps and not any(c["discarded"] or c["at_output_limit"] for c in calls)
    assert json.loads((tmp_path / "summary-tier1-split.json").read_text())["decision_accuracy"]["k"] == len(primaries)

    # A restart scores nothing again.
    assert script.run_baseline(_args(directory, split, tmp_path), fake, ENCODING) == 0
    assert len(fake.requests) == steps


def test_stops_before_a_call_that_could_pass_the_cap(tiny, tmp_path):
    directory, split, primaries = tiny
    script = _script()
    fake = LabelReplay(primaries)

    # One call costs at most about (1,700 input x 1.1) at $2/M + 128 output at $8/M = $0.0048.
    assert script.run_baseline(_args(directory, split, tmp_path, max_usd=0.004), fake, ENCODING) == script.EXIT_BUDGET
    assert fake.requests == [] and not (tmp_path / "rows-tier1-split.jsonl").exists()


def test_api_errors_stop_without_scoring(tiny, tmp_path):
    directory, split, _ = tiny
    script = _script()

    def fails(**request):
        raise ConnectionError("service unavailable")

    assert script.run_baseline(_args(directory, split, tmp_path), fails, ENCODING) == script.EXIT_API_ERROR
    assert not (tmp_path / "rows-tier1-split.jsonl").exists()


def test_action_text_strips_one_fence_only():
    assert action_text('  {"a": 1}\n') == '{"a": 1}'
    assert action_text('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert action_text('```\n{"a": 1}\n```') == '{"a": 1}'
    assert action_text('Answer: {"a": 1}') == 'Answer: {"a": 1}'


def test_a_case_logged_but_not_scored_is_replayed_without_new_calls(tiny, tmp_path, monkeypatch):
    directory, split, primaries = tiny
    script = _script()
    fake = LabelReplay(primaries)
    real_score = case_sources.score

    def crash(prepared, episode):
        raise RuntimeError("scoring crashed")

    # The run stops while scoring its first case, after paying for its calls.
    monkeypatch.setattr(case_sources, "score", crash)
    with pytest.raises(RuntimeError, match="scoring crashed"):
        script.run_baseline(_args(directory, split, tmp_path), fake, ENCODING)

    paid = len(fake.requests)
    ledger = json.loads((tmp_path / "ledger.json").read_text(encoding="utf-8"))["spend"]
    assert paid == len(primaries[0]["steps"]) and not (tmp_path / "rows-tier1-split.jsonl").exists()

    # Resuming scores that case from its logged replies: no new calls, same ledger, no duplicate log lines.
    monkeypatch.setattr(case_sources, "score", real_score)
    assert script.run_baseline(_args(directory, split, tmp_path), fake, ENCODING) == 0

    rows = [json.loads(line) for line in (tmp_path / "rows-tier1-split.jsonl").open(encoding="utf-8")]
    assert rows[0]["case_id"] == primaries[0]["case_id"] and rows[0]["correct"]
    steps = sum(len(v["steps"]) for v in primaries)
    assert len(fake.requests) == steps  # only the other cases were called
    after = json.loads((tmp_path / "ledger.json").read_text(encoding="utf-8"))["spend"]
    assert after["calls"] == ledger["calls"] + steps - paid
    calls = [json.loads(line) for line in (tmp_path / "calls.jsonl").open(encoding="utf-8")]
    assert len(calls) == steps and len({(c["case_id"], c["call"]) for c in calls}) == steps


def _as_tier2_copy(directory, split, tmp_path):
    """The same cases (same case IDs) marked as a tier 2 dataset."""
    copy = tmp_path / "tier2-copy"
    shutil.copytree(directory, copy)
    cases = [json.loads(line) for line in (copy / "evaluator" / "cases.jsonl").open(encoding="utf-8")]
    (copy / "evaluator" / "cases.jsonl").write_text("".join(json.dumps({**c, "tier": 2}) + "\n" for c in cases), encoding="utf-8")
    tags = [json.loads(line) for line in (copy / "evaluator" / "tags.jsonl").open(encoding="utf-8")]
    (copy / "evaluator" / "tags.jsonl").write_text("".join(json.dumps({**t, "compound_pair": False}) + "\n" for t in tags), encoding="utf-8")
    return copy, split


def test_datasets_sharing_case_ids_never_share_logged_calls(tiny, tmp_path):
    directory, split, primaries = tiny
    script = _script()
    out = tmp_path / "out"

    # Tier 1 runs to the end; every case ID now has logged calls.
    tier1 = LabelReplay(primaries)
    assert script.run_baseline(_args(directory, split, out), tier1, ENCODING) == 0

    # Tier 2 has the same case IDs: each case is called afresh, never replayed from tier 1's calls.
    copy, split2 = _as_tier2_copy(directory, split, tmp_path)
    stops = []

    def stop(**request):
        stops.append(request)
        usage = SimpleNamespace(input_tokens=1500, output_tokens=20, input_tokens_details=None)
        return SimpleNamespace(output_text='{"action": "decide", "verb": "no_intervention", "args": {}}', usage=usage)

    assert script.run_baseline(_args(copy, split2, out), stop, ENCODING) == 0
    assert len(stops) == len(primaries)
    assert all(r["instructions"] == system_prompt(2) for r in stops)

    rows = [json.loads(line) for line in (out / "rows-tier2-split.jsonl").open(encoding="utf-8")]
    assert [r["case_id"] for r in rows] == [v["case_id"] for v in primaries]
    assert all(r["final"]["verb"] == "no_intervention" and r["tier"] == 2 for r in rows)

    calls = [json.loads(line) for line in (out / "calls.jsonl").open(encoding="utf-8")]
    assert {c["tier"] for c in calls} == {1, 2} and sum(c["tier"] == 2 for c in calls) == len(primaries)
    ledger = json.loads((out / "ledger.json").read_text(encoding="utf-8"))
    assert set(ledger["datasets"]) == {"1", "2"}


def test_one_dataset_per_tier_and_untagged_logs_stop(tiny, tmp_path):
    directory, split, primaries = tiny
    script = _script()
    out = tmp_path / "out"
    assert script.run_baseline(_args(directory, split, out), LabelReplay(primaries), ENCODING) == 0

    # Another tier 1 dataset in the same output directory is refused.
    other = tmp_path / "other"
    shutil.copytree(directory, other)
    manifest = json.loads((other / "manifest.json").read_text(encoding="utf-8"))
    manifest["files"]["hetren_visible.jsonl"] = "0" * 64
    (other / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert script.run_baseline(_args(other, split, out), LabelReplay(primaries), ENCODING) == 2

    # A call log written before calls carried their tier and dataset is refused.
    calls = [json.loads(line) for line in (out / "calls.jsonl").open(encoding="utf-8")]
    (out / "calls.jsonl").write_text("".join(json.dumps({k: v for k, v in c.items() if k not in ("tier", "dataset", "dataset_sha256")}) + "\n"
                                             for c in calls), encoding="utf-8")
    assert script.run_baseline(_args(directory, split, out), LabelReplay(primaries), ENCODING) == 2


def test_two_splits_of_one_tier_keep_separate_rows_and_summaries(tiny, tmp_path):
    directory, split, primaries = tiny
    script = _script()
    out = tmp_path / "out"
    first, second = tmp_path / "first.txt", tmp_path / "second.txt"
    first.write_text("".join(v["case_id"] + "\n" for v in primaries[:2]))
    second.write_text("".join(v["case_id"] + "\n" for v in primaries[2:]))

    for split_file in (first, second):
        assert script.run_baseline(_args(directory, split_file, out), LabelReplay(primaries), ENCODING) == 0

    assert len((out / "rows-tier1-first.jsonl").read_text().splitlines()) == 2
    assert len((out / "rows-tier1-second.jsonl").read_text().splitlines()) == len(primaries) - 2
    assert json.loads((out / "summary-tier1-second.json").read_text())["cases"] == len(primaries) - 2

    # A directory with rows from before split-named rows is refused.
    (out / "rows-tier1.jsonl").write_text("")
    assert script.run_baseline(_args(directory, first, out), LabelReplay(primaries), ENCODING) == 2

"""Episodes on the live split, fully offline: runs recorded by a fake live
model are labelled, replayed from their captures and scored by category,
and the gpt-4.1 runner covers the live split with ``--live``.

- Proxy-matched runs replay to the live record's first input, and their
  labels verify by execution.
- Final-label-only runs are scored without any agent re-run, a recovery
  included (scored wrong, never a crash).
- Live-confirmed runs accept only the confirmed recovery.
"""

import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import socket
from types import SimpleNamespace

import pytest
import tiktoken

from packages.hetren_evidence import render_evidence
from packages.support_evaluator import gpt41_baseline, live_labels
from packages.support_evaluator.episodes import run_episode
from packages.support_evaluator.live import export_live
from packages.support_evaluator.live_episodes import live_cases, live_model_id, prepare_live, score_live

from tests.integration.test_live_test_recording import FakeLive


pytestmark = pytest.mark.slow

REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL = "gpt-4.1-mini-2025-04-14"
ENCODING = tiktoken.get_encoding("o200k_base")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("network access attempted in an offline test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def _record(live_dir):
    export_live(live_dir, per_kind=1, seed=5)
    spec = importlib.util.spec_from_file_location("record_live_test", REPO_ROOT / "scripts" / "record_live_test.py")
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    args = argparse.Namespace(
        specs=live_dir / "specs", captures=live_dir / "captures", model=MODEL, max_usd=1.0, limit=None,
        input_usd_per_mtok=0.40, output_usd_per_mtok=1.60, confirm_live=True,
        confirmations=None, confirm_captures=None,
    )
    assert script.record_runs(args, FakeLive, ENCODING) == 0


def _label(live_dir):
    live_labels.label_live(live_dir)
    (live_dir / "evaluator" / "confirmations.jsonl").write_text("", encoding="utf-8")
    live_labels.finalize_live_labels(live_dir)


@pytest.fixture(scope="module")
def recorded(tmp_path_factory):
    """One recorded live export, labelled twice: with the scripted proxies and without any."""
    base = tmp_path_factory.mktemp("live")
    proxied = base / "proxied"
    _record(proxied)
    unmatched = base / "unmatched"
    shutil.copytree(proxied, unmatched)
    _label(proxied)

    original = live_labels.BEHAVIOURS
    live_labels.BEHAVIOURS = ()
    try:
        _label(unmatched)
    finally:
        live_labels.BEHAVIOURS = original

    return proxied, unmatched


def _replay(steps):
    queue = [s["target"] for s in steps]
    return lambda compact: queue.pop(0)


def test_proxy_matched_runs_replay_and_their_labels_verify(recorded):
    proxied, _ = recorded
    cases = live_cases(proxied)
    assert cases and all(row["category"] == "proxy_matched" for _, row in cases)

    for visible, row in cases:
        prepared = prepare_live(proxied, visible, row, live_model_id(proxied))
        scored = score_live(prepared, row, run_episode(_replay(visible["steps"]), prepared))

        assert scored["correct"] and scored["exact"], visible["run_id"]
        assert scored["behaviour"] == "live" and scored["live_category"] == "proxy_matched"
        assert scored["proxy_behaviour"] in row["matching_behaviours"]


def test_final_label_only_runs_never_need_an_agent_re_run(recorded):
    _, unmatched = recorded
    cases = live_cases(unmatched)
    labels = [json.loads(line) for line in (unmatched / "evaluator" / "live_labels_final.jsonl").open()]

    # Without proxies, healthy runs keep a final label and faulty runs are excluded (never scored).
    assert {row["category"] for _, row in cases} == {"final_label_only"}
    assert len(cases) == sum(row["category"] == "final_label_only" for row in labels) < len(labels)

    for visible, row in cases:
        prepared = prepare_live(unmatched, visible, row, live_model_id(unmatched))
        assert prepared.planned.behaviour == "live" and not prepared.determined

        right = score_live(prepared, row, run_episode(_replay(visible["steps"]), prepared))
        recover = {"action": "recover", "verb": "rerun", "args": {}}
        wrong = score_live(prepared, row, run_episode(lambda compact: recover, prepared))

        assert right["correct"] and not wrong["correct"]


def test_live_confirmed_runs_accept_only_the_confirmed_recovery(recorded):
    proxied, _ = recorded
    visible, row = next((v, r) for v, r in live_cases(proxied) if r["label"]["action"] == "recover")
    confirmed = {**row, "category": "live_confirmed_target", "matching_behaviours": [], "probes": None, "determined": None}
    prepared = prepare_live(proxied, visible, confirmed, live_model_id(proxied))
    other = {"action": "recover", "verb": "rerun", "args": {}} if row["label"]["verb"] != "rerun" else \
        {"action": "decide", "verb": "abstain", "args": {"reason": "x"}}

    assert score_live(prepared, confirmed, run_episode(lambda compact: row["label"], prepared))["correct"]
    assert not score_live(prepared, confirmed, run_episode(lambda compact: other, prepared))["correct"]


def test_the_runner_covers_the_live_split(recorded, tmp_path):
    proxied, _ = recorded
    answers = {render_evidence(s["input"]): s["target"]
               for v, _ in live_cases(proxied) for s in v["steps"]}
    requests = []

    def create(**request):
        requests.append(request)
        usage = SimpleNamespace(input_tokens=1500, output_tokens=25, input_tokens_details=None)
        return SimpleNamespace(output_text=json.dumps(answers[request["input"]]), usage=usage)

    args = argparse.Namespace(live=proxied, dataset=None, split=None, out=tmp_path, model="gpt-4.1-2025-04-14",
                              max_usd=5.0, limit=None, input_usd_per_mtok=2.0, output_usd_per_mtok=8.0, confirm_live=True)
    assert gpt41_baseline.run_baseline(args, create, ENCODING) == 0

    rows = [json.loads(line) for line in (tmp_path / "rows-live.jsonl").open()]
    assert len(rows) == len(live_cases(proxied)) and all(r["correct"] for r in rows)
    assert all(c["tier"] == "live" for c in map(json.loads, (tmp_path / "calls.jsonl").open()))
    summary = json.loads((tmp_path / "summary-live.json").read_text())
    assert summary["live_categories"]["proxy_matched"]["k"] == len(rows)
    assert json.loads((tmp_path / "ledger.json").read_text())["datasets"]["live"]["name"] == "proxied"


def test_the_runner_needs_one_source(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "not-used")
    base = ["--confirm-live", "--max-usd", "1", "--out", str(tmp_path / "out")]

    assert gpt41_baseline.main(base) == 2
    assert gpt41_baseline.main(base + ["--live", str(tmp_path), "--dataset", str(tmp_path)]) == 2
    assert gpt41_baseline.main(base + ["--dataset", str(tmp_path)]) == 2


def test_the_small_model_runner_covers_the_live_split(recorded, tmp_path):
    from packages.hetren_baselines.local_model import Generation
    from packages.support_evaluator import local_model_baseline

    proxied, _ = recorded
    answers = {render_evidence(s["input"]): s["target"] for v, _ in live_cases(proxied) for s in v["steps"]}

    def generate(system, user):
        return Generation(json.dumps(answers[user]), 1800, 25, True, False)

    args = argparse.Namespace(live=proxied, dataset=None, split=None, out=tmp_path, smoke=None, limit=None)
    assert local_model_baseline.run_baseline(args, generate, {"model": "fake"}) == 0

    rows = [json.loads(line) for line in (tmp_path / "rows-live.jsonl").open()]
    assert len(rows) == len(live_cases(proxied)) and all(r["correct"] for r in rows)
    assert all(c["tier"] == "live" for c in map(json.loads, (tmp_path / "calls.jsonl").open()))
    assert "live_categories" in json.loads((tmp_path / "summary-live.json").read_text())


def test_the_rules_runner_covers_the_live_split(recorded, tmp_path):
    from packages.support_evaluator.rules_baseline import run_rules

    proxied, _ = recorded
    args = argparse.Namespace(live=proxied, dataset=None, split=None, out=tmp_path, processes=2)
    assert run_rules(args, {"policy": "rules", "commit": "test"}) == 0

    rows = [json.loads(line) for line in (tmp_path / "rows-live.jsonl").open()]
    assert [r["case_id"] for r in rows] == [v["run_id"] for v, _ in live_cases(proxied)]
    assert all(r["live_category"] == "proxy_matched" and r["tier"] == 1 for r in rows)

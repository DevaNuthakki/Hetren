"""Live labelling, offline: runs recorded by a fake live model that behaves
like the scripted ``trust`` agent are replayed and labelled.

- A run matching scripted behaviours is proxy-matched and gets the same
  label as the scripted labeller.
- Without any matching behaviour, a correct outcome is final-label-only and
  a wrong one is excluded.
"""

import argparse
import importlib.util
import json
from pathlib import Path
import socket

import pytest
import tiktoken

from packages.support_evaluator import live_labels
from packages.support_evaluator.labeler import label_case
from packages.support_evaluator.live import export_live
from packages.support_evaluator.plan import PlannedCase

from tests.integration.test_live_test_recording import FakeLive


pytestmark = pytest.mark.slow

REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL = "gpt-4.1-mini-2025-04-14"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("network access attempted in an offline test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


@pytest.fixture(scope="module")
def recorded(tmp_path_factory):
    live_dir = tmp_path_factory.mktemp("live") / "export"
    export_live(live_dir, per_kind=1, seed=5)
    spec = importlib.util.spec_from_file_location("record_live_test", REPO_ROOT / "scripts" / "record_live_test.py")
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    args = argparse.Namespace(
        specs=live_dir / "specs", captures=live_dir / "captures", model=MODEL, max_usd=1.0, limit=None,
        input_usd_per_mtok=0.40, output_usd_per_mtok=1.60, confirm_live=True,
    )
    assert script.record_runs(args, FakeLive, tiktoken.get_encoding("o200k_base")) == 0
    plans = {r["planned"]["case_kind"]: r for r in map(json.loads, (live_dir / "evaluator" / "live_plan.jsonl").open())}
    return live_dir, plans


def test_matching_runs_get_the_scripted_label(recorded):
    live_dir, plans = recorded

    for kind in ("mapping_swap", "recent_tier_change"):
        row = plans[kind]
        result = live_labels.label_live_run(str(live_dir), row["run_id"], MODEL)["evaluator"]
        expected = label_case(PlannedCase(**{**row["planned"], "behaviour": "trust"}))

        assert result["category"] == "proxy_matched"
        assert "trust" in result["matching_behaviours"]
        assert result["label"] == expected.run_label.label
        assert result["probes"] == list(expected.probe_label.probes)
        assert result["output_limit_calls"] == 0


def test_without_a_matching_behaviour_only_rerun_free_labels_survive(recorded, monkeypatch):
    live_dir, plans = recorded
    monkeypatch.setattr(live_labels, "BEHAVIOURS", ())

    healthy = live_labels.label_live_run(str(live_dir), plans["recent_tier_change"]["run_id"], MODEL)
    faulty = live_labels.label_live_run(str(live_dir), plans["mapping_swap"]["run_id"], MODEL)

    assert healthy["evaluator"]["category"] == "final_label_only"
    assert healthy["evaluator"]["label"]["verb"] == "no_intervention"
    assert healthy["evaluator"]["probes"] is None
    assert len(healthy["visible"]["steps"]) == 1

    assert faulty["evaluator"]["category"] == "excluded"
    assert faulty["evaluator"]["label"] is None

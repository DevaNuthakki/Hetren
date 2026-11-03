"""Live test split preparation, fully offline.

- The input-token estimate reproduces every recorded Milestone 1 live call.
- ``BudgetedModel`` refuses a call that could pass the cap without sending it.
- ``scripts/record_live_test.py`` records runs from neutral specs, keeps a
  ledger, resumes, and stops before the cap (fake live model, no network).
- The live export uses fresh seeds and its specs carry no case information.
"""

import argparse
import asyncio
import importlib.util
import json
from pathlib import Path
import socket

import pytest
import tiktoken
from agents import Model, ModelResponse, ModelSettings
from agents.usage import Usage

from packages.contracts import ContractError
from packages.integrations.openai_agents import RunProvenance
from packages.integrations.openai_agents.budget import (
    BudgetExceeded,
    BudgetedModel,
    Prices,
    SpendLedger,
    estimate_input_tokens,
)
from packages.support_agent import ScriptedSupportModel
from packages.support_evaluator import CASE_KINDS
from packages.support_evaluator.live import LIVE_SEED_RANGE, export_live, live_plan
from packages.support_evaluator.plan import DEFAULT_PLAN_KINDS
from packages.support_evaluator.recordings import RECORDING_SOURCE_MODEL_ID, first_run_number
from packages.support_examples.harness import ReplaySource, SupportHarness


REPO_ROOT = Path(__file__).resolve().parents[2]
ENCODING = tiktoken.get_encoding("o200k_base")
PRICES = Prices(0.40, 1.60)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("network access attempted in an offline test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def _script():
    spec = importlib.util.spec_from_file_location("record_live_test", REPO_ROOT / "scripts" / "record_live_test.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Estimate calibration


class _Counting(Model):
    def __init__(self, inner, calls):
        self.inner, self.calls = inner, calls

    def __getattr__(self, name):
        return getattr(self.inner, name)

    async def get_response(self, system_instructions, input, *args, **kwargs):
        response = await self.inner.get_response(system_instructions, input, *args, **kwargs)
        self.calls.append((estimate_input_tokens(system_instructions, input, ENCODING), response.usage.input_tokens))
        return response

    def stream_response(self, *args, **kwargs):
        raise NotImplementedError


def test_estimate_reproduces_every_recorded_milestone_1_call():
    calls = []

    class CountingSource(ReplaySource):
        def model_for(self, run_id):
            return _Counting(super().model_for(run_id), calls)

    for name in ("example_correct_run", "example_insufficient_evidence", "example_verified_recovery"):
        SupportHarness(
            example_name=name, first_run_number=first_run_number(name),
            model_source=CountingSource(
                root=REPO_ROOT / "tests" / "fixtures" / "support_captures",
                source_provenance=RunProvenance.LIVE, source_model_id=RECORDING_SOURCE_MODEL_ID,
            ),
        ).run_example()

    assert len(calls) == 20
    assert all(estimate == actual for estimate, actual in calls), calls


# Budgeted model


class FakeLive(Model):
    """Scripted decisions with provider-like usage; no hetren provenance (treated as live)."""

    def __init__(self, behaviour="trust", output_tokens=25):
        self.scripted = ScriptedSupportModel(behaviour)
        self.output_tokens = output_tokens
        self.calls = 0

    async def get_response(self, system_instructions, input, *args, **kwargs):
        self.calls += 1
        response = await self.scripted.get_response(system_instructions, input, *args, **kwargs)
        usage = Usage(
            requests=1,
            input_tokens=estimate_input_tokens(system_instructions, input, ENCODING),
            output_tokens=self.output_tokens,
        )
        return ModelResponse(output=response.output, usage=usage, response_id=None)

    def stream_response(self, *args, **kwargs):
        raise NotImplementedError


def _call(model, settings):
    return asyncio.run(model.get_response(
        "Route the ticket.", "Please handle support ticket T-1001.", settings, [], None, [], None,
        previous_response_id=None, conversation_id=None, prompt=None,
    ))


def test_budgeted_model_refuses_before_passing_the_cap():
    inner = FakeLive()
    ledger = SpendLedger(cap_usd=0.001, prices=PRICES)
    model = BudgetedModel(inner=inner, ledger=ledger, encoding=ENCODING)
    settings = ModelSettings(store=False, max_tokens=300)

    while True:
        try:
            _call(model, settings)
        except BudgetExceeded:
            break

    assert inner.calls == ledger.calls > 0
    assert ledger.spent_usd <= ledger.cap_usd

    with pytest.raises(ContractError, match="max_tokens"):
        _call(BudgetedModel(inner=FakeLive(), ledger=SpendLedger(1.0, PRICES), encoding=ENCODING), ModelSettings(store=False))


# Recording script


@pytest.fixture(scope="module")
def live_export(tmp_path_factory):
    out = tmp_path_factory.mktemp("live") / "export"
    manifest = export_live(out, per_kind=1, seed=7)
    return out, manifest


def _args(export, captures, **overrides):
    values = dict(
        specs=export / "specs", captures=captures, model="gpt-4.1-mini-2025-04-14",
        max_usd=1.0, limit=None, input_usd_per_mtok=0.40, output_usd_per_mtok=1.60, confirm_live=True,
        confirmations=None, confirm_captures=None,
    )
    values.update(overrides)
    return argparse.Namespace(**values)


def test_recording_writes_one_directory_per_run_and_a_ledger(live_export, tmp_path):
    export, manifest = live_export
    script = _script()

    assert script.record_runs(_args(export, tmp_path, limit=4), FakeLive, ENCODING) == 0
    ledger = json.loads((tmp_path / "ledger.json").read_text())
    assert len(ledger["completed"]) == 4
    assert all(json.loads(path.read_text())["source_provenance"] == "live" for path in tmp_path.glob("run-*/capture-*.json"))
    assert sorted(p.name for p in tmp_path.iterdir() if p.is_dir()) == sorted(ledger["completed"])

    # Resume records only the remaining runs and keeps the cumulative spend.
    assert script.record_runs(_args(export, tmp_path), FakeLive, ENCODING) == 0
    resumed = json.loads((tmp_path / "ledger.json").read_text())
    assert len(resumed["completed"]) == manifest["runs"]
    assert resumed["spend"]["calls"] > ledger["spend"]["calls"]


def test_recording_stops_before_the_cap_and_sets_the_partial_run_aside(live_export, tmp_path):
    export, _ = live_export
    script = _script()

    assert script.record_runs(_args(export, tmp_path, max_usd=0.003), FakeLive, ENCODING) == script.EXIT_BUDGET
    ledger = json.loads((tmp_path / "ledger.json").read_text())
    assert ledger["spend"]["spent_usd"] <= 0.003
    assert 0 < len(ledger["completed"]) < 10

    for run_dir in tmp_path.glob("run-*"):
        assert run_dir.name in ledger["completed"]

    assert all(path.parent.name == "_aborted" for path in tmp_path.glob("_aborted/*"))


def test_script_refuses_without_confirmation_cap_or_key(monkeypatch, tmp_path, capsys):
    script = _script()
    base = ["--specs", str(tmp_path), "--captures", str(tmp_path / "c"), "--model", "m"]
    monkeypatch.setenv("OPENAI_API_KEY", "placeholder-not-a-key")

    assert script.main(base + ["--max-usd", "1"]) == 2
    assert script.main(base + ["--confirm-live"]) == 2
    monkeypatch.delenv("OPENAI_API_KEY")
    assert script.main(base + ["--confirm-live", "--max-usd", "1"]) == 2
    assert "OPENAI_API_KEY is not set" in capsys.readouterr().err


# Live export


def test_live_plan_is_balanced_on_fresh_seeds():
    plan = live_plan(per_kind=3, seed=11)

    assert [p.case_kind for p, _ in plan] == [k for k in DEFAULT_PLAN_KINDS for _ in range(3)]
    assert all(LIVE_SEED_RANGE[0] <= p.world_seed < LIVE_SEED_RANGE[1] for p, _ in plan)
    assert {p.behaviour for p, _ in plan} == {"live"}
    assert [p for p, _ in live_plan(per_kind=3, seed=11)] == [p for p, _ in plan]


def test_specs_are_neutral(live_export):
    export, manifest = live_export
    specs = sorted((export / "specs").glob("run-*.json"))

    assert len(specs) == manifest["runs"] == len(DEFAULT_PLAN_KINDS)

    for path in specs:
        spec = json.loads(path.read_text())
        assert set(spec) == {"run_id", "ticket_id", "world"}
        text = path.read_text().lower()
        assert not any(kind in text for kind in CASE_KINDS), path.name

"""Replay the committed live recordings of all three examples, offline.

Runs in CI on every push: the harness replays each example from
``tests/fixtures/support_captures`` with the network blocked, and the
verifier must reach the expected verdict.
"""

from pathlib import Path
import socket

import pytest

from packages.integrations.openai_agents import RunProvenance, RunStatus, run_manifest
from packages.support_evaluator import SupportVerdict
from packages.support_examples import ReplaySource, SupportHarness
from packages.support_recovery import DiagnosisOutcome
from packages.verification.support_verification import recorded_replay_plan


FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "support_captures"
PLAN = {entry.example_name: entry for entry in recorded_replay_plan()}

EXPECTED = {
    "example_correct_run": (DiagnosisOutcome.HEALTHY, False, SupportVerdict.NO_INTERVENTION_CORRECT),
    "example_insufficient_evidence": (
        DiagnosisOutcome.INSUFFICIENT_EVIDENCE, False, SupportVerdict.INSUFFICIENT_EVIDENCE_CORRECT,
    ),
    "example_verified_recovery": (
        DiagnosisOutcome.MAPPING_INCONSISTENCY, True, SupportVerdict.RECOVERY_VERIFIED,
    ),
}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("network access attempted in an offline test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def _replay(example_name):
    entry = PLAN[example_name]
    return SupportHarness(
        example_name=example_name,
        first_run_number=entry.first_run_number,
        model_source=ReplaySource(
            root=FIXTURES,
            source_provenance=RunProvenance.LIVE,
            source_model_id=entry.source_model_id,
        ),
    ).run_example()


def test_every_example_has_a_recording():
    assert set(PLAN) == set(EXPECTED)


@pytest.mark.parametrize("example_name", sorted(EXPECTED))
def test_recorded_example_replays_to_its_expected_verdict(example_name):
    result = _replay(example_name)
    diagnosis, claims_fix, verdict = EXPECTED[example_name]

    assert result.frozen.outcome.diagnosis.outcome is diagnosis
    assert result.frozen.outcome.claims_fix is claims_fix
    assert result.verification.evaluator_verdict is verdict
    assert tuple(run.record.run_id for run in result.runs) == PLAN[example_name].run_ids


@pytest.mark.parametrize("example_name", sorted(EXPECTED))
def test_replayed_runs_are_live_sourced_store_false_and_consistent(example_name):
    result = _replay(example_name)

    for run in result.runs:
        record = run.record
        assert record.status is RunStatus.COMPLETED
        assert record.provenance is RunProvenance.REPLAY
        assert record.source_provenance is RunProvenance.LIVE
        assert record.model_id == f"replay:{PLAN[example_name].source_model_id}"
        assert record.replay_capture_ids == (
            "capture-0001", "capture-0002", "capture-0003", "capture-0004",
        )
        assert record.model_settings == {"store": False}
        assert run_manifest(record)["store"] is False
        assert record.sdk_evidence.discrepancies == ()


@pytest.mark.parametrize("example_name", sorted(EXPECTED))
def test_replay_is_deterministic(example_name):
    first, second = _replay(example_name), _replay(example_name)

    assert first.frozen.frozen_sha256 == second.frozen.frozen_sha256
    assert first.verification.verification_sha256 == second.verification.verification_sha256
    assert [run.record.record_sha256 for run in first.runs] == [
        run.record.record_sha256 for run in second.runs
    ]

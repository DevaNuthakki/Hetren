import json
from pathlib import Path
import re
import socket
import subprocess
import sys

import pytest

from environments.support.faults import IdentifierMappingSwap
from packages.contracts import ContractError
from packages.integrations.openai_agents import RunProvenance, RunStatus
from packages.support_agent import ScriptedSupportModel
from packages.support_evaluator import (
    EXAMPLES,
    FAULTS,
    NEUTRAL_FILE_NAME,
    NEUTRAL_RUN_ID,
    SupportVerdict,
    assert_no_leaks,
    scan_agent_outputs,
    scan_content,
    scan_identifiers,
)
from packages.support_examples import (
    MAX_RUNS_PER_EXAMPLE,
    SCENARIOS,
    RecordingSource,
    ReplaySource,
    ScriptedSource,
    SupportHarness,
    live_recording_source,
)
from packages.support_recovery import DiagnosisOutcome


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "record_recovery_example.py"
SCRIPTED_ID = ScriptedSupportModel.hetren_model_id
LIVE_MODEL = "gpt-4.1-mini-2025-04-14"

EXPECTED_VERDICTS = {
    "example_correct_run": SupportVerdict.NO_INTERVENTION_CORRECT,
    "example_verified_recovery": SupportVerdict.RECOVERY_VERIFIED,
    "example_insufficient_evidence": SupportVerdict.INSUFFICIENT_EVIDENCE_CORRECT,
}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("network access attempted in an offline test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def _recording(root):
    return RecordingSource(
        root=root, inner_factory=ScriptedSupportModel, source_provenance=RunProvenance.SCRIPTED,
    )


def _replay(root):
    return ReplaySource(root=root, source_provenance=RunProvenance.SCRIPTED, source_model_id=SCRIPTED_ID)


# Scenario setup agrees with the evaluator


def test_scenarios_match_the_evaluator_catalog():
    assert set(SCENARIOS) == set(EXAMPLES)

    for name, scenario in SCENARIOS.items():
        spec = EXAMPLES[name]
        assert scenario.ticket_id == spec.target_ticket_id

        if spec.fault_id is None:
            assert scenario.swap is None
        else:
            assert (
                IdentifierMappingSwap(*scenario.swap).canonical_payload()
                == FAULTS[spec.fault_id].fault_payload()
            )

        assert scenario.withhold_account_observation is (
            spec.evidence_condition.value == "account_observation_withheld"
        )


# Scripted runs of every example


@pytest.mark.parametrize("example_name", sorted(SCENARIOS))
def test_scripted_examples_reach_their_expected_verdicts(example_name):
    result = SupportHarness(example_name=example_name, model_source=ScriptedSource()).run_example()

    assert result.verification.evaluator_verdict is EXPECTED_VERDICTS[example_name]
    assert all(run.record.provenance is RunProvenance.SCRIPTED for run in result.runs)
    assert len(result.runs) <= MAX_RUNS_PER_EXAMPLE


def test_recovery_example_runs_initial_rerun_and_regression_in_one_process():
    harness = SupportHarness(example_name="example_verified_recovery", model_source=ScriptedSource())

    result = harness.run_example()

    assert [(run.role, run.record.run_id) for run in result.runs] == [
        ("initial", "run-0001"), ("rerun", "run-0002"), ("regression", "run-0003"),
    ]
    assert result.frozen.outcome.diagnosis.outcome is DiagnosisOutcome.MAPPING_INCONSISTENCY
    assert result.frozen.outcome.post_recovery_run_id == "run-0002"
    assert result.verification.regression_run_ids == ("run-0003",)
    rerun_ticket = result.runs[1].record.stage_records[3].payload["observation"]
    assert (rerun_ticket["queue_id"], rerun_ticket["status"]) == ("Q-GENERAL", "routed")


def test_first_run_number_offsets_all_run_ids():
    result = SupportHarness(
        example_name="example_verified_recovery", model_source=ScriptedSource(), first_run_number=3,
    ).run_example()

    assert [run.record.run_id for run in result.runs] == ["run-0003", "run-0004", "run-0005"]


# Recording and replay


def test_recording_writes_one_capture_directory_per_run_and_nothing_else(tmp_path):
    result = SupportHarness(
        example_name="example_verified_recovery", model_source=_recording(tmp_path),
        first_run_number=3,
    ).run_example()

    assert sorted(path.name for path in tmp_path.iterdir()) == ["run-0003", "run-0004", "run-0005"]

    for run in result.runs:
        directory = tmp_path / run.record.run_id
        assert sorted(path.name for path in directory.iterdir()) == [
            f"{capture_id}.json" for capture_id in run.record.recorded_capture_ids
        ]
        assert run.record.provenance is RunProvenance.SCRIPTED

    every_file = [path for path in tmp_path.rglob("*") if path.is_file()]
    assert all(re.fullmatch(r"capture-[0-9]{4}\.json", path.name) for path in every_file)


def test_replay_reproduces_the_recorded_example_exactly(tmp_path):
    recorded = SupportHarness(
        example_name="example_verified_recovery", model_source=_recording(tmp_path),
        first_run_number=3,
    ).run_example()

    replayed = SupportHarness(
        example_name="example_verified_recovery", model_source=_replay(tmp_path),
        first_run_number=3,
    ).run_example()

    assert replayed.verification.evaluator_verdict is SupportVerdict.RECOVERY_VERIFIED

    original, again = recorded.frozen.outcome, replayed.frozen.outcome
    assert again.diagnosis.findings == original.diagnosis.findings
    assert again.candidate.actions == original.candidate.actions
    assert again.application.state_before_sha256 == original.application.state_before_sha256
    assert again.application.state_after_sha256 == original.application.state_after_sha256
    assert again.post_recovery_diagnosis.outcome is original.post_recovery_diagnosis.outcome
    # Hetren's input records provenance, so the replayed outcome is
    # distinguishable from the recorded one.
    assert again.diagnosis.assessment.input_sha256 != original.diagnosis.assessment.input_sha256
    assert replayed.frozen.frozen_sha256 != recorded.frozen.frozen_sha256

    for original, again in zip(recorded.runs, replayed.runs):
        assert again.record.provenance is RunProvenance.REPLAY
        assert again.record.source_provenance is RunProvenance.SCRIPTED
        assert again.record.replay_capture_ids == original.record.recorded_capture_ids
        assert again.record.stage_records_sha256 == original.record.stage_records_sha256


def test_preflight_refuses_any_used_directory_before_the_first_model_call(tmp_path):
    (tmp_path / "run-0004").mkdir(parents=True)
    (tmp_path / "run-0004" / "capture-0001.json").write_text("{}", encoding="utf-8")
    calls = []

    def inner():
        calls.append(1)
        return ScriptedSupportModel()

    source = RecordingSource(
        root=tmp_path, inner_factory=inner, source_provenance=RunProvenance.SCRIPTED,
    )

    with pytest.raises(ContractError, match="run-0004 is not empty"):
        SupportHarness(
            example_name="example_verified_recovery", model_source=source, first_run_number=3,
        ).run_example()

    assert calls == []
    assert not (tmp_path / "run-0003").exists()


# Live wiring, with a fake client (never a real request)


class StopAfterRequest(Exception):
    pass


class FakeClient:
    def __init__(self) -> None:
        self.requests = []
        outer = self

        class Responses:
            async def create(self, **kwargs):
                outer.requests.append(kwargs)
                raise StopAfterRequest("request captured")

        self.responses = Responses()


def test_live_recording_source_sends_store_false_and_writes_nothing_on_failure(tmp_path):
    client = FakeClient()

    result = SupportHarness(
        example_name="example_verified_recovery",
        model_source=live_recording_source(root=tmp_path, model=LIVE_MODEL, client=client),
        first_run_number=3,
    ).run_example()

    assert client.requests
    assert {request["store"] for request in client.requests} == {False}
    assert {request["model"] for request in client.requests} == {LIVE_MODEL}
    assert all(run.record.provenance is RunProvenance.LIVE for run in result.runs)
    assert all(run.record.status is RunStatus.ERROR for run in result.runs)
    assert result.frozen.outcome.claims_fix is False
    assert [path for path in tmp_path.rglob("*") if path.is_file()] == []


# Script guards (subprocess, no client is ever created)


def _script(*args, env=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO_ROOT, text=True, capture_output=True, check=False,
        env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1", **(env or {})},
    )


def test_script_guards_refuse_before_any_client_exists(tmp_path):
    common = ["--model", LIVE_MODEL, "--output-root", str(tmp_path)]
    key = {"OPENAI_API_KEY": "synthetic-not-used"}

    unconfirmed = _script(*common, "--first-run-id", "run-0003", env=key)
    assert (unconfirmed.returncode, "requires --confirm-live" in unconfirmed.stderr) == (2, True)

    keyless = _script(*common, "--first-run-id", "run-0003", "--confirm-live")
    assert (keyless.returncode, "OPENAI_API_KEY is not set" in keyless.stderr) == (2, True)

    for bad_id in ("recovery-1", "run-3", "run-00003"):
        result = _script(*common, "--first-run-id", bad_id, "--confirm-live", env=key)
        assert (result.returncode, "neutral run-NNNN" in result.stderr) == (2, True)

    (tmp_path / "run-0005").mkdir()
    (tmp_path / "run-0005" / "capture-0001.json").write_text("{}", encoding="utf-8")
    used = _script(*common, "--first-run-id", "run-0003", "--confirm-live", env=key)
    assert (used.returncode, "run-0005 must be empty or new" in used.stderr) == (2, True)

    assert sorted(path.name for path in tmp_path.iterdir()) == ["run-0005"]


def test_script_is_side_effect_free_and_matches_the_harness():
    source = SCRIPT.read_text(encoding="utf-8")
    module_level = source.split("def main(")[0]

    assert "AsyncOpenAI(" not in module_level
    assert "from packages" not in module_level
    assert f"RUNS_NEEDED = {MAX_RUNS_PER_EXAMPLE}" in source
    assert "support_evaluator" not in source
    assert "model_settings" not in source


# Leakage and the harness boundary


@pytest.mark.parametrize("example_name", sorted(SCENARIOS))
def test_everything_hetren_sees_and_every_file_written_is_clean(tmp_path, example_name):
    result = SupportHarness(example_name=example_name, model_source=_recording(tmp_path)).run_example()
    evidence_keys = set(result.runs[0].record.evidence_payload())

    for index, diagnosis_input in enumerate(result.diagnosis_inputs):
        assert set(diagnosis_input) == evidence_keys
        assert "final_message" not in json.dumps(diagnosis_input)
        assert_no_leaks(scan_content({f"diagnosis_input[{index}]": diagnosis_input}))

    assert_no_leaks(scan_content({"hetren_outcome": result.frozen.outcome.canonical_payload()}))

    for run in result.runs:
        assert_no_leaks(scan_content({run.record.run_id: run.record.evidence_payload()}))
        assert_no_leaks(scan_agent_outputs({run.record.run_id: run.record.agent_output_payload()}))

    run_ids = [run.record.run_id for run in result.runs]
    assert_no_leaks(scan_identifiers("run_ids", run_ids, NEUTRAL_RUN_ID))
    assert_no_leaks(
        scan_identifiers("run_directories", [f"{path.name}.json" for path in tmp_path.iterdir()], NEUTRAL_FILE_NAME)
    )

    for path in tmp_path.rglob("*.json"):
        document = json.loads(path.read_text(encoding="utf-8"))
        model_output = document.pop("response")
        assert_no_leaks(scan_identifiers("capture_files", [path.name], NEUTRAL_FILE_NAME))
        assert_no_leaks(scan_content({path.name: document}))
        assert_no_leaks(scan_agent_outputs({path.name: model_output}))

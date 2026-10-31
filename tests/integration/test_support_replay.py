from functools import partial
import json
from pathlib import Path
import socket
import subprocess
import sys

import pytest

from environments.support.faults import IdentifierMappingSwap, inject_fault
from environments.support.fixtures import SupportEnvironment
from environments.support.tools import (
    SUPPORT_TOOL_DESCRIPTIONS,
    SUPPORT_TOOL_SCHEMAS,
    SUPPORT_TOOLS,
)
from packages.action_gateway import AllowListPolicy, GatedTool, ToolGateway
from packages.integrations.openai_agents import (
    CaptureConflictError,
    CaptureStore,
    RecordingModel,
    ReplayMissError,
    ReplayModel,
    ReplayVersionError,
    RunProvenance,
    gateway_function_tools,
    run_agent,
    run_manifest,
)
from packages.support_agent import ScriptedSupportModel, build_support_agent, task_message
from packages.support_evaluator import (
    EXAMPLES,
    NEUTRAL_FILE_NAME,
    NEUTRAL_RUN_ID,
    assert_no_leaks,
    fault,
    scan_agent_outputs,
    scan_content,
    scan_identifiers,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "record_support_captures.py"
AGENT_TOOLS = ("read_ticket", "lookup_account", "route_ticket")
SCRIPTED_ID = ScriptedSupportModel.hetren_model_id


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("network access attempted in an offline test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def _environment(swap=None) -> SupportEnvironment:
    environment = SupportEnvironment()

    if swap is not None:
        inject_fault(environment, IdentifierMappingSwap(*swap))

    return environment


def _run(environment, ticket_id, model, provenance, run_id="run-0001"):
    gateway = ToolGateway(
        tools=[
            GatedTool(
                name, partial(SUPPORT_TOOLS[name], environment),
                SUPPORT_TOOL_SCHEMAS[name], SUPPORT_TOOL_DESCRIPTIONS[name],
            )
            for name in AGENT_TOOLS
        ],
        policy=AllowListPolicy(AGENT_TOOLS),
        state_sha256=environment.state_sha256,
    )
    agent = build_support_agent(
        environment=environment, tools=gateway_function_tools(gateway), model=model,
    )
    return run_agent(
        agent=agent, task_input=task_message(ticket_id), gateway=gateway,
        run_id=run_id, provenance=provenance,
    )


def _record(store, environment, ticket_id="T-1003", run_id="run-0001"):
    model = RecordingModel(
        inner=ScriptedSupportModel(), store=store, source_provenance=RunProvenance.SCRIPTED,
    )
    return _run(environment, ticket_id, model, RunProvenance.SCRIPTED, run_id)


def _replay(store, environment, ticket_id="T-1003", source=RunProvenance.SCRIPTED, run_id="run-0002"):
    model = ReplayModel(store=store, source_provenance=source, source_model_id=SCRIPTED_ID)
    return _run(environment, ticket_id, model, RunProvenance.REPLAY, run_id)


# Recording with the scripted model


def test_recording_a_scripted_run_writes_one_neutral_capture_per_model_call(tmp_path):
    store = CaptureStore(tmp_path)

    record = _record(store, _environment())

    assert record.provenance is RunProvenance.SCRIPTED
    assert record.source_provenance is None
    assert record.recorded_capture_ids == (
        "capture-0001", "capture-0002", "capture-0003", "capture-0004",
    )
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        f"{capture_id}.json" for capture_id in record.recorded_capture_ids
    ]
    assert {capture.source_provenance for capture in store.captures()} == {RunProvenance.SCRIPTED}
    assert {capture.source_model_id for capture in store.captures()} == {SCRIPTED_ID}


# Replay


def test_replay_reproduces_the_recorded_run_exactly(tmp_path):
    store = CaptureStore(tmp_path)
    recorded = _record(store, _environment())

    replayed = _replay(CaptureStore(tmp_path), _environment())

    assert replayed.provenance is RunProvenance.REPLAY
    assert replayed.source_provenance is RunProvenance.SCRIPTED
    assert replayed.model_id == f"replay:{SCRIPTED_ID}"
    assert replayed.replay_capture_ids == recorded.recorded_capture_ids
    assert replayed.recorded_capture_ids == ()
    assert replayed.final_message == recorded.final_message
    assert replayed.stage_records_sha256 == recorded.stage_records_sha256
    assert replayed.final_state_sha256 == recorded.final_state_sha256
    assert replayed.sdk_evidence.discrepancies == ()
    assert run_manifest(replayed)["source_provenance"] == "scripted"


def test_replay_of_scripted_captures_cannot_claim_a_live_source(tmp_path):
    store = CaptureStore(tmp_path)
    _record(store, _environment())

    with pytest.raises(ReplayMissError, match="source provenance scripted, not live"):
        _replay(store, _environment(), source=RunProvenance.LIVE)


def test_replay_is_offline_and_never_calls_a_model(tmp_path, monkeypatch):
    store = CaptureStore(tmp_path)
    _record(store, _environment())

    async def forbidden(*args, **kwargs):
        raise AssertionError("replay called the scripted model")

    monkeypatch.setattr(ScriptedSupportModel, "get_response", forbidden)

    assert _replay(store, _environment()).final_message == "Routed T-1003 to Q-PRIORITY."


# Context: a changed history is a miss, never a nearby capture


def test_a_changed_history_raises_a_replay_miss(tmp_path):
    store = CaptureStore(tmp_path)
    faulty = _record(store, _environment(swap=("C-3103", "C-3104")))
    assert faulty.final_message == "Routed T-1003 to Q-GENERAL."

    # After a recovery the lookup observation differs, so turn 3 has no capture.
    with pytest.raises(ReplayMissError, match="differs in: prior_observations$"):
        _replay(store, _environment())


def test_each_run_replays_only_from_its_own_directory(tmp_path):
    faulty_store = CaptureStore(tmp_path / "run-0001")
    clean_store = CaptureStore(tmp_path / "run-0002")
    _record(faulty_store, _environment(swap=("C-3103", "C-3104")), run_id="run-0001")
    _record(clean_store, _environment(), run_id="run-0002")

    faulty = _replay(faulty_store, _environment(swap=("C-3103", "C-3104")), run_id="run-0003")
    clean = _replay(clean_store, _environment(), run_id="run-0004")

    assert faulty.final_message == "Routed T-1003 to Q-GENERAL."
    assert clean.final_message == "Routed T-1003 to Q-PRIORITY."

    # Identical first turns exist in the other directory; that is not reused.
    with pytest.raises(ReplayMissError, match="differs in: prior_observations$"):
        _replay(faulty_store, _environment(), run_id="run-0005")
    with pytest.raises(ReplayMissError):
        _replay(faulty_store, _environment(swap=("C-3103", "C-3101")), run_id="run-0006")


def test_recording_into_a_used_directory_is_refused(tmp_path):
    store = CaptureStore(tmp_path)
    _record(store, _environment())

    with pytest.raises(CaptureConflictError, match="empty capture store"):
        _record(CaptureStore(tmp_path), _environment(), run_id="run-0002")


def test_a_different_task_misses_at_the_first_turn(tmp_path):
    store = CaptureStore(tmp_path)
    _record(store, _environment(), ticket_id="T-1003")

    with pytest.raises(ReplayMissError, match="differs in: input_items$"):
        _replay(store, _environment(), ticket_id="T-1001")


def test_version_mismatch_stops_replay_through_the_runner(tmp_path):
    store = CaptureStore(tmp_path)
    _record(store, _environment())
    path = tmp_path / "capture-0001.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["versions"]["openai"] = "3.41.0"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ReplayVersionError, match="capture-0001"):
        _replay(CaptureStore(tmp_path), _environment())


# Live recording script (never run live here)


def _script(*args, env=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO_ROOT, text=True, capture_output=True, check=False,
        env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1", **(env or {})},
    )


def test_live_script_refuses_without_confirmation_or_key(tmp_path):
    common = ["--ticket", "T-1001", "--model", "m", "--run-id", "run-0001",
              "--output-dir", str(tmp_path / "out")]

    unconfirmed = _script(*common, env={"OPENAI_API_KEY": "synthetic-not-used"})
    assert unconfirmed.returncode == 2
    assert "requires --confirm-live" in unconfirmed.stderr

    keyless = _script(*common, "--confirm-live")
    assert keyless.returncode == 2
    assert "OPENAI_API_KEY is not set" in keyless.stderr

    assert not (tmp_path / "out").exists()


def test_live_script_import_is_side_effect_free():
    source = SCRIPT.read_text(encoding="utf-8")
    module_level = source.split("def main(")[0]

    assert "AsyncOpenAI(" not in module_level
    assert "from agents" not in module_level
    assert 'if __name__ == "__main__":' in source


# Leakage: capture files, names, and replay records


@pytest.mark.parametrize("example_name", sorted(EXAMPLES))
def test_capture_files_names_and_replay_records_are_clean(tmp_path, example_name):
    spec = EXAMPLES[example_name]
    swap = None if spec.fault_id is None else tuple(fault(spec.fault_id).parameters.values())
    store = CaptureStore(tmp_path)

    _record(store, _environment(swap), ticket_id=spec.target_ticket_id)
    replayed = _replay(store, _environment(swap), ticket_id=spec.target_ticket_id)

    names = sorted(path.name for path in tmp_path.iterdir())
    assert_no_leaks(scan_identifiers("capture_file_names", names, NEUTRAL_FILE_NAME))

    for path in tmp_path.iterdir():
        document = json.loads(path.read_text(encoding="utf-8"))
        model_output = document.pop("response")
        assert_no_leaks(scan_content({path.name: document}))
        assert_no_leaks(scan_agent_outputs({f"{path.name}:response": model_output}))

    assert_no_leaks(scan_content({"replay_record": replayed.evidence_payload()}))
    assert_no_leaks(
        scan_identifiers(
            "capture_ids",
            [f"{capture_id}.json" for capture_id in replayed.replay_capture_ids],
            NEUTRAL_FILE_NAME,
        )
    )
    assert_no_leaks(scan_identifiers("run_id", [replayed.run_id], NEUTRAL_RUN_ID))

"""The descriptive CLI check's command line and comparison (no model; the run itself is operator-run)."""

from __future__ import annotations

import json
from pathlib import Path

from packages.hetren_cli import main as cli
from packages.support_evaluator import cli_check


def test_the_cli_is_run_as_a_user_runs_it_with_the_validation_threads():
    command = cli_check.cli_command(Path("in.json"), Path("m.gguf"), Path("tok"), Path("llama-server"), python="py")
    assert command == ["py", "-m", "packages.hetren_cli", "diagnose", "--compact", "in.json", "--model", "m.gguf",
                       "--tokenizer", "tok", "--llama-server", "llama-server", "--threads", "6", "--format", "json"]
    args = cli._parser().parse_args(command[3:])  # the CLI accepts exactly this command line
    assert args.threads == 6 and args.format == "json"


def test_first_actions_are_each_cases_call_0(tmp_path):
    calls = [
        {"case_id": "case-1", "call": 1, "text": '{"action": "decide", "verb": "abstain", "args": {}}'},
        {"case_id": "case-1", "call": 0, "text": '{"action": "probe", "verb": "resolve", "args": {"customer_ref": "C-3103"}}'},
        {"case_id": "case-2", "call": 0, "text": "not json"},
        {"case_id": "case-3", "call": 0, "text": '{"action": "decide", "verb": "abstain", "args": {}}', "discarded": True},
    ]
    path = tmp_path / "calls.jsonl"
    path.write_text("".join(json.dumps(c) + "\n" for c in calls), encoding="utf-8")
    first = cli_check.first_actions(path)

    assert first["case-1"]["verb"] == "resolve"
    assert first["case-2"] == {"unparsable": "not json"}
    assert "case-3" not in first


def test_cli_actions_and_the_summary_keep_the_tiers_apart():
    decision = {"action": "decide", "verb": "no_intervention", "args": {}}
    assert cli_check.cli_action({"result": {"outcome": "decision", "action": decision}}) == decision
    assert cli_check.cli_action({"result": {"outcome": "invalid_reply", "reply": " x "}}) == {"unparsable": "x"}
    assert cli_check.cli_action(None) is None

    rows = [{"tier": 1, "case_id": "a", "same": True, "exit": 0}, {"tier": 1, "case_id": "b", "same": False, "exit": 4},
            {"tier": 2, "case_id": "c", "same": False, "exit": 3}]
    summary = cli_check.summarize(rows)
    assert summary["tiers"]["tier1"] == {"cases": 2, "same_first_action": 1, "differing": ["b"], "cli_failures": [],
                                         "comparison": "like for like (same input and prompt; prompt cache differs)"}
    assert summary["tiers"]["tier2"]["cli_failures"] == ["c"]
    assert "not like for like" in summary["tiers"]["tier2"]["comparison"]

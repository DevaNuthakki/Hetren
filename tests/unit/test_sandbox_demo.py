"""The full-episode demo (step 8): it refuses test and non-validation cases before anything runs, and with the
validation run's logged Q4_K_M replies it reproduces the three approved demo cases' logged episodes exactly."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from packages.hetren_baselines.prompt import PROMPT_VERSION, system_prompt
from packages.support_evaluator import sandbox_demo as demo


REPO_ROOT = Path(__file__).resolve().parents[2]
SPLITS = REPO_ROOT / "docs/milestone-2/splits-v1"
CALLS = REPO_ROOT / "artifacts/milestone-4/validation-1/Q4_K_M/tier1/calls.jsonl"
DEMO_CASES = ("case-000123", "case-001478", "case-002332")  # approved by the operator, 2026-11-11


def _first(name: str) -> str:
    return (SPLITS / f"{name}.txt").read_text(encoding="utf-8").split()[0]


@pytest.mark.parametrize("split", ["test_in_distribution", "test_held_out"])
def test_test_cases_are_refused_by_name(split):
    case_id = _first(split)
    with pytest.raises(demo.DemoRefused, match=f"{case_id} is a {split} case: the demo never runs test cases"):
        demo.check_case(case_id)


def test_only_validation_cases_run():
    with pytest.raises(demo.DemoRefused, match="not a tier 1 validation case"):
        demo.check_case(_first("train"))
    with pytest.raises(demo.DemoRefused, match="not a tier 1 validation case"):
        demo.check_case("case-999999")
    for case_id in DEMO_CASES:
        demo.check_case(case_id)


def test_a_test_list_wins_even_if_a_case_were_also_listed_as_validation(tmp_path):
    for name, ids in {"validation": "case-1 case-2", "test_in_distribution": "case-2", "test_held_out": "case-3",
                      "train": "case-4"}.items():
        (tmp_path / f"{name}.txt").write_text(ids + "\n", encoding="utf-8")
    demo.check_case("case-1", tmp_path)
    with pytest.raises(demo.DemoRefused, match="test_in_distribution"):
        demo.check_case("case-2", tmp_path)


def test_the_command_refuses_a_test_case_before_checking_or_starting_anything(tmp_path, capsys):
    code = demo.main(["--case", _first("test_held_out"), "--gguf-dir", str(tmp_path / "none"),
                      "--tokenizer", str(tmp_path / "none"), "--llama-cpp", str(tmp_path / "none"),
                      "--out", str(tmp_path / "out")])
    assert code == 2 and "the demo never runs test cases" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_the_probe_and_run_descriptions():
    compact = {"task": "Please handle support ticket T-1.", "run": {"status": "completed", "error_type": None},
               "steps": [{"tool": "lookup_account", "args": {"account_id": "A-1"}, "outcome": "failed",
                          "error": {"type": "ToolUnavailableError", "message": "service unavailable"}}],
               "discrepancies": [], "probes": []}
    assert demo.describe_run(compact)[2] == ('  1. lookup_account({"account_id": "A-1"}) -> failed: '
                                             '{"message": "service unavailable", "type": "ToolUnavailableError"}')
    probe = {"tool": "find_owners", "args": {"customer_ref": "C-1"}, "outcome": "succeeded",
             "observation": {"account_ids": ["A-2"], "customer_ref": "C-1"}, "changed_state": False}
    assert demo.describe_probe(probe) == ('probe find_owners({"customer_ref": "C-1"}) in a sandboxed fork -> succeeded: '
                                          '{"account_ids": ["A-2"], "customer_ref": "C-1"}')
    assert demo.label_rule({"rule": "smallest_verified_change"}) == "smallest_verified_change"
    assert demo.label_rule({"run_label": {"rule": "outcome_correct"}}) == "outcome_correct"


needs_logs = pytest.mark.skipif(not CALLS.is_file() or not (REPO_ROOT / "artifacts/milestone-2/dataset-v2").is_dir(),
                                reason="the dataset and the validation run's logs are gitignored")


def _replay(case_id: str):
    calls = sorted((c for c in map(json.loads, CALLS.open(encoding="utf-8"))
                    if c["case_id"] == case_id and not c.get("discarded")), key=lambda c: c["call"])
    replies = iter(c["text"] for c in calls)
    seen = []

    def generate(system, user):
        seen.append((system, user))
        return SimpleNamespace(text=next(replies), prompt_tokens=None, new_tokens=None)

    return generate, seen, len(calls)


@needs_logs
def test_the_three_demo_cases_reproduce_the_logged_validation_episodes():
    assert PROMPT_VERSION == 2
    lines = []
    results = {}
    for case_id in DEMO_CASES:
        generate, seen, logged_calls = _replay(case_id)
        results[case_id] = demo.run_demo(case_id, generate, log=lines.append)
        assert results[case_id]["matches_validation_run"] is True and len(seen) == logged_calls
        assert all(system == system_prompt(1) for system, _ in seen)  # prompt version 2, tier 1, as validated
        assert '"format":"compact-evidence-v1"' in seen[0][1]

    healthy, swap, failure = (results[c] for c in DEMO_CASES)
    assert healthy["row"]["correct"] and healthy["episode"]["final"]["verb"] == "no_intervention"
    assert [p["verb"] for p in healthy["episode"]["probes"]] == ["find_owners"] and "after" not in healthy["verification"]

    assert swap["row"]["correct"] and swap["row"]["exact"] and swap["episode"]["final"]["verb"] == "set_mapping"
    assert swap["verification"]["before"]["checks"] == {"target_queue": False, "target_account": False}
    assert swap["verification"]["after"]["checks"] == {"target_queue": True, "target_account": True}
    assert swap["verification"]["applied"]["task_rerun"] is True

    assert not failure["row"]["correct"] and failure["episode"]["final"]["verb"] == "rerun"
    assert failure["rule"] == "persistent_tool_error" and failure["row"]["label"]["verb"] == "abstain"
    assert failure["verification"]["after"]["checks"]["target_queue"] is False  # the re-run still cannot route it
    assert "verdict (episodes.score): WRONG" in lines and "verdict (episodes.score): CORRECT, exactly the label" in lines

"""The Linux agreement check's memory guard, comparison and refusal outside the image (no model, no Docker)."""

from __future__ import annotations

import io
import contextlib

from packages.support_evaluator import linux_agreement as check


def test_memory_is_read_from_proc_meminfo_and_the_guard_fits_one_server():
    memory = check.meminfo("MemTotal:        8025604 kB\nMemFree:  100 kB\nMemAvailable:    7500000 kB\n")
    assert memory == {"MemTotal": 8025604 * 1024, "MemAvailable": 7500000 * 1024}
    assert memory["MemTotal"] >= check.MIN_MEMORY_BYTES  # Docker Desktop's 7.654 GiB VM qualifies
    assert check.MIN_MEMORY_BYTES > 5_100_000_000  # above Q8_0's peak on the Mac


def _calls(case: str, *verbs: str) -> list[dict]:
    actions = {"no_intervention": '{"action": "decide", "verb": "no_intervention", "args": {}}',
               "abstain": '{"action": "decide", "verb": "abstain", "args": {}}',
               "resolve": '{"action": "probe", "verb": "resolve", "args": {"customer_ref": "C-3103"}}'}
    return [{"case_id": case, "call": i, "text": actions[v]} for i, v in enumerate(verbs)]


def test_agreement_compares_whole_episodes_and_first_actions():
    linux = _calls("a", "resolve", "abstain") + _calls("b", "resolve", "no_intervention") + _calls("c", "abstain")
    mac = _calls("a", "resolve", "abstain") + _calls("b", "resolve", "abstain") + _calls("c", "no_intervention") \
        + _calls("d", "abstain")
    result = check.agreement(linux, mac, ["a", "b", "c"])
    assert result == {"cases": 3, "same_episode": 1, "same_first_action": 2, "differing_episodes": ["b", "c"]}
    assert check.agreement([], mac, ["d"])["same_episode"] == 0  # a case missing on Linux never agrees


def test_it_refuses_to_run_outside_the_check_image(tmp_path, monkeypatch):
    monkeypatch.setattr(check, "BUILD_INFO", tmp_path / "missing-build-info.json")
    err = io.StringIO()

    with contextlib.redirect_stderr(err):
        code = check.main(["run", "--gguf-dir", str(tmp_path), "--tokenizer", str(tmp_path), "--runs", str(tmp_path),
                           "--out", str(tmp_path / "out")])

    assert code == 2 and "check image" in err.getvalue()
    assert not (tmp_path / "out").exists()

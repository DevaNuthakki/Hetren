"""The report is reproducible from existing rows without a new evaluation.

CI has no gitignored artifacts, so it checks the report's coverage and CLI
failure behaviour. The exact CLI regeneration test runs on the operator's
machine, following the Milestone 2 report test's artifact/slow convention.
"""

import hashlib
import itertools
import subprocess
import sys

import pytest

from packages.support_evaluator import milestone3_results as results


def test_committed_report_keeps_fixed_prose_and_all_primary_comparisons():
    text = results.RESULTS.read_text(encoding="utf-8")
    assert text.startswith(results.HEAD) and text.endswith(results.TAIL)
    primary = text.split("### Primary endpoints\n", 1)[1].split("### All paired comparisons\n", 1)[0]
    paired = text.split("### All paired comparisons\n", 1)[1].split("### Secondary decision metrics\n", 1)[0]
    for name, _, _ in results.m2.SETS:
        for system in results.SYSTEMS:
            assert primary.count(f"| {name} | {system} |") == 1
        for a, b in itertools.combinations(results.SYSTEMS, 2):
            assert paired.count(f"| {name} | {a} − {b} |") == 1
        assert f"### Per family: {name}\n" in text
    for section in ("Training history", "Selection and full validation", "F6 and F7: held-out findings", "Limitations"):
        assert f"## {section}\n" in text


def test_original_baseline_primary_results_and_comparisons_are_preserved():
    previous = results.m2.RESULTS.read_text(encoding="utf-8")
    current = results.RESULTS.read_text(encoding="utf-8")
    primary = previous.split("### Primary endpoints\n", 1)[1].split("### Secondary metrics\n", 1)[0]
    rows = [line for line in primary.splitlines() if line.startswith(("| Tier ", "| Live |"))]
    assert len(rows) == 30  # 15 system/set rows and 15 pair/set rows (two endpoints per pair)
    assert all(line in current.splitlines() for line in rows)


@pytest.mark.parametrize("content", [b"report\n", b"report\r\n", b"changed\n", None])
def test_check_compares_exact_bytes_without_writing(tmp_path, monkeypatch, content):
    out = tmp_path / "RESULTS.md"
    if content is not None:
        out.write_bytes(content)
    monkeypatch.setattr(results, "row_files", lambda: [])
    monkeypatch.setattr(results, "render", lambda: "report\n")
    assert results.main(["--check", "--out", str(out)]) == (0 if content == b"report\n" else 1)
    assert (out.read_bytes() if out.exists() else None) == content


def test_missing_rows_stop_before_rendering(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(results, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(results, "row_files", lambda: [tmp_path / "missing.jsonl"])
    monkeypatch.setattr(results, "render", lambda: pytest.fail("missing rows must not be analyzed"))
    assert results.main(["--check"]) == 2
    assert "recorded rows are missing: missing.jsonl" in capsys.readouterr().err


def test_rows_must_match_their_numbered_run_log_before_being_read(tmp_path):
    rows = tmp_path / "rows-live.jsonl"
    content = b'{"case_id": "run-0001"}\n'
    rows.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    log = f"| 5 | `rows-live.jsonl` `{digest}` |\n"
    assert results._rows(rows, log, run=5) == [{"case_id": "run-0001"}]
    with pytest.raises(ValueError, match="sha256 does not match"):
        results._rows(rows, log, run=6)
    rows.write_bytes(b"this changed and is no longer JSON\n")
    with pytest.raises(ValueError, match="sha256 does not match"):
        results._rows(rows, log, run=5)


ARTIFACTS_PRESENT = all(p.exists() for p in results.row_files())
SETS = [name for name, _, _ in results.m2.SETS]
BASELINES = [s for s in results.SYSTEMS if s != results.FT]


@pytest.fixture(scope="module")
def computed():
    """Summaries and paired comparisons recomputed from the logged rows (offline)."""
    data = results.load()
    return data, results.comparisons(data)


def _verdict(paired, name, a, endpoint):
    """Verdict of baseline ``a`` against the fine-tuned model (always system B)."""
    return paired[name, a, results.FT][endpoint]["verdict"]


def _family(data, name, system, kind):
    return results.decision_metrics([r for r in data[name, system][0] if r["case_kind"] == kind])


def _k_n(m):
    return m["k"], m["n"]


@pytest.mark.slow
@pytest.mark.skipif(not ARTIFACTS_PRESENT, reason="recorded rows are gitignored")
def test_fixed_prose_findings_hold_against_the_computed_summaries(computed):
    data, paired = computed
    text = results.RESULTS.read_text(encoding="utf-8")
    # Finding 1: fine-tuned accuracy better than both model baselines on all five sets.
    assert "Every accuracy comparison with GPT-4.1 and untrained Qwen favours fine-tuning" in text
    for name in SETS:
        for baseline in ("GPT-4.1", "Qwen untrained"):
            assert _verdict(paired, name, baseline, "decision_accuracy") == "B better", (name, baseline)
    # Finding 2: rules better on accuracy on four sets, tier 2 held-out n.s.; wrong interventions
    # favour fine-tuning on both held-out sets and live, n.s. on the two in-distribution sets.
    assert "Rules retain an accuracy advantage on four sets." in text
    for name in SETS:
        expected = "no significant difference" if name == "Tier 2 held-out" else "A better"
        assert _verdict(paired, name, "rules v1", "decision_accuracy") == expected, name
        expected = "no significant difference" if "in-distribution" in name else "B better"
        assert _verdict(paired, name, "rules v1", "wrong_interventions_on_healthy") == expected, name
    # Finding 4: more wrong interventions than untrained Qwen on every set, significantly on both
    # held-out sets, largest on tier 2 held-out; no invalid actions, but failed recovery calls remain.
    wrong = {name: (data[name, results.FT][1]["wrong_interventions_on_healthy"]["rate"]
                    - data[name, "Qwen untrained"][1]["wrong_interventions_on_healthy"]["rate"]) for name in SETS}
    assert all(difference >= 0 for difference in wrong.values()) and max(wrong, key=wrong.get) == "Tier 2 held-out"
    for name in SETS:
        expected = "A better" if "held-out" in name else "no significant difference"
        assert _verdict(paired, name, "Qwen untrained", "wrong_interventions_on_healthy") == expected, name
        assert data[name, results.FT][1]["invalid_actions"]["k"] == 0, name
    assert sum(data[name, results.FT][1]["failed_recovery_calls"] for name in SETS) > 0
    # Finding 5's headline: the baselines fixed no two-recovery label; the fine-tuned model fixed some.
    for name in results.TIER2_SETS:
        assert all(data[name, s][1]["sequence"]["two_recovery_labels"]["k"] == 0 for s in BASELINES), name
        assert data[name, results.FT][1]["sequence"]["two_recovery_labels"]["k"] > 0, name
    # Finding 6: F7 includes successful recoveries.
    assert _family(data, "Tier 1 held-out", results.FT, "tier_format_drift")["verified_recovery_rate"]["k"] > 0


@pytest.mark.slow
@pytest.mark.skipif(not ARTIFACTS_PRESENT, reason="recorded rows are gitignored")
def test_fixed_prose_f6_and_f7_paragraphs_hold_against_the_computed_summaries(computed):
    data, _ = computed
    ft = results.FT
    # F6: complete-evidence escalation never correct (0/400); live F6 has 29 abstain labels and one
    # healthy run; live abstain recall over all families is 0/44.
    f6 = _family(data, "Tier 1 held-out", ft, "queue_misconfiguration")
    assert _k_n(f6["abstain"]["recall"]) == (0, 400)
    live_f6 = _family(data, "Live", ft, "queue_misconfiguration")
    assert live_f6["abstain"]["recall"]["n"] == 29 and live_f6["no_intervention"]["recall"]["n"] == 1
    assert _k_n(data["Live", ft][1]["abstain"]["recall"]) == (0, 44)
    # F7: 318/480 on tier 1 held-out; live 29/30, all 30 healthy, both model baselines 30/30.
    assert _k_n(_family(data, "Tier 1 held-out", ft, "tier_format_drift")["decision_accuracy"]) == (318, 480)
    live_f7 = {s: _family(data, "Live", s, "tier_format_drift") for s in results.SYSTEMS}
    assert _k_n(live_f7[ft]["decision_accuracy"]) == (29, 30)
    assert live_f7[ft]["no_intervention"]["recall"]["n"] == 30
    for baseline in ("GPT-4.1", "Qwen untrained"):
        assert _k_n(live_f7[baseline]["decision_accuracy"]) == (30, 30), baseline


@pytest.mark.slow
@pytest.mark.skipif(not ARTIFACTS_PRESENT, reason="recorded rows are gitignored")
def test_check_reproduces_the_committed_results_exactly():
    completed = subprocess.run(
        [sys.executable, "-m", "packages.support_evaluator.milestone3_results", "--check"],
        cwd=results.REPO_ROOT, capture_output=True, text=True, timeout=300,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "matches the regenerated results" in completed.stdout

"""The demo video script (step 8): its cases are the approved validation cases, its commands run, and every number
it quotes is in a committed source."""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess

import pytest

from packages.support_evaluator import sandbox_demo


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (REPO_ROOT / "docs/milestone-4/DEMO_SCRIPT.md").read_text(encoding="utf-8")
DEMO_CASES = {"case-000123", "case-001478", "case-002332"}  # approved by the operator, 2026-11-11
ROWS = REPO_ROOT / "artifacts/milestone-4/validation-1/Q4_K_M/tier1/rows-tier1-validation.jsonl"


def _command(prefix: str) -> str:
    lines = [line for line in SCRIPT.splitlines() if line.startswith(prefix)]
    assert len(lines) == 1, prefix
    return lines[0]


def test_the_cases_are_the_approved_validation_cases():
    assert set(re.findall(r"case-\d{6}", SCRIPT)) == DEMO_CASES
    for case_id in DEMO_CASES:
        sandbox_demo.check_case(case_id)  # raises for a test or non-validation case
    assert re.findall(r"^DEMO (case-\d{6})$", SCRIPT, re.MULTILINE) == ["case-000123", "case-001478", "case-002332"]


def test_the_modules_and_files_it_names_exist():
    for module in re.findall(r"python -m (packages(?:\.\w+)+)", SCRIPT):
        assert (REPO_ROOT / (module.replace(".", "/") + ".py")).is_file(), module
    for path in set(re.findall(r"\b((?:docs|deploy|packages|tests|scripts)/[\w./-]+\.\w+)", SCRIPT)):
        assert (REPO_ROOT / path).is_file(), path


def test_the_image_and_model_are_the_release_ones():
    assert set(re.findall(r"ghcr\.io/devanuthakki/hetren-cli:(\S+)", SCRIPT)) == {"v1.0.0"}
    chart = (REPO_ROOT / "deploy/helm/hetren/values.yaml").read_text(encoding="utf-8")
    revision = re.search(r"--revision ([0-9a-f]{40})", SCRIPT).group(1)
    assert revision in chart and "Harsha1412/hetren-qwen3-4b-diagnosis" in SCRIPT
    assert "docker run --rm --network none" in SCRIPT and "diagnose --compact /work/visible.jsonl" in SCRIPT


def test_the_f6_numbers_are_the_logged_test_results():
    card = (REPO_ROOT / "docs/milestone-4/model-card.md").read_text(encoding="utf-8")
    assert "0.0% (0/400)" in card and "0 of 44 abstain labels" in card
    assert "0 of\n400" in SCRIPT or "0 of 400" in SCRIPT
    run = subprocess.run(["bash", "-c", _command("grep -n ")], cwd=REPO_ROOT, capture_output=True, text=True)
    assert run.returncode == 0 and "0.0% (0/400)" in run.stdout and "0 of 44 abstain labels" in run.stdout


def test_the_load_test_line_runs_and_its_numbers_are_logged():
    run = subprocess.run(["bash", "-c", _command("python3 -c ")], cwd=REPO_ROOT, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    lines = run.stdout.splitlines()
    assert lines[0] == "c01 1 users: 0.067 diagnoses/s, p50 8.4 s, rejected or failed 0%"
    assert lines[-1] == "c16 16 users: 0.27 diagnoses/s, p50 0.0 s, rejected or failed 98%"
    log = (REPO_ROOT / "docs/milestone-4/DEPLOY_LOG.md").read_text(encoding="utf-8")
    assert "0.27 diagnoses per second" in log and "**171 s**" in log and "about 150 s" in log
    assert "Cached best case" in SCRIPT and "171 seconds" in SCRIPT and "0.27 diagnoses per second" in SCRIPT


@pytest.mark.skipif(not ROWS.is_file(), reason="the validation run's rows are gitignored")
def test_the_25_of_30_retries_are_the_logged_validation_runs():
    rows = [json.loads(line) for line in ROWS.open(encoding="utf-8")]
    abstain = [r for r in rows if r["case_kind"] == "mishandled_tool_error" and r["label"]["verb"] == "abstain"]
    assert len(abstain) == 30 and sum(r["final"]["verb"] == "rerun" for r in abstain) == 25
    assert "25 times out of 30" in SCRIPT


def _card_row(label: str) -> list[float]:
    """The percentages of a model card results row: rules v1, GPT-4.1, untrained Qwen, this model."""
    card = (REPO_ROOT / "docs/milestone-4/model-card.md").read_text(encoding="utf-8")
    line = next(line for line in card.splitlines() if line.startswith(f"| {label} |"))
    cells = [cell.strip() for cell in line.strip("|").split("|")][2:]
    return [float(re.search(r"(\d+\.\d)%", cell).group(1)) for cell in cells]


def _title_card() -> str:
    return SCRIPT.split("### 7. Results at a glance", 1)[1].split("```text\n", 1)[1].split("```", 1)[0]


ACCURACY_ROWS = {"Tier 1 in-distribution": "Tier 1 in-distribution: accuracy",
                 "Tier 1 held-out families": "Tier 1 held-out families: accuracy",
                 "Tier 2 in-distribution": "Tier 2 in-distribution: accuracy",
                 "Tier 2 held-out families": "Tier 2 held-out families: accuracy",
                 "Live gpt-4.1-mini runs": "Live (runs of a `gpt-4.1-mini` agent): accuracy"}


def test_the_results_card_accuracy_table_is_the_model_cards():
    card = _title_card()
    for label, row in ACCURACY_ROWS.items():
        line = next(line for line in card.splitlines() if line.startswith(label))
        tuned, gpt, untrained = (float(x) for x in re.findall(r"(\d+\.\d)%", line))
        rules, card_gpt, card_untrained, card_tuned = _card_row(row)
        assert (tuned, gpt, untrained) == (card_tuned, card_gpt, card_untrained), label
        assert tuned > gpt and tuned > untrained, label  # the claim the next line makes
    text = (REPO_ROOT / "docs/milestone-4/model-card.md").read_text(encoding="utf-8")
    assert "fine-tuning is more accurate than GPT-4.1 and than the untrained base on every set" in text
    assert "More accurate than both on every set (paired bootstrap, 95%)." in card


def test_the_results_card_other_lines_are_the_model_cards():
    card = _title_card()

    def tuned_vs(row: str, column: int) -> str:
        values = _card_row(row)
        return f"{values[3]:.1f}% vs {values[column]:.1f}%"

    gpt, rules = 1, 0
    assert f"{tuned_vs('Tier 1 in-distribution: wrong interventions', gpt)}".replace("0.0% vs", "0.0% vs GPT-4.1") in card
    assert f"{tuned_vs('Live: wrong interventions', gpt)} (live)" in card
    assert f"{tuned_vs('Tier 1 held-out families: wrong interventions', gpt)} (tier 1)" in card
    assert f"{tuned_vs('Tier 2 held-out families: wrong interventions', gpt)} (tier 2)" in card
    assert f"{_card_row('Tier 1 in-distribution: accuracy')[rules]:.1f}% vs 73.8% (tier 1)" in card
    assert f"{_card_row('Tier 2 in-distribution: accuracy')[rules]:.1f}% vs 71.1% (tier 2)" in card
    text = (REPO_ROOT / "docs/milestone-4/model-card.md").read_text(encoding="utf-8")
    assert "**0.0% (0/400)**" in text and "abstain recall 0.0% (0/400)" in card
    assert "| −0.13 [−1.50, +1.25] |" in text and "(criterion: lower bound ≥ −2 points)" in text
    assert "within the 2-point margin of fp16: -0.13 points pooled [-1.50, +1.25]" in card

"""The README (v1.0.0): every result it quotes is in the model card or the logs, its links and commands point to
things that exist, and the release identifiers agree with the rest of the repository."""

from __future__ import annotations

from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[2]
README = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
CARD = (REPO_ROOT / "docs/milestone-4/model-card.md").read_text(encoding="utf-8")
DEPLOY_LOG = (REPO_ROOT / "docs/milestone-4/DEPLOY_LOG.md").read_text(encoding="utf-8")
EXPORT_LOG = (REPO_ROOT / "docs/milestone-4/EXPORT_LOG.md").read_text(encoding="utf-8")
REVISION = "3e875e4e8719acef839dc18e220a3ae498a1975b"

ROWS = {  # README row -> the model card's row, per table
    "accuracy": {"Tier 1 in-distribution": "Tier 1 in-distribution: accuracy",
                 "Tier 1 held-out families": "Tier 1 held-out families: accuracy",
                 "Tier 2 in-distribution": "Tier 2 in-distribution: accuracy",
                 "Tier 2 held-out families": "Tier 2 held-out families: accuracy",
                 "Live (`gpt-4.1-mini` agent runs)": "Live (runs of a `gpt-4.1-mini` agent): accuracy"},
    "wrong": {"Tier 1 in-distribution": "Tier 1 in-distribution: wrong interventions",
              "Tier 1 held-out families": "Tier 1 held-out families: wrong interventions",
              "Tier 2 in-distribution": "Tier 2 in-distribution: wrong interventions",
              "Tier 2 held-out families": "Tier 2 held-out families: wrong interventions",
              "Live": "Live: wrong interventions"},
}


def _cells(text: str, label: str) -> list[str]:
    line = next(line for line in text.splitlines() if line.startswith(f"| {label} |"))
    return [cell.strip() for cell in line.strip().strip("|").split("|")][1:]


def _percent(cell: str) -> float:
    return float(re.search(r"(\d+\.\d)%", cell).group(1))


def _table(heading: str) -> str:
    return README.split(heading, 1)[1].split("\n\n", 2)[1]


def test_both_results_tables_are_the_model_cards():
    for heading, kind in (("**Decision accuracy**", "accuracy"), ("**Wrong interventions on healthy runs**", "wrong")):
        table = _table(heading)
        assert len([line for line in table.splitlines() if line.startswith("| T") or line.startswith("| L")]) == 5
        for label, card_label in ROWS[kind].items():
            mine, theirs = _cells(table, label), _cells(CARD, card_label)
            assert re.sub(r"\D", "", mine[0]) == re.sub(r"\D", "", theirs[0]), label  # cases / healthy runs
            assert [_percent(c) for c in mine[1:]] == [_percent(c) for c in theirs[1:]], label


def test_the_claims_under_the_tables_are_the_model_cards():
    assert "more accurate than GPT-4.1 and the untrained\n  base on every set" in README
    assert "fine-tuning is more accurate than GPT-4.1 and than the untrained base on every set" in CARD
    assert "more accurate on four of the five sets. On tier 2 held-out the difference is not significant." in README
    assert "the rules policy is more accurate on four of the five sets. On tier 2 held-out the difference is not significant." in CARD
    assert "**0.0% (0/400)**" in README and "**0.0% (0/400)**" in CARD
    assert "0 of 44 abstain labels" in README and "0 of 44 abstain labels" in CARD
    assert "−0.13 points [−1.50, +1.25]" in README and "| −0.13 [−1.50, +1.25] |" in CARD
    assert "lower bound ≥ −2 points" in CARD and "2-point margin" in README
    assert "42.9% of healthy runs" in README and "**42.9% (24/56)" in CARD


def test_the_deployment_and_platform_numbers_are_logged():
    assert "took 162 s" in README and "generation 162.4 s" in DEPLOY_LOG
    assert "171 s later" in README and "**171 s**" in DEPLOY_LOG
    assert "about 0.27 diagnoses per second" in README and "0.27 diagnoses per second" in DEPLOY_LOG
    assert "cached best case" in README and "about 8 s per diagnosis against about 150 s fresh" in README
    assert "about 8 s, against about 136–162 s" in DEPLOY_LOG
    assert "$2.27" in README and "**$2.27**" in DEPLOY_LOG and "$0.48" in README and "$0.48" in DEPLOY_LOG
    assert "16\ndistinct inputs" in README or "16 distinct inputs" in README
    assert "18 of 20" in README and "| Q4_K_M | **18 of 20** |" in EXPORT_LOG
    assert "20 of 20" in README and "| Q8_0 | **20 of 20** |" in EXPORT_LOG


def test_the_scope_and_licences_are_stated():
    assert "not a general\n> agent-trace diagnoser" in README and "single-recovery (tier 1) runs only" in README
    assert "Code and model: Apache-2.0" in README and "Data: CC BY 4.0" in README
    assert "AVX2, FMA and F16C" in README and "`linux/amd64`" in README


def test_the_release_identifiers_agree():
    assert set(re.findall(r"ghcr\.io/devanuthakki/hetren-cli:([^\s`]+)", README)) == {"v1.0.0"}
    assert set(re.findall(r"--revision ([0-9a-f]{40})", README)) == {REVISION}
    assert REVISION in (REPO_ROOT / "deploy/helm/hetren/values.yaml").read_text(encoding="utf-8")
    assert "Harsha1412/hetren-qwen3-4b-diagnosis" in README and "Harsha1412/hetren-support-runs" in README
    assert "`620d2225c` (build 11669)" in README


def test_links_files_and_modules_exist():
    for target in re.findall(r"\]\(((?!https?://)[^)#]+)\)", README):
        assert (REPO_ROOT / target).exists(), target
    for module in re.findall(r"python -m (packages(?:\.\w+)+)", README):
        assert (REPO_ROOT / (module.replace(".", "/") + ".py")).is_file() or \
            (REPO_ROOT / module.replace(".", "/") / "__main__.py").is_file(), module
    for path in ("requirements-cli.txt", "requirements-dev.txt", "tests/fixtures/hetren_cli/compact_first_step.json",
                 "docs/milestone-2/TEST_RUN_LOG.md", "docs/milestone-3/VALIDATION_LOG.md", "notebooks/milestone-3",
                 "docs/milestone-4/EXPORT_RUNBOOK.md", "docs/milestone-4/DEPLOY_RUNBOOK.md", "tests/qualification"):
        assert path in README and (REPO_ROOT / path).exists(), path


def test_the_moved_sections_are_kept():
    milestone1 = (REPO_ROOT / "docs/milestone-1/README.md").read_text(encoding="utf-8")
    assert "## Live recording facts" in milestone1 and "about $0.005 at list prices" in milestone1
    portfolio = (REPO_ROOT / "docs/portfolio/README.md").read_text(encoding="utf-8")
    assert "## Claim limits" in portfolio and "PASS != VERIFIED" in portfolio

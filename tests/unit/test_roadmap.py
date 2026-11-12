"""The roadmap (docs/ROADMAP.md) and the README's audit additions: what each says exists today is in the repository,
and the roadmap marks everything else as planned."""

from __future__ import annotations

import json
from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[2]
ROADMAP = (REPO_ROOT / "docs/ROADMAP.md").read_text(encoding="utf-8")
README = (REPO_ROOT / "README.md").read_text(encoding="utf-8")


def read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_the_roadmap_is_labelled_and_linked():
    assert "> **Planned, not done.**" in ROADMAP and "There are no\n> dates." in ROADMAP
    assert "| Roadmap | [`docs/ROADMAP.md`](docs/ROADMAP.md): planned, not done |" in README
    items = re.findall(r"^- \*\*(.+?)\*\*", ROADMAP, re.MULTILINE)
    assert len(items) == 18, items
    for section in ROADMAP.split("\n- **")[1:]:
        assert "**Today:**" in section and "**Planned:**" in section, section[:60]


def test_the_only_date_is_the_retirement_and_it_is_sourced():
    assert re.findall(r"(?<![\w-])20\d\d-\d\d-\d\d(?![\w-])", ROADMAP) == ["2027-01-14"]  # not the model ID's
    assert "leaves the API on 2027-01-14" in read("docs/milestone-4/dataset-card.md")


def test_the_files_it_names_exist():
    for path in set(re.findall(r"`((?:docs|deploy|packages|environments|examples|\.github)/[^`]+|requirements-cli\.txt)`",
                               ROADMAP)):
        assert (REPO_ROOT / path).exists(), path
    for path in ("linux_agreement.py",):
        assert (REPO_ROOT / "packages/support_evaluator" / path).is_file()


def test_what_it_says_exists_today_does():
    cli = read("requirements-cli.txt")
    for package, version in re.findall(r"`(transformers|fsspec)` ([\d.]+)", ROADMAP.split("**Planned:**", 1)[0]):
        assert f"{package}=={version}\n" in cli, package
    assert set(re.findall(r"platforms: (\S+)", read(".github/workflows/ci.yml"))) == {"linux/amd64"}
    assert not (REPO_ROOT / "pyproject.toml").exists() and not (REPO_ROOT / "setup.py").exists()
    inputs = json.loads(read("deploy/loadtest/inputs.json"))
    assert len(inputs["inputs"]) == 16 and "training examples only" in inputs["source"] and "16 distinct inputs" in ROADMAP
    log = read("docs/milestone-4/DEPLOY_LOG.md")
    assert "about 150 s" in log and "about 150 s for a fresh prompt" in ROADMAP
    card = read("docs/milestone-4/model-card.md")
    assert "**0.0% (0/400)**" in card and "0 of 44 abstain labels" in card
    protocol = read("docs/milestone-2/EVAL_PROTOCOL.md")
    assert "**Score:** S = ½(A₁ + A₂) − W" in protocol and "S = ½(A₁ + A₂) − W" in ROADMAP
    assert "`abstain` recall" in protocol.split("**Monitoring only (never used for the choice):**", 1)[1].split("\n", 1)[0]
    assert "is a possible later experiment and needs its own amendment" in protocol
    assert "loss on the assistant tokens only" in protocol
    assert "no few-shot strong-model baseline or contrast-partner ablation was tested" in read("docs/milestone-3/RESULTS.md")
    inputs_py = read("packages/hetren_cli/inputs.py")
    assert 'SUPPORT_TOOLS = ("read_ticket", "lookup_account", "route_ticket")' in inputs_py
    assert "compact-evidence-v2 is a tier 2 input" in inputs_py
    integrations = {p.name for p in (REPO_ROOT / "packages/integrations").iterdir()
                    if p.is_dir() and any(f.suffix == ".py" for f in p.iterdir())}
    assert integrations == {"openai_agents"}
    api = read("packages/hetren_cli/api.py")
    for name in ("hetren_diagnoses_total", "hetren_rejected_total", "hetren_http_responses_total",
                 "hetren_request_seconds", "hetren_generation_seconds"):
        assert name in api, name
    assert re.search(r"managed_prometheus \{\s+enabled = false", read("deploy/terraform/gke/cluster.tf"))
    assert not list((REPO_ROOT / "deploy").rglob("*dashboard*"))
    dataset_card = read("docs/milestone-4/dataset-card.md")
    assert "can no longer serve as a blind test" in dataset_card and "new, unpublished seeds" in dataset_card


def test_the_readme_framing_matches_the_example():
    case = json.loads(read("examples/v2-case-001478.jsonl"))
    evidence = case["steps"][0]["input"]
    assert evidence["run"]["status"] == "completed"
    assert [s["outcome"] for s in evidence["steps"]] == ["succeeded"] * 3
    assert "every tool call succeeds and the run\ncompletes" in README
    assert "applying a recovery is left to a human" in README


def test_the_readme_amendments_licences_and_acknowledgements_are_sourced():
    protocol = read("docs/milestone-2/EVAL_PROTOCOL.md")
    for date, topic in re.findall(r"  - Amendment \d \((\d{4}-\d\d-\d\d)\): (.+)", README):
        assert re.search(rf"^### Amendment \d \({date}\)", protocol, re.MULTILINE), date
    assert len(re.findall(r"^### Amendment \d", protocol, re.MULTILINE)) == 2 and "There are two" in README
    notice = read("NOTICE")
    assert "Qwen3-4B-Instruct-2507 by the Qwen team (Alibaba Cloud), licensed under the Apache License" in notice
    assert "No model weights are included in this repository." in notice
    assert "openai-agents==0.24.0" in read("requirements-dev.txt") and "`openai-agents` 0.24.0" in README
    assert "https://github.com/ggml-org/llama.cpp.git" in read("docker/hetren-cli/Dockerfile")
    assert "peft==" in read("notebooks/milestone-3/qlora_training.ipynb")
    assert "Kaggle" in read("docs/milestone-2/TEST_RUN_LOG.md") and "Kaggle" in read("docs/milestone-3/VALIDATION_LOG.md")
    assert "Kaggle, GPU T4" in read("docs/milestone-4/EXPORT_LOG.md")
    assert "Free Trial" in read("docs/milestone-4/DEPLOY_LOG.md")
    assert "license: cc-by-4.0" in read("docs/milestone-4/dataset-card.md")
    limitations = README.split("## Limitations", 1)[1].split("\n## ", 1)[0]
    cli = read("requirements-cli.txt")
    for package, version in re.findall(r"`(transformers|fsspec)` ([\d.]+)", limitations):
        assert f"{package}=={version}\n" in cli, package
    assert "## Acknowledgements" in README and "## Reporting issues" in README

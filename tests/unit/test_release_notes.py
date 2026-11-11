"""The v1.0.0 release notes: their hashes match the export manifest and the release record, their links and
revisions are the released ones, and every result they quote is the model card's."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from packages.hetren_cli.models import DEFAULT_REVISION


REPO_ROOT = Path(__file__).resolve().parents[2]
NOTES = (REPO_ROOT / "docs/RELEASE_NOTES.md").read_text(encoding="utf-8")
CARD = (REPO_ROOT / "docs/milestone-4/model-card.md").read_text(encoding="utf-8")
PLAN = (REPO_ROOT / "docs/milestone-4/PLAN.md").read_text(encoding="utf-8")
MANIFEST_PATH = REPO_ROOT / "docs/milestone-4/export.manifest.json"
DIGEST = "sha256:efafa907ab9cd6c87965fc8c00d8818c70e49faa869ee3e15f6f9d21f60e2bc0"  # run #244 (PLAN.md, 8.7)
PDF_SHA256 = "bd2baabcd8d8681027f640fd469a02e8d3c9beca44f84109ffa64a00b2dac77d"  # the layout-only, reproducible rebuild (PLAN.md, 8.7)


def _checksums() -> dict[str, str]:
    table = NOTES.split("## Checksums", 1)[1].split("\n## ", 1)[0]
    return {re.search(r"`([^`]+)`", line).group(1): re.findall(r"`([0-9a-f]{64})`", line)[-1]
            for line in table.splitlines() if line.startswith("| `") or line.startswith("| image")
            if re.findall(r"`([0-9a-f]{64})`", line)}


def test_the_checksums_match_the_manifest_and_the_release_record():
    sums = _checksums()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert sums["export.manifest.json"] == hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
    for name in ("hetren-qwen3-4b-ckpt0792-q4_k_m.gguf", "hetren-qwen3-4b-ckpt0792-q8_0.gguf"):
        assert sums[name] == manifest["gguf"][name]["sha256"], name
    assert sums["hetren-cli:v1.0.0"] == DIGEST.split(":")[1]
    assert sums["TECHNICAL_REPORT.pdf"] == PDF_SHA256
    assert f"`ghcr.io/devanuthakki/hetren-cli:v1.0.0@{DIGEST}`" in PLAN and f"`{PDF_SHA256}`" in PLAN


def test_the_image_digest_is_the_same_everywhere():
    for name, text in (("notes", NOTES), ("README", (REPO_ROOT / "README.md").read_text(encoding="utf-8")),
                       ("model card", CARD)):
        found = set(re.findall(r"hetren-cli:v1\.0\.0@(sha256:[0-9a-f]{64})", text))
        assert found == {DIGEST}, name
    assert "hetren-cli:<tag>" not in CARD


def test_the_revisions_and_links_are_the_released_ones():
    assert f"revision `{DEFAULT_REVISION}`" in NOTES
    export_log = (REPO_ROOT / "docs/milestone-4/EXPORT_LOG.md").read_text(encoding="utf-8")
    dataset_commit = re.search(r"`Harsha1412/hetren-support-runs`\]\([^)]+\), revision `([0-9a-f]{40})`", NOTES).group(1)
    assert f"**`{dataset_commit}`**" in export_log
    assert "679c131c143a8583d5ac1bab133f7f3584ac9a45" in NOTES and "`679c131c143a8583d5ac1bab133f7f3584ac9a45`" in PLAN
    assert "https://github.com/DevaNuthakki/Hetren/blob/v1.0.0/docs/TECHNICAL_REPORT.md" in NOTES
    assert (REPO_ROOT / "docs/TECHNICAL_REPORT.md").is_file()
    assert "| Demo video | to follow |" in NOTES  # replaced with the link once it is recorded


ROWS = {"Tier 1 in-distribution, accuracy": "Tier 1 in-distribution: accuracy",
        "Tier 1 held-out families, accuracy": "Tier 1 held-out families: accuracy",
        "Tier 2 in-distribution, accuracy": "Tier 2 in-distribution: accuracy",
        "Tier 2 held-out families, accuracy": "Tier 2 held-out families: accuracy",
        "Live (`gpt-4.1-mini` runs), accuracy": "Live (runs of a `gpt-4.1-mini` agent): accuracy"}


def _percents(line: str) -> list[float]:
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    return [float(re.search(r"(\d+\.\d)%", cell).group(1)) for cell in cells if re.search(r"\d+\.\d%", cell)]


def test_the_results_are_the_model_cards():
    for label, card_label in ROWS.items():
        mine = _percents(next(l for l in NOTES.splitlines() if l.startswith(f"| {label} |")))
        rules, gpt, untrained, tuned = _percents(next(l for l in CARD.splitlines() if l.startswith(f"| {card_label} |")))
        assert mine == [tuned, gpt, untrained, rules], label
    for phrase in ("0.0% against GPT-4.1's 33.0%", "0.8%\n  against 31.4% live", "7.4% against 0.0% in tier 1",
                   "42.9% against\n  10.7% in tier 2", "0.0% (0/400)", "−0.13 points pooled\n  [−1.50, +1.25]",
                   "0 of 44 abstain labels", "18 of 20 pilot cases", "$3.79 gross"):
        assert phrase in NOTES, phrase


def test_the_scope_and_limitations_are_stated():
    assert "not a general agent-trace diagnoser" in NOTES and "single-recovery (tier 1) runs only" in NOTES
    for heading in ("## Results at a glance", "## Get it", "## Checksums", "## Known limitations", "## Provenance"):
        assert heading in NOTES, heading
    assert "AVX2, FMA and F16C" in NOTES and "cached best case" in NOTES


def test_the_attached_pdf_names_its_commit_and_run():
    provenance = " ".join(NOTES.split("## Provenance", 1)[1].split())
    assert "CI run #245" in provenance and "`643da6a333124d250e0d615b034c1a9786edafb7`" in provenance
    assert "recorded after the build" not in NOTES


def test_the_dependency_advisories_are_listed_with_the_pinned_versions():
    limitations = " ".join(NOTES.split("## Known limitations", 1)[1].split("\n## ", 1)[0].split())
    cli = (REPO_ROOT / "requirements-cli.txt").read_text(encoding="utf-8")
    for package, version in re.findall(r"`(transformers|fsspec)` ([\d.]+)", limitations):
        assert f"{package}=={version}\n" in cli, package  # the versions named are the image's pins
    for ghsa in ("GHSA-27vj-qcqg-25rc", "GHSA-x9r9-c232-4q39", "GHSA-xrqw-3rrv-vx5w", "GHSA-fgcw-684q-jj6r",
                 "GHSA-29pf-2h5f-8g72", "GHSA-69w3-r845-3855"):
        assert ghsa in limitations, ghsa
    assert "**Dependency advisories**" in PLAN

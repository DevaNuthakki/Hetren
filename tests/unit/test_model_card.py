"""The model card's numbers (step 7a): every interval and count comes from RESULTS.md or the export log, and
the hashes and sizes equal the manifest's. Committed with the card."""

from __future__ import annotations

import json
from pathlib import Path
import re

from scripts import hf_release as release


REPO_ROOT = Path(__file__).resolve().parents[2]


CARD = (REPO_ROOT / "docs/milestone-4/model-card.md").read_text(encoding="utf-8")
SOURCES = "\n".join((REPO_ROOT / p).read_text(encoding="utf-8")
                    for p in ("docs/milestone-3/RESULTS.md", "docs/milestone-4/EXPORT_LOG.md"))


def _points(value: str) -> str:
    """'−1.38' (percentage points) as the log writes the fraction: '−0.0138'."""
    sign = value[0] if value[0] in "+−-" else ""
    return f"{sign}{abs(float(value.lstrip('+−-'))) / 100:.4f}"


def test_every_interval_in_the_card_is_in_the_results_or_the_export_log():
    intervals = re.findall(r"\[([+−-]?\d+\.\d+), ([+−-]?\d+\.\d+)\]", CARD)
    assert len(intervals) > 40

    for low, high in intervals:
        assert f"[{low}, {high}]" in SOURCES or f"[{_points(low)}, {_points(high)}]" in SOURCES, (low, high)


def test_every_count_and_its_percentage_in_the_card_agree_with_the_sources():
    counts = re.findall(r"(\d+\.\d)% \((\d+)/(\d+)\)", CARD)
    assert len(counts) >= 13

    for percent, k, n in counts:
        assert f"{k}/{n}" in SOURCES, (k, n)
        assert f"{100 * int(k) / int(n):.1f}" == percent, (percent, k, n)

    for row in re.findall(r"^\| decision accuracy, tier ([12]) \((\d+)\) \|(.*)$", CARD, re.MULTILINE):
        for percent, k in re.findall(r"(\d+\.\d)% \((\d+)\)", row[2]):
            assert f"{100 * int(k) / int(row[1]):.1f}" == percent, (row, percent, k)


def test_the_baseline_cells_and_the_hashes_are_the_logged_ones():
    for percent in re.findall(r"\| (\d+\.\d)% \[", CARD):
        assert f"{percent}% (" in SOURCES, percent

    manifest = json.loads(release.MANIFEST.read_text(encoding="utf-8"))
    for name in release.RELEASED_GGUFS:
        assert manifest["gguf"][name]["sha256"] in CARD and f"{manifest['gguf'][name]['bytes']:,}" in CARD
    assert release.sha256_file(release.MANIFEST) in CARD
    assert release.REPO_PLACEHOLDER in CARD

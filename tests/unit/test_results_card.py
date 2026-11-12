"""The LinkedIn results card (docs/media/hetren-results-card.png): every number on it is the model card's, each
plain-language label maps to the model-card row it reports, and the committed PNG carries exactly the text that
scripts/make_results_card.py defines. Reads the PNG with the standard library only; CI never renders it."""

from __future__ import annotations

import json
from pathlib import Path
import re
import struct
import zlib

from scripts.make_results_card import CARD, SIZE


REPO_ROOT = Path(__file__).resolve().parents[2]
PNG = REPO_ROOT / "docs/media/hetren-results-card.png"
MODEL_CARD = (REPO_ROOT / "docs/milestone-4/model-card.md").read_text(encoding="utf-8")
README = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

LABELS = {  # the card's plain label -> the model card row it reports (tier 1 test sets and the live test)
    "Failure types seen in training": "Tier 1 in-distribution: accuracy",
    "Failure types never seen in training": "Tier 1 held-out families: accuracy",
    "Runs of a live gpt-4.1-mini agent": "Live (runs of a `gpt-4.1-mini` agent): accuracy",
}


def _card_row(label: str) -> list[float]:
    """The model card row's percentages: rules v1, GPT-4.1, untrained Qwen, this model."""
    line = next(line for line in MODEL_CARD.splitlines() if line.startswith(f"| {label} |"))
    cells = [cell.strip() for cell in line.strip("|").split("|")][2:]
    return [float(re.search(r"(\d+\.\d)%", cell).group(1)) for cell in cells]


def _percent(text: str) -> float:
    return float(text.rstrip("%"))


def _chunks() -> list[tuple[bytes, bytes]]:
    data = PNG.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    chunks, at = [], 8
    while at < len(data):
        length, kind = struct.unpack(">I4s", data[at:at + 8])
        body = data[at + 8:at + 8 + length]
        assert zlib.crc32(kind + body) == struct.unpack(">I", data[at + 8 + length:at + 12 + length])[0]
        chunks.append((kind, body))
        at += 12 + length
    return chunks


def test_the_chart_is_the_model_cards_with_its_rows_mapped():
    assert CARD["legend"] == ["My model (4B)", "GPT-4.1"]
    assert {label: row for label, row, *_ in CARD["rows"]} == LABELS
    for label, row, mine, gpt in CARD["rows"]:
        _, card_gpt, _, card_tuned = _card_row(row)
        assert (_percent(mine), _percent(gpt)) == (card_tuned, card_gpt), label
        assert card_tuned > card_gpt, label
    # every set also holds healthy runs: each has a wrong-intervention row in the model card
    for row in ("Tier 1 in-distribution", "Tier 1 held-out families", "Live"):
        assert any(line.startswith(f"| {row}: wrong interventions |") for line in MODEL_CARD.splitlines()), row
    assert "healthy runs that should be left alone" in CARD["chart_note"]
    assert "Each\nsystem ran once per test set" in README and "Each system ran once." in CARD["chart_note"]


def test_the_headline_is_the_first_rows_result():
    headline = CARD["headline"]
    first = CARD["rows"][0]
    assert headline["row"] == first[1] == LABELS["Failure types seen in training"]
    assert (headline["tuned"], headline["gpt"]) == (first[2], first[3]) == ("73.8%", "33.8%")
    assert "My 4B model vs GPT-4.1" in CARD["headline_note"]
    assert "failure types seen in training (tier 1, frozen test set)" in CARD["headline_note"]


def test_the_notes_title_steps_and_footer_are_sourced():
    rules, _, _, tuned = _card_row("Tier 1 in-distribution: accuracy")
    assert CARD["notes"][0].endswith(f"{rules:.1f}% vs {tuned:.1f}% (tier 1).") and rules > tuned
    assert "built for the training families" in README
    assert CARD["notes"][1] == "It never escalated on a held-out failure type that needs a human (F6): 0 of 400."
    assert "**0.0% (0/400)**" in MODEL_CARD
    assert "on the held-out `queue_misconfiguration` family, where the right answer\n  is `abstain`" in README
    assert "or escalate to a human" in README
    assert CARD["title"] == "Hetren: a 4B model that diagnoses failed AI-agent runs"
    assert "base_model: Qwen/Qwen3-4B-Instruct-2507" in MODEL_CARD
    assert CARD["steps"] == ["Agent run", "Diagnose", "Propose a fix", "Verified in a sandbox"]
    assert "each recovery is verified in a sandboxed copy of the world" in README
    name, site = CARD["footer"].split(" · ")
    assert "author = {Nuthakki, Deva Harsha}" in README and name == "Deva Harsha Nuthakki"
    assert f"https://{site}" in README


def test_the_png_is_the_scripts_card_and_carries_no_other_text():
    chunks = _chunks()
    width, height = struct.unpack(">II", chunks[0][1][:8])
    assert chunks[0][0] == b"IHDR" and (width, height) == SIZE == (1080, 1350)
    texts = [body for kind, body in chunks if kind in (b"tEXt", b"iTXt", b"zTXt")]
    assert len(texts) == 1
    key, value = texts[0].split(b"\x00", 1)
    assert key == b"hetren-card" and json.loads(value.decode("latin-1")) == CARD
    assert {kind for kind, _ in chunks} <= {b"IHDR", b"IDAT", b"IEND", b"tEXt"}

"""Render the LinkedIn results card, docs/media/hetren-results-card.png (1080 x 1350, 4:5).

The card's text is CARD below. tests/unit/test_results_card.py checks every number in it against the model card,
maps each plain-language label to its model-card row, and checks that the committed PNG carries this exact text
(in its "hetren-card" text chunk), so the image cannot drift from the script without a failing test. Rendering
needs Pillow and macOS's Avenir Next; neither is a project dependency, and CI never renders the card:

    python3 -m venv <venv> && <venv>/bin/pip install pillow==11.3.0
    <venv>/bin/python scripts/make_results_card.py --out docs/media/hetren-results-card.png
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


CARD = {
    "title": "Hetren: a 4B model that diagnoses failed AI-agent runs",
    "steps": ["Agent run", "Diagnose", "Propose a fix", "Verified in a sandbox"],
    "headline": {"row": "Tier 1 in-distribution: accuracy", "tuned": "73.8%", "gpt": "33.8%"},
    "headline_note": ("My 4B model vs GPT-4.1: how often each chose the right action on failure types seen in "
                      "training (tier 1, frozen test set)"),
    "chart_title": "Right action chosen, frozen test sets",
    "chart_note": "Each set also has healthy runs that should be left alone. Each system ran once.",
    "legend": ["My model (4B)", "GPT-4.1"],
    "rows": [  # plain label, model card row, my model, GPT-4.1
        ["Failure types seen in training", "Tier 1 in-distribution: accuracy", "73.8%", "33.8%"],
        ["Failure types never seen in training", "Tier 1 held-out families: accuracy", "41.5%", "24.8%"],
        ["Runs of a live gpt-4.1-mini agent", "Live (runs of a `gpt-4.1-mini` agent): accuracy", "66.3%", "28.0%"],
    ],
    "notes": [
        "Hand-written rules, built for the training faults, still beat it on them: 99.5% vs 73.8% (tier 1).",
        "It never escalated on a held-out failure type that needs a human (F6): 0 of 400.",
    ],
    "footer": "Deva Harsha Nuthakki · github.com/DevaNuthakki/Hetren",
}

SIZE = (1080, 1350)
MARGIN = 96
FONT_FILE = "/System/Library/Fonts/Avenir Next.ttc"
FACES = {"regular": 7, "medium": 5, "demi": 2, "bold": 0}  # indices in Avenir Next.ttc
COLOURS = {"background": "#faf7f2", "text": "#2b2b2b", "muted": "#6e6a64", "faint": "#9a958d",
           "rule": "#e4ded4", "accent": "#0f6e74", "gpt": "#bdb6aa", "gpt_text": "#857f75", "icon_bg": "#efe9df"}


def _wrap(draw, text: str, font, width: int) -> list[str]:
    """The fewest lines that fit ``width``, balanced so that no line is left with a single word."""
    words = text.split()
    for count in range(1, len(words) + 1):
        target = draw.textlength(text, font=font) / count
        lines, line = [], ""
        for word in words:
            trial = f"{line} {word}".strip()
            if line and (draw.textlength(trial, font=font) > width or
                         (len(lines) < count - 1 and draw.textlength(line, font=font) >= target)):
                lines.append(line)
                line = word
            else:
                line = trial
        lines.append(line)
        if len(lines) == count and all(draw.textlength(l, font=font) <= width for l in lines):
            return lines
    return [text]


def _icon(draw, kind: str, cx: int, cy: int, colour: str, background: str) -> None:
    """Simple line icons, 56 px across: an agent run, a magnifier, a wrench, a sandbox with a tick."""
    w = 5
    if kind == "Agent run":
        points = [(cx - 20, cy + 12), (cx, cy - 12), (cx + 20, cy + 12)]
        draw.line(points, fill=colour, width=w, joint="curve")
        for x, y in points:
            draw.ellipse((x - 8, y - 8, x + 8, y + 8), fill=background, outline=colour, width=w)
    elif kind == "Diagnose":
        draw.ellipse((cx - 20, cy - 20, cx + 8, cy + 8), outline=colour, width=w)
        draw.line((cx + 6, cy + 6, cx + 20, cy + 20), fill=colour, width=w + 2)
    elif kind == "Propose a fix":
        draw.line((cx - 16, cy + 16, cx + 6, cy - 6), fill=colour, width=w + 3)
        draw.ellipse((cx - 2, cy - 22, cx + 22, cy + 2), fill=colour)
        draw.pieslice((cx + 2, cy - 30, cx + 30, cy - 2), 135, 225, fill=background)
        draw.ellipse((cx - 22, cy + 12, cx - 12, cy + 22), fill=colour)
    else:
        for x in range(cx - 22, cx + 22, 10):  # a dashed box
            draw.line((x, cy - 22, x + 5, cy - 22), fill=colour, width=3)
            draw.line((x, cy + 22, x + 5, cy + 22), fill=colour, width=3)
        for y in range(cy - 22, cy + 22, 10):
            draw.line((cx - 22, y, cx - 22, y + 5), fill=colour, width=3)
            draw.line((cx + 22, y, cx + 22, y + 5), fill=colour, width=3)
        draw.line([(cx - 11, cy + 1), (cx - 3, cy + 9), (cx + 12, cy - 9)], fill=colour, width=w, joint="curve")


def render(out: Path, font_file: str = FONT_FILE) -> None:
    from PIL import Image, ImageDraw, ImageFont
    from PIL.PngImagePlugin import PngInfo

    def font(face: str, size: int):
        return ImageFont.truetype(font_file, size, index=FACES[face])

    c = COLOURS
    image = Image.new("RGB", SIZE, c["background"])
    draw = ImageDraw.Draw(image)
    left, right = MARGIN, SIZE[0] - MARGIN
    width = right - left
    y = 66

    # Title
    for line in _wrap(draw, CARD["title"], font("bold", 46), width):
        draw.text((left, y), line, font=font("bold", 46), fill=c["text"])
        y += 56
    y += 24

    # How it works: four steps, each an icon in a soft circle, joined by thin arrows
    step_w = width // 4
    for i, step in enumerate(CARD["steps"]):
        cx = left + step_w * i + 44
        cy = y + 44
        draw.ellipse((cx - 44, cy - 44, cx + 44, cy + 44), fill=c["icon_bg"])
        _icon(draw, step, cx, cy, c["accent"], c["icon_bg"])
        label_y = y + 102
        for line in _wrap(draw, step, font("medium", 24), step_w - 20):
            draw.text((cx - 44, label_y), line, font=font("medium", 24), fill=c["text"])
            label_y += 30
        if i < len(CARD["steps"]) - 1:
            ax0, ax1 = cx + 58, left + step_w * (i + 1) + 44 - 58
            draw.line((ax0, cy, ax1, cy), fill=c["faint"], width=2)
            draw.polygon([(ax1, cy), (ax1 - 9, cy - 6), (ax1 - 9, cy + 6)], fill=c["faint"])
    y += 176
    draw.line((left, y, right, y), fill=c["rule"], width=2)
    y += 20

    # The headline result
    big = font("bold", 100)
    tuned, gpt = CARD["headline"]["tuned"], CARD["headline"]["gpt"]
    x = left
    draw.text((x, y), tuned, font=big, fill=c["accent"])
    x += draw.textlength(tuned, font=big) + 26
    vs = font("medium", 48)
    draw.text((x, y + 44), "vs", font=vs, fill=c["muted"])
    x += draw.textlength("vs", font=vs) + 26
    draw.text((x, y), gpt, font=big, fill=c["gpt_text"])
    y += 128
    for line in _wrap(draw, CARD["headline_note"], font("regular", 28), width):
        draw.text((left, y), line, font=font("regular", 28), fill=c["text"])
        y += 36
    y += 22

    # The grouped bar chart, with its legend on the title's line
    draw.text((left, y), CARD["chart_title"], font=font("demi", 26), fill=c["text"])
    lx = right
    legend = font("medium", 22)
    for name, colour in reversed(list(zip(CARD["legend"], (c["accent"], c["gpt"])))):
        lx -= draw.textlength(name, font=legend)
        draw.text((lx, y + 3), name, font=legend, fill=c["muted"])
        lx -= 26
        draw.rounded_rectangle((lx, y + 9, lx + 16, y + 25), radius=4, fill=colour)
        lx -= 28
    y += 46
    value_font = font("demi", 24)
    bar_max = width - 96
    for label, _, mine, theirs in CARD["rows"]:
        draw.text((left, y), label, font=font("medium", 26), fill=c["text"])
        y += 36
        for value, colour, text_colour in ((mine, c["accent"], c["accent"]), (theirs, c["gpt"], c["gpt_text"])):
            length = round(bar_max * float(value.rstrip("%")) / 100)
            draw.rounded_rectangle((left, y, left + length, y + 24), radius=6, fill=colour)
            draw.text((left + length + 12, y + 12), value, font=value_font, fill=text_colour, anchor="lm")
            y += 31
        y += 20
    draw.text((left, y - 10), CARD["chart_note"], font=font("regular", 23), fill=c["muted"])
    y += 36

    # The honest notes: calm, smaller, plain
    for note in CARD["notes"]:
        for line in _wrap(draw, note, font("regular", 26), width):
            draw.text((left, y), line, font=font("regular", 26), fill=c["text"])
            y += 35
        y += 12

    # Footer
    footer_y = SIZE[1] - 64 - 26
    if y > footer_y - 36:
        raise SystemExit(f"the card's text runs into the footer (y {y} > {footer_y - 36}); shorten it")
    draw.line((left, footer_y - 26, right, footer_y - 26), fill=c["rule"], width=2)
    draw.text((left, footer_y), CARD["footer"], font=font("medium", 24), fill=c["muted"])

    info = PngInfo()
    info.add_text("hetren-card", json.dumps(CARD, sort_keys=True))
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out, format="PNG", pnginfo=info, optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path("docs/media/hetren-results-card.png"))
    render(parser.parse_args().out)


if __name__ == "__main__":
    main()

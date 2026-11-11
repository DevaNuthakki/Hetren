"""The technical report (v1.0.0): every number it states is in a committed result or log, its sections are the
planned ones, and its claims carry the protocol's caveats."""

from __future__ import annotations

from pathlib import Path
import re
import subprocess


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT = (REPO_ROOT / "docs/TECHNICAL_REPORT.md").read_text(encoding="utf-8")
SOURCES = (
    "docs/milestone-2/EVAL_PROTOCOL.md", "docs/milestone-2/RESULTS.md", "docs/milestone-2/TEST_RUN_LOG.md",
    "docs/milestone-2/dataset-v2.manifest.json", "docs/milestone-2/dataset-v3.manifest.json",
    "docs/milestone-3/RESULTS.md", "docs/milestone-3/VALIDATION_LOG.md",
    "docs/milestone-4/EXPORT_LOG.md", "docs/milestone-4/DEPLOY_LOG.md", "docs/milestone-4/model-card.md",
    "docs/milestone-4/dataset-card.md", "docs/milestone-4/PLAN.md",
)


def _normal(text: str) -> str:
    return text.replace("−", "-").replace(" ", " ")


SOURCE_TEXT = _normal("\n".join((REPO_ROOT / path).read_text(encoding="utf-8") for path in SOURCES))


def _prose(text: str) -> str:
    """The report without its front matter, code spans and dates (identifiers and dates are not results)."""
    body = text.split("\n---\n", 1)[1]
    body = re.sub(r"`[^`]*`", " ", body)
    return re.sub(r"\b\d{4}-\d{2}-\d{2}\b", " ", body)


def _numbers(text: str) -> set[str]:
    found = set()
    for token in re.findall(r"\$?\d[\d,]*(?:\.\d+)?%?(?:/\d[\d,]*)?", _normal(text)):
        token = token.rstrip(",")
        if any(c in token for c in "%./$,") or (token.isdigit() and int(token) >= 100):
            found.add(token)
    return found


def test_every_number_is_in_a_committed_source():
    missing = sorted(n for n in _numbers(_prose(REPORT)) if n not in SOURCE_TEXT)
    assert not missing, f"numbers not found in the results and logs: {missing}"


def test_the_number_check_would_catch_an_invented_figure():
    assert "47.3%" in _numbers("accuracy rose to 47.3% on tier 1")
    assert "47.3%" not in SOURCE_TEXT  # so a made-up figure like this fails the test above


def test_the_sections_are_the_planned_ones():
    headings = re.findall(r"^# (.+)$", REPORT, re.MULTILINE)
    assert headings == ["Summary", "1. Problem", "2. Environment and fault families", "3. Labels and datasets",
                        "4. Protocol and claim rule", "5. Systems", "6. Training and selection", "7. Test results",
                        "8. CPU export (Amendment 2)", "9. Packaging and deployment", "10. Limitations",
                        "11. Reproducing and artefacts"]


def test_the_quoted_protocol_text_is_verbatim():
    protocol = (REPO_ROOT / "docs/milestone-2/EVAL_PROTOCOL.md").read_text(encoding="utf-8")
    def flat(text: str) -> str:
        return re.sub(r"\s+", " ", text)

    quotes = [  # every passage the report quotes from the protocol
        "Measure whether a diagnosis-and-recovery method fixes failed support-agent runs when a fix is possible, stays "
        "out of healthy runs, and says so when evidence is missing or no available recovery works. Results are "
        "reported per fault family, with held-out families reported separately.",
        "A recovery label is a recovery that, applied in a sandboxed copy of the world and followed by re-running the "
        "task, passes verification, including regression checks on unaffected tickets. Probe labels come from simple "
        "counterfactual enumeration: a probe sequence is sufficient when every candidate world consistent with its "
        "observations has the same verified outcome.",
        "only if the paired bootstrap 95% interval for the difference, computed on the same cases, excludes zero in its "
        "favour",
        "No correction for multiple comparisons is applied; every comparison made is reported.",
    ]
    for quote in quotes:
        assert quote in flat(REPORT), quote[:60]
        assert quote in flat(protocol), quote[:60]


def test_the_caveats_are_stated():
    assert "The model is not a general agent-trace\ndiagnoser" in REPORT
    assert "**These latencies are a cached best case.**" in REPORT
    assert "0.0% (0/400)" in REPORT and "0/44" in REPORT
    assert "No correction for multiple comparisons is applied" in REPORT
    assert "descriptive, not a re-validation" in REPORT
    assert "3e875e4e8719acef839dc18e220a3ae498a1975b" in REPORT


def _job(name: str) -> str:
    workflow = (REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    match = re.search(rf"^  {name}:\n(.*?)(?=^  [a-z_-]+:\n|\Z)", workflow.split("\njobs:\n", 1)[1],
                      re.MULTILINE | re.DOTALL)
    assert match, name
    return match.group(1)


def test_ci_builds_the_pdf_read_only_on_every_push():
    job = _job("report")
    assert "    permissions:\n      contents: read\n\n" in job and not re.search(r"^    if:", job, re.MULTILINE)
    assert 'scripts/build_report_pdf.sh "$RUNNER_TEMP/report"' in job
    assert "uses: actions/upload-artifact@v4" in job and "if-no-files-found: error" in job
    for forbidden in ("contents: write", "packages: write", "id-token", "gh release"):
        assert forbidden not in job, forbidden


def test_the_pdf_script_pins_its_image_and_runs_offline():
    script = (REPO_ROOT / "scripts/build_report_pdf.sh").read_text(encoding="utf-8")
    assert re.search(r'IMAGE="pandoc/typst:3\.11\.0\.0@sha256:[0-9a-f]{64}"', script)
    assert "--network none" in script and "-v \"$root/docs\":/data:ro" in script
    assert "-f markdown+lists_without_preceding_blankline" in script and "--pdf-engine=typst" in script
    assert "TECHNICAL_REPORT.pdf.sha256" in script
    run = subprocess.run(["bash", "-n", str(REPO_ROOT / "scripts/build_report_pdf.sh")], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr


def test_no_digit_is_followed_by_an_apostrophe():
    # Typst typesets "2's" with a prime (2′s); the report words these differently.
    assert not re.findall(r"\d's", REPORT)


def test_the_pdf_build_is_reproducible_and_laid_out_by_the_style_file():
    script = (REPO_ROOT / "scripts/build_report_pdf.sh").read_text(encoding="utf-8")
    assert re.search(r"^REPORT_DATE_EPOCH=1794355200 ", script, re.MULTILINE)  # 2026-11-11T00:00:00Z
    assert '-e SOURCE_DATE_EPOCH="$REPORT_DATE_EPOCH"' in script
    assert '"$root/scripts/report-pdf.typ":/style/report-pdf.typ:ro' in script
    assert "--include-before-body=/style/report-pdf.typ" in script
    style = (REPO_ROOT / "scripts/report-pdf.typ").read_text(encoding="utf-8")
    for rule in ("#set par(justify: false)", "#show heading: set block(sticky: true)", "#show table: set text(size: 9pt)"):
        assert rule in style, rule


def test_every_table_sets_its_column_widths():
    # Each separator line gives its columns' relative widths (pandoc reads the dash counts); none is left at the
    # equal widths that cramped the tag-run PDF.
    separators = re.findall(r"^\|(?::?-+\|)+$", REPORT, re.MULTILINE)
    assert len(separators) == 7
    assert "|:---------|:---|:---|" not in REPORT and "|:---------|:---|:---|:---|:---|:---|" not in REPORT

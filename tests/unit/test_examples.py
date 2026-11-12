"""The README's example input: one line of dataset v2's visible file, a tier 1 validation case that the CLI accepts,
and the input that the README's Docker and from-source commands use, with the expected first line of output."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from packages.hetren_cli.inputs import SUPPORT_TOOLS, from_compact, read_json
from packages.hetren_cli.report import KIND_TITLES
from packages.support_evaluator import sandbox_demo


REPO_ROOT = Path(__file__).resolve().parents[2]
README = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
EXAMPLE = REPO_ROOT / "examples/v2-case-001478.jsonl"
CASE_ID = "case-001478"
DATASET = REPO_ROOT / "artifacts/milestone-2/dataset-v2/hetren_visible.jsonl"  # gitignored
MANIFEST = REPO_ROOT / "docs/milestone-2/dataset-v2.manifest.json"
ROWS = REPO_ROOT / "artifacts/milestone-4/validation-1/Q4_K_M/tier1/rows-tier1-validation.jsonl"  # gitignored


def _example() -> dict:
    lines = EXAMPLE.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    return json.loads(lines[0])


def _expected_line() -> str:
    first = _example()["steps"][0]["target"]
    args = json.dumps(first["args"], sort_keys=True)
    return f"  {KIND_TITLES[first['action']]}: {first['verb']} {args}"


def test_the_example_is_a_tier_1_validation_case_the_cli_accepts():
    case = _example()
    assert case["case_id"] == CASE_ID and set(case) == {"case_id", "steps"}
    sandbox_demo.check_case(CASE_ID)  # in splits v1's validation list, and in no test split
    compact = from_compact(read_json(EXAMPLE))
    assert compact == case["steps"][0]["input"]
    assert {step["tool"] for step in compact["steps"]} <= set(SUPPORT_TOOLS)


@pytest.mark.skipif(not DATASET.is_file(), reason="dataset v2 is gitignored")
def test_the_example_is_the_dataset_line():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    digest = next(v for k, v in _flatten(manifest) if k.endswith("/hetren_visible.jsonl"))
    assert hashlib.sha256(DATASET.read_bytes()).hexdigest() == digest  # the dataset as released
    line = next(line for line in DATASET.read_bytes().splitlines(keepends=True)
                if line.startswith(f'{{"case_id":"{CASE_ID}"'.encode()))
    assert EXAMPLE.read_bytes() == line


def _flatten(value, prefix=""):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _flatten(item, f"{prefix}/{key}")
    elif isinstance(value, str):
        yield prefix, value


def test_the_readme_commands_use_the_example():
    docker = README.split("### Docker (offline diagnosis)", 1)[1].split("\n### ", 1)[0]
    assert '-v "$PWD/examples":/work:ro' in docker and "diagnose --compact /work/v2-case-001478.jsonl" in docker
    assert "git clone https://github.com/DevaNuthakki/Hetren.git && cd Hetren" in docker
    assert "diagnose --compact examples/v2-case-001478.jsonl --llama-server" in README
    assert "compact_first_step.json" not in README
    assert f"\n{_expected_line()}\n" in docker
    assert _expected_line() == '  Needs probe: find_owners {"customer_ref": "C-3983"}'
    for statement in ("`linux/amd64` only", "**AVX2, FMA and F16C**", "Apple Silicon (`arm64`)",
                      "synthetic support workflow"):
        assert statement in docker, statement
    assert "Mac on 18 of 20" in docker
    log = (REPO_ROOT / "docs/milestone-4/EXPORT_LOG.md").read_text(encoding="utf-8")
    entry = " ".join(log.split("### The README example in the v1.0.0 image", 1)[1].split("\n## ", 1)[0].split())
    assert "Docker Desktop, 6 threads" in entry and "first run of this case in the image" in entry
    assert f"`{_expected_line().strip()}`" in entry and "Docker Desktop, 6 threads, 2026-11-12" in docker
    digest = "sha256:efafa907ab9cd6c87965fc8c00d8818c70e49faa869ee3e15f6f9d21f60e2bc0"  # the v1.0.0 image (PLAN.md, 8.7)
    assert f"run by the tag `ghcr.io/devanuthakki/hetren-cli:v1.0.0`, which resolved to `{digest}`" in entry
    assert "`efafa907ab9c`" in entry and digest[:15] + "…" in docker and "by the `:v1.0.0` tag, which resolved to" in docker


@pytest.mark.skipif(not ROWS.is_file(), reason="the validation run's rows are gitignored")
def test_the_expected_line_is_the_logged_first_action():
    row = next(json.loads(line) for line in ROWS.open(encoding="utf-8") if f'"case_id": "{CASE_ID}"' in line)
    first = row["probes"][0] if row["probes"] else row["final"]
    assert first == _example()["steps"][0]["target"]

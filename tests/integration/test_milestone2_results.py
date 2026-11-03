"""docs/milestone-2/RESULTS.md is exactly what scripts/milestone2_results.py
generates from the recorded test rows. The rows are gitignored, so the full
regeneration runs only where they exist (the operator's machine); the fixed
prose is always checked."""

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("milestone2_results", ROOT / "scripts" / "milestone2_results.py")
results = importlib.util.module_from_spec(spec)
spec.loader.exec_module(results)


def test_the_committed_results_keep_the_scripts_fixed_text():
    text = results.RESULTS.read_text(encoding="utf-8")

    assert text.startswith(results.HEAD) and text.endswith(results.TAIL)


@pytest.mark.slow
@pytest.mark.skipif(not all(p.exists() for p in results.row_files()), reason="recorded test rows are gitignored")
def test_regenerating_reproduces_the_committed_results_exactly():
    assert results.render() == results.RESULTS.read_text(encoding="utf-8")

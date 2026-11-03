"""docs/milestone-2/RESULTS.md is exactly what
``packages.support_evaluator.milestone2_results`` generates from the recorded
test rows. The rows are gitignored, so the full regeneration runs only where
they exist (the operator's machine); the fixed prose is always checked."""

import pytest

from packages.support_evaluator import milestone2_results as results


def test_the_committed_results_keep_the_scripts_fixed_text():
    text = results.RESULTS.read_text(encoding="utf-8")

    assert text.startswith(results.HEAD) and text.endswith(results.TAIL)


@pytest.mark.slow
@pytest.mark.skipif(not all(p.exists() for p in results.row_files()), reason="recorded test rows are gitignored")
def test_regenerating_reproduces_the_committed_results_exactly():
    assert results.render() == results.RESULTS.read_text(encoding="utf-8")

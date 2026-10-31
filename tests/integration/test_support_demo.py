from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_offline_demo_runs_without_an_api_key_and_prints_the_three_examples():
    result = subprocess.run(
        [sys.executable, "-m", "packages.support_examples.demo"],
        cwd=REPO_ROOT, text=True, capture_output=True, check=False,
        env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"},
    )

    assert result.returncode == 0, result.stderr
    rows = [line.split("  ")[0] for line in result.stdout.splitlines()[5:]]
    assert rows == ["Correct run", "Insufficient evidence", "Verified recovery"]

    output = result.stdout
    assert "network blocked" in output
    assert "no_intervention_correct" in output
    assert "insufficient_evidence (4 items missing)" in output
    assert "mapping_inconsistency -> 2 mapping entries corrected" in output
    assert "recovery_verified" in output
    assert "run-0003, run-0004, run-0005" in output


def test_demo_rows_are_built_from_the_harness_results():
    from packages.support_examples.demo import replay_examples, table_rows

    assert table_rows(replay_examples()) == [
        ("Correct run", "run-0001", "healthy", "no_intervention_correct"),
        (
            "Insufficient evidence", "run-0002",
            "insufficient_evidence (4 items missing)", "insufficient_evidence_correct",
        ),
        (
            "Verified recovery", "run-0003, run-0004, run-0005",
            "mapping_inconsistency -> 2 mapping entries corrected", "recovery_verified",
        ),
    ]

"""Tests for the fixed exploratory diagnostic comparison."""

from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from packages.core.hetren_diagnosis.contracts import (
    DiagnosisStatus,
)
from scripts.incident_triage_diagnostic_benchmark import (
    CASES,
    POLICIES,
    SCHEMA,
    _collect_case,
    classify_outcome,
    run_development_benchmark,
    validate_executed_evidence,
)


def test_fixed_development_case_inventory():
    assert CASES == (
        "filter_tool_selection",
        "threshold_transformation",
        "compound_fault",
    )
    assert POLICIES == (
        "closed_world_one_probe",
        "open_set_one_probe",
        "predeclared_two_probe_challenge",
    )


def test_all_nine_comparisons_match_observed_development_result():
    report = run_development_benchmark(
        run_prefix="a5-fixed-metrics",
    )

    assert report["schema"] == SCHEMA
    assert report["case_count"] == 3
    assert len(report["case_results"]) == 9

    expected = {
        "closed_world_one_probe": (2, 1, 0, 1.0),
        "open_set_one_probe": (2, 1, 0, 1.0),
        "predeclared_two_probe_challenge": (
            2, 0, 1, 2.0,
        ),
    }

    for policy, (
        correct, false, abstain, cost
    ) in expected.items():
        summary = report["summary"][policy]
        assert summary["cases"] == 3
        assert summary["correct_specific"] == correct
        assert summary["false_specific"] == false
        assert summary["appropriate_abstention"] == abstain
        assert summary["mean_attributed_cost_units"] == cost
        assert summary["missed_known_diagnosis"] == 0
        assert summary["budget_exhausted"] == 0

    assert all(
        item is False
        for item in report["claims"].values()
    )


def test_compound_fault_reveals_one_probe_false_specific():
    report = run_development_benchmark(
        run_prefix="a5-compound-metrics",
    )

    rows = [
        row for row in report["case_results"]
        if row["case"] == "compound_fault"
    ]

    assert len(rows) == 3
    assert rows[0]["classification"] == "false_specific"
    assert rows[1]["classification"] == "false_specific"
    assert rows[2]["classification"] == "appropriate_abstention"
    assert rows[2]["status"] == "INCONCLUSIVE"
    assert rows[2]["reason"] == "evidence_contradiction"
    assert rows[2]["diagnosed_hypothesis"] is None
    assert rows[2]["experiment_count"] == 2


@pytest.mark.parametrize("case", CASES)
def test_real_evidence_is_consistent(case):
    problem, observations, runs = _collect_case(
        case, "a5-evidence",
    )
    validate_executed_evidence(
        problem, observations, runs,
    )


def test_modified_execution_hash_is_rejected():
    problem, observations, runs = _collect_case(
        "compound_fault", "a5-corruption",
    )
    corrupted = (
        replace(
            observations[0],
            evidence_sha256="0" * 64,
        ),
        observations[1],
    )
    with pytest.raises(ValueError, match="evidence mismatch"):
        validate_executed_evidence(
            problem, corrupted, runs,
        )


def test_reordered_observations_are_rejected():
    problem, observations, runs = _collect_case(
        "filter_tool_selection", "a5-reorder",
    )
    with pytest.raises(ValueError, match="evidence mismatch"):
        validate_executed_evidence(
            problem, observations[::-1], runs,
        )


def test_nonterminal_prediction_cannot_be_scored():
    with pytest.raises(ValueError, match="nonterminal"):
        classify_outcome(
            DiagnosisStatus.ACTIVE,
            None,
            None,
        )


def test_budget_exhaustion_not_counted_as_appropriate_abstention():
    assert classify_outcome(
        DiagnosisStatus.BUDGET_EXHAUSTED,
        None,
        None,
    ) == "budget_exhausted"


@pytest.mark.parametrize(
    "bad_prefix",
    ("", "a/b", "../escape", "two words", None, 42),
)
def test_invalid_run_prefix_is_rejected(bad_prefix):
    with pytest.raises(ValueError):
        run_development_benchmark(
            run_prefix=bad_prefix,
        )


def test_identical_inputs_produce_identical_reports():
    assert run_development_benchmark(
        run_prefix="a5-repeat",
    ) == run_development_benchmark(
        run_prefix="a5-repeat",
    )


def test_cli_outputs_valid_json_report():
    root = Path(__file__).resolve().parents[2]
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.incident_triage_diagnostic_benchmark",
            "--run-prefix",
            "a5-cli",
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    assert completed.stderr == ""
    assert json.loads(completed.stdout) == (
        run_development_benchmark(
            run_prefix="a5-cli",
        )
    )

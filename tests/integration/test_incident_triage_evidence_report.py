"""Acceptance tests for the existing lifecycle report interface."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.incident_triage_evidence_report import (
    SCHEMA,
    build_report,
)


@pytest.mark.parametrize(
    "scenario,expected_cause,expected_repair",
    [
        (
            "filter_tool_selection",
            "filter_tool_selection_fault",
            "replace_tool",
        ),
        (
            "threshold_transformation",
            "threshold_transformation_fault",
            "override_parameter",
        ),
    ],
)
def test_report_uses_actual_completed_agent_lifecycle(
    scenario, expected_cause, expected_repair
):
    report = build_report(scenario, "a4-positive")

    assert report["schema"] == SCHEMA
    assert report["diagnosis"]["status"] == "DIAGNOSED"
    assert (
        report["diagnosis"]["hypothesis_key"]
        == expected_cause
    )
    assert report["repair"]["kind"] == expected_repair

    assert report["ordinary_evaluation"]["outcome"] == "PASS"
    assert report["verification"]["outcome"] == "VERIFIED"
    assert report["eligibility"]["outcome"] == "ELIGIBLE"

    source = report["ordinary_evaluation"]
    verified = report["verification"]

    assert source["execution_id"] != verified["execution_id"]
    assert (
        source["execution_evidence_sha256"]
        != verified["execution_evidence_sha256"]
    )

    assert "same local Python process" in verified["limitations"]

    authority = report["authority"]
    assert authority["deployment_authorized"] is False
    assert (
        authority["protected_scientific_execution_authorized"]
        is False
    )
    assert (
        authority["independent_process_verification"]
        is False
    )


def test_policy_denial_does_not_rewrite_verification():
    baseline = build_report(
        "filter_tool_selection",
        "a4-policy-control",
    )
    restricted = build_report(
        "filter_tool_selection",
        "a4-policy-control",
        exclude_candidate_policy=True,
    )

    assert baseline["verification"] == restricted["verification"]
    assert baseline["eligibility"]["outcome"] == "ELIGIBLE"
    assert restricted["eligibility"]["outcome"] == "INELIGIBLE"
    assert restricted["authority"]["deployment_authorized"] is False


def test_identical_inputs_produce_identical_reports():
    first = build_report(
        "threshold_transformation",
        "a4-deterministic",
    )
    second = build_report(
        "threshold_transformation",
        "a4-deterministic",
    )
    assert first == second


@pytest.mark.parametrize(
    "bad_id",
    ["", "contains space", "../outside", "bad:identifier"],
)
def test_unsafe_run_identifier_rejected(bad_id):
    with pytest.raises(ValueError):
        build_report("filter_tool_selection", bad_id)


def test_boolean_policy_flag_is_strictly_typed():
    with pytest.raises(TypeError):
        build_report(
            "filter_tool_selection",
            "a4-policy-type",
            exclude_candidate_policy="yes",
        )


def test_terminal_interface_outputs_machine_readable_evidence():
    root = Path(__file__).resolve().parents[2]

    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.incident_triage_evidence_report",
            "--scenario",
            "filter_tool_selection",
            "--run-id",
            "a4-cli-test",
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    result = json.loads(completed.stdout)

    assert result == build_report(
        "filter_tool_selection",
        "a4-cli-test",
    )
    assert completed.stderr == ""


def test_terminal_policy_negative_control():
    root = Path(__file__).resolve().parents[2]

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.incident_triage_evidence_report",
            "--scenario",
            "threshold_transformation",
            "--run-id",
            "a4-cli-policy",
            "--exclude-candidate-policy",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )

    report = json.loads(completed.stdout)

    assert report["verification"]["outcome"] == "VERIFIED"
    assert report["eligibility"]["outcome"] == "INELIGIBLE"
    assert report["authority"]["deployment_authorized"] is False

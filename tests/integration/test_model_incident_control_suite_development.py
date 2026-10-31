"""Tests for the independent offline incident development control suite."""

from dataclasses import replace

import pytest

import packages.engines.behavioral.model_incident_control_suite_development as suite

from packages.contracts import ContractError
from packages.engines.behavioral.model_incident_development_evaluation import (
    evaluate_incident_development_cases,
)
from packages.engines.behavioral.model_incident_timeline_development import (
    reconstruct_incident_timeline,
)


EXPECTED = (
    ("correct", "correct", "completed", True),
    ("wrong", "wrong", "completed", False),
    ("recovery", "recover", "completed", True),
    ("repeat", "repeat", "rejected", False),
    ("exhaust", "exhaust", "recovery_exhausted", False),
    ("budget", "budget", "budget_exhausted", False),
    ("interrupt", "interrupt", "interrupted", False),
    ("reject", "reject", "rejected", False),
)


def test_versioned_manifest_is_explicit():
    payload = suite.control_manifest_payload()

    assert payload["record_type"] == "SyntheticIncidentControlManifest"
    assert payload["schema_version"] == 1
    assert payload["development_only"] is True
    assert payload["version"] == "a5-10h-cc-development-v1"
    assert payload["model_label"] == "offline"

    assert tuple(
        (
            item.case_id,
            item.behavior,
            item.expected_status,
            item.expected_correct,
        )
        for item in suite.CONTROL_CASES
    ) == EXPECTED

    assert len(payload["cases"]) == 8
    assert len(suite.control_manifest_sha256()) == 64


def test_suite_executes_independently_of_test_helpers():
    result = suite.run_synthetic_control_suite()

    assert len(result.inputs) == 8
    assert len(result.report.cases) == 8
    assert result.manifest_sha256 == suite.control_manifest_sha256()
    assert result.report.report_id == "a510h-cc-development-v1"

    assert [score.case_id for score in result.report.cases] == [
        item[0] for item in EXPECTED
    ]


def test_every_control_has_expected_outcome():
    result = suite.run_synthetic_control_suite()

    for score, expected in zip(result.report.cases, EXPECTED):
        assert score.case_id == expected[0]
        assert score.status == expected[2]
        assert score.correct is expected[3]


def test_expected_aggregate_denominators():
    summary = suite.run_synthetic_control_suite().report.summary

    assert summary.denominator_cases == 8
    assert summary.correct_cases == 2
    assert summary.completed_cases == 3
    assert summary.completed_incorrect_cases == 1

    assert summary.rejected_cases == 2
    assert summary.interrupted_cases == 1
    assert summary.recovery_exhausted_cases == 1
    assert summary.budget_exhausted_cases == 1

    assert summary.cases_with_injected_failures == 3
    assert summary.recovered_correctly_cases == 1

    assert summary.attempts == 27
    assert summary.executed_actions == 22
    assert summary.injected_failures == 3
    assert summary.rejected_actions == 2
    assert summary.interrupted_captures == 1
    assert summary.capture_calls == 28


def test_offline_fixture_never_claims_provider_usage():
    result = suite.run_synthetic_control_suite()

    calls = tuple(
        call
        for item in result.inputs
        for call in item.observed.calls
    )

    assert len(calls) == 28

    assert all(
        call.origin in ("offline_capture", "capture_source_exception")
        for call in calls
    )

    assert all(
        call.total_tokens is None
        and call.input_tokens is None
        and call.output_tokens is None
        and call.provider_result_sha256 is None
        for call in calls
    )

    summary = result.report.summary

    assert summary.calls_with_reported_tokens == 0
    assert summary.calls_without_reported_tokens == 28
    assert summary.complete_reported_tokens is None
    assert summary.known_call_token_sum is None


def test_correctness_is_distinct_from_completion():
    result = suite.run_synthetic_control_suite()

    scores = {
        score.case_id: score
        for score in result.report.cases
    }

    assert scores["correct"].completed
    assert scores["correct"].correct

    assert scores["wrong"].completed
    assert not scores["wrong"].correct

    assert scores["recovery"].completed
    assert scores["recovery"].recovered_correctly

    assert sum(score.correct for score in scores.values()) == 2


def test_failed_attempts_do_not_advance_workflow():
    result = suite.run_synthetic_control_suite()

    for item in result.inputs:
        failures = [
            attempt
            for attempt in item.observed.run.attempts
            if attempt.injected_failure is not None
        ]

        for attempt in failures:
            assert not attempt.executed
            assert (
                attempt.workflow_before_sha256
                == attempt.workflow_after_sha256
            )
            assert (
                attempt.injected_failure.origin
                == "synthetic_pre_execution_failure"
            )

    assert sum(
        attempt.injected_failure is not None
        for item in result.inputs
        for attempt in item.observed.run.attempts
    ) == 3


def test_interruption_is_a_non_executed_capture():
    result = suite.run_synthetic_control_suite()

    item = next(
        item
        for item in result.inputs
        if item.case_id == "interrupt"
    )

    run = item.observed.run

    assert run.status == "interrupted"
    assert run.interruption is not None
    assert len(item.observed.calls) == len(run.attempts) + 1

    last = item.observed.calls[-1]

    assert last.outcome == "interrupted"
    assert last.capture_sha256 is None
    assert last.total_tokens is None


def test_each_report_case_links_to_reconstructed_evidence():
    result = suite.run_synthetic_control_suite()

    for item, score in zip(result.inputs, result.report.cases):
        timeline = reconstruct_incident_timeline(
            scenario=item.scenario,
            model=item.model,
            observed=item.observed,
        )

        assert score.case_id == item.case_id

        assert (
            score.timeline_sha256
            == timeline.execution_evidence_sha256
        )
        assert (
            score.observed_sha256
            == item.observed.execution_evidence_sha256
        )
        assert score.status == timeline.status
        assert score.correct == timeline.passed


def test_same_captured_evidence_produces_same_report():
    result = suite.run_synthetic_control_suite()

    report_again = evaluate_incident_development_cases(
        report_id=result.report.report_id,
        cases=result.inputs,
    )

    assert result.report.canonical_payload() == (
        report_again.canonical_payload()
    )
    assert result.report.report_sha256 == report_again.report_sha256

    assert result.evidence_sha256 == result.evidence_sha256

    # Do not compare hashes of separately executed runs:
    # measured local capture durations can legitimately differ.


def test_manifest_changes_are_detectable(monkeypatch):
    original_hash = suite.control_manifest_sha256()

    monkeypatch.setattr(
        suite,
        "CONTROL_CASES",
        tuple(reversed(suite.CONTROL_CASES)),
    )

    assert suite.control_manifest_sha256() != original_hash


def test_mismatched_status_expectation_fails_closed(monkeypatch):
    original = suite.CONTROL_CASES

    changed = (
        replace(original[0], expected_status="rejected"),
        *original[1:],
    )

    monkeypatch.setattr(
        suite, "CONTROL_CASES", changed
    )

    with pytest.raises(ContractError):
        suite.run_synthetic_control_suite()


def test_mismatched_correctness_expectation_fails_closed(monkeypatch):
    original = suite.CONTROL_CASES

    changed = (
        replace(original[0], expected_correct=False),
        *original[1:],
    )

    monkeypatch.setattr(
        suite, "CONTROL_CASES", changed
    )

    with pytest.raises(ContractError):
        suite.run_synthetic_control_suite()


def test_duplicate_case_identity_fails_closed(monkeypatch):
    original = suite.CONTROL_CASES

    changed = (
        *original[:-1],
        original[0],
    )

    monkeypatch.setattr(
        suite, "CONTROL_CASES", changed
    )

    with pytest.raises(ContractError):
        suite.run_synthetic_control_suite()


def test_harness_limitations_are_explicit():
    result = suite.run_synthetic_control_suite()

    joined = " ".join(result.limitations).lower()

    assert "offline" in joined
    assert "not llm reasoning" in joined
    assert "independent verification" in joined
    assert "not genuine outages" in joined
    assert "measured capture duration" in joined
    assert "generalization" in joined

    assert (
        result.report.canonical_payload()["dataset_kind"]
        == "synthetic_development"
    )

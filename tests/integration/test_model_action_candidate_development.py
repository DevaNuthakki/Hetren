"""Offline cross-case candidate regression tests for A5-9D."""

from pathlib import Path
import json

import pytest

from packages.contracts import ContractError
from packages.core.hetren_diagnosis.contracts import InterventionKind
from packages.engines.behavioral.model_action_diagnosis_development import (
    CandidateDevelopmentCase,
    diagnose_captured_addition_development,
    evaluate_diagnosed_candidate_development,
)
from packages.engines.behavioral.model_proposed_tool_agent import (
    build_addition_request,
)
from packages.model_capture import (
    ModelCapture,
    capture_json_response,
)


def _source(left, right, tool, a, b, model="offline-model"):
    request = build_addition_request(
        model=model,
        left=left,
        right=right,
    )
    capture = capture_json_response(
        request=request,
        raw_response_text=json.dumps({
            "tool": tool,
            "a": a,
            "b": b,
        }, sort_keys=True),
    )
    return request, capture


def _diagnosis(tool="multiply_ints", a=3, b=4, budget=2):
    request, capture = _source(3, 4, tool, a, b)
    return diagnose_captured_addition_development(
        request=request,
        capture=capture,
        run_id="a59d-source",
        left=3,
        right=4,
        budget_units=budget,
    )


def _case(case_id, left, right, tool, a, b):
    request, capture = _source(
        left, right, tool, a, b,
    )
    return CandidateDevelopmentCase(
        case_id=case_id,
        request=request,
        capture=capture,
        left=left,
        right=right,
    )


def _recorded_live_control():
    path = Path(__file__).with_name(
        "a5_8e_live_capture_fixture.json"
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    task = data["request"]
    record = data["capture"]

    request = build_addition_request(
        model=task["model"],
        left=task["left"],
        right=task["right"],
    )

    capture = ModelCapture(
        provider=record["provider"],
        model=record["model"],
        request_sha256=record["request_sha256"],
        raw_response_text=record["raw_response_text"],
        normalized_response=record["normalized_response"],
        normalizer_id=record["normalizer_id"],
        normalizer_version=record["normalizer_version"],
        limitations=tuple(record["limitations"]),
    )

    assert capture.capture_sha256 == record["capture_sha256"]

    return CandidateDevelopmentCase(
        case_id="live-control",
        request=request,
        capture=capture,
        left=3,
        right=4,
    )


def test_tool_replacement_repairs_new_case_and_preserves_live_control():
    diagnosis = _diagnosis()
    failing = _case(
        "wrong-tool", 5, 6, "multiply_ints", 5, 6,
    )
    passing = _recorded_live_control()

    original_capture = passing.capture.capture_sha256

    result = evaluate_diagnosed_candidate_development(
        diagnosis=diagnosis,
        cases=(failing, passing),
    )

    assert result.intervention is InterventionKind.REPLACE_TOOL
    assert result.passed
    assert len(result.outcomes) == 2

    repaired, preserved = result.outcomes
    assert repaired.baseline_run.output == 30
    assert repaired.candidate_run.output == 11
    assert repaired.improves_failure
    assert repaired.candidate_run.selected_tool == "add_ints"

    assert preserved.baseline_run.passed
    assert preserved.preserves_success
    assert preserved.baseline_run.output == 7
    assert preserved.candidate_run.output == 7
    assert passing.capture.capture_sha256 == original_capture

    assert repaired.baseline_run.trace.run_id != (
        repaired.candidate_run.trace.run_id
    )
    assert len(result.evidence_sha256) == 64


def test_parameter_intervention_repairs_new_case():
    diagnosis = _diagnosis(
        tool="add_ints", a=2, b=4,
    )
    failing = _case(
        "wrong-args", 5, 6, "add_ints", 4, 6,
    )

    result = evaluate_diagnosed_candidate_development(
        diagnosis=diagnosis,
        cases=(failing, _recorded_live_control()),
    )

    assert result.intervention is InterventionKind.OVERRIDE_PARAMETER
    assert result.passed

    repaired = result.outcomes[0]
    assert repaired.baseline_run.status == "rejected"
    assert repaired.candidate_run.status == "executed"
    assert repaired.candidate_run.arguments == (5, 6)
    assert repaired.candidate_run.output == 11


def test_compound_error_is_not_falsely_marked_repaired():
    diagnosis = _diagnosis()
    compound = _case(
        "compound", 5, 6, "multiply_ints", 4, 6,
    )

    result = evaluate_diagnosed_candidate_development(
        diagnosis=diagnosis,
        cases=(compound, _recorded_live_control()),
    )

    assert not result.passed
    assert not result.outcomes[0].improves_failure
    assert result.outcomes[0].candidate_run.status == "rejected"
    assert result.outcomes[0].candidate_run.output is None


def test_inconclusive_diagnosis_cannot_select_candidate():
    diagnosis = _diagnosis(
        tool="multiply_ints", a=2, b=4,
    )

    with pytest.raises(ContractError, match="failed, diagnosed"):
        evaluate_diagnosed_candidate_development(
            diagnosis=diagnosis,
            cases=(
                _case("failure", 5, 6, "multiply_ints", 5, 6),
                _recorded_live_control(),
            ),
        )


def test_budget_exhaustion_cannot_select_candidate():
    diagnosis = _diagnosis(
        tool="add_ints", a=2, b=4, budget=1,
    )

    with pytest.raises(ContractError, match="failed, diagnosed"):
        evaluate_diagnosed_candidate_development(
            diagnosis=diagnosis,
            cases=(
                _case("failure", 5, 6, "add_ints", 4, 6),
                _recorded_live_control(),
            ),
        )


def test_missing_passing_control_is_not_accepted():
    diagnosis = _diagnosis()

    with pytest.raises(ContractError, match="failing and passing"):
        evaluate_diagnosed_candidate_development(
            diagnosis=diagnosis,
            cases=(
                _case("failure-a", 5, 6, "multiply_ints", 5, 6),
                _case("failure-b", 7, 8, "multiply_ints", 7, 8),
            ),
        )


def test_reused_diagnostic_source_is_rejected():
    diagnosis = _diagnosis()
    request, capture = _source(
        3, 4, "multiply_ints", 3, 4,
    )

    with pytest.raises(ContractError, match="distinct model requests"):
        evaluate_diagnosed_candidate_development(
            diagnosis=diagnosis,
            cases=(
                CandidateDevelopmentCase(
                    "reused", request, capture, 3, 4,
                ),
                _recorded_live_control(),
            ),
        )


def test_duplicate_case_identity_is_rejected():
    diagnosis = _diagnosis()

    with pytest.raises(ContractError, match="duplicate"):
        evaluate_diagnosed_candidate_development(
            diagnosis=diagnosis,
            cases=(
                _case("same", 5, 6, "multiply_ints", 5, 6),
                _case("same", 7, 8, "add_ints", 7, 8),
            ),
        )


def test_unsupported_action_fails_closed():
    diagnosis = _diagnosis()
    unsupported = _case(
        "unknown", 5, 6, "shell", 5, 6,
    )

    with pytest.raises(ContractError, match="unsupported tool"):
        evaluate_diagnosed_candidate_development(
            diagnosis=diagnosis,
            cases=(unsupported, _recorded_live_control()),
        )


def test_candidate_regression_is_deterministic():
    diagnosis = _diagnosis()
    cases = (
        _case("failure", 5, 6, "multiply_ints", 5, 6),
        _recorded_live_control(),
    )

    first = evaluate_diagnosed_candidate_development(
        diagnosis=diagnosis, cases=cases,
    )
    second = evaluate_diagnosed_candidate_development(
        diagnosis=diagnosis, cases=cases,
    )

    assert first == second
    assert first.evidence_sha256 == second.evidence_sha256
    assert "not independent scientific verification" in (
        " ".join(first.limitations)
    )

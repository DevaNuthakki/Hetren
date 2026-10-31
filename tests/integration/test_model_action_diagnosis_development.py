"""Bounded counterfactual diagnosis tests; no live model calls."""

from dataclasses import replace
import json
from pathlib import Path

import pytest

from packages.contracts import ContractError
from packages.core.hetren_diagnosis.contracts import (
    DiagnosisStatus,
    EventKind,
    InterventionKind,
    Verdict,
)
from packages.engines.behavioral.model_action_diagnosis_development import (
    diagnose_captured_addition_development,
)
from packages.engines.behavioral.model_proposed_tool_agent import (
    build_addition_request,
)
from packages.model_capture import (
    ModelCapture,
    capture_json_response,
)


def _source(proposal):
    request = build_addition_request(
        model="offline-model",
        left=3,
        right=4,
    )
    capture = capture_json_response(
        request=request,
        raw_response_text=json.dumps(
            proposal, sort_keys=True,
        ),
    )
    return request, capture


def _diagnose(proposal, budget=2):
    request, capture = _source(proposal)
    original_bytes = capture.raw_response_text
    original_sha = capture.capture_sha256

    result = diagnose_captured_addition_development(
        request=request,
        capture=capture,
        run_id="a59-development",
        left=3,
        right=4,
        budget_units=budget,
    )

    assert capture.raw_response_text == original_bytes
    assert capture.capture_sha256 == original_sha
    assert result.source_capture_sha256 == original_sha
    assert result.baseline_run.capture_sha256 == original_sha
    assert not result.baseline_run.passed

    for observation, run in zip(
        result.policy_result.observations,
        result.policy_result.diagnostic_runs,
    ):
        assert observation.evidence_sha256 == (
            run.execution_evidence_sha256
        )
        assert run.source_capture_sha256 == original_sha
        assert run.source_request_sha256 == request.request_sha256
        assert run.source_proposal_sha256 == (
            result.baseline_run.proposal_sha256
        )
        assert run.trace.run_id == run.run_id
        assert run.trace.events[0].component == (
            "diagnostic_intervention"
        )
        assert observation.verdict == (
            Verdict.PASS if run.passed else Verdict.FAIL
        )

    assert (
        len(result.policy_result.diagnostic_runs)
        == result.policy_result.experiment_count
    )

    return result


def test_wrong_tool_diagnosed_after_actual_replacement():
    result = _diagnose({
        "tool": "multiply_ints",
        "a": 3,
        "b": 4,
    })

    policy = result.policy_result
    assert result.baseline_run.output == 12
    assert policy.policy_status is DiagnosisStatus.DIAGNOSED
    assert policy.diagnosed_hypothesis_key == (
        "tool_selection_fault"
    )
    assert policy.experiment_count == 1
    assert policy.experiment_cost_units == 1

    run = policy.diagnostic_runs[0]
    assert run.intervention is InterventionKind.REPLACE_TOOL
    assert run.selected_tool == "add_ints"
    assert run.arguments == (3, 4)
    assert run.output == 7
    assert run.passed
    assert any(
        event.kind is EventKind.TOOL_CALL
        for event in run.trace.events
    )


def test_argument_mismatch_requires_second_probe():
    result = _diagnose({
        "tool": "add_ints",
        "a": 2,
        "b": 4,
    })

    policy = result.policy_result
    assert result.baseline_run.status == "rejected"
    assert policy.policy_status is DiagnosisStatus.DIAGNOSED
    assert policy.diagnosed_hypothesis_key == (
        "parameter_transformation_fault"
    )
    assert policy.experiment_count == 2
    assert policy.experiment_cost_units == 2

    first, second = policy.diagnostic_runs
    assert first.intervention is InterventionKind.REPLACE_TOOL
    assert first.status == "rejected"
    assert first.output is None
    assert not first.passed
    assert all(
        event.kind is not EventKind.TOOL_CALL
        for event in first.trace.events
    )

    assert second.intervention is InterventionKind.OVERRIDE_PARAMETER
    assert second.status == "executed"
    assert second.selected_tool == "add_ints"
    assert second.arguments == (3, 4)
    assert second.output == 7
    assert second.passed


def test_compound_fault_abstains_after_two_failed_probes():
    result = _diagnose({
        "tool": "multiply_ints",
        "a": 2,
        "b": 4,
    })

    policy = result.policy_result
    assert policy.policy_status is DiagnosisStatus.INCONCLUSIVE
    assert policy.policy_reason == "evidence_contradiction"
    assert policy.diagnosed_hypothesis_key is None
    assert policy.experiment_count == 2

    first, second = policy.diagnostic_runs
    assert first.status == "rejected"
    assert first.output is None
    assert second.status == "executed"
    assert second.output == 12
    assert not first.passed
    assert not second.passed
    assert all(
        item.counterexample_sha256 is not None
        for item in policy.observations
    )


@pytest.mark.parametrize(
    "proposal",
    [
        {"tool": "shell", "a": 3, "b": 4},
        {"tool": "add_ints", "a": "3", "b": 4},
        {"tool": "add_ints", "a": True, "b": 4},
        {"tool": "add_ints", "a": 101, "b": 4},
        {"tool": "add_ints", "a": 3},
        {"tool": "add_ints", "a": 3, "b": 4, "extra": 1},
    ],
)
def test_unsupported_proposals_are_not_forced_into_hypotheses(
    proposal,
):
    request, capture = _source(proposal)

    with pytest.raises(ContractError):
        diagnose_captured_addition_development(
            request=request,
            capture=capture,
            run_id="a59-unsupported",
            left=3,
            right=4,
        )


def test_insufficient_budget_does_not_certify_parameter_cause():
    result = _diagnose({
        "tool": "add_ints",
        "a": 2,
        "b": 4,
    }, budget=1)

    policy = result.policy_result
    assert policy.policy_status is DiagnosisStatus.BUDGET_EXHAUSTED
    assert policy.diagnosed_hypothesis_key is None
    assert policy.experiment_count == 1


def test_counterfactual_diagnosis_is_deterministic():
    proposal = {"tool": "multiply_ints", "a": 3, "b": 4}
    assert _diagnose(proposal) == _diagnose(proposal)


def test_tampered_capture_is_rejected_before_diagnosis():
    request, capture = _source({
        "tool": "multiply_ints", "a": 3, "b": 4,
    })
    corrupted = replace(
        capture,
        raw_response_text='{"tool":"add_ints","a":3,"b":4}',
    )

    with pytest.raises(ContractError):
        diagnose_captured_addition_development(
            request=request,
            capture=corrupted,
            run_id="a59-corrupt",
            left=3,
            right=4,
        )


def test_successful_recorded_live_observation_is_not_a_failure():
    path = Path(__file__).with_name(
        "a5_8e_live_capture_fixture.json"
    )
    fixture = json.loads(path.read_text(encoding="utf-8"))
    task = fixture["request"]
    data = fixture["capture"]

    request = build_addition_request(
        model=task["model"],
        left=task["left"],
        right=task["right"],
    )

    capture = ModelCapture(
        provider=data["provider"],
        model=data["model"],
        request_sha256=data["request_sha256"],
        raw_response_text=data["raw_response_text"],
        normalized_response=data["normalized_response"],
        normalizer_id=data["normalizer_id"],
        normalizer_version=data["normalizer_version"],
        limitations=tuple(data["limitations"]),
    )

    assert capture.capture_sha256 == data["capture_sha256"]

    with pytest.raises(ContractError, match="passing baseline"):
        diagnose_captured_addition_development(
            request=request,
            capture=capture,
            run_id="a59-live-ok",
            left=3,
            right=4,
        )


def test_counterfactual_claim_limits_are_explicit():
    result = _diagnose({
        "tool": "multiply_ints",
        "a": 3,
        "b": 4,
    })
    limitations = " ".join(result.limitations)

    assert "counterfactual" in limitations
    assert "no fresh model inference" in limitations
    assert "not independently authenticated" in limitations
    assert "does not authorize deployment" in limitations

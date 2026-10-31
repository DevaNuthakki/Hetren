"""A5-10E: recorded incident-action diagnosis, without provider calls."""

from dataclasses import replace
import json

import pytest

from packages.contracts import ContractError
from packages.core.hetren_diagnosis.contracts import (
    DiagnosisStatus,
    EventKind,
    InterventionKind,
    Verdict,
)
from packages.engines.behavioral.model_incident_diagnosis_development import (
    diagnose_captured_incident_development,
)
from packages.engines.behavioral.model_incident_triage_agent import (
    build_incident_triage_request,
    run_injected_openai_incident_triage,
)
from packages.model_capture import capture_json_response


def _source(proposal):
    request = build_incident_triage_request(model="offline-model")
    capture = capture_json_response(
        request=request,
        raw_response_text=json.dumps(proposal, sort_keys=True),
    )
    return request, capture


def _diagnose(proposal, *, budget=2, run_id="a510e-case"):
    request, capture = _source(proposal)
    raw_before = capture.raw_response_text
    sha_before = capture.capture_sha256

    result = diagnose_captured_incident_development(
        request=request,
        capture=capture,
        run_id=run_id,
        budget_units=budget,
    )

    assert capture.raw_response_text == raw_before
    assert capture.capture_sha256 == sha_before
    assert result.source_capture_sha256 == sha_before
    assert result.baseline_run.capture_sha256 == sha_before
    assert not result.baseline_run.passed

    policy = result.policy_result

    assert len(policy.observations) == len(policy.diagnostic_runs)
    assert len(policy.diagnostic_runs) == policy.experiment_count

    for observation, run in zip(
        policy.observations,
        policy.diagnostic_runs,
    ):
        assert run.source_request_sha256 == request.request_sha256
        assert run.source_capture_sha256 == sha_before
        assert run.source_proposal_sha256 == (
            result.baseline_run.proposal_sha256
        )
        assert observation.evidence_sha256 == (
            run.execution_evidence_sha256
        )
        assert observation.verdict == (
            Verdict.PASS if run.passed else Verdict.FAIL
        )
        assert observation.counterexample_sha256 is None if run.passed else (
            observation.counterexample_sha256 is not None
        )
        assert run.trace.run_id == run.run_id
        assert run.environment_run.trace == run.trace
        assert any(
            event.kind is EventKind.TOOL_CALL
            for event in run.trace.events
        )

    return result


def test_wrong_tool_replacement_yields_one_probe_diagnosis():
    result = _diagnose({
        "tool": "strict_severity_filter",
        "threshold": 3,
    })

    policy = result.policy_result
    assert policy.policy_status is DiagnosisStatus.DIAGNOSED
    assert policy.diagnosed_hypothesis_key == (
        "filter_tool_selection_fault"
    )
    assert policy.experiment_count == 1
    assert policy.experiment_cost_units == 1

    run = policy.diagnostic_runs[0]
    assert run.intervention is InterventionKind.REPLACE_TOOL
    assert run.selected_filter_tool == "inclusive_severity_filter"
    assert run.threshold == 3
    assert run.passed
    assert run.environment_run.report.incident_ids == (
        "INC-1001", "INC-1002", "INC-1004"
    )


def test_wrong_threshold_requires_two_actual_probes():
    result = _diagnose({
        "tool": "inclusive_severity_filter",
        "threshold": 4,
    })

    policy = result.policy_result
    assert policy.policy_status is DiagnosisStatus.DIAGNOSED
    assert policy.diagnosed_hypothesis_key == (
        "threshold_transformation_fault"
    )
    assert policy.experiment_count == 2
    assert policy.experiment_cost_units == 2

    first, second = policy.diagnostic_runs
    assert first.intervention is InterventionKind.REPLACE_TOOL
    assert first.selected_filter_tool == "inclusive_severity_filter"
    assert first.threshold == 4
    assert not first.passed
    assert first.environment_run.report.incident_ids == (
        "INC-1001", "INC-1004"
    )

    assert second.intervention is InterventionKind.OVERRIDE_PARAMETER
    assert second.threshold == 3
    assert second.passed
    assert policy.observations[0].counterexample_sha256 is not None
    assert policy.observations[1].counterexample_sha256 is None


def test_compound_fault_abstains_after_two_failing_probes():
    result = _diagnose({
        "tool": "strict_severity_filter",
        "threshold": 4,
    })

    policy = result.policy_result
    assert policy.policy_status is DiagnosisStatus.INCONCLUSIVE
    assert policy.policy_reason == "evidence_contradiction"
    assert policy.diagnosed_hypothesis_key is None
    assert policy.experiment_count == 2
    assert all(not run.passed for run in policy.diagnostic_runs)
    assert all(
        item.counterexample_sha256 is not None
        for item in policy.observations
    )


def test_insufficient_budget_does_not_diagnose_threshold_fault():
    result = _diagnose({
        "tool": "inclusive_severity_filter",
        "threshold": 4,
    }, budget=1)

    policy = result.policy_result
    assert policy.policy_status is DiagnosisStatus.BUDGET_EXHAUSTED
    assert policy.diagnosed_hypothesis_key is None
    assert policy.experiment_count == 1


def test_successful_action_is_not_diagnosed():
    request, capture = _source({
        "tool": "inclusive_severity_filter",
        "threshold": 3,
    })

    with pytest.raises(ContractError, match="passing baseline"):
        diagnose_captured_incident_development(
            request=request,
            capture=capture,
            run_id="a510e-success",
        )


@pytest.mark.parametrize("proposal", [
    {"tool": "shell", "threshold": 3},
    {"tool": "inclusive_severity_filter", "threshold": True},
    {"tool": "inclusive_severity_filter", "threshold": -1},
    {"tool": "inclusive_severity_filter", "threshold": "3"},
    {"tool": "inclusive_severity_filter"},
    {
        "tool": "inclusive_severity_filter",
        "threshold": 3,
        "invented_incident_ids": ["INC-9999"],
    },
])
def test_rejected_actions_are_not_assigned_diagnostic_causes(proposal):
    request, capture = _source(proposal)

    with pytest.raises(ContractError, match="rejected or unsupported"):
        diagnose_captured_incident_development(
            request=request,
            capture=capture,
            run_id="a510e-rejected",
        )


def test_capture_tampering_is_rejected():
    request, capture = _source({
        "tool": "strict_severity_filter",
        "threshold": 3,
    })
    altered = replace(
        capture,
        raw_response_text=json.dumps({
            "tool": "inclusive_severity_filter",
            "threshold": 3,
        }),
    )

    with pytest.raises(ContractError):
        diagnose_captured_incident_development(
            request=request,
            capture=altered,
            run_id="a510e-tampered",
        )


def test_diagnosis_is_deterministic_for_identical_evidence():
    proposal = {
        "tool": "inclusive_severity_filter",
        "threshold": 4,
    }

    first = _diagnose(proposal)
    second = _diagnose(proposal)

    assert first == second
    assert (
        first.policy_result.diagnostic_runs[0].execution_evidence_sha256
        == second.policy_result.diagnostic_runs[0].execution_evidence_sha256
    )


def test_distinct_run_ids_produce_distinct_execution_evidence():
    proposal = {
        "tool": "strict_severity_filter",
        "threshold": 3,
    }

    first = _diagnose(proposal, run_id="a510e-first")
    second = _diagnose(proposal, run_id="a510e-second")

    assert (
        first.source_capture_sha256
        == second.source_capture_sha256
    )
    assert (
        first.policy_result.diagnostic_runs[0].execution_evidence_sha256
        != second.policy_result.diagnostic_runs[0].execution_evidence_sha256
    )


def test_injected_provider_capture_can_be_diagnosed_without_network():
    calls = []

    def fake_transport(endpoint, body, headers, timeout):
        calls.append(endpoint)
        assert json.loads(body)["store"] is False
        return json.dumps({
            "id": "resp_a510e_synthetic",
            "model": "offline-model",
            "status": "completed",
            "output": [{
                "type": "message",
                "role": "assistant",
                "content": [{
                    "type": "output_text",
                    "text": json.dumps({
                        "tool": "strict_severity_filter",
                        "threshold": 3,
                    }),
                }],
            }],
            "usage": {
                "input_tokens": 12,
                "output_tokens": 8,
                "total_tokens": 20,
            },
        }).encode("utf-8")

    execution = run_injected_openai_incident_triage(
        model="offline-model",
        run_id="a510e-injected",
        api_key="synthetic-offline-credential",
        transport=fake_transport,
    )

    assert len(calls) == 1
    assert not execution.agent_run.passed

    request = build_incident_triage_request(model="offline-model")

    diagnosis = diagnose_captured_incident_development(
        request=request,
        capture=execution.provider_result.capture,
        run_id="a510e-provider",
    )

    assert diagnosis.policy_result.policy_status is (
        DiagnosisStatus.DIAGNOSED
    )
    assert diagnosis.policy_result.diagnosed_hypothesis_key == (
        "filter_tool_selection_fault"
    )
    assert diagnosis.source_capture_sha256 == (
        execution.provider_result.capture.capture_sha256
    )


def test_result_explicitly_limits_claims():
    result = _diagnose({
        "tool": "strict_severity_filter",
        "threshold": 3,
    })

    text = " ".join(result.limitations)
    assert "local counterfactual" in text
    assert "no new model inference" in text
    assert "no independent scientific verification" in text
    assert "does not explain model intent" in text
    assert "no automatic model repair" in text

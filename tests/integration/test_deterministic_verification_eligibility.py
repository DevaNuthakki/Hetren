"""Integration tests for separate verification and eligibility."""

from dataclasses import fields

import pytest

from packages.contracts import (
    CandidateEligibilityOutcome,
    ContractError,
    EvaluationOutcome,
    ExecutionStatus,
    VerificationOutcome,
)
from packages.core.hetren_diagnosis.contracts import (
    InterventionKind,
)
from packages.engines.behavioral import (
    FaultMode,
    run_repair_evaluation_demo,
)
from packages.verification import (
    execute_verification_candidate,
    run_verification_eligibility_demo,
)


@pytest.mark.parametrize(
    "fault_mode",
    (
        FaultMode.TOOL_SELECTION,
        FaultMode.PARAMETER_TRANSFORMATION,
    ),
)
def test_positive_candidate_is_separately_verified_then_eligible(
    fault_mode,
):
    result = run_verification_eligibility_demo(
        fault_mode,
        run_id=f"positive-{fault_mode.value}",
    )

    assert (
        result.source.evaluation.outcome
        is EvaluationOutcome.PASS
    )

    assert (
        result.verification_execution.status
        is ExecutionStatus.COMPLETED
    )

    assert (
        result.verification_evaluation.outcome
        is EvaluationOutcome.PASS
    )

    assert (
        result.verification_report.outcome
        is VerificationOutcome.VERIFIED
    )

    assert (
        result.eligibility_decision.outcome
        is CandidateEligibilityOutcome.ELIGIBLE
    )


def test_verification_execution_and_evaluation_are_distinct_records():
    result = run_verification_eligibility_demo(
        FaultMode.TOOL_SELECTION,
        run_id="distinct-lineage",
    )

    assert (
        result.source.execution.execution_id
        != result.verification_execution.execution_id
    )

    assert (
        result.source.evaluation.evaluation_id
        != result.verification_evaluation.evaluation_id
    )

    assert (
        result.source.execution.runner_id
        != result.verification_execution.runner_id
    )

    assert (
        result.source.evaluation.evaluator_id
        != result.verification_evaluation.evaluator_id
    )


def test_both_lineages_bind_exact_same_candidate_snapshot():
    result = run_verification_eligibility_demo(
        FaultMode.PARAMETER_TRANSFORMATION,
        run_id="same-candidate",
    )

    source = result.source.execution
    verification = result.verification_execution

    assert (
        source.system_snapshot_id
        == verification.system_snapshot_id
        == result.source.snapshot.snapshot_id
    )

    assert (
        source.system_snapshot_sha256
        == verification.system_snapshot_sha256
        == result.source.snapshot.snapshot_sha256
    )


def test_verification_is_an_actual_second_execution():
    result = run_verification_eligibility_demo(
        FaultMode.TOOL_SELECTION,
        run_id="actual-second-run",
    )

    assert result.source.candidate_run.output == 12
    assert result.verification_run.output == 12

    assert (
        result.source.candidate_run.run_id
        != result.verification_run.run_id
    )

    assert (
        result.source.candidate_run.trace.trace_sha256
        != result.verification_run.trace.trace_sha256
    )


def test_verification_report_validates_full_lineage():
    result = run_verification_eligibility_demo(
        FaultMode.PARAMETER_TRANSFORMATION,
        run_id="lineage-validation",
    )

    result.verification_report.validate_against(
        goal=result.source.goal,
        snapshot=result.source.snapshot,
        source_execution=result.source.execution,
        source_evaluation=result.source.evaluation,
        verification_execution=(
            result.verification_execution
        ),
        verification_evaluation=(
            result.verification_evaluation
        ),
    )


def test_failed_source_evaluation_cannot_enter_verification():
    source = run_repair_evaluation_demo(
        FaultMode.TOOL_SELECTION,
        run_id="source-fail",
        repair_kind=(
            InterventionKind.OVERRIDE_PARAMETER
        ),
    )

    assert (
        source.evaluation.outcome
        is EvaluationOutcome.FAIL
    )

    with pytest.raises(ContractError):
        execute_verification_candidate(
            source=source,
            fault_mode=FaultMode.TOOL_SELECTION,
            run_id="must-not-run",
        )


def test_verified_candidate_can_still_be_ineligible():
    result = run_verification_eligibility_demo(
        FaultMode.TOOL_SELECTION,
        run_id="verified-but-ineligible",
        permitted_component_ids=(
            "different-component-v1",
        ),
    )

    assert (
        result.verification_report.outcome
        is VerificationOutcome.VERIFIED
    )

    assert (
        result.eligibility_decision.outcome
        is CandidateEligibilityOutcome.INELIGIBLE
    )

    result.eligibility_decision.validate_against(
        goal=result.source.goal,
        snapshot=result.source.snapshot,
        verification=result.verification_report,
    )


def test_positive_policy_allows_exact_candidate_component():
    result = run_verification_eligibility_demo(
        FaultMode.PARAMETER_TRANSFORMATION,
        run_id="component-policy",
    )

    component_references = tuple(
        item
        for item in (
            result.eligibility_decision
            .policy_input_references
        )
        if item.startswith(
            "candidate-components:"
        )
    )

    assert len(component_references) == 1

    recorded_components = tuple(
        component_references[0].split(
            "candidate-components:",
            1,
        )[1].split(",")
    )

    assert (
        result.source.snapshot.component_version_ids
        == recorded_components
    )


def test_verification_independence_claim_is_explicitly_limited():
    result = run_verification_eligibility_demo(
        FaultMode.TOOL_SELECTION,
        run_id="independence-limit",
    )

    report = result.verification_report

    assert report.independence_references

    assert (
        "same local Python process"
        in report.limitations
    )

    assert (
        "independence references are provenance, not proof"
        in report.limitations
    )


def test_eligibility_decision_contains_no_authority_surface():
    result = run_verification_eligibility_demo(
        FaultMode.TOOL_SELECTION,
        run_id="no-authority",
    )

    names = {
        field.name
        for field in fields(
            type(result.eligibility_decision)
        )
    }

    assert names.isdisjoint(
        {
            "authorization",
            "authorized",
            "approval",
            "approved",
            "can_execute",
            "can_deploy",
            "deployment_authority",
            "promotion_authority",
            "lifecycle_state",
            "complete",
            "is_complete",
        }
    )


def test_full_verification_and_policy_demo_is_deterministic():
    first = run_verification_eligibility_demo(
        FaultMode.PARAMETER_TRANSFORMATION,
        run_id="deterministic-governance",
    )

    second = run_verification_eligibility_demo(
        FaultMode.PARAMETER_TRANSFORMATION,
        run_id="deterministic-governance",
    )

    assert first == second


def test_policy_input_changes_eligibility_without_changing_verification():
    eligible = run_verification_eligibility_demo(
        FaultMode.TOOL_SELECTION,
        run_id="policy-separation",
    )

    ineligible = run_verification_eligibility_demo(
        FaultMode.TOOL_SELECTION,
        run_id="policy-separation",
        permitted_component_ids=(
            "not-the-candidate-component",
        ),
    )

    assert (
        eligible.verification_report
        == ineligible.verification_report
    )

    assert (
        eligible.eligibility_decision.outcome
        is CandidateEligibilityOutcome.ELIGIBLE
    )

    assert (
        ineligible.eligibility_decision.outcome
        is CandidateEligibilityOutcome.INELIGIBLE
    )

    assert (
        eligible.eligibility_decision.policy_sha256
        != ineligible.eligibility_decision.policy_sha256
    )

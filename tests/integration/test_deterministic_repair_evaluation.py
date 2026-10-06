"""Integration tests for deterministic repair execution/evaluation."""

from dataclasses import fields, replace

import pytest

from packages.contracts import (
    ContractError,
    EvaluationOutcome,
    EvaluationRecord,
    ExecutionRecord,
    ExecutionStatus,
    GoalContract,
    MethodProposal,
    SystemSnapshot,
)
from packages.core.hetren_diagnosis.contracts import (
    InterventionKind,
)
from packages.engines.behavioral import (
    FaultMode,
    build_candidate_snapshot,
    build_repair_goal,
    build_repair_proposal,
    execute_repair_candidate,
    run_diagnosis_demo,
    run_repair_evaluation_demo,
    select_candidate_repair,
)


@pytest.mark.parametrize(
    (
        "fault_mode",
        "expected_repair",
    ),
    (
        (
            FaultMode.TOOL_SELECTION,
            InterventionKind.REPLACE_TOOL,
        ),
        (
            FaultMode.PARAMETER_TRANSFORMATION,
            InterventionKind.OVERRIDE_PARAMETER,
        ),
    ),
)
def test_repair_is_selected_from_diagnosis(
    fault_mode,
    expected_repair,
):
    diagnosis = run_diagnosis_demo(
        fault_mode,
        run_id=f"repair-selection-{fault_mode.value}",
    )

    assert (
        select_candidate_repair(
            diagnosis
        )
        is expected_repair
    )


def test_frozen_goal_is_independent_of_fault_mode():
    first = build_repair_goal()
    second = build_repair_goal()

    assert first == second
    assert (
        first.system_version_id
        == "faulty-v1"
    )


@pytest.mark.parametrize(
    "fault_mode",
    (
        FaultMode.TOOL_SELECTION,
        FaultMode.PARAMETER_TRANSFORMATION,
    ),
)
def test_candidate_snapshot_is_distinct_from_frozen_baseline_version(
    fault_mode,
):
    result = run_repair_evaluation_demo(
        fault_mode,
        run_id=f"candidate-version-{fault_mode.value}",
    )

    assert (
        result.snapshot.system_id
        == result.goal.system_id
    )

    assert (
        result.snapshot.system_version_id
        != result.goal.system_version_id
    )


@pytest.mark.parametrize(
    "fault_mode",
    (
        FaultMode.TOOL_SELECTION,
        FaultMode.PARAMETER_TRANSFORMATION,
    ),
)
def test_correct_diagnosed_candidate_actually_passes_evaluation(
    fault_mode,
):
    result = run_repair_evaluation_demo(
        fault_mode,
        run_id=f"correct-repair-{fault_mode.value}",
    )

    assert result.candidate_run.output == 12

    assert (
        result.execution.status
        is ExecutionStatus.COMPLETED
    )

    assert (
        result.evaluation.outcome
        is EvaluationOutcome.PASS
    )


@pytest.mark.parametrize(
    (
        "fault_mode",
        "wrong_repair",
    ),
    (
        (
            FaultMode.TOOL_SELECTION,
            InterventionKind.OVERRIDE_PARAMETER,
        ),
        (
            FaultMode.PARAMETER_TRANSFORMATION,
            InterventionKind.REPLACE_TOOL,
        ),
    ),
)
def test_wrong_candidate_can_complete_execution_and_fail_evaluation(
    fault_mode,
    wrong_repair,
):
    result = run_repair_evaluation_demo(
        fault_mode,
        run_id=f"wrong-repair-{fault_mode.value}",
        repair_kind=wrong_repair,
    )

    assert result.candidate_run.output == 2

    assert (
        result.execution.status
        is ExecutionStatus.COMPLETED
    )

    assert (
        result.execution.exit_code
        == 0
    )

    assert (
        result.evaluation.outcome
        is EvaluationOutcome.FAIL
    )


@pytest.mark.parametrize(
    "fault_mode",
    (
        FaultMode.TOOL_SELECTION,
        FaultMode.PARAMETER_TRANSFORMATION,
    ),
)
def test_execution_and_evaluation_validate_against_existing_contracts(
    fault_mode,
):
    result = run_repair_evaluation_demo(
        fault_mode,
        run_id=f"contract-links-{fault_mode.value}",
    )

    result.execution.validate_against(
        goal=result.goal,
        snapshot=result.snapshot,
        proposal=result.proposal,
    )

    result.evaluation.validate_against(
        goal=result.goal,
        execution=result.execution,
    )


def test_candidate_records_use_existing_governance_contract_types():
    result = run_repair_evaluation_demo(
        FaultMode.TOOL_SELECTION,
        run_id="existing-contract-types",
    )

    assert isinstance(
        result.goal,
        GoalContract,
    )

    assert isinstance(
        result.snapshot,
        SystemSnapshot,
    )

    assert isinstance(
        result.proposal,
        MethodProposal,
    )

    assert isinstance(
        result.execution,
        ExecutionRecord,
    )

    assert isinstance(
        result.evaluation,
        EvaluationRecord,
    )


def test_candidate_execution_is_bound_to_proposal_semantics():
    diagnosis = run_diagnosis_demo(
        FaultMode.TOOL_SELECTION,
        run_id="proposal-binding-diagnosis",
    )

    goal = build_repair_goal()

    repair_kind = (
        InterventionKind.REPLACE_TOOL
    )

    snapshot = build_candidate_snapshot(
        diagnosis,
        repair_kind,
    )

    proposal = build_repair_proposal(
        goal=goal,
        snapshot=snapshot,
        diagnosis=diagnosis,
        repair_kind=repair_kind,
    )

    forged = replace(
        proposal,
        generated_program="arguments = (7, 5)",
    )

    with pytest.raises(ContractError):
        execute_repair_candidate(
            fault_mode=FaultMode.TOOL_SELECTION,
            run_id="proposal-binding-candidate",
            goal=goal,
            snapshot=snapshot,
            proposal=forged,
            repair_kind=repair_kind,
        )


def test_candidate_execution_is_bound_to_snapshot_code_identity():
    diagnosis = run_diagnosis_demo(
        FaultMode.TOOL_SELECTION,
        run_id="snapshot-binding-diagnosis",
    )

    goal = build_repair_goal()

    repair_kind = (
        InterventionKind.REPLACE_TOOL
    )

    snapshot = build_candidate_snapshot(
        diagnosis,
        repair_kind,
    )

    proposal = build_repair_proposal(
        goal=goal,
        snapshot=snapshot,
        diagnosis=diagnosis,
        repair_kind=repair_kind,
    )

    forged = replace(
        snapshot,
        code_identity="f" * 64,
    )

    with pytest.raises(ContractError):
        execute_repair_candidate(
            fault_mode=FaultMode.TOOL_SELECTION,
            run_id="snapshot-binding-candidate",
            goal=goal,
            snapshot=forged,
            proposal=proposal,
            repair_kind=repair_kind,
        )


def test_candidate_evidence_binds_actual_execution():
    result = run_repair_evaluation_demo(
        FaultMode.PARAMETER_TRANSFORMATION,
        run_id="candidate-evidence",
    )

    evidence = (
        result.candidate_run.execution_evidence_sha256
    )

    assert (
        f"candidate-evidence-sha256:{evidence}"
        in result.execution.output_references
    )

    assert (
        f"candidate-evidence-sha256:{evidence}"
        in result.evaluation.evidence_references
    )


def test_evaluator_measures_actual_candidate_result():
    failed = run_repair_evaluation_demo(
        FaultMode.TOOL_SELECTION,
        run_id="actual-measurement",
        repair_kind=(
            InterventionKind.OVERRIDE_PARAMETER
        ),
    )

    assert failed.candidate_run.output == 2
    assert (
        failed.evaluation.outcome
        is EvaluationOutcome.FAIL
    )


def test_ordinary_pass_does_not_manufacture_verification_or_eligibility():
    result = run_repair_evaluation_demo(
        FaultMode.TOOL_SELECTION,
        run_id="authority-boundary",
    )

    assert (
        result.evaluation.outcome
        is EvaluationOutcome.PASS
    )

    names = {
        field.name
        for field in fields(
            type(result)
        )
    }

    assert names.isdisjoint(
        {
            "verification",
            "verification_report",
            "eligibility",
            "eligibility_decision",
            "authorization",
            "approval",
            "deployment",
            "complete",
        }
    )


def test_demo_is_deterministic_for_same_inputs():
    first = run_repair_evaluation_demo(
        FaultMode.PARAMETER_TRANSFORMATION,
        run_id="deterministic-repair-demo",
    )

    second = run_repair_evaluation_demo(
        FaultMode.PARAMETER_TRANSFORMATION,
        run_id="deterministic-repair-demo",
    )

    assert first == second

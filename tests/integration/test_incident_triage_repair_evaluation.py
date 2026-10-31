"""Integration tests for incident-triage repair and ordinary evaluation."""

from dataclasses import fields, replace
import inspect

import pytest

from environments.agent.incident_triage import (
    IncidentFaultMode,
    expected_incident_ids,
)
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
from packages.engines.behavioral.incident_triage_diagnosis import (
    run_diagnosis_demo,
)
from packages.engines.behavioral.incident_triage_repair import (
    IncidentRepairEvaluationResult,
    build_candidate_snapshot,
    build_repair_goal,
    build_repair_proposal,
    evaluate_candidate_run,
    execute_repair_candidate,
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
            IncidentFaultMode.FILTER_TOOL_SELECTION,
            InterventionKind.REPLACE_TOOL,
        ),
        (
            IncidentFaultMode.THRESHOLD_TRANSFORMATION,
            InterventionKind.OVERRIDE_PARAMETER,
        ),
    ),
)
def test_repair_is_selected_from_diagnosis_only(
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


def test_repair_selector_has_no_latent_fault_input():
    signature = inspect.signature(
        select_candidate_repair
    )

    assert tuple(signature.parameters) == (
        "diagnosis",
    )

    source = inspect.getsource(
        select_candidate_repair
    )

    assert "fault_mode" not in source
    assert "IncidentFaultMode" not in source


def test_frozen_goal_is_fault_independent():
    first = build_repair_goal()
    second = build_repair_goal()

    assert first == second

    assert (
        first.system_version_id
        == "faulty-v1"
    )

    assert (
        first.system_id
        == "deterministic-incident-triage-agent"
    )


@pytest.mark.parametrize(
    "fault_mode",
    (
        IncidentFaultMode.FILTER_TOOL_SELECTION,
        IncidentFaultMode.THRESHOLD_TRANSFORMATION,
    ),
)
def test_candidate_snapshot_is_distinct_from_baseline(
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
    (
        "fault_mode",
        "expected_repair",
    ),
    (
        (
            IncidentFaultMode.FILTER_TOOL_SELECTION,
            InterventionKind.REPLACE_TOOL,
        ),
        (
            IncidentFaultMode.THRESHOLD_TRANSFORMATION,
            InterventionKind.OVERRIDE_PARAMETER,
        ),
    ),
)
def test_diagnosed_candidate_passes_frozen_evaluation(
    fault_mode,
    expected_repair,
):
    result = run_repair_evaluation_demo(
        fault_mode,
        run_id=f"correct-repair-{fault_mode.value}",
    )

    assert result.repair_kind is expected_repair

    assert (
        result.candidate_run.report.incident_ids
        == expected_incident_ids()
    )

    assert result.candidate_run.report.count == 3
    assert result.candidate_run.passed is True

    assert (
        result.execution.status
        is ExecutionStatus.COMPLETED
    )

    assert result.execution.exit_code == 0

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
            IncidentFaultMode.FILTER_TOOL_SELECTION,
            InterventionKind.OVERRIDE_PARAMETER,
        ),
        (
            IncidentFaultMode.THRESHOLD_TRANSFORMATION,
            InterventionKind.REPLACE_TOOL,
        ),
    ),
)
def test_wrong_repair_can_complete_and_fail_evaluation(
    fault_mode,
    wrong_repair,
):
    result = run_repair_evaluation_demo(
        fault_mode,
        run_id=f"wrong-repair-{fault_mode.value}",
        repair_kind=wrong_repair,
    )

    assert result.candidate_run.passed is False

    assert (
        result.execution.status
        is ExecutionStatus.COMPLETED
    )

    assert result.execution.exit_code == 0

    assert (
        result.evaluation.outcome
        is EvaluationOutcome.FAIL
    )


@pytest.mark.parametrize(
    "fault_mode",
    (
        IncidentFaultMode.FILTER_TOOL_SELECTION,
        IncidentFaultMode.THRESHOLD_TRANSFORMATION,
    ),
)
def test_existing_execution_and_evaluation_contracts_validate(
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


def test_result_uses_existing_contract_types():
    result = run_repair_evaluation_demo(
        IncidentFaultMode.FILTER_TOOL_SELECTION,
        run_id="existing-contract-types",
    )

    assert isinstance(
        result,
        IncidentRepairEvaluationResult,
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


def test_execution_is_bound_to_proposal_semantics():
    diagnosis = run_diagnosis_demo(
        IncidentFaultMode.FILTER_TOOL_SELECTION,
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
        generated_program="threshold = 3",
    )

    with pytest.raises(ContractError):
        execute_repair_candidate(
            fault_mode=(
                IncidentFaultMode.FILTER_TOOL_SELECTION
            ),
            run_id="proposal-binding-candidate",
            goal=goal,
            snapshot=snapshot,
            proposal=forged,
            repair_kind=repair_kind,
        )


def test_execution_is_bound_to_snapshot_identity():
    diagnosis = run_diagnosis_demo(
        IncidentFaultMode.FILTER_TOOL_SELECTION,
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
            fault_mode=(
                IncidentFaultMode.FILTER_TOOL_SELECTION
            ),
            run_id="snapshot-binding-candidate",
            goal=goal,
            snapshot=forged,
            proposal=proposal,
            repair_kind=repair_kind,
        )


def test_candidate_evidence_binds_actual_execution_and_report():
    result = run_repair_evaluation_demo(
        IncidentFaultMode.THRESHOLD_TRANSFORMATION,
        run_id="candidate-evidence",
    )

    evidence = (
        result.candidate_run.execution_evidence_sha256
    )

    report = (
        result.candidate_run.report.report_sha256
    )

    assert (
        f"candidate-evidence-sha256:{evidence}"
        in result.execution.output_references
    )

    assert (
        f"candidate-report-sha256:{report}"
        in result.execution.output_references
    )

    assert (
        f"candidate-evidence-sha256:{evidence}"
        in result.evaluation.evidence_references
    )

    assert (
        f"candidate-report-sha256:{report}"
        in result.evaluation.evidence_references
    )


def test_evaluator_measures_actual_candidate_report():
    failed = run_repair_evaluation_demo(
        IncidentFaultMode.FILTER_TOOL_SELECTION,
        run_id="actual-measurement",
        repair_kind=(
            InterventionKind.OVERRIDE_PARAMETER
        ),
    )

    assert (
        failed.candidate_run.report.incident_ids
        == (
            "INC-1001",
            "INC-1004",
        )
    )

    assert failed.candidate_run.report.count == 2

    assert (
        failed.evaluation.outcome
        is EvaluationOutcome.FAIL
    )


def test_ordinary_pass_does_not_manufacture_authority():
    result = run_repair_evaluation_demo(
        IncidentFaultMode.FILTER_TOOL_SELECTION,
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


def test_evaluation_is_separate_from_execution_completion():
    failed = run_repair_evaluation_demo(
        IncidentFaultMode.THRESHOLD_TRANSFORMATION,
        run_id="completion-vs-success",
        repair_kind=(
            InterventionKind.REPLACE_TOOL
        ),
    )

    assert (
        failed.execution.status
        is ExecutionStatus.COMPLETED
    )

    assert failed.execution.exit_code == 0

    assert (
        failed.evaluation.outcome
        is EvaluationOutcome.FAIL
    )


def test_demo_is_deterministic_for_same_inputs():
    first = run_repair_evaluation_demo(
        IncidentFaultMode.THRESHOLD_TRANSFORMATION,
        run_id="deterministic-repair-demo",
    )

    second = run_repair_evaluation_demo(
        IncidentFaultMode.THRESHOLD_TRANSFORMATION,
        run_id="deterministic-repair-demo",
    )

    assert first == second


def test_evaluator_does_not_use_repair_kind_as_verdict():
    source = inspect.getsource(
        evaluate_candidate_run
    )

    assert "repair_kind" not in source
    assert "candidate_run.report" in source
    assert "EvaluationOutcome.PASS" in source
    assert "EvaluationOutcome.FAIL" in source

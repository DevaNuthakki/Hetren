"""Bounded repair and ordinary evaluation for incident triage.

P08.1C consumes a completed incident-triage diagnosis, selects a bounded
candidate repair from diagnosed evidence, materializes candidate provenance,
executes the repaired multi-step workflow, and evaluates the produced report.

This module stops at ordinary EvaluationRecord. PASS is not independent
verification, candidate eligibility, authorization, deployment approval, or
lifecycle completion.
"""

from dataclasses import dataclass

from environments.agent.incident_triage import (
    IncidentFaultMode,
    IncidentTriageRun,
    expected_incident_ids,
    run_incident_triage,
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
    canonical_sha256,
)
from packages.core.hetren_diagnosis.contracts import (
    DiagnosisStatus,
    InterventionKind,
)
from packages.engines.behavioral.incident_triage_diagnosis import (
    IncidentDiagnosisResult,
    run_diagnosis_demo,
)


_REPAIR_RUNNER_ID = "incident-triage-repair-runner"
_REPAIR_RUNNER_VERSION = "1"
_EVALUATOR_ID = "incident-triage-report-evaluator"
_EVALUATOR_VERSION = "1"
_EXPECTED_SERVICE = "payments"


@dataclass(frozen=True)
class IncidentRepairEvaluationResult:
    """Convenience bundle for one bounded repair/evaluation run."""

    diagnosis: IncidentDiagnosisResult
    repair_kind: InterventionKind
    goal: GoalContract
    snapshot: SystemSnapshot
    proposal: MethodProposal
    candidate_run: IncidentTriageRun
    execution: ExecutionRecord
    evaluation: EvaluationRecord


def build_repair_goal() -> GoalContract:
    """Return the fault-independent frozen incident-triage objective."""
    return GoalContract(
        tenant_id="portfolio",
        project_id="incident-triage-repair",
        contract_id="incident-triage-repair-goal",
        contract_version="1",
        system_id="deterministic-incident-triage-agent",
        system_version_id="faulty-v1",
        claim_scope=(
            "bounded repair of the deterministic "
            "multi-step incident-triage fixture"
        ),
        objective=(
            "restore the expected payments incident "
            "triage report for minimum severity 3"
        ),
        metrics=(
            "exact-triage-report-match",
        ),
        minimum_effect=(
            "candidate report exactly matches the frozen "
            "expected payments incident set"
        ),
        baseline_reference=(
            "fixture://deterministic-incident-triage/faulty-v1"
        ),
        acceptance_predicates=(
            "candidate report service equals payments",
            "candidate report incident IDs exactly equal "
            "INC-1001, INC-1002, INC-1004",
            "candidate report count equals 3",
        ),
        hard_constraints=(
            "candidate execution remains deterministic",
            "candidate changes only the diagnosed bounded behavior",
        ),
        invariants=(
            "no network or external-provider execution",
            "incident fixture remains unchanged",
            "frozen evaluation occurs after candidate execution",
        ),
        eligible_changes=(
            "severity-filter-selection rule",
            "severity-threshold-transformation rule",
        ),
        budget_constraints=(
            "one candidate execution",
        ),
        reviewer_version="deterministic-reviewer-v1",
        evaluator_version=_EVALUATOR_VERSION,
        evidence_requirements=(
            "candidate execution evidence digest",
            "candidate execution trace digest",
            "candidate report digest",
        ),
        protected_evaluation_requirements=(
            "evaluation outcome calculated from the "
            "executed candidate report",
        ),
        uncertainty_policy=(
            "claims remain limited to the deterministic "
            "incident-triage fixture"
        ),
        failure_invalidity_policy=(
            "preserve candidate execution completion separately "
            "from evaluator outcome"
        ),
        verification_requirements=(
            "ordinary PASS requires separate later verification "
            "before any VERIFIED claim",
        ),
    )


def select_candidate_repair(
    diagnosis: IncidentDiagnosisResult,
) -> InterventionKind:
    """Select a bounded repair from diagnosed evidence only."""
    if not isinstance(
        diagnosis,
        IncidentDiagnosisResult,
    ):
        raise ContractError(
            "diagnosis must be an IncidentDiagnosisResult"
        )

    if (
        diagnosis.final_decision.status
        is not DiagnosisStatus.DIAGNOSED
    ):
        raise ContractError(
            "repair selection requires a DIAGNOSED result"
        )

    key = diagnosis.diagnosed_hypothesis_key

    mapping = {
        "filter_tool_selection_fault": (
            InterventionKind.REPLACE_TOOL
        ),
        "threshold_transformation_fault": (
            InterventionKind.OVERRIDE_PARAMETER
        ),
    }

    try:
        return mapping[key]
    except KeyError as exc:
        raise ContractError(
            "diagnosed hypothesis has no bounded repair"
        ) from exc


def _repair_program(
    repair_kind: InterventionKind,
) -> str:
    if (
        repair_kind
        is InterventionKind.REPLACE_TOOL
    ):
        return (
            'selected_filter_tool = '
            '"inclusive_severity_filter"'
        )

    if (
        repair_kind
        is InterventionKind.OVERRIDE_PARAMETER
    ):
        return "threshold = 3"

    raise ContractError(
        "unsupported incident-triage repair kind"
    )


def _repair_component_id(
    repair_kind: InterventionKind,
) -> str:
    if (
        repair_kind
        is InterventionKind.REPLACE_TOOL
    ):
        return (
            "repair-replace-severity-filter-"
            "inclusive-v1"
        )

    if (
        repair_kind
        is InterventionKind.OVERRIDE_PARAMETER
    ):
        return (
            "repair-override-severity-threshold-3-v1"
        )

    raise ContractError(
        "unsupported incident-triage repair kind"
    )


def _repair_code_identity(
    repair_kind: InterventionKind,
) -> str:
    return canonical_sha256(
        {
            "repair_kind": repair_kind.value,
            "generated_program": (
                _repair_program(
                    repair_kind
                )
            ),
        }
    )


def build_candidate_snapshot(
    diagnosis: IncidentDiagnosisResult,
    repair_kind: InterventionKind,
) -> SystemSnapshot:
    """Materialize exact candidate state for a bounded repair."""
    if not isinstance(
        diagnosis,
        IncidentDiagnosisResult,
    ):
        raise ContractError(
            "diagnosis must be an IncidentDiagnosisResult"
        )

    if not isinstance(
        repair_kind,
        InterventionKind,
    ):
        raise ContractError(
            "repair_kind must be an InterventionKind"
        )

    diagnosed_key = (
        diagnosis.diagnosed_hypothesis_key
    )

    if diagnosed_key is None:
        raise ContractError(
            "candidate snapshot requires "
            "a diagnosed hypothesis"
        )

    return SystemSnapshot(
        tenant_id="portfolio",
        project_id="incident-triage-repair",
        snapshot_id=(
            "candidate-"
            f"{diagnosed_key}-"
            f"{repair_kind.value}-v1"
        ),
        system_id=(
            "deterministic-incident-triage-agent"
        ),
        system_version_id=(
            "candidate-"
            f"{repair_kind.value}-v1"
        ),
        environment_family=(
            "deterministic-incident-triage-fixture"
        ),
        component_version_ids=(
            _repair_component_id(
                repair_kind
            ),
        ),
        provider_binding_ids=(),
        adapter_binding_ids=(),
        evaluator_binding_ids=(
            _EVALUATOR_ID,
        ),
        code_identity=(
            _repair_code_identity(
                repair_kind
            )
        ),
        data_identity=None,
        prompt_identity=None,
        runtime_identity=(
            "python-deterministic-fixture-v1"
        ),
        state_references=(
            "baseline-trace-sha256:"
            f"{diagnosis.baseline_run.trace.trace_sha256}",
            "diagnosis-problem-sha256:"
            f"{diagnosis.problem.problem_sha256}",
            "diagnosed-hypothesis:"
            f"{diagnosed_key}",
        ),
        artifact_references=(),
    )


def build_repair_proposal(
    *,
    goal: GoalContract,
    snapshot: SystemSnapshot,
    diagnosis: IncidentDiagnosisResult,
    repair_kind: InterventionKind,
) -> MethodProposal:
    """Describe the candidate repair before executing it."""
    if not isinstance(
        goal,
        GoalContract,
    ):
        raise ContractError(
            "goal must be a GoalContract"
        )

    if not isinstance(
        snapshot,
        SystemSnapshot,
    ):
        raise ContractError(
            "snapshot must be a SystemSnapshot"
        )

    if not isinstance(
        diagnosis,
        IncidentDiagnosisResult,
    ):
        raise ContractError(
            "diagnosis must be an IncidentDiagnosisResult"
        )

    if not isinstance(
        repair_kind,
        InterventionKind,
    ):
        raise ContractError(
            "repair_kind must be an InterventionKind"
        )

    diagnosed_key = (
        diagnosis.diagnosed_hypothesis_key
    )

    if diagnosed_key is None:
        raise ContractError(
            "repair proposal requires "
            "a diagnosed hypothesis"
        )

    return MethodProposal(
        tenant_id=goal.tenant_id,
        project_id=goal.project_id,
        proposal_id=(
            "proposal-"
            f"{diagnosed_key}-"
            f"{repair_kind.value}-v1"
        ),
        proposal_version="1",
        goal_contract_id=goal.contract_id,
        system_snapshot_id=snapshot.snapshot_id,
        question=(
            "Does this bounded candidate restore "
            "the frozen expected incident-triage report?"
        ),
        alternatives=(
            "candidate passes frozen evaluator",
            "candidate fails frozen evaluator",
        ),
        expected_outcomes=(
            "candidate execution produces an independently "
            "measurable triage report",
        ),
        controls=(
            "same deterministic incident dataset",
            "same target service payments",
            "same minimum severity requirement 3",
            "same frozen expected incident IDs",
        ),
        generated_program=(
            _repair_program(
                repair_kind
            )
        ),
        dependencies=(
            "diagnosis:"
            f"{diagnosis.problem.problem_sha256}",
        ),
        stopping_rule=(
            "execute exactly one deterministic candidate trial"
        ),
    )


def _validate_candidate_semantics(
    *,
    snapshot: SystemSnapshot,
    proposal: MethodProposal,
    repair_kind: InterventionKind,
) -> None:
    """Bind candidate provenance to the repair actually executed."""
    expected_program = (
        _repair_program(
            repair_kind
        )
    )

    expected_component = (
        _repair_component_id(
            repair_kind
        )
    )

    expected_code_identity = (
        _repair_code_identity(
            repair_kind
        )
    )

    if (
        proposal.generated_program
        != expected_program
    ):
        raise ContractError(
            "proposal program does not match "
            "the selected repair kind"
        )

    if (
        snapshot.code_identity
        != expected_code_identity
    ):
        raise ContractError(
            "candidate code identity does not match "
            "the selected repair kind"
        )

    if (
        snapshot.component_version_ids
        != (expected_component,)
    ):
        raise ContractError(
            "candidate component identity does not match "
            "the selected repair kind"
        )


def execute_repair_candidate(
    *,
    fault_mode: IncidentFaultMode,
    run_id: str,
    goal: GoalContract,
    snapshot: SystemSnapshot,
    proposal: MethodProposal,
    repair_kind: InterventionKind,
) -> tuple[
    IncidentTriageRun,
    ExecutionRecord,
]:
    """Actually execute one frozen incident-triage candidate."""
    if not isinstance(
        fault_mode,
        IncidentFaultMode,
    ):
        raise ContractError(
            "fault_mode must be an IncidentFaultMode"
        )

    if (
        not isinstance(run_id, str)
        or not run_id.strip()
    ):
        raise ContractError(
            "run_id must be non-empty text"
        )

    if not isinstance(
        goal,
        GoalContract,
    ):
        raise ContractError(
            "goal must be a GoalContract"
        )

    if not isinstance(
        snapshot,
        SystemSnapshot,
    ):
        raise ContractError(
            "snapshot must be a SystemSnapshot"
        )

    if not isinstance(
        proposal,
        MethodProposal,
    ):
        raise ContractError(
            "proposal must be a MethodProposal"
        )

    if not isinstance(
        repair_kind,
        InterventionKind,
    ):
        raise ContractError(
            "repair_kind must be an InterventionKind"
        )

    _validate_candidate_semantics(
        snapshot=snapshot,
        proposal=proposal,
        repair_kind=repair_kind,
    )

    candidate_run = run_incident_triage(
        fault_mode,
        run_id=run_id,
        intervention=repair_kind,
    )

    execution_manifest = {
        "runner_id": _REPAIR_RUNNER_ID,
        "runner_version": _REPAIR_RUNNER_VERSION,
        "repair_kind": repair_kind.value,
        "candidate_snapshot_sha256": (
            snapshot.snapshot_sha256
        ),
        "proposal_sha256": (
            proposal.proposal_sha256
        ),
    }

    execution = ExecutionRecord(
        tenant_id=goal.tenant_id,
        project_id=goal.project_id,
        execution_id=(
            f"execution-{run_id}"
        ),
        goal_contract_id=goal.contract_id,
        goal_contract_sha256=(
            goal.contract_sha256
        ),
        system_snapshot_id=(
            snapshot.snapshot_id
        ),
        system_snapshot_sha256=(
            snapshot.snapshot_sha256
        ),
        method_proposal_id=(
            proposal.proposal_id
        ),
        method_proposal_sha256=(
            proposal.proposal_sha256
        ),
        runner_id=_REPAIR_RUNNER_ID,
        runner_version=(
            _REPAIR_RUNNER_VERSION
        ),
        environment_reference=(
            "fixture://deterministic-incident-triage"
        ),
        execution_manifest_reference=(
            "sha256:"
            f"{canonical_sha256(execution_manifest)}"
        ),
        status=ExecutionStatus.COMPLETED,
        exit_code=0,
        termination_reason=None,
        input_references=(
            "goal-sha256:"
            f"{goal.contract_sha256}",
            "snapshot-sha256:"
            f"{snapshot.snapshot_sha256}",
            "proposal-sha256:"
            f"{proposal.proposal_sha256}",
        ),
        output_references=(
            "candidate-evidence-sha256:"
            f"{candidate_run.execution_evidence_sha256}",
            "candidate-report-sha256:"
            f"{candidate_run.report.report_sha256}",
        ),
        trace_references=(
            "trace-sha256:"
            f"{candidate_run.trace.trace_sha256}",
        ),
        limitations=(
            "deterministic multi-step fixture only",
        ),
    )

    execution.validate_against(
        goal=goal,
        snapshot=snapshot,
        proposal=proposal,
    )

    return candidate_run, execution


def evaluate_candidate_run(
    *,
    goal: GoalContract,
    execution: ExecutionRecord,
    candidate_run: IncidentTriageRun,
) -> EvaluationRecord:
    """Evaluate the actual report produced by candidate execution."""
    if not isinstance(
        goal,
        GoalContract,
    ):
        raise ContractError(
            "goal must be a GoalContract"
        )

    if not isinstance(
        execution,
        ExecutionRecord,
    ):
        raise ContractError(
            "execution must be an ExecutionRecord"
        )

    if not isinstance(
        candidate_run,
        IncidentTriageRun,
    ):
        raise ContractError(
            "candidate_run must be an IncidentTriageRun"
        )

    expected_ids = expected_incident_ids()

    matches = (
        candidate_run.report.service
        == _EXPECTED_SERVICE
        and candidate_run.report.incident_ids
        == expected_ids
        and candidate_run.report.count
        == len(expected_ids)
    )

    outcome = (
        EvaluationOutcome.PASS
        if matches
        else EvaluationOutcome.FAIL
    )

    measurement = {
        "actual_report": (
            candidate_run.report.canonical_payload()
        ),
        "expected_report": {
            "service": _EXPECTED_SERVICE,
            "incident_ids": expected_ids,
            "count": len(expected_ids),
        },
        "matches": matches,
    }

    protocol = {
        "evaluator_id": _EVALUATOR_ID,
        "evaluator_version": (
            _EVALUATOR_VERSION
        ),
        "acceptance_predicates": (
            goal.acceptance_predicates
        ),
        "metric": "exact-triage-report-match",
    }

    if outcome is EvaluationOutcome.PASS:
        rationale = (
            "executed candidate report exactly matched "
            "the frozen expected triage report"
        )
    else:
        rationale = (
            "executed candidate report did not exactly match "
            "the frozen expected triage report"
        )

    evaluation = EvaluationRecord(
        tenant_id=goal.tenant_id,
        project_id=goal.project_id,
        evaluation_id=(
            f"evaluation-{execution.execution_id}"
        ),
        goal_contract_id=goal.contract_id,
        goal_contract_sha256=(
            goal.contract_sha256
        ),
        execution_id=(
            execution.execution_id
        ),
        execution_sha256=(
            execution.execution_sha256
        ),
        evaluator_id=_EVALUATOR_ID,
        evaluator_version=(
            goal.evaluator_version
        ),
        protocol_reference=(
            "internal://incident-triage-report-evaluator/v1"
        ),
        protocol_sha256=(
            canonical_sha256(protocol)
        ),
        outcome=outcome,
        measurement_references=(
            "sha256:"
            f"{canonical_sha256(measurement)}",
        ),
        evidence_references=(
            "candidate-evidence-sha256:"
            f"{candidate_run.execution_evidence_sha256}",
            "candidate-report-sha256:"
            f"{candidate_run.report.report_sha256}",
        ),
        rationale=rationale,
        uncertainty=(
            "evaluation is exact for this deterministic "
            "incident-triage fixture only"
        ),
        limitations=(
            "not independent verification",
            "not candidate eligibility",
            "not authorization",
        ),
    )

    evaluation.validate_against(
        goal=goal,
        execution=execution,
    )

    return evaluation


def run_repair_evaluation_demo(
    fault_mode: IncidentFaultMode,
    *,
    run_id: str,
    repair_kind: InterventionKind | None = None,
) -> IncidentRepairEvaluationResult:
    """Run diagnosis, candidate execution, and ordinary evaluation."""
    if not isinstance(
        fault_mode,
        IncidentFaultMode,
    ):
        raise ContractError(
            "fault_mode must be an IncidentFaultMode"
        )

    diagnosis = run_diagnosis_demo(
        fault_mode,
        run_id=f"{run_id}:diagnosis",
    )

    selected_repair = (
        select_candidate_repair(
            diagnosis
        )
        if repair_kind is None
        else repair_kind
    )

    if not isinstance(
        selected_repair,
        InterventionKind,
    ):
        raise ContractError(
            "repair_kind must be an InterventionKind"
        )

    goal = build_repair_goal()

    snapshot = build_candidate_snapshot(
        diagnosis,
        selected_repair,
    )

    proposal = build_repair_proposal(
        goal=goal,
        snapshot=snapshot,
        diagnosis=diagnosis,
        repair_kind=selected_repair,
    )

    candidate_run, execution = (
        execute_repair_candidate(
            fault_mode=fault_mode,
            run_id=f"{run_id}:candidate",
            goal=goal,
            snapshot=snapshot,
            proposal=proposal,
            repair_kind=selected_repair,
        )
    )

    evaluation = evaluate_candidate_run(
        goal=goal,
        execution=execution,
        candidate_run=candidate_run,
    )

    return IncidentRepairEvaluationResult(
        diagnosis=diagnosis,
        repair_kind=selected_repair,
        goal=goal,
        snapshot=snapshot,
        proposal=proposal,
        candidate_run=candidate_run,
        execution=execution,
        evaluation=evaluation,
    )


__all__ = [
    "IncidentRepairEvaluationResult",
    "build_candidate_snapshot",
    "build_repair_goal",
    "build_repair_proposal",
    "evaluate_candidate_run",
    "execute_repair_candidate",
    "run_repair_evaluation_demo",
    "select_candidate_repair",
]

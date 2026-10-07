"""Separate verification and eligibility for incident-triage candidates.

Ordinary evaluation PASS is only the prerequisite for this layer. Verification
uses a distinct execution/evaluation lineage over the exact same candidate
snapshot. Eligibility is then a separate bounded policy decision.

The deterministic local rerun demonstrates procedural separation only. It does
not prove infrastructure independence, organizational independence,
authorization, deployment approval, or lifecycle completion.
"""

from dataclasses import dataclass

from environments.agent.incident_triage import (
    IncidentFaultMode,
    IncidentTriageRun,
    expected_incident_ids,
    run_incident_triage,
)
from packages.contracts import (
    CandidateEligibilityDecision,
    CandidateEligibilityOutcome,
    ContractError,
    EvaluationOutcome,
    EvaluationRecord,
    ExecutionRecord,
    ExecutionStatus,
    VerificationOutcome,
    VerificationReport,
    canonical_sha256,
)
from packages.engines.behavioral.incident_triage_repair import (
    IncidentRepairEvaluationResult,
    run_repair_evaluation_demo,
)


_VERIFICATION_RUNNER_ID = (
    "incident-triage-verification-runner"
)
_VERIFICATION_RUNNER_VERSION = "1"

_VERIFICATION_EVALUATOR_ID = (
    "incident-triage-verification-evaluator"
)

_VERIFIER_ID = "incident-triage-verifier"
_VERIFIER_VERSION = "1"

_REVIEWER_ID = (
    "incident-triage-policy-reviewer"
)

_EXPECTED_SERVICE = "payments"


@dataclass(frozen=True)
class IncidentVerificationEligibilityResult:
    """Bundle for one verification and eligibility demonstration."""

    source: IncidentRepairEvaluationResult
    verification_run: IncidentTriageRun
    verification_execution: ExecutionRecord
    verification_evaluation: EvaluationRecord
    verification_report: VerificationReport
    eligibility_decision: CandidateEligibilityDecision


def _require_source_pass(
    source: IncidentRepairEvaluationResult,
) -> None:
    if not isinstance(
        source,
        IncidentRepairEvaluationResult,
    ):
        raise ContractError(
            "source must be an IncidentRepairEvaluationResult"
        )

    if (
        source.execution.status
        is not ExecutionStatus.COMPLETED
    ):
        raise ContractError(
            "source execution must be COMPLETED "
            "before verification"
        )

    if (
        source.evaluation.outcome
        is not EvaluationOutcome.PASS
    ):
        raise ContractError(
            "source evaluation must PASS "
            "before independent verification"
        )

    source.execution.validate_against(
        goal=source.goal,
        snapshot=source.snapshot,
        proposal=source.proposal,
    )

    source.evaluation.validate_against(
        goal=source.goal,
        execution=source.execution,
    )


def execute_verification_candidate(
    *,
    source: IncidentRepairEvaluationResult,
    fault_mode: IncidentFaultMode,
    run_id: str,
) -> tuple[
    IncidentTriageRun,
    ExecutionRecord,
]:
    """Run the same candidate through a distinct verification attempt."""
    _require_source_pass(
        source
    )

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

    verification_run = run_incident_triage(
        fault_mode,
        run_id=run_id,
        intervention=source.repair_kind,
    )

    manifest = {
        "runner_id": _VERIFICATION_RUNNER_ID,
        "runner_version": (
            _VERIFICATION_RUNNER_VERSION
        ),
        "mode": "verification",
        "repair_kind": source.repair_kind.value,
        "source_execution_sha256": (
            source.execution.execution_sha256
        ),
        "candidate_snapshot_sha256": (
            source.snapshot.snapshot_sha256
        ),
        "proposal_sha256": (
            source.proposal.proposal_sha256
        ),
    }

    execution = ExecutionRecord(
        tenant_id=source.goal.tenant_id,
        project_id=source.goal.project_id,
        execution_id=(
            f"verification-execution-{run_id}"
        ),
        goal_contract_id=(
            source.goal.contract_id
        ),
        goal_contract_sha256=(
            source.goal.contract_sha256
        ),
        system_snapshot_id=(
            source.snapshot.snapshot_id
        ),
        system_snapshot_sha256=(
            source.snapshot.snapshot_sha256
        ),
        method_proposal_id=(
            source.proposal.proposal_id
        ),
        method_proposal_sha256=(
            source.proposal.proposal_sha256
        ),
        runner_id=_VERIFICATION_RUNNER_ID,
        runner_version=(
            _VERIFICATION_RUNNER_VERSION
        ),
        environment_reference=(
            "fixture://deterministic-incident-triage/"
            "verification"
        ),
        execution_manifest_reference=(
            "sha256:"
            f"{canonical_sha256(manifest)}"
        ),
        status=ExecutionStatus.COMPLETED,
        exit_code=0,
        termination_reason=None,
        input_references=(
            "source-execution-sha256:"
            f"{source.execution.execution_sha256}",
            "candidate-snapshot-sha256:"
            f"{source.snapshot.snapshot_sha256}",
            "proposal-sha256:"
            f"{source.proposal.proposal_sha256}",
        ),
        output_references=(
            "verification-evidence-sha256:"
            f"{verification_run.execution_evidence_sha256}",
            "verification-report-artifact-sha256:"
            f"{verification_run.report.report_sha256}",
        ),
        trace_references=(
            "verification-trace-sha256:"
            f"{verification_run.trace.trace_sha256}",
        ),
        limitations=(
            "same local Python process",
            "same deterministic fixture implementation",
            "separate run does not prove infrastructure independence",
        ),
    )

    execution.validate_against(
        goal=source.goal,
        snapshot=source.snapshot,
        proposal=source.proposal,
    )

    if (
        execution.execution_id
        == source.execution.execution_id
    ):
        raise ContractError(
            "verification execution must be distinct "
            "from source execution"
        )

    if (
        verification_run.run_id
        == source.candidate_run.run_id
    ):
        raise ContractError(
            "verification run must be distinct "
            "from source candidate run"
        )

    return verification_run, execution


def evaluate_verification_candidate(
    *,
    source: IncidentRepairEvaluationResult,
    verification_run: IncidentTriageRun,
    verification_execution: ExecutionRecord,
) -> EvaluationRecord:
    """Evaluate the report produced by the separate verification run."""
    _require_source_pass(
        source
    )

    if not isinstance(
        verification_run,
        IncidentTriageRun,
    ):
        raise ContractError(
            "verification_run must be an IncidentTriageRun"
        )

    if not isinstance(
        verification_execution,
        ExecutionRecord,
    ):
        raise ContractError(
            "verification_execution must be an ExecutionRecord"
        )

    verification_execution.validate_against(
        goal=source.goal,
        snapshot=source.snapshot,
        proposal=source.proposal,
    )

    expected_ids = expected_incident_ids()

    matches = (
        verification_run.report.service
        == _EXPECTED_SERVICE
        and verification_run.report.incident_ids
        == expected_ids
        and verification_run.report.count
        == len(expected_ids)
    )

    outcome = (
        EvaluationOutcome.PASS
        if matches
        else EvaluationOutcome.FAIL
    )

    measurement = {
        "actual_report": (
            verification_run.report.canonical_payload()
        ),
        "expected_report": {
            "service": _EXPECTED_SERVICE,
            "incident_ids": expected_ids,
            "count": len(expected_ids),
        },
        "matches": matches,
        "trace_sha256": (
            verification_run.trace.trace_sha256
        ),
    }

    protocol = {
        "evaluator_id": (
            _VERIFICATION_EVALUATOR_ID
        ),
        "evaluator_version": (
            source.goal.evaluator_version
        ),
        "metric": "exact-triage-report-match",
        "acceptance_predicates": (
            source.goal.acceptance_predicates
        ),
        "mode": "verification",
    }

    evaluation = EvaluationRecord(
        tenant_id=source.goal.tenant_id,
        project_id=source.goal.project_id,
        evaluation_id=(
            "verification-evaluation-"
            f"{verification_execution.execution_id}"
        ),
        goal_contract_id=(
            source.goal.contract_id
        ),
        goal_contract_sha256=(
            source.goal.contract_sha256
        ),
        execution_id=(
            verification_execution.execution_id
        ),
        execution_sha256=(
            verification_execution.execution_sha256
        ),
        evaluator_id=(
            _VERIFICATION_EVALUATOR_ID
        ),
        evaluator_version=(
            source.goal.evaluator_version
        ),
        protocol_reference=(
            "internal://incident-triage-verification/"
            "exact-report-v1"
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
            "verification-evidence-sha256:"
            f"{verification_run.execution_evidence_sha256}",
            "verification-report-artifact-sha256:"
            f"{verification_run.report.report_sha256}",
        ),
        rationale=(
            "separate verification rerun report "
            + (
                "matched"
                if outcome
                is EvaluationOutcome.PASS
                else "did not match"
            )
            + " the frozen expected triage report"
        ),
        uncertainty=(
            "exact for this deterministic verification "
            "fixture only"
        ),
        limitations=(
            "same process as portfolio demonstration",
            "not proof of organizational independence",
            "not candidate eligibility",
            "not authorization",
        ),
    )

    evaluation.validate_against(
        goal=source.goal,
        execution=verification_execution,
    )

    if (
        evaluation.evaluation_id
        == source.evaluation.evaluation_id
    ):
        raise ContractError(
            "verification evaluation must be distinct "
            "from source evaluation"
        )

    return evaluation


def build_verification_report(
    *,
    source: IncidentRepairEvaluationResult,
    verification_run: IncidentTriageRun,
    verification_execution: ExecutionRecord,
    verification_evaluation: EvaluationRecord,
) -> VerificationReport:
    """Construct the existing VerificationReport over the second lineage."""
    _require_source_pass(
        source
    )

    if not isinstance(
        verification_run,
        IncidentTriageRun,
    ):
        raise ContractError(
            "verification_run must be an IncidentTriageRun"
        )

    if not isinstance(
        verification_execution,
        ExecutionRecord,
    ):
        raise ContractError(
            "verification_execution must be an ExecutionRecord"
        )

    if not isinstance(
        verification_evaluation,
        EvaluationRecord,
    ):
        raise ContractError(
            "verification_evaluation must be an EvaluationRecord"
        )

    source.execution.validate_against(
        goal=source.goal,
        snapshot=source.snapshot,
        proposal=source.proposal,
    )

    verification_execution.validate_against(
        goal=source.goal,
        snapshot=source.snapshot,
        proposal=source.proposal,
    )

    verification_evaluation.validate_against(
        goal=source.goal,
        execution=verification_execution,
    )

    outcome_by_evaluation = {
        EvaluationOutcome.PASS:
            VerificationOutcome.VERIFIED,
        EvaluationOutcome.FAIL:
            VerificationOutcome.REJECTED,
        EvaluationOutcome.INCONCLUSIVE:
            VerificationOutcome.INCONCLUSIVE,
        EvaluationOutcome.BLOCKED:
            VerificationOutcome.BLOCKED,
        EvaluationOutcome.INVALID:
            VerificationOutcome.INVALID,
    }

    outcome = outcome_by_evaluation[
        verification_evaluation.outcome
    ]

    protocol = {
        "verifier_id": _VERIFIER_ID,
        "verifier_version": _VERIFIER_VERSION,
        "mode": "separate-verification-lineage",
        "source_execution_sha256": (
            source.execution.execution_sha256
        ),
        "verification_execution_sha256": (
            verification_execution.execution_sha256
        ),
        "verification_evaluation_sha256": (
            verification_evaluation.evaluation_sha256
        ),
    }

    report = VerificationReport(
        tenant_id=source.goal.tenant_id,
        project_id=source.goal.project_id,
        verification_id=(
            "verification-"
            f"{verification_execution.execution_id}"
        ),
        goal_contract_id=(
            source.goal.contract_id
        ),
        goal_contract_sha256=(
            source.goal.contract_sha256
        ),
        system_snapshot_id=(
            source.snapshot.snapshot_id
        ),
        system_snapshot_sha256=(
            source.snapshot.snapshot_sha256
        ),
        source_execution_id=(
            source.execution.execution_id
        ),
        source_execution_sha256=(
            source.execution.execution_sha256
        ),
        source_evaluation_id=(
            source.evaluation.evaluation_id
        ),
        source_evaluation_sha256=(
            source.evaluation.evaluation_sha256
        ),
        verification_execution_id=(
            verification_execution.execution_id
        ),
        verification_execution_sha256=(
            verification_execution.execution_sha256
        ),
        verification_evaluation_id=(
            verification_evaluation.evaluation_id
        ),
        verification_evaluation_sha256=(
            verification_evaluation.evaluation_sha256
        ),
        verifier_id=_VERIFIER_ID,
        verifier_version=_VERIFIER_VERSION,
        protocol_reference=(
            "internal://incident-triage-verifier/"
            "separate-rerun-v1"
        ),
        protocol_sha256=(
            canonical_sha256(protocol)
        ),
        outcome=outcome,
        independence_references=(
            "source-run-id:"
            f"{source.candidate_run.run_id}",
            "verification-run-id:"
            f"{verification_run.run_id}",
            "source-runner-id:"
            f"{source.execution.runner_id}",
            "verification-runner-id:"
            f"{verification_execution.runner_id}",
            "source-evaluator-id:"
            f"{source.evaluation.evaluator_id}",
            "verification-evaluator-id:"
            f"{verification_evaluation.evaluator_id}",
        ),
        evidence_references=(
            "verification-evidence-sha256:"
            f"{verification_run.execution_evidence_sha256}",
            "verification-trace-sha256:"
            f"{verification_run.trace.trace_sha256}",
            "verification-report-artifact-sha256:"
            f"{verification_run.report.report_sha256}",
        ),
        rationale=(
            "verification outcome is derived from "
            "the separate verification evaluation"
        ),
        uncertainty=(
            "procedural separation is demonstrated; "
            "infrastructure and organizational independence "
            "are not established"
        ),
        limitations=(
            "same local Python process",
            "same deterministic fixture implementation",
            "independence references are provenance, not proof",
            "not candidate eligibility",
            "not authorization",
        ),
    )

    report.validate_against(
        goal=source.goal,
        snapshot=source.snapshot,
        source_execution=source.execution,
        source_evaluation=source.evaluation,
        verification_execution=(
            verification_execution
        ),
        verification_evaluation=(
            verification_evaluation
        ),
    )

    return report


def review_candidate_eligibility(
    *,
    source: IncidentRepairEvaluationResult,
    verification: VerificationReport,
    permitted_component_ids: tuple[str, ...],
) -> CandidateEligibilityDecision:
    """Apply one explicit bounded component policy after verification."""
    _require_source_pass(
        source
    )

    if not isinstance(
        verification,
        VerificationReport,
    ):
        raise ContractError(
            "verification must be a VerificationReport"
        )

    if not isinstance(
        permitted_component_ids,
        tuple,
    ):
        raise ContractError(
            "permitted_component_ids must be a tuple"
        )

    if any(
        not isinstance(item, str)
        or not item.strip()
        for item in permitted_component_ids
    ):
        raise ContractError(
            "permitted_component_ids must contain "
            "non-empty text"
        )

    if len(permitted_component_ids) != len(
        set(permitted_component_ids)
    ):
        raise ContractError(
            "permitted_component_ids must be unique"
        )

    verification_binding = (
        verification.goal_contract_id
        == source.goal.contract_id
        and verification.goal_contract_sha256
        == source.goal.contract_sha256
        and verification.system_snapshot_id
        == source.snapshot.snapshot_id
        and verification.system_snapshot_sha256
        == source.snapshot.snapshot_sha256
    )

    if not verification_binding:
        raise ContractError(
            "verification does not bind the "
            "source goal and candidate"
        )

    permitted = set(
        permitted_component_ids
    )

    candidate_components = (
        source.snapshot.component_version_ids
    )

    components_allowed = all(
        component in permitted
        for component in candidate_components
    )

    if (
        verification.outcome
        is VerificationOutcome.VERIFIED
    ):
        outcome = (
            CandidateEligibilityOutcome.ELIGIBLE
            if components_allowed
            else CandidateEligibilityOutcome.INELIGIBLE
        )
    elif (
        verification.outcome
        is VerificationOutcome.INCONCLUSIVE
    ):
        outcome = (
            CandidateEligibilityOutcome.INCONCLUSIVE
        )
    elif (
        verification.outcome
        is VerificationOutcome.BLOCKED
    ):
        outcome = (
            CandidateEligibilityOutcome.BLOCKED
        )
    elif (
        verification.outcome
        is VerificationOutcome.INVALID
    ):
        outcome = (
            CandidateEligibilityOutcome.INVALID
        )
    else:
        outcome = (
            CandidateEligibilityOutcome.INELIGIBLE
        )

    policy_input = {
        "permitted_component_ids": (
            permitted_component_ids
        ),
        "candidate_component_ids": (
            candidate_components
        ),
    }

    policy = {
        "policy": (
            "verified candidate plus permitted "
            "component identities"
        ),
        "policy_version": "1",
        "policy_input": policy_input,
    }

    measured = outcome in (
        CandidateEligibilityOutcome.ELIGIBLE,
        CandidateEligibilityOutcome.INELIGIBLE,
        CandidateEligibilityOutcome.INCONCLUSIVE,
    )

    evidence_references = ()

    if measured:
        evidence_references = (
            "verification-report-sha256:"
            f"{verification.verification_sha256}",
            "policy-check-sha256:"
            f"{canonical_sha256(policy_input)}",
        )

    if (
        outcome
        is CandidateEligibilityOutcome.ELIGIBLE
    ):
        rationale = (
            "candidate is VERIFIED and all candidate "
            "components are permitted by current policy input"
        )
    elif (
        outcome
        is CandidateEligibilityOutcome.INELIGIBLE
        and verification.outcome
        is VerificationOutcome.VERIFIED
    ):
        rationale = (
            "candidate is VERIFIED but one or more "
            "candidate components are not permitted "
            "by current policy input"
        )
    else:
        rationale = (
            "candidate eligibility reflects the bounded "
            "verification and policy state"
        )

    decision = CandidateEligibilityDecision(
        tenant_id=source.goal.tenant_id,
        project_id=source.goal.project_id,
        decision_id=(
            "eligibility-"
            f"{verification.verification_id}-"
            f"{canonical_sha256(policy_input)[:12]}"
        ),
        goal_contract_id=(
            source.goal.contract_id
        ),
        goal_contract_sha256=(
            source.goal.contract_sha256
        ),
        system_snapshot_id=(
            source.snapshot.snapshot_id
        ),
        system_snapshot_sha256=(
            source.snapshot.snapshot_sha256
        ),
        verification_id=(
            verification.verification_id
        ),
        verification_sha256=(
            verification.verification_sha256
        ),
        reviewer_id=_REVIEWER_ID,
        reviewer_version=(
            source.goal.reviewer_version
        ),
        policy_reference=(
            "internal://incident-triage-"
            "candidate-eligibility/v1"
        ),
        policy_sha256=(
            canonical_sha256(policy)
        ),
        outcome=outcome,
        policy_input_references=(
            "policy-input-sha256:"
            f"{canonical_sha256(policy_input)}",
            "candidate-components:"
            + ",".join(candidate_components),
        ),
        evidence_references=(
            evidence_references
        ),
        rationale=rationale,
        uncertainty=(
            "decision is limited to the supplied "
            "bounded component policy"
        ),
        limitations=(
            "does not authorize execution",
            "does not authorize deployment",
            "does not advance lifecycle state",
            "does not establish general candidate safety",
        ),
    )

    decision.validate_against(
        goal=source.goal,
        snapshot=source.snapshot,
        verification=verification,
    )

    return decision


def run_verification_eligibility_demo(
    fault_mode: IncidentFaultMode,
    *,
    run_id: str,
    permitted_component_ids: tuple[str, ...] | None = None,
) -> IncidentVerificationEligibilityResult:
    """Run ordinary repair/evaluation, verification, then policy review."""
    if not isinstance(
        fault_mode,
        IncidentFaultMode,
    ):
        raise ContractError(
            "fault_mode must be an IncidentFaultMode"
        )

    source = run_repair_evaluation_demo(
        fault_mode,
        run_id=f"{run_id}:source",
    )

    (
        verification_run,
        verification_execution,
    ) = execute_verification_candidate(
        source=source,
        fault_mode=fault_mode,
        run_id=f"{run_id}:verification",
    )

    verification_evaluation = (
        evaluate_verification_candidate(
            source=source,
            verification_run=verification_run,
            verification_execution=(
                verification_execution
            ),
        )
    )

    verification_report = (
        build_verification_report(
            source=source,
            verification_run=verification_run,
            verification_execution=(
                verification_execution
            ),
            verification_evaluation=(
                verification_evaluation
            ),
        )
    )

    current_policy = (
        source.snapshot.component_version_ids
        if permitted_component_ids is None
        else permitted_component_ids
    )

    eligibility_decision = (
        review_candidate_eligibility(
            source=source,
            verification=verification_report,
            permitted_component_ids=(
                current_policy
            ),
        )
    )

    return IncidentVerificationEligibilityResult(
        source=source,
        verification_run=verification_run,
        verification_execution=(
            verification_execution
        ),
        verification_evaluation=(
            verification_evaluation
        ),
        verification_report=(
            verification_report
        ),
        eligibility_decision=(
            eligibility_decision
        ),
    )


__all__ = [
    "IncidentVerificationEligibilityResult",
    "build_verification_report",
    "evaluate_verification_candidate",
    "execute_verification_candidate",
    "review_candidate_eligibility",
    "run_verification_eligibility_demo",
]

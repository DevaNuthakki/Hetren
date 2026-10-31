"""Deterministic verification and eligibility vertical slice.

P07.7C consumes a successful ordinary P07.7B repair/evaluation result, performs
a separate real candidate rerun, separately evaluates that rerun, constructs
the existing VerificationReport, and then applies one explicit bounded
candidate-eligibility policy.

Separate records and a separate runner/evaluator pathway establish procedural
separation in this fixture. They do not prove organizational, infrastructure,
data, or environment independence.

VERIFIED is not authorization. ELIGIBLE is not authorization, deployment
approval, lifecycle completion, or permission to execute a production action.
"""

from dataclasses import dataclass

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
from packages.engines.behavioral import (
    FaultMode,
    RepairEvaluationDemoResult,
    ToolAgentRun,
    run_repair_evaluation_demo,
    run_tool_agent,
)


_VERIFICATION_RUNNER_ID = (
    "deterministic-verification-runner"
)
_VERIFICATION_RUNNER_VERSION = "1"

_VERIFICATION_EVALUATOR_ID = (
    "deterministic-verification-evaluator"
)
_VERIFICATION_EVALUATOR_VERSION = "1"

_VERIFIER_ID = "deterministic-verifier"
_VERIFIER_VERSION = "1"

_REVIEWER_ID = "deterministic-policy-reviewer"


@dataclass(frozen=True)
class VerificationEligibilityDemoResult:
    """Convenience bundle; not a new governance or authority contract."""

    source: RepairEvaluationDemoResult
    verification_run: ToolAgentRun
    verification_execution: ExecutionRecord
    verification_evaluation: EvaluationRecord
    verification_report: VerificationReport
    eligibility_decision: CandidateEligibilityDecision


def _require_source_pass(
    source: RepairEvaluationDemoResult,
) -> None:
    if not isinstance(
        source,
        RepairEvaluationDemoResult,
    ):
        raise ContractError(
            "source must be a RepairEvaluationDemoResult"
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

    if (
        source.execution.status
        is not ExecutionStatus.COMPLETED
    ):
        raise ContractError(
            "verification fixture requires "
            "a completed source execution"
        )

    if (
        source.evaluation.outcome
        is not EvaluationOutcome.PASS
    ):
        raise ContractError(
            "source evaluation must PASS "
            "before verification"
        )


def execute_verification_candidate(
    *,
    source: RepairEvaluationDemoResult,
    fault_mode: FaultMode,
    run_id: str,
) -> tuple[ToolAgentRun, ExecutionRecord]:
    """Execute the exact source candidate again as a distinct real run."""
    _require_source_pass(source)

    if not isinstance(
        fault_mode,
        FaultMode,
    ):
        raise ContractError(
            "fault_mode must be a FaultMode"
        )

    if (
        not isinstance(run_id, str)
        or not run_id.strip()
    ):
        raise ContractError(
            "run_id must be non-empty text"
        )

    verification_run = run_tool_agent(
        fault_mode,
        run_id=run_id,
        intervention=source.repair_kind,
    )

    manifest = {
        "runner_id": _VERIFICATION_RUNNER_ID,
        "runner_version": (
            _VERIFICATION_RUNNER_VERSION
        ),
        "source_execution_sha256": (
            source.execution.execution_sha256
        ),
        "candidate_snapshot_sha256": (
            source.snapshot.snapshot_sha256
        ),
        "proposal_sha256": (
            source.proposal.proposal_sha256
        ),
        "repair_kind": (
            source.repair_kind.value
        ),
        "mode": "separate-verification-rerun",
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
            "fixture://deterministic-tool-agent/"
            "verification-rerun"
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

    return verification_run, execution


def evaluate_verification_candidate(
    *,
    source: RepairEvaluationDemoResult,
    verification_run: ToolAgentRun,
    verification_execution: ExecutionRecord,
) -> EvaluationRecord:
    """Separately evaluate observed behavior from the verification rerun."""
    _require_source_pass(source)

    if not isinstance(
        verification_run,
        ToolAgentRun,
    ):
        raise ContractError(
            "verification_run must be a ToolAgentRun"
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

    outcome = (
        EvaluationOutcome.PASS
        if verification_run.output
        == verification_run.expected_output
        else EvaluationOutcome.FAIL
    )

    measurement = {
        "actual_output": verification_run.output,
        "expected_output": (
            verification_run.expected_output
        ),
        "matches": (
            verification_run.output
            == verification_run.expected_output
        ),
        "trace_sha256": (
            verification_run.trace.trace_sha256
        ),
    }

    protocol = {
        "evaluator_id": (
            _VERIFICATION_EVALUATOR_ID
        ),
        "evaluator_version": (
            _VERIFICATION_EVALUATOR_VERSION
        ),
        "metric": "exact-output-match",
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
            "internal://deterministic-verification/"
            "exact-output-v1"
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
        ),
        rationale=(
            "separate verification rerun output "
            + (
                "matched"
                if outcome
                is EvaluationOutcome.PASS
                else "did not match"
            )
            + " the frozen expected output"
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
    source: RepairEvaluationDemoResult,
    verification_execution: ExecutionRecord,
    verification_evaluation: EvaluationRecord,
) -> VerificationReport:
    """Construct and validate the existing VerificationReport."""
    _require_source_pass(source)

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

    mapping = {
        EvaluationOutcome.PASS: (
            VerificationOutcome.VERIFIED
        ),
        EvaluationOutcome.FAIL: (
            VerificationOutcome.REJECTED
        ),
        EvaluationOutcome.INCONCLUSIVE: (
            VerificationOutcome.INCONCLUSIVE
        ),
        EvaluationOutcome.BLOCKED: (
            VerificationOutcome.BLOCKED
        ),
        EvaluationOutcome.INVALID: (
            VerificationOutcome.INVALID
        ),
    }

    outcome = mapping[
        verification_evaluation.outcome
    ]

    measured = outcome in (
        VerificationOutcome.VERIFIED,
        VerificationOutcome.REJECTED,
        VerificationOutcome.INCONCLUSIVE,
    )

    protocol = {
        "verifier_id": _VERIFIER_ID,
        "verifier_version": _VERIFIER_VERSION,
        "rule": (
            "map separate verification evaluation "
            "outcome to verification outcome"
        ),
        "candidate_snapshot_sha256": (
            source.snapshot.snapshot_sha256
        ),
    }

    independence_references = ()

    if measured:
        independence_references = (
            "procedural-separation:"
            f"source-execution:{source.execution.execution_id}",
            "procedural-separation:"
            "verification-execution:"
            f"{verification_execution.execution_id}",
            "procedural-separation:"
            f"source-evaluation:{source.evaluation.evaluation_id}",
            "procedural-separation:"
            "verification-evaluation:"
            f"{verification_evaluation.evaluation_id}",
        )

    evidence_references = ()

    if measured:
        evidence_references = (
            "verification-evaluation-sha256:"
            f"{verification_evaluation.evaluation_sha256}",
            *verification_evaluation.evidence_references,
        )

    report = VerificationReport(
        tenant_id=source.goal.tenant_id,
        project_id=source.goal.project_id,
        verification_id=(
            "verification-report-"
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
            "internal://deterministic-verifier/v1"
        ),
        protocol_sha256=(
            canonical_sha256(protocol)
        ),
        outcome=outcome,
        independence_references=(
            independence_references
        ),
        evidence_references=(
            evidence_references
        ),
        rationale=(
            "verification conclusion derived from "
            "a distinct candidate rerun and evaluation"
        ),
        uncertainty=(
            "procedural separation is demonstrated; "
            "infrastructure, organizational and data "
            "independence are not established"
        ),
        limitations=(
            "same local Python process",
            "same deterministic fixture implementation",
            "independence references are provenance, not proof",
            "no authorization or deployment authority",
        ),
    )

    report.validate_against(
        goal=source.goal,
        snapshot=source.snapshot,
        source_execution=source.execution,
        source_evaluation=source.evaluation,
        verification_execution=verification_execution,
        verification_evaluation=verification_evaluation,
    )

    return report


def review_candidate_eligibility(
    *,
    source: RepairEvaluationDemoResult,
    verification: VerificationReport,
    permitted_component_ids: tuple[str, ...],
) -> CandidateEligibilityDecision:
    """Apply one explicit bounded candidate policy.

    VERIFIED is necessary for ELIGIBLE but is not sufficient. The candidate's
    component identities must also be present in the caller-supplied current
    policy input.
    """
    _require_source_pass(source)

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
            "internal://deterministic-candidate-"
            "eligibility/v1"
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
    fault_mode: FaultMode,
    *,
    run_id: str,
    permitted_component_ids: tuple[str, ...] | None = None,
) -> VerificationEligibilityDemoResult:
    """Run ordinary repair/evaluation, verification, then policy review."""
    if not isinstance(
        fault_mode,
        FaultMode,
    ):
        raise ContractError(
            "fault_mode must be a FaultMode"
        )

    source = run_repair_evaluation_demo(
        fault_mode,
        run_id=f"{run_id}:source",
    )

    verification_run, verification_execution = (
        execute_verification_candidate(
            source=source,
            fault_mode=fault_mode,
            run_id=f"{run_id}:verification",
        )
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

    report = build_verification_report(
        source=source,
        verification_execution=(
            verification_execution
        ),
        verification_evaluation=(
            verification_evaluation
        ),
    )

    current_policy = (
        source.snapshot.component_version_ids
        if permitted_component_ids is None
        else permitted_component_ids
    )

    eligibility = review_candidate_eligibility(
        source=source,
        verification=report,
        permitted_component_ids=(
            current_policy
        ),
    )

    return VerificationEligibilityDemoResult(
        source=source,
        verification_run=verification_run,
        verification_execution=(
            verification_execution
        ),
        verification_evaluation=(
            verification_evaluation
        ),
        verification_report=report,
        eligibility_decision=eligibility,
    )


__all__ = [
    "VerificationEligibilityDemoResult",
    "build_verification_report",
    "evaluate_verification_candidate",
    "execute_verification_candidate",
    "review_candidate_eligibility",
    "run_verification_eligibility_demo",
]

"""Deterministic bounded repair and evaluation integration.

P07.7B consumes the diagnosis produced by the P07.7A deterministic fixture,
selects a bounded candidate repair, materializes that candidate through the
existing governance contracts, actually executes it, and evaluates the
observed result.

This module deliberately stops at ordinary EvaluationRecord. A PASS does not
create independent verification, eligibility, authorization, deployment
permission, lifecycle completion, or a claim of general repair capability.
"""

from dataclasses import dataclass

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
from .deterministic_tool_agent import (
    DiagnosisDemoResult,
    FaultMode,
    ToolAgentRun,
    run_diagnosis_demo,
    run_tool_agent,
)


_REPAIR_RUNNER_ID = "deterministic-repair-runner"
_REPAIR_RUNNER_VERSION = "1"
_EVALUATOR_ID = "deterministic-sum-evaluator"
_EVALUATOR_VERSION = "1"


@dataclass(frozen=True)
class RepairEvaluationDemoResult:
    """Convenience bundle for one bounded executable repair demonstration.

    This is not a governance or authority contract. The authoritative
    provenance records remain GoalContract, SystemSnapshot, MethodProposal,
    ExecutionRecord and EvaluationRecord.
    """

    diagnosis: DiagnosisDemoResult
    repair_kind: InterventionKind
    goal: GoalContract
    snapshot: SystemSnapshot
    proposal: MethodProposal
    candidate_run: ToolAgentRun
    execution: ExecutionRecord
    evaluation: EvaluationRecord


def build_repair_goal() -> GoalContract:
    """Return the frozen objective used by every P07.7B candidate."""
    return GoalContract(
        tenant_id="portfolio",
        project_id="deterministic-agent-repair",
        contract_id="deterministic-sum-repair-goal",
        contract_version="1",
        system_id="deterministic-tool-agent",
        system_version_id="faulty-v1",
        claim_scope=(
            "bounded repair of the deterministic "
            "arithmetic tool-agent fixture"
        ),
        objective=(
            "restore the requested 7 + 5 result "
            "to the expected value 12"
        ),
        metrics=(
            "exact-output-match",
        ),
        minimum_effect=(
            "candidate output equals 12"
        ),
        baseline_reference=(
            "fixture://deterministic-tool-agent/faulty-v1"
        ),
        acceptance_predicates=(
            "candidate output equals expected output 12",
        ),
        hard_constraints=(
            "candidate execution remains deterministic",
            "candidate changes only the diagnosed bounded behavior",
        ),
        invariants=(
            "no network or external-provider execution",
            "frozen evaluation occurs after candidate execution",
        ),
        eligible_changes=(
            "tool-selection rule",
            "argument-transformation rule",
        ),
        budget_constraints=(
            "one candidate execution",
        ),
        reviewer_version="deterministic-reviewer-v1",
        evaluator_version=_EVALUATOR_VERSION,
        evidence_requirements=(
            "candidate execution evidence digest",
            "candidate execution trace digest",
        ),
        protected_evaluation_requirements=(
            "evaluation outcome calculated from executed candidate output",
        ),
        uncertainty_policy=(
            "claims remain limited to the deterministic fixture"
        ),
        failure_invalidity_policy=(
            "preserve candidate execution failure separately "
            "from evaluator invalidity"
        ),
        verification_requirements=(
            "ordinary PASS requires separate later verification "
            "before any VERIFIED claim",
        ),
    )


def select_candidate_repair(
    diagnosis: DiagnosisDemoResult,
) -> InterventionKind:
    """Select the bounded repair from diagnosed evidence only.

    The function receives no latent FaultMode. The simulated environment's
    hidden fault is used later only to execute the candidate against that
    controlled environment.
    """
    if not isinstance(
        diagnosis,
        DiagnosisDemoResult,
    ):
        raise ContractError(
            "diagnosis must be a DiagnosisDemoResult"
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
        "tool_selection_fault": (
            InterventionKind.REPLACE_TOOL
        ),
        "parameter_transformation_fault": (
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
        return 'selected_tool = "add"'

    if (
        repair_kind
        is InterventionKind.OVERRIDE_PARAMETER
    ):
        return "arguments = (7, 5)"

    raise ContractError(
        "unsupported candidate repair kind"
    )


def _repair_component_id(
    repair_kind: InterventionKind,
) -> str:
    if (
        repair_kind
        is InterventionKind.REPLACE_TOOL
    ):
        return "repair-replace-tool-add-v1"

    if (
        repair_kind
        is InterventionKind.OVERRIDE_PARAMETER
    ):
        return "repair-override-arguments-7-5-v1"

    raise ContractError(
        "unsupported candidate repair kind"
    )


def _repair_code_identity(
    repair_kind: InterventionKind,
) -> str:
    program = _repair_program(
        repair_kind
    )

    return canonical_sha256(
        {
            "repair_kind": repair_kind.value,
            "generated_program": program,
        }
    )


def build_candidate_snapshot(
    diagnosis: DiagnosisDemoResult,
    repair_kind: InterventionKind,
) -> SystemSnapshot:
    """Materialize exact candidate state for one bounded repair."""
    if not isinstance(
        diagnosis,
        DiagnosisDemoResult,
    ):
        raise ContractError(
            "diagnosis must be a DiagnosisDemoResult"
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
            "candidate snapshot requires a diagnosed hypothesis"
        )

    return SystemSnapshot(
        tenant_id="portfolio",
        project_id="deterministic-agent-repair",
        snapshot_id=(
            "candidate-"
            f"{diagnosed_key}-"
            f"{repair_kind.value}-v1"
        ),
        system_id="deterministic-tool-agent",
        system_version_id=(
            "candidate-"
            f"{repair_kind.value}-v1"
        ),
        environment_family=(
            "deterministic-tool-agent-fixture"
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
    diagnosis: DiagnosisDemoResult,
    repair_kind: InterventionKind,
) -> MethodProposal:
    """Describe the candidate method without executing it."""
    if not isinstance(goal, GoalContract):
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
        DiagnosisDemoResult,
    ):
        raise ContractError(
            "diagnosis must be a DiagnosisDemoResult"
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
            "repair proposal requires a diagnosed hypothesis"
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
            "the frozen expected output?"
        ),
        alternatives=(
            "candidate passes frozen evaluator",
            "candidate fails frozen evaluator",
        ),
        expected_outcomes=(
            "candidate execution produces independently "
            "measurable output",
        ),
        controls=(
            "same deterministic arithmetic request",
            "same frozen expected output 12",
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
    """Bind typed repair semantics to snapshot/proposal provenance.

    Existing governance contracts validate lineage. This helper additionally
    ensures that the candidate actually executed by this deterministic runner
    is the same bounded repair encoded by the supplied snapshot and proposal.
    """
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
    fault_mode: FaultMode,
    run_id: str,
    goal: GoalContract,
    snapshot: SystemSnapshot,
    proposal: MethodProposal,
    repair_kind: InterventionKind,
) -> tuple[ToolAgentRun, ExecutionRecord]:
    """Actually execute one frozen candidate repair."""
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

    if not isinstance(goal, GoalContract):
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

    candidate_run = run_tool_agent(
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
            "fixture://deterministic-tool-agent"
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
        ),
        trace_references=(
            "trace-sha256:"
            f"{candidate_run.trace.trace_sha256}",
        ),
        limitations=(
            "deterministic fixture only",
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
    candidate_run: ToolAgentRun,
) -> EvaluationRecord:
    """Evaluate observed candidate behavior after execution.

    The verdict is computed from the actual candidate output. It does not use
    the repair hypothesis, repair kind, proposal expected outcomes, or runner
    completion status as a substitute for the frozen acceptance predicate.
    """
    if not isinstance(goal, GoalContract):
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
        ToolAgentRun,
    ):
        raise ContractError(
            "candidate_run must be a ToolAgentRun"
        )

    outcome = (
        EvaluationOutcome.PASS
        if candidate_run.output
        == candidate_run.expected_output
        else EvaluationOutcome.FAIL
    )

    measurement = {
        "actual_output": candidate_run.output,
        "expected_output": (
            candidate_run.expected_output
        ),
        "matches": (
            candidate_run.output
            == candidate_run.expected_output
        ),
    }

    protocol = {
        "evaluator_id": _EVALUATOR_ID,
        "evaluator_version": (
            _EVALUATOR_VERSION
        ),
        "acceptance_predicates": (
            goal.acceptance_predicates
        ),
        "metric": "exact-output-match",
    }

    if outcome is EvaluationOutcome.PASS:
        rationale = (
            "executed candidate output matched "
            "the frozen expected output"
        )
    else:
        rationale = (
            "executed candidate output did not match "
            "the frozen expected output"
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
            "internal://deterministic-sum-evaluator/v1"
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
        ),
        rationale=rationale,
        uncertainty=(
            "evaluation is exact for this deterministic "
            "fixture only"
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
    fault_mode: FaultMode,
    *,
    run_id: str,
    repair_kind: InterventionKind | None = None,
) -> RepairEvaluationDemoResult:
    """Run diagnosis, candidate construction, execution and evaluation.

    Supplying repair_kind is intentionally supported for controlled negative
    tests. When omitted, the candidate is selected only from diagnosis.
    """
    if not isinstance(
        fault_mode,
        FaultMode,
    ):
        raise ContractError(
            "fault_mode must be a FaultMode"
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

    return RepairEvaluationDemoResult(
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
    "RepairEvaluationDemoResult",
    "build_candidate_snapshot",
    "build_repair_goal",
    "build_repair_proposal",
    "evaluate_candidate_run",
    "execute_repair_candidate",
    "run_repair_evaluation_demo",
    "select_candidate_repair",
]

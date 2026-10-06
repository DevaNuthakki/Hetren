"""Inert records for terminal attempts and evaluator-reported outcomes.

These types validate structure and explicit links. They do not run tools,
resolve evidence, authorize actions, calculate verdicts, or verify repairs.
"""

from dataclasses import dataclass, fields
from enum import StrEnum
import re

from .records import (
    ContractError,
    GoalContract,
    MethodProposal,
    SystemSnapshot,
    _require_optional_text,
    _require_text,
    _require_tuple,
    canonical_sha256,
)


class ExecutionStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class EvaluationOutcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"
    BLOCKED = "BLOCKED"
    INVALID = "INVALID"


def _require_sha256(value: object, field: str) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ContractError(f"{field} must be a lowercase SHA-256 hex digest")


def _require_equal(actual: object, expected: object, field: str) -> None:
    if actual != expected:
        raise ContractError(f"{field} does not match the supplied record")


def _require_type(value: object, expected: type, field: str) -> None:
    if not isinstance(value, expected):
        raise ContractError(f"{field} must be a {expected.__name__}")


def _require_scope(record: object, related: object, name: str) -> None:
    for field in ("tenant_id", "project_id"):
        _require_equal(
            getattr(record, field), getattr(related, field), f"{name}.{field}"
        )


@dataclass(frozen=True)
class ExecutionRecord:
    """One terminal attempt; COMPLETED describes the runner, not task success.

    BLOCKED records an attempt prevented from starting by a prerequisite.
    Diagnostic traces are allowed for such an attempt; a process exit code
    is not. Other abnormal endings require an explanation. Exit codes, when
    known, describe the top-level runner, not commands the agent called.

    References are opaque identifiers. An execution manifest should preserve
    replay mode, trial/condition identity, configuration and resource usage.
    This class never reads that manifest or proves its contents are true.
    """

    tenant_id: str
    project_id: str
    execution_id: str
    goal_contract_id: str
    goal_contract_sha256: str
    system_snapshot_id: str
    system_snapshot_sha256: str
    method_proposal_id: str
    method_proposal_sha256: str
    runner_id: str
    runner_version: str
    environment_reference: str | None
    execution_manifest_reference: str | None
    status: ExecutionStatus
    exit_code: int | None
    termination_reason: str | None
    input_references: tuple[str, ...]
    output_references: tuple[str, ...]
    trace_references: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        for field in (
            "tenant_id", "project_id", "execution_id", "goal_contract_id",
            "system_snapshot_id", "method_proposal_id", "runner_id",
            "runner_version",
        ):
            _require_text(getattr(self, field), field)
        for field in (
            "goal_contract_sha256", "system_snapshot_sha256",
            "method_proposal_sha256",
        ):
            _require_sha256(getattr(self, field), field)
        for field in (
            "environment_reference", "execution_manifest_reference",
            "termination_reason",
        ):
            _require_optional_text(getattr(self, field), field)
        for field in (
            "input_references", "output_references", "trace_references",
            "limitations",
        ):
            _require_tuple(getattr(self, field), field)
        _require_type(self.status, ExecutionStatus, "status")
        # bool is an int subclass, but is not a valid process exit code.
        if self.exit_code is not None and type(self.exit_code) is not int:
            raise ContractError("exit_code must be an integer or None")
        if self.status is ExecutionStatus.COMPLETED:
            if self.exit_code not in (None, 0):
                raise ContractError("completed runner cannot have a nonzero exit_code")
        elif self.termination_reason is None:
            raise ContractError("abnormal termination requires termination_reason")
        if self.status is ExecutionStatus.BLOCKED and self.exit_code is not None:
            raise ContractError("blocked before launch cannot have an exit_code")

    def canonical_payload(self) -> dict[str, object]:
        payload = {field.name: getattr(self, field.name) for field in fields(self)}
        payload["status"] = self.status.value
        return {"record_type": "ExecutionRecord", "schema_version": 1, **payload}

    @property
    def execution_sha256(self) -> str:
        return canonical_sha256(self.canonical_payload())

    def validate_against(
        self, *, goal: GoalContract, snapshot: SystemSnapshot,
        proposal: MethodProposal,
    ) -> None:
        """Check supplied objects and bindings without resolving external data.

        The goal's declared system version may be a baseline and the snapshot
        may be a repair candidate. Version eligibility is a separate policy
        check; exact snapshot content is bound here by its digest.
        """
        for value, kind, name in (
            (goal, GoalContract, "goal"),
            (snapshot, SystemSnapshot, "snapshot"),
            (proposal, MethodProposal, "proposal"),
        ):
            _require_type(value, kind, name)
            _require_scope(self, value, name)
        for actual, expected, name in (
            (self.goal_contract_id, goal.contract_id, "goal_contract_id"),
            (self.goal_contract_sha256, goal.contract_sha256, "goal_contract_sha256"),
            (self.system_snapshot_id, snapshot.snapshot_id, "system_snapshot_id"),
            (self.system_snapshot_sha256, snapshot.snapshot_sha256, "system_snapshot_sha256"),
            (self.method_proposal_id, proposal.proposal_id, "method_proposal_id"),
            (self.method_proposal_sha256, proposal.proposal_sha256, "method_proposal_sha256"),
            (proposal.goal_contract_id, goal.contract_id, "proposal.goal_contract_id"),
            (proposal.system_snapshot_id, snapshot.snapshot_id, "proposal.system_snapshot_id"),
            (goal.system_id, snapshot.system_id, "snapshot.system_id"),
        ):
            _require_equal(actual, expected, name)


@dataclass(frozen=True)
class EvaluationRecord:
    """Evaluator-reported outcome; construction is not evaluation or verification.

    PASS, FAIL and INCONCLUSIVE require evidence references structurally.
    Evidence validity, predicate coverage and verdict correctness remain the
    evaluator's responsibility. BLOCKED and INVALID may lack usable evidence
    but still require a rationale and an explicit uncertainty statement.

    There is no automatic mapping from execution status to evaluation outcome:
    a timed-out run may decisively FAIL a deadline predicate, for example.
    """

    tenant_id: str
    project_id: str
    evaluation_id: str
    goal_contract_id: str
    goal_contract_sha256: str
    execution_id: str
    execution_sha256: str
    evaluator_id: str
    evaluator_version: str
    protocol_reference: str
    protocol_sha256: str
    outcome: EvaluationOutcome
    measurement_references: tuple[str, ...]
    evidence_references: tuple[str, ...]
    rationale: str
    uncertainty: str
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        for field in (
            "tenant_id", "project_id", "evaluation_id", "goal_contract_id",
            "execution_id", "evaluator_id", "evaluator_version",
            "protocol_reference", "rationale", "uncertainty",
        ):
            _require_text(getattr(self, field), field)
        for field in (
            "goal_contract_sha256", "execution_sha256", "protocol_sha256",
        ):
            _require_sha256(getattr(self, field), field)
        for field in (
            "measurement_references", "evidence_references", "limitations",
        ):
            _require_tuple(getattr(self, field), field)
        _require_type(self.outcome, EvaluationOutcome, "outcome")
        if self.outcome in (
            EvaluationOutcome.PASS, EvaluationOutcome.FAIL,
            EvaluationOutcome.INCONCLUSIVE,
        ) and not self.evidence_references:
            raise ContractError(f"{self.outcome.value} requires evidence references")

    def canonical_payload(self) -> dict[str, object]:
        payload = {field.name: getattr(self, field.name) for field in fields(self)}
        payload["outcome"] = self.outcome.value
        return {"record_type": "EvaluationRecord", "schema_version": 1, **payload}

    @property
    def evaluation_sha256(self) -> str:
        return canonical_sha256(self.canonical_payload())

    def validate_against(
        self, *, goal: GoalContract, execution: ExecutionRecord,
    ) -> None:
        """Check goal/execution/evaluator bindings; not the truth of the verdict.

        This checks only the supplied execution's goal binding. Its snapshot
        and proposal must separately pass ExecutionRecord.validate_against.
        """
        for value, kind, name in (
            (goal, GoalContract, "goal"),
            (execution, ExecutionRecord, "execution"),
        ):
            _require_type(value, kind, name)
            _require_scope(self, value, name)
        for actual, expected, name in (
            (self.goal_contract_id, goal.contract_id, "goal_contract_id"),
            (self.goal_contract_sha256, goal.contract_sha256, "goal_contract_sha256"),
            (self.execution_id, execution.execution_id, "execution_id"),
            (self.execution_sha256, execution.execution_sha256, "execution_sha256"),
            (execution.goal_contract_id, goal.contract_id, "execution.goal_contract_id"),
            (execution.goal_contract_sha256, goal.contract_sha256, "execution.goal_contract_sha256"),
            (self.evaluator_version, goal.evaluator_version, "evaluator_version"),
        ):
            _require_equal(actual, expected, name)


__all__ = [
    "ExecutionStatus", "EvaluationOutcome", "ExecutionRecord", "EvaluationRecord",
]

"""Inert provenance contract for independent verification.

The report validates structure, lineage and explicit bindings. It does not run
verification, resolve referenced evidence, prove independence, authorize a
repair, mutate lifecycle state, or establish that a verifier's conclusion is
true.
"""

from dataclasses import dataclass, fields
from enum import StrEnum

from .execution import (
    EvaluationOutcome,
    EvaluationRecord,
    ExecutionRecord,
    _require_equal,
    _require_scope,
    _require_sha256,
    _require_type,
)
from .records import (
    ContractError,
    GoalContract,
    SystemSnapshot,
    _require_text,
    _require_tuple,
    canonical_sha256,
)


class VerificationOutcome(StrEnum):
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    BLOCKED = "BLOCKED"
    INVALID = "INVALID"


_EVALUATION_OUTCOME_BY_VERIFICATION_OUTCOME = {
    VerificationOutcome.VERIFIED: EvaluationOutcome.PASS,
    VerificationOutcome.REJECTED: EvaluationOutcome.FAIL,
    VerificationOutcome.INCONCLUSIVE: EvaluationOutcome.INCONCLUSIVE,
    VerificationOutcome.BLOCKED: EvaluationOutcome.BLOCKED,
    VerificationOutcome.INVALID: EvaluationOutcome.INVALID,
}


@dataclass(frozen=True)
class VerificationReport:
    """Verifier-reported result for a separate verification lineage.

    The source execution/evaluation identify the ordinary evaluation lineage.
    That source evaluation must have reported PASS before this independent
    verification gate is applicable.

    The verification execution/evaluation identify a separate attempt over the
    same candidate snapshot. Distinct record identities establish only that the
    records/runs are separate. They do not prove hidden-data isolation,
    organizational independence, clean infrastructure, evidence truth, or
    satisfaction of GoalContract.verification_requirements.

    VERIFIED, REJECTED and INCONCLUSIVE require both evidence references and
    independence references structurally. BLOCKED and INVALID may lack usable
    evidence because the verification process itself may have been unavailable
    or invalid.

    Construction and validation never authorize a repair or advance any
    lifecycle to VERIFIED or COMPLETE.
    """

    tenant_id: str
    project_id: str
    verification_id: str

    goal_contract_id: str
    goal_contract_sha256: str

    system_snapshot_id: str
    system_snapshot_sha256: str

    source_execution_id: str
    source_execution_sha256: str
    source_evaluation_id: str
    source_evaluation_sha256: str

    verification_execution_id: str
    verification_execution_sha256: str
    verification_evaluation_id: str
    verification_evaluation_sha256: str

    verifier_id: str
    verifier_version: str

    protocol_reference: str
    protocol_sha256: str

    outcome: VerificationOutcome

    independence_references: tuple[str, ...]
    evidence_references: tuple[str, ...]

    rationale: str
    uncertainty: str
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        for field in (
            "tenant_id",
            "project_id",
            "verification_id",
            "goal_contract_id",
            "system_snapshot_id",
            "source_execution_id",
            "source_evaluation_id",
            "verification_execution_id",
            "verification_evaluation_id",
            "verifier_id",
            "verifier_version",
            "protocol_reference",
            "rationale",
            "uncertainty",
        ):
            _require_text(getattr(self, field), field)

        for field in (
            "goal_contract_sha256",
            "system_snapshot_sha256",
            "source_execution_sha256",
            "source_evaluation_sha256",
            "verification_execution_sha256",
            "verification_evaluation_sha256",
            "protocol_sha256",
        ):
            _require_sha256(getattr(self, field), field)

        for field in (
            "independence_references",
            "evidence_references",
            "limitations",
        ):
            _require_tuple(getattr(self, field), field)

        _require_type(
            self.outcome,
            VerificationOutcome,
            "outcome",
        )

        if self.source_execution_id == self.verification_execution_id:
            raise ContractError(
                "verification execution must be distinct from source execution"
            )

        if (
            self.source_evaluation_id
            == self.verification_evaluation_id
        ):
            raise ContractError(
                "verification evaluation must be distinct from source evaluation"
            )

        if (
            self.source_execution_sha256
            == self.verification_execution_sha256
        ):
            raise ContractError(
                "verification execution digest must differ from source execution"
            )

        if (
            self.source_evaluation_sha256
            == self.verification_evaluation_sha256
        ):
            raise ContractError(
                "verification evaluation digest must differ from source evaluation"
            )

        if self.outcome in (
            VerificationOutcome.VERIFIED,
            VerificationOutcome.REJECTED,
            VerificationOutcome.INCONCLUSIVE,
        ):
            if not self.evidence_references:
                raise ContractError(
                    f"{self.outcome.value} requires evidence references"
                )

            if not self.independence_references:
                raise ContractError(
                    f"{self.outcome.value} requires independence references"
                )

    def canonical_payload(self) -> dict[str, object]:
        payload = {
            field.name: getattr(self, field.name)
            for field in fields(self)
        }
        payload["outcome"] = self.outcome.value

        return {
            "record_type": "VerificationReport",
            "schema_version": 1,
            **payload,
        }

    @property
    def verification_sha256(self) -> str:
        return canonical_sha256(self.canonical_payload())

    def validate_against(
        self,
        *,
        goal: GoalContract,
        snapshot: SystemSnapshot,
        source_execution: ExecutionRecord,
        source_evaluation: EvaluationRecord,
        verification_execution: ExecutionRecord,
        verification_evaluation: EvaluationRecord,
    ) -> None:
        """Validate supplied lineage without resolving external evidence.

        This validates record identities, hashes, shared scope, the frozen goal,
        the common candidate snapshot, the ordinary PASS prerequisite, and the
        correspondence between the independent evaluation outcome and this
        verifier-reported outcome.

        ExecutionRecord.validate_against still remains responsible for each
        execution's MethodProposal binding. This method deliberately does not
        resolve those proposals or any external evidence/reference.
        """

        for value, kind, name in (
            (goal, GoalContract, "goal"),
            (snapshot, SystemSnapshot, "snapshot"),
            (
                source_execution,
                ExecutionRecord,
                "source_execution",
            ),
            (
                source_evaluation,
                EvaluationRecord,
                "source_evaluation",
            ),
            (
                verification_execution,
                ExecutionRecord,
                "verification_execution",
            ),
            (
                verification_evaluation,
                EvaluationRecord,
                "verification_evaluation",
            ),
        ):
            _require_type(value, kind, name)
            _require_scope(self, value, name)

        for actual, expected, name in (
            (
                self.goal_contract_id,
                goal.contract_id,
                "goal_contract_id",
            ),
            (
                self.goal_contract_sha256,
                goal.contract_sha256,
                "goal_contract_sha256",
            ),
            (
                self.system_snapshot_id,
                snapshot.snapshot_id,
                "system_snapshot_id",
            ),
            (
                self.system_snapshot_sha256,
                snapshot.snapshot_sha256,
                "system_snapshot_sha256",
            ),
            (
                self.source_execution_id,
                source_execution.execution_id,
                "source_execution_id",
            ),
            (
                self.source_execution_sha256,
                source_execution.execution_sha256,
                "source_execution_sha256",
            ),
            (
                self.source_evaluation_id,
                source_evaluation.evaluation_id,
                "source_evaluation_id",
            ),
            (
                self.source_evaluation_sha256,
                source_evaluation.evaluation_sha256,
                "source_evaluation_sha256",
            ),
            (
                self.verification_execution_id,
                verification_execution.execution_id,
                "verification_execution_id",
            ),
            (
                self.verification_execution_sha256,
                verification_execution.execution_sha256,
                "verification_execution_sha256",
            ),
            (
                self.verification_evaluation_id,
                verification_evaluation.evaluation_id,
                "verification_evaluation_id",
            ),
            (
                self.verification_evaluation_sha256,
                verification_evaluation.evaluation_sha256,
                "verification_evaluation_sha256",
            ),
            (
                source_execution.goal_contract_id,
                goal.contract_id,
                "source_execution.goal_contract_id",
            ),
            (
                source_execution.goal_contract_sha256,
                goal.contract_sha256,
                "source_execution.goal_contract_sha256",
            ),
            (
                verification_execution.goal_contract_id,
                goal.contract_id,
                "verification_execution.goal_contract_id",
            ),
            (
                verification_execution.goal_contract_sha256,
                goal.contract_sha256,
                "verification_execution.goal_contract_sha256",
            ),
            (
                source_execution.system_snapshot_id,
                snapshot.snapshot_id,
                "source_execution.system_snapshot_id",
            ),
            (
                source_execution.system_snapshot_sha256,
                snapshot.snapshot_sha256,
                "source_execution.system_snapshot_sha256",
            ),
            (
                verification_execution.system_snapshot_id,
                snapshot.snapshot_id,
                "verification_execution.system_snapshot_id",
            ),
            (
                verification_execution.system_snapshot_sha256,
                snapshot.snapshot_sha256,
                "verification_execution.system_snapshot_sha256",
            ),
            (
                goal.system_id,
                snapshot.system_id,
                "snapshot.system_id",
            ),
        ):
            _require_equal(actual, expected, name)

        if (
            source_execution.execution_id
            == verification_execution.execution_id
        ):
            raise ContractError(
                "verification execution must be distinct from source execution"
            )

        if (
            source_evaluation.evaluation_id
            == verification_evaluation.evaluation_id
        ):
            raise ContractError(
                "verification evaluation must be distinct from source evaluation"
            )

        source_evaluation.validate_against(
            goal=goal,
            execution=source_execution,
        )

        verification_evaluation.validate_against(
            goal=goal,
            execution=verification_execution,
        )

        if source_evaluation.outcome is not EvaluationOutcome.PASS:
            raise ContractError(
                "source evaluation must PASS before independent verification"
            )

        expected_outcome = (
            _EVALUATION_OUTCOME_BY_VERIFICATION_OUTCOME[
                self.outcome
            ]
        )

        if verification_evaluation.outcome is not expected_outcome:
            raise ContractError(
                "verification outcome does not match "
                "the supplied verification evaluation"
            )


__all__ = [
    "VerificationOutcome",
    "VerificationReport",
]

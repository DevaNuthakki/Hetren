"""Inert contract for bounded Repair Contrast evidence.

A RepairContrastRecord compares ordinary evaluations of one known-bad state
and one candidate repaired state for one exact bounded claim.

The contract validates structural lineage and the registered contrast rule. It
does not execute either system state, calculate the underlying evaluations,
resolve referenced evidence, prove causal correctness, prove that the repair is
globally correct, perform independent verification, establish eligibility,
authorize deployment, or mutate lifecycle state.

REPAIR_DISCRIMINATING has one deliberately narrow meaning here:

    known-bad ordinary evaluation == FAIL
    candidate ordinary evaluation == PASS

under the same ordinary evaluator identity/version, the same evaluation
protocol, the same execution-runner identity/version, and the same registered
comparison case.

The comparison case is a hash-bound reference to the test stimulus and
conditions that are intended to remain fixed across the two states. Requiring
the same reference is structural provenance only; this contract does not prove
that an external runner actually honored those conditions.

That pattern supports only the registered bounded repair claim. It is not proof
of general correctness, causal attribution, or independence.
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


class RepairContrastOutcome(StrEnum):
    REPAIR_DISCRIMINATING = "REPAIR_DISCRIMINATING"
    NOT_REPAIR_DISCRIMINATING = "NOT_REPAIR_DISCRIMINATING"
    INCONCLUSIVE = "INCONCLUSIVE"
    BLOCKED = "BLOCKED"
    INVALID = "INVALID"


def _expected_contrast_outcome(
    known_bad: EvaluationOutcome,
    candidate: EvaluationOutcome,
) -> RepairContrastOutcome:
    if (
        known_bad is EvaluationOutcome.INVALID
        or candidate is EvaluationOutcome.INVALID
    ):
        return RepairContrastOutcome.INVALID

    if (
        known_bad is EvaluationOutcome.BLOCKED
        or candidate is EvaluationOutcome.BLOCKED
    ):
        return RepairContrastOutcome.BLOCKED

    if (
        known_bad is EvaluationOutcome.INCONCLUSIVE
        or candidate is EvaluationOutcome.INCONCLUSIVE
    ):
        return RepairContrastOutcome.INCONCLUSIVE

    if (
        known_bad is EvaluationOutcome.FAIL
        and candidate is EvaluationOutcome.PASS
    ):
        return RepairContrastOutcome.REPAIR_DISCRIMINATING

    return RepairContrastOutcome.NOT_REPAIR_DISCRIMINATING


@dataclass(frozen=True)
class RepairContrastRecord:
    """Qualifier-reported bounded contrast over two ordinary evaluations."""

    tenant_id: str
    project_id: str
    contrast_id: str

    goal_contract_id: str
    goal_contract_sha256: str

    known_bad_snapshot_id: str
    known_bad_snapshot_sha256: str

    candidate_snapshot_id: str
    candidate_snapshot_sha256: str

    known_bad_execution_id: str
    known_bad_execution_sha256: str
    known_bad_evaluation_id: str
    known_bad_evaluation_sha256: str

    candidate_execution_id: str
    candidate_execution_sha256: str
    candidate_evaluation_id: str
    candidate_evaluation_sha256: str

    claim_reference: str
    claim_sha256: str

    comparison_case_reference: str
    comparison_case_sha256: str

    contrast_qualifier_id: str
    contrast_qualifier_version: str

    contrast_protocol_reference: str
    contrast_protocol_sha256: str

    outcome: RepairContrastOutcome

    evidence_references: tuple[str, ...]
    rationale: str
    uncertainty: str
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        for field in (
            "tenant_id",
            "project_id",
            "contrast_id",
            "goal_contract_id",
            "known_bad_snapshot_id",
            "candidate_snapshot_id",
            "known_bad_execution_id",
            "known_bad_evaluation_id",
            "candidate_execution_id",
            "candidate_evaluation_id",
            "claim_reference",
            "comparison_case_reference",
            "contrast_qualifier_id",
            "contrast_qualifier_version",
            "contrast_protocol_reference",
            "rationale",
            "uncertainty",
        ):
            _require_text(
                getattr(self, field),
                field,
            )

        for field in (
            "goal_contract_sha256",
            "known_bad_snapshot_sha256",
            "candidate_snapshot_sha256",
            "known_bad_execution_sha256",
            "known_bad_evaluation_sha256",
            "candidate_execution_sha256",
            "candidate_evaluation_sha256",
            "claim_sha256",
            "comparison_case_sha256",
            "contrast_protocol_sha256",
        ):
            _require_sha256(
                getattr(self, field),
                field,
            )

        _require_tuple(
            self.evidence_references,
            "evidence_references",
        )

        _require_tuple(
            self.limitations,
            "limitations",
        )

        _require_type(
            self.outcome,
            RepairContrastOutcome,
            "outcome",
        )

        if (
            self.known_bad_snapshot_id
            == self.candidate_snapshot_id
        ):
            raise ContractError(
                "known-bad and candidate snapshot IDs must differ"
            )

        if (
            self.known_bad_snapshot_sha256
            == self.candidate_snapshot_sha256
        ):
            raise ContractError(
                "known-bad and candidate snapshot digests must differ"
            )

        if (
            self.known_bad_execution_id
            == self.candidate_execution_id
        ):
            raise ContractError(
                "known-bad and candidate execution IDs must differ"
            )

        if (
            self.known_bad_evaluation_id
            == self.candidate_evaluation_id
        ):
            raise ContractError(
                "known-bad and candidate evaluation IDs must differ"
            )

        if self.outcome in (
            RepairContrastOutcome.REPAIR_DISCRIMINATING,
            RepairContrastOutcome.NOT_REPAIR_DISCRIMINATING,
            RepairContrastOutcome.INCONCLUSIVE,
        ) and not self.evidence_references:
            raise ContractError(
                f"{self.outcome.value} requires evidence references"
            )

    def canonical_payload(self) -> dict[str, object]:
        payload = {
            field.name: getattr(
                self,
                field.name,
            )
            for field in fields(self)
        }

        payload["outcome"] = self.outcome.value

        return {
            "record_type": "RepairContrastRecord",
            "schema_version": 1,
            **payload,
        }

    @property
    def contrast_sha256(self) -> str:
        return canonical_sha256(
            self.canonical_payload()
        )

    def validate_against(
        self,
        *,
        goal: GoalContract,
        known_bad_snapshot: SystemSnapshot,
        candidate_snapshot: SystemSnapshot,
        known_bad_execution: ExecutionRecord,
        known_bad_evaluation: EvaluationRecord,
        candidate_execution: ExecutionRecord,
        candidate_evaluation: EvaluationRecord,
    ) -> None:
        """Validate exact contrast lineage without resolving evidence."""

        for value, kind, name in (
            (
                goal,
                GoalContract,
                "goal",
            ),
            (
                known_bad_snapshot,
                SystemSnapshot,
                "known_bad_snapshot",
            ),
            (
                candidate_snapshot,
                SystemSnapshot,
                "candidate_snapshot",
            ),
            (
                known_bad_execution,
                ExecutionRecord,
                "known_bad_execution",
            ),
            (
                known_bad_evaluation,
                EvaluationRecord,
                "known_bad_evaluation",
            ),
            (
                candidate_execution,
                ExecutionRecord,
                "candidate_execution",
            ),
            (
                candidate_evaluation,
                EvaluationRecord,
                "candidate_evaluation",
            ),
        ):
            _require_type(
                value,
                kind,
                name,
            )

            _require_scope(
                self,
                value,
                name,
            )

        for actual, expected, name in (
            (
                known_bad_snapshot.system_id,
                goal.system_id,
                "known_bad_snapshot.system_id",
            ),
            (
                candidate_snapshot.system_id,
                goal.system_id,
                "candidate_snapshot.system_id",
            ),
            (
                known_bad_execution.runner_id,
                candidate_execution.runner_id,
                "candidate_execution.runner_id",
            ),
            (
                known_bad_execution.runner_version,
                candidate_execution.runner_version,
                "candidate_execution.runner_version",
            ),
        ):
            _require_equal(
                actual,
                expected,
                name,
            )

        comparison_case_binding = (
            f"{self.comparison_case_reference}"
            f"#sha256={self.comparison_case_sha256}"
        )

        if (
            comparison_case_binding
            not in known_bad_execution.input_references
        ):
            raise ContractError(
                "known-bad execution must bind the registered "
                "comparison case"
            )

        if (
            comparison_case_binding
            not in candidate_execution.input_references
        ):
            raise ContractError(
                "candidate execution must bind the registered "
                "comparison case"
            )

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
                self.known_bad_snapshot_id,
                known_bad_snapshot.snapshot_id,
                "known_bad_snapshot_id",
            ),
            (
                self.known_bad_snapshot_sha256,
                known_bad_snapshot.snapshot_sha256,
                "known_bad_snapshot_sha256",
            ),
            (
                self.candidate_snapshot_id,
                candidate_snapshot.snapshot_id,
                "candidate_snapshot_id",
            ),
            (
                self.candidate_snapshot_sha256,
                candidate_snapshot.snapshot_sha256,
                "candidate_snapshot_sha256",
            ),
            (
                self.known_bad_execution_id,
                known_bad_execution.execution_id,
                "known_bad_execution_id",
            ),
            (
                self.known_bad_execution_sha256,
                known_bad_execution.execution_sha256,
                "known_bad_execution_sha256",
            ),
            (
                self.known_bad_evaluation_id,
                known_bad_evaluation.evaluation_id,
                "known_bad_evaluation_id",
            ),
            (
                self.known_bad_evaluation_sha256,
                known_bad_evaluation.evaluation_sha256,
                "known_bad_evaluation_sha256",
            ),
            (
                self.candidate_execution_id,
                candidate_execution.execution_id,
                "candidate_execution_id",
            ),
            (
                self.candidate_execution_sha256,
                candidate_execution.execution_sha256,
                "candidate_execution_sha256",
            ),
            (
                self.candidate_evaluation_id,
                candidate_evaluation.evaluation_id,
                "candidate_evaluation_id",
            ),
            (
                self.candidate_evaluation_sha256,
                candidate_evaluation.evaluation_sha256,
                "candidate_evaluation_sha256",
            ),
            (
                known_bad_execution.system_snapshot_id,
                known_bad_snapshot.snapshot_id,
                "known_bad_execution.system_snapshot_id",
            ),
            (
                known_bad_execution.system_snapshot_sha256,
                known_bad_snapshot.snapshot_sha256,
                "known_bad_execution.system_snapshot_sha256",
            ),
            (
                candidate_execution.system_snapshot_id,
                candidate_snapshot.snapshot_id,
                "candidate_execution.system_snapshot_id",
            ),
            (
                candidate_execution.system_snapshot_sha256,
                candidate_snapshot.snapshot_sha256,
                "candidate_execution.system_snapshot_sha256",
            ),
        ):
            _require_equal(
                actual,
                expected,
                name,
            )

        known_bad_evaluation.validate_against(
            goal=goal,
            execution=known_bad_execution,
        )

        candidate_evaluation.validate_against(
            goal=goal,
            execution=candidate_execution,
        )

        for actual, expected, name in (
            (
                known_bad_evaluation.evaluator_id,
                candidate_evaluation.evaluator_id,
                "candidate_evaluation.evaluator_id",
            ),
            (
                known_bad_evaluation.evaluator_version,
                candidate_evaluation.evaluator_version,
                "candidate_evaluation.evaluator_version",
            ),
            (
                known_bad_evaluation.protocol_reference,
                candidate_evaluation.protocol_reference,
                "candidate_evaluation.protocol_reference",
            ),
            (
                known_bad_evaluation.protocol_sha256,
                candidate_evaluation.protocol_sha256,
                "candidate_evaluation.protocol_sha256",
            ),
        ):
            _require_equal(
                actual,
                expected,
                name,
            )

        expected_outcome = _expected_contrast_outcome(
            known_bad_evaluation.outcome,
            candidate_evaluation.outcome,
        )

        if self.outcome is not expected_outcome:
            raise ContractError(
                "repair contrast outcome does not match "
                "the supplied evaluation pair"
            )


__all__ = [
    "RepairContrastOutcome",
    "RepairContrastRecord",
]

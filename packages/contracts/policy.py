"""Inert contract for governed candidate-eligibility decisions.

The record validates structure and explicit lineage. It does not resolve
policy inputs, prove policy correctness, grant authorization, execute or
deploy a candidate, mutate lifecycle state, or establish completion.
"""

from dataclasses import dataclass, fields
from enum import StrEnum

from .execution import (
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
from .verification import (
    VerificationOutcome,
    VerificationReport,
)


class CandidateEligibilityOutcome(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    INCONCLUSIVE = "INCONCLUSIVE"
    BLOCKED = "BLOCKED"
    INVALID = "INVALID"


@dataclass(frozen=True)
class CandidateEligibilityDecision:
    """Reviewer-reported policy decision for one exact candidate.

    ELIGIBLE means only that the supplied reviewer/policy reports the candidate
    eligible for a later governed action. It is not an authorization grant,
    deployment approval, execution permission, lifecycle transition, or claim
    that the candidate is universally safe or correct.

    An ELIGIBLE decision requires a VerificationReport whose outcome is
    VERIFIED. VERIFIED does not imply ELIGIBLE: a separately verified
    candidate may still violate change eligibility, budgets, capability
    prerequisites, compatibility requirements, or another governed policy.

    ELIGIBLE, INELIGIBLE and INCONCLUSIVE require evidence references.
    BLOCKED and INVALID may lack usable evidence.

    policy_input_references are opaque provenance references. Their presence
    does not establish that referenced policy inputs are valid or satisfied.
    """

    tenant_id: str
    project_id: str
    decision_id: str

    goal_contract_id: str
    goal_contract_sha256: str

    system_snapshot_id: str
    system_snapshot_sha256: str

    verification_id: str
    verification_sha256: str

    reviewer_id: str
    reviewer_version: str

    policy_reference: str
    policy_sha256: str

    outcome: CandidateEligibilityOutcome

    policy_input_references: tuple[str, ...]
    evidence_references: tuple[str, ...]

    rationale: str
    uncertainty: str
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        for field in (
            "tenant_id",
            "project_id",
            "decision_id",
            "goal_contract_id",
            "system_snapshot_id",
            "verification_id",
            "reviewer_id",
            "reviewer_version",
            "policy_reference",
            "rationale",
            "uncertainty",
        ):
            _require_text(getattr(self, field), field)

        for field in (
            "goal_contract_sha256",
            "system_snapshot_sha256",
            "verification_sha256",
            "policy_sha256",
        ):
            _require_sha256(getattr(self, field), field)

        for field in (
            "policy_input_references",
            "evidence_references",
            "limitations",
        ):
            _require_tuple(getattr(self, field), field)

        _require_type(
            self.outcome,
            CandidateEligibilityOutcome,
            "outcome",
        )

        if self.outcome in (
            CandidateEligibilityOutcome.ELIGIBLE,
            CandidateEligibilityOutcome.INELIGIBLE,
            CandidateEligibilityOutcome.INCONCLUSIVE,
        ) and not self.evidence_references:
            raise ContractError(
                f"{self.outcome.value} requires evidence references"
            )

    def canonical_payload(self) -> dict[str, object]:
        payload = {
            field.name: getattr(self, field.name)
            for field in fields(self)
        }

        payload["outcome"] = self.outcome.value

        return {
            "record_type": "CandidateEligibilityDecision",
            "schema_version": 1,
            **payload,
        }

    @property
    def eligibility_sha256(self) -> str:
        return canonical_sha256(self.canonical_payload())

    def validate_against(
        self,
        *,
        goal: GoalContract,
        snapshot: SystemSnapshot,
        verification: VerificationReport,
    ) -> None:
        """Validate supplied lineage, not the truth of the policy decision.

        VerificationReport.validate_against remains responsible for validating
        the complete execution/evaluation verification lineage. This method
        binds the already-produced report to the same frozen goal and exact
        candidate and checks the reviewer version frozen by GoalContract.

        It deliberately does not interpret GoalContract.eligible_changes,
        capability authorization_prerequisites, policy_input_references,
        evidence references, or external policy semantics.
        """

        for value, kind, name in (
            (goal, GoalContract, "goal"),
            (snapshot, SystemSnapshot, "snapshot"),
            (
                verification,
                VerificationReport,
                "verification",
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
                self.verification_id,
                verification.verification_id,
                "verification_id",
            ),
            (
                self.verification_sha256,
                verification.verification_sha256,
                "verification_sha256",
            ),
            (
                verification.goal_contract_id,
                goal.contract_id,
                "verification.goal_contract_id",
            ),
            (
                verification.goal_contract_sha256,
                goal.contract_sha256,
                "verification.goal_contract_sha256",
            ),
            (
                verification.system_snapshot_id,
                snapshot.snapshot_id,
                "verification.system_snapshot_id",
            ),
            (
                verification.system_snapshot_sha256,
                snapshot.snapshot_sha256,
                "verification.system_snapshot_sha256",
            ),
            (
                goal.system_id,
                snapshot.system_id,
                "snapshot.system_id",
            ),
            (
                self.reviewer_version,
                goal.reviewer_version,
                "reviewer_version",
            ),
        ):
            _require_equal(actual, expected, name)

        if (
            self.outcome
            is CandidateEligibilityOutcome.ELIGIBLE
            and verification.outcome
            is not VerificationOutcome.VERIFIED
        ):
            raise ContractError(
                "ELIGIBLE requires a VERIFIED verification report"
            )


__all__ = [
    "CandidateEligibilityOutcome",
    "CandidateEligibilityDecision",
]

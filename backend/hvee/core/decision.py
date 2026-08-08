from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from hvee.core.contracts import HveeContractError


class DecisionVerdict(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"
    INVALID = "invalid"


class IntegrityAssessment(StrEnum):
    VALID = "valid"
    INVALID = "invalid"


class CriticalAssessment(StrEnum):
    CLEAR = "clear"
    VIOLATED = "violated"


class EvidenceAssessment(StrEnum):
    SUFFICIENT = "sufficient"
    INSUFFICIENT = "insufficient"


class ClaimAssessment(StrEnum):
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    UNRESOLVED = "unresolved"


class DecisionReason(StrEnum):
    INTEGRITY_INVALID = "integrity_invalid"
    CRITICAL_VIOLATION = "critical_violation"
    EVIDENCE_INSUFFICIENT = "evidence_insufficient"
    CLAIM_CONTRADICTED = "claim_contradicted"
    CLAIM_UNRESOLVED = "claim_unresolved"
    CLAIM_SUPPORTED = "claim_supported"


@dataclass(frozen=True, slots=True)
class DecisionInputs:
    """
    Domain-neutral inputs to one HVEE decision.

    Domain packs are responsible for translating their observations,
    requirements, and evidence into these assessments. The kernel owns
    only deterministic verdict precedence.
    """

    integrity: IntegrityAssessment
    critical: CriticalAssessment
    evidence: EvidenceAssessment
    claim: ClaimAssessment

    def __post_init__(self) -> None:
        checks = (
            (
                "integrity",
                self.integrity,
                IntegrityAssessment,
            ),
            (
                "critical",
                self.critical,
                CriticalAssessment,
            ),
            (
                "evidence",
                self.evidence,
                EvidenceAssessment,
            ),
            (
                "claim",
                self.claim,
                ClaimAssessment,
            ),
        )

        for name, value, expected_type in checks:
            if not isinstance(
                value,
                expected_type,
            ):
                raise HveeContractError(
                    f"{name} assessment must be "
                    f"{expected_type.__name__}"
                )


@dataclass(frozen=True, slots=True)
class DecisionResult:
    verdict: DecisionVerdict
    reason: DecisionReason

    def __post_init__(self) -> None:
        if not isinstance(
            self.verdict,
            DecisionVerdict,
        ):
            raise HveeContractError(
                "decision verdict must be a DecisionVerdict"
            )

        if not isinstance(
            self.reason,
            DecisionReason,
        ):
            raise HveeContractError(
                "decision reason must be a DecisionReason"
            )


def decide(
    inputs: DecisionInputs,
) -> DecisionResult:
    """
    Produce one deterministic HVEE verdict.

    Precedence is intentional:

    1. Invalid integrity -> INVALID.
    2. Critical violation -> FAIL.
    3. Insufficient evidence -> INCONCLUSIVE.
    4. Contradicted claim -> FAIL.
    5. Unresolved claim -> INCONCLUSIVE.
    6. Otherwise the supported claim -> PASS.

    A lower-priority condition never overrides a higher-priority one.
    """

    if not isinstance(
        inputs,
        DecisionInputs,
    ):
        raise HveeContractError(
            "decision inputs must be DecisionInputs"
        )

    if (
        inputs.integrity
        == IntegrityAssessment.INVALID
    ):
        return DecisionResult(
            verdict=DecisionVerdict.INVALID,
            reason=DecisionReason.INTEGRITY_INVALID,
        )

    if (
        inputs.critical
        == CriticalAssessment.VIOLATED
    ):
        return DecisionResult(
            verdict=DecisionVerdict.FAIL,
            reason=DecisionReason.CRITICAL_VIOLATION,
        )

    if (
        inputs.evidence
        == EvidenceAssessment.INSUFFICIENT
    ):
        return DecisionResult(
            verdict=DecisionVerdict.INCONCLUSIVE,
            reason=DecisionReason.EVIDENCE_INSUFFICIENT,
        )

    if (
        inputs.claim
        == ClaimAssessment.CONTRADICTED
    ):
        return DecisionResult(
            verdict=DecisionVerdict.FAIL,
            reason=DecisionReason.CLAIM_CONTRADICTED,
        )

    if (
        inputs.claim
        == ClaimAssessment.UNRESOLVED
    ):
        return DecisionResult(
            verdict=DecisionVerdict.INCONCLUSIVE,
            reason=DecisionReason.CLAIM_UNRESOLVED,
        )

    return DecisionResult(
        verdict=DecisionVerdict.PASS,
        reason=DecisionReason.CLAIM_SUPPORTED,
    )

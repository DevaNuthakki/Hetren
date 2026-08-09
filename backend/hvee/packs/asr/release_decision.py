from __future__ import annotations

from dataclasses import dataclass

from hvee.core.contracts import HveeContractError
from hvee.core.decision import (
    CriticalAssessment,
    DecisionInputs,
    DecisionResult,
    decide,
)
from hvee.packs.asr.matched_evidence import (
    ASRMatchedQualityCohorts,
)
from hvee.packs.asr.release_assurance import (
    ASRMatchedReleaseAssuranceResult,
    evaluate_asr_matched_release_assurance,
)
from hvee.packs.asr.release_assurance_policy import (
    ASRMatchedReleaseAssurancePolicyV1,
)


@dataclass(frozen=True, slots=True)
class ASRMatchedReleaseDecisionResult:
    """
    Universal HVEE decision for one matched ASR release comparison.

    Scientific ASR assurance is evaluated first. The resulting
    integrity/evidence/claim assessments are then passed unchanged
    into the domain-neutral HVEE decision kernel.

    v1 has no release-level critical-invariant rules, so critical is
    explicitly CLEAR rather than inferred or fabricated.
    """

    assurance: ASRMatchedReleaseAssuranceResult
    critical: CriticalAssessment
    decision: DecisionResult

    def __post_init__(self) -> None:
        if not isinstance(
            self.assurance,
            ASRMatchedReleaseAssuranceResult,
        ):
            raise HveeContractError(
                "ASR matched release decision requires "
                "ASRMatchedReleaseAssuranceResult"
            )

        if not isinstance(
            self.critical,
            CriticalAssessment,
        ):
            raise HveeContractError(
                "ASR matched release decision critical "
                "assessment must be CriticalAssessment"
            )

        if not isinstance(
            self.decision,
            DecisionResult,
        ):
            raise HveeContractError(
                "ASR matched release decision requires "
                "DecisionResult"
            )

        expected = decide(
            DecisionInputs(
                integrity=(
                    self.assurance.integrity
                ),
                critical=self.critical,
                evidence=(
                    self.assurance.evidence
                ),
                claim=self.assurance.claim,
            )
        )

        if self.decision != expected:
            raise HveeContractError(
                "ASR matched release decision does not "
                "match the universal decision kernel"
            )


def evaluate_asr_matched_release_decision(
    *,
    cohorts: ASRMatchedQualityCohorts,
    policy: ASRMatchedReleaseAssurancePolicyV1,
) -> ASRMatchedReleaseDecisionResult:
    """
    Produce one four-state HVEE matched ASR release decision.

    v1 decision flow:

        matched evidence
            ->
        statistical assurance
            ->
        universal HVEE decision kernel

    This function performs no persistence and does not use the legacy
    Phase-2 ReleaseReport threshold engine.
    """

    if not isinstance(
        cohorts,
        ASRMatchedQualityCohorts,
    ):
        raise HveeContractError(
            "ASR matched release decision requires "
            "ASRMatchedQualityCohorts"
        )

    if not isinstance(
        policy,
        ASRMatchedReleaseAssurancePolicyV1,
    ):
        raise HveeContractError(
            "ASR matched release decision requires "
            "ASRMatchedReleaseAssurancePolicyV1"
        )

    assurance = (
        evaluate_asr_matched_release_assurance(
            cohorts=cohorts,
            policy=policy,
        )
    )

    critical = CriticalAssessment.CLEAR

    decision = decide(
        DecisionInputs(
            integrity=assurance.integrity,
            critical=critical,
            evidence=assurance.evidence,
            claim=assurance.claim,
        )
    )

    return ASRMatchedReleaseDecisionResult(
        assurance=assurance,
        critical=critical,
        decision=decision,
    )

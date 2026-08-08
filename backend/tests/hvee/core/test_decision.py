import itertools

import pytest

from hvee.core.contracts import HveeContractError
from hvee.core.decision import (
    ClaimAssessment,
    CriticalAssessment,
    DecisionInputs,
    DecisionReason,
    DecisionResult,
    DecisionVerdict,
    EvidenceAssessment,
    IntegrityAssessment,
    decide,
)


def inputs(
    *,
    integrity: IntegrityAssessment = (
        IntegrityAssessment.VALID
    ),
    critical: CriticalAssessment = (
        CriticalAssessment.CLEAR
    ),
    evidence: EvidenceAssessment = (
        EvidenceAssessment.SUFFICIENT
    ),
    claim: ClaimAssessment = (
        ClaimAssessment.SUPPORTED
    ),
) -> DecisionInputs:
    return DecisionInputs(
        integrity=integrity,
        critical=critical,
        evidence=evidence,
        claim=claim,
    )


def test_supported_claim_with_valid_sufficient_evidence_passes():
    result = decide(inputs())

    assert result == DecisionResult(
        verdict=DecisionVerdict.PASS,
        reason=DecisionReason.CLAIM_SUPPORTED,
    )


def test_invalid_integrity_produces_invalid():
    result = decide(
        inputs(
            integrity=(
                IntegrityAssessment.INVALID
            )
        )
    )

    assert result.verdict == DecisionVerdict.INVALID
    assert (
        result.reason
        == DecisionReason.INTEGRITY_INVALID
    )


def test_critical_violation_produces_fail():
    result = decide(
        inputs(
            critical=(
                CriticalAssessment.VIOLATED
            )
        )
    )

    assert result.verdict == DecisionVerdict.FAIL
    assert (
        result.reason
        == DecisionReason.CRITICAL_VIOLATION
    )


def test_insufficient_evidence_is_inconclusive():
    result = decide(
        inputs(
            evidence=(
                EvidenceAssessment.INSUFFICIENT
            )
        )
    )

    assert (
        result.verdict
        == DecisionVerdict.INCONCLUSIVE
    )
    assert (
        result.reason
        == DecisionReason.EVIDENCE_INSUFFICIENT
    )


def test_contradicted_claim_fails():
    result = decide(
        inputs(
            claim=ClaimAssessment.CONTRADICTED
        )
    )

    assert result.verdict == DecisionVerdict.FAIL
    assert (
        result.reason
        == DecisionReason.CLAIM_CONTRADICTED
    )


def test_unresolved_claim_is_inconclusive():
    result = decide(
        inputs(
            claim=ClaimAssessment.UNRESOLVED
        )
    )

    assert (
        result.verdict
        == DecisionVerdict.INCONCLUSIVE
    )
    assert (
        result.reason
        == DecisionReason.CLAIM_UNRESOLVED
    )


@pytest.mark.parametrize(
    ("critical", "evidence", "claim"),
    itertools.product(
        CriticalAssessment,
        EvidenceAssessment,
        ClaimAssessment,
    ),
)
def test_invalid_integrity_has_absolute_precedence(
    critical,
    evidence,
    claim,
):
    result = decide(
        inputs(
            integrity=IntegrityAssessment.INVALID,
            critical=critical,
            evidence=evidence,
            claim=claim,
        )
    )

    assert result == DecisionResult(
        verdict=DecisionVerdict.INVALID,
        reason=DecisionReason.INTEGRITY_INVALID,
    )


@pytest.mark.parametrize(
    ("evidence", "claim"),
    itertools.product(
        EvidenceAssessment,
        ClaimAssessment,
    ),
)
def test_critical_violation_precedes_evidence_and_claim(
    evidence,
    claim,
):
    result = decide(
        inputs(
            critical=CriticalAssessment.VIOLATED,
            evidence=evidence,
            claim=claim,
        )
    )

    assert result == DecisionResult(
        verdict=DecisionVerdict.FAIL,
        reason=DecisionReason.CRITICAL_VIOLATION,
    )


@pytest.mark.parametrize(
    "claim",
    ClaimAssessment,
)
def test_insufficient_evidence_precedes_claim(
    claim,
):
    result = decide(
        inputs(
            evidence=EvidenceAssessment.INSUFFICIENT,
            claim=claim,
        )
    )

    assert result == DecisionResult(
        verdict=DecisionVerdict.INCONCLUSIVE,
        reason=DecisionReason.EVIDENCE_INSUFFICIENT,
    )


def test_string_values_do_not_bypass_enum_contract():
    with pytest.raises(
        HveeContractError,
        match="integrity assessment",
    ):
        DecisionInputs(
            integrity="valid",
            critical=CriticalAssessment.CLEAR,
            evidence=EvidenceAssessment.SUFFICIENT,
            claim=ClaimAssessment.SUPPORTED,
        )


def test_decide_rejects_non_contract_input():
    with pytest.raises(
        HveeContractError,
        match="DecisionInputs",
    ):
        decide(object())


def test_result_contract_rejects_raw_strings():
    with pytest.raises(
        HveeContractError,
        match="decision verdict",
    ):
        DecisionResult(
            verdict="pass",
            reason=DecisionReason.CLAIM_SUPPORTED,
        )

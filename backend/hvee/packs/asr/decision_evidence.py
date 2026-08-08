from __future__ import annotations

from hvee.core.contracts import HveeContractError
from hvee.core.decision_evidence import (
    DecisionEvidenceBundle,
    build_decision_evidence_bundle,
)
from hvee.core.evidence_readiness import (
    EvidenceReadinessResult,
    EvidenceTarget,
    InvalidEvidence,
    ObservationRequirement,
    UnavailableEvidence,
)
from hvee.core.observation_evidence import (
    ObservationEvidenceRecord,
)
from hvee.packs.asr.decision_evaluation import (
    ASRRuleFinding,
    evaluate_asr_test_case_decision,
)
from hvee.packs.asr.decision_policy import (
    ASRTestCaseDecisionPolicyV1,
)


def build_asr_policy_snapshot(
    policy: ASRTestCaseDecisionPolicyV1,
) -> dict[str, object]:
    if not isinstance(
        policy,
        ASRTestCaseDecisionPolicyV1,
    ):
        raise HveeContractError(
            "ASR decision evidence requires "
            "ASRTestCaseDecisionPolicyV1"
        )

    return {
        "max_normalized_wer": (
            None
            if policy.max_normalized_wer is None
            else float(policy.max_normalized_wer)
        ),
        "max_normalized_cer": (
            None
            if policy.max_normalized_cer is None
            else float(policy.max_normalized_cer)
        ),
        "missing_output": (
            policy.missing_output.value
        ),
        "unexpected_output": (
            policy.unexpected_output.value
        ),
        "numeric_sequence_match": (
            policy.numeric_sequence_match.value
        ),
    }


def _requirement_snapshot(
    requirement: ObservationRequirement,
) -> dict[str, object]:
    if not isinstance(
        requirement,
        ObservationRequirement,
    ):
        raise HveeContractError(
            "readiness requirement must be "
            "an ObservationRequirement"
        )

    return {
        "metric": {
            "key": requirement.metric_key,
            "version": requirement.metric_version,
        },
        "evaluator": {
            "key": requirement.evaluator_key,
            "version": requirement.evaluator_version,
        },
        "evaluation_type": (
            requirement.evaluation_type
        ),
        "scope": requirement.scope,
        "value_type": (
            requirement.value_type.value
        ),
    }


def _unavailable_snapshot(
    evidence: UnavailableEvidence,
) -> dict[str, object]:
    if not isinstance(
        evidence,
        UnavailableEvidence,
    ):
        raise HveeContractError(
            "unavailable readiness evidence has invalid type"
        )

    return {
        "requirement": _requirement_snapshot(
            evidence.requirement
        ),
        "status": evidence.status.value,
        "status_detail": evidence.status_detail,
    }


def _invalid_snapshot(
    evidence: InvalidEvidence,
) -> dict[str, object]:
    if not isinstance(
        evidence,
        InvalidEvidence,
    ):
        raise HveeContractError(
            "invalid readiness evidence has invalid type"
        )

    return {
        "requirement": _requirement_snapshot(
            evidence.requirement
        ),
        "status_detail": evidence.status_detail,
    }


def build_asr_readiness_snapshot(
    readiness: EvidenceReadinessResult,
) -> dict[str, object]:
    if not isinstance(
        readiness,
        EvidenceReadinessResult,
    ):
        raise HveeContractError(
            "ASR decision readiness must be "
            "an EvidenceReadinessResult"
        )

    return {
        "integrity": readiness.integrity.value,
        "evidence": readiness.evidence.value,
        "required_count": readiness.required_count,
        "usable_count": readiness.usable_count,
        "missing": [
            _requirement_snapshot(requirement)
            for requirement in readiness.missing
        ],
        "unavailable": [
            _unavailable_snapshot(item)
            for item in readiness.unavailable
        ],
        "invalid": [
            _invalid_snapshot(item)
            for item in readiness.invalid
        ],
        "duplicates": [
            _requirement_snapshot(requirement)
            for requirement in readiness.duplicates
        ],
    }


def build_asr_finding_snapshot(
    finding: ASRRuleFinding,
) -> dict[str, object]:
    if not isinstance(
        finding,
        ASRRuleFinding,
    ):
        raise HveeContractError(
            "ASR decision finding must be an ASRRuleFinding"
        )

    return {
        "rule": finding.rule.value,
        "disposition": finding.disposition.value,
        "outcome": finding.outcome.value,
        "observed_value": finding.observed_value,
        "limit": finding.limit,
    }


def build_asr_test_case_decision_evidence(
    *,
    policy: ASRTestCaseDecisionPolicyV1,
    records: list[ObservationEvidenceRecord]
    | tuple[ObservationEvidenceRecord, ...],
    target: EvidenceTarget,
    result_provenance_id: int,
    provenance_sha256: str,
    observation_evidence_sha256: str,
) -> DecisionEvidenceBundle:
    """
    Evaluate and serialize one ASR test-case decision.

    The adapter intentionally evaluates the supplied observations using
    the supplied policy itself. This prevents a precomputed evaluation
    produced under one policy configuration from being rebound to a
    different policy snapshot.
    """

    if not isinstance(
        policy,
        ASRTestCaseDecisionPolicyV1,
    ):
        raise HveeContractError(
            "ASR decision evidence requires "
            "ASRTestCaseDecisionPolicyV1"
        )

    if not isinstance(
        target,
        EvidenceTarget,
    ):
        raise HveeContractError(
            "ASR decision evidence target must be "
            "an EvidenceTarget"
        )

    if target.test_case_id is None:
        raise HveeContractError(
            "ASR test-case decision evidence requires "
            "a test-case target"
        )

    evaluation = evaluate_asr_test_case_decision(
        records=records,
        policy=policy,
        target=target,
    )

    return build_decision_evidence_bundle(
        evaluation_type="asr",
        target=evaluation.target,
        policy_key=policy.key,
        policy_version=policy.version,
        policy_snapshot=(
            build_asr_policy_snapshot(
                policy
            )
        ),
        result_provenance_id=(
            result_provenance_id
        ),
        provenance_sha256=(
            provenance_sha256
        ),
        observation_evidence_sha256=(
            observation_evidence_sha256
        ),
        integrity=evaluation.integrity,
        evidence=evaluation.readiness.evidence,
        critical=evaluation.critical,
        claim=evaluation.claim,
        decision=evaluation.decision,
        readiness_snapshot=(
            build_asr_readiness_snapshot(
                evaluation.readiness
            )
        ),
        findings=[
            build_asr_finding_snapshot(
                finding
            )
            for finding in evaluation.findings
        ],
    )

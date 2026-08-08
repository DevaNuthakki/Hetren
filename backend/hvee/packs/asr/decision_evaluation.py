from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from hvee.core.contracts import (
    HveeContractError,
    ObservationStatus,
)
from hvee.core.decision import (
    ClaimAssessment,
    CriticalAssessment,
    DecisionInputs,
    DecisionResult,
    EvidenceAssessment,
    IntegrityAssessment,
    decide,
)
from hvee.core.evidence_readiness import (
    EvidenceReadinessResult,
    EvidenceTarget,
    ObservationRequirement,
    assess_evidence_readiness,
)
from hvee.core.observation_evidence import (
    ObservationEvidenceRecord,
)
from hvee.packs.asr.decision_policy import (
    ASRRuleDisposition,
    ASRTestCaseDecisionPolicyV1,
    build_asr_test_case_requirements,
)
from hvee.packs.asr.normalized_evaluation import (
    NORMALIZED_CER_METRIC,
    NORMALIZED_WER_METRIC,
)
from hvee.packs.asr.numeric_preservation import (
    NUMERIC_TOKEN_SEQUENCE_MATCH_METRIC,
    REFERENCE_NUMERIC_TOKEN_COUNT_METRIC,
)
from hvee.packs.asr.transcript_integrity import (
    MISSING_OUTPUT_METRIC,
    UNEXPECTED_OUTPUT_METRIC,
)


class ASRDecisionRule(StrEnum):
    MAX_NORMALIZED_WER = "max_normalized_wer"
    MAX_NORMALIZED_CER = "max_normalized_cer"
    MISSING_OUTPUT = "missing_output"
    UNEXPECTED_OUTPUT = "unexpected_output"
    NUMERIC_SEQUENCE_MATCH = "numeric_sequence_match"


class ASRRuleOutcome(StrEnum):
    SATISFIED = "satisfied"
    VIOLATED = "violated"
    UNRESOLVED = "unresolved"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class ASRRuleFinding:
    rule: ASRDecisionRule
    disposition: ASRRuleDisposition
    outcome: ASRRuleOutcome
    observed_value: float | int | bool | None = None
    limit: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(
            self.rule,
            ASRDecisionRule,
        ):
            raise HveeContractError(
                "ASR rule finding requires "
                "an ASRDecisionRule"
            )

        if not isinstance(
            self.disposition,
            ASRRuleDisposition,
        ):
            raise HveeContractError(
                "ASR rule finding requires "
                "an ASRRuleDisposition"
            )

        if not isinstance(
            self.outcome,
            ASRRuleOutcome,
        ):
            raise HveeContractError(
                "ASR rule finding requires "
                "an ASRRuleOutcome"
            )


@dataclass(frozen=True, slots=True)
class ASRTestCaseDecisionEvaluation:
    policy_key: str
    policy_version: str
    target: EvidenceTarget
    readiness: EvidenceReadinessResult
    integrity: IntegrityAssessment
    critical: CriticalAssessment
    claim: ClaimAssessment
    decision: DecisionResult
    findings: tuple[ASRRuleFinding, ...]


def _matches_requirement_and_target(
    *,
    record: ObservationEvidenceRecord,
    requirement: ObservationRequirement,
    target: EvidenceTarget,
) -> bool:
    if (
        record.evaluation_type
        != requirement.evaluation_type
        or record.scope
        != requirement.scope
        or record.metric_key
        != requirement.metric_key
        or record.metric_version
        != requirement.metric_version
        or record.evaluator_key
        != requirement.evaluator_key
        or record.evaluator_version
        != requirement.evaluator_version
        or record.evaluation_run_id
        != target.evaluation_run_id
    ):
        return False

    if requirement.scope == "run":
        return record.test_case_id is None

    return (
        target.test_case_id is not None
        and record.test_case_id
        == target.test_case_id
    )


def _successful_record(
    *,
    records: list[ObservationEvidenceRecord]
    | tuple[ObservationEvidenceRecord, ...],
    requirement: ObservationRequirement,
    target: EvidenceTarget,
) -> ObservationEvidenceRecord | None:
    matches = [
        record
        for record in records
        if _matches_requirement_and_target(
            record=record,
            requirement=requirement,
            target=target,
        )
    ]

    if len(matches) != 1:
        return None

    record = matches[0]

    if record.status != ObservationStatus.SUCCESS:
        return None

    return record


def _requirement_by_metric(
    *,
    requirements: tuple[
        ObservationRequirement,
        ...,
    ],
    metric_key: str,
) -> ObservationRequirement:
    matches = [
        requirement
        for requirement in requirements
        if requirement.metric_key == metric_key
    ]

    if len(matches) != 1:
        raise HveeContractError(
            "ASR decision policy produced an invalid "
            "metric requirement set"
        )

    return matches[0]


def _threshold_finding(
    *,
    rule: ASRDecisionRule,
    metric_key: str,
    limit: float,
    records: list[ObservationEvidenceRecord]
    | tuple[ObservationEvidenceRecord, ...],
    requirements: tuple[
        ObservationRequirement,
        ...,
    ],
    target: EvidenceTarget,
) -> ASRRuleFinding:
    requirement = _requirement_by_metric(
        requirements=requirements,
        metric_key=metric_key,
    )

    record = _successful_record(
        records=records,
        requirement=requirement,
        target=target,
    )

    if record is None:
        return ASRRuleFinding(
            rule=rule,
            disposition=ASRRuleDisposition.CLAIM,
            outcome=ASRRuleOutcome.UNRESOLVED,
            limit=float(limit),
        )

    observed = float(record.value)

    if observed < 0:
        return ASRRuleFinding(
            rule=rule,
            disposition=ASRRuleDisposition.CLAIM,
            outcome=ASRRuleOutcome.INVALID,
            observed_value=observed,
            limit=float(limit),
        )

    return ASRRuleFinding(
        rule=rule,
        disposition=ASRRuleDisposition.CLAIM,
        outcome=(
            ASRRuleOutcome.VIOLATED
            if observed > float(limit)
            else ASRRuleOutcome.SATISFIED
        ),
        observed_value=observed,
        limit=float(limit),
    )


def _boolean_violation_finding(
    *,
    rule: ASRDecisionRule,
    metric_key: str,
    disposition: ASRRuleDisposition,
    records: list[ObservationEvidenceRecord]
    | tuple[ObservationEvidenceRecord, ...],
    requirements: tuple[
        ObservationRequirement,
        ...,
    ],
    target: EvidenceTarget,
) -> ASRRuleFinding:
    requirement = _requirement_by_metric(
        requirements=requirements,
        metric_key=metric_key,
    )

    record = _successful_record(
        records=records,
        requirement=requirement,
        target=target,
    )

    if record is None:
        return ASRRuleFinding(
            rule=rule,
            disposition=disposition,
            outcome=ASRRuleOutcome.UNRESOLVED,
        )

    observed = bool(record.value)

    return ASRRuleFinding(
        rule=rule,
        disposition=disposition,
        outcome=(
            ASRRuleOutcome.VIOLATED
            if observed
            else ASRRuleOutcome.SATISFIED
        ),
        observed_value=observed,
    )


def _numeric_sequence_finding(
    *,
    disposition: ASRRuleDisposition,
    records: list[ObservationEvidenceRecord]
    | tuple[ObservationEvidenceRecord, ...],
    requirements: tuple[
        ObservationRequirement,
        ...,
    ],
    target: EvidenceTarget,
) -> ASRRuleFinding:
    sequence_requirement = _requirement_by_metric(
        requirements=requirements,
        metric_key=(
            NUMERIC_TOKEN_SEQUENCE_MATCH_METRIC.key
        ),
    )
    count_requirement = _requirement_by_metric(
        requirements=requirements,
        metric_key=(
            REFERENCE_NUMERIC_TOKEN_COUNT_METRIC.key
        ),
    )

    sequence_record = _successful_record(
        records=records,
        requirement=sequence_requirement,
        target=target,
    )
    count_record = _successful_record(
        records=records,
        requirement=count_requirement,
        target=target,
    )

    # If a successful reference-count observation exists, validate its
    # semantic domain before interpreting any sequence result. Invalid
    # domain evidence must outrank a policy violation.
    reference_count: int | None = None

    if count_record is not None:
        reference_count = int(
            count_record.value
        )

        if reference_count < 0:
            return ASRRuleFinding(
                rule=(
                    ASRDecisionRule.NUMERIC_SEQUENCE_MATCH
                ),
                disposition=disposition,
                outcome=ASRRuleOutcome.INVALID,
                observed_value=reference_count,
            )

    if sequence_record is None:
        return ASRRuleFinding(
            rule=ASRDecisionRule.NUMERIC_SEQUENCE_MATCH,
            disposition=disposition,
            outcome=ASRRuleOutcome.UNRESOLVED,
        )

    sequence_match = bool(
        sequence_record.value
    )

    # A known mismatch is decisive even if the supporting reference
    # count is unavailable. This preserves critical-rule precedence
    # over unrelated evidence insufficiency.
    if not sequence_match:
        return ASRRuleFinding(
            rule=ASRDecisionRule.NUMERIC_SEQUENCE_MATCH,
            disposition=disposition,
            outcome=ASRRuleOutcome.VIOLATED,
            observed_value=False,
        )

    # A matching empty/empty numeric sequence does not demonstrate
    # numeric preservation. Without a usable positive reference count,
    # the rule remains unresolved rather than producing a false PASS.
    if (
        reference_count is None
        or reference_count == 0
    ):
        return ASRRuleFinding(
            rule=ASRDecisionRule.NUMERIC_SEQUENCE_MATCH,
            disposition=disposition,
            outcome=ASRRuleOutcome.UNRESOLVED,
            observed_value=True,
        )

    return ASRRuleFinding(
        rule=ASRDecisionRule.NUMERIC_SEQUENCE_MATCH,
        disposition=disposition,
        outcome=ASRRuleOutcome.SATISFIED,
        observed_value=True,
    )


def evaluate_asr_test_case_decision(
    *,
    records: list[ObservationEvidenceRecord]
    | tuple[ObservationEvidenceRecord, ...],
    policy: ASRTestCaseDecisionPolicyV1,
    target: EvidenceTarget,
) -> ASRTestCaseDecisionEvaluation:
    """
    Evaluate one ASR test-case policy using bound HVEE observations.

    Evidence integrity has absolute precedence. With valid but
    incomplete evidence, available critical violations may still
    produce FAIL; ordinary claim contradictions remain subordinate to
    evidence insufficiency through the universal decision kernel.
    """

    if not isinstance(
        policy,
        ASRTestCaseDecisionPolicyV1,
    ):
        raise HveeContractError(
            "ASR decision policy must be "
            "ASRTestCaseDecisionPolicyV1"
        )

    requirements = (
        build_asr_test_case_requirements(
            policy
        )
    )

    readiness = assess_evidence_readiness(
        records=records,
        requirements=requirements,
        target=target,
    )

    if (
        readiness.integrity
        == IntegrityAssessment.INVALID
    ):
        critical = CriticalAssessment.CLEAR
        claim = ClaimAssessment.UNRESOLVED

        decision = decide(
            DecisionInputs(
                integrity=IntegrityAssessment.INVALID,
                critical=critical,
                evidence=readiness.evidence,
                claim=claim,
            )
        )

        return ASRTestCaseDecisionEvaluation(
            policy_key=policy.key,
            policy_version=policy.version,
            target=target,
            readiness=readiness,
            integrity=IntegrityAssessment.INVALID,
            critical=critical,
            claim=claim,
            decision=decision,
            findings=(),
        )

    findings: list[
        ASRRuleFinding
    ] = []

    if policy.max_normalized_wer is not None:
        findings.append(
            _threshold_finding(
                rule=ASRDecisionRule.MAX_NORMALIZED_WER,
                metric_key=NORMALIZED_WER_METRIC.key,
                limit=policy.max_normalized_wer,
                records=records,
                requirements=requirements,
                target=target,
            )
        )

    if policy.max_normalized_cer is not None:
        findings.append(
            _threshold_finding(
                rule=ASRDecisionRule.MAX_NORMALIZED_CER,
                metric_key=NORMALIZED_CER_METRIC.key,
                limit=policy.max_normalized_cer,
                records=records,
                requirements=requirements,
                target=target,
            )
        )

    if (
        policy.missing_output
        != ASRRuleDisposition.DISABLED
    ):
        findings.append(
            _boolean_violation_finding(
                rule=ASRDecisionRule.MISSING_OUTPUT,
                metric_key=MISSING_OUTPUT_METRIC.key,
                disposition=policy.missing_output,
                records=records,
                requirements=requirements,
                target=target,
            )
        )

    if (
        policy.unexpected_output
        != ASRRuleDisposition.DISABLED
    ):
        findings.append(
            _boolean_violation_finding(
                rule=ASRDecisionRule.UNEXPECTED_OUTPUT,
                metric_key=UNEXPECTED_OUTPUT_METRIC.key,
                disposition=policy.unexpected_output,
                records=records,
                requirements=requirements,
                target=target,
            )
        )

    if (
        policy.numeric_sequence_match
        != ASRRuleDisposition.DISABLED
    ):
        findings.append(
            _numeric_sequence_finding(
                disposition=(
                    policy.numeric_sequence_match
                ),
                records=records,
                requirements=requirements,
                target=target,
            )
        )

    domain_invalid = any(
        finding.outcome
        == ASRRuleOutcome.INVALID
        for finding in findings
    )

    effective_integrity = (
        IntegrityAssessment.INVALID
        if domain_invalid
        else readiness.integrity
    )

    critical = (
        CriticalAssessment.VIOLATED
        if any(
            finding.disposition
            == ASRRuleDisposition.CRITICAL
            and finding.outcome
            == ASRRuleOutcome.VIOLATED
            for finding in findings
        )
        else CriticalAssessment.CLEAR
    )

    if any(
        finding.outcome
        == ASRRuleOutcome.INVALID
        for finding in findings
    ):
        claim = ClaimAssessment.UNRESOLVED
    elif any(
        finding.disposition
        == ASRRuleDisposition.CLAIM
        and finding.outcome
        == ASRRuleOutcome.VIOLATED
        for finding in findings
    ):
        claim = ClaimAssessment.CONTRADICTED
    elif any(
        finding.outcome
        == ASRRuleOutcome.UNRESOLVED
        for finding in findings
    ):
        claim = ClaimAssessment.UNRESOLVED
    else:
        claim = ClaimAssessment.SUPPORTED

    decision = decide(
        DecisionInputs(
            integrity=effective_integrity,
            critical=critical,
            evidence=readiness.evidence,
            claim=claim,
        )
    )

    return ASRTestCaseDecisionEvaluation(
        policy_key=policy.key,
        policy_version=policy.version,
        target=target,
        readiness=readiness,
        integrity=effective_integrity,
        critical=critical,
        claim=claim,
        decision=decision,
        findings=tuple(findings),
    )

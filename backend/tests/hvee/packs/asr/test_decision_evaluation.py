from hvee.core.contracts import (
    ObservationStatus,
)
from hvee.core.decision import (
    ClaimAssessment,
    CriticalAssessment,
    DecisionReason,
    DecisionVerdict,
    EvidenceAssessment,
    IntegrityAssessment,
)
from hvee.core.evidence_readiness import (
    EvidenceTarget,
)
from hvee.core.observation_evidence import (
    ObservationEvidenceRecord,
)
from hvee.packs.asr.decision_evaluation import (
    ASRDecisionRule,
    ASRRuleOutcome,
    evaluate_asr_test_case_decision,
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


TARGET = EvidenceTarget(
    evaluation_run_id=10,
    test_case_id=20,
)


_DEFAULT_VALUES = {
    NORMALIZED_WER_METRIC.key: 0.10,
    NORMALIZED_CER_METRIC.key: 0.05,
    MISSING_OUTPUT_METRIC.key: False,
    UNEXPECTED_OUTPUT_METRIC.key: False,
    REFERENCE_NUMERIC_TOKEN_COUNT_METRIC.key: 2,
    NUMERIC_TOKEN_SEQUENCE_MATCH_METRIC.key: True,
}


def records_for(
    policy,
    *,
    values=None,
    omitted=None,
    statuses=None,
    run_id=10,
    test_case_id=20,
):
    values = {
        **_DEFAULT_VALUES,
        **(values or {}),
    }
    omitted = set(omitted or ())
    statuses = statuses or {}

    records = []

    for requirement in (
        build_asr_test_case_requirements(
            policy
        )
    ):
        if requirement.metric_key in omitted:
            continue

        status = statuses.get(
            requirement.metric_key,
            ObservationStatus.SUCCESS,
        )

        if status == ObservationStatus.SUCCESS:
            value = values[
                requirement.metric_key
            ]
            detail = None
        else:
            value = None
            detail = "not usable"

        records.append(
            ObservationEvidenceRecord(
                metric_key=requirement.metric_key,
                metric_version=requirement.metric_version,
                evaluator_key=requirement.evaluator_key,
                evaluator_version=requirement.evaluator_version,
                evaluation_type=requirement.evaluation_type,
                scope=requirement.scope,
                evaluation_run_id=run_id,
                test_case_id=test_case_id,
                status=status,
                value_type=requirement.value_type,
                value=value,
                status_detail=detail,
            )
        )

    return records


def full_policy():
    return ASRTestCaseDecisionPolicyV1(
        max_normalized_wer=0.20,
        max_normalized_cer=0.10,
        missing_output=ASRRuleDisposition.CRITICAL,
        unexpected_output=ASRRuleDisposition.CLAIM,
        numeric_sequence_match=ASRRuleDisposition.CRITICAL,
    )


def test_all_satisfied_rules_pass():
    policy = full_policy()

    result = evaluate_asr_test_case_decision(
        records=records_for(policy),
        policy=policy,
        target=TARGET,
    )

    assert result.integrity == IntegrityAssessment.VALID
    assert result.readiness.evidence == EvidenceAssessment.SUFFICIENT
    assert result.critical == CriticalAssessment.CLEAR
    assert result.claim == ClaimAssessment.SUPPORTED
    assert result.decision.verdict == DecisionVerdict.PASS
    assert (
        result.decision.reason
        == DecisionReason.CLAIM_SUPPORTED
    )


def test_threshold_equality_is_supported():
    policy = ASRTestCaseDecisionPolicyV1(
        max_normalized_wer=0.20,
    )

    result = evaluate_asr_test_case_decision(
        records=records_for(
            policy,
            values={
                NORMALIZED_WER_METRIC.key: 0.20,
            },
        ),
        policy=policy,
        target=TARGET,
    )

    assert result.decision.verdict == DecisionVerdict.PASS


def test_wer_above_limit_contradicts_claim():
    policy = ASRTestCaseDecisionPolicyV1(
        max_normalized_wer=0.20,
    )

    result = evaluate_asr_test_case_decision(
        records=records_for(
            policy,
            values={
                NORMALIZED_WER_METRIC.key: 0.21,
            },
        ),
        policy=policy,
        target=TARGET,
    )

    assert result.claim == ClaimAssessment.CONTRADICTED
    assert result.decision.verdict == DecisionVerdict.FAIL
    assert (
        result.decision.reason
        == DecisionReason.CLAIM_CONTRADICTED
    )


def test_cer_above_limit_contradicts_claim():
    policy = ASRTestCaseDecisionPolicyV1(
        max_normalized_cer=0.10,
    )

    result = evaluate_asr_test_case_decision(
        records=records_for(
            policy,
            values={
                NORMALIZED_CER_METRIC.key: 0.11,
            },
        ),
        policy=policy,
        target=TARGET,
    )

    assert result.decision.verdict == DecisionVerdict.FAIL


def test_missing_output_as_claim_rule_fails_claim():
    policy = ASRTestCaseDecisionPolicyV1(
        missing_output=ASRRuleDisposition.CLAIM,
    )

    result = evaluate_asr_test_case_decision(
        records=records_for(
            policy,
            values={
                MISSING_OUTPUT_METRIC.key: True,
            },
        ),
        policy=policy,
        target=TARGET,
    )

    assert result.critical == CriticalAssessment.CLEAR
    assert result.claim == ClaimAssessment.CONTRADICTED
    assert result.decision.verdict == DecisionVerdict.FAIL


def test_missing_output_as_critical_rule_is_critical_failure():
    policy = ASRTestCaseDecisionPolicyV1(
        missing_output=ASRRuleDisposition.CRITICAL,
    )

    result = evaluate_asr_test_case_decision(
        records=records_for(
            policy,
            values={
                MISSING_OUTPUT_METRIC.key: True,
            },
        ),
        policy=policy,
        target=TARGET,
    )

    assert result.critical == CriticalAssessment.VIOLATED
    assert result.decision.verdict == DecisionVerdict.FAIL
    assert (
        result.decision.reason
        == DecisionReason.CRITICAL_VIOLATION
    )


def test_unexpected_output_can_be_critical():
    policy = ASRTestCaseDecisionPolicyV1(
        unexpected_output=ASRRuleDisposition.CRITICAL,
    )

    result = evaluate_asr_test_case_decision(
        records=records_for(
            policy,
            values={
                UNEXPECTED_OUTPUT_METRIC.key: True,
            },
        ),
        policy=policy,
        target=TARGET,
    )

    assert result.critical == CriticalAssessment.VIOLATED
    assert result.decision.verdict == DecisionVerdict.FAIL


def test_numeric_mismatch_as_claim_rule_contradicts_claim():
    policy = ASRTestCaseDecisionPolicyV1(
        numeric_sequence_match=ASRRuleDisposition.CLAIM,
    )

    result = evaluate_asr_test_case_decision(
        records=records_for(
            policy,
            values={
                NUMERIC_TOKEN_SEQUENCE_MATCH_METRIC.key: False,
            },
        ),
        policy=policy,
        target=TARGET,
    )

    assert result.claim == ClaimAssessment.CONTRADICTED
    assert result.decision.verdict == DecisionVerdict.FAIL


def test_numeric_mismatch_as_critical_rule_is_critical_failure():
    policy = ASRTestCaseDecisionPolicyV1(
        numeric_sequence_match=ASRRuleDisposition.CRITICAL,
    )

    result = evaluate_asr_test_case_decision(
        records=records_for(
            policy,
            values={
                NUMERIC_TOKEN_SEQUENCE_MATCH_METRIC.key: False,
            },
        ),
        policy=policy,
        target=TARGET,
    )

    assert result.critical == CriticalAssessment.VIOLATED
    assert result.decision.verdict == DecisionVerdict.FAIL


def test_numeric_rule_with_no_reference_numbers_is_inconclusive():
    policy = ASRTestCaseDecisionPolicyV1(
        numeric_sequence_match=ASRRuleDisposition.CRITICAL,
    )

    result = evaluate_asr_test_case_decision(
        records=records_for(
            policy,
            values={
                REFERENCE_NUMERIC_TOKEN_COUNT_METRIC.key: 0,
                NUMERIC_TOKEN_SEQUENCE_MATCH_METRIC.key: True,
            },
        ),
        policy=policy,
        target=TARGET,
    )

    assert result.readiness.evidence == EvidenceAssessment.SUFFICIENT
    assert result.claim == ClaimAssessment.UNRESOLVED
    assert (
        result.decision.verdict
        == DecisionVerdict.INCONCLUSIVE
    )
    assert (
        result.decision.reason
        == DecisionReason.CLAIM_UNRESOLVED
    )


def test_known_critical_mismatch_beats_missing_supporting_count():
    policy = ASRTestCaseDecisionPolicyV1(
        numeric_sequence_match=ASRRuleDisposition.CRITICAL,
    )

    result = evaluate_asr_test_case_decision(
        records=records_for(
            policy,
            values={
                NUMERIC_TOKEN_SEQUENCE_MATCH_METRIC.key: False,
            },
            omitted={
                REFERENCE_NUMERIC_TOKEN_COUNT_METRIC.key,
            },
        ),
        policy=policy,
        target=TARGET,
    )

    assert (
        result.readiness.evidence
        == EvidenceAssessment.INSUFFICIENT
    )
    assert result.critical == CriticalAssessment.VIOLATED
    assert result.decision.verdict == DecisionVerdict.FAIL
    assert (
        result.decision.reason
        == DecisionReason.CRITICAL_VIOLATION
    )


def test_known_critical_violation_beats_other_missing_evidence():
    policy = full_policy()

    result = evaluate_asr_test_case_decision(
        records=records_for(
            policy,
            values={
                MISSING_OUTPUT_METRIC.key: True,
            },
            omitted={
                NORMALIZED_WER_METRIC.key,
            },
        ),
        policy=policy,
        target=TARGET,
    )

    assert (
        result.readiness.evidence
        == EvidenceAssessment.INSUFFICIENT
    )
    assert result.critical == CriticalAssessment.VIOLATED
    assert result.decision.verdict == DecisionVerdict.FAIL


def test_claim_violation_does_not_beat_insufficient_evidence():
    policy = ASRTestCaseDecisionPolicyV1(
        max_normalized_wer=0.20,
        max_normalized_cer=0.10,
    )

    result = evaluate_asr_test_case_decision(
        records=records_for(
            policy,
            values={
                NORMALIZED_WER_METRIC.key: 0.50,
            },
            omitted={
                NORMALIZED_CER_METRIC.key,
            },
        ),
        policy=policy,
        target=TARGET,
    )

    assert result.claim == ClaimAssessment.CONTRADICTED
    assert (
        result.readiness.evidence
        == EvidenceAssessment.INSUFFICIENT
    )
    assert (
        result.decision.verdict
        == DecisionVerdict.INCONCLUSIVE
    )
    assert (
        result.decision.reason
        == DecisionReason.EVIDENCE_INSUFFICIENT
    )


def test_invalid_observation_has_absolute_precedence():
    policy = ASRTestCaseDecisionPolicyV1(
        missing_output=ASRRuleDisposition.CRITICAL,
    )

    records = records_for(
        policy,
        statuses={
            MISSING_OUTPUT_METRIC.key: (
                ObservationStatus.INVALID
            ),
        },
    )

    result = evaluate_asr_test_case_decision(
        records=records,
        policy=policy,
        target=TARGET,
    )

    assert result.integrity == IntegrityAssessment.INVALID
    assert result.decision.verdict == DecisionVerdict.INVALID
    assert (
        result.decision.reason
        == DecisionReason.INTEGRITY_INVALID
    )


def test_negative_wer_is_domain_invalid_not_a_pass():
    policy = ASRTestCaseDecisionPolicyV1(
        max_normalized_wer=0.20,
    )

    result = evaluate_asr_test_case_decision(
        records=records_for(
            policy,
            values={
                NORMALIZED_WER_METRIC.key: -0.01,
            },
        ),
        policy=policy,
        target=TARGET,
    )

    assert result.integrity == IntegrityAssessment.INVALID
    assert result.decision.verdict == DecisionVerdict.INVALID


def test_negative_numeric_reference_count_is_domain_invalid():
    policy = ASRTestCaseDecisionPolicyV1(
        numeric_sequence_match=ASRRuleDisposition.CLAIM,
    )

    result = evaluate_asr_test_case_decision(
        records=records_for(
            policy,
            values={
                REFERENCE_NUMERIC_TOKEN_COUNT_METRIC.key: -1,
                NUMERIC_TOKEN_SEQUENCE_MATCH_METRIC.key: True,
            },
        ),
        policy=policy,
        target=TARGET,
    )

    assert result.integrity == IntegrityAssessment.INVALID
    assert result.decision.verdict == DecisionVerdict.INVALID


def test_wrong_target_cannot_supply_policy_evidence():
    policy = ASRTestCaseDecisionPolicyV1(
        max_normalized_wer=0.20,
    )

    result = evaluate_asr_test_case_decision(
        records=records_for(
            policy,
            test_case_id=21,
        ),
        policy=policy,
        target=TARGET,
    )

    assert (
        result.readiness.evidence
        == EvidenceAssessment.INSUFFICIENT
    )
    assert (
        result.decision.verdict
        == DecisionVerdict.INCONCLUSIVE
    )


def test_findings_are_in_stable_policy_rule_order():
    policy = full_policy()

    result = evaluate_asr_test_case_decision(
        records=records_for(policy),
        policy=policy,
        target=TARGET,
    )

    assert [
        finding.rule
        for finding in result.findings
    ] == [
        ASRDecisionRule.MAX_NORMALIZED_WER,
        ASRDecisionRule.MAX_NORMALIZED_CER,
        ASRDecisionRule.MISSING_OUTPUT,
        ASRDecisionRule.UNEXPECTED_OUTPUT,
        ASRDecisionRule.NUMERIC_SEQUENCE_MATCH,
    ]

    assert all(
        finding.outcome
        == ASRRuleOutcome.SATISFIED
        for finding in result.findings
    )


def test_negative_numeric_count_is_invalid_even_when_sequence_mismatches():
    policy = ASRTestCaseDecisionPolicyV1(
        numeric_sequence_match=ASRRuleDisposition.CRITICAL,
    )

    result = evaluate_asr_test_case_decision(
        records=records_for(
            policy,
            values={
                REFERENCE_NUMERIC_TOKEN_COUNT_METRIC.key: -1,
                NUMERIC_TOKEN_SEQUENCE_MATCH_METRIC.key: False,
            },
        ),
        policy=policy,
        target=TARGET,
    )

    assert result.integrity == IntegrityAssessment.INVALID
    assert result.decision.verdict == DecisionVerdict.INVALID
    assert (
        result.decision.reason
        == DecisionReason.INTEGRITY_INVALID
    )

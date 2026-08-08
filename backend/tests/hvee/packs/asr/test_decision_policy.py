import math

import pytest

from hvee.core.contracts import (
    HveeContractError,
    MetricValueType,
)
from hvee.packs.asr import (
    NORMALIZED_CER_EVALUATOR,
    NORMALIZED_CER_METRIC,
    NORMALIZED_WER_EVALUATOR,
    NORMALIZED_WER_METRIC,
)
from hvee.packs.asr.decision_policy import (
    ASRRuleDisposition,
    ASRTestCaseDecisionPolicyV1,
    ASR_TEST_CASE_DECISION_POLICY_KEY,
    ASR_TEST_CASE_DECISION_POLICY_VERSION,
    build_asr_test_case_requirements,
)
from hvee.packs.asr.numeric_preservation import (
    NUMERIC_TOKEN_PRESERVATION_EVALUATOR,
    NUMERIC_TOKEN_SEQUENCE_MATCH_METRIC,
    REFERENCE_NUMERIC_TOKEN_COUNT_METRIC,
)
from hvee.packs.asr.transcript_integrity import (
    MISSING_OUTPUT_METRIC,
    TRANSCRIPT_INTEGRITY_EVALUATOR,
    UNEXPECTED_OUTPUT_METRIC,
)


def identity_tuple(requirement):
    return (
        requirement.metric_key,
        requirement.metric_version,
        requirement.evaluator_key,
        requirement.evaluator_version,
        requirement.evaluation_type,
        requirement.scope,
    )


def test_policy_identity_is_frozen_v1():
    policy = ASRTestCaseDecisionPolicyV1(
        max_normalized_wer=0.2,
    )

    assert (
        policy.key
        == ASR_TEST_CASE_DECISION_POLICY_KEY
    )
    assert (
        policy.version
        == ASR_TEST_CASE_DECISION_POLICY_VERSION
    )


def test_policy_requires_at_least_one_rule():
    with pytest.raises(
        HveeContractError,
        match="at least one decision rule",
    ):
        ASRTestCaseDecisionPolicyV1()


@pytest.mark.parametrize(
    "value",
    [
        -0.01,
        math.inf,
        -math.inf,
        math.nan,
        True,
        "0.2",
    ],
)
def test_invalid_wer_limits_are_rejected(
    value,
):
    with pytest.raises(
        HveeContractError,
        match="maximum normalized WER",
    ):
        ASRTestCaseDecisionPolicyV1(
            max_normalized_wer=value,
        )


@pytest.mark.parametrize(
    "value",
    [
        -0.01,
        math.inf,
        -math.inf,
        math.nan,
        False,
        "0.1",
    ],
)
def test_invalid_cer_limits_are_rejected(
    value,
):
    with pytest.raises(
        HveeContractError,
        match="maximum normalized CER",
    ):
        ASRTestCaseDecisionPolicyV1(
            max_normalized_cer=value,
        )


def test_zero_threshold_is_valid():
    policy = ASRTestCaseDecisionPolicyV1(
        max_normalized_wer=0.0,
    )

    assert policy.max_normalized_wer == 0.0


def test_wer_above_one_is_valid():
    policy = ASRTestCaseDecisionPolicyV1(
        max_normalized_wer=1.5,
    )

    assert policy.max_normalized_wer == 1.5


def test_raw_disposition_string_is_rejected():
    with pytest.raises(
        HveeContractError,
        match="missing-output disposition",
    ):
        ASRTestCaseDecisionPolicyV1(
            missing_output="critical",
        )


def test_wer_rule_requires_exact_normalized_wer_identity():
    policy = ASRTestCaseDecisionPolicyV1(
        max_normalized_wer=0.2,
    )

    requirements = (
        build_asr_test_case_requirements(
            policy
        )
    )

    assert len(requirements) == 1

    requirement = requirements[0]

    assert identity_tuple(requirement) == (
        NORMALIZED_WER_METRIC.key,
        NORMALIZED_WER_METRIC.version,
        NORMALIZED_WER_EVALUATOR.key,
        NORMALIZED_WER_EVALUATOR.version,
        "asr",
        "test_case",
    )


def test_cer_rule_requires_exact_normalized_cer_identity():
    policy = ASRTestCaseDecisionPolicyV1(
        max_normalized_cer=0.1,
    )

    requirements = (
        build_asr_test_case_requirements(
            policy
        )
    )

    assert len(requirements) == 1

    assert identity_tuple(
        requirements[0]
    ) == (
        NORMALIZED_CER_METRIC.key,
        NORMALIZED_CER_METRIC.version,
        NORMALIZED_CER_EVALUATOR.key,
        NORMALIZED_CER_EVALUATOR.version,
        "asr",
        "test_case",
    )


@pytest.mark.parametrize(
    "disposition",
    [
        ASRRuleDisposition.CLAIM,
        ASRRuleDisposition.CRITICAL,
    ],
)
def test_missing_output_rule_requires_integrity_signal(
    disposition,
):
    policy = ASRTestCaseDecisionPolicyV1(
        missing_output=disposition,
    )

    requirements = (
        build_asr_test_case_requirements(
            policy
        )
    )

    assert len(requirements) == 1

    assert identity_tuple(
        requirements[0]
    ) == (
        MISSING_OUTPUT_METRIC.key,
        MISSING_OUTPUT_METRIC.version,
        TRANSCRIPT_INTEGRITY_EVALUATOR.key,
        TRANSCRIPT_INTEGRITY_EVALUATOR.version,
        "asr",
        "test_case",
    )


@pytest.mark.parametrize(
    "disposition",
    [
        ASRRuleDisposition.CLAIM,
        ASRRuleDisposition.CRITICAL,
    ],
)
def test_unexpected_output_rule_requires_integrity_signal(
    disposition,
):
    policy = ASRTestCaseDecisionPolicyV1(
        unexpected_output=disposition,
    )

    requirements = (
        build_asr_test_case_requirements(
            policy
        )
    )

    assert len(requirements) == 1

    assert identity_tuple(
        requirements[0]
    ) == (
        UNEXPECTED_OUTPUT_METRIC.key,
        UNEXPECTED_OUTPUT_METRIC.version,
        TRANSCRIPT_INTEGRITY_EVALUATOR.key,
        TRANSCRIPT_INTEGRITY_EVALUATOR.version,
        "asr",
        "test_case",
    )


@pytest.mark.parametrize(
    "disposition",
    [
        ASRRuleDisposition.CLAIM,
        ASRRuleDisposition.CRITICAL,
    ],
)
def test_numeric_rule_requires_reference_count_and_sequence_signal(
    disposition,
):
    policy = ASRTestCaseDecisionPolicyV1(
        numeric_sequence_match=disposition,
    )

    requirements = (
        build_asr_test_case_requirements(
            policy
        )
    )

    assert len(requirements) == 2

    assert {
        requirement.metric_key
        for requirement in requirements
    } == {
        REFERENCE_NUMERIC_TOKEN_COUNT_METRIC.key,
        REFERENCE_NUMERIC_TOKEN_COUNT_METRIC.key,
        NUMERIC_TOKEN_SEQUENCE_MATCH_METRIC.key,
    }

    for requirement in requirements:
        assert (
            requirement.evaluator_key
            == NUMERIC_TOKEN_PRESERVATION_EVALUATOR.key
        )
        assert (
            requirement.evaluator_version
            == NUMERIC_TOKEN_PRESERVATION_EVALUATOR.version
        )
        assert requirement.evaluation_type == "asr"
        assert requirement.scope == "test_case"


def test_disabled_rules_do_not_require_observations():
    policy = ASRTestCaseDecisionPolicyV1(
        max_normalized_wer=0.2,
        missing_output=ASRRuleDisposition.DISABLED,
        unexpected_output=ASRRuleDisposition.DISABLED,
        numeric_sequence_match=ASRRuleDisposition.DISABLED,
    )

    requirements = (
        build_asr_test_case_requirements(
            policy
        )
    )

    assert {
        requirement.metric_key
        for requirement in requirements
    } == {
        NORMALIZED_WER_METRIC.key,
    }


def test_all_enabled_rules_build_deterministic_requirement_set():
    policy = ASRTestCaseDecisionPolicyV1(
        max_normalized_wer=0.2,
        max_normalized_cer=0.1,
        missing_output=ASRRuleDisposition.CRITICAL,
        unexpected_output=ASRRuleDisposition.CLAIM,
        numeric_sequence_match=ASRRuleDisposition.CRITICAL,
    )

    requirements = (
        build_asr_test_case_requirements(
            policy
        )
    )

    assert len(requirements) == 6

    identities = [
        requirement.identity
        for requirement in requirements
    ]

    assert identities == sorted(identities)

    assert {
        requirement.metric_key
        for requirement in requirements
    } == {
        NORMALIZED_WER_METRIC.key,
        NORMALIZED_CER_METRIC.key,
        MISSING_OUTPUT_METRIC.key,
        UNEXPECTED_OUTPUT_METRIC.key,
        REFERENCE_NUMERIC_TOKEN_COUNT_METRIC.key,
        NUMERIC_TOKEN_SEQUENCE_MATCH_METRIC.key,
    }


def test_rule_disposition_does_not_change_required_identity():
    claim_policy = ASRTestCaseDecisionPolicyV1(
        missing_output=ASRRuleDisposition.CLAIM,
    )
    critical_policy = (
        ASRTestCaseDecisionPolicyV1(
            missing_output=(
                ASRRuleDisposition.CRITICAL
            ),
        )
    )

    assert (
        build_asr_test_case_requirements(
            claim_policy
        )
        == build_asr_test_case_requirements(
            critical_policy
        )
    )


def test_requirement_builder_rejects_wrong_contract_type():
    with pytest.raises(
        HveeContractError,
        match="ASRTestCaseDecisionPolicyV1",
    ):
        build_asr_test_case_requirements(
            object()
        )

from dataclasses import replace

import pytest

from hvee.core.decision import (
    ClaimAssessment,
    DecisionReason,
    DecisionResult,
    DecisionVerdict,
    EvidenceAssessment,
    IntegrityAssessment,
)
from hvee.core.paired_assurance import (
    PairedIntervalMethod,
    PairedIntervalPolicy,
)
from hvee.core.paired_interval import (
    PairedIntervalReason,
    PairedMeanDeltaInterval,
)
from hvee.packs.asr.normalized_evaluation import (
    NORMALIZED_CER_METRIC,
    NORMALIZED_WER_METRIC,
)
from hvee.packs.asr.release_assurance import (
    ASRMatchedReleaseAssuranceResult,
    ASRMetricNoninferiorityAssessment,
)
from hvee.packs.asr.release_assurance_policy import (
    ASRMatchedReleaseAssurancePolicyV1,
)
from hvee.packs.asr.reliability_qualification import (
    ASR_RELIABILITY_CRITICAL_GROUP_KEYS_V1,
    ASR_RELIABILITY_QUALIFICATION_RESULT_KEY,
    ASR_RELIABILITY_QUALIFICATION_RESULT_SCHEMA_VERSION,
    ASR_RELIABILITY_QUALIFICATION_RESULT_VERSION,
    ASRReliabilityQualificationError,
    evaluate_asr_reliability_qualification_v1,
)
from hvee.packs.asr.reliability_qualification_policy import (
    ASRCriticalIntegrityConfidencePolicyV1,
    build_asr_reliability_qualification_policy_v1,
)
from hvee.packs.asr.reliability_scoring import (
    ASREvidenceAssuranceEvidence,
    ASRMatchedControlRobustnessEvidence,
    ASROperationalFitnessEvidence,
    ASRReliabilityGateEvidence,
    ASRReliabilityPerformanceEvidence,
    ASRReliabilityRateEvidence,
    ASRReliabilityScoringEvidence,
)
from hvee.packs.asr.transcript_integrity import (
    MISSING_OUTPUT_METRIC,
    UNEXPECTED_OUTPUT_METRIC,
)


def _matched_policy() -> ASRMatchedReleaseAssurancePolicyV1:
    return ASRMatchedReleaseAssurancePolicyV1(
        interval=PairedIntervalPolicy(
            method=PairedIntervalMethod.BOOTSTRAP_PERCENTILE_V1,
            confidence_level=0.95,
            minimum_usable_pairs=16,
            resamples=10_000,
            random_seed=20_260_822,
        ),
        normalized_wer_noninferiority_margin=0.02,
        normalized_cer_noninferiority_margin=0.01,
    )


def _policy():
    return build_asr_reliability_qualification_policy_v1(
        minimum_hetren_reliability_index=90.0,
        minimum_reliability_performance_index=90.0,
        minimum_evidence_assurance_index=100.0,
        minimum_operational_fitness_index=95.0,
        minimum_matched_control_robustness_score=90.0,
        minimum_critical_integrity_group_score=90.0,
        minimum_matched_control_pairs=16,
        matched_release_assurance=_matched_policy(),
        critical_integrity_confidence=(
            ASRCriticalIntegrityConfidencePolicyV1(
                familywise_confidence_level_ppm=950_000,
                minimum_conclusive_observations_per_group=30,
                minimum_preservation_lower_bound_ppm=900_000,
            )
        ),
    )


def _rate(
    successful: int = 40,
    observed: int = 40,
    expected: int = 40,
) -> ASRReliabilityRateEvidence:
    return ASRReliabilityRateEvidence(
        successful_count=successful,
        observed_count=observed,
        expected_count=expected,
    )


def _gate(
    *,
    metric_key: str,
    violations: int = 0,
    observed: int = 64,
    expected: int = 64,
) -> ASRReliabilityGateEvidence:
    return ASRReliabilityGateEvidence(
        metric_key=metric_key,
        violation_count=violations,
        observed_count=observed,
        expected_count=expected,
    )


def _complete_evidence() -> ASRReliabilityScoringEvidence:
    return ASRReliabilityScoringEvidence(
        performance=ASRReliabilityPerformanceEvidence(
            matched_control_robustness=(
                ASRMatchedControlRobustnessEvidence(
                    wer_differential=0.0,
                    cer_differential=0.0,
                    observed_pair_count=16,
                    expected_pair_count=16,
                )
            ),
            critical_number_integrity=_rate(),
            critical_identifier_integrity=_rate(),
            critical_terminology_integrity=_rate(),
        ),
        assurance=ASREvidenceAssuranceEvidence(
            profile_and_evaluators_verified=True,
            input_provenance_verified=True,
            runtime_identity_verified=True,
            reproducibility_verified=True,
        ),
        operational=ASROperationalFitnessEvidence(
            execution_completion=_rate(64, 64, 64),
            timeout_free=_rate(64, 64, 64),
            cancellation_free=_rate(64, 64, 64),
            provider_error_free=_rate(64, 64, 64),
        ),
        missing_output_gate=_gate(metric_key=MISSING_OUTPUT_METRIC.key),
        unexpected_output_gate=_gate(
            metric_key=UNEXPECTED_OUTPUT_METRIC.key
        ),
    )


def _interval(
    *,
    policy: ASRMatchedReleaseAssurancePolicyV1,
    lower: float = -0.005,
    upper: float = 0.005,
    reason: PairedIntervalReason = PairedIntervalReason.READY,
) -> PairedMeanDeltaInterval:
    ready = reason == PairedIntervalReason.READY
    invalid = reason == PairedIntervalReason.INTEGRITY_INVALID
    return PairedMeanDeltaInterval(
        method=policy.interval.method,
        confidence_level=policy.interval.confidence_level,
        minimum_usable_pairs=policy.interval.minimum_usable_pairs,
        resamples=policy.interval.resamples,
        random_seed=policy.interval.random_seed,
        total_cases=32,
        usable_pairs=32 if ready else 31,
        integrity=(
            IntegrityAssessment.INVALID
            if invalid
            else IntegrityAssessment.VALID
        ),
        evidence=(
            EvidenceAssessment.SUFFICIENT
            if ready
            else EvidenceAssessment.INSUFFICIENT
        ),
        reason=reason,
        mean_delta=0.0 if ready else None,
        lower_bound=lower if ready else None,
        upper_bound=upper if ready else None,
    )


def _metric_assessment(
    *,
    policy: ASRMatchedReleaseAssurancePolicyV1,
    metric,
    margin: float,
    lower: float,
    upper: float,
    reason: PairedIntervalReason,
) -> ASRMetricNoninferiorityAssessment:
    interval = _interval(
        policy=policy,
        lower=lower,
        upper=upper,
        reason=reason,
    )
    if not interval.ready:
        claim = ClaimAssessment.UNRESOLVED
    elif interval.upper_bound <= margin:
        claim = ClaimAssessment.SUPPORTED
    elif interval.lower_bound > margin:
        claim = ClaimAssessment.CONTRADICTED
    else:
        claim = ClaimAssessment.UNRESOLVED
    return ASRMetricNoninferiorityAssessment(
        metric_key=metric.key,
        metric_version=metric.version,
        noninferiority_margin=margin,
        interval=interval,
        claim=claim,
    )


def _matched_assurance(
    *,
    policy=None,
    wer_lower: float = -0.005,
    wer_upper: float = 0.005,
    wer_reason: PairedIntervalReason = PairedIntervalReason.READY,
    cer_lower: float = -0.003,
    cer_upper: float = 0.003,
    cer_reason: PairedIntervalReason = PairedIntervalReason.READY,
) -> ASRMatchedReleaseAssuranceResult:
    if policy is None:
        policy = _policy()
    matched = policy.matched_release_assurance
    wer = _metric_assessment(
        policy=matched,
        metric=NORMALIZED_WER_METRIC,
        margin=matched.normalized_wer_noninferiority_margin,
        lower=wer_lower,
        upper=wer_upper,
        reason=wer_reason,
    )
    cer = _metric_assessment(
        policy=matched,
        metric=NORMALIZED_CER_METRIC,
        margin=matched.normalized_cer_noninferiority_margin,
        lower=cer_lower,
        upper=cer_upper,
        reason=cer_reason,
    )
    enabled = (wer, cer)
    integrity = (
        IntegrityAssessment.INVALID
        if any(
            value.interval.integrity == IntegrityAssessment.INVALID
            for value in enabled
        )
        else IntegrityAssessment.VALID
    )
    evidence = (
        EvidenceAssessment.SUFFICIENT
        if all(
            value.interval.evidence == EvidenceAssessment.SUFFICIENT
            for value in enabled
        )
        else EvidenceAssessment.INSUFFICIENT
    )
    claims = tuple(value.claim for value in enabled)
    if ClaimAssessment.CONTRADICTED in claims:
        claim = ClaimAssessment.CONTRADICTED
    elif all(value == ClaimAssessment.SUPPORTED for value in claims):
        claim = ClaimAssessment.SUPPORTED
    else:
        claim = ClaimAssessment.UNRESOLVED
    return ASRMatchedReleaseAssuranceResult(
        policy_key=matched.key,
        policy_version=matched.version,
        baseline_run_id=10,
        candidate_run_id=20,
        declared_test_case_ids=tuple(range(1, 33)),
        normalized_wer=wer,
        normalized_cer=cer,
        integrity=integrity,
        evidence=evidence,
        claim=claim,
    )


def _evaluate(*, evidence=None, assurance=None, policy=None):
    if evidence is None:
        evidence = _complete_evidence()
    if policy is None:
        policy = _policy()
    if assurance is None:
        assurance = _matched_assurance(policy=policy)
    return evaluate_asr_reliability_qualification_v1(
        scoring_evidence=evidence,
        matched_assurance=assurance,
        policy=policy,
    )


def test_complete_supported_evidence_passes_explicit_policy():
    result = _evaluate()

    assert result.payload["schema_version"] == (
        ASR_RELIABILITY_QUALIFICATION_RESULT_SCHEMA_VERSION
    )
    assert result.payload["artifact"] == {
        "key": ASR_RELIABILITY_QUALIFICATION_RESULT_KEY,
        "version": ASR_RELIABILITY_QUALIFICATION_RESULT_VERSION,
        "type": "non_authoritative_qualification_decision",
    }
    assert result.decision.verdict == DecisionVerdict.PASS
    assert result.decision.reason == DecisionReason.CLAIM_SUPPORTED
    assert result.decision_inputs.integrity == IntegrityAssessment.VALID
    assert result.decision_inputs.evidence == EvidenceAssessment.SUFFICIENT
    assert result.decision_inputs.claim == ClaimAssessment.SUPPORTED
    assert all(
        value.claim == ClaimAssessment.SUPPORTED
        for value in result.score_floor_assessments
    )


def test_critical_confidence_uses_exact_bounds_and_holm_family():
    result = _evaluate()
    assessments = result.critical_confidence_assessments
    payload = result.payload["critical_confidence"]

    assert tuple(value.key for value in assessments) == (
        ASR_RELIABILITY_CRITICAL_GROUP_KEYS_V1
    )
    assert payload["methodology"] == {
        "rate_scale": 1_000_000,
        "interval": "clopper_pearson_one_sided_lower_scaled",
        "hypothesis_test_tail": "greater_than_or_equal",
        "multiplicity_control": "holm_step_down",
        "support_rule": (
            "lower_bound_meets_threshold_and_holm_rejected"
        ),
    }
    assert payload["familywise_alpha"] == {
        "numerator": 1,
        "denominator": 20,
    }
    assert all(value.lower_bound_ppm == 927_842 for value in assessments)
    assert sorted(value.holm_rank for value in assessments) == [1, 2, 3]
    assert all(value.holm_rejected is True for value in assessments)
    assert all(value.claim == ClaimAssessment.SUPPORTED for value in assessments)


def test_known_hard_gate_violation_fails_before_missing_support():
    source = _complete_evidence()
    evidence = replace(
        source,
        missing_output_gate=_gate(
            metric_key=MISSING_OUTPUT_METRIC.key,
            violations=1,
            observed=1,
            expected=64,
        ),
    )
    result = _evaluate(evidence=evidence)

    assert result.decision_inputs.evidence == EvidenceAssessment.INSUFFICIENT
    assert result.decision.verdict == DecisionVerdict.FAIL
    assert result.decision.reason == DecisionReason.CRITICAL_VIOLATION


def test_invalid_matched_evidence_produces_invalid_verdict():
    result = _evaluate(
        assurance=_matched_assurance(
            wer_reason=PairedIntervalReason.INTEGRITY_INVALID,
        )
    )

    assert result.decision_inputs.integrity == IntegrityAssessment.INVALID
    assert result.decision.verdict == DecisionVerdict.INVALID
    assert result.decision.reason == DecisionReason.INTEGRITY_INVALID


def test_incomplete_matched_assurance_is_inconclusive():
    result = _evaluate(
        assurance=_matched_assurance(
            wer_reason=PairedIntervalReason.COHORT_INCOMPLETE,
        )
    )

    assert result.matched_assurance_support_sufficient is False
    assert result.decision.verdict == DecisionVerdict.INCONCLUSIVE
    assert result.decision.reason == DecisionReason.EVIDENCE_INSUFFICIENT


def test_critical_minimum_support_is_required_even_for_complete_scorecard():
    source = _complete_evidence()
    evidence = replace(
        source,
        performance=replace(
            source.performance,
            critical_number_integrity=_rate(20, 20, 20),
            critical_identifier_integrity=_rate(20, 20, 20),
            critical_terminology_integrity=_rate(20, 20, 20),
        ),
    )
    result = _evaluate(evidence=evidence)

    assert result.scorecard_support_sufficient is True
    assert result.critical_support_sufficient is False
    assert all(
        value.lower_bound_ppm is None
        for value in result.critical_confidence_assessments
    )
    assert result.decision.verdict == DecisionVerdict.INCONCLUSIVE
    assert result.decision.reason == DecisionReason.EVIDENCE_INSUFFICIENT


def test_unresolved_critical_confidence_is_not_silently_failed():
    source = _complete_evidence()
    evidence = replace(
        source,
        performance=replace(
            source.performance,
            critical_number_integrity=_rate(38, 40, 40),
            critical_identifier_integrity=_rate(38, 40, 40),
            critical_terminology_integrity=_rate(38, 40, 40),
        ),
    )
    result = _evaluate(evidence=evidence)

    assert result.decision_inputs.evidence == EvidenceAssessment.SUFFICIENT
    assert result.decision_inputs.claim == ClaimAssessment.UNRESOLVED
    assert result.decision.verdict == DecisionVerdict.INCONCLUSIVE
    assert result.decision.reason == DecisionReason.CLAIM_UNRESOLVED
    assert all(
        value.lower_bound_ppm == 850_848
        for value in result.critical_confidence_assessments
    )


def test_complete_score_floor_failure_produces_fail():
    source = _complete_evidence()
    evidence = replace(
        source,
        performance=replace(
            source.performance,
            critical_number_integrity=_rate(35, 40, 40),
        ),
    )
    result = _evaluate(evidence=evidence)

    number = next(
        value
        for value in result.score_floor_assessments
        if value.key == "critical_number_integrity"
    )
    assert number.observed_score == 87.5
    assert number.claim == ClaimAssessment.CONTRADICTED
    assert result.decision_inputs.evidence == EvidenceAssessment.SUFFICIENT
    assert result.decision.verdict == DecisionVerdict.FAIL
    assert result.decision.reason == DecisionReason.CLAIM_CONTRADICTED


def test_statistically_contradicted_matched_claim_produces_fail():
    result = _evaluate(
        assurance=_matched_assurance(
            wer_lower=0.03,
            wer_upper=0.04,
        )
    )

    assert result.matched_assurance.claim == ClaimAssessment.CONTRADICTED
    assert result.decision.verdict == DecisionVerdict.FAIL
    assert result.decision.reason == DecisionReason.CLAIM_CONTRADICTED


def test_overlapping_matched_interval_remains_inconclusive():
    result = _evaluate(
        assurance=_matched_assurance(
            wer_lower=-0.01,
            wer_upper=0.03,
        )
    )

    assert result.matched_assurance.claim == ClaimAssessment.UNRESOLVED
    assert result.decision_inputs.evidence == EvidenceAssessment.SUFFICIENT
    assert result.decision.verdict == DecisionVerdict.INCONCLUSIVE
    assert result.decision.reason == DecisionReason.CLAIM_UNRESOLVED


def test_partial_scorecard_is_inconclusive_not_compared_as_complete():
    source = _complete_evidence()
    evidence = replace(
        source,
        performance=replace(
            source.performance,
            critical_terminology_integrity=None,
        ),
    )
    result = _evaluate(evidence=evidence)

    assert result.scorecard_support_sufficient is False
    assert result.decision.verdict == DecisionVerdict.INCONCLUSIVE
    assert result.decision.reason == DecisionReason.EVIDENCE_INSUFFICIENT


def test_matched_control_pair_minimum_is_explicit_support_requirement():
    source = _complete_evidence()
    evidence = replace(
        source,
        performance=replace(
            source.performance,
            matched_control_robustness=(
                ASRMatchedControlRobustnessEvidence(
                    wer_differential=0.0,
                    cer_differential=0.0,
                    observed_pair_count=15,
                    expected_pair_count=16,
                )
            ),
        ),
    )
    result = _evaluate(evidence=evidence)

    assert result.matched_control_support_sufficient is False
    assert result.decision.verdict == DecisionVerdict.INCONCLUSIVE
    assert result.decision.reason == DecisionReason.EVIDENCE_INSUFFICIENT


def test_result_is_deterministic_hash_bound_and_engineer_readable():
    first = _evaluate()
    second = _evaluate()

    assert first is not second
    assert first.payload == second.payload
    assert first.sha256 == second.sha256
    assert len(first.sha256) == 64
    labels = {
        value.payload["engineer_label"]
        for value in first.score_floor_assessments
    }
    assert "Hetren Reliability Index" in labels
    assert "Critical Identifier Integrity" in labels


def test_result_does_not_claim_certification_or_release_authority():
    boundary = _evaluate().payload["evidence_boundary"]

    assert boundary["explicit_policy_applied"] is True
    assert boundary["model_qualification_verdict_issued"] is True
    assert boundary["certification_issued"] is False
    assert boundary["production_qualified"] is False
    assert boundary["release_enforcement_eligible"] is False
    assert boundary["official_release_verdict_modified"] is False


def test_mismatched_interval_policy_binding_is_rejected():
    policy = _policy()
    assurance = _matched_assurance(policy=policy)
    changed_interval = replace(
        assurance.normalized_wer.interval,
        random_seed=policy.matched_release_assurance.interval.random_seed + 1,
    )
    changed_wer = replace(
        assurance.normalized_wer,
        interval=changed_interval,
    )
    changed_assurance = replace(
        assurance,
        normalized_wer=changed_wer,
    )

    with pytest.raises(
        ASRReliabilityQualificationError,
        match="policy binding",
    ):
        _evaluate(policy=policy, assurance=changed_assurance)


def test_duplicate_declared_case_identity_maps_to_invalid():
    assurance = _matched_assurance()
    changed = replace(
        assurance,
        declared_test_case_ids=(1,) * 32,
    )
    result = _evaluate(assurance=changed)

    assert result.decision.verdict == DecisionVerdict.INVALID
    assert result.decision.reason == DecisionReason.INTEGRITY_INVALID


def test_sufficient_interval_must_cover_every_declared_case():
    assurance = _matched_assurance()
    changed_interval = replace(
        assurance.normalized_wer.interval,
        usable_pairs=31,
    )
    changed_wer = replace(
        assurance.normalized_wer,
        interval=changed_interval,
    )
    changed_assurance = replace(
        assurance,
        normalized_wer=changed_wer,
    )
    result = _evaluate(assurance=changed_assurance)

    assert result.decision.verdict == DecisionVerdict.INVALID
    assert result.decision.reason == DecisionReason.INTEGRITY_INVALID


@pytest.mark.parametrize(
    ("argument", "value", "message"),
    (
        ("scoring_evidence", object(), "raw scoring evidence"),
        ("matched_assurance", object(), "matched release assurance"),
        ("policy", object(), "exact B11A policy"),
    ),
)
def test_wrong_top_level_input_type_is_rejected(argument, value, message):
    arguments = {
        "scoring_evidence": _complete_evidence(),
        "matched_assurance": _matched_assurance(),
        "policy": _policy(),
    }
    arguments[argument] = value

    with pytest.raises(ASRReliabilityQualificationError, match=message):
        evaluate_asr_reliability_qualification_v1(**arguments)


def test_result_rejects_decision_tampering():
    result = _evaluate()
    tampered = DecisionResult(
        verdict=DecisionVerdict.FAIL,
        reason=DecisionReason.CLAIM_CONTRADICTED,
    )

    with pytest.raises(
        ASRReliabilityQualificationError,
        match="universal kernel",
    ):
        replace(result, decision=tampered)

from dataclasses import replace
import math

import pytest

from hvee.packs.asr import (
    ASR_RELIABILITY_PROFILE_V1,
    ASR_RELIABILITY_PROFILE_V1_SHA256,
    ASR_RELIABILITY_SCORING_KEY,
    ASR_RELIABILITY_SCORING_SCHEMA_VERSION,
    ASR_RELIABILITY_SCORING_V1,
    ASR_RELIABILITY_SCORING_V1_SHA256,
    ASR_RELIABILITY_SCORING_VERSION,
    MISSING_OUTPUT_METRIC,
    UNEXPECTED_OUTPUT_METRIC,
    ASREvidenceAssuranceEvidence,
    ASRMatchedControlRobustnessEvidence,
    ASROperationalFitnessEvidence,
    ASRReliabilityGateEvidence,
    ASRReliabilityGateStatus,
    ASRReliabilityIndexStatus,
    ASRReliabilityMaturityStatus,
    ASRReliabilityPerformanceEvidence,
    ASRReliabilityRateEvidence,
    ASRReliabilityScoringError,
    ASRReliabilityScoringEvidence,
    score_asr_reliability_v1,
    verify_asr_reliability_scoring_v1,
)


def _rate(
    successful: int = 10,
    observed: int = 10,
    expected: int = 10,
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
        missing_output_gate=_gate(
            metric_key=MISSING_OUTPUT_METRIC.key,
        ),
        unexpected_output_gate=_gate(
            metric_key=UNEXPECTED_OUTPUT_METRIC.key,
        ),
    )


def test_scoring_definition_has_frozen_identity():
    definition = ASR_RELIABILITY_SCORING_V1

    assert definition.key == ASR_RELIABILITY_SCORING_KEY
    assert definition.version == ASR_RELIABILITY_SCORING_VERSION
    assert definition.profile_sha256 == ASR_RELIABILITY_PROFILE_V1_SHA256
    assert definition.sha256 == ASR_RELIABILITY_SCORING_V1_SHA256
    assert len(definition.sha256) == 64
    assert definition.payload["schema_version"] == (
        ASR_RELIABILITY_SCORING_SCHEMA_VERSION
    )
    assert verify_asr_reliability_scoring_v1(definition) is definition


def test_scoring_definition_has_explicit_non_overlapping_weights():
    indices = ASR_RELIABILITY_SCORING_V1.payload["indices"]

    assert indices["reliability_performance_index"]["groups"] == {
        "matched_control_robustness": 0.25,
        "critical_number_integrity": 0.25,
        "critical_identifier_integrity": 0.25,
        "critical_terminology_integrity": 0.25,
    }
    assert indices["hetren_reliability_index"]["pillars"] == {
        "reliability_performance_index": 0.60,
        "evidence_assurance_index": 0.25,
        "operational_fitness_index": 0.15,
    }


def test_scoring_definition_declares_missing_and_gate_semantics():
    methodology = ASR_RELIABILITY_SCORING_V1.payload["methodology"]

    assert methodology == {
        "higher_scores_are_better": True,
        "zero_component_is_non_compensable": True,
        "missing_components_are_not_imputed": True,
        "partial_scores_are_provisional_and_not_comparable": True,
        "complete_score_requires_all_components": True,
        "known_hard_gate_failure_precedes_missing_evidence": True,
        "clear_gate_requires_complete_gate_observation": True,
    }


@pytest.mark.parametrize(
    ("differential", "expected"),
    (
        (-0.25, 100.0),
        (0.0, 100.0),
        (0.01, 99.0),
        (0.10, 90.0),
        (1.0, 0.0),
        (1.5, 0.0),
    ),
)
def test_robustness_transform_is_bounded_and_does_not_reward_regression(
    differential,
    expected,
):
    assert ASRMatchedControlRobustnessEvidence.transform_differential(
        differential
    ) == expected


def test_correlated_wer_and_cer_use_conservative_group_score():
    evidence = ASRMatchedControlRobustnessEvidence(
        wer_differential=0.05,
        cer_differential=0.10,
        observed_pair_count=16,
        expected_pair_count=16,
    )

    assert evidence.wer_score == 95.0
    assert evidence.cer_score == 90.0
    assert evidence.score == 90.0
    assert evidence.coverage_ratio == 1.0
    assert evidence.complete is True
    assert evidence.payload["aggregation"] == (
        "conservative_minimum_correlated_signal_score"
    )


def test_partial_robustness_signal_is_visible_but_incomplete():
    evidence = ASRMatchedControlRobustnessEvidence(
        wer_differential=0.05,
        cer_differential=None,
        observed_pair_count=8,
        expected_pair_count=16,
    )

    assert evidence.score == 95.0
    assert evidence.coverage_ratio == 0.25
    assert evidence.complete is False


def test_rate_evidence_separates_observed_score_from_coverage():
    evidence = _rate(successful=7, observed=8, expected=16)

    assert evidence.score == 87.5
    assert evidence.coverage_ratio == 0.5
    assert evidence.complete is False


def test_complete_clean_evidence_produces_complete_hundred_scorecard():
    scorecard = score_asr_reliability_v1(
        evidence=_complete_evidence(),
    )

    assert scorecard.profile_sha256 == ASR_RELIABILITY_PROFILE_V1_SHA256
    assert scorecard.gate_status == ASRReliabilityGateStatus.CLEAR
    assert scorecard.maturity_status == (
        ASRReliabilityMaturityStatus.COMPLETE_DESCRIPTIVE_EVIDENCE
    )
    assert scorecard.performance_index.score == 100.0
    assert scorecard.evidence_assurance_index.score == 100.0
    assert scorecard.operational_fitness_index.score == 100.0
    assert scorecard.hetren_reliability_index.score == 100.0
    assert scorecard.hetren_reliability_index.status == (
        ASRReliabilityIndexStatus.COMPLETE
    )


def test_scorecard_build_is_deterministic_and_hashable():
    first = score_asr_reliability_v1(evidence=_complete_evidence())
    second = score_asr_reliability_v1(evidence=_complete_evidence())

    assert first is not second
    assert first.payload == second.payload
    assert first.sha256 == second.sha256
    assert len(first.sha256) == 64


def test_zero_critical_component_cannot_be_compensated():
    source = _complete_evidence()
    evidence = replace(
        source,
        performance=replace(
            source.performance,
            critical_number_integrity=_rate(0, 10, 10),
        ),
    )
    scorecard = score_asr_reliability_v1(evidence=evidence)

    assert scorecard.performance_index.score == 0.0
    assert scorecard.hetren_reliability_index.score == 0.0
    assert scorecard.hetren_reliability_index.status == (
        ASRReliabilityIndexStatus.COMPLETE
    )


def test_missing_primary_evidence_withholds_complete_index():
    source = _complete_evidence()
    evidence = replace(
        source,
        performance=replace(
            source.performance,
            critical_terminology_integrity=None,
        ),
    )
    scorecard = score_asr_reliability_v1(evidence=evidence)

    assert scorecard.performance_index.status == (
        ASRReliabilityIndexStatus.PROVISIONAL
    )
    assert scorecard.performance_index.score is None
    assert scorecard.performance_index.observed_score == 100.0
    assert scorecard.performance_index.coverage_ratio == 0.75
    assert scorecard.hetren_reliability_index.score is None
    assert scorecard.hetren_reliability_index.observed_score == 100.0
    assert scorecard.maturity_status == (
        ASRReliabilityMaturityStatus.PARTIAL_DESCRIPTIVE_EVIDENCE
    )


def test_unresolved_gate_withholds_otherwise_complete_index():
    source = _complete_evidence()
    evidence = replace(
        source,
        missing_output_gate=_gate(
            metric_key=MISSING_OUTPUT_METRIC.key,
            observed=63,
            expected=64,
        ),
    )
    scorecard = score_asr_reliability_v1(evidence=evidence)

    assert scorecard.gate_status == ASRReliabilityGateStatus.UNRESOLVED
    assert scorecard.hetren_reliability_index.status == (
        ASRReliabilityIndexStatus.PROVISIONAL
    )
    assert scorecard.hetren_reliability_index.score is None
    assert scorecard.hetren_reliability_index.observed_score == 100.0


def test_known_gate_failure_precedes_all_other_missing_evidence():
    evidence = ASRReliabilityScoringEvidence(
        performance=ASRReliabilityPerformanceEvidence(),
        assurance=ASREvidenceAssuranceEvidence(),
        operational=ASROperationalFitnessEvidence(),
        missing_output_gate=_gate(
            metric_key=MISSING_OUTPUT_METRIC.key,
            violations=1,
            observed=1,
            expected=64,
        ),
        unexpected_output_gate=None,
    )
    scorecard = score_asr_reliability_v1(evidence=evidence)

    assert scorecard.gate_status == ASRReliabilityGateStatus.TRIGGERED
    assert scorecard.maturity_status == (
        ASRReliabilityMaturityStatus.HARD_GATE_FAILURE_OBSERVED
    )
    assert scorecard.hetren_reliability_index.status == (
        ASRReliabilityIndexStatus.HARD_GATE_TRIGGERED
    )
    assert scorecard.hetren_reliability_index.score == 0.0
    assert scorecard.hetren_reliability_index.observed_score is None


def test_failed_assurance_check_is_not_treated_as_missing():
    source = _complete_evidence()
    evidence = replace(
        source,
        assurance=replace(
            source.assurance,
            runtime_identity_verified=False,
        ),
    )
    scorecard = score_asr_reliability_v1(evidence=evidence)

    assert scorecard.evidence_assurance_index.status == (
        ASRReliabilityIndexStatus.COMPLETE
    )
    assert scorecard.evidence_assurance_index.score == 0.0
    assert scorecard.hetren_reliability_index.score == 0.0


@pytest.mark.parametrize(
    "counts",
    (
        (-1, 0, 1),
        (2, 1, 2),
        (1, 3, 2),
        (0, 0, 0),
    ),
)
def test_invalid_rate_counts_are_rejected(counts):
    with pytest.raises(ASRReliabilityScoringError):
        ASRReliabilityRateEvidence(
            successful_count=counts[0],
            observed_count=counts[1],
            expected_count=counts[2],
        )


@pytest.mark.parametrize("value", (math.nan, math.inf, -math.inf))
def test_non_finite_robustness_differentials_are_rejected(value):
    with pytest.raises(
        ASRReliabilityScoringError,
        match="finite",
    ):
        ASRMatchedControlRobustnessEvidence(
            wer_differential=value,
            cer_differential=0.0,
            observed_pair_count=1,
            expected_pair_count=1,
        )


def test_wrong_gate_metric_identity_is_rejected():
    source = _complete_evidence()

    with pytest.raises(
        ASRReliabilityScoringError,
        match="gate metric identity",
    ):
        replace(
            source,
            missing_output_gate=_gate(
                metric_key="asr.wrong-gate",
            ),
        )


def test_changed_profile_is_rejected():
    changed = replace(
        ASR_RELIABILITY_PROFILE_V1,
        version="1.0.1",
    )

    with pytest.raises(
        ASRReliabilityScoringError,
        match="exact v1 profile",
    ):
        score_asr_reliability_v1(
            evidence=_complete_evidence(),
            profile=changed,
        )


def test_changed_scoring_definition_is_rejected():
    changed = replace(
        ASR_RELIABILITY_SCORING_V1,
        version="1.0.1",
    )

    with pytest.raises(
        ASRReliabilityScoringError,
        match="unsupported or changed",
    ):
        verify_asr_reliability_scoring_v1(changed)


def test_scorecard_explicitly_withholds_decision_authority():
    scorecard = score_asr_reliability_v1(evidence=_complete_evidence())
    boundary = scorecard.payload["evidence_boundary"]

    assert boundary == {
        "descriptive_scorecard_only": True,
        "aggregate_score_computed": True,
        "provisional_score_exposed": False,
        "missing_evidence_imputed": False,
        "qualification_threshold_applied": False,
        "model_winner_declared": False,
        "certification_issued": False,
        "production_qualified": False,
        "release_enforcement_eligible": False,
        "official_release_verdict_modified": False,
    }

    with pytest.raises(
        ASRReliabilityScoringError,
        match="no qualification threshold",
    ):
        scorecard.require_qualification_decision()

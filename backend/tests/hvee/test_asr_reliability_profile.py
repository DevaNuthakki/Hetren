from dataclasses import replace

import pytest

from app.adversarial_asr_human_external_voices_matched_control_metrics import (
    ASR_ADVERSARIAL_VOICES_METRIC_EQUALITY_ABSOLUTE_TOLERANCE as B7_TOLERANCE,
)
from app.adversarial_asr_human_external_voices_model_comparison import (
    ASR_ADVERSARIAL_VOICES_METRIC_EQUALITY_ABSOLUTE_TOLERANCE as B8_TOLERANCE,
)
from hvee.packs.asr import (
    ASR_RELIABILITY_METRIC_EQUALITY_ABSOLUTE_TOLERANCE,
    ASR_RELIABILITY_PROFILE_KEY,
    ASR_RELIABILITY_PROFILE_SCHEMA_VERSION,
    ASR_RELIABILITY_PROFILE_V1,
    ASR_RELIABILITY_PROFILE_V1_SHA256,
    ASR_RELIABILITY_PROFILE_VERSION,
    CRITICAL_IDENTIFIER_PRESERVED_METRIC,
    CRITICAL_NUMBER_PRESERVED_METRIC,
    CRITICAL_TERMINOLOGY_PRESERVED_METRIC,
    MATCHED_CONTROL_CER_NOISE_DEGRADATION_METRIC,
    MATCHED_CONTROL_CER_ROBUSTNESS_DIFFERENTIAL_METRIC,
    MATCHED_CONTROL_WER_NOISE_DEGRADATION_METRIC,
    MATCHED_CONTROL_WER_ROBUSTNESS_DIFFERENTIAL_METRIC,
    MISSING_OUTPUT_METRIC,
    NORMALIZED_CER_METRIC,
    NORMALIZED_WER_METRIC,
    UNEXPECTED_OUTPUT_METRIC,
    ASRReliabilityAggregationUse,
    ASRReliabilityMetricRole,
    ASRReliabilityProfileError,
    build_asr_reliability_profile_v1,
    verify_asr_reliability_profile_v1,
)


def _binding(metric):
    return ASR_RELIABILITY_PROFILE_V1.binding_for(
        metric_key=metric.key,
        metric_version=metric.version,
    )


def test_profile_has_exact_versioned_identity():
    profile = ASR_RELIABILITY_PROFILE_V1

    assert profile.key == ASR_RELIABILITY_PROFILE_KEY
    assert profile.version == ASR_RELIABILITY_PROFILE_VERSION
    assert profile.evaluation_type == "asr"
    assert profile.sha256 == ASR_RELIABILITY_PROFILE_V1_SHA256
    assert len(profile.sha256) == 64
    assert profile.payload["schema_version"] == (
        ASR_RELIABILITY_PROFILE_SCHEMA_VERSION
    )


def test_profile_build_is_deterministic_and_verifiable():
    rebuilt = build_asr_reliability_profile_v1()

    assert rebuilt is not ASR_RELIABILITY_PROFILE_V1
    assert rebuilt.payload == ASR_RELIABILITY_PROFILE_V1.payload
    assert rebuilt.sha256 == ASR_RELIABILITY_PROFILE_V1_SHA256
    assert verify_asr_reliability_profile_v1(rebuilt) is rebuilt


def test_profile_declares_fifteen_unique_metric_identities():
    bindings = ASR_RELIABILITY_PROFILE_V1.bindings
    identities = tuple(value.metric_identity for value in bindings)

    assert len(bindings) == 15
    assert len(set(identities)) == 15


def test_profile_separates_primary_diagnostics_and_gates():
    counts = {
        role: sum(
            binding.role == role
            for binding in ASR_RELIABILITY_PROFILE_V1.bindings
        )
        for role in ASRReliabilityMetricRole
    }

    assert counts == {
        ASRReliabilityMetricRole.PRIMARY: 5,
        ASRReliabilityMetricRole.SUPPORTING: 8,
        ASRReliabilityMetricRole.HARD_GATE: 2,
    }


@pytest.mark.parametrize(
    "metric",
    (
        NORMALIZED_WER_METRIC,
        NORMALIZED_CER_METRIC,
        MATCHED_CONTROL_WER_NOISE_DEGRADATION_METRIC,
        MATCHED_CONTROL_CER_NOISE_DEGRADATION_METRIC,
    ),
)
def test_error_rates_and_within_model_degradation_are_diagnostic_only(
    metric,
):
    binding = _binding(metric)

    assert binding.role == ASRReliabilityMetricRole.SUPPORTING
    assert (
        binding.aggregation_use
        == ASRReliabilityAggregationUse.DIAGNOSTIC_ONLY
    )


@pytest.mark.parametrize(
    "metric",
    (
        MATCHED_CONTROL_WER_ROBUSTNESS_DIFFERENTIAL_METRIC,
        MATCHED_CONTROL_CER_ROBUSTNESS_DIFFERENTIAL_METRIC,
        CRITICAL_NUMBER_PRESERVED_METRIC,
        CRITICAL_IDENTIFIER_PRESERVED_METRIC,
        CRITICAL_TERMINOLOGY_PRESERVED_METRIC,
    ),
)
def test_distinctive_and_critical_fidelity_metrics_are_primary(metric):
    binding = _binding(metric)

    assert binding.role == ASRReliabilityMetricRole.PRIMARY
    assert (
        binding.aggregation_use
        == ASRReliabilityAggregationUse.COMPONENT_CANDIDATE
    )


def test_correlated_robustness_differentials_share_one_group():
    wer = _binding(
        MATCHED_CONTROL_WER_ROBUSTNESS_DIFFERENTIAL_METRIC
    )
    cer = _binding(
        MATCHED_CONTROL_CER_ROBUSTNESS_DIFFERENTIAL_METRIC
    )

    assert wer.aggregation_group == "matched_control_robustness"
    assert cer.aggregation_group == wer.aggregation_group
    assert wer.engineer_label == "Hetren Robustness Differential (WER)"
    assert cer.engineer_label == "Hetren Robustness Differential (CER)"


@pytest.mark.parametrize(
    "metric",
    (
        MISSING_OUTPUT_METRIC,
        UNEXPECTED_OUTPUT_METRIC,
    ),
)
def test_output_integrity_failures_are_gate_only(metric):
    binding = _binding(metric)

    assert binding.role == ASRReliabilityMetricRole.HARD_GATE
    assert (
        binding.aggregation_use
        == ASRReliabilityAggregationUse.GATE_ONLY
    )


def test_metric_equality_matches_b7_and_b8():
    assert ASR_RELIABILITY_METRIC_EQUALITY_ABSOLUTE_TOLERANCE == 1e-12
    assert B7_TOLERANCE == (
        ASR_RELIABILITY_METRIC_EQUALITY_ABSOLUTE_TOLERANCE
    )
    assert B8_TOLERANCE == (
        ASR_RELIABILITY_METRIC_EQUALITY_ABSOLUTE_TOLERANCE
    )
    assert ASR_RELIABILITY_PROFILE_V1.payload["methodology"][
        "metric_equality"
    ] == {
        "absolute_tolerance": 1e-12,
        "relative_tolerance": 0.0,
        "canonical_zero": True,
    }


def test_profile_explicitly_withholds_score_and_decision_authority():
    boundary = ASR_RELIABILITY_PROFILE_V1.payload[
        "evidence_boundary"
    ]

    assert boundary == {
        "declarative_profile_only": True,
        "metric_values_computed": False,
        "aggregate_score_computed": False,
        "score_transform_defined": False,
        "metric_weights_defined": False,
        "missing_evidence_policy_defined": False,
        "qualification_threshold_applied": False,
        "model_verdict_issued": False,
        "production_qualified": False,
        "release_decision_issued": False,
    }

    with pytest.raises(
        ASRReliabilityProfileError,
        match="no aggregate score",
    ):
        ASR_RELIABILITY_PROFILE_V1.require_aggregate_score()

    with pytest.raises(
        ASRReliabilityProfileError,
        match="does not apply qualification",
    ):
        ASR_RELIABILITY_PROFILE_V1.require_qualification_decision()


def test_engineer_facing_metadata_is_complete():
    for binding in ASR_RELIABILITY_PROFILE_V1.bindings:
        assert binding.engineer_label == binding.engineer_label.strip()
        assert binding.engineer_interpretation == (
            binding.engineer_interpretation.strip()
        )
        assert binding.engineer_label
        assert binding.engineer_interpretation
        assert binding.aggregation_group


def test_duplicate_metric_identity_is_rejected():
    profile = ASR_RELIABILITY_PROFILE_V1

    with pytest.raises(
        ASRReliabilityProfileError,
        match="metric identities must be unique",
    ):
        replace(
            profile,
            bindings=(
                *profile.bindings,
                profile.bindings[0],
            ),
        )


def test_role_and_aggregation_use_mismatch_is_rejected():
    with pytest.raises(
        ASRReliabilityProfileError,
        match="role and aggregation use",
    ):
        replace(
            ASR_RELIABILITY_PROFILE_V1.bindings[0],
            aggregation_use=(
                ASRReliabilityAggregationUse.COMPONENT_CANDIDATE
            ),
        )


def test_changed_profile_is_rejected_by_exact_verifier():
    changed = replace(
        ASR_RELIABILITY_PROFILE_V1,
        version="1.0.1",
    )

    with pytest.raises(
        ASRReliabilityProfileError,
        match="unsupported or changed",
    ):
        verify_asr_reliability_profile_v1(changed)


def test_unknown_metric_identity_is_rejected():
    with pytest.raises(
        ASRReliabilityProfileError,
        match="not bound",
    ):
        ASR_RELIABILITY_PROFILE_V1.binding_for(
            metric_key="asr.unknown",
            metric_version="1.0.0",
        )

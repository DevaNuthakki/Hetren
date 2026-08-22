from dataclasses import replace
import math

import pytest

from hvee.core.paired_assurance import (
    PairedIntervalMethod,
    PairedIntervalPolicy,
)
from hvee.packs.asr.critical_number_private_statistics import (
    CRITICAL_NUMBER_PRIVATE_MULTIPLICITY_CONTROL_KEY,
    CRITICAL_NUMBER_PRIVATE_MULTIPLICITY_CONTROL_VERSION,
)
from hvee.packs.asr.release_assurance_policy import (
    ASRMatchedReleaseAssurancePolicyV1,
)
from hvee.packs.asr import (
    ASR_CRITICAL_INTEGRITY_CLAIM_COUNT_V1,
    ASR_CRITICAL_INTEGRITY_CONFIDENCE_METHOD_KEY,
    ASR_CRITICAL_INTEGRITY_CONFIDENCE_METHOD_VERSION,
    ASR_RELIABILITY_PROFILE_V1_SHA256,
    ASR_RELIABILITY_QUALIFICATION_POLICY_KEY,
    ASR_RELIABILITY_QUALIFICATION_POLICY_SCHEMA_VERSION,
    ASR_RELIABILITY_QUALIFICATION_POLICY_VERSION,
    ASR_RELIABILITY_RATE_SCALE,
    ASR_RELIABILITY_SCORING_V1_SHA256,
    ASRCriticalIntegrityConfidencePolicyV1,
    ASRReliabilityQualificationPolicyError,
    build_asr_reliability_qualification_policy_v1,
    verify_asr_reliability_qualification_policy_v1,
)


def _matched_assurance() -> ASRMatchedReleaseAssurancePolicyV1:
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


def _critical_confidence() -> ASRCriticalIntegrityConfidencePolicyV1:
    return ASRCriticalIntegrityConfidencePolicyV1(
        familywise_confidence_level_ppm=950_000,
        minimum_conclusive_observations_per_group=30,
        minimum_preservation_lower_bound_ppm=900_000,
    )


def _policy():
    return build_asr_reliability_qualification_policy_v1(
        minimum_hetren_reliability_index=90.0,
        minimum_reliability_performance_index=90.0,
        minimum_evidence_assurance_index=100.0,
        minimum_operational_fitness_index=95.0,
        minimum_matched_control_robustness_score=90.0,
        minimum_critical_integrity_group_score=100.0,
        minimum_matched_control_pairs=16,
        matched_release_assurance=_matched_assurance(),
        critical_integrity_confidence=_critical_confidence(),
    )


def test_policy_has_exact_versioned_identity_and_bindings():
    policy = _policy()

    assert policy.key == ASR_RELIABILITY_QUALIFICATION_POLICY_KEY
    assert policy.version == ASR_RELIABILITY_QUALIFICATION_POLICY_VERSION
    assert policy.payload["schema_version"] == (
        ASR_RELIABILITY_QUALIFICATION_POLICY_SCHEMA_VERSION
    )
    assert policy.payload["bindings"] == {
        "profile": {
            "key": "hetren.asr.reliability-profile",
            "version": "1.0.0",
            "sha256": ASR_RELIABILITY_PROFILE_V1_SHA256,
        },
        "scoring": {
            "key": "hetren.asr.reliability-scoring",
            "version": "1.0.0",
            "sha256": ASR_RELIABILITY_SCORING_V1_SHA256,
        },
    }
    assert verify_asr_reliability_qualification_policy_v1(policy) is policy


def test_policy_records_every_score_floor_without_hidden_defaults():
    floors = _policy().payload["scorecard_requirements"]["score_floors"]

    assert floors == {
        "hetren_reliability_index": 90.0,
        "reliability_performance_index": 90.0,
        "evidence_assurance_index": 100.0,
        "operational_fitness_index": 95.0,
        "matched_control_robustness": 90.0,
        "each_critical_integrity_group": 100.0,
    }


def test_policy_requires_complete_scorecard_and_clear_hard_gates():
    requirements = _policy().payload["scorecard_requirements"]

    assert requirements["required_maturity_status"] == (
        "complete_descriptive_evidence"
    )
    assert requirements["required_gate_status"] == "clear"


def test_matched_assurance_configuration_is_fully_snapshotted():
    matched = _policy().payload["statistical_assurance"]["matched_release"]

    assert matched == {
        "key": "hetren.asr.matched-release-assurance",
        "version": "1.0.0",
        "interval": {
            "method": "paired_bootstrap_percentile_v1",
            "confidence_level": 0.95,
            "minimum_usable_pairs": 16,
            "resamples": 10_000,
            "random_seed": 20_260_822,
        },
        "normalized_wer_noninferiority_margin": 0.02,
        "normalized_cer_noninferiority_margin": 0.01,
    }


def test_critical_integrity_confidence_is_simultaneous_and_versioned():
    critical = _policy().payload["statistical_assurance"][
        "critical_integrity"
    ]

    assert critical["method"] == {
        "key": ASR_CRITICAL_INTEGRITY_CONFIDENCE_METHOD_KEY,
        "version": ASR_CRITICAL_INTEGRITY_CONFIDENCE_METHOD_VERSION,
        "interval_side": "one_sided_lower",
        "distribution": "binomial",
    }
    assert critical["multiplicity_control"] == {
        "key": CRITICAL_NUMBER_PRIVATE_MULTIPLICITY_CONTROL_KEY,
        "version": CRITICAL_NUMBER_PRIVATE_MULTIPLICITY_CONTROL_VERSION,
        "family": [
            "critical_number_integrity",
            "critical_identifier_integrity",
            "critical_terminology_integrity",
        ],
        "claim_count": ASR_CRITICAL_INTEGRITY_CLAIM_COUNT_V1,
    }
    assert critical["rate_scale"] == ASR_RELIABILITY_RATE_SCALE
    assert critical["familywise_confidence_level_ppm"] == 950_000
    assert critical["minimum_conclusive_observations_per_group"] == 30
    assert critical["minimum_preservation_lower_bound_ppm"] == 900_000
    assert critical["insufficient_minimum_behavior"] == (
        "insufficient_evidence"
    )


def test_policy_maps_to_existing_universal_four_state_kernel():
    mapping = _policy().payload["decision_mapping"]

    assert mapping == {
        "kernel": "hvee.core.decision.decide",
        "invalid_integrity": "invalid",
        "known_hard_gate_violation": "fail",
        "insufficient_support_or_confidence": "inconclusive",
        "contradicted_qualification_claim": "fail",
        "unresolved_qualification_claim": "inconclusive",
        "supported_qualification_claim": "pass",
    }


def test_policy_payload_and_digest_are_deterministic():
    first = _policy()
    second = _policy()

    assert first is not second
    assert first.payload == second.payload
    assert first.sha256 == second.sha256
    assert len(first.sha256) == 64


def test_threshold_change_changes_policy_digest():
    original = _policy()
    changed = replace(
        original,
        minimum_hetren_reliability_index=91.0,
    )

    assert changed.payload != original.payload
    assert changed.sha256 != original.sha256


@pytest.mark.parametrize(
    "value",
    (-0.01, 100.01, math.nan, math.inf, True, "90"),
)
def test_invalid_score_floors_are_rejected(value):
    with pytest.raises(
        ASRReliabilityQualificationPolicyError,
        match="between 0 and 100",
    ):
        replace(
            _policy(),
            minimum_hetren_reliability_index=value,
        )


@pytest.mark.parametrize("value", (0, 1, -1, True, 2.5))
def test_invalid_matched_control_minimum_is_rejected(value):
    with pytest.raises(ASRReliabilityQualificationPolicyError):
        replace(
            _policy(),
            minimum_matched_control_pairs=value,
        )


@pytest.mark.parametrize(
    "value",
    (0, ASR_RELIABILITY_RATE_SCALE, -1, True, 950_000.0),
)
def test_invalid_familywise_confidence_is_rejected(value):
    with pytest.raises(ASRReliabilityQualificationPolicyError):
        ASRCriticalIntegrityConfidencePolicyV1(
            familywise_confidence_level_ppm=value,
            minimum_conclusive_observations_per_group=30,
            minimum_preservation_lower_bound_ppm=900_000,
        )


@pytest.mark.parametrize("value", (0, -1, True, 30.0))
def test_invalid_critical_minimum_support_is_rejected(value):
    with pytest.raises(ASRReliabilityQualificationPolicyError):
        ASRCriticalIntegrityConfidencePolicyV1(
            familywise_confidence_level_ppm=950_000,
            minimum_conclusive_observations_per_group=value,
            minimum_preservation_lower_bound_ppm=900_000,
        )


@pytest.mark.parametrize(
    "value",
    (-1, ASR_RELIABILITY_RATE_SCALE + 1, True, 900_000.0),
)
def test_invalid_critical_lower_bound_is_rejected(value):
    with pytest.raises(ASRReliabilityQualificationPolicyError):
        ASRCriticalIntegrityConfidencePolicyV1(
            familywise_confidence_level_ppm=950_000,
            minimum_conclusive_observations_per_group=30,
            minimum_preservation_lower_bound_ppm=value,
        )


def test_wrong_nested_matched_assurance_type_is_rejected():
    with pytest.raises(
        ASRReliabilityQualificationPolicyError,
        match="matched release assurance",
    ):
        replace(
            _policy(),
            matched_release_assurance=None,
        )


def test_wrong_nested_critical_confidence_type_is_rejected():
    with pytest.raises(
        ASRReliabilityQualificationPolicyError,
        match="critical-integrity confidence",
    ):
        replace(
            _policy(),
            critical_integrity_confidence=None,
        )


def test_policy_explicitly_withholds_evaluation_and_release_authority():
    policy = _policy()
    boundary = policy.payload["evidence_boundary"]

    assert boundary == {
        "policy_definition_only": True,
        "scorecard_evaluated": False,
        "confidence_bounds_computed": False,
        "qualification_threshold_applied": False,
        "decision_kernel_called": False,
        "model_verdict_issued": False,
        "certification_issued": False,
        "production_qualified": False,
        "release_enforcement_eligible": False,
        "official_release_verdict_modified": False,
    }

    with pytest.raises(
        ASRReliabilityQualificationPolicyError,
        match="no qualification verdict",
    ):
        policy.require_qualification_decision()


def test_verifier_rejects_non_policy_input():
    with pytest.raises(
        ASRReliabilityQualificationPolicyError,
        match="requires policy v1",
    ):
        verify_asr_reliability_qualification_policy_v1(object())

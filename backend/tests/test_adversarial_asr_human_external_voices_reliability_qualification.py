from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest

from app import (
    adversarial_asr_human_external_voices_reliability_qualification
    as qualification_module,
)
from app.adversarial_asr_human_external_voices_reliability_qualification import (
    ASR_ADVERSARIAL_VOICES_RELIABILITY_QUALIFICATION_KEY,
    ASR_ADVERSARIAL_VOICES_RELIABILITY_QUALIFICATION_SCHEMA_VERSION,
    ASR_ADVERSARIAL_VOICES_RELIABILITY_QUALIFICATION_VERSION,
    ASRAdversarialVOiCESReliabilityQualificationBundle,
    ASRAdversarialVOiCESReliabilityQualificationError,
    evaluate_asr_adversarial_voices_reliability_qualification_v1,
)


class _FakePerformance:
    def __init__(self):
        self.matched_control_robustness = object()
        self.critical_number_integrity = None
        self.critical_identifier_integrity = None
        self.critical_terminology_integrity = None


class _FakeScoringEvidence:
    def __init__(self):
        self.performance = _FakePerformance()
        self.reproducibility = None


class _FakePolicy:
    key = "policy-key"
    version = "1.0.0"
    sha256 = "a" * 64

    def __init__(self, matched_release_assurance):
        self.matched_release_assurance = matched_release_assurance


class _FakeProjection:
    sha256 = "b" * 64
    execution = SimpleNamespace(sha256="c" * 64)

    def __init__(self, matched_release_assurance_policy):
        self.scoring_evidence = _FakeScoringEvidence()
        self.matched_assurance = object()
        self.matched_release_assurance_policy = (
            matched_release_assurance_policy
        )
        self.baseline_run_id = 101
        self.candidate_run_id = 202

    @property
    def payload(self):
        return {
            "runs": {
                "baseline": {
                    "evaluation_run_id": self.baseline_run_id,
                    "model_key": "small.en",
                },
                "candidate": {
                    "evaluation_run_id": self.candidate_run_id,
                    "model_key": "large-v3-turbo",
                },
            },
            "evidence_boundary": {
                "qualification_threshold_applied": False,
            },
        }


class _FakeQualification:
    sha256 = "d" * 64
    decision = SimpleNamespace(
        verdict=SimpleNamespace(value="inconclusive"),
        reason=SimpleNamespace(value="insufficient_evidence"),
    )

    @property
    def payload(self):
        return {
            "decision": {
                "inputs": {
                    "integrity": "valid",
                    "critical": "clear",
                    "evidence": "insufficient",
                    "claim": "unresolved",
                },
                "verdict": self.decision.verdict.value,
                "reason": self.decision.reason.value,
            },
            "support": {
                "scorecard": {"sufficient": False},
                "critical_integrity": {"sufficient": False},
            },
            "evidence_boundary": {
                "model_qualification_verdict_issued": True,
                "production_qualified": False,
            },
        }


@pytest.fixture
def composed_values(monkeypatch):
    matched_policy = object()
    policy = _FakePolicy(matched_policy)
    projection = _FakeProjection(matched_policy)
    qualification = _FakeQualification()

    monkeypatch.setattr(
        qualification_module,
        "_reverify_policy",
        lambda value: value,
    )
    monkeypatch.setattr(
        qualification_module,
        "_reverify_projection",
        lambda *, value, policy: value,
    )
    monkeypatch.setattr(
        qualification_module,
        "_reverify_qualification",
        lambda *, value, projection, policy: value,
    )

    return policy, projection, qualification


def test_constants_are_versioned_and_namespaced():
    assert ASR_ADVERSARIAL_VOICES_RELIABILITY_QUALIFICATION_SCHEMA_VERSION == 1
    assert ASR_ADVERSARIAL_VOICES_RELIABILITY_QUALIFICATION_VERSION == "1.0.0"
    assert ASR_ADVERSARIAL_VOICES_RELIABILITY_QUALIFICATION_KEY.startswith(
        "hetren.asr."
    )


def test_public_evaluator_composes_exact_projection_and_policy(
    monkeypatch,
    composed_values,
):
    policy, projection, qualification = composed_values
    execution = object()
    observed = {}

    def project(**kwargs):
        observed["projection"] = kwargs
        return projection

    def evaluate(**kwargs):
        observed["qualification"] = kwargs
        return qualification

    monkeypatch.setattr(
        qualification_module,
        "project_asr_adversarial_voices_reliability_evidence_v1",
        project,
    )
    monkeypatch.setattr(
        qualification_module,
        "evaluate_asr_reliability_qualification_v1",
        evaluate,
    )

    bundle = evaluate_asr_adversarial_voices_reliability_qualification_v1(
        execution=execution,
        baseline_run_id=101,
        candidate_run_id=202,
        policy=policy,
    )

    assert observed["projection"] == {
        "execution": execution,
        "baseline_run_id": 101,
        "candidate_run_id": 202,
        "matched_release_assurance_policy": (
            policy.matched_release_assurance
        ),
    }
    assert observed["qualification"] == {
        "scoring_evidence": projection.scoring_evidence,
        "matched_assurance": projection.matched_assurance,
        "policy": policy,
    }
    assert bundle.projection is projection
    assert bundle.qualification is qualification


def test_bundle_payload_binds_every_governed_stage(composed_values):
    policy, projection, qualification = composed_values
    bundle = ASRAdversarialVOiCESReliabilityQualificationBundle(
        projection=projection,
        policy=policy,
        qualification=qualification,
    )

    assert bundle.payload["upstream"] == {
        "b9_execution_sha256": "c" * 64,
        "b11c_projection": {
            "key": (
                "hetren.asr.adversarial-human-external-voices-"
                "reliability-evidence-projection"
            ),
            "version": "1.0.0",
            "sha256": "b" * 64,
        },
        "b11b_qualification": {
            "key": "hetren.asr.reliability-qualification-result",
            "version": "1.0.0",
            "sha256": "d" * 64,
        },
    }
    assert bundle.payload["bindings"]["policy"]["sha256"] == "a" * 64
    assert bundle.payload["runs"] == projection.payload["runs"]
    assert bundle.payload["decision"]["verdict"] == "inconclusive"
    assert bundle.payload["support"]["critical_integrity"] == {
        "sufficient": False,
    }
    assert bundle.payload["projection"] == projection.payload
    assert bundle.payload["qualification"] == qualification.payload


def test_bundle_is_deterministic_and_non_authoritative(composed_values):
    policy, projection, qualification = composed_values
    first = ASRAdversarialVOiCESReliabilityQualificationBundle(
        projection=projection,
        policy=policy,
        qualification=qualification,
    )
    second = ASRAdversarialVOiCESReliabilityQualificationBundle(
        projection=projection,
        policy=policy,
        qualification=qualification,
    )

    assert first.payload == second.payload
    assert first.sha256 == second.sha256
    assert len(first.sha256) == 64
    boundary = first.payload["evidence_boundary"]
    assert boundary["non_authoritative_model_qualification_verdict_issued"]
    assert not boundary["critical_content_qualification_evidence_claimed"]
    assert not boundary["model_winner_declared"]
    assert not boundary["certification_issued"]
    assert not boundary["production_qualified"]
    assert not boundary["release_enforcement_eligible"]
    assert not boundary["official_release_verdict_modified"]

    with pytest.raises(
        ASRAdversarialVOiCESReliabilityQualificationError,
        match="does not certify",
    ):
        first.require_certification()


def test_bundle_rejects_mismatched_matched_assurance_policy(
    monkeypatch,
    composed_values,
):
    policy, projection, qualification = composed_values
    projection.matched_release_assurance_policy = object()

    with pytest.raises(
        ASRAdversarialVOiCESReliabilityQualificationError,
        match="does not match",
    ):
        ASRAdversarialVOiCESReliabilityQualificationBundle(
            projection=projection,
            policy=policy,
            qualification=qualification,
        )


def test_bundle_rejects_evidence_outside_general_voices_scope(
    composed_values,
):
    policy, projection, qualification = composed_values
    projection.scoring_evidence.performance.critical_number_integrity = object()

    with pytest.raises(
        ASRAdversarialVOiCESReliabilityQualificationError,
        match="cannot claim critical-content",
    ):
        ASRAdversarialVOiCESReliabilityQualificationBundle(
            projection=projection,
            policy=policy,
            qualification=qualification,
        )


def test_real_reverification_helpers_fail_closed():
    with pytest.raises(
        ASRAdversarialVOiCESReliabilityQualificationError,
        match="exact B11A policy",
    ):
        qualification_module._reverify_policy(object())

    with pytest.raises(
        ASRAdversarialVOiCESReliabilityQualificationError,
        match="exact B11C projection",
    ):
        qualification_module._reverify_projection(
            value=object(),
            policy=object(),
        )

    with pytest.raises(
        ASRAdversarialVOiCESReliabilityQualificationError,
        match="exact B11B result",
    ):
        qualification_module._reverify_qualification(
            value=object(),
            projection=object(),
            policy=object(),
        )


def test_bundle_is_frozen(composed_values):
    policy, projection, qualification = composed_values
    bundle = ASRAdversarialVOiCESReliabilityQualificationBundle(
        projection=projection,
        policy=policy,
        qualification=qualification,
    )

    with pytest.raises(FrozenInstanceError):
        bundle.policy = object()

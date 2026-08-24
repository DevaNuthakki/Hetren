from __future__ import annotations

from dataclasses import dataclass, FrozenInstanceError
from types import SimpleNamespace

import pytest

from app import (
    adversarial_asr_human_external_voices_reliability_projection
    as projection_module,
)
from app.adversarial_asr_human_external_voices_reliability_projection import (
    ASR_ADVERSARIAL_VOICES_RELIABILITY_PROJECTED_CASE_COUNT,
    ASR_ADVERSARIAL_VOICES_RELIABILITY_PROJECTED_EXECUTION_COUNT,
    ASR_ADVERSARIAL_VOICES_RELIABILITY_PROJECTED_OBSERVATION_COUNT,
    ASR_ADVERSARIAL_VOICES_RELIABILITY_PROJECTION_KEY,
    ASR_ADVERSARIAL_VOICES_RELIABILITY_PROJECTION_SCHEMA_VERSION,
    ASR_ADVERSARIAL_VOICES_RELIABILITY_PROJECTION_VERSION,
    ASRAdversarialVOiCESReliabilityProjectionBundle,
    ASRAdversarialVOiCESReliabilityProjectionError,
    project_asr_adversarial_voices_reliability_evidence_v1,
)
from hvee.core.contracts import ObservationStatus
from hvee.core.paired_assurance import (
    PairedIntervalMethod,
    PairedIntervalPolicy,
)
from hvee.packs.asr.adversarial_execution_evidence import (
    ASRAdversarialExecutionStatus,
)
from hvee.packs.asr.normalized_evaluation import (
    NORMALIZED_CER_METRIC,
    NORMALIZED_WER_METRIC,
    evaluate_normalized_transcript_pair,
)
from hvee.packs.asr.release_assurance_policy import (
    ASRMatchedReleaseAssurancePolicyV1,
)
from hvee.packs.asr.transcript_integrity import (
    MISSING_OUTPUT_METRIC,
    UNEXPECTED_OUTPUT_METRIC,
)


BASELINE_RUN_ID = 4101
CANDIDATE_RUN_ID = 4102


def _matched_policy() -> ASRMatchedReleaseAssurancePolicyV1:
    return ASRMatchedReleaseAssurancePolicyV1(
        interval=PairedIntervalPolicy(
            method=PairedIntervalMethod.BOOTSTRAP_PERCENTILE_V1,
            confidence_level=0.95,
            minimum_usable_pairs=16,
            resamples=10_000,
            random_seed=20_260_823,
        ),
        normalized_wer_noninferiority_margin=0.10,
        normalized_cer_noninferiority_margin=0.10,
    )


def _evaluation(*, generated: str):
    return evaluate_normalized_transcript_pair(
        reference_text="alpha beta gamma delta",
        generated_text=generated,
    )


@dataclass(frozen=True)
class _FakeCase:
    case_id: str
    baseline: object
    candidate: object


class _FakeComparison:
    def __init__(self, *, missing_candidate_index: int | None = None):
        cases = []

        for index in range(1, 33):
            candidate_text = (
                ""
                if index == missing_candidate_index
                else "alpha beta gamma delta"
            )
            cases.append(
                _FakeCase(
                    case_id=f"voices-case-{index:02d}",
                    baseline=SimpleNamespace(
                        evaluation=_evaluation(
                            generated="alpha beta gamma delta"
                        )
                    ),
                    candidate=SimpleNamespace(
                        evaluation=_evaluation(generated=candidate_text)
                    ),
                )
            )

        self.cases = tuple(cases)
        self.pairs = tuple(object() for _ in range(16))
        self.sha256 = "8" * 64

    @property
    def aggregate(self):
        return {
            "pair_noise_degradation_macro_mean": {
                "candidate_minus_baseline": {
                    "wer": 0.03,
                    "cer": 0.02,
                }
            }
        }


class _FakeExecution:
    def __init__(self, *, comparison=None, status_counts=None):
        self._comparison = comparison or _FakeComparison()
        counts = status_counts or {
            status.value: (
                32
                if status == ASRAdversarialExecutionStatus.COMPLETED
                else 0
            )
            for status in ASRAdversarialExecutionStatus
        }
        baseline_definition = SimpleNamespace(
            campaign_id="voices-small-en",
            campaign_version="1.0.0",
            provider_key="faster_whisper",
            model_key="small.en",
        )
        candidate_definition = SimpleNamespace(
            campaign_id="voices-large-v3-turbo",
            campaign_version="1.0.0",
            provider_key="faster_whisper",
            model_key="large-v3-turbo",
        )
        self.baseline_campaign = SimpleNamespace(
            sha256="1" * 64,
            status_counts=dict(counts),
            campaign=SimpleNamespace(definition=baseline_definition),
        )
        self.candidate_campaign = SimpleNamespace(
            sha256="2" * 64,
            status_counts=dict(counts),
            campaign=SimpleNamespace(definition=candidate_definition),
        )
        self.baseline_metrics = SimpleNamespace(sha256="3" * 64)
        self.candidate_metrics = SimpleNamespace(sha256="4" * 64)
        self.matched_control_suite_sha256 = "5" * 64
        self.sha256 = "6" * 64

    def require_complete_comparison(self):
        return self._comparison


@pytest.fixture
def bypass_b9_reverification(monkeypatch):
    monkeypatch.setattr(
        projection_module,
        "_reverify_execution",
        lambda value: value,
    )


def _projection(
    *,
    execution=None,
) -> ASRAdversarialVOiCESReliabilityProjectionBundle:
    return project_asr_adversarial_voices_reliability_evidence_v1(
        execution=execution or _FakeExecution(),
        baseline_run_id=BASELINE_RUN_ID,
        candidate_run_id=CANDIDATE_RUN_ID,
        matched_release_assurance_policy=_matched_policy(),
    )


def test_projection_builds_exact_matched_evidence_and_assurance(
    bypass_b9_reverification,
):
    projected = _projection()

    assert len(projected.comparison.cases) == (
        ASR_ADVERSARIAL_VOICES_RELIABILITY_PROJECTED_CASE_COUNT
    )
    assert projected.declared_test_case_ids == tuple(range(1, 33))
    assert projected.case_id_by_test_case_id[0] == "voices-case-01"
    assert projected.case_id_by_test_case_id[-1] == "voices-case-32"

    records = projected.observation_records
    assert len(records) == (
        ASR_ADVERSARIAL_VOICES_RELIABILITY_PROJECTED_OBSERVATION_COUNT
    )
    assert {value.evaluation_run_id for value in records} == {
        BASELINE_RUN_ID,
        CANDIDATE_RUN_ID,
    }
    assert {value.metric_key for value in records} == {
        NORMALIZED_WER_METRIC.key,
        NORMALIZED_CER_METRIC.key,
    }
    assert all(value.status == ObservationStatus.SUCCESS for value in records)

    assert projected.cohorts.total_cases == 32
    assert projected.cohorts.complete is True
    assert projected.cohorts.integrity_valid is True
    assert projected.matched_assurance.baseline_run_id == BASELINE_RUN_ID
    assert projected.matched_assurance.candidate_run_id == CANDIDATE_RUN_ID
    assert projected.matched_assurance.declared_test_case_ids == tuple(
        range(1, 33)
    )


def test_projection_maps_robustness_operations_assurance_and_gates(
    bypass_b9_reverification,
):
    evidence = _projection().scoring_evidence
    performance = evidence.performance
    robustness = performance.matched_control_robustness

    assert robustness is not None
    assert robustness.wer_differential == 0.03
    assert robustness.cer_differential == 0.02
    assert robustness.observed_pair_count == 16
    assert robustness.expected_pair_count == 16
    assert performance.critical_number_integrity is None
    assert performance.critical_identifier_integrity is None
    assert performance.critical_terminology_integrity is None

    assert evidence.assurance.profile_and_evaluators_verified is True
    assert evidence.assurance.input_provenance_verified is True
    assert evidence.assurance.runtime_identity_verified is True
    assert evidence.assurance.reproducibility_verified is None

    for _key, value in evidence.operational.values:
        assert value is not None
        assert value.successful_count == (
            ASR_ADVERSARIAL_VOICES_RELIABILITY_PROJECTED_EXECUTION_COUNT
        )
        assert value.observed_count == (
            ASR_ADVERSARIAL_VOICES_RELIABILITY_PROJECTED_EXECUTION_COUNT
        )
        assert value.expected_count == (
            ASR_ADVERSARIAL_VOICES_RELIABILITY_PROJECTED_EXECUTION_COUNT
        )

    assert evidence.missing_output_gate is not None
    assert evidence.missing_output_gate.metric_key == MISSING_OUTPUT_METRIC.key
    assert evidence.missing_output_gate.violation_count == 0
    assert evidence.unexpected_output_gate is not None
    assert evidence.unexpected_output_gate.metric_key == (
        UNEXPECTED_OUTPUT_METRIC.key
    )
    assert evidence.unexpected_output_gate.violation_count == 0


def test_projection_detects_missing_output_without_promoting_critical_evidence(
    bypass_b9_reverification,
):
    projected = _projection(
        execution=_FakeExecution(
            comparison=_FakeComparison(missing_candidate_index=7)
        )
    )
    evidence = projected.scoring_evidence

    assert evidence.missing_output_gate is not None
    assert evidence.missing_output_gate.violation_count == 1
    assert evidence.unexpected_output_gate is not None
    assert evidence.unexpected_output_gate.violation_count == 0
    assert evidence.performance.critical_number_integrity is None
    assert evidence.performance.critical_identifier_integrity is None
    assert evidence.performance.critical_terminology_integrity is None


def test_operational_projection_preserves_each_failure_category():
    per_campaign = {
        ASRAdversarialExecutionStatus.COMPLETED.value: 28,
        ASRAdversarialExecutionStatus.FAILED.value: 1,
        ASRAdversarialExecutionStatus.TIMED_OUT.value: 1,
        ASRAdversarialExecutionStatus.CANCELLED.value: 1,
        ASRAdversarialExecutionStatus.INVALID.value: 1,
    }
    operational = projection_module._operational_evidence(
        _FakeExecution(status_counts=per_campaign)
    )

    assert operational.execution_completion.successful_count == 56
    assert operational.timeout_free.successful_count == 62
    assert operational.cancellation_free.successful_count == 62
    assert operational.provider_error_free.successful_count == 62
    assert all(
        value.observed_count == 64
        and value.expected_count == 64
        for _key, value in operational.values
    )


@pytest.mark.parametrize(
    ("baseline_run_id", "candidate_run_id"),
    (
        (0, 2),
        (1, 0),
        (-1, 2),
        (1, -2),
        (True, 2),
        (1, True),
        (5, 5),
    ),
)
def test_projection_rejects_invalid_or_ambiguous_run_identity(
    bypass_b9_reverification,
    baseline_run_id,
    candidate_run_id,
):
    with pytest.raises(ASRAdversarialVOiCESReliabilityProjectionError):
        ASRAdversarialVOiCESReliabilityProjectionBundle(
            execution=_FakeExecution(),
            baseline_run_id=baseline_run_id,
            candidate_run_id=candidate_run_id,
            matched_release_assurance_policy=_matched_policy(),
        )


def test_projection_rejects_non_b9_input_without_test_bypass():
    with pytest.raises(
        ASRAdversarialVOiCESReliabilityProjectionError,
        match="exact B9 execution",
    ):
        project_asr_adversarial_voices_reliability_evidence_v1(
            execution=object(),
            baseline_run_id=BASELINE_RUN_ID,
            candidate_run_id=CANDIDATE_RUN_ID,
            matched_release_assurance_policy=_matched_policy(),
        )


def test_projection_requires_explicit_matched_assurance_policy(
    bypass_b9_reverification,
):
    with pytest.raises(
        ASRAdversarialVOiCESReliabilityProjectionError,
        match="explicit matched release-assurance policy",
    ):
        project_asr_adversarial_voices_reliability_evidence_v1(
            execution=_FakeExecution(),
            baseline_run_id=BASELINE_RUN_ID,
            candidate_run_id=CANDIDATE_RUN_ID,
            matched_release_assurance_policy=None,
        )


def test_projection_payload_is_deterministic_and_non_authoritative(
    bypass_b9_reverification,
):
    projected = _projection()
    payload = projected.payload

    assert payload["schema_version"] == (
        ASR_ADVERSARIAL_VOICES_RELIABILITY_PROJECTION_SCHEMA_VERSION
    )
    assert payload["artifact"] == {
        "key": ASR_ADVERSARIAL_VOICES_RELIABILITY_PROJECTION_KEY,
        "version": ASR_ADVERSARIAL_VOICES_RELIABILITY_PROJECTION_VERSION,
        "type": "voices_two_model_reliability_evidence_projection",
    }
    assert payload["population"]["case_count"] == 32
    assert payload["population"]["pair_count"] == 16
    assert payload["population"]["execution_count"] == 64
    assert payload["population"]["observation_record_count"] == 128
    assert payload["methodology"]["critical_content_projection"].startswith(
        "withheld_"
    )
    assert payload["evidence_boundary"] == {
        "development_evidence_only": True,
        "b9_execution_reverified": True,
        "complete_b8_comparison_required": True,
        "normalized_observations_projected": True,
        "matched_release_assurance_computed": True,
        "reliability_scoring_evidence_projected": True,
        "critical_content_qualification_evidence_claimed": False,
        "qualification_threshold_applied": False,
        "model_qualification_verdict_issued": False,
        "model_winner_declared": False,
        "certification_issued": False,
        "production_qualified": False,
        "release_enforcement_eligible": False,
        "official_release_verdict_modified": False,
    }
    assert projected.sha256 == _projection().sha256

    with pytest.raises(
        ASRAdversarialVOiCESReliabilityProjectionError,
        match="no qualification verdict",
    ):
        projected.require_qualification_verdict()


def test_projection_bundle_is_frozen(
    bypass_b9_reverification,
):
    projected = _projection()

    with pytest.raises(FrozenInstanceError):
        projected.baseline_run_id = 0

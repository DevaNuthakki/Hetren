"""Project trusted VOiCES comparison evidence into Reliability contracts.

This B11C adapter bridges the application-owned B9 two-model execution to
the domain-neutral B10H scoring and matched-release-assurance contracts.  It
does not choose qualification thresholds, issue a model verdict, certify a
model, qualify production use, or authorize release enforcement.

The projection accepts caller-owned positive run identifiers because the B9
campaign identities are strings and must not be silently reinterpreted as
database EvaluationRun identifiers.  Test-case integers are deterministic
one-based ordinals over B8's already-verified ordered case cohort; the exact
string case mapping is embedded in the resulting evidence payload.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from app.adversarial_asr_human_external_voices_matched_control_suite_projection import (
    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CASE_COUNT,
)
from app.adversarial_asr_human_external_voices_model_comparison import (
    ASRAdversarialVOiCESModelComparisonBundle,
)
from app.adversarial_asr_human_external_voices_model_comparison_execution import (
    ASRAdversarialVOiCESModelComparisonExecutionBundle,
    ASRAdversarialVOiCESModelComparisonExecutionError,
)
from hvee.core.contracts import HveeContractError, ObservationStatus
from hvee.core.observation_evidence import ObservationEvidenceRecord
from hvee.packs.asr.adversarial_execution_evidence import (
    ASRAdversarialExecutionStatus,
)
from hvee.packs.asr.adversarial_human_external_voices_babble_matched_control_v1 import (
    ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_PAIR_COUNT,
)
from hvee.packs.asr.matched_evidence import (
    ASRMatchedQualityCohorts,
    build_asr_matched_quality_cohorts,
)
from hvee.packs.asr.normalized_evaluation import (
    NORMALIZED_CER_EVALUATOR,
    NORMALIZED_CER_METRIC,
    NORMALIZED_WER_EVALUATOR,
    NORMALIZED_WER_METRIC,
)
from hvee.packs.asr.release_assurance import (
    ASRMatchedReleaseAssuranceResult,
    ASRMetricNoninferiorityAssessment,
    evaluate_asr_matched_release_assurance,
)
from hvee.packs.asr.release_assurance_policy import (
    ASRMatchedReleaseAssurancePolicyV1,
)
from hvee.packs.asr.reliability_profile import (
    ASR_RELIABILITY_PROFILE_V1,
    verify_asr_reliability_profile_v1,
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
    evaluate_transcript_integrity,
)


ASR_ADVERSARIAL_VOICES_RELIABILITY_PROJECTION_SCHEMA_VERSION = 1
ASR_ADVERSARIAL_VOICES_RELIABILITY_PROJECTION_VERSION = "1.0.0"
ASR_ADVERSARIAL_VOICES_RELIABILITY_PROJECTION_KEY = (
    "hetren.asr.adversarial-human-external-voices-"
    "reliability-evidence-projection"
)
ASR_ADVERSARIAL_VOICES_RELIABILITY_PROJECTED_RUN_COUNT = 2
ASR_ADVERSARIAL_VOICES_RELIABILITY_PROJECTED_CASE_COUNT = (
    ASR_ADVERSARIAL_VOICES_MATCHED_CONTROL_SUITE_CASE_COUNT
)
ASR_ADVERSARIAL_VOICES_RELIABILITY_PROJECTED_EXECUTION_COUNT = (
    ASR_ADVERSARIAL_VOICES_RELIABILITY_PROJECTED_RUN_COUNT
    * ASR_ADVERSARIAL_VOICES_RELIABILITY_PROJECTED_CASE_COUNT
)
ASR_ADVERSARIAL_VOICES_RELIABILITY_PROJECTED_OBSERVATION_COUNT = (
    ASR_ADVERSARIAL_VOICES_RELIABILITY_PROJECTED_EXECUTION_COUNT * 2
)


class ASRAdversarialVOiCESReliabilityProjectionError(HveeContractError):
    """Raised when B9 evidence cannot form a trusted Reliability projection."""


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ASRAdversarialVOiCESReliabilityProjectionError(
            "VOiCES Reliability projection must be deterministic JSON."
        ) from error


def _require_positive_run_id(*, name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ASRAdversarialVOiCESReliabilityProjectionError(
            f"{name} must be a positive integer."
        )
    return value


def _reverify_execution(
    value: object,
) -> ASRAdversarialVOiCESModelComparisonExecutionBundle:
    if not isinstance(
        value,
        ASRAdversarialVOiCESModelComparisonExecutionBundle,
    ):
        raise ASRAdversarialVOiCESReliabilityProjectionError(
            "VOiCES Reliability projection requires the exact B9 execution."
        )

    try:
        reverified = ASRAdversarialVOiCESModelComparisonExecutionBundle(
            matched_control_suite_sha256=value.matched_control_suite_sha256,
            baseline_campaign=value.baseline_campaign,
            candidate_campaign=value.candidate_campaign,
            baseline_metrics=value.baseline_metrics,
            candidate_metrics=value.candidate_metrics,
            comparison=value.comparison,
        )
        comparison = reverified.require_complete_comparison()
    except (ASRAdversarialVOiCESModelComparisonExecutionError, ValueError) as error:
        raise ASRAdversarialVOiCESReliabilityProjectionError(
            "VOiCES Reliability projection requires a complete reverified "
            "B9 comparison."
        ) from error

    if reverified.sha256 != value.sha256:
        raise ASRAdversarialVOiCESReliabilityProjectionError(
            "VOiCES B9 execution identity changed during projection."
        )

    if (
        not isinstance(comparison, ASRAdversarialVOiCESModelComparisonBundle)
        or len(comparison.cases)
        != ASR_ADVERSARIAL_VOICES_RELIABILITY_PROJECTED_CASE_COUNT
        or len(comparison.pairs)
        != ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_PAIR_COUNT
    ):
        raise ASRAdversarialVOiCESReliabilityProjectionError(
            "VOiCES Reliability projection population changed."
        )

    return reverified


def _reverify_policy(
    value: object,
) -> ASRMatchedReleaseAssurancePolicyV1:
    if not isinstance(value, ASRMatchedReleaseAssurancePolicyV1):
        raise ASRAdversarialVOiCESReliabilityProjectionError(
            "VOiCES Reliability projection requires explicit matched "
            "release-assurance policy v1."
        )

    try:
        reverified = ASRMatchedReleaseAssurancePolicyV1(
            interval=value.interval,
            normalized_wer_noninferiority_margin=(
                value.normalized_wer_noninferiority_margin
            ),
            normalized_cer_noninferiority_margin=(
                value.normalized_cer_noninferiority_margin
            ),
        )
    except (HveeContractError, ValueError) as error:
        raise ASRAdversarialVOiCESReliabilityProjectionError(
            "VOiCES matched release-assurance policy failed revalidation."
        ) from error

    if reverified != value:
        raise ASRAdversarialVOiCESReliabilityProjectionError(
            "VOiCES matched release-assurance policy identity changed."
        )

    return reverified


def _observation_record(
    *,
    metric,
    evaluator,
    run_id: int,
    test_case_id: int,
    value: float,
) -> ObservationEvidenceRecord:
    return ObservationEvidenceRecord(
        metric_key=metric.key,
        metric_version=metric.version,
        evaluator_key=evaluator.key,
        evaluator_version=evaluator.version,
        evaluation_type=metric.evaluation_type,
        scope="test_case",
        evaluation_run_id=run_id,
        test_case_id=test_case_id,
        status=ObservationStatus.SUCCESS,
        value_type=metric.value_type,
        value=value,
    )


def _observation_records(
    *,
    comparison: ASRAdversarialVOiCESModelComparisonBundle,
    baseline_run_id: int,
    candidate_run_id: int,
) -> tuple[ObservationEvidenceRecord, ...]:
    records: list[ObservationEvidenceRecord] = []

    for test_case_id, case in enumerate(comparison.cases, start=1):
        for run_id, result in (
            (baseline_run_id, case.baseline),
            (candidate_run_id, case.candidate),
        ):
            records.extend(
                (
                    _observation_record(
                        metric=NORMALIZED_WER_METRIC,
                        evaluator=NORMALIZED_WER_EVALUATOR,
                        run_id=run_id,
                        test_case_id=test_case_id,
                        value=result.evaluation.wer,
                    ),
                    _observation_record(
                        metric=NORMALIZED_CER_METRIC,
                        evaluator=NORMALIZED_CER_EVALUATOR,
                        run_id=run_id,
                        test_case_id=test_case_id,
                        value=result.evaluation.cer,
                    ),
                )
            )

    observed = tuple(records)

    if len(observed) != ASR_ADVERSARIAL_VOICES_RELIABILITY_PROJECTED_OBSERVATION_COUNT:
        raise ASRAdversarialVOiCESReliabilityProjectionError(
            "VOiCES Reliability observation population changed."
        )

    return observed


def _combined_status_counts(
    execution: ASRAdversarialVOiCESModelComparisonExecutionBundle,
) -> dict[ASRAdversarialExecutionStatus, int]:
    return {
        status: (
            execution.baseline_campaign.status_counts[status.value]
            + execution.candidate_campaign.status_counts[status.value]
        )
        for status in ASRAdversarialExecutionStatus
    }


def _operational_evidence(
    execution: ASRAdversarialVOiCESModelComparisonExecutionBundle,
) -> ASROperationalFitnessEvidence:
    counts = _combined_status_counts(execution)
    expected = ASR_ADVERSARIAL_VOICES_RELIABILITY_PROJECTED_EXECUTION_COUNT
    observed = sum(counts.values())

    if observed != expected:
        raise ASRAdversarialVOiCESReliabilityProjectionError(
            "VOiCES Reliability operational population changed."
        )

    return ASROperationalFitnessEvidence(
        execution_completion=ASRReliabilityRateEvidence(
            successful_count=counts[ASRAdversarialExecutionStatus.COMPLETED],
            observed_count=observed,
            expected_count=expected,
        ),
        timeout_free=ASRReliabilityRateEvidence(
            successful_count=(
                observed - counts[ASRAdversarialExecutionStatus.TIMED_OUT]
            ),
            observed_count=observed,
            expected_count=expected,
        ),
        cancellation_free=ASRReliabilityRateEvidence(
            successful_count=(
                observed - counts[ASRAdversarialExecutionStatus.CANCELLED]
            ),
            observed_count=observed,
            expected_count=expected,
        ),
        provider_error_free=ASRReliabilityRateEvidence(
            successful_count=(
                observed - counts[ASRAdversarialExecutionStatus.FAILED]
            ),
            observed_count=observed,
            expected_count=expected,
        ),
    )


def _transcript_integrity_gates(
    comparison: ASRAdversarialVOiCESModelComparisonBundle,
) -> tuple[ASRReliabilityGateEvidence, ASRReliabilityGateEvidence]:
    evaluations = tuple(
        result.evaluation
        for case in comparison.cases
        for result in (case.baseline, case.candidate)
    )
    integrity = tuple(evaluate_transcript_integrity(value) for value in evaluations)
    expected = ASR_ADVERSARIAL_VOICES_RELIABILITY_PROJECTED_EXECUTION_COUNT

    if len(integrity) != expected:
        raise ASRAdversarialVOiCESReliabilityProjectionError(
            "VOiCES transcript-integrity population changed."
        )

    return (
        ASRReliabilityGateEvidence(
            metric_key=MISSING_OUTPUT_METRIC.key,
            violation_count=sum(value.missing_output for value in integrity),
            observed_count=len(integrity),
            expected_count=expected,
        ),
        ASRReliabilityGateEvidence(
            metric_key=UNEXPECTED_OUTPUT_METRIC.key,
            violation_count=sum(value.unexpected_output for value in integrity),
            observed_count=len(integrity),
            expected_count=expected,
        ),
    )


def _robustness_evidence(
    comparison: ASRAdversarialVOiCESModelComparisonBundle,
) -> ASRMatchedControlRobustnessEvidence:
    aggregate = comparison.aggregate["pair_noise_degradation_macro_mean"]
    differential = aggregate["candidate_minus_baseline"]

    if not isinstance(differential, dict):
        raise ASRAdversarialVOiCESReliabilityProjectionError(
            "VOiCES B8 robustness aggregate changed."
        )

    return ASRMatchedControlRobustnessEvidence(
        wer_differential=differential.get("wer"),
        cer_differential=differential.get("cer"),
        observed_pair_count=len(comparison.pairs),
        expected_pair_count=(
            ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_PAIR_COUNT
        ),
    )


def _scoring_evidence(
    execution: ASRAdversarialVOiCESModelComparisonExecutionBundle,
) -> ASRReliabilityScoringEvidence:
    try:
        verify_asr_reliability_profile_v1(ASR_RELIABILITY_PROFILE_V1)
    except Exception as error:
        raise ASRAdversarialVOiCESReliabilityProjectionError(
            "VOiCES Reliability projection requires the exact canonical "
            "Reliability Profile v1."
        ) from error

    comparison = execution.require_complete_comparison()
    missing, unexpected = _transcript_integrity_gates(comparison)

    return ASRReliabilityScoringEvidence(
        performance=ASRReliabilityPerformanceEvidence(
            matched_control_robustness=_robustness_evidence(comparison),
            # VOiCES is a general external-voices robustness cohort.  Its
            # opportunistic semantic observations are not promoted into
            # preregistered critical-content qualification evidence.
            critical_number_integrity=None,
            critical_identifier_integrity=None,
            critical_terminology_integrity=None,
        ),
        assurance=ASREvidenceAssuranceEvidence(
            profile_and_evaluators_verified=True,
            input_provenance_verified=True,
            runtime_identity_verified=True,
            # One campaign per model does not establish repeatability.
            reproducibility_verified=None,
        ),
        operational=_operational_evidence(execution),
        missing_output_gate=missing,
        unexpected_output_gate=unexpected,
    )


def _record_payload(record: ObservationEvidenceRecord) -> dict[str, object]:
    return {
        "metric_key": record.metric_key,
        "metric_version": record.metric_version,
        "evaluator_key": record.evaluator_key,
        "evaluator_version": record.evaluator_version,
        "evaluation_type": record.evaluation_type,
        "scope": record.scope,
        "evaluation_run_id": record.evaluation_run_id,
        "test_case_id": record.test_case_id,
        "status": record.status.value,
        "value_type": record.value_type.value,
        "value": record.value,
        "status_detail": record.status_detail,
    }


def _scoring_evidence_payload(
    evidence: ASRReliabilityScoringEvidence,
) -> dict[str, object]:
    performance = evidence.performance
    return {
        "performance": {
            "matched_control_robustness": (
                None
                if performance.matched_control_robustness is None
                else performance.matched_control_robustness.payload
            ),
            "critical_number_integrity": None,
            "critical_identifier_integrity": None,
            "critical_terminology_integrity": None,
        },
        "assurance": dict(evidence.assurance.values),
        "operational": {
            key: None if value is None else value.payload
            for key, value in evidence.operational.values
        },
        "hard_gates": {
            "missing_output": (
                None
                if evidence.missing_output_gate is None
                else evidence.missing_output_gate.payload
            ),
            "unexpected_output": (
                None
                if evidence.unexpected_output_gate is None
                else evidence.unexpected_output_gate.payload
            ),
        },
    }


def _interval_payload(
    assessment: ASRMetricNoninferiorityAssessment | None,
) -> dict[str, object] | None:
    if assessment is None:
        return None

    interval = assessment.interval
    return {
        "metric_key": assessment.metric_key,
        "metric_version": assessment.metric_version,
        "noninferiority_margin": assessment.noninferiority_margin,
        "method": interval.method.value,
        "confidence_level": interval.confidence_level,
        "minimum_usable_pairs": interval.minimum_usable_pairs,
        "resamples": interval.resamples,
        "random_seed": interval.random_seed,
        "total_cases": interval.total_cases,
        "usable_pairs": interval.usable_pairs,
        "integrity": interval.integrity.value,
        "evidence": interval.evidence.value,
        "reason": interval.reason.value,
        "mean_delta": interval.mean_delta,
        "lower_bound": interval.lower_bound,
        "upper_bound": interval.upper_bound,
        "claim": assessment.claim.value,
    }


def _matched_assurance_payload(
    result: ASRMatchedReleaseAssuranceResult,
) -> dict[str, object]:
    return {
        "policy": {
            "key": result.policy_key,
            "version": result.policy_version,
        },
        "runs": {
            "baseline_run_id": result.baseline_run_id,
            "candidate_run_id": result.candidate_run_id,
        },
        "declared_test_case_ids": list(result.declared_test_case_ids),
        "normalized_wer": _interval_payload(result.normalized_wer),
        "normalized_cer": _interval_payload(result.normalized_cer),
        "assessment": {
            "integrity": result.integrity.value,
            "evidence": result.evidence.value,
            "claim": result.claim.value,
        },
    }


@dataclass(frozen=True, slots=True)
class ASRAdversarialVOiCESReliabilityProjectionBundle:
    """Deterministic, non-authoritative B11C Reliability evidence."""

    execution: ASRAdversarialVOiCESModelComparisonExecutionBundle
    baseline_run_id: int
    candidate_run_id: int
    matched_release_assurance_policy: ASRMatchedReleaseAssurancePolicyV1

    def __post_init__(self) -> None:
        _reverify_execution(self.execution)
        baseline = _require_positive_run_id(
            name="VOiCES baseline run id",
            value=self.baseline_run_id,
        )
        candidate = _require_positive_run_id(
            name="VOiCES candidate run id",
            value=self.candidate_run_id,
        )

        if baseline == candidate:
            raise ASRAdversarialVOiCESReliabilityProjectionError(
                "VOiCES Reliability projection requires distinct run ids."
            )

        _reverify_policy(self.matched_release_assurance_policy)

    @property
    def comparison(self) -> ASRAdversarialVOiCESModelComparisonBundle:
        return self.execution.require_complete_comparison()

    @property
    def declared_test_case_ids(self) -> tuple[int, ...]:
        return tuple(
            range(
                1,
                ASR_ADVERSARIAL_VOICES_RELIABILITY_PROJECTED_CASE_COUNT + 1,
            )
        )

    @property
    def case_id_by_test_case_id(self) -> tuple[str, ...]:
        return tuple(value.case_id for value in self.comparison.cases)

    @property
    def observation_records(self) -> tuple[ObservationEvidenceRecord, ...]:
        return _observation_records(
            comparison=self.comparison,
            baseline_run_id=self.baseline_run_id,
            candidate_run_id=self.candidate_run_id,
        )

    @property
    def cohorts(self) -> ASRMatchedQualityCohorts:
        return build_asr_matched_quality_cohorts(
            baseline_run_id=self.baseline_run_id,
            candidate_run_id=self.candidate_run_id,
            declared_test_case_ids=self.declared_test_case_ids,
            records=self.observation_records,
        )

    @property
    def matched_assurance(self) -> ASRMatchedReleaseAssuranceResult:
        return evaluate_asr_matched_release_assurance(
            cohorts=self.cohorts,
            policy=self.matched_release_assurance_policy,
        )

    @property
    def scoring_evidence(self) -> ASRReliabilityScoringEvidence:
        return _scoring_evidence(self.execution)

    @property
    def payload(self) -> dict[str, object]:
        baseline = self.execution.baseline_campaign.campaign.definition
        candidate = self.execution.candidate_campaign.campaign.definition
        comparison = self.comparison
        scoring = self.scoring_evidence
        assurance = self.matched_assurance

        return {
            "schema_version": (
                ASR_ADVERSARIAL_VOICES_RELIABILITY_PROJECTION_SCHEMA_VERSION
            ),
            "artifact": {
                "key": ASR_ADVERSARIAL_VOICES_RELIABILITY_PROJECTION_KEY,
                "version": (
                    ASR_ADVERSARIAL_VOICES_RELIABILITY_PROJECTION_VERSION
                ),
                "type": "voices_two_model_reliability_evidence_projection",
            },
            "upstream": {
                "b9_execution_sha256": self.execution.sha256,
                "b8_comparison_sha256": comparison.sha256,
                "matched_control_suite_sha256": (
                    self.execution.matched_control_suite_sha256
                ),
                "baseline_campaign_sha256": (
                    self.execution.baseline_campaign.sha256
                ),
                "candidate_campaign_sha256": (
                    self.execution.candidate_campaign.sha256
                ),
                "baseline_metrics_sha256": (
                    self.execution.baseline_metrics.sha256
                ),
                "candidate_metrics_sha256": (
                    self.execution.candidate_metrics.sha256
                ),
            },
            "runs": {
                "baseline": {
                    "evaluation_run_id": self.baseline_run_id,
                    "campaign_id": baseline.campaign_id,
                    "campaign_version": baseline.campaign_version,
                    "provider_key": baseline.provider_key,
                    "model_key": baseline.model_key,
                },
                "candidate": {
                    "evaluation_run_id": self.candidate_run_id,
                    "campaign_id": candidate.campaign_id,
                    "campaign_version": candidate.campaign_version,
                    "provider_key": candidate.provider_key,
                    "model_key": candidate.model_key,
                },
            },
            "methodology": {
                "test_case_identity_mapping": (
                    "one_based_ordinal_over_verified_b8_order"
                ),
                "matched_quality_metrics": [
                    NORMALIZED_WER_METRIC.key,
                    NORMALIZED_CER_METRIC.key,
                ],
                "robustness_signal": (
                    "candidate_minus_baseline_change_in_"
                    "babble_minus_control_macro_mean"
                ),
                "critical_content_projection": (
                    "withheld_general_voices_cohort_not_preregistered_"
                    "for_critical_content_qualification"
                ),
                "reproducibility_projection": (
                    "withheld_single_campaign_per_model"
                ),
                "matched_release_assurance_policy_caller_supplied": True,
            },
            "population": {
                "case_count": len(comparison.cases),
                "pair_count": len(comparison.pairs),
                "execution_count": (
                    ASR_ADVERSARIAL_VOICES_RELIABILITY_PROJECTED_EXECUTION_COUNT
                ),
                "observation_record_count": len(self.observation_records),
                "case_identity_map": [
                    {
                        "test_case_id": test_case_id,
                        "voices_case_id": case_id,
                    }
                    for test_case_id, case_id in zip(
                        self.declared_test_case_ids,
                        self.case_id_by_test_case_id,
                        strict=True,
                    )
                ],
            },
            "matched_observation_records": [
                _record_payload(value) for value in self.observation_records
            ],
            "scoring_evidence": _scoring_evidence_payload(scoring),
            "matched_release_assurance": _matched_assurance_payload(assurance),
            "evidence_boundary": {
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
            },
        }

    @property
    def sha256(self) -> str:
        return hashlib.sha256(_canonical_json_bytes(self.payload)).hexdigest()

    def require_qualification_verdict(self) -> None:
        raise ASRAdversarialVOiCESReliabilityProjectionError(
            "VOiCES B11C is a non-authoritative evidence projection; no "
            "qualification verdict was issued."
        )


def project_asr_adversarial_voices_reliability_evidence_v1(
    *,
    execution: ASRAdversarialVOiCESModelComparisonExecutionBundle,
    baseline_run_id: int,
    candidate_run_id: int,
    matched_release_assurance_policy: ASRMatchedReleaseAssurancePolicyV1,
) -> ASRAdversarialVOiCESReliabilityProjectionBundle:
    """Build deterministic scoring evidence and matched assurance from B9."""

    verified_execution = _reverify_execution(execution)
    verified_policy = _reverify_policy(matched_release_assurance_policy)

    return ASRAdversarialVOiCESReliabilityProjectionBundle(
        execution=verified_execution,
        baseline_run_id=baseline_run_id,
        candidate_run_id=candidate_run_id,
        matched_release_assurance_policy=verified_policy,
    )

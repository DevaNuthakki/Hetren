"""Evaluate explicit Hetren ASR Reliability qualification policy v1.

B10H computes a descriptive scorecard and B11A defines an explicit policy.
This module composes those contracts with existing paired ASR assurance,
exact Clopper-Pearson bounds, deterministic Holm familywise control, and the
domain-neutral four-state decision kernel.  A result is a non-authoritative
qualification evaluation: it does not certify a model, qualify production,
or authorize release enforcement.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
import math

from hvee.core.contracts import HveeContractError
from hvee.core.decision import (
    ClaimAssessment,
    CriticalAssessment,
    DecisionInputs,
    DecisionResult,
    EvidenceAssessment,
    IntegrityAssessment,
    decide,
)
from hvee.packs.asr.normalized_evaluation import (
    NORMALIZED_CER_METRIC,
    NORMALIZED_WER_METRIC,
)
from hvee.packs.asr.release_assurance import (
    ASRMatchedReleaseAssuranceResult,
    ASRMetricNoninferiorityAssessment,
)
from hvee.packs.asr.reliability_profile import (
    ASR_RELIABILITY_PROFILE_V1_SHA256,
)
from hvee.packs.asr.reliability_qualification_policy import (
    ASR_RELIABILITY_RATE_SCALE,
    ASRReliabilityQualificationPolicyV1,
    verify_asr_reliability_qualification_policy_v1,
)
from hvee.packs.asr.reliability_scoring import (
    ASR_RELIABILITY_SCORING_V1_SHA256,
    ASRMatchedControlRobustnessEvidence,
    ASRReliabilityGateStatus,
    ASRReliabilityIndexComponent,
    ASRReliabilityMaturityStatus,
    ASRReliabilityRateEvidence,
    ASRReliabilityScorecard,
    ASRReliabilityScoringEvidence,
    score_asr_reliability_v1,
)
from hvee.statistics.exact_binomial import (
    ExactBinomialTail,
    ExactPValue,
    HolmStepDownDecision,
    clopper_pearson_lower_bound_scaled,
    exact_binomial_tail_probability,
    holm_step_down,
)


ASR_RELIABILITY_QUALIFICATION_RESULT_SCHEMA_VERSION = 1
ASR_RELIABILITY_QUALIFICATION_RESULT_KEY = (
    "hetren.asr.reliability-qualification-result"
)
ASR_RELIABILITY_QUALIFICATION_RESULT_VERSION = "1.0.0"
ASR_RELIABILITY_CRITICAL_GROUP_KEYS_V1 = (
    "critical_number_integrity",
    "critical_identifier_integrity",
    "critical_terminology_integrity",
)


class ASRReliabilityQualificationError(HveeContractError):
    """Raised when Reliability qualification inputs or output are invalid."""


def _require_text(*, name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
    ):
        raise ASRReliabilityQualificationError(
            f"{name} must be non-empty trimmed text."
        )
    return value


def _require_score(*, name: str, value: object) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or not 0.0 <= float(value) <= 100.0
    ):
        raise ASRReliabilityQualificationError(
            f"{name} must be a finite score between 0 and 100."
        )
    return float(value)


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
        raise ASRReliabilityQualificationError(
            "Reliability qualification must be deterministic JSON."
        ) from error


def _fraction_payload(value: Fraction | None) -> dict[str, int] | None:
    if value is None:
        return None
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
    }


@dataclass(frozen=True, slots=True)
class ASRReliabilityScoreFloorAssessment:
    """One higher-is-better score comparison with an engineer label."""

    key: str
    engineer_label: str
    observed_score: float | None
    minimum_score: float
    claim: ClaimAssessment

    def __post_init__(self) -> None:
        _require_text(name="Score-floor key", value=self.key)
        _require_text(name="Score-floor engineer label", value=self.engineer_label)
        minimum = _require_score(
            name="Score-floor minimum",
            value=self.minimum_score,
        )
        if self.observed_score is not None:
            observed = _require_score(
                name="Score-floor observed value",
                value=self.observed_score,
            )
            expected = (
                ClaimAssessment.SUPPORTED
                if observed >= minimum
                else ClaimAssessment.CONTRADICTED
            )
        else:
            expected = ClaimAssessment.UNRESOLVED
        if self.claim != expected:
            raise ASRReliabilityQualificationError(
                "Score-floor claim does not match its observed score."
            )

    @property
    def payload(self) -> dict[str, object]:
        return {
            "key": self.key,
            "engineer_label": self.engineer_label,
            "comparison": "greater_than_or_equal",
            "observed_score": self.observed_score,
            "minimum_score": self.minimum_score,
            "claim": self.claim.value,
        }


@dataclass(frozen=True, slots=True)
class ASRCriticalIntegrityQualificationAssessment:
    """One critical-content preservation claim under exact Holm control."""

    key: str
    engineer_label: str
    successful_count: int | None
    observed_count: int | None
    expected_count: int | None
    minimum_observations: int
    lower_bound_ppm: int | None
    minimum_lower_bound_ppm: int
    raw_p_value: Fraction | None
    holm_rank: int | None
    holm_critical_value: Fraction | None
    holm_adjusted_p_value: Fraction | None
    holm_rejected: bool | None
    claim: ClaimAssessment

    def __post_init__(self) -> None:
        _require_text(name="Critical qualification key", value=self.key)
        _require_text(
            name="Critical qualification engineer label",
            value=self.engineer_label,
        )
        if (
            type(self.minimum_observations) is not int
            or self.minimum_observations < 1
        ):
            raise ASRReliabilityQualificationError(
                "Critical qualification minimum observations must be positive."
            )
        if (
            type(self.minimum_lower_bound_ppm) is not int
            or not 0
            <= self.minimum_lower_bound_ppm
            <= ASR_RELIABILITY_RATE_SCALE
        ):
            raise ASRReliabilityQualificationError(
                "Critical qualification lower-bound threshold is invalid."
            )

        counts = (
            self.successful_count,
            self.observed_count,
            self.expected_count,
        )
        if any(value is None for value in counts):
            if not all(value is None for value in counts):
                raise ASRReliabilityQualificationError(
                    "Critical qualification counts must be all present or missing."
                )
        else:
            successful = self.successful_count
            observed = self.observed_count
            expected = self.expected_count
            assert successful is not None
            assert observed is not None
            assert expected is not None
            if (
                type(successful) is not int
                or type(observed) is not int
                or type(expected) is not int
                or expected < 1
                or not 0 <= successful <= observed <= expected
            ):
                raise ASRReliabilityQualificationError(
                    "Critical qualification counts are invalid."
                )

        statistical_values = (
            self.lower_bound_ppm,
            self.raw_p_value,
            self.holm_rank,
            self.holm_critical_value,
            self.holm_adjusted_p_value,
            self.holm_rejected,
        )
        presence = tuple(value is not None for value in statistical_values)
        if any(presence) != all(presence):
            raise ASRReliabilityQualificationError(
                "Critical qualification statistics must be complete or withheld."
            )
        calculated = all(presence)

        if calculated:
            if (
                type(self.lower_bound_ppm) is not int
                or not 0
                <= self.lower_bound_ppm
                <= ASR_RELIABILITY_RATE_SCALE
                or type(self.holm_rank) is not int
                or self.holm_rank < 1
                or not isinstance(self.raw_p_value, Fraction)
                or not isinstance(self.holm_critical_value, Fraction)
                or not isinstance(self.holm_adjusted_p_value, Fraction)
                or type(self.holm_rejected) is not bool
                or not 0 <= self.raw_p_value <= 1
                or not 0 <= self.holm_critical_value <= 1
                or not 0 <= self.holm_adjusted_p_value <= 1
            ):
                raise ASRReliabilityQualificationError(
                    "Critical qualification statistical result is invalid."
                )
            expected_claim = (
                ClaimAssessment.SUPPORTED
                if self.lower_bound_ppm >= self.minimum_lower_bound_ppm
                and self.holm_rejected
                else ClaimAssessment.UNRESOLVED
            )
        else:
            expected_claim = ClaimAssessment.UNRESOLVED

        if self.claim != expected_claim:
            raise ASRReliabilityQualificationError(
                "Critical qualification claim does not match exact evidence."
            )

    @property
    def payload(self) -> dict[str, object]:
        observed_rate = None
        if self.successful_count is not None and self.observed_count:
            observed_rate = self.successful_count / self.observed_count
        return {
            "key": self.key,
            "engineer_label": self.engineer_label,
            "successful_count": self.successful_count,
            "observed_count": self.observed_count,
            "expected_count": self.expected_count,
            "observed_preservation_rate": observed_rate,
            "minimum_observations": self.minimum_observations,
            "minimum_observations_met": (
                self.observed_count is not None
                and self.observed_count >= self.minimum_observations
            ),
            "bound": {
                "method": "clopper_pearson_one_sided_lower_scaled",
                "scale": ASR_RELIABILITY_RATE_SCALE,
                "lower_bound_ppm": self.lower_bound_ppm,
                "minimum_lower_bound_ppm": self.minimum_lower_bound_ppm,
                "comparison": "greater_than_or_equal",
            },
            "multiplicity": {
                "method": "holm_step_down",
                "raw_p_value": _fraction_payload(self.raw_p_value),
                "holm_rank": self.holm_rank,
                "holm_critical_value": _fraction_payload(
                    self.holm_critical_value
                ),
                "holm_adjusted_p_value": _fraction_payload(
                    self.holm_adjusted_p_value
                ),
                "holm_rejected": self.holm_rejected,
            },
            "claim": self.claim.value,
        }


def _critical_groups(
    evidence: ASRReliabilityScoringEvidence,
) -> tuple[tuple[str, str, ASRReliabilityRateEvidence | None], ...]:
    return (
        (
            "critical_number_integrity",
            "Critical Number Integrity",
            evidence.performance.critical_number_integrity,
        ),
        (
            "critical_identifier_integrity",
            "Critical Identifier Integrity",
            evidence.performance.critical_identifier_integrity,
        ),
        (
            "critical_terminology_integrity",
            "Critical Terminology Integrity",
            evidence.performance.critical_terminology_integrity,
        ),
    )


def _critical_support_sufficient(
    *,
    evidence: ASRReliabilityScoringEvidence,
    policy: ASRReliabilityQualificationPolicyV1,
) -> bool:
    minimum = (
        policy.critical_integrity_confidence
        .minimum_conclusive_observations_per_group
    )
    return all(
        value is not None
        and value.complete
        and value.observed_count >= minimum
        for _key, _label, value in _critical_groups(evidence)
    )


def _withheld_critical_assessments(
    *,
    evidence: ASRReliabilityScoringEvidence,
    policy: ASRReliabilityQualificationPolicyV1,
) -> tuple[ASRCriticalIntegrityQualificationAssessment, ...]:
    minimum = (
        policy.critical_integrity_confidence
        .minimum_conclusive_observations_per_group
    )
    threshold = (
        policy.critical_integrity_confidence
        .minimum_preservation_lower_bound_ppm
    )
    return tuple(
        ASRCriticalIntegrityQualificationAssessment(
            key=key,
            engineer_label=label,
            successful_count=(
                None if value is None else value.successful_count
            ),
            observed_count=None if value is None else value.observed_count,
            expected_count=None if value is None else value.expected_count,
            minimum_observations=minimum,
            lower_bound_ppm=None,
            minimum_lower_bound_ppm=threshold,
            raw_p_value=None,
            holm_rank=None,
            holm_critical_value=None,
            holm_adjusted_p_value=None,
            holm_rejected=None,
            claim=ClaimAssessment.UNRESOLVED,
        )
        for key, label, value in _critical_groups(evidence)
    )


def _critical_confidence_assessments(
    *,
    evidence: ASRReliabilityScoringEvidence,
    policy: ASRReliabilityQualificationPolicyV1,
) -> tuple[ASRCriticalIntegrityQualificationAssessment, ...]:
    if not _critical_support_sufficient(evidence=evidence, policy=policy):
        return _withheld_critical_assessments(
            evidence=evidence,
            policy=policy,
        )

    confidence_policy = policy.critical_integrity_confidence
    confidence = Fraction(
        confidence_policy.familywise_confidence_level_ppm,
        ASR_RELIABILITY_RATE_SCALE,
    )
    alpha = 1 - confidence
    threshold = confidence_policy.minimum_preservation_lower_bound_ppm
    observations = []

    for key, label, value in _critical_groups(evidence):
        assert value is not None
        lower_bound = clopper_pearson_lower_bound_scaled(
            successes=value.successful_count,
            trials=value.observed_count,
            confidence_level=confidence,
            scale=ASR_RELIABILITY_RATE_SCALE,
        )
        raw_p_value = exact_binomial_tail_probability(
            successes=value.successful_count,
            trials=value.observed_count,
            probability=Fraction(threshold, ASR_RELIABILITY_RATE_SCALE),
            tail=ExactBinomialTail.GREATER_THAN_OR_EQUAL,
        )
        observations.append(
            (key, label, value, lower_bound, raw_p_value)
        )

    decisions = holm_step_down(
        p_values=tuple(
            ExactPValue(claim_key=key, value=raw_p_value)
            for key, _label, _value, _bound, raw_p_value in observations
        ),
        familywise_alpha=alpha,
    )
    decisions_by_key = {
        decision.claim_key: decision for decision in decisions
    }

    return tuple(
        _critical_assessment_from_calculation(
            key=key,
            label=label,
            value=value,
            lower_bound=lower_bound,
            decision=decisions_by_key[key],
            policy=policy,
        )
        for key, label, value, lower_bound, _p_value in observations
    )


def _critical_assessment_from_calculation(
    *,
    key: str,
    label: str,
    value: ASRReliabilityRateEvidence,
    lower_bound: int,
    decision: HolmStepDownDecision,
    policy: ASRReliabilityQualificationPolicyV1,
) -> ASRCriticalIntegrityQualificationAssessment:
    threshold = (
        policy.critical_integrity_confidence
        .minimum_preservation_lower_bound_ppm
    )
    claim = (
        ClaimAssessment.SUPPORTED
        if lower_bound >= threshold and decision.rejected
        else ClaimAssessment.UNRESOLVED
    )
    return ASRCriticalIntegrityQualificationAssessment(
        key=key,
        engineer_label=label,
        successful_count=value.successful_count,
        observed_count=value.observed_count,
        expected_count=value.expected_count,
        minimum_observations=(
            policy.critical_integrity_confidence
            .minimum_conclusive_observations_per_group
        ),
        lower_bound_ppm=lower_bound,
        minimum_lower_bound_ppm=threshold,
        raw_p_value=decision.raw_p_value,
        holm_rank=decision.rank,
        holm_critical_value=decision.critical_value,
        holm_adjusted_p_value=decision.adjusted_p_value,
        holm_rejected=decision.rejected,
        claim=claim,
    )


def _component_by_key(
    *,
    scorecard: ASRReliabilityScorecard,
    key: str,
) -> ASRReliabilityIndexComponent:
    matches = tuple(
        value
        for value in scorecard.performance_index.components
        if value.key == key
    )
    if len(matches) != 1:
        raise ASRReliabilityQualificationError(
            f"Reliability scorecard must contain exactly one {key} component."
        )
    return matches[0]


def _score_floor(
    *,
    key: str,
    label: str,
    observed: float | None,
    minimum: float,
) -> ASRReliabilityScoreFloorAssessment:
    if observed is None:
        claim = ClaimAssessment.UNRESOLVED
    elif observed >= minimum:
        claim = ClaimAssessment.SUPPORTED
    else:
        claim = ClaimAssessment.CONTRADICTED
    return ASRReliabilityScoreFloorAssessment(
        key=key,
        engineer_label=label,
        observed_score=observed,
        minimum_score=minimum,
        claim=claim,
    )


def _score_floor_assessments(
    *,
    scorecard: ASRReliabilityScorecard,
    policy: ASRReliabilityQualificationPolicyV1,
) -> tuple[ASRReliabilityScoreFloorAssessment, ...]:
    robustness = _component_by_key(
        scorecard=scorecard,
        key="matched_control_robustness",
    )
    number = _component_by_key(
        scorecard=scorecard,
        key="critical_number_integrity",
    )
    identifier = _component_by_key(
        scorecard=scorecard,
        key="critical_identifier_integrity",
    )
    terminology = _component_by_key(
        scorecard=scorecard,
        key="critical_terminology_integrity",
    )
    critical_minimum = policy.minimum_critical_integrity_group_score
    return (
        _score_floor(
            key="hetren_reliability_index",
            label="Hetren Reliability Index",
            observed=scorecard.hetren_reliability_index.score,
            minimum=policy.minimum_hetren_reliability_index,
        ),
        _score_floor(
            key="reliability_performance_index",
            label="Reliability Performance Index",
            observed=scorecard.performance_index.score,
            minimum=policy.minimum_reliability_performance_index,
        ),
        _score_floor(
            key="evidence_assurance_index",
            label="Evidence Assurance Index",
            observed=scorecard.evidence_assurance_index.score,
            minimum=policy.minimum_evidence_assurance_index,
        ),
        _score_floor(
            key="operational_fitness_index",
            label="Operational Fitness Index",
            observed=scorecard.operational_fitness_index.score,
            minimum=policy.minimum_operational_fitness_index,
        ),
        _score_floor(
            key="matched_control_robustness",
            label="Matched-Control Acoustic Robustness",
            observed=robustness.score,
            minimum=policy.minimum_matched_control_robustness_score,
        ),
        _score_floor(
            key="critical_number_integrity",
            label="Critical Number Integrity",
            observed=number.score,
            minimum=critical_minimum,
        ),
        _score_floor(
            key="critical_identifier_integrity",
            label="Critical Identifier Integrity",
            observed=identifier.score,
            minimum=critical_minimum,
        ),
        _score_floor(
            key="critical_terminology_integrity",
            label="Critical Terminology Integrity",
            observed=terminology.score,
            minimum=critical_minimum,
        ),
    )


def _interval_policy_matches(
    *,
    assessment: ASRMetricNoninferiorityAssessment,
    policy: ASRReliabilityQualificationPolicyV1,
) -> bool:
    interval = assessment.interval
    expected = policy.matched_release_assurance.interval
    return (
        interval.method == expected.method
        and interval.confidence_level == expected.confidence_level
        and interval.minimum_usable_pairs == expected.minimum_usable_pairs
        and interval.resamples == expected.resamples
        and interval.random_seed == expected.random_seed
    )


def _require_metric_assurance_binding(
    *,
    name: str,
    assessment: ASRMetricNoninferiorityAssessment | None,
    margin: float | None,
    metric,
    policy: ASRReliabilityQualificationPolicyV1,
) -> None:
    if margin is None:
        if assessment is not None:
            raise ASRReliabilityQualificationError(
                f"Disabled {name} assurance must be absent."
            )
        return
    if assessment is None:
        raise ASRReliabilityQualificationError(
            f"Enabled {name} assurance is missing."
        )
    if (
        assessment.metric_key != metric.key
        or assessment.metric_version != metric.version
        or assessment.noninferiority_margin != float(margin)
        or not _interval_policy_matches(assessment=assessment, policy=policy)
    ):
        raise ASRReliabilityQualificationError(
            f"{name} assurance does not match the explicit policy binding."
        )


def _assurance_structural_integrity_valid(
    assurance: ASRMatchedReleaseAssuranceResult,
) -> bool:
    identifiers = assurance.declared_test_case_ids
    enabled = tuple(
        value
        for value in (assurance.normalized_wer, assurance.normalized_cer)
        if value is not None
    )
    return (
        isinstance(identifiers, tuple)
        and bool(identifiers)
        and all(type(value) is int and value > 0 for value in identifiers)
        and len(set(identifiers)) == len(identifiers)
        and all(
            value.interval.total_cases == len(identifiers)
            and (
                value.interval.evidence
                != EvidenceAssessment.SUFFICIENT
                or value.interval.usable_pairs == len(identifiers)
            )
            for value in enabled
        )
    )


def _verify_assurance_policy_binding(
    *,
    assurance: ASRMatchedReleaseAssuranceResult,
    policy: ASRReliabilityQualificationPolicyV1,
) -> bool:
    matched_policy = policy.matched_release_assurance
    if (
        assurance.policy_key != matched_policy.key
        or assurance.policy_version != matched_policy.version
    ):
        raise ASRReliabilityQualificationError(
            "Matched assurance policy identity does not match B11A."
        )
    _require_metric_assurance_binding(
        name="normalized WER",
        assessment=assurance.normalized_wer,
        margin=matched_policy.normalized_wer_noninferiority_margin,
        metric=NORMALIZED_WER_METRIC,
        policy=policy,
    )
    _require_metric_assurance_binding(
        name="normalized CER",
        assessment=assurance.normalized_cer,
        margin=matched_policy.normalized_cer_noninferiority_margin,
        metric=NORMALIZED_CER_METRIC,
        policy=policy,
    )
    return _assurance_structural_integrity_valid(assurance)


def _scorecard_support_sufficient(scorecard: ASRReliabilityScorecard) -> bool:
    return (
        scorecard.gate_status == ASRReliabilityGateStatus.CLEAR
        and scorecard.maturity_status
        == ASRReliabilityMaturityStatus.COMPLETE_DESCRIPTIVE_EVIDENCE
    )


def _matched_control_support_sufficient(
    *,
    robustness: ASRMatchedControlRobustnessEvidence | None,
    policy: ASRReliabilityQualificationPolicyV1,
) -> bool:
    return (
        robustness is not None
        and robustness.complete
        and robustness.observed_pair_count
        >= policy.minimum_matched_control_pairs
    )


def _combine_claims(
    claims: tuple[ClaimAssessment, ...],
) -> ClaimAssessment:
    if ClaimAssessment.CONTRADICTED in claims:
        return ClaimAssessment.CONTRADICTED
    if claims and all(value == ClaimAssessment.SUPPORTED for value in claims):
        return ClaimAssessment.SUPPORTED
    return ClaimAssessment.UNRESOLVED


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
            "critical_number_integrity": (
                None
                if performance.critical_number_integrity is None
                else performance.critical_number_integrity.payload
            ),
            "critical_identifier_integrity": (
                None
                if performance.critical_identifier_integrity is None
                else performance.critical_identifier_integrity.payload
            ),
            "critical_terminology_integrity": (
                None
                if performance.critical_terminology_integrity is None
                else performance.critical_terminology_integrity.payload
            ),
        },
        "assurance": dict(evidence.assurance.values),
        "operational": {
            key: None if value is None else value.payload
            for key, value in evidence.operational.values
        },
        "hard_gates": [
            None if value is None else value.payload
            for value in (
                evidence.missing_output_gate,
                evidence.unexpected_output_gate,
            )
        ],
    }


def _interval_payload(assessment: ASRMetricNoninferiorityAssessment):
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
    assurance: ASRMatchedReleaseAssuranceResult,
) -> dict[str, object]:
    return {
        "policy": {
            "key": assurance.policy_key,
            "version": assurance.policy_version,
        },
        "runs": {
            "baseline_run_id": assurance.baseline_run_id,
            "candidate_run_id": assurance.candidate_run_id,
        },
        "declared_test_case_ids": list(assurance.declared_test_case_ids),
        "normalized_wer": (
            None
            if assurance.normalized_wer is None
            else _interval_payload(assurance.normalized_wer)
        ),
        "normalized_cer": (
            None
            if assurance.normalized_cer is None
            else _interval_payload(assurance.normalized_cer)
        ),
        "assessment": {
            "integrity": assurance.integrity.value,
            "evidence": assurance.evidence.value,
            "claim": assurance.claim.value,
        },
    }


@dataclass(frozen=True, slots=True)
class ASRReliabilityQualificationResult:
    """One deterministic, non-authoritative B11B qualification decision."""

    policy: ASRReliabilityQualificationPolicyV1
    scoring_evidence: ASRReliabilityScoringEvidence
    scorecard: ASRReliabilityScorecard
    matched_assurance: ASRMatchedReleaseAssuranceResult
    score_floor_assessments: tuple[ASRReliabilityScoreFloorAssessment, ...]
    critical_confidence_assessments: tuple[
        ASRCriticalIntegrityQualificationAssessment, ...
    ]
    scorecard_support_sufficient: bool
    matched_control_support_sufficient: bool
    matched_assurance_support_sufficient: bool
    critical_support_sufficient: bool
    decision_inputs: DecisionInputs
    decision: DecisionResult

    def __post_init__(self) -> None:
        try:
            verify_asr_reliability_qualification_policy_v1(self.policy)
        except Exception as error:
            raise ASRReliabilityQualificationError(
                "Qualification result requires the exact B11A policy."
            ) from error
        if not isinstance(self.scoring_evidence, ASRReliabilityScoringEvidence):
            raise ASRReliabilityQualificationError(
                "Qualification result requires scoring evidence."
            )
        if not isinstance(self.scorecard, ASRReliabilityScorecard):
            raise ASRReliabilityQualificationError(
                "Qualification result requires a scorecard."
            )
        if not isinstance(
            self.matched_assurance,
            ASRMatchedReleaseAssuranceResult,
        ):
            raise ASRReliabilityQualificationError(
                "Qualification result requires matched assurance."
            )

        expected_scorecard = score_asr_reliability_v1(
            evidence=self.scoring_evidence
        )
        if self.scorecard != expected_scorecard:
            raise ASRReliabilityQualificationError(
                "Qualification scorecard does not match raw scoring evidence."
            )

        structural_integrity = _verify_assurance_policy_binding(
            assurance=self.matched_assurance,
            policy=self.policy,
        )
        expected_floors = _score_floor_assessments(
            scorecard=self.scorecard,
            policy=self.policy,
        )
        expected_critical = _critical_confidence_assessments(
            evidence=self.scoring_evidence,
            policy=self.policy,
        )
        if self.score_floor_assessments != expected_floors:
            raise ASRReliabilityQualificationError(
                "Qualification score-floor assessments are inconsistent."
            )
        if self.critical_confidence_assessments != expected_critical:
            raise ASRReliabilityQualificationError(
                "Qualification critical-confidence assessments are inconsistent."
            )

        robustness = (
            self.scoring_evidence.performance.matched_control_robustness
        )
        expected_support = (
            _scorecard_support_sufficient(self.scorecard),
            _matched_control_support_sufficient(
                robustness=robustness,
                policy=self.policy,
            ),
            self.matched_assurance.evidence == EvidenceAssessment.SUFFICIENT
            and structural_integrity,
            _critical_support_sufficient(
                evidence=self.scoring_evidence,
                policy=self.policy,
            ),
        )
        observed_support = (
            self.scorecard_support_sufficient,
            self.matched_control_support_sufficient,
            self.matched_assurance_support_sufficient,
            self.critical_support_sufficient,
        )
        if observed_support != expected_support:
            raise ASRReliabilityQualificationError(
                "Qualification support assessments are inconsistent."
            )

        integrity = (
            IntegrityAssessment.VALID
            if self.matched_assurance.integrity == IntegrityAssessment.VALID
            and structural_integrity
            else IntegrityAssessment.INVALID
        )
        critical = (
            CriticalAssessment.VIOLATED
            if self.scorecard.gate_status == ASRReliabilityGateStatus.TRIGGERED
            else CriticalAssessment.CLEAR
        )
        evidence = (
            EvidenceAssessment.SUFFICIENT
            if all(expected_support)
            else EvidenceAssessment.INSUFFICIENT
        )
        claim = _combine_claims(
            tuple(value.claim for value in expected_floors)
            + (self.matched_assurance.claim,)
            + tuple(value.claim for value in expected_critical)
        )
        expected_inputs = DecisionInputs(
            integrity=integrity,
            critical=critical,
            evidence=evidence,
            claim=claim,
        )
        if self.decision_inputs != expected_inputs:
            raise ASRReliabilityQualificationError(
                "Qualification decision inputs are inconsistent."
            )
        if self.decision != decide(expected_inputs):
            raise ASRReliabilityQualificationError(
                "Qualification verdict does not match the universal kernel."
            )

    @property
    def payload(self) -> dict[str, object]:
        evidence_payload = _scoring_evidence_payload(self.scoring_evidence)
        robustness = self.scoring_evidence.performance.matched_control_robustness
        familywise_confidence_ppm = (
            self.policy.critical_integrity_confidence
            .familywise_confidence_level_ppm
        )
        familywise_alpha = Fraction(
            ASR_RELIABILITY_RATE_SCALE - familywise_confidence_ppm,
            ASR_RELIABILITY_RATE_SCALE,
        )
        critical_counts = {
            key: (
                None
                if value is None
                else {
                    "successful_count": value.successful_count,
                    "observed_count": value.observed_count,
                    "expected_count": value.expected_count,
                    "complete": value.complete,
                }
            )
            for key, _label, value in _critical_groups(self.scoring_evidence)
        }
        return {
            "schema_version": ASR_RELIABILITY_QUALIFICATION_RESULT_SCHEMA_VERSION,
            "artifact": {
                "key": ASR_RELIABILITY_QUALIFICATION_RESULT_KEY,
                "version": ASR_RELIABILITY_QUALIFICATION_RESULT_VERSION,
                "type": "non_authoritative_qualification_decision",
            },
            "bindings": {
                "policy": {
                    "key": self.policy.key,
                    "version": self.policy.version,
                    "sha256": self.policy.sha256,
                },
                "profile_sha256": ASR_RELIABILITY_PROFILE_V1_SHA256,
                "scoring_sha256": ASR_RELIABILITY_SCORING_V1_SHA256,
                "decision_kernel": "hvee.core.decision.decide",
            },
            "inputs": {
                "scoring_evidence_sha256": hashlib.sha256(
                    _canonical_json_bytes(evidence_payload)
                ).hexdigest(),
                "scorecard_sha256": self.scorecard.sha256,
                "scorecard": self.scorecard.payload,
                "matched_release_assurance": _matched_assurance_payload(
                    self.matched_assurance
                ),
            },
            "score_floors": [
                value.payload for value in self.score_floor_assessments
            ],
            "support": {
                "scorecard": {
                    "required_maturity": (
                        ASRReliabilityMaturityStatus
                        .COMPLETE_DESCRIPTIVE_EVIDENCE.value
                    ),
                    "required_gate": ASRReliabilityGateStatus.CLEAR.value,
                    "observed_maturity": self.scorecard.maturity_status.value,
                    "observed_gate": self.scorecard.gate_status.value,
                    "sufficient": self.scorecard_support_sufficient,
                },
                "matched_control_pairs": {
                    "minimum_required": self.policy.minimum_matched_control_pairs,
                    "observed": (
                        None if robustness is None else robustness.observed_pair_count
                    ),
                    "expected": (
                        None if robustness is None else robustness.expected_pair_count
                    ),
                    "complete": None if robustness is None else robustness.complete,
                    "sufficient": self.matched_control_support_sufficient,
                },
                "matched_release_assurance": {
                    "observed": self.matched_assurance.evidence.value,
                    "sufficient": self.matched_assurance_support_sufficient,
                },
                "critical_integrity": {
                    "minimum_observations_per_group": (
                        self.policy.critical_integrity_confidence
                        .minimum_conclusive_observations_per_group
                    ),
                    "groups": critical_counts,
                    "sufficient": self.critical_support_sufficient,
                },
            },
            "critical_confidence": {
                "methodology": {
                    "rate_scale": ASR_RELIABILITY_RATE_SCALE,
                    "interval": "clopper_pearson_one_sided_lower_scaled",
                    "hypothesis_test_tail": (
                        ExactBinomialTail.GREATER_THAN_OR_EQUAL.value
                    ),
                    "multiplicity_control": "holm_step_down",
                    "support_rule": (
                        "lower_bound_meets_threshold_and_holm_rejected"
                    ),
                },
                "familywise_confidence_level_ppm": familywise_confidence_ppm,
                "familywise_alpha": _fraction_payload(familywise_alpha),
                "family_size": len(self.critical_confidence_assessments),
                "claims": [
                    value.payload
                    for value in self.critical_confidence_assessments
                ],
            },
            "decision": {
                "inputs": {
                    "integrity": self.decision_inputs.integrity.value,
                    "critical": self.decision_inputs.critical.value,
                    "evidence": self.decision_inputs.evidence.value,
                    "claim": self.decision_inputs.claim.value,
                },
                "verdict": self.decision.verdict.value,
                "reason": self.decision.reason.value,
            },
            "evidence_boundary": {
                "explicit_policy_applied": True,
                "scorecard_rebuilt_from_raw_evidence": True,
                "paired_assurance_recomputed": False,
                "matched_assurance_policy_binding_verified": True,
                "critical_confidence_bounds_computed": (
                    self.critical_support_sufficient
                ),
                "decision_kernel_called": True,
                "model_qualification_verdict_issued": True,
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


def evaluate_asr_reliability_qualification_v1(
    *,
    scoring_evidence: ASRReliabilityScoringEvidence,
    matched_assurance: ASRMatchedReleaseAssuranceResult,
    policy: ASRReliabilityQualificationPolicyV1,
) -> ASRReliabilityQualificationResult:
    """Apply one explicit policy and call the universal decision kernel."""

    if not isinstance(scoring_evidence, ASRReliabilityScoringEvidence):
        raise ASRReliabilityQualificationError(
            "Reliability qualification requires raw scoring evidence."
        )
    if not isinstance(matched_assurance, ASRMatchedReleaseAssuranceResult):
        raise ASRReliabilityQualificationError(
            "Reliability qualification requires matched release assurance."
        )
    try:
        verified_policy = verify_asr_reliability_qualification_policy_v1(
            policy
        )
    except Exception as error:
        raise ASRReliabilityQualificationError(
            "Reliability qualification requires the exact B11A policy."
        ) from error

    scorecard = score_asr_reliability_v1(evidence=scoring_evidence)
    structural_integrity = _verify_assurance_policy_binding(
        assurance=matched_assurance,
        policy=verified_policy,
    )
    floors = _score_floor_assessments(
        scorecard=scorecard,
        policy=verified_policy,
    )
    critical_confidence = _critical_confidence_assessments(
        evidence=scoring_evidence,
        policy=verified_policy,
    )
    robustness = scoring_evidence.performance.matched_control_robustness
    scorecard_support = _scorecard_support_sufficient(scorecard)
    matched_control_support = _matched_control_support_sufficient(
        robustness=robustness,
        policy=verified_policy,
    )
    matched_assurance_support = (
        matched_assurance.evidence == EvidenceAssessment.SUFFICIENT
        and structural_integrity
    )
    critical_support = _critical_support_sufficient(
        evidence=scoring_evidence,
        policy=verified_policy,
    )
    integrity = (
        IntegrityAssessment.VALID
        if matched_assurance.integrity == IntegrityAssessment.VALID
        and structural_integrity
        else IntegrityAssessment.INVALID
    )
    critical = (
        CriticalAssessment.VIOLATED
        if scorecard.gate_status == ASRReliabilityGateStatus.TRIGGERED
        else CriticalAssessment.CLEAR
    )
    evidence = (
        EvidenceAssessment.SUFFICIENT
        if all(
            (
                scorecard_support,
                matched_control_support,
                matched_assurance_support,
                critical_support,
            )
        )
        else EvidenceAssessment.INSUFFICIENT
    )
    claim = _combine_claims(
        tuple(value.claim for value in floors)
        + (matched_assurance.claim,)
        + tuple(value.claim for value in critical_confidence)
    )
    inputs = DecisionInputs(
        integrity=integrity,
        critical=critical,
        evidence=evidence,
        claim=claim,
    )

    return ASRReliabilityQualificationResult(
        policy=verified_policy,
        scoring_evidence=scoring_evidence,
        scorecard=scorecard,
        matched_assurance=matched_assurance,
        score_floor_assessments=floors,
        critical_confidence_assessments=critical_confidence,
        scorecard_support_sufficient=scorecard_support,
        matched_control_support_sufficient=matched_control_support,
        matched_assurance_support_sufficient=matched_assurance_support,
        critical_support_sufficient=critical_support,
        decision_inputs=inputs,
        decision=decide(inputs),
    )

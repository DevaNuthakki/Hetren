"""Define explicit qualification policy inputs for ASR Reliability v1.

B10H produces descriptive, explainable scorecards.  B11A defines the policy
contract that a later evaluator will apply to those scorecards and their
underlying statistical evidence.  Every threshold and sample requirement is
explicit.  This module does not evaluate evidence, issue a verdict, qualify a
model for production, or authorize release enforcement.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.critical_number_private_statistics import (
    CRITICAL_NUMBER_PRIVATE_MULTIPLICITY_CONTROL_KEY,
    CRITICAL_NUMBER_PRIVATE_MULTIPLICITY_CONTROL_VERSION,
)
from hvee.packs.asr.release_assurance_policy import (
    ASRMatchedReleaseAssurancePolicyV1,
)
from hvee.packs.asr.reliability_profile import (
    ASR_RELIABILITY_PROFILE_V1,
    ASR_RELIABILITY_PROFILE_V1_SHA256,
)
from hvee.packs.asr.reliability_scoring import (
    ASR_RELIABILITY_SCORING_V1,
    ASR_RELIABILITY_SCORING_V1_SHA256,
    ASRReliabilityGateStatus,
    ASRReliabilityMaturityStatus,
)


ASR_RELIABILITY_QUALIFICATION_POLICY_SCHEMA_VERSION = 1
ASR_RELIABILITY_QUALIFICATION_POLICY_KEY = (
    "hetren.asr.reliability-qualification"
)
ASR_RELIABILITY_QUALIFICATION_POLICY_VERSION = "1.0.0"
ASR_CRITICAL_INTEGRITY_CONFIDENCE_METHOD_KEY = (
    "exact-binomial-one-sided-lower-bound"
)
ASR_CRITICAL_INTEGRITY_CONFIDENCE_METHOD_VERSION = "1.0.0"
ASR_CRITICAL_INTEGRITY_CLAIM_COUNT_V1 = 3
ASR_RELIABILITY_RATE_SCALE = 1_000_000


class ASRReliabilityQualificationPolicyError(HveeContractError):
    """Raised when an ASR Reliability qualification policy is invalid."""


def _require_score(*, name: str, value: object) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or not 0.0 <= float(value) <= 100.0
    ):
        raise ASRReliabilityQualificationPolicyError(
            f"{name} must be a finite score between 0 and 100."
        )

    return float(value)


def _require_positive_integer(*, name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ASRReliabilityQualificationPolicyError(
            f"{name} must be a positive integer."
        )

    return value


def _require_rate(*, name: str, value: object, interior: bool) -> int:
    valid = (
        not isinstance(value, bool)
        and isinstance(value, int)
        and 0 <= value <= ASR_RELIABILITY_RATE_SCALE
    )

    if interior:
        valid = valid and 0 < value < ASR_RELIABILITY_RATE_SCALE

    if not valid:
        boundary = "strictly between 0 and 1,000,000" if interior else (
            "between 0 and 1,000,000 inclusive"
        )
        raise ASRReliabilityQualificationPolicyError(
            f"{name} must be an integer {boundary}."
        )

    return value


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
        raise ASRReliabilityQualificationPolicyError(
            "ASR Reliability qualification policy must be deterministic JSON."
        ) from error


@dataclass(frozen=True, slots=True)
class ASRCriticalIntegrityConfidencePolicyV1:
    """Simultaneous confidence requirements for three critical-content axes."""

    familywise_confidence_level_ppm: int
    minimum_conclusive_observations_per_group: int
    minimum_preservation_lower_bound_ppm: int

    def __post_init__(self) -> None:
        _require_rate(
            name="Critical-integrity family-wise confidence level",
            value=self.familywise_confidence_level_ppm,
            interior=True,
        )
        _require_positive_integer(
            name="Critical-integrity minimum conclusive observations",
            value=self.minimum_conclusive_observations_per_group,
        )
        _require_rate(
            name="Critical-integrity minimum preservation lower bound",
            value=self.minimum_preservation_lower_bound_ppm,
            interior=False,
        )

    @property
    def payload(self) -> dict[str, object]:
        return {
            "method": {
                "key": ASR_CRITICAL_INTEGRITY_CONFIDENCE_METHOD_KEY,
                "version": ASR_CRITICAL_INTEGRITY_CONFIDENCE_METHOD_VERSION,
                "interval_side": "one_sided_lower",
                "distribution": "binomial",
            },
            "multiplicity_control": {
                "key": CRITICAL_NUMBER_PRIVATE_MULTIPLICITY_CONTROL_KEY,
                "version": CRITICAL_NUMBER_PRIVATE_MULTIPLICITY_CONTROL_VERSION,
                "family": [
                    "critical_number_integrity",
                    "critical_identifier_integrity",
                    "critical_terminology_integrity",
                ],
                "claim_count": ASR_CRITICAL_INTEGRITY_CLAIM_COUNT_V1,
            },
            "rate_scale": ASR_RELIABILITY_RATE_SCALE,
            "familywise_confidence_level_ppm": (
                self.familywise_confidence_level_ppm
            ),
            "minimum_conclusive_observations_per_group": (
                self.minimum_conclusive_observations_per_group
            ),
            "minimum_preservation_lower_bound_ppm": (
                self.minimum_preservation_lower_bound_ppm
            ),
            "insufficient_minimum_behavior": "insufficient_evidence",
        }


def _matched_assurance_payload(
    value: ASRMatchedReleaseAssurancePolicyV1,
) -> dict[str, object]:
    return {
        "key": value.key,
        "version": value.version,
        "interval": {
            "method": value.interval.method.value,
            "confidence_level": value.interval.confidence_level,
            "minimum_usable_pairs": value.interval.minimum_usable_pairs,
            "resamples": value.interval.resamples,
            "random_seed": value.interval.random_seed,
        },
        "normalized_wer_noninferiority_margin": (
            value.normalized_wer_noninferiority_margin
        ),
        "normalized_cer_noninferiority_margin": (
            value.normalized_cer_noninferiority_margin
        ),
    }


@dataclass(frozen=True, slots=True)
class ASRReliabilityQualificationPolicyV1:
    """Explicit inputs for a later four-state Reliability decision."""

    minimum_hetren_reliability_index: float
    minimum_reliability_performance_index: float
    minimum_evidence_assurance_index: float
    minimum_operational_fitness_index: float
    minimum_matched_control_robustness_score: float
    minimum_critical_integrity_group_score: float
    minimum_matched_control_pairs: int
    matched_release_assurance: ASRMatchedReleaseAssurancePolicyV1
    critical_integrity_confidence: ASRCriticalIntegrityConfidencePolicyV1

    def __post_init__(self) -> None:
        for name, value in (
            (
                "Minimum Hetren Reliability Index",
                self.minimum_hetren_reliability_index,
            ),
            (
                "Minimum Reliability Performance Index",
                self.minimum_reliability_performance_index,
            ),
            (
                "Minimum Evidence Assurance Index",
                self.minimum_evidence_assurance_index,
            ),
            (
                "Minimum Operational Fitness Index",
                self.minimum_operational_fitness_index,
            ),
            (
                "Minimum matched-control robustness score",
                self.minimum_matched_control_robustness_score,
            ),
            (
                "Minimum critical-integrity group score",
                self.minimum_critical_integrity_group_score,
            ),
        ):
            _require_score(name=name, value=value)

        _require_positive_integer(
            name="Minimum matched-control pairs",
            value=self.minimum_matched_control_pairs,
        )

        if self.minimum_matched_control_pairs < 2:
            raise ASRReliabilityQualificationPolicyError(
                "Minimum matched-control pairs must be at least 2."
            )

        if not isinstance(
            self.matched_release_assurance,
            ASRMatchedReleaseAssurancePolicyV1,
        ):
            raise ASRReliabilityQualificationPolicyError(
                "Reliability qualification requires matched release "
                "assurance policy v1."
            )

        if not isinstance(
            self.critical_integrity_confidence,
            ASRCriticalIntegrityConfidencePolicyV1,
        ):
            raise ASRReliabilityQualificationPolicyError(
                "Reliability qualification requires critical-integrity "
                "confidence policy v1."
            )

    @property
    def key(self) -> str:
        return ASR_RELIABILITY_QUALIFICATION_POLICY_KEY

    @property
    def version(self) -> str:
        return ASR_RELIABILITY_QUALIFICATION_POLICY_VERSION

    @property
    def payload(self) -> dict[str, object]:
        return {
            "schema_version": (
                ASR_RELIABILITY_QUALIFICATION_POLICY_SCHEMA_VERSION
            ),
            "policy": {
                "key": self.key,
                "version": self.version,
                "type": "explicit_reliability_qualification_policy",
            },
            "bindings": {
                "profile": {
                    "key": ASR_RELIABILITY_PROFILE_V1.key,
                    "version": ASR_RELIABILITY_PROFILE_V1.version,
                    "sha256": ASR_RELIABILITY_PROFILE_V1_SHA256,
                },
                "scoring": {
                    "key": ASR_RELIABILITY_SCORING_V1.key,
                    "version": ASR_RELIABILITY_SCORING_V1.version,
                    "sha256": ASR_RELIABILITY_SCORING_V1_SHA256,
                },
            },
            "scorecard_requirements": {
                "required_maturity_status": (
                    ASRReliabilityMaturityStatus
                    .COMPLETE_DESCRIPTIVE_EVIDENCE.value
                ),
                "required_gate_status": ASRReliabilityGateStatus.CLEAR.value,
                "score_floors": {
                    "hetren_reliability_index": (
                        self.minimum_hetren_reliability_index
                    ),
                    "reliability_performance_index": (
                        self.minimum_reliability_performance_index
                    ),
                    "evidence_assurance_index": (
                        self.minimum_evidence_assurance_index
                    ),
                    "operational_fitness_index": (
                        self.minimum_operational_fitness_index
                    ),
                    "matched_control_robustness": (
                        self.minimum_matched_control_robustness_score
                    ),
                    "each_critical_integrity_group": (
                        self.minimum_critical_integrity_group_score
                    ),
                },
            },
            "support_requirements": {
                "minimum_matched_control_pairs": (
                    self.minimum_matched_control_pairs
                ),
                "critical_integrity": (
                    self.critical_integrity_confidence.payload
                ),
            },
            "statistical_assurance": {
                "matched_release": _matched_assurance_payload(
                    self.matched_release_assurance
                ),
                "critical_integrity": (
                    self.critical_integrity_confidence.payload
                ),
            },
            "decision_mapping": {
                "kernel": "hvee.core.decision.decide",
                "invalid_integrity": "invalid",
                "known_hard_gate_violation": "fail",
                "insufficient_support_or_confidence": "inconclusive",
                "contradicted_qualification_claim": "fail",
                "unresolved_qualification_claim": "inconclusive",
                "supported_qualification_claim": "pass",
            },
            "evidence_boundary": {
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
            },
        }

    @property
    def sha256(self) -> str:
        return hashlib.sha256(_canonical_json_bytes(self.payload)).hexdigest()

    def require_qualification_decision(self) -> None:
        raise ASRReliabilityQualificationPolicyError(
            "B11A defines qualification policy inputs only; no scorecard "
            "was evaluated and no qualification verdict was issued."
        )


def build_asr_reliability_qualification_policy_v1(
    *,
    minimum_hetren_reliability_index: float,
    minimum_reliability_performance_index: float,
    minimum_evidence_assurance_index: float,
    minimum_operational_fitness_index: float,
    minimum_matched_control_robustness_score: float,
    minimum_critical_integrity_group_score: float,
    minimum_matched_control_pairs: int,
    matched_release_assurance: ASRMatchedReleaseAssurancePolicyV1,
    critical_integrity_confidence: ASRCriticalIntegrityConfidencePolicyV1,
) -> ASRReliabilityQualificationPolicyV1:
    """Build one explicit policy without hidden statistical defaults."""

    return ASRReliabilityQualificationPolicyV1(
        minimum_hetren_reliability_index=(
            minimum_hetren_reliability_index
        ),
        minimum_reliability_performance_index=(
            minimum_reliability_performance_index
        ),
        minimum_evidence_assurance_index=minimum_evidence_assurance_index,
        minimum_operational_fitness_index=minimum_operational_fitness_index,
        minimum_matched_control_robustness_score=(
            minimum_matched_control_robustness_score
        ),
        minimum_critical_integrity_group_score=(
            minimum_critical_integrity_group_score
        ),
        minimum_matched_control_pairs=minimum_matched_control_pairs,
        matched_release_assurance=matched_release_assurance,
        critical_integrity_confidence=critical_integrity_confidence,
    )


def verify_asr_reliability_qualification_policy_v1(
    value: ASRReliabilityQualificationPolicyV1,
) -> ASRReliabilityQualificationPolicyV1:
    """Require the exact B11A policy schema and scientific bindings."""

    if not isinstance(value, ASRReliabilityQualificationPolicyV1):
        raise ASRReliabilityQualificationPolicyError(
            "ASR Reliability qualification verification requires policy v1."
        )

    if (
        value.key != ASR_RELIABILITY_QUALIFICATION_POLICY_KEY
        or value.version != ASR_RELIABILITY_QUALIFICATION_POLICY_VERSION
        or value.payload["bindings"]["profile"]["sha256"]
        != ASR_RELIABILITY_PROFILE_V1_SHA256
        or value.payload["bindings"]["scoring"]["sha256"]
        != ASR_RELIABILITY_SCORING_V1_SHA256
    ):
        raise ASRReliabilityQualificationPolicyError(
            "ASR Reliability qualification policy identity or bindings "
            "are unsupported."
        )

    return value

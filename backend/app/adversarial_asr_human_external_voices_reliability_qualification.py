"""Evaluate VOiCES two-model evidence under one explicit Reliability policy.

B11C projects the application-owned B9 execution into the domain-neutral
Reliability scoring and matched-assurance contracts.  B11B applies an
explicit B11A policy to those contracts.  This B11D composition is the only
place that joins those two operations for the VOiCES cohort.

The resulting verdict is deliberately non-authoritative.  It may be pass,
fail, inconclusive, or invalid under the universal decision kernel, but it
does not certify a model, qualify production use, declare a winner, or
authorize release enforcement.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from app.adversarial_asr_human_external_voices_model_comparison_execution import (
    ASRAdversarialVOiCESModelComparisonExecutionBundle,
)
from app.adversarial_asr_human_external_voices_reliability_projection import (
    ASR_ADVERSARIAL_VOICES_RELIABILITY_PROJECTION_KEY,
    ASR_ADVERSARIAL_VOICES_RELIABILITY_PROJECTION_VERSION,
    ASRAdversarialVOiCESReliabilityProjectionBundle,
    project_asr_adversarial_voices_reliability_evidence_v1,
)
from hvee.core.contracts import HveeContractError
from hvee.packs.asr.reliability_qualification import (
    ASR_RELIABILITY_QUALIFICATION_RESULT_KEY,
    ASR_RELIABILITY_QUALIFICATION_RESULT_VERSION,
    ASRReliabilityQualificationResult,
    evaluate_asr_reliability_qualification_v1,
)
from hvee.packs.asr.reliability_qualification_policy import (
    ASRReliabilityQualificationPolicyV1,
    verify_asr_reliability_qualification_policy_v1,
)


ASR_ADVERSARIAL_VOICES_RELIABILITY_QUALIFICATION_SCHEMA_VERSION = 1
ASR_ADVERSARIAL_VOICES_RELIABILITY_QUALIFICATION_VERSION = "1.0.0"
ASR_ADVERSARIAL_VOICES_RELIABILITY_QUALIFICATION_KEY = (
    "hetren.asr.adversarial-human-external-voices-"
    "reliability-qualification"
)


class ASRAdversarialVOiCESReliabilityQualificationError(HveeContractError):
    """Raised when B11D inputs or derived qualification are inconsistent."""


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
        raise ASRAdversarialVOiCESReliabilityQualificationError(
            "VOiCES Reliability qualification must be deterministic JSON."
        ) from error


def _reverify_policy(
    value: object,
) -> ASRReliabilityQualificationPolicyV1:
    try:
        return verify_asr_reliability_qualification_policy_v1(value)
    except Exception as error:
        raise ASRAdversarialVOiCESReliabilityQualificationError(
            "VOiCES Reliability qualification requires the exact B11A policy."
        ) from error


def _reverify_projection(
    *,
    value: object,
    policy: ASRReliabilityQualificationPolicyV1,
) -> ASRAdversarialVOiCESReliabilityProjectionBundle:
    if not isinstance(
        value,
        ASRAdversarialVOiCESReliabilityProjectionBundle,
    ):
        raise ASRAdversarialVOiCESReliabilityQualificationError(
            "VOiCES Reliability qualification requires the exact B11C "
            "projection."
        )

    try:
        reverified = project_asr_adversarial_voices_reliability_evidence_v1(
            execution=value.execution,
            baseline_run_id=value.baseline_run_id,
            candidate_run_id=value.candidate_run_id,
            matched_release_assurance_policy=(
                policy.matched_release_assurance
            ),
        )
    except Exception as error:
        raise ASRAdversarialVOiCESReliabilityQualificationError(
            "VOiCES B11C projection failed revalidation."
        ) from error

    if reverified != value or reverified.sha256 != value.sha256:
        raise ASRAdversarialVOiCESReliabilityQualificationError(
            "VOiCES B11C projection identity changed."
        )

    return reverified


def _reverify_qualification(
    *,
    value: object,
    projection: ASRAdversarialVOiCESReliabilityProjectionBundle,
    policy: ASRReliabilityQualificationPolicyV1,
) -> ASRReliabilityQualificationResult:
    if not isinstance(value, ASRReliabilityQualificationResult):
        raise ASRAdversarialVOiCESReliabilityQualificationError(
            "VOiCES Reliability qualification requires the exact B11B result."
        )

    try:
        reverified = evaluate_asr_reliability_qualification_v1(
            scoring_evidence=projection.scoring_evidence,
            matched_assurance=projection.matched_assurance,
            policy=policy,
        )
    except Exception as error:
        raise ASRAdversarialVOiCESReliabilityQualificationError(
            "VOiCES B11B qualification failed revalidation."
        ) from error

    if reverified != value or reverified.sha256 != value.sha256:
        raise ASRAdversarialVOiCESReliabilityQualificationError(
            "VOiCES B11B qualification identity changed."
        )

    return reverified


def _require_voices_evidence_scope(
    projection: ASRAdversarialVOiCESReliabilityProjectionBundle,
) -> None:
    performance = projection.scoring_evidence.performance
    if any(
        value is not None
        for value in (
            performance.critical_number_integrity,
            performance.critical_identifier_integrity,
            performance.critical_terminology_integrity,
            projection.scoring_evidence.reproducibility,
        )
    ):
        raise ASRAdversarialVOiCESReliabilityQualificationError(
            "General VOiCES evidence cannot claim critical-content or "
            "multi-run reproducibility qualification support."
        )


@dataclass(frozen=True, slots=True)
class ASRAdversarialVOiCESReliabilityQualificationBundle:
    """One deterministic, non-authoritative B11D evaluation bundle."""

    projection: ASRAdversarialVOiCESReliabilityProjectionBundle
    policy: ASRReliabilityQualificationPolicyV1
    qualification: ASRReliabilityQualificationResult

    def __post_init__(self) -> None:
        verified_policy = _reverify_policy(self.policy)

        if (
            self.projection.matched_release_assurance_policy
            != verified_policy.matched_release_assurance
        ):
            raise ASRAdversarialVOiCESReliabilityQualificationError(
                "VOiCES projection matched-assurance policy does not match "
                "the complete B11A policy."
            )

        verified_projection = _reverify_projection(
            value=self.projection,
            policy=verified_policy,
        )
        _require_voices_evidence_scope(verified_projection)
        _reverify_qualification(
            value=self.qualification,
            projection=verified_projection,
            policy=verified_policy,
        )

    @property
    def execution(self) -> ASRAdversarialVOiCESModelComparisonExecutionBundle:
        return self.projection.execution

    @property
    def payload(self) -> dict[str, object]:
        projection_payload = self.projection.payload
        qualification_payload = self.qualification.payload

        return {
            "schema_version": (
                ASR_ADVERSARIAL_VOICES_RELIABILITY_QUALIFICATION_SCHEMA_VERSION
            ),
            "artifact": {
                "key": ASR_ADVERSARIAL_VOICES_RELIABILITY_QUALIFICATION_KEY,
                "version": (
                    ASR_ADVERSARIAL_VOICES_RELIABILITY_QUALIFICATION_VERSION
                ),
                "type": "voices_non_authoritative_reliability_qualification",
            },
            "upstream": {
                "b9_execution_sha256": self.execution.sha256,
                "b11c_projection": {
                    "key": ASR_ADVERSARIAL_VOICES_RELIABILITY_PROJECTION_KEY,
                    "version": (
                        ASR_ADVERSARIAL_VOICES_RELIABILITY_PROJECTION_VERSION
                    ),
                    "sha256": self.projection.sha256,
                },
                "b11b_qualification": {
                    "key": ASR_RELIABILITY_QUALIFICATION_RESULT_KEY,
                    "version": ASR_RELIABILITY_QUALIFICATION_RESULT_VERSION,
                    "sha256": self.qualification.sha256,
                },
            },
            "bindings": {
                "policy": {
                    "key": self.policy.key,
                    "version": self.policy.version,
                    "sha256": self.policy.sha256,
                },
                "decision_kernel": "hvee.core.decision.decide",
                "matched_assurance_policy_from_complete_policy": True,
            },
            "runs": projection_payload["runs"],
            "decision": qualification_payload["decision"],
            "support": qualification_payload["support"],
            "projection": projection_payload,
            "qualification": qualification_payload,
            "evidence_boundary": {
                "development_evidence_only": True,
                "b9_execution_reverified": True,
                "b11c_projection_rebuilt": True,
                "explicit_b11a_policy_applied": True,
                "b11b_qualification_recomputed": True,
                "decision_kernel_called": True,
                "critical_content_qualification_evidence_claimed": False,
                "non_authoritative_model_qualification_verdict_issued": True,
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

    def require_certification(self) -> None:
        raise ASRAdversarialVOiCESReliabilityQualificationError(
            "VOiCES B11D is a non-authoritative qualification evaluation; "
            "it does not certify a model or qualify production use."
        )


def evaluate_asr_adversarial_voices_reliability_qualification_v1(
    *,
    execution: ASRAdversarialVOiCESModelComparisonExecutionBundle,
    baseline_run_id: int,
    candidate_run_id: int,
    policy: ASRReliabilityQualificationPolicyV1,
) -> ASRAdversarialVOiCESReliabilityQualificationBundle:
    """Project B9 evidence and apply one complete explicit policy."""

    verified_policy = _reverify_policy(policy)
    projection = project_asr_adversarial_voices_reliability_evidence_v1(
        execution=execution,
        baseline_run_id=baseline_run_id,
        candidate_run_id=candidate_run_id,
        matched_release_assurance_policy=(
            verified_policy.matched_release_assurance
        ),
    )
    qualification = evaluate_asr_reliability_qualification_v1(
        scoring_evidence=projection.scoring_evidence,
        matched_assurance=projection.matched_assurance,
        policy=verified_policy,
    )

    return ASRAdversarialVOiCESReliabilityQualificationBundle(
        projection=projection,
        policy=verified_policy,
        qualification=qualification,
    )

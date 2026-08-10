"""Governance-review readiness for Critical Number Fidelity v1.

This module composes already-sealed evaluator-assurance, private statistical,
production-derived, and matched-release shadow evidence into one deterministic
readiness dossier.

Readiness is intentionally not certification.  This module cannot qualify the
evaluator for production, enable release enforcement, or modify an official
release decision.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum

from hvee.core.contracts import HveeContractError
from hvee.core.observation_evidence import ObservationEvidenceRecord
from hvee.packs.asr.critical_number_assurance import (
    CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SHA256_V1,
    CRITICAL_NUMBER_ASSURANCE_PROFILE_KEY,
    CRITICAL_NUMBER_ASSURANCE_PROFILE_VERSION,
    ASRCriticalNumberAssuranceEvidenceBundle,
    ASRCriticalNumberAssuranceStatus,
    verify_critical_number_assurance_evidence_bundle,
)
from hvee.packs.asr.critical_number_private_assessment import (
    ASRCriticalNumberPrivateStatisticalAssessmentBundle,
    ASRCriticalNumberPrivateStatisticalAssessmentResult,
    verify_critical_number_private_statistical_assessment_v1,
)
from hvee.packs.asr.critical_number_private_evidence import (
    ASRCriticalNumberPrivateEvidenceDisclosureDefinition,
    ASRCriticalNumberPrivateEvidenceDisclosureManifestBundle,
    ASRCriticalNumberPrivateEvidenceVerifiedEnvelope,
)
from hvee.packs.asr.critical_number_private_holdout import (
    ASRCriticalNumberPrivateHoldoutBlindRunBundle,
    ASRCriticalNumberPrivateHoldoutBlindRunDefinition,
    ASRCriticalNumberPrivateHoldoutPlanBundle,
    ASRCriticalNumberPrivateHoldoutPlanDefinition,
)
from hvee.packs.asr.critical_number_private_qualification import (
    ASRCriticalNumberPrivateQualificationAdjudicationBundle,
    ASRCriticalNumberPrivateQualificationAdjudicationDefinition,
    ASRCriticalNumberPrivateQualificationCampaignBundle,
    ASRCriticalNumberPrivateQualificationCampaignDefinition,
    ASRCriticalNumberPrivateQualificationProtocolBundle,
    calculate_critical_number_private_qualification_sha256,
)
from hvee.packs.asr.critical_number_private_statistics import (
    CRITICAL_NUMBER_PRIVATE_STATISTICAL_METHOD_KEY,
    CRITICAL_NUMBER_PRIVATE_STATISTICAL_METHOD_VERSION,
    ASRCriticalNumberPrivateStatisticalMethodManifestBundle,
    verify_critical_number_private_statistical_method_manifest_v1,
)
from hvee.packs.asr.critical_number_production_evidence import (
    CRITICAL_NUMBER_PRODUCTION_EVIDENCE_PROTOCOL_KEY,
    CRITICAL_NUMBER_PRODUCTION_EVIDENCE_PROTOCOL_VERSION,
    ASRCriticalNumberPrivateHoldoutExclusionManifestBundle,
    ASRCriticalNumberProductionEvidenceDefinition,
    ASRCriticalNumberProductionEvidenceManifestBundle,
    calculate_critical_number_production_evidence_sha256,
    verify_critical_number_private_holdout_exclusion_manifest,
    verify_critical_number_production_evidence_manifest,
)
from hvee.packs.asr.critical_number_release_shadow import (
    CRITICAL_NUMBER_MATCHED_RELEASE_SHADOW_KEY,
    CRITICAL_NUMBER_MATCHED_RELEASE_SHADOW_VERSION,
    ASRCriticalNumberMatchedReleaseShadowResult,
    evaluate_asr_critical_number_matched_release_shadow,
)
from hvee.packs.asr.release_assurance_policy import (
    ASRMatchedReleaseAssurancePolicyV1,
)


CRITICAL_NUMBER_QUALIFICATION_READINESS_SCHEMA_VERSION = 1
CRITICAL_NUMBER_QUALIFICATION_READINESS_KEY = (
    "hetren.asr.critical-number-qualification-readiness.en-us"
)
CRITICAL_NUMBER_QUALIFICATION_READINESS_VERSION = "1.0.0"


class ASRCriticalNumberQualificationReadinessResult(StrEnum):
    """Non-certifying evidence-readiness disposition."""

    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CRITERIA_NOT_MET = "criteria_not_met"
    READY_FOR_GOVERNANCE_REVIEW = "ready_for_governance_review"


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberQualificationReadinessBundle:
    """Deterministic governance-review readiness artifact."""

    payload: dict[str, object]
    sha256: str


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberPrivateQualificationVerificationContext:
    """Inputs required to reverify the complete sealed private chain."""

    adjudication: ASRCriticalNumberPrivateQualificationAdjudicationBundle
    campaign: ASRCriticalNumberPrivateQualificationCampaignBundle
    protocol: ASRCriticalNumberPrivateQualificationProtocolBundle
    campaign_definition: ASRCriticalNumberPrivateQualificationCampaignDefinition
    plan: ASRCriticalNumberPrivateHoldoutPlanBundle
    plan_definition: ASRCriticalNumberPrivateHoldoutPlanDefinition
    run: ASRCriticalNumberPrivateHoldoutBlindRunBundle
    run_definition: ASRCriticalNumberPrivateHoldoutBlindRunDefinition
    disclosure_manifest: ASRCriticalNumberPrivateEvidenceDisclosureManifestBundle
    disclosure_definition: ASRCriticalNumberPrivateEvidenceDisclosureDefinition
    verified_plan_envelope: ASRCriticalNumberPrivateEvidenceVerifiedEnvelope
    verified_run_envelope: ASRCriticalNumberPrivateEvidenceVerifiedEnvelope
    verified_disclosure_envelope: ASRCriticalNumberPrivateEvidenceVerifiedEnvelope
    adjudication_definition: (
        ASRCriticalNumberPrivateQualificationAdjudicationDefinition
    )


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberProductionEvidenceVerificationContext:
    """Inputs required to reverify production evidence and holdout exclusion."""

    plan: ASRCriticalNumberPrivateHoldoutPlanBundle
    plan_definition: ASRCriticalNumberPrivateHoldoutPlanDefinition
    linkage_tokens: tuple[str, ...]
    definition: ASRCriticalNumberProductionEvidenceDefinition


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberMatchedReleaseShadowVerificationContext:
    """Raw inputs required to rebuild matched-release shadow evidence."""

    baseline_run_id: int
    candidate_run_id: int
    declared_test_case_ids: tuple[int, ...]
    policy: ASRMatchedReleaseAssurancePolicyV1
    records: tuple[ObservationEvidenceRecord, ...]


def _require_sha256(*, name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise HveeContractError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _require_dict(*, name: str, value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise HveeContractError(f"{name} must be an object")
    return value


def _require_string(*, name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise HveeContractError(f"{name} must be a non-empty string")
    return value


def _canonical_json(value: object) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise HveeContractError(
            "critical-number qualification-readiness evidence must be "
            "deterministic JSON"
        ) from exc


def calculate_critical_number_qualification_readiness_sha256(
    payload: object,
) -> str:
    """Return the canonical digest for a readiness artifact."""

    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _enum_value(*, name: str, value: object) -> str:
    enum_value = getattr(value, "value", None)
    if not isinstance(enum_value, str):
        raise HveeContractError(f"{name} must be a versioned enum value")
    return enum_value


def _validate_private_assessment(
    *,
    assessment: ASRCriticalNumberPrivateStatisticalAssessmentBundle,
    method_manifest: ASRCriticalNumberPrivateStatisticalMethodManifestBundle,
    verification: ASRCriticalNumberPrivateQualificationVerificationContext,
) -> ASRCriticalNumberPrivateStatisticalAssessmentResult:
    if not isinstance(
        assessment,
        ASRCriticalNumberPrivateStatisticalAssessmentBundle,
    ):
        raise HveeContractError(
            "qualification readiness requires a private statistical assessment"
        )
    if not isinstance(
        verification,
        ASRCriticalNumberPrivateQualificationVerificationContext,
    ):
        raise HveeContractError(
            "qualification readiness requires private verification context"
        )

    assessment = verify_critical_number_private_statistical_assessment_v1(
        payload=assessment.payload,
        expected_sha256=assessment.sha256,
        method_manifest=method_manifest,
        adjudication=verification.adjudication,
        campaign=verification.campaign,
        protocol=verification.protocol,
        campaign_definition=verification.campaign_definition,
        plan=verification.plan,
        plan_definition=verification.plan_definition,
        run=verification.run,
        run_definition=verification.run_definition,
        disclosure_manifest=verification.disclosure_manifest,
        disclosure_definition=verification.disclosure_definition,
        verified_plan_envelope=verification.verified_plan_envelope,
        verified_run_envelope=verification.verified_run_envelope,
        verified_disclosure_envelope=(
            verification.verified_disclosure_envelope
        ),
        adjudication_definition=verification.adjudication_definition,
    )

    expected_digest = _require_sha256(
        name="private statistical assessment SHA-256",
        value=assessment.sha256,
    )
    payload = _require_dict(
        name="private statistical assessment payload",
        value=assessment.payload,
    )
    if calculate_critical_number_private_qualification_sha256(
        payload
    ) != expected_digest:
        raise HveeContractError(
            "private statistical assessment does not match its SHA-256"
        )

    method = _require_dict(
        name="private statistical assessment method",
        value=payload.get("method"),
    )
    if (
        method.get("key") != CRITICAL_NUMBER_PRIVATE_STATISTICAL_METHOD_KEY
        or method.get("version")
        != CRITICAL_NUMBER_PRIVATE_STATISTICAL_METHOD_VERSION
        or method.get("artifact") != "private_statistical_assessment"
        or method.get("manifest_sha256") != method_manifest.sha256
    ):
        raise HveeContractError(
            "private statistical assessment method binding is inconsistent"
        )

    sealed_evidence = _require_dict(
        name="private statistical assessment sealed evidence",
        value=payload.get("sealed_evidence"),
    )
    if sealed_evidence.get("complete_chain_reverified") is not True:
        raise HveeContractError(
            "private statistical assessment did not reverify its sealed chain"
        )
    for key in (
        "qualification_protocol_sha256",
        "qualification_campaign_sha256",
        "private_adjudication_sha256",
        "statistical_criteria_sha256",
    ):
        _require_sha256(
            name=f"private statistical assessment {key}",
            value=sealed_evidence.get(key),
        )

    expected_qualification = {
        "campaign_mechanics_verified": True,
        "statistical_qualification_assessed": True,
        "evaluator_status": "experimental",
        "certification_issued": False,
        "production_qualified": False,
        "release_enforcement_eligible": False,
        "official_release_verdict_modified": False,
    }
    if payload.get("qualification") != expected_qualification:
        raise HveeContractError(
            "private statistical assessment qualification boundary changed"
        )

    expected_confidentiality = {
        "private_case_content_in_artifact": False,
        "expected_results_in_artifact": False,
        "private_provenance_in_artifact": False,
        "evaluator_outputs_in_artifact": False,
        "private_salts_in_artifact": False,
        "case_tokens_in_artifact": False,
        "aggregate_outcomes_only": True,
    }
    if payload.get("confidentiality") != expected_confidentiality:
        raise HveeContractError(
            "private statistical assessment confidentiality boundary changed"
        )

    result = _require_dict(
        name="private statistical assessment result",
        value=payload.get("result"),
    )
    raw_result = result.get("value")
    try:
        assessment_result = (
            ASRCriticalNumberPrivateStatisticalAssessmentResult(raw_result)
        )
    except (TypeError, ValueError) as exc:
        raise HveeContractError(
            "private statistical assessment result is invalid"
        ) from exc

    all_minimums_met = result.get("all_minimums_met")
    all_fraction_gates_met = result.get("all_fraction_gates_met")
    all_statistical_claims_met = result.get("all_statistical_claims_met")

    if not isinstance(all_minimums_met, bool):
        raise HveeContractError(
            "private statistical assessment minimum result is invalid"
        )
    if not isinstance(all_fraction_gates_met, bool):
        raise HveeContractError(
            "private statistical assessment fraction-gate result is invalid"
        )
    if (
        all_statistical_claims_met is not None
        and not isinstance(all_statistical_claims_met, bool)
    ):
        raise HveeContractError(
            "private statistical assessment claim result is invalid"
        )

    if (
        assessment_result
        == ASRCriticalNumberPrivateStatisticalAssessmentResult
        .INSUFFICIENT_EVIDENCE
    ):
        if all_minimums_met is not False:
            raise HveeContractError(
                "insufficient private assessment has inconsistent minimums"
            )
    elif (
        assessment_result
        == ASRCriticalNumberPrivateStatisticalAssessmentResult
        .MEETS_PREREGISTERED_CRITERIA
    ):
        if (
            all_minimums_met is not True
            or all_fraction_gates_met is not True
            or all_statistical_claims_met is not True
        ):
            raise HveeContractError(
                "meeting private assessment has inconsistent criteria results"
            )
    else:
        if (
            all_minimums_met is not True
            or (
                all_fraction_gates_met is True
                and all_statistical_claims_met is True
            )
        ):
            raise HveeContractError(
                "non-meeting private assessment has inconsistent criteria "
                "results"
            )

    return assessment_result


def _validate_production_boundaries(
    *,
    name: str,
    payload: dict[str, object],
) -> None:
    expected_evidence_boundary = {
        "evaluator_development_use_only": True,
        "production_origin_attested_not_independently_verified": True,
        "legal_compliance_determined": False,
        "privacy_compliance_determined": False,
        "certification_issued": False,
        "production_qualified": False,
        "release_enforcement_eligible": False,
        "official_release_verdict_modified": False,
    }
    if payload.get("evidence_boundary") != expected_evidence_boundary:
        raise HveeContractError(
            f"{name} evidence boundary changed"
        )

    expected_confidentiality = {
        "raw_audio_in_artifact": False,
        "raw_transcripts_in_artifact": False,
        "pii_in_artifact": False,
        "hmac_keys_in_artifact": False,
        "linkage_salts_in_artifact": False,
        "opaque_identifiers_and_commitments_only": True,
    }
    if payload.get("confidentiality") != expected_confidentiality:
        raise HveeContractError(
            f"{name} confidentiality boundary changed"
        )


def _validate_production_artifacts(
    *,
    assurance_sha256: str,
    private_holdout_exclusion: (
        ASRCriticalNumberPrivateHoldoutExclusionManifestBundle
    ),
    production_evidence: ASRCriticalNumberProductionEvidenceManifestBundle,
    verification: ASRCriticalNumberProductionEvidenceVerificationContext,
) -> tuple[dict[str, object], dict[str, object]]:
    if not isinstance(
        private_holdout_exclusion,
        ASRCriticalNumberPrivateHoldoutExclusionManifestBundle,
    ):
        raise HveeContractError(
            "qualification readiness requires a private-holdout exclusion"
        )
    if not isinstance(
        production_evidence,
        ASRCriticalNumberProductionEvidenceManifestBundle,
    ):
        raise HveeContractError(
            "qualification readiness requires production-derived evidence"
        )
    if not isinstance(
        verification,
        ASRCriticalNumberProductionEvidenceVerificationContext,
    ):
        raise HveeContractError(
            "qualification readiness requires production verification context"
        )

    private_holdout_exclusion = (
        verify_critical_number_private_holdout_exclusion_manifest(
            payload=private_holdout_exclusion.payload,
            expected_sha256=private_holdout_exclusion.sha256,
            plan=verification.plan,
            plan_definition=verification.plan_definition,
            linkage_tokens=verification.linkage_tokens,
        )
    )
    production_evidence = verify_critical_number_production_evidence_manifest(
        payload=production_evidence.payload,
        expected_sha256=production_evidence.sha256,
        definition=verification.definition,
        private_holdout_exclusion=private_holdout_exclusion,
    )

    exclusion_payload = _require_dict(
        name="private-holdout exclusion payload",
        value=private_holdout_exclusion.payload,
    )
    exclusion_sha256 = _require_sha256(
        name="private-holdout exclusion SHA-256",
        value=private_holdout_exclusion.sha256,
    )
    if calculate_critical_number_production_evidence_sha256(
        exclusion_payload
    ) != exclusion_sha256:
        raise HveeContractError(
            "private-holdout exclusion does not match its SHA-256"
        )

    production_payload = _require_dict(
        name="production-evidence payload",
        value=production_evidence.payload,
    )
    production_sha256 = _require_sha256(
        name="production-evidence SHA-256",
        value=production_evidence.sha256,
    )
    if calculate_critical_number_production_evidence_sha256(
        production_payload
    ) != production_sha256:
        raise HveeContractError(
            "production evidence does not match its SHA-256"
        )

    for name, payload, artifact in (
        (
            "private-holdout exclusion",
            exclusion_payload,
            "private_holdout_exclusion_manifest",
        ),
        (
            "production evidence",
            production_payload,
            "production_derived_evidence_manifest",
        ),
    ):
        protocol = _require_dict(
            name=f"{name} protocol",
            value=payload.get("protocol"),
        )
        if (
            protocol.get("key")
            != CRITICAL_NUMBER_PRODUCTION_EVIDENCE_PROTOCOL_KEY
            or protocol.get("version")
            != CRITICAL_NUMBER_PRODUCTION_EVIDENCE_PROTOCOL_VERSION
            or protocol.get("artifact") != artifact
        ):
            raise HveeContractError(
                f"{name} protocol identity changed"
            )

        bindings = _require_dict(
            name=f"{name} bindings",
            value=payload.get("bindings"),
        )
        assurance_binding = _require_dict(
            name=f"{name} assurance-profile binding",
            value=bindings.get("assurance_profile"),
        )
        if (
            assurance_binding.get("key")
            != CRITICAL_NUMBER_ASSURANCE_PROFILE_KEY
            or assurance_binding.get("version")
            != CRITICAL_NUMBER_ASSURANCE_PROFILE_VERSION
            or assurance_binding.get("status")
            != ASRCriticalNumberAssuranceStatus.EXPERIMENTAL.value
            or assurance_binding.get("sha256") != assurance_sha256
        ):
            raise HveeContractError(
                f"{name} does not bind the sealed assurance artifact"
            )

        _validate_production_boundaries(name=name, payload=payload)

    holdout_binding = _require_dict(
        name="private-holdout exclusion binding",
        value=exclusion_payload.get("private_holdout_binding"),
    )
    if holdout_binding.get("complete_plan_coverage_attested") is not True:
        raise HveeContractError(
            "private-holdout exclusion does not attest complete plan coverage"
        )
    plan_sha256 = _require_sha256(
        name="private-holdout plan SHA-256",
        value=holdout_binding.get("plan_sha256"),
    )
    case_count = holdout_binding.get("case_count")
    linkage_tokens = holdout_binding.get("linkage_tokens")
    if (
        not isinstance(case_count, int)
        or isinstance(case_count, bool)
        or case_count <= 0
        or not isinstance(linkage_tokens, list)
        or len(linkage_tokens) != case_count
    ):
        raise HveeContractError(
            "private-holdout exclusion coverage is inconsistent"
        )

    snapshot = _require_dict(
        name="production evidence snapshot",
        value=production_payload.get("production_snapshot"),
    )
    if snapshot.get("private_holdout_exclusion_sha256") != exclusion_sha256:
        raise HveeContractError(
            "production evidence does not bind the supplied exclusion manifest"
        )

    production_case_count = snapshot.get("case_count")
    production_cases = snapshot.get("cases")
    if (
        not isinstance(production_case_count, int)
        or isinstance(production_case_count, bool)
        or production_case_count <= 0
        or not isinstance(production_cases, list)
        or len(production_cases) != production_case_count
    ):
        raise HveeContractError(
            "production evidence case coverage is inconsistent"
        )

    _require_string(
        name="production manifest id",
        value=snapshot.get("manifest_id"),
    )
    _require_string(
        name="production manifest version",
        value=snapshot.get("manifest_version"),
    )

    return (
        {
            "sha256": exclusion_sha256,
            "plan_sha256": plan_sha256,
            "case_count": case_count,
            "complete_plan_coverage_attested": True,
        },
        {
            "sha256": production_sha256,
            "manifest_id": snapshot["manifest_id"],
            "manifest_version": snapshot["manifest_version"],
            "case_count": production_case_count,
            "private_holdout_exclusion_sha256": exclusion_sha256,
        },
    )


def _validate_shadow(
    *,
    shadow: ASRCriticalNumberMatchedReleaseShadowResult,
    assurance_sha256: str,
    verification: ASRCriticalNumberMatchedReleaseShadowVerificationContext,
) -> dict[str, object]:
    if not isinstance(shadow, ASRCriticalNumberMatchedReleaseShadowResult):
        raise HveeContractError(
            "qualification readiness requires a matched-release shadow result"
        )
    if not isinstance(
        verification,
        ASRCriticalNumberMatchedReleaseShadowVerificationContext,
    ):
        raise HveeContractError(
            "qualification readiness requires shadow verification context"
        )

    rebuilt = evaluate_asr_critical_number_matched_release_shadow(
        baseline_run_id=verification.baseline_run_id,
        candidate_run_id=verification.candidate_run_id,
        declared_test_case_ids=verification.declared_test_case_ids,
        policy=verification.policy,
        records=verification.records,
    )
    if rebuilt != shadow:
        raise HveeContractError(
            "matched-release shadow does not match its raw observation evidence"
        )

    shadow = rebuilt

    if (
        shadow.shadow_key != CRITICAL_NUMBER_MATCHED_RELEASE_SHADOW_KEY
        or shadow.shadow_version
        != CRITICAL_NUMBER_MATCHED_RELEASE_SHADOW_VERSION
        or shadow.assurance_profile_key
        != CRITICAL_NUMBER_ASSURANCE_PROFILE_KEY
        or shadow.assurance_profile_version
        != CRITICAL_NUMBER_ASSURANCE_PROFILE_VERSION
        or shadow.assurance_status
        != ASRCriticalNumberAssuranceStatus.EXPERIMENTAL
        or shadow.assurance_sha256 != assurance_sha256
        or shadow.production_qualified is not False
        or shadow.release_enforcement_eligible is not False
    ):
        raise HveeContractError(
            "matched-release shadow is not bound to the sealed experimental "
            "assurance profile"
        )

    official_assurance = shadow.official.assurance
    return {
        "key": shadow.shadow_key,
        "version": shadow.shadow_version,
        "assurance_sha256": shadow.assurance_sha256,
        "baseline_run_id": official_assurance.baseline_run_id,
        "candidate_run_id": official_assurance.candidate_run_id,
        "declared_test_case_ids": list(
            official_assurance.declared_test_case_ids
        ),
        "case_count": len(shadow.cases),
        "critical_integrity": _enum_value(
            name="shadow critical integrity",
            value=shadow.critical_integrity,
        ),
        "critical_evidence": _enum_value(
            name="shadow critical evidence",
            value=shadow.critical_evidence,
        ),
        "hypothetical_critical": (
            None
            if shadow.hypothetical_critical is None
            else _enum_value(
                name="shadow hypothetical critical assessment",
                value=shadow.hypothetical_critical,
            )
        ),
        "official_decision": {
            "verdict": _enum_value(
                name="official shadow verdict",
                value=shadow.official.decision.verdict,
            ),
            "reason": _enum_value(
                name="official shadow reason",
                value=shadow.official.decision.reason,
            ),
        },
        "hypothetical_decision": {
            "verdict": _enum_value(
                name="hypothetical shadow verdict",
                value=shadow.hypothetical_decision.verdict,
            ),
            "reason": _enum_value(
                name="hypothetical shadow reason",
                value=shadow.hypothetical_decision.reason,
            ),
        },
        "would_change_official_decision": (
            shadow.would_change_official_decision
        ),
    }


def _readiness_result(
    result: ASRCriticalNumberPrivateStatisticalAssessmentResult,
) -> ASRCriticalNumberQualificationReadinessResult:
    if (
        result
        == ASRCriticalNumberPrivateStatisticalAssessmentResult
        .INSUFFICIENT_EVIDENCE
    ):
        return (
            ASRCriticalNumberQualificationReadinessResult
            .INSUFFICIENT_EVIDENCE
        )
    if (
        result
        == ASRCriticalNumberPrivateStatisticalAssessmentResult
        .DOES_NOT_MEET_PREREGISTERED_CRITERIA
    ):
        return (
            ASRCriticalNumberQualificationReadinessResult
            .CRITERIA_NOT_MET
        )
    if (
        result
        == ASRCriticalNumberPrivateStatisticalAssessmentResult
        .MEETS_PREREGISTERED_CRITERIA
    ):
        return (
            ASRCriticalNumberQualificationReadinessResult
            .READY_FOR_GOVERNANCE_REVIEW
        )
    raise HveeContractError(
        "private statistical assessment result is unsupported"
    )


def build_critical_number_qualification_readiness_v1(
    *,
    assurance: ASRCriticalNumberAssuranceEvidenceBundle,
    method_manifest: ASRCriticalNumberPrivateStatisticalMethodManifestBundle,
    private_assessment: ASRCriticalNumberPrivateStatisticalAssessmentBundle,
    private_verification: (
        ASRCriticalNumberPrivateQualificationVerificationContext
    ),
    private_holdout_exclusion: (
        ASRCriticalNumberPrivateHoldoutExclusionManifestBundle
    ),
    production_evidence: ASRCriticalNumberProductionEvidenceManifestBundle,
    production_verification: (
        ASRCriticalNumberProductionEvidenceVerificationContext
    ),
    matched_release_shadow: ASRCriticalNumberMatchedReleaseShadowResult,
    matched_release_shadow_verification: (
        ASRCriticalNumberMatchedReleaseShadowVerificationContext
    ),
) -> ASRCriticalNumberQualificationReadinessBundle:
    """Compose sealed evidence into a non-certifying readiness dossier."""

    if not isinstance(assurance, ASRCriticalNumberAssuranceEvidenceBundle):
        raise HveeContractError(
            "qualification readiness requires assurance evidence"
        )

    verified_assurance = verify_critical_number_assurance_evidence_bundle(
        payload=assurance.payload,
        expected_sha256=assurance.sha256,
    )
    if verified_assurance.sha256 != (
        CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SHA256_V1
    ):
        raise HveeContractError(
            "qualification readiness requires the sealed v1 assurance artifact"
        )

    if not isinstance(
        method_manifest,
        ASRCriticalNumberPrivateStatisticalMethodManifestBundle,
    ):
        raise HveeContractError(
            "qualification readiness requires a statistical method manifest"
        )
    verified_method = (
        verify_critical_number_private_statistical_method_manifest_v1(
            payload=method_manifest.payload,
            expected_sha256=method_manifest.sha256,
        )
    )

    private_result = _validate_private_assessment(
        assessment=private_assessment,
        method_manifest=verified_method,
        verification=private_verification,
    )

    if not isinstance(
        production_verification,
        ASRCriticalNumberProductionEvidenceVerificationContext,
    ):
        raise HveeContractError(
            "qualification readiness requires production verification context"
        )

    if private_verification.plan.sha256 != production_verification.plan.sha256:
        raise HveeContractError(
            "production holdout exclusion is not bound to the private "
            "qualification plan"
        )

    exclusion_snapshot, production_snapshot = (
        _validate_production_artifacts(
            assurance_sha256=verified_assurance.sha256,
            private_holdout_exclusion=private_holdout_exclusion,
            production_evidence=production_evidence,
            verification=production_verification,
        )
    )

    shadow_snapshot = _validate_shadow(
        shadow=matched_release_shadow,
        assurance_sha256=verified_assurance.sha256,
        verification=matched_release_shadow_verification,
    )

    readiness_result = _readiness_result(private_result)

    payload: dict[str, object] = {
        "schema_version": (
            CRITICAL_NUMBER_QUALIFICATION_READINESS_SCHEMA_VERSION
        ),
        "readiness_profile": {
            "key": CRITICAL_NUMBER_QUALIFICATION_READINESS_KEY,
            "version": CRITICAL_NUMBER_QUALIFICATION_READINESS_VERSION,
            "artifact": "qualification_readiness_dossier",
            "evaluation_type": "asr",
        },
        "bindings": {
            "assurance": {
                "profile_key": CRITICAL_NUMBER_ASSURANCE_PROFILE_KEY,
                "profile_version": CRITICAL_NUMBER_ASSURANCE_PROFILE_VERSION,
                "sha256": verified_assurance.sha256,
            },
            "statistical_method": {
                "key": CRITICAL_NUMBER_PRIVATE_STATISTICAL_METHOD_KEY,
                "version": (
                    CRITICAL_NUMBER_PRIVATE_STATISTICAL_METHOD_VERSION
                ),
                "sha256": verified_method.sha256,
            },
            "private_statistical_assessment_sha256": private_assessment.sha256,
            "private_holdout_exclusion_sha256": (
                private_holdout_exclusion.sha256
            ),
            "production_evidence_sha256": production_evidence.sha256,
            "matched_release_shadow": {
                "key": matched_release_shadow.shadow_key,
                "version": matched_release_shadow.shadow_version,
                "assurance_sha256": matched_release_shadow.assurance_sha256,
            },
        },
        "evidence": {
            "assurance": {
                "status": ASRCriticalNumberAssuranceStatus.EXPERIMENTAL.value,
                "sealed_v1_verified": True,
            },
            "private_qualification": {
                "statistical_method_verified": True,
                "assessment_sha256": private_assessment.sha256,
                "complete_chain_reverification_attested": True,
                "assessment_result": private_result.value,
            },
            "production_derived": {
                "private_holdout_exclusion": exclusion_snapshot,
                "production_manifest": production_snapshot,
            },
            "matched_release_shadow": shadow_snapshot,
        },
        "readiness": {
            "required_evidence_complete": True,
            "private_assessment_result": private_result.value,
            "result": readiness_result.value,
        },
        "governance_boundary": {
            "evaluator_status": "experimental",
            "governance_review_only": True,
            "certification_issued": False,
            "production_qualified": False,
            "release_enforcement_eligible": False,
            "official_release_verdict_modified": False,
        },
        "confidentiality": {
            "private_case_content_in_artifact": False,
            "production_case_commitments_in_artifact": False,
            "cross_set_linkage_tokens_in_artifact": False,
            "aggregate_evidence_only": True,
        },
    }

    return ASRCriticalNumberQualificationReadinessBundle(
        payload=payload,
        sha256=calculate_critical_number_qualification_readiness_sha256(
            payload
        ),
    )


def verify_critical_number_qualification_readiness_v1(
    *,
    payload: object,
    expected_sha256: object,
    assurance: ASRCriticalNumberAssuranceEvidenceBundle,
    method_manifest: ASRCriticalNumberPrivateStatisticalMethodManifestBundle,
    private_assessment: ASRCriticalNumberPrivateStatisticalAssessmentBundle,
    private_verification: (
        ASRCriticalNumberPrivateQualificationVerificationContext
    ),
    private_holdout_exclusion: (
        ASRCriticalNumberPrivateHoldoutExclusionManifestBundle
    ),
    production_evidence: ASRCriticalNumberProductionEvidenceManifestBundle,
    production_verification: (
        ASRCriticalNumberProductionEvidenceVerificationContext
    ),
    matched_release_shadow: ASRCriticalNumberMatchedReleaseShadowResult,
    matched_release_shadow_verification: (
        ASRCriticalNumberMatchedReleaseShadowVerificationContext
    ),
) -> ASRCriticalNumberQualificationReadinessBundle:
    """Rebuild the v1 readiness dossier and require exact equality."""

    expected_digest = _require_sha256(
        name="qualification-readiness SHA-256",
        value=expected_sha256,
    )
    supplied = _require_dict(
        name="qualification-readiness payload",
        value=payload,
    )
    if calculate_critical_number_qualification_readiness_sha256(
        supplied
    ) != expected_digest:
        raise HveeContractError(
            "qualification-readiness payload does not match expected SHA-256"
        )

    rebuilt = build_critical_number_qualification_readiness_v1(
        assurance=assurance,
        method_manifest=method_manifest,
        private_assessment=private_assessment,
        private_verification=private_verification,
        private_holdout_exclusion=private_holdout_exclusion,
        production_evidence=production_evidence,
        production_verification=production_verification,
        matched_release_shadow=matched_release_shadow,
        matched_release_shadow_verification=(
            matched_release_shadow_verification
        ),
    )
    if supplied != rebuilt.payload or expected_digest != rebuilt.sha256:
        raise HveeContractError(
            "qualification-readiness dossier does not match bound evidence"
        )
    return rebuilt

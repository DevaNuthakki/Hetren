"""Sealed-evidence statistical assessment for private qualification."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction

from hvee.core.contracts import HveeContractError
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
    CRITICAL_NUMBER_PRIVATE_QUALIFICATION_CONTROL_STRATA_V1,
    CRITICAL_NUMBER_PRIVATE_QUALIFICATION_ORACLE_STRATA_V1,
    CRITICAL_NUMBER_PRIVATE_QUALIFICATION_RATE_SCALE,
    CRITICAL_NUMBER_PRIVATE_QUALIFICATION_REQUIRED_STRATA_V1,
    ASRCriticalNumberPrivateQualificationAdjudicationBundle,
    ASRCriticalNumberPrivateQualificationAdjudicationDefinition,
    ASRCriticalNumberPrivateQualificationAdjudicationOutcome,
    ASRCriticalNumberPrivateQualificationCampaignBundle,
    ASRCriticalNumberPrivateQualificationCampaignDefinition,
    ASRCriticalNumberPrivateQualificationProtocolBundle,
    ASRCriticalNumberPrivateQualificationStatisticalCriteria,
    ASRCriticalNumberPrivateQualificationStratum,
    calculate_critical_number_private_qualification_sha256,
    verify_critical_number_private_qualification_adjudication,
)
from hvee.packs.asr.critical_number_private_statistics import (
    CRITICAL_NUMBER_PRIVATE_MULTIPLICITY_CONTROL_KEY,
    CRITICAL_NUMBER_PRIVATE_MULTIPLICITY_CONTROL_VERSION,
    CRITICAL_NUMBER_PRIVATE_STATISTICAL_CLAIM_COUNT_V1,
    CRITICAL_NUMBER_PRIVATE_STATISTICAL_METHOD_KEY,
    CRITICAL_NUMBER_PRIVATE_STATISTICAL_METHOD_VERSION,
    ASRCriticalNumberPrivateStatisticalMethodManifestBundle,
    verify_critical_number_private_statistical_method_manifest_v1,
)
from hvee.statistics import (
    ExactBinomialTail,
    ExactPValue,
    clopper_pearson_lower_bound_scaled,
    clopper_pearson_upper_bound_scaled,
    exact_binomial_tail_probability,
    holm_step_down,
)


CRITICAL_NUMBER_PRIVATE_STATISTICAL_ASSESSMENT_SCHEMA_VERSION = 1


class ASRCriticalNumberPrivateStatisticalAssessmentResult(StrEnum):
    """Non-certifying result of the preregistered private assessment."""

    DOES_NOT_MEET_PREREGISTERED_CRITERIA = (
        "does_not_meet_preregistered_criteria"
    )
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    MEETS_PREREGISTERED_CRITERIA = "meets_preregistered_criteria"


def _require_sha256(*, name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise HveeContractError(f"{name} must be a lowercase SHA-256 hex digest")
    return value


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberPrivateStatisticalAssessmentBundle:
    """Canonical aggregate assessment and its deterministic digest."""

    payload: dict[str, object]
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.payload, dict):
            raise HveeContractError(
                "private statistical assessment must be an object"
            )
        _require_sha256(
            name="private statistical assessment SHA-256",
            value=self.sha256,
        )
        if calculate_critical_number_private_qualification_sha256(
            self.payload
        ) != self.sha256:
            raise HveeContractError(
                "private statistical assessment SHA-256 does not match "
                "its payload"
            )


def _fraction_snapshot(value: Fraction) -> dict[str, int]:
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
    }


def _outcome_count(
    *,
    definition: ASRCriticalNumberPrivateQualificationAdjudicationDefinition,
    stratum: ASRCriticalNumberPrivateQualificationStratum | None,
    outcome: ASRCriticalNumberPrivateQualificationAdjudicationOutcome,
) -> int:
    return sum(
        case.outcome == outcome
        and (stratum is None or case.stratum == stratum)
        for case in definition.cases
    )


def _selected_count(
    *,
    definition: ASRCriticalNumberPrivateQualificationAdjudicationDefinition,
    stratum: ASRCriticalNumberPrivateQualificationStratum | None,
) -> int:
    return sum(
        stratum is None or case.stratum == stratum
        for case in definition.cases
    )


def _usable_count(
    *,
    definition: ASRCriticalNumberPrivateQualificationAdjudicationDefinition,
    stratum: ASRCriticalNumberPrivateQualificationStratum,
) -> int:
    if stratum in CRITICAL_NUMBER_PRIVATE_QUALIFICATION_ORACLE_STRATA_V1:
        usable_outcomes = (
            ASRCriticalNumberPrivateQualificationAdjudicationOutcome.DETECTED,
            ASRCriticalNumberPrivateQualificationAdjudicationOutcome.MISSED,
        )
    else:
        usable_outcomes = (
            ASRCriticalNumberPrivateQualificationAdjudicationOutcome.TRUE_NEGATIVE,
            ASRCriticalNumberPrivateQualificationAdjudicationOutcome.FALSE_POSITIVE,
        )
    return sum(
        case.stratum == stratum and case.outcome in usable_outcomes
        for case in definition.cases
    )


def _readiness_snapshot(
    *,
    definition: ASRCriticalNumberPrivateQualificationAdjudicationDefinition,
    criteria: ASRCriticalNumberPrivateQualificationStatisticalCriteria,
) -> tuple[dict[str, object], bool]:
    strata = []
    for stratum in CRITICAL_NUMBER_PRIVATE_QUALIFICATION_REQUIRED_STRATA_V1:
        selected = _selected_count(definition=definition, stratum=stratum)
        usable = _usable_count(definition=definition, stratum=stratum)
        strata.append(
            {
                "stratum": stratum.value,
                "selected_case_count": selected,
                "usable_case_count": usable,
                "minimum_usable_case_count": (
                    criteria.minimum_usable_cases_per_stratum
                ),
                "minimum_met": (
                    usable >= criteria.minimum_usable_cases_per_stratum
                ),
            }
        )
    total_usable = sum(int(item["usable_case_count"]) for item in strata)
    minimums_met = (
        total_usable >= criteria.minimum_total_usable_cases
        and all(bool(item["minimum_met"]) for item in strata)
    )
    return (
        {
            "selected_case_count": len(definition.cases),
            "total_usable_case_count": total_usable,
            "minimum_total_usable_case_count": (
                criteria.minimum_total_usable_cases
            ),
            "strata": strata,
            "all_minimums_met": minimums_met,
        },
        minimums_met,
    )


def _fraction_gate_snapshot(
    *,
    key: str,
    outcome: ASRCriticalNumberPrivateQualificationAdjudicationOutcome,
    maximum_ppm: int,
    definition: ASRCriticalNumberPrivateQualificationAdjudicationDefinition,
) -> dict[str, object]:
    scale = CRITICAL_NUMBER_PRIVATE_QUALIFICATION_RATE_SCALE
    denominator = len(definition.cases)
    numerator = _outcome_count(
        definition=definition,
        stratum=None,
        outcome=outcome,
    )
    strata = []
    for stratum in CRITICAL_NUMBER_PRIVATE_QUALIFICATION_REQUIRED_STRATA_V1:
        stratum_denominator = _selected_count(
            definition=definition,
            stratum=stratum,
        )
        stratum_numerator = _outcome_count(
            definition=definition,
            stratum=stratum,
            outcome=outcome,
        )
        strata.append(
            {
                "stratum": stratum.value,
                "numerator": stratum_numerator,
                "denominator": stratum_denominator,
            }
        )
    return {
        "key": key,
        "numerator": numerator,
        "denominator": denominator,
        "maximum_ppm": maximum_ppm,
        "comparison": "exact_cross_multiplication_less_than_or_equal",
        "meets_criterion": numerator * scale <= maximum_ppm * denominator,
        "strata": strata,
    }


def _claim_observations(
    *,
    definition: ASRCriticalNumberPrivateQualificationAdjudicationDefinition,
    criteria: ASRCriticalNumberPrivateQualificationStatisticalCriteria,
) -> list[dict[str, object]]:
    scale = CRITICAL_NUMBER_PRIVATE_QUALIFICATION_RATE_SCALE
    confidence = Fraction(criteria.confidence_level_ppm, scale)
    observations: list[dict[str, object]] = []

    for stratum in CRITICAL_NUMBER_PRIVATE_QUALIFICATION_ORACLE_STRATA_V1:
        detected = _outcome_count(
            definition=definition,
            stratum=stratum,
            outcome=(
                ASRCriticalNumberPrivateQualificationAdjudicationOutcome.DETECTED
            ),
        )
        missed = _outcome_count(
            definition=definition,
            stratum=stratum,
            outcome=(
                ASRCriticalNumberPrivateQualificationAdjudicationOutcome.MISSED
            ),
        )
        threshold = criteria.minimum_oracle_detection_lower_bound_ppm
        bound = clopper_pearson_lower_bound_scaled(
            successes=detected,
            trials=detected + missed,
            confidence_level=confidence,
            scale=scale,
        )
        p_value = exact_binomial_tail_probability(
            successes=detected,
            trials=detected + missed,
            probability=Fraction(threshold, scale),
            tail=ExactBinomialTail.GREATER_THAN_OR_EQUAL,
        )
        observations.append(
            {
                "key": f"oracle_detection_lower_bound.{stratum.value}",
                "stratum": stratum.value,
                "estimand": "oracle_detection",
                "bound": "lower",
                "successes": detected,
                "trials": detected + missed,
                "bound_ppm": bound,
                "threshold_ppm": threshold,
                "bound_meets_criterion": bound >= threshold,
                "raw_p_value": p_value,
            }
        )

    for stratum in CRITICAL_NUMBER_PRIVATE_QUALIFICATION_CONTROL_STRATA_V1:
        false_positive = _outcome_count(
            definition=definition,
            stratum=stratum,
            outcome=(
                ASRCriticalNumberPrivateQualificationAdjudicationOutcome.FALSE_POSITIVE
            ),
        )
        true_negative = _outcome_count(
            definition=definition,
            stratum=stratum,
            outcome=(
                ASRCriticalNumberPrivateQualificationAdjudicationOutcome.TRUE_NEGATIVE
            ),
        )
        threshold = criteria.maximum_control_false_positive_upper_bound_ppm
        bound = clopper_pearson_upper_bound_scaled(
            successes=false_positive,
            trials=false_positive + true_negative,
            confidence_level=confidence,
            scale=scale,
        )
        p_value = exact_binomial_tail_probability(
            successes=false_positive,
            trials=false_positive + true_negative,
            probability=Fraction(threshold, scale),
            tail=ExactBinomialTail.LESS_THAN_OR_EQUAL,
        )
        observations.append(
            {
                "key": (
                    "control_false_positive_upper_bound."
                    f"{stratum.value}"
                ),
                "stratum": stratum.value,
                "estimand": "control_false_positive",
                "bound": "upper",
                "successes": false_positive,
                "trials": false_positive + true_negative,
                "bound_ppm": bound,
                "threshold_ppm": threshold,
                "bound_meets_criterion": bound <= threshold,
                "raw_p_value": p_value,
            }
        )

    for stratum in CRITICAL_NUMBER_PRIVATE_QUALIFICATION_REQUIRED_STRATA_V1:
        abstained = _outcome_count(
            definition=definition,
            stratum=stratum,
            outcome=(
                ASRCriticalNumberPrivateQualificationAdjudicationOutcome.ABSTAINED
            ),
        )
        selected = _selected_count(definition=definition, stratum=stratum)
        threshold = criteria.maximum_abstention_upper_bound_ppm
        bound = clopper_pearson_upper_bound_scaled(
            successes=abstained,
            trials=selected,
            confidence_level=confidence,
            scale=scale,
        )
        p_value = exact_binomial_tail_probability(
            successes=abstained,
            trials=selected,
            probability=Fraction(threshold, scale),
            tail=ExactBinomialTail.LESS_THAN_OR_EQUAL,
        )
        observations.append(
            {
                "key": f"abstention_upper_bound.{stratum.value}",
                "stratum": stratum.value,
                "estimand": "abstention",
                "bound": "upper",
                "successes": abstained,
                "trials": selected,
                "bound_ppm": bound,
                "threshold_ppm": threshold,
                "bound_meets_criterion": bound <= threshold,
                "raw_p_value": p_value,
            }
        )
    return sorted(observations, key=lambda item: str(item["key"]))


def _claims_snapshot(
    *,
    definition: ASRCriticalNumberPrivateQualificationAdjudicationDefinition,
    criteria: ASRCriticalNumberPrivateQualificationStatisticalCriteria,
) -> tuple[dict[str, object], bool]:
    observations = _claim_observations(
        definition=definition,
        criteria=criteria,
    )
    if len(observations) != CRITICAL_NUMBER_PRIVATE_STATISTICAL_CLAIM_COUNT_V1:
        raise HveeContractError(
            "private statistical assessment did not calculate 14 claims"
        )
    alpha = Fraction(
        CRITICAL_NUMBER_PRIVATE_QUALIFICATION_RATE_SCALE
        - criteria.confidence_level_ppm,
        CRITICAL_NUMBER_PRIVATE_QUALIFICATION_RATE_SCALE,
    )
    decisions = holm_step_down(
        p_values=tuple(
            ExactPValue(
                claim_key=str(observation["key"]),
                value=observation["raw_p_value"],
            )
            for observation in observations
        ),
        familywise_alpha=alpha,
    )
    decisions_by_key = {decision.claim_key: decision for decision in decisions}
    claims = []
    for observation in observations:
        key = str(observation["key"])
        decision = decisions_by_key[key]
        bound_meets = bool(observation["bound_meets_criterion"])
        claim_meets = bound_meets and decision.rejected
        claims.append(
            {
                **{
                    name: value
                    for name, value in observation.items()
                    if name not in {"raw_p_value", "bound_meets_criterion"}
                },
                "bound_meets_criterion": bound_meets,
                "raw_p_value": _fraction_snapshot(decision.raw_p_value),
                "holm_rank": decision.rank,
                "holm_critical_value": _fraction_snapshot(
                    decision.critical_value
                ),
                "holm_adjusted_p_value": _fraction_snapshot(
                    decision.adjusted_p_value
                ),
                "holm_rejected": decision.rejected,
                "meets_criterion": claim_meets,
            }
        )
    all_claims_met = all(bool(claim["meets_criterion"]) for claim in claims)
    return (
        {
            "calculated": True,
            "family_size": len(claims),
            "familywise_alpha": _fraction_snapshot(alpha),
            "claims": claims,
            "all_claims_met": all_claims_met,
        },
        all_claims_met,
    )


def _verify_method_binding(
    *,
    criteria: ASRCriticalNumberPrivateQualificationStatisticalCriteria,
    method_manifest: ASRCriticalNumberPrivateStatisticalMethodManifestBundle,
) -> ASRCriticalNumberPrivateStatisticalMethodManifestBundle:
    if not isinstance(
        method_manifest,
        ASRCriticalNumberPrivateStatisticalMethodManifestBundle,
    ):
        raise HveeContractError(
            "private statistical assessment requires the method manifest"
        )
    verified = verify_critical_number_private_statistical_method_manifest_v1(
        payload=method_manifest.payload,
        expected_sha256=method_manifest.sha256,
    )
    if (
        criteria.method_key != CRITICAL_NUMBER_PRIVATE_STATISTICAL_METHOD_KEY
        or criteria.method_version
        != CRITICAL_NUMBER_PRIVATE_STATISTICAL_METHOD_VERSION
        or criteria.method_manifest_sha256 != verified.sha256
        or criteria.multiplicity_control_key
        != CRITICAL_NUMBER_PRIVATE_MULTIPLICITY_CONTROL_KEY
        or criteria.multiplicity_control_version
        != CRITICAL_NUMBER_PRIVATE_MULTIPLICITY_CONTROL_VERSION
    ):
        raise HveeContractError(
            "preregistered criteria do not bind the v1 statistical method"
        )
    return verified


def build_critical_number_private_statistical_assessment_v1(
    *,
    method_manifest: ASRCriticalNumberPrivateStatisticalMethodManifestBundle,
    adjudication: ASRCriticalNumberPrivateQualificationAdjudicationBundle,
    campaign: ASRCriticalNumberPrivateQualificationCampaignBundle,
    protocol: ASRCriticalNumberPrivateQualificationProtocolBundle,
    campaign_definition: ASRCriticalNumberPrivateQualificationCampaignDefinition,
    plan: ASRCriticalNumberPrivateHoldoutPlanBundle,
    plan_definition: ASRCriticalNumberPrivateHoldoutPlanDefinition,
    run: ASRCriticalNumberPrivateHoldoutBlindRunBundle,
    run_definition: ASRCriticalNumberPrivateHoldoutBlindRunDefinition,
    disclosure_manifest: ASRCriticalNumberPrivateEvidenceDisclosureManifestBundle,
    disclosure_definition: ASRCriticalNumberPrivateEvidenceDisclosureDefinition,
    verified_plan_envelope: ASRCriticalNumberPrivateEvidenceVerifiedEnvelope,
    verified_run_envelope: ASRCriticalNumberPrivateEvidenceVerifiedEnvelope,
    verified_disclosure_envelope: ASRCriticalNumberPrivateEvidenceVerifiedEnvelope,
    adjudication_definition: (
        ASRCriticalNumberPrivateQualificationAdjudicationDefinition
    ),
) -> ASRCriticalNumberPrivateStatisticalAssessmentBundle:
    """Assess only after independently rebuilding the sealed evidence chain."""

    if not isinstance(
        adjudication,
        ASRCriticalNumberPrivateQualificationAdjudicationBundle,
    ):
        raise HveeContractError(
            "private statistical assessment requires adjudication evidence"
        )
    verified_adjudication = (
        verify_critical_number_private_qualification_adjudication(
            payload=adjudication.payload,
            expected_sha256=adjudication.sha256,
            campaign=campaign,
            protocol=protocol,
            campaign_definition=campaign_definition,
            plan=plan,
            plan_definition=plan_definition,
            run=run,
            run_definition=run_definition,
            disclosure_manifest=disclosure_manifest,
            disclosure_definition=disclosure_definition,
            verified_plan_envelope=verified_plan_envelope,
            verified_run_envelope=verified_run_envelope,
            verified_disclosure_envelope=verified_disclosure_envelope,
            definition=adjudication_definition,
        )
    )
    criteria = campaign_definition.statistical_criteria
    verified_method = _verify_method_binding(
        criteria=criteria,
        method_manifest=method_manifest,
    )
    readiness, minimums_met = _readiness_snapshot(
        definition=adjudication_definition,
        criteria=criteria,
    )
    fraction_gates = [
        _fraction_gate_snapshot(
            key="unresolved_fraction",
            outcome=(
                ASRCriticalNumberPrivateQualificationAdjudicationOutcome.UNRESOLVED
            ),
            maximum_ppm=criteria.maximum_unresolved_fraction_ppm,
            definition=adjudication_definition,
        ),
        _fraction_gate_snapshot(
            key="execution_failure_fraction",
            outcome=(
                ASRCriticalNumberPrivateQualificationAdjudicationOutcome
                .EXECUTION_FAILURE
            ),
            maximum_ppm=criteria.maximum_execution_failure_fraction_ppm,
            definition=adjudication_definition,
        ),
    ]
    all_fraction_gates_met = all(
        bool(gate["meets_criterion"]) for gate in fraction_gates
    )

    if minimums_met:
        claims, all_claims_met = _claims_snapshot(
            definition=adjudication_definition,
            criteria=criteria,
        )
        if all_fraction_gates_met and all_claims_met:
            result = (
                ASRCriticalNumberPrivateStatisticalAssessmentResult
                .MEETS_PREREGISTERED_CRITERIA
            )
        else:
            result = (
                ASRCriticalNumberPrivateStatisticalAssessmentResult
                .DOES_NOT_MEET_PREREGISTERED_CRITERIA
            )
    else:
        claims = {
            "calculated": False,
            "family_size": CRITICAL_NUMBER_PRIVATE_STATISTICAL_CLAIM_COUNT_V1,
            "familywise_alpha": _fraction_snapshot(
                Fraction(
                    CRITICAL_NUMBER_PRIVATE_QUALIFICATION_RATE_SCALE
                    - criteria.confidence_level_ppm,
                    CRITICAL_NUMBER_PRIVATE_QUALIFICATION_RATE_SCALE,
                )
            ),
            "claims": [],
            "all_claims_met": None,
        }
        all_claims_met = False
        result = (
            ASRCriticalNumberPrivateStatisticalAssessmentResult.INSUFFICIENT_EVIDENCE
        )

    adjudication_assessment = verified_adjudication.payload.get(
        "statistical_assessment"
    )
    if not isinstance(adjudication_assessment, dict):
        raise HveeContractError(
            "verified private adjudication statistical binding is malformed"
        )
    criteria_sha256 = adjudication_assessment.get("criteria_sha256")
    _require_sha256(
        name="verified private statistical criteria",
        value=criteria_sha256,
    )
    payload: dict[str, object] = {
        "schema_version": (
            CRITICAL_NUMBER_PRIVATE_STATISTICAL_ASSESSMENT_SCHEMA_VERSION
        ),
        "method": {
            "key": CRITICAL_NUMBER_PRIVATE_STATISTICAL_METHOD_KEY,
            "version": CRITICAL_NUMBER_PRIVATE_STATISTICAL_METHOD_VERSION,
            "artifact": "private_statistical_assessment",
            "manifest_sha256": verified_method.sha256,
            "multiplicity_control": {
                "key": CRITICAL_NUMBER_PRIVATE_MULTIPLICITY_CONTROL_KEY,
                "version": CRITICAL_NUMBER_PRIVATE_MULTIPLICITY_CONTROL_VERSION,
            },
        },
        "sealed_evidence": {
            "qualification_protocol_sha256": protocol.sha256,
            "qualification_campaign_sha256": campaign.sha256,
            "private_adjudication_sha256": verified_adjudication.sha256,
            "statistical_criteria_sha256": criteria_sha256,
            "complete_chain_reverified": True,
        },
        "readiness": readiness,
        "observed_fraction_gates": fraction_gates,
        "statistical_claims": claims,
        "result": {
            "value": result.value,
            "all_minimums_met": minimums_met,
            "all_fraction_gates_met": all_fraction_gates_met,
            "all_statistical_claims_met": (
                all_claims_met if minimums_met else None
            ),
        },
        "qualification": {
            "campaign_mechanics_verified": True,
            "statistical_qualification_assessed": True,
            "evaluator_status": "experimental",
            "certification_issued": False,
            "production_qualified": False,
            "release_enforcement_eligible": False,
            "official_release_verdict_modified": False,
        },
        "confidentiality": {
            "private_case_content_in_artifact": False,
            "expected_results_in_artifact": False,
            "private_provenance_in_artifact": False,
            "evaluator_outputs_in_artifact": False,
            "private_salts_in_artifact": False,
            "case_tokens_in_artifact": False,
            "aggregate_outcomes_only": True,
        },
    }
    return ASRCriticalNumberPrivateStatisticalAssessmentBundle(
        payload=payload,
        sha256=calculate_critical_number_private_qualification_sha256(
            payload
        ),
    )


def verify_critical_number_private_statistical_assessment_v1(
    *,
    payload: object,
    expected_sha256: object,
    method_manifest: ASRCriticalNumberPrivateStatisticalMethodManifestBundle,
    adjudication: ASRCriticalNumberPrivateQualificationAdjudicationBundle,
    campaign: ASRCriticalNumberPrivateQualificationCampaignBundle,
    protocol: ASRCriticalNumberPrivateQualificationProtocolBundle,
    campaign_definition: ASRCriticalNumberPrivateQualificationCampaignDefinition,
    plan: ASRCriticalNumberPrivateHoldoutPlanBundle,
    plan_definition: ASRCriticalNumberPrivateHoldoutPlanDefinition,
    run: ASRCriticalNumberPrivateHoldoutBlindRunBundle,
    run_definition: ASRCriticalNumberPrivateHoldoutBlindRunDefinition,
    disclosure_manifest: ASRCriticalNumberPrivateEvidenceDisclosureManifestBundle,
    disclosure_definition: ASRCriticalNumberPrivateEvidenceDisclosureDefinition,
    verified_plan_envelope: ASRCriticalNumberPrivateEvidenceVerifiedEnvelope,
    verified_run_envelope: ASRCriticalNumberPrivateEvidenceVerifiedEnvelope,
    verified_disclosure_envelope: ASRCriticalNumberPrivateEvidenceVerifiedEnvelope,
    adjudication_definition: (
        ASRCriticalNumberPrivateQualificationAdjudicationDefinition
    ),
) -> ASRCriticalNumberPrivateStatisticalAssessmentBundle:
    """Rebuild the complete v1 assessment and require exact equality."""

    expected_digest = _require_sha256(
        name="expected private statistical assessment",
        value=expected_sha256,
    )
    if not isinstance(payload, dict):
        raise HveeContractError(
            "supplied private statistical assessment must be an object"
        )
    supplied = ASRCriticalNumberPrivateStatisticalAssessmentBundle(
        payload=payload,
        sha256=expected_digest,
    )
    rebuilt = build_critical_number_private_statistical_assessment_v1(
        method_manifest=method_manifest,
        adjudication=adjudication,
        campaign=campaign,
        protocol=protocol,
        campaign_definition=campaign_definition,
        plan=plan,
        plan_definition=plan_definition,
        run=run,
        run_definition=run_definition,
        disclosure_manifest=disclosure_manifest,
        disclosure_definition=disclosure_definition,
        verified_plan_envelope=verified_plan_envelope,
        verified_run_envelope=verified_run_envelope,
        verified_disclosure_envelope=verified_disclosure_envelope,
        adjudication_definition=adjudication_definition,
    )
    if supplied.payload != rebuilt.payload or supplied.sha256 != rebuilt.sha256:
        raise HveeContractError(
            "private statistical assessment does not match v1 evidence"
        )
    return rebuilt

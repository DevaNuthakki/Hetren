"""Private statistical method for Critical Number Fidelity qualification.

The v1 manifest freezes estimands, denominators, directional exact tests,
multiplicity control, endpoint behavior, and non-certifying boundaries before
private campaign outcomes are statistically assessed.
"""

from __future__ import annotations

from dataclasses import dataclass

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.critical_number_private_qualification import (
    CRITICAL_NUMBER_PRIVATE_QUALIFICATION_CONTROL_STRATA_V1,
    CRITICAL_NUMBER_PRIVATE_QUALIFICATION_ORACLE_STRATA_V1,
    CRITICAL_NUMBER_PRIVATE_QUALIFICATION_RATE_SCALE,
    CRITICAL_NUMBER_PRIVATE_QUALIFICATION_REQUIRED_STRATA_V1,
    calculate_critical_number_private_qualification_sha256,
)


CRITICAL_NUMBER_PRIVATE_STATISTICAL_METHOD_SCHEMA_VERSION = 1
CRITICAL_NUMBER_PRIVATE_STATISTICAL_METHOD_KEY = (
    "hetren.private.stratified-exact-interval"
)
CRITICAL_NUMBER_PRIVATE_STATISTICAL_METHOD_VERSION = "1.0.0"
CRITICAL_NUMBER_PRIVATE_MULTIPLICITY_CONTROL_KEY = "holm-familywise-control"
CRITICAL_NUMBER_PRIVATE_MULTIPLICITY_CONTROL_VERSION = "1.0.0"
CRITICAL_NUMBER_PRIVATE_STATISTICAL_CLAIM_COUNT_V1 = 14


def _require_sha256(*, name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise HveeContractError(
            f"{name} must be a lowercase SHA-256 hex digest"
        )
    return value


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberPrivateStatisticalMethodManifestBundle:
    """Canonical private statistical-method manifest and its digest."""

    payload: dict[str, object]
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.payload, dict):
            raise HveeContractError(
                "private statistical-method manifest must be an object"
            )
        _require_sha256(
            name="private statistical-method manifest SHA-256",
            value=self.sha256,
        )
        if calculate_critical_number_private_qualification_sha256(
            self.payload
        ) != self.sha256:
            raise HveeContractError(
                "private statistical-method manifest SHA-256 does not match "
                "its payload"
            )


def _claim(
    *,
    key: str,
    stratum: str,
    estimand: str,
    numerator_outcomes: tuple[str, ...],
    denominator_outcomes: tuple[str, ...] | None,
    denominator_population: str,
    bound: str,
    null_boundary_criteria_field: str,
) -> dict[str, object]:
    return {
        "key": key,
        "stratum": stratum,
        "estimand": estimand,
        "numerator_outcomes": list(numerator_outcomes),
        "denominator_outcomes": (
            list(denominator_outcomes)
            if denominator_outcomes is not None
            else None
        ),
        "denominator_population": denominator_population,
        "bound": bound,
        "null_boundary_criteria_field": null_boundary_criteria_field,
    }


def _statistical_claims() -> list[dict[str, object]]:
    claims = [
        _claim(
            key=f"oracle_detection_lower_bound.{stratum.value}",
            stratum=stratum.value,
            estimand="oracle_detection",
            numerator_outcomes=("detected",),
            denominator_outcomes=("detected", "missed"),
            denominator_population="decisive_outcomes_in_stratum",
            bound="lower",
            null_boundary_criteria_field=(
                "minimum_oracle_detection_lower_bound_ppm"
            ),
        )
        for stratum in CRITICAL_NUMBER_PRIVATE_QUALIFICATION_ORACLE_STRATA_V1
    ]
    claims.extend(
        _claim(
            key=f"control_false_positive_upper_bound.{stratum.value}",
            stratum=stratum.value,
            estimand="control_false_positive",
            numerator_outcomes=("false_positive",),
            denominator_outcomes=("true_negative", "false_positive"),
            denominator_population="decisive_outcomes_in_stratum",
            bound="upper",
            null_boundary_criteria_field=(
                "maximum_control_false_positive_upper_bound_ppm"
            ),
        )
        for stratum in CRITICAL_NUMBER_PRIVATE_QUALIFICATION_CONTROL_STRATA_V1
    )
    claims.extend(
        _claim(
            key=f"abstention_upper_bound.{stratum.value}",
            stratum=stratum.value,
            estimand="abstention",
            numerator_outcomes=("abstained",),
            denominator_outcomes=None,
            denominator_population="all_selected_cases_in_stratum",
            bound="upper",
            null_boundary_criteria_field=(
                "maximum_abstention_upper_bound_ppm"
            ),
        )
        for stratum in CRITICAL_NUMBER_PRIVATE_QUALIFICATION_REQUIRED_STRATA_V1
    )
    return sorted(claims, key=lambda claim: str(claim["key"]))


def build_critical_number_private_statistical_method_manifest_v1(
) -> ASRCriticalNumberPrivateStatisticalMethodManifestBundle:
    """Build the deterministic v1 private statistical-method manifest."""

    claims = _statistical_claims()
    if len(claims) != CRITICAL_NUMBER_PRIVATE_STATISTICAL_CLAIM_COUNT_V1:
        raise HveeContractError(
            "private statistical-method claim family does not contain 14 claims"
        )

    payload: dict[str, object] = {
        "schema_version": (
            CRITICAL_NUMBER_PRIVATE_STATISTICAL_METHOD_SCHEMA_VERSION
        ),
        "method": {
            "key": CRITICAL_NUMBER_PRIVATE_STATISTICAL_METHOD_KEY,
            "version": CRITICAL_NUMBER_PRIVATE_STATISTICAL_METHOD_VERSION,
            "artifact": "private_statistical_method_manifest",
            "rate_scale": CRITICAL_NUMBER_PRIVATE_QUALIFICATION_RATE_SCALE,
            "randomness_used": False,
        },
        "readiness": {
            "verify_complete_sealed_evidence_chain_first": True,
            "verify_independent_adjudication_artifact_first": True,
            "minimum_total_usable_cases_criteria_field": (
                "minimum_total_usable_cases"
            ),
            "minimum_usable_cases_per_stratum_criteria_field": (
                "minimum_usable_cases_per_stratum"
            ),
            "usable_outcomes": [
                "detected",
                "false_positive",
                "missed",
                "true_negative",
            ],
            "insufficient_minimum_behavior": "insufficient_evidence",
            "calculate_claims_when_insufficient": False,
            "invalid_or_incomplete_evidence_behavior": "contract_error",
        },
        "statistical_claims": {
            "family_size": (
                CRITICAL_NUMBER_PRIVATE_STATISTICAL_CLAIM_COUNT_V1
            ),
            "claims": claims,
        },
        "exact_binomial": {
            "interval": "one_sided_clopper_pearson",
            "tail_probability": "inclusive",
            "arithmetic": "exact_rational_and_integer",
            "bound_grid": {
                "minimum": 0,
                "maximum": (
                    CRITICAL_NUMBER_PRIVATE_QUALIFICATION_RATE_SCALE
                ),
                "step": 1,
                "unit": "ppm",
            },
            "confidence_level_criteria_field": "confidence_level_ppm",
            "familywise_alpha": "one_minus_confidence_level",
            "lower_bound_zero_successes_ppm": 0,
            "upper_bound_all_successes_ppm": (
                CRITICAL_NUMBER_PRIVATE_QUALIFICATION_RATE_SCALE
            ),
            "lower_claim_p_value": (
                "P_null_boundary[X_greater_than_or_equal_observed]"
            ),
            "upper_claim_p_value": (
                "P_null_boundary[X_less_than_or_equal_observed]"
            ),
            "lower_bound_comparison": (
                "greater_than_or_equal_threshold"
            ),
            "upper_bound_comparison": "less_than_or_equal_threshold",
        },
        "multiplicity_control": {
            "key": CRITICAL_NUMBER_PRIVATE_MULTIPLICITY_CONTROL_KEY,
            "version": (
                CRITICAL_NUMBER_PRIVATE_MULTIPLICITY_CONTROL_VERSION
            ),
            "procedure": "holm_step_down",
            "scope": "all_14_directional_claims",
            "ordering": "raw_exact_p_value_ascending",
            "tie_breaker": "claim_key_ascending",
            "critical_value_at_rank": (
                "familywise_alpha/(family_size-rank+1)"
            ),
            "critical_comparison": "p_value_less_than_or_equal",
            "stop_after_first_non_rejection": True,
            "claim_meets_criterion": (
                "preregistered_bound_comparison_and_holm_rejection"
            ),
        },
        "observed_fraction_gates": [
            {
                "key": "unresolved_fraction",
                "numerator_outcomes": ["unresolved"],
                "denominator_population": "all_campaign_cases",
                "maximum_criteria_field": (
                    "maximum_unresolved_fraction_ppm"
                ),
                "comparison": (
                    "exact_cross_multiplication_less_than_or_equal"
                ),
                "per_stratum_values_reported_for_audit": True,
            },
            {
                "key": "execution_failure_fraction",
                "numerator_outcomes": ["execution_failure"],
                "denominator_population": "all_campaign_cases",
                "maximum_criteria_field": (
                    "maximum_execution_failure_fraction_ppm"
                ),
                "comparison": (
                    "exact_cross_multiplication_less_than_or_equal"
                ),
                "per_stratum_values_reported_for_audit": True,
            },
        ],
        "result_boundary": {
            "result_precedence": [
                "insufficient_evidence",
                "does_not_meet_preregistered_criteria",
                "meets_preregistered_criteria",
            ],
            "allowed_results": [
                "does_not_meet_preregistered_criteria",
                "insufficient_evidence",
                "meets_preregistered_criteria",
            ],
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
            "aggregate_method_metadata_only": True,
        },
    }

    return ASRCriticalNumberPrivateStatisticalMethodManifestBundle(
        payload=payload,
        sha256=(
            calculate_critical_number_private_qualification_sha256(
                payload
            )
        ),
    )


def verify_critical_number_private_statistical_method_manifest_v1(
    *,
    payload: object,
    expected_sha256: object,
) -> ASRCriticalNumberPrivateStatisticalMethodManifestBundle:
    """Require exact equality with the deterministic v1 method manifest."""

    expected_digest = _require_sha256(
        name="expected private statistical-method manifest",
        value=expected_sha256,
    )
    if not isinstance(payload, dict):
        raise HveeContractError(
            "supplied private statistical-method manifest must be an object"
        )

    supplied = ASRCriticalNumberPrivateStatisticalMethodManifestBundle(
        payload=payload,
        sha256=expected_digest,
    )
    rebuilt = (
        build_critical_number_private_statistical_method_manifest_v1()
    )
    if (
        supplied.payload != rebuilt.payload
        or supplied.sha256 != rebuilt.sha256
    ):
        raise HveeContractError(
            "private statistical-method manifest does not match v1"
        )
    return rebuilt

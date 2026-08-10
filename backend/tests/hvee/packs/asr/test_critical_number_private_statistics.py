from __future__ import annotations

import copy

import pytest

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.critical_number_private_qualification import (
    CRITICAL_NUMBER_PRIVATE_QUALIFICATION_REQUIRED_STRATA_V1,
)
from hvee.packs.asr.critical_number_private_statistics import (
    CRITICAL_NUMBER_PRIVATE_STATISTICAL_CLAIM_COUNT_V1,
    CRITICAL_NUMBER_PRIVATE_STATISTICAL_METHOD_KEY,
    CRITICAL_NUMBER_PRIVATE_STATISTICAL_METHOD_VERSION,
    build_critical_number_private_statistical_method_manifest_v1,
    verify_critical_number_private_statistical_method_manifest_v1,
)


def _claims_by_key() -> dict[str, dict[str, object]]:
    manifest = (
        build_critical_number_private_statistical_method_manifest_v1()
    )
    statistical_claims = manifest.payload["statistical_claims"]
    assert isinstance(statistical_claims, dict)
    claims = statistical_claims["claims"]
    assert isinstance(claims, list)
    return {str(claim["key"]): claim for claim in claims}


def test_method_manifest_is_deterministic_and_rebuild_verifiable() -> None:
    first = build_critical_number_private_statistical_method_manifest_v1()
    second = build_critical_number_private_statistical_method_manifest_v1()

    assert first == second
    assert first.payload["method"] == {
        "key": CRITICAL_NUMBER_PRIVATE_STATISTICAL_METHOD_KEY,
        "version": CRITICAL_NUMBER_PRIVATE_STATISTICAL_METHOD_VERSION,
        "artifact": "private_statistical_method_manifest",
        "rate_scale": 1_000_000,
        "randomness_used": False,
    }
    assert verify_critical_number_private_statistical_method_manifest_v1(
        payload=first.payload,
        expected_sha256=first.sha256,
    ) == first


def test_method_manifest_freezes_all_fourteen_directional_claims() -> None:
    claims = _claims_by_key()

    assert (
        len(claims)
        == CRITICAL_NUMBER_PRIVATE_STATISTICAL_CLAIM_COUNT_V1
    )
    assert len(claims) == 14

    for stratum in (
        CRITICAL_NUMBER_PRIVATE_QUALIFICATION_REQUIRED_STRATA_V1
    ):
        abstention = claims[
            f"abstention_upper_bound.{stratum.value}"
        ]
        assert abstention["numerator_outcomes"] == ["abstained"]
        assert abstention["denominator_outcomes"] is None
        assert (
            abstention["denominator_population"]
            == "all_selected_cases_in_stratum"
        )


def test_method_manifest_freezes_decisive_denominators() -> None:
    claims = _claims_by_key()

    oracle = claims[
        "oracle_detection_lower_bound.substitution_mutation"
    ]
    assert oracle["numerator_outcomes"] == ["detected"]
    assert oracle["denominator_outcomes"] == ["detected", "missed"]
    assert oracle["bound"] == "lower"

    control = claims[
        "control_false_positive_upper_bound."
        "equivalent_rendering_control"
    ]
    assert control["numerator_outcomes"] == ["false_positive"]
    assert control["denominator_outcomes"] == [
        "true_negative",
        "false_positive",
    ]
    assert control["bound"] == "upper"


def test_method_manifest_freezes_readiness_and_fraction_gates() -> None:
    manifest = (
        build_critical_number_private_statistical_method_manifest_v1()
    )

    readiness = manifest.payload["readiness"]
    assert isinstance(readiness, dict)
    assert readiness["calculate_claims_when_insufficient"] is False
    assert (
        readiness["invalid_or_incomplete_evidence_behavior"]
        == "contract_error"
    )

    gates = manifest.payload["observed_fraction_gates"]
    assert isinstance(gates, list)
    assert [gate["key"] for gate in gates] == [
        "unresolved_fraction",
        "execution_failure_fraction",
    ]
    assert all(
        gate["denominator_population"] == "all_campaign_cases"
        for gate in gates
    )


def test_method_manifest_freezes_exact_holm_behavior() -> None:
    manifest = (
        build_critical_number_private_statistical_method_manifest_v1()
    )

    exact_binomial = manifest.payload["exact_binomial"]
    assert isinstance(exact_binomial, dict)
    assert (
        exact_binomial["arithmetic"]
        == "exact_rational_and_integer"
    )
    assert exact_binomial["lower_bound_zero_successes_ppm"] == 0
    assert (
        exact_binomial["upper_bound_all_successes_ppm"]
        == 1_000_000
    )

    multiplicity = manifest.payload["multiplicity_control"]
    assert isinstance(multiplicity, dict)
    assert multiplicity["procedure"] == "holm_step_down"
    assert multiplicity["tie_breaker"] == "claim_key_ascending"
    assert multiplicity["stop_after_first_non_rejection"] is True

    result_boundary = manifest.payload["result_boundary"]
    assert isinstance(result_boundary, dict)
    assert result_boundary["result_precedence"] == [
        "insufficient_evidence",
        "does_not_meet_preregistered_criteria",
        "meets_preregistered_criteria",
    ]


def test_method_manifest_rejects_tampering() -> None:
    manifest = (
        build_critical_number_private_statistical_method_manifest_v1()
    )
    tampered = copy.deepcopy(manifest.payload)
    tampered["result_boundary"]["production_qualified"] = True

    with pytest.raises(HveeContractError):
        verify_critical_number_private_statistical_method_manifest_v1(
            payload=tampered,
            expected_sha256=manifest.sha256,
        )

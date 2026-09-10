from __future__ import annotations

import copy

import pytest

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.critical_number_assurance import (
    CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SHA256_V1,
)
from hvee.packs.asr.critical_number_assurance_v1_2 import (
    ASRCriticalNumberAssuranceV12Bundle,
    CRITICAL_NUMBER_ASSURANCE_V1_2_EXPECTED_BASE_CASES,
    CRITICAL_NUMBER_ASSURANCE_V1_2_EXPECTED_BOUNDARY_CASES,
    CRITICAL_NUMBER_ASSURANCE_V1_2_EXPECTED_INHERITED_MUTANTS,
    CRITICAL_NUMBER_ASSURANCE_V1_2_EXPECTED_NEW_MUTANTS,
    CRITICAL_NUMBER_ASSURANCE_V1_2_EXPECTED_V1_1_BOUNDARY_CASES,
    build_critical_number_assurance_v1_2_candidate,
    calculate_critical_number_assurance_v1_2_sha256,
    verify_critical_number_assurance_v1_2_candidate,
)


EXPECTED_V1 = (
    "e8459e209a022883007f5c6f72972c43"
    "f48758c0c6442e0d4d31d4ad20c24a72"
)
EXPECTED_V1_1 = (
    "fdd4a72abd5c4c568fbef14244299eb97"
    "1928ea81e7b3beba602a236b63efe24"
)


def _bundle():
    return build_critical_number_assurance_v1_2_candidate()


def test_v1_2_candidate_is_deterministic_and_reproducible():
    first = _bundle()
    second = _bundle()

    assert first == second
    assert first.sha256 == second.sha256

    assert verify_critical_number_assurance_v1_2_candidate(
        payload=first.payload,
        expected_sha256=first.sha256,
    ) == first


def test_v1_2_candidate_binds_exact_evaluator_and_preserves_old_identities():
    bindings = _bundle().payload["bindings"]

    assert bindings["evaluator"] == {
        "key": "hetren.asr.critical-number-fidelity.en-us",
        "version": "1.2.0",
        "evaluation_type": "asr",
    }

    assert bindings["default_evaluator_preserved"] == {
        "key": "hetren.asr.critical-number-fidelity.en-us",
        "version": "1.1.0",
        "evaluation_type": "asr",
    }

    assert bindings["historical_evaluator_preserved"] == {
        "key": "hetren.asr.critical-number-fidelity.en-us",
        "version": "1.0.0",
        "evaluation_type": "asr",
    }


def test_v1_2_candidate_preserves_historical_assurance_digests_exactly():
    bindings = _bundle().payload["bindings"]

    assert CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SHA256_V1 == EXPECTED_V1
    assert bindings["historical_v1_assurance_sha256"] == EXPECTED_V1
    assert bindings["historical_v1_1_assurance_sha256"] == EXPECTED_V1_1


def test_v1_2_candidate_passes_inherited_portfolio_with_v1_2_observations():
    baseline = _bundle().payload["inherited_baseline"]

    assert baseline["total_cases"] == (
        CRITICAL_NUMBER_ASSURANCE_V1_2_EXPECTED_BASE_CASES
    )
    assert baseline["total_cases"] == 29
    assert baseline["passed_cases"] == 29
    assert baseline["failed_cases"] == 0
    assert baseline["passed"] is True

    assert all(
        len(case["observations"]) == 10
        and {
            observation["evaluator_version"]
            for observation in case["observations"]
        }
        == {"1.2.0"}
        for case in baseline["case_runs"]
    )


def test_v1_2_candidate_passes_inherited_v1_1_boundary_suite():
    boundary = _bundle().payload["inherited_v1_1_boundary"]

    assert boundary["total_cases"] == (
        CRITICAL_NUMBER_ASSURANCE_V1_2_EXPECTED_V1_1_BOUNDARY_CASES
    )
    assert boundary["total_cases"] == 6
    assert boundary["passed_cases"] == 6
    assert boundary["failed_cases"] == 0
    assert boundary["passed"] is True

    assert all(
        case["actual"]["evaluator_version"] == "1.2.0"
        for case in boundary["case_runs"]
    )


def test_v1_2_candidate_passes_all_85_new_hostile_boundary_cases():
    boundary = _bundle().payload["v1_2_boundary"]

    assert boundary["total_cases"] == (
        CRITICAL_NUMBER_ASSURANCE_V1_2_EXPECTED_BOUNDARY_CASES
    )
    assert boundary["total_cases"] == 85
    assert boundary["passed_cases"] == 85
    assert boundary["failed_cases"] == 0
    assert boundary["passed"] is True

    assert all(case["passed"] is True for case in boundary["case_runs"])

    case_ids = {
        case["definition"]["case_id"]
        for case in boundary["case_runs"]
    }

    assert "v1-2.integer-substitution.001" in case_ids
    assert "v1-2.decimal-substitution.001" in case_ids
    assert "v1-2.word-digit-equivalence.002" in case_ids
    assert "v1-2.multiple-number.001" in case_ids
    assert "v1-2.unsupported-boundary.001" in case_ids


def test_v1_2_candidate_kills_all_inherited_and_new_mutants():
    mutation = _bundle().payload["mutation_assurance"]
    inherited = mutation["inherited"]
    new = mutation["v1_2_semantic"]

    assert inherited["total_mutants"] == (
        CRITICAL_NUMBER_ASSURANCE_V1_2_EXPECTED_INHERITED_MUTANTS
    )
    assert inherited["total_mutants"] == 9
    assert inherited["killed_mutants"] == 9
    assert inherited["survived_mutants"] == 0
    assert inherited["mutation_score"] == 1.0

    assert new["total_mutants"] == (
        CRITICAL_NUMBER_ASSURANCE_V1_2_EXPECTED_NEW_MUTANTS
    )
    assert new["total_mutants"] == 2
    assert new["killed_mutants"] == 2
    assert new["survived_mutants"] == 0
    assert new["mutation_score"] == 1.0

    result_by_name = {
        result["mutation"]: result
        for result in new["results"]
    }

    legacy = result_by_name["restore_legacy_v1_1_behavior"]
    strip = result_by_name["strip_all_periods"]

    assert legacy["killed"] is True
    assert legacy["changed_case_ids"]

    assert strip["killed"] is True
    assert strip["changed_case_ids"]


def test_v1_2_candidate_grants_no_production_release_or_certification_authority():
    profile = _bundle().payload["assurance_profile"]

    assert profile["status"] == "experimental"
    assert profile["production_qualified"] is False
    assert profile["release_enforcement_eligible"] is False
    assert profile["certification_issued"] is False

    validity = _bundle().payload["validity"]
    assert validity["does_not_grant_production_authority"] is True
    assert validity["does_not_promote_default_evaluator"] is True


def test_v1_2_candidate_contains_no_run04_results_holdout_or_timestamp():
    serialized = repr(_bundle().payload).lower()

    for forbidden in (
        "timestamp",
        "created_at",
        "generated_at",
        "model_result",
        "model_prediction",
        "run04_score",
        "holdout_membership",
    ):
        assert forbidden not in serialized


def test_v1_2_candidate_verifier_rejects_rehashed_tampering():
    bundle = _bundle()
    tampered = copy.deepcopy(bundle.payload)

    tampered["v1_2_boundary"]["passed_cases"] = 84

    tampered_sha = calculate_critical_number_assurance_v1_2_sha256(
        tampered
    )

    with pytest.raises(
        HveeContractError,
        match="reproducible build",
    ):
        verify_critical_number_assurance_v1_2_candidate(
            payload=tampered,
            expected_sha256=tampered_sha,
        )


def test_v1_2_candidate_bundle_rejects_digest_mismatch():
    bundle = _bundle()

    with pytest.raises(
        HveeContractError,
        match="does not match its payload",
    ):
        ASRCriticalNumberAssuranceV12Bundle(
            payload=bundle.payload,
            sha256="0" * 64,
        )

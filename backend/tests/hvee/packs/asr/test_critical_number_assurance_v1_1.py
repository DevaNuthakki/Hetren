from __future__ import annotations

import copy

import pytest

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.critical_number_assurance import (
    CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SHA256_V1,
    verify_critical_number_assurance_profile_v1,
)
from hvee.packs.asr.critical_number_assurance_v1_1 import (
    CRITICAL_NUMBER_ASSURANCE_V1_1_EXPECTED_BASE_CASES,
    CRITICAL_NUMBER_ASSURANCE_V1_1_EXPECTED_BOUNDARY_CASES,
    CRITICAL_NUMBER_ASSURANCE_V1_1_EXPECTED_MUTANTS,
    ASRCriticalNumberAssuranceV11Bundle,
    build_critical_number_assurance_v1_1_candidate,
    calculate_critical_number_assurance_v1_1_sha256,
    verify_critical_number_assurance_v1_1_candidate,
)


def _bundle():
    return build_critical_number_assurance_v1_1_candidate()


def test_v1_1_candidate_is_deterministic_and_reproducible():
    first = _bundle()
    second = _bundle()

    assert first == second
    assert first.sha256 == second.sha256
    assert verify_critical_number_assurance_v1_1_candidate(
        payload=first.payload,
        expected_sha256=first.sha256,
    ) == first


def test_v1_1_candidate_preserves_historical_v1_seal():
    historical = verify_critical_number_assurance_profile_v1()

    assert historical.sha256 == CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SHA256_V1
    assert _bundle().payload["bindings"]["historical_v1_assurance_sha256"] == (
        CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SHA256_V1
    )


def test_v1_1_candidate_binds_current_evaluator_only():
    bindings = _bundle().payload["bindings"]

    assert bindings["evaluator"] == {
        "key": "hetren.asr.critical-number-fidelity.en-us",
        "version": "1.1.0",
        "evaluation_type": "asr",
    }
    assert bindings["historical_v1_assurance_sha256"] == (
        "e8459e209a022883007f5c6f72972c43"
        "f48758c0c6442e0d4d31d4ad20c24a72"
    )


def test_v1_1_candidate_passes_inherited_and_boundary_cases():
    payload = _bundle().payload
    baseline = payload["inherited_baseline"]
    boundary = payload["v1_1_boundary"]

    assert baseline["total_cases"] == (
        CRITICAL_NUMBER_ASSURANCE_V1_1_EXPECTED_BASE_CASES
    )
    assert baseline["passed_cases"] == 29
    assert baseline["failed_cases"] == 0
    assert baseline["passed"] is True
    assert all(
        len(case["observations"]) == 10
        and {
            observation["evaluator_version"]
            for observation in case["observations"]
        }
        == {"1.1.0"}
        for case in baseline["case_runs"]
    )
    assert boundary["total_cases"] == (
        CRITICAL_NUMBER_ASSURANCE_V1_1_EXPECTED_BOUNDARY_CASES
    )
    assert boundary["passed_cases"] == 6
    assert boundary["failed_cases"] == 0
    assert all(case["passed"] is True for case in boundary["case_runs"])


def test_v1_1_candidate_records_safety_measurements():
    measurements = _bundle().payload["qualification_measurements"]

    assert measurements["inherited_portfolio"] == {
        "dangerous_false_passes": {
            "cases": 20,
            "false_passes": 0,
            "detection_rate": 1.0,
        },
        "equivalence_false_failures": {
            "cases": 6,
            "false_failures": 0,
            "acceptance_rate": 1.0,
        },
        "abstention": {
            "expected_cases": 2,
            "correct": 2,
            "errors": 0,
        },
        "not_applicable": {
            "expected_cases": 1,
            "correct": 1,
            "errors": 0,
        },
    }
    assert measurements["v1_1_boundary"] == {
        "dangerous_false_passes": {
            "cases": 3,
            "false_passes": 0,
            "detection_rate": 1.0,
        },
        "equivalence_false_failures": {
            "cases": 3,
            "false_failures": 0,
            "acceptance_rate": 1.0,
        },
    }


def test_v1_1_candidate_kills_every_mutant():
    mutation = _bundle().payload["evaluator_mutation_suite"]

    assert mutation["total_mutants"] == (
        CRITICAL_NUMBER_ASSURANCE_V1_1_EXPECTED_MUTANTS
    )
    assert mutation["killed_mutants"] == 9
    assert mutation["survived_mutants"] == 0
    assert mutation["mutation_score"] == 1.0


def test_v1_1_candidate_grants_no_production_or_release_authority():
    profile = _bundle().payload["assurance_profile"]

    assert profile["status"] == "experimental"
    assert profile["production_qualified"] is False
    assert profile["release_enforcement_eligible"] is False


def test_v1_1_candidate_contains_no_run_timestamp_or_model_result():
    serialized = repr(_bundle().payload).lower()

    assert "timestamp" not in serialized
    assert "created_at" not in serialized
    assert "generated_at" not in serialized
    assert "model_result" not in serialized
    assert "holdout_membership" not in serialized


def test_v1_1_candidate_verifier_rejects_rehashed_tampering():
    bundle = _bundle()
    tampered = copy.deepcopy(bundle.payload)
    tampered["inherited_baseline"]["passed_cases"] = 28
    tampered_sha = calculate_critical_number_assurance_v1_1_sha256(tampered)

    with pytest.raises(HveeContractError, match="reproducible build"):
        verify_critical_number_assurance_v1_1_candidate(
            payload=tampered,
            expected_sha256=tampered_sha,
        )


def test_v1_1_candidate_bundle_rejects_digest_mismatch():
    bundle = _bundle()

    with pytest.raises(HveeContractError, match="does not match its payload"):
        ASRCriticalNumberAssuranceV11Bundle(
            payload=bundle.payload,
            sha256="0" * 64,
        )

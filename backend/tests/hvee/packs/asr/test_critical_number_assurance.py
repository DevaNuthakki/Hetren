from __future__ import annotations

import copy
from dataclasses import replace

import pytest

from hvee.core.contracts import HveeContractError
from hvee.packs.asr import critical_number_assurance as assurance_module
from hvee.packs.asr.critical_number_assurance import (
    CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SCHEMA_VERSION,
    CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SHA256_V1,
    CRITICAL_NUMBER_ASSURANCE_EXPECTED_CASES_V1,
    CRITICAL_NUMBER_ASSURANCE_EXPECTED_MUTANTS_V1,
    CRITICAL_NUMBER_ASSURANCE_PROFILE_KEY,
    CRITICAL_NUMBER_ASSURANCE_PROFILE_VERSION,
    ASRCriticalNumberAssuranceEvidenceBundle,
    build_critical_number_assurance_evidence_bundle,
    calculate_critical_number_assurance_sha256,
    verify_critical_number_assurance_evidence_bundle,
    verify_critical_number_assurance_profile_v1,
)
from hvee.packs.asr.critical_number_fidelity import (
    CRITICAL_NUMBER_FIDELITY_EVALUATOR,
    EN_US_CRITICAL_NUMBER_PROFILE,
)
from hvee.packs.asr.critical_number_portfolio import (
    CRITICAL_NUMBER_FIDELITY_PORTFOLIO_V1,
    ASRCriticalNumberPortfolioDefinition,
)


def _bundle():
    return build_critical_number_assurance_evidence_bundle()


def test_assurance_evidence_is_deterministic_and_sealed():
    first = _bundle()
    second = _bundle()

    assert first == second
    assert first.sha256 == second.sha256
    assert first.sha256 == CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SHA256_V1
    assert verify_critical_number_assurance_profile_v1() == first


def test_assurance_profile_is_experimental_and_cannot_enforce_releases():
    bundle = _bundle()

    assert bundle.payload["schema_version"] == (
        CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SCHEMA_VERSION
    )
    assert bundle.payload["evaluation_type"] == "asr"

    profile = bundle.payload["assurance_profile"]
    assert isinstance(profile, dict)
    assert profile == {
        "key": CRITICAL_NUMBER_ASSURANCE_PROFILE_KEY,
        "version": CRITICAL_NUMBER_ASSURANCE_PROFILE_VERSION,
        "status": "experimental",
        "intended_use": "advisory_shadow_evidence",
        "production_qualified": False,
        "release_enforcement_eligible": False,
    }

    serialized = repr(bundle.payload)
    assert "ReleaseReport" not in serialized
    assert "release_decision" not in serialized


def test_assurance_evidence_binds_all_scientific_identities():
    bindings = _bundle().payload["bindings"]
    assert isinstance(bindings, dict)

    assert bindings["evaluator"] == {
        "key": "hetren.asr.critical-number-fidelity.en-us",
        "version": "1.0.0",
        "evaluation_type": "asr",
    }
    assert bindings["evaluation_profile"] == {
        "key": "hetren.asr.critical-number-profile.en-us",
        "version": "1.0.0",
        "language": "en",
        "locale": "en-US",
    }
    assert bindings["portfolio"] == {
        "key": "hetren.asr.critical-number-fidelity-portfolio.en-us",
        "version": "1.0.0",
    }
    assert bindings["mutation_suite"] == {
        "key": (
            "hetren.asr.critical-number-evaluator-"
            "mutation-suite.en-us"
        ),
        "version": "1.0.0",
    }


def test_assurance_evidence_records_exact_baseline_and_partitions():
    baseline = _bundle().payload["baseline"]
    assert isinstance(baseline, dict)

    assert baseline["total_cases"] == (
        CRITICAL_NUMBER_ASSURANCE_EXPECTED_CASES_V1
    )
    assert baseline["passed_cases"] == 29
    assert baseline["failed_cases"] == 0
    assert baseline["passed"] is True
    assert baseline["partition_counts"] == {
        "calibration": 13,
        "regression_holdout": 16,
    }

    case_runs = baseline["case_runs"]
    assert isinstance(case_runs, list)
    assert len(case_runs) == 29
    assert all(
        isinstance(case_run, dict)
        and case_run["result"] == {
            "passed": True,
            "failed_checks": [],
        }
        and len(case_run["observations"]) == 10
        for case_run in case_runs
    )


def test_assurance_evidence_records_safety_measurements():
    measurements = _bundle().payload["assurance_measurements"]
    assert isinstance(measurements, dict)

    assert measurements["dangerous_false_passes"] == {
        "cases": 20,
        "false_passes": 0,
        "detection_rate": 1.0,
    }
    assert measurements["equivalence_false_failures"] == {
        "cases": 6,
        "false_failures": 0,
        "acceptance_rate": 1.0,
    }
    assert measurements["applicability"] == {
        "cases": 29,
        "correct": 29,
        "errors": 0,
    }
    assert measurements["abstention"] == {
        "expected_cases": 2,
        "correct": 2,
        "errors": 0,
    }
    assert measurements["unsupported"] == {
        "expected_cases": 1,
        "correct": 1,
        "errors": 0,
    }

    coverage = measurements["numeric_type_coverage"]
    assert isinstance(coverage, dict)
    assert coverage["missing_types"] == []
    assert coverage["supported_types"] == [
        "cardinal_decimal",
        "percentage",
        "currency",
        "measurement",
        "clock_time",
        "calendar_date",
    ]
    assert coverage["types_with_full_error_matrix"] == (
        coverage["supported_types"]
    )


def test_assurance_evidence_records_exact_mutation_results():
    suite = _bundle().payload["evaluator_mutation_suite"]
    assert isinstance(suite, dict)

    assert suite["total_mutants"] == (
        CRITICAL_NUMBER_ASSURANCE_EXPECTED_MUTANTS_V1
    )
    assert suite["killed_mutants"] == 9
    assert suite["survived_mutants"] == 0
    assert suite["mutation_score"] == 1.0
    assert len(suite["mutations"]) == 9
    assert len(set(suite["mutations"])) == 9
    assert all(result["killed"] is True for result in suite["results"])


def test_assurance_evidence_declares_known_v1_limitations():
    limitations = _bundle().payload["limitations"]
    assert isinstance(limitations, list)

    assert {item["code"] for item in limitations} == {
        "en_us_scope_only",
        "source_visible_regression_holdout",
        "no_private_certification_set",
        "no_production_derived_cases",
    }


def test_assurance_evidence_contains_no_run_timestamp():
    serialized = repr(_bundle().payload).lower()

    assert "timestamp" not in serialized
    assert "created_at" not in serialized
    assert "generated_at" not in serialized


def test_verifier_accepts_reproducible_bundle_and_rejects_tampering():
    bundle = _bundle()

    assert verify_critical_number_assurance_evidence_bundle(
        payload=bundle.payload,
        expected_sha256=bundle.sha256,
    ) == bundle

    tampered = copy.deepcopy(bundle.payload)
    baseline = tampered["baseline"]
    assert isinstance(baseline, dict)
    baseline["passed_cases"] = 28
    tampered_sha = calculate_critical_number_assurance_sha256(tampered)

    with pytest.raises(HveeContractError, match="reproducibly rebuilt"):
        verify_critical_number_assurance_evidence_bundle(
            payload=tampered,
            expected_sha256=tampered_sha,
        )


def test_bundle_rejects_payload_digest_mismatch():
    bundle = _bundle()

    with pytest.raises(HveeContractError, match="does not match its payload"):
        ASRCriticalNumberAssuranceEvidenceBundle(
            payload=bundle.payload,
            sha256="0" * 64,
        )


def test_same_version_portfolio_change_fails_sealed_verification():
    original = CRITICAL_NUMBER_FIDELITY_PORTFOLIO_V1
    changed_case = replace(
        original.cases[0],
        description=original.cases[0].description + " Changed fixture.",
    )
    changed_portfolio = ASRCriticalNumberPortfolioDefinition(
        key=original.key,
        version=original.version,
        cases=(changed_case, *original.cases[1:]),
    )
    changed = build_critical_number_assurance_evidence_bundle(
        changed_portfolio
    )

    assert changed.sha256 != CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SHA256_V1
    with pytest.raises(HveeContractError, match="reproducibly rebuilt"):
        verify_critical_number_assurance_evidence_bundle(
            payload=_bundle().payload,
            expected_sha256=CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SHA256_V1,
            portfolio=changed_portfolio,
        )


@pytest.mark.parametrize(
    ("attribute", "changed_value", "message"),
    [
        (
            "CRITICAL_NUMBER_FIDELITY_EVALUATOR",
            replace(CRITICAL_NUMBER_FIDELITY_EVALUATOR, version="1.0.1"),
            "evaluator identity changed",
        ),
        (
            "EN_US_CRITICAL_NUMBER_PROFILE",
            replace(EN_US_CRITICAL_NUMBER_PROFILE, version="1.0.1"),
            "evaluation profile identity changed",
        ),
        (
            "CRITICAL_NUMBER_MUTATION_SUITE_VERSION",
            "1.0.1",
            "mutation-suite identity changed",
        ),
    ],
)
def test_identity_changes_fail_closed(
    monkeypatch,
    attribute,
    changed_value,
    message,
):
    monkeypatch.setattr(assurance_module, attribute, changed_value)

    with pytest.raises(HveeContractError, match=message):
        build_critical_number_assurance_evidence_bundle()

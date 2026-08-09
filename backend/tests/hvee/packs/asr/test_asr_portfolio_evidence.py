from __future__ import annotations

import copy
from dataclasses import replace

import pytest

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.evaluator_mutation import (
    ASR_EVALUATOR_MUTATION_SUITE_KEY,
    ASR_EVALUATOR_MUTATION_SUITE_VERSION,
)
from hvee.packs.asr.portfolio import (
    ASR_EVALUATION_PORTFOLIO_V1,
    ASRPortfolioDefinition,
)
from hvee.packs.asr.portfolio_evidence import (
    ASR_PORTFOLIO_EVIDENCE_SCHEMA_VERSION,
    ASRPortfolioEvidenceBundle,
    build_asr_portfolio_evidence_bundle,
    calculate_asr_portfolio_evidence_sha256,
    verify_asr_portfolio_evidence_bundle,
)


def test_portfolio_evidence_is_deterministic():
    first = build_asr_portfolio_evidence_bundle(
        ASR_EVALUATION_PORTFOLIO_V1
    )
    second = build_asr_portfolio_evidence_bundle(
        ASR_EVALUATION_PORTFOLIO_V1
    )

    assert first == second
    assert first.sha256 == second.sha256
    assert len(first.sha256) == 64
    assert first.sha256 == first.sha256.lower()


def test_portfolio_evidence_binds_exact_v1_identity():
    bundle = build_asr_portfolio_evidence_bundle(
        ASR_EVALUATION_PORTFOLIO_V1
    )

    assert bundle.payload["schema_version"] == (
        ASR_PORTFOLIO_EVIDENCE_SCHEMA_VERSION
    )
    assert bundle.payload["evaluation_type"] == "asr"

    portfolio = bundle.payload["portfolio"]

    assert isinstance(portfolio, dict)
    assert portfolio["key"] == (
        "hetren.asr.evaluation-portfolio"
    )
    assert portfolio["version"] == "1.0.0"

    cases = portfolio["cases"]
    assert isinstance(cases, list)
    assert len(cases) == 12


def test_portfolio_evidence_binds_baseline_results():
    bundle = build_asr_portfolio_evidence_bundle(
        ASR_EVALUATION_PORTFOLIO_V1
    )

    baseline = bundle.payload["baseline"]
    assert isinstance(baseline, dict)

    assert baseline["total_cases"] == 12
    assert baseline["passed_cases"] == 12
    assert baseline["failed_cases"] == 0
    assert baseline["total_expectations"] == 103
    assert baseline["matched_expectations"] == 103
    assert baseline["mismatched_expectations"] == 0
    assert baseline["passed"] is True


def test_portfolio_evidence_binds_versioned_mutation_suite():
    bundle = build_asr_portfolio_evidence_bundle(
        ASR_EVALUATION_PORTFOLIO_V1
    )

    suite = bundle.payload[
        "evaluator_mutation_suite"
    ]
    assert isinstance(suite, dict)

    assert suite["key"] == (
        ASR_EVALUATOR_MUTATION_SUITE_KEY
    )
    assert suite["version"] == (
        ASR_EVALUATOR_MUTATION_SUITE_VERSION
    )

    assert suite["total_mutants"] == 8
    assert suite["killed_mutants"] == 8
    assert suite["survived_mutants"] == 0
    assert suite["mutation_score"] == 1.0

    mutations = suite["mutations"]
    assert isinstance(mutations, list)
    assert len(mutations) == 8
    assert len(set(mutations)) == 8


def test_portfolio_evidence_contains_no_run_timestamp():
    bundle = build_asr_portfolio_evidence_bundle(
        ASR_EVALUATION_PORTFOLIO_V1
    )

    serialized = repr(
        bundle.payload
    ).lower()

    assert "timestamp" not in serialized
    assert "created_at" not in serialized
    assert "generated_at" not in serialized


def test_portfolio_definition_change_changes_digest():
    original = ASR_EVALUATION_PORTFOLIO_V1
    first_case = original.cases[0]

    changed_case = replace(
        first_case,
        description=(
            first_case.description
            + " Changed scientific fixture."
        ),
    )

    changed_portfolio = ASRPortfolioDefinition(
        key=original.key,
        version=original.version,
        cases=(
            changed_case,
            *original.cases[1:],
        ),
    )

    original_bundle = (
        build_asr_portfolio_evidence_bundle(
            original
        )
    )

    changed_bundle = (
        build_asr_portfolio_evidence_bundle(
            changed_portfolio
        )
    )

    assert (
        changed_bundle.sha256
        != original_bundle.sha256
    )


def test_verifier_accepts_reproducible_bundle():
    bundle = build_asr_portfolio_evidence_bundle(
        ASR_EVALUATION_PORTFOLIO_V1
    )

    verified = (
        verify_asr_portfolio_evidence_bundle(
            portfolio=(
                ASR_EVALUATION_PORTFOLIO_V1
            ),
            payload=bundle.payload,
            expected_sha256=bundle.sha256,
        )
    )

    assert verified == bundle


def test_verifier_rejects_tampered_payload():
    bundle = build_asr_portfolio_evidence_bundle(
        ASR_EVALUATION_PORTFOLIO_V1
    )

    tampered = copy.deepcopy(
        bundle.payload
    )

    baseline = tampered["baseline"]
    assert isinstance(baseline, dict)

    baseline["passed_cases"] = 11

    tampered_sha = (
        calculate_asr_portfolio_evidence_sha256(
            tampered
        )
    )

    with pytest.raises(
        HveeContractError,
        match="reproducibly rebuilt",
    ):
        verify_asr_portfolio_evidence_bundle(
            portfolio=(
                ASR_EVALUATION_PORTFOLIO_V1
            ),
            payload=tampered,
            expected_sha256=tampered_sha,
        )


def test_verifier_rejects_wrong_digest():
    bundle = build_asr_portfolio_evidence_bundle(
        ASR_EVALUATION_PORTFOLIO_V1
    )

    wrong_digest = "0" * 64

    assert wrong_digest != bundle.sha256

    with pytest.raises(
        HveeContractError,
        match="expected SHA-256",
    ):
        verify_asr_portfolio_evidence_bundle(
            portfolio=(
                ASR_EVALUATION_PORTFOLIO_V1
            ),
            payload=bundle.payload,
            expected_sha256=wrong_digest,
        )


def test_bundle_rejects_payload_digest_mismatch():
    bundle = build_asr_portfolio_evidence_bundle(
        ASR_EVALUATION_PORTFOLIO_V1
    )

    with pytest.raises(
        HveeContractError,
        match="does not match its payload",
    ):
        ASRPortfolioEvidenceBundle(
            payload=bundle.payload,
            sha256="0" * 64,
        )

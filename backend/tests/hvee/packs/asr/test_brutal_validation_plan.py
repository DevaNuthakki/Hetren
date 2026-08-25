from __future__ import annotations

import copy

from hvee.packs.asr.brutal_validation_plan import (
    ASR_BRUTAL_VALIDATION_BASELINE_COMMIT,
    ASR_BRUTAL_VALIDATION_CASES_V1,
    ASR_BRUTAL_VALIDATION_PLAN_SCHEMA_VERSION,
    ASR_BRUTAL_VALIDATION_WORKFLOW_V1,
    ASRBrutalCaseSource,
    ASRBrutalSemanticDimension,
    ASRBrutalStressFamily,
    build_asr_brutal_validation_plan_v1,
    calculate_asr_brutal_validation_plan_sha256,
    verify_asr_brutal_validation_plan_v1,
)


def test_brutal_v1_plan_is_deterministic():
    first = build_asr_brutal_validation_plan_v1()
    second = build_asr_brutal_validation_plan_v1()

    assert first.payload == second.payload
    assert first.sha256 == second.sha256


def test_brutal_v1_schema_and_baseline_are_frozen():
    bundle = build_asr_brutal_validation_plan_v1()

    assert bundle.payload["schema_version"] == (
        ASR_BRUTAL_VALIDATION_PLAN_SCHEMA_VERSION
    )

    assert bundle.payload["type"] == (
        "asr_brutal_validation_plan"
    )

    assert bundle.payload[
        "baseline"
    ]["git_commit"] == (
        ASR_BRUTAL_VALIDATION_BASELINE_COMMIT
    )


def test_brutal_v1_has_exact_unique_case_ids():
    case_ids = [
        case.case_id
        for case
        in ASR_BRUTAL_VALIDATION_CASES_V1
    ]

    assert len(case_ids) == 13
    assert len(case_ids) == len(set(case_ids))


def test_existing_and_required_new_cases_are_distinct():
    existing = {
        case.case_id
        for case
        in ASR_BRUTAL_VALIDATION_CASES_V1
        if case.source
        is ASRBrutalCaseSource.EXISTING_CORPUS
    }

    required_new = {
        case.case_id
        for case
        in ASR_BRUTAL_VALIDATION_CASES_V1
        if case.source
        is ASRBrutalCaseSource.REQUIRED_NEW_CASE
    }

    assert len(existing) == 10
    assert len(required_new) == 3
    assert existing.isdisjoint(required_new)

    assert {
        "brutal.terminology.clean",
        "brutal.terminology.telephony-noise",
        "brutal.compound-critical.telephony-noise",
    } == required_new


def test_brutal_v1_covers_all_stress_families():
    observed = {
        family
        for case
        in ASR_BRUTAL_VALIDATION_CASES_V1
        for family
        in case.stress_families
    }

    assert observed == set(
        ASRBrutalStressFamily
    )


def test_brutal_v1_covers_all_critical_semantics():
    observed = {
        dimension
        for case
        in ASR_BRUTAL_VALIDATION_CASES_V1
        for dimension
        in case.semantic_dimensions
    }

    assert observed == set(
        ASRBrutalSemanticDimension
    )


def test_brutal_v1_requires_real_execution():
    bundle = build_asr_brutal_validation_plan_v1()

    requirements = bundle.payload[
        "execution_requirements"
    ]

    assert requirements[
        "real_audio_material_required"
    ] is True

    assert requirements[
        "real_asr_provider_execution_required"
    ] is True

    assert requirements[
        "real_cross_stage_evidence_required"
    ] is True

    assert requirements[
        "real_incident_chain_required"
    ] is True

    assert requirements[
        "verifier_stubs_allowed"
    ] is False

    assert requirements[
        "synthetic_only_campaign_acceptable"
    ] is False


def test_brutal_v1_workflow_reaches_incident_governance():
    bundle = build_asr_brutal_validation_plan_v1()

    assert tuple(
        bundle.payload[
            "workflow"
        ]["required_stages"]
    ) == ASR_BRUTAL_VALIDATION_WORKFLOW_V1

    assert ASR_BRUTAL_VALIDATION_WORKFLOW_V1[-2:] == (
        "incident_mode",
        "governance_assurance",
    )


def test_plan_itself_does_not_start_brutal_execution():
    bundle = build_asr_brutal_validation_plan_v1()

    boundary = bundle.payload[
        "execution_boundary"
    ]

    assert all(
        value is False
        for value
        in boundary.values()
    )


def test_brutal_v1_never_grants_production_authority():
    bundle = build_asr_brutal_validation_plan_v1()

    boundary = bundle.payload[
        "authority_boundary"
    ]

    assert boundary[
        "development_evidence_only"
    ] is True

    assert boundary[
        "production_certification"
    ] is False

    assert boundary[
        "contract_promoted"
    ] is False

    assert boundary[
        "blocking_release_gate_enabled"
    ] is False

    assert boundary[
        "release_authority_granted"
    ] is False

    assert boundary[
        "qualification_authority"
    ] is False


def test_brutal_plan_verifier_rejects_rehashed_tampering():
    bundle = build_asr_brutal_validation_plan_v1()

    tampered = copy.deepcopy(
        bundle.payload
    )

    tampered[
        "execution_requirements"
    ][
        "verifier_stubs_allowed"
    ] = True

    digest = (
        calculate_asr_brutal_validation_plan_sha256(
            tampered
        )
    )

    assert not (
        verify_asr_brutal_validation_plan_v1(
            payload=tampered,
            expected_sha256=digest,
        )
    )


def test_brutal_plan_verifies_exactly():
    bundle = build_asr_brutal_validation_plan_v1()

    assert verify_asr_brutal_validation_plan_v1(
        payload=bundle.payload,
        expected_sha256=bundle.sha256,
    )

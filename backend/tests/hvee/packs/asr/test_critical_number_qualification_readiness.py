from __future__ import annotations

import copy
import importlib.util
from dataclasses import replace
from functools import lru_cache
from pathlib import Path
from types import ModuleType

import pytest

from hvee.core.contracts import HveeContractError
from hvee.packs import asr
from hvee.packs.asr.critical_number_assurance import (
    verify_critical_number_assurance_profile_v1,
)
from hvee.packs.asr.critical_number_private_assessment import (
    ASRCriticalNumberPrivateStatisticalAssessmentBundle,
    ASRCriticalNumberPrivateStatisticalAssessmentResult,
)
from hvee.packs.asr.critical_number_private_qualification import (
    ASRCriticalNumberPrivateQualificationAdjudicationOutcome,
    calculate_critical_number_private_qualification_sha256,
)
from hvee.packs.asr.critical_number_private_statistics import (
    build_critical_number_private_statistical_method_manifest_v1,
)
from hvee.packs.asr.critical_number_production_evidence import (
    ASRCriticalNumberPrivateHoldoutExclusionManifestBundle,
    ASRCriticalNumberProductionEvidenceManifestBundle,
    build_critical_number_private_holdout_exclusion_manifest,
    build_critical_number_production_evidence_manifest,
    calculate_critical_number_production_evidence_sha256,
)
from hvee.packs.asr.critical_number_qualification_readiness import (
    CRITICAL_NUMBER_QUALIFICATION_READINESS_KEY,
    CRITICAL_NUMBER_QUALIFICATION_READINESS_SCHEMA_VERSION,
    CRITICAL_NUMBER_QUALIFICATION_READINESS_VERSION,
    ASRCriticalNumberMatchedReleaseShadowVerificationContext,
    ASRCriticalNumberPrivateQualificationVerificationContext,
    ASRCriticalNumberProductionEvidenceVerificationContext,
    ASRCriticalNumberQualificationReadinessResult,
    build_critical_number_qualification_readiness_v1,
    calculate_critical_number_qualification_readiness_sha256,
    verify_critical_number_qualification_readiness_v1,
)
from hvee.packs.asr.critical_number_release_shadow import (
    evaluate_asr_critical_number_matched_release_shadow,
)


def _load_sibling_test_module(filename: str, module_name: str) -> ModuleType:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load test fixture module: {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_PRIVATE = _load_sibling_test_module(
    "test_critical_number_private_qualification.py",
    "_hetren_readiness_private_fixtures",
)
_PRODUCTION = _load_sibling_test_module(
    "test_critical_number_production_evidence.py",
    "_hetren_readiness_production_fixtures",
)
_SHADOW = _load_sibling_test_module(
    "test_critical_number_release_shadow.py",
    "_hetren_readiness_shadow_fixtures",
)


def _private_chain(kind: str):
    criteria = _PRIVATE._assessment_criteria()

    if kind == "insufficient":
        context = _PRIVATE._full_campaign(
            statistical_criteria=criteria,
        )
    else:
        context = _PRIVATE._full_campaign(
            statistical_criteria=criteria,
            execution_statuses=_PRIVATE._all_completed_statuses(),
        )

    adjudication_definition = _PRIVATE._adjudication_definition(context)

    if kind == "criteria_not_met":
        detected_index = next(
            index
            for index, case in enumerate(adjudication_definition.cases)
            if case.outcome
            == ASRCriticalNumberPrivateQualificationAdjudicationOutcome.DETECTED
        )
        changed_cases = list(adjudication_definition.cases)
        changed_cases[detected_index] = replace(
            changed_cases[detected_index],
            outcome=(
                ASRCriticalNumberPrivateQualificationAdjudicationOutcome.MISSED
            ),
        )
        adjudication_definition = replace(
            adjudication_definition,
            cases=tuple(changed_cases),
        )

    adjudication = _PRIVATE._build_adjudication(
        context,
        adjudication_definition,
    )
    assessment = _PRIVATE._build_assessment(
        context,
        adjudication_definition,
        adjudication,
    )

    verification = ASRCriticalNumberPrivateQualificationVerificationContext(
        adjudication=adjudication,
        campaign=context["campaign"],
        protocol=context["protocol"],
        campaign_definition=context["campaign_definition"],
        plan=context["plan"],
        plan_definition=context["plan_definition"],
        run=context["run"],
        run_definition=context["run_definition"],
        disclosure_manifest=context["manifest"],
        disclosure_definition=context["disclosure_definition"],
        verified_plan_envelope=context["verified_plan"],
        verified_run_envelope=context["verified_run"],
        verified_disclosure_envelope=context["verified_disclosure"],
        adjudication_definition=adjudication_definition,
    )

    return context, assessment, verification


def _production_chain(private_context):
    linkage_tokens = tuple(
        sorted(
            _PRODUCTION._linkage_token(
                f"qualification-private-case-{index}"
            )
            for index, _case in enumerate(
                private_context["plan_definition"].cases,
                start=1,
            )
        )
    )

    exclusion = build_critical_number_private_holdout_exclusion_manifest(
        plan=private_context["plan"],
        plan_definition=private_context["plan_definition"],
        linkage_tokens=linkage_tokens,
    )
    definition = _PRODUCTION._production_definition(exclusion.sha256)
    manifest = build_critical_number_production_evidence_manifest(
        definition=definition,
        private_holdout_exclusion=exclusion,
    )
    verification = ASRCriticalNumberProductionEvidenceVerificationContext(
        plan=private_context["plan"],
        plan_definition=private_context["plan_definition"],
        linkage_tokens=linkage_tokens,
        definition=definition,
    )

    return exclusion, manifest, verification


def _shadow_chain(*, candidate_violation: bool):
    candidate_overrides = (
        {1: "invoice 48271 total $1,250"}
        if candidate_violation
        else None
    )
    records = _SHADOW._inputs(
        candidate_overrides=candidate_overrides,
    )
    policy = _SHADOW._policy()

    result = evaluate_asr_critical_number_matched_release_shadow(
        baseline_run_id=10,
        candidate_run_id=20,
        declared_test_case_ids=(1, 2, 3, 4),
        policy=policy,
        records=records,
    )
    verification = ASRCriticalNumberMatchedReleaseShadowVerificationContext(
        baseline_run_id=10,
        candidate_run_id=20,
        declared_test_case_ids=(1, 2, 3, 4),
        policy=policy,
        records=records,
    )

    return result, verification


@lru_cache(maxsize=None)
def _evidence(kind: str = "ready", candidate_violation: bool = False):
    assurance = verify_critical_number_assurance_profile_v1()
    method_manifest = (
        build_critical_number_private_statistical_method_manifest_v1()
    )
    private_context, private_assessment, private_verification = (
        _private_chain(kind)
    )
    exclusion, production_evidence, production_verification = (
        _production_chain(private_context)
    )
    shadow, shadow_verification = _shadow_chain(
        candidate_violation=candidate_violation
    )

    return {
        "assurance": assurance,
        "method_manifest": method_manifest,
        "private_context": private_context,
        "private_assessment": private_assessment,
        "private_verification": private_verification,
        "private_holdout_exclusion": exclusion,
        "production_evidence": production_evidence,
        "production_verification": production_verification,
        "matched_release_shadow": shadow,
        "matched_release_shadow_verification": shadow_verification,
    }


def _build(evidence):
    return build_critical_number_qualification_readiness_v1(
        assurance=evidence["assurance"],
        method_manifest=evidence["method_manifest"],
        private_assessment=evidence["private_assessment"],
        private_verification=evidence["private_verification"],
        private_holdout_exclusion=evidence["private_holdout_exclusion"],
        production_evidence=evidence["production_evidence"],
        production_verification=evidence["production_verification"],
        matched_release_shadow=evidence["matched_release_shadow"],
        matched_release_shadow_verification=(
            evidence["matched_release_shadow_verification"]
        ),
    )


def _verify(bundle, evidence):
    return verify_critical_number_qualification_readiness_v1(
        payload=bundle.payload,
        expected_sha256=bundle.sha256,
        assurance=evidence["assurance"],
        method_manifest=evidence["method_manifest"],
        private_assessment=evidence["private_assessment"],
        private_verification=evidence["private_verification"],
        private_holdout_exclusion=evidence["private_holdout_exclusion"],
        production_evidence=evidence["production_evidence"],
        production_verification=evidence["production_verification"],
        matched_release_shadow=evidence["matched_release_shadow"],
        matched_release_shadow_verification=(
            evidence["matched_release_shadow_verification"]
        ),
    )


def test_readiness_is_deterministic_and_sealed():
    evidence = _evidence("ready")
    first = _build(evidence)
    second = _build(evidence)

    assert first == second
    assert first.sha256 == (
        calculate_critical_number_qualification_readiness_sha256(
            first.payload
        )
    )
    assert first.payload["schema_version"] == (
        CRITICAL_NUMBER_QUALIFICATION_READINESS_SCHEMA_VERSION
    )
    assert first.payload["readiness_profile"] == {
        "key": CRITICAL_NUMBER_QUALIFICATION_READINESS_KEY,
        "version": CRITICAL_NUMBER_QUALIFICATION_READINESS_VERSION,
        "artifact": "qualification_readiness_dossier",
        "evaluation_type": "asr",
    }
    assert first.payload["readiness"] == {
        "required_evidence_complete": True,
        "private_assessment_result": (
            ASRCriticalNumberPrivateStatisticalAssessmentResult
            .MEETS_PREREGISTERED_CRITERIA.value
        ),
        "result": (
            ASRCriticalNumberQualificationReadinessResult
            .READY_FOR_GOVERNANCE_REVIEW.value
        ),
    }


def test_readiness_verifier_rebuilds_exact_bound_evidence():
    evidence = _evidence("ready")
    dossier = _build(evidence)

    assert _verify(dossier, evidence) == dossier


@pytest.mark.parametrize(
    ("kind", "expected_private", "expected_readiness"),
    (
        (
            "ready",
            ASRCriticalNumberPrivateStatisticalAssessmentResult
            .MEETS_PREREGISTERED_CRITERIA.value,
            ASRCriticalNumberQualificationReadinessResult
            .READY_FOR_GOVERNANCE_REVIEW.value,
        ),
        (
            "criteria_not_met",
            ASRCriticalNumberPrivateStatisticalAssessmentResult
            .DOES_NOT_MEET_PREREGISTERED_CRITERIA.value,
            ASRCriticalNumberQualificationReadinessResult
            .CRITERIA_NOT_MET.value,
        ),
        (
            "insufficient",
            ASRCriticalNumberPrivateStatisticalAssessmentResult
            .INSUFFICIENT_EVIDENCE.value,
            ASRCriticalNumberQualificationReadinessResult
            .INSUFFICIENT_EVIDENCE.value,
        ),
    ),
)
def test_readiness_maps_only_preregistered_private_assessment(
    kind,
    expected_private,
    expected_readiness,
):
    dossier = _build(_evidence(kind))

    assert dossier.payload["readiness"]["private_assessment_result"] == (
        expected_private
    )
    assert dossier.payload["readiness"]["result"] == expected_readiness


def test_shadow_decision_change_is_evidence_not_a_post_hoc_gate():
    evidence = _evidence("ready", True)
    dossier = _build(evidence)
    shadow = dossier.payload["evidence"]["matched_release_shadow"]

    assert shadow["would_change_official_decision"] is True
    assert shadow["official_decision"]["verdict"] == "pass"
    assert shadow["hypothetical_decision"]["verdict"] == "fail"
    assert dossier.payload["readiness"]["result"] == (
        ASRCriticalNumberQualificationReadinessResult
        .READY_FOR_GOVERNANCE_REVIEW.value
    )


def test_readiness_remains_non_certifying_and_non_enforcing():
    dossier = _build(_evidence("ready"))

    assert dossier.payload["governance_boundary"] == {
        "evaluator_status": "experimental",
        "governance_review_only": True,
        "certification_issued": False,
        "production_qualified": False,
        "release_enforcement_eligible": False,
        "official_release_verdict_modified": False,
    }


def test_readiness_does_not_copy_confidential_case_material():
    evidence = _evidence("ready")
    dossier = _build(evidence)
    serialized = repr(dossier.payload)

    private_cases = evidence["private_context"]["plan_definition"].cases
    production_cases = (
        evidence["production_verification"].definition.cases
    )

    assert all(case.case_token not in serialized for case in private_cases)
    assert all(
        case.cross_set_linkage_token not in serialized
        for case in production_cases
    )
    assert all(
        token not in serialized
        for token in evidence["production_verification"].linkage_tokens
    )
    assert "private reference" not in serialized
    assert "private expected" not in serialized

    assert dossier.payload["confidentiality"] == {
        "private_case_content_in_artifact": False,
        "production_case_commitments_in_artifact": False,
        "cross_set_linkage_tokens_in_artifact": False,
        "aggregate_evidence_only": True,
    }


def test_recomputed_but_forged_private_assessment_is_rejected():
    evidence = _evidence("ready")
    payload = copy.deepcopy(evidence["private_assessment"].payload)
    payload["result"]["value"] = (
        ASRCriticalNumberPrivateStatisticalAssessmentResult
        .INSUFFICIENT_EVIDENCE.value
    )
    forged = ASRCriticalNumberPrivateStatisticalAssessmentBundle(
        payload=payload,
        sha256=calculate_critical_number_private_qualification_sha256(
            payload
        ),
    )
    changed = dict(evidence)
    changed["private_assessment"] = forged

    with pytest.raises(
        HveeContractError,
        match="does not match v1 evidence",
    ):
        _build(changed)


def test_private_assessment_method_binding_tampering_is_rejected():
    evidence = _evidence("ready")
    payload = copy.deepcopy(evidence["private_assessment"].payload)
    payload["method"]["manifest_sha256"] = _PRIVATE._digest(
        "forged-method-manifest"
    )
    forged = ASRCriticalNumberPrivateStatisticalAssessmentBundle(
        payload=payload,
        sha256=calculate_critical_number_private_qualification_sha256(
            payload
        ),
    )
    changed = dict(evidence)
    changed["private_assessment"] = forged

    with pytest.raises(HveeContractError):
        _build(changed)


def test_recomputed_but_forged_production_manifest_is_rejected():
    evidence = _evidence("ready")
    payload = copy.deepcopy(evidence["production_evidence"].payload)
    payload["production_snapshot"]["manifest_id"] = "forged-production"
    forged = ASRCriticalNumberProductionEvidenceManifestBundle(
        payload=payload,
        sha256=calculate_critical_number_production_evidence_sha256(
            payload
        ),
    )
    changed = dict(evidence)
    changed["production_evidence"] = forged

    with pytest.raises(
        HveeContractError,
        match="does not match its definition",
    ):
        _build(changed)


def test_recomputed_but_forged_holdout_exclusion_is_rejected():
    evidence = _evidence("ready")
    payload = copy.deepcopy(evidence["private_holdout_exclusion"].payload)
    payload["private_holdout_binding"]["plan_sha256"] = (
        _PRIVATE._digest("forged-private-plan")
    )
    forged = ASRCriticalNumberPrivateHoldoutExclusionManifestBundle(
        payload=payload,
        sha256=calculate_critical_number_production_evidence_sha256(
            payload
        ),
    )
    changed = dict(evidence)
    changed["private_holdout_exclusion"] = forged

    with pytest.raises(
        HveeContractError,
        match="does not match its verified plan and tokens",
    ):
        _build(changed)


def test_valid_production_evidence_for_other_private_plan_is_rejected():
    evidence = _evidence("ready")

    other_plan_definition, other_plan, tokens, exclusion = (
        _PRODUCTION._exclusion()
    )
    definition = _PRODUCTION._production_definition(exclusion.sha256)
    manifest = build_critical_number_production_evidence_manifest(
        definition=definition,
        private_holdout_exclusion=exclusion,
    )
    verification = ASRCriticalNumberProductionEvidenceVerificationContext(
        plan=other_plan,
        plan_definition=other_plan_definition,
        linkage_tokens=tokens,
        definition=definition,
    )

    changed = dict(evidence)
    changed["private_holdout_exclusion"] = exclusion
    changed["production_evidence"] = manifest
    changed["production_verification"] = verification

    with pytest.raises(
        HveeContractError,
        match="not bound to the private qualification plan",
    ):
        _build(changed)


def test_shadow_must_rebuild_from_same_raw_observations():
    evidence = _evidence("ready", True)

    clear_records = _SHADOW._inputs()
    mismatched_verification = replace(
        evidence["matched_release_shadow_verification"],
        records=clear_records,
    )
    changed = dict(evidence)
    changed["matched_release_shadow_verification"] = (
        mismatched_verification
    )

    with pytest.raises(
        HveeContractError,
        match="does not match its raw observation evidence",
    ):
        _build(changed)


def test_readiness_payload_tampering_is_rejected_even_with_new_digest():
    evidence = _evidence("ready")
    dossier = _build(evidence)

    payload = copy.deepcopy(dossier.payload)
    payload["governance_boundary"]["production_qualified"] = True
    forged_sha256 = (
        calculate_critical_number_qualification_readiness_sha256(payload)
    )

    with pytest.raises(
        HveeContractError,
        match="does not match bound evidence",
    ):
        verify_critical_number_qualification_readiness_v1(
            payload=payload,
            expected_sha256=forged_sha256,
            assurance=evidence["assurance"],
            method_manifest=evidence["method_manifest"],
            private_assessment=evidence["private_assessment"],
            private_verification=evidence["private_verification"],
            private_holdout_exclusion=(
                evidence["private_holdout_exclusion"]
            ),
            production_evidence=evidence["production_evidence"],
            production_verification=evidence["production_verification"],
            matched_release_shadow=evidence["matched_release_shadow"],
            matched_release_shadow_verification=(
                evidence["matched_release_shadow_verification"]
            ),
        )


def test_readiness_payload_wrong_digest_is_rejected():
    evidence = _evidence("ready")
    dossier = _build(evidence)

    with pytest.raises(
        HveeContractError,
        match="does not match expected SHA-256",
    ):
        verify_critical_number_qualification_readiness_v1(
            payload=dossier.payload,
            expected_sha256=_PRIVATE._digest("wrong-readiness-digest"),
            assurance=evidence["assurance"],
            method_manifest=evidence["method_manifest"],
            private_assessment=evidence["private_assessment"],
            private_verification=evidence["private_verification"],
            private_holdout_exclusion=(
                evidence["private_holdout_exclusion"]
            ),
            production_evidence=evidence["production_evidence"],
            production_verification=evidence["production_verification"],
            matched_release_shadow=evidence["matched_release_shadow"],
            matched_release_shadow_verification=(
                evidence["matched_release_shadow_verification"]
            ),
        )


def test_readiness_public_exports_are_complete():
    expected = {
        "ASRCriticalNumberMatchedReleaseShadowVerificationContext",
        "ASRCriticalNumberPrivateQualificationVerificationContext",
        "ASRCriticalNumberProductionEvidenceVerificationContext",
        "ASRCriticalNumberQualificationReadinessBundle",
        "ASRCriticalNumberQualificationReadinessResult",
        "CRITICAL_NUMBER_QUALIFICATION_READINESS_KEY",
        "CRITICAL_NUMBER_QUALIFICATION_READINESS_SCHEMA_VERSION",
        "CRITICAL_NUMBER_QUALIFICATION_READINESS_VERSION",
        "build_critical_number_qualification_readiness_v1",
        "calculate_critical_number_qualification_readiness_sha256",
        "verify_critical_number_qualification_readiness_v1",
    }

    assert expected.issubset(set(asr.__all__))
    assert all(hasattr(asr, name) for name in expected)

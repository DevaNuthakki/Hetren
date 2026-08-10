from __future__ import annotations

import copy
import hashlib
import importlib.util
from dataclasses import replace
from functools import lru_cache
from pathlib import Path
from types import ModuleType

import pytest

from hvee.core.contracts import HveeContractError
from hvee.packs import asr
from hvee.packs.asr.critical_number_fidelity import (
    CRITICAL_NUMBER_FIDELITY_EVALUATOR,
    EN_US_CRITICAL_NUMBER_PROFILE,
)
from hvee.packs.asr.critical_number_governance_review import (
    ASRCriticalNumberGovernanceDisposition,
    ASRCriticalNumberGovernanceReviewBundle,
    calculate_critical_number_governance_review_sha256,
)
from hvee.packs.asr.critical_number_production_qualification import (
    CRITICAL_NUMBER_PRODUCTION_QUALIFICATION_AUTHORIZATION_SCHEMA_VERSION,
    CRITICAL_NUMBER_PRODUCTION_QUALIFICATION_KEY,
    CRITICAL_NUMBER_PRODUCTION_QUALIFICATION_POLICY_SCHEMA_VERSION,
    CRITICAL_NUMBER_PRODUCTION_QUALIFICATION_VERSION,
    CRITICAL_NUMBER_PRODUCTION_REQUALIFICATION_TRIGGERS_V1,
    ASRCriticalNumberGovernanceReviewVerificationContext,
    ASRCriticalNumberProductionQualificationAuthorizationBundle,
    ASRCriticalNumberProductionQualificationAuthorizationDefinition,
    ASRCriticalNumberProductionQualificationAuthority,
    ASRCriticalNumberProductionQualificationPolicyBundle,
    ASRCriticalNumberProductionQualificationPolicyDefinition,
    ASRCriticalNumberProductionQualificationScope,
    ASRCriticalNumberProductionUseCategory,
    ASRCriticalNumberRequalificationTrigger,
    build_critical_number_production_qualification_authorization_v1,
    build_critical_number_production_qualification_policy_v1,
    calculate_critical_number_production_qualification_sha256,
    verify_critical_number_production_qualification_authorization_v1,
    verify_critical_number_production_qualification_policy_v1,
)


def _load_sibling_test_module(filename: str, module_name: str) -> ModuleType:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load test fixture module: {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_GOVERNANCE = _load_sibling_test_module(
    "test_critical_number_governance_review.py",
    "_hetren_production_qualification_governance_fixtures",
)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _scope(**changes):
    values = {
        "evaluator_key": CRITICAL_NUMBER_FIDELITY_EVALUATOR.key,
        "evaluator_version": CRITICAL_NUMBER_FIDELITY_EVALUATOR.version,
        "evaluation_type": CRITICAL_NUMBER_FIDELITY_EVALUATOR.evaluation_type,
        "evaluation_profile_key": EN_US_CRITICAL_NUMBER_PROFILE.key,
        "evaluation_profile_version": EN_US_CRITICAL_NUMBER_PROFILE.version,
        "language": EN_US_CRITICAL_NUMBER_PROFILE.language,
        "locale": EN_US_CRITICAL_NUMBER_PROFILE.locale,
        "production_use_category": (
            ASRCriticalNumberProductionUseCategory
            .ADVISORY_PRODUCTION_EVALUATION
        ),
        "scope_definition_sha256": _digest(
            "critical-number-production-scope-v1"
        ),
    }
    values.update(changes)
    return ASRCriticalNumberProductionQualificationScope(**values)


def _authority(**changes):
    values = {
        "key_id": "critical-number-production-qualification-authority",
        "affiliation_key": "independent-production-qualification-authority",
        "qualification_sha256": _digest(
            "production-qualification-authority-qualification"
        ),
        "authorization_sha256": _digest(
            "production-qualification-authority-authorization"
        ),
        "independence_attestation_sha256": _digest(
            "production-qualification-authority-independence"
        ),
    }
    values.update(changes)
    return ASRCriticalNumberProductionQualificationAuthority(**values)


def _governance_review_context(
    disposition: str = "approved",
    *,
    candidate_violation: bool = False,
):
    context = _GOVERNANCE._governance_context(
        "ready",
        candidate_violation,
    )
    definition = context["review_definition"]

    if disposition != "approved":
        if disposition == "rejected":
            dispositions = (
                ASRCriticalNumberGovernanceDisposition
                .APPROVED_FOR_QUALIFICATION_CONSIDERATION,
                ASRCriticalNumberGovernanceDisposition
                .APPROVED_FOR_QUALIFICATION_CONSIDERATION,
                ASRCriticalNumberGovernanceDisposition.REJECTED,
            )
        elif disposition == "more_evidence":
            dispositions = (
                ASRCriticalNumberGovernanceDisposition
                .APPROVED_FOR_QUALIFICATION_CONSIDERATION,
                ASRCriticalNumberGovernanceDisposition
                .MORE_EVIDENCE_REQUIRED,
                ASRCriticalNumberGovernanceDisposition
                .APPROVED_FOR_QUALIFICATION_CONSIDERATION,
            )
        else:
            raise ValueError(f"unknown governance disposition: {disposition}")

        definition = replace(
            definition,
            decisions=_GOVERNANCE._decisions(
                context["readiness"],
                context["reviewers"],
                dispositions=dispositions,
            ),
        )

    review = _GOVERNANCE._build_review(context, definition)

    verification = ASRCriticalNumberGovernanceReviewVerificationContext(
        protocol=context["protocol"],
        protocol_definition=context["protocol_definition"],
        readiness=context["readiness"],
        readiness_evidence=context["readiness_evidence"],
        definition=definition,
    )

    return context, review, verification


def _policy_definition(
    governance_review,
    *,
    scope=None,
    authority=None,
    **changes,
):
    values = {
        "qualification_id": "critical-number-production-qualification-001",
        "qualification_version": "1.0.0",
        "governance_review_sha256": governance_review.sha256,
        "scope": scope or _scope(),
        "authority": authority or _authority(),
        "effective_at_utc": "2026-08-10T00:00:00Z",
        "expires_at_utc": "2027-08-10T00:00:00Z",
        "qualification_procedure_sha256": _digest(
            "production-qualification-procedure"
        ),
        "validity_policy_sha256": _digest(
            "production-qualification-validity-policy"
        ),
        "requalification_policy_sha256": _digest(
            "production-requalification-policy"
        ),
        "revocation_policy_sha256": _digest(
            "production-qualification-revocation-policy"
        ),
    }
    values.update(changes)
    return ASRCriticalNumberProductionQualificationPolicyDefinition(**values)


@lru_cache(maxsize=None)
def _qualification_context(candidate_violation: bool = False):
    governance_context, governance_review, governance_verification = (
        _governance_review_context(
            candidate_violation=candidate_violation,
        )
    )

    policy_definition = _policy_definition(governance_review)

    policy = build_critical_number_production_qualification_policy_v1(
        definition=policy_definition,
        governance_review=governance_review,
        governance_verification=governance_verification,
    )

    authorization_definition = (
        ASRCriticalNumberProductionQualificationAuthorizationDefinition(
            qualification_id=policy_definition.qualification_id,
            qualification_version=policy_definition.qualification_version,
            policy_sha256=policy.sha256,
            governance_review_sha256=governance_review.sha256,
            authority_key_id=policy_definition.authority.key_id,
            authorization_record_sha256=_digest(
                "production-qualification-authorization-record"
            ),
            issuance_attestation_sha256=_digest(
                "production-qualification-issuance-attestation"
            ),
        )
    )

    return {
        "governance_context": governance_context,
        "governance_review": governance_review,
        "governance_verification": governance_verification,
        "policy_definition": policy_definition,
        "policy": policy,
        "authorization_definition": authorization_definition,
    }


def _build_authorization(context, definition=None):
    return build_critical_number_production_qualification_authorization_v1(
        policy=context["policy"],
        policy_definition=context["policy_definition"],
        governance_review=context["governance_review"],
        governance_verification=context["governance_verification"],
        definition=definition or context["authorization_definition"],
    )


def test_production_qualification_policy_is_deterministic_and_non_authorizing():
    context = _qualification_context()

    first = build_critical_number_production_qualification_policy_v1(
        definition=context["policy_definition"],
        governance_review=context["governance_review"],
        governance_verification=context["governance_verification"],
    )
    second = build_critical_number_production_qualification_policy_v1(
        definition=context["policy_definition"],
        governance_review=context["governance_review"],
        governance_verification=context["governance_verification"],
    )

    assert first == second
    assert first.sha256 == (
        calculate_critical_number_production_qualification_sha256(
            first.payload
        )
    )
    assert first.payload["schema_version"] == (
        CRITICAL_NUMBER_PRODUCTION_QUALIFICATION_POLICY_SCHEMA_VERSION
    )
    assert first.payload["qualification_profile"] == {
        "key": CRITICAL_NUMBER_PRODUCTION_QUALIFICATION_KEY,
        "version": CRITICAL_NUMBER_PRODUCTION_QUALIFICATION_VERSION,
        "artifact": "production_qualification_policy",
    }
    assert first.payload["authority_boundary"] == {
        "qualification_policy_only": True,
        "qualification_authorization_issued": False,
        "certification_issued": False,
        "production_qualified": False,
        "release_enforcement_eligible": False,
        "official_release_verdict_modified": False,
    }


def test_production_qualification_policy_verifier_rebuilds_full_chain():
    context = _qualification_context()

    verified = verify_critical_number_production_qualification_policy_v1(
        payload=context["policy"].payload,
        expected_sha256=context["policy"].sha256,
        definition=context["policy_definition"],
        governance_review=context["governance_review"],
        governance_verification=context["governance_verification"],
    )

    assert verified == context["policy"]


def test_production_authorization_is_deterministic_and_scoped():
    context = _qualification_context()

    first = _build_authorization(context)
    second = _build_authorization(context)

    assert first == second
    assert first.sha256 == (
        calculate_critical_number_production_qualification_sha256(
            first.payload
        )
    )
    assert first.payload["schema_version"] == (
        CRITICAL_NUMBER_PRODUCTION_QUALIFICATION_AUTHORIZATION_SCHEMA_VERSION
    )

    assert first.payload["authority"] == {
        "qualification_authorization_issued": True,
        "production_qualified": True,
        "production_use_limited_to_authorized_scope": True,
        "runtime_eligibility_currently_evaluated": False,
        "validity_window_check_required": True,
        "revocation_check_required": True,
        "requalification_trigger_check_required": True,
        "certification_issued": False,
        "release_enforcement_eligible": False,
        "official_release_verdict_modified": False,
    }


def test_production_authorization_verifier_rebuilds_exact_authorization():
    context = _qualification_context()
    authorization = _build_authorization(context)

    verified = (
        verify_critical_number_production_qualification_authorization_v1(
            payload=authorization.payload,
            expected_sha256=authorization.sha256,
            policy=context["policy"],
            policy_definition=context["policy_definition"],
            governance_review=context["governance_review"],
            governance_verification=context["governance_verification"],
            definition=context["authorization_definition"],
        )
    )

    assert verified == authorization


def test_production_scope_binds_canonical_evaluator_and_en_us_profile():
    context = _qualification_context()
    scope = context["policy"].payload["bindings"]["scope"]

    assert scope["evaluator"] == {
        "key": CRITICAL_NUMBER_FIDELITY_EVALUATOR.key,
        "version": CRITICAL_NUMBER_FIDELITY_EVALUATOR.version,
        "evaluation_type": CRITICAL_NUMBER_FIDELITY_EVALUATOR.evaluation_type,
    }
    assert scope["evaluation_profile"] == {
        "key": EN_US_CRITICAL_NUMBER_PROFILE.key,
        "version": EN_US_CRITICAL_NUMBER_PROFILE.version,
        "language": EN_US_CRITICAL_NUMBER_PROFILE.language,
        "locale": EN_US_CRITICAL_NUMBER_PROFILE.locale,
    }
    assert scope["production_use_category"] == (
        ASRCriticalNumberProductionUseCategory
        .ADVISORY_PRODUCTION_EVALUATION.value
    )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("evaluator_key", "other-evaluator"),
        ("evaluator_version", "2.0.0"),
        ("evaluation_type", "tts"),
        ("evaluation_profile_key", "other-profile"),
        ("evaluation_profile_version", "2.0.0"),
        ("language", "de"),
        ("locale", "de-DE"),
    ),
)
def test_production_scope_rejects_noncanonical_identity(field, value):
    with pytest.raises(
        HveeContractError,
        match="must match the canonical",
    ):
        _scope(**{field: value})


@pytest.mark.parametrize("disposition", ("rejected", "more_evidence"))
def test_production_qualification_requires_governance_approval(disposition):
    _, governance_review, verification = _governance_review_context(
        disposition
    )
    definition = _policy_definition(governance_review)

    with pytest.raises(
        HveeContractError,
        match="requires governance approval",
    ):
        build_critical_number_production_qualification_policy_v1(
            definition=definition,
            governance_review=governance_review,
            governance_verification=verification,
        )


def test_qualification_authority_must_be_distinct_from_governance_reviewers():
    governance_context, governance_review, verification = (
        _governance_review_context()
    )
    reviewer_key = governance_context["reviewers"][0].key_id
    authority = _authority(key_id=reviewer_key)
    definition = _policy_definition(
        governance_review,
        authority=authority,
    )

    with pytest.raises(
        HveeContractError,
        match="distinct from governance reviewers",
    ):
        build_critical_number_production_qualification_policy_v1(
            definition=definition,
            governance_review=governance_review,
            governance_verification=verification,
        )


def test_qualification_authority_must_be_distinct_from_private_adjudicators():
    governance_context, governance_review, verification = (
        _governance_review_context()
    )
    private_key = (
        governance_context["evidence"]["private_verification"]
        .adjudication_definition
        .adjudicators[0]
        .key_id
    )
    authority = _authority(key_id=private_key)
    definition = _policy_definition(
        governance_review,
        authority=authority,
    )

    with pytest.raises(
        HveeContractError,
        match="distinct from private adjudicators",
    ):
        build_critical_number_production_qualification_policy_v1(
            definition=definition,
            governance_review=governance_review,
            governance_verification=verification,
        )


@pytest.mark.parametrize(
    "timestamp",
    (
        "2026-08-10",
        "2026-08-10T00:00:00",
        "2026-08-10T00:00:00+00:00",
        "2026-08-10T00:00:00.000Z",
    ),
)
def test_qualification_validity_requires_canonical_utc(timestamp):
    _, governance_review, _ = _governance_review_context()

    with pytest.raises(
        HveeContractError,
        match="must use",
    ):
        _policy_definition(
            governance_review,
            effective_at_utc=timestamp,
        )


@pytest.mark.parametrize(
    "expires_at",
    (
        "2026-08-10T00:00:00Z",
        "2026-08-09T23:59:59Z",
    ),
)
def test_qualification_expiration_must_follow_effective_time(expires_at):
    _, governance_review, _ = _governance_review_context()

    with pytest.raises(
        HveeContractError,
        match="expiration must follow",
    ):
        _policy_definition(
            governance_review,
            effective_at_utc="2026-08-10T00:00:00Z",
            expires_at_utc=expires_at,
        )


def test_policy_must_bind_exact_governance_review():
    context = _qualification_context()

    definition = replace(
        context["policy_definition"],
        governance_review_sha256=_digest("different-governance-review"),
    )

    with pytest.raises(
        HveeContractError,
        match="does not bind",
    ):
        build_critical_number_production_qualification_policy_v1(
            definition=definition,
            governance_review=context["governance_review"],
            governance_verification=context["governance_verification"],
        )


def test_authorization_must_bind_exact_policy():
    context = _qualification_context()

    definition = replace(
        context["authorization_definition"],
        policy_sha256=_digest("different-policy"),
    )

    with pytest.raises(
        HveeContractError,
        match="does not bind the policy",
    ):
        _build_authorization(context, definition)


def test_authorization_must_bind_exact_governance_review():
    context = _qualification_context()

    definition = replace(
        context["authorization_definition"],
        governance_review_sha256=_digest("different-governance-review"),
    )

    with pytest.raises(
        HveeContractError,
        match="does not bind governance review",
    ):
        _build_authorization(context, definition)


def test_authorization_authority_must_match_policy():
    context = _qualification_context()

    definition = replace(
        context["authorization_definition"],
        authority_key_id="different-production-qualification-authority",
    )

    with pytest.raises(
        HveeContractError,
        match="authority does not match policy",
    ):
        _build_authorization(context, definition)


def test_forged_rehashed_governance_review_cannot_produce_qualification():
    context = _qualification_context()

    payload = copy.deepcopy(context["governance_review"].payload)
    payload["authority"]["production_qualified"] = True

    forged = ASRCriticalNumberGovernanceReviewBundle(
        payload=payload,
        sha256=calculate_critical_number_governance_review_sha256(payload),
    )

    definition = replace(
        context["policy_definition"],
        governance_review_sha256=forged.sha256,
    )

    with pytest.raises(HveeContractError):
        build_critical_number_production_qualification_policy_v1(
            definition=definition,
            governance_review=forged,
            governance_verification=context["governance_verification"],
        )


def test_forged_rehashed_policy_is_rejected():
    context = _qualification_context()

    payload = copy.deepcopy(context["policy"].payload)
    payload["authority_boundary"]["production_qualified"] = True

    forged = ASRCriticalNumberProductionQualificationPolicyBundle(
        payload=payload,
        sha256=calculate_critical_number_production_qualification_sha256(
            payload
        ),
    )

    changed = dict(context)
    changed["policy"] = forged

    with pytest.raises(
        HveeContractError,
        match="does not match bound evidence",
    ):
        _build_authorization(changed)


def test_forged_rehashed_authorization_is_rejected():
    context = _qualification_context()
    authorization = _build_authorization(context)

    payload = copy.deepcopy(authorization.payload)
    payload["authority"]["release_enforcement_eligible"] = True

    forged = ASRCriticalNumberProductionQualificationAuthorizationBundle(
        payload=payload,
        sha256=calculate_critical_number_production_qualification_sha256(
            payload
        ),
    )

    with pytest.raises(
        HveeContractError,
        match="does not match its bound evidence",
    ):
        verify_critical_number_production_qualification_authorization_v1(
            payload=forged.payload,
            expected_sha256=forged.sha256,
            policy=context["policy"],
            policy_definition=context["policy_definition"],
            governance_review=context["governance_review"],
            governance_verification=context["governance_verification"],
            definition=context["authorization_definition"],
        )


def test_requalification_trigger_set_is_exact_and_versioned():
    assert CRITICAL_NUMBER_PRODUCTION_REQUALIFICATION_TRIGGERS_V1 == (
        ASRCriticalNumberRequalificationTrigger.EVALUATOR_VERSION_CHANGE,
        ASRCriticalNumberRequalificationTrigger.ASSURANCE_PROFILE_CHANGE,
        ASRCriticalNumberRequalificationTrigger.STATISTICAL_METHOD_CHANGE,
        (
            ASRCriticalNumberRequalificationTrigger
            .PRIVATE_QUALIFICATION_EVIDENCE_CHANGE
        ),
        ASRCriticalNumberRequalificationTrigger.PRODUCTION_EVIDENCE_CHANGE,
        ASRCriticalNumberRequalificationTrigger.GOVERNANCE_REVIEW_CHANGE,
        ASRCriticalNumberRequalificationTrigger.QUALIFICATION_SCOPE_EXPANSION,
        ASRCriticalNumberRequalificationTrigger.MATERIAL_EVALUATOR_REGRESSION,
        ASRCriticalNumberRequalificationTrigger.QUALIFICATION_EXPIRATION,
        ASRCriticalNumberRequalificationTrigger.EXPLICIT_REVOCATION,
    )

    context = _qualification_context()
    authorization = _build_authorization(context)

    assert authorization.payload["controls"]["requalification_triggers"] == [
        trigger.value
        for trigger in CRITICAL_NUMBER_PRODUCTION_REQUALIFICATION_TRIGGERS_V1
    ]


def test_historical_authorization_does_not_claim_runtime_eligibility():
    context = _qualification_context()
    authorization = _build_authorization(context)

    assert authorization.payload["authority"][
        "runtime_eligibility_currently_evaluated"
    ] is False
    assert authorization.payload["authority"][
        "validity_window_check_required"
    ] is True
    assert authorization.payload["authority"][
        "revocation_check_required"
    ] is True
    assert authorization.payload["authority"][
        "requalification_trigger_check_required"
    ] is True

    assert context["policy"].payload["qualification_policy"][
        "wall_clock_consulted_during_build"
    ] is False


def test_production_qualification_does_not_copy_confidential_evidence():
    context = _qualification_context()
    authorization = _build_authorization(context)
    serialized = repr(authorization.payload)

    evidence = context["governance_context"]["evidence"]

    assert all(
        case.case_token not in serialized
        for case in evidence["private_context"]["plan_definition"].cases
    )
    assert all(
        case.cross_set_linkage_token not in serialized
        for case in evidence["production_verification"].definition.cases
    )
    assert all(
        token not in serialized
        for token in evidence["production_verification"].linkage_tokens
    )

    assert authorization.payload["confidentiality"] == {
        "governance_review_payload_in_artifact": False,
        "qualification_readiness_payload_in_artifact": False,
        "private_case_content_in_artifact": False,
        "production_case_commitments_in_artifact": False,
        "cross_set_linkage_tokens_in_artifact": False,
        "authorization_record_contents_in_artifact": False,
        "opaque_commitments_and_scope_only": True,
    }


def test_shadow_hypothetical_failure_does_not_create_post_hoc_gate():
    context = _qualification_context(candidate_violation=True)

    assert context["governance_context"]["readiness"].payload[
        "evidence"
    ]["matched_release_shadow"]["would_change_official_decision"] is True

    authorization = _build_authorization(context)

    assert authorization.payload["authority"]["production_qualified"] is True
    assert authorization.payload["authority"][
        "release_enforcement_eligible"
    ] is False
    assert authorization.payload["authority"][
        "official_release_verdict_modified"
    ] is False


def test_production_qualification_public_exports_are_complete():
    expected = {
        "ASRCriticalNumberGovernanceReviewVerificationContext",
        "ASRCriticalNumberProductionQualificationAuthorizationBundle",
        "ASRCriticalNumberProductionQualificationAuthorizationDefinition",
        "ASRCriticalNumberProductionQualificationAuthority",
        "ASRCriticalNumberProductionQualificationPolicyBundle",
        "ASRCriticalNumberProductionQualificationPolicyDefinition",
        "ASRCriticalNumberProductionQualificationScope",
        "ASRCriticalNumberProductionUseCategory",
        "ASRCriticalNumberRequalificationTrigger",
        "CRITICAL_NUMBER_PRODUCTION_QUALIFICATION_AUTHORIZATION_SCHEMA_VERSION",
        "CRITICAL_NUMBER_PRODUCTION_QUALIFICATION_KEY",
        "CRITICAL_NUMBER_PRODUCTION_QUALIFICATION_POLICY_SCHEMA_VERSION",
        "CRITICAL_NUMBER_PRODUCTION_QUALIFICATION_VERSION",
        "CRITICAL_NUMBER_PRODUCTION_REQUALIFICATION_TRIGGERS_V1",
        "build_critical_number_production_qualification_authorization_v1",
        "build_critical_number_production_qualification_policy_v1",
        "calculate_critical_number_production_qualification_sha256",
        "verify_critical_number_production_qualification_authorization_v1",
        "verify_critical_number_production_qualification_policy_v1",
    }

    assert expected.issubset(set(asr.__all__))
    assert all(hasattr(asr, name) for name in expected)

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
from hvee.packs.asr.critical_number_governance_review import (
    CRITICAL_NUMBER_GOVERNANCE_DECISION_RULE_KEY,
    CRITICAL_NUMBER_GOVERNANCE_DECISION_RULE_VERSION,
    CRITICAL_NUMBER_GOVERNANCE_REQUIRED_ROLES_V1,
    CRITICAL_NUMBER_GOVERNANCE_REVIEW_PROTOCOL_KEY,
    CRITICAL_NUMBER_GOVERNANCE_REVIEW_PROTOCOL_SCHEMA_VERSION,
    CRITICAL_NUMBER_GOVERNANCE_REVIEW_PROTOCOL_VERSION,
    CRITICAL_NUMBER_GOVERNANCE_REVIEW_SCHEMA_VERSION,
    ASRCriticalNumberGovernanceDisposition,
    ASRCriticalNumberGovernanceReviewBundle,
    ASRCriticalNumberGovernanceReviewDefinition,
    ASRCriticalNumberGovernanceReviewer,
    ASRCriticalNumberGovernanceReviewerDecision,
    ASRCriticalNumberGovernanceReviewerRole,
    ASRCriticalNumberGovernanceReviewProtocolBundle,
    ASRCriticalNumberGovernanceReviewProtocolDefinition,
    ASRCriticalNumberQualificationReadinessEvidenceContext,
    build_critical_number_governance_review_protocol_v1,
    build_critical_number_governance_review_v1,
    calculate_critical_number_governance_reviewer_roster_sha256,
    calculate_critical_number_governance_review_sha256,
    verify_critical_number_governance_review_protocol_v1,
    verify_critical_number_governance_review_v1,
)
from hvee.packs.asr.critical_number_qualification_readiness import (
    ASRCriticalNumberQualificationReadinessResult,
)


def _load_sibling_test_module(filename: str, module_name: str) -> ModuleType:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load test fixture module: {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_READINESS = _load_sibling_test_module(
    "test_critical_number_qualification_readiness.py",
    "_hetren_governance_readiness_fixtures",
)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _readiness_context(evidence):
    return ASRCriticalNumberQualificationReadinessEvidenceContext(
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


def _reviewers():
    return tuple(
        ASRCriticalNumberGovernanceReviewer(
            role=role,
            key_id=f"critical-number-governance-{role.value}",
            affiliation_key=f"independent-governance-{role.value}",
            qualification_sha256=_digest(
                f"governance-qualification-{role.value}"
            ),
            authorization_sha256=_digest(
                f"governance-authorization-{role.value}"
            ),
            independence_attestation_sha256=_digest(
                f"governance-independence-{role.value}"
            ),
        )
        for role in CRITICAL_NUMBER_GOVERNANCE_REQUIRED_ROLES_V1
    )


def _protocol_definition(readiness, *, reviewers=None, **changes):
    values = {
        "review_id": "critical-number-governance-review-001",
        "review_version": "1.0.0",
        "readiness_sha256": readiness.sha256,
        "reviewers": reviewers or _reviewers(),
        "review_procedure_sha256": _digest("governance-review-procedure"),
        "reviewer_qualification_policy_sha256": _digest(
            "governance-reviewer-qualification-policy"
        ),
        "conflict_of_interest_policy_sha256": _digest(
            "governance-conflict-of-interest-policy"
        ),
        "authority_policy_sha256": _digest("governance-authority-policy"),
    }
    values.update(changes)
    return ASRCriticalNumberGovernanceReviewProtocolDefinition(**values)


def _decisions(readiness, reviewers, *, dispositions=None):
    dispositions = dispositions or tuple(
        ASRCriticalNumberGovernanceDisposition
        .APPROVED_FOR_QUALIFICATION_CONSIDERATION
        for _reviewer in reviewers
    )
    return tuple(
        ASRCriticalNumberGovernanceReviewerDecision(
            role=reviewer.role,
            reviewer_key_id=reviewer.key_id,
            readiness_sha256=readiness.sha256,
            disposition=disposition,
            decision_record_sha256=_digest(
                f"governance-decision-{reviewer.role.value}"
            ),
            evidence_review_attestation_sha256=_digest(
                f"governance-evidence-review-{reviewer.role.value}"
            ),
        )
        for reviewer, disposition in zip(
            reviewers,
            dispositions,
            strict=True,
        )
    )


@lru_cache(maxsize=None)
def _governance_context(
    readiness_kind: str = "ready",
    candidate_violation: bool = False,
):
    evidence = _READINESS._evidence(
        readiness_kind,
        candidate_violation,
    )
    readiness = _READINESS._build(evidence)
    readiness_evidence = _readiness_context(evidence)

    reviewers = _reviewers()
    protocol_definition = _protocol_definition(
        readiness,
        reviewers=reviewers,
    )
    protocol = build_critical_number_governance_review_protocol_v1(
        definition=protocol_definition,
        readiness=readiness,
        readiness_evidence=readiness_evidence,
    )

    decisions = _decisions(readiness, reviewers)
    review_definition = ASRCriticalNumberGovernanceReviewDefinition(
        review_id=protocol_definition.review_id,
        review_version=protocol_definition.review_version,
        protocol_sha256=protocol.sha256,
        readiness_sha256=readiness.sha256,
        review_environment_sha256=_digest(
            "governance-review-environment"
        ),
        independence_attestation_sha256=_digest(
            "governance-review-independence"
        ),
        decisions=decisions,
    )

    return {
        "evidence": evidence,
        "readiness": readiness,
        "readiness_evidence": readiness_evidence,
        "reviewers": reviewers,
        "protocol_definition": protocol_definition,
        "protocol": protocol,
        "decisions": decisions,
        "review_definition": review_definition,
    }


def _build_review(context, definition=None):
    return build_critical_number_governance_review_v1(
        protocol=context["protocol"],
        protocol_definition=context["protocol_definition"],
        readiness=context["readiness"],
        readiness_evidence=context["readiness_evidence"],
        definition=definition or context["review_definition"],
    )


def test_governance_protocol_is_deterministic_and_sealed():
    context = _governance_context()
    first = build_critical_number_governance_review_protocol_v1(
        definition=context["protocol_definition"],
        readiness=context["readiness"],
        readiness_evidence=context["readiness_evidence"],
    )
    second = build_critical_number_governance_review_protocol_v1(
        definition=context["protocol_definition"],
        readiness=context["readiness"],
        readiness_evidence=context["readiness_evidence"],
    )

    assert first == second
    assert first.sha256 == calculate_critical_number_governance_review_sha256(
        first.payload
    )
    assert first.payload["schema_version"] == (
        CRITICAL_NUMBER_GOVERNANCE_REVIEW_PROTOCOL_SCHEMA_VERSION
    )
    assert first.payload["protocol"] == {
        "key": CRITICAL_NUMBER_GOVERNANCE_REVIEW_PROTOCOL_KEY,
        "version": CRITICAL_NUMBER_GOVERNANCE_REVIEW_PROTOCOL_VERSION,
        "artifact": "preregistered_governance_review_protocol",
        "decision_rule": {
            "key": CRITICAL_NUMBER_GOVERNANCE_DECISION_RULE_KEY,
            "version": CRITICAL_NUMBER_GOVERNANCE_DECISION_RULE_VERSION,
        },
    }
    assert (
        first.payload["sealed_evidence"][
            "complete_readiness_chain_reverified"
        ]
        is True
    )
    assert first.payload["preregistration"]["approval_requires_unanimity"] is True


def test_governance_protocol_verifier_rebuilds_readiness_chain():
    context = _governance_context()

    verified = verify_critical_number_governance_review_protocol_v1(
        payload=context["protocol"].payload,
        expected_sha256=context["protocol"].sha256,
        definition=context["protocol_definition"],
        readiness=context["readiness"],
        readiness_evidence=context["readiness_evidence"],
    )

    assert verified == context["protocol"]


def test_unanimous_governance_approval_only_authorizes_consideration():
    context = _governance_context()
    first = _build_review(context)
    second = _build_review(context)

    assert first == second
    assert first.sha256 == calculate_critical_number_governance_review_sha256(
        first.payload
    )
    assert first.payload["schema_version"] == (
        CRITICAL_NUMBER_GOVERNANCE_REVIEW_SCHEMA_VERSION
    )
    assert first.payload["governance_review"]["disposition"] == (
        ASRCriticalNumberGovernanceDisposition
        .APPROVED_FOR_QUALIFICATION_CONSIDERATION.value
    )
    assert first.payload["governance_review"]["unanimous_approval"] is True

    assert first.payload["authority"] == {
        "governance_disposition": (
            ASRCriticalNumberGovernanceDisposition
            .APPROVED_FOR_QUALIFICATION_CONSIDERATION.value
        ),
        "qualification_consideration_authorized": True,
        "evaluator_status": "experimental",
        "approval_scope": "qualification_consideration_only",
        "certification_issued": False,
        "production_qualified": False,
        "release_enforcement_eligible": False,
        "official_release_verdict_modified": False,
    }


def test_completed_governance_review_verifier_rebuilds_exact_review():
    context = _governance_context()
    review = _build_review(context)

    verified = verify_critical_number_governance_review_v1(
        payload=review.payload,
        expected_sha256=review.sha256,
        protocol=context["protocol"],
        protocol_definition=context["protocol_definition"],
        readiness=context["readiness"],
        readiness_evidence=context["readiness_evidence"],
        definition=context["review_definition"],
    )

    assert verified == review


def test_rejection_dominates_governance_resolution():
    context = _governance_context()
    dispositions = (
        ASRCriticalNumberGovernanceDisposition
        .APPROVED_FOR_QUALIFICATION_CONSIDERATION,
        ASRCriticalNumberGovernanceDisposition.MORE_EVIDENCE_REQUIRED,
        ASRCriticalNumberGovernanceDisposition.REJECTED,
    )
    definition = replace(
        context["review_definition"],
        decisions=_decisions(
            context["readiness"],
            context["reviewers"],
            dispositions=dispositions,
        ),
    )

    review = _build_review(context, definition)

    assert review.payload["governance_review"]["disposition"] == (
        ASRCriticalNumberGovernanceDisposition.REJECTED.value
    )
    assert review.payload["authority"][
        "qualification_consideration_authorized"
    ] is False


def test_more_evidence_dominates_non_unanimous_approval():
    context = _governance_context()
    dispositions = (
        ASRCriticalNumberGovernanceDisposition
        .APPROVED_FOR_QUALIFICATION_CONSIDERATION,
        ASRCriticalNumberGovernanceDisposition.MORE_EVIDENCE_REQUIRED,
        ASRCriticalNumberGovernanceDisposition
        .APPROVED_FOR_QUALIFICATION_CONSIDERATION,
    )
    definition = replace(
        context["review_definition"],
        decisions=_decisions(
            context["readiness"],
            context["reviewers"],
            dispositions=dispositions,
        ),
    )

    review = _build_review(context, definition)

    assert review.payload["governance_review"]["disposition"] == (
        ASRCriticalNumberGovernanceDisposition.MORE_EVIDENCE_REQUIRED.value
    )
    assert review.payload["governance_review"]["unanimous_approval"] is False
    assert review.payload["authority"][
        "qualification_consideration_authorized"
    ] is False


@pytest.mark.parametrize("kind", ("criteria_not_met", "insufficient"))
def test_governance_cannot_review_non_ready_evidence(kind):
    evidence = _READINESS._evidence(kind)
    readiness = _READINESS._build(evidence)

    assert readiness.payload["readiness"]["result"] != (
        ASRCriticalNumberQualificationReadinessResult
        .READY_FOR_GOVERNANCE_REVIEW.value
    )

    definition = _protocol_definition(readiness)

    with pytest.raises(
        HveeContractError,
        match="requires evidence ready for governance review",
    ):
        build_critical_number_governance_review_protocol_v1(
            definition=definition,
            readiness=readiness,
            readiness_evidence=_readiness_context(evidence),
        )


def test_governance_reviewers_must_be_distinct_from_private_adjudicators():
    evidence = _READINESS._evidence("ready")
    readiness = _READINESS._build(evidence)

    private_key = (
        evidence["private_verification"]
        .adjudication_definition
        .adjudicators[0]
        .key_id
    )
    reviewers = list(_reviewers())
    reviewers[0] = replace(reviewers[0], key_id=private_key)

    definition = _protocol_definition(
        readiness,
        reviewers=tuple(reviewers),
    )

    with pytest.raises(
        HveeContractError,
        match="distinct from private adjudicators",
    ):
        build_critical_number_governance_review_protocol_v1(
            definition=definition,
            readiness=readiness,
            readiness_evidence=_readiness_context(evidence),
        )


def test_governance_reviewer_roster_requires_exact_roles_and_unique_keys():
    reviewers = _reviewers()

    with pytest.raises(
        HveeContractError,
        match="required ordered roles",
    ):
        ASRCriticalNumberGovernanceReviewProtocolDefinition(
            review_id="governance-invalid-order",
            review_version="1.0.0",
            readiness_sha256=_digest("readiness"),
            reviewers=tuple(reversed(reviewers)),
            review_procedure_sha256=_digest("procedure"),
            reviewer_qualification_policy_sha256=_digest("qualification"),
            conflict_of_interest_policy_sha256=_digest("coi"),
            authority_policy_sha256=_digest("authority"),
        )

    duplicate = list(reviewers)
    duplicate[1] = replace(
        duplicate[1],
        key_id=duplicate[0].key_id,
    )

    with pytest.raises(
        HveeContractError,
        match="distinct key ids",
    ):
        ASRCriticalNumberGovernanceReviewProtocolDefinition(
            review_id="governance-duplicate-key",
            review_version="1.0.0",
            readiness_sha256=_digest("readiness"),
            reviewers=tuple(duplicate),
            review_procedure_sha256=_digest("procedure"),
            reviewer_qualification_policy_sha256=_digest("qualification"),
            conflict_of_interest_policy_sha256=_digest("coi"),
            authority_policy_sha256=_digest("authority"),
        )


def test_governance_decisions_require_independent_records():
    context = _governance_context()
    decisions = list(context["decisions"])
    decisions[1] = replace(
        decisions[1],
        decision_record_sha256=decisions[0].decision_record_sha256,
    )

    with pytest.raises(
        HveeContractError,
        match="distinct decision records",
    ):
        replace(
            context["review_definition"],
            decisions=tuple(decisions),
        )

    decisions = list(context["decisions"])
    decisions[1] = replace(
        decisions[1],
        evidence_review_attestation_sha256=(
            decisions[0].evidence_review_attestation_sha256
        ),
    )

    with pytest.raises(
        HveeContractError,
        match="distinct evidence-review attestations",
    ):
        replace(
            context["review_definition"],
            decisions=tuple(decisions),
        )


def test_governance_decision_must_match_preregistered_reviewer():
    context = _governance_context()
    decisions = list(context["decisions"])
    decisions[0] = replace(
        decisions[0],
        reviewer_key_id="different-governance-reviewer",
    )
    definition = replace(
        context["review_definition"],
        decisions=tuple(decisions),
    )

    with pytest.raises(
        HveeContractError,
        match="does not match preregistration",
    ):
        _build_review(context, definition)


def test_protocol_tampering_is_rejected_even_with_recomputed_digest():
    context = _governance_context()
    payload = copy.deepcopy(context["protocol"].payload)
    payload["preregistration"]["approval_requires_unanimity"] = False

    forged = ASRCriticalNumberGovernanceReviewProtocolBundle(
        payload=payload,
        sha256=calculate_critical_number_governance_review_sha256(payload),
    )

    changed = dict(context)
    changed["protocol"] = forged

    with pytest.raises(
        HveeContractError,
        match="does not match bound readiness evidence",
    ):
        _build_review(changed)


def test_review_tampering_is_rejected_even_with_recomputed_digest():
    context = _governance_context()
    review = _build_review(context)

    payload = copy.deepcopy(review.payload)
    payload["authority"]["production_qualified"] = True

    forged = ASRCriticalNumberGovernanceReviewBundle(
        payload=payload,
        sha256=calculate_critical_number_governance_review_sha256(payload),
    )

    with pytest.raises(
        HveeContractError,
        match="does not match its bound evidence",
    ):
        verify_critical_number_governance_review_v1(
            payload=forged.payload,
            expected_sha256=forged.sha256,
            protocol=context["protocol"],
            protocol_definition=context["protocol_definition"],
            readiness=context["readiness"],
            readiness_evidence=context["readiness_evidence"],
            definition=context["review_definition"],
        )


def test_governance_artifacts_do_not_copy_confidential_evidence():
    context = _governance_context()
    review = _build_review(context)
    serialized = repr(review.payload)

    evidence = context["evidence"]

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
    assert "private reference" not in serialized
    assert "private expected" not in serialized

    assert review.payload["confidentiality"] == {
        "qualification_readiness_payload_in_artifact": False,
        "private_case_content_in_artifact": False,
        "production_case_commitments_in_artifact": False,
        "cross_set_linkage_tokens_in_artifact": False,
        "review_record_contents_in_artifact": False,
        "opaque_commitments_and_dispositions_only": True,
    }


def test_shadow_hypothetical_failure_does_not_bypass_governance_contract():
    context = _governance_context(
        readiness_kind="ready",
        candidate_violation=True,
    )

    assert context["readiness"].payload[
        "evidence"
    ]["matched_release_shadow"]["would_change_official_decision"] is True

    review = _build_review(context)

    assert review.payload["governance_review"]["disposition"] == (
        ASRCriticalNumberGovernanceDisposition
        .APPROVED_FOR_QUALIFICATION_CONSIDERATION.value
    )
    assert review.payload["authority"]["production_qualified"] is False
    assert review.payload["authority"]["release_enforcement_eligible"] is False


def test_governance_reviewer_roster_digest_is_deterministic():
    reviewers = _reviewers()

    assert (
        calculate_critical_number_governance_reviewer_roster_sha256(
            reviewers
        )
        == calculate_critical_number_governance_reviewer_roster_sha256(
            reviewers
        )
    )


def test_governance_public_exports_are_complete():
    expected = {
        "ASRCriticalNumberGovernanceDisposition",
        "ASRCriticalNumberGovernanceReviewBundle",
        "ASRCriticalNumberGovernanceReviewDefinition",
        "ASRCriticalNumberGovernanceReviewer",
        "ASRCriticalNumberGovernanceReviewerDecision",
        "ASRCriticalNumberGovernanceReviewerRole",
        "ASRCriticalNumberGovernanceReviewProtocolBundle",
        "ASRCriticalNumberGovernanceReviewProtocolDefinition",
        "ASRCriticalNumberQualificationReadinessEvidenceContext",
        "CRITICAL_NUMBER_GOVERNANCE_DECISION_RULE_KEY",
        "CRITICAL_NUMBER_GOVERNANCE_DECISION_RULE_VERSION",
        "CRITICAL_NUMBER_GOVERNANCE_REQUIRED_ROLES_V1",
        "CRITICAL_NUMBER_GOVERNANCE_REVIEW_PROTOCOL_KEY",
        "CRITICAL_NUMBER_GOVERNANCE_REVIEW_PROTOCOL_SCHEMA_VERSION",
        "CRITICAL_NUMBER_GOVERNANCE_REVIEW_PROTOCOL_VERSION",
        "CRITICAL_NUMBER_GOVERNANCE_REVIEW_SCHEMA_VERSION",
        "build_critical_number_governance_review_protocol_v1",
        "build_critical_number_governance_review_v1",
        "calculate_critical_number_governance_reviewer_roster_sha256",
        "calculate_critical_number_governance_review_sha256",
        "verify_critical_number_governance_review_protocol_v1",
        "verify_critical_number_governance_review_v1",
    }

    assert expected.issubset(set(asr.__all__))
    assert all(hasattr(asr, name) for name in expected)

from __future__ import annotations

import copy
import hashlib
from dataclasses import FrozenInstanceError

import pytest

import hvee.core.incident_governance_assurance as governance
from hvee.core.contracts import HveeContractError
from hvee.core.incident_governance_assurance import (
    INCIDENT_GOVERNANCE_ASSURANCE_PROTOCOL_SCHEMA_VERSION,
    INCIDENT_GOVERNANCE_ASSURANCE_SCHEMA_VERSION,
    INCIDENT_GOVERNANCE_REQUIRED_ROLES_V1,
    IncidentGovernanceAssuranceDefinition,
    IncidentGovernanceAssuranceProtocolDefinition,
    IncidentGovernanceAssuranceStatus,
    IncidentGovernanceDisposition,
    IncidentGovernanceIntegrationVerificationContext,
    IncidentGovernanceReviewer,
    IncidentGovernanceReviewerDecision,
    IncidentGovernanceReviewerKind,
    IncidentGovernanceReviewerRole,
    build_incident_governance_assurance_bundle,
    build_incident_governance_assurance_protocol_bundle,
    calculate_incident_governance_assurance_protocol_sha256,
    calculate_incident_governance_assurance_sha256,
    calculate_incident_governance_reviewer_roster_sha256,
    verify_incident_governance_assurance_bundle,
    verify_incident_governance_assurance_protocol_bundle,
)
from hvee.core.incident_integration_gate import (
    IncidentIntegrationGateBundle,
    calculate_incident_integration_gate_sha256,
)


def _sha(value: str) -> str:
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def _integration():
    payload = {
        "schema_version": 1,
        "type": "incident_integration_gate",
        "evaluation_type": "asr",
        "incident": {
            "key": "production-asr-incident",
            "version": "1.0.0",
        },
        "integration": {
            "status": "verified_indeterminate",
            "integration_verified": True,
        },
        "evidence_boundary": {
            "model_failure_verified": False,
            "causal_explanation_claimed": False,
            "counterexample_confirmed": False,
            "contract_promoted": False,
            "blocking_release_gate_enabled": False,
            "governance_assurance_completed": False,
            "release_authority_granted": False,
            "qualification_authority": False,
        },
    }

    return IncidentIntegrationGateBundle(
        payload=payload,
        sha256=(
            calculate_incident_integration_gate_sha256(
                payload
            )
        ),
    )


def _verification():
    return IncidentGovernanceIntegrationVerificationContext(
        intake_payload={},
        expected_intake_sha256=_sha("intake"),
        replay_preparation_payload={},
        expected_replay_preparation_sha256=(
            _sha("preparation")
        ),
        environment_manifest_payload={},
        expected_environment_manifest_sha256=(
            _sha("manifest")
        ),
        runner_compatibility_payload={},
        expected_runner_compatibility_sha256=(
            _sha("compatibility")
        ),
        required_capabilities=(
            "asr",
            "incident_replay",
        ),
        compatibility_observation=object(),
        environment_materialization_payload={},
        expected_environment_materialization_sha256=(
            _sha("materialization")
        ),
        controlled_replay_payload={},
        expected_controlled_replay_sha256=(
            _sha("replay")
        ),
        reproduction_evidence_payload={},
        expected_reproduction_evidence_sha256=(
            _sha("reproduction")
        ),
        comparison_observation=object(),
    )


def _reviewer(
    role,
    *,
    key_id=None,
    reviewer_kind=IncidentGovernanceReviewerKind.HUMAN,
):
    if key_id is None:
        key_id = f"{role.value}-001"

    return IncidentGovernanceReviewer(
        role=role,
        key_id=key_id,
        affiliation_key="hetren-reliability",
        reviewer_kind=reviewer_kind,
        qualification_sha256=(
            _sha(f"qualification-{role.value}")
        ),
        authorization_sha256=(
            _sha(f"authorization-{role.value}")
        ),
        independence_attestation_sha256=(
            _sha(f"independence-{role.value}")
        ),
    )


def _reviewers():
    return (
        _reviewer(
            IncidentGovernanceReviewerRole
            .EVALUATION_REVIEWER
        ),
        _reviewer(
            IncidentGovernanceReviewerRole
            .RISK_REVIEWER
        ),
        _reviewer(
            IncidentGovernanceReviewerRole
            .GOVERNANCE_APPROVER,
            reviewer_kind=(
                IncidentGovernanceReviewerKind
                .GOVERNANCE_BODY
            ),
        ),
    )


def _protocol_definition(
    integration,
    *,
    reviewers=None,
):
    return IncidentGovernanceAssuranceProtocolDefinition(
        review_id="incident-governance-review",
        review_version="1.0.0",
        integration_gate_sha256=integration.sha256,
        reviewers=reviewers or _reviewers(),
        review_procedure_sha256=(
            _sha("review-procedure")
        ),
        reviewer_qualification_policy_sha256=(
            _sha("reviewer-qualification-policy")
        ),
        conflict_of_interest_policy_sha256=(
            _sha("conflict-of-interest-policy")
        ),
        authority_policy_sha256=(
            _sha("authority-policy")
        ),
    )


def _decision(
    reviewer,
    integration,
    *,
    disposition=(
        IncidentGovernanceDisposition
        .APPROVED_FOR_ASSURANCE
    ),
):
    return IncidentGovernanceReviewerDecision(
        role=reviewer.role,
        reviewer_key_id=reviewer.key_id,
        integration_gate_sha256=(
            integration.sha256
        ),
        disposition=disposition,
        rationale_code="verified-evidence-review",
        rationale_sha256=(
            _sha(f"rationale-{reviewer.role.value}")
        ),
        decision_record_sha256=(
            _sha(f"decision-{reviewer.role.value}")
        ),
        evidence_review_attestation_sha256=(
            _sha(
                "evidence-review-"
                f"{reviewer.role.value}"
            )
        ),
    )


def _definition(
    protocol,
    protocol_definition,
    integration,
    *,
    dispositions=None,
):
    if dispositions is None:
        dispositions = (
            IncidentGovernanceDisposition
            .APPROVED_FOR_ASSURANCE,
        ) * 3

    decisions = tuple(
        _decision(
            reviewer,
            integration,
            disposition=disposition,
        )
        for reviewer, disposition in zip(
            protocol_definition.reviewers,
            dispositions,
            strict=True,
        )
    )

    return IncidentGovernanceAssuranceDefinition(
        review_id=protocol_definition.review_id,
        review_version=(
            protocol_definition.review_version
        ),
        protocol_sha256=protocol.sha256,
        integration_gate_sha256=integration.sha256,
        review_environment_sha256=(
            _sha("review-environment")
        ),
        independence_attestation_sha256=(
            _sha("review-independence")
        ),
        decisions=decisions,
    )


@pytest.fixture(autouse=True)
def _verified_stage9(monkeypatch):
    monkeypatch.setattr(
        governance,
        "verify_incident_integration_gate_bundle",
        lambda **_: True,
    )


def _context():
    integration = _integration()
    verification = _verification()
    protocol_definition = (
        _protocol_definition(integration)
    )

    protocol = (
        build_incident_governance_assurance_protocol_bundle(
            integration_gate=integration,
            integration_verification=verification,
            definition=protocol_definition,
        )
    )

    definition = _definition(
        protocol,
        protocol_definition,
        integration,
    )

    assurance = (
        build_incident_governance_assurance_bundle(
            protocol=protocol,
            protocol_definition=(
                protocol_definition
            ),
            integration_gate=integration,
            integration_verification=verification,
            definition=definition,
        )
    )

    return {
        "integration": integration,
        "verification": verification,
        "protocol_definition": (
            protocol_definition
        ),
        "protocol": protocol,
        "definition": definition,
        "assurance": assurance,
    }


def test_protocol_schema_and_identity_are_versioned():
    context = _context()
    payload = context["protocol"].payload

    assert payload["schema_version"] == (
        INCIDENT_GOVERNANCE_ASSURANCE_PROTOCOL_SCHEMA_VERSION
    )

    assert payload["type"] == (
        "incident_governance_assurance_protocol"
    )


def test_assurance_schema_and_identity_are_versioned():
    context = _context()
    payload = context["assurance"].payload

    assert payload["schema_version"] == (
        INCIDENT_GOVERNANCE_ASSURANCE_SCHEMA_VERSION
    )

    assert payload["type"] == (
        "incident_governance_assurance"
    )


def test_required_roles_match_existing_governance_shape():
    assert INCIDENT_GOVERNANCE_REQUIRED_ROLES_V1 == (
        IncidentGovernanceReviewerRole
        .EVALUATION_REVIEWER,
        IncidentGovernanceReviewerRole
        .RISK_REVIEWER,
        IncidentGovernanceReviewerRole
        .GOVERNANCE_APPROVER,
    )


def test_protocol_binds_exact_integration_gate():
    context = _context()

    assert context["protocol"].payload[
        "incident"
    ]["integration_gate_sha256"] == (
        context["integration"].sha256
    )


def test_reviewer_roster_requires_unique_keys():
    integration = _integration()

    reviewers = list(_reviewers())

    reviewers[1] = _reviewer(
        IncidentGovernanceReviewerRole
        .RISK_REVIEWER,
        key_id=reviewers[0].key_id,
    )

    with pytest.raises(
        HveeContractError,
        match="keys must be unique",
    ):
        _protocol_definition(
            integration,
            reviewers=tuple(reviewers),
        )


def test_reviewer_roster_requires_canonical_role_order():
    integration = _integration()

    with pytest.raises(
        HveeContractError,
        match="canonical required-role order",
    ):
        _protocol_definition(
            integration,
            reviewers=tuple(
                reversed(_reviewers())
            ),
        )


def test_automated_reviewer_kind_is_not_representable():
    with pytest.raises(
        HveeContractError,
        match="reviewer kind",
    ):
        IncidentGovernanceReviewer(
            role=(
                IncidentGovernanceReviewerRole
                .EVALUATION_REVIEWER
            ),
            key_id="reviewer-001",
            affiliation_key="hetren-reliability",
            reviewer_kind="ai_agent",
            qualification_sha256=_sha("q"),
            authorization_sha256=_sha("a"),
            independence_attestation_sha256=(
                _sha("i")
            ),
        )


def test_governance_body_is_explicitly_supported():
    reviewer = _reviewer(
        IncidentGovernanceReviewerRole
        .GOVERNANCE_APPROVER,
        reviewer_kind=(
            IncidentGovernanceReviewerKind
            .GOVERNANCE_BODY
        ),
    )

    assert reviewer.reviewer_kind == (
        IncidentGovernanceReviewerKind
        .GOVERNANCE_BODY
    )


def test_unanimous_approval_produces_assured_status():
    context = _context()

    assert context["assurance"].payload[
        "review"
    ]["status"] == (
        IncidentGovernanceAssuranceStatus
        .ASSURED.value
    )

    assert context["assurance"].payload[
        "review"
    ]["unanimous_approval"] is True


def test_rejection_dominates_governance_outcome():
    integration = _integration()
    verification = _verification()
    protocol_definition = (
        _protocol_definition(integration)
    )
    protocol = (
        build_incident_governance_assurance_protocol_bundle(
            integration_gate=integration,
            integration_verification=verification,
            definition=protocol_definition,
        )
    )

    definition = _definition(
        protocol,
        protocol_definition,
        integration,
        dispositions=(
            IncidentGovernanceDisposition
            .APPROVED_FOR_ASSURANCE,
            IncidentGovernanceDisposition.REJECTED,
            IncidentGovernanceDisposition
            .APPROVED_FOR_ASSURANCE,
        ),
    )

    bundle = (
        build_incident_governance_assurance_bundle(
            protocol=protocol,
            protocol_definition=(
                protocol_definition
            ),
            integration_gate=integration,
            integration_verification=verification,
            definition=definition,
        )
    )

    assert bundle.payload[
        "review"
    ]["status"] == "rejected"

    assert bundle.payload[
        "evidence_boundary"
    ]["governance_assurance_completed"] is False


def test_more_evidence_conservatively_escalates():
    integration = _integration()
    verification = _verification()
    protocol_definition = (
        _protocol_definition(integration)
    )
    protocol = (
        build_incident_governance_assurance_protocol_bundle(
            integration_gate=integration,
            integration_verification=verification,
            definition=protocol_definition,
        )
    )

    definition = _definition(
        protocol,
        protocol_definition,
        integration,
        dispositions=(
            IncidentGovernanceDisposition
            .APPROVED_FOR_ASSURANCE,
            IncidentGovernanceDisposition
            .MORE_EVIDENCE_REQUIRED,
            IncidentGovernanceDisposition
            .APPROVED_FOR_ASSURANCE,
        ),
    )

    bundle = (
        build_incident_governance_assurance_bundle(
            protocol=protocol,
            protocol_definition=(
                protocol_definition
            ),
            integration_gate=integration,
            integration_verification=verification,
            definition=definition,
        )
    )

    assert bundle.payload[
        "review"
    ]["status"] == (
        "more_evidence_required"
    )

    assert bundle.payload[
        "evidence_boundary"
    ]["governance_assurance_completed"] is False


def test_decisions_must_match_preregistered_reviewers():
    context = _context()

    decisions = list(
        context["definition"].decisions
    )

    first = decisions[0]

    decisions[0] = (
        IncidentGovernanceReviewerDecision(
            role=first.role,
            reviewer_key_id="another-reviewer",
            integration_gate_sha256=(
                first.integration_gate_sha256
            ),
            disposition=first.disposition,
            rationale_code=first.rationale_code,
            rationale_sha256=first.rationale_sha256,
            decision_record_sha256=(
                first.decision_record_sha256
            ),
            evidence_review_attestation_sha256=(
                first
                .evidence_review_attestation_sha256
            ),
        )
    )

    definition = (
        IncidentGovernanceAssuranceDefinition(
            review_id=(
                context["definition"].review_id
            ),
            review_version=(
                context["definition"].review_version
            ),
            protocol_sha256=(
                context["definition"].protocol_sha256
            ),
            integration_gate_sha256=(
                context["definition"]
                .integration_gate_sha256
            ),
            review_environment_sha256=(
                context["definition"]
                .review_environment_sha256
            ),
            independence_attestation_sha256=(
                context["definition"]
                .independence_attestation_sha256
            ),
            decisions=tuple(decisions),
        )
    )

    with pytest.raises(
        HveeContractError,
        match="preregistered reviewer",
    ):
        build_incident_governance_assurance_bundle(
            protocol=context["protocol"],
            protocol_definition=(
                context["protocol_definition"]
            ),
            integration_gate=(
                context["integration"]
            ),
            integration_verification=(
                context["verification"]
            ),
            definition=definition,
        )


def test_decisions_must_bind_integration_gate():
    context = _context()

    decisions = list(
        context["definition"].decisions
    )

    first = decisions[0]

    decisions[0] = (
        IncidentGovernanceReviewerDecision(
            role=first.role,
            reviewer_key_id=(
                first.reviewer_key_id
            ),
            integration_gate_sha256=(
                _sha("different-integration")
            ),
            disposition=first.disposition,
            rationale_code=first.rationale_code,
            rationale_sha256=first.rationale_sha256,
            decision_record_sha256=(
                first.decision_record_sha256
            ),
            evidence_review_attestation_sha256=(
                first
                .evidence_review_attestation_sha256
            ),
        )
    )

    definition = (
        IncidentGovernanceAssuranceDefinition(
            review_id=(
                context["definition"].review_id
            ),
            review_version=(
                context["definition"].review_version
            ),
            protocol_sha256=(
                context["definition"].protocol_sha256
            ),
            integration_gate_sha256=(
                context["definition"]
                .integration_gate_sha256
            ),
            review_environment_sha256=(
                context["definition"]
                .review_environment_sha256
            ),
            independence_attestation_sha256=(
                context["definition"]
                .independence_attestation_sha256
            ),
            decisions=tuple(decisions),
        )
    )

    with pytest.raises(
        HveeContractError,
        match="bind the integration gate",
    ):
        build_incident_governance_assurance_bundle(
            protocol=context["protocol"],
            protocol_definition=(
                context["protocol_definition"]
            ),
            integration_gate=(
                context["integration"]
            ),
            integration_verification=(
                context["verification"]
            ),
            definition=definition,
        )


def test_assurance_never_grants_higher_authority():
    context = _context()

    boundary = context["assurance"].payload[
        "evidence_boundary"
    ]

    assert boundary[
        "governance_assurance_completed"
    ] is True

    assert boundary[
        "model_failure_verified"
    ] is False

    assert boundary[
        "causal_explanation_claimed"
    ] is False

    assert boundary[
        "counterexample_confirmed"
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


def test_protocol_contains_no_raw_incident_content():
    context = _context()

    boundary = context["protocol"].payload[
        "content_boundary"
    ]

    assert all(
        boundary[key] is False
        for key in (
            "integration_gate_payload_embedded",
            "upstream_payloads_embedded",
            "raw_audio_embedded",
            "raw_transcript_embedded",
            "artifact_bytes_embedded",
            "transport_trace_embedded",
            "reviewer_private_material_embedded",
            "policy_contents_embedded",
        )
    )

    assert boundary[
        "opaque_commitments_and_identifiers_only"
    ] is True


def test_protocol_verifier_detects_tampering():
    context = _context()

    tampered = copy.deepcopy(
        context["protocol"].payload
    )

    tampered["review"][
        "review_id"
    ] = "different-review"

    digest = (
        calculate_incident_governance_assurance_protocol_sha256(
            tampered
        )
    )

    assert not (
        verify_incident_governance_assurance_protocol_bundle(
            payload=tampered,
            expected_sha256=digest,
            integration_gate=(
                context["integration"]
            ),
            integration_verification=(
                context["verification"]
            ),
            definition=(
                context["protocol_definition"]
            ),
        )
    )


def test_assurance_verifier_detects_tampering():
    context = _context()

    tampered = copy.deepcopy(
        context["assurance"].payload
    )

    tampered["evidence_boundary"][
        "qualification_authority"
    ] = True

    digest = (
        calculate_incident_governance_assurance_sha256(
            tampered
        )
    )

    assert not (
        verify_incident_governance_assurance_bundle(
            payload=tampered,
            expected_sha256=digest,
            protocol=context["protocol"],
            protocol_definition=(
                context["protocol_definition"]
            ),
            integration_gate=(
                context["integration"]
            ),
            integration_verification=(
                context["verification"]
            ),
            definition=context["definition"],
        )
    )


def test_reviewer_roster_digest_is_deterministic():
    reviewers = _reviewers()

    assert (
        calculate_incident_governance_reviewer_roster_sha256(
            reviewers
        )
        == calculate_incident_governance_reviewer_roster_sha256(
            reviewers
        )
    )


def test_reviewer_and_decision_are_frozen():
    reviewer = _reviewers()[0]

    with pytest.raises(
        FrozenInstanceError
    ):
        reviewer.key_id = "changed"

    integration = _integration()

    decision = _decision(
        reviewer,
        integration,
    )

    with pytest.raises(
        FrozenInstanceError
    ):
        decision.reviewer_key_id = "changed"

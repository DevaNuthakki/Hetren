"""Governance and evaluator assurance for verified Incident Mode evidence.

This stage consumes a verified final Incident Mode integration gate and
records a policy-bound governance review by independently authorized
reviewers.

Governance assurance means that the technical evidence was reviewed under
the registered governance procedure. It does not prove model failure,
establish causality, promote a contract, enable a release gate, grant
release authority, or grant qualification authority.

Production qualification remains a later and independently authorized
stage.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum

from hvee.core.contracts import HveeContractError
from hvee.core.incident_integration_gate import (
    IncidentIntegrationGateBundle,
    verify_incident_integration_gate_bundle,
)


INCIDENT_GOVERNANCE_ASSURANCE_PROTOCOL_SCHEMA_VERSION = 1
INCIDENT_GOVERNANCE_ASSURANCE_SCHEMA_VERSION = 1

INCIDENT_GOVERNANCE_ASSURANCE_PROTOCOL_KEY = (
    "hetren.incident-governance-assurance"
)
INCIDENT_GOVERNANCE_ASSURANCE_PROTOCOL_VERSION = "1.0.0"

INCIDENT_GOVERNANCE_DECISION_RULE_KEY = (
    "unanimous-approval-conservative-escalation"
)
INCIDENT_GOVERNANCE_DECISION_RULE_VERSION = "1.0.0"


_KEY_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9._-]*$"
)


class IncidentGovernanceReviewerRole(StrEnum):
    """Required independent review responsibilities."""

    EVALUATION_REVIEWER = "evaluation_reviewer"
    RISK_REVIEWER = "risk_reviewer"
    GOVERNANCE_APPROVER = "governance_approver"


INCIDENT_GOVERNANCE_REQUIRED_ROLES_V1 = tuple(
    IncidentGovernanceReviewerRole
)


class IncidentGovernanceReviewerKind(StrEnum):
    """Authorized reviewer classes.

    Automated agents are intentionally not a reviewer kind.
    """

    HUMAN = "human"
    GOVERNANCE_BODY = "governance_body"


class IncidentGovernanceDisposition(StrEnum):
    """One reviewer's governance disposition."""

    REJECTED = "rejected"
    MORE_EVIDENCE_REQUIRED = "more_evidence_required"
    APPROVED_FOR_ASSURANCE = "approved_for_assurance"


class IncidentGovernanceAssuranceStatus(StrEnum):
    """Aggregate Stage-10 governance outcome."""

    ASSURED = "assured"
    REJECTED = "rejected"
    MORE_EVIDENCE_REQUIRED = "more_evidence_required"


_CONTENT_BOUNDARY = {
    "integration_gate_payload_embedded": False,
    "upstream_payloads_embedded": False,
    "raw_audio_embedded": False,
    "raw_transcript_embedded": False,
    "artifact_bytes_embedded": False,
    "transport_trace_embedded": False,
    "reviewer_private_material_embedded": False,
    "policy_contents_embedded": False,
    "opaque_commitments_and_identifiers_only": True,
}


_POLICY = {
    "technical_integration_must_be_verified": True,
    "all_required_governance_roles_must_review": True,
    "reviewer_keys_must_be_unique": True,
    "reviewer_authorization_must_be_committed": True,
    "reviewer_qualification_must_be_committed": True,
    "reviewer_independence_must_be_attested": True,
    "automated_reviewer_authority_allowed": False,
    "unanimous_approval_required_for_assurance": True,
    "rejection_dominates": True,
    "more_evidence_requires_escalation": True,
    "governance_assurance_is_not_reproduction": True,
    "governance_assurance_is_not_model_failure_proof": True,
    "governance_assurance_is_not_causal_proof": True,
    "governance_assurance_does_not_promote_contracts": True,
    "governance_assurance_does_not_enable_release_gates": True,
    "governance_assurance_does_not_grant_release_authority": True,
    "governance_assurance_does_not_grant_qualification_authority": True,
    "qualification_authority_requires_separate_stage": True,
    "qualification_authority_must_be_independent": True,
    "model_or_replay_execution_permitted": False,
}


def _require_text(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
    ):
        raise HveeContractError(
            f"{name} must be canonical non-empty text"
        )

    return value


def _require_key(
    *,
    name: str,
    value: object,
) -> str:
    normalized = _require_text(
        name=name,
        value=value,
    )

    if _KEY_PATTERN.fullmatch(normalized) is None:
        raise HveeContractError(
            f"{name} must be a canonical identifier"
        )

    return normalized


def _require_sha256(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(
            character not in "0123456789abcdef"
            for character in value
        )
    ):
        raise HveeContractError(
            f"{name} must be a lowercase SHA-256 hex digest"
        )

    return value


def _canonical_json(
    value: object,
    *,
    name: str,
) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise HveeContractError(
            f"{name} must be deterministic JSON"
        ) from exc


def _canonical_json_value(
    value: object,
    *,
    name: str,
) -> object:
    return json.loads(
        _canonical_json(
            value,
            name=name,
        )
    )


def _calculate_sha256(
    value: object,
    *,
    name: str,
) -> str:
    canonical = _canonical_json(
        value,
        name=name,
    )

    return hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class IncidentGovernanceReviewer:
    """One preregistered governance reviewer."""

    role: IncidentGovernanceReviewerRole
    key_id: str
    affiliation_key: str
    reviewer_kind: IncidentGovernanceReviewerKind
    qualification_sha256: str
    authorization_sha256: str
    independence_attestation_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.role,
            IncidentGovernanceReviewerRole,
        ):
            raise HveeContractError(
                "incident governance reviewer role "
                "must be canonical"
            )

        if not isinstance(
            self.reviewer_kind,
            IncidentGovernanceReviewerKind,
        ):
            raise HveeContractError(
                "incident governance reviewer kind "
                "must be canonical"
            )

        _require_key(
            name="incident governance reviewer key id",
            value=self.key_id,
        )

        _require_key(
            name="incident governance reviewer affiliation",
            value=self.affiliation_key,
        )

        for name, value in (
            (
                "qualification",
                self.qualification_sha256,
            ),
            (
                "authorization",
                self.authorization_sha256,
            ),
            (
                "independence attestation",
                self.independence_attestation_sha256,
            ),
        ):
            _require_sha256(
                name=(
                    "incident governance reviewer "
                    f"{name}"
                ),
                value=value,
            )


@dataclass(frozen=True, slots=True)
class IncidentGovernanceReviewerDecision:
    """One policy-bound reviewer decision."""

    role: IncidentGovernanceReviewerRole
    reviewer_key_id: str
    integration_gate_sha256: str
    disposition: IncidentGovernanceDisposition
    rationale_code: str
    rationale_sha256: str
    decision_record_sha256: str
    evidence_review_attestation_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.role,
            IncidentGovernanceReviewerRole,
        ):
            raise HveeContractError(
                "incident governance decision role "
                "must be canonical"
            )

        if not isinstance(
            self.disposition,
            IncidentGovernanceDisposition,
        ):
            raise HveeContractError(
                "incident governance disposition "
                "must be canonical"
            )

        _require_key(
            name="incident governance decision reviewer key",
            value=self.reviewer_key_id,
        )

        _require_sha256(
            name="incident governance integration gate",
            value=self.integration_gate_sha256,
        )

        _require_key(
            name="incident governance rationale code",
            value=self.rationale_code,
        )

        for name, value in (
            ("rationale", self.rationale_sha256),
            (
                "decision record",
                self.decision_record_sha256,
            ),
            (
                "evidence review attestation",
                self.evidence_review_attestation_sha256,
            ),
        ):
            _require_sha256(
                name=f"incident governance {name}",
                value=value,
            )


@dataclass(frozen=True, slots=True)
class IncidentGovernanceAssuranceProtocolDefinition:
    """Preregistered Stage-10 review procedure."""

    review_id: str
    review_version: str
    integration_gate_sha256: str
    reviewers: tuple[IncidentGovernanceReviewer, ...]
    review_procedure_sha256: str
    reviewer_qualification_policy_sha256: str
    conflict_of_interest_policy_sha256: str
    authority_policy_sha256: str

    def __post_init__(self) -> None:
        _require_key(
            name="incident governance review id",
            value=self.review_id,
        )

        _require_text(
            name="incident governance review version",
            value=self.review_version,
        )

        _require_sha256(
            name="incident governance integration gate",
            value=self.integration_gate_sha256,
        )

        if not isinstance(
            self.reviewers,
            tuple,
        ):
            raise HveeContractError(
                "incident governance reviewers "
                "must be a tuple"
            )

        _validate_reviewer_roster(
            self.reviewers
        )

        for name, value in (
            (
                "review procedure",
                self.review_procedure_sha256,
            ),
            (
                "reviewer qualification policy",
                self.reviewer_qualification_policy_sha256,
            ),
            (
                "conflict of interest policy",
                self.conflict_of_interest_policy_sha256,
            ),
            (
                "authority policy",
                self.authority_policy_sha256,
            ),
        ):
            _require_sha256(
                name=f"incident governance {name}",
                value=value,
            )


@dataclass(frozen=True, slots=True)
class IncidentGovernanceAssuranceDefinition:
    """Completed governance review definition."""

    review_id: str
    review_version: str
    protocol_sha256: str
    integration_gate_sha256: str
    review_environment_sha256: str
    independence_attestation_sha256: str
    decisions: tuple[
        IncidentGovernanceReviewerDecision,
        ...
    ]

    def __post_init__(self) -> None:
        _require_key(
            name="incident governance review id",
            value=self.review_id,
        )

        _require_text(
            name="incident governance review version",
            value=self.review_version,
        )

        for name, value in (
            ("protocol", self.protocol_sha256),
            (
                "integration gate",
                self.integration_gate_sha256,
            ),
            (
                "review environment",
                self.review_environment_sha256,
            ),
            (
                "review independence attestation",
                self.independence_attestation_sha256,
            ),
        ):
            _require_sha256(
                name=f"incident governance {name}",
                value=value,
            )

        if not isinstance(
            self.decisions,
            tuple,
        ):
            raise HveeContractError(
                "incident governance decisions "
                "must be a tuple"
            )


@dataclass(frozen=True, slots=True)
class IncidentGovernanceIntegrationVerificationContext:
    """Inputs needed to reconstruct the Stage-9 technical gate."""

    intake_payload: object
    expected_intake_sha256: object

    replay_preparation_payload: object
    expected_replay_preparation_sha256: object

    environment_manifest_payload: object
    expected_environment_manifest_sha256: object

    runner_compatibility_payload: object
    expected_runner_compatibility_sha256: object

    required_capabilities: object
    compatibility_observation: object

    environment_materialization_payload: object
    expected_environment_materialization_sha256: object

    controlled_replay_payload: object
    expected_controlled_replay_sha256: object

    reproduction_evidence_payload: object
    expected_reproduction_evidence_sha256: object

    comparison_observation: object


@dataclass(frozen=True, slots=True)
class IncidentGovernanceAssuranceProtocolBundle:
    payload: dict[str, object]
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.payload,
            dict,
        ):
            raise HveeContractError(
                "incident governance protocol payload "
                "must be a JSON object"
            )

        _require_sha256(
            name="incident governance protocol SHA-256",
            value=self.sha256,
        )


@dataclass(frozen=True, slots=True)
class IncidentGovernanceAssuranceBundle:
    payload: dict[str, object]
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.payload,
            dict,
        ):
            raise HveeContractError(
                "incident governance assurance payload "
                "must be a JSON object"
            )

        _require_sha256(
            name="incident governance assurance SHA-256",
            value=self.sha256,
        )


def _reviewer_snapshot(
    reviewer: IncidentGovernanceReviewer,
) -> dict[str, object]:
    return {
        "role": reviewer.role.value,
        "key_id": reviewer.key_id,
        "affiliation_key": reviewer.affiliation_key,
        "kind": reviewer.reviewer_kind.value,
        "qualification_sha256": (
            reviewer.qualification_sha256
        ),
        "authorization_sha256": (
            reviewer.authorization_sha256
        ),
        "independence_attestation_sha256": (
            reviewer.independence_attestation_sha256
        ),
    }


def _decision_snapshot(
    decision: IncidentGovernanceReviewerDecision,
) -> dict[str, object]:
    return {
        "role": decision.role.value,
        "reviewer_key_id": (
            decision.reviewer_key_id
        ),
        "integration_gate_sha256": (
            decision.integration_gate_sha256
        ),
        "disposition": decision.disposition.value,
        "rationale_code": decision.rationale_code,
        "rationale_sha256": (
            decision.rationale_sha256
        ),
        "decision_record_sha256": (
            decision.decision_record_sha256
        ),
        "evidence_review_attestation_sha256": (
            decision.evidence_review_attestation_sha256
        ),
    }


def _validate_reviewer_roster(
    reviewers: tuple[
        IncidentGovernanceReviewer,
        ...
    ],
) -> None:
    if len(reviewers) != len(
        INCIDENT_GOVERNANCE_REQUIRED_ROLES_V1
    ):
        raise HveeContractError(
            "incident governance reviewer roster "
            "must contain every required role exactly once"
        )

    roles = tuple(
        reviewer.role
        for reviewer in reviewers
    )

    if roles != (
        INCIDENT_GOVERNANCE_REQUIRED_ROLES_V1
    ):
        raise HveeContractError(
            "incident governance reviewer roster "
            "must use canonical required-role order"
        )

    keys = tuple(
        reviewer.key_id
        for reviewer in reviewers
    )

    if len(keys) != len(set(keys)):
        raise HveeContractError(
            "incident governance reviewer keys "
            "must be unique"
        )


def calculate_incident_governance_reviewer_roster_sha256(
    reviewers: tuple[
        IncidentGovernanceReviewer,
        ...
    ],
) -> str:
    _validate_reviewer_roster(
        reviewers
    )

    return _calculate_sha256(
        [
            _reviewer_snapshot(reviewer)
            for reviewer in reviewers
        ],
        name="incident governance reviewer roster",
    )


def calculate_incident_governance_assurance_protocol_sha256(
    payload: object,
) -> str:
    return _calculate_sha256(
        payload,
        name="incident governance assurance protocol",
    )


def calculate_incident_governance_assurance_sha256(
    payload: object,
) -> str:
    return _calculate_sha256(
        payload,
        name="incident governance assurance",
    )


def _verify_integration_gate(
    *,
    integration_gate: IncidentIntegrationGateBundle,
    verification: (
        IncidentGovernanceIntegrationVerificationContext
    ),
) -> None:
    if not isinstance(
        integration_gate,
        IncidentIntegrationGateBundle,
    ):
        raise HveeContractError(
            "incident governance requires a canonical "
            "integration gate bundle"
        )

    if not isinstance(
        verification,
        IncidentGovernanceIntegrationVerificationContext,
    ):
        raise HveeContractError(
            "incident governance requires canonical "
            "integration verification context"
        )

    verified = verify_incident_integration_gate_bundle(
        payload=integration_gate.payload,
        expected_sha256=integration_gate.sha256,
        intake_payload=verification.intake_payload,
        expected_intake_sha256=(
            verification.expected_intake_sha256
        ),
        replay_preparation_payload=(
            verification.replay_preparation_payload
        ),
        expected_replay_preparation_sha256=(
            verification.expected_replay_preparation_sha256
        ),
        environment_manifest_payload=(
            verification.environment_manifest_payload
        ),
        expected_environment_manifest_sha256=(
            verification.expected_environment_manifest_sha256
        ),
        runner_compatibility_payload=(
            verification.runner_compatibility_payload
        ),
        expected_runner_compatibility_sha256=(
            verification.expected_runner_compatibility_sha256
        ),
        required_capabilities=(
            verification.required_capabilities
        ),
        compatibility_observation=(
            verification.compatibility_observation
        ),
        environment_materialization_payload=(
            verification.environment_materialization_payload
        ),
        expected_environment_materialization_sha256=(
            verification.expected_environment_materialization_sha256
        ),
        controlled_replay_payload=(
            verification.controlled_replay_payload
        ),
        expected_controlled_replay_sha256=(
            verification.expected_controlled_replay_sha256
        ),
        reproduction_evidence_payload=(
            verification.reproduction_evidence_payload
        ),
        expected_reproduction_evidence_sha256=(
            verification.expected_reproduction_evidence_sha256
        ),
        comparison_observation=(
            verification.comparison_observation
        ),
    )

    if verified is not True:
        raise HveeContractError(
            "incident governance integration gate "
            "failed verification"
        )

    integration = integration_gate.payload.get(
        "integration"
    )

    evidence_boundary = integration_gate.payload.get(
        "evidence_boundary"
    )

    if (
        not isinstance(integration, dict)
        or integration.get(
            "integration_verified"
        )
        is not True
    ):
        raise HveeContractError(
            "incident governance requires a verified "
            "technical integration gate"
        )

    if not isinstance(
        evidence_boundary,
        dict,
    ):
        raise HveeContractError(
            "incident governance requires the "
            "integration evidence boundary"
        )

    required_false = (
        "model_failure_verified",
        "causal_explanation_claimed",
        "counterexample_confirmed",
        "contract_promoted",
        "blocking_release_gate_enabled",
        "governance_assurance_completed",
        "release_authority_granted",
        "qualification_authority",
    )

    if any(
        evidence_boundary.get(key) is not False
        for key in required_false
    ):
        raise HveeContractError(
            "incident governance requires an "
            "authority-clean integration gate"
        )


def _incident_identity(
    integration_gate: IncidentIntegrationGateBundle,
) -> tuple[str, str, str]:
    incident = integration_gate.payload.get(
        "incident"
    )

    evaluation_type = _require_text(
        name="incident governance evaluation type",
        value=integration_gate.payload.get(
            "evaluation_type"
        ),
    )

    if not isinstance(
        incident,
        dict,
    ):
        raise HveeContractError(
            "incident governance incident identity "
            "is invalid"
        )

    key = _require_key(
        name="incident governance incident key",
        value=incident.get("key"),
    )

    version = _require_text(
        name="incident governance incident version",
        value=incident.get("version"),
    )

    return (
        evaluation_type,
        key,
        version,
    )


def _aggregate_status(
    decisions: tuple[
        IncidentGovernanceReviewerDecision,
        ...
    ],
) -> IncidentGovernanceAssuranceStatus:
    dispositions = {
        decision.disposition
        for decision in decisions
    }

    if (
        IncidentGovernanceDisposition.REJECTED
        in dispositions
    ):
        return (
            IncidentGovernanceAssuranceStatus.REJECTED
        )

    if (
        IncidentGovernanceDisposition
        .MORE_EVIDENCE_REQUIRED
        in dispositions
    ):
        return (
            IncidentGovernanceAssuranceStatus
            .MORE_EVIDENCE_REQUIRED
        )

    if dispositions == {
        IncidentGovernanceDisposition
        .APPROVED_FOR_ASSURANCE
    }:
        return (
            IncidentGovernanceAssuranceStatus.ASSURED
        )

    raise HveeContractError(
        "incident governance decisions cannot be "
        "aggregated"
    )


def build_incident_governance_assurance_protocol_bundle(
    *,
    integration_gate: IncidentIntegrationGateBundle,
    integration_verification: (
        IncidentGovernanceIntegrationVerificationContext
    ),
    definition: (
        IncidentGovernanceAssuranceProtocolDefinition
    ),
) -> IncidentGovernanceAssuranceProtocolBundle:
    if not isinstance(
        definition,
        IncidentGovernanceAssuranceProtocolDefinition,
    ):
        raise HveeContractError(
            "incident governance protocol requires "
            "a canonical definition"
        )

    _verify_integration_gate(
        integration_gate=integration_gate,
        verification=integration_verification,
    )

    if (
        definition.integration_gate_sha256
        != integration_gate.sha256
    ):
        raise HveeContractError(
            "incident governance protocol does not "
            "bind the supplied integration gate"
        )

    (
        evaluation_type,
        incident_key,
        incident_version,
    ) = _incident_identity(
        integration_gate
    )

    roster_sha256 = (
        calculate_incident_governance_reviewer_roster_sha256(
            definition.reviewers
        )
    )

    payload: dict[str, object] = {
        "schema_version": (
            INCIDENT_GOVERNANCE_ASSURANCE_PROTOCOL_SCHEMA_VERSION
        ),
        "type": (
            "incident_governance_assurance_protocol"
        ),
        "protocol": {
            "key": (
                INCIDENT_GOVERNANCE_ASSURANCE_PROTOCOL_KEY
            ),
            "version": (
                INCIDENT_GOVERNANCE_ASSURANCE_PROTOCOL_VERSION
            ),
        },
        "evaluation_type": evaluation_type,
        "incident": {
            "key": incident_key,
            "version": incident_version,
            "integration_gate_sha256": (
                integration_gate.sha256
            ),
        },
        "review": {
            "review_id": definition.review_id,
            "review_version": (
                definition.review_version
            ),
            "decision_rule": {
                "key": (
                    INCIDENT_GOVERNANCE_DECISION_RULE_KEY
                ),
                "version": (
                    INCIDENT_GOVERNANCE_DECISION_RULE_VERSION
                ),
            },
            "required_roles": [
                role.value
                for role
                in INCIDENT_GOVERNANCE_REQUIRED_ROLES_V1
            ],
            "reviewer_roster_sha256": (
                roster_sha256
            ),
            "review_procedure_sha256": (
                definition.review_procedure_sha256
            ),
            "reviewer_qualification_policy_sha256": (
                definition
                .reviewer_qualification_policy_sha256
            ),
            "conflict_of_interest_policy_sha256": (
                definition
                .conflict_of_interest_policy_sha256
            ),
            "authority_policy_sha256": (
                definition.authority_policy_sha256
            ),
        },
        "reviewers": [
            _reviewer_snapshot(reviewer)
            for reviewer in definition.reviewers
        ],
        "policy": dict(_POLICY),
        "content_boundary": dict(
            _CONTENT_BOUNDARY
        ),
        "authority_boundary": {
            "governance_assurance_completed": False,
            "release_authority_granted": False,
            "qualification_authority": False,
            "contract_promoted": False,
            "blocking_release_gate_enabled": False,
        },
    }

    canonical = _canonical_json_value(
        payload,
        name="incident governance assurance protocol",
    )

    if not isinstance(
        canonical,
        dict,
    ):
        raise HveeContractError(
            "incident governance assurance protocol "
            "must be a JSON object"
        )

    return IncidentGovernanceAssuranceProtocolBundle(
        payload=canonical,
        sha256=(
            calculate_incident_governance_assurance_protocol_sha256(
                canonical
            )
        ),
    )


def verify_incident_governance_assurance_protocol_bundle(
    *,
    payload: object,
    expected_sha256: object,
    integration_gate: IncidentIntegrationGateBundle,
    integration_verification: (
        IncidentGovernanceIntegrationVerificationContext
    ),
    definition: (
        IncidentGovernanceAssuranceProtocolDefinition
    ),
) -> bool:
    try:
        expected = _require_sha256(
            name="expected incident governance protocol SHA-256",
            value=expected_sha256,
        )

        if not isinstance(
            payload,
            dict,
        ):
            return False

        if (
            calculate_incident_governance_assurance_protocol_sha256(
                payload
            )
            != expected
        ):
            return False

        rebuilt = (
            build_incident_governance_assurance_protocol_bundle(
                integration_gate=integration_gate,
                integration_verification=(
                    integration_verification
                ),
                definition=definition,
            )
        )

        return (
            rebuilt.payload == payload
            and rebuilt.sha256 == expected
        )
    except (
        HveeContractError,
        TypeError,
        ValueError,
    ):
        return False


def _validate_decisions(
    *,
    decisions: tuple[
        IncidentGovernanceReviewerDecision,
        ...
    ],
    reviewers: tuple[
        IncidentGovernanceReviewer,
        ...
    ],
    integration_gate_sha256: str,
) -> None:
    if len(decisions) != len(reviewers):
        raise HveeContractError(
            "incident governance requires one decision "
            "from every preregistered reviewer"
        )

    for reviewer, decision in zip(
        reviewers,
        decisions,
        strict=True,
    ):
        if (
            decision.role != reviewer.role
            or decision.reviewer_key_id
            != reviewer.key_id
        ):
            raise HveeContractError(
                "incident governance decision does not "
                "match preregistered reviewer"
            )

        if (
            decision.integration_gate_sha256
            != integration_gate_sha256
        ):
            raise HveeContractError(
                "incident governance decision does not "
                "bind the integration gate"
            )


def build_incident_governance_assurance_bundle(
    *,
    protocol: (
        IncidentGovernanceAssuranceProtocolBundle
    ),
    protocol_definition: (
        IncidentGovernanceAssuranceProtocolDefinition
    ),
    integration_gate: IncidentIntegrationGateBundle,
    integration_verification: (
        IncidentGovernanceIntegrationVerificationContext
    ),
    definition: IncidentGovernanceAssuranceDefinition,
) -> IncidentGovernanceAssuranceBundle:
    if not isinstance(
        protocol,
        IncidentGovernanceAssuranceProtocolBundle,
    ):
        raise HveeContractError(
            "incident governance assurance requires "
            "a canonical protocol bundle"
        )

    if not isinstance(
        definition,
        IncidentGovernanceAssuranceDefinition,
    ):
        raise HveeContractError(
            "incident governance assurance requires "
            "a canonical review definition"
        )

    if not (
        verify_incident_governance_assurance_protocol_bundle(
            payload=protocol.payload,
            expected_sha256=protocol.sha256,
            integration_gate=integration_gate,
            integration_verification=(
                integration_verification
            ),
            definition=protocol_definition,
        )
    ):
        raise HveeContractError(
            "incident governance assurance protocol "
            "failed verification"
        )

    _verify_integration_gate(
        integration_gate=integration_gate,
        verification=integration_verification,
    )

    if (
        definition.review_id
        != protocol_definition.review_id
        or definition.review_version
        != protocol_definition.review_version
    ):
        raise HveeContractError(
            "incident governance review identity "
            "does not match protocol"
        )

    if definition.protocol_sha256 != protocol.sha256:
        raise HveeContractError(
            "incident governance review does not bind "
            "the protocol"
        )

    if (
        definition.integration_gate_sha256
        != integration_gate.sha256
    ):
        raise HveeContractError(
            "incident governance review does not bind "
            "the integration gate"
        )

    _validate_decisions(
        decisions=definition.decisions,
        reviewers=protocol_definition.reviewers,
        integration_gate_sha256=(
            integration_gate.sha256
        ),
    )

    status = _aggregate_status(
        definition.decisions
    )

    (
        evaluation_type,
        incident_key,
        incident_version,
    ) = _incident_identity(
        integration_gate
    )

    roster_sha256 = (
        calculate_incident_governance_reviewer_roster_sha256(
            protocol_definition.reviewers
        )
    )

    assured = (
        status
        is IncidentGovernanceAssuranceStatus.ASSURED
    )

    payload: dict[str, object] = {
        "schema_version": (
            INCIDENT_GOVERNANCE_ASSURANCE_SCHEMA_VERSION
        ),
        "type": "incident_governance_assurance",
        "evaluation_type": evaluation_type,
        "incident": {
            "key": incident_key,
            "version": incident_version,
            "integration_gate_sha256": (
                integration_gate.sha256
            ),
        },
        "bindings": {
            "protocol_sha256": protocol.sha256,
            "reviewer_roster_sha256": (
                roster_sha256
            ),
            "review_procedure_sha256": (
                protocol_definition
                .review_procedure_sha256
            ),
            "reviewer_qualification_policy_sha256": (
                protocol_definition
                .reviewer_qualification_policy_sha256
            ),
            "conflict_of_interest_policy_sha256": (
                protocol_definition
                .conflict_of_interest_policy_sha256
            ),
            "authority_policy_sha256": (
                protocol_definition
                .authority_policy_sha256
            ),
        },
        "review": {
            "review_id": definition.review_id,
            "review_version": (
                definition.review_version
            ),
            "status": status.value,
            "decision_rule": {
                "key": (
                    INCIDENT_GOVERNANCE_DECISION_RULE_KEY
                ),
                "version": (
                    INCIDENT_GOVERNANCE_DECISION_RULE_VERSION
                ),
            },
            "all_required_reviewers_decided": True,
            "unanimous_approval": assured,
            "review_environment_sha256": (
                definition.review_environment_sha256
            ),
            "independence_attestation_sha256": (
                definition
                .independence_attestation_sha256
            ),
        },
        "decisions": [
            _decision_snapshot(decision)
            for decision in definition.decisions
        ],
        "sealed_evidence": {
            "integration_gate_sha256": (
                integration_gate.sha256
            ),
            "integration_gate_reverified": True,
            "protocol_sha256": protocol.sha256,
            "protocol_reverified": True,
            "reviewer_roster_sha256": (
                roster_sha256
            ),
        },
        "policy": dict(_POLICY),
        "content_boundary": dict(
            _CONTENT_BOUNDARY
        ),
        "evidence_boundary": {
            "governance_review_completed": True,
            "technical_integration_reverified": True,
            "review_policy_bound": True,
            "reviewer_roster_bound": True,
            "reviewer_authority_bound": True,
            "reviewer_qualification_bound": True,
            "reviewer_independence_attested": True,
            "governance_assurance_completed": assured,
            "model_failure_verified": False,
            "causal_explanation_claimed": False,
            "counterexample_confirmed": False,
            "contract_promoted": False,
            "blocking_release_gate_enabled": False,
            "release_authority_granted": False,
            "qualification_authority": False,
        },
    }

    canonical = _canonical_json_value(
        payload,
        name="incident governance assurance",
    )

    if not isinstance(
        canonical,
        dict,
    ):
        raise HveeContractError(
            "incident governance assurance "
            "must be a JSON object"
        )

    return IncidentGovernanceAssuranceBundle(
        payload=canonical,
        sha256=(
            calculate_incident_governance_assurance_sha256(
                canonical
            )
        ),
    )


def verify_incident_governance_assurance_bundle(
    *,
    payload: object,
    expected_sha256: object,
    protocol: (
        IncidentGovernanceAssuranceProtocolBundle
    ),
    protocol_definition: (
        IncidentGovernanceAssuranceProtocolDefinition
    ),
    integration_gate: IncidentIntegrationGateBundle,
    integration_verification: (
        IncidentGovernanceIntegrationVerificationContext
    ),
    definition: IncidentGovernanceAssuranceDefinition,
) -> bool:
    try:
        expected = _require_sha256(
            name="expected incident governance assurance SHA-256",
            value=expected_sha256,
        )

        if not isinstance(
            payload,
            dict,
        ):
            return False

        if (
            calculate_incident_governance_assurance_sha256(
                payload
            )
            != expected
        ):
            return False

        rebuilt = (
            build_incident_governance_assurance_bundle(
                protocol=protocol,
                protocol_definition=(
                    protocol_definition
                ),
                integration_gate=integration_gate,
                integration_verification=(
                    integration_verification
                ),
                definition=definition,
            )
        )

        return (
            rebuilt.payload == payload
            and rebuilt.sha256 == expected
        )
    except (
        HveeContractError,
        TypeError,
        ValueError,
    ):
        return False


__all__ = [
    "INCIDENT_GOVERNANCE_ASSURANCE_PROTOCOL_KEY",
    "INCIDENT_GOVERNANCE_ASSURANCE_PROTOCOL_SCHEMA_VERSION",
    "INCIDENT_GOVERNANCE_ASSURANCE_PROTOCOL_VERSION",
    "INCIDENT_GOVERNANCE_ASSURANCE_SCHEMA_VERSION",
    "INCIDENT_GOVERNANCE_DECISION_RULE_KEY",
    "INCIDENT_GOVERNANCE_DECISION_RULE_VERSION",
    "INCIDENT_GOVERNANCE_REQUIRED_ROLES_V1",
    "IncidentGovernanceAssuranceBundle",
    "IncidentGovernanceAssuranceDefinition",
    "IncidentGovernanceAssuranceProtocolBundle",
    "IncidentGovernanceAssuranceProtocolDefinition",
    "IncidentGovernanceAssuranceStatus",
    "IncidentGovernanceDisposition",
    "IncidentGovernanceIntegrationVerificationContext",
    "IncidentGovernanceReviewer",
    "IncidentGovernanceReviewerDecision",
    "IncidentGovernanceReviewerKind",
    "IncidentGovernanceReviewerRole",
    "build_incident_governance_assurance_bundle",
    "build_incident_governance_assurance_protocol_bundle",
    "calculate_incident_governance_assurance_protocol_sha256",
    "calculate_incident_governance_assurance_sha256",
    "calculate_incident_governance_reviewer_roster_sha256",
    "verify_incident_governance_assurance_bundle",
    "verify_incident_governance_assurance_protocol_bundle",
]

"""Independent governance review for Critical Number Fidelity v1.

Governance review consumes only a fully verified qualification-readiness
dossier. It records whether the evidence may advance to qualification
consideration.

Governance approval is not certification, production qualification, release
enforcement eligibility, or permission to modify an official release verdict.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.critical_number_assurance import (
    ASRCriticalNumberAssuranceEvidenceBundle,
)
from hvee.packs.asr.critical_number_private_assessment import (
    ASRCriticalNumberPrivateStatisticalAssessmentBundle,
)
from hvee.packs.asr.critical_number_private_statistics import (
    ASRCriticalNumberPrivateStatisticalMethodManifestBundle,
)
from hvee.packs.asr.critical_number_production_evidence import (
    ASRCriticalNumberPrivateHoldoutExclusionManifestBundle,
    ASRCriticalNumberProductionEvidenceManifestBundle,
)
from hvee.packs.asr.critical_number_qualification_readiness import (
    CRITICAL_NUMBER_QUALIFICATION_READINESS_KEY,
    CRITICAL_NUMBER_QUALIFICATION_READINESS_VERSION,
    ASRCriticalNumberMatchedReleaseShadowVerificationContext,
    ASRCriticalNumberPrivateQualificationVerificationContext,
    ASRCriticalNumberProductionEvidenceVerificationContext,
    ASRCriticalNumberQualificationReadinessBundle,
    ASRCriticalNumberQualificationReadinessResult,
    verify_critical_number_qualification_readiness_v1,
)
from hvee.packs.asr.critical_number_release_shadow import (
    ASRCriticalNumberMatchedReleaseShadowResult,
)


CRITICAL_NUMBER_GOVERNANCE_REVIEW_PROTOCOL_SCHEMA_VERSION = 1
CRITICAL_NUMBER_GOVERNANCE_REVIEW_SCHEMA_VERSION = 1
CRITICAL_NUMBER_GOVERNANCE_REVIEW_PROTOCOL_KEY = (
    "hetren.asr.critical-number-governance-review.en-us"
)
CRITICAL_NUMBER_GOVERNANCE_REVIEW_PROTOCOL_VERSION = "1.0.0"

CRITICAL_NUMBER_GOVERNANCE_DECISION_RULE_KEY = (
    "unanimous-approval-conservative-escalation"
)
CRITICAL_NUMBER_GOVERNANCE_DECISION_RULE_VERSION = "1.0.0"


class ASRCriticalNumberGovernanceReviewerRole(StrEnum):
    """Required independent governance responsibilities."""

    EVALUATION_REVIEWER = "evaluation_reviewer"
    RISK_REVIEWER = "risk_reviewer"
    GOVERNANCE_APPROVER = "governance_approver"


CRITICAL_NUMBER_GOVERNANCE_REQUIRED_ROLES_V1 = tuple(
    ASRCriticalNumberGovernanceReviewerRole
)


class ASRCriticalNumberGovernanceDisposition(StrEnum):
    """Allowed governance-review dispositions."""

    REJECTED = "rejected"
    MORE_EVIDENCE_REQUIRED = "more_evidence_required"
    APPROVED_FOR_QUALIFICATION_CONSIDERATION = (
        "approved_for_qualification_consideration"
    )


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberQualificationReadinessEvidenceContext:
    """Inputs required to reconstruct qualification readiness."""

    assurance: ASRCriticalNumberAssuranceEvidenceBundle
    method_manifest: ASRCriticalNumberPrivateStatisticalMethodManifestBundle
    private_assessment: ASRCriticalNumberPrivateStatisticalAssessmentBundle
    private_verification: (
        ASRCriticalNumberPrivateQualificationVerificationContext
    )
    private_holdout_exclusion: (
        ASRCriticalNumberPrivateHoldoutExclusionManifestBundle
    )
    production_evidence: ASRCriticalNumberProductionEvidenceManifestBundle
    production_verification: (
        ASRCriticalNumberProductionEvidenceVerificationContext
    )
    matched_release_shadow: ASRCriticalNumberMatchedReleaseShadowResult
    matched_release_shadow_verification: (
        ASRCriticalNumberMatchedReleaseShadowVerificationContext
    )


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberGovernanceReviewer:
    """One authorized governance reviewer."""

    role: ASRCriticalNumberGovernanceReviewerRole
    key_id: str
    affiliation_key: str
    qualification_sha256: str
    authorization_sha256: str
    independence_attestation_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.role, ASRCriticalNumberGovernanceReviewerRole):
            raise HveeContractError(
                "critical-number governance reviewer requires a versioned role"
            )
        _require_identifier(
            name="governance reviewer key id",
            value=self.key_id,
        )
        _require_identifier(
            name="governance reviewer affiliation key",
            value=self.affiliation_key,
        )
        for name, value in (
            ("qualification", self.qualification_sha256),
            ("authorization", self.authorization_sha256),
            (
                "independence attestation",
                self.independence_attestation_sha256,
            ),
        ):
            _require_sha256(
                name=f"governance reviewer {name}",
                value=value,
            )


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberGovernanceReviewProtocolDefinition:
    """Preregistered governance-review definition."""

    review_id: str
    review_version: str
    readiness_sha256: str
    reviewers: tuple[ASRCriticalNumberGovernanceReviewer, ...]
    review_procedure_sha256: str
    reviewer_qualification_policy_sha256: str
    conflict_of_interest_policy_sha256: str
    authority_policy_sha256: str

    def __post_init__(self) -> None:
        _require_identifier(
            name="governance review id",
            value=self.review_id,
        )
        _require_version(
            name="governance review version",
            value=self.review_version,
        )
        _require_sha256(
            name="governance readiness binding",
            value=self.readiness_sha256,
        )
        _require_governance_reviewer_roster(self.reviewers)
        for name, value in (
            ("review procedure", self.review_procedure_sha256),
            (
                "reviewer qualification policy",
                self.reviewer_qualification_policy_sha256,
            ),
            (
                "conflict-of-interest policy",
                self.conflict_of_interest_policy_sha256,
            ),
            ("authority policy", self.authority_policy_sha256),
        ):
            _require_sha256(
                name=f"governance {name}",
                value=value,
            )


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberGovernanceReviewProtocolBundle:
    """Sealed governance-review protocol."""

    payload: dict[str, object]
    sha256: str


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberGovernanceReviewerDecision:
    """Opaque commitment to one reviewer's decision record."""

    role: ASRCriticalNumberGovernanceReviewerRole
    reviewer_key_id: str
    readiness_sha256: str
    disposition: ASRCriticalNumberGovernanceDisposition
    decision_record_sha256: str
    evidence_review_attestation_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.role, ASRCriticalNumberGovernanceReviewerRole):
            raise HveeContractError(
                "governance decision requires a versioned reviewer role"
            )
        _require_identifier(
            name="governance decision reviewer key id",
            value=self.reviewer_key_id,
        )
        _require_sha256(
            name="governance decision readiness binding",
            value=self.readiness_sha256,
        )
        if not isinstance(
            self.disposition,
            ASRCriticalNumberGovernanceDisposition,
        ):
            raise HveeContractError(
                "governance decision requires a versioned disposition"
            )
        _require_sha256(
            name="governance decision record",
            value=self.decision_record_sha256,
        )
        _require_sha256(
            name="governance evidence-review attestation",
            value=self.evidence_review_attestation_sha256,
        )


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberGovernanceReviewDefinition:
    """Completed independent governance review."""

    review_id: str
    review_version: str
    protocol_sha256: str
    readiness_sha256: str
    review_environment_sha256: str
    independence_attestation_sha256: str
    decisions: tuple[ASRCriticalNumberGovernanceReviewerDecision, ...]

    def __post_init__(self) -> None:
        _require_identifier(
            name="completed governance review id",
            value=self.review_id,
        )
        _require_version(
            name="completed governance review version",
            value=self.review_version,
        )
        for name, value in (
            ("protocol", self.protocol_sha256),
            ("readiness", self.readiness_sha256),
            ("review environment", self.review_environment_sha256),
            (
                "review independence attestation",
                self.independence_attestation_sha256,
            ),
        ):
            _require_sha256(
                name=f"completed governance review {name}",
                value=value,
            )
        _require_decision_tuple(self.decisions)


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberGovernanceReviewBundle:
    """Sealed completed governance review."""

    payload: dict[str, object]
    sha256: str


def _require_sha256(*, name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise HveeContractError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _require_identifier(*, name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HveeContractError(f"{name} must be a non-empty identifier")
    return value


def _require_version(*, name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HveeContractError(f"{name} must be a non-empty version")
    return value


def _require_dict(*, name: str, value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise HveeContractError(f"{name} must be an object")
    return value


def _canonical_json(value: object) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise HveeContractError(
            "critical-number governance review must be deterministic JSON"
        ) from exc


def calculate_critical_number_governance_review_sha256(
    payload: object,
) -> str:
    """Return a canonical SHA-256 for governance-review evidence."""

    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _reviewer_snapshot(
    reviewer: ASRCriticalNumberGovernanceReviewer,
) -> dict[str, object]:
    return {
        "role": reviewer.role.value,
        "key_id": reviewer.key_id,
        "affiliation_key": reviewer.affiliation_key,
        "qualification_sha256": reviewer.qualification_sha256,
        "authorization_sha256": reviewer.authorization_sha256,
        "independence_attestation_sha256": (
            reviewer.independence_attestation_sha256
        ),
    }


def _require_governance_reviewer_roster(
    reviewers: tuple[ASRCriticalNumberGovernanceReviewer, ...],
) -> None:
    if (
        not isinstance(reviewers, tuple)
        or len(reviewers) != len(CRITICAL_NUMBER_GOVERNANCE_REQUIRED_ROLES_V1)
        or any(
            not isinstance(reviewer, ASRCriticalNumberGovernanceReviewer)
            for reviewer in reviewers
        )
    ):
        raise HveeContractError(
            "governance review requires exactly one reviewer per required role"
        )

    roles = tuple(reviewer.role for reviewer in reviewers)
    if roles != CRITICAL_NUMBER_GOVERNANCE_REQUIRED_ROLES_V1:
        raise HveeContractError(
            "governance reviewer roster must use the required ordered roles"
        )

    key_ids = tuple(reviewer.key_id for reviewer in reviewers)
    if len(set(key_ids)) != len(key_ids):
        raise HveeContractError(
            "governance reviewers must use distinct key ids"
        )


def calculate_critical_number_governance_reviewer_roster_sha256(
    reviewers: tuple[ASRCriticalNumberGovernanceReviewer, ...],
) -> str:
    """Commit the exact ordered governance-reviewer roster."""

    _require_governance_reviewer_roster(reviewers)
    return calculate_critical_number_governance_review_sha256(
        {
            "domain": CRITICAL_NUMBER_GOVERNANCE_REVIEW_PROTOCOL_KEY,
            "version": CRITICAL_NUMBER_GOVERNANCE_REVIEW_PROTOCOL_VERSION,
            "artifact": "governance_reviewer_roster",
            "reviewers": [
                _reviewer_snapshot(reviewer) for reviewer in reviewers
            ],
        }
    )


def _decision_snapshot(
    decision: ASRCriticalNumberGovernanceReviewerDecision,
) -> dict[str, object]:
    return {
        "role": decision.role.value,
        "reviewer_key_id": decision.reviewer_key_id,
        "readiness_sha256": decision.readiness_sha256,
        "disposition": decision.disposition.value,
        "decision_record_sha256": decision.decision_record_sha256,
        "evidence_review_attestation_sha256": (
            decision.evidence_review_attestation_sha256
        ),
    }


def _require_decision_tuple(
    decisions: tuple[ASRCriticalNumberGovernanceReviewerDecision, ...],
) -> None:
    if (
        not isinstance(decisions, tuple)
        or len(decisions) != len(CRITICAL_NUMBER_GOVERNANCE_REQUIRED_ROLES_V1)
        or any(
            not isinstance(
                decision,
                ASRCriticalNumberGovernanceReviewerDecision,
            )
            for decision in decisions
        )
    ):
        raise HveeContractError(
            "governance review requires exactly one decision per required role"
        )

    if tuple(decision.role for decision in decisions) != (
        CRITICAL_NUMBER_GOVERNANCE_REQUIRED_ROLES_V1
    ):
        raise HveeContractError(
            "governance decisions must retain the required ordered roles"
        )

    reviewer_keys = tuple(
        decision.reviewer_key_id for decision in decisions
    )
    if len(set(reviewer_keys)) != len(reviewer_keys):
        raise HveeContractError(
            "governance decisions must use distinct reviewer key ids"
        )

    decision_records = tuple(
        decision.decision_record_sha256 for decision in decisions
    )
    if len(set(decision_records)) != len(decision_records):
        raise HveeContractError(
            "governance reviewers must use distinct decision records"
        )

    evidence_attestations = tuple(
        decision.evidence_review_attestation_sha256
        for decision in decisions
    )
    if len(set(evidence_attestations)) != len(evidence_attestations):
        raise HveeContractError(
            "governance reviewers must use distinct evidence-review "
            "attestations"
        )


def _governance_boundary() -> dict[str, object]:
    return {
        "evaluator_status": "experimental",
        "approval_scope": "qualification_consideration_only",
        "certification_issued": False,
        "production_qualified": False,
        "release_enforcement_eligible": False,
        "official_release_verdict_modified": False,
    }


def _verify_readiness(
    *,
    readiness: ASRCriticalNumberQualificationReadinessBundle,
    evidence: ASRCriticalNumberQualificationReadinessEvidenceContext,
) -> ASRCriticalNumberQualificationReadinessBundle:
    if not isinstance(
        readiness,
        ASRCriticalNumberQualificationReadinessBundle,
    ):
        raise HveeContractError(
            "governance review requires a qualification-readiness dossier"
        )
    if not isinstance(
        evidence,
        ASRCriticalNumberQualificationReadinessEvidenceContext,
    ):
        raise HveeContractError(
            "governance review requires readiness evidence context"
        )

    verified = verify_critical_number_qualification_readiness_v1(
        payload=readiness.payload,
        expected_sha256=readiness.sha256,
        assurance=evidence.assurance,
        method_manifest=evidence.method_manifest,
        private_assessment=evidence.private_assessment,
        private_verification=evidence.private_verification,
        private_holdout_exclusion=evidence.private_holdout_exclusion,
        production_evidence=evidence.production_evidence,
        production_verification=evidence.production_verification,
        matched_release_shadow=evidence.matched_release_shadow,
        matched_release_shadow_verification=(
            evidence.matched_release_shadow_verification
        ),
    )

    readiness_state = _require_dict(
        name="qualification readiness result",
        value=verified.payload.get("readiness"),
    )
    if readiness_state.get("result") != (
        ASRCriticalNumberQualificationReadinessResult
        .READY_FOR_GOVERNANCE_REVIEW.value
    ):
        raise HveeContractError(
            "governance review requires evidence ready for governance review"
        )

    if verified.payload.get("governance_boundary") != {
        "evaluator_status": "experimental",
        "governance_review_only": True,
        "certification_issued": False,
        "production_qualified": False,
        "release_enforcement_eligible": False,
        "official_release_verdict_modified": False,
    }:
        raise HveeContractError(
            "qualification-readiness governance boundary changed"
        )

    return verified


def _readiness_binding(
    readiness: ASRCriticalNumberQualificationReadinessBundle,
) -> dict[str, object]:
    bindings = _require_dict(
        name="qualification-readiness bindings",
        value=readiness.payload.get("bindings"),
    )
    assurance = _require_dict(
        name="qualification-readiness assurance binding",
        value=bindings.get("assurance"),
    )
    return {
        "profile_key": CRITICAL_NUMBER_QUALIFICATION_READINESS_KEY,
        "profile_version": CRITICAL_NUMBER_QUALIFICATION_READINESS_VERSION,
        "sha256": readiness.sha256,
        "result": (
            ASRCriticalNumberQualificationReadinessResult
            .READY_FOR_GOVERNANCE_REVIEW.value
        ),
        "assurance_sha256": _require_sha256(
            name="qualification-readiness assurance SHA-256",
            value=assurance.get("sha256"),
        ),
        "private_statistical_assessment_sha256": _require_sha256(
            name="qualification-readiness private assessment SHA-256",
            value=bindings.get("private_statistical_assessment_sha256"),
        ),
        "production_evidence_sha256": _require_sha256(
            name="qualification-readiness production evidence SHA-256",
            value=bindings.get("production_evidence_sha256"),
        ),
    }


def _require_governance_independence(
    *,
    reviewers: tuple[ASRCriticalNumberGovernanceReviewer, ...],
    evidence: ASRCriticalNumberQualificationReadinessEvidenceContext,
) -> None:
    private_adjudicators = (
        evidence.private_verification.adjudication_definition.adjudicators
    )
    private_keys = {adjudicator.key_id for adjudicator in private_adjudicators}
    governance_keys = {reviewer.key_id for reviewer in reviewers}
    if private_keys.intersection(governance_keys):
        raise HveeContractError(
            "governance reviewers must be distinct from private adjudicators"
        )


def build_critical_number_governance_review_protocol_v1(
    *,
    definition: ASRCriticalNumberGovernanceReviewProtocolDefinition,
    readiness: ASRCriticalNumberQualificationReadinessBundle,
    readiness_evidence: ASRCriticalNumberQualificationReadinessEvidenceContext,
) -> ASRCriticalNumberGovernanceReviewProtocolBundle:
    """Seal the preregistered governance-review protocol."""

    if not isinstance(
        definition,
        ASRCriticalNumberGovernanceReviewProtocolDefinition,
    ):
        raise HveeContractError(
            "governance review requires a protocol definition"
        )

    verified_readiness = _verify_readiness(
        readiness=readiness,
        evidence=readiness_evidence,
    )
    if definition.readiness_sha256 != verified_readiness.sha256:
        raise HveeContractError(
            "governance protocol does not bind the supplied readiness dossier"
        )

    _require_governance_independence(
        reviewers=definition.reviewers,
        evidence=readiness_evidence,
    )

    roster_sha256 = (
        calculate_critical_number_governance_reviewer_roster_sha256(
            definition.reviewers
        )
    )

    payload: dict[str, object] = {
        "schema_version": (
            CRITICAL_NUMBER_GOVERNANCE_REVIEW_PROTOCOL_SCHEMA_VERSION
        ),
        "protocol": {
            "key": CRITICAL_NUMBER_GOVERNANCE_REVIEW_PROTOCOL_KEY,
            "version": CRITICAL_NUMBER_GOVERNANCE_REVIEW_PROTOCOL_VERSION,
            "artifact": "preregistered_governance_review_protocol",
            "decision_rule": {
                "key": CRITICAL_NUMBER_GOVERNANCE_DECISION_RULE_KEY,
                "version": CRITICAL_NUMBER_GOVERNANCE_DECISION_RULE_VERSION,
            },
        },
        "bindings": {
            "readiness": _readiness_binding(verified_readiness),
        },
        "preregistration": {
            "review_id": definition.review_id,
            "review_version": definition.review_version,
            "review_procedure_sha256": (
                definition.review_procedure_sha256
            ),
            "reviewer_qualification_policy_sha256": (
                definition.reviewer_qualification_policy_sha256
            ),
            "conflict_of_interest_policy_sha256": (
                definition.conflict_of_interest_policy_sha256
            ),
            "authority_policy_sha256": definition.authority_policy_sha256,
            "reviewer_roster_sha256": roster_sha256,
            "required_roles": [
                role.value
                for role in CRITICAL_NUMBER_GOVERNANCE_REQUIRED_ROLES_V1
            ],
            "reviewers": [
                _reviewer_snapshot(reviewer)
                for reviewer in definition.reviewers
            ],
            "private_adjudicator_key_ids_disjoint": True,
            "approval_requires_unanimity": True,
            "rejection_dominates": True,
            "more_evidence_dominates_non_unanimous_approval": True,
        },
        "sealed_evidence": {
            "qualification_readiness_sha256": verified_readiness.sha256,
            "complete_readiness_chain_reverified": True,
        },
        "governance_boundary": _governance_boundary(),
    }

    return ASRCriticalNumberGovernanceReviewProtocolBundle(
        payload=payload,
        sha256=calculate_critical_number_governance_review_sha256(payload),
    )


def verify_critical_number_governance_review_protocol_v1(
    *,
    payload: object,
    expected_sha256: object,
    definition: ASRCriticalNumberGovernanceReviewProtocolDefinition,
    readiness: ASRCriticalNumberQualificationReadinessBundle,
    readiness_evidence: ASRCriticalNumberQualificationReadinessEvidenceContext,
) -> ASRCriticalNumberGovernanceReviewProtocolBundle:
    """Rebuild the governance protocol and require exact equality."""

    expected_digest = _require_sha256(
        name="governance protocol SHA-256",
        value=expected_sha256,
    )
    supplied = _require_dict(
        name="governance protocol payload",
        value=payload,
    )
    if calculate_critical_number_governance_review_sha256(
        supplied
    ) != expected_digest:
        raise HveeContractError(
            "governance protocol does not match expected SHA-256"
        )

    rebuilt = build_critical_number_governance_review_protocol_v1(
        definition=definition,
        readiness=readiness,
        readiness_evidence=readiness_evidence,
    )
    if supplied != rebuilt.payload or expected_digest != rebuilt.sha256:
        raise HveeContractError(
            "governance protocol does not match bound readiness evidence"
        )
    return rebuilt


def _resolve_governance_disposition(
    decisions: tuple[ASRCriticalNumberGovernanceReviewerDecision, ...],
) -> ASRCriticalNumberGovernanceDisposition:
    dispositions = tuple(decision.disposition for decision in decisions)

    if ASRCriticalNumberGovernanceDisposition.REJECTED in dispositions:
        return ASRCriticalNumberGovernanceDisposition.REJECTED

    if (
        ASRCriticalNumberGovernanceDisposition.MORE_EVIDENCE_REQUIRED
        in dispositions
    ):
        return (
            ASRCriticalNumberGovernanceDisposition.MORE_EVIDENCE_REQUIRED
        )

    if all(
        disposition
        == (
            ASRCriticalNumberGovernanceDisposition
            .APPROVED_FOR_QUALIFICATION_CONSIDERATION
        )
        for disposition in dispositions
    ):
        return (
            ASRCriticalNumberGovernanceDisposition
            .APPROVED_FOR_QUALIFICATION_CONSIDERATION
        )

    raise HveeContractError(
        "governance decisions cannot be resolved under the v1 rule"
    )


def build_critical_number_governance_review_v1(
    *,
    protocol: ASRCriticalNumberGovernanceReviewProtocolBundle,
    protocol_definition: ASRCriticalNumberGovernanceReviewProtocolDefinition,
    readiness: ASRCriticalNumberQualificationReadinessBundle,
    readiness_evidence: ASRCriticalNumberQualificationReadinessEvidenceContext,
    definition: ASRCriticalNumberGovernanceReviewDefinition,
) -> ASRCriticalNumberGovernanceReviewBundle:
    """Build a completed, non-certifying governance review."""

    if not isinstance(
        definition,
        ASRCriticalNumberGovernanceReviewDefinition,
    ):
        raise HveeContractError(
            "governance review requires a completed review definition"
        )

    verified_protocol = verify_critical_number_governance_review_protocol_v1(
        payload=protocol.payload,
        expected_sha256=protocol.sha256,
        definition=protocol_definition,
        readiness=readiness,
        readiness_evidence=readiness_evidence,
    )
    verified_readiness = _verify_readiness(
        readiness=readiness,
        evidence=readiness_evidence,
    )

    if (
        definition.review_id != protocol_definition.review_id
        or definition.review_version != protocol_definition.review_version
    ):
        raise HveeContractError(
            "completed governance review identity does not match protocol"
        )
    if definition.protocol_sha256 != verified_protocol.sha256:
        raise HveeContractError(
            "completed governance review does not bind the protocol"
        )
    if definition.readiness_sha256 != verified_readiness.sha256:
        raise HveeContractError(
            "completed governance review does not bind readiness"
        )

    expected_reviewers = {
        reviewer.role: reviewer
        for reviewer in protocol_definition.reviewers
    }
    for decision in definition.decisions:
        reviewer = expected_reviewers.get(decision.role)
        if (
            reviewer is None
            or decision.reviewer_key_id != reviewer.key_id
            or decision.readiness_sha256 != verified_readiness.sha256
        ):
            raise HveeContractError(
                "governance reviewer decision does not match preregistration"
            )

    disposition = _resolve_governance_disposition(definition.decisions)
    roster_sha256 = (
        calculate_critical_number_governance_reviewer_roster_sha256(
            protocol_definition.reviewers
        )
    )

    payload: dict[str, object] = {
        "schema_version": CRITICAL_NUMBER_GOVERNANCE_REVIEW_SCHEMA_VERSION,
        "protocol": {
            "key": CRITICAL_NUMBER_GOVERNANCE_REVIEW_PROTOCOL_KEY,
            "version": CRITICAL_NUMBER_GOVERNANCE_REVIEW_PROTOCOL_VERSION,
            "artifact": "independent_governance_review",
            "decision_rule": {
                "key": CRITICAL_NUMBER_GOVERNANCE_DECISION_RULE_KEY,
                "version": CRITICAL_NUMBER_GOVERNANCE_DECISION_RULE_VERSION,
            },
        },
        "bindings": {
            "governance_protocol_sha256": verified_protocol.sha256,
            "readiness": _readiness_binding(verified_readiness),
        },
        "sealed_evidence": {
            "qualification_readiness_sha256": verified_readiness.sha256,
            "complete_readiness_chain_reverified": True,
            "governance_protocol_reverified": True,
        },
        "governance_review": {
            "review_id": definition.review_id,
            "review_version": definition.review_version,
            "review_environment_sha256": (
                definition.review_environment_sha256
            ),
            "independence_attestation_sha256": (
                definition.independence_attestation_sha256
            ),
            "reviewer_roster_sha256": roster_sha256,
            "reviewers": [
                _reviewer_snapshot(reviewer)
                for reviewer in protocol_definition.reviewers
            ],
            "decisions": [
                _decision_snapshot(decision)
                for decision in definition.decisions
            ],
            "decision_counts": {
                candidate.value: sum(
                    decision.disposition == candidate
                    for decision in definition.decisions
                )
                for candidate in ASRCriticalNumberGovernanceDisposition
            },
            "disposition": disposition.value,
            "unanimous_approval": disposition
            == (
                ASRCriticalNumberGovernanceDisposition
                .APPROVED_FOR_QUALIFICATION_CONSIDERATION
            ),
        },
        "authority": {
            "governance_disposition": disposition.value,
            "qualification_consideration_authorized": disposition
            == (
                ASRCriticalNumberGovernanceDisposition
                .APPROVED_FOR_QUALIFICATION_CONSIDERATION
            ),
            **_governance_boundary(),
        },
        "confidentiality": {
            "qualification_readiness_payload_in_artifact": False,
            "private_case_content_in_artifact": False,
            "production_case_commitments_in_artifact": False,
            "cross_set_linkage_tokens_in_artifact": False,
            "review_record_contents_in_artifact": False,
            "opaque_commitments_and_dispositions_only": True,
        },
    }

    return ASRCriticalNumberGovernanceReviewBundle(
        payload=payload,
        sha256=calculate_critical_number_governance_review_sha256(payload),
    )


def verify_critical_number_governance_review_v1(
    *,
    payload: object,
    expected_sha256: object,
    protocol: ASRCriticalNumberGovernanceReviewProtocolBundle,
    protocol_definition: ASRCriticalNumberGovernanceReviewProtocolDefinition,
    readiness: ASRCriticalNumberQualificationReadinessBundle,
    readiness_evidence: ASRCriticalNumberQualificationReadinessEvidenceContext,
    definition: ASRCriticalNumberGovernanceReviewDefinition,
) -> ASRCriticalNumberGovernanceReviewBundle:
    """Rebuild a completed governance review and require exact equality."""

    expected_digest = _require_sha256(
        name="governance review SHA-256",
        value=expected_sha256,
    )
    supplied = _require_dict(
        name="governance review payload",
        value=payload,
    )
    if calculate_critical_number_governance_review_sha256(
        supplied
    ) != expected_digest:
        raise HveeContractError(
            "governance review does not match expected SHA-256"
        )

    rebuilt = build_critical_number_governance_review_v1(
        protocol=protocol,
        protocol_definition=protocol_definition,
        readiness=readiness,
        readiness_evidence=readiness_evidence,
        definition=definition,
    )
    if supplied != rebuilt.payload or expected_digest != rebuilt.sha256:
        raise HveeContractError(
            "governance review does not match its bound evidence"
        )
    return rebuilt

"""Scoped production qualification for Critical Number Fidelity v1.

This layer consumes an independently verified governance approval and may
authorize one exact evaluator/profile combination for narrowly scoped advisory
production evaluation.

Production qualification is not certification, release-enforcement
eligibility, or permission to modify an official release verdict.

The artifact is deterministic and historical. It does not consult a wall
clock or determine whether the authorization is currently eligible at runtime.
Runtime use must separately check the validity window, revocation state, and
requalification triggers.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.critical_number_fidelity import (
    CRITICAL_NUMBER_FIDELITY_EVALUATOR,
    EN_US_CRITICAL_NUMBER_PROFILE,
)
from hvee.packs.asr.critical_number_governance_review import (
    CRITICAL_NUMBER_GOVERNANCE_REVIEW_PROTOCOL_KEY,
    CRITICAL_NUMBER_GOVERNANCE_REVIEW_PROTOCOL_VERSION,
    ASRCriticalNumberGovernanceDisposition,
    ASRCriticalNumberGovernanceReviewBundle,
    ASRCriticalNumberGovernanceReviewDefinition,
    ASRCriticalNumberGovernanceReviewProtocolBundle,
    ASRCriticalNumberGovernanceReviewProtocolDefinition,
    ASRCriticalNumberQualificationReadinessEvidenceContext,
    verify_critical_number_governance_review_v1,
)
from hvee.packs.asr.critical_number_qualification_readiness import (
    ASRCriticalNumberQualificationReadinessBundle,
)


CRITICAL_NUMBER_PRODUCTION_QUALIFICATION_POLICY_SCHEMA_VERSION = 1
CRITICAL_NUMBER_PRODUCTION_QUALIFICATION_AUTHORIZATION_SCHEMA_VERSION = 1
CRITICAL_NUMBER_PRODUCTION_QUALIFICATION_KEY = (
    "hetren.asr.critical-number-production-qualification.en-us"
)
CRITICAL_NUMBER_PRODUCTION_QUALIFICATION_VERSION = "1.0.0"


class ASRCriticalNumberProductionUseCategory(StrEnum):
    """Production use permitted by the v1 qualification scope."""

    ADVISORY_PRODUCTION_EVALUATION = "advisory_production_evaluation"


class ASRCriticalNumberRequalificationTrigger(StrEnum):
    """Events requiring production qualification to be reconsidered."""

    EVALUATOR_VERSION_CHANGE = "evaluator_version_change"
    ASSURANCE_PROFILE_CHANGE = "assurance_profile_change"
    STATISTICAL_METHOD_CHANGE = "statistical_method_change"
    PRIVATE_QUALIFICATION_EVIDENCE_CHANGE = (
        "private_qualification_evidence_change"
    )
    PRODUCTION_EVIDENCE_CHANGE = "production_evidence_change"
    GOVERNANCE_REVIEW_CHANGE = "governance_review_change"
    QUALIFICATION_SCOPE_EXPANSION = "qualification_scope_expansion"
    MATERIAL_EVALUATOR_REGRESSION = "material_evaluator_regression"
    QUALIFICATION_EXPIRATION = "qualification_expiration"
    EXPLICIT_REVOCATION = "explicit_revocation"


CRITICAL_NUMBER_PRODUCTION_REQUALIFICATION_TRIGGERS_V1 = tuple(
    ASRCriticalNumberRequalificationTrigger
)


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberGovernanceReviewVerificationContext:
    """Evidence required to reconstruct the governance review."""

    protocol: ASRCriticalNumberGovernanceReviewProtocolBundle
    protocol_definition: ASRCriticalNumberGovernanceReviewProtocolDefinition
    readiness: ASRCriticalNumberQualificationReadinessBundle
    readiness_evidence: ASRCriticalNumberQualificationReadinessEvidenceContext
    definition: ASRCriticalNumberGovernanceReviewDefinition


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberProductionQualificationScope:
    """Exact evaluator/profile scope qualified for production use."""

    evaluator_key: str
    evaluator_version: str
    evaluation_type: str
    evaluation_profile_key: str
    evaluation_profile_version: str
    language: str
    locale: str
    production_use_category: ASRCriticalNumberProductionUseCategory
    scope_definition_sha256: str

    def __post_init__(self) -> None:
        for name, value in (
            ("evaluator key", self.evaluator_key),
            ("evaluator version", self.evaluator_version),
            ("evaluation type", self.evaluation_type),
            ("evaluation profile key", self.evaluation_profile_key),
            ("evaluation profile version", self.evaluation_profile_version),
            ("language", self.language),
            ("locale", self.locale),
        ):
            _require_identifier(
                name=f"production qualification {name}",
                value=value,
            )

        if not isinstance(
            self.production_use_category,
            ASRCriticalNumberProductionUseCategory,
        ):
            raise HveeContractError(
                "production qualification requires a versioned use category"
            )

        _require_sha256(
            name="production qualification scope definition",
            value=self.scope_definition_sha256,
        )

        expected = (
            CRITICAL_NUMBER_FIDELITY_EVALUATOR.key,
            CRITICAL_NUMBER_FIDELITY_EVALUATOR.version,
            CRITICAL_NUMBER_FIDELITY_EVALUATOR.evaluation_type,
            EN_US_CRITICAL_NUMBER_PROFILE.key,
            EN_US_CRITICAL_NUMBER_PROFILE.version,
            EN_US_CRITICAL_NUMBER_PROFILE.language,
            EN_US_CRITICAL_NUMBER_PROFILE.locale,
        )
        supplied = (
            self.evaluator_key,
            self.evaluator_version,
            self.evaluation_type,
            self.evaluation_profile_key,
            self.evaluation_profile_version,
            self.language,
            self.locale,
        )
        if supplied != expected:
            raise HveeContractError(
                "production qualification scope must match the canonical "
                "Critical Number Fidelity v1 evaluator and en-US profile"
            )


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberProductionQualificationAuthority:
    """Independent authority permitted to issue production qualification."""

    key_id: str
    affiliation_key: str
    qualification_sha256: str
    authorization_sha256: str
    independence_attestation_sha256: str

    def __post_init__(self) -> None:
        _require_identifier(
            name="production qualification authority key id",
            value=self.key_id,
        )
        _require_identifier(
            name="production qualification authority affiliation key",
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
                name=f"production qualification authority {name}",
                value=value,
            )


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberProductionQualificationPolicyDefinition:
    """Preregistered policy controlling a production qualification."""

    qualification_id: str
    qualification_version: str
    governance_review_sha256: str
    scope: ASRCriticalNumberProductionQualificationScope
    authority: ASRCriticalNumberProductionQualificationAuthority
    effective_at_utc: str
    expires_at_utc: str
    qualification_procedure_sha256: str
    validity_policy_sha256: str
    requalification_policy_sha256: str
    revocation_policy_sha256: str

    def __post_init__(self) -> None:
        _require_identifier(
            name="production qualification id",
            value=self.qualification_id,
        )
        _require_version(
            name="production qualification version",
            value=self.qualification_version,
        )
        _require_sha256(
            name="production qualification governance review",
            value=self.governance_review_sha256,
        )
        if not isinstance(
            self.scope,
            ASRCriticalNumberProductionQualificationScope,
        ):
            raise HveeContractError(
                "production qualification requires a versioned scope"
            )
        if not isinstance(
            self.authority,
            ASRCriticalNumberProductionQualificationAuthority,
        ):
            raise HveeContractError(
                "production qualification requires an authority"
            )

        effective = _require_utc_timestamp(
            name="production qualification effective time",
            value=self.effective_at_utc,
        )
        expires = _require_utc_timestamp(
            name="production qualification expiration time",
            value=self.expires_at_utc,
        )
        if expires <= effective:
            raise HveeContractError(
                "production qualification expiration must follow "
                "its effective time"
            )

        for name, value in (
            (
                "qualification procedure",
                self.qualification_procedure_sha256,
            ),
            ("validity policy", self.validity_policy_sha256),
            ("requalification policy", self.requalification_policy_sha256),
            ("revocation policy", self.revocation_policy_sha256),
        ):
            _require_sha256(
                name=f"production qualification {name}",
                value=value,
            )


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberProductionQualificationPolicyBundle:
    """Sealed production-qualification policy."""

    payload: dict[str, object]
    sha256: str


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberProductionQualificationAuthorizationDefinition:
    """One immutable production-qualification authorization issuance."""

    qualification_id: str
    qualification_version: str
    policy_sha256: str
    governance_review_sha256: str
    authority_key_id: str
    authorization_record_sha256: str
    issuance_attestation_sha256: str

    def __post_init__(self) -> None:
        _require_identifier(
            name="qualification authorization id",
            value=self.qualification_id,
        )
        _require_version(
            name="qualification authorization version",
            value=self.qualification_version,
        )
        _require_identifier(
            name="qualification authorization authority key",
            value=self.authority_key_id,
        )
        for name, value in (
            ("policy", self.policy_sha256),
            ("governance review", self.governance_review_sha256),
            ("authorization record", self.authorization_record_sha256),
            ("issuance attestation", self.issuance_attestation_sha256),
        ):
            _require_sha256(
                name=f"qualification authorization {name}",
                value=value,
            )


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberProductionQualificationAuthorizationBundle:
    """Sealed scoped production-qualification authorization."""

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


def _require_utc_timestamp(*, name: str, value: object) -> datetime:
    if not isinstance(value, str):
        raise HveeContractError(
            f"{name} must be a canonical UTC timestamp"
        )
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise HveeContractError(
            f"{name} must use YYYY-MM-DDTHH:MM:SSZ"
        ) from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise HveeContractError(
            f"{name} must use canonical UTC representation"
        )
    return parsed


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
            "critical-number production qualification must be "
            "deterministic JSON"
        ) from exc


def calculate_critical_number_production_qualification_sha256(
    payload: object,
) -> str:
    """Return the canonical SHA-256 for qualification artifacts."""

    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _scope_snapshot(
    scope: ASRCriticalNumberProductionQualificationScope,
) -> dict[str, object]:
    return {
        "evaluator": {
            "key": scope.evaluator_key,
            "version": scope.evaluator_version,
            "evaluation_type": scope.evaluation_type,
        },
        "evaluation_profile": {
            "key": scope.evaluation_profile_key,
            "version": scope.evaluation_profile_version,
            "language": scope.language,
            "locale": scope.locale,
        },
        "production_use_category": scope.production_use_category.value,
        "scope_definition_sha256": scope.scope_definition_sha256,
    }


def _authority_snapshot(
    authority: ASRCriticalNumberProductionQualificationAuthority,
) -> dict[str, object]:
    return {
        "key_id": authority.key_id,
        "affiliation_key": authority.affiliation_key,
        "qualification_sha256": authority.qualification_sha256,
        "authorization_sha256": authority.authorization_sha256,
        "independence_attestation_sha256": (
            authority.independence_attestation_sha256
        ),
    }


def _policy_boundary() -> dict[str, object]:
    return {
        "qualification_policy_only": True,
        "qualification_authorization_issued": False,
        "certification_issued": False,
        "production_qualified": False,
        "release_enforcement_eligible": False,
        "official_release_verdict_modified": False,
    }


def _authorization_boundary() -> dict[str, object]:
    return {
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


def _verify_governance_review(
    *,
    governance_review: ASRCriticalNumberGovernanceReviewBundle,
    verification: ASRCriticalNumberGovernanceReviewVerificationContext,
) -> ASRCriticalNumberGovernanceReviewBundle:
    if not isinstance(
        governance_review,
        ASRCriticalNumberGovernanceReviewBundle,
    ):
        raise HveeContractError(
            "production qualification requires a governance review"
        )
    if not isinstance(
        verification,
        ASRCriticalNumberGovernanceReviewVerificationContext,
    ):
        raise HveeContractError(
            "production qualification requires governance verification context"
        )

    verified = verify_critical_number_governance_review_v1(
        payload=governance_review.payload,
        expected_sha256=governance_review.sha256,
        protocol=verification.protocol,
        protocol_definition=verification.protocol_definition,
        readiness=verification.readiness,
        readiness_evidence=verification.readiness_evidence,
        definition=verification.definition,
    )

    expected_authority = {
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
    if verified.payload.get("authority") != expected_authority:
        raise HveeContractError(
            "production qualification requires governance approval "
            "for qualification consideration"
        )

    return verified


def _governance_binding(
    governance_review: ASRCriticalNumberGovernanceReviewBundle,
) -> dict[str, object]:
    bindings = _require_dict(
        name="governance-review bindings",
        value=governance_review.payload.get("bindings"),
    )
    readiness = _require_dict(
        name="governance-review readiness binding",
        value=bindings.get("readiness"),
    )
    return {
        "protocol_key": CRITICAL_NUMBER_GOVERNANCE_REVIEW_PROTOCOL_KEY,
        "protocol_version": CRITICAL_NUMBER_GOVERNANCE_REVIEW_PROTOCOL_VERSION,
        "sha256": governance_review.sha256,
        "governance_protocol_sha256": _require_sha256(
            name="governance protocol SHA-256",
            value=bindings.get("governance_protocol_sha256"),
        ),
        "qualification_readiness_sha256": _require_sha256(
            name="governance readiness SHA-256",
            value=readiness.get("sha256"),
        ),
        "disposition": (
            ASRCriticalNumberGovernanceDisposition
            .APPROVED_FOR_QUALIFICATION_CONSIDERATION.value
        ),
    }


def _require_authority_independence(
    *,
    authority: ASRCriticalNumberProductionQualificationAuthority,
    verification: ASRCriticalNumberGovernanceReviewVerificationContext,
) -> None:
    governance_keys = {
        reviewer.key_id
        for reviewer in verification.protocol_definition.reviewers
    }
    private_keys = {
        adjudicator.key_id
        for adjudicator in (
            verification.readiness_evidence
            .private_verification
            .adjudication_definition
            .adjudicators
        )
    }

    if authority.key_id in governance_keys:
        raise HveeContractError(
            "production qualification authority must be distinct "
            "from governance reviewers"
        )
    if authority.key_id in private_keys:
        raise HveeContractError(
            "production qualification authority must be distinct "
            "from private adjudicators"
        )


def build_critical_number_production_qualification_policy_v1(
    *,
    definition: ASRCriticalNumberProductionQualificationPolicyDefinition,
    governance_review: ASRCriticalNumberGovernanceReviewBundle,
    governance_verification: ASRCriticalNumberGovernanceReviewVerificationContext,
) -> ASRCriticalNumberProductionQualificationPolicyBundle:
    """Seal the scoped production-qualification policy."""

    if not isinstance(
        definition,
        ASRCriticalNumberProductionQualificationPolicyDefinition,
    ):
        raise HveeContractError(
            "production qualification requires a policy definition"
        )

    verified_governance = _verify_governance_review(
        governance_review=governance_review,
        verification=governance_verification,
    )
    if definition.governance_review_sha256 != verified_governance.sha256:
        raise HveeContractError(
            "production qualification policy does not bind "
            "the supplied governance review"
        )

    _require_authority_independence(
        authority=definition.authority,
        verification=governance_verification,
    )

    payload: dict[str, object] = {
        "schema_version": (
            CRITICAL_NUMBER_PRODUCTION_QUALIFICATION_POLICY_SCHEMA_VERSION
        ),
        "qualification_profile": {
            "key": CRITICAL_NUMBER_PRODUCTION_QUALIFICATION_KEY,
            "version": CRITICAL_NUMBER_PRODUCTION_QUALIFICATION_VERSION,
            "artifact": "production_qualification_policy",
        },
        "bindings": {
            "governance_review": _governance_binding(verified_governance),
            "scope": _scope_snapshot(definition.scope),
        },
        "qualification_policy": {
            "qualification_id": definition.qualification_id,
            "qualification_version": definition.qualification_version,
            "qualification_procedure_sha256": (
                definition.qualification_procedure_sha256
            ),
            "validity_policy_sha256": definition.validity_policy_sha256,
            "requalification_policy_sha256": (
                definition.requalification_policy_sha256
            ),
            "revocation_policy_sha256": definition.revocation_policy_sha256,
            "effective_at_utc": definition.effective_at_utc,
            "expires_at_utc": definition.expires_at_utc,
            "wall_clock_consulted_during_build": False,
            "requalification_triggers": [
                trigger.value
                for trigger
                in CRITICAL_NUMBER_PRODUCTION_REQUALIFICATION_TRIGGERS_V1
            ],
        },
        "qualification_authority": _authority_snapshot(
            definition.authority
        ),
        "independence": {
            "authority_distinct_from_governance_reviewers": True,
            "authority_distinct_from_private_adjudicators": True,
        },
        "sealed_evidence": {
            "governance_review_sha256": verified_governance.sha256,
            "complete_governance_chain_reverified": True,
        },
        "authority_boundary": _policy_boundary(),
        "confidentiality": {
            "governance_review_payload_in_artifact": False,
            "qualification_readiness_payload_in_artifact": False,
            "private_case_content_in_artifact": False,
            "production_case_commitments_in_artifact": False,
            "cross_set_linkage_tokens_in_artifact": False,
            "opaque_commitments_and_scope_only": True,
        },
    }

    return ASRCriticalNumberProductionQualificationPolicyBundle(
        payload=payload,
        sha256=calculate_critical_number_production_qualification_sha256(
            payload
        ),
    )


def verify_critical_number_production_qualification_policy_v1(
    *,
    payload: object,
    expected_sha256: object,
    definition: ASRCriticalNumberProductionQualificationPolicyDefinition,
    governance_review: ASRCriticalNumberGovernanceReviewBundle,
    governance_verification: ASRCriticalNumberGovernanceReviewVerificationContext,
) -> ASRCriticalNumberProductionQualificationPolicyBundle:
    """Rebuild a production-qualification policy and require exact equality."""

    expected_digest = _require_sha256(
        name="production qualification policy SHA-256",
        value=expected_sha256,
    )
    supplied = _require_dict(
        name="production qualification policy payload",
        value=payload,
    )
    if calculate_critical_number_production_qualification_sha256(
        supplied
    ) != expected_digest:
        raise HveeContractError(
            "production qualification policy does not match expected SHA-256"
        )

    rebuilt = build_critical_number_production_qualification_policy_v1(
        definition=definition,
        governance_review=governance_review,
        governance_verification=governance_verification,
    )
    if supplied != rebuilt.payload or expected_digest != rebuilt.sha256:
        raise HveeContractError(
            "production qualification policy does not match bound evidence"
        )
    return rebuilt


def build_critical_number_production_qualification_authorization_v1(
    *,
    policy: ASRCriticalNumberProductionQualificationPolicyBundle,
    policy_definition: ASRCriticalNumberProductionQualificationPolicyDefinition,
    governance_review: ASRCriticalNumberGovernanceReviewBundle,
    governance_verification: ASRCriticalNumberGovernanceReviewVerificationContext,
    definition: (
        ASRCriticalNumberProductionQualificationAuthorizationDefinition
    ),
) -> ASRCriticalNumberProductionQualificationAuthorizationBundle:
    """Issue a scoped, non-enforcing production qualification."""

    if not isinstance(
        definition,
        ASRCriticalNumberProductionQualificationAuthorizationDefinition,
    ):
        raise HveeContractError(
            "production qualification requires an authorization definition"
        )

    verified_policy = (
        verify_critical_number_production_qualification_policy_v1(
            payload=policy.payload,
            expected_sha256=policy.sha256,
            definition=policy_definition,
            governance_review=governance_review,
            governance_verification=governance_verification,
        )
    )
    verified_governance = _verify_governance_review(
        governance_review=governance_review,
        verification=governance_verification,
    )

    if (
        definition.qualification_id != policy_definition.qualification_id
        or definition.qualification_version
        != policy_definition.qualification_version
    ):
        raise HveeContractError(
            "qualification authorization identity does not match policy"
        )
    if definition.policy_sha256 != verified_policy.sha256:
        raise HveeContractError(
            "qualification authorization does not bind the policy"
        )
    if definition.governance_review_sha256 != verified_governance.sha256:
        raise HveeContractError(
            "qualification authorization does not bind governance review"
        )
    if definition.authority_key_id != policy_definition.authority.key_id:
        raise HveeContractError(
            "qualification authorization authority does not match policy"
        )

    payload: dict[str, object] = {
        "schema_version": (
            CRITICAL_NUMBER_PRODUCTION_QUALIFICATION_AUTHORIZATION_SCHEMA_VERSION
        ),
        "qualification_profile": {
            "key": CRITICAL_NUMBER_PRODUCTION_QUALIFICATION_KEY,
            "version": CRITICAL_NUMBER_PRODUCTION_QUALIFICATION_VERSION,
            "artifact": "production_qualification_authorization",
        },
        "bindings": {
            "qualification_policy_sha256": verified_policy.sha256,
            "governance_review": _governance_binding(verified_governance),
            "scope": _scope_snapshot(policy_definition.scope),
        },
        "authorization": {
            "qualification_id": definition.qualification_id,
            "qualification_version": definition.qualification_version,
            "authority_key_id": definition.authority_key_id,
            "authorization_record_sha256": (
                definition.authorization_record_sha256
            ),
            "issuance_attestation_sha256": (
                definition.issuance_attestation_sha256
            ),
            "effective_at_utc": policy_definition.effective_at_utc,
            "expires_at_utc": policy_definition.expires_at_utc,
        },
        "controls": {
            "validity_policy_sha256": (
                policy_definition.validity_policy_sha256
            ),
            "requalification_policy_sha256": (
                policy_definition.requalification_policy_sha256
            ),
            "revocation_policy_sha256": (
                policy_definition.revocation_policy_sha256
            ),
            "requalification_triggers": [
                trigger.value
                for trigger
                in CRITICAL_NUMBER_PRODUCTION_REQUALIFICATION_TRIGGERS_V1
            ],
        },
        "sealed_evidence": {
            "qualification_policy_sha256": verified_policy.sha256,
            "governance_review_sha256": verified_governance.sha256,
            "complete_governance_chain_reverified": True,
            "qualification_policy_reverified": True,
        },
        "authority": _authorization_boundary(),
        "confidentiality": {
            "governance_review_payload_in_artifact": False,
            "qualification_readiness_payload_in_artifact": False,
            "private_case_content_in_artifact": False,
            "production_case_commitments_in_artifact": False,
            "cross_set_linkage_tokens_in_artifact": False,
            "authorization_record_contents_in_artifact": False,
            "opaque_commitments_and_scope_only": True,
        },
    }

    return ASRCriticalNumberProductionQualificationAuthorizationBundle(
        payload=payload,
        sha256=calculate_critical_number_production_qualification_sha256(
            payload
        ),
    )


def verify_critical_number_production_qualification_authorization_v1(
    *,
    payload: object,
    expected_sha256: object,
    policy: ASRCriticalNumberProductionQualificationPolicyBundle,
    policy_definition: ASRCriticalNumberProductionQualificationPolicyDefinition,
    governance_review: ASRCriticalNumberGovernanceReviewBundle,
    governance_verification: ASRCriticalNumberGovernanceReviewVerificationContext,
    definition: (
        ASRCriticalNumberProductionQualificationAuthorizationDefinition
    ),
) -> ASRCriticalNumberProductionQualificationAuthorizationBundle:
    """Rebuild the production qualification and require exact equality."""

    expected_digest = _require_sha256(
        name="production qualification authorization SHA-256",
        value=expected_sha256,
    )
    supplied = _require_dict(
        name="production qualification authorization payload",
        value=payload,
    )
    if calculate_critical_number_production_qualification_sha256(
        supplied
    ) != expected_digest:
        raise HveeContractError(
            "production qualification authorization does not match "
            "expected SHA-256"
        )

    rebuilt = (
        build_critical_number_production_qualification_authorization_v1(
            policy=policy,
            policy_definition=policy_definition,
            governance_review=governance_review,
            governance_verification=governance_verification,
            definition=definition,
        )
    )
    if supplied != rebuilt.payload or expected_digest != rebuilt.sha256:
        raise HveeContractError(
            "production qualification authorization does not match "
            "its bound evidence"
        )
    return rebuilt

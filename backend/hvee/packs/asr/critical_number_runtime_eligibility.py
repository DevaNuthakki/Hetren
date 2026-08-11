"""Runtime eligibility for Critical Number production qualification v1.

This layer evaluates whether an already-issued production qualification may be
used for one requested scope at one explicitly supplied point in time and
state.

It does not issue qualification, query a wall clock, query revocation
infrastructure, infer requalification events, grant release-enforcement
authority, or modify an official release verdict.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.critical_number_governance_review import (
    ASRCriticalNumberGovernanceReviewBundle,
)
from hvee.packs.asr.critical_number_production_qualification import (
    CRITICAL_NUMBER_PRODUCTION_QUALIFICATION_KEY,
    CRITICAL_NUMBER_PRODUCTION_QUALIFICATION_VERSION,
    CRITICAL_NUMBER_PRODUCTION_REQUALIFICATION_TRIGGERS_V1,
    ASRCriticalNumberGovernanceReviewVerificationContext,
    ASRCriticalNumberProductionQualificationAuthorizationBundle,
    ASRCriticalNumberProductionQualificationAuthorizationDefinition,
    ASRCriticalNumberProductionQualificationPolicyBundle,
    ASRCriticalNumberProductionQualificationPolicyDefinition,
    ASRCriticalNumberProductionQualificationScope,
    ASRCriticalNumberProductionUseCategory,
    ASRCriticalNumberRequalificationTrigger,
    verify_critical_number_production_qualification_authorization_v1,
)


CRITICAL_NUMBER_RUNTIME_ELIGIBILITY_SCHEMA_VERSION = 1
CRITICAL_NUMBER_RUNTIME_ELIGIBILITY_KEY = (
    "hetren.asr.critical-number-runtime-eligibility.en-us"
)
CRITICAL_NUMBER_RUNTIME_ELIGIBILITY_VERSION = "1.0.0"


class ASRCriticalNumberRuntimeEligibilityResult(StrEnum):
    """Deterministic runtime disposition for a qualified evaluator."""

    ELIGIBLE = "eligible"
    NOT_YET_EFFECTIVE = "not_yet_effective"
    EXPIRED = "expired"
    REVOKED = "revoked"
    REQUALIFICATION_REQUIRED = "requalification_required"
    SCOPE_MISMATCH = "scope_mismatch"


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberProductionQualificationVerificationContext:
    """Evidence required to reconstruct the production authorization."""

    policy: ASRCriticalNumberProductionQualificationPolicyBundle
    policy_definition: ASRCriticalNumberProductionQualificationPolicyDefinition
    governance_review: ASRCriticalNumberGovernanceReviewBundle
    governance_verification: ASRCriticalNumberGovernanceReviewVerificationContext
    authorization_definition: (
        ASRCriticalNumberProductionQualificationAuthorizationDefinition
    )


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberRuntimeRequestedScope:
    """Caller-requested use scope.

    Unlike the qualification scope, this object intentionally permits a scope
    that does not match the authorized scope. A mismatch is a runtime result,
    not a contract error.
    """

    evaluator_key: str
    evaluator_version: str
    evaluation_type: str
    evaluation_profile_key: str
    evaluation_profile_version: str
    language: str
    locale: str
    production_use_category: ASRCriticalNumberProductionUseCategory

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
                name=f"runtime requested scope {name}",
                value=value,
            )

        if not isinstance(
            self.production_use_category,
            ASRCriticalNumberProductionUseCategory,
        ):
            raise HveeContractError(
                "runtime requested scope requires a versioned use category"
            )


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberRuntimeRevocationState:
    """Caller-supplied revocation history for this authorization."""

    revoked: bool
    revoked_at_utc: str | None = None
    revocation_record_sha256: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.revoked, bool):
            raise HveeContractError(
                "runtime revocation state requires a boolean revoked flag"
            )

        if self.revoked:
            _require_utc_timestamp(
                name="runtime revocation time",
                value=self.revoked_at_utc,
            )
            _require_sha256(
                name="runtime revocation record",
                value=self.revocation_record_sha256,
            )
            return

        if (
            self.revoked_at_utc is not None
            or self.revocation_record_sha256 is not None
        ):
            raise HveeContractError(
                "non-revoked runtime state cannot contain revocation evidence"
            )


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberRuntimeRequalificationEvent:
    """Opaque evidence that one versioned requalification trigger occurred."""

    trigger: ASRCriticalNumberRequalificationTrigger
    triggered_at_utc: str
    evidence_record_sha256: str

    def __post_init__(self) -> None:
        if (
            not isinstance(
                self.trigger,
                ASRCriticalNumberRequalificationTrigger,
            )
            or self.trigger
            not in CRITICAL_NUMBER_PRODUCTION_REQUALIFICATION_TRIGGERS_V1
        ):
            raise HveeContractError(
                "runtime requalification event requires a v1 trigger"
            )

        _require_utc_timestamp(
            name="runtime requalification trigger time",
            value=self.triggered_at_utc,
        )
        _require_sha256(
            name="runtime requalification evidence record",
            value=self.evidence_record_sha256,
        )


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberRuntimeEligibilityDefinition:
    """Replayable caller-supplied runtime state."""

    evaluation_id: str
    evaluation_version: str
    evaluated_at_utc: str
    requested_scope: ASRCriticalNumberRuntimeRequestedScope
    revocation: ASRCriticalNumberRuntimeRevocationState
    requalification_events: tuple[
        ASRCriticalNumberRuntimeRequalificationEvent,
        ...,
    ] = ()

    def __post_init__(self) -> None:
        _require_identifier(
            name="runtime eligibility evaluation id",
            value=self.evaluation_id,
        )
        _require_version(
            name="runtime eligibility evaluation version",
            value=self.evaluation_version,
        )
        _require_utc_timestamp(
            name="runtime eligibility evaluated time",
            value=self.evaluated_at_utc,
        )

        if not isinstance(
            self.requested_scope,
            ASRCriticalNumberRuntimeRequestedScope,
        ):
            raise HveeContractError(
                "runtime eligibility requires a requested scope"
            )
        if not isinstance(
            self.revocation,
            ASRCriticalNumberRuntimeRevocationState,
        ):
            raise HveeContractError(
                "runtime eligibility requires revocation state"
            )
        if (
            not isinstance(self.requalification_events, tuple)
            or any(
                not isinstance(
                    event,
                    ASRCriticalNumberRuntimeRequalificationEvent,
                )
                for event in self.requalification_events
            )
        ):
            raise HveeContractError(
                "runtime eligibility requalification events must be a tuple"
            )

        triggers = tuple(
            event.trigger for event in self.requalification_events
        )
        if len(set(triggers)) != len(triggers):
            raise HveeContractError(
                "runtime eligibility cannot contain duplicate "
                "requalification triggers"
            )


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberRuntimeEligibilityBundle:
    """Sealed deterministic runtime-eligibility evaluation."""

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
            "critical-number runtime eligibility must be deterministic JSON"
        ) from exc


def calculate_critical_number_runtime_eligibility_sha256(
    payload: object,
) -> str:
    """Return canonical SHA-256 for a runtime-eligibility artifact."""

    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _requested_scope_snapshot(
    scope: ASRCriticalNumberRuntimeRequestedScope,
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
    }


def _authorized_scope_snapshot(
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


def _scope_matches(
    *,
    requested: ASRCriticalNumberRuntimeRequestedScope,
    authorized: ASRCriticalNumberProductionQualificationScope,
) -> bool:
    return (
        requested.evaluator_key == authorized.evaluator_key
        and requested.evaluator_version == authorized.evaluator_version
        and requested.evaluation_type == authorized.evaluation_type
        and requested.evaluation_profile_key
        == authorized.evaluation_profile_key
        and requested.evaluation_profile_version
        == authorized.evaluation_profile_version
        and requested.language == authorized.language
        and requested.locale == authorized.locale
        and requested.production_use_category
        == authorized.production_use_category
    )


def _revocation_snapshot(
    revocation: ASRCriticalNumberRuntimeRevocationState,
) -> dict[str, object]:
    return {
        "revoked": revocation.revoked,
        "revoked_at_utc": revocation.revoked_at_utc,
        "revocation_record_sha256": revocation.revocation_record_sha256,
    }


def _requalification_event_snapshot(
    event: ASRCriticalNumberRuntimeRequalificationEvent,
) -> dict[str, object]:
    return {
        "trigger": event.trigger.value,
        "triggered_at_utc": event.triggered_at_utc,
        "evidence_record_sha256": event.evidence_record_sha256,
    }


def _verify_production_authorization(
    *,
    authorization: ASRCriticalNumberProductionQualificationAuthorizationBundle,
    verification: ASRCriticalNumberProductionQualificationVerificationContext,
) -> ASRCriticalNumberProductionQualificationAuthorizationBundle:
    if not isinstance(
        authorization,
        ASRCriticalNumberProductionQualificationAuthorizationBundle,
    ):
        raise HveeContractError(
            "runtime eligibility requires production qualification "
            "authorization"
        )
    if not isinstance(
        verification,
        ASRCriticalNumberProductionQualificationVerificationContext,
    ):
        raise HveeContractError(
            "runtime eligibility requires production qualification "
            "verification context"
        )

    verified = (
        verify_critical_number_production_qualification_authorization_v1(
            payload=authorization.payload,
            expected_sha256=authorization.sha256,
            policy=verification.policy,
            policy_definition=verification.policy_definition,
            governance_review=verification.governance_review,
            governance_verification=verification.governance_verification,
            definition=verification.authorization_definition,
        )
    )

    expected_authority = {
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
    if verified.payload.get("authority") != expected_authority:
        raise HveeContractError(
            "runtime eligibility requires a valid scoped production "
            "qualification"
        )

    return verified


def _authorization_binding(
    authorization: ASRCriticalNumberProductionQualificationAuthorizationBundle,
) -> dict[str, object]:
    bindings = _require_dict(
        name="production qualification bindings",
        value=authorization.payload.get("bindings"),
    )
    return {
        "profile_key": CRITICAL_NUMBER_PRODUCTION_QUALIFICATION_KEY,
        "profile_version": CRITICAL_NUMBER_PRODUCTION_QUALIFICATION_VERSION,
        "sha256": authorization.sha256,
        "qualification_policy_sha256": _require_sha256(
            name="runtime qualification policy SHA-256",
            value=bindings.get("qualification_policy_sha256"),
        ),
    }


def _active_revocation(
    *,
    revocation: ASRCriticalNumberRuntimeRevocationState,
    evaluated_at: datetime,
) -> bool:
    if not revocation.revoked:
        return False

    revoked_at = _require_utc_timestamp(
        name="runtime revocation time",
        value=revocation.revoked_at_utc,
    )
    return revoked_at <= evaluated_at


def _active_requalification_events(
    *,
    events: tuple[ASRCriticalNumberRuntimeRequalificationEvent, ...],
    evaluated_at: datetime,
) -> tuple[ASRCriticalNumberRuntimeRequalificationEvent, ...]:
    return tuple(
        event
        for event in events
        if _require_utc_timestamp(
            name="runtime requalification trigger time",
            value=event.triggered_at_utc,
        )
        <= evaluated_at
    )


def _resolve_runtime_result(
    *,
    definition: ASRCriticalNumberRuntimeEligibilityDefinition,
    authorized_scope: ASRCriticalNumberProductionQualificationScope,
    effective_at_utc: str,
    expires_at_utc: str,
) -> tuple[
    ASRCriticalNumberRuntimeEligibilityResult,
    tuple[ASRCriticalNumberRuntimeRequalificationEvent, ...],
]:
    evaluated_at = _require_utc_timestamp(
        name="runtime eligibility evaluated time",
        value=definition.evaluated_at_utc,
    )

    if not _scope_matches(
        requested=definition.requested_scope,
        authorized=authorized_scope,
    ):
        return (
            ASRCriticalNumberRuntimeEligibilityResult.SCOPE_MISMATCH,
            (),
        )

    if _active_revocation(
        revocation=definition.revocation,
        evaluated_at=evaluated_at,
    ):
        return (
            ASRCriticalNumberRuntimeEligibilityResult.REVOKED,
            (),
        )

    active_events = _active_requalification_events(
        events=definition.requalification_events,
        evaluated_at=evaluated_at,
    )
    if active_events:
        return (
            ASRCriticalNumberRuntimeEligibilityResult
            .REQUALIFICATION_REQUIRED,
            active_events,
        )

    effective_at = _require_utc_timestamp(
        name="production qualification effective time",
        value=effective_at_utc,
    )
    expires_at = _require_utc_timestamp(
        name="production qualification expiration time",
        value=expires_at_utc,
    )

    if evaluated_at < effective_at:
        return (
            ASRCriticalNumberRuntimeEligibilityResult.NOT_YET_EFFECTIVE,
            (),
        )

    if evaluated_at >= expires_at:
        return (
            ASRCriticalNumberRuntimeEligibilityResult.EXPIRED,
            (),
        )

    return (
        ASRCriticalNumberRuntimeEligibilityResult.ELIGIBLE,
        (),
    )


def build_critical_number_runtime_eligibility_v1(
    *,
    authorization: ASRCriticalNumberProductionQualificationAuthorizationBundle,
    authorization_verification: (
        ASRCriticalNumberProductionQualificationVerificationContext
    ),
    definition: ASRCriticalNumberRuntimeEligibilityDefinition,
) -> ASRCriticalNumberRuntimeEligibilityBundle:
    """Evaluate one replayable runtime-eligibility state."""

    if not isinstance(
        definition,
        ASRCriticalNumberRuntimeEligibilityDefinition,
    ):
        raise HveeContractError(
            "runtime eligibility requires an evaluation definition"
        )

    verified_authorization = _verify_production_authorization(
        authorization=authorization,
        verification=authorization_verification,
    )

    policy_definition = authorization_verification.policy_definition
    authorized_scope = policy_definition.scope

    result, active_events = _resolve_runtime_result(
        definition=definition,
        authorized_scope=authorized_scope,
        effective_at_utc=policy_definition.effective_at_utc,
        expires_at_utc=policy_definition.expires_at_utc,
    )

    runtime_eligible = (
        result == ASRCriticalNumberRuntimeEligibilityResult.ELIGIBLE
    )

    payload: dict[str, object] = {
        "schema_version": CRITICAL_NUMBER_RUNTIME_ELIGIBILITY_SCHEMA_VERSION,
        "runtime_profile": {
            "key": CRITICAL_NUMBER_RUNTIME_ELIGIBILITY_KEY,
            "version": CRITICAL_NUMBER_RUNTIME_ELIGIBILITY_VERSION,
            "artifact": "runtime_qualification_eligibility",
        },
        "bindings": {
            "production_qualification_authorization": (
                _authorization_binding(verified_authorization)
            ),
            "authorized_scope": _authorized_scope_snapshot(
                authorized_scope
            ),
        },
        "evaluation": {
            "evaluation_id": definition.evaluation_id,
            "evaluation_version": definition.evaluation_version,
            "evaluated_at_utc": definition.evaluated_at_utc,
            "requested_scope": _requested_scope_snapshot(
                definition.requested_scope
            ),
            "scope_matches_authorization": _scope_matches(
                requested=definition.requested_scope,
                authorized=authorized_scope,
            ),
            "effective_at_utc": policy_definition.effective_at_utc,
            "expires_at_utc": policy_definition.expires_at_utc,
            "expiration_is_exclusive": True,
            "result": result.value,
        },
        "runtime_state": {
            "revocation": _revocation_snapshot(definition.revocation),
            "requalification_events": [
                _requalification_event_snapshot(event)
                for event in definition.requalification_events
            ],
            "active_requalification_events": [
                _requalification_event_snapshot(event)
                for event in active_events
            ],
            "caller_supplied_state_only": True,
            "wall_clock_consulted_during_build": False,
            "external_revocation_source_queried": False,
            "external_requalification_source_queried": False,
        },
        "sealed_evidence": {
            "production_qualification_authorization_sha256": (
                verified_authorization.sha256
            ),
            "production_qualification_reverified": True,
            "complete_upstream_chain_reverified": True,
        },
        "authority": {
            "production_qualified": True,
            "runtime_eligibility_evaluated": True,
            "runtime_eligible": runtime_eligible,
            "runtime_result": result.value,
            "certification_issued": False,
            "release_enforcement_eligible": False,
            "official_release_verdict_modified": False,
        },
        "confidentiality": {
            "production_qualification_payload_in_artifact": False,
            "governance_review_payload_in_artifact": False,
            "qualification_readiness_payload_in_artifact": False,
            "private_case_content_in_artifact": False,
            "production_case_commitments_in_artifact": False,
            "cross_set_linkage_tokens_in_artifact": False,
            "revocation_record_contents_in_artifact": False,
            "requalification_record_contents_in_artifact": False,
            "opaque_commitments_scope_and_runtime_state_only": True,
        },
    }

    return ASRCriticalNumberRuntimeEligibilityBundle(
        payload=payload,
        sha256=calculate_critical_number_runtime_eligibility_sha256(
            payload
        ),
    )


def verify_critical_number_runtime_eligibility_v1(
    *,
    payload: object,
    expected_sha256: object,
    authorization: ASRCriticalNumberProductionQualificationAuthorizationBundle,
    authorization_verification: (
        ASRCriticalNumberProductionQualificationVerificationContext
    ),
    definition: ASRCriticalNumberRuntimeEligibilityDefinition,
) -> ASRCriticalNumberRuntimeEligibilityBundle:
    """Rebuild runtime eligibility and require exact equality."""

    expected_digest = _require_sha256(
        name="runtime eligibility SHA-256",
        value=expected_sha256,
    )
    supplied = _require_dict(
        name="runtime eligibility payload",
        value=payload,
    )

    if calculate_critical_number_runtime_eligibility_sha256(
        supplied
    ) != expected_digest:
        raise HveeContractError(
            "runtime eligibility does not match expected SHA-256"
        )

    rebuilt = build_critical_number_runtime_eligibility_v1(
        authorization=authorization,
        authorization_verification=authorization_verification,
        definition=definition,
    )
    if supplied != rebuilt.payload or expected_digest != rebuilt.sha256:
        raise HveeContractError(
            "runtime eligibility does not match its bound evidence and state"
        )

    return rebuilt

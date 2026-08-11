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
from hvee.packs.asr.critical_number_production_qualification import (
    ASRCriticalNumberProductionQualificationAuthorizationBundle,
    ASRCriticalNumberRequalificationTrigger,
    calculate_critical_number_production_qualification_sha256,
)
from hvee.packs.asr.critical_number_runtime_eligibility import (
    CRITICAL_NUMBER_RUNTIME_ELIGIBILITY_KEY,
    CRITICAL_NUMBER_RUNTIME_ELIGIBILITY_SCHEMA_VERSION,
    CRITICAL_NUMBER_RUNTIME_ELIGIBILITY_VERSION,
    ASRCriticalNumberProductionQualificationVerificationContext,
    ASRCriticalNumberRuntimeEligibilityBundle,
    ASRCriticalNumberRuntimeEligibilityDefinition,
    ASRCriticalNumberRuntimeEligibilityResult,
    ASRCriticalNumberRuntimeRequestedScope,
    ASRCriticalNumberRuntimeRequalificationEvent,
    ASRCriticalNumberRuntimeRevocationState,
    build_critical_number_runtime_eligibility_v1,
    calculate_critical_number_runtime_eligibility_sha256,
    verify_critical_number_runtime_eligibility_v1,
)


def _load_sibling_test_module(filename: str, module_name: str) -> ModuleType:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load test fixture module: {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_QUALIFICATION = _load_sibling_test_module(
    "test_critical_number_production_qualification.py",
    "_hetren_runtime_eligibility_qualification_fixtures",
)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _requested_scope(authorized_scope, **changes):
    values = {
        "evaluator_key": authorized_scope.evaluator_key,
        "evaluator_version": authorized_scope.evaluator_version,
        "evaluation_type": authorized_scope.evaluation_type,
        "evaluation_profile_key": authorized_scope.evaluation_profile_key,
        "evaluation_profile_version": (
            authorized_scope.evaluation_profile_version
        ),
        "language": authorized_scope.language,
        "locale": authorized_scope.locale,
        "production_use_category": (
            authorized_scope.production_use_category
        ),
    }
    values.update(changes)
    return ASRCriticalNumberRuntimeRequestedScope(**values)


def _revocation(
    *,
    revoked: bool = False,
    revoked_at_utc: str | None = None,
    record: str = "runtime-revocation-record",
):
    return ASRCriticalNumberRuntimeRevocationState(
        revoked=revoked,
        revoked_at_utc=revoked_at_utc,
        revocation_record_sha256=(
            _digest(record) if revoked else None
        ),
    )


def _event(
    *,
    trigger=ASRCriticalNumberRequalificationTrigger.MATERIAL_EVALUATOR_REGRESSION,
    triggered_at_utc: str = "2026-11-15T00:00:00Z",
    record: str = "runtime-requalification-record",
):
    return ASRCriticalNumberRuntimeRequalificationEvent(
        trigger=trigger,
        triggered_at_utc=triggered_at_utc,
        evidence_record_sha256=_digest(record),
    )


@lru_cache(maxsize=None)
def _runtime_context(candidate_violation: bool = False):
    qualification = _QUALIFICATION._qualification_context(
        candidate_violation
    )
    authorization = _QUALIFICATION._build_authorization(qualification)

    verification = (
        ASRCriticalNumberProductionQualificationVerificationContext(
            policy=qualification["policy"],
            policy_definition=qualification["policy_definition"],
            governance_review=qualification["governance_review"],
            governance_verification=(
                qualification["governance_verification"]
            ),
            authorization_definition=(
                qualification["authorization_definition"]
            ),
        )
    )

    authorized_scope = qualification["policy_definition"].scope

    definition = ASRCriticalNumberRuntimeEligibilityDefinition(
        evaluation_id="critical-number-runtime-eligibility-001",
        evaluation_version="1.0.0",
        evaluated_at_utc="2026-12-01T00:00:00Z",
        requested_scope=_requested_scope(authorized_scope),
        revocation=_revocation(),
        requalification_events=(),
    )

    return {
        "qualification": qualification,
        "authorization": authorization,
        "verification": verification,
        "authorized_scope": authorized_scope,
        "definition": definition,
    }


def _build(context, definition=None):
    return build_critical_number_runtime_eligibility_v1(
        authorization=context["authorization"],
        authorization_verification=context["verification"],
        definition=definition or context["definition"],
    )


def test_runtime_eligibility_is_deterministic_and_sealed():
    context = _runtime_context()

    first = _build(context)
    second = _build(context)

    assert first == second
    assert first.sha256 == (
        calculate_critical_number_runtime_eligibility_sha256(
            first.payload
        )
    )
    assert first.payload["schema_version"] == (
        CRITICAL_NUMBER_RUNTIME_ELIGIBILITY_SCHEMA_VERSION
    )
    assert first.payload["runtime_profile"] == {
        "key": CRITICAL_NUMBER_RUNTIME_ELIGIBILITY_KEY,
        "version": CRITICAL_NUMBER_RUNTIME_ELIGIBILITY_VERSION,
        "artifact": "runtime_qualification_eligibility",
    }


def test_runtime_eligibility_verifier_rebuilds_full_authority_chain():
    context = _runtime_context()
    result = _build(context)

    verified = verify_critical_number_runtime_eligibility_v1(
        payload=result.payload,
        expected_sha256=result.sha256,
        authorization=context["authorization"],
        authorization_verification=context["verification"],
        definition=context["definition"],
    )

    assert verified == result


def test_runtime_eligible_inside_valid_window():
    context = _runtime_context()
    result = _build(context)

    assert result.payload["evaluation"]["result"] == (
        ASRCriticalNumberRuntimeEligibilityResult.ELIGIBLE.value
    )
    assert result.payload["authority"] == {
        "production_qualified": True,
        "runtime_eligibility_evaluated": True,
        "runtime_eligible": True,
        "runtime_result": "eligible",
        "certification_issued": False,
        "release_enforcement_eligible": False,
        "official_release_verdict_modified": False,
    }


def test_runtime_not_yet_effective():
    context = _runtime_context()
    definition = replace(
        context["definition"],
        evaluated_at_utc="2026-08-09T23:59:59Z",
    )

    result = _build(context, definition)

    assert result.payload["evaluation"]["result"] == (
        ASRCriticalNumberRuntimeEligibilityResult
        .NOT_YET_EFFECTIVE.value
    )
    assert result.payload["authority"]["production_qualified"] is True
    assert result.payload["authority"]["runtime_eligible"] is False


def test_runtime_exact_effective_time_is_eligible():
    context = _runtime_context()
    definition = replace(
        context["definition"],
        evaluated_at_utc="2026-08-10T00:00:00Z",
    )

    result = _build(context, definition)

    assert result.payload["evaluation"]["result"] == "eligible"


def test_runtime_expired_after_validity_window():
    context = _runtime_context()
    definition = replace(
        context["definition"],
        evaluated_at_utc="2027-08-10T00:00:01Z",
    )

    result = _build(context, definition)

    assert result.payload["evaluation"]["result"] == (
        ASRCriticalNumberRuntimeEligibilityResult.EXPIRED.value
    )
    assert result.payload["authority"]["production_qualified"] is True
    assert result.payload["authority"]["runtime_eligible"] is False


def test_runtime_expiration_boundary_is_exclusive():
    context = _runtime_context()
    definition = replace(
        context["definition"],
        evaluated_at_utc="2027-08-10T00:00:00Z",
    )

    result = _build(context, definition)

    assert result.payload["evaluation"]["result"] == "expired"
    assert result.payload["evaluation"]["expiration_is_exclusive"] is True


def test_runtime_active_revocation_is_ineligible():
    context = _runtime_context()
    definition = replace(
        context["definition"],
        revocation=_revocation(
            revoked=True,
            revoked_at_utc="2026-11-01T00:00:00Z",
        ),
    )

    result = _build(context, definition)

    assert result.payload["evaluation"]["result"] == (
        ASRCriticalNumberRuntimeEligibilityResult.REVOKED.value
    )
    assert result.payload["authority"]["production_qualified"] is True
    assert result.payload["authority"]["runtime_eligible"] is False


def test_runtime_revocation_at_exact_evaluation_time_is_active():
    context = _runtime_context()
    definition = replace(
        context["definition"],
        revocation=_revocation(
            revoked=True,
            revoked_at_utc="2026-12-01T00:00:00Z",
        ),
    )

    result = _build(context, definition)

    assert result.payload["evaluation"]["result"] == "revoked"


def test_future_revocation_does_not_change_historical_replay():
    context = _runtime_context()
    definition = replace(
        context["definition"],
        revocation=_revocation(
            revoked=True,
            revoked_at_utc="2026-12-02T00:00:00Z",
        ),
    )

    result = _build(context, definition)

    assert result.payload["evaluation"]["result"] == "eligible"
    assert result.payload["runtime_state"]["revocation"]["revoked"] is True


def test_active_requalification_trigger_requires_requalification():
    context = _runtime_context()
    event = _event(
        triggered_at_utc="2026-11-15T00:00:00Z",
    )
    definition = replace(
        context["definition"],
        requalification_events=(event,),
    )

    result = _build(context, definition)

    assert result.payload["evaluation"]["result"] == (
        ASRCriticalNumberRuntimeEligibilityResult
        .REQUALIFICATION_REQUIRED.value
    )
    assert result.payload["authority"]["runtime_eligible"] is False
    assert result.payload["runtime_state"][
        "active_requalification_events"
    ] == [
        {
            "trigger": "material_evaluator_regression",
            "triggered_at_utc": "2026-11-15T00:00:00Z",
            "evidence_record_sha256": event.evidence_record_sha256,
        }
    ]


def test_requalification_trigger_at_exact_evaluation_time_is_active():
    context = _runtime_context()
    definition = replace(
        context["definition"],
        requalification_events=(
            _event(
                triggered_at_utc="2026-12-01T00:00:00Z",
            ),
        ),
    )

    result = _build(context, definition)

    assert result.payload["evaluation"]["result"] == (
        "requalification_required"
    )


def test_future_requalification_event_does_not_change_historical_replay():
    context = _runtime_context()
    event = _event(
        triggered_at_utc="2026-12-02T00:00:00Z",
    )
    definition = replace(
        context["definition"],
        requalification_events=(event,),
    )

    result = _build(context, definition)

    assert result.payload["evaluation"]["result"] == "eligible"
    assert result.payload["runtime_state"][
        "active_requalification_events"
    ] == []


def test_runtime_scope_mismatch_does_not_invalidate_qualification():
    context = _runtime_context()
    definition = replace(
        context["definition"],
        requested_scope=_requested_scope(
            context["authorized_scope"],
            locale="en-GB",
        ),
    )

    result = _build(context, definition)

    assert result.payload["evaluation"]["result"] == (
        ASRCriticalNumberRuntimeEligibilityResult.SCOPE_MISMATCH.value
    )
    assert result.payload["evaluation"][
        "scope_matches_authorization"
    ] is False
    assert result.payload["authority"]["production_qualified"] is True
    assert result.payload["authority"]["runtime_eligible"] is False


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("evaluator_key", "different-evaluator"),
        ("evaluator_version", "2.0.0"),
        ("evaluation_type", "tts"),
        ("evaluation_profile_key", "different-profile"),
        ("evaluation_profile_version", "2.0.0"),
        ("language", "de"),
        ("locale", "de-DE"),
    ),
)
def test_each_runtime_scope_dimension_is_enforced(field, value):
    context = _runtime_context()
    definition = replace(
        context["definition"],
        requested_scope=_requested_scope(
            context["authorized_scope"],
            **{field: value},
        ),
    )

    result = _build(context, definition)

    assert result.payload["evaluation"]["result"] == "scope_mismatch"


def test_scope_mismatch_has_highest_runtime_precedence():
    context = _runtime_context()
    definition = replace(
        context["definition"],
        evaluated_at_utc="2027-08-10T00:00:00Z",
        requested_scope=_requested_scope(
            context["authorized_scope"],
            locale="en-GB",
        ),
        revocation=_revocation(
            revoked=True,
            revoked_at_utc="2026-10-01T00:00:00Z",
        ),
        requalification_events=(
            _event(
                triggered_at_utc="2026-11-01T00:00:00Z",
            ),
        ),
    )

    result = _build(context, definition)

    assert result.payload["evaluation"]["result"] == "scope_mismatch"


def test_revocation_dominates_requalification_and_time_state():
    context = _runtime_context()
    definition = replace(
        context["definition"],
        evaluated_at_utc="2027-08-10T00:00:00Z",
        revocation=_revocation(
            revoked=True,
            revoked_at_utc="2026-10-01T00:00:00Z",
        ),
        requalification_events=(
            _event(
                triggered_at_utc="2026-11-01T00:00:00Z",
            ),
        ),
    )

    result = _build(context, definition)

    assert result.payload["evaluation"]["result"] == "revoked"


def test_requalification_dominates_time_state():
    context = _runtime_context()
    definition = replace(
        context["definition"],
        evaluated_at_utc="2027-08-10T00:00:00Z",
        requalification_events=(
            _event(
                triggered_at_utc="2026-11-01T00:00:00Z",
            ),
        ),
    )

    result = _build(context, definition)

    assert result.payload["evaluation"]["result"] == (
        "requalification_required"
    )


def test_future_revocation_does_not_hide_expiration():
    context = _runtime_context()
    definition = replace(
        context["definition"],
        evaluated_at_utc="2027-08-10T00:00:00Z",
        revocation=_revocation(
            revoked=True,
            revoked_at_utc="2027-08-11T00:00:00Z",
        ),
    )

    result = _build(context, definition)

    assert result.payload["evaluation"]["result"] == "expired"


def test_future_requalification_event_does_not_hide_expiration():
    context = _runtime_context()
    definition = replace(
        context["definition"],
        evaluated_at_utc="2027-08-10T00:00:00Z",
        requalification_events=(
            _event(
                triggered_at_utc="2027-08-11T00:00:00Z",
            ),
        ),
    )

    result = _build(context, definition)

    assert result.payload["evaluation"]["result"] == "expired"


def test_non_revoked_state_cannot_contain_revocation_evidence():
    with pytest.raises(
        HveeContractError,
        match="cannot contain revocation evidence",
    ):
        ASRCriticalNumberRuntimeRevocationState(
            revoked=False,
            revoked_at_utc="2026-11-01T00:00:00Z",
            revocation_record_sha256=_digest("revocation"),
        )


def test_revoked_state_requires_time_and_record():
    with pytest.raises(
        HveeContractError,
        match="canonical UTC timestamp",
    ):
        ASRCriticalNumberRuntimeRevocationState(
            revoked=True,
            revoked_at_utc=None,
            revocation_record_sha256=_digest("revocation"),
        )

    with pytest.raises(
        HveeContractError,
        match="lowercase SHA-256 digest",
    ):
        ASRCriticalNumberRuntimeRevocationState(
            revoked=True,
            revoked_at_utc="2026-11-01T00:00:00Z",
            revocation_record_sha256=None,
        )


def test_duplicate_requalification_triggers_are_rejected():
    context = _runtime_context()

    first = _event(
        triggered_at_utc="2026-10-01T00:00:00Z",
        record="event-one",
    )
    second = _event(
        triggered_at_utc="2026-11-01T00:00:00Z",
        record="event-two",
    )

    with pytest.raises(
        HveeContractError,
        match="duplicate requalification triggers",
    ):
        replace(
            context["definition"],
            requalification_events=(first, second),
        )


@pytest.mark.parametrize(
    "timestamp",
    (
        "2026-12-01",
        "2026-12-01T00:00:00",
        "2026-12-01T00:00:00+00:00",
        "2026-12-01T00:00:00.000Z",
    ),
)
def test_runtime_evaluation_requires_canonical_utc(timestamp):
    context = _runtime_context()

    with pytest.raises(
        HveeContractError,
        match="must use",
    ):
        replace(
            context["definition"],
            evaluated_at_utc=timestamp,
        )


def test_requalification_event_requires_canonical_utc():
    with pytest.raises(
        HveeContractError,
        match="must use",
    ):
        _event(
            triggered_at_utc="2026-11-01T00:00:00+00:00",
        )


def test_runtime_artifact_uses_only_caller_supplied_runtime_state():
    context = _runtime_context()
    result = _build(context)

    assert result.payload["runtime_state"][
        "caller_supplied_state_only"
    ] is True
    assert result.payload["runtime_state"][
        "wall_clock_consulted_during_build"
    ] is False
    assert result.payload["runtime_state"][
        "external_revocation_source_queried"
    ] is False
    assert result.payload["runtime_state"][
        "external_requalification_source_queried"
    ] is False


def test_forged_rehashed_production_authorization_is_rejected():
    context = _runtime_context()

    payload = copy.deepcopy(context["authorization"].payload)
    payload["authority"]["release_enforcement_eligible"] = True

    forged = ASRCriticalNumberProductionQualificationAuthorizationBundle(
        payload=payload,
        sha256=calculate_critical_number_production_qualification_sha256(
            payload
        ),
    )

    with pytest.raises(HveeContractError):
        build_critical_number_runtime_eligibility_v1(
            authorization=forged,
            authorization_verification=context["verification"],
            definition=context["definition"],
        )


def test_runtime_payload_tampering_is_rejected_even_with_recomputed_digest():
    context = _runtime_context()
    result = _build(context)

    payload = copy.deepcopy(result.payload)
    payload["authority"]["release_enforcement_eligible"] = True

    forged = ASRCriticalNumberRuntimeEligibilityBundle(
        payload=payload,
        sha256=calculate_critical_number_runtime_eligibility_sha256(
            payload
        ),
    )

    with pytest.raises(
        HveeContractError,
        match="does not match its bound evidence and state",
    ):
        verify_critical_number_runtime_eligibility_v1(
            payload=forged.payload,
            expected_sha256=forged.sha256,
            authorization=context["authorization"],
            authorization_verification=context["verification"],
            definition=context["definition"],
        )


def test_runtime_wrong_digest_is_rejected():
    context = _runtime_context()
    result = _build(context)

    with pytest.raises(
        HveeContractError,
        match="does not match expected SHA-256",
    ):
        verify_critical_number_runtime_eligibility_v1(
            payload=result.payload,
            expected_sha256=_digest("wrong-runtime-digest"),
            authorization=context["authorization"],
            authorization_verification=context["verification"],
            definition=context["definition"],
        )


@pytest.mark.parametrize(
    "result_kind",
    (
        "not_yet_effective",
        "expired",
        "revoked",
        "requalification_required",
        "scope_mismatch",
    ),
)
def test_ineligible_runtime_results_preserve_historical_qualification(
    result_kind,
):
    context = _runtime_context()

    if result_kind == "not_yet_effective":
        definition = replace(
            context["definition"],
            evaluated_at_utc="2026-08-09T23:59:59Z",
        )
    elif result_kind == "expired":
        definition = replace(
            context["definition"],
            evaluated_at_utc="2027-08-10T00:00:00Z",
        )
    elif result_kind == "revoked":
        definition = replace(
            context["definition"],
            revocation=_revocation(
                revoked=True,
                revoked_at_utc="2026-11-01T00:00:00Z",
            ),
        )
    elif result_kind == "requalification_required":
        definition = replace(
            context["definition"],
            requalification_events=(
                _event(
                    triggered_at_utc="2026-11-01T00:00:00Z",
                ),
            ),
        )
    else:
        definition = replace(
            context["definition"],
            requested_scope=_requested_scope(
                context["authorized_scope"],
                locale="en-GB",
            ),
        )

    result = _build(context, definition)

    assert result.payload["evaluation"]["result"] == result_kind
    assert result.payload["authority"]["production_qualified"] is True
    assert result.payload["authority"]["runtime_eligible"] is False
    assert result.payload["authority"][
        "release_enforcement_eligible"
    ] is False
    assert result.payload["authority"][
        "official_release_verdict_modified"
    ] is False


def test_runtime_eligibility_does_not_copy_confidential_upstream_evidence():
    context = _runtime_context()
    result = _build(context)
    serialized = repr(result.payload)

    evidence = (
        context["qualification"]["governance_context"]["evidence"]
    )

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

    assert result.payload["confidentiality"] == {
        "production_qualification_payload_in_artifact": False,
        "governance_review_payload_in_artifact": False,
        "qualification_readiness_payload_in_artifact": False,
        "private_case_content_in_artifact": False,
        "production_case_commitments_in_artifact": False,
        "cross_set_linkage_tokens_in_artifact": False,
        "revocation_record_contents_in_artifact": False,
        "requalification_record_contents_in_artifact": False,
        "opaque_commitments_scope_and_runtime_state_only": True,
    }


def test_shadow_hypothetical_failure_does_not_become_runtime_gate():
    context = _runtime_context(candidate_violation=True)

    assert context["qualification"]["governance_context"]["readiness"].payload[
        "evidence"
    ]["matched_release_shadow"]["would_change_official_decision"] is True

    result = _build(context)

    assert result.payload["evaluation"]["result"] == "eligible"
    assert result.payload["authority"]["production_qualified"] is True
    assert result.payload["authority"]["runtime_eligible"] is True
    assert result.payload["authority"][
        "release_enforcement_eligible"
    ] is False


def test_runtime_public_exports_are_complete():
    expected = {
        "ASRCriticalNumberProductionQualificationVerificationContext",
        "ASRCriticalNumberRuntimeEligibilityBundle",
        "ASRCriticalNumberRuntimeEligibilityDefinition",
        "ASRCriticalNumberRuntimeEligibilityResult",
        "ASRCriticalNumberRuntimeRequestedScope",
        "ASRCriticalNumberRuntimeRequalificationEvent",
        "ASRCriticalNumberRuntimeRevocationState",
        "CRITICAL_NUMBER_RUNTIME_ELIGIBILITY_KEY",
        "CRITICAL_NUMBER_RUNTIME_ELIGIBILITY_SCHEMA_VERSION",
        "CRITICAL_NUMBER_RUNTIME_ELIGIBILITY_VERSION",
        "build_critical_number_runtime_eligibility_v1",
        "calculate_critical_number_runtime_eligibility_sha256",
        "verify_critical_number_runtime_eligibility_v1",
    }

    assert expected.issubset(set(asr.__all__))
    assert all(hasattr(asr, name) for name in expected)

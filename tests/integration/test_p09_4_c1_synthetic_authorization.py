"""Focused synthetic-only P09.4 authorization preflight tests."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib

import pytest

from packages.engines.behavioral.p09_4_c1_synthetic_authorization import (
    ApprovalDecision,
    OPERATION,
    PROTOCOL_SHA256,
    ROOT_BINDING,
    PreflightCode,
    canonical_synthetic_identity_bytes,
    evaluate_synthetic_c1_preclaim,
    synthetic_identity,
    synthetic_identity_sha256,
    validate_canonical_synthetic_identity_bytes,
)


FIXED_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)

EXPECTED_SHA = (
    "1e99155aaae81f740868692327d86db2be030653d9ddb53800de0a978f148c68"
)


def valid_request():
    return {
        "operation": OPERATION,
        "identity_sha256": synthetic_identity_sha256(),
        "approval_fixture_ref": "synthetic_approval_a",
        "root_binding_id": ROOT_BINDING,
    }


def evaluate(request=None, **overrides):
    kwargs = {
        "request": valid_request() if request is None else request,
        "environment_ready": True,
        "protocol_digest_provider": lambda: PROTOCOL_SHA256,
        "approval_verifier": lambda **_: ApprovalDecision.ACCEPT,
        "fixed_now_utc": FIXED_NOW,
    }
    kwargs.update(overrides)
    return evaluate_synthetic_c1_preclaim(**kwargs)


def assert_rejected(result, code):
    assert result.accepted is False
    assert result.code is code


def test_fixed_identity_has_independent_frozen_vector():
    raw = canonical_synthetic_identity_bytes()
    assert len(raw) == 228
    assert hashlib.sha256(raw).hexdigest() == EXPECTED_SHA
    assert synthetic_identity_sha256() == EXPECTED_SHA
    assert validate_canonical_synthetic_identity_bytes(raw)


def test_insertion_order_does_not_change_canonical_bytes():
    reordered = dict(reversed(list(synthetic_identity().items())))
    assert canonical_synthetic_identity_bytes(reordered) == (
        canonical_synthetic_identity_bytes()
    )


@pytest.mark.parametrize("mutation", [
    lambda v: {k: x for k, x in v.items() if k != "schema"},
    lambda v: {**v, "extra": "value"},
    lambda v: {**v, "study_id": 123},
    lambda v: {**v, "study_id": True},
    lambda v: {**v, "study_version": "protected"},
])
def test_identity_rejects_wrong_fields_and_types(mutation):
    with pytest.raises(ValueError):
        canonical_synthetic_identity_bytes(
            mutation(synthetic_identity())
        )


@pytest.mark.parametrize("mutation", [
    lambda data: bytes.fromhex("efbbbf") + data,
    lambda data: data + bytes([10]),
    lambda data: data + b" ",
    lambda data: data.replace(
        b'"study_version":"synthetic_only"',
        b'"study_version":"protected"',
    ),
])
def test_noncanonical_identity_bytes_rejected(mutation):
    raw = canonical_synthetic_identity_bytes()
    assert not validate_canonical_synthetic_identity_bytes(
        mutation(raw)
    )


@pytest.mark.parametrize("mutation", [
    lambda v: {**v, "extra": "bad"},
    lambda v: {k: x for k, x in v.items()
               if k != "operation"},
    lambda v: {**v, "operation": True},
    lambda v: {**v, "operation": "CREATE_PROTECTED_C1_SEED"},
    lambda v: {**v, "identity_sha256": "invalid"},
    lambda v: {**v, "approval_fixture_ref": "../escape"},
    lambda v: {**v, "output_directory": "/tmp/elsewhere"},
])
def test_invalid_requests_rejected_before_verifier(mutation):
    called = []
    result = evaluate(
        mutation(valid_request()),
        approval_verifier=lambda **kw: called.append(kw),
    )
    assert_rejected(result, PreflightCode.INVALID_REQUEST)
    assert called == []


def test_environment_rejection_precedes_bad_request():
    result = evaluate(
        {"invalid": True},
        environment_ready=False,
    )
    assert_rejected(result, PreflightCode.UNSUPPORTED_ENV)


def test_naive_fixed_clock_is_not_accepted():
    result = evaluate(
        fixed_now_utc=datetime(2026, 1, 1)
    )
    assert_rejected(result, PreflightCode.UNSUPPORTED_ENV)


def test_protocol_mismatch_precedes_identity_mismatch():
    request = valid_request()
    request["identity_sha256"] = "0" * 64
    result = evaluate(
        request,
        protocol_digest_provider=lambda: "f" * 64,
    )
    assert_rejected(result, PreflightCode.PROTOCOL_MISMATCH)


def test_protocol_provider_exception_fails_closed():
    def broken():
        raise RuntimeError("synthetic provider failed")

    assert_rejected(
        evaluate(protocol_digest_provider=broken),
        PreflightCode.INTERNAL_FAILURE,
    )


def test_valid_shape_wrong_identity_rejected():
    request = valid_request()
    request["identity_sha256"] = "0" * 64
    assert_rejected(
        evaluate(request),
        PreflightCode.IDENTITY_MISMATCH,
    )


def test_root_binding_mismatch_rejected_before_verifier():
    request = valid_request()
    request["root_binding_id"] = "another_fixture"
    calls = []
    assert_rejected(
        evaluate(
            request,
            approval_verifier=lambda **kw: calls.append(kw),
        ),
        PreflightCode.ROOT_MISMATCH,
    )
    assert not calls


def test_missing_fixture_rejected_before_verifier():
    request = valid_request()
    request["approval_fixture_ref"] = ""
    calls = []
    assert_rejected(
        evaluate(
            request,
            approval_verifier=lambda **kw: calls.append(kw),
        ),
        PreflightCode.APPROVAL_MISSING,
    )
    assert not calls


@pytest.mark.parametrize("decision, expected", [
    (ApprovalDecision.DENIED, PreflightCode.APPROVAL_DENIED),
    (ApprovalDecision.SCOPE, PreflightCode.APPROVAL_SCOPE),
    (ApprovalDecision.EXPIRED, PreflightCode.APPROVAL_EXPIRED),
    (ApprovalDecision.REPLAY, PreflightCode.APPROVAL_REPLAY),
])
def test_synthetic_verifier_decision_mapping(decision, expected):
    assert_rejected(
        evaluate(
            approval_verifier=lambda **_: decision,
        ),
        expected,
    )


def test_approval_acceptance_returns_preflight_only():
    calls = []

    def verifier(**kwargs):
        calls.append(kwargs)
        return ApprovalDecision.ACCEPT

    result = evaluate(approval_verifier=verifier)
    assert result.accepted is True
    assert result.code is None
    assert len(calls) == 1
    assert calls[0]["operation"] == OPERATION
    assert calls[0]["protocol_sha256"] == PROTOCOL_SHA256
    assert calls[0]["root_binding_id"] == ROOT_BINDING
    assert calls[0]["fixed_now_utc"] == FIXED_NOW


def test_verifier_exception_fails_closed():
    def broken(**kwargs):
        raise RuntimeError("synthetic verifier failure")

    assert_rejected(
        evaluate(approval_verifier=broken),
        PreflightCode.INTERNAL_FAILURE,
    )


@pytest.mark.parametrize("decision", [
    None,
    True,
    "ACCEPT",
])
def test_non_enum_verifier_result_is_rejected(decision):
    assert_rejected(
        evaluate(approval_verifier=lambda **_: decision),
        PreflightCode.INTERNAL_FAILURE,
    )

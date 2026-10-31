"""Synthetic P09.4 C1 authorization preflight.

Development-only. No persistence, randomness, seed generation,
protected scientific authorization, or production entrypoint.

A trusted test harness supplies the verifier, protocol provider,
clock, and environment readiness. A successful result allows
only a later synthetic development step to be considered.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import hashlib
import json
import re


PROTOCOL_SHA256 = (
    "46ea27e825bedbfbd8ee0443173884f904f20881fc929a4c44fae30c550e7621"
)

SCHEMA = "hetren.dev.c1-authorization-identity.v1"
OPERATION = "SIMULATE_C1_AUTHORIZED_CLAIM"
ROOT_BINDING = "hetren-dev-fixture-root-v1"

REQUEST_FIELDS = frozenset({
    "operation",
    "identity_sha256",
    "approval_fixture_ref",
    "root_binding_id",
})

DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}")
FIXTURE_PATTERN = re.compile(r"[a-z][a-z0-9_-]{0,63}")


class ApprovalDecision(str, Enum):
    ACCEPT = "ACCEPT"
    DENIED = "DENIED"
    SCOPE = "SCOPE"
    EXPIRED = "EXPIRED"
    REPLAY = "REPLAY"


class PreflightCode(str, Enum):
    INVALID_REQUEST = "DEV_INVALID_REQUEST"
    UNSUPPORTED_ENV = "DEV_UNSUPPORTED_ENV"
    ROOT_MISMATCH = "DEV_ROOT_MISMATCH"
    IDENTITY_MISMATCH = "DEV_IDENTITY_MISMATCH"
    PROTOCOL_MISMATCH = "DEV_PROTOCOL_MISMATCH"
    APPROVAL_MISSING = "DEV_APPROVAL_MISSING"
    APPROVAL_DENIED = "DEV_APPROVAL_DENIED"
    APPROVAL_SCOPE = "DEV_APPROVAL_SCOPE"
    APPROVAL_EXPIRED = "DEV_APPROVAL_EXPIRED"
    APPROVAL_REPLAY = "DEV_APPROVAL_REPLAY"
    INTERNAL_FAILURE = "DEV_INTERNAL_FAILURE"


@dataclass(frozen=True, slots=True)
class PreflightResult:
    accepted: bool
    code: PreflightCode | None


def synthetic_identity() -> dict[str, str]:
    """Return a fresh copy of the fixed synthetic identity."""
    return {
        "schema": SCHEMA,
        "study_id": "P09.4",
        "study_version": "synthetic_only",
        "purpose": "synthetic_c1_authorization",
        "protocol_sha256": PROTOCOL_SHA256,
    }


def canonical_synthetic_identity_bytes(
    identity: object = None,
) -> bytes:
    """Validate exact fields and serialize deterministically."""
    expected = synthetic_identity()
    value = expected if identity is None else identity

    if type(value) is not dict or set(value) != set(expected):
        raise ValueError("Invalid synthetic identity shape")

    for key, expected_value in expected.items():
        if type(value[key]) is not str or value[key] != expected_value:
            raise ValueError("Invalid synthetic identity value")

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def synthetic_identity_sha256() -> str:
    return hashlib.sha256(
        canonical_synthetic_identity_bytes()
    ).hexdigest()


def validate_canonical_synthetic_identity_bytes(
    candidate: object,
) -> bool:
    """Reject altered JSON, duplicate keys, BOMs and whitespace."""
    if type(candidate) is not bytes:
        return False
    try:
        decoded = json.loads(candidate)
        canonical = canonical_synthetic_identity_bytes(decoded)
    except (ValueError, TypeError, UnicodeError):
        return False
    return candidate == canonical


def _reject(code: PreflightCode) -> PreflightResult:
    return PreflightResult(accepted=False, code=code)


def evaluate_synthetic_c1_preclaim(
    *,
    request: object,
    environment_ready: bool,
    protocol_digest_provider: Callable[[], str],
    approval_verifier: Callable[..., ApprovalDecision],
    fixed_now_utc: datetime,
) -> PreflightResult:
    """Evaluate a synthetic request without claiming identity.

    This is a pure preclaim decision layer. It does not verify
    physical root confinement or execute persistence operations.
    The caller must be a trusted development test harness.
    """

    # Q1 stage 1: trusted harness/environment prerequisites.
    if (
        type(environment_ready) is not bool
        or not environment_ready
        or not callable(protocol_digest_provider)
        or not callable(approval_verifier)
        or not isinstance(fixed_now_utc, datetime)
        or fixed_now_utc.tzinfo is None
        or fixed_now_utc.utcoffset() is None
    ):
        return _reject(PreflightCode.UNSUPPORTED_ENV)

    # Q1 stage 2: strict request schema.
    if (
        type(request) is not dict
        or set(request) != REQUEST_FIELDS
        or any(type(request[key]) is not str for key in REQUEST_FIELDS)
    ):
        return _reject(PreflightCode.INVALID_REQUEST)

    if request["operation"] != OPERATION:
        return _reject(PreflightCode.INVALID_REQUEST)

    if DIGEST_PATTERN.fullmatch(request["identity_sha256"]) is None:
        return _reject(PreflightCode.INVALID_REQUEST)

    fixture_reference = request["approval_fixture_ref"]

    if fixture_reference and (
        FIXTURE_PATTERN.fullmatch(fixture_reference) is None
    ):
        return _reject(PreflightCode.INVALID_REQUEST)

    # Q1 stage 3: trusted frozen protocol binding.
    try:
        observed_protocol = protocol_digest_provider()
    except Exception:
        return _reject(PreflightCode.INTERNAL_FAILURE)

    if (
        type(observed_protocol) is not str
        or observed_protocol != PROTOCOL_SHA256
    ):
        return _reject(PreflightCode.PROTOCOL_MISMATCH)

    # Q1 stage 4: canonical synthetic identity binding.
    if request["identity_sha256"] != synthetic_identity_sha256():
        return _reject(PreflightCode.IDENTITY_MISMATCH)

    # Q1 stage 5: logical synthetic fixture-root binding.
    # This does not establish physical filesystem ownership.
    if request["root_binding_id"] != ROOT_BINDING:
        return _reject(PreflightCode.ROOT_MISMATCH)

    # Q1 stage 6: a missing fixture never reaches the verifier.
    if not fixture_reference:
        return _reject(PreflightCode.APPROVAL_MISSING)

    # Q1 stage 7: verifier supplied by the trusted test harness.
    try:
        decision = approval_verifier(
            fixture_reference=fixture_reference,
            operation=OPERATION,
            identity_sha256=synthetic_identity_sha256(),
            protocol_sha256=PROTOCOL_SHA256,
            root_binding_id=ROOT_BINDING,
            fixed_now_utc=fixed_now_utc,
        )
    except Exception:
        return _reject(PreflightCode.INTERNAL_FAILURE)

    outcome_codes = {
        ApprovalDecision.DENIED: PreflightCode.APPROVAL_DENIED,
        ApprovalDecision.SCOPE: PreflightCode.APPROVAL_SCOPE,
        ApprovalDecision.EXPIRED: PreflightCode.APPROVAL_EXPIRED,
        ApprovalDecision.REPLAY: PreflightCode.APPROVAL_REPLAY,
    }

    if type(decision) is not ApprovalDecision:
        return _reject(PreflightCode.INTERNAL_FAILURE)

    if decision is ApprovalDecision.ACCEPT:
        return PreflightResult(accepted=True, code=None)

    return _reject(outcome_codes[decision])

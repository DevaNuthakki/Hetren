"""Synthetic-only authorization-to-persistence integration.

This module is not a protected scientific execution entrypoint.
It uses a fixed nonsecret seed fixture and the qualified
development-only C1 persistence implementation.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
import stat
from pathlib import Path

from packages.core.hetren_diagnosis.contracts import ContractError
from packages.engines.behavioral.p09_4_c1_synthetic_authorization import (
    ApprovalDecision,
    PROTOCOL_SHA256,
    evaluate_synthetic_c1_preclaim,
)
from packages.engines.behavioral import p09_4_c1_persistence as persistence


# Pinned development checkpoint, not a production source attestation.
DEVELOPMENT_SOURCE = "150195417edb58546438852e8f147d89854e6fc9"


@dataclass(frozen=True, slots=True)
class SyntheticExecutionOutcome:
    accepted: bool
    code: str | None
    identity_consumed: bool
    seed_sha256: str | None


def _synthetic_seed(size: int) -> bytes:
    """Fixed nonsecret fixture; never an OS-random study seed."""
    if type(size) is not int or size != 32:
        raise ValueError("Invalid synthetic fixture size")
    return bytes(range(32))


def _rejected(code: str, *, consumed: bool = False):
    return SyntheticExecutionOutcome(
        accepted=False,
        code=code,
        identity_consumed=consumed,
        seed_sha256=None,
    )


def _existing_disposition(root: Path) -> str:
    """Check fixed synthetic evidence before classifying prior success.

    This is a local development consistency check, not independent
    scientific verification or an authenticity guarantee.
    The identity remains consumed regardless of this classification.
    """
    incomplete = "DEV_CLAIM_INCOMPLETE"

    # Never follow a final-component symlink during evidence reads.
    # Unsupported platforms conservatively return INCOMPLETE.
    nofollow = getattr(os, "O_NOFOLLOW", None)
    nonblock = getattr(os, "O_NONBLOCK", None)
    if nofollow is None or nonblock is None:
        return incomplete

    batch = root / persistence._IDENTITY
    public = batch / "public"
    treatment = batch / "treatment"

    raw_file = treatment / "c1_raw_seed.bin"
    commitment_file = public / "c1_seed_commitment.json"
    disposition_file = public / "c1_seed_disposition.json"

    def regular_file_matches(path: Path, expected: bytes) -> bool:
        fd = os.open(
            path,
            os.O_RDONLY | nofollow | nonblock | getattr(os, "O_CLOEXEC", 0),
        )
        try:
            metadata = os.fstat(fd)

            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_size != len(expected)
                or stat.S_IMODE(metadata.st_mode) & 0o077
            ):
                return False

            with os.fdopen(fd, "rb", closefd=False) as stream:
                return stream.read(len(expected) + 1) == expected
        finally:
            os.close(fd)

    try:
        for directory in (batch, public, treatment):
            metadata = directory.lstat()

            if (
                not stat.S_ISDIR(metadata.st_mode)
                or stat.S_IMODE(metadata.st_mode) & 0o077
            ):
                return incomplete

        fixture = bytes(range(32))
        fixture_digest = hashlib.sha256(fixture).hexdigest()

        commitment_bytes = (
            persistence.build_development_c1_commitment(
                raw_seed=fixture,
                protocol_sha256=PROTOCOL_SHA256,
                source_commit=DEVELOPMENT_SOURCE,
                generation_seed_sha256=None,
            ).canonical_json_bytes()
        )

        disposition_bytes = persistence._disposition(
            status="SUCCEEDED",
            phase="COMPLETE",
            protocol_sha256=PROTOCOL_SHA256,
            source_commit=DEVELOPMENT_SOURCE,
            seed_persisted=True,
            seed_sha256=fixture_digest,
        )

        expected_files = (
            (raw_file, fixture),
            (commitment_file, commitment_bytes),
            (disposition_file, disposition_bytes),
        )

        for path, expected in expected_files:
            if type(expected) is not bytes:
                return incomplete

            if not regular_file_matches(path, expected):
                return incomplete

        return "DEV_ALREADY_CLAIMED"

    except Exception:
        # An unexpected verification failure is never evidence
        # that a previously consumed identity may be rerun.
        return incomplete



def execute_synthetic_authorized_c1(
    *,
    request: object,
    development_root: Path,
    environment_ready: bool,
    protocol_digest_provider: Callable[[], str],
    approval_verifier: Callable[..., ApprovalDecision],
    fixed_now_utc: datetime,
) -> SyntheticExecutionOutcome:
    """Run one synthetic attempt from a trusted test harness.

    The operation request cannot supply a root or seed factory.
    The separate development_root argument is trusted harness
    configuration, not an untrusted operation-request field.

    This local development adapter does not establish cross-host
    identity uniqueness or an independent approval authority.
    """

    if not isinstance(development_root, Path):
        return _rejected("DEV_ROOT_MISMATCH")

    # Validate the actual development root BEFORE authorization
    # and before any filesystem identity claim.
    try:
        qualified_root = persistence._preflight(
            development_root,
            PROTOCOL_SHA256,
            DEVELOPMENT_SOURCE,
            None,
            _synthetic_seed,
        )
    except (ContractError, OSError, ValueError, TypeError):
        return _rejected("DEV_ROOT_MISMATCH")

    # Development-only, read-only filesystem capability check.
    # Directory fsync must be available before the one-shot claim.
    # This does not guarantee future writes or crash durability.
    try:
        flags = (
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        directory_fd = os.open(qualified_root, flags)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except (OSError, ValueError):
        return _rejected("DEV_UNSUPPORTED_ENV")

    preflight = evaluate_synthetic_c1_preclaim(
        request=request,
        environment_ready=environment_ready,
        protocol_digest_provider=protocol_digest_provider,
        approval_verifier=approval_verifier,
        fixed_now_utc=fixed_now_utc,
    )

    if not preflight.accepted:
        return _rejected(preflight.code.value)

    # The existing qualified implementation owns the claim,
    # STARTED persistence, synthetic factory invocation,
    # evidence publication, and consumed-failure semantics.
    try:
        result = persistence.persist_development_c1_attempt(
            development_root=qualified_root,
            protocol_sha256=PROTOCOL_SHA256,
            source_commit=DEVELOPMENT_SOURCE,
            seed_factory=_synthetic_seed,
            generation_seed_sha256=None,
        )

    except persistence.P094DevelopmentC1AlreadyExists:
        return _rejected(
            _existing_disposition(qualified_root),
            consumed=True,
        )

    except persistence.P094DevelopmentC1PersistenceError:
        return _rejected(
            "DEV_PERSISTENCE_FAILED",
            consumed=True,
        )

    except (ContractError, OSError, ValueError, TypeError):
        # Unexpected errors are not permission to retry.
        # The identity may already have been consumed.
        consumed = os.path.lexists(
            qualified_root / persistence._IDENTITY
        )
        return _rejected(
            "DEV_INTERNAL_FAILURE",
            consumed=consumed,
        )

    return SyntheticExecutionOutcome(
        accepted=True,
        code=None,
        identity_consumed=True,
        seed_sha256=result.seed_sha256,
    )

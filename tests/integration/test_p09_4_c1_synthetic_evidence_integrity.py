"""Local synthetic evidence-integrity regression tests.

These tests do not establish independent scientific authorization,
authenticity against a privileged attacker, or crash durability.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import os

import pytest

from packages.engines.behavioral import (
    p09_4_c1_persistence as persistence,
    p09_4_c1_synthetic_execution as execution,
)
from packages.engines.behavioral.p09_4_c1_synthetic_authorization import (
    ApprovalDecision,
    OPERATION,
    PROTOCOL_SHA256,
    ROOT_BINDING,
    synthetic_identity_sha256,
)


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
SEED = bytes(range(32))


def request_fixture():
    return {
        "operation": OPERATION,
        "identity_sha256": synthetic_identity_sha256(),
        "approval_fixture_ref": "fixture_a",
        "root_binding_id": ROOT_BINDING,
    }


def run(root):
    return execution.execute_synthetic_authorized_c1(
        request=request_fixture(),
        development_root=root,
        environment_ready=True,
        protocol_digest_provider=lambda: PROTOCOL_SHA256,
        approval_verifier=lambda **_: ApprovalDecision.ACCEPT,
        fixed_now_utc=NOW,
    )


@pytest.mark.parametrize("mutation", [
    "untouched",
    "private_corrupted",
    "commitment_corrupted",
    "private_symlink",
    "commitment_symlink",
    "disposition_symlink",
    "disposition_forged",
    "private_missing",
    "commitment_missing",
    "private_truncated",
    "commitment_appended",
])
def test_prior_claim_evidence_integrity(
    tmp_path, monkeypatch, mutation
):
    root = tmp_path / "synthetic-evidence"
    root.mkdir(mode=0o700)

    calls = []

    def factory(size):
        calls.append(size)
        return SEED

    monkeypatch.setattr(execution, "_synthetic_seed", factory)

    first = run(root)

    assert first.accepted
    assert first.identity_consumed
    assert first.seed_sha256 == hashlib.sha256(SEED).hexdigest()
    assert calls == [32]

    batch = root / persistence._IDENTITY

    private = batch / "treatment" / "c1_raw_seed.bin"
    commitment = batch / "public" / "c1_seed_commitment.json"
    disposition = batch / "public" / "c1_seed_disposition.json"

    redirected = None

    if mutation == "private_corrupted":
        data = private.read_bytes()
        private.write_bytes(bytes([data[0] ^ 1]) + data[1:])

    elif mutation == "commitment_corrupted":
        data = commitment.read_bytes()
        commitment.write_bytes(bytes([data[0] ^ 1]) + data[1:])

    elif mutation in (
        "private_symlink",
        "commitment_symlink",
        "disposition_symlink",
    ):
        selected = {
            "private_symlink": private,
            "commitment_symlink": commitment,
            "disposition_symlink": disposition,
        }[mutation]

        redirected = tmp_path / "outside-target.bin"
        redirected.write_bytes(selected.read_bytes())

        selected.unlink()
        selected.symlink_to(redirected)

    elif mutation == "disposition_forged":
        disposition.write_text(
            '{"status":"SUCCEEDED","evidence":"unknown"}',
            encoding="utf-8",
        )

    elif mutation == "private_missing":
        private.unlink()

    elif mutation == "commitment_missing":
        commitment.unlink()

    elif mutation == "private_truncated":
        private.write_bytes(private.read_bytes()[:4])

    elif mutation == "commitment_appended":
        commitment.write_bytes(commitment.read_bytes() + b" ")

    outside_before = (
        redirected.read_bytes() if redirected is not None else None
    )

    second = run(root)

    assert not second.accepted
    assert second.identity_consumed
    assert second.seed_sha256 is None

    if mutation == "untouched":
        assert second.code == "DEV_ALREADY_CLAIMED"
    else:
        assert second.code == "DEV_CLAIM_INCOMPLETE"

    # No repeat generation, even after detected evidence damage.
    assert calls == [32]

    if redirected is not None:
        assert redirected.read_bytes() == outside_before


def test_claim_without_disposition_remains_consumed(tmp_path):
    root = tmp_path / "abandoned-identity"
    root.mkdir(mode=0o700)

    batch = root / persistence._IDENTITY
    batch.mkdir(mode=0o700)

    result = run(root)

    assert not result.accepted
    assert result.identity_consumed
    assert result.code == "DEV_CLAIM_INCOMPLETE"


@pytest.mark.parametrize("target_name", [
    "private",
    "commitment",
    "disposition",
])
def test_fifo_evidence_never_blocks_or_regenerates(
    tmp_path, monkeypatch, target_name
):
    """Nonregular prior evidence must fail closed without blocking."""
    root = tmp_path / "synthetic-fifo"
    root.mkdir(mode=0o700)

    calls = []

    def factory(size):
        calls.append(size)
        return SEED

    monkeypatch.setattr(execution, "_synthetic_seed", factory)

    first = run(root)

    assert first.accepted
    assert first.identity_consumed
    assert calls == [32]

    batch = root / persistence._IDENTITY
    targets = {
        "private": batch / "treatment" / "c1_raw_seed.bin",
        "commitment": batch / "public" / "c1_seed_commitment.json",
        "disposition": batch / "public" / "c1_seed_disposition.json",
    }

    target = targets[target_name]
    target.unlink()
    os.mkfifo(target, mode=0o600)

    retry = run(root)

    assert retry.accepted is False
    assert retry.identity_consumed is True
    assert retry.code == "DEV_CLAIM_INCOMPLETE"
    assert calls == [32]

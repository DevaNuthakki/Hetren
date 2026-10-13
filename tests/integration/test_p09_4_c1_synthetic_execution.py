"""K5D-4E3B2 synthetic-only integration acceptance tests."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json

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


def root_fixture(tmp_path):
    root = tmp_path / "synthetic-authorized-attempt"
    root.mkdir(mode=0o700)
    return root


def request_fixture():
    return {
        "operation": OPERATION,
        "identity_sha256": synthetic_identity_sha256(),
        "approval_fixture_ref": "fixture_a",
        "root_binding_id": ROOT_BINDING,
    }


def attempt(root, request=None, verifier=None):
    return execution.execute_synthetic_authorized_c1(
        request=request_fixture() if request is None else request,
        development_root=root,
        environment_ready=True,
        protocol_digest_provider=lambda: PROTOCOL_SHA256,
        approval_verifier=(
            verifier if verifier is not None
            else lambda **_: ApprovalDecision.ACCEPT
        ),
        fixed_now_utc=NOW,
    )


@pytest.mark.parametrize("decision,expected", [
    (ApprovalDecision.DENIED, "DEV_APPROVAL_DENIED"),
    (ApprovalDecision.SCOPE, "DEV_APPROVAL_SCOPE"),
    (ApprovalDecision.EXPIRED, "DEV_APPROVAL_EXPIRED"),
    (ApprovalDecision.REPLAY, "DEV_APPROVAL_REPLAY"),
])
def test_rejected_approvals_do_not_claim(tmp_path, decision, expected):
    root = root_fixture(tmp_path)
    result = attempt(root, verifier=lambda **_: decision)
    assert result.accepted is False
    assert result.code == expected
    assert result.identity_consumed is False
    assert list(root.iterdir()) == []


def test_missing_approval_does_not_claim(tmp_path):
    root = root_fixture(tmp_path)
    request = request_fixture()
    request["approval_fixture_ref"] = ""
    result = attempt(root, request=request)
    assert result.code == "DEV_APPROVAL_MISSING"
    assert not result.identity_consumed
    assert not list(root.iterdir())


def test_invalid_identity_does_not_claim(tmp_path):
    root = root_fixture(tmp_path)
    request = request_fixture()
    request["identity_sha256"] = "0" * 64
    result = attempt(root, request=request)
    assert result.code == "DEV_IDENTITY_MISMATCH"
    assert not result.identity_consumed
    assert not list(root.iterdir())


def test_untrusted_root_override_rejected(tmp_path):
    root = root_fixture(tmp_path)
    request = request_fixture()
    request["development_root"] = str(tmp_path / "another")
    result = attempt(root, request=request)
    assert result.code == "DEV_INVALID_REQUEST"
    assert not result.identity_consumed
    assert not list(root.iterdir())


def test_repository_root_cannot_be_used_as_fixture():
    from pathlib import Path
    import subprocess
    repo = Path(
        subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            text=True,
        ).strip()
    )
    result = attempt(repo)
    assert result.code == "DEV_ROOT_MISMATCH"
    assert not result.identity_consumed


def test_success_persists_fixed_synthetic_evidence_once(tmp_path):
    root = root_fixture(tmp_path)
    result = attempt(root)

    assert result.accepted is True
    assert result.code is None
    assert result.identity_consumed is True
    assert result.seed_sha256 == hashlib.sha256(SEED).hexdigest()

    batch = root / persistence._IDENTITY
    private = batch / "treatment" / "c1_raw_seed.bin"
    public = batch / "public" / "c1_seed_disposition.json"

    assert private.read_bytes() == SEED
    assert json.loads(public.read_text())["status"] == "SUCCEEDED"

    retry = attempt(root)
    assert retry.accepted is False
    assert retry.code == "DEV_ALREADY_CLAIMED"
    assert retry.identity_consumed is True
    assert private.read_bytes() == SEED


def test_postclaim_factory_failure_consumes_identity(tmp_path, monkeypatch):
    root = root_fixture(tmp_path)
    calls = []

    def failing_factory(size):
        calls.append(size)
        raise RuntimeError("synthetic injected failure")

    monkeypatch.setattr(execution, "_synthetic_seed", failing_factory)

    result = attempt(root)
    assert result.code == "DEV_PERSISTENCE_FAILED"
    assert result.identity_consumed is True
    assert calls == [32]

    batch = root / persistence._IDENTITY
    disposition = batch / "public" / "c1_seed_disposition.json"
    assert json.loads(disposition.read_text())["status"] == "FAILED"

    retry = attempt(root)
    assert retry.code == "DEV_CLAIM_INCOMPLETE"
    assert retry.identity_consumed is True
    assert calls == [32]


def test_abandoned_claim_refuses_regeneration(tmp_path):
    root = root_fixture(tmp_path)
    (root / persistence._IDENTITY).mkdir(mode=0o700)

    result = attempt(root)
    assert result.accepted is False
    assert result.code == "DEV_CLAIM_INCOMPLETE"
    assert result.identity_consumed is True


def test_competing_synthetic_attempts_claim_at_most_once(tmp_path):
    root = root_fixture(tmp_path)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(attempt, root) for _ in range(2)]
        results = [future.result() for future in futures]

    assert sum(result.accepted for result in results) == 1
    assert all(result.identity_consumed for result in results)
    assert {
        result.code for result in results if not result.accepted
    }.issubset({"DEV_ALREADY_CLAIMED", "DEV_CLAIM_INCOMPLETE"})


def test_verifier_exception_does_not_claim(tmp_path):
    root = root_fixture(tmp_path)

    def broken(**kwargs):
        raise RuntimeError("synthetic verifier failure")

    result = attempt(root, verifier=broken)
    assert result.code == "DEV_INTERNAL_FAILURE"
    assert not result.identity_consumed
    assert not list(root.iterdir())

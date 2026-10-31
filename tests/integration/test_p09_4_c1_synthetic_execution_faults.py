"""Synthetic-only one-shot execution fault-injection tests.

All seed bytes are fixed nonsecret development fixtures.
All filesystem operations use pytest temporary directories.
No protected scientific operation or real seed is authorized.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import threading

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


def fixture_root(tmp_path):
    root = tmp_path / "synthetic-fault-experiment"
    root.mkdir(mode=0o700)
    return root


def request():
    return {
        "operation": OPERATION,
        "identity_sha256": synthetic_identity_sha256(),
        "approval_fixture_ref": "fixture_a",
        "root_binding_id": ROOT_BINDING,
    }


def run(root, supplied_request=None):
    return execution.execute_synthetic_authorized_c1(
        request=request() if supplied_request is None
        else supplied_request,
        development_root=root,
        environment_ready=True,
        protocol_digest_provider=lambda: PROTOCOL_SHA256,
        approval_verifier=lambda **_: ApprovalDecision.ACCEPT,
        fixed_now_utc=NOW,
    )


def disposition(root):
    return (
        root / persistence._IDENTITY
        / "public" / "c1_seed_disposition.json"
    )


def counted_factory(monkeypatch):
    calls = []

    def factory(size):
        calls.append(size)
        return SEED

    monkeypatch.setattr(execution, "_synthetic_seed", factory)
    return calls


def test_invalid_identity_never_calls_factory_or_claims(
    tmp_path, monkeypatch
):
    root = fixture_root(tmp_path)
    calls = counted_factory(monkeypatch)

    bad = request()
    bad["identity_sha256"] = "0" * 64

    result = run(root, bad)

    assert result.code == "DEV_IDENTITY_MISMATCH"
    assert not result.identity_consumed
    assert calls == []
    assert list(root.iterdir()) == []


def test_claim_sync_failure_consumes_without_factory(
    tmp_path, monkeypatch
):
    root = fixture_root(tmp_path)
    calls = counted_factory(monkeypatch)
    original = persistence._fsync_directory

    def failure(directory):
        if directory == root:
            raise OSError("injected claim synchronization failure")
        return original(directory)

    monkeypatch.setattr(
        persistence, "_fsync_directory", failure
    )

    first = run(root)

    assert first.code == "DEV_PERSISTENCE_FAILED"
    assert first.identity_consumed
    assert calls == []
    assert (root / persistence._IDENTITY).is_dir()

    second = run(root)
    assert second.code == "DEV_CLAIM_INCOMPLETE"
    assert second.identity_consumed
    assert calls == []


def test_started_write_failure_consumes_without_factory(
    tmp_path, monkeypatch
):
    root = fixture_root(tmp_path)
    calls = counted_factory(monkeypatch)
    original = persistence._write_new

    def failure(path, data):
        if path.name == "c1_seed_disposition.json":
            raise OSError("injected STARTED publication failure")
        return original(path, data)

    monkeypatch.setattr(persistence, "_write_new", failure)

    first = run(root)

    assert first.code == "DEV_PERSISTENCE_FAILED"
    assert first.identity_consumed
    assert calls == []
    assert (root / persistence._IDENTITY).exists()

    retry = run(root)
    assert retry.code == "DEV_CLAIM_INCOMPLETE"
    assert retry.identity_consumed
    assert calls == []


@pytest.mark.parametrize(
    "failed_filename",
    ["c1_raw_seed.bin", "c1_seed_commitment.json"],
)
def test_private_or_public_publication_failure_consumes_identity(
    tmp_path, monkeypatch, failed_filename
):
    root = fixture_root(tmp_path)
    calls = counted_factory(monkeypatch)
    original = persistence._write_new

    def failure(path, data):
        if path.name == failed_filename:
            raise OSError("injected synthetic publication failure")
        return original(path, data)

    monkeypatch.setattr(persistence, "_write_new", failure)

    first = run(root)

    assert first.code == "DEV_PERSISTENCE_FAILED"
    assert first.identity_consumed
    assert calls == [32]
    assert json.loads(
        disposition(root).read_text()
    )["status"] == "FAILED"

    public = root / persistence._IDENTITY / "public"

    for file in public.rglob("*"):
        if file.is_file():
            assert SEED not in file.read_bytes()

    retry = run(root)
    assert retry.code == "DEV_CLAIM_INCOMPLETE"
    assert retry.identity_consumed
    assert calls == [32]


def test_terminal_disposition_failure_leaves_consumed_identity(
    tmp_path, monkeypatch
):
    root = fixture_root(tmp_path)
    calls = counted_factory(monkeypatch)

    def failure(path, data):
        raise OSError("injected terminal disposition failure")

    monkeypatch.setattr(
        persistence, "_replace_disposition", failure
    )

    first = run(root)

    assert first.code == "DEV_PERSISTENCE_FAILED"
    assert first.identity_consumed
    assert calls == [32]

    # STARTED may remain even though synthetic private/public
    # artifacts were published. This is not permission to reroll.
    record = json.loads(disposition(root).read_text())
    assert record["status"] == "STARTED"

    retry = run(root)
    assert retry.code == "DEV_CLAIM_INCOMPLETE"
    assert retry.identity_consumed
    assert calls == [32]


def test_existing_symlink_claim_is_not_followed(
    tmp_path, monkeypatch
):
    root = fixture_root(tmp_path)
    outside = tmp_path / "other-fixture"
    outside.mkdir(mode=0o700)

    (root / persistence._IDENTITY).symlink_to(
        outside, target_is_directory=True
    )

    calls = counted_factory(monkeypatch)
    result = run(root)

    assert result.code == "DEV_CLAIM_INCOMPLETE"
    assert result.identity_consumed
    assert calls == []
    assert list(outside.iterdir()) == []


def test_four_competing_claims_invoke_factory_at_most_once(
    tmp_path, monkeypatch
):
    root = fixture_root(tmp_path)
    calls = []
    lock = threading.Lock()

    def factory(size):
        with lock:
            calls.append(size)
        return SEED

    monkeypatch.setattr(execution, "_synthetic_seed", factory)

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(run, root) for _ in range(4)]
        results = [future.result() for future in futures]

    assert sum(item.accepted for item in results) == 1
    assert calls == [32]
    assert all(item.identity_consumed for item in results)
    assert all(
        item.code in (
            None, "DEV_ALREADY_CLAIMED", "DEV_CLAIM_INCOMPLETE"
        )
        for item in results
    )

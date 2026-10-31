"""Development-only synthetic acceptance gap tests.

No real study seed, protected execution, or external credentials.
"""

from __future__ import annotations

from datetime import datetime, timezone
import errno
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


def root_fixture(tmp_path):
    root = tmp_path / "synthetic-acceptance"
    root.mkdir(mode=0o700)
    return root


def request_fixture():
    return {
        "operation": OPERATION,
        "identity_sha256": synthetic_identity_sha256(),
        "approval_fixture_ref": "fixture_a",
        "root_binding_id": ROOT_BINDING,
    }


def run(root, *, request=None, protocol=None, ready=True):
    return execution.execute_synthetic_authorized_c1(
        request=request_fixture() if request is None else request,
        development_root=root,
        environment_ready=ready,
        protocol_digest_provider=(
            lambda: PROTOCOL_SHA256 if protocol is None else protocol
        ),
        approval_verifier=lambda **_: ApprovalDecision.ACCEPT,
        fixed_now_utc=NOW,
    )


def counted_factory(monkeypatch):
    calls = []

    def factory(size):
        calls.append(size)
        return SEED

    monkeypatch.setattr(execution, "_synthetic_seed", factory)
    return calls


@pytest.mark.parametrize("mutation", [
    "wrong_operation",
    "wrong_root",
    "extra_field",
    "missing_field",
    "wrong_type",
])
def test_invalid_request_never_claims_or_generates(
    tmp_path, monkeypatch, mutation
):
    root = root_fixture(tmp_path)
    calls = counted_factory(monkeypatch)
    request = request_fixture()

    if mutation == "wrong_operation":
        request["operation"] = "UNSUPPORTED_OPERATION"
    elif mutation == "wrong_root":
        request["root_binding_id"] = "untrusted-root"
    elif mutation == "extra_field":
        request["development_root"] = "/somewhere/else"
    elif mutation == "missing_field":
        del request["operation"]
    elif mutation == "wrong_type":
        request["identity_sha256"] = 12345

    result = run(root, request=request)

    assert not result.accepted
    assert not result.identity_consumed
    assert calls == []
    assert list(root.iterdir()) == []


def test_protocol_mismatch_never_claims(
    tmp_path, monkeypatch
):
    root = root_fixture(tmp_path)
    calls = counted_factory(monkeypatch)

    result = run(root, protocol="0" * 64)

    assert result.code == "DEV_PROTOCOL_MISMATCH"
    assert not result.identity_consumed
    assert calls == []
    assert list(root.iterdir()) == []


def test_unready_environment_never_claims(
    tmp_path, monkeypatch
):
    root = root_fixture(tmp_path)
    calls = counted_factory(monkeypatch)

    result = run(root, ready=False)

    assert result.code == "DEV_UNSUPPORTED_ENV"
    assert not result.identity_consumed
    assert calls == []
    assert list(root.iterdir()) == []


def test_directory_sync_unavailable_rejects_before_claim(
    tmp_path, monkeypatch
):
    root = root_fixture(tmp_path)
    calls = counted_factory(monkeypatch)

    def unsupported_fsync(fd):
        raise OSError(
            errno.EINVAL,
            "injected unsupported directory synchronization",
        )

    monkeypatch.setattr(execution.os, "fsync", unsupported_fsync)

    result = run(root)

    assert result.code == "DEV_UNSUPPORTED_ENV"
    assert not result.identity_consumed
    assert calls == []
    assert list(root.iterdir()) == []


def test_directory_open_unavailable_rejects_before_claim(
    tmp_path, monkeypatch
):
    root = root_fixture(tmp_path)
    calls = counted_factory(monkeypatch)
    original_open = os.open

    def unsupported_open(path, flags, *args, **kwargs):
        if os.fspath(path) == os.fspath(root):
            raise OSError(
                errno.EOPNOTSUPP,
                "injected unsupported directory opening",
            )
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(execution.os, "open", unsupported_open)

    result = run(root)

    assert result.code == "DEV_UNSUPPORTED_ENV"
    assert not result.identity_consumed
    assert calls == []
    assert list(root.iterdir()) == []


@pytest.mark.parametrize("mode", ["symlink", "parent"])
def test_invalid_fixture_path_rejected_without_claim(
    tmp_path, monkeypatch, mode
):
    root = root_fixture(tmp_path)
    calls = counted_factory(monkeypatch)

    if mode == "symlink":
        supplied_root = tmp_path / "alias"
        supplied_root.symlink_to(root, target_is_directory=True)
    else:
        supplied_root = root / ".." / root.name

    result = run(supplied_root)

    assert result.code == "DEV_ROOT_MISMATCH"
    assert not result.identity_consumed
    assert calls == []
    assert list(root.iterdir()) == []


def test_success_calls_factory_once_and_retry_never_reexecutes(
    tmp_path, monkeypatch
):
    root = root_fixture(tmp_path)
    calls = counted_factory(monkeypatch)

    first = run(root)
    retry = run(root)

    assert first.accepted
    assert first.identity_consumed
    assert calls == [32]

    assert not retry.accepted
    assert retry.identity_consumed
    assert retry.code == "DEV_ALREADY_CLAIMED"
    assert calls == [32]

    private = (
        root / persistence._IDENTITY
        / "treatment" / "c1_raw_seed.bin"
    )
    assert private.read_bytes() == SEED

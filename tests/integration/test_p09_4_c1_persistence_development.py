"""Development-only C1 persistence tests using isolated synthetic fixtures."""
from __future__ import annotations

import ast
import hashlib
import inspect
import json
import os
from pathlib import Path
import stat

import pytest

from packages.core.hetren_diagnosis.contracts import ContractError
import packages.engines.behavioral.p09_4_c1_persistence as module
from packages.engines.behavioral.p09_4_c1_persistence import (
    P094DevelopmentC1AlreadyExists,
    P094DevelopmentC1PersistenceError,
    persist_development_c1_attempt,
)

PROTOCOL = (
    "46ea27e825bedbfbd8ee0443173884f904f20881fc929a4c44fae30c550e7621"
)

SOURCE = "3d2e4aecae25f511d0d2543cb2ce3df880fa1c39"

SYNTHETIC_SEED = bytes(range(32))


def sandbox(tmp_path: Path) -> Path:
    root = tmp_path / "isolated-development"
    root.mkdir(mode=0o700)
    return root


def attempt(root: Path, factory=None, **overrides):
    args = dict(
        development_root=root,
        protocol_sha256=PROTOCOL,
        source_commit=SOURCE,
        seed_factory=factory or (lambda size: SYNTHETIC_SEED),
    )
    args.update(overrides)
    return persist_development_c1_attempt(**args)


def status(root: Path) -> dict:
    path = (
        root /
        "development_c1_v1/public/c1_seed_disposition.json"
    )
    return json.loads(path.read_text())


def test_success_records_exact_private_and_public_artifacts(tmp_path):
    root = sandbox(tmp_path)
    result = attempt(root)
    batch = root / "development_c1_v1"

    assert result.batch_directory == batch

    assert sorted(p.name for p in batch.iterdir()) == [
        "public", "treatment",
    ]

    assert sorted(p.name for p in (batch / "public").iterdir()) == [
        "c1_seed_commitment.json",
        "c1_seed_disposition.json",
    ]

    assert sorted(p.name for p in (batch / "treatment").iterdir()) == [
        "c1_raw_seed.bin",
    ]

    assert (
        batch / "treatment/c1_raw_seed.bin"
    ).read_bytes() == SYNTHETIC_SEED

    commit_bytes = (
        batch / "public/c1_seed_commitment.json"
    ).read_bytes()

    assert result.seed_sha256 == hashlib.sha256(
        SYNTHETIC_SEED
    ).hexdigest()

    assert result.commitment_file_sha256 == hashlib.sha256(
        commit_bytes
    ).hexdigest()

    assert json.loads(commit_bytes)["development_only"] is True
    assert status(root)["status"] == "SUCCEEDED"
    assert status(root)["seed_persisted"] is True

    for path in (batch / "public").iterdir():
        assert SYNTHETIC_SEED not in path.read_bytes()
        assert (
            SYNTHETIC_SEED.hex().encode()
            not in path.read_bytes()
        )


def test_started_is_durable_before_synthetic_factory(tmp_path):
    root = sandbox(tmp_path)
    seen = []

    def factory(size):
        seen.append(size)
        assert size == 32
        assert status(root)["status"] == "STARTED"
        assert status(root)["phase"] == "CLAIMED"

        assert (
            root / "development_c1_v1/treatment"
        ).is_dir()

        assert not (
            root / "development_c1_v1/treatment/c1_raw_seed.bin"
        ).exists()

        return SYNTHETIC_SEED

    attempt(root, factory)
    assert seen == [32]


def test_duplicate_success_refuses_without_factory(tmp_path):
    root = sandbox(tmp_path)
    attempt(root)

    invoked = []

    with pytest.raises(P094DevelopmentC1AlreadyExists):
        attempt(root, lambda n: invoked.append(n))

    assert not invoked
    assert status(root)["status"] == "SUCCEEDED"


def test_abandoned_claim_refuses_reroll(tmp_path):
    root = sandbox(tmp_path)
    (root / "development_c1_v1").mkdir(mode=0o700)

    with pytest.raises(P094DevelopmentC1AlreadyExists):
        attempt(
            root,
            lambda n: pytest.fail("factory invoked"),
        )


def test_preexisting_symlink_identity_refuses_reroll(tmp_path):
    root = sandbox(tmp_path)
    (root / "elsewhere").mkdir()

    (root / "development_c1_v1").symlink_to(
        root / "elsewhere"
    )

    with pytest.raises(P094DevelopmentC1AlreadyExists):
        attempt(
            root,
            lambda n: pytest.fail("factory invoked"),
        )


def test_synthetic_factory_failure_consumes_identity(tmp_path):
    root = sandbox(tmp_path)
    observed = []

    def factory(size):
        observed.append(status(root)["status"])
        raise RuntimeError("synthetic fixture exception")

    with pytest.raises(
        P094DevelopmentC1PersistenceError,
        match="identity consumed",
    ):
        attempt(root, factory)

    assert observed == ["STARTED"]
    assert status(root)["status"] == "FAILED"
    assert status(root)["seed_persisted"] is False

    assert not (
        root / "development_c1_v1/treatment/c1_raw_seed.bin"
    ).exists()

    with pytest.raises(P094DevelopmentC1AlreadyExists):
        attempt(
            root,
            lambda n: pytest.fail("reroll invoked"),
        )


@pytest.mark.parametrize(
    "invalid",
    [
        b"short",
        b"x" * 33,
        bytearray(range(32)),
        None,
    ],
)
def test_invalid_seed_consumes_claim_without_private_file(
    tmp_path,
    invalid,
):
    root = sandbox(tmp_path)

    with pytest.raises(P094DevelopmentC1PersistenceError):
        attempt(root, lambda n: invalid)

    assert status(root)["status"] == "FAILED"
    assert status(root)["seed_persisted"] is False

    assert not (
        root / "development_c1_v1/treatment/c1_raw_seed.bin"
    ).exists()


def test_failure_after_private_seed_is_consumed(monkeypatch, tmp_path):
    root = sandbox(tmp_path)

    def fail_build(**kwargs):
        raise ContractError("development fault injection")

    monkeypatch.setattr(
        module,
        "build_development_c1_commitment",
        fail_build,
    )

    with pytest.raises(P094DevelopmentC1PersistenceError):
        attempt(root)

    assert (
        root / "development_c1_v1/treatment/c1_raw_seed.bin"
    ).read_bytes() == SYNTHETIC_SEED

    assert status(root)["status"] == "FAILED"
    assert status(root)["seed_persisted"] is True

    assert (
        status(root)["phase"]
        == "BUILD_DEVELOPMENT_COMMITMENT"
    )

    assert not (
        root / "development_c1_v1/public/c1_seed_commitment.json"
    ).exists()

    with pytest.raises(P094DevelopmentC1AlreadyExists):
        attempt(
            root,
            lambda n: pytest.fail("reroll invoked"),
        )


def test_failure_to_persist_disposition_leaves_consumed_identity(
    monkeypatch,
    tmp_path,
):
    root = sandbox(tmp_path)

    def fail_replace(*args, **kwargs):
        raise OSError("synthetic replace fault")

    monkeypatch.setattr(
        module,
        "_replace_disposition",
        fail_replace,
    )

    with pytest.raises(
        P094DevelopmentC1PersistenceError,
        match="disposition unavailable",
    ):
        attempt(root)

    assert status(root)["status"] == "STARTED"

    assert (
        root / "development_c1_v1/treatment/c1_raw_seed.bin"
    ).read_bytes() == SYNTHETIC_SEED

    with pytest.raises(P094DevelopmentC1AlreadyExists):
        attempt(
            root,
            lambda n: pytest.fail("reroll invoked"),
        )


def test_collision_consistently_fails_after_claim(tmp_path):
    root = sandbox(tmp_path)
    digest = hashlib.sha256(SYNTHETIC_SEED).hexdigest()

    with pytest.raises(P094DevelopmentC1PersistenceError):
        attempt(root, generation_seed_sha256=digest)

    assert status(root)["status"] == "FAILED"
    assert status(root)["seed_persisted"] is True


@pytest.mark.parametrize(
    "field,value",
    [
        ("protocol_sha256", "bad"),
        ("source_commit", "BAD"),
        ("generation_seed_sha256", "invalid"),
        ("seed_factory", None),
    ],
)
def test_preflight_invalid_contract_does_not_claim(
    tmp_path,
    field,
    value,
):
    root = sandbox(tmp_path)

    with pytest.raises(ContractError):
        attempt(root, **{field: value})

    assert not (root / "development_c1_v1").exists()


def test_preflight_rejects_symlink_root(tmp_path):
    root = sandbox(tmp_path)
    link = tmp_path / "root-link"

    link.symlink_to(
        root,
        target_is_directory=True,
    )

    with pytest.raises(ContractError):
        attempt(link)

    assert not (root / "development_c1_v1").exists()


def test_preflight_rejects_insecure_root_permissions(tmp_path):
    root = sandbox(tmp_path)
    root.chmod(0o755)

    with pytest.raises(ContractError):
        attempt(root)

    assert not (root / "development_c1_v1").exists()


def test_preflight_rejects_repository_path_before_factory():
    repository = Path(module.__file__).resolve().parents[3]

    with pytest.raises(ContractError):
        attempt(
            repository,
            lambda n: pytest.fail("factory invoked"),
        )


def test_private_permissions_restrict_access(tmp_path):
    root = sandbox(tmp_path)
    batch = attempt(root).batch_directory

    for path in [
        batch,
        batch / "public",
        batch / "treatment",
    ]:
        assert stat.S_IMODE(path.stat().st_mode) == 0o700

    for path in (batch / "public").iterdir():
        assert stat.S_IMODE(path.stat().st_mode) == 0o600

    assert stat.S_IMODE(
        (batch / "treatment/c1_raw_seed.bin").stat().st_mode
    ) == 0o600


def test_source_contains_no_random_source_or_production_entrypoint():
    tree = ast.parse(inspect.getsource(module))

    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }

    assert not imports.intersection({
        "secrets",
        "random",
        "subprocess",
    })

    assert not any(
        isinstance(node, ast.Name)
        and node.id in {"token_bytes", "urandom"}
        for node in ast.walk(tree)
    )

    assert not any(
        isinstance(node, ast.FunctionDef)
        and node.name == "main"
        for node in tree.body
    )


def test_interrupted_started_write_removes_temp_and_consumes(
    monkeypatch, tmp_path
):
    root = sandbox(tmp_path)
    original = module._write_all
    calls = []

    def interrupted(descriptor, data):
        calls.append(1)
        if len(calls) == 1:
            os.write(descriptor, memoryview(data)[:8])
            raise OSError("synthetic interrupted STARTED write")
        return original(descriptor, data)

    monkeypatch.setattr(module, "_write_all", interrupted)

    with pytest.raises(P094DevelopmentC1PersistenceError):
        attempt(root)

    batch = root / "development_c1_v1"
    assert status(root)["status"] == "FAILED"
    assert status(root)["seed_persisted"] is False
    assert not list(batch.rglob("*.tmp"))
    assert not (batch / "treatment/c1_raw_seed.bin").exists()

    with pytest.raises(P094DevelopmentC1AlreadyExists):
        attempt(root, lambda n: pytest.fail("reroll invoked"))


def test_interrupted_private_seed_write_removes_fragment(
    monkeypatch, tmp_path
):
    root = sandbox(tmp_path)
    original = module._write_all
    calls = []

    def interrupted(descriptor, data):
        calls.append(1)
        if len(calls) == 2:
            os.write(descriptor, memoryview(data)[:8])
            raise OSError("synthetic interrupted private write")
        return original(descriptor, data)

    monkeypatch.setattr(module, "_write_all", interrupted)

    with pytest.raises(P094DevelopmentC1PersistenceError):
        attempt(root)

    batch = root / "development_c1_v1"
    assert status(root)["status"] == "FAILED"
    assert status(root)["seed_persisted"] is False
    assert not list(batch.rglob("*.tmp"))
    assert not (batch / "treatment/c1_raw_seed.bin").exists()

    with pytest.raises(P094DevelopmentC1AlreadyExists):
        attempt(root, lambda n: pytest.fail("reroll invoked"))


def test_interrupted_disposition_replacement_removes_temp(
    monkeypatch, tmp_path
):
    root = sandbox(tmp_path)
    original = module._write_all
    calls = []

    def interrupted(descriptor, data):
        calls.append(1)
        if len(calls) == 4:
            os.write(descriptor, memoryview(data)[:8])
            raise OSError("synthetic interrupted replacement")
        return original(descriptor, data)

    monkeypatch.setattr(module, "_write_all", interrupted)

    with pytest.raises(P094DevelopmentC1PersistenceError):
        attempt(root)

    batch = root / "development_c1_v1"
    assert status(root)["status"] == "FAILED"
    assert status(root)["seed_persisted"] is True
    assert not list(batch.rglob("*.tmp"))

    assert (
        batch / "treatment/c1_raw_seed.bin"
    ).read_bytes() == SYNTHETIC_SEED

    with pytest.raises(P094DevelopmentC1AlreadyExists):
        attempt(root, lambda n: pytest.fail("reroll invoked"))


def test_intermediate_symlink_parent_rejected_before_claim(tmp_path):
    actual_parent = tmp_path / "actual-parent"
    actual_parent.mkdir(mode=0o700)

    actual_root = actual_parent / "isolated"
    actual_root.mkdir(mode=0o700)

    alias_parent = tmp_path / "alias-parent"
    alias_parent.symlink_to(
        actual_parent,
        target_is_directory=True,
    )

    alias_root = alias_parent / "isolated"

    with pytest.raises(ContractError):
        attempt(
            alias_root,
            lambda n: pytest.fail("seed factory invoked"),
        )

    assert not (
        actual_root / "development_c1_v1"
    ).exists()


def test_development_root_rejects_outside_configured_temp_boundary(
    monkeypatch, tmp_path
):
    root = sandbox(tmp_path)

    unrelated = tmp_path / "unrelated-anchor"
    unrelated.mkdir(mode=0o700)

    monkeypatch.setattr(
        module.tempfile,
        "gettempdir",
        lambda: str(unrelated),
    )

    with pytest.raises(ContractError):
        attempt(
            root,
            lambda n: pytest.fail("seed factory invoked"),
        )

    assert not (root / "development_c1_v1").exists()

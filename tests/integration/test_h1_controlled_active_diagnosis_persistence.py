import hashlib
import json
import os
from pathlib import Path

import pytest

import packages.engines.behavioral.h1_controlled_active_diagnosis_persistence as persistence
from packages.engines.behavioral.h1_controlled_active_diagnosis_generation import (
    build_h1_batch_manifests,
)
from packages.engines.behavioral.h1_controlled_active_diagnosis_persistence import (
    H1GenerationAlreadyExists,
    H1GenerationPersistenceError,
    persist_h1_generation_attempt,
)


PROTOCOL_SHA = (
    "6b738092e28036ea400f6498a4ad1663"
    "dd8cbb1e1c9c1e54e48ff4030ceb6ef8"
)

HARNESS_COMMIT_ID = (
    "ccc65a6a7e3e1745e0ceda3968287507a2de81d2"
)

REPOSITORY_HEAD_ID = (
    "abe1fe69fe957298ed0c4e7bba6a4352dae838b5"
)

GENERATOR_SHA = (
    "17424bd4cc7ea8bb2215b18ea9d19468"
    "b2dde8bb35c1d1d91bea69d2288ff39b"
)

FIXED_SEED = bytes.fromhex(
    "22" * 32
)

BATCH_ID = "development-persistence-test-v1"


def fixed_seed_factory(
    length,
):
    assert length == 32

    return FIXED_SEED


def generate(
    tmp_path,
    *,
    seed_factory=fixed_seed_factory,
    batch_id=BATCH_ID,
):
    return persist_h1_generation_attempt(
        artifact_root=(
            tmp_path
            / "development-artifacts"
        ),
        batch_id=batch_id,
        protocol_sha256=PROTOCOL_SHA,
        harness_commit_id=HARNESS_COMMIT_ID,
        repository_head_commit_id=REPOSITORY_HEAD_ID,
        generator_module_sha256=GENERATOR_SHA,
        seed_factory=seed_factory,
    )


def load_json(
    path,
):
    return json.loads(
        Path(
            path
        ).read_text(
            encoding="utf-8"
        )
    )


def test_success_writes_expected_artifacts_and_preserves_fixed_seed(
    tmp_path,
):
    result = generate(
        tmp_path
    )

    batch = result.batch_directory

    expected = {
        batch
        / "public"
        / "generation_disposition.json",

        batch
        / "public"
        / "seed_commitment.json",

        batch
        / "public"
        / "public_manifest.json",

        batch
        / "public"
        / "generation_record.json",

        batch
        / "evaluator"
        / "raw_seed.bin",

        batch
        / "evaluator"
        / "hidden_truth_manifest.json",
    }

    assert all(
        path.is_file()
        for path in expected
    )

    assert (
        batch
        / "evaluator"
        / "raw_seed.bin"
    ).read_bytes() == FIXED_SEED

    disposition = load_json(
        batch
        / "public"
        / "generation_disposition.json"
    )

    assert disposition[
        "status"
    ] == "SUCCEEDED"

    assert disposition[
        "seed_persisted"
    ] is True


def test_success_public_files_do_not_contain_raw_seed(
    tmp_path,
):
    result = generate(
        tmp_path
    )

    raw_hex = FIXED_SEED.hex()

    public_directory = (
        result.batch_directory
        / "public"
    )

    for path in public_directory.iterdir():
        if not path.is_file():
            continue

        text = path.read_text(
            encoding="utf-8"
        )

        assert raw_hex not in text

    hidden_text = (
        result.batch_directory
        / "evaluator"
        / "hidden_truth_manifest.json"
    ).read_text(
        encoding="utf-8"
    )

    assert raw_hex not in hidden_text


def test_second_attempt_refuses_before_seed_factory_is_called(
    tmp_path,
):
    generate(
        tmp_path
    )

    calls = []

    def forbidden_factory(
        length,
    ):
        calls.append(
            length
        )

        raise AssertionError(
            "seed factory must not run on occupied attempt"
        )

    with pytest.raises(
        H1GenerationAlreadyExists,
        match="already exists",
    ):
        generate(
            tmp_path,
            seed_factory=forbidden_factory,
        )

    assert calls == []


def test_failure_after_seed_persistence_preserves_seed_and_failed_disposition(
    tmp_path,
    monkeypatch,
):
    def fail_after_seed(
        **kwargs,
    ):
        raise RuntimeError(
            "development injected manifest failure"
        )

    monkeypatch.setattr(
        persistence,
        "build_h1_batch_manifests",
        fail_after_seed,
    )

    with pytest.raises(
        H1GenerationPersistenceError,
        match="attempt preserved",
    ):
        generate(
            tmp_path
        )

    batch = (
        tmp_path
        / "development-artifacts"
        / BATCH_ID
    )

    raw_seed_path = (
        batch
        / "evaluator"
        / "raw_seed.bin"
    )

    assert raw_seed_path.read_bytes() == FIXED_SEED

    seed_commitment = load_json(
        batch
        / "public"
        / "seed_commitment.json"
    )

    expected_seed_sha = hashlib.sha256(
        FIXED_SEED
    ).hexdigest()

    assert seed_commitment[
        "seed_sha256"
    ] == expected_seed_sha

    disposition = load_json(
        batch
        / "public"
        / "generation_disposition.json"
    )

    assert disposition[
        "status"
    ] == "FAILED"

    assert disposition[
        "seed_persisted"
    ] is True

    assert disposition[
        "seed_commitment_sha256"
    ] == expected_seed_sha

    assert disposition[
        "failure_type"
    ] == "RuntimeError"


def test_seed_factory_failure_consumes_attempt_without_seed_file(
    tmp_path,
):
    def broken_factory(
        length,
    ):
        assert length == 32

        raise RuntimeError(
            "development seed source failure"
        )

    with pytest.raises(
        H1GenerationPersistenceError,
        match="attempt preserved",
    ):
        generate(
            tmp_path,
            seed_factory=broken_factory,
        )

    batch = (
        tmp_path
        / "development-artifacts"
        / BATCH_ID
    )

    assert batch.is_dir()

    assert not (
        batch
        / "evaluator"
        / "raw_seed.bin"
    ).exists()

    disposition = load_json(
        batch
        / "public"
        / "generation_disposition.json"
    )

    assert disposition[
        "status"
    ] == "FAILED"

    assert disposition[
        "seed_persisted"
    ] is False

    assert disposition[
        "seed_commitment_sha256"
    ] is None


def test_invalid_seed_length_records_failure_and_no_seed_file(
    tmp_path,
):
    def short_factory(
        length,
    ):
        assert length == 32

        return b"x" * 31

    with pytest.raises(
        H1GenerationPersistenceError,
        match="attempt preserved",
    ):
        generate(
            tmp_path,
            seed_factory=short_factory,
        )

    batch = (
        tmp_path
        / "development-artifacts"
        / BATCH_ID
    )

    assert not (
        batch
        / "evaluator"
        / "raw_seed.bin"
    ).exists()

    disposition = load_json(
        batch
        / "public"
        / "generation_disposition.json"
    )

    assert disposition[
        "status"
    ] == "FAILED"

    assert disposition[
        "failure_type"
    ] == "ContractError"


def test_post_claim_setup_failure_records_failed_disposition_and_consumes_attempt(
    tmp_path,
    monkeypatch,
):
    original = persistence._fsync_directory
    calls = 0
    seed_calls = []

    def fail_first_fsync(
        directory,
    ):
        nonlocal calls

        calls += 1

        if calls == 1:
            raise OSError(
                "development injected post-claim setup failure"
            )

        return original(
            directory
        )

    def forbidden_seed_factory(
        length,
    ):
        seed_calls.append(
            length
        )

        raise AssertionError(
            "seed factory must not execute"
        )

    monkeypatch.setattr(
        persistence,
        "_fsync_directory",
        fail_first_fsync,
    )

    with pytest.raises(
        H1GenerationPersistenceError,
        match="attempt preserved",
    ):
        generate(
            tmp_path,
            seed_factory=forbidden_seed_factory,
        )

    assert seed_calls == []

    batch = (
        tmp_path
        / "development-artifacts"
        / BATCH_ID
    )

    disposition_path = (
        batch
        / "public"
        / "generation_disposition.json"
    )

    assert disposition_path.is_file()

    disposition = load_json(
        disposition_path
    )

    assert disposition[
        "status"
    ] == "FAILED"

    assert disposition[
        "phase"
    ] == "FSYNC_BATCH_CLAIM"

    assert disposition[
        "seed_persisted"
    ] is False

    assert disposition[
        "seed_commitment_sha256"
    ] is None

    assert disposition[
        "failure_type"
    ] == "OSError"

    with pytest.raises(
        H1GenerationAlreadyExists,
        match="already exists",
    ):
        generate(
            tmp_path,
            seed_factory=forbidden_seed_factory,
        )

    assert seed_calls == []


def test_initial_disposition_write_failure_is_recovered_as_failed_disposition(
    tmp_path,
    monkeypatch,
):
    original = persistence._atomic_write_new
    injected = False
    seed_calls = []

    def fail_first_disposition_write(
        path,
        data,
        *,
        mode,
    ):
        nonlocal injected

        if (
            path.name
            == "generation_disposition.json"
            and not injected
        ):
            injected = True

            raise OSError(
                "development injected initial-disposition failure"
            )

        return original(
            path,
            data,
            mode=mode,
        )

    def forbidden_seed_factory(
        length,
    ):
        seed_calls.append(
            length
        )

        raise AssertionError(
            "seed factory must not execute"
        )

    monkeypatch.setattr(
        persistence,
        "_atomic_write_new",
        fail_first_disposition_write,
    )

    with pytest.raises(
        H1GenerationPersistenceError,
        match="attempt preserved",
    ):
        generate(
            tmp_path,
            seed_factory=forbidden_seed_factory,
        )

    assert injected is True
    assert seed_calls == []

    batch = (
        tmp_path
        / "development-artifacts"
        / BATCH_ID
    )

    disposition = load_json(
        batch
        / "public"
        / "generation_disposition.json"
    )

    assert disposition[
        "status"
    ] == "FAILED"

    assert disposition[
        "phase"
    ] == "PERSIST_STARTED_DISPOSITION"

    assert disposition[
        "seed_persisted"
    ] is False

    assert disposition[
        "failure_type"
    ] == "OSError"

    assert not (
        batch
        / "evaluator"
        / "raw_seed.bin"
    ).exists()


def test_generation_record_hashes_match_persisted_manifests(
    tmp_path,
):
    result = generate(
        tmp_path
    )

    batch = result.batch_directory

    generation_record_path = (
        batch
        / "public"
        / "generation_record.json"
    )

    record = load_json(
        generation_record_path
    )

    public_manifest_bytes = (
        batch
        / "public"
        / "public_manifest.json"
    ).read_bytes()

    hidden_manifest_bytes = (
        batch
        / "evaluator"
        / "hidden_truth_manifest.json"
    ).read_bytes()

    public_payload = json.loads(
        public_manifest_bytes
    )

    hidden_payload = json.loads(
        hidden_manifest_bytes
    )

    from packages.core.hetren_diagnosis.contracts import (
        canonical_sha256,
    )

    assert record[
        "public_manifest_sha256"
    ] == canonical_sha256(
        public_payload
    )

    assert record[
        "hidden_truth_manifest_sha256"
    ] == canonical_sha256(
        hidden_payload
    )

    assert (
        hashlib.sha256(
            generation_record_path.read_bytes()
        ).hexdigest()
        == result.generation_record_sha256
    )


def test_private_permissions_are_restrictive(
    tmp_path,
):
    result = generate(
        tmp_path
    )

    batch = result.batch_directory

    for directory in (
        result.batch_directory.parent,
        result.batch_directory,
        batch
        / "public",
        batch
        / "evaluator",
    ):
        assert (
            os.stat(
                directory
            ).st_mode
            & 0o777
        ) == 0o700

    for path in (
        batch
        / "public"
        / "generation_disposition.json",

        batch
        / "public"
        / "seed_commitment.json",

        batch
        / "public"
        / "public_manifest.json",

        batch
        / "public"
        / "generation_record.json",

        batch
        / "evaluator"
        / "raw_seed.bin",

        batch
        / "evaluator"
        / "hidden_truth_manifest.json",
    ):
        assert (
            os.stat(
                path
            ).st_mode
            & 0o777
        ) == 0o600


def test_persistence_source_contains_fsync_and_atomic_replace():
    source = Path(
        persistence.__file__
    ).read_text(
        encoding="utf-8"
    )

    assert "os.fsync(" in source
    assert "os.replace(" in source
    assert "os.O_EXCL" in source
    assert "0o600" in source
    assert "0o700" in source


def test_production_command_is_explicitly_guarded_and_uses_secrets():
    command = Path(
        "scripts/"
        "generate_h1_controlled_active_diagnosis_protected.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "CREATE_P09_3_H1_PROTECTED_BATCH_ONCE"
        in command
    )

    assert "secrets.token_bytes" in command

    assert "--expected-head" in command
    assert "--confirm" in command
    assert "protected_v1" in command

    assert (
        'if __name__ == "__main__":'
        in command
    )


def test_success_can_be_reconstructed_from_persisted_seed(
    tmp_path,
):
    result = generate(
        tmp_path
    )

    batch = result.batch_directory

    raw_seed = (
        batch
        / "evaluator"
        / "raw_seed.bin"
    ).read_bytes()

    reconstructed = build_h1_batch_manifests(
        raw_seed=raw_seed,
        batch_id=BATCH_ID,
        protocol_sha256=PROTOCOL_SHA,
        harness_commit_id=HARNESS_COMMIT_ID,
    )

    persisted_public = (
        batch
        / "public"
        / "public_manifest.json"
    ).read_bytes()

    persisted_hidden = (
        batch
        / "evaluator"
        / "hidden_truth_manifest.json"
    ).read_bytes()

    assert (
        reconstructed.public_manifest.canonical_json_bytes
        == persisted_public
    )

    assert (
        reconstructed.hidden_truth_manifest.canonical_json_bytes
        == persisted_hidden
    )

    assert (
        result.seed_commitment_sha256
        == hashlib.sha256(
            raw_seed
        ).hexdigest()
    )

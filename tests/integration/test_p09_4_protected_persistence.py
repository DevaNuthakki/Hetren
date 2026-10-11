from __future__ import annotations

import hashlib
import inspect
import json
import os
from pathlib import Path
import stat

import pytest

from packages.core.hetren_diagnosis.contracts import (
    ContractError,
)
from packages.engines.behavioral.p09_4_protected_generation import (
    build_development_generation_plan,
)
import packages.engines.behavioral.p09_4_protected_persistence as persistence
from packages.engines.behavioral.p09_4_protected_persistence import (
    P094GenerationAlreadyExists,
    P094GenerationPersistenceError,
    persist_p09_4_generation_attempt,
)


BATCH_ID = "protected_v1"

PROTOCOL_SHA = (
    "46ea27e825bedbfbd8ee0443173884f904f20881fc929a4c44fae30c550e7621"
)

SOURCE_COMMIT = (
    "9c230e65e9f5375f7d0b4f923e314fe33c43ec43"
)

REPOSITORY_HEAD = SOURCE_COMMIT

GENERATOR_SHA = (
    "adff1938a5709ffd04ae27f8bd7744e25e2bcc295bfd7dca857994ba6572ac6b"
)

MATERIALIZER_SHA = (
    "b5861344b66c9a3cf8ea6e4c8921441fd34410f52fbce3d5745eba67fa71d027"
)

PERSISTENCE_SHA = (
    "a"
    * 64
)

FIXED_SEED = bytes(
    range(
        32
    )
)


def _artifact_root(
    tmp_path: Path,
) -> Path:
    return (
        tmp_path
        / "p09_4_scientific_arms"
    )


def _persist(
    tmp_path: Path,
    *,
    seed_factory=None,
):
    if seed_factory is None:
        seed_factory = (
            lambda size:
                FIXED_SEED
        )

    return persist_p09_4_generation_attempt(
        artifact_root=(
            _artifact_root(
                tmp_path
            )
        ),
        batch_id=BATCH_ID,
        protocol_sha256=PROTOCOL_SHA,
        source_commit=SOURCE_COMMIT,
        repository_head_commit_id=(
            REPOSITORY_HEAD
        ),
        generator_module_sha256=(
            GENERATOR_SHA
        ),
        materializer_module_sha256=(
            MATERIALIZER_SHA
        ),
        persistence_module_sha256=(
            PERSISTENCE_SHA
        ),
        seed_factory=(
            seed_factory
        ),
    )


def _batch(
    tmp_path: Path,
) -> Path:
    return (
        _artifact_root(
            tmp_path
        )
        / BATCH_ID
    )


def _load_json(
    path: Path,
):
    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def test_success_writes_exact_six_artifacts_and_preserves_fixed_seed(
    tmp_path,
):
    result = _persist(
        tmp_path
    )

    batch = (
        result.batch_directory
    )

    files = tuple(
        sorted(
            str(
                item.relative_to(
                    batch
                )
            )
            for item
            in batch.rglob(
                "*"
            )
            if item.is_file()
        )
    )

    assert files == (
        "evaluator/generation_raw_seed.bin",
        "evaluator/hidden_assignment_manifest.json",
        "public/generation_disposition.json",
        "public/generation_record.json",
        "public/generation_seed_commitment.json",
        "public/public_population_manifest.json",
    )

    assert (
        batch
        / "evaluator"
        / "generation_raw_seed.bin"
    ).read_bytes() == FIXED_SEED

    assert (
        result.generation_seed_sha256
        == hashlib.sha256(
            FIXED_SEED
        ).hexdigest()
    )

    disposition = _load_json(
        batch
        / "public"
        / "generation_disposition.json"
    )

    assert (
        disposition[
            "status"
        ]
        == "SUCCEEDED"
    )

    assert (
        disposition[
            "phase"
        ]
        == "SUCCEEDED"
    )


def test_seed_factory_observes_claimed_identity_and_started_disposition(
    tmp_path,
):
    observed = {
        "calls":
            0,
    }

    def seed_factory(
        size,
    ):
        observed[
            "calls"
        ] += 1

        assert size == 32

        batch = _batch(
            tmp_path
        )

        assert batch.is_dir()

        disposition_path = (
            batch
            / "public"
            / "generation_disposition.json"
        )

        assert (
            disposition_path.is_file()
        )

        disposition = (
            _load_json(
                disposition_path
            )
        )

        assert (
            disposition[
                "status"
            ]
            == "STARTED"
        )

        assert (
            disposition[
                "phase"
            ]
            == "CLAIMED"
        )

        assert (
            disposition[
                "generation_seed_persisted"
            ]
            is False
        )

        return FIXED_SEED

    _persist(
        tmp_path,
        seed_factory=(
            seed_factory
        ),
    )

    assert (
        observed[
            "calls"
        ]
        == 1
    )


def test_second_attempt_refuses_before_seed_factory_is_called(
    tmp_path,
):
    _persist(
        tmp_path
    )

    called = False

    def second_factory(
        size,
    ):
        nonlocal called

        called = True

        return bytes(
            size
        )

    with pytest.raises(
        P094GenerationAlreadyExists
    ):
        _persist(
            tmp_path,
            seed_factory=(
                second_factory
            ),
        )

    assert called is False


def test_seed_factory_failure_consumes_identity_without_seed_file(
    tmp_path,
):
    def broken_factory(
        size,
    ):
        raise RuntimeError(
            "development seed failure"
        )

    with pytest.raises(
        P094GenerationPersistenceError
    ):
        _persist(
            tmp_path,
            seed_factory=(
                broken_factory
            ),
        )

    batch = _batch(
        tmp_path
    )

    assert batch.is_dir()

    assert not (
        batch
        / "evaluator"
        / "generation_raw_seed.bin"
    ).exists()

    disposition = _load_json(
        batch
        / "public"
        / "generation_disposition.json"
    )

    assert (
        disposition[
            "status"
        ]
        == "FAILED"
    )

    assert (
        disposition[
            "phase"
        ]
        == "GENERATE_GENERATION_SEED"
    )

    assert (
        disposition[
            "generation_seed_persisted"
        ]
        is False
    )

    with pytest.raises(
        P094GenerationAlreadyExists
    ):
        _persist(
            tmp_path
        )


def test_invalid_seed_length_records_failure_without_seed_file(
    tmp_path,
):
    with pytest.raises(
        P094GenerationPersistenceError
    ):
        _persist(
            tmp_path,
            seed_factory=(
                lambda size:
                    b"too-short"
            ),
        )

    batch = _batch(
        tmp_path
    )

    assert not (
        batch
        / "evaluator"
        / "generation_raw_seed.bin"
    ).exists()

    disposition = _load_json(
        batch
        / "public"
        / "generation_disposition.json"
    )

    assert (
        disposition[
            "status"
        ]
        == "FAILED"
    )

    assert (
        disposition[
            "generation_seed_persisted"
        ]
        is False
    )


def test_failure_after_seed_persistence_preserves_seed_and_failed_disposition(
    tmp_path,
    monkeypatch,
):
    def fail_plan(
        **kwargs,
    ):
        raise RuntimeError(
            "development population build failure"
        )

    monkeypatch.setattr(
        persistence,
        "build_development_generation_plan",
        fail_plan,
    )

    with pytest.raises(
        P094GenerationPersistenceError
    ):
        _persist(
            tmp_path
        )

    batch = _batch(
        tmp_path
    )

    raw_seed = (
        batch
        / "evaluator"
        / "generation_raw_seed.bin"
    )

    assert (
        raw_seed.read_bytes()
        == FIXED_SEED
    )

    commitment = (
        batch
        / "public"
        / "generation_seed_commitment.json"
    )

    assert commitment.is_file()

    disposition = _load_json(
        batch
        / "public"
        / "generation_disposition.json"
    )

    assert (
        disposition[
            "status"
        ]
        == "FAILED"
    )

    assert (
        disposition[
            "phase"
        ]
        == "BUILD_PROTECTED_POPULATION"
    )

    assert (
        disposition[
            "generation_seed_persisted"
        ]
        is True
    )

    assert (
        disposition[
            "generation_seed_sha256"
        ]
        == hashlib.sha256(
            FIXED_SEED
        ).hexdigest()
    )


def test_public_files_contain_no_raw_seed_or_hidden_truth_labels(
    tmp_path,
):
    _persist(
        tmp_path
    )

    public = (
        _batch(
            tmp_path
        )
        / "public"
    )

    for path in public.iterdir():
        if not path.is_file():
            continue

        data = path.read_bytes()

        assert (
            FIXED_SEED
            not in data
        )

        text = data.decode(
            "utf-8"
        )

        assert (
            '"hidden_stratum"'
            not in text
        )

        assert (
            '"expected_hypothesis_key"'
            not in text
        )

    manifest = _load_json(
        public
        / "public_population_manifest.json"
    )

    assert (
        manifest[
            "case_count"
        ]
        == 144
    )


def test_generation_record_hashes_match_persisted_artifacts(
    tmp_path,
):
    result = _persist(
        tmp_path
    )

    batch = (
        result.batch_directory
    )

    record_path = (
        batch
        / "public"
        / "generation_record.json"
    )

    record = _load_json(
        record_path
    )

    commitment_bytes = (
        batch
        / "public"
        / "generation_seed_commitment.json"
    ).read_bytes()

    public_bytes = (
        batch
        / "public"
        / "public_population_manifest.json"
    ).read_bytes()

    hidden_bytes = (
        batch
        / "evaluator"
        / "hidden_assignment_manifest.json"
    ).read_bytes()

    assert (
        record[
            "generation_seed_commitment_file_sha256"
        ]
        == hashlib.sha256(
            commitment_bytes
        ).hexdigest()
    )

    assert (
        record[
            "public_population_manifest_sha256"
        ]
        == hashlib.sha256(
            public_bytes
        ).hexdigest()
    )

    assert (
        record[
            "hidden_assignment_manifest_sha256"
        ]
        == hashlib.sha256(
            hidden_bytes
        ).hexdigest()
    )

    assert (
        result.generation_record_sha256
        == hashlib.sha256(
            record_path.read_bytes()
        ).hexdigest()
    )


def test_success_reconstructs_generation_plan_from_persisted_seed(
    tmp_path,
):
    _persist(
        tmp_path
    )

    batch = _batch(
        tmp_path
    )

    raw_seed = (
        batch
        / "evaluator"
        / "generation_raw_seed.bin"
    ).read_bytes()

    plan = (
        build_development_generation_plan(
            raw_seed=raw_seed,
            protocol_sha256=(
                PROTOCOL_SHA
            ),
            source_commit=(
                SOURCE_COMMIT
            ),
        )
    )

    public_manifest = _load_json(
        batch
        / "public"
        / "public_population_manifest.json"
    )

    hidden_manifest = _load_json(
        batch
        / "evaluator"
        / "hidden_assignment_manifest.json"
    )

    persisted_case_ids = tuple(
        record[
            "case_id"
        ]
        for record
        in public_manifest[
            "cases"
        ]
    )

    expected_case_ids = tuple(
        slot.case_id
        for slot
        in plan.public_slots
    )

    assert (
        persisted_case_ids
        == expected_case_ids
    )

    assert (
        hidden_manifest[
            "assignments"
        ]
        == [
            assignment.canonical_payload()
            for assignment
            in plan.hidden_assignments
        ]
    )


def test_private_permissions_are_restrictive(
    tmp_path,
):
    result = _persist(
        tmp_path
    )

    batch = (
        result.batch_directory
    )

    directories = (
        _artifact_root(
            tmp_path
        ),
        batch,
        batch
        / "public",
        batch
        / "evaluator",
    )

    for directory in directories:
        mode = stat.S_IMODE(
            directory.stat().st_mode
        )

        assert mode == 0o700

    for path in batch.rglob(
        "*"
    ):
        if not path.is_file():
            continue

        mode = stat.S_IMODE(
            path.stat().st_mode
        )

        assert mode == 0o600


def test_public_population_contains_144_unique_failing_baselines(
    tmp_path,
):
    _persist(
        tmp_path
    )

    manifest = _load_json(
        _batch(
            tmp_path
        )
        / "public"
        / "public_population_manifest.json"
    )

    cases = (
        manifest[
            "cases"
        ]
    )

    assert len(
        cases
    ) == 144

    assert len(
        {
            record[
                "case_id"
            ]
            for record
            in cases
        }
    ) == 144

    assert len(
        {
            record[
                "public_configuration_sha256"
            ]
            for record
            in cases
        }
    ) == 144

    assert len(
        {
            record[
                "materialization_spec_sha256"
            ]
            for record
            in cases
        }
    ) == 144

    for record in cases:
        baseline = (
            record[
                "baseline"
            ]
        )

        assert (
            baseline[
                "run_id"
            ]
            == record[
                "case_id"
            ]
        )

        assert (
            baseline[
                "passed"
            ]
            is False
        )

        assert len(
            baseline[
                "checkpoints"
            ]
        ) == 3

        assert len(
            {
                checkpoint[
                    "checkpoint_state_sha256"
                ]
                for checkpoint
                in baseline[
                    "checkpoints"
                ]
            }
        ) == 3


def test_persistence_source_has_one_shot_atomicity_and_no_treatment_or_c1_logic():
    source = inspect.getsource(
        persistence
    )

    for required in (
        "_fsync_directory",
        "_atomic_write_new",
        "_atomic_replace",
        "generation_raw_seed.bin",
        "generation_seed_commitment.json",
        "generation_disposition.json",
        "PERSIST_STARTED_DISPOSITION",
        "GENERATE_GENERATION_SEED",
        "BUILD_PROTECTED_POPULATION",
    ):
        assert required in source

    import ast as _ast

    tree = _ast.parse(
        source
    )

    imported_modules = set()
    imported_names = set()
    executable_names = set()
    call_sites = []

    for current in _ast.walk(
        tree
    ):
        if isinstance(
            current,
            _ast.Import,
        ):
            for alias in current.names:
                imported_modules.add(
                    alias.name
                )

        elif isinstance(
            current,
            _ast.ImportFrom,
        ):
            if current.module is not None:
                imported_modules.add(
                    current.module
                )

            for alias in current.names:
                imported_names.add(
                    alias.asname
                    or alias.name
                )

        elif isinstance(
            current,
            _ast.Name,
        ):
            executable_names.add(
                current.id
            )

        elif isinstance(
            current,
            _ast.Call,
        ):
            if isinstance(
                current.func,
                _ast.Name,
            ):
                call_name = (
                    current.func.id
                )

            elif isinstance(
                current.func,
                _ast.Attribute,
            ):
                parts = []
                cursor = current.func

                while isinstance(
                    cursor,
                    _ast.Attribute,
                ):
                    parts.append(
                        cursor.attr
                    )
                    cursor = cursor.value

                if isinstance(
                    cursor,
                    _ast.Name,
                ):
                    parts.append(
                        cursor.id
                    )

                call_name = ".".join(
                    reversed(
                        parts
                    )
                )

            else:
                call_name = (
                    "<dynamic>"
                )

            call_sites.append(
                (
                    call_name,
                    current.lineno,
                    current,
                )
            )

    assert not any(
        module == "secrets"
        or module.startswith(
            "secrets."
        )
        for module
        in imported_modules
    )

    assert "c1_raw_seed" not in executable_names

    assert not any(
        "p09_4_protected_evaluator"
        in module
        for module
        in imported_modules
    )

    forbidden_call_tails = {
        "run_scientific_arm",
        "execute_checkpoint_replay",
        "evaluate_protected_records",
        "evaluate_protected_study",
        "evaluate_p09_4_protected_records",
        "evaluate_p09_4_protected_study",
    }

    assert not any(
        call_name.split(
            "."
        )[
            -1
        ]
        in forbidden_call_tails
        for (
            call_name,
            _,
            _,
        )
        in call_sites
    )

    seed_factory_calls = [
        (
            line,
            current,
        )
        for (
            call_name,
            line,
            current,
        )
        in call_sites
        if call_name
        == "seed_factory"
    ]

    assert len(
        seed_factory_calls
    ) == 1

    seed_factory_line = (
        seed_factory_calls[
            0
        ][
            0
        ]
    )

    batch_claim_lines = []

    for current in _ast.walk(
        tree
    ):
        if not isinstance(
            current,
            _ast.Call,
        ):
            continue

        if not isinstance(
            current.func,
            _ast.Attribute,
        ):
            continue

        if current.func.attr != "mkdir":
            continue

        if not isinstance(
            current.func.value,
            _ast.Name,
        ):
            continue

        if current.func.value.id != "os":
            continue

        if not current.args:
            continue

        first = current.args[
            0
        ]

        if (
            isinstance(
                first,
                _ast.Name,
            )
            and first.id
            == "batch_directory"
        ):
            batch_claim_lines.append(
                current.lineno
            )

    assert len(
        batch_claim_lines
    ) == 1

    phase_lines = {}

    for current in _ast.walk(
        tree
    ):
        if not isinstance(
            current,
            _ast.Assign,
        ):
            continue

        if len(
            current.targets
        ) != 1:
            continue

        target = current.targets[
            0
        ]

        if not (
            isinstance(
                target,
                _ast.Name,
            )
            and target.id
            == "phase"
        ):
            continue

        if not isinstance(
            current.value,
            _ast.Constant,
        ):
            continue

        if isinstance(
            current.value.value,
            str,
        ):
            phase_lines[
                current.value.value
            ] = current.lineno

    assert (
        "PERSIST_STARTED_DISPOSITION"
        in phase_lines
    )

    assert (
        "GENERATE_GENERATION_SEED"
        in phase_lines
    )

    disposition_write_lines = []

    for (
        call_name,
        line,
        current,
    ) in call_sites:
        if call_name != "_atomic_write_new":
            continue

        if not current.args:
            continue

        first = current.args[
            0
        ]

        if (
            isinstance(
                first,
                _ast.Name,
            )
            and first.id
            == "disposition_path"
        ):
            disposition_write_lines.append(
                line
            )

    pre_seed_disposition_writes = [
        line
        for line
        in disposition_write_lines
        if line
        < seed_factory_line
    ]

    assert pre_seed_disposition_writes

    assert (
        batch_claim_lines[
            0
        ]
        < min(
            pre_seed_disposition_writes
        )
        < seed_factory_line
    )

    assert (
        phase_lines[
            "PERSIST_STARTED_DISPOSITION"
        ]
        < min(
            pre_seed_disposition_writes
        )
        < phase_lines[
            "GENERATE_GENERATION_SEED"
        ]
        < seed_factory_line
    )

    assert "secrets" not in imported_names

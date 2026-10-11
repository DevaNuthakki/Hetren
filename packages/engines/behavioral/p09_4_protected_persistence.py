"""One-shot P09.4 protected population persistence.

This module contains filesystem and commitment mechanics only.

The caller supplies a seed factory.

The module claims the protected batch identity before invoking that factory.

It persists a STARTED disposition before seed creation.

It never imports or calls scientific-arm treatment execution.

It never creates or manages the separately preregistered C1 seed.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re

from packages.core.hetren_diagnosis.contracts import (
    ContractError,
    canonical_sha256,
)
from packages.engines.behavioral.p09_4_protected_generation import (
    build_development_generation_plan,
)
from packages.engines.behavioral.p09_4_protected_materialization import (
    build_public_materialization_spec,
    materialize_protected_replay_baseline,
)


_BATCH_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*$"
)

_HEX_40_RE = re.compile(
    r"^[0-9a-f]{40}$"
)

_HEX_64_RE = re.compile(
    r"^[0-9a-f]{64}$"
)


class P094GenerationAlreadyExists(
    RuntimeError
):
    """Raised before seed creation when a protected identity already exists."""


class P094GenerationPersistenceError(
    RuntimeError
):
    """Raised after an attempted identity claim has been preserved."""


@dataclass(
    frozen=True
)
class P094GenerationPersistenceResult:
    batch_id: str
    batch_directory: Path

    generation_seed_sha256: str
    generation_seed_commitment_file_sha256: str

    public_population_manifest_sha256: str
    hidden_assignment_manifest_sha256: str
    generation_record_sha256: str

    repository_head_commit_id: str
    source_commit: str

    generator_module_sha256: str
    materializer_module_sha256: str
    persistence_module_sha256: str


def _require_batch_id(
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or not _BATCH_RE.fullmatch(
            value
        )
        or value
        in {
            ".",
            "..",
        }
    ):
        raise ContractError(
            "batch_id must be a safe non-empty identifier"
        )

    return value


def _require_commit(
    value: object,
    name: str,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or not _HEX_40_RE.fullmatch(
            value
        )
    ):
        raise ContractError(
            f"{name} must be a lowercase 40-character Git commit"
        )

    return value


def _require_sha256(
    value: object,
    name: str,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or not _HEX_64_RE.fullmatch(
            value
        )
    ):
        raise ContractError(
            f"{name} must be a lowercase SHA-256 hex digest"
        )

    return value


def _json_bytes(
    payload: object,
) -> bytes:
    return (
        json.dumps(
            payload,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
            ensure_ascii=False,
        ).encode(
            "utf-8"
        )
        + b"\n"
    )


def _sha256_bytes(
    data: bytes,
) -> str:
    return hashlib.sha256(
        data
    ).hexdigest()


def _fsync_directory(
    directory: Path,
) -> None:
    fd = os.open(
        directory,
        os.O_RDONLY,
    )

    try:
        os.fsync(
            fd
        )

    finally:
        os.close(
            fd
        )


def _write_all(
    fd: int,
    data: bytes,
) -> None:
    view = memoryview(
        data
    )

    offset = 0

    while offset < len(
        view
    ):
        written = os.write(
            fd,
            view[
                offset:
            ],
        )

        if written <= 0:
            raise OSError(
                "short write while persisting protected artifact"
            )

        offset += written


def _atomic_write_new(
    path: Path,
    data: bytes,
    *,
    mode: int,
) -> None:
    if os.path.lexists(
        path
    ):
        raise FileExistsError(
            path
        )

    temporary = path.with_name(
        "."
        + path.name
        + ".new.tmp"
    )

    if os.path.lexists(
        temporary
    ):
        raise FileExistsError(
            temporary
        )

    fd = os.open(
        temporary,
        (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
        ),
        mode,
    )

    try:
        _write_all(
            fd,
            data,
        )

        os.fsync(
            fd
        )

    finally:
        os.close(
            fd
        )

    os.chmod(
        temporary,
        mode,
    )

    os.replace(
        temporary,
        path,
    )

    os.chmod(
        path,
        mode,
    )

    _fsync_directory(
        path.parent
    )


def _atomic_replace(
    path: Path,
    data: bytes,
    *,
    mode: int,
) -> None:
    temporary = path.with_name(
        "."
        + path.name
        + ".replace.tmp"
    )

    if os.path.lexists(
        temporary
    ):
        raise FileExistsError(
            temporary
        )

    fd = os.open(
        temporary,
        (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
        ),
        mode,
    )

    try:
        _write_all(
            fd,
            data,
        )

        os.fsync(
            fd
        )

    finally:
        os.close(
            fd
        )

    os.chmod(
        temporary,
        mode,
    )

    os.replace(
        temporary,
        path,
    )

    os.chmod(
        path,
        mode,
    )

    _fsync_directory(
        path.parent
    )


def _disposition_payload(
    *,
    batch_id: str,
    status: str,
    phase: str,
    protocol_sha256: str,
    source_commit: str,
    repository_head_commit_id: str,
    generator_module_sha256: str,
    materializer_module_sha256: str,
    persistence_module_sha256: str,
    generation_seed_persisted: bool,
    generation_seed_sha256: str | None,
    generation_seed_commitment_file_sha256: str | None = None,
    public_population_manifest_sha256: str | None = None,
    hidden_assignment_manifest_sha256: str | None = None,
    generation_record_sha256: str | None = None,
    failure_type: str | None = None,
) -> dict[
    str,
    object,
]:
    return {
        "record_type":
            "P094ProtectedGenerationDisposition",

        "schema_version":
            1,

        "batch_id":
            batch_id,

        "status":
            status,

        "phase":
            phase,

        "protocol_sha256":
            protocol_sha256,

        "source_commit":
            source_commit,

        "repository_head_commit_id":
            repository_head_commit_id,

        "generator_module_sha256":
            generator_module_sha256,

        "materializer_module_sha256":
            materializer_module_sha256,

        "persistence_module_sha256":
            persistence_module_sha256,

        "generation_seed_persisted":
            generation_seed_persisted,

        "generation_seed_sha256":
            generation_seed_sha256,

        "generation_seed_commitment_file_sha256":
            generation_seed_commitment_file_sha256,

        "public_population_manifest_sha256":
            public_population_manifest_sha256,

        "hidden_assignment_manifest_sha256":
            hidden_assignment_manifest_sha256,

        "generation_record_sha256":
            generation_record_sha256,

        "failure_type":
            failure_type,
    }


def _build_population_payloads(
    *,
    raw_generation_seed: bytes,
    batch_id: str,
    protocol_sha256: str,
    source_commit: str,
    generation_seed_sha256: str,
) -> tuple[
    dict[str, object],
    dict[str, object],
    str,
]:
    plan = build_development_generation_plan(
        raw_seed=(
            raw_generation_seed
        ),
        protocol_sha256=(
            protocol_sha256
        ),
        source_commit=(
            source_commit
        ),
    )

    if len(
        plan.public_slots
    ) != 144:
        raise ContractError(
            "protected generation plan must contain exactly 144 public slots"
        )

    if len(
        plan.hidden_assignments
    ) != 144:
        raise ContractError(
            "protected generation plan must contain exactly 144 hidden assignments"
        )

    plan_commitment_payload = (
        plan.seed_commitment.canonical_payload()
    )

    scalar_commitment_values = {
        value
        for value
        in plan_commitment_payload.values()
        if isinstance(
            value,
            str,
        )
    }

    if (
        generation_seed_sha256
        not in scalar_commitment_values
    ):
        raise ContractError(
            "generation-plan commitment does not bind persisted generation seed"
        )

    plan_seed_commitment_record_sha256 = (
        canonical_sha256(
            plan_commitment_payload
        )
    )

    assignment_by_case = {
        assignment.case_id:
            assignment
        for assignment
        in plan.hidden_assignments
    }

    public_case_ids = {
        slot.case_id
        for slot
        in plan.public_slots
    }

    if set(
        assignment_by_case
    ) != public_case_ids:
        raise ContractError(
            "public-slot and hidden-assignment case sets differ"
        )

    public_cases = []

    for slot in plan.public_slots:
        assignment = (
            assignment_by_case[
                slot.case_id
            ]
        )

        spec = (
            build_public_materialization_spec(
                slot
            )
        )

        baseline = (
            materialize_protected_replay_baseline(
                public_slot=slot,
                hidden_assignment=assignment,
            )
        )

        if baseline.run.passed:
            raise ContractError(
                "protected population contains a passing pre-diagnosis baseline"
            )

        checkpoint_records = tuple(
            {
                "checkpoint_key":
                    checkpoint.key,

                "checkpoint_state_sha256":
                    checkpoint.state_sha256,

                "checkpoint":
                    checkpoint.canonical_payload(),
            }
            for checkpoint
            in baseline.checkpoints
        )

        public_cases.append(
            {
                "case_id":
                    slot.case_id,

                "template_id":
                    slot.template_id,

                "public_configuration_sha256":
                    slot.public_configuration_sha256,

                "public_slot":
                    slot.canonical_payload(),

                "materialization_spec":
                    spec.canonical_payload(),

                "materialization_spec_sha256":
                    spec.materialization_spec_sha256,

                "baseline":
                    {
                        "run_id":
                            baseline.run.run_id,

                        "passed":
                            False,

                        "trace_sha256":
                            baseline.run.trace.trace_sha256,

                        "report":
                            baseline.run.report.canonical_payload(),

                        "report_sha256":
                            baseline.run.report.report_sha256,

                        "checkpoints":
                            checkpoint_records,
                    },
            }
        )

    public_manifest = {
        "record_type":
            "P094ProtectedPublicPopulationManifest",

        "schema_version":
            1,

        "batch_id":
            batch_id,

        "protocol_sha256":
            protocol_sha256,

        "source_commit":
            source_commit,

        "generation_seed_sha256":
            generation_seed_sha256,

        "plan_seed_commitment_record_sha256":
            plan_seed_commitment_record_sha256,

        "case_count":
            len(
                public_cases
            ),

        "cases":
            tuple(
                public_cases
            ),
    }

    hidden_manifest = {
        "record_type":
            "P094ProtectedHiddenAssignmentManifest",

        "schema_version":
            1,

        "batch_id":
            batch_id,

        "protocol_sha256":
            protocol_sha256,

        "source_commit":
            source_commit,

        "generation_seed_sha256":
            generation_seed_sha256,

        "plan_seed_commitment_record_sha256":
            plan_seed_commitment_record_sha256,

        "assignment_count":
            len(
                plan.hidden_assignments
            ),

        "assignments":
            tuple(
                assignment.canonical_payload()
                for assignment
                in plan.hidden_assignments
            ),
    }

    return (
        public_manifest,
        hidden_manifest,
        plan_seed_commitment_record_sha256,
    )


def persist_p09_4_generation_attempt(
    *,
    artifact_root: Path,
    batch_id: str,
    protocol_sha256: str,
    source_commit: str,
    repository_head_commit_id: str,
    generator_module_sha256: str,
    materializer_module_sha256: str,
    persistence_module_sha256: str,
    seed_factory: Callable[
        [
            int
        ],
        bytes,
    ],
) -> P094GenerationPersistenceResult:
    """Claim and persist exactly one P09.4 generation identity."""

    if not isinstance(
        artifact_root,
        Path,
    ):
        raise ContractError(
            "artifact_root must be a pathlib.Path"
        )

    batch_id = (
        _require_batch_id(
            batch_id
        )
    )

    protocol_sha256 = (
        _require_sha256(
            protocol_sha256,
            "protocol_sha256",
        )
    )

    source_commit = (
        _require_commit(
            source_commit,
            "source_commit",
        )
    )

    repository_head_commit_id = (
        _require_commit(
            repository_head_commit_id,
            "repository_head_commit_id",
        )
    )

    generator_module_sha256 = (
        _require_sha256(
            generator_module_sha256,
            "generator_module_sha256",
        )
    )

    materializer_module_sha256 = (
        _require_sha256(
            materializer_module_sha256,
            "materializer_module_sha256",
        )
    )

    persistence_module_sha256 = (
        _require_sha256(
            persistence_module_sha256,
            "persistence_module_sha256",
        )
    )

    if not callable(
        seed_factory
    ):
        raise ContractError(
            "seed_factory must be callable"
        )

    artifact_root.mkdir(
        parents=True,
        exist_ok=True,
        mode=0o700,
    )

    if (
        not artifact_root.is_dir()
        or artifact_root.is_symlink()
    ):
        raise ContractError(
            "artifact_root must be a real directory"
        )

    os.chmod(
        artifact_root,
        0o700,
    )

    batch_directory = (
        artifact_root
        / batch_id
    )

    if os.path.lexists(
        batch_directory
    ):
        raise P094GenerationAlreadyExists(
            f"generation batch already exists: {batch_id}"
        )

    try:
        os.mkdir(
            batch_directory,
            0o700,
        )

    except FileExistsError as exc:
        raise P094GenerationAlreadyExists(
            f"generation batch already exists: {batch_id}"
        ) from exc

    public_directory = (
        batch_directory
        / "public"
    )

    evaluator_directory = (
        batch_directory
        / "evaluator"
    )

    disposition_path = (
        public_directory
        / "generation_disposition.json"
    )

    commitment_path = (
        public_directory
        / "generation_seed_commitment.json"
    )

    public_manifest_path = (
        public_directory
        / "public_population_manifest.json"
    )

    generation_record_path = (
        public_directory
        / "generation_record.json"
    )

    raw_seed_path = (
        evaluator_directory
        / "generation_raw_seed.bin"
    )

    hidden_manifest_path = (
        evaluator_directory
        / "hidden_assignment_manifest.json"
    )

    phase = "CLAIMED"

    generation_seed_persisted = False
    generation_seed_sha256 = None

    generation_seed_commitment_file_sha256 = None
    public_population_manifest_sha256 = None
    hidden_assignment_manifest_sha256 = None
    generation_record_sha256 = None

    started = (
        _disposition_payload(
            batch_id=batch_id,
            status="STARTED",
            phase="CLAIMED",
            protocol_sha256=protocol_sha256,
            source_commit=source_commit,
            repository_head_commit_id=(
                repository_head_commit_id
            ),
            generator_module_sha256=(
                generator_module_sha256
            ),
            materializer_module_sha256=(
                materializer_module_sha256
            ),
            persistence_module_sha256=(
                persistence_module_sha256
            ),
            generation_seed_persisted=False,
            generation_seed_sha256=None,
        )
    )

    try:
        phase = "FSYNC_BATCH_CLAIM"

        _fsync_directory(
            artifact_root
        )

        phase = "CREATE_PUBLIC_DIRECTORY"

        os.mkdir(
            public_directory,
            0o700,
        )

        _fsync_directory(
            batch_directory
        )

        phase = "PERSIST_STARTED_DISPOSITION"

        _atomic_write_new(
            disposition_path,
            _json_bytes(
                started
            ),
            mode=0o600,
        )

        phase = "CREATE_EVALUATOR_DIRECTORY"

        os.mkdir(
            evaluator_directory,
            0o700,
        )

        _fsync_directory(
            batch_directory
        )

        phase = "GENERATE_GENERATION_SEED"

        raw_generation_seed = (
            seed_factory(
                32
            )
        )

        if (
            not isinstance(
                raw_generation_seed,
                bytes,
            )
            or len(
                raw_generation_seed
            )
            != 32
        ):
            raise ContractError(
                "seed_factory must return exactly 32 bytes"
            )

        generation_seed_sha256 = (
            hashlib.sha256(
                raw_generation_seed
            ).hexdigest()
        )

        phase = "PERSIST_GENERATION_RAW_SEED"

        _atomic_write_new(
            raw_seed_path,
            raw_generation_seed,
            mode=0o600,
        )

        generation_seed_persisted = True

        phase = "PERSIST_GENERATION_SEED_COMMITMENT"

        generation_seed_commitment = {
            "record_type":
                "P094ProtectedGenerationSeedCommitment",

            "schema_version":
                1,

            "batch_id":
                batch_id,

            "protocol_sha256":
                protocol_sha256,

            "source_commit":
                source_commit,

            "generation_seed_sha256":
                generation_seed_sha256,
        }

        generation_seed_commitment_bytes = (
            _json_bytes(
                generation_seed_commitment
            )
        )

        generation_seed_commitment_file_sha256 = (
            _sha256_bytes(
                generation_seed_commitment_bytes
            )
        )

        _atomic_write_new(
            commitment_path,
            generation_seed_commitment_bytes,
            mode=0o600,
        )

        phase = "BUILD_PROTECTED_POPULATION"

        (
            public_population_manifest,
            hidden_assignment_manifest,
            plan_seed_commitment_record_sha256,
        ) = _build_population_payloads(
            raw_generation_seed=(
                raw_generation_seed
            ),
            batch_id=batch_id,
            protocol_sha256=(
                protocol_sha256
            ),
            source_commit=(
                source_commit
            ),
            generation_seed_sha256=(
                generation_seed_sha256
            ),
        )

        phase = "PERSIST_PUBLIC_POPULATION_MANIFEST"

        public_population_manifest_bytes = (
            _json_bytes(
                public_population_manifest
            )
        )

        public_population_manifest_sha256 = (
            _sha256_bytes(
                public_population_manifest_bytes
            )
        )

        _atomic_write_new(
            public_manifest_path,
            public_population_manifest_bytes,
            mode=0o600,
        )

        phase = "PERSIST_HIDDEN_ASSIGNMENT_MANIFEST"

        hidden_assignment_manifest_bytes = (
            _json_bytes(
                hidden_assignment_manifest
            )
        )

        hidden_assignment_manifest_sha256 = (
            _sha256_bytes(
                hidden_assignment_manifest_bytes
            )
        )

        _atomic_write_new(
            hidden_manifest_path,
            hidden_assignment_manifest_bytes,
            mode=0o600,
        )

        phase = "PERSIST_GENERATION_RECORD"

        generation_record = {
            "record_type":
                "P094ProtectedGenerationRecord",

            "schema_version":
                1,

            "batch_id":
                batch_id,

            "protocol_sha256":
                protocol_sha256,

            "source_commit":
                source_commit,

            "repository_head_commit_id":
                repository_head_commit_id,

            "generator_module_sha256":
                generator_module_sha256,

            "materializer_module_sha256":
                materializer_module_sha256,

            "persistence_module_sha256":
                persistence_module_sha256,

            "generation_seed_sha256":
                generation_seed_sha256,

            "generation_seed_commitment_file_sha256":
                generation_seed_commitment_file_sha256,

            "plan_seed_commitment_record_sha256":
                plan_seed_commitment_record_sha256,

            "public_population_manifest_sha256":
                public_population_manifest_sha256,

            "hidden_assignment_manifest_sha256":
                hidden_assignment_manifest_sha256,

            "artifact_paths":
                {
                    "generation_disposition":
                        "public/generation_disposition.json",

                    "generation_seed_commitment":
                        "public/generation_seed_commitment.json",

                    "public_population_manifest":
                        "public/public_population_manifest.json",

                    "generation_record":
                        "public/generation_record.json",

                    "generation_raw_seed":
                        "evaluator/generation_raw_seed.bin",

                    "hidden_assignment_manifest":
                        "evaluator/hidden_assignment_manifest.json",
                },
        }

        generation_record_bytes = (
            _json_bytes(
                generation_record
            )
        )

        generation_record_sha256 = (
            _sha256_bytes(
                generation_record_bytes
            )
        )

        _atomic_write_new(
            generation_record_path,
            generation_record_bytes,
            mode=0o600,
        )

        phase = "SUCCEEDED"

        succeeded = (
            _disposition_payload(
                batch_id=batch_id,
                status="SUCCEEDED",
                phase=phase,
                protocol_sha256=(
                    protocol_sha256
                ),
                source_commit=(
                    source_commit
                ),
                repository_head_commit_id=(
                    repository_head_commit_id
                ),
                generator_module_sha256=(
                    generator_module_sha256
                ),
                materializer_module_sha256=(
                    materializer_module_sha256
                ),
                persistence_module_sha256=(
                    persistence_module_sha256
                ),
                generation_seed_persisted=True,
                generation_seed_sha256=(
                    generation_seed_sha256
                ),
                generation_seed_commitment_file_sha256=(
                    generation_seed_commitment_file_sha256
                ),
                public_population_manifest_sha256=(
                    public_population_manifest_sha256
                ),
                hidden_assignment_manifest_sha256=(
                    hidden_assignment_manifest_sha256
                ),
                generation_record_sha256=(
                    generation_record_sha256
                ),
            )
        )

        _atomic_replace(
            disposition_path,
            _json_bytes(
                succeeded
            ),
            mode=0o600,
        )

        return P094GenerationPersistenceResult(
            batch_id=batch_id,
            batch_directory=(
                batch_directory
            ),
            generation_seed_sha256=(
                generation_seed_sha256
            ),
            generation_seed_commitment_file_sha256=(
                generation_seed_commitment_file_sha256
            ),
            public_population_manifest_sha256=(
                public_population_manifest_sha256
            ),
            hidden_assignment_manifest_sha256=(
                hidden_assignment_manifest_sha256
            ),
            generation_record_sha256=(
                generation_record_sha256
            ),
            repository_head_commit_id=(
                repository_head_commit_id
            ),
            source_commit=(
                source_commit
            ),
            generator_module_sha256=(
                generator_module_sha256
            ),
            materializer_module_sha256=(
                materializer_module_sha256
            ),
            persistence_module_sha256=(
                persistence_module_sha256
            ),
        )

    except Exception as exc:
        failed = (
            _disposition_payload(
                batch_id=batch_id,
                status="FAILED",
                phase=phase,
                protocol_sha256=(
                    protocol_sha256
                ),
                source_commit=(
                    source_commit
                ),
                repository_head_commit_id=(
                    repository_head_commit_id
                ),
                generator_module_sha256=(
                    generator_module_sha256
                ),
                materializer_module_sha256=(
                    materializer_module_sha256
                ),
                persistence_module_sha256=(
                    persistence_module_sha256
                ),
                generation_seed_persisted=(
                    generation_seed_persisted
                ),
                generation_seed_sha256=(
                    generation_seed_sha256
                ),
                generation_seed_commitment_file_sha256=(
                    generation_seed_commitment_file_sha256
                ),
                public_population_manifest_sha256=(
                    public_population_manifest_sha256
                ),
                hidden_assignment_manifest_sha256=(
                    hidden_assignment_manifest_sha256
                ),
                generation_record_sha256=(
                    generation_record_sha256
                ),
                failure_type=(
                    type(
                        exc
                    ).__name__
                ),
            )
        )

        try:
            if public_directory.exists():
                if (
                    not public_directory.is_dir()
                    or public_directory.is_symlink()
                ):
                    raise OSError(
                        "public generation path is not a safe directory"
                    )

            else:
                os.mkdir(
                    public_directory,
                    0o700,
                )

                _fsync_directory(
                    batch_directory
                )

            failed_bytes = (
                _json_bytes(
                    failed
                )
            )

            if disposition_path.exists():
                _atomic_replace(
                    disposition_path,
                    failed_bytes,
                    mode=0o600,
                )

            else:
                _atomic_write_new(
                    disposition_path,
                    failed_bytes,
                    mode=0o600,
                )

        except Exception as disposition_exc:
            raise P094GenerationPersistenceError(
                "generation failed after protected identity was claimed; "
                "failure disposition could not be persisted; "
                "attempt remains consumed"
            ) from disposition_exc

        raise P094GenerationPersistenceError(
            "generation attempt failed; protected identity is consumed"
        ) from exc


__all__ = [
    "P094GenerationAlreadyExists",
    "P094GenerationPersistenceError",
    "P094GenerationPersistenceResult",
    "persist_p09_4_generation_attempt",
]

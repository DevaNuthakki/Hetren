"""One-shot persistence for the P09.3 H1 protected-generation attempt.

This module provides persistence capability only.

It does not itself choose a production artifact path and it does not call
``secrets.token_bytes``. The caller supplies a seed factory.

The production CLI supplies ``secrets.token_bytes``.

Development tests supply fixed deterministic seed factories and temporary
directories.

Scientific invariants:

- one batch identity is single-use;
- an existing batch directory blocks every rerun;
- raw seed bytes are evaluator-only;
- the public commitment contains only SHA-256 of the seed;
- Python-level failures preserve the attempt directory;
- if the seed was persisted before failure, it is not deleted or rerolled;
- failure disposition never includes raw seed bytes;
- treatment-visible manifest remains separate from evaluator truth;
- writes use fsync plus atomic replacement inside the fresh batch directory.

Arbitrary sudden power loss between two filesystem operations cannot be made
fully transactional by application code alone. Each completed file write and
directory update is fsynced to minimize that boundary.
"""

from collections.abc import Callable
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re

from packages.core.hetren_diagnosis.contracts import (
    ContractError,
)
from packages.engines.behavioral.h1_controlled_active_diagnosis_generation import (
    build_h1_batch_manifests,
)


_SHA256 = re.compile(
    r"^[0-9a-f]{64}$"
)

_GIT_COMMIT_ID = re.compile(
    r"^[0-9a-f]{40}$"
)

_BATCH_ID = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
)


class H1GenerationAlreadyExists(
    RuntimeError
):
    """Raised before seed creation when a batch identity is already occupied."""


class H1GenerationPersistenceError(
    RuntimeError
):
    """Raised when generation failed after the attempt directory was claimed."""


@dataclass(frozen=True)
class H1GenerationPersistenceResult:
    """Safe result object that intentionally excludes raw seed bytes."""

    batch_id: str
    batch_directory: Path
    seed_commitment_sha256: str
    seed_commitment_record_sha256: str
    public_manifest_sha256: str
    hidden_truth_manifest_sha256: str
    generation_record_sha256: str
    repository_head_commit_id: str
    generator_module_sha256: str


def _require_sha256(
    value: object,
    name: str,
) -> str:
    if (
        not isinstance(value, str)
        or _SHA256.fullmatch(value) is None
    ):
        raise ContractError(
            f"{name} must be a lowercase SHA-256 digest"
        )

    return value


def _require_git_commit_id(
    value: object,
    name: str,
) -> str:
    if (
        not isinstance(value, str)
        or _GIT_COMMIT_ID.fullmatch(value) is None
    ):
        raise ContractError(
            f"{name} must be a lowercase 40-hex Git commit ID"
        )

    return value


def _require_batch_id(
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or _BATCH_ID.fullmatch(value) is None
        or value in {
            ".",
            "..",
        }
    ):
        raise ContractError(
            "batch_id must be one safe path-segment identifier"
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
            allow_nan=False,
        )
        + "\n"
    ).encode(
        "utf-8"
    )


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
    remaining = memoryview(
        data
    )

    while remaining:
        written = os.write(
            fd,
            remaining,
        )

        if written <= 0:
            raise OSError(
                "short filesystem write"
            )

        remaining = remaining[
            written:
        ]


def _atomic_write_new(
    path: Path,
    data: bytes,
    *,
    mode: int,
) -> None:
    if path.exists():
        raise FileExistsError(
            str(path)
        )

    temporary = path.with_name(
        "." + path.name + ".tmp"
    )

    if temporary.exists():
        raise FileExistsError(
            str(temporary)
        )

    fd = None

    try:
        fd = os.open(
            temporary,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL,
            mode,
        )

        _write_all(
            fd,
            data,
        )

        os.fsync(
            fd
        )

        os.close(
            fd
        )

        fd = None

        if path.exists():
            raise FileExistsError(
                str(path)
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

    except Exception:
        if fd is not None:
            try:
                os.close(
                    fd
                )
            except OSError:
                pass

        try:
            temporary.unlink()
        except FileNotFoundError:
            pass

        raise


def _atomic_replace(
    path: Path,
    data: bytes,
    *,
    mode: int,
) -> None:
    temporary = path.with_name(
        "." + path.name + ".replace.tmp"
    )

    if temporary.exists():
        raise FileExistsError(
            str(temporary)
        )

    fd = None

    try:
        fd = os.open(
            temporary,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL,
            mode,
        )

        _write_all(
            fd,
            data,
        )

        os.fsync(
            fd
        )

        os.close(
            fd
        )

        fd = None

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

    except Exception:
        if fd is not None:
            try:
                os.close(
                    fd
                )
            except OSError:
                pass

        try:
            temporary.unlink()
        except FileNotFoundError:
            pass

        raise


def _disposition_payload(
    *,
    batch_id: str,
    status: str,
    phase: str,
    protocol_sha256: str,
    harness_commit_id: str,
    repository_head_commit_id: str,
    generator_module_sha256: str,
    seed_persisted: bool,
    seed_commitment_sha256: str | None,
    public_manifest_sha256: str | None = None,
    hidden_truth_manifest_sha256: str | None = None,
    generation_record_sha256: str | None = None,
    failure_type: str | None = None,
) -> dict[str, object]:
    return {
        "record_type": "H1ProtectedGenerationDisposition",
        "schema_version": 1,
        "batch_id": batch_id,
        "status": status,
        "phase": phase,
        "protocol_sha256": protocol_sha256,
        "harness_commit_id": harness_commit_id,
        "repository_head_commit_id": repository_head_commit_id,
        "generator_module_sha256": generator_module_sha256,
        "seed_persisted": seed_persisted,
        "seed_commitment_sha256": seed_commitment_sha256,
        "public_manifest_sha256": public_manifest_sha256,
        "hidden_truth_manifest_sha256": hidden_truth_manifest_sha256,
        "generation_record_sha256": generation_record_sha256,
        "failure_type": failure_type,
    }


def persist_h1_generation_attempt(
    *,
    artifact_root: Path,
    batch_id: str,
    protocol_sha256: str,
    harness_commit_id: str,
    repository_head_commit_id: str,
    generator_module_sha256: str,
    seed_factory: Callable[[int], bytes],
) -> H1GenerationPersistenceResult:
    """Create one single-use separated generation attempt."""

    if not isinstance(
        artifact_root,
        Path,
    ):
        raise ContractError(
            "artifact_root must be a pathlib.Path"
        )

    batch_id = _require_batch_id(
        batch_id
    )

    protocol_sha256 = _require_sha256(
        protocol_sha256,
        "protocol_sha256",
    )

    harness_commit_id = _require_git_commit_id(
        harness_commit_id,
        "harness_commit_id",
    )

    repository_head_commit_id = _require_git_commit_id(
        repository_head_commit_id,
        "repository_head_commit_id",
    )

    generator_module_sha256 = _require_sha256(
        generator_module_sha256,
        "generator_module_sha256",
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

    os.chmod(
        artifact_root,
        0o700,
    )

    batch_directory = (
        artifact_root
        / batch_id
    )

    if batch_directory.exists():
        raise H1GenerationAlreadyExists(
            f"generation batch already exists: {batch_id}"
        )

    try:
        os.mkdir(
            batch_directory,
            0o700,
        )
    except FileExistsError as exc:
        raise H1GenerationAlreadyExists(
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

    seed_commitment_path = (
        public_directory
        / "seed_commitment.json"
    )

    public_manifest_path = (
        public_directory
        / "public_manifest.json"
    )

    generation_record_path = (
        public_directory
        / "generation_record.json"
    )

    raw_seed_path = (
        evaluator_directory
        / "raw_seed.bin"
    )

    hidden_manifest_path = (
        evaluator_directory
        / "hidden_truth_manifest.json"
    )

    phase = "CLAIMED"
    seed_persisted = False
    seed_sha256 = None

    public_manifest_sha256 = None
    hidden_manifest_sha256 = None
    generation_record_sha256 = None

    started = _disposition_payload(
        batch_id=batch_id,
        status="STARTED",
        phase="CLAIMED",
        protocol_sha256=protocol_sha256,
        harness_commit_id=harness_commit_id,
        repository_head_commit_id=repository_head_commit_id,
        generator_module_sha256=generator_module_sha256,
        seed_persisted=False,
        seed_commitment_sha256=None,
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

        phase = "GENERATE_SEED"

        raw_seed = seed_factory(
            32
        )

        if (
            not isinstance(raw_seed, bytes)
            or len(raw_seed) != 32
        ):
            raise ContractError(
                "seed_factory must return exactly 32 bytes"
            )

        seed_sha256 = hashlib.sha256(
            raw_seed
        ).hexdigest()

        phase = "PERSIST_RAW_SEED"

        _atomic_write_new(
            raw_seed_path,
            raw_seed,
            mode=0o600,
        )

        seed_persisted = True

        phase = "PERSIST_SEED_COMMITMENT"

        seed_commitment_payload = {
            "record_type": "H1SeedCommitment",
            "schema_version": 1,
            "batch_id": batch_id,
            "protocol_sha256": protocol_sha256,
            "harness_commit_id": harness_commit_id,
            "generator_id": (
                "h1-controlled-active-diagnosis-generator"
            ),
            "generator_version": "1",
            "seed_sha256": seed_sha256,
        }

        _atomic_write_new(
            seed_commitment_path,
            _json_bytes(
                seed_commitment_payload
            ),
            mode=0o600,
        )

        phase = "BUILD_MANIFESTS"

        generated = build_h1_batch_manifests(
            raw_seed=raw_seed,
            batch_id=batch_id,
            protocol_sha256=protocol_sha256,
            harness_commit_id=harness_commit_id,
        )

        if (
            generated.seed_commitment.seed_sha256
            != seed_sha256
        ):
            raise ContractError(
                "generator seed commitment differs from persisted seed"
            )

        phase = "PERSIST_PUBLIC_MANIFEST"

        _atomic_write_new(
            public_manifest_path,
            generated.public_manifest.canonical_json_bytes,
            mode=0o600,
        )

        public_manifest_sha256 = (
            generated.public_manifest.manifest_sha256
        )

        phase = "PERSIST_HIDDEN_MANIFEST"

        _atomic_write_new(
            hidden_manifest_path,
            generated.hidden_truth_manifest.canonical_json_bytes,
            mode=0o600,
        )

        hidden_manifest_sha256 = (
            generated.hidden_truth_manifest.manifest_sha256
        )

        phase = "PERSIST_GENERATION_RECORD"

        generation_record = {
            "record_type": "H1ProtectedGenerationRecord",
            "schema_version": 1,
            "batch_id": batch_id,
            "protocol_sha256": protocol_sha256,
            "harness_commit_id": harness_commit_id,
            "repository_head_commit_id": repository_head_commit_id,
            "generator_module_sha256": generator_module_sha256,
            "seed_commitment_sha256": seed_sha256,
            "seed_commitment_record_sha256": (
                generated.seed_commitment.commitment_record_sha256
            ),
            "public_manifest_sha256": public_manifest_sha256,
            "hidden_truth_manifest_sha256": hidden_manifest_sha256,
            "artifact_paths": {
                "seed_commitment": (
                    "public/seed_commitment.json"
                ),
                "public_manifest": (
                    "public/public_manifest.json"
                ),
                "generation_disposition": (
                    "public/generation_disposition.json"
                ),
                "raw_seed": (
                    "evaluator/raw_seed.bin"
                ),
                "hidden_truth_manifest": (
                    "evaluator/hidden_truth_manifest.json"
                ),
            },
        }

        generation_record_bytes = _json_bytes(
            generation_record
        )

        generation_record_sha256 = hashlib.sha256(
            generation_record_bytes
        ).hexdigest()

        _atomic_write_new(
            generation_record_path,
            generation_record_bytes,
            mode=0o600,
        )

        phase = "SUCCEEDED"

        succeeded = _disposition_payload(
            batch_id=batch_id,
            status="SUCCEEDED",
            phase=phase,
            protocol_sha256=protocol_sha256,
            harness_commit_id=harness_commit_id,
            repository_head_commit_id=repository_head_commit_id,
            generator_module_sha256=generator_module_sha256,
            seed_persisted=True,
            seed_commitment_sha256=seed_sha256,
            public_manifest_sha256=public_manifest_sha256,
            hidden_truth_manifest_sha256=hidden_manifest_sha256,
            generation_record_sha256=generation_record_sha256,
        )

        _atomic_replace(
            disposition_path,
            _json_bytes(
                succeeded
            ),
            mode=0o600,
        )

        return H1GenerationPersistenceResult(
            batch_id=batch_id,
            batch_directory=batch_directory,
            seed_commitment_sha256=seed_sha256,
            seed_commitment_record_sha256=(
                generated.seed_commitment.commitment_record_sha256
            ),
            public_manifest_sha256=public_manifest_sha256,
            hidden_truth_manifest_sha256=hidden_manifest_sha256,
            generation_record_sha256=generation_record_sha256,
            repository_head_commit_id=repository_head_commit_id,
            generator_module_sha256=generator_module_sha256,
        )

    except Exception as exc:
        failed = _disposition_payload(
            batch_id=batch_id,
            status="FAILED",
            phase=phase,
            protocol_sha256=protocol_sha256,
            harness_commit_id=harness_commit_id,
            repository_head_commit_id=repository_head_commit_id,
            generator_module_sha256=generator_module_sha256,
            seed_persisted=seed_persisted,
            seed_commitment_sha256=seed_sha256,
            public_manifest_sha256=public_manifest_sha256,
            hidden_truth_manifest_sha256=hidden_manifest_sha256,
            generation_record_sha256=generation_record_sha256,
            failure_type=type(
                exc
            ).__name__,
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

            failed_bytes = _json_bytes(
                failed
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
            raise H1GenerationPersistenceError(
                "generation failed after batch identity was claimed; "
                "failure disposition could not be persisted; "
                "attempt remains consumed"
            ) from disposition_exc

        raise H1GenerationPersistenceError(
            "generation attempt failed; attempt preserved and cannot be rerun"
        ) from exc


__all__ = [
    "H1GenerationAlreadyExists",
    "H1GenerationPersistenceError",
    "H1GenerationPersistenceResult",
    "persist_h1_generation_attempt",
]

"""Synthetic-only one-shot P09.4 C1 persistence development fixture.

Not a protected K5D seed generator or an authorized production artifact schema.
No randomness source, production CLI, or scientific-arm execution is present.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile

from packages.core.hetren_diagnosis.contracts import ContractError
from packages.engines.behavioral.p09_4_c1_commitment import (
    build_development_c1_commitment,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_IDENTITY = "development_c1_v1"
_HEX_40 = re.compile(r"^[0-9a-f]{40}$")
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")


class P094DevelopmentC1AlreadyExists(RuntimeError):
    """An already claimed development identity cannot be rerolled."""


class P094DevelopmentC1PersistenceError(RuntimeError):
    """An attempt failed after its synthetic identity was claimed."""


@dataclass(frozen=True)
class P094DevelopmentC1PersistenceResult:
    batch_directory: Path
    seed_sha256: str
    commitment_file_sha256: str


def _require_digest(value: object, pattern: re.Pattern[str], label: str) -> None:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ContractError(f"invalid {label}")


def _preflight(
    root: Path,
    protocol_sha256: str,
    source_commit: str,
    generation_seed_sha256: str | None,
    seed_factory: Callable[[int], bytes],
) -> Path:
    if not isinstance(root, Path) or not root.is_absolute():
        raise ContractError("development root must be an absolute Path")

    if root.is_symlink() or not root.is_dir():
        raise ContractError("development root must be a non-symlink directory")

    resolved = root.resolve(strict=True)

    if resolved == _REPO_ROOT or _REPO_ROOT in resolved.parents:
        raise ContractError(
            "development persistence is forbidden inside the repository"
        )

    # Both the literal and canonical temporary roots are accepted to
    # accommodate platform-level aliases such as macOS /var.
    # No symbolic-link components are accepted below that trusted root.
    temporary_root = Path(tempfile.gettempdir())
    canonical_temporary_root = temporary_root.resolve(strict=True)

    relative = None
    lexical_base = None

    for candidate_base in (temporary_root, canonical_temporary_root):
        try:
            candidate_relative = root.relative_to(candidate_base)
        except ValueError:
            continue

        relative = candidate_relative
        lexical_base = candidate_base
        break

    if (
        relative is None
        or not relative.parts
        or ".." in relative.parts
        or resolved == canonical_temporary_root
        or canonical_temporary_root not in resolved.parents
    ):
        raise ContractError(
            "development root must be inside the temporary fixture area"
        )

    current = lexical_base

    for component in relative.parts:
        current = current / component

        if current.is_symlink():
            raise ContractError(
                "development root contains a symbolic-link component"
            )

    if stat.S_IMODE(root.stat().st_mode) & 0o077:
        raise ContractError(
            "development root must not be accessible by group or others"
        )

    _require_digest(protocol_sha256, _HEX_64, "protocol SHA256")
    _require_digest(source_commit, _HEX_40, "source commit")

    if generation_seed_sha256 is not None:
        _require_digest(
            generation_seed_sha256,
            _HEX_64,
            "generation commitment",
        )

    if not callable(seed_factory):
        raise ContractError("synthetic seed factory must be callable")

    return resolved


def _fsync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_all(descriptor: int, data: bytes) -> None:
    view = memoryview(data)
    offset = 0

    while offset < len(view):
        count = os.write(descriptor, view[offset:])
        if count <= 0:
            raise OSError(
                "short write while recording development evidence"
            )
        offset += count


def _write_new(path: Path, data: bytes) -> None:
    """Durably publish a new file without replacing an existing destination."""
    temporary = path.with_name("." + path.name + ".new.tmp")

    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )

    try:
        try:
            os.fchmod(descriptor, 0o600)
            _write_all(descriptor, data)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

        os.link(temporary, path)
        _fsync_directory(path.parent)

    finally:
        if os.path.lexists(temporary):
            os.unlink(temporary)
            _fsync_directory(path.parent)


def _replace_disposition(path: Path, data: bytes) -> None:
    temporary = path.with_name("." + path.name + ".replace.tmp")

    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )

    try:
        try:
            os.fchmod(descriptor, 0o600)
            _write_all(descriptor, data)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

        os.replace(temporary, path)
        _fsync_directory(path.parent)

    finally:
        if os.path.lexists(temporary):
            os.unlink(temporary)
            _fsync_directory(path.parent)


def _json_bytes(payload: dict[str, object]) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _disposition(
    *,
    status: str,
    phase: str,
    protocol_sha256: str,
    source_commit: str,
    seed_persisted: bool,
    seed_sha256: str | None,
    failure_type: str | None = None,
) -> bytes:
    return _json_bytes({
        "record_type": "P094DevelopmentC1Disposition",
        "development_only": True,
        "schema_version": 1,
        "identity": _IDENTITY,
        "status": status,
        "phase": phase,
        "protocol_sha256": protocol_sha256,
        "source_commit": source_commit,
        "seed_persisted": seed_persisted,
        "seed_sha256": seed_sha256,
        "failure_type": failure_type,
    })


def persist_development_c1_attempt(
    *,
    development_root: Path,
    protocol_sha256: str,
    source_commit: str,
    seed_factory: Callable[[int], bytes],
    generation_seed_sha256: str | None = None,
) -> P094DevelopmentC1PersistenceResult:
    """Exercise one-shot persistence using injected synthetic seed fixtures."""
    root = _preflight(
        development_root,
        protocol_sha256,
        source_commit,
        generation_seed_sha256,
        seed_factory,
    )

    batch = root / _IDENTITY

    if os.path.lexists(batch):
        raise P094DevelopmentC1AlreadyExists(
            "development identity already consumed"
        )

    try:
        os.mkdir(batch, 0o700)
    except FileExistsError as exc:
        raise P094DevelopmentC1AlreadyExists(
            "development identity already consumed"
        ) from exc

    public = batch / "public"
    treatment = batch / "treatment"
    disposition = public / "c1_seed_disposition.json"
    raw_file = treatment / "c1_raw_seed.bin"
    commitment_file = public / "c1_seed_commitment.json"

    phase = "CLAIMED"
    seed_persisted = False
    seed_sha256 = None

    try:
        phase = "FSYNC_CLAIM"
        _fsync_directory(root)

        phase = "CREATE_PUBLIC_DIRECTORY"
        os.mkdir(public, 0o700)
        _fsync_directory(batch)

        phase = "PERSIST_STARTED_DISPOSITION"
        _write_new(disposition, _disposition(
            status="STARTED",
            phase="CLAIMED",
            protocol_sha256=protocol_sha256,
            source_commit=source_commit,
            seed_persisted=False,
            seed_sha256=None,
        ))

        phase = "CREATE_TREATMENT_DIRECTORY"
        os.mkdir(treatment, 0o700)
        _fsync_directory(batch)

        phase = "GENERATE_SYNTHETIC_C1_SEED"
        raw_seed = seed_factory(32)

        if type(raw_seed) is not bytes or len(raw_seed) != 32:
            raise ContractError(
                "synthetic C1 seed must be exactly 32 bytes"
            )

        seed_sha256 = hashlib.sha256(raw_seed).hexdigest()

        phase = "PERSIST_SYNTHETIC_RAW_SEED"
        _write_new(raw_file, raw_seed)
        seed_persisted = True

        phase = "BUILD_DEVELOPMENT_COMMITMENT"
        commitment = build_development_c1_commitment(
            raw_seed=raw_seed,
            protocol_sha256=protocol_sha256,
            source_commit=source_commit,
            generation_seed_sha256=generation_seed_sha256,
        )

        commitment_bytes = commitment.canonical_json_bytes()

        phase = "PERSIST_PUBLIC_COMMITMENT"
        _write_new(commitment_file, commitment_bytes)

        phase = "PERSIST_SUCCEEDED_DISPOSITION"
        _replace_disposition(disposition, _disposition(
            status="SUCCEEDED",
            phase="COMPLETE",
            protocol_sha256=protocol_sha256,
            source_commit=source_commit,
            seed_persisted=True,
            seed_sha256=seed_sha256,
        ))

        return P094DevelopmentC1PersistenceResult(
            batch_directory=batch,
            seed_sha256=seed_sha256,
            commitment_file_sha256=hashlib.sha256(
                commitment_bytes
            ).hexdigest(),
        )

    except Exception as exc:
        failed = _disposition(
            status="FAILED",
            phase=phase,
            protocol_sha256=protocol_sha256,
            source_commit=source_commit,
            seed_persisted=seed_persisted,
            seed_sha256=seed_sha256,
            failure_type=type(exc).__name__,
        )

        try:
            if not public.exists():
                os.mkdir(public, 0o700)
                _fsync_directory(batch)
            elif public.is_symlink() or not public.is_dir():
                raise OSError("unsafe public development path")

            if os.path.lexists(disposition):
                _replace_disposition(disposition, failed)
            else:
                _write_new(disposition, failed)

        except Exception:
            raise P094DevelopmentC1PersistenceError(
                "attempt consumed; failure disposition unavailable"
            ) from None

        raise P094DevelopmentC1PersistenceError(
            "synthetic C1 attempt failed; identity consumed"
        ) from None

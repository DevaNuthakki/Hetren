from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path

from sqlalchemy.orm import Session

from app import models
from app.evaluation_provenance import (
    ASR_EVALUATION_TYPE,
    canonicalize_json,
    verify_evaluation_run_manifest,
)


INPUT_ARTIFACT_SEAL_SCHEMA_VERSION = 1

ASR_INPUT_AUDIO_ROLE = "input_audio"
AUDIO_ARTIFACT_TYPE = "audio"

SUPPORTED_ASR_AUDIO_MEDIA_TYPES = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
}

DEFAULT_COPY_CHUNK_SIZE = 1024 * 1024

_SAFE_TOKEN_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9_-]*$"
)


class EvaluationInputArtifactSealError(ValueError):
    """Raised when trusted input artifact sealing cannot be completed."""


def _normalize_token(
    value: str,
    *,
    field_name: str,
    max_length: int = 50,
) -> str:
    normalized = value.strip().lower()

    if (
        not normalized
        or len(normalized) > max_length
        or _SAFE_TOKEN_PATTERN.fullmatch(
            normalized
        )
        is None
    ):
        raise EvaluationInputArtifactSealError(
            f"{field_name} is invalid."
        )

    return normalized


def _normalize_sha256(
    value: str,
    *,
    field_name: str,
) -> str:
    normalized = value.strip().lower()

    if re.fullmatch(
        r"[0-9a-f]{64}",
        normalized,
    ) is None:
        raise EvaluationInputArtifactSealError(
            f"{field_name} is invalid."
        )

    return normalized


def _normalize_media_type(
    value: str,
) -> str:
    normalized = (
        value.split(";", maxsplit=1)[0]
        .strip()
        .lower()
    )

    if (
        not normalized
        or len(normalized) > 100
        or "/" not in normalized
    ):
        raise EvaluationInputArtifactSealError(
            "media_type is invalid."
        )

    return normalized


def calculate_content_sha256(
    path: str | Path,
    *,
    chunk_size: int = DEFAULT_COPY_CHUNK_SIZE,
) -> tuple[str, int]:
    if chunk_size <= 0:
        raise EvaluationInputArtifactSealError(
            "chunk_size must be positive."
        )

    file_path = Path(path)

    digest = hashlib.sha256()
    byte_length = 0

    with file_path.open("rb") as source:
        while True:
            chunk = source.read(chunk_size)

            if not chunk:
                break

            digest.update(chunk)
            byte_length += len(chunk)

    return digest.hexdigest(), byte_length


def calculate_artifact_seal_sha256(
    payload: dict[str, object],
) -> str:
    canonical_payload = canonicalize_json(
        payload
    )

    return hashlib.sha256(
        canonical_payload.encode("utf-8")
    ).hexdigest()


def build_evaluation_input_artifact_seal_payload(
    *,
    evaluation_run_id: int,
    test_case_id: int,
    evaluation_type: str,
    artifact_role: str,
    artifact_type: str,
    content_sha256: str,
    byte_length: int,
    media_type: str,
    run_manifest_sha256: str,
) -> dict[str, object]:
    if evaluation_run_id <= 0:
        raise EvaluationInputArtifactSealError(
            "evaluation_run_id is invalid."
        )

    if test_case_id <= 0:
        raise EvaluationInputArtifactSealError(
            "test_case_id is invalid."
        )

    normalized_evaluation_type = (
        _normalize_token(
            evaluation_type,
            field_name="evaluation_type",
        )
    )

    normalized_artifact_role = (
        _normalize_token(
            artifact_role,
            field_name="artifact_role",
        )
    )

    normalized_artifact_type = (
        _normalize_token(
            artifact_type,
            field_name="artifact_type",
        )
    )

    normalized_media_type = (
        _normalize_media_type(media_type)
    )

    normalized_content_sha256 = (
        _normalize_sha256(
            content_sha256,
            field_name="content_sha256",
        )
    )

    normalized_manifest_sha256 = (
        _normalize_sha256(
            run_manifest_sha256,
            field_name="run_manifest_sha256",
        )
    )

    if byte_length <= 0:
        raise EvaluationInputArtifactSealError(
            "byte_length must be positive."
        )

    return {
        "schema_version": (
            INPUT_ARTIFACT_SEAL_SCHEMA_VERSION
        ),
        "evaluation_type": (
            normalized_evaluation_type
        ),
        "artifact_role": normalized_artifact_role,
        "artifact_type": normalized_artifact_type,
        "evaluation_run_id": evaluation_run_id,
        "test_case_id": test_case_id,
        "run_manifest": {
            "sha256": normalized_manifest_sha256,
        },
        "content": {
            "sha256": normalized_content_sha256,
            "byte_length": byte_length,
            "media_type": normalized_media_type,
        },
    }


def _resolve_source_file(
    *,
    source_path: str | Path,
    source_root: str | Path,
) -> tuple[Path, Path]:
    try:
        root = Path(source_root).resolve(
            strict=True
        )
        source = Path(source_path).resolve(
            strict=True
        )
    except (OSError, RuntimeError) as exc:
        raise EvaluationInputArtifactSealError(
            "Input artifact is unavailable."
        ) from exc

    if (
        not root.is_dir()
        or not source.is_relative_to(root)
        or not source.is_file()
    ):
        raise EvaluationInputArtifactSealError(
            "Input artifact is unavailable."
        )

    return source, root


def _resolve_storage_root(
    *,
    storage_root: str | Path,
    source_root: Path,
) -> Path:
    candidate = Path(storage_root)

    try:
        candidate.mkdir(
            parents=True,
            exist_ok=True,
        )
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise EvaluationInputArtifactSealError(
            "Artifact seal storage is unavailable."
        ) from exc

    if (
        not resolved.is_dir()
        or not resolved.is_relative_to(
            source_root
        )
    ):
        raise EvaluationInputArtifactSealError(
            "Artifact seal storage is invalid."
        )

    return resolved


def _resolve_existing_snapshot(
    *,
    seal: models.EvaluationInputArtifactSeal,
    storage_root: str | Path,
) -> Path:
    root = Path(storage_root)

    try:
        root = root.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise EvaluationInputArtifactSealError(
            "Artifact seal storage is unavailable."
        ) from exc

    relative_path = Path(
        seal.sealed_file_path
    )

    if relative_path.is_absolute():
        raise EvaluationInputArtifactSealError(
            "Sealed artifact path is invalid."
        )

    try:
        snapshot = (
            root / relative_path
        ).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise EvaluationInputArtifactSealError(
            "Sealed input artifact is unavailable."
        ) from exc

    if (
        not snapshot.is_relative_to(root)
        or not snapshot.is_file()
    ):
        raise EvaluationInputArtifactSealError(
            "Sealed input artifact is unavailable."
        )

    return snapshot


def verify_evaluation_input_artifact_seal(
    seal: models.EvaluationInputArtifactSeal,
    *,
    storage_root: str | Path | None = None,
    expected_run_manifest_sha256: str | None = None,
) -> bool:
    try:
        if (
            seal.schema_version
            != INPUT_ARTIFACT_SEAL_SCHEMA_VERSION
        ):
            return False

        payload = seal.seal_payload

        if not isinstance(payload, dict):
            return False

        run_manifest = payload.get(
            "run_manifest"
        )

        if not isinstance(run_manifest, dict):
            return False

        manifest_sha256 = run_manifest.get(
            "sha256"
        )

        if not isinstance(
            manifest_sha256,
            str,
        ):
            return False

        expected_payload = (
            build_evaluation_input_artifact_seal_payload(
                evaluation_run_id=seal.run_id,
                test_case_id=seal.test_case_id,
                evaluation_type=(
                    seal.evaluation_type
                ),
                artifact_role=seal.artifact_role,
                artifact_type=seal.artifact_type,
                content_sha256=(
                    seal.content_sha256
                ),
                byte_length=seal.byte_length,
                media_type=seal.media_type,
                run_manifest_sha256=(
                    manifest_sha256
                ),
            )
        )

        if payload != expected_payload:
            return False

        if (
            calculate_artifact_seal_sha256(
                payload
            )
            != seal.seal_sha256
        ):
            return False

        if (
            expected_run_manifest_sha256
            is not None
            and manifest_sha256
            != expected_run_manifest_sha256
        ):
            return False

        if storage_root is not None:
            snapshot = (
                _resolve_existing_snapshot(
                    seal=seal,
                    storage_root=storage_root,
                )
            )

            content_sha256, byte_length = (
                calculate_content_sha256(
                    snapshot
                )
            )

            if (
                content_sha256
                != seal.content_sha256
                or byte_length
                != seal.byte_length
            ):
                return False

        return True

    except (
        EvaluationInputArtifactSealError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ):
        return False


def _copy_source_to_snapshot(
    *,
    source: Path,
    storage_root: Path,
    run_id: int,
    test_case_id: int,
    artifact_role: str,
) -> tuple[Path, str, int, bool]:
    destination_dir = (
        storage_root
        / "runs"
        / str(run_id)
        / "test-cases"
        / str(test_case_id)
    )

    destination_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    suffix = source.suffix.lower()

    if (
        suffix
        and re.fullmatch(
            r"\.[a-z0-9]{1,10}",
            suffix,
        )
        is None
    ):
        suffix = ""

    digest = hashlib.sha256()
    byte_length = 0
    temp_path: Path | None = None

    try:
        with source.open("rb") as source_file:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=destination_dir,
                prefix=".artifact-",
                suffix=".part",
                delete=False,
            ) as temp_file:
                temp_path = Path(temp_file.name)

                while True:
                    chunk = source_file.read(
                        DEFAULT_COPY_CHUNK_SIZE
                    )

                    if not chunk:
                        break

                    digest.update(chunk)
                    byte_length += len(chunk)
                    temp_file.write(chunk)

                temp_file.flush()
                os.fsync(temp_file.fileno())

        if byte_length <= 0:
            raise EvaluationInputArtifactSealError(
                "Input artifact is empty."
            )

        content_sha256 = digest.hexdigest()

        final_path = (
            destination_dir
            / (
                f"{artifact_role}-"
                f"{content_sha256}"
                f"{suffix}"
            )
        )

        created_final = False

        try:
            os.link(
                temp_path,
                final_path,
            )
            created_final = True
        except FileExistsError:
            existing_sha256, existing_length = (
                calculate_content_sha256(
                    final_path
                )
            )

            if (
                existing_sha256
                != content_sha256
                or existing_length
                != byte_length
            ):
                raise (
                    EvaluationInputArtifactSealError(
                        "Existing sealed artifact "
                        "failed integrity validation."
                    )
                )

        temp_path.unlink(missing_ok=True)

        return (
            final_path,
            content_sha256,
            byte_length,
            created_final,
        )

    except Exception:
        if temp_path is not None:
            try:
                temp_path.unlink(
                    missing_ok=True
                )
            except OSError:
                pass

        raise


def ensure_evaluation_input_artifact_seal(
    db: Session,
    *,
    evaluation_run: models.EvaluationRun,
    test_case: models.TestCase,
    source_path: str | Path,
    source_root: str | Path,
    storage_root: str | Path,
    media_type: str,
    evaluation_type: str = ASR_EVALUATION_TYPE,
    artifact_role: str = ASR_INPUT_AUDIO_ROLE,
    artifact_type: str = AUDIO_ARTIFACT_TYPE,
) -> models.EvaluationInputArtifactSeal:
    """
    Create or reuse a trusted integrity-verified input artifact seal.

    The source is copied in bounded chunks while hashing the exact bytes
    written to a server-owned snapshot. Existing seals are reused only
    after their metadata, evidence payload, and snapshot bytes verify.
    Filesystem tampering is detected and rejected rather than prevented.

    This function flushes the SQLAlchemy session but does not commit it.
    """
    if (
        evaluation_run.id is None
        or test_case.id is None
    ):
        raise EvaluationInputArtifactSealError(
            "Run and test case must be persisted."
        )

    normalized_evaluation_type = (
        _normalize_token(
            evaluation_type,
            field_name="evaluation_type",
        )
    )

    normalized_artifact_role = (
        _normalize_token(
            artifact_role,
            field_name="artifact_role",
        )
    )

    normalized_artifact_type = (
        _normalize_token(
            artifact_type,
            field_name="artifact_type",
        )
    )

    normalized_media_type = (
        _normalize_media_type(media_type)
    )

    if (
        normalized_evaluation_type
        == ASR_EVALUATION_TYPE
        and normalized_artifact_role
        == ASR_INPUT_AUDIO_ROLE
    ):
        if (
            normalized_artifact_type
            != AUDIO_ARTIFACT_TYPE
            or not normalized_media_type.startswith(
                "audio/"
            )
        ):
            raise EvaluationInputArtifactSealError(
                "ASR input audio metadata is invalid."
            )

    locked_run = (
        db.query(models.EvaluationRun)
        .filter(
            models.EvaluationRun.id
            == evaluation_run.id
        )
        .with_for_update()
        .one_or_none()
    )

    if locked_run is None:
        raise EvaluationInputArtifactSealError(
            "Evaluation run is unavailable."
        )

    test_case_row = (
        db.query(
            models.TestCase,
            models.Dataset.project_id,
        )
        .join(
            models.Dataset,
            models.Dataset.id
            == models.TestCase.dataset_id,
        )
        .filter(
            models.TestCase.id
            == test_case.id
        )
        .one_or_none()
    )

    if test_case_row is None:
        raise EvaluationInputArtifactSealError(
            "Test case is unavailable."
        )

    persisted_test_case = test_case_row[0]
    test_case_project_id = test_case_row[1]

    if (
        test_case_project_id
        != locked_run.project_id
    ):
        raise EvaluationInputArtifactSealError(
            "Run and test case do not belong "
            "to the same project."
        )

    manifest = (
        db.query(models.EvaluationRunManifest)
        .filter(
            models.EvaluationRunManifest.run_id
            == locked_run.id
        )
        .one_or_none()
    )

    if (
        manifest is None
        or not verify_evaluation_run_manifest(
            manifest
        )
        or manifest.evaluation_type
        != normalized_evaluation_type
    ):
        raise EvaluationInputArtifactSealError(
            "Evaluation run manifest is "
            "unavailable or invalid."
        )

    existing = (
        db.query(
            models.EvaluationInputArtifactSeal
        )
        .filter(
            models.EvaluationInputArtifactSeal.run_id
            == locked_run.id,
            models.EvaluationInputArtifactSeal.test_case_id
            == persisted_test_case.id,
            models.EvaluationInputArtifactSeal.artifact_role
            == normalized_artifact_role,
        )
        .one_or_none()
    )

    if existing is not None:
        if (
            existing.evaluation_type
            != normalized_evaluation_type
            or existing.artifact_type
            != normalized_artifact_type
            or existing.media_type
            != normalized_media_type
            or not verify_evaluation_input_artifact_seal(
                existing,
                storage_root=storage_root,
                expected_run_manifest_sha256=(
                    manifest.manifest_sha256
                ),
            )
        ):
            raise EvaluationInputArtifactSealError(
                "Existing input artifact seal "
                "failed integrity validation."
            )

        return existing

    source, resolved_source_root = (
        _resolve_source_file(
            source_path=source_path,
            source_root=source_root,
        )
    )

    if (
        normalized_evaluation_type
        == ASR_EVALUATION_TYPE
        and normalized_artifact_role
        == ASR_INPUT_AUDIO_ROLE
    ):
        if not persisted_test_case.audio_file_path:
            raise EvaluationInputArtifactSealError(
                "Test case input audio is unavailable."
            )

        authoritative_source, _ = (
            _resolve_source_file(
                source_path=(
                    persisted_test_case.audio_file_path
                ),
                source_root=source_root,
            )
        )

        if source != authoritative_source:
            raise EvaluationInputArtifactSealError(
                "Input artifact does not match "
                "the test case audio."
            )

    resolved_storage_root = (
        _resolve_storage_root(
            storage_root=storage_root,
            source_root=resolved_source_root,
        )
    )

    if source.is_relative_to(
        resolved_storage_root
    ):
        raise EvaluationInputArtifactSealError(
            "Input artifact must not already "
            "be a sealed snapshot."
        )

    (
        snapshot,
        content_sha256,
        byte_length,
        created_snapshot,
    ) = _copy_source_to_snapshot(
        source=source,
        storage_root=resolved_storage_root,
        run_id=locked_run.id,
        test_case_id=persisted_test_case.id,
        artifact_role=normalized_artifact_role,
    )

    relative_snapshot_path = (
        snapshot.relative_to(
            resolved_storage_root
        ).as_posix()
    )

    payload = (
        build_evaluation_input_artifact_seal_payload(
            evaluation_run_id=locked_run.id,
            test_case_id=persisted_test_case.id,
            evaluation_type=(
                normalized_evaluation_type
            ),
            artifact_role=(
                normalized_artifact_role
            ),
            artifact_type=(
                normalized_artifact_type
            ),
            content_sha256=content_sha256,
            byte_length=byte_length,
            media_type=normalized_media_type,
            run_manifest_sha256=(
                manifest.manifest_sha256
            ),
        )
    )

    seal = models.EvaluationInputArtifactSeal(
        run=locked_run,
        test_case=persisted_test_case,
        schema_version=(
            INPUT_ARTIFACT_SEAL_SCHEMA_VERSION
        ),
        evaluation_type=(
            normalized_evaluation_type
        ),
        artifact_role=(
            normalized_artifact_role
        ),
        artifact_type=(
            normalized_artifact_type
        ),
        content_sha256=content_sha256,
        byte_length=byte_length,
        media_type=normalized_media_type,
        sealed_file_path=relative_snapshot_path,
        seal_payload=payload,
        seal_sha256=(
            calculate_artifact_seal_sha256(
                payload
            )
        ),
    )

    db.add(seal)

    try:
        db.flush()
    except Exception:
        if created_snapshot:
            try:
                snapshot.unlink(
                    missing_ok=True
                )
            except OSError:
                pass

        raise

    return seal


def resolve_verified_sealed_artifact_path(
    seal: models.EvaluationInputArtifactSeal,
    *,
    storage_root: str | Path,
    expected_run_manifest_sha256: str | None = None,
) -> Path:
    if not verify_evaluation_input_artifact_seal(
        seal,
        storage_root=storage_root,
        expected_run_manifest_sha256=(
            expected_run_manifest_sha256
        ),
    ):
        raise EvaluationInputArtifactSealError(
            "Sealed input artifact failed "
            "integrity validation."
        )

    return _resolve_existing_snapshot(
        seal=seal,
        storage_root=storage_root,
    )

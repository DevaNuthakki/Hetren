from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.evaluation_artifacts import (
    ensure_evaluation_input_artifact_seal,
    resolve_verified_sealed_artifact_path,
    verify_evaluation_input_artifact_seal,
)
from app.evaluation_provenance import (
    stage_evaluation_run_with_manifest,
)


pytestmark = pytest.mark.postgres


def _stage_postgres_context(
    db: Session,
    tmp_path: Path,
    *,
    name: str,
) -> tuple[
    models.TestCase,
    models.EvaluationRun,
    Path,
    Path,
    Path,
]:
    organization = models.Organization(
        name=f"{name} organization",
    )
    db.add(organization)
    db.flush()

    project = models.Project(
        organization_id=organization.id,
        name=f"{name} project",
    )
    db.add(project)
    db.flush()

    dataset = models.Dataset(
        project_id=project.id,
        name=f"{name} dataset",
    )
    db.add(dataset)
    db.flush()

    uploads_root = tmp_path / "uploads"

    audio_dir = (
        uploads_root
        / "datasets"
        / str(dataset.id)
        / "audio"
    )
    audio_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    audio_path = audio_dir / "sample.wav"
    audio_path.write_bytes(
        b"postgres-artifact-audio"
    )

    test_case = models.TestCase(
        dataset_id=dataset.id,
        title=f"{name} test case",
        audio_file_path=str(audio_path),
        reference_transcript=(
            "postgres reference transcript"
        ),
    )
    db.add(test_case)
    db.flush()

    run = stage_evaluation_run_with_manifest(
        db,
        project_id=project.id,
        run_name=f"{name} run",
        model_name="mock-asr",
    )

    db.flush()

    storage_root = (
        uploads_root
        / "evaluation-inputs"
    )

    return (
        test_case,
        run,
        uploads_root,
        storage_root,
        audio_path,
    )


def _seal(
    db: Session,
    *,
    run: models.EvaluationRun,
    test_case: models.TestCase,
    uploads_root: Path,
    storage_root: Path,
    audio_path: Path,
):
    return ensure_evaluation_input_artifact_seal(
        db,
        evaluation_run=run,
        test_case=test_case,
        source_path=audio_path,
        source_root=uploads_root,
        storage_root=storage_root,
        media_type="audio/wav",
    )


def test_postgres_persists_and_verifies_artifact_seal(
    postgres_session: Session,
    tmp_path: Path,
):
    db = postgres_session

    (
        test_case,
        run,
        uploads_root,
        storage_root,
        audio_path,
    ) = _stage_postgres_context(
        db,
        tmp_path,
        name="postgres persistence",
    )

    seal = _seal(
        db,
        run=run,
        test_case=test_case,
        uploads_root=uploads_root,
        storage_root=storage_root,
        audio_path=audio_path,
    )

    db.flush()

    persisted = (
        db.query(
            models.EvaluationInputArtifactSeal
        )
        .filter(
            models.EvaluationInputArtifactSeal.id
            == seal.id
        )
        .one()
    )

    snapshot = (
        resolve_verified_sealed_artifact_path(
            persisted,
            storage_root=storage_root,
        )
    )

    assert snapshot.read_bytes() == (
        b"postgres-artifact-audio"
    )

    assert verify_evaluation_input_artifact_seal(
        persisted,
        storage_root=storage_root,
        expected_run_manifest_sha256=(
            run.manifest.manifest_sha256
        ),
    )


def test_postgres_unique_constraint_blocks_duplicate_role(
    postgres_session: Session,
    tmp_path: Path,
):
    db = postgres_session

    (
        test_case,
        run,
        uploads_root,
        storage_root,
        audio_path,
    ) = _stage_postgres_context(
        db,
        tmp_path,
        name="postgres uniqueness",
    )

    seal = _seal(
        db,
        run=run,
        test_case=test_case,
        uploads_root=uploads_root,
        storage_root=storage_root,
        audio_path=audio_path,
    )

    db.flush()

    duplicate = models.EvaluationInputArtifactSeal(
        run_id=seal.run_id,
        test_case_id=seal.test_case_id,
        schema_version=seal.schema_version,
        evaluation_type=seal.evaluation_type,
        artifact_role=seal.artifact_role,
        artifact_type=seal.artifact_type,
        content_sha256=seal.content_sha256,
        byte_length=seal.byte_length,
        media_type=seal.media_type,
        sealed_file_path=seal.sealed_file_path,
        seal_payload=seal.seal_payload,
        seal_sha256=seal.seal_sha256,
    )

    db.add(duplicate)

    with pytest.raises(IntegrityError):
        db.flush()

    db.rollback()


def test_postgres_run_delete_cascades_seal(
    postgres_session: Session,
    tmp_path: Path,
):
    db = postgres_session

    (
        test_case,
        run,
        uploads_root,
        storage_root,
        audio_path,
    ) = _stage_postgres_context(
        db,
        tmp_path,
        name="postgres cascade",
    )

    seal = _seal(
        db,
        run=run,
        test_case=test_case,
        uploads_root=uploads_root,
        storage_root=storage_root,
        audio_path=audio_path,
    )

    db.flush()

    seal_id = seal.id

    db.delete(run)
    db.flush()

    remaining = (
        db.query(
            models.EvaluationInputArtifactSeal
        )
        .filter(
            models.EvaluationInputArtifactSeal.id
            == seal_id
        )
        .count()
    )

    assert remaining == 0


def test_postgres_transaction_rollback_removes_seal_row(
    postgres_session: Session,
    tmp_path: Path,
):
    db = postgres_session

    (
        test_case,
        run,
        uploads_root,
        storage_root,
        audio_path,
    ) = _stage_postgres_context(
        db,
        tmp_path,
        name="postgres rollback",
    )

    savepoint = db.begin_nested()

    seal = _seal(
        db,
        run=run,
        test_case=test_case,
        uploads_root=uploads_root,
        storage_root=storage_root,
        audio_path=audio_path,
    )

    db.flush()

    seal_id = seal.id

    assert seal_id is not None

    savepoint.rollback()

    remaining = (
        db.query(
            models.EvaluationInputArtifactSeal
        )
        .filter(
            models.EvaluationInputArtifactSeal.id
            == seal_id
        )
        .count()
    )

    assert remaining == 0

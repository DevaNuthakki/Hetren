from __future__ import annotations

import hashlib
from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app import evaluation_artifacts
from app.database import Base
from app.evaluation_artifacts import (
    ASR_INPUT_AUDIO_ROLE,
    AUDIO_ARTIFACT_TYPE,
    EvaluationInputArtifactSealError,
    ensure_evaluation_input_artifact_seal,
    resolve_verified_sealed_artifact_path,
    verify_evaluation_input_artifact_seal,
)
from app.evaluation_provenance import (
    stage_evaluation_run_with_manifest,
)


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)

    session_factory = sessionmaker(
        bind=engine
    )
    session = session_factory()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _stage_context(
    db: Session,
    tmp_path: Path,
    *,
    project_name: str,
    audio_bytes: bytes = b"trusted-audio",
    with_manifest: bool = True,
) -> tuple[
    models.Project,
    models.TestCase,
    models.EvaluationRun,
    Path,
    Path,
    Path,
]:
    organization = models.Organization(
        name=f"{project_name} organization",
    )
    db.add(organization)
    db.flush()

    project = models.Project(
        organization_id=organization.id,
        name=project_name,
    )
    db.add(project)
    db.flush()

    dataset = models.Dataset(
        project_id=project.id,
        name=f"{project_name} dataset",
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

    audio_path = (
        audio_dir
        / f"sample-{project.id}.wav"
    )
    audio_path.write_bytes(audio_bytes)

    test_case = models.TestCase(
        dataset_id=dataset.id,
        title=f"{project_name} case",
        audio_file_path=str(audio_path),
        reference_transcript=(
            "trusted reference transcript"
        ),
    )
    db.add(test_case)
    db.flush()

    if with_manifest:
        run = stage_evaluation_run_with_manifest(
            db,
            project_id=project.id,
            run_name=f"{project_name} run",
            model_name="mock-asr",
        )
    else:
        run = models.EvaluationRun(
            project_id=project.id,
            run_name=f"{project_name} legacy run",
            model_name="mock-asr",
            status="created",
        )
        db.add(run)
        db.flush()

    db.flush()

    storage_root = (
        uploads_root
        / "evaluation-inputs"
    )

    return (
        project,
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
    audio_path: Path,
    uploads_root: Path,
    storage_root: Path,
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


def test_seals_exact_bytes_with_canonical_evidence(
    db: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    audio_bytes = (
        b"0123456789"
        b"abcdefghij"
        b"ABCDEFGHIJ"
    )

    (
        _project,
        test_case,
        run,
        uploads_root,
        storage_root,
        audio_path,
    ) = _stage_context(
        db,
        tmp_path,
        project_name="Exact bytes",
        audio_bytes=audio_bytes,
    )

    # Force multiple copy iterations so the test
    # proves chunked hashing/copy behavior.
    monkeypatch.setattr(
        evaluation_artifacts,
        "DEFAULT_COPY_CHUNK_SIZE",
        4,
    )

    seal = _seal(
        db,
        run=run,
        test_case=test_case,
        audio_path=audio_path,
        uploads_root=uploads_root,
        storage_root=storage_root,
    )

    snapshot = (
        resolve_verified_sealed_artifact_path(
            seal,
            storage_root=storage_root,
        )
    )

    expected_sha256 = hashlib.sha256(
        audio_bytes
    ).hexdigest()

    assert snapshot.read_bytes() == audio_bytes
    assert seal.content_sha256 == expected_sha256
    assert seal.byte_length == len(audio_bytes)
    assert seal.media_type == "audio/wav"
    assert seal.artifact_role == (
        ASR_INPUT_AUDIO_ROLE
    )
    assert seal.artifact_type == (
        AUDIO_ARTIFACT_TYPE
    )

    assert (
        seal.seal_payload["content"]
        == {
            "sha256": expected_sha256,
            "byte_length": len(audio_bytes),
            "media_type": "audio/wav",
        }
    )

    assert not Path(
        seal.sealed_file_path
    ).is_absolute()

    serialized_payload = str(
        seal.seal_payload
    ).lower()

    assert "sealed_file_path" not in (
        serialized_payload
    )
    assert "uploads" not in serialized_payload
    assert "path" not in serialized_payload

    assert verify_evaluation_input_artifact_seal(
        seal,
        storage_root=storage_root,
    )


def test_reuses_existing_seal_and_snapshot(
    db: Session,
    tmp_path: Path,
):
    (
        _project,
        test_case,
        run,
        uploads_root,
        storage_root,
        audio_path,
    ) = _stage_context(
        db,
        tmp_path,
        project_name="Seal reuse",
    )

    first = _seal(
        db,
        run=run,
        test_case=test_case,
        audio_path=audio_path,
        uploads_root=uploads_root,
        storage_root=storage_root,
    )

    first_path = (
        resolve_verified_sealed_artifact_path(
            first,
            storage_root=storage_root,
        )
    )

    second = _seal(
        db,
        run=run,
        test_case=test_case,
        audio_path=audio_path,
        uploads_root=uploads_root,
        storage_root=storage_root,
    )

    second_path = (
        resolve_verified_sealed_artifact_path(
            second,
            storage_root=storage_root,
        )
    )

    assert second.id == first.id
    assert second_path == first_path

    assert (
        db.query(
            models.EvaluationInputArtifactSeal
        ).count()
        == 1
    )

    files = [
        path
        for path in storage_root.rglob("*")
        if path.is_file()
    ]

    assert files == [first_path]


def test_original_source_mutation_cannot_change_sealed_input(
    db: Session,
    tmp_path: Path,
):
    original = b"original-evaluation-audio"

    (
        _project,
        test_case,
        run,
        uploads_root,
        storage_root,
        audio_path,
    ) = _stage_context(
        db,
        tmp_path,
        project_name="Source mutation",
        audio_bytes=original,
    )

    seal = _seal(
        db,
        run=run,
        test_case=test_case,
        audio_path=audio_path,
        uploads_root=uploads_root,
        storage_root=storage_root,
    )

    snapshot = (
        resolve_verified_sealed_artifact_path(
            seal,
            storage_root=storage_root,
        )
    )

    audio_path.write_bytes(
        b"later-mutated-source-audio"
    )

    reused = _seal(
        db,
        run=run,
        test_case=test_case,
        audio_path=audio_path,
        uploads_root=uploads_root,
        storage_root=storage_root,
    )

    assert reused.id == seal.id
    assert snapshot.read_bytes() == original

    assert verify_evaluation_input_artifact_seal(
        reused,
        storage_root=storage_root,
    )


def test_snapshot_tampering_fails_closed(
    db: Session,
    tmp_path: Path,
):
    (
        _project,
        test_case,
        run,
        uploads_root,
        storage_root,
        audio_path,
    ) = _stage_context(
        db,
        tmp_path,
        project_name="Snapshot tamper",
    )

    seal = _seal(
        db,
        run=run,
        test_case=test_case,
        audio_path=audio_path,
        uploads_root=uploads_root,
        storage_root=storage_root,
    )

    snapshot = (
        resolve_verified_sealed_artifact_path(
            seal,
            storage_root=storage_root,
        )
    )

    snapshot.write_bytes(
        b"tampered-snapshot"
    )

    assert not (
        verify_evaluation_input_artifact_seal(
            seal,
            storage_root=storage_root,
        )
    )

    with pytest.raises(
        EvaluationInputArtifactSealError,
        match="integrity validation",
    ):
        resolve_verified_sealed_artifact_path(
            seal,
            storage_root=storage_root,
        )

    with pytest.raises(
        EvaluationInputArtifactSealError,
        match="integrity validation",
    ):
        _seal(
            db,
            run=run,
            test_case=test_case,
            audio_path=audio_path,
            uploads_root=uploads_root,
            storage_root=storage_root,
        )


def test_rejects_source_outside_trusted_root(
    db: Session,
    tmp_path: Path,
):
    (
        _project,
        test_case,
        run,
        uploads_root,
        storage_root,
        _audio_path,
    ) = _stage_context(
        db,
        tmp_path,
        project_name="Outside source",
    )

    outside = tmp_path / "outside.wav"
    outside.write_bytes(b"outside-audio")

    test_case.audio_file_path = str(outside)
    db.flush()

    with pytest.raises(
        EvaluationInputArtifactSealError,
        match="unavailable",
    ):
        _seal(
            db,
            run=run,
            test_case=test_case,
            audio_path=outside,
            uploads_root=uploads_root,
            storage_root=storage_root,
        )


def test_rejects_wrong_trusted_audio_for_test_case(
    db: Session,
    tmp_path: Path,
):
    (
        _project,
        test_case,
        run,
        uploads_root,
        storage_root,
        audio_path,
    ) = _stage_context(
        db,
        tmp_path,
        project_name="Wrong trusted audio",
    )

    wrong_audio = (
        audio_path.parent / "other.wav"
    )
    wrong_audio.write_bytes(
        b"another-trusted-file"
    )

    with pytest.raises(
        EvaluationInputArtifactSealError,
        match="does not match",
    ):
        _seal(
            db,
            run=run,
            test_case=test_case,
            audio_path=wrong_audio,
            uploads_root=uploads_root,
            storage_root=storage_root,
        )

    assert (
        db.query(
            models.EvaluationInputArtifactSeal
        ).count()
        == 0
    )


def test_rejects_empty_input_artifact(
    db: Session,
    tmp_path: Path,
):
    (
        _project,
        test_case,
        run,
        uploads_root,
        storage_root,
        audio_path,
    ) = _stage_context(
        db,
        tmp_path,
        project_name="Empty audio",
        audio_bytes=b"",
    )

    with pytest.raises(
        EvaluationInputArtifactSealError,
        match="empty",
    ):
        _seal(
            db,
            run=run,
            test_case=test_case,
            audio_path=audio_path,
            uploads_root=uploads_root,
            storage_root=storage_root,
        )

    files = (
        []
        if not storage_root.exists()
        else [
            path
            for path in storage_root.rglob("*")
            if path.is_file()
        ]
    )

    assert files == []


def test_rejects_cross_project_run_and_test_case(
    db: Session,
    tmp_path: Path,
):
    (
        _first_project,
        _first_test_case,
        first_run,
        uploads_root,
        storage_root,
        _first_audio,
    ) = _stage_context(
        db,
        tmp_path,
        project_name="First project",
    )

    (
        _second_project,
        second_test_case,
        _second_run,
        _uploads_root,
        _storage_root,
        second_audio,
    ) = _stage_context(
        db,
        tmp_path,
        project_name="Second project",
    )

    with pytest.raises(
        EvaluationInputArtifactSealError,
        match="same project",
    ):
        _seal(
            db,
            run=first_run,
            test_case=second_test_case,
            audio_path=second_audio,
            uploads_root=uploads_root,
            storage_root=storage_root,
        )


def test_requires_sealed_run_manifest(
    db: Session,
    tmp_path: Path,
):
    (
        _project,
        test_case,
        run,
        uploads_root,
        storage_root,
        audio_path,
    ) = _stage_context(
        db,
        tmp_path,
        project_name="Missing manifest",
        with_manifest=False,
    )

    with pytest.raises(
        EvaluationInputArtifactSealError,
        match="manifest",
    ):
        _seal(
            db,
            run=run,
            test_case=test_case,
            audio_path=audio_path,
            uploads_root=uploads_root,
            storage_root=storage_root,
        )


def test_rejects_invalid_run_manifest(
    db: Session,
    tmp_path: Path,
):
    (
        _project,
        test_case,
        run,
        uploads_root,
        storage_root,
        audio_path,
    ) = _stage_context(
        db,
        tmp_path,
        project_name="Invalid manifest",
    )

    manifest = (
        db.query(models.EvaluationRunManifest)
        .filter(
            models.EvaluationRunManifest.run_id
            == run.id
        )
        .one()
    )

    manifest.manifest_payload = {
        **manifest.manifest_payload,
        "model": {
            "name": "tampered-model",
        },
    }

    with pytest.raises(
        EvaluationInputArtifactSealError,
        match="manifest",
    ):
        _seal(
            db,
            run=run,
            test_case=test_case,
            audio_path=audio_path,
            uploads_root=uploads_root,
            storage_root=storage_root,
        )


def test_verifier_rejects_schema_and_hash_tampering(
    db: Session,
    tmp_path: Path,
):
    (
        _project,
        test_case,
        run,
        uploads_root,
        storage_root,
        audio_path,
    ) = _stage_context(
        db,
        tmp_path,
        project_name="Metadata tamper",
    )

    seal = _seal(
        db,
        run=run,
        test_case=test_case,
        audio_path=audio_path,
        uploads_root=uploads_root,
        storage_root=storage_root,
    )

    seal.schema_version = 999

    assert not (
        verify_evaluation_input_artifact_seal(
            seal,
            storage_root=storage_root,
        )
    )

    seal.schema_version = 1
    original_hash = seal.content_sha256

    seal.content_sha256 = "z" * 64

    assert not (
        verify_evaluation_input_artifact_seal(
            seal,
            storage_root=storage_root,
        )
    )

    seal.content_sha256 = original_hash

    assert verify_evaluation_input_artifact_seal(
        seal,
        storage_root=storage_root,
    )


def test_asr_contract_rejects_non_audio_metadata(
    db: Session,
    tmp_path: Path,
):
    (
        _project,
        test_case,
        run,
        uploads_root,
        storage_root,
        audio_path,
    ) = _stage_context(
        db,
        tmp_path,
        project_name="Invalid ASR metadata",
    )

    with pytest.raises(
        EvaluationInputArtifactSealError,
        match="metadata",
    ):
        ensure_evaluation_input_artifact_seal(
            db,
            evaluation_run=run,
            test_case=test_case,
            source_path=audio_path,
            source_root=uploads_root,
            storage_root=storage_root,
            media_type="application/octet-stream",
            evaluation_type="asr",
            artifact_role="input_audio",
            artifact_type="audio",
        )


def test_flush_failure_removes_new_snapshot(
    db: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    (
        _project,
        test_case,
        run,
        uploads_root,
        storage_root,
        audio_path,
    ) = _stage_context(
        db,
        tmp_path,
        project_name="Flush failure",
    )

    db.commit()

    original_flush = db.flush

    def fail_when_seal_is_pending(
        objects=None,
    ):
        has_pending_seal = any(
            isinstance(
                value,
                models.EvaluationInputArtifactSeal,
            )
            for value in db.new
        )

        if has_pending_seal:
            raise RuntimeError(
                "simulated seal flush failure"
            )

        return original_flush(objects)

    monkeypatch.setattr(
        db,
        "flush",
        fail_when_seal_is_pending,
    )

    with pytest.raises(
        RuntimeError,
        match="simulated seal flush failure",
    ):
        _seal(
            db,
            run=run,
            test_case=test_case,
            audio_path=audio_path,
            uploads_root=uploads_root,
            storage_root=storage_root,
        )

    db.rollback()

    files = (
        []
        if not storage_root.exists()
        else [
            path
            for path in storage_root.rglob("*")
            if path.is_file()
        ]
    )

    assert files == []


def test_run_delete_cascades_artifact_seal_row(
    db: Session,
    tmp_path: Path,
):
    (
        _project,
        test_case,
        run,
        uploads_root,
        storage_root,
        audio_path,
    ) = _stage_context(
        db,
        tmp_path,
        project_name="Seal cascade",
    )

    seal = _seal(
        db,
        run=run,
        test_case=test_case,
        audio_path=audio_path,
        uploads_root=uploads_root,
        storage_root=storage_root,
    )

    seal_id = seal.id

    assert seal_id is not None

    db.delete(run)
    db.flush()

    assert (
        db.query(
            models.EvaluationInputArtifactSeal
        )
        .filter(
            models.EvaluationInputArtifactSeal.id
            == seal_id
        )
        .count()
        == 0
    )

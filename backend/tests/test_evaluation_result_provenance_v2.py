from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from app.evaluation_artifacts import (
    ensure_evaluation_input_artifact_seal,
)
from app.evaluation_provenance import (
    EVALUATION_RESULT_PROVENANCE_INPUT_ARTIFACT_SCHEMA_VERSION,
    calculate_manifest_sha256,
    stage_evaluation_result_provenance,
    stage_evaluation_run_with_manifest,
    verify_evaluation_result_provenance,
)
from app.evaluation_service import (
    stage_evaluation_result,
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


def _create_sealed_resources(
    db: Session,
    tmp_path: Path,
):
    project = models.Project(
        name="Result provenance v2 project",
    )
    db.add(project)
    db.flush()

    dataset = models.Dataset(
        project_id=project.id,
        name="Result provenance v2 dataset",
    )
    db.add(dataset)
    db.flush()

    uploads_root = tmp_path / "uploads"

    audio_dir = (
        uploads_root
        / "datasets"
        / str(dataset.id)
        / "test-cases"
        / "audio"
    )
    audio_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    audio_path = (
        audio_dir / "sample.wav"
    )
    audio_path.write_bytes(
        b"exact-v2-audio"
    )

    test_case = models.TestCase(
        dataset_id=dataset.id,
        title="V2 sample",
        audio_file_path=str(audio_path),
        reference_transcript="hello world",
    )
    db.add(test_case)
    db.flush()

    run = stage_evaluation_run_with_manifest(
        db,
        project_id=project.id,
        run_name="V2 run",
        model_name="mock-asr",
    )

    db.flush()

    storage_root = (
        uploads_root
        / "evaluation-inputs"
    )

    seal = (
        ensure_evaluation_input_artifact_seal(
            db,
            evaluation_run=run,
            test_case=test_case,
            source_path=audio_path,
            source_root=uploads_root,
            storage_root=storage_root,
            media_type="audio/wav",
        )
    )

    result = stage_evaluation_result(
        db=db,
        db_run=run,
        db_test_case=test_case,
        generated_text="hello world",
    )

    db.flush()

    return (
        run,
        test_case,
        result,
        seal,
    )


def test_v2_provenance_binds_exact_input_artifact(
    db: Session,
    tmp_path: Path,
):
    (
        run,
        test_case,
        result,
        seal,
    ) = _create_sealed_resources(
        db,
        tmp_path,
    )

    provenance = (
        stage_evaluation_result_provenance(
            db,
            result=result,
            evaluation_run=run,
            test_case=test_case,
            execution_mode="server_asr",
            server_observed={
                "provider": "mock",
                "model_name": "mock-asr",
            },
            input_artifact_seal=seal,
        )
    )

    db.flush()

    assert provenance.schema_version == (
        EVALUATION_RESULT_PROVENANCE_INPUT_ARTIFACT_SCHEMA_VERSION
    )

    evidence = (
        provenance.provenance_payload[
            "input_artifact"
        ]
    )

    assert evidence["status"] == "sealed"
    assert evidence["seal_id"] == seal.id
    assert (
        evidence["seal_sha256"]
        == seal.seal_sha256
    )
    assert (
        evidence["content_sha256"]
        == seal.content_sha256
    )
    assert (
        evidence["byte_length"]
        == seal.byte_length
    )
    assert (
        evidence["run_manifest_sha256"]
        == run.manifest.manifest_sha256
    )

    assert verify_evaluation_result_provenance(
        provenance
    )


def test_v2_verifier_detects_artifact_evidence_rewrite(
    db: Session,
    tmp_path: Path,
):
    (
        run,
        test_case,
        result,
        seal,
    ) = _create_sealed_resources(
        db,
        tmp_path,
    )

    provenance = (
        stage_evaluation_result_provenance(
            db,
            result=result,
            evaluation_run=run,
            test_case=test_case,
            execution_mode="server_asr",
            input_artifact_seal=seal,
        )
    )

    db.flush()

    payload = dict(
        provenance.provenance_payload
    )

    artifact = dict(
        payload["input_artifact"]
    )

    artifact["content_sha256"] = (
        "f" * 64
    )

    payload["input_artifact"] = artifact

    # Simulate an attacker rewriting the outer digest
    # as well. Internal seal consistency must still fail.
    provenance.provenance_payload = payload
    provenance.provenance_sha256 = (
        calculate_manifest_sha256(
            payload
        )
    )

    assert not (
        verify_evaluation_result_provenance(
            provenance
        )
    )


def test_input_artifact_is_rejected_for_non_asr_execution_mode(
    db: Session,
    tmp_path: Path,
):
    (
        run,
        test_case,
        result,
        seal,
    ) = _create_sealed_resources(
        db,
        tmp_path,
    )

    with pytest.raises(
        ValueError,
        match="only supported for ASR",
    ):
        stage_evaluation_result_provenance(
            db,
            result=result,
            evaluation_run=run,
            test_case=test_case,
            execution_mode=(
                "uploaded_transcript"
            ),
            input_artifact_seal=seal,
        )

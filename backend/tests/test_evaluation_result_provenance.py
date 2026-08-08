from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from app.evaluation_provenance import (
    build_evaluation_result_provenance_payload,
    calculate_manifest_sha256,
    calculate_text_sha256,
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


def _stage_project_resources(
    db: Session,
) -> tuple[
    models.Project,
    models.TestCase,
]:
    project = models.Project(
        name="Result provenance project",
    )
    db.add(project)
    db.flush()

    dataset = models.Dataset(
        project_id=project.id,
        name="Result provenance dataset",
    )
    db.add(dataset)
    db.flush()

    test_case = models.TestCase(
        dataset_id=dataset.id,
        title="Result provenance sample",
        reference_transcript=(
            "unique private reference phrase"
        ),
    )
    db.add(test_case)
    db.flush()

    return project, test_case


def _stage_result(
    db: Session,
    *,
    run: models.EvaluationRun,
    test_case: models.TestCase,
) -> models.EvaluationResult:
    result = stage_evaluation_result(
        db=db,
        db_run=run,
        db_test_case=test_case,
        generated_text=(
            "unique generated output phrase"
        ),
    )

    db.flush()

    return result


def test_text_sha256_uses_exact_utf8_content():
    assert calculate_text_sha256(
        "héllo"
    ) == calculate_text_sha256(
        "héllo"
    )

    assert calculate_text_sha256(
        "héllo"
    ) != calculate_text_sha256(
        "hello"
    )


def test_result_provenance_links_sealed_run(
    db: Session,
):
    project, test_case = (
        _stage_project_resources(db)
    )

    run = stage_evaluation_run_with_manifest(
        db,
        project_id=project.id,
        run_name="Sealed run",
        model_name="mock-model",
    )

    result = _stage_result(
        db,
        run=run,
        test_case=test_case,
    )

    provenance = (
        stage_evaluation_result_provenance(
            db,
            result=result,
            evaluation_run=run,
            test_case=test_case,
            execution_mode="server_asr",
            server_observed={
                "provider": "mock_local",
                "model_name": "mock-model",
            },
        )
    )
    db.flush()

    payload = provenance.provenance_payload

    assert (
        payload["run_manifest"]["status"]
        == "sealed"
    )
    assert (
        payload["run_manifest"]["sha256"]
        == run.manifest.manifest_sha256
    )
    assert verify_evaluation_result_provenance(
        provenance
    )


def test_result_provenance_does_not_duplicate_transcripts(
    db: Session,
):
    project, test_case = (
        _stage_project_resources(db)
    )

    run = stage_evaluation_run_with_manifest(
        db,
        project_id=project.id,
        run_name="Privacy-conscious run",
        model_name="mock-model",
    )

    result = _stage_result(
        db,
        run=run,
        test_case=test_case,
    )

    payload = (
        build_evaluation_result_provenance_payload(
            result=result,
            evaluation_run=run,
            test_case=test_case,
            execution_mode="uploaded_transcript",
        )
    )

    serialized = str(payload)

    assert (
        test_case.reference_transcript
        not in serialized
    )
    assert (
        result.generated_transcript
        not in serialized
    )

    assert payload[
        "evidence"
    ][
        "reference_transcript"
    ][
        "sha256"
    ] == calculate_text_sha256(
        test_case.reference_transcript
    )


def test_legacy_run_is_explicitly_unsealed(
    db: Session,
):
    project, test_case = (
        _stage_project_resources(db)
    )

    run = models.EvaluationRun(
        project_id=project.id,
        run_name="Legacy run",
        model_name="legacy-model",
        status="created",
    )
    db.add(run)
    db.flush()

    result = _stage_result(
        db,
        run=run,
        test_case=test_case,
    )

    provenance = (
        stage_evaluation_result_provenance(
            db,
            result=result,
            evaluation_run=run,
            test_case=test_case,
            execution_mode="uploaded_transcript",
        )
    )
    db.flush()

    assert provenance.provenance_payload[
        "run_manifest"
    ] == {
        "status": "legacy_unsealed",
        "schema_version": None,
        "sha256": None,
    }


def test_result_provenance_detects_payload_tampering(
    db: Session,
):
    project, test_case = (
        _stage_project_resources(db)
    )

    run = stage_evaluation_run_with_manifest(
        db,
        project_id=project.id,
        run_name="Tamper test",
        model_name="mock-model",
    )

    result = _stage_result(
        db,
        run=run,
        test_case=test_case,
    )

    provenance = (
        stage_evaluation_result_provenance(
            db,
            result=result,
            evaluation_run=run,
            test_case=test_case,
            execution_mode="seed_fixture",
        )
    )
    db.flush()

    assert verify_evaluation_result_provenance(
        provenance
    )

    tampered_payload = dict(
        provenance.provenance_payload
    )
    tampered_payload["evaluation_type"] = (
        "tampered"
    )
    provenance.provenance_payload = (
        tampered_payload
    )

    assert not verify_evaluation_result_provenance(
        provenance
    )


def test_result_provenance_rejects_unknown_execution_mode(
    db: Session,
):
    project, test_case = (
        _stage_project_resources(db)
    )

    run = stage_evaluation_run_with_manifest(
        db,
        project_id=project.id,
        run_name="Mode validation run",
        model_name="mock-model",
    )

    result = _stage_result(
        db,
        run=run,
        test_case=test_case,
    )

    with pytest.raises(
        ValueError,
        match="Unsupported evaluation execution mode",
    ):
        build_evaluation_result_provenance_payload(
            result=result,
            evaluation_run=run,
            test_case=test_case,
            execution_mode="unknown_mode",
        )


def test_historical_v1_provenance_remains_verifiable(
    db: Session,
):
    project, test_case = _stage_project_resources(db)

    run = stage_evaluation_run_with_manifest(
        db,
        project_id=project.id,
        run_name="Historical v1 run",
        model_name="legacy-model",
    )

    result = _stage_result(
        db,
        run=run,
        test_case=test_case,
    )

    payload = build_evaluation_result_provenance_payload(
        result=result,
        evaluation_run=run,
        test_case=test_case,
        execution_mode="uploaded_transcript",
    )

    payload.pop("hvee_asr", None)
    payload["schema_version"] = 1

    provenance = models.EvaluationResultProvenance(
        result_id=result.id,
        schema_version=1,
        evaluation_type="asr",
        execution_mode="uploaded_transcript",
        provenance_payload=payload,
        provenance_sha256=(
            calculate_manifest_sha256(payload)
        ),
    )

    db.add(provenance)
    db.flush()

    assert verify_evaluation_result_provenance(
        provenance
    )

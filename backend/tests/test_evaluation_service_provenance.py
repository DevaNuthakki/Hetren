from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from app.evaluation_provenance import (
    EVALUATION_RESULT_PROVENANCE_OBSERVATION_EVIDENCE_SCHEMA_VERSION,
    stage_evaluation_run_with_manifest,
    verify_evaluation_result_observation_binding,
    verify_evaluation_result_provenance,
)
from app.evaluation_service import (
    persist_evaluation_result,
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

    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _create_resources(
    db: Session,
) -> tuple[
    models.EvaluationRun,
    models.TestCase,
]:
    project = models.Project(
        name="Evaluation service provenance",
    )
    db.add(project)
    db.flush()

    dataset = models.Dataset(
        project_id=project.id,
        name="Evaluation service dataset",
    )
    db.add(dataset)
    db.flush()

    test_case = models.TestCase(
        dataset_id=dataset.id,
        title="Evaluation service sample",
        reference_transcript=(
            "the reference transcript"
        ),
    )
    db.add(test_case)
    db.flush()

    run = stage_evaluation_run_with_manifest(
        db,
        project_id=project.id,
        run_name="Evaluation service run",
        model_name="requested-model",
    )

    return run, test_case


def test_uploaded_transcript_persists_provenance(
    db: Session,
):
    run, test_case = _create_resources(db)

    result = persist_evaluation_result(
        db=db,
        db_run=run,
        db_test_case=test_case,
        generated_text="the generated transcript",
        execution_mode="uploaded_transcript",
    )

    assert result.provenance is not None
    assert (
        result.provenance.execution_mode
        == "uploaded_transcript"
    )
    assert result.provenance.schema_version == (
        EVALUATION_RESULT_PROVENANCE_OBSERVATION_EVIDENCE_SCHEMA_VERSION
    )

    payload = result.provenance.provenance_payload

    assert payload["hvee_observations"]["count"] == 17
    assert verify_evaluation_result_observation_binding(
        db,
        result.provenance,
    )

    hvee_asr = payload["hvee_asr"]

    assert hvee_asr["normalization"] == {
        "key": "hetren.asr.text.basic",
        "version": "1.0.0",
    }

    assert (
        hvee_asr["derived_text"]["reference"][
            "source_sha256"
        ]
        == payload["evidence"][
            "reference_transcript"
        ]["sha256"]
    )

    assert (
        hvee_asr["derived_text"]["generated"][
            "source_sha256"
        ]
        == payload["evidence"][
            "generated_transcript"
        ]["sha256"]
    )

    assert (
        "normalized_text"
        not in hvee_asr["derived_text"]["reference"]
    )
    assert (
        "normalized_text"
        not in hvee_asr["derived_text"]["generated"]
    )

    assert (
        result.provenance.provenance_payload[
            "execution"
        ]["server_observed"]
        == {}
    )
    assert verify_evaluation_result_provenance(
        result.provenance
    )


def test_server_asr_persists_observed_provider(
    db: Session,
):
    run, test_case = _create_resources(db)

    result = persist_evaluation_result(
        db=db,
        db_run=run,
        db_test_case=test_case,
        generated_text="the generated transcript",
        execution_mode="server_asr",
        server_observed={
            "provider": "mock_local",
            "model_name": "actual-model",
        },
    )

    execution = (
        result.provenance.provenance_payload[
            "execution"
        ]
    )

    assert execution["mode"] == "server_asr"
    assert execution["requested_model"] == (
        "requested-model"
    )
    assert execution["server_observed"] == {
        "provider": "mock_local",
        "model_name": "actual-model",
    }
    assert execution["external_reported"] == {}

    assert verify_evaluation_result_provenance(
        result.provenance
    )


def test_invalid_provenance_rolls_back_result(
    db: Session,
):
    run, test_case = _create_resources(db)

    # Persist the pre-existing evaluation resources first.
    # The failure below must roll back only the attempted
    # result/provenance transaction, not the test setup.
    db.commit()

    with pytest.raises(
        ValueError,
        match="Unsupported evaluation execution mode",
    ):
        persist_evaluation_result(
            db=db,
            db_run=run,
            db_test_case=test_case,
            generated_text="must not persist",
            execution_mode="invalid_mode",
        )

    assert (
        db.query(models.EvaluationResult).count()
        == 0
    )
    assert (
        db.query(
            models.EvaluationResultProvenance
        ).count()
        == 0
    )

    db.refresh(run)

    assert run.status == "created"

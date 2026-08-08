from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from app.evaluation_provenance import (
    stage_evaluation_run_with_manifest,
)
from app.evaluation_service import (
    persist_evaluation_result,
    stage_evaluation_result,
)
from app.hvee_asr_observation_service import (
    stage_asr_text_error_observations,
)
from app.hvee_models import HveeObservation
from app.hvee_observation_service import (
    HveeObservationPersistenceError,
)
from hvee.packs.asr.evaluation import (
    evaluate_transcript_pair,
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

    factory = sessionmaker(bind=engine)
    session = factory()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _resources(
    db: Session,
) -> tuple[
    models.EvaluationRun,
    models.TestCase,
]:
    project = models.Project(
        name="HVEE observation sealing project",
    )
    db.add(project)
    db.flush()

    dataset = models.Dataset(
        project_id=project.id,
        name="HVEE observation sealing dataset",
    )
    db.add(dataset)
    db.flush()

    test_case = models.TestCase(
        dataset_id=dataset.id,
        title="HVEE observation sealing case",
        reference_transcript="one two three",
    )
    db.add(test_case)
    db.flush()

    run = stage_evaluation_run_with_manifest(
        db,
        project_id=project.id,
        run_name="HVEE observation sealing run",
        model_name="test-model",
    )

    return run, test_case


def test_observations_can_stage_before_provenance(
    db: Session,
):
    run, test_case = _resources(db)

    result = stage_evaluation_result(
        db=db,
        db_run=run,
        db_test_case=test_case,
        generated_text="one two",
    )

    db.flush()

    assert result.id is not None
    assert result.provenance is None

    count = (
        db.query(HveeObservation)
        .filter(
            HveeObservation.evaluation_run_id
            == run.id,
            HveeObservation.test_case_id
            == test_case.id,
        )
        .count()
    )

    assert count > 0


def test_result_provenance_seals_test_case_observations(
    db: Session,
):
    run, test_case = _resources(db)

    result = persist_evaluation_result(
        db=db,
        db_run=run,
        db_test_case=test_case,
        generated_text="one two",
        execution_mode="uploaded_transcript",
    )

    assert result.provenance is not None

    count_before = (
        db.query(HveeObservation)
        .filter(
            HveeObservation.evaluation_run_id
            == run.id,
            HveeObservation.test_case_id
            == test_case.id,
        )
        .count()
    )

    evaluation = evaluate_transcript_pair(
        reference_text=(
            test_case.reference_transcript
        ),
        generated_text="one two",
    )

    with pytest.raises(
        HveeObservationPersistenceError,
        match="immutable after result provenance",
    ):
        stage_asr_text_error_observations(
            db,
            evaluation_run=run,
            test_case=test_case,
            evaluation=evaluation,
        )

    count_after = (
        db.query(HveeObservation)
        .filter(
            HveeObservation.evaluation_run_id
            == run.id,
            HveeObservation.test_case_id
            == test_case.id,
        )
        .count()
    )

    assert count_after == count_before

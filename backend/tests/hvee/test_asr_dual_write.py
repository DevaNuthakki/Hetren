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
from app.hvee_models import (
    HveeEvaluatorVersion,
    HveeMetricDefinition,
    HveeObservation,
)
from hvee.packs.asr import (
    CER_EVALUATOR,
    CER_METRIC,
    WER_EVALUATOR,
    WER_METRIC,
)


@pytest.fixture()
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


def build_resources(
    db: Session,
) -> tuple[
    models.EvaluationRun,
    models.TestCase,
]:
    project = models.Project(
        name="HVEE ASR dual-write project",
    )
    db.add(project)
    db.flush()

    dataset = models.Dataset(
        project_id=project.id,
        name="HVEE ASR dual-write dataset",
    )
    db.add(dataset)
    db.flush()

    test_case = models.TestCase(
        dataset_id=dataset.id,
        title="HVEE ASR dual-write case",
        reference_transcript="the quick brown fox",
    )
    db.add(test_case)
    db.flush()

    run = stage_evaluation_run_with_manifest(
        db,
        project_id=project.id,
        run_name="HVEE ASR dual-write run",
        model_name="requested-model",
    )

    return run, test_case


def observation_by_metric_key(
    db: Session,
) -> dict[str, HveeObservation]:
    observations = (
        db.query(HveeObservation)
        .all()
    )

    metric_by_id = {
        metric.id: metric.key
        for metric in (
            db.query(HveeMetricDefinition)
            .all()
        )
    }

    return {
        metric_by_id[
            observation.metric_definition_id
        ]: observation
        for observation in observations
    }


def test_synchronous_result_dual_writes_wer_and_cer(
    db: Session,
):
    run, test_case = build_resources(db)

    result = persist_evaluation_result(
        db=db,
        db_run=run,
        db_test_case=test_case,
        generated_text="the quick fox",
        execution_mode="uploaded_transcript",
    )

    observations = observation_by_metric_key(
        db
    )

    assert set(observations) == {
        WER_METRIC.key,
        CER_METRIC.key,
    }

    wer = observations[WER_METRIC.key]
    cer = observations[CER_METRIC.key]

    assert wer.evaluation_run_id == run.id
    assert wer.test_case_id == test_case.id
    assert wer.scope == "test_case"
    assert wer.status == "success"
    assert wer.value_type == "number"
    assert wer.number_value == result.wer

    assert cer.evaluation_run_id == run.id
    assert cer.test_case_id == test_case.id
    assert cer.scope == "test_case"
    assert cer.status == "success"
    assert cer.value_type == "number"
    assert cer.number_value == result.cer


def test_dual_write_resolves_canonical_registry_once(
    db: Session,
):
    run, first_case = build_resources(db)

    first = persist_evaluation_result(
        db=db,
        db_run=run,
        db_test_case=first_case,
        generated_text="the quick fox",
        execution_mode="uploaded_transcript",
    )

    second_case = models.TestCase(
        dataset_id=first_case.dataset_id,
        title="Second ASR case",
        reference_transcript="hello world",
    )
    db.add(second_case)
    db.commit()

    second = persist_evaluation_result(
        db=db,
        db_run=run,
        db_test_case=second_case,
        generated_text="hello there",
        execution_mode="uploaded_transcript",
    )

    assert first.id != second.id

    assert (
        db.query(HveeMetricDefinition).count()
        == 2
    )
    assert (
        db.query(HveeEvaluatorVersion).count()
        == 2
    )
    assert (
        db.query(HveeObservation).count()
        == 4
    )

    metrics = {
        (row.key, row.version)
        for row in db.query(
            HveeMetricDefinition
        ).all()
    }
    evaluators = {
        (row.key, row.version)
        for row in db.query(
            HveeEvaluatorVersion
        ).all()
    }

    assert metrics == {
        (WER_METRIC.key, WER_METRIC.version),
        (CER_METRIC.key, CER_METRIC.version),
    }

    assert evaluators == {
        (
            WER_EVALUATOR.key,
            WER_EVALUATOR.version,
        ),
        (
            CER_EVALUATOR.key,
            CER_EVALUATOR.version,
        ),
    }


def test_provenance_failure_rolls_back_entire_dual_write(
    db: Session,
):
    run, test_case = build_resources(db)

    # Preserve only setup resources. Everything created by the failed
    # evaluation must disappear in the rollback.
    db.commit()

    with pytest.raises(
        ValueError,
        match="Unsupported evaluation execution mode",
    ):
        persist_evaluation_result(
            db=db,
            db_run=run,
            db_test_case=test_case,
            generated_text="the quick fox",
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
    assert (
        db.query(HveeObservation).count()
        == 0
    )
    assert (
        db.query(HveeMetricDefinition).count()
        == 0
    )
    assert (
        db.query(HveeEvaluatorVersion).count()
        == 0
    )

    db.refresh(run)
    assert run.status == "created"


def test_stage_dual_write_does_not_commit(
    db: Session,
):
    run, test_case = build_resources(db)
    db.commit()

    stage_evaluation_result(
        db=db,
        db_run=run,
        db_test_case=test_case,
        generated_text="the quick fox",
    )

    assert (
        db.query(HveeObservation).count()
        == 2
    )

    db.rollback()

    assert (
        db.query(models.EvaluationResult).count()
        == 0
    )
    assert (
        db.query(HveeObservation).count()
        == 0
    )
    assert (
        db.query(HveeMetricDefinition).count()
        == 0
    )
    assert (
        db.query(HveeEvaluatorVersion).count()
        == 0
    )

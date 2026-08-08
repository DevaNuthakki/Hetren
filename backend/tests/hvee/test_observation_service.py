import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models
from app.database import Base
from app.hvee_models import (
    HveeEvaluatorVersion,
    HveeMetricDefinition,
)
from app.hvee_observation_service import (
    HveeObservationPersistenceError,
    stage_hvee_observation,
)
from hvee.core.contracts import (
    HveeContractError,
    MetricValueType,
    Observation,
    ObservationStatus,
)


@pytest.fixture()
def db() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
    )

    Base.metadata.create_all(engine)

    with Session(engine) as session:
        yield session

    engine.dispose()


def build_foundation(
    db: Session,
) -> tuple[
    models.EvaluationRun,
    models.TestCase,
    HveeMetricDefinition,
    HveeEvaluatorVersion,
]:
    project = models.Project(
        name="HVEE service project",
    )

    dataset = models.Dataset(
        project=project,
        name="HVEE service dataset",
    )

    test_case = models.TestCase(
        dataset=dataset,
        title="Service test case",
        reference_transcript="hello world",
    )

    run = models.EvaluationRun(
        project=project,
        run_name="Service run",
        evaluation_type="asr",
        model_name="test-model",
    )

    metric = HveeMetricDefinition(
        key="asr.wer",
        version="1.0.0",
        evaluation_type="asr",
        value_type="number",
        direction="lower_is_better",
        unit="ratio",
        description="Word error rate.",
    )

    evaluator = HveeEvaluatorVersion(
        key="hetren.asr.wer",
        version="1.0.0",
        evaluation_type="asr",
        description="Deterministic WER evaluator.",
    )

    db.add_all(
        [
            project,
            dataset,
            test_case,
            run,
            metric,
            evaluator,
        ]
    )
    db.commit()

    return run, test_case, metric, evaluator


def build_success_observation() -> Observation:
    return Observation(
        metric_key="asr.wer",
        metric_version="1.0.0",
        evaluator_key="hetren.asr.wer",
        evaluator_version="1.0.0",
        evaluation_type="asr",
        status=ObservationStatus.SUCCESS,
        value_type=MetricValueType.NUMBER,
        value=0.125,
    )


def test_stage_run_observation_derives_persistence_fields(
    db: Session,
):
    run, _, metric, evaluator = build_foundation(db)

    staged = stage_hvee_observation(
        db,
        evaluation_run=run,
        metric_definition=metric,
        evaluator_version=evaluator,
        observation=build_success_observation(),
    )

    assert staged.id is None
    assert staged in db.new
    assert staged.scope == "run"
    assert staged.evaluation_type == "asr"
    assert staged.value_type == "number"
    assert staged.number_value == 0.125
    assert staged.test_case_id is None


def test_stage_test_case_observation_derives_scope(
    db: Session,
):
    run, test_case, metric, evaluator = build_foundation(db)

    staged = stage_hvee_observation(
        db,
        evaluation_run=run,
        test_case=test_case,
        metric_definition=metric,
        evaluator_version=evaluator,
        observation=build_success_observation(),
    )

    assert staged.scope == "test_case"
    assert staged.test_case_id == test_case.id


def test_rejects_test_case_from_different_project(
    db: Session,
):
    run, _, metric, evaluator = build_foundation(db)

    other_project = models.Project(
        name="Other project",
    )
    other_dataset = models.Dataset(
        project=other_project,
        name="Other dataset",
    )
    other_test_case = models.TestCase(
        dataset=other_dataset,
        title="Wrong project case",
        reference_transcript="different",
    )

    db.add_all(
        [
            other_project,
            other_dataset,
            other_test_case,
        ]
    )
    db.commit()

    with pytest.raises(
        HveeObservationPersistenceError,
        match="does not belong",
    ):
        stage_hvee_observation(
            db,
            evaluation_run=run,
            test_case=other_test_case,
            metric_definition=metric,
            evaluator_version=evaluator,
            observation=build_success_observation(),
        )


def test_rejects_run_evaluation_type_mismatch(
    db: Session,
):
    run, _, metric, evaluator = build_foundation(db)

    run.evaluation_type = "diarization"

    with pytest.raises(
        HveeObservationPersistenceError,
        match="run type",
    ):
        stage_hvee_observation(
            db,
            evaluation_run=run,
            metric_definition=metric,
            evaluator_version=evaluator,
            observation=build_success_observation(),
        )


def test_rejects_metric_identity_mismatch(
    db: Session,
):
    run, _, metric, evaluator = build_foundation(db)

    observation = Observation(
        metric_key="asr.cer",
        metric_version="1.0.0",
        evaluator_key="hetren.asr.wer",
        evaluator_version="1.0.0",
        evaluation_type="asr",
        status=ObservationStatus.SUCCESS,
        value_type=MetricValueType.NUMBER,
        value=0.125,
    )

    with pytest.raises(
        HveeContractError,
        match="metric key",
    ):
        stage_hvee_observation(
            db,
            evaluation_run=run,
            metric_definition=metric,
            evaluator_version=evaluator,
            observation=observation,
        )


def test_non_success_observation_stages_without_value(
    db: Session,
):
    run, _, metric, evaluator = build_foundation(db)

    observation = Observation(
        metric_key="asr.wer",
        metric_version="1.0.0",
        evaluator_key="hetren.asr.wer",
        evaluator_version="1.0.0",
        evaluation_type="asr",
        status=ObservationStatus.ABSTAINED,
        value_type=MetricValueType.NUMBER,
        status_detail="Reference is not suitable for this evaluator.",
    )

    staged = stage_hvee_observation(
        db,
        evaluation_run=run,
        metric_definition=metric,
        evaluator_version=evaluator,
        observation=observation,
    )

    assert staged.status == "abstained"
    assert staged.number_value is None
    assert staged.integer_value is None
    assert staged.boolean_value is None
    assert staged.string_value is None
    assert staged.json_value is None
    assert staged.status_detail is not None


def test_unpersisted_run_is_rejected(
    db: Session,
):
    _, _, metric, evaluator = build_foundation(db)

    run = models.EvaluationRun(
        project_id=1,
        run_name="Unpersisted run",
        evaluation_type="asr",
        model_name="test-model",
    )

    with pytest.raises(
        HveeObservationPersistenceError,
        match="must be persisted",
    ):
        stage_hvee_observation(
            db,
            evaluation_run=run,
            metric_definition=metric,
            evaluator_version=evaluator,
            observation=build_success_observation(),
        )

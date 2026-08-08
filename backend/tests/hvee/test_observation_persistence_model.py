import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.database import Base
from app.hvee_models import (
    HveeEvaluatorVersion,
    HveeMetricDefinition,
    HveeObservation,
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
        name="HVEE observation project",
    )

    dataset = models.Dataset(
        project=project,
        name="HVEE observation dataset",
    )

    test_case = models.TestCase(
        dataset=dataset,
        title="Observation test case",
        reference_transcript="hello world",
    )

    run = models.EvaluationRun(
        project=project,
        run_name="Observation run",
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


def test_successful_run_observation_persists_numeric_value(
    db: Session,
):
    run, _, metric, evaluator = build_foundation(db)

    observation = HveeObservation(
        evaluation_run_id=run.id,
        metric_definition_id=metric.id,
        evaluator_version_id=evaluator.id,
        evaluation_type="asr",
        scope="run",
        status="success",
        value_type="number",
        number_value=0.125,
    )

    db.add(observation)
    db.commit()

    assert observation.id is not None
    assert observation.number_value == 0.125
    assert observation.test_case_id is None


def test_successful_test_case_observation_has_test_case(
    db: Session,
):
    run, test_case, metric, evaluator = build_foundation(db)

    observation = HveeObservation(
        evaluation_run_id=run.id,
        test_case_id=test_case.id,
        metric_definition_id=metric.id,
        evaluator_version_id=evaluator.id,
        evaluation_type="asr",
        scope="test_case",
        status="success",
        value_type="number",
        number_value=0.20,
    )

    db.add(observation)
    db.commit()

    assert observation.id is not None
    assert observation.test_case_id == test_case.id


def test_run_scope_rejects_test_case_target(
    db: Session,
):
    run, test_case, metric, evaluator = build_foundation(db)

    db.add(
        HveeObservation(
            evaluation_run_id=run.id,
            test_case_id=test_case.id,
            metric_definition_id=metric.id,
            evaluator_version_id=evaluator.id,
            evaluation_type="asr",
            scope="run",
            status="success",
            value_type="number",
            number_value=0.10,
        )
    )

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_test_case_scope_requires_test_case(
    db: Session,
):
    run, _, metric, evaluator = build_foundation(db)

    db.add(
        HveeObservation(
            evaluation_run_id=run.id,
            metric_definition_id=metric.id,
            evaluator_version_id=evaluator.id,
            evaluation_type="asr",
            scope="test_case",
            status="success",
            value_type="number",
            number_value=0.10,
        )
    )

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_success_requires_exact_matching_typed_value(
    db: Session,
):
    run, _, metric, evaluator = build_foundation(db)

    db.add(
        HveeObservation(
            evaluation_run_id=run.id,
            metric_definition_id=metric.id,
            evaluator_version_id=evaluator.id,
            evaluation_type="asr",
            scope="run",
            status="success",
            value_type="number",
            integer_value=1,
        )
    )

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_success_rejects_multiple_value_columns(
    db: Session,
):
    run, _, metric, evaluator = build_foundation(db)

    db.add(
        HveeObservation(
            evaluation_run_id=run.id,
            metric_definition_id=metric.id,
            evaluator_version_id=evaluator.id,
            evaluation_type="asr",
            scope="run",
            status="success",
            value_type="number",
            number_value=0.10,
            string_value="unexpected",
        )
    )

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


@pytest.mark.parametrize(
    "status",
    [
        "abstained",
        "unsupported",
        "timed_out",
        "failed",
        "cancelled",
        "invalid",
    ],
)
def test_non_success_has_no_value_and_requires_detail(
    db: Session,
    status: str,
):
    run, _, metric, evaluator = build_foundation(db)

    observation = HveeObservation(
        evaluation_run_id=run.id,
        metric_definition_id=metric.id,
        evaluator_version_id=evaluator.id,
        evaluation_type="asr",
        scope="run",
        status=status,
        value_type="number",
        status_detail="No valid measurement was produced.",
    )

    db.add(observation)
    db.commit()

    assert observation.id is not None
    assert observation.number_value is None


def test_non_success_rejects_metric_value(
    db: Session,
):
    run, _, metric, evaluator = build_foundation(db)

    db.add(
        HveeObservation(
            evaluation_run_id=run.id,
            metric_definition_id=metric.id,
            evaluator_version_id=evaluator.id,
            evaluation_type="asr",
            scope="run",
            status="failed",
            value_type="number",
            number_value=0.0,
            status_detail="Evaluator failed.",
        )
    )

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_non_success_requires_nonblank_detail(
    db: Session,
):
    run, _, metric, evaluator = build_foundation(db)

    db.add(
        HveeObservation(
            evaluation_run_id=run.id,
            metric_definition_id=metric.id,
            evaluator_version_id=evaluator.id,
            evaluation_type="asr",
            scope="run",
            status="failed",
            value_type="number",
            status_detail="   ",
        )
    )

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_invalid_scope_is_rejected(
    db: Session,
):
    run, _, metric, evaluator = build_foundation(db)

    db.add(
        HveeObservation(
            evaluation_run_id=run.id,
            metric_definition_id=metric.id,
            evaluator_version_id=evaluator.id,
            evaluation_type="asr",
            scope="segment",
            status="success",
            value_type="number",
            number_value=0.10,
        )
    )

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_duplicate_run_observation_is_rejected(
    db: Session,
):
    run, _, metric, evaluator = build_foundation(db)

    db.add(
        HveeObservation(
            evaluation_run_id=run.id,
            metric_definition_id=metric.id,
            evaluator_version_id=evaluator.id,
            evaluation_type="asr",
            scope="run",
            status="success",
            value_type="number",
            number_value=0.10,
        )
    )
    db.commit()

    db.add(
        HveeObservation(
            evaluation_run_id=run.id,
            metric_definition_id=metric.id,
            evaluator_version_id=evaluator.id,
            evaluation_type="asr",
            scope="run",
            status="success",
            value_type="number",
            number_value=0.20,
        )
    )

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_duplicate_test_case_observation_is_rejected(
    db: Session,
):
    run, test_case, metric, evaluator = build_foundation(db)

    db.add(
        HveeObservation(
            evaluation_run_id=run.id,
            test_case_id=test_case.id,
            metric_definition_id=metric.id,
            evaluator_version_id=evaluator.id,
            evaluation_type="asr",
            scope="test_case",
            status="success",
            value_type="number",
            number_value=0.10,
        )
    )
    db.commit()

    db.add(
        HveeObservation(
            evaluation_run_id=run.id,
            test_case_id=test_case.id,
            metric_definition_id=metric.id,
            evaluator_version_id=evaluator.id,
            evaluation_type="asr",
            scope="test_case",
            status="success",
            value_type="number",
            number_value=0.20,
        )
    )

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_same_metric_can_exist_for_different_test_cases(
    db: Session,
):
    run, test_case, metric, evaluator = build_foundation(db)

    second_test_case = models.TestCase(
        dataset=test_case.dataset,
        title="Second observation test case",
        reference_transcript="another reference",
    )

    db.add(second_test_case)
    db.commit()

    db.add_all(
        [
            HveeObservation(
                evaluation_run_id=run.id,
                test_case_id=test_case.id,
                metric_definition_id=metric.id,
                evaluator_version_id=evaluator.id,
                evaluation_type="asr",
                scope="test_case",
                status="success",
                value_type="number",
                number_value=0.10,
            ),
            HveeObservation(
                evaluation_run_id=run.id,
                test_case_id=second_test_case.id,
                metric_definition_id=metric.id,
                evaluator_version_id=evaluator.id,
                evaluation_type="asr",
                scope="test_case",
                status="success",
                value_type="number",
                number_value=0.20,
            ),
        ]
    )

    db.commit()

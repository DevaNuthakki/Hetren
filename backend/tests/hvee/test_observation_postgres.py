import os

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.hvee_models import (
    HveeEvaluatorVersion,
    HveeMetricDefinition,
    HveeObservation,
)


pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        os.getenv("RUN_POSTGRES_TESTS") != "1",
        reason=(
            "Set RUN_POSTGRES_TESTS=1 to run PostgreSQL "
            "integration tests."
        ),
    ),
]


def build_foundation(
    postgres_session: Session,
) -> tuple[
    models.EvaluationRun,
    models.TestCase,
    HveeMetricDefinition,
    HveeEvaluatorVersion,
]:
    project = models.Project(
        name="HVEE PostgreSQL observation project",
    )

    dataset = models.Dataset(
        project=project,
        name="HVEE PostgreSQL observation dataset",
    )

    test_case = models.TestCase(
        dataset=dataset,
        title="HVEE PostgreSQL observation case",
        reference_transcript="hello world",
    )

    run = models.EvaluationRun(
        project=project,
        run_name="HVEE PostgreSQL observation run",
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

    postgres_session.add_all(
        [
            project,
            dataset,
            test_case,
            run,
            metric,
            evaluator,
        ]
    )
    postgres_session.flush()

    return run, test_case, metric, evaluator


def build_run_observation(
    *,
    run: models.EvaluationRun,
    metric: HveeMetricDefinition,
    evaluator: HveeEvaluatorVersion,
    status: str = "success",
    value_type: str = "number",
    number_value: float | None = 0.125,
    status_detail: str | None = None,
) -> HveeObservation:
    return HveeObservation(
        evaluation_run_id=run.id,
        metric_definition_id=metric.id,
        evaluator_version_id=evaluator.id,
        evaluation_type="asr",
        scope="run",
        status=status,
        value_type=value_type,
        number_value=number_value,
        status_detail=status_detail,
    )


def test_postgres_accepts_valid_numeric_observation(
    postgres_session: Session,
):
    run, _, metric, evaluator = build_foundation(
        postgres_session
    )

    observation = build_run_observation(
        run=run,
        metric=metric,
        evaluator=evaluator,
    )

    postgres_session.add(observation)
    postgres_session.flush()

    assert observation.id is not None
    assert observation.number_value == 0.125


def test_postgres_accepts_non_success_with_detail(
    postgres_session: Session,
):
    run, _, metric, evaluator = build_foundation(
        postgres_session
    )

    observation = build_run_observation(
        run=run,
        metric=metric,
        evaluator=evaluator,
        status="abstained",
        number_value=None,
        status_detail=(
            "Reference is unsuitable for this evaluator."
        ),
    )

    postgres_session.add(observation)
    postgres_session.flush()

    assert observation.id is not None
    assert observation.number_value is None


def test_postgres_rejects_duplicate_run_observation(
    postgres_session: Session,
):
    run, _, metric, evaluator = build_foundation(
        postgres_session
    )

    first = build_run_observation(
        run=run,
        metric=metric,
        evaluator=evaluator,
        number_value=0.10,
    )
    postgres_session.add(first)
    postgres_session.flush()

    duplicate = build_run_observation(
        run=run,
        metric=metric,
        evaluator=evaluator,
        number_value=0.20,
    )
    postgres_session.add(duplicate)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


def test_postgres_rejects_duplicate_test_case_observation(
    postgres_session: Session,
):
    run, test_case, metric, evaluator = build_foundation(
        postgres_session
    )

    first = HveeObservation(
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

    postgres_session.add(first)
    postgres_session.flush()

    duplicate = HveeObservation(
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

    postgres_session.add(duplicate)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


def test_postgres_allows_same_metric_for_different_test_cases(
    postgres_session: Session,
):
    run, first_case, metric, evaluator = build_foundation(
        postgres_session
    )

    second_case = models.TestCase(
        dataset_id=first_case.dataset_id,
        title="Second PostgreSQL observation case",
        reference_transcript="another reference",
    )

    postgres_session.add(second_case)
    postgres_session.flush()

    first = HveeObservation(
        evaluation_run_id=run.id,
        test_case_id=first_case.id,
        metric_definition_id=metric.id,
        evaluator_version_id=evaluator.id,
        evaluation_type="asr",
        scope="test_case",
        status="success",
        value_type="number",
        number_value=0.10,
    )

    second = HveeObservation(
        evaluation_run_id=run.id,
        test_case_id=second_case.id,
        metric_definition_id=metric.id,
        evaluator_version_id=evaluator.id,
        evaluation_type="asr",
        scope="test_case",
        status="success",
        value_type="number",
        number_value=0.20,
    )

    postgres_session.add_all(
        [first, second]
    )
    postgres_session.flush()

    assert first.id is not None
    assert second.id is not None


def test_postgres_rejects_success_with_wrong_typed_value(
    postgres_session: Session,
):
    run, _, metric, evaluator = build_foundation(
        postgres_session
    )

    observation = HveeObservation(
        evaluation_run_id=run.id,
        metric_definition_id=metric.id,
        evaluator_version_id=evaluator.id,
        evaluation_type="asr",
        scope="run",
        status="success",
        value_type="number",
        integer_value=1,
    )

    postgres_session.add(observation)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


def test_postgres_rejects_success_with_multiple_values(
    postgres_session: Session,
):
    run, _, metric, evaluator = build_foundation(
        postgres_session
    )

    observation = HveeObservation(
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

    postgres_session.add(observation)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


def test_postgres_rejects_non_success_with_value(
    postgres_session: Session,
):
    run, _, metric, evaluator = build_foundation(
        postgres_session
    )

    observation = build_run_observation(
        run=run,
        metric=metric,
        evaluator=evaluator,
        status="failed",
        number_value=0.0,
        status_detail="Evaluator failed.",
    )

    postgres_session.add(observation)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


@pytest.mark.parametrize(
    "status_detail",
    [
        None,
        "",
        "   ",
    ],
)
def test_postgres_rejects_non_success_without_detail(
    postgres_session: Session,
    status_detail: str | None,
):
    run, _, metric, evaluator = build_foundation(
        postgres_session
    )

    observation = build_run_observation(
        run=run,
        metric=metric,
        evaluator=evaluator,
        status="failed",
        number_value=None,
        status_detail=status_detail,
    )

    postgres_session.add(observation)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


def test_postgres_rejects_run_scope_with_test_case(
    postgres_session: Session,
):
    run, test_case, metric, evaluator = build_foundation(
        postgres_session
    )

    observation = HveeObservation(
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

    postgres_session.add(observation)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


def test_postgres_rejects_test_case_scope_without_test_case(
    postgres_session: Session,
):
    run, _, metric, evaluator = build_foundation(
        postgres_session
    )

    observation = HveeObservation(
        evaluation_run_id=run.id,
        metric_definition_id=metric.id,
        evaluator_version_id=evaluator.id,
        evaluation_type="asr",
        scope="test_case",
        status="success",
        value_type="number",
        number_value=0.10,
    )

    postgres_session.add(observation)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("scope", "segment"),
        ("status", "unknown"),
        ("value_type", "vector"),
    ],
)
def test_postgres_rejects_invalid_observation_enums(
    postgres_session: Session,
    field_name: str,
    invalid_value: str,
):
    run, _, metric, evaluator = build_foundation(
        postgres_session
    )

    values = {
        "evaluation_run_id": run.id,
        "metric_definition_id": metric.id,
        "evaluator_version_id": evaluator.id,
        "evaluation_type": "asr",
        "scope": "run",
        "status": "success",
        "value_type": "number",
        "number_value": 0.10,
    }
    values[field_name] = invalid_value

    observation = HveeObservation(
        **values
    )

    postgres_session.add(observation)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


def test_postgres_rejects_invalid_observation_foreign_key(
    postgres_session: Session,
):
    run, _, metric, evaluator = build_foundation(
        postgres_session
    )

    observation = HveeObservation(
        evaluation_run_id=2_147_483_647,
        metric_definition_id=metric.id,
        evaluator_version_id=evaluator.id,
        evaluation_type=run.evaluation_type,
        scope="run",
        status="success",
        value_type="number",
        number_value=0.10,
    )

    postgres_session.add(observation)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()

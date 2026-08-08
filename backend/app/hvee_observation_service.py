from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.hvee_models import (
    HveeEvaluatorVersion,
    HveeMetricDefinition,
    HveeObservation,
)
from hvee.core.contracts import (
    EvaluatorVersion,
    HveeContractError,
    MetricDefinition,
    MetricDirection,
    MetricValueType,
    Observation,
    ObservationStatus,
)
from hvee.core.validation import (
    validate_observation_contract,
)


class HveeObservationPersistenceError(ValueError):
    """Raised when an observation cannot be safely persisted."""


def _build_metric_contract(
    metric: HveeMetricDefinition,
) -> MetricDefinition:
    try:
        return MetricDefinition(
            key=metric.key,
            version=metric.version,
            evaluation_type=metric.evaluation_type,
            value_type=MetricValueType(metric.value_type),
            direction=MetricDirection(metric.direction),
            unit=metric.unit,
            description=metric.description,
        )
    except (ValueError, HveeContractError) as exc:
        raise HveeObservationPersistenceError(
            "persisted metric definition violates the HVEE contract"
        ) from exc


def _build_evaluator_contract(
    evaluator: HveeEvaluatorVersion,
) -> EvaluatorVersion:
    try:
        return EvaluatorVersion(
            key=evaluator.key,
            version=evaluator.version,
            evaluation_type=evaluator.evaluation_type,
            description=evaluator.description,
        )
    except HveeContractError as exc:
        raise HveeObservationPersistenceError(
            "persisted evaluator version violates the HVEE contract"
        ) from exc


def _validate_persisted_identity(
    *,
    name: str,
    record_id: int | None,
) -> None:
    if record_id is None:
        raise HveeObservationPersistenceError(
            f"{name} must be persisted before staging an observation"
        )


def _validate_test_case_scope(
    db: Session,
    *,
    evaluation_run: models.EvaluationRun,
    test_case: models.TestCase | None,
) -> str:
    if test_case is None:
        return "run"

    _validate_persisted_identity(
        name="test case",
        record_id=test_case.id,
    )

    dataset = db.get(
        models.Dataset,
        test_case.dataset_id,
    )

    if dataset is None:
        raise HveeObservationPersistenceError(
            "test case dataset does not exist"
        )

    if dataset.project_id != evaluation_run.project_id:
        raise HveeObservationPersistenceError(
            "test case does not belong to the evaluation run project"
        )

    return "test_case"


def _lock_and_validate_unsealed_test_case_target(
    db: Session,
    *,
    evaluation_run: models.EvaluationRun,
    test_case: models.TestCase | None,
) -> None:
    """
    Serialize observation staging for one test-case target.

    Once result provenance exists, the test-case observation set is
    sealed and may not be extended through the application service.
    Run-scoped observations are intentionally unaffected because they
    are excluded from result-level immutable provenance.
    """

    if test_case is None:
        return

    locked_test_case = (
        db.query(models.TestCase)
        .filter(
            models.TestCase.id == test_case.id
        )
        .with_for_update()
        .one_or_none()
    )

    if locked_test_case is None:
        raise HveeObservationPersistenceError(
            "test case does not exist"
        )

    existing_result = (
        db.query(models.EvaluationResult)
        .filter(
            models.EvaluationResult.run_id
            == evaluation_run.id,
            models.EvaluationResult.test_case_id
            == test_case.id,
        )
        .one_or_none()
    )

    if existing_result is None:
        return

    provenance_exists = (
        db.query(
            models.EvaluationResultProvenance.id
        )
        .filter(
            models.EvaluationResultProvenance.result_id
            == existing_result.id
        )
        .first()
        is not None
    )

    if provenance_exists:
        raise HveeObservationPersistenceError(
            "test-case observations are immutable after "
            "result provenance is sealed"
        )


def _build_value_columns(
    observation: Observation,
) -> dict[str, object | None]:
    values: dict[str, object | None] = {
        "number_value": None,
        "integer_value": None,
        "boolean_value": None,
        "string_value": None,
        "json_value": None,
    }

    if observation.status != ObservationStatus.SUCCESS:
        return values

    if observation.value_type == MetricValueType.NUMBER:
        values["number_value"] = float(observation.value)

    elif observation.value_type == MetricValueType.INTEGER:
        values["integer_value"] = observation.value

    elif observation.value_type == MetricValueType.BOOLEAN:
        values["boolean_value"] = observation.value

    elif observation.value_type == MetricValueType.STRING:
        values["string_value"] = observation.value

    elif observation.value_type == MetricValueType.JSON:
        values["json_value"] = observation.value

    return values


def stage_hvee_observation(
    db: Session,
    *,
    evaluation_run: models.EvaluationRun,
    metric_definition: HveeMetricDefinition,
    evaluator_version: HveeEvaluatorVersion,
    observation: Observation,
    test_case: models.TestCase | None = None,
) -> HveeObservation:
    """
    Stage one validated HVEE observation without committing.

    The caller owns the surrounding transaction so an observation can
    later be committed atomically with evaluation results and evidence.
    """

    _validate_persisted_identity(
        name="evaluation run",
        record_id=evaluation_run.id,
    )
    _validate_persisted_identity(
        name="metric definition",
        record_id=metric_definition.id,
    )
    _validate_persisted_identity(
        name="evaluator version",
        record_id=evaluator_version.id,
    )

    metric_contract = _build_metric_contract(
        metric_definition
    )
    evaluator_contract = _build_evaluator_contract(
        evaluator_version
    )

    validate_observation_contract(
        metric=metric_contract,
        evaluator=evaluator_contract,
        observation=observation,
    )

    if (
        evaluation_run.evaluation_type
        != observation.evaluation_type
    ):
        raise HveeObservationPersistenceError(
            "evaluation run type does not match observation type"
        )

    scope = _validate_test_case_scope(
        db,
        evaluation_run=evaluation_run,
        test_case=test_case,
    )

    _lock_and_validate_unsealed_test_case_target(
        db,
        evaluation_run=evaluation_run,
        test_case=test_case,
    )

    value_columns = _build_value_columns(
        observation
    )

    db_observation = HveeObservation(
        evaluation_run_id=evaluation_run.id,
        test_case_id=(
            test_case.id
            if test_case is not None
            else None
        ),
        metric_definition_id=metric_definition.id,
        evaluator_version_id=evaluator_version.id,
        evaluation_type=evaluation_run.evaluation_type,
        scope=scope,
        status=observation.status.value,
        value_type=observation.value_type.value,
        status_detail=observation.status_detail,
        **value_columns,
    )

    db.add(db_observation)

    return db_observation

from __future__ import annotations

from sqlalchemy.orm import Session

from app.hvee_models import (
    HveeEvaluatorVersion,
    HveeMetricDefinition,
    HveeObservation,
)
from hvee.core.contracts import (
    HveeContractError,
    MetricValueType,
    ObservationStatus,
)
from hvee.core.observation_evidence import (
    ObservationEvidenceRecord,
    build_observation_evidence_bundle,
)


class HveeObservationEvidenceError(ValueError):
    """Raised when persisted observations cannot form valid evidence."""


def _build_persisted_value(
    observation: HveeObservation,
    *,
    status: ObservationStatus,
    value_type: MetricValueType,
) -> object | None:
    values = {
        MetricValueType.NUMBER: (
            observation.number_value
        ),
        MetricValueType.INTEGER: (
            observation.integer_value
        ),
        MetricValueType.BOOLEAN: (
            observation.boolean_value
        ),
        MetricValueType.STRING: (
            observation.string_value
        ),
        MetricValueType.JSON: (
            observation.json_value
        ),
    }

    populated = [
        candidate
        for candidate in values.values()
        if candidate is not None
    ]

    if status != ObservationStatus.SUCCESS:
        if populated:
            raise HveeObservationEvidenceError(
                "non-success persisted observation "
                "cannot contain a typed value"
            )

        return None

    value = values[value_type]

    if value is None:
        raise HveeObservationEvidenceError(
            "successful persisted observation "
            "is missing its typed value"
        )

    if len(populated) != 1:
        raise HveeObservationEvidenceError(
            "successful persisted observation "
            "must contain exactly one typed value"
        )

    return value


def build_observation_evidence_record(
    *,
    observation: HveeObservation,
    metric: HveeMetricDefinition,
    evaluator: HveeEvaluatorVersion,
) -> ObservationEvidenceRecord:
    """
    Adapt one persisted HVEE observation to the pure evidence contract.

    Database registry IDs and timestamps are deliberately excluded.
    """

    if (
        observation.id is None
        or metric.id is None
        or evaluator.id is None
    ):
        raise HveeObservationEvidenceError(
            "observation evidence requires persisted records"
        )

    if (
        observation.metric_definition_id
        != metric.id
    ):
        raise HveeObservationEvidenceError(
            "observation metric identity does not match"
        )

    if (
        observation.evaluator_version_id
        != evaluator.id
    ):
        raise HveeObservationEvidenceError(
            "observation evaluator identity does not match"
        )

    if not (
        observation.evaluation_type
        == metric.evaluation_type
        == evaluator.evaluation_type
    ):
        raise HveeObservationEvidenceError(
            "observation, metric, and evaluator "
            "evaluation types do not match"
        )

    if observation.value_type != metric.value_type:
        raise HveeObservationEvidenceError(
            "observation value type does not match "
            "metric definition"
        )

    try:
        status = ObservationStatus(
            observation.status
        )
        value_type = MetricValueType(
            observation.value_type
        )
    except ValueError as exc:
        raise HveeObservationEvidenceError(
            "persisted observation contains an "
            "unsupported status or value type"
        ) from exc

    value = _build_persisted_value(
        observation,
        status=status,
        value_type=value_type,
    )

    try:
        return ObservationEvidenceRecord(
            metric_key=metric.key,
            metric_version=metric.version,
            evaluator_key=evaluator.key,
            evaluator_version=evaluator.version,
            evaluation_type=(
                observation.evaluation_type
            ),
            scope=observation.scope,
            evaluation_run_id=(
                observation.evaluation_run_id
            ),
            test_case_id=(
                observation.test_case_id
            ),
            status=status,
            value_type=value_type,
            value=value,
            status_detail=(
                observation.status_detail
            ),
        )
    except HveeContractError as exc:
        raise HveeObservationEvidenceError(
            "persisted observation violates the "
            "observation evidence contract"
        ) from exc


def load_test_case_observation_evidence_records(
    db: Session,
    *,
    evaluation_run_id: int,
    test_case_id: int,
) -> tuple[ObservationEvidenceRecord, ...]:
    """
    Load evidence records for one evaluated test case.

    Run-scoped observations are deliberately excluded because a
    result's immutable evidence must not depend on aggregates that can
    change when other test cases complete.
    """

    rows = (
        db.query(
            HveeObservation,
            HveeMetricDefinition,
            HveeEvaluatorVersion,
        )
        .join(
            HveeMetricDefinition,
            HveeMetricDefinition.id
            == HveeObservation.metric_definition_id,
        )
        .join(
            HveeEvaluatorVersion,
            HveeEvaluatorVersion.id
            == HveeObservation.evaluator_version_id,
        )
        .filter(
            HveeObservation.evaluation_run_id
            == evaluation_run_id,
            HveeObservation.test_case_id
            == test_case_id,
            HveeObservation.scope
            == "test_case",
        )
        .all()
    )

    if not rows:
        raise HveeObservationEvidenceError(
            "no test-case observations are available "
            "for evidence binding"
        )

    records = tuple(
        build_observation_evidence_record(
            observation=observation,
            metric=metric,
            evaluator=evaluator,
        )
        for observation, metric, evaluator
        in rows
    )

    return records


def build_test_case_observation_evidence_bundle(
    db: Session,
    *,
    evaluation_run_id: int,
    test_case_id: int,
) -> dict[str, object]:
    records = (
        load_test_case_observation_evidence_records(
            db,
            evaluation_run_id=evaluation_run_id,
            test_case_id=test_case_id,
        )
    )

    try:
        return build_observation_evidence_bundle(
            records
        )
    except HveeContractError as exc:
        raise HveeObservationEvidenceError(
            "persisted observations cannot form "
            "canonical evidence"
        ) from exc

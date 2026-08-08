from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.hvee_models import (
    HveeEvaluatorVersion,
    HveeMetricDefinition,
)
from hvee.core.contracts import (
    EvaluatorVersion,
    MetricDefinition,
)


class HveeRegistryError(ValueError):
    """Base error for HVEE registry operations."""


class HveeRegistryConflictError(HveeRegistryError):
    """
    Raised when an existing versioned identity no longer matches
    its canonical definition.
    """


def _metric_matches(
    persisted: HveeMetricDefinition,
    definition: MetricDefinition,
) -> bool:
    return (
        persisted.key == definition.key
        and persisted.version == definition.version
        and persisted.evaluation_type
        == definition.evaluation_type
        and persisted.value_type
        == definition.value_type.value
        and persisted.direction
        == definition.direction.value
        and persisted.unit == definition.unit
        and persisted.description
        == definition.description
    )


def _evaluator_matches(
    persisted: HveeEvaluatorVersion,
    definition: EvaluatorVersion,
) -> bool:
    return (
        persisted.key == definition.key
        and persisted.version == definition.version
        and persisted.evaluation_type
        == definition.evaluation_type
        and persisted.description
        == definition.description
    )


def _get_metric(
    db: Session,
    definition: MetricDefinition,
) -> HveeMetricDefinition | None:
    return db.scalar(
        select(HveeMetricDefinition).where(
            HveeMetricDefinition.key
            == definition.key,
            HveeMetricDefinition.version
            == definition.version,
        )
    )


def _get_evaluator(
    db: Session,
    definition: EvaluatorVersion,
) -> HveeEvaluatorVersion | None:
    return db.scalar(
        select(HveeEvaluatorVersion).where(
            HveeEvaluatorVersion.key
            == definition.key,
            HveeEvaluatorVersion.version
            == definition.version,
        )
    )


def resolve_metric_definition(
    db: Session,
    definition: MetricDefinition,
) -> HveeMetricDefinition:
    existing = _get_metric(
        db,
        definition,
    )

    if existing is not None:
        if not _metric_matches(
            existing,
            definition,
        ):
            raise HveeRegistryConflictError(
                "existing metric version does not match "
                "its canonical HVEE definition"
            )

        return existing

    candidate = HveeMetricDefinition(
        key=definition.key,
        version=definition.version,
        evaluation_type=definition.evaluation_type,
        value_type=definition.value_type.value,
        direction=definition.direction.value,
        unit=definition.unit,
        description=definition.description,
    )

    try:
        # A nested transaction keeps a concurrent insert conflict
        # from rolling back the caller's surrounding transaction.
        with db.begin_nested():
            db.add(candidate)
            db.flush()

        return candidate
    except IntegrityError:
        # Another transaction may have created the same versioned
        # identity between our initial lookup and insert.
        existing = _get_metric(
            db,
            definition,
        )

        if existing is None:
            raise

        if not _metric_matches(
            existing,
            definition,
        ):
            raise HveeRegistryConflictError(
                "existing metric version does not match "
                "its canonical HVEE definition"
            )

        return existing


def resolve_evaluator_version(
    db: Session,
    definition: EvaluatorVersion,
) -> HveeEvaluatorVersion:
    existing = _get_evaluator(
        db,
        definition,
    )

    if existing is not None:
        if not _evaluator_matches(
            existing,
            definition,
        ):
            raise HveeRegistryConflictError(
                "existing evaluator version does not match "
                "its canonical HVEE definition"
            )

        return existing

    candidate = HveeEvaluatorVersion(
        key=definition.key,
        version=definition.version,
        evaluation_type=definition.evaluation_type,
        description=definition.description,
    )

    try:
        with db.begin_nested():
            db.add(candidate)
            db.flush()

        return candidate
    except IntegrityError:
        existing = _get_evaluator(
            db,
            definition,
        )

        if existing is None:
            raise

        if not _evaluator_matches(
            existing,
            definition,
        ):
            raise HveeRegistryConflictError(
                "existing evaluator version does not match "
                "its canonical HVEE definition"
            )

        return existing

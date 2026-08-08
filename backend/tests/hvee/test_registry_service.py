import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.hvee_asr_registry import (
    resolve_asr_text_error_registry,
)
from app.hvee_models import (
    HveeEvaluatorVersion,
    HveeMetricDefinition,
)
from app.hvee_registry_service import (
    HveeRegistryConflictError,
    resolve_evaluator_version,
    resolve_metric_definition,
)
from hvee.packs.asr import (
    WER_EVALUATOR,
    WER_METRIC,
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


def test_resolve_metric_definition_creates_exact_identity(
    db: Session,
):
    persisted = resolve_metric_definition(
        db,
        WER_METRIC,
    )

    assert persisted.id is not None
    assert persisted.key == WER_METRIC.key
    assert persisted.version == WER_METRIC.version
    assert (
        persisted.evaluation_type
        == WER_METRIC.evaluation_type
    )
    assert (
        persisted.value_type
        == WER_METRIC.value_type.value
    )
    assert (
        persisted.direction
        == WER_METRIC.direction.value
    )
    assert persisted.unit == WER_METRIC.unit
    assert (
        persisted.description
        == WER_METRIC.description
    )


def test_resolve_metric_definition_is_idempotent(
    db: Session,
):
    first = resolve_metric_definition(
        db,
        WER_METRIC,
    )
    second = resolve_metric_definition(
        db,
        WER_METRIC,
    )

    assert second.id == first.id

    assert (
        db.query(HveeMetricDefinition)
        .filter(
            HveeMetricDefinition.key
            == WER_METRIC.key,
            HveeMetricDefinition.version
            == WER_METRIC.version,
        )
        .count()
        == 1
    )


def test_metric_version_conflict_is_rejected(
    db: Session,
):
    conflicting = HveeMetricDefinition(
        key=WER_METRIC.key,
        version=WER_METRIC.version,
        evaluation_type="asr",
        value_type="number",
        direction="higher_is_better",
        unit="ratio",
        description=WER_METRIC.description,
    )

    db.add(conflicting)
    db.commit()

    with pytest.raises(
        HveeRegistryConflictError,
        match="metric version",
    ):
        resolve_metric_definition(
            db,
            WER_METRIC,
        )


def test_resolve_evaluator_version_is_idempotent(
    db: Session,
):
    first = resolve_evaluator_version(
        db,
        WER_EVALUATOR,
    )
    second = resolve_evaluator_version(
        db,
        WER_EVALUATOR,
    )

    assert first.id is not None
    assert second.id == first.id

    assert (
        db.query(HveeEvaluatorVersion)
        .filter(
            HveeEvaluatorVersion.key
            == WER_EVALUATOR.key,
            HveeEvaluatorVersion.version
            == WER_EVALUATOR.version,
        )
        .count()
        == 1
    )


def test_evaluator_version_conflict_is_rejected(
    db: Session,
):
    conflicting = HveeEvaluatorVersion(
        key=WER_EVALUATOR.key,
        version=WER_EVALUATOR.version,
        evaluation_type="asr",
        description="Different implementation semantics.",
    )

    db.add(conflicting)
    db.commit()

    with pytest.raises(
        HveeRegistryConflictError,
        match="evaluator version",
    ):
        resolve_evaluator_version(
            db,
            WER_EVALUATOR,
        )


def test_asr_registry_resolves_four_versioned_records(
    db: Session,
):
    registry = resolve_asr_text_error_registry(
        db
    )

    assert registry.wer_metric.id is not None
    assert registry.wer_evaluator.id is not None
    assert registry.cer_metric.id is not None
    assert registry.cer_evaluator.id is not None

    assert (
        db.query(HveeMetricDefinition).count()
        == 2
    )
    assert (
        db.query(HveeEvaluatorVersion).count()
        == 2
    )


def test_asr_registry_is_idempotent(
    db: Session,
):
    first = resolve_asr_text_error_registry(
        db
    )
    second = resolve_asr_text_error_registry(
        db
    )

    assert second.wer_metric.id == first.wer_metric.id
    assert (
        second.wer_evaluator.id
        == first.wer_evaluator.id
    )
    assert second.cer_metric.id == first.cer_metric.id
    assert (
        second.cer_evaluator.id
        == first.cer_evaluator.id
    )

    assert (
        db.query(HveeMetricDefinition).count()
        == 2
    )
    assert (
        db.query(HveeEvaluatorVersion).count()
        == 2
    )

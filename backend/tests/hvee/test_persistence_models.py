import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import Base
from app.hvee_models import (
    HveeEvaluatorVersion,
    HveeMetricDefinition,
)


@pytest.fixture()
def db() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
    )

    HveeMetricDefinition.__table__.create(engine)
    HveeEvaluatorVersion.__table__.create(engine)

    with Session(engine) as session:
        yield session

    engine.dispose()


def test_hvee_tables_share_application_metadata():
    assert (
        "hvee_metric_definitions"
        in Base.metadata.tables
    )
    assert (
        "hvee_evaluator_versions"
        in Base.metadata.tables
    )


def test_metric_definition_persists_versioned_identity(
    db: Session,
):
    metric = HveeMetricDefinition(
        key="asr.wer",
        version="1.0.0",
        evaluation_type="asr",
        value_type="number",
        direction="lower_is_better",
        unit="ratio",
        description="Word error rate.",
    )

    db.add(metric)
    db.commit()

    persisted = db.scalar(
        select(HveeMetricDefinition).where(
            HveeMetricDefinition.key == "asr.wer",
            HveeMetricDefinition.version == "1.0.0",
        )
    )

    assert persisted is not None
    assert persisted.evaluation_type == "asr"
    assert persisted.value_type == "number"
    assert persisted.direction == "lower_is_better"


def test_metric_definition_identity_is_unique(
    db: Session,
):
    db.add_all(
        [
            HveeMetricDefinition(
                key="asr.wer",
                version="1.0.0",
                evaluation_type="asr",
                value_type="number",
                direction="lower_is_better",
                description="Word error rate.",
            ),
            HveeMetricDefinition(
                key="asr.wer",
                version="1.0.0",
                evaluation_type="asr",
                value_type="number",
                direction="lower_is_better",
                description="Duplicate word error rate.",
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("value_type", "vector"),
        ("direction", "sometimes_better"),
    ],
)
def test_metric_definition_rejects_invalid_enum_values(
    db: Session,
    field_name: str,
    invalid_value: str,
):
    values = {
        "key": "asr.wer",
        "version": "1.0.0",
        "evaluation_type": "asr",
        "value_type": "number",
        "direction": "lower_is_better",
        "description": "Word error rate.",
    }
    values[field_name] = invalid_value

    db.add(
        HveeMetricDefinition(**values)
    )

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_evaluator_version_persists_independent_identity(
    db: Session,
):
    evaluator = HveeEvaluatorVersion(
        key="hetren.asr.wer",
        version="1.0.0",
        evaluation_type="asr",
        description=(
            "Deterministic ASR word error evaluator."
        ),
    )

    db.add(evaluator)
    db.commit()

    persisted = db.scalar(
        select(HveeEvaluatorVersion).where(
            HveeEvaluatorVersion.key
            == "hetren.asr.wer",
            HveeEvaluatorVersion.version
            == "1.0.0",
        )
    )

    assert persisted is not None
    assert persisted.evaluation_type == "asr"


def test_evaluator_version_identity_is_unique(
    db: Session,
):
    db.add_all(
        [
            HveeEvaluatorVersion(
                key="hetren.asr.wer",
                version="1.0.0",
                evaluation_type="asr",
                description="First.",
            ),
            HveeEvaluatorVersion(
                key="hetren.asr.wer",
                version="1.0.0",
                evaluation_type="asr",
                description="Duplicate.",
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_metric_and_evaluator_identities_are_independent(
    db: Session,
):
    metric = HveeMetricDefinition(
        key="asr.wer",
        version="1.0.0",
        evaluation_type="asr",
        value_type="number",
        direction="lower_is_better",
        description="Word error rate.",
    )

    evaluator = HveeEvaluatorVersion(
        key="hetren.asr.wer",
        version="1.0.0",
        evaluation_type="asr",
        description="WER evaluator.",
    )

    db.add_all([metric, evaluator])
    db.commit()

    assert metric.id is not None
    assert evaluator.id is not None
    assert metric.key != evaluator.key

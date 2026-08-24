from dataclasses import replace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models as _app_models  # noqa: F401
from app.database import Base
from app.hvee_asr_registry import (
    resolve_asr_reliability_profile_registry,
)
from app.hvee_models import (
    HveeEvaluatorVersion,
    HveeMetricDefinition,
)
from hvee.packs.asr import (
    ASR_RELIABILITY_PROFILE_V1,
    ASR_RELIABILITY_PROFILE_V1_SHA256,
    MATCHED_CONTROL_RELIABILITY_EVALUATOR,
    MATCHED_CONTROL_WER_ROBUSTNESS_DIFFERENTIAL_METRIC,
    ASRReliabilityProfileError,
)


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        yield session

    engine.dispose()


def test_profile_registry_resolves_all_unique_identities(db: Session):
    registry = resolve_asr_reliability_profile_registry(db)

    assert registry.profile_key == ASR_RELIABILITY_PROFILE_V1.key
    assert registry.profile_version == ASR_RELIABILITY_PROFILE_V1.version
    assert registry.profile_sha256 == ASR_RELIABILITY_PROFILE_V1_SHA256
    assert len(registry.metric_definitions) == 15
    assert len(registry.evaluator_versions) == 8
    assert all(value.id is not None for value in registry.metric_definitions)
    assert all(value.id is not None for value in registry.evaluator_versions)
    assert db.query(HveeMetricDefinition).count() == 15
    assert db.query(HveeEvaluatorVersion).count() == 8


def test_profile_registry_is_idempotent(db: Session):
    first = resolve_asr_reliability_profile_registry(db)
    second = resolve_asr_reliability_profile_registry(db)

    assert tuple(value.id for value in second.metric_definitions) == tuple(
        value.id
        for value in first.metric_definitions
    )
    assert tuple(value.id for value in second.evaluator_versions) == tuple(
        value.id
        for value in first.evaluator_versions
    )
    assert db.query(HveeMetricDefinition).count() == 15
    assert db.query(HveeEvaluatorVersion).count() == 8


def test_profile_registry_lookup_uses_exact_versioned_identity(db: Session):
    registry = resolve_asr_reliability_profile_registry(db)

    metric = registry.metric_by_identity(
        key=(
            MATCHED_CONTROL_WER_ROBUSTNESS_DIFFERENTIAL_METRIC.key
        ),
        version=(
            MATCHED_CONTROL_WER_ROBUSTNESS_DIFFERENTIAL_METRIC.version
        ),
    )
    evaluator = registry.evaluator_by_identity(
        key=MATCHED_CONTROL_RELIABILITY_EVALUATOR.key,
        version=MATCHED_CONTROL_RELIABILITY_EVALUATOR.version,
    )

    assert metric.key == (
        MATCHED_CONTROL_WER_ROBUSTNESS_DIFFERENTIAL_METRIC.key
    )
    assert evaluator.key == MATCHED_CONTROL_RELIABILITY_EVALUATOR.key


def test_profile_registry_lookup_rejects_unknown_identity(db: Session):
    registry = resolve_asr_reliability_profile_registry(db)

    with pytest.raises(KeyError, match="metric identity"):
        registry.metric_by_identity(
            key="asr.unknown",
            version="1.0.0",
        )

    with pytest.raises(KeyError, match="evaluator identity"):
        registry.evaluator_by_identity(
            key="hetren.asr.unknown",
            version="1.0.0",
        )


def test_changed_profile_is_rejected_before_registry_writes(db: Session):
    changed = replace(
        ASR_RELIABILITY_PROFILE_V1,
        version="1.0.1",
    )

    with pytest.raises(
        ASRReliabilityProfileError,
        match="unsupported or changed",
    ):
        resolve_asr_reliability_profile_registry(
            db,
            profile=changed,
        )

    assert db.query(HveeMetricDefinition).count() == 0
    assert db.query(HveeEvaluatorVersion).count() == 0


def test_registry_resolver_does_not_call_commit(
    db: Session,
    monkeypatch,
):
    def reject_commit():
        raise AssertionError("registry resolver must not commit")

    monkeypatch.setattr(db, "commit", reject_commit)

    registry = resolve_asr_reliability_profile_registry(db)

    assert len(registry.metric_definitions) == 15
    assert len(registry.evaluator_versions) == 8

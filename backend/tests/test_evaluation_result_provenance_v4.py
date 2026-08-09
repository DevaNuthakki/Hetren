from collections.abc import Generator
from copy import deepcopy

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from app.evaluation_provenance import (
    EVALUATION_RESULT_PROVENANCE_OBSERVATION_EVIDENCE_SCHEMA_VERSION,
    calculate_manifest_sha256,
    stage_evaluation_result_provenance,
    stage_evaluation_run_with_manifest,
    verify_evaluation_result_observation_binding,
    verify_evaluation_result_provenance,
)
from app.evaluation_service import (
    persist_evaluation_result,
)
from app.hvee_models import (
    HveeMetricDefinition,
    HveeObservation,
)
from app.hvee_observation_evidence import (
    HveeObservationEvidenceError,
)
from hvee.core.observation_evidence import (
    calculate_observation_evidence_sha256,
)
from hvee.packs.asr import (
    REFERENCE_NUMERIC_TOKEN_COUNT_METRIC,
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


def create_resources(
    db: Session,
) -> tuple[
    models.EvaluationRun,
    models.Dataset,
    models.TestCase,
]:
    project = models.Project(
        name="V4 provenance project",
    )
    db.add(project)
    db.flush()

    dataset = models.Dataset(
        project_id=project.id,
        name="V4 dataset",
    )
    db.add(dataset)
    db.flush()

    test_case = models.TestCase(
        dataset_id=dataset.id,
        title="V4 case",
        reference_transcript=(
            "invoice 48217 total 1,250"
        ),
    )
    db.add(test_case)
    db.flush()

    run = stage_evaluation_run_with_manifest(
        db,
        project_id=project.id,
        run_name="V4 run",
        model_name="test-model",
    )

    return run, dataset, test_case


def persist_result(
    db: Session,
    *,
    run: models.EvaluationRun,
    test_case: models.TestCase,
    generated_text: str = (
        "invoice 48271 total 1,250"
    ),
) -> models.EvaluationResult:
    return persist_evaluation_result(
        db=db,
        db_run=run,
        db_test_case=test_case,
        generated_text=generated_text,
        execution_mode="uploaded_transcript",
    )


def test_new_provenance_is_v4_and_binds_27_observations(
    db: Session,
):
    run, _dataset, test_case = (
        create_resources(db)
    )

    result = persist_result(
        db,
        run=run,
        test_case=test_case,
    )

    provenance = result.provenance

    assert provenance is not None
    assert provenance.schema_version == (
        EVALUATION_RESULT_PROVENANCE_OBSERVATION_EVIDENCE_SCHEMA_VERSION
    )

    bundle = provenance.provenance_payload[
        "hvee_observations"
    ]

    assert bundle["count"] == 27
    assert verify_evaluation_result_provenance(
        provenance
    )
    assert verify_evaluation_result_observation_binding(
        db,
        provenance,
    )


def test_live_binding_detects_persisted_observation_change(
    db: Session,
):
    run, _dataset, test_case = (
        create_resources(db)
    )

    result = persist_result(
        db,
        run=run,
        test_case=test_case,
    )

    provenance = result.provenance
    assert provenance is not None

    metric = (
        db.query(HveeMetricDefinition)
        .filter(
            HveeMetricDefinition.key
            == WER_METRIC.key,
        )
        .one()
    )

    observation = (
        db.query(HveeObservation)
        .filter(
            HveeObservation.evaluation_run_id
            == run.id,
            HveeObservation.test_case_id
            == test_case.id,
            HveeObservation.metric_definition_id
            == metric.id,
        )
        .one()
    )

    observation.number_value = 0.987654
    db.flush()

    # Stored evidence remains internally valid.
    assert verify_evaluation_result_provenance(
        provenance
    )

    # But it no longer matches the live observation rows.
    assert not (
        verify_evaluation_result_observation_binding(
            db,
            provenance,
        )
    )


def test_rewritten_bundle_can_be_self_consistent_but_fails_live_binding(
    db: Session,
):
    run, _dataset, test_case = (
        create_resources(db)
    )

    result = persist_result(
        db,
        run=run,
        test_case=test_case,
    )

    provenance = result.provenance
    assert provenance is not None

    payload = deepcopy(
        provenance.provenance_payload
    )
    bundle = payload[
        "hvee_observations"
    ]

    target = next(
        observation
        for observation in bundle[
            "observations"
        ]
        if observation["metric"]["key"]
        == REFERENCE_NUMERIC_TOKEN_COUNT_METRIC.key
    )

    target["value"] = target["value"] + 1

    body = {
        "schema_version": (
            bundle["schema_version"]
        ),
        "count": bundle["count"],
        "observations": (
            bundle["observations"]
        ),
    }

    bundle["sha256"] = (
        calculate_observation_evidence_sha256(
            body
        )
    )

    provenance.provenance_payload = payload
    provenance.provenance_sha256 = (
        calculate_manifest_sha256(payload)
    )

    # Internal hashes alone cannot provide authenticity against a
    # privileged actor able to rewrite the whole stored evidence.
    assert verify_evaluation_result_provenance(
        provenance
    )

    # Independent live observation reconstruction detects the change.
    assert not (
        verify_evaluation_result_observation_binding(
            db,
            provenance,
        )
    )


def test_v4_rejects_bundle_copied_from_another_result(
    db: Session,
):
    run, dataset, first_case = (
        create_resources(db)
    )

    first_result = persist_result(
        db,
        run=run,
        test_case=first_case,
    )

    second_case = models.TestCase(
        dataset_id=dataset.id,
        title="Second V4 case",
        reference_transcript="order 900",
    )
    db.add(second_case)
    db.commit()

    second_result = persist_result(
        db,
        run=run,
        test_case=second_case,
        generated_text="order 901",
    )

    first_provenance = first_result.provenance
    second_provenance = second_result.provenance

    assert first_provenance is not None
    assert second_provenance is not None

    payload = deepcopy(
        first_provenance.provenance_payload
    )

    payload["hvee_observations"] = deepcopy(
        second_provenance.provenance_payload[
            "hvee_observations"
        ]
    )

    first_provenance.provenance_payload = (
        payload
    )
    first_provenance.provenance_sha256 = (
        calculate_manifest_sha256(payload)
    )

    assert not verify_evaluation_result_provenance(
        first_provenance
    )


def test_provenance_staging_rejects_result_without_observations(
    db: Session,
):
    run, _dataset, test_case = (
        create_resources(db)
    )

    result = models.EvaluationResult(
        run_id=run.id,
        test_case_id=test_case.id,
        generated_transcript="manual bypass",
        wer=1.0,
        cer=1.0,
        quality_label="regression",
        error_summary="manual",
    )

    db.add(result)
    db.flush()

    with pytest.raises(
        HveeObservationEvidenceError,
        match="no test-case observations",
    ):
        stage_evaluation_result_provenance(
            db,
            result=result,
            evaluation_run=run,
            test_case=test_case,
            execution_mode="uploaded_transcript",
        )


def test_non_fixture_cannot_disable_observation_binding(
    db: Session,
):
    run, _dataset, test_case = (
        create_resources(db)
    )

    result = models.EvaluationResult(
        run_id=run.id,
        test_case_id=test_case.id,
        generated_transcript="manual bypass",
        wer=1.0,
        cer=1.0,
        quality_label="regression",
        error_summary="manual",
    )
    db.add(result)
    db.flush()

    with pytest.raises(
        ValueError,
        match=(
            "may only be omitted for explicit "
            "seed fixtures"
        ),
    ):
        stage_evaluation_result_provenance(
            db,
            result=result,
            evaluation_run=run,
            test_case=test_case,
            execution_mode="uploaded_transcript",
            bind_observation_evidence=False,
        )

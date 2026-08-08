from __future__ import annotations

import copy
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from app.evaluation_provenance import (
    calculate_manifest_sha256,
    stage_evaluation_run_with_manifest,
    verify_evaluation_result_provenance,
)
from app.evaluation_service import (
    persist_evaluation_result,
)
from app.hvee_decision_service import (
    HveeDecisionConflictError,
    HveeDecisionPersistenceError,
    stage_asr_hvee_decision,
)
from app.hvee_models import (
    HveeDecision,
    HveeMetricDefinition,
    HveeObservation,
)
from hvee.packs.asr.decision_policy import (
    ASRRuleDisposition,
    ASRTestCaseDecisionPolicyV1,
)
from hvee.packs.asr.normalized_evaluation import (
    NORMALIZED_WER_METRIC,
)


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)

    factory = sessionmaker(
        bind=engine
    )
    session = factory()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _create_result(
    db: Session,
) -> models.EvaluationResult:
    project = models.Project(
        name="HVEE decision service project",
    )
    db.add(project)
    db.flush()

    dataset = models.Dataset(
        project_id=project.id,
        name="HVEE decision service dataset",
    )
    db.add(dataset)
    db.flush()

    test_case = models.TestCase(
        dataset_id=dataset.id,
        title="HVEE decision service case",
        reference_transcript=(
            "the quick brown fox"
        ),
    )
    db.add(test_case)
    db.flush()

    run = stage_evaluation_run_with_manifest(
        db,
        project_id=project.id,
        run_name="HVEE decision service run",
        model_name="test-model",
    )

    return persist_evaluation_result(
        db=db,
        db_run=run,
        db_test_case=test_case,
        generated_text="the quick fox",
        execution_mode="uploaded_transcript",
    )


def _passing_policy(
) -> ASRTestCaseDecisionPolicyV1:
    return ASRTestCaseDecisionPolicyV1(
        max_normalized_wer=0.30,
        missing_output=(
            ASRRuleDisposition.CRITICAL
        ),
    )


def test_stages_decision_from_verified_provenance(
    db: Session,
):
    result = _create_result(db)

    provenance = result.provenance
    assert provenance is not None

    decision = stage_asr_hvee_decision(
        db,
        result_provenance_id=provenance.id,
        policy=_passing_policy(),
    )

    assert decision.id is not None
    assert decision.verdict == "pass"
    assert decision.reason == "claim_supported"
    assert (
        decision.result_provenance_id
        == provenance.id
    )
    assert (
        decision.provenance_sha256
        == provenance.provenance_sha256
    )
    assert (
        decision.decision_payload[
            "decision"
        ]["verdict"]
        == decision.verdict
    )
    assert (
        decision.decision_payload[
            "policy"
        ]["sha256"]
        == decision.policy_sha256
    )
    assert (
        decision.decision_payload[
            "evidence"
        ]["observation_evidence_sha256"]
        == decision.observation_evidence_sha256
    )


def test_same_policy_and_evidence_is_idempotent(
    db: Session,
):
    result = _create_result(db)
    provenance = result.provenance
    assert provenance is not None

    first = stage_asr_hvee_decision(
        db,
        result_provenance_id=provenance.id,
        policy=_passing_policy(),
    )

    second = stage_asr_hvee_decision(
        db,
        result_provenance_id=provenance.id,
        policy=_passing_policy(),
    )

    assert first.id == second.id
    assert (
        db.query(HveeDecision).count()
        == 1
    )


def test_different_policy_snapshot_creates_separate_decision(
    db: Session,
):
    result = _create_result(db)
    provenance = result.provenance
    assert provenance is not None

    passing = stage_asr_hvee_decision(
        db,
        result_provenance_id=provenance.id,
        policy=_passing_policy(),
    )

    strict = stage_asr_hvee_decision(
        db,
        result_provenance_id=provenance.id,
        policy=(
            ASRTestCaseDecisionPolicyV1(
                max_normalized_wer=0.10,
                missing_output=(
                    ASRRuleDisposition.CRITICAL
                ),
            )
        ),
    )

    assert passing.id != strict.id
    assert passing.verdict == "pass"
    assert strict.verdict == "fail"
    assert (
        passing.policy_sha256
        != strict.policy_sha256
    )
    assert (
        db.query(HveeDecision).count()
        == 2
    )


def test_rejects_non_current_provenance_schema(
    db: Session,
):
    result = _create_result(db)
    provenance = result.provenance
    assert provenance is not None

    provenance.schema_version = 3
    db.flush()

    with pytest.raises(
        HveeDecisionPersistenceError,
        match="current observation-bound provenance",
    ):
        stage_asr_hvee_decision(
            db,
            result_provenance_id=provenance.id,
            policy=_passing_policy(),
        )


def test_rejects_tampered_provenance_payload(
    db: Session,
):
    result = _create_result(db)
    provenance = result.provenance
    assert provenance is not None

    payload = copy.deepcopy(
        provenance.provenance_payload
    )
    payload["evaluation_type"] = "tampered"

    provenance.provenance_payload = payload
    db.flush()

    with pytest.raises(
        HveeDecisionPersistenceError,
        match="failed verification",
    ):
        stage_asr_hvee_decision(
            db,
            result_provenance_id=provenance.id,
            policy=_passing_policy(),
        )


def test_rejects_relational_result_identity_rebinding(
    db: Session,
):
    result = _create_result(db)
    provenance = result.provenance
    assert provenance is not None

    payload = copy.deepcopy(
        provenance.provenance_payload
    )
    payload["result"]["id"] = (
        result.id + 1000
    )

    provenance.provenance_payload = payload
    provenance.provenance_sha256 = (
        calculate_manifest_sha256(
            payload
        )
    )
    db.flush()

    # The generic provenance verifier checks the self-contained
    # evidence contract. The decision service additionally binds that
    # payload to the relational parent row.
    assert verify_evaluation_result_provenance(
        provenance
    )

    with pytest.raises(
        HveeDecisionPersistenceError,
        match="relational result identity",
    ):
        stage_asr_hvee_decision(
            db,
            result_provenance_id=provenance.id,
            policy=_passing_policy(),
        )


def test_rejects_observation_drift_after_provenance_binding(
    db: Session,
):
    result = _create_result(db)
    provenance = result.provenance
    assert provenance is not None

    observation = (
        db.query(HveeObservation)
        .join(
            HveeMetricDefinition,
            HveeMetricDefinition.id
            == HveeObservation.metric_definition_id,
        )
        .filter(
            HveeMetricDefinition.key
            == NORMALIZED_WER_METRIC.key
        )
        .one()
    )

    observation.number_value = 0.99
    db.flush()

    with pytest.raises(
        HveeDecisionPersistenceError,
        match="no longer match",
    ):
        stage_asr_hvee_decision(
            db,
            result_provenance_id=provenance.id,
            policy=_passing_policy(),
        )


def test_existing_decision_tampering_becomes_conflict(
    db: Session,
):
    result = _create_result(db)
    provenance = result.provenance
    assert provenance is not None

    decision = stage_asr_hvee_decision(
        db,
        result_provenance_id=provenance.id,
        policy=_passing_policy(),
    )

    decision.verdict = "fail"
    db.flush()

    with pytest.raises(
        HveeDecisionConflictError,
        match="does not match",
    ):
        stage_asr_hvee_decision(
            db,
            result_provenance_id=provenance.id,
            policy=_passing_policy(),
        )


def test_missing_provenance_is_rejected(
    db: Session,
):
    with pytest.raises(
        HveeDecisionPersistenceError,
        match="was not found",
    ):
        stage_asr_hvee_decision(
            db,
            result_provenance_id=2_147_483_647,
            policy=_passing_policy(),
        )

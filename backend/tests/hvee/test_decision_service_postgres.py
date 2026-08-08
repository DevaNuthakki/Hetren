from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.evaluation_provenance import (
    stage_evaluation_run_with_manifest,
)
from app.evaluation_service import (
    persist_evaluation_result,
)
from app.hvee_decision_service import (
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


def _create_result(
    db: Session,
    *,
    suffix: str,
) -> models.EvaluationResult:
    project = models.Project(
        name=f"HVEE decision PostgreSQL project {suffix}",
    )
    db.add(project)
    db.flush()

    dataset = models.Dataset(
        project_id=project.id,
        name=f"HVEE decision PostgreSQL dataset {suffix}",
    )
    db.add(dataset)
    db.flush()

    test_case = models.TestCase(
        dataset_id=dataset.id,
        title=f"HVEE decision PostgreSQL case {suffix}",
        reference_transcript="the quick brown fox",
    )
    db.add(test_case)
    db.flush()

    run = stage_evaluation_run_with_manifest(
        db,
        project_id=project.id,
        run_name=f"HVEE decision PostgreSQL run {suffix}",
        model_name="postgres-test-model",
    )

    return persist_evaluation_result(
        db=db,
        db_run=run,
        db_test_case=test_case,
        generated_text="the quick fox",
        execution_mode="uploaded_transcript",
    )


def _policy(
    *,
    max_wer: float = 0.30,
) -> ASRTestCaseDecisionPolicyV1:
    return ASRTestCaseDecisionPolicyV1(
        max_normalized_wer=max_wer,
        missing_output=(
            ASRRuleDisposition.CRITICAL
        ),
    )


def test_postgres_stages_verified_hvee_decision(
    postgres_session: Session,
):
    result = _create_result(
        postgres_session,
        suffix=uuid4().hex,
    )

    provenance = result.provenance
    assert provenance is not None

    decision = stage_asr_hvee_decision(
        postgres_session,
        result_provenance_id=provenance.id,
        policy=_policy(),
    )

    postgres_session.flush()
    postgres_session.refresh(decision)

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
        == "pass"
    )

    assert (
        decision.decision_payload[
            "policy"
        ]["sha256"]
        == decision.policy_sha256
    )

    assert decision.created_at is not None
    assert decision.created_at.tzinfo is not None
    assert (
        decision.created_at.utcoffset()
        is not None
    )


def test_postgres_same_policy_is_idempotent(
    postgres_session: Session,
):
    result = _create_result(
        postgres_session,
        suffix=uuid4().hex,
    )

    provenance = result.provenance
    assert provenance is not None

    first = stage_asr_hvee_decision(
        postgres_session,
        result_provenance_id=provenance.id,
        policy=_policy(),
    )

    second = stage_asr_hvee_decision(
        postgres_session,
        result_provenance_id=provenance.id,
        policy=_policy(),
    )

    assert first.id == second.id

    count = postgres_session.scalar(
        select(func.count())
        .select_from(HveeDecision)
        .where(
            HveeDecision.result_provenance_id
            == provenance.id
        )
    )

    assert count == 1


def test_postgres_different_policy_snapshot_creates_new_decision(
    postgres_session: Session,
):
    result = _create_result(
        postgres_session,
        suffix=uuid4().hex,
    )

    provenance = result.provenance
    assert provenance is not None

    passing = stage_asr_hvee_decision(
        postgres_session,
        result_provenance_id=provenance.id,
        policy=_policy(
            max_wer=0.30,
        ),
    )

    failing = stage_asr_hvee_decision(
        postgres_session,
        result_provenance_id=provenance.id,
        policy=_policy(
            max_wer=0.10,
        ),
    )

    assert passing.id != failing.id
    assert passing.verdict == "pass"
    assert failing.verdict == "fail"

    assert (
        passing.policy_sha256
        != failing.policy_sha256
    )

    count = postgres_session.scalar(
        select(func.count())
        .select_from(HveeDecision)
        .where(
            HveeDecision.result_provenance_id
            == provenance.id
        )
    )

    assert count == 2


def test_postgres_rejects_observation_drift(
    postgres_session: Session,
):
    result = _create_result(
        postgres_session,
        suffix=uuid4().hex,
    )

    provenance = result.provenance
    assert provenance is not None

    observation = postgres_session.scalar(
        select(HveeObservation)
        .join(
            HveeMetricDefinition,
            HveeMetricDefinition.id
            == HveeObservation.metric_definition_id,
        )
        .where(
            HveeObservation.evaluation_run_id
            == result.run_id,
            HveeObservation.test_case_id
            == result.test_case_id,
            HveeMetricDefinition.key
            == NORMALIZED_WER_METRIC.key,
        )
    )

    assert observation is not None

    observation.number_value = 0.99
    postgres_session.flush()

    with pytest.raises(
        HveeDecisionPersistenceError,
        match="no longer match",
    ):
        stage_asr_hvee_decision(
            postgres_session,
            result_provenance_id=provenance.id,
            policy=_policy(),
        )

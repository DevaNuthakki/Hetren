from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app import models
from app.asr_semantic_evidence_service import (
    build_asr_semantic_evidence_read,
)
from app.critical_terminology_vocabulary_service import (
    stage_critical_terminology_vocabulary_version,
)
from app.evaluation_provenance import (
    resolve_evaluation_run_critical_terminology_profile,
    stage_evaluation_run_with_manifest,
    verify_evaluation_result_observation_binding,
    verify_evaluation_result_provenance,
    verify_evaluation_run_manifest,
)
from app.evaluation_service import persist_evaluation_result
from app.hvee_models import (
    HveeMetricDefinition,
    HveeObservation,
)
from hvee.packs.asr import (
    CRITICAL_IDENTIFIER_METRICS,
    CRITICAL_NUMBER_METRICS,
    CRITICAL_TERMINOLOGY_METRICS,
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


REFERENCE_TEXT = (
    "Transfer 250 dollars using confirmation code AB-123 "
    "and administer Cardiovex today"
)


def _terminology_terms() -> list[dict[str, object]]:
    return [
        {
            "term_key": "cardiovex",
            "canonical_text": "Cardiovex",
            "accepted_surfaces": [
                "Cardiovex",
            ],
        },
        {
            "term_key": "neurodex",
            "canonical_text": "Neurodex",
            "accepted_surfaces": [
                "Neurodex",
            ],
        },
    ]


def test_postgres_autoflush_false_run_manifest_is_visible_before_result_persistence(
    postgres_session: Session,
) -> None:
    """
    Reproduce the production SessionLocal autoflush=False contract.

    A newly staged run must expose its sealed Critical Terminology
    manifest immediately inside the caller-owned transaction. Otherwise
    result persistence can incorrectly skip the configured terminology
    evaluator and commit a result whose manifest promises terminology
    evidence that was never staged.
    """

    db = postgres_session
    db.autoflush = False

    assert db.autoflush is False

    suffix = uuid4().hex

    user = models.User(
        email=f"terminology-flush-{suffix}@example.com",
    )
    organization = models.Organization(
        name=f"Terminology flush organization {suffix}",
    )

    db.add_all(
        [
            user,
            organization,
        ]
    )
    db.flush()

    project = models.Project(
        organization_id=organization.id,
        name=f"Terminology flush project {suffix}",
    )
    db.add(project)
    db.flush()

    dataset = models.Dataset(
        project_id=project.id,
        name="Terminology manifest flush validation",
    )
    db.add(dataset)
    db.flush()

    test_case = models.TestCase(
        dataset_id=dataset.id,
        title="Configured terminology persistence",
        reference_transcript=REFERENCE_TEXT,
    )
    db.add(test_case)
    db.flush()

    vocabulary = (
        stage_critical_terminology_vocabulary_version(
            db,
            project_id=project.id,
            created_by_user_id=user.id,
            terms=_terminology_terms(),
        )
    )

    run = stage_evaluation_run_with_manifest(
        db,
        project_id=project.id,
        run_name="Configured terminology autoflush validation",
        model_name="test-model",
    )

    # This query is the exact production-sensitive boundary. With
    # autoflush disabled, the manifest must already have been flushed by
    # stage_evaluation_run_with_manifest().
    manifest = (
        db.query(models.EvaluationRunManifest)
        .filter(
            models.EvaluationRunManifest.run_id == run.id
        )
        .one()
    )

    assert verify_evaluation_run_manifest(
        manifest
    )
    assert (
        manifest.manifest_payload[
            "critical_terminology"
        ]["status"]
        == "configured"
    )
    assert (
        manifest.manifest_payload[
            "critical_terminology"
        ]["revision"]
        == vocabulary.revision
    )

    profile = (
        resolve_evaluation_run_critical_terminology_profile(
            db,
            evaluation_run=run,
        )
    )

    assert profile is not None
    assert profile.key == vocabulary.profile_key
    assert profile.version == vocabulary.profile_version
    assert len(profile.terms) == 2

    result = persist_evaluation_result(
        db=db,
        db_run=run,
        db_test_case=test_case,
        generated_text=REFERENCE_TEXT,
        execution_mode="uploaded_transcript",
    )

    persisted_observations = (
        db.query(HveeObservation)
        .filter(
            HveeObservation.evaluation_run_id == run.id,
            HveeObservation.test_case_id == test_case.id,
        )
        .all()
    )

    # Existing ASR evidence set = 38.
    # Configured Critical Terminology adds exactly 11.
    assert len(persisted_observations) == 49

    semantic_rows = (
        db.query(
            HveeMetricDefinition.key,
            HveeObservation.status,
        )
        .join(
            HveeObservation,
            HveeObservation.metric_definition_id
            == HveeMetricDefinition.id,
        )
        .filter(
            HveeObservation.evaluation_run_id == run.id,
            HveeObservation.test_case_id == test_case.id,
            HveeMetricDefinition.key.like(
                "asr.critical-%"
            ),
        )
        .all()
    )

    semantic_keys = {
        key
        for key, _status in semantic_rows
    }

    number_keys = {
        metric.key
        for metric in CRITICAL_NUMBER_METRICS
    }
    identifier_keys = {
        metric.key
        for metric in CRITICAL_IDENTIFIER_METRICS
    }
    terminology_keys = {
        metric.key
        for metric in CRITICAL_TERMINOLOGY_METRICS
    }

    assert number_keys.issubset(
        semantic_keys
    )
    assert identifier_keys.issubset(
        semantic_keys
    )
    assert terminology_keys.issubset(
        semantic_keys
    )

    assert len(number_keys) == 10
    assert len(identifier_keys) == 11
    assert len(terminology_keys) == 11

    terminology_observations = [
        key
        for key, _status in semantic_rows
        if key in terminology_keys
    ]

    assert len(terminology_observations) == 11

    assert result.provenance is not None
    assert verify_evaluation_result_provenance(
        result.provenance
    )
    assert verify_evaluation_result_observation_binding(
        db,
        result.provenance,
    )

    evidence = build_asr_semantic_evidence_read(
        db,
        result=result,
        evaluation_run=run,
    )

    assert evidence["result_id"] == result.id

    assert (
        evidence["critical_number"]["status"]
        == "available"
    )
    assert len(
        evidence["critical_number"]["observations"]
    ) == 10

    assert (
        evidence["critical_identifier"]["status"]
        == "available"
    )
    assert len(
        evidence["critical_identifier"]["observations"]
    ) == 11

    assert (
        evidence["critical_terminology"]["status"]
        == "available"
    )
    assert len(
        evidence["critical_terminology"]["observations"]
    ) == 11

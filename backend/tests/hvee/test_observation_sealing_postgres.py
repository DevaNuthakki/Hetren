from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app import models
from app.evaluation_provenance import (
    stage_evaluation_run_with_manifest,
)
from app.evaluation_service import (
    persist_evaluation_result,
)
from app.hvee_asr_observation_service import (
    stage_asr_text_error_observations,
)
from app.hvee_models import HveeObservation
from app.hvee_observation_service import (
    HveeObservationPersistenceError,
)
from hvee.packs.asr.evaluation import (
    evaluate_transcript_pair,
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


def test_postgres_provenance_seals_test_case_observations(
    postgres_session: Session,
):
    suffix = uuid4().hex

    project = models.Project(
        name=f"HVEE sealing project {suffix}",
    )
    postgres_session.add(project)
    postgres_session.flush()

    dataset = models.Dataset(
        project_id=project.id,
        name=f"HVEE sealing dataset {suffix}",
    )
    postgres_session.add(dataset)
    postgres_session.flush()

    test_case = models.TestCase(
        dataset_id=dataset.id,
        title=f"HVEE sealing case {suffix}",
        reference_transcript="one two three",
    )
    postgres_session.add(test_case)
    postgres_session.flush()

    run = stage_evaluation_run_with_manifest(
        postgres_session,
        project_id=project.id,
        run_name=f"HVEE sealing run {suffix}",
        model_name="postgres-test-model",
    )

    result = persist_evaluation_result(
        db=postgres_session,
        db_run=run,
        db_test_case=test_case,
        generated_text="one two",
        execution_mode="uploaded_transcript",
    )

    assert result.provenance is not None

    count_before = (
        postgres_session.query(
            HveeObservation
        )
        .filter(
            HveeObservation.evaluation_run_id
            == run.id,
            HveeObservation.test_case_id
            == test_case.id,
        )
        .count()
    )

    evaluation = evaluate_transcript_pair(
        reference_text=(
            test_case.reference_transcript
        ),
        generated_text="one two",
    )

    with pytest.raises(
        HveeObservationPersistenceError,
        match="immutable after result provenance",
    ):
        stage_asr_text_error_observations(
            postgres_session,
            evaluation_run=run,
            test_case=test_case,
            evaluation=evaluation,
        )

    count_after = (
        postgres_session.query(
            HveeObservation
        )
        .filter(
            HveeObservation.evaluation_run_id
            == run.id,
            HveeObservation.test_case_id
            == test_case.id,
        )
        .count()
    )

    assert count_after == count_before

import os

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models


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


def test_postgres_schema_is_at_alembic_head(
    postgres_test_engine: Engine,
):
    alembic_config = Config("alembic.ini")
    migration_head = ScriptDirectory.from_config(
        alembic_config
    ).get_current_head()

    with postgres_test_engine.connect() as connection:
        database_revision = connection.scalar(
            text("SELECT version_num FROM alembic_version")
        )

    assert database_revision == migration_head

    required_tables = {
        "alembic_version",
        "projects",
        "datasets",
        "test_cases",
        "evaluation_runs",
        "evaluation_results",
        "run_comparisons",
        "debug_cases",
        "release_policies",
        "release_reports",
    }

    actual_tables = set(
        inspect(postgres_test_engine).get_table_names()
    )

    assert required_tables.issubset(actual_tables)


def test_postgres_returns_timezone_aware_timestamps(
    postgres_session: Session,
):
    project = models.Project(
        name="PostgreSQL timestamp test",
        description="Validates timezone-aware timestamps.",
    )

    postgres_session.add(project)
    postgres_session.flush()
    postgres_session.refresh(project)

    assert project.created_at is not None
    assert project.created_at.tzinfo is not None
    assert project.created_at.utcoffset() is not None


def test_postgres_enforces_foreign_keys(
    postgres_session: Session,
):
    invalid_dataset = models.Dataset(
        project_id=2_147_483_647,
        name="Invalid foreign-key dataset",
    )

    postgres_session.add(invalid_dataset)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


def test_postgres_enforces_one_release_report_per_comparison(
    postgres_session: Session,
):
    project = models.Project(
        name="Release-report uniqueness test",
    )
    postgres_session.add(project)
    postgres_session.flush()

    baseline_run = models.EvaluationRun(
        project_id=project.id,
        run_name="baseline",
        model_name="baseline-model",
        status="completed",
    )
    current_run = models.EvaluationRun(
        project_id=project.id,
        run_name="candidate",
        model_name="candidate-model",
        status="completed",
    )

    postgres_session.add_all(
        [baseline_run, current_run]
    )
    postgres_session.flush()

    comparison = models.RunComparison(
        baseline_run_id=baseline_run.id,
        current_run_id=current_run.id,
        comparison_status="no_significant_change",
    )

    postgres_session.add(comparison)
    postgres_session.flush()

    first_report = models.ReleaseReport(
        project_id=project.id,
        comparison_id=comparison.id,
        status="pass",
        severity="none",
        headline="Release passed",
        summary="No blocking regression detected.",
        recommendation="Proceed.",
        policy_snapshot={},
        checks=[],
    )

    postgres_session.add(first_report)
    postgres_session.flush()

    duplicate_report = models.ReleaseReport(
        project_id=project.id,
        comparison_id=comparison.id,
        status="pass",
        severity="none",
        headline="Duplicate report",
        summary="This record must be rejected.",
        recommendation="Do not persist.",
        policy_snapshot={},
        checks=[],
    )

    postgres_session.add(duplicate_report)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()

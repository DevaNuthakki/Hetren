import hashlib
import os
from datetime import UTC, datetime, timedelta

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
        "runner_registration_tokens",
        "runners",
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

def _test_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _create_test_project(
    postgres_session: Session,
    suffix: str,
) -> models.Project:
    project = models.Project(
        name=f"Runner project {suffix}",
    )
    postgres_session.add(project)
    postgres_session.flush()
    return project


def _create_test_registration_token(
    postgres_session: Session,
    project_id: int,
    suffix: str,
) -> models.RunnerRegistrationToken:
    created_at = datetime.now(UTC)

    token = models.RunnerRegistrationToken(
        project_id=project_id,
        label=f"Registration token {suffix}",
        token_hash=_test_digest(f"registration:{suffix}"),
        created_at=created_at,
        expires_at=created_at + timedelta(hours=1),
    )

    postgres_session.add(token)
    postgres_session.flush()
    return token


def _build_test_runner(
    project_id: int,
    registration_token_id: int,
    suffix: str,
    *,
    name: str | None = None,
    status: str = "active",
    revoked_at: datetime | None = None,
) -> models.Runner:
    return models.Runner(
        project_id=project_id,
        registration_token_id=registration_token_id,
        public_id=f"runner-{suffix}",
        name=name or f"Runner {suffix}",
        status=status,
        runner_version="0.1.0-test",
        capabilities=["asr"],
        system_info={"platform": "pytest"},
        credential_hash=_test_digest(f"credential:{suffix}"),
        revoked_at=revoked_at,
    )


def test_postgres_runner_defaults_and_timestamps(
    postgres_session: Session,
):
    project = _create_test_project(
        postgres_session,
        "defaults",
    )
    token = _create_test_registration_token(
        postgres_session,
        project.id,
        "defaults",
    )

    runner = models.Runner(
        project_id=project.id,
        registration_token_id=token.id,
        public_id="runner-defaults",
        name="Runner defaults",
        credential_hash=_test_digest("credential:defaults"),
    )

    postgres_session.add(runner)
    postgres_session.flush()
    postgres_session.refresh(runner)

    assert runner.status == "active"
    assert runner.capabilities == []
    assert runner.system_info == {}
    assert runner.last_seen_at is None
    assert runner.revoked_at is None

    assert runner.created_at.tzinfo is not None
    assert runner.created_at.utcoffset() is not None
    assert runner.updated_at.tzinfo is not None
    assert runner.updated_at.utcoffset() is not None

    assert token.created_at.tzinfo is not None
    assert token.expires_at.tzinfo is not None
    assert token.consumed_at is None
    assert token.revoked_at is None


def test_postgres_enforces_registration_token_expiry(
    postgres_session: Session,
):
    project = _create_test_project(
        postgres_session,
        "invalid-expiry",
    )
    created_at = datetime.now(UTC)

    token = models.RunnerRegistrationToken(
        project_id=project.id,
        label="Invalid expiry",
        token_hash=_test_digest("registration:invalid-expiry"),
        created_at=created_at,
        expires_at=created_at,
    )

    postgres_session.add(token)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


def test_postgres_enforces_registration_token_lifecycle(
    postgres_session: Session,
):
    project = _create_test_project(
        postgres_session,
        "invalid-lifecycle",
    )
    created_at = datetime.now(UTC)

    token = models.RunnerRegistrationToken(
        project_id=project.id,
        label="Invalid lifecycle",
        token_hash=_test_digest(
            "registration:invalid-lifecycle"
        ),
        created_at=created_at,
        expires_at=created_at + timedelta(hours=1),
        consumed_at=created_at,
        revoked_at=created_at,
    )

    postgres_session.add(token)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


def test_postgres_enforces_unique_registration_token_hash(
    postgres_session: Session,
):
    first_project = _create_test_project(
        postgres_session,
        "token-hash-first",
    )
    second_project = _create_test_project(
        postgres_session,
        "token-hash-second",
    )
    created_at = datetime.now(UTC)
    shared_hash = _test_digest("registration:shared")

    first_token = models.RunnerRegistrationToken(
        project_id=first_project.id,
        label="First token",
        token_hash=shared_hash,
        created_at=created_at,
        expires_at=created_at + timedelta(hours=1),
    )
    postgres_session.add(first_token)
    postgres_session.flush()

    duplicate_token = models.RunnerRegistrationToken(
        project_id=second_project.id,
        label="Duplicate token",
        token_hash=shared_hash,
        created_at=created_at,
        expires_at=created_at + timedelta(hours=1),
    )
    postgres_session.add(duplicate_token)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


def test_postgres_enforces_runner_token_project_match(
    postgres_session: Session,
):
    token_project = _create_test_project(
        postgres_session,
        "token-owner",
    )
    runner_project = _create_test_project(
        postgres_session,
        "runner-owner",
    )
    token = _create_test_registration_token(
        postgres_session,
        token_project.id,
        "cross-project",
    )

    runner = _build_test_runner(
        project_id=runner_project.id,
        registration_token_id=token.id,
        suffix="cross-project",
    )
    postgres_session.add(runner)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


def test_postgres_enforces_unique_runner_name_per_project(
    postgres_session: Session,
):
    project = _create_test_project(
        postgres_session,
        "unique-name",
    )
    first_token = _create_test_registration_token(
        postgres_session,
        project.id,
        "unique-name-first",
    )
    second_token = _create_test_registration_token(
        postgres_session,
        project.id,
        "unique-name-second",
    )

    first_runner = _build_test_runner(
        project_id=project.id,
        registration_token_id=first_token.id,
        suffix="unique-name-first",
        name="Shared runner name",
    )
    postgres_session.add(first_runner)
    postgres_session.flush()

    duplicate_runner = _build_test_runner(
        project_id=project.id,
        registration_token_id=second_token.id,
        suffix="unique-name-second",
        name="Shared runner name",
    )
    postgres_session.add(duplicate_runner)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


def test_postgres_allows_one_runner_per_registration_token(
    postgres_session: Session,
):
    project = _create_test_project(
        postgres_session,
        "single-use-token",
    )
    token = _create_test_registration_token(
        postgres_session,
        project.id,
        "single-use-token",
    )

    first_runner = _build_test_runner(
        project_id=project.id,
        registration_token_id=token.id,
        suffix="single-use-first",
    )
    postgres_session.add(first_runner)
    postgres_session.flush()

    duplicate_runner = _build_test_runner(
        project_id=project.id,
        registration_token_id=token.id,
        suffix="single-use-second",
    )
    postgres_session.add(duplicate_runner)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


@pytest.mark.parametrize(
    ("status", "has_revocation_timestamp"),
    [
        ("active", True),
        ("revoked", False),
    ],
)
def test_postgres_enforces_runner_revocation_consistency(
    postgres_session: Session,
    status: str,
    has_revocation_timestamp: bool,
):
    project = _create_test_project(
        postgres_session,
        f"revocation-{status}-{has_revocation_timestamp}",
    )
    token = _create_test_registration_token(
        postgres_session,
        project.id,
        f"revocation-{status}-{has_revocation_timestamp}",
    )

    revoked_at = (
        datetime.now(UTC)
        if has_revocation_timestamp
        else None
    )

    runner = _build_test_runner(
        project_id=project.id,
        registration_token_id=token.id,
        suffix=f"revoke-{status}-{has_revocation_timestamp}",
        status=status,
        revoked_at=revoked_at,
    )
    postgres_session.add(runner)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()

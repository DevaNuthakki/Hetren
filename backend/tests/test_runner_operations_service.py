from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from app.runner_job_service import (
    claim_next_job,
    enqueue_job,
)
from app.runner_operations_service import (
    RunnerOperationsJobNotFoundError,
    RunnerOperationsProjectNotFoundError,
    get_project_runner_job_logs,
    get_project_runner_operations,
)
from app.runner_service import (
    issue_registration_token,
    register_runner,
)


@pytest.fixture
def db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(
        database_connection,
        _connection_record,
    ):
        cursor = database_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session = Session(bind=engine)

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def create_project(
    db: Session,
    name: str,
) -> models.Project:
    project = models.Project(name=name)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def create_registered_runner(
    db: Session,
    *,
    project: models.Project,
    name: str,
):
    issued = issue_registration_token(
        db,
        project_id=project.id,
        label=f"{name} registration",
    )

    return register_runner(
        db,
        registration_token=issued.token,
        name=name,
        runner_version="0.1.0-test",
        capabilities=["asr", "cpu"],
        system_info={
            "platform": "pytest",
            "private_hostname": "must-not-be-exposed",
        },
    )


def test_project_runner_operations_are_project_scoped_and_safe(
    db: Session,
):
    project = create_project(db, "Operations project")
    other_project = create_project(db, "Other project")

    registered = create_registered_runner(
        db,
        project=project,
        name="Operations runner",
    )

    enqueue_job(
        db,
        project_id=project.id,
        name="Project ASR job",
        job_type="asr_evaluation",
        required_capabilities=["asr"],
        input_payload={
            "private_path": "/private/audio.wav",
        },
    )

    claimed = claim_next_job(
        db,
        credential=registered.credential,
    )

    assert claimed is not None

    enqueue_job(
        db,
        project_id=other_project.id,
        name="Other project job",
        job_type="asr_evaluation",
        input_payload={"source": "other-project"},
    )

    snapshot = get_project_runner_operations(
        db,
        project_id=project.id,
    )

    assert snapshot.project_id == project.id
    assert len(snapshot.runners) == 1
    assert len(snapshot.jobs) == 1

    runner = snapshot.runners[0]
    assert runner.public_id == registered.runner.public_id
    assert runner.name == "Operations runner"
    assert runner.capabilities == ("asr", "cpu")
    assert not hasattr(runner, "credential_hash")
    assert not hasattr(runner, "system_info")
    assert not hasattr(runner, "registration_token_id")

    job = snapshot.jobs[0]
    assert job.public_id == claimed.job.public_id
    assert job.status == "claimed"
    assert (
        job.assigned_runner_public_id
        == registered.runner.public_id
    )
    assert job.assigned_runner_name == "Operations runner"
    assert not hasattr(job, "input_payload")
    assert not hasattr(job, "result_payload")
    assert not hasattr(job, "claim_token_hash")


def test_project_runner_operations_reject_missing_project(
    db: Session,
):
    with pytest.raises(
        RunnerOperationsProjectNotFoundError
    ):
        get_project_runner_operations(
            db,
            project_id=999,
        )


def test_project_runner_job_logs_are_safe_and_paginated(
    db: Session,
):
    project = create_project(db, "Log project")
    registered = create_registered_runner(
        db,
        project=project,
        name="Log runner",
    )

    enqueue_job(
        db,
        project_id=project.id,
        name="Logged ASR job",
        job_type="asr_evaluation",
        required_capabilities=["asr"],
        input_payload={"source": "pytest"},
    )

    claimed = claim_next_job(
        db,
        credential=registered.credential,
    )

    assert claimed is not None

    created_at = datetime(
        2026,
        8,
        2,
        1,
        0,
        tzinfo=UTC,
    )

    for sequence_number in range(1, 4):
        db.add(
            models.RunnerJobLog(
                public_id=str(uuid4()),
                project_id=project.id,
                job_id=claimed.job.id,
                runner_id=registered.runner.id,
                sequence_number=sequence_number,
                attempt_number=1,
                level="info",
                event_type="runner_test_event",
                message=f"Safe message {sequence_number}",
                context_payload={
                    "private_path": (
                        f"/private/{sequence_number}.wav"
                    )
                },
                created_at=created_at
                + timedelta(seconds=sequence_number),
            )
        )

    db.commit()

    first_page = get_project_runner_job_logs(
        db,
        project_id=project.id,
        job_public_id=claimed.job.public_id,
        limit=2,
    )

    assert [
        log.sequence_number
        for log in first_page.logs
    ] == [1, 2]
    assert first_page.has_more is True
    assert first_page.next_after_sequence == 2
    assert not hasattr(
        first_page.logs[0],
        "context_payload",
    )

    second_page = get_project_runner_job_logs(
        db,
        project_id=project.id,
        job_public_id=claimed.job.public_id,
        after_sequence=2,
        limit=2,
    )

    assert [
        log.sequence_number
        for log in second_page.logs
    ] == [3]
    assert second_page.has_more is False
    assert second_page.next_after_sequence == 3


def test_project_runner_job_logs_enforce_project_scope(
    db: Session,
):
    project = create_project(db, "First project")
    other_project = create_project(db, "Second project")

    job = enqueue_job(
        db,
        project_id=project.id,
        name="First project job",
        job_type="asr_evaluation",
        input_payload={"source": "pytest"},
    )

    with pytest.raises(
        RunnerOperationsJobNotFoundError
    ):
        get_project_runner_job_logs(
            db,
            project_id=other_project.id,
            job_public_id=job.public_id,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("project_id", 0),
        ("project_id", True),
        ("job_limit", 0),
        ("job_limit", 201),
    ],
)
def test_project_runner_operations_validate_inputs(
    db: Session,
    field: str,
    value,
):
    project = create_project(db, "Validation project")

    arguments = {
        "project_id": project.id,
        "job_limit": 100,
    }
    arguments[field] = value

    with pytest.raises(ValueError):
        get_project_runner_operations(
            db,
            **arguments,
        )

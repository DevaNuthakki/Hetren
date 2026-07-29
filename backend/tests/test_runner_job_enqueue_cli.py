import argparse
from io import StringIO

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from app.runner_job_service import (
    RunnerJobEnqueueConflictError,
)
from scripts import enqueue_runner_job as enqueue_cli


@pytest.fixture
def session_factory():
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

    factory = sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )

    try:
        yield factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def create_project(session_factory) -> models.Project:
    with session_factory() as db:
        project = models.Project(
            name="Runner job enqueue CLI project",
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return project


def test_cli_enqueues_controlled_runner_job(
    session_factory,
):
    project = create_project(session_factory)
    stdout = StringIO()
    stderr = StringIO()

    exit_code = enqueue_cli.run_cli(
        [
            "--project-id",
            str(project.id),
            "--name",
            "CLI ASR evaluation",
            "--job-type",
            "asr_evaluation",
            "--capability",
            "asr",
            "--capability",
            "cpu",
            "--input-json",
            '{"evaluation_run_id":42}',
            "--priority",
            "25",
            "--max-attempts",
            "5",
        ],
        session_factory=session_factory,
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert stderr.getvalue() == ""
    assert "Runner job enqueued successfully." in (
        stdout.getvalue()
    )

    with session_factory() as db:
        job = db.query(models.RunnerJob).one()

        assert job.project_id == project.id
        assert job.name == "CLI ASR evaluation"
        assert job.job_type == "asr_evaluation"
        assert job.status == "queued"
        assert job.required_capabilities == ["asr", "cpu"]
        assert job.input_payload == {
            "evaluation_run_id": 42
        }
        assert job.priority == 25
        assert job.max_attempts == 5


def test_cli_uses_safe_enqueue_defaults(
    session_factory,
):
    project = create_project(session_factory)
    stdout = StringIO()
    stderr = StringIO()

    exit_code = enqueue_cli.run_cli(
        [
            "--project-id",
            str(project.id),
            "--name",
            "Default CLI job",
            "--job-type",
            "asr_evaluation",
        ],
        session_factory=session_factory,
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert stderr.getvalue() == ""

    with session_factory() as db:
        job = db.query(models.RunnerJob).one()

        assert job.priority == 0
        assert job.required_capabilities == []
        assert job.input_payload == {}
        assert job.max_attempts == 3


def test_cli_rejects_missing_project(
    session_factory,
):
    stdout = StringIO()
    stderr = StringIO()

    exit_code = enqueue_cli.run_cli(
        [
            "--project-id",
            "2147483647",
            "--name",
            "Missing project job",
            "--job-type",
            "asr_evaluation",
        ],
        session_factory=session_factory,
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 2
    assert stdout.getvalue() == ""
    assert "was not found" in stderr.getvalue()


@pytest.mark.parametrize(
    "value",
    [
        "not-json",
        "[]",
        '"text"',
    ],
)
def test_json_object_rejects_invalid_values(
    value: str,
):
    with pytest.raises(argparse.ArgumentTypeError):
        enqueue_cli.json_object(value)


def test_cli_maps_enqueue_conflict_to_exit_one(
    session_factory,
    monkeypatch,
):
    project = create_project(session_factory)

    def reject_enqueue(_db, **_kwargs):
        raise RunnerJobEnqueueConflictError(
            "Internal enqueue conflict."
        )

    monkeypatch.setattr(
        enqueue_cli,
        "enqueue_job",
        reject_enqueue,
    )

    stdout = StringIO()
    stderr = StringIO()

    exit_code = enqueue_cli.run_cli(
        [
            "--project-id",
            str(project.id),
            "--name",
            "Conflicting job",
            "--job-type",
            "asr_evaluation",
        ],
        session_factory=session_factory,
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 1
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == (
        "ERROR: The runner job could not be enqueued.\n"
    )
    assert "internal enqueue conflict" not in (
        stderr.getvalue()
    )

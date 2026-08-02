from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from app import runner_operations_routes
from app.main import app
from app.runner_operations_service import (
    RunnerOperationsJob,
    RunnerOperationsJobNotFoundError,
    RunnerOperationsLog,
    RunnerOperationsLogPage,
    RunnerOperationsProjectNotFoundError,
    RunnerOperationsRunner,
    RunnerOperationsSnapshot,
)


def build_snapshot() -> RunnerOperationsSnapshot:
    now = datetime(
        2026,
        8,
        2,
        2,
        0,
        tzinfo=UTC,
    )

    runner = RunnerOperationsRunner(
        project_id=7,
        public_id="runner-public-id",
        name="Local ASR Runner",
        status="active",
        runner_version="0.1.0",
        capabilities=("asr", "cpu"),
        last_seen_at=now,
        revoked_at=None,
        created_at=now,
        updated_at=now,
    )

    job = RunnerOperationsJob(
        project_id=7,
        public_id="job-public-id",
        name="ASR evaluation",
        job_type="asr_evaluation",
        status="running",
        priority=0,
        required_capabilities=("asr",),
        assigned_runner_public_id=runner.public_id,
        assigned_runner_name=runner.name,
        attempt_count=1,
        max_attempts=3,
        error_message=None,
        available_at=now,
        claimed_at=now,
        lease_expires_at=now,
        started_at=now,
        completed_at=None,
        failed_at=None,
        cancelled_at=None,
        created_at=now,
        updated_at=now,
    )

    return RunnerOperationsSnapshot(
        project_id=7,
        runners=(runner,),
        jobs=(job,),
    )


def build_log_page() -> RunnerOperationsLogPage:
    now = datetime(
        2026,
        8,
        2,
        2,
        1,
        tzinfo=UTC,
    )

    return RunnerOperationsLogPage(
        project_id=7,
        job_public_id="job-public-id",
        logs=(
            RunnerOperationsLog(
                public_id="log-public-id",
                sequence_number=1,
                attempt_number=1,
                level="info",
                event_type="runner_started",
                message="Runner started the job.",
                created_at=now,
            ),
        ),
        has_more=False,
        next_after_sequence=1,
    )


def test_runner_operations_routes_are_included_in_app():
    paths = app.openapi()["paths"]

    assert (
        "/projects/{project_id}/runner-operations"
        in paths
    )
    assert (
        "get"
        in paths[
            "/projects/{project_id}/runner-operations"
        ]
    )

    log_path = (
        "/projects/{project_id}/runner-jobs/"
        "{job_public_id}/logs"
    )
    assert log_path in paths
    assert "get" in paths[log_path]


def test_runner_operations_endpoint_returns_snapshot(
    monkeypatch,
):
    snapshot = build_snapshot()

    def fake_get_operations(_db, **kwargs):
        assert kwargs == {
            "project_id": 7,
            "job_limit": 50,
        }
        return snapshot

    monkeypatch.setattr(
        runner_operations_routes,
        "get_project_runner_operations",
        fake_get_operations,
    )

    response = (
        runner_operations_routes
        .get_project_runner_operations_endpoint(
            project_id=7,
            job_limit=50,
            db=object(),
        )
    )

    assert response is snapshot


def test_runner_operations_endpoint_maps_missing_project(
    monkeypatch,
):
    def reject_operations(_db, **_kwargs):
        raise RunnerOperationsProjectNotFoundError(
            "Internal project state."
        )

    monkeypatch.setattr(
        runner_operations_routes,
        "get_project_runner_operations",
        reject_operations,
    )

    with pytest.raises(HTTPException) as error:
        (
            runner_operations_routes
            .get_project_runner_operations_endpoint(
                project_id=999,
                job_limit=100,
                db=object(),
            )
        )

    assert error.value.status_code == 404
    assert error.value.detail == "Project not found."
    assert "internal project" not in error.value.detail


def test_runner_job_logs_endpoint_returns_safe_page(
    monkeypatch,
):
    page = build_log_page()

    def fake_get_logs(_db, **kwargs):
        assert kwargs == {
            "project_id": 7,
            "job_public_id": "job-public-id",
            "after_sequence": 10,
            "limit": 25,
        }
        return page

    monkeypatch.setattr(
        runner_operations_routes,
        "get_project_runner_job_logs",
        fake_get_logs,
    )

    response = (
        runner_operations_routes
        .get_project_runner_job_logs_endpoint(
            project_id=7,
            job_public_id="job-public-id",
            after_sequence=10,
            limit=25,
            db=object(),
        )
    )

    assert response is page


def test_runner_job_logs_endpoint_maps_missing_job(
    monkeypatch,
):
    def reject_logs(_db, **_kwargs):
        raise RunnerOperationsJobNotFoundError(
            "Internal job state."
        )

    monkeypatch.setattr(
        runner_operations_routes,
        "get_project_runner_job_logs",
        reject_logs,
    )

    with pytest.raises(HTTPException) as error:
        (
            runner_operations_routes
            .get_project_runner_job_logs_endpoint(
                project_id=7,
                job_public_id="unknown-job",
                after_sequence=0,
                limit=100,
                db=object(),
            )
        )

    assert error.value.status_code == 404
    assert error.value.detail == (
        "Runner job not found in this project."
    )
    assert "internal job" not in error.value.detail


def test_runner_operations_endpoint_maps_invalid_input(
    monkeypatch,
):
    def reject_operations(_db, **_kwargs):
        raise ValueError(
            "Job limit must be between 1 and 200."
        )

    monkeypatch.setattr(
        runner_operations_routes,
        "get_project_runner_operations",
        reject_operations,
    )

    with pytest.raises(HTTPException) as error:
        (
            runner_operations_routes
            .get_project_runner_operations_endpoint(
                project_id=7,
                job_limit=201,
                db=object(),
            )
        )

    assert error.value.status_code == 422
    assert error.value.detail == (
        "Job limit must be between 1 and 200."
    )

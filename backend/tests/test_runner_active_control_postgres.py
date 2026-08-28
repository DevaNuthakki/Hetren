from __future__ import annotations

import asyncio
import os
import threading
from collections.abc import Generator
from dataclasses import dataclass
from uuid import uuid4

import httpx
import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app import models
from app.database import get_db
from app.local_runner_client import LocalRunnerClient
from app.local_runner_execution import (
    GENERIC_EXECUTION_TIMEOUT_ERROR,
    ExecutionControl,
    LocalRunnerCycleResult,
    run_one_local_runner_cycle,
)
from app.main import app
from app.runner_config import LocalRunnerSettings
from app.runner_job_service import (
    cancel_job,
    enqueue_job,
)
from app.runner_service import (
    issue_registration_token,
    register_runner,
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


@dataclass(frozen=True)
class RunnerHTTPHarness:
    transport: httpx.BaseTransport
    session_factory: sessionmaker[Session]


@dataclass(frozen=True)
class RunnerIntegrationCase:
    project_id: int
    registration_token_id: int
    runner_id: int
    job_id: int
    credential: str
    job_public_id: str


class SynchronousASGITransport(httpx.BaseTransport):
    """
    Adapt HTTPX's asynchronous ASGI transport for the synchronous
    LocalRunnerClient without using Starlette's deprecated TestClient.
    """

    def handle_request(
        self,
        request: httpx.Request,
    ) -> httpx.Response:
        return asyncio.run(
            self._handle_request(request)
        )

    async def _handle_request(
        self,
        request: httpx.Request,
    ) -> httpx.Response:
        transport = httpx.ASGITransport(
            app=app,
        )

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            response = await client.request(
                method=request.method,
                url=request.url,
                headers=request.headers,
                content=request.read(),
            )
            content = await response.aread()

        return httpx.Response(
            status_code=response.status_code,
            headers=response.headers,
            content=content,
            request=request,
            extensions=response.extensions,
        )


class CooperativeBlockingExecutor:
    """
    Block until the runner supplies a cooperative stop signal.

    The started event lets the test perform an external administrative
    cancellation only after the production start and initial log routes
    have completed.
    """

    def __init__(self):
        self.started = threading.Event()
        self.stopped = threading.Event()

    def execute(
        self,
        _job,
        control: ExecutionControl,
    ) -> dict[str, object]:
        self.started.set()

        if not control.wait(timeout=5):
            raise AssertionError(
                "Execution control was not signalled."
            )

        try:
            control.raise_if_stopped()
        finally:
            self.stopped.set()

        raise AssertionError(
            "Stopped execution must not continue."
        )


@pytest.fixture
def runner_http_harness(
    postgres_test_engine: Engine,
) -> Generator[RunnerHTTPHarness, None, None]:
    """
    Route the synchronous LocalRunnerClient into the real FastAPI app.

    Every HTTP request receives a fresh PostgreSQL session. This mirrors
    production request isolation and avoids sharing SQLAlchemy sessions
    across the runner and job-control threads.
    """
    session_factory = sessionmaker(
        bind=postgres_test_engine,
        expire_on_commit=False,
    )

    def override_get_db():
        db = session_factory()

        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    try:
        yield RunnerHTTPHarness(
            transport=SynchronousASGITransport(),
            session_factory=session_factory,
        )
    finally:
        app.dependency_overrides.pop(
            get_db,
            None,
        )


def create_runner_case(
    harness: RunnerHTTPHarness,
    *,
    label: str,
) -> RunnerIntegrationCase:
    suffix = uuid4().hex
    db = harness.session_factory()

    try:
        project = models.Project(
            name=(
                f"Runner active-control integration "
                f"{label} {suffix}"
            ),
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        issued = issue_registration_token(
            db,
            project_id=project.id,
            label=(
                f"Active-control integration "
                f"{label} registration"
            ),
        )

        registered = register_runner(
            db,
            registration_token=issued.token,
            name=(
                f"Active-control runner "
                f"{label} {suffix}"
            ),
            runner_version="0.1.0-integration",
            capabilities=["asr", "cpu"],
            system_info={
                "platform": "postgres-integration",
            },
        )

        job = enqueue_job(
            db,
            project_id=project.id,
            name=(
                f"Active-control job "
                f"{label} {suffix}"
            ),
            job_type="asr_evaluation",
            required_capabilities=["asr"],
            input_payload={
                "source": "postgres-integration",
                "scenario": label,
            },
            max_attempts=3,
        )

        return RunnerIntegrationCase(
            project_id=project.id,
            registration_token_id=issued.record.id,
            runner_id=registered.runner.id,
            job_id=job.id,
            credential=registered.credential,
            job_public_id=job.public_id,
        )
    finally:
        db.close()


def cleanup_runner_case(
    harness: RunnerHTTPHarness,
    case: RunnerIntegrationCase,
) -> None:
    db = harness.session_factory()

    try:
        (
            db.query(models.RunnerJobLog)
            .filter(
                models.RunnerJobLog.job_id
                == case.job_id
            )
            .delete(synchronize_session=False)
        )
        (
            db.query(models.RunnerJob)
            .filter(
                models.RunnerJob.id
                == case.job_id
            )
            .delete(synchronize_session=False)
        )
        (
            db.query(models.Runner)
            .filter(
                models.Runner.id
                == case.runner_id
            )
            .delete(synchronize_session=False)
        )
        (
            db.query(
                models.RunnerRegistrationToken
            )
            .filter(
                models.RunnerRegistrationToken.id
                == case.registration_token_id
            )
            .delete(synchronize_session=False)
        )
        (
            db.query(models.Project)
            .filter(
                models.Project.id
                == case.project_id
            )
            .delete(synchronize_session=False)
        )

        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def build_runner_settings(
    case: RunnerIntegrationCase,
    *,
    execution_timeout_seconds: float,
) -> LocalRunnerSettings:
    return LocalRunnerSettings(
        _env_file=None,
        HETREN_RUNNER_API_URL="http://testserver",
        HETREN_RUNNER_CREDENTIAL=case.credential,
        HETREN_RUNNER_VERSION=(
            "0.1.0-integration"
        ),
        HETREN_RUNNER_CAPABILITIES=[
            "asr",
            "cpu",
        ],
        HETREN_RUNNER_REQUEST_TIMEOUT_SECONDS=5,
        HETREN_RUNNER_LEASE_SECONDS=30,
        HETREN_RUNNER_POLL_INTERVAL_SECONDS=0.01,
        HETREN_RUNNER_LEASE_RENEWAL_INTERVAL_SECONDS=1,
        HETREN_RUNNER_CONTROL_POLL_INTERVAL_SECONDS=(
            0.01
        ),
        HETREN_RUNNER_EXECUTION_TIMEOUT_SECONDS=(
            execution_timeout_seconds
        ),
    )


def build_runner_client(
    harness: RunnerHTTPHarness,
    case: RunnerIntegrationCase,
) -> LocalRunnerClient:
    return LocalRunnerClient(
        api_base_url="http://testserver",
        credential=case.credential,
        timeout_seconds=5,
        transport=harness.transport,
    )


def read_job_and_logs(
    harness: RunnerHTTPHarness,
    case: RunnerIntegrationCase,
) -> tuple[
    models.RunnerJob,
    list[models.RunnerJobLog],
]:
    db = harness.session_factory()

    try:
        job = (
            db.query(models.RunnerJob)
            .filter(
                models.RunnerJob.id
                == case.job_id
            )
            .one()
        )

        logs = (
            db.query(models.RunnerJobLog)
            .filter(
                models.RunnerJobLog.job_id
                == case.job_id
            )
            .order_by(
                models.RunnerJobLog.sequence_number
            )
            .all()
        )

        db.expunge(job)

        for log in logs:
            db.expunge(log)

        return job, logs
    finally:
        db.close()


def test_postgres_running_job_cancellation_reaches_executor(
    runner_http_harness: RunnerHTTPHarness,
):
    case = create_runner_case(
        runner_http_harness,
        label="cancellation",
    )
    executor = CooperativeBlockingExecutor()

    cycle_results: list[
        LocalRunnerCycleResult
    ] = []
    cycle_errors: list[BaseException] = []

    try:
        with build_runner_client(
            runner_http_harness,
            case,
        ) as client:

            def run_cycle() -> None:
                try:
                    cycle_results.append(
                        run_one_local_runner_cycle(
                            client=client,
                            settings=(
                                build_runner_settings(
                                    case,
                                    execution_timeout_seconds=5,
                                )
                            ),
                            executor=executor,
                            system_info={
                                "platform": (
                                    "postgres-integration"
                                ),
                            },
                        )
                    )
                except BaseException as exc:
                    cycle_errors.append(exc)

            cycle_thread = threading.Thread(
                target=run_cycle,
                name=(
                    "hetren-cancellation-integration"
                ),
            )
            cycle_thread.start()

            assert executor.started.wait(timeout=5)

            cancellation_session = (
                runner_http_harness.session_factory()
            )

            try:
                cancelled = cancel_job(
                    cancellation_session,
                    job_public_id=case.job_public_id,
                )

                assert cancelled.status == "cancelled"
            finally:
                cancellation_session.close()

            cycle_thread.join(timeout=5)

            assert cycle_thread.is_alive() is False
            assert cycle_errors == []
            assert len(cycle_results) == 1

        result = cycle_results[0]

        assert result.status == "cancelled"
        assert result.job_public_id == (
            case.job_public_id
        )
        assert executor.stopped.is_set()

        job, logs = read_job_and_logs(
            runner_http_harness,
            case,
        )

        assert job.status == "cancelled"
        assert job.assigned_runner_id == (
            case.runner_id
        )
        assert job.claimed_at is not None
        assert job.started_at is not None
        assert job.cancelled_at is not None
        assert job.lease_expires_at is None
        assert job.claim_token_hash is None
        assert job.completed_at is None
        assert job.failed_at is None
        assert job.result_payload is None
        assert job.error_message is None

        assert [
            log.event_type
            for log in logs
        ] == [
            "execution_started",
        ]
    finally:
        cleanup_runner_case(
            runner_http_harness,
            case,
        )


def test_postgres_execution_timeout_logs_and_fails_job(
    runner_http_harness: RunnerHTTPHarness,
):
    case = create_runner_case(
        runner_http_harness,
        label="timeout",
    )
    executor = CooperativeBlockingExecutor()

    try:
        with build_runner_client(
            runner_http_harness,
            case,
        ) as client:
            result = run_one_local_runner_cycle(
                client=client,
                settings=build_runner_settings(
                    case,
                    execution_timeout_seconds=0.1,
                ),
                executor=executor,
                system_info={
                    "platform": (
                        "postgres-integration"
                    ),
                },
            )

        assert result.status == "failed"
        assert result.job_public_id == (
            case.job_public_id
        )
        assert result.timed_out is True
        assert result.error_message == (
            GENERIC_EXECUTION_TIMEOUT_ERROR
        )
        assert executor.started.is_set()
        assert executor.stopped.is_set()

        job, logs = read_job_and_logs(
            runner_http_harness,
            case,
        )

        assert job.status == "failed"
        assert job.assigned_runner_id == (
            case.runner_id
        )
        assert job.claimed_at is not None
        assert job.started_at is not None
        assert job.failed_at is not None
        assert job.completed_at is None
        assert job.cancelled_at is None
        assert job.lease_expires_at is None
        assert job.claim_token_hash is None
        assert job.result_payload is None
        assert job.error_message == (
            GENERIC_EXECUTION_TIMEOUT_ERROR
        )

        assert [
            log.event_type
            for log in logs
        ] == [
            "execution_started",
            "execution_timed_out",
        ]

        timeout_log = logs[1]

        assert timeout_log.level == "error"
        assert timeout_log.attempt_number == 1
        assert timeout_log.context_payload == {
            "job_type": "asr_evaluation",
            "timeout_seconds": 0.1,
        }
    finally:
        cleanup_runner_case(
            runner_http_harness,
            case,
        )

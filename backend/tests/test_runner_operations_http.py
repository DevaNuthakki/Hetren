import asyncio
from collections.abc import Generator
from dataclasses import dataclass
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base, get_db
from app.main import app
from app.runner_job_service import (
    claim_next_job,
    enqueue_job,
)
from app.runner_service import (
    issue_registration_token,
    register_runner,
)


class SynchronousASGITransport(httpx.BaseTransport):
    """Adapt HTTPX ASGI transport for synchronous route tests."""

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
        transport = httpx.ASGITransport(app=app)

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


@dataclass(frozen=True)
class OperationsHTTPCase:
    project_id: int
    other_project_id: int
    runner_public_id: str
    job_public_id: str
    runner_credential: str
    claim_token: str
    private_hostname: str
    private_path: str


@pytest.fixture
def operations_http_harness() -> Generator[
    tuple[
        httpx.Client,
        sessionmaker[Session],
    ],
    None,
    None,
]:
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

    session_factory = sessionmaker(
        bind=engine,
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
        with httpx.Client(
            transport=SynchronousASGITransport(),
            base_url="http://testserver",
        ) as client:
            yield client, session_factory
    finally:
        app.dependency_overrides.pop(
            get_db,
            None,
        )
        Base.metadata.drop_all(engine)
        engine.dispose()


def create_operations_case(
    session_factory: sessionmaker[Session],
) -> OperationsHTTPCase:
    private_hostname = "private-runner.internal.example"
    private_path = "/private/customer/audio.wav"

    db = session_factory()

    try:
        project = models.Project(
            name="Runner operations HTTP project",
        )
        other_project = models.Project(
            name="Other HTTP project",
        )

        db.add_all([project, other_project])
        db.commit()
        db.refresh(project)
        db.refresh(other_project)

        issued = issue_registration_token(
            db,
            project_id=project.id,
            label="HTTP test registration",
        )

        registered = register_runner(
            db,
            registration_token=issued.token,
            name="HTTP ASR runner",
            runner_version="0.1.0-http-test",
            capabilities=["asr", "cpu"],
            system_info={
                "platform": "pytest",
                "private_hostname": private_hostname,
            },
        )

        enqueue_job(
            db,
            project_id=project.id,
            name="HTTP ASR evaluation",
            job_type="asr_evaluation",
            required_capabilities=["asr"],
            input_payload={
                "private_path": private_path,
            },
        )

        claimed = claim_next_job(
            db,
            credential=registered.credential,
        )

        assert claimed is not None

        db.add(
            models.RunnerJobLog(
                public_id=str(uuid4()),
                project_id=project.id,
                job_id=claimed.job.id,
                runner_id=registered.runner.id,
                sequence_number=1,
                attempt_number=1,
                level="info",
                event_type="runner_http_test",
                message="Safe runner HTTP log.",
                context_payload={
                    "private_path": private_path,
                    "private_hostname": private_hostname,
                },
            )
        )
        db.commit()

        return OperationsHTTPCase(
            project_id=project.id,
            other_project_id=other_project.id,
            runner_public_id=registered.runner.public_id,
            job_public_id=claimed.job.public_id,
            runner_credential=registered.credential,
            claim_token=claimed.claim_token,
            private_hostname=private_hostname,
            private_path=private_path,
        )
    finally:
        db.close()


def test_runner_operations_http_response_is_safe(
    operations_http_harness,
):
    client, session_factory = operations_http_harness
    case = create_operations_case(session_factory)

    response = client.get(
        f"/projects/{case.project_id}/runner-operations"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["project_id"] == case.project_id
    assert len(payload["runners"]) == 1
    assert len(payload["jobs"]) == 1

    runner = payload["runners"][0]
    job = payload["jobs"][0]

    assert runner["public_id"] == case.runner_public_id
    assert job["public_id"] == case.job_public_id
    assert job["assigned_runner_public_id"] == (
        case.runner_public_id
    )

    assert {
        "credential_hash",
        "registration_token_id",
        "system_info",
    }.isdisjoint(runner)

    assert {
        "claim_token_hash",
        "input_payload",
        "result_payload",
    }.isdisjoint(job)

    response_text = response.text

    assert case.runner_credential not in response_text
    assert case.claim_token not in response_text
    assert case.private_hostname not in response_text
    assert case.private_path not in response_text


def test_runner_operations_logs_http_response_is_safe(
    operations_http_harness,
):
    client, session_factory = operations_http_harness
    case = create_operations_case(session_factory)

    response = client.get(
        f"/projects/{case.project_id}/runner-jobs/"
        f"{case.job_public_id}/logs"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["project_id"] == case.project_id
    assert payload["job_public_id"] == (
        case.job_public_id
    )
    assert payload["has_more"] is False
    assert payload["next_after_sequence"] == 1
    assert len(payload["logs"]) == 1

    log = payload["logs"][0]

    assert log["sequence_number"] == 1
    assert log["message"] == "Safe runner HTTP log."
    assert "context_payload" not in log

    assert case.private_hostname not in response.text
    assert case.private_path not in response.text


def test_runner_operations_http_enforces_project_scope(
    operations_http_harness,
):
    client, session_factory = operations_http_harness
    case = create_operations_case(session_factory)

    response = client.get(
        f"/projects/{case.other_project_id}/runner-jobs/"
        f"{case.job_public_id}/logs"
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": (
            "Runner job not found in this project."
        )
    }


def test_runner_operations_http_maps_missing_project(
    operations_http_harness,
):
    client, _session_factory = operations_http_harness

    response = client.get(
        "/projects/999999/runner-operations"
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Project not found."
    }

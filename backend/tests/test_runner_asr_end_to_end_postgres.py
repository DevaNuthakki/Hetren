from __future__ import annotations

import asyncio
import os
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app import models
from app.database import get_db
from app.local_runner_client import LocalRunnerClient
from app.local_runner_execution import (
    run_one_local_runner_cycle,
)
from app.main import app
from app.runner_config import LocalRunnerSettings
from app.runner_job_service import enqueue_job
from app.runner_service import issue_registration_token
from app.speech.mock_provider import MockASRProvider


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


EXPECTED_TRANSCRIPT = (
    "mock asr transcript generated from input"
)


class RecordingSynchronousASGITransport(
    httpx.BaseTransport
):
    """
    Route the synchronous runner client through the real FastAPI app.

    Request paths are retained so the test can prove that the complete
    claim, context, audio, and atomic-result protocol was exercised.
    """

    def __init__(self):
        self.requests: list[tuple[str, str]] = []

    def handle_request(
        self,
        request: httpx.Request,
    ) -> httpx.Response:
        self.requests.append(
            (
                request.method,
                request.url.path,
            )
        )

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
class RunnerHTTPHarness:
    transport: RecordingSynchronousASGITransport
    session_factory: sessionmaker[Session]


@dataclass(frozen=True)
class RunnerASREndToEndCase:
    project_id: int
    dataset_id: int
    test_case_id: int
    evaluation_run_id: int
    registration_token_id: int
    runner_id: int
    job_id: int
    job_public_id: str
    credential: str
    source_audio_path: Path


@pytest.fixture
def runner_http_harness(
    postgres_test_engine: Engine,
) -> Generator[RunnerHTTPHarness, None, None]:
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
            transport=(
                RecordingSynchronousASGITransport()
            ),
            session_factory=session_factory,
        )
    finally:
        app.dependency_overrides.pop(
            get_db,
            None,
        )


def cleanup_case(
    harness: RunnerHTTPHarness,
    case: RunnerASREndToEndCase,
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
            db.query(models.EvaluationResult)
            .filter(
                models.EvaluationResult.run_id
                == case.evaluation_run_id
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
            db.query(models.TestCase)
            .filter(
                models.TestCase.id
                == case.test_case_id
            )
            .delete(synchronize_session=False)
        )
        (
            db.query(models.EvaluationRun)
            .filter(
                models.EvaluationRun.id
                == case.evaluation_run_id
            )
            .delete(synchronize_session=False)
        )
        (
            db.query(models.Dataset)
            .filter(
                models.Dataset.id
                == case.dataset_id
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


def create_case(
    harness: RunnerHTTPHarness,
    *,
    uploads_root: Path,
) -> RunnerASREndToEndCase:
    suffix = uuid4().hex
    source_audio_path = (
        uploads_root
        / "datasets"
        / suffix
        / "test-cases"
        / "audio"
        / "support-call.wav"
    )
    source_audio_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    source_audio_path.write_bytes(
        b"ovrin-runner-asr-end-to-end-audio"
    )

    db = harness.session_factory()

    try:
        project = models.Project(
            name=f"Runner ASR E2E {suffix}",
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        issued = issue_registration_token(
            db,
            project_id=project.id,
            label=f"Runner ASR E2E token {suffix}",
        )

        dataset = models.Dataset(
            project_id=project.id,
            name=f"Runner ASR E2E dataset {suffix}",
        )
        db.add(dataset)
        db.flush()

        test_case = models.TestCase(
            dataset_id=dataset.id,
            title="Runner ASR E2E support call",
            audio_file_path=str(source_audio_path),
            reference_transcript=EXPECTED_TRANSCRIPT,
        )
        evaluation_run = models.EvaluationRun(
            project_id=project.id,
            run_name="Runner ASR E2E evaluation",
            model_name="mock-asr-integration",
        )
        db.add_all(
            [
                test_case,
                evaluation_run,
            ]
        )
        db.commit()
        db.refresh(dataset)
        db.refresh(test_case)
        db.refresh(evaluation_run)

        project_id = project.id
        dataset_id = dataset.id
        test_case_id = test_case.id
        evaluation_run_id = evaluation_run.id
        registration_token_id = issued.record.id
        registration_token = issued.token
    finally:
        db.close()

    with httpx.Client(
        transport=harness.transport,
        base_url="http://testserver",
        timeout=5,
    ) as registration_client:
        response = registration_client.post(
            "/runners/register",
            json={
                "registration_token": registration_token,
                "name": f"Runner ASR E2E {suffix}",
                "runner_version": (
                    "0.1.0-asr-e2e"
                ),
                "capabilities": [
                    "asr",
                    "cpu",
                    "local",
                ],
                "system_info": {
                    "platform": (
                        "postgres-asr-integration"
                    ),
                },
            },
        )

    response.raise_for_status()
    registration_payload = response.json()
    credential = registration_payload["credential"]
    runner_public_id = registration_payload[
        "runner"
    ]["public_id"]

    db = harness.session_factory()

    try:
        runner = (
            db.query(models.Runner)
            .filter(
                models.Runner.public_id
                == runner_public_id
            )
            .one()
        )

        job = enqueue_job(
            db,
            project_id=project_id,
            name=f"Runner ASR E2E job {suffix}",
            job_type="asr_evaluation",
            required_capabilities=["asr"],
            input_payload={
                "evaluation_run_id": (
                    evaluation_run_id
                ),
                "test_case_id": test_case_id,
            },
            max_attempts=3,
        )

        return RunnerASREndToEndCase(
            project_id=project_id,
            dataset_id=dataset_id,
            test_case_id=test_case_id,
            evaluation_run_id=evaluation_run_id,
            registration_token_id=(
                registration_token_id
            ),
            runner_id=runner.id,
            job_id=job.id,
            job_public_id=job.public_id,
            credential=credential,
            source_audio_path=source_audio_path,
        )
    finally:
        db.close()


def build_settings(
    case: RunnerASREndToEndCase,
) -> LocalRunnerSettings:
    return LocalRunnerSettings(
        _env_file=None,
        OVRIN_RUNNER_API_URL="http://testserver",
        OVRIN_RUNNER_CREDENTIAL=case.credential,
        OVRIN_RUNNER_VERSION="0.1.0-asr-e2e",
        OVRIN_RUNNER_CAPABILITIES=[
            "asr",
            "cpu",
            "local",
        ],
        OVRIN_RUNNER_REQUEST_TIMEOUT_SECONDS=5,
        OVRIN_RUNNER_LEASE_SECONDS=30,
        OVRIN_RUNNER_POLL_INTERVAL_SECONDS=0.01,
        OVRIN_RUNNER_LEASE_RENEWAL_INTERVAL_SECONDS=1,
        OVRIN_RUNNER_CONTROL_POLL_INTERVAL_SECONDS=0.01,
        OVRIN_RUNNER_EXECUTION_TIMEOUT_SECONDS=5,
        OVRIN_RUNNER_ASR_PROVIDER="mock_local",
        OVRIN_RUNNER_ASR_MODEL="mock-asr-foundation",
        OVRIN_RUNNER_ASR_DEVICE="cpu",
        OVRIN_RUNNER_ASR_COMPUTE_TYPE="int8",
    )


def test_postgres_runner_executes_asr_evaluation_end_to_end(
    runner_http_harness: RunnerHTTPHarness,
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)

    uploads_root = tmp_path / "uploads"
    case = create_case(
        runner_http_harness,
        uploads_root=uploads_root,
    )

    temporary_audio_paths: list[Path] = []
    original_transcribe = MockASRProvider.transcribe

    def record_transcription(
        self,
        audio_path: str | Path,
        model_name: str | None = None,
    ):
        temporary_audio_path = Path(audio_path)

        assert temporary_audio_path.exists()
        assert temporary_audio_path.name == "input.wav"
        assert temporary_audio_path.read_bytes() == (
            b"ovrin-runner-asr-end-to-end-audio"
        )

        temporary_audio_paths.append(
            temporary_audio_path,
        )

        return original_transcribe(
            self,
            temporary_audio_path,
            model_name=model_name,
        )

    monkeypatch.setattr(
        MockASRProvider,
        "transcribe",
        record_transcription,
    )

    try:
        with LocalRunnerClient(
            api_base_url="http://testserver",
            credential=case.credential,
            timeout_seconds=5,
            transport=runner_http_harness.transport,
        ) as client:
            cycle_result = run_one_local_runner_cycle(
                client=client,
                settings=build_settings(case),
                system_info={
                    "platform": (
                        "postgres-asr-integration"
                    ),
                },
            )

        assert cycle_result.status == "completed"
        assert cycle_result.job_public_id == (
            case.job_public_id
        )

        result_payload = cycle_result.result_payload

        assert result_payload is not None
        assert result_payload[
            "evaluation_run_id"
        ] == case.evaluation_run_id
        assert result_payload[
            "test_case_id"
        ] == case.test_case_id
        assert result_payload["provider"] == "mock_local"
        assert result_payload[
            "provider_metadata"
        ] == {
            "model_name": "mock-asr-integration",
        }
        assert result_payload["wer"] == pytest.approx(0.0)
        assert result_payload["cer"] == pytest.approx(0.0)
        assert result_payload[
            "quality_label"
        ] == "excellent"

        assert len(temporary_audio_paths) == 1
        assert not temporary_audio_paths[0].exists()

        # The backend-owned source file remains available. Only the
        # runner's temporary downloaded copy is deleted.
        assert case.source_audio_path.exists()

        request_paths = [
            path
            for _method, path
            in runner_http_harness.transport.requests
        ]

        context_path = (
            f"/runners/jobs/{case.job_public_id}"
            "/asr/context"
        )
        audio_path = (
            f"/runners/jobs/{case.job_public_id}"
            "/asr/audio"
        )
        result_path = (
            f"/runners/jobs/{case.job_public_id}"
            "/asr/result"
        )

        assert "/runners/register" in request_paths
        assert "/runners/heartbeat" in request_paths
        assert "/runners/jobs/claim" in request_paths
        assert context_path in request_paths
        assert audio_path in request_paths
        assert result_path in request_paths

        assert request_paths.index(
            context_path
        ) < request_paths.index(
            audio_path
        ) < request_paths.index(
            result_path
        )

        db = runner_http_harness.session_factory()

        try:
            job = db.get(
                models.RunnerJob,
                case.job_id,
            )
            evaluation_run = db.get(
                models.EvaluationRun,
                case.evaluation_run_id,
            )
            registration_token = db.get(
                models.RunnerRegistrationToken,
                case.registration_token_id,
            )

            assert job is not None
            assert evaluation_run is not None
            assert registration_token is not None

            persisted_results = (
                db.query(models.EvaluationResult)
                .filter(
                    models.EvaluationResult.run_id
                    == case.evaluation_run_id,
                    models.EvaluationResult.test_case_id
                    == case.test_case_id,
                )
                .all()
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

            assert len(persisted_results) == 1

            evaluation_result = persisted_results[0]

            assert evaluation_result.generated_transcript == (
                EXPECTED_TRANSCRIPT
            )
            assert evaluation_result.generated_file_path is None
            assert evaluation_result.wer == pytest.approx(0.0)
            assert evaluation_result.cer == pytest.approx(0.0)
            assert evaluation_result.quality_label == (
                "excellent"
            )

            assert evaluation_run.status == "evaluated"
            assert evaluation_run.reference_transcript == (
                EXPECTED_TRANSCRIPT
            )
            assert evaluation_run.generated_transcript == (
                EXPECTED_TRANSCRIPT
            )
            assert evaluation_run.wer == pytest.approx(0.0)
            assert evaluation_run.cer == pytest.approx(0.0)
            assert evaluation_run.quality_label == (
                "excellent"
            )

            assert job.status == "completed"
            assert job.assigned_runner_id == case.runner_id
            assert job.attempt_count == 1
            assert job.claimed_at is not None
            assert job.started_at is not None
            assert job.completed_at is not None
            assert job.failed_at is None
            assert job.cancelled_at is None
            assert job.lease_expires_at is None
            assert job.claim_token_hash is None
            assert job.error_message is None
            assert job.result_payload == result_payload

            assert registration_token.consumed_at is not None

            assert [
                log.event_type
                for log in logs
            ] == [
                "execution_started",
                "execution_completed",
            ]
        finally:
            db.close()
    finally:
        cleanup_case(
            runner_http_harness,
            case,
        )

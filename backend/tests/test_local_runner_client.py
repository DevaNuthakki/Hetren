from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from app.local_runner_client import (
    LocalRunnerAPIError,
    LocalRunnerAuthenticationError,
    LocalRunnerClient,
    LocalRunnerInputError,
    LocalRunnerProtocolError,
    LocalRunnerRequestError,
    build_local_runner_client,
)
from app.runner_config import LocalRunnerSettings


NOW = datetime(
    2026,
    7,
    31,
    21,
    0,
    tzinfo=UTC,
).isoformat()


def build_runner_payload() -> dict[str, object]:
    return {
        "project_id": 7,
        "public_id": (
            "10000000-0000-0000-0000-000000000001"
        ),
        "name": "Local ASR Runner",
        "status": "active",
        "runner_version": "0.1.0",
        "capabilities": ["asr", "cpu"],
        "system_info": {
            "platform": "darwin",
        },
        "last_seen_at": NOW,
        "revoked_at": None,
        "created_at": NOW,
        "updated_at": NOW,
    }


def build_job_payload() -> dict[str, object]:
    return {
        "public_id": (
            "20000000-0000-0000-0000-000000000001"
        ),
        "project_id": 7,
        "name": "ASR evaluation",
        "job_type": "asr_evaluation",
        "status": "claimed",
        "priority": 10,
        "required_capabilities": ["asr"],
        "input_payload": {
            "evaluation_run_id": 42,
        },
        "attempt_count": 1,
        "max_attempts": 3,
        "available_at": NOW,
        "claimed_at": NOW,
        "lease_expires_at": NOW,
        "started_at": None,
        "completed_at": None,
        "failed_at": None,
        "cancelled_at": None,
        "result_payload": None,
        "error_message": None,
        "created_at": NOW,
        "updated_at": NOW,
    }


def test_local_runner_client_sends_authenticated_heartbeat():
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/runners/heartbeat"
        assert request.headers["authorization"] == (
            "Bearer ovrin_runner_test-credential"
        )

        assert request.read() == (
            b'{"runner_version":"0.2.0",'
            b'"capabilities":["asr","cpu"],'
            b'"system_info":{"platform":"darwin"}}'
        )

        return httpx.Response(
            200,
            json={
                "status": "ok",
                "runner": build_runner_payload(),
            },
        )

    transport = httpx.MockTransport(handler)

    with LocalRunnerClient(
        api_base_url="https://ovrin.example.com/",
        credential="ovrin_runner_test-credential",
        transport=transport,
    ) as client:
        response = client.heartbeat(
            runner_version="0.2.0",
            capabilities=["asr", "cpu"],
            system_info={"platform": "darwin"},
        )

    assert response.status == "ok"
    assert response.runner.project_id == 7
    assert response.runner.name == "Local ASR Runner"


def test_local_runner_client_claims_job():
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/runners/jobs/claim"
        assert request.headers["authorization"] == (
            "Bearer ovrin_runner_test-credential"
        )
        assert request.read() == b'{"lease_seconds":600}'

        return httpx.Response(
            200,
            json={
                "status": "claimed",
                "claim_token": "ovrin_claim_test-token",
                "job": build_job_payload(),
            },
        )

    transport = httpx.MockTransport(handler)

    with LocalRunnerClient(
        api_base_url="https://ovrin.example.com",
        credential="ovrin_runner_test-credential",
        transport=transport,
    ) as client:
        response = client.claim_next_job(
            lease_seconds=600,
        )

    assert response.status == "claimed"
    assert response.claim_token == "ovrin_claim_test-token"
    assert response.job is not None
    assert response.job.job_type == "asr_evaluation"


def test_local_runner_client_handles_idle_queue():
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200,
            json={
                "status": "idle",
                "claim_token": None,
                "job": None,
            },
        )
    )

    with LocalRunnerClient(
        api_base_url="https://ovrin.example.com",
        credential="ovrin_runner_test-credential",
        transport=transport,
    ) as client:
        response = client.claim_next_job(
            lease_seconds=300,
        )

    assert response.status == "idle"
    assert response.claim_token is None
    assert response.job is None


def test_local_runner_client_maps_authentication_failure():
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            401,
            json={
                "detail": (
                    "Runner credential is invalid "
                    "or unavailable."
                )
            },
        )
    )

    with LocalRunnerClient(
        api_base_url="https://ovrin.example.com",
        credential="ovrin_runner_secret-value",
        transport=transport,
    ) as client:
        with pytest.raises(
            LocalRunnerAuthenticationError,
        ) as error:
            client.claim_next_job(
                lease_seconds=300,
            )

    assert "ovrin_runner_secret-value" not in str(
        error.value
    )


def test_local_runner_client_maps_api_error():
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            409,
            json={
                "detail": "Internal state must remain hidden."
            },
        )
    )

    with LocalRunnerClient(
        api_base_url="https://ovrin.example.com",
        credential="ovrin_runner_test-credential",
        transport=transport,
    ) as client:
        with pytest.raises(
            LocalRunnerAPIError,
        ) as error:
            client.claim_next_job(
                lease_seconds=300,
            )

    assert error.value.status_code == 409
    assert "Internal state" not in str(error.value)


@pytest.mark.parametrize(
    "response_payload",
    [
        {
            "status": "claimed",
            "claim_token": None,
            "job": None,
        },
        {
            "status": "idle",
            "claim_token": "ovrin_claim_invalid-token",
            "job": None,
        },
        {
            "status": "idle",
            "claim_token": None,
            "job": build_job_payload(),
        },
    ],
)
def test_local_runner_client_rejects_invalid_response(
    response_payload: dict[str, object],
):
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200,
            json=response_payload,
        )
    )

    with LocalRunnerClient(
        api_base_url="https://ovrin.example.com",
        credential="ovrin_runner_test-credential",
        transport=transport,
    ) as client:
        with pytest.raises(LocalRunnerProtocolError):
            client.claim_next_job(
                lease_seconds=300,
            )


def test_local_runner_client_maps_connection_failure():
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        raise httpx.ConnectError(
            "Connection failed.",
            request=request,
        )

    transport = httpx.MockTransport(handler)

    with LocalRunnerClient(
        api_base_url="https://ovrin.example.com",
        credential="ovrin_runner_test-credential",
        transport=transport,
    ) as client:
        with pytest.raises(LocalRunnerRequestError):
            client.heartbeat(
                runner_version="0.1.0",
                capabilities=["asr"],
            )


def test_build_local_runner_client_uses_settings():
    settings = LocalRunnerSettings(
        _env_file=None,
        OVRIN_RUNNER_API_URL=(
            "https://ovrin.example.com/"
        ),
        OVRIN_RUNNER_CREDENTIAL=(
            "ovrin_runner_test-credential"
        ),
        OVRIN_RUNNER_REQUEST_TIMEOUT_SECONDS=45,
    )

    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "status": "idle",
                "claim_token": None,
                "job": None,
            },
            request=request,
        )
    )

    with build_local_runner_client(
        settings,
        transport=transport,
    ) as client:
        response = client.claim_next_job(
            lease_seconds=settings.lease_seconds,
        )

    assert response.status == "idle"


def test_local_runner_client_starts_claimed_job():
    job_payload = build_job_payload()
    job_payload["status"] = "running"
    job_payload["started_at"] = NOW

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.url.path == (
            "/runners/jobs/"
            "20000000-0000-0000-0000-000000000001/start"
        )
        assert request.method == "POST"
        assert request.read() == (
            b'{"claim_token":"ovrin_claim_test-token"}'
        )

        return httpx.Response(
            200,
            json={
                "status": "running",
                "job": job_payload,
            },
        )

    with LocalRunnerClient(
        api_base_url="https://ovrin.example.com",
        credential="ovrin_runner_test-credential",
        transport=httpx.MockTransport(handler),
    ) as client:
        response = client.start_job(
            job_public_id=str(
                build_job_payload()["public_id"]
            ),
            claim_token="ovrin_claim_test-token",
        )

    assert response.status == "running"
    assert response.job.status == "running"


def test_local_runner_client_renews_job_lease():
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.url.path.endswith("/renew")
        assert request.read() == (
            b'{"claim_token":"ovrin_claim_test-token",'
            b'"lease_seconds":600}'
        )

        return httpx.Response(
            200,
            json={
                "status": "renewed",
                "job": build_job_payload(),
            },
        )

    with LocalRunnerClient(
        api_base_url="https://ovrin.example.com",
        credential="ovrin_runner_test-credential",
        transport=httpx.MockTransport(handler),
    ) as client:
        response = client.renew_job_lease(
            job_public_id=str(
                build_job_payload()["public_id"]
            ),
            claim_token="ovrin_claim_test-token",
            lease_seconds=600,
        )

    assert response.status == "renewed"


def test_local_runner_client_appends_structured_logs():
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.url.path.endswith("/logs")
        assert request.read() == (
            b'{"claim_token":"ovrin_claim_test-token",'
            b'"entries":[{"level":"info",'
            b'"event_type":"execution_started",'
            b'"message":"Runner execution started.",'
            b'"context_payload":{"executor":"placeholder"}}]}'
        )

        return httpx.Response(
            201,
            json={
                "status": "appended",
                "logs": [
                    {
                        "public_id": (
                            "30000000-0000-0000-0000-"
                            "000000000001"
                        ),
                        "sequence_number": 1,
                        "attempt_number": 1,
                        "level": "info",
                        "event_type": "execution_started",
                        "message": (
                            "Runner execution started."
                        ),
                        "context_payload": {
                            "executor": "placeholder",
                        },
                        "created_at": NOW,
                    }
                ],
            },
        )

    with LocalRunnerClient(
        api_base_url="https://ovrin.example.com",
        credential="ovrin_runner_test-credential",
        transport=httpx.MockTransport(handler),
    ) as client:
        response = client.append_job_logs(
            job_public_id=str(
                build_job_payload()["public_id"]
            ),
            claim_token="ovrin_claim_test-token",
            entries=[
                {
                    "level": "info",
                    "event_type": "execution_started",
                    "message": (
                        "Runner execution started."
                    ),
                    "context_payload": {
                        "executor": "placeholder",
                    },
                }
            ],
        )

    assert response.status == "appended"
    assert response.logs[0].sequence_number == 1


def test_local_runner_client_completes_job():
    job_payload = build_job_payload()
    job_payload["status"] = "completed"
    job_payload["completed_at"] = NOW
    job_payload["lease_expires_at"] = None
    job_payload["result_payload"] = {
        "execution_mode": "placeholder",
    }

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.url.path.endswith("/complete")
        assert request.read() == (
            b'{"claim_token":"ovrin_claim_test-token",'
            b'"result_payload":'
            b'{"execution_mode":"placeholder"}}'
        )

        return httpx.Response(
            200,
            json={
                "status": "completed",
                "job": job_payload,
            },
        )

    with LocalRunnerClient(
        api_base_url="https://ovrin.example.com",
        credential="ovrin_runner_test-credential",
        transport=httpx.MockTransport(handler),
    ) as client:
        response = client.complete_job(
            job_public_id=str(
                build_job_payload()["public_id"]
            ),
            claim_token="ovrin_claim_test-token",
            result_payload={
                "execution_mode": "placeholder",
            },
        )

    assert response.status == "completed"
    assert response.job.status == "completed"


def test_local_runner_client_fails_job():
    job_payload = build_job_payload()
    job_payload["status"] = "failed"
    job_payload["failed_at"] = NOW
    job_payload["lease_expires_at"] = None
    job_payload["error_message"] = (
        "Placeholder execution failed."
    )

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.url.path.endswith("/fail")
        assert request.read() == (
            b'{"claim_token":"ovrin_claim_test-token",'
            b'"error_message":'
            b'"Placeholder execution failed."}'
        )

        return httpx.Response(
            200,
            json={
                "status": "failed",
                "job": job_payload,
            },
        )

    with LocalRunnerClient(
        api_base_url="https://ovrin.example.com",
        credential="ovrin_runner_test-credential",
        transport=httpx.MockTransport(handler),
    ) as client:
        response = client.fail_job(
            job_public_id=str(
                build_job_payload()["public_id"]
            ),
            claim_token="ovrin_claim_test-token",
            error_message=(
                "Placeholder execution failed."
            ),
        )

    assert response.status == "failed"
    assert response.job.status == "failed"


@pytest.mark.parametrize(
    "job_public_id",
    [
        "",
        "   ",
        "../another-job",
        "job/another-job",
    ],
)
def test_local_runner_client_rejects_unsafe_job_id(
    job_public_id: str,
):
    with LocalRunnerClient(
        api_base_url="https://ovrin.example.com",
        credential="ovrin_runner_test-credential",
        transport=httpx.MockTransport(
            lambda _request: pytest.fail(
                "HTTP request must not be sent."
            )
        ),
    ) as client:
        with pytest.raises(
            LocalRunnerInputError,
        ):
            client.start_job(
                job_public_id=job_public_id,
                claim_token="ovrin_claim_test-token",
            )


def test_local_runner_client_rejects_invalid_log_batch():
    with LocalRunnerClient(
        api_base_url="https://ovrin.example.com",
        credential="ovrin_runner_test-credential",
        transport=httpx.MockTransport(
            lambda _request: pytest.fail(
                "HTTP request must not be sent."
            )
        ),
    ) as client:
        with pytest.raises(
            LocalRunnerInputError,
        ):
            client.append_job_logs(
                job_public_id=str(
                    build_job_payload()["public_id"]
                ),
                claim_token="ovrin_claim_test-token",
                entries=[],
            )


def test_local_runner_client_gets_active_job_control_status():
    job_public_id = (
        "20000000-0000-0000-0000-000000000001"
    )

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == (
            f"/runners/jobs/{job_public_id}/control"
        )
        assert request.headers["authorization"] == (
            "Bearer ovrin_runner_test-credential"
        )
        assert request.read() == b"{}"

        return httpx.Response(
            200,
            json={
                "status": "active",
            },
        )

    with LocalRunnerClient(
        api_base_url="https://ovrin.example.com",
        credential="ovrin_runner_test-credential",
        transport=httpx.MockTransport(handler),
    ) as client:
        response = client.get_job_control_status(
            job_public_id=job_public_id,
        )

    assert response.status == "active"


def test_local_runner_client_gets_cancelled_job_control_status():
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200,
            json={
                "status": "cancelled",
            },
        )
    )

    with LocalRunnerClient(
        api_base_url="https://ovrin.example.com",
        credential="ovrin_runner_test-credential",
        transport=transport,
    ) as client:
        response = client.get_job_control_status(
            job_public_id=(
                "20000000-0000-0000-0000-000000000001"
            ),
        )

    assert response.status == "cancelled"



@pytest.mark.parametrize(
    "job_public_id",
    [
        "",
        "   ",
        "../another-job",
        "job/another-job",
    ],
)
def test_local_runner_client_rejects_unsafe_control_job_id(
    job_public_id: str,
):
    with LocalRunnerClient(
        api_base_url="https://ovrin.example.com",
        credential="ovrin_runner_test-credential",
        transport=httpx.MockTransport(
            lambda _request: pytest.fail(
                "HTTP request must not be sent."
            )
        ),
    ) as client:
        with pytest.raises(LocalRunnerInputError):
            client.get_job_control_status(
                job_public_id=job_public_id,
            )



def test_local_runner_client_gets_asr_evaluation_context():
    job_public_id = (
        "20000000-0000-0000-0000-000000000001"
    )

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == (
            f"/runners/jobs/{job_public_id}/asr/context"
        )
        assert request.headers["authorization"] == (
            "Bearer ovrin_runner_test-credential"
        )
        assert request.headers["accept"] == (
            "application/json"
        )
        assert request.read() == (
            b'{"claim_token":"ovrin_claim_test-token"}'
        )

        return httpx.Response(
            200,
            json={
                "project_id": 7,
                "evaluation_run_id": 42,
                "test_case_id": 9,
                "run_name": "Candidate evaluation",
                "model_name": "large-v3-turbo",
                "test_case_title": "Support call",
                "audio_file_name": "support-call.wav",
            },
        )

    with LocalRunnerClient(
        api_base_url="https://ovrin.example.com",
        credential="ovrin_runner_test-credential",
        transport=httpx.MockTransport(handler),
    ) as client:
        context = client.get_asr_evaluation_context(
            job_public_id=job_public_id,
            claim_token="ovrin_claim_test-token",
        )

    assert context.project_id == 7
    assert context.evaluation_run_id == 42
    assert context.test_case_id == 9
    assert context.run_name == "Candidate evaluation"
    assert context.model_name == "large-v3-turbo"
    assert context.test_case_title == "Support call"
    assert context.audio_file_name == "support-call.wav"


def test_local_runner_client_rejects_invalid_asr_context_response():
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200,
            json={
                "project_id": 7,
                "evaluation_run_id": 42,
                "test_case_id": 9,
                "run_name": "Candidate evaluation",
                "model_name": "large-v3-turbo",
                "test_case_title": "Support call",
            },
        )
    )

    with LocalRunnerClient(
        api_base_url="https://ovrin.example.com",
        credential="ovrin_runner_test-credential",
        transport=transport,
    ) as client:
        with pytest.raises(LocalRunnerProtocolError):
            client.get_asr_evaluation_context(
                job_public_id=(
                    "20000000-0000-0000-0000-"
                    "000000000001"
                ),
                claim_token="ovrin_claim_test-token",
            )


def test_local_runner_client_downloads_asr_audio_atomically(
    tmp_path: Path,
):
    job_public_id = (
        "20000000-0000-0000-0000-000000000001"
    )
    destination = (
        tmp_path
        / "runner-work"
        / job_public_id
        / "support-call.wav"
    )

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == (
            f"/runners/jobs/{job_public_id}/asr/audio"
        )
        assert request.headers["authorization"] == (
            "Bearer ovrin_runner_test-credential"
        )
        assert request.headers["accept"] == "audio/*"
        assert request.read() == (
            b'{"claim_token":"ovrin_claim_test-token"}'
        )

        return httpx.Response(
            200,
            content=b"complete-runner-audio",
            headers={
                "content-type": "audio/wav",
            },
        )

    with LocalRunnerClient(
        api_base_url="https://ovrin.example.com",
        credential="ovrin_runner_test-credential",
        transport=httpx.MockTransport(handler),
    ) as client:
        downloaded_path = (
            client.download_asr_evaluation_audio(
                job_public_id=job_public_id,
                claim_token="ovrin_claim_test-token",
                destination=destination,
            )
        )

    assert downloaded_path == destination
    assert destination.read_bytes() == (
        b"complete-runner-audio"
    )
    assert list(
        destination.parent.glob(
            f".{destination.name}.*.part"
        )
    ) == []


def test_local_runner_audio_download_replaces_complete_file(
    tmp_path: Path,
):
    destination = tmp_path / "support-call.mp3"
    destination.write_bytes(b"previous-complete-audio")

    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200,
            content=b"new-complete-audio",
            headers={
                "content-type": (
                    "audio/mpeg; charset=binary"
                ),
            },
        )
    )

    with LocalRunnerClient(
        api_base_url="https://ovrin.example.com",
        credential="ovrin_runner_test-credential",
        transport=transport,
    ) as client:
        client.download_asr_evaluation_audio(
            job_public_id=(
                "20000000-0000-0000-0000-"
                "000000000001"
            ),
            claim_token="ovrin_claim_test-token",
            destination=destination,
        )

    assert destination.read_bytes() == (
        b"new-complete-audio"
    )
    assert list(
        destination.parent.glob(
            f".{destination.name}.*.part"
        )
    ) == []


def test_local_runner_audio_download_rejects_non_audio_response(
    tmp_path: Path,
):
    destination = tmp_path / "support-call.wav"
    destination.write_bytes(b"previous-complete-audio")

    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200,
            content=b'{"detail":"unexpected response"}',
            headers={
                "content-type": "application/json",
            },
        )
    )

    with LocalRunnerClient(
        api_base_url="https://ovrin.example.com",
        credential="ovrin_runner_test-credential",
        transport=transport,
    ) as client:
        with pytest.raises(LocalRunnerProtocolError):
            client.download_asr_evaluation_audio(
                job_public_id=(
                    "20000000-0000-0000-0000-"
                    "000000000001"
                ),
                claim_token="ovrin_claim_test-token",
                destination=destination,
            )

    assert destination.read_bytes() == (
        b"previous-complete-audio"
    )
    assert list(
        destination.parent.glob(
            f".{destination.name}.*.part"
        )
    ) == []


def test_local_runner_audio_download_preserves_file_on_interruption(
    tmp_path: Path,
):
    destination = tmp_path / "support-call.wav"
    destination.write_bytes(b"previous-complete-audio")

    class InterruptedAudioStream(httpx.SyncByteStream):
        def __init__(
            self,
            request: httpx.Request,
        ):
            self._request = request

        def __iter__(self):
            yield b"partial-audio"
            raise httpx.ReadError(
                "Audio stream was interrupted.",
                request=self._request,
            )

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            headers={
                "content-type": "audio/wav",
            },
            stream=InterruptedAudioStream(request),
        )

    with LocalRunnerClient(
        api_base_url="https://ovrin.example.com",
        credential="ovrin_runner_test-credential",
        transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(LocalRunnerRequestError):
            client.download_asr_evaluation_audio(
                job_public_id=(
                    "20000000-0000-0000-0000-"
                    "000000000001"
                ),
                claim_token="ovrin_claim_test-token",
                destination=destination,
            )

    assert destination.read_bytes() == (
        b"previous-complete-audio"
    )
    assert list(
        destination.parent.glob(
            f".{destination.name}.*.part"
        )
    ) == []


def test_local_runner_audio_download_maps_authentication_failure(
    tmp_path: Path,
):
    destination = tmp_path / "support-call.wav"

    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            401,
            json={
                "detail": (
                    "Runner credential is invalid "
                    "or unavailable."
                ),
            },
        )
    )

    with LocalRunnerClient(
        api_base_url="https://ovrin.example.com",
        credential="ovrin_runner_secret-value",
        transport=transport,
    ) as client:
        with pytest.raises(
            LocalRunnerAuthenticationError,
        ) as error:
            client.download_asr_evaluation_audio(
                job_public_id=(
                    "20000000-0000-0000-0000-"
                    "000000000001"
                ),
                claim_token="ovrin_claim_test-token",
                destination=destination,
            )

    assert not destination.exists()
    assert "ovrin_runner_secret-value" not in str(
        error.value
    )


def test_local_runner_audio_download_maps_api_failure(
    tmp_path: Path,
):
    destination = tmp_path / "support-call.wav"

    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            409,
            json={
                "detail": (
                    "Internal audio state must remain hidden."
                ),
            },
        )
    )

    with LocalRunnerClient(
        api_base_url="https://ovrin.example.com",
        credential="ovrin_runner_test-credential",
        transport=transport,
    ) as client:
        with pytest.raises(
            LocalRunnerAPIError,
        ) as error:
            client.download_asr_evaluation_audio(
                job_public_id=(
                    "20000000-0000-0000-0000-"
                    "000000000001"
                ),
                claim_token="ovrin_claim_test-token",
                destination=destination,
            )

    assert error.value.status_code == 409
    assert "Internal audio state" not in str(
        error.value
    )
    assert not destination.exists()


def test_local_runner_audio_download_rejects_directory_destination(
    tmp_path: Path,
):
    destination = tmp_path / "audio-directory"
    destination.mkdir()

    with LocalRunnerClient(
        api_base_url="https://ovrin.example.com",
        credential="ovrin_runner_test-credential",
        transport=httpx.MockTransport(
            lambda _request: pytest.fail(
                "HTTP request must not be sent."
            )
        ),
    ) as client:
        with pytest.raises(LocalRunnerInputError):
            client.download_asr_evaluation_audio(
                job_public_id=(
                    "20000000-0000-0000-0000-"
                    "000000000001"
                ),
                claim_token="ovrin_claim_test-token",
                destination=destination,
            )


@pytest.mark.parametrize(
    "job_public_id",
    [
        "",
        "   ",
        "../another-job",
        "job/another-job",
    ],
)
def test_local_runner_asr_methods_reject_unsafe_job_id(
    job_public_id: str,
    tmp_path: Path,
):
    with LocalRunnerClient(
        api_base_url="https://ovrin.example.com",
        credential="ovrin_runner_test-credential",
        transport=httpx.MockTransport(
            lambda _request: pytest.fail(
                "HTTP request must not be sent."
            )
        ),
    ) as client:
        with pytest.raises(LocalRunnerInputError):
            client.get_asr_evaluation_context(
                job_public_id=job_public_id,
                claim_token="ovrin_claim_test-token",
            )

        with pytest.raises(LocalRunnerInputError):
            client.download_asr_evaluation_audio(
                job_public_id=job_public_id,
                claim_token="ovrin_claim_test-token",
                destination=(
                    tmp_path / "support-call.wav"
                ),
            )



def test_local_runner_client_submits_asr_evaluation_result():
    job_public_id = (
        "20000000-0000-0000-0000-000000000001"
    )
    job_payload = build_job_payload()
    job_payload["status"] = "completed"
    job_payload["completed_at"] = NOW
    job_payload["lease_expires_at"] = None
    job_payload["result_payload"] = {
        "evaluation_result_id": 81,
        "evaluation_run_id": 42,
        "test_case_id": 9,
        "provider": "faster-whisper",
        "provider_metadata": {
            "device": "cpu",
            "language": "en",
        },
        "wer": 0.0,
        "cer": 0.0,
        "quality_label": "excellent",
    }

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == (
            f"/runners/jobs/{job_public_id}/asr/result"
        )
        assert request.headers["authorization"] == (
            "Bearer ovrin_runner_test-credential"
        )
        assert request.headers["accept"] == (
            "application/json"
        )
        assert request.read() == (
            b'{"claim_token":"ovrin_claim_test-token",'
            b'"generated_transcript":'
            b'"thank you for calling",'
            b'"provider":"faster-whisper",'
            b'"provider_metadata":'
            b'{"device":"cpu","language":"en"}}'
        )

        return httpx.Response(
            200,
            json={
                "status": "completed",
                "result": {
                    "id": 81,
                    "run_id": 42,
                    "test_case_id": 9,
                    "generated_transcript": (
                        "thank you for calling"
                    ),
                    "wer": 0.0,
                    "cer": 0.0,
                    "quality_label": "excellent",
                    "error_summary": (
                        "WER=0.000, CER=0.000. "
                        "Substitutions=0, insertions=0, "
                        "deletions=0."
                    ),
                    "created_at": NOW,
                },
                "job": job_payload,
                "provider": "faster-whisper",
                "provider_metadata": {
                    "device": "cpu",
                    "language": "en",
                },
            },
        )

    with LocalRunnerClient(
        api_base_url="https://ovrin.example.com",
        credential="ovrin_runner_test-credential",
        transport=httpx.MockTransport(handler),
    ) as client:
        response = (
            client.submit_asr_evaluation_result(
                job_public_id=job_public_id,
                claim_token="ovrin_claim_test-token",
                generated_transcript=(
                    "thank you for calling"
                ),
                provider="faster-whisper",
                provider_metadata={
                    "device": "cpu",
                    "language": "en",
                },
            )
        )

    assert response.status == "completed"
    assert response.result.id == 81
    assert response.result.run_id == 42
    assert response.result.test_case_id == 9
    assert response.result.generated_transcript == (
        "thank you for calling"
    )
    assert response.result.wer == pytest.approx(0.0)
    assert response.result.cer == pytest.approx(0.0)
    assert response.result.quality_label == "excellent"
    assert response.job.status == "completed"
    assert response.provider == "faster-whisper"
    assert response.provider_metadata == {
        "device": "cpu",
        "language": "en",
    }


@pytest.mark.parametrize(
    (
        "generated_transcript",
        "provider",
    ),
    [
        ("   ", "faster-whisper"),
        ("thank you for calling", "   "),
    ],
)
def test_local_runner_client_rejects_invalid_asr_result_input(
    generated_transcript: str,
    provider: str,
):
    with LocalRunnerClient(
        api_base_url="https://ovrin.example.com",
        credential="ovrin_runner_test-credential",
        transport=httpx.MockTransport(
            lambda _request: pytest.fail(
                "HTTP request must not be sent."
            )
        ),
    ) as client:
        with pytest.raises(LocalRunnerInputError):
            client.submit_asr_evaluation_result(
                job_public_id=(
                    "20000000-0000-0000-0000-"
                    "000000000001"
                ),
                claim_token="ovrin_claim_test-token",
                generated_transcript=generated_transcript,
                provider=provider,
            )


def test_local_runner_client_rejects_invalid_asr_result_response():
    job_payload = build_job_payload()
    job_payload["status"] = "completed"
    job_payload["completed_at"] = NOW
    job_payload["lease_expires_at"] = None

    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200,
            json={
                "status": "completed",
                "job": job_payload,
                "provider": "faster-whisper",
                "provider_metadata": {},
            },
        )
    )

    with LocalRunnerClient(
        api_base_url="https://ovrin.example.com",
        credential="ovrin_runner_test-credential",
        transport=transport,
    ) as client:
        with pytest.raises(LocalRunnerProtocolError):
            client.submit_asr_evaluation_result(
                job_public_id=(
                    "20000000-0000-0000-0000-"
                    "000000000001"
                ),
                claim_token="ovrin_claim_test-token",
                generated_transcript=(
                    "thank you for calling"
                ),
                provider="faster-whisper",
            )


def test_local_runner_asr_result_maps_api_failure():
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            409,
            json={
                "detail": (
                    "Internal ASR result state must remain "
                    "hidden."
                ),
            },
        )
    )

    with LocalRunnerClient(
        api_base_url="https://ovrin.example.com",
        credential="ovrin_runner_test-credential",
        transport=transport,
    ) as client:
        with pytest.raises(
            LocalRunnerAPIError,
        ) as error:
            client.submit_asr_evaluation_result(
                job_public_id=(
                    "20000000-0000-0000-0000-"
                    "000000000001"
                ),
                claim_token="ovrin_claim_test-token",
                generated_transcript=(
                    "thank you for calling"
                ),
                provider="faster-whisper",
            )

    assert error.value.status_code == 409
    assert "Internal ASR result state" not in str(
        error.value
    )


@pytest.mark.parametrize(
    "job_public_id",
    [
        "",
        "   ",
        "../another-job",
        "job/another-job",
    ],
)
def test_local_runner_asr_result_rejects_unsafe_job_id(
    job_public_id: str,
):
    with LocalRunnerClient(
        api_base_url="https://ovrin.example.com",
        credential="ovrin_runner_test-credential",
        transport=httpx.MockTransport(
            lambda _request: pytest.fail(
                "HTTP request must not be sent."
            )
        ),
    ) as client:
        with pytest.raises(LocalRunnerInputError):
            client.submit_asr_evaluation_result(
                job_public_id=job_public_id,
                claim_token="ovrin_claim_test-token",
                generated_transcript=(
                    "thank you for calling"
                ),
                provider="faster-whisper",
            )

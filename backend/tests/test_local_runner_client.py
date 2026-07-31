from datetime import UTC, datetime

import httpx
import pytest

from app.local_runner_client import (
    LocalRunnerAPIError,
    LocalRunnerAuthenticationError,
    LocalRunnerClient,
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

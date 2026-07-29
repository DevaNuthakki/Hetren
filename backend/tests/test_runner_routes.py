from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import runner_routes
from app.main import app
from app.runner_schemas import RunnerRegisterRequest
from app.runner_service import (
    RegisteredRunner,
    RegistrationTokenUnavailableError,
    RunnerRegistrationConflictError,
)


def build_request() -> RunnerRegisterRequest:
    return RunnerRegisterRequest(
        registration_token="ovrin_reg_test-token",
        name="Local ASR Runner",
        runner_version="0.1.0",
        capabilities=["asr", "cpu"],
        system_info={
            "platform": "darwin",
            "architecture": "arm64",
        },
    )


def build_registered_runner() -> RegisteredRunner:
    now = datetime.now(UTC)

    runner = SimpleNamespace(
        project_id=7,
        public_id="60c26299-7e7e-4470-873d-4aa7411bf1ec",
        name="Local ASR Runner",
        status="active",
        runner_version="0.1.0",
        capabilities=["asr", "cpu"],
        system_info={
            "platform": "darwin",
            "architecture": "arm64",
        },
        last_seen_at=None,
        revoked_at=None,
        created_at=now,
        updated_at=now,
    )

    return RegisteredRunner(
        credential="ovrin_runner_test-credential",
        runner=runner,
    )


def test_runner_registration_route_is_included_in_app():
    openapi_paths = app.openapi()["paths"]

    assert "/runners/register" in openapi_paths
    assert "post" in openapi_paths["/runners/register"]


def test_register_runner_endpoint_returns_one_time_credential(
    monkeypatch,
):
    registered = build_registered_runner()

    def fake_register_runner(_db, **kwargs):
        assert kwargs == {
            "registration_token": "ovrin_reg_test-token",
            "name": "Local ASR Runner",
            "runner_version": "0.1.0",
            "capabilities": ["asr", "cpu"],
            "system_info": {
                "platform": "darwin",
                "architecture": "arm64",
            },
        }
        return registered

    monkeypatch.setattr(
        runner_routes,
        "register_runner",
        fake_register_runner,
    )

    response = runner_routes.register_runner_endpoint(
        request=build_request(),
        db=object(),
    )

    assert response["credential"] == registered.credential
    assert response["runner"] is registered.runner


def test_register_runner_endpoint_hides_token_state(
    monkeypatch,
):
    def reject_registration(_db, **_kwargs):
        raise RegistrationTokenUnavailableError(
            "Specific internal token state."
        )

    monkeypatch.setattr(
        runner_routes,
        "register_runner",
        reject_registration,
    )

    with pytest.raises(HTTPException) as error:
        runner_routes.register_runner_endpoint(
            request=build_request(),
            db=object(),
        )

    assert error.value.status_code == 401
    assert error.value.detail == (
        "Registration token is invalid or unavailable."
    )
    assert "internal token state" not in error.value.detail


def test_register_runner_endpoint_maps_conflict_to_409(
    monkeypatch,
):
    def reject_registration(_db, **_kwargs):
        raise RunnerRegistrationConflictError(
            "Internal uniqueness constraint."
        )

    monkeypatch.setattr(
        runner_routes,
        "register_runner",
        reject_registration,
    )

    with pytest.raises(HTTPException) as error:
        runner_routes.register_runner_endpoint(
            request=build_request(),
            db=object(),
        )

    assert error.value.status_code == 409
    assert error.value.detail == (
        "Runner registration conflicts with an existing runner."
    )


def test_register_runner_endpoint_maps_invalid_metadata_to_422(
    monkeypatch,
):
    def reject_registration(_db, **_kwargs):
        raise ValueError(
            "Runner system_info must contain JSON-serializable values."
        )

    monkeypatch.setattr(
        runner_routes,
        "register_runner",
        reject_registration,
    )

    with pytest.raises(HTTPException) as error:
        runner_routes.register_runner_endpoint(
            request=build_request(),
            db=object(),
        )

    assert error.value.status_code == 422
    assert error.value.detail == (
        "Runner system_info must contain JSON-serializable values."
    )


def test_runner_heartbeat_route_is_included_in_app():
    openapi_paths = app.openapi()["paths"]

    assert "/runners/heartbeat" in openapi_paths
    assert "post" in openapi_paths["/runners/heartbeat"]


def test_runner_credential_dependency_requires_bearer_token():
    with pytest.raises(HTTPException) as error:
        runner_routes.get_runner_credential(None)

    assert error.value.status_code == 401
    assert error.value.detail == "Runner credential is required."
    assert error.value.headers == {
        "WWW-Authenticate": "Bearer"
    }


def test_runner_heartbeat_returns_authenticated_runner(
    monkeypatch,
):
    registered = build_registered_runner()

    def fake_record_heartbeat(_db, **kwargs):
        assert kwargs["credential"] == (
            "ovrin_runner_test-credential"
        )
        assert kwargs["runner_version"] == "0.2.0"
        assert kwargs["capabilities"] == ["asr", "cpu"]
        return registered.runner

    monkeypatch.setattr(
        runner_routes,
        "record_runner_heartbeat",
        fake_record_heartbeat,
    )

    request = runner_routes.RunnerHeartbeatRequest(
        runner_version="0.2.0",
        capabilities=["asr", "cpu"],
    )

    response = runner_routes.runner_heartbeat_endpoint(
        request=request,
        credential="ovrin_runner_test-credential",
        db=object(),
    )

    assert response["status"] == "ok"
    assert response["runner"] is registered.runner


def test_runner_heartbeat_maps_authentication_failure_to_401(
    monkeypatch,
):
    def reject_heartbeat(_db, **_kwargs):
        raise runner_routes.RunnerAuthenticationError(
            "Internal authentication state."
        )

    monkeypatch.setattr(
        runner_routes,
        "record_runner_heartbeat",
        reject_heartbeat,
    )

    request = runner_routes.RunnerHeartbeatRequest()

    with pytest.raises(HTTPException) as error:
        runner_routes.runner_heartbeat_endpoint(
            request=request,
            credential="invalid",
            db=object(),
        )

    assert error.value.status_code == 401
    assert error.value.detail == (
        "Runner credential is invalid or unavailable."
    )
    assert error.value.headers == {
        "WWW-Authenticate": "Bearer"
    }


def build_claimed_runner_job():
    from app.runner_job_service import ClaimedRunnerJob

    now = datetime.now(UTC)

    job = SimpleNamespace(
        public_id="10000000-0000-0000-0000-000000000001",
        project_id=7,
        name="ASR evaluation job",
        job_type="asr_evaluation",
        status="claimed",
        priority=10,
        required_capabilities=["asr"],
        input_payload={"run_id": 42},
        attempt_count=1,
        max_attempts=3,
        available_at=now,
        claimed_at=now,
        lease_expires_at=now + timedelta(minutes=10),
        started_at=None,
        completed_at=None,
        failed_at=None,
        cancelled_at=None,
        result_payload=None,
        error_message=None,
        created_at=now,
        updated_at=now,
    )

    return ClaimedRunnerJob(
        claim_token="ovrin_claim_test-token",
        job=job,
    )


def test_runner_job_claim_route_is_included_in_app():
    openapi_paths = app.openapi()["paths"]

    assert "/runners/jobs/claim" in openapi_paths
    assert "post" in openapi_paths["/runners/jobs/claim"]


def test_runner_job_claim_returns_claimed_job(
    monkeypatch,
):
    claimed = build_claimed_runner_job()

    def fake_claim_next_job(_db, **kwargs):
        assert kwargs["credential"] == (
            "ovrin_runner_test-credential"
        )
        assert kwargs["lease_duration"] == timedelta(
            seconds=600
        )
        return claimed

    monkeypatch.setattr(
        runner_routes,
        "claim_next_job",
        fake_claim_next_job,
    )

    request = runner_routes.RunnerJobClaimRequest(
        lease_seconds=600,
    )

    response = runner_routes.runner_job_claim_endpoint(
        request=request,
        credential="ovrin_runner_test-credential",
        db=object(),
    )

    assert response["status"] == "claimed"
    assert response["claim_token"] == claimed.claim_token
    assert response["job"] is claimed.job


def test_runner_job_claim_returns_idle_when_queue_is_empty(
    monkeypatch,
):
    monkeypatch.setattr(
        runner_routes,
        "claim_next_job",
        lambda _db, **_kwargs: None,
    )

    response = runner_routes.runner_job_claim_endpoint(
        request=runner_routes.RunnerJobClaimRequest(),
        credential="ovrin_runner_test-credential",
        db=object(),
    )

    assert response == {
        "status": "idle",
        "claim_token": None,
        "job": None,
    }


def test_runner_job_claim_maps_authentication_failure_to_401(
    monkeypatch,
):
    def reject_claim(_db, **_kwargs):
        raise runner_routes.RunnerAuthenticationError(
            "Internal authentication state."
        )

    monkeypatch.setattr(
        runner_routes,
        "claim_next_job",
        reject_claim,
    )

    with pytest.raises(HTTPException) as error:
        runner_routes.runner_job_claim_endpoint(
            request=runner_routes.RunnerJobClaimRequest(),
            credential="invalid",
            db=object(),
        )

    assert error.value.status_code == 401
    assert error.value.detail == (
        "Runner credential is invalid or unavailable."
    )
    assert error.value.headers == {
        "WWW-Authenticate": "Bearer"
    }


def test_runner_job_claim_maps_conflict_to_409(
    monkeypatch,
):
    def reject_claim(_db, **_kwargs):
        raise runner_routes.RunnerJobClaimConflictError(
            "Internal database conflict."
        )

    monkeypatch.setattr(
        runner_routes,
        "claim_next_job",
        reject_claim,
    )

    with pytest.raises(HTTPException) as error:
        runner_routes.runner_job_claim_endpoint(
            request=runner_routes.RunnerJobClaimRequest(),
            credential="ovrin_runner_test-credential",
            db=object(),
        )

    assert error.value.status_code == 409
    assert error.value.detail == (
        "Runner job could not be claimed."
    )


def test_runner_job_claim_maps_invalid_lease_to_422(
    monkeypatch,
):
    def reject_claim(_db, **_kwargs):
        raise ValueError(
            "Runner job lease duration is invalid."
        )

    monkeypatch.setattr(
        runner_routes,
        "claim_next_job",
        reject_claim,
    )

    with pytest.raises(HTTPException) as error:
        runner_routes.runner_job_claim_endpoint(
            request=runner_routes.RunnerJobClaimRequest(),
            credential="ovrin_runner_test-credential",
            db=object(),
        )

    assert error.value.status_code == 422
    assert error.value.detail == (
        "Runner job lease duration is invalid."
    )


def test_runner_job_transition_routes_are_included_in_app():
    openapi_paths = app.openapi()["paths"]

    for route in (
        "/runners/jobs/{job_public_id}/start",
        "/runners/jobs/{job_public_id}/complete",
        "/runners/jobs/{job_public_id}/fail",
    ):
        assert route in openapi_paths
        assert "post" in openapi_paths[route]


def test_runner_job_start_returns_running_job(
    monkeypatch,
):
    claimed = build_claimed_runner_job()
    claimed.job.status = "running"
    claimed.job.started_at = datetime.now(UTC)

    def fake_start_job(_db, **kwargs):
        assert kwargs == {
            "credential": "ovrin_runner_test-credential",
            "job_public_id": claimed.job.public_id,
            "claim_token": "ovrin_claim_test-token",
        }
        return claimed.job

    monkeypatch.setattr(
        runner_routes,
        "start_job",
        fake_start_job,
    )

    response = runner_routes.runner_job_start_endpoint(
        job_public_id=claimed.job.public_id,
        request=runner_routes.RunnerJobStartRequest(
            claim_token="ovrin_claim_test-token",
        ),
        credential="ovrin_runner_test-credential",
        db=object(),
    )

    assert response["status"] == "running"
    assert response["job"] is claimed.job


def test_runner_job_complete_returns_completed_job(
    monkeypatch,
):
    claimed = build_claimed_runner_job()
    claimed.job.status = "completed"
    claimed.job.completed_at = datetime.now(UTC)
    claimed.job.result_payload = {"evaluation_run_id": 42}
    claimed.job.lease_expires_at = None

    def fake_complete_job(_db, **kwargs):
        assert kwargs == {
            "credential": "ovrin_runner_test-credential",
            "job_public_id": claimed.job.public_id,
            "claim_token": "ovrin_claim_test-token",
            "result_payload": {"evaluation_run_id": 42},
        }
        return claimed.job

    monkeypatch.setattr(
        runner_routes,
        "complete_job",
        fake_complete_job,
    )

    response = runner_routes.runner_job_complete_endpoint(
        job_public_id=claimed.job.public_id,
        request=runner_routes.RunnerJobCompleteRequest(
            claim_token="ovrin_claim_test-token",
            result_payload={"evaluation_run_id": 42},
        ),
        credential="ovrin_runner_test-credential",
        db=object(),
    )

    assert response["status"] == "completed"
    assert response["job"] is claimed.job


def test_runner_job_fail_returns_failed_job(
    monkeypatch,
):
    claimed = build_claimed_runner_job()
    claimed.job.status = "failed"
    claimed.job.failed_at = datetime.now(UTC)
    claimed.job.error_message = "Runner process failed."
    claimed.job.lease_expires_at = None

    def fake_fail_job(_db, **kwargs):
        assert kwargs == {
            "credential": "ovrin_runner_test-credential",
            "job_public_id": claimed.job.public_id,
            "claim_token": "ovrin_claim_test-token",
            "error_message": "Runner process failed.",
        }
        return claimed.job

    monkeypatch.setattr(
        runner_routes,
        "fail_job",
        fake_fail_job,
    )

    response = runner_routes.runner_job_fail_endpoint(
        job_public_id=claimed.job.public_id,
        request=runner_routes.RunnerJobFailRequest(
            claim_token="ovrin_claim_test-token",
            error_message="Runner process failed.",
        ),
        credential="ovrin_runner_test-credential",
        db=object(),
    )

    assert response["status"] == "failed"
    assert response["job"] is claimed.job


def test_runner_job_start_maps_authentication_failure_to_401(
    monkeypatch,
):
    def reject_start(_db, **_kwargs):
        raise runner_routes.RunnerAuthenticationError(
            "Internal authentication state."
        )

    monkeypatch.setattr(
        runner_routes,
        "start_job",
        reject_start,
    )

    with pytest.raises(HTTPException) as error:
        runner_routes.runner_job_start_endpoint(
            job_public_id=(
                "10000000-0000-0000-0000-000000000001"
            ),
            request=runner_routes.RunnerJobStartRequest(
                claim_token="ovrin_claim_test-token",
            ),
            credential="invalid",
            db=object(),
        )

    assert error.value.status_code == 401
    assert error.value.detail == (
        "Runner credential is invalid or unavailable."
    )


def test_runner_job_start_hides_invalid_claim_state(
    monkeypatch,
):
    def reject_start(_db, **_kwargs):
        raise runner_routes.RunnerJobClaimUnavailableError(
            "Specific internal claim state."
        )

    monkeypatch.setattr(
        runner_routes,
        "start_job",
        reject_start,
    )

    with pytest.raises(HTTPException) as error:
        runner_routes.runner_job_start_endpoint(
            job_public_id=(
                "10000000-0000-0000-0000-000000000001"
            ),
            request=runner_routes.RunnerJobStartRequest(
                claim_token="ovrin_claim_test-token",
            ),
            credential="ovrin_runner_test-credential",
            db=object(),
        )

    assert error.value.status_code == 409
    assert error.value.detail == (
        "Runner job claim is invalid or unavailable."
    )
    assert "internal claim state" not in error.value.detail


def test_runner_job_complete_maps_transition_failure_to_409(
    monkeypatch,
):
    def reject_completion(_db, **_kwargs):
        raise runner_routes.RunnerJobTransitionUnavailableError(
            "Specific internal lifecycle state."
        )

    monkeypatch.setattr(
        runner_routes,
        "complete_job",
        reject_completion,
    )

    with pytest.raises(HTTPException) as error:
        runner_routes.runner_job_complete_endpoint(
            job_public_id=(
                "10000000-0000-0000-0000-000000000001"
            ),
            request=runner_routes.RunnerJobCompleteRequest(
                claim_token="ovrin_claim_test-token",
            ),
            credential="ovrin_runner_test-credential",
            db=object(),
        )

    assert error.value.status_code == 409
    assert error.value.detail == (
        "Runner job transition is invalid or unavailable."
    )


def test_runner_job_fail_maps_invalid_error_to_422(
    monkeypatch,
):
    def reject_failure(_db, **_kwargs):
        raise ValueError(
            "Runner job error message must not be empty."
        )

    monkeypatch.setattr(
        runner_routes,
        "fail_job",
        reject_failure,
    )

    with pytest.raises(HTTPException) as error:
        runner_routes.runner_job_fail_endpoint(
            job_public_id=(
                "10000000-0000-0000-0000-000000000001"
            ),
            request=runner_routes.RunnerJobFailRequest(
                claim_token="ovrin_claim_test-token",
                error_message="Temporary valid value",
            ),
            credential="ovrin_runner_test-credential",
            db=object(),
        )

    assert error.value.status_code == 422
    assert error.value.detail == (
        "Runner job error message must not be empty."
    )


def test_runner_job_renew_route_is_included_in_app():
    openapi_paths = app.openapi()["paths"]

    route = "/runners/jobs/{job_public_id}/renew"

    assert route in openapi_paths
    assert "post" in openapi_paths[route]


def test_runner_job_renew_returns_renewed_job(
    monkeypatch,
):
    claimed = build_claimed_runner_job()

    def fake_renew_job_lease(_db, **kwargs):
        assert kwargs == {
            "credential": "ovrin_runner_test-credential",
            "job_public_id": claimed.job.public_id,
            "claim_token": "ovrin_claim_test-token",
            "lease_duration": timedelta(seconds=600),
        }
        return claimed.job

    monkeypatch.setattr(
        runner_routes,
        "renew_job_lease",
        fake_renew_job_lease,
    )

    response = runner_routes.runner_job_renew_endpoint(
        job_public_id=claimed.job.public_id,
        request=runner_routes.RunnerJobRenewRequest(
            claim_token="ovrin_claim_test-token",
            lease_seconds=600,
        ),
        credential="ovrin_runner_test-credential",
        db=object(),
    )

    assert response["status"] == "renewed"
    assert response["job"] is claimed.job


def test_runner_job_renew_maps_authentication_failure_to_401(
    monkeypatch,
):
    def reject_renewal(_db, **_kwargs):
        raise runner_routes.RunnerAuthenticationError(
            "Internal authentication state."
        )

    monkeypatch.setattr(
        runner_routes,
        "renew_job_lease",
        reject_renewal,
    )

    with pytest.raises(HTTPException) as error:
        runner_routes.runner_job_renew_endpoint(
            job_public_id=(
                "10000000-0000-0000-0000-000000000001"
            ),
            request=runner_routes.RunnerJobRenewRequest(
                claim_token="ovrin_claim_test-token",
            ),
            credential="invalid",
            db=object(),
        )

    assert error.value.status_code == 401
    assert error.value.detail == (
        "Runner credential is invalid or unavailable."
    )


def test_runner_job_renew_hides_invalid_claim_state(
    monkeypatch,
):
    def reject_renewal(_db, **_kwargs):
        raise runner_routes.RunnerJobClaimUnavailableError(
            "Specific internal claim state."
        )

    monkeypatch.setattr(
        runner_routes,
        "renew_job_lease",
        reject_renewal,
    )

    with pytest.raises(HTTPException) as error:
        runner_routes.runner_job_renew_endpoint(
            job_public_id=(
                "10000000-0000-0000-0000-000000000001"
            ),
            request=runner_routes.RunnerJobRenewRequest(
                claim_token="ovrin_claim_test-token",
            ),
            credential="ovrin_runner_test-credential",
            db=object(),
        )

    assert error.value.status_code == 409
    assert error.value.detail == (
        "Runner job claim is invalid or unavailable."
    )
    assert "internal claim state" not in error.value.detail


def test_runner_job_renew_maps_transition_failure_to_409(
    monkeypatch,
):
    def reject_renewal(_db, **_kwargs):
        raise runner_routes.RunnerJobTransitionUnavailableError(
            "Specific internal transition state."
        )

    monkeypatch.setattr(
        runner_routes,
        "renew_job_lease",
        reject_renewal,
    )

    with pytest.raises(HTTPException) as error:
        runner_routes.runner_job_renew_endpoint(
            job_public_id=(
                "10000000-0000-0000-0000-000000000001"
            ),
            request=runner_routes.RunnerJobRenewRequest(
                claim_token="ovrin_claim_test-token",
            ),
            credential="ovrin_runner_test-credential",
            db=object(),
        )

    assert error.value.status_code == 409
    assert error.value.detail == (
        "Runner job transition is invalid or unavailable."
    )


def test_runner_job_renew_maps_invalid_duration_to_422(
    monkeypatch,
):
    def reject_renewal(_db, **_kwargs):
        raise ValueError(
            "Runner job lease duration is invalid."
        )

    monkeypatch.setattr(
        runner_routes,
        "renew_job_lease",
        reject_renewal,
    )

    with pytest.raises(HTTPException) as error:
        runner_routes.runner_job_renew_endpoint(
            job_public_id=(
                "10000000-0000-0000-0000-000000000001"
            ),
            request=runner_routes.RunnerJobRenewRequest(
                claim_token="ovrin_claim_test-token",
            ),
            credential="ovrin_runner_test-credential",
            db=object(),
        )

    assert error.value.status_code == 422
    assert error.value.detail == (
        "Runner job lease duration is invalid."
    )

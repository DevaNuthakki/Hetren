from datetime import UTC, datetime
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

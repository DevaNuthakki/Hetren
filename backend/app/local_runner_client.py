from __future__ import annotations

from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.runner_config import LocalRunnerSettings
from app.runner_schemas import (
    RunnerHeartbeatResponse,
    RunnerJobClaimResponse,
    RunnerJobCompleteRequest,
    RunnerJobControlStatusResponse,
    RunnerJobFailRequest,
    RunnerJobLeaseRenewalResponse,
    RunnerJobLogAppendRequest,
    RunnerJobLogAppendResponse,
    RunnerJobRenewRequest,
    RunnerJobStartRequest,
    RunnerJobTransitionResponse,
)


ResponseModel = TypeVar(
    "ResponseModel",
    bound=BaseModel,
)


class LocalRunnerClientError(Exception):
    """Base exception for standalone runner API operations."""


class LocalRunnerAuthenticationError(
    LocalRunnerClientError
):
    """Raised when the runner credential is rejected."""


class LocalRunnerAPIError(LocalRunnerClientError):
    """Raised when the Ovrin API rejects a runner request."""

    def __init__(self, status_code: int):
        self.status_code = status_code
        super().__init__(
            "Ovrin runner API request failed with "
            f"HTTP {status_code}."
        )


class LocalRunnerRequestError(LocalRunnerClientError):
    """Raised when the Ovrin API cannot be reached."""


class LocalRunnerProtocolError(LocalRunnerClientError):
    """Raised when the Ovrin API returns an invalid response."""


class LocalRunnerInputError(LocalRunnerClientError):
    """Raised when a local runner request is invalid."""


class LocalRunnerClient:
    """
    Typed HTTP client for the standalone local or CI runner.

    Runner credentials are sent only through the Bearer authorization
    header and are never included in exception messages.
    """

    def __init__(
        self,
        *,
        api_base_url: str,
        credential: str,
        timeout_seconds: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ):
        normalized_api_url = api_base_url.strip().rstrip("/")
        normalized_credential = credential.strip()

        if not normalized_api_url:
            raise ValueError(
                "Runner API base URL must not be empty."
            )

        if not normalized_credential:
            raise ValueError(
                "Runner credential must not be empty."
            )

        if timeout_seconds <= 0:
            raise ValueError(
                "Runner request timeout must be greater than zero."
            )

        self._client = httpx.Client(
            base_url=normalized_api_url,
            timeout=timeout_seconds,
            headers={
                "Authorization": (
                    f"Bearer {normalized_credential}"
                ),
                "Accept": "application/json",
            },
            transport=transport,
        )

    def __enter__(self) -> LocalRunnerClient:
        return self

    def __exit__(
        self,
        _exception_type,
        _exception,
        _traceback,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    @staticmethod
    def _validate_job_public_id(
        job_public_id: str,
    ) -> str:
        normalized = job_public_id.strip()

        if not normalized:
            raise LocalRunnerInputError(
                "Runner job public ID must not be empty."
            )

        if "/" in normalized or "\\" in normalized:
            raise LocalRunnerInputError(
                "Runner job public ID is invalid."
            )

        return normalized

    @staticmethod
    def _validate_request_payload(
        *,
        request_model: type[BaseModel],
        payload: dict[str, object],
    ) -> dict[str, object]:
        try:
            request = request_model.model_validate(
                payload
            )
        except ValidationError as exc:
            raise LocalRunnerInputError(
                "Local runner request payload is invalid."
            ) from exc

        return request.model_dump(mode="json")

    def _post(
        self,
        *,
        path: str,
        payload: dict[str, object],
        response_model: type[ResponseModel],
    ) -> ResponseModel:
        try:
            response = self._client.post(
                path,
                json=payload,
            )
        except httpx.TimeoutException as exc:
            raise LocalRunnerRequestError(
                "Ovrin runner API request timed out."
            ) from exc
        except httpx.RequestError as exc:
            raise LocalRunnerRequestError(
                "Ovrin runner API could not be reached."
            ) from exc

        if response.status_code == 401:
            raise LocalRunnerAuthenticationError(
                "Runner credential is invalid or unavailable."
            )

        if response.is_error:
            raise LocalRunnerAPIError(
                response.status_code
            )

        try:
            response_payload = response.json()
            return response_model.model_validate(
                response_payload
            )
        except (ValueError, ValidationError) as exc:
            raise LocalRunnerProtocolError(
                "Ovrin runner API returned an invalid response."
            ) from exc

    def heartbeat(
        self,
        *,
        runner_version: str,
        capabilities: list[str],
        system_info: dict[str, object] | None = None,
    ) -> RunnerHeartbeatResponse:
        return self._post(
            path="/runners/heartbeat",
            payload={
                "runner_version": runner_version,
                "capabilities": list(capabilities),
                "system_info": dict(system_info or {}),
            },
            response_model=RunnerHeartbeatResponse,
        )

    def claim_next_job(
        self,
        *,
        lease_seconds: int,
    ) -> RunnerJobClaimResponse:
        return self._post(
            path="/runners/jobs/claim",
            payload={
                "lease_seconds": lease_seconds,
            },
            response_model=RunnerJobClaimResponse,
        )

    def start_job(
        self,
        *,
        job_public_id: str,
        claim_token: str,
    ) -> RunnerJobTransitionResponse:
        normalized_job_id = self._validate_job_public_id(
            job_public_id
        )
        payload = self._validate_request_payload(
            request_model=RunnerJobStartRequest,
            payload={
                "claim_token": claim_token,
            },
        )

        return self._post(
            path=(
                f"/runners/jobs/{normalized_job_id}/start"
            ),
            payload=payload,
            response_model=RunnerJobTransitionResponse,
        )

    def get_job_control_status(
        self,
        *,
        job_public_id: str,
    ) -> RunnerJobControlStatusResponse:
        normalized_job_id = self._validate_job_public_id(
            job_public_id
        )

        return self._post(
            path=(
                f"/runners/jobs/{normalized_job_id}/control"
            ),
            payload={},
            response_model=RunnerJobControlStatusResponse,
        )

    def renew_job_lease(
        self,
        *,
        job_public_id: str,
        claim_token: str,
        lease_seconds: int,
    ) -> RunnerJobLeaseRenewalResponse:
        normalized_job_id = self._validate_job_public_id(
            job_public_id
        )
        payload = self._validate_request_payload(
            request_model=RunnerJobRenewRequest,
            payload={
                "claim_token": claim_token,
                "lease_seconds": lease_seconds,
            },
        )

        return self._post(
            path=(
                f"/runners/jobs/{normalized_job_id}/renew"
            ),
            payload=payload,
            response_model=RunnerJobLeaseRenewalResponse,
        )

    def append_job_logs(
        self,
        *,
        job_public_id: str,
        claim_token: str,
        entries: list[dict[str, object]],
    ) -> RunnerJobLogAppendResponse:
        normalized_job_id = self._validate_job_public_id(
            job_public_id
        )
        payload = self._validate_request_payload(
            request_model=RunnerJobLogAppendRequest,
            payload={
                "claim_token": claim_token,
                "entries": entries,
            },
        )

        return self._post(
            path=f"/runners/jobs/{normalized_job_id}/logs",
            payload=payload,
            response_model=RunnerJobLogAppendResponse,
        )

    def complete_job(
        self,
        *,
        job_public_id: str,
        claim_token: str,
        result_payload: dict[str, object] | None = None,
    ) -> RunnerJobTransitionResponse:
        normalized_job_id = self._validate_job_public_id(
            job_public_id
        )
        payload = self._validate_request_payload(
            request_model=RunnerJobCompleteRequest,
            payload={
                "claim_token": claim_token,
                "result_payload": dict(
                    result_payload or {}
                ),
            },
        )

        return self._post(
            path=(
                f"/runners/jobs/{normalized_job_id}/complete"
            ),
            payload=payload,
            response_model=RunnerJobTransitionResponse,
        )

    def fail_job(
        self,
        *,
        job_public_id: str,
        claim_token: str,
        error_message: str,
    ) -> RunnerJobTransitionResponse:
        normalized_job_id = self._validate_job_public_id(
            job_public_id
        )
        payload = self._validate_request_payload(
            request_model=RunnerJobFailRequest,
            payload={
                "claim_token": claim_token,
                "error_message": error_message,
            },
        )

        return self._post(
            path=f"/runners/jobs/{normalized_job_id}/fail",
            payload=payload,
            response_model=RunnerJobTransitionResponse,
        )


def build_local_runner_client(
    settings: LocalRunnerSettings,
    *,
    transport: httpx.BaseTransport | None = None,
) -> LocalRunnerClient:
    return LocalRunnerClient(
        api_base_url=settings.api_base_url,
        credential=settings.credential.get_secret_value(),
        timeout_seconds=settings.request_timeout_seconds,
        transport=transport,
    )

from __future__ import annotations

from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.runner_config import LocalRunnerSettings
from app.runner_schemas import (
    RunnerHeartbeatResponse,
    RunnerJobClaimResponse,
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

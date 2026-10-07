"""Deterministic capture and replay primitives for structured model output.

This module deliberately does not call a model provider.

A future live-provider adapter may create ModelRequest instances, call a real
model, and persist a ModelCapture produced here. Normal tests and CI can then
replay the captured response without network access or credentials.

The records preserve request/response provenance and deterministic JSON
normalization. They do not establish that a provider response is correct,
trustworthy, independent, safe, or suitable for deployment.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
import json
from typing import Any

from packages.contracts import (
    ContractError,
    canonical_sha256,
)


_JSONValue = (
    None
    | bool
    | int
    | float
    | str
    | list["_JSONValue"]
    | dict[str, "_JSONValue"]
)


def _require_text(
    value: object,
    name: str,
) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
    ):
        raise ContractError(
            f"{name} must be non-empty text"
        )

    return value


def _require_sha256(
    value: object,
    name: str,
) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(
            character not in "0123456789abcdef"
            for character in value
        )
    ):
        raise ContractError(
            f"{name} must be a lowercase SHA-256 digest"
        )

    return value


def _normalize_json_value(
    value: Any,
    *,
    path: str,
) -> _JSONValue:
    """Return a strictly JSON-compatible value with string object keys."""
    if value is None:
        return None

    if isinstance(value, bool):
        return value

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        if value != value:
            raise ContractError(
                f"{path} contains NaN"
            )

        if value in (
            float("inf"),
            float("-inf"),
        ):
            raise ContractError(
                f"{path} contains infinity"
            )

        return value

    if isinstance(value, str):
        return value

    if isinstance(value, list):
        return [
            _normalize_json_value(
                item,
                path=f"{path}[{index}]",
            )
            for index, item in enumerate(value)
        ]

    if isinstance(value, dict):
        normalized: dict[str, _JSONValue] = {}

        for key, item in value.items():
            if not isinstance(key, str):
                raise ContractError(
                    f"{path} contains a non-string object key"
                )

            normalized[key] = (
                _normalize_json_value(
                    item,
                    path=f"{path}.{key}",
                )
            )

        return normalized

    raise ContractError(
        f"{path} contains a non-JSON value"
    )


def _require_json_object(
    value: object,
    name: str,
) -> dict[str, _JSONValue]:
    normalized = _normalize_json_value(
        value,
        path=name,
    )

    if not isinstance(normalized, dict):
        raise ContractError(
            f"{name} must be a JSON object"
        )

    return normalized


@dataclass(frozen=True)
class ModelRequest:
    """One exact structured-output model request.

    generation_parameters intentionally contain non-secret inference settings
    only. Credentials, API keys, authorization headers, and private endpoints
    do not belong in this record.
    """

    provider: str
    model: str

    system_prompt: str
    user_prompt: str

    response_schema_name: str
    response_schema: dict[str, _JSONValue]

    generation_parameters: dict[str, _JSONValue]

    def __post_init__(self) -> None:
        for name in (
            "provider",
            "model",
            "system_prompt",
            "user_prompt",
            "response_schema_name",
        ):
            _require_text(
                getattr(self, name),
                name,
            )

        normalized_schema = (
            _require_json_object(
                self.response_schema,
                "response_schema",
            )
        )

        normalized_parameters = (
            _require_json_object(
                self.generation_parameters,
                "generation_parameters",
            )
        )

        object.__setattr__(
            self,
            "response_schema",
            normalized_schema,
        )

        object.__setattr__(
            self,
            "generation_parameters",
            normalized_parameters,
        )

    def canonical_payload(
        self,
    ) -> dict[str, object]:
        return {
            "record_type": "ModelRequest",
            "schema_version": 1,
            "provider": self.provider,
            "model": self.model,
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
            "response_schema_name": (
                self.response_schema_name
            ),
            "response_schema": (
                self.response_schema
            ),
            "generation_parameters": (
                self.generation_parameters
            ),
        }

    @property
    def request_sha256(self) -> str:
        return canonical_sha256(
            self.canonical_payload()
        )


@dataclass(frozen=True)
class ModelCapture:
    """Captured structured model response bound to one exact request."""

    provider: str
    model: str

    request_sha256: str

    raw_response_text: str

    normalized_response: dict[str, _JSONValue]

    normalizer_id: str
    normalizer_version: str

    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "provider",
            "model",
            "raw_response_text",
            "normalizer_id",
            "normalizer_version",
        ):
            _require_text(
                getattr(self, name),
                name,
            )

        _require_sha256(
            self.request_sha256,
            "request_sha256",
        )

        normalized_response = (
            _require_json_object(
                self.normalized_response,
                "normalized_response",
            )
        )

        object.__setattr__(
            self,
            "normalized_response",
            normalized_response,
        )

        if not isinstance(
            self.limitations,
            tuple,
        ):
            raise ContractError(
                "limitations must be a tuple"
            )

        for limitation in self.limitations:
            _require_text(
                limitation,
                "limitation",
            )

    @property
    def raw_response_sha256(
        self,
    ) -> str:
        return canonical_sha256(
            {
                "raw_response_text":
                    self.raw_response_text,
            }
        )

    @property
    def normalized_response_sha256(
        self,
    ) -> str:
        return canonical_sha256(
            self.normalized_response
        )

    def canonical_payload(
        self,
    ) -> dict[str, object]:
        payload = {
            field.name: getattr(
                self,
                field.name,
            )
            for field in fields(self)
        }

        return {
            "record_type": "ModelCapture",
            "schema_version": 1,
            **payload,
            "raw_response_sha256": (
                self.raw_response_sha256
            ),
            "normalized_response_sha256": (
                self.normalized_response_sha256
            ),
        }

    @property
    def capture_sha256(
        self,
    ) -> str:
        return canonical_sha256(
            self.canonical_payload()
        )

    def validate_against(
        self,
        request: ModelRequest,
    ) -> None:
        if not isinstance(
            request,
            ModelRequest,
        ):
            raise ContractError(
                "request must be a ModelRequest"
            )

        if self.provider != request.provider:
            raise ContractError(
                "capture provider does not match request"
            )

        if self.model != request.model:
            raise ContractError(
                "capture model does not match request"
            )

        if (
            self.request_sha256
            != request.request_sha256
        ):
            raise ContractError(
                "capture request digest does not match request"
            )


def parse_json_response(
    raw_response_text: str,
) -> dict[str, _JSONValue]:
    """Parse one provider response body expected to contain a JSON object."""
    _require_text(
        raw_response_text,
        "raw_response_text",
    )

    try:
        decoded = json.loads(
            raw_response_text
        )
    except json.JSONDecodeError as exc:
        raise ContractError(
            "model response is not valid JSON"
        ) from exc

    return _require_json_object(
        decoded,
        "model_response",
    )


def capture_json_response(
    *,
    request: ModelRequest,
    raw_response_text: str,
    normalizer_id: str = "strict-json-object",
    normalizer_version: str = "1",
) -> ModelCapture:
    """Capture a JSON response without calling or trusting any provider."""
    if not isinstance(
        request,
        ModelRequest,
    ):
        raise ContractError(
            "request must be a ModelRequest"
        )

    normalized_response = (
        parse_json_response(
            raw_response_text
        )
    )

    return ModelCapture(
        provider=request.provider,
        model=request.model,
        request_sha256=(
            request.request_sha256
        ),
        raw_response_text=(
            raw_response_text
        ),
        normalized_response=(
            normalized_response
        ),
        normalizer_id=normalizer_id,
        normalizer_version=(
            normalizer_version
        ),
        limitations=(
            "capture does not prove provider identity",
            "capture does not prove model-response correctness",
            "capture contains no authorization decision",
            "replay is not a fresh model inference",
        ),
    )


def replay_json_capture(
    *,
    request: ModelRequest,
    capture: ModelCapture,
) -> dict[str, _JSONValue]:
    """Replay and revalidate a previously captured JSON response."""
    if not isinstance(
        capture,
        ModelCapture,
    ):
        raise ContractError(
            "capture must be a ModelCapture"
        )

    capture.validate_against(
        request
    )

    reparsed = parse_json_response(
        capture.raw_response_text
    )

    if (
        canonical_sha256(reparsed)
        != capture.normalized_response_sha256
    ):
        raise ContractError(
            "captured raw response no longer matches "
            "the normalized response"
        )

    return reparsed


__all__ = [
    "ModelCapture",
    "ModelRequest",
    "capture_json_response",
    "parse_json_response",
    "replay_json_capture",
]

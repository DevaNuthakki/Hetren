"""Optional OpenAI Responses API adapter for structured model capture.

This module is the provider-specific live boundary for P08.2.

Normal Hetren tests and CI do not need network access or credentials. Callers
may inject a transport for deterministic testing, or use the default HTTPS
transport explicitly for a live request.

The API key is supplied by the caller and is never stored in ModelRequest,
ModelCapture, OpenAIResponsesResult, request payloads, or evidence hashes.

A successful HTTP response is provider-reported evidence. It does not by itself
prove provider identity, model identity, output correctness, safety,
independence, authorization, or deployment suitability.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import hashlib
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from packages.contracts import (
    ContractError,
    canonical_sha256,
)
from packages.model_capture import (
    ModelCapture,
    ModelRequest,
    capture_json_response,
)


_OPENAI_RESPONSES_ENDPOINT = (
    "https://api.openai.com/v1/responses"
)

_PROVIDER = "openai"

Transport = Callable[
    [
        str,
        bytes,
        dict[str, str],
        float,
    ],
    bytes,
]


class OpenAIResponsesError(RuntimeError):
    """Provider adapter failure without credential disclosure."""


class OpenAIResponsesRefusal(OpenAIResponsesError):
    """The model returned an explicit refusal instead of schema output."""


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


def _require_optional_nonnegative_int(
    value: object,
    name: str,
) -> int | None:
    if value is None:
        return None

    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < 0
    ):
        raise ContractError(
            f"{name} must be a non-negative integer or None"
        )

    return value


@dataclass(frozen=True)
class OpenAIResponsesResult:
    """Provider-reported response metadata plus Hetren's bounded capture."""

    response_id: str
    response_model: str
    status: str

    request_payload_sha256: str
    response_body_sha256: str

    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None

    capture: ModelCapture

    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "response_id",
            "response_model",
            "status",
        ):
            _require_text(
                getattr(self, name),
                name,
            )

        if self.status != "completed":
            raise ContractError(
                "OpenAIResponsesResult requires completed status"
            )

        _require_sha256(
            self.request_payload_sha256,
            "request_payload_sha256",
        )

        _require_sha256(
            self.response_body_sha256,
            "response_body_sha256",
        )

        for name in (
            "input_tokens",
            "output_tokens",
            "total_tokens",
        ):
            _require_optional_nonnegative_int(
                getattr(self, name),
                name,
            )

        if not isinstance(
            self.capture,
            ModelCapture,
        ):
            raise ContractError(
                "capture must be a ModelCapture"
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

    def canonical_payload(
        self,
    ) -> dict[str, object]:
        return {
            "record_type":
                "OpenAIResponsesResult",
            "schema_version": 1,
            "response_id":
                self.response_id,
            "response_model":
                self.response_model,
            "status":
                self.status,
            "request_payload_sha256":
                self.request_payload_sha256,
            "response_body_sha256":
                self.response_body_sha256,
            "input_tokens":
                self.input_tokens,
            "output_tokens":
                self.output_tokens,
            "total_tokens":
                self.total_tokens,
            "capture_sha256":
                self.capture.capture_sha256,
            "limitations":
                self.limitations,
        }

    @property
    def evidence_sha256(
        self,
    ) -> str:
        return canonical_sha256(
            self.canonical_payload()
        )


def build_openai_responses_payload(
    request: ModelRequest,
) -> dict[str, object]:
    """Build one stateless strict-structured-output Responses request."""
    if not isinstance(
        request,
        ModelRequest,
    ):
        raise ContractError(
            "request must be a ModelRequest"
        )

    if request.provider != _PROVIDER:
        raise ContractError(
            "OpenAI adapter requires provider='openai'"
        )

    reserved = {
        "model",
        "input",
        "text",
        "store",
        "stream",
    }

    overlap = (
        reserved
        & set(
            request.generation_parameters
        )
    )

    if overlap:
        raise ContractError(
            "generation_parameters cannot override "
            "provider-controlled fields: "
            + ", ".join(
                sorted(overlap)
            )
        )

    payload: dict[str, object] = {
        "model": request.model,
        "input": [
            {
                "role": "system",
                "content":
                    request.system_prompt,
            },
            {
                "role": "user",
                "content":
                    request.user_prompt,
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name":
                    request.response_schema_name,
                "strict": True,
                "schema":
                    request.response_schema,
            },
        },
        "store": False,
        "stream": False,
    }

    payload.update(
        request.generation_parameters
    )

    return payload


def _canonical_request_bytes(
    payload: dict[str, object],
) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode(
        "utf-8"
    )


def _response_body_sha256(
    body: bytes,
) -> str:
    return hashlib.sha256(
        body
    ).hexdigest()


def _default_transport(
    endpoint: str,
    body: bytes,
    headers: dict[str, str],
    timeout_seconds: float,
) -> bytes:
    request = Request(
        endpoint,
        data=body,
        headers=headers,
        method="POST",
    )

    try:
        with urlopen(
            request,
            timeout=timeout_seconds,
        ) as response:
            return response.read()
    except HTTPError as exc:
        raise OpenAIResponsesError(
            "OpenAI Responses API returned "
            f"HTTP {exc.code}"
        ) from exc
    except URLError as exc:
        raise OpenAIResponsesError(
            "OpenAI Responses API network request failed"
        ) from exc


def _decode_provider_body(
    body: bytes,
) -> dict[str, Any]:
    if not isinstance(
        body,
        bytes,
    ):
        raise ContractError(
            "provider response body must be bytes"
        )

    if not body:
        raise OpenAIResponsesError(
            "OpenAI Responses API returned an empty body"
        )

    try:
        decoded = json.loads(
            body.decode(
                "utf-8"
            )
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise OpenAIResponsesError(
            "OpenAI Responses API returned "
            "an invalid JSON body"
        ) from exc

    if not isinstance(
        decoded,
        dict,
    ):
        raise OpenAIResponsesError(
            "OpenAI Responses API body "
            "must be a JSON object"
        )

    return decoded


def _extract_output_text(
    response: dict[str, Any],
) -> str:
    output = response.get(
        "output"
    )

    if not isinstance(
        output,
        list,
    ):
        raise OpenAIResponsesError(
            "OpenAI response is missing output items"
        )

    output_texts: list[str] = []
    refusals: list[str] = []

    for item in output:
        if (
            not isinstance(item, dict)
            or item.get("type")
            != "message"
        ):
            continue

        content = item.get(
            "content"
        )

        if not isinstance(
            content,
            list,
        ):
            continue

        for part in content:
            if not isinstance(
                part,
                dict,
            ):
                continue

            part_type = part.get(
                "type"
            )

            if part_type == "refusal":
                refusal = part.get(
                    "refusal"
                )

                if isinstance(
                    refusal,
                    str,
                ) and refusal.strip():
                    refusals.append(
                        refusal
                    )

            elif part_type == "output_text":
                text = part.get(
                    "text"
                )

                if isinstance(
                    text,
                    str,
                ) and text.strip():
                    output_texts.append(
                        text
                    )

    if refusals:
        raise OpenAIResponsesRefusal(
            "OpenAI model returned an explicit refusal"
        )

    if len(output_texts) != 1:
        raise OpenAIResponsesError(
            "expected exactly one structured "
            "output_text item"
        )

    return output_texts[0]


def _usage_value(
    usage: object,
    name: str,
) -> int | None:
    if not isinstance(
        usage,
        dict,
    ):
        return None

    value = usage.get(
        name
    )

    return _require_optional_nonnegative_int(
        value,
        f"usage.{name}",
    )


def parse_openai_responses_body(
    *,
    request: ModelRequest,
    body: bytes,
) -> OpenAIResponsesResult:
    """Convert one provider body into bounded Hetren capture evidence."""
    if not isinstance(
        request,
        ModelRequest,
    ):
        raise ContractError(
            "request must be a ModelRequest"
        )

    if request.provider != _PROVIDER:
        raise ContractError(
            "OpenAI adapter requires provider='openai'"
        )

    response = _decode_provider_body(
        body
    )

    status = response.get(
        "status"
    )

    if status != "completed":
        incomplete = response.get(
            "incomplete_details"
        )

        reason = None

        if isinstance(
            incomplete,
            dict,
        ):
            candidate = incomplete.get(
                "reason"
            )

            if isinstance(
                candidate,
                str,
            ) and candidate.strip():
                reason = candidate

        suffix = (
            f": {reason}"
            if reason
            else ""
        )

        raise OpenAIResponsesError(
            "OpenAI response did not complete"
            + suffix
        )

    response_id = _require_text(
        response.get(
            "id"
        ),
        "response.id",
    )

    response_model = _require_text(
        response.get(
            "model"
        ),
        "response.model",
    )

    output_text = (
        _extract_output_text(
            response
        )
    )

    capture = (
        capture_json_response(
            request=request,
            raw_response_text=(
                output_text
            ),
            normalizer_id=(
                "openai-responses-"
                "structured-output"
            ),
            normalizer_version="1",
        )
    )

    payload = (
        build_openai_responses_payload(
            request
        )
    )

    usage = response.get(
        "usage"
    )

    result = OpenAIResponsesResult(
        response_id=response_id,
        response_model=(
            response_model
        ),
        status="completed",
        request_payload_sha256=(
            canonical_sha256(
                payload
            )
        ),
        response_body_sha256=(
            _response_body_sha256(
                body
            )
        ),
        input_tokens=(
            _usage_value(
                usage,
                "input_tokens",
            )
        ),
        output_tokens=(
            _usage_value(
                usage,
                "output_tokens",
            )
        ),
        total_tokens=(
            _usage_value(
                usage,
                "total_tokens",
            )
        ),
        capture=capture,
        limitations=(
            "response metadata is provider-reported",
            "response ID does not independently authenticate the provider",
            "response model field does not independently prove model identity",
            "successful structured output does not establish correctness",
            "live provider execution is not deterministic replay",
            "result contains no authorization or deployment decision",
        ),
    )

    capture.validate_against(
        request
    )

    return result


def call_openai_responses(
    *,
    request: ModelRequest,
    api_key: str,
    timeout_seconds: float = 30.0,
    transport: Transport | None = None,
) -> OpenAIResponsesResult:
    """Execute one explicit OpenAI Responses call or injected transport."""
    if not isinstance(
        request,
        ModelRequest,
    ):
        raise ContractError(
            "request must be a ModelRequest"
        )

    if request.provider != _PROVIDER:
        raise ContractError(
            "OpenAI adapter requires provider='openai'"
        )

    _require_text(
        api_key,
        "api_key",
    )

    if (
        not isinstance(
            timeout_seconds,
            (int, float),
        )
        or isinstance(
            timeout_seconds,
            bool,
        )
        or timeout_seconds <= 0
    ):
        raise ContractError(
            "timeout_seconds must be positive"
        )

    payload = (
        build_openai_responses_payload(
            request
        )
    )

    body = _canonical_request_bytes(
        payload
    )

    headers = {
        "Authorization":
            f"Bearer {api_key}",
        "Content-Type":
            "application/json",
        "User-Agent":
            "hetren-portfolio/1",
    }

    selected_transport = (
        _default_transport
        if transport is None
        else transport
    )

    response_body = (
        selected_transport(
            _OPENAI_RESPONSES_ENDPOINT,
            body,
            headers,
            float(
                timeout_seconds
            ),
        )
    )

    return parse_openai_responses_body(
        request=request,
        body=response_body,
    )


__all__ = [
    "OpenAIResponsesError",
    "OpenAIResponsesRefusal",
    "OpenAIResponsesResult",
    "build_openai_responses_payload",
    "call_openai_responses",
    "parse_openai_responses_body",
]

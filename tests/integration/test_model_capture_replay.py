"""Integration tests for deterministic structured-model capture and replay."""

from pathlib import Path

import pytest

from packages import model_capture
from packages.contracts import ContractError
from packages.model_capture import (
    ModelRequest,
    capture_json_response,
    replay_json_capture,
)


def _request(
    *,
    provider: str = "example-provider",
    model: str = "example-model-v1",
    system_prompt: str = "Return only structured JSON.",
    user_prompt: str = "Choose the incident filter configuration.",
) -> ModelRequest:
    return ModelRequest(
        provider=provider,
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response_schema_name=(
            "incident_filter_decision"
        ),
        response_schema={
            "type": "object",
            "properties": {
                "selected_filter_tool": {
                    "type": "string",
                },
                "threshold": {
                    "type": "integer",
                },
            },
            "required": [
                "selected_filter_tool",
                "threshold",
            ],
            "additionalProperties": False,
        },
        generation_parameters={
            "temperature": 0,
        },
    )


_RAW_RESPONSE = (
    '{"selected_filter_tool":"inclusive_severity_filter",'
    '"threshold":3}'
)


def test_request_identity_is_deterministic():
    first = _request()
    second = _request()

    assert first == second
    assert (
        first.request_sha256
        == second.request_sha256
    )

    assert len(
        first.request_sha256
    ) == 64


def test_request_identity_changes_when_model_changes():
    first = _request(
        model="example-model-v1",
    )

    second = _request(
        model="example-model-v2",
    )

    assert (
        first.request_sha256
        != second.request_sha256
    )


def test_capture_and_replay_round_trip():
    request = _request()

    capture = capture_json_response(
        request=request,
        raw_response_text=_RAW_RESPONSE,
    )

    replayed = replay_json_capture(
        request=request,
        capture=capture,
    )

    assert replayed == {
        "selected_filter_tool":
            "inclusive_severity_filter",
        "threshold": 3,
    }

    assert (
        capture.normalized_response
        == replayed
    )


def test_capture_binds_exact_request_digest():
    request = _request()

    capture = capture_json_response(
        request=request,
        raw_response_text=_RAW_RESPONSE,
    )

    assert (
        capture.provider
        == request.provider
    )

    assert (
        capture.model
        == request.model
    )

    assert (
        capture.request_sha256
        == request.request_sha256
    )

    capture.validate_against(
        request
    )


def test_replay_rejects_different_model_request():
    source = _request(
        model="example-model-v1",
    )

    different = _request(
        model="example-model-v2",
    )

    capture = capture_json_response(
        request=source,
        raw_response_text=_RAW_RESPONSE,
    )

    with pytest.raises(
        ContractError
    ):
        replay_json_capture(
            request=different,
            capture=capture,
        )


def test_replay_rejects_different_prompt_request():
    source = _request(
        user_prompt=(
            "Choose the incident filter configuration."
        ),
    )

    different = _request(
        user_prompt=(
            "Choose a different configuration."
        ),
    )

    capture = capture_json_response(
        request=source,
        raw_response_text=_RAW_RESPONSE,
    )

    with pytest.raises(
        ContractError
    ):
        replay_json_capture(
            request=different,
            capture=capture,
        )


def test_capture_rejects_non_json_response():
    request = _request()

    with pytest.raises(
        ContractError
    ):
        capture_json_response(
            request=request,
            raw_response_text=(
                "Use threshold 3."
            ),
        )


def test_capture_rejects_json_array_response():
    request = _request()

    with pytest.raises(
        ContractError
    ):
        capture_json_response(
            request=request,
            raw_response_text='[1, 2, 3]',
        )


def test_request_rejects_non_json_schema_value():
    with pytest.raises(
        ContractError
    ):
        ModelRequest(
            provider="example-provider",
            model="example-model-v1",
            system_prompt="Return JSON.",
            user_prompt="Choose configuration.",
            response_schema_name="decision",
            response_schema={
                "type": "object",
                "invalid": object(),
            },
            generation_parameters={},
        )


def test_request_rejects_non_string_json_key():
    with pytest.raises(
        ContractError
    ):
        ModelRequest(
            provider="example-provider",
            model="example-model-v1",
            system_prompt="Return JSON.",
            user_prompt="Choose configuration.",
            response_schema_name="decision",
            response_schema={
                1: "invalid-key",
            },
            generation_parameters={},
        )


@pytest.mark.parametrize(
    "value",
    (
        float("nan"),
        float("inf"),
        float("-inf"),
    ),
)
def test_generation_parameters_reject_non_finite_float(
    value,
):
    with pytest.raises(
        ContractError
    ):
        ModelRequest(
            provider="example-provider",
            model="example-model-v1",
            system_prompt="Return JSON.",
            user_prompt="Choose configuration.",
            response_schema_name="decision",
            response_schema={
                "type": "object",
            },
            generation_parameters={
                "temperature": value,
            },
        )


def test_capture_hashes_are_deterministic():
    request = _request()

    first = capture_json_response(
        request=request,
        raw_response_text=_RAW_RESPONSE,
    )

    second = capture_json_response(
        request=request,
        raw_response_text=_RAW_RESPONSE,
    )

    assert first == second

    assert (
        first.raw_response_sha256
        == second.raw_response_sha256
    )

    assert (
        first.normalized_response_sha256
        == second.normalized_response_sha256
    )

    assert (
        first.capture_sha256
        == second.capture_sha256
    )

    assert len(
        first.raw_response_sha256
    ) == 64

    assert len(
        first.normalized_response_sha256
    ) == 64

    assert len(
        first.capture_sha256
    ) == 64


def test_capture_claim_limits_are_explicit():
    capture = capture_json_response(
        request=_request(),
        raw_response_text=_RAW_RESPONSE,
    )

    assert (
        "capture does not prove provider identity"
        in capture.limitations
    )

    assert (
        "capture does not prove model-response correctness"
        in capture.limitations
    )

    assert (
        "capture contains no authorization decision"
        in capture.limitations
    )

    assert (
        "replay is not a fresh model inference"
        in capture.limitations
    )


def test_public_surface_is_bounded():
    assert set(
        model_capture.__all__
    ) == {
        "ModelCapture",
        "ModelRequest",
        "capture_json_response",
        "parse_json_response",
        "replay_json_capture",
    }


def test_module_has_no_network_or_credential_access():
    source = Path(
        model_capture.__file__
    ).read_text(
        encoding="utf-8"
    ).lower()

    forbidden = (
        "import requests",
        "import httpx",
        "import aiohttp",
        "urllib.request",
        "os.environ",
        "os.getenv",
        "api_key=",
        "authorization:",
        "bearer ",
    )

    for token in forbidden:
        assert token not in source

"""Offline integration tests for the OpenAI Responses adapter."""

import json
from pathlib import Path

import pytest

from packages.contracts import ContractError
from packages.model_capture import ModelRequest
from packages.openai_responses import (
    OpenAIResponsesError,
    OpenAIResponsesRefusal,
    build_openai_responses_payload,
    call_openai_responses,
    parse_openai_responses_body,
)


def _request(
    *,
    provider: str = "openai",
    model: str = "gpt-6-luna",
    generation_parameters=None,
) -> ModelRequest:
    if generation_parameters is None:
        generation_parameters = {
            "reasoning": {
                "effort": "none",
            },
            "max_output_tokens": 120,
        }

    return ModelRequest(
        provider=provider,
        model=model,
        system_prompt=(
            "Return only the required structured decision."
        ),
        user_prompt=(
            "Choose the incident-triage severity filter."
        ),
        response_schema_name=(
            "incident_filter_decision"
        ),
        response_schema={
            "type": "object",
            "properties": {
                "selected_filter_tool": {
                    "type": "string",
                    "enum": [
                        "inclusive_severity_filter",
                        "strict_severity_filter",
                    ],
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
        generation_parameters=(
            generation_parameters
        ),
    )


def _completed_response(
    *,
    output_text=(
        '{"selected_filter_tool":'
        '"inclusive_severity_filter",'
        '"threshold":3}'
    ),
    usage=True,
):
    body = {
        "id": "resp_offline_fixture",
        "object": "response",
        "status": "completed",
        "model": "gpt-6-luna",
        "output": [
            {
                "id": "msg_offline_fixture",
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [
                    {
                        "type": "output_text",
                        "annotations": [],
                        "text": output_text,
                    },
                ],
            },
        ],
    }

    if usage:
        body["usage"] = {
            "input_tokens": 42,
            "output_tokens": 12,
            "total_tokens": 54,
        }

    return body


def test_payload_uses_strict_structured_outputs_and_disables_storage():
    request = _request()

    payload = (
        build_openai_responses_payload(
            request
        )
    )

    assert payload["model"] == "gpt-6-luna"
    assert payload["store"] is False
    assert payload["stream"] is False

    assert payload["input"] == [
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
    ]

    format_spec = (
        payload["text"]["format"]
    )

    assert (
        format_spec["type"]
        == "json_schema"
    )

    assert (
        format_spec["name"]
        == request.response_schema_name
    )

    assert (
        format_spec["strict"]
        is True
    )

    assert (
        format_spec["schema"]
        == request.response_schema
    )


def test_non_reserved_generation_parameters_are_preserved():
    payload = (
        build_openai_responses_payload(
            _request()
        )
    )

    assert payload["reasoning"] == {
        "effort": "none",
    }

    assert (
        payload["max_output_tokens"]
        == 120
    )


@pytest.mark.parametrize(
    "reserved",
    (
        "model",
        "input",
        "text",
        "store",
        "stream",
    ),
)
def test_reserved_provider_fields_cannot_be_overridden(
    reserved,
):
    request = _request(
        generation_parameters={
            reserved: True,
        },
    )

    with pytest.raises(
        ContractError
    ):
        build_openai_responses_payload(
            request
        )


def test_openai_provider_is_required():
    request = _request(
        provider="different-provider",
    )

    with pytest.raises(
        ContractError
    ):
        build_openai_responses_payload(
            request
        )


def test_fake_transport_executes_complete_provider_path():
    request = _request()

    observed = {}

    def fake_transport(
        endpoint,
        body,
        headers,
        timeout_seconds,
    ):
        observed["endpoint"] = endpoint
        observed["body"] = body
        observed["headers"] = headers
        observed["timeout"] = timeout_seconds

        return json.dumps(
            _completed_response(),
            sort_keys=True,
        ).encode(
            "utf-8"
        )

    result = call_openai_responses(
        request=request,
        api_key="offline-secret",
        timeout_seconds=7,
        transport=fake_transport,
    )

    assert (
        observed["endpoint"]
        == "https://api.openai.com/v1/responses"
    )

    assert observed["timeout"] == 7.0

    sent = json.loads(
        observed["body"].decode(
            "utf-8"
        )
    )

    assert sent["model"] == "gpt-6-luna"
    assert sent["store"] is False
    assert sent["stream"] is False

    assert (
        result.capture.normalized_response
        == {
            "selected_filter_tool":
                "inclusive_severity_filter",
            "threshold": 3,
        }
    )

    assert (
        result.response_id
        == "resp_offline_fixture"
    )

    assert (
        result.response_model
        == "gpt-6-luna"
    )

    assert result.input_tokens == 42
    assert result.output_tokens == 12
    assert result.total_tokens == 54


def test_api_key_is_excluded_from_payload_and_evidence():
    request = _request()

    secret = (
        "offline-secret-value-"
        "must-not-enter-evidence"
    )

    observed = {}

    def fake_transport(
        endpoint,
        body,
        headers,
        timeout_seconds,
    ):
        observed["body"] = body
        observed["headers"] = headers

        return json.dumps(
            _completed_response(),
            sort_keys=True,
        ).encode(
            "utf-8"
        )

    result = call_openai_responses(
        request=request,
        api_key=secret,
        transport=fake_transport,
    )

    assert (
        observed["headers"]["Authorization"]
        == f"Bearer {secret}"
    )

    assert (
        secret.encode("utf-8")
        not in observed["body"]
    )

    canonical = json.dumps(
        result.canonical_payload(),
        sort_keys=True,
    )

    assert secret not in canonical
    assert secret not in repr(result)

    assert len(
        result.request_payload_sha256
    ) == 64

    assert len(
        result.response_body_sha256
    ) == 64

    assert len(
        result.evidence_sha256
    ) == 64


def test_explicit_refusal_is_not_schema_output():
    request = _request()

    body = json.dumps(
        {
            "id": "resp_refusal",
            "status": "completed",
            "model": "gpt-6-luna",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "refusal",
                            "refusal":
                                "I cannot provide that response.",
                        },
                    ],
                },
            ],
        }
    ).encode(
        "utf-8"
    )

    with pytest.raises(
        OpenAIResponsesRefusal
    ):
        parse_openai_responses_body(
            request=request,
            body=body,
        )


def test_incomplete_response_is_rejected_with_reason():
    request = _request()

    body = json.dumps(
        {
            "id": "resp_incomplete",
            "status": "incomplete",
            "model": "gpt-6-luna",
            "incomplete_details": {
                "reason":
                    "max_output_tokens",
            },
            "output": [],
        }
    ).encode(
        "utf-8"
    )

    with pytest.raises(
        OpenAIResponsesError,
        match="max_output_tokens",
    ):
        parse_openai_responses_body(
            request=request,
            body=body,
        )


def test_completed_response_without_output_is_rejected():
    request = _request()

    body = json.dumps(
        {
            "id": "resp_missing_output",
            "status": "completed",
            "model": "gpt-6-luna",
            "output": [],
        }
    ).encode(
        "utf-8"
    )

    with pytest.raises(
        OpenAIResponsesError,
        match="exactly one structured",
    ):
        parse_openai_responses_body(
            request=request,
            body=body,
        )


def test_multiple_output_text_items_are_rejected():
    request = _request()

    body = json.dumps(
        {
            "id": "resp_multiple",
            "status": "completed",
            "model": "gpt-6-luna",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type":
                                "output_text",
                            "text":
                                '{"threshold":3}',
                        },
                        {
                            "type":
                                "output_text",
                            "text":
                                '{"threshold":4}',
                        },
                    ],
                },
            ],
        }
    ).encode(
        "utf-8"
    )

    with pytest.raises(
        OpenAIResponsesError,
        match="exactly one structured",
    ):
        parse_openai_responses_body(
            request=request,
            body=body,
        )


def test_invalid_provider_json_body_is_rejected():
    request = _request()

    with pytest.raises(
        OpenAIResponsesError,
        match="invalid JSON body",
    ):
        parse_openai_responses_body(
            request=request,
            body=b"not-json",
        )


def test_usage_metadata_is_optional():
    request = _request()

    body = json.dumps(
        _completed_response(
            usage=False,
        )
    ).encode(
        "utf-8"
    )

    result = (
        parse_openai_responses_body(
            request=request,
            body=body,
        )
    )

    assert result.input_tokens is None
    assert result.output_tokens is None
    assert result.total_tokens is None


def test_negative_usage_metadata_is_rejected():
    request = _request()

    response = (
        _completed_response()
    )

    response["usage"] = {
        "input_tokens": -1,
        "output_tokens": 12,
        "total_tokens": 11,
    }

    body = json.dumps(
        response
    ).encode(
        "utf-8"
    )

    with pytest.raises(
        ContractError
    ):
        parse_openai_responses_body(
            request=request,
            body=body,
        )


def test_adapter_does_not_discover_credentials():
    source = Path(
        "packages/openai_responses.py"
    ).read_text(
        encoding="utf-8"
    ).lower()

    for forbidden in (
        "os.environ",
        "os.getenv",
        "dotenv",
        ".env",
    ):
        assert forbidden not in source

"""Offline model-proposed action execution and provider adapter tests."""

from dataclasses import replace
import json

import pytest

from packages.contracts import ContractError
from packages.core.hetren_diagnosis.contracts import EventKind
from packages.model_capture import capture_json_response
from packages.engines.behavioral.model_proposed_tool_agent import (
    build_addition_request,
    run_captured_addition_agent,
    run_openai_addition_agent,
)


def _request():
    return build_addition_request(
        model="offline-model",
        left=3,
        right=4,
    )


def _capture(proposal):
    return capture_json_response(
        request=_request(),
        raw_response_text=json.dumps(
            proposal, sort_keys=True,
        ),
    )


def _run(proposal, run_id="a58-replay"):
    return run_captured_addition_agent(
        request=_request(),
        capture=_capture(proposal),
        run_id=run_id,
        left=3,
        right=4,
    )


def test_valid_model_proposal_executes_allowlisted_addition():
    result = _run({
        "tool": "add_ints",
        "a": 3,
        "b": 4,
    })

    assert result.status == "executed"
    assert result.passed
    assert result.output == 7
    assert result.expected_output == 7
    assert result.arguments == (3, 4)
    assert result.rejection_reason is None
    assert len(result.trace.events) == 3
    assert [event.kind for event in result.trace.events] == [
        EventKind.DECISION,
        EventKind.TOOL_CALL,
        EventKind.TERMINATION,
    ]
    assert len(result.execution_evidence_sha256) == 64


def test_wrong_allowlisted_tool_executes_but_fails_evaluation():
    result = _run({
        "tool": "multiply_ints",
        "a": 3,
        "b": 4,
    })

    assert result.status == "executed"
    assert result.output == 12
    assert result.expected_output == 7
    assert not result.passed
    assert len(result.trace.events) == 3


@pytest.mark.parametrize(
    "proposal,reason",
    [
        (
            {"tool": "shell", "a": 3, "b": 4},
            "tool_not_allowlisted",
        ),
        (
            {"tool": "add_ints", "a": 4, "b": 3},
            "arguments_do_not_match_task",
        ),
        (
            {"tool": "add_ints", "a": True, "b": 4},
            "invalid_arguments",
        ),
        (
            {"tool": "add_ints", "a": 101, "b": 4},
            "invalid_arguments",
        ),
        (
            {"tool": "add_ints", "a": "3", "b": 4},
            "invalid_arguments",
        ),
        (
            {"tool": "add_ints", "a": 3},
            "invalid_proposal_shape",
        ),
        (
            {
                "tool": "add_ints",
                "a": 3,
                "b": 4,
                "extra": "unexpected",
            },
            "invalid_proposal_shape",
        ),
    ],
)
def test_invalid_or_unsafe_proposals_never_execute(
    proposal, reason
):
    result = _run(proposal)

    assert result.status == "rejected"
    assert result.rejection_reason == reason
    assert result.output is None
    assert result.selected_tool is None
    assert result.arguments is None
    assert not result.passed
    assert len(result.trace.events) == 2
    assert all(
        event.kind is not EventKind.TOOL_CALL
        for event in result.trace.events
    )


def test_request_is_bound_to_exact_task():
    with pytest.raises(ContractError):
        run_captured_addition_agent(
            request=_request(),
            capture=_capture({
                "tool": "add_ints",
                "a": 3,
                "b": 4,
            }),
            run_id="a58-mismatch",
            left=3,
            right=5,
        )


def test_tampered_response_is_not_replayed_as_original():
    capture = _capture({
        "tool": "add_ints",
        "a": 3,
        "b": 4,
    })

    tampered = replace(
        capture,
        raw_response_text=json.dumps({
            "tool": "multiply_ints",
            "a": 3,
            "b": 4,
        }),
    )

    with pytest.raises(ContractError):
        run_captured_addition_agent(
            request=_request(),
            capture=tampered,
            run_id="a58-tamper",
            left=3,
            right=4,
        )


def test_capture_from_different_request_is_rejected():
    other = build_addition_request(
        model="offline-model",
        left=2,
        right=5,
    )

    capture = capture_json_response(
        request=other,
        raw_response_text=json.dumps({
            "tool": "add_ints",
            "a": 2,
            "b": 5,
        }),
    )

    with pytest.raises(ContractError):
        run_captured_addition_agent(
            request=_request(),
            capture=capture,
            run_id="a58-wrong-capture",
            left=3,
            right=4,
        )


@pytest.mark.parametrize(
    "left,right",
    [(True, 4), (-1, 4), (101, 4), (3, 1000)],
)
def test_unbounded_or_invalid_tasks_are_rejected(left, right):
    with pytest.raises(ContractError):
        build_addition_request(
            model="offline-model",
            left=left,
            right=right,
        )


def test_replay_is_deterministic():
    proposal = {
        "tool": "add_ints",
        "a": 3,
        "b": 4,
    }
    assert _run(proposal) == _run(proposal)


def test_distinct_run_ids_change_execution_evidence():
    proposal = {
        "tool": "add_ints",
        "a": 3,
        "b": 4,
    }
    first = _run(proposal, run_id="a58-one")
    second = _run(proposal, run_id="a58-two")

    assert (
        first.execution_evidence_sha256
        != second.execution_evidence_sha256
    )


def test_injected_provider_transport_executes_full_agent_path():
    observed = {}

    def fake_transport(endpoint, body, headers, timeout):
        observed["endpoint"] = endpoint
        observed["payload"] = json.loads(body)
        observed["authorization"] = headers["Authorization"]
        observed["timeout"] = timeout

        return json.dumps({
            "id": "resp_a58_offline",
            "model": "offline-model",
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps({
                                "tool": "add_ints",
                                "a": 3,
                                "b": 4,
                            }),
                        }
                    ],
                }
            ],
            "usage": {
                "input_tokens": 8,
                "output_tokens": 5,
                "total_tokens": 13,
            },
        }).encode("utf-8")

    result = run_openai_addition_agent(
        model="offline-model",
        left=3,
        right=4,
        run_id="a58-injected",
        api_key="offline-test-key",
        transport=fake_transport,
    )

    assert result.agent_run.passed
    assert result.agent_run.output == 7
    assert result.provider_result.status == "completed"
    assert (
        result.agent_run.capture_sha256
        == result.provider_result.capture.capture_sha256
    )
    assert observed["endpoint"] == (
        "https://api.openai.com/v1/responses"
    )
    assert observed["payload"]["store"] is False
    assert observed["payload"]["stream"] is False
    assert observed["authorization"] == "Bearer offline-test-key"
    assert observed["timeout"] == 30.0

    assert "offline-test-key" not in repr(result)
    assert "offline-test-key" not in json.dumps(
        result.provider_result.canonical_payload()
    )


def test_request_has_strict_tool_schema_and_no_credentials():
    request = _request()

    assert request.provider == "openai"
    assert request.response_schema["additionalProperties"] is False
    assert request.response_schema["required"] == [
        "tool", "a", "b"
    ]
    assert request.generation_parameters == {}


def test_no_shell_or_filesystem_tool_is_exposed():
    request = _request()
    tools = request.response_schema["properties"]["tool"]["enum"]
    assert tools == ["add_ints", "multiply_ints"]

"""No network: injected provider response -> captured incident execution."""

import json

import pytest

from packages.contracts import ContractError
from packages.openai_responses import OpenAIResponsesError
from packages.engines.behavioral.model_incident_triage_agent import (
    build_incident_triage_request,
    run_captured_incident_triage,
    run_injected_openai_incident_triage,
)


def _body(proposal, *, status="completed"):
    return json.dumps({
        "id": "resp_a510d_synthetic_offline",
        "model": "offline-model",
        "status": status,
        "output": [{
            "type": "message",
            "role": "assistant",
            "content": [{
                "type": "output_text",
                "text": json.dumps(proposal, sort_keys=True),
            }],
        }],
        "usage": {
            "input_tokens": 12,
            "output_tokens": 8,
            "total_tokens": 20,
        },
    }).encode("utf-8")


def _run(proposal, *, run_id="a510d-offline"):
    observed = {}

    def fake_transport(endpoint, body, headers, timeout):
        observed["endpoint"] = endpoint
        observed["request"] = json.loads(body)
        observed["authorization"] = headers["Authorization"]
        observed["timeout"] = timeout
        return _body(proposal)

    result = run_injected_openai_incident_triage(
        model="offline-model",
        run_id=run_id,
        api_key="synthetic-offline-credential",
        transport=fake_transport,
    )
    assert observed["endpoint"] == "https://api.openai.com/v1/responses"
    assert observed["authorization"] == "Bearer synthetic-offline-credential"
    assert observed["timeout"] == 30.0
    assert observed["request"]["store"] is False
    assert observed["request"]["stream"] is False
    assert result.provider_result.status == "completed"
    assert result.provider_result.capture.capture_sha256 == result.agent_run.capture_sha256
    assert result.agent_run.trace.run_id == run_id
    assert "synthetic-offline-credential" not in repr(result)
    assert "synthetic-offline-credential" not in json.dumps(
        result.provider_result.canonical_payload()
    )
    return result


def test_correct_injected_action_executes_and_replays():
    proposal = {"tool": "inclusive_severity_filter", "threshold": 3}
    result = _run(proposal)
    assert result.agent_run.passed
    assert result.agent_run.environment_run.report.incident_ids == (
        "INC-1001", "INC-1002", "INC-1004"
    )

    request = build_incident_triage_request(model="offline-model")
    replay = run_captured_incident_triage(
        request=request,
        capture=result.provider_result.capture,
        run_id=result.agent_run.run_id,
    )
    assert replay == result.agent_run
    assert replay.execution_evidence_sha256 == result.agent_run.execution_evidence_sha256


@pytest.mark.parametrize(
    "proposal,expected_ids",
    [
        ({"tool": "strict_severity_filter", "threshold": 3},
         ("INC-1001", "INC-1004")),
        ({"tool": "inclusive_severity_filter", "threshold": 4},
         ("INC-1001", "INC-1004")),
    ],
)
def test_injected_incorrect_action_executes_but_fails(proposal, expected_ids):
    result = _run(proposal)
    assert result.agent_run.status == "executed"
    assert not result.agent_run.passed
    assert result.agent_run.environment_run.report.incident_ids == expected_ids


@pytest.mark.parametrize(
    "proposal,reason",
    [
        ({"tool": "shell", "threshold": 3}, "unsupported_tool"),
        ({"tool": "inclusive_severity_filter", "threshold": True},
         "invalid_threshold"),
        ({"tool": "inclusive_severity_filter", "threshold": 3,
          "invented_incident_ids": ["INC-9999"]}, "invalid_proposal_shape"),
    ],
)
def test_injected_unsafe_action_never_executes(proposal, reason):
    result = _run(proposal)
    assert result.agent_run.status == "rejected"
    assert result.agent_run.rejection_reason == reason
    assert result.agent_run.environment_run is None
    assert not result.agent_run.passed


def test_missing_transport_rejected_without_default_network():
    with pytest.raises(ContractError, match="injected transport"):
        run_injected_openai_incident_triage(
            model="offline-model", run_id="a510d-none",
            api_key="synthetic-offline-credential", transport=None,
        )


def test_bad_run_id_rejected_before_transport_invocation():
    calls = []

    def forbidden_transport(*args):
        calls.append(args)
        raise AssertionError("transport must not run")

    with pytest.raises(ContractError, match="run_id"):
        run_injected_openai_incident_triage(
            model="offline-model", run_id=" invalid identifier ",
            api_key="synthetic-offline-credential", transport=forbidden_transport,
        )
    assert not calls


def test_malformed_provider_body_rejected_without_tool_execution():
    calls = []

    def fake_transport(endpoint, body, headers, timeout):
        calls.append(endpoint)
        return b'{"status":"completed"'

    with pytest.raises((OpenAIResponsesError, ContractError)):
        run_injected_openai_incident_triage(
            model="offline-model", run_id="a510d-malformed",
            api_key="synthetic-offline-credential", transport=fake_transport,
        )
    assert len(calls) == 1


def test_injected_result_is_replay_deterministic():
    proposal = {"tool": "inclusive_severity_filter", "threshold": 3}
    first = _run(proposal, run_id="a510d-deterministic")
    second = _run(proposal, run_id="a510d-deterministic")
    assert first == second
    assert first.agent_run.execution_evidence_sha256 == (
        second.agent_run.execution_evidence_sha256
    )

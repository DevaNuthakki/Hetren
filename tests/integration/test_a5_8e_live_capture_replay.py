"""Replay a single live-model observation without API access.

This is recorded development evidence, not new model inference
or an independent scientific study.
"""

from dataclasses import replace
import json
from pathlib import Path

import pytest

from packages.contracts import ContractError
from packages.model_capture import ModelCapture, replay_json_capture
from packages.engines.behavioral.model_proposed_tool_agent import (
    build_addition_request,
    run_captured_addition_agent,
)


FIXTURE = Path(__file__).with_name(
    "a5_8e_live_capture_fixture.json"
)

CAPTURE_SHA = "0dafc9f8c0f5d5260d37eb2a3225a3d3fb9450b382ab354e9133db8d73de6ebe"
EXECUTION_SHA = "f7facc19e08f178a64e6c64a0df8cab546b07989fc36c956ffd215e5bef46437"
SOURCE_SHA = "323bc982b0b335efa2c061378763961bb4524be12ff351de175cc1e9d653f4e0"


def _replay():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    task = fixture["request"]
    record = fixture["capture"]

    request = build_addition_request(
        model=task["model"],
        left=task["left"],
        right=task["right"],
    )
    assert request.request_sha256 == task["request_sha256"]

    capture = ModelCapture(
        provider=record["provider"],
        model=record["model"],
        request_sha256=record["request_sha256"],
        raw_response_text=record["raw_response_text"],
        normalized_response=record["normalized_response"],
        normalizer_id=record["normalizer_id"],
        normalizer_version=record["normalizer_version"],
        limitations=tuple(record["limitations"]),
    )

    assert capture.capture_sha256 == CAPTURE_SHA
    assert capture.capture_sha256 == record["capture_sha256"]

    proposal = replay_json_capture(
        request=request,
        capture=capture,
    )

    run = run_captured_addition_agent(
        request=request,
        capture=capture,
        run_id=fixture["execution"]["run_id"],
        left=task["left"],
        right=task["right"],
    )

    return fixture, request, capture, proposal, run


def test_live_proposal_replays_offline():
    fixture, _, _, proposal, run = _replay()

    assert proposal == {"tool": "add_ints", "a": 3, "b": 4}
    assert run.status == "executed"
    assert run.selected_tool == "add_ints"
    assert run.arguments == (3, 4)
    assert run.output == run.expected_output == 7
    assert run.passed is True
    assert run.execution_evidence_sha256 == EXECUTION_SHA
    assert (
        run.trace.canonical_payload()
        == fixture["execution"]["trace"]
    )


def test_recorded_provenance_and_claim_limits():
    fixture, _, _, _, _ = _replay()

    assert fixture["source_type"] == "single_live_provider_observation"
    assert fixture["provenance"]["source_artifact_sha256"] == SOURCE_SHA
    assert fixture["provenance"]["provider_reported_model"] == (
        "gpt-5-mini-2025-08-07"
    )
    assert all(v is False for v in fixture["claims"].values())


def test_fixture_excludes_credentials_and_response_id():
    text = FIXTURE.read_text(encoding="utf-8")

    for forbidden in (
        "OPENAI_API_KEY",
        "Bearer ",
        "sk-",
        "api_key",
        "Authorization",
        "resp_",
        "/Users/",
    ):
        assert forbidden not in text


def test_tampered_response_is_rejected():
    _, request, capture, _, _ = _replay()

    tampered = replace(
        capture,
        raw_response_text='{"tool":"multiply_ints","a":3,"b":4}',
    )

    with pytest.raises(ContractError):
        replay_json_capture(
            request=request,
            capture=tampered,
        )


def test_wrong_request_is_rejected():
    _, _, capture, _, _ = _replay()

    other_request = build_addition_request(
        model="gpt-5-mini", left=3, right=5,
    )

    with pytest.raises(ContractError):
        replay_json_capture(
            request=other_request,
            capture=capture,
        )


def test_identical_offline_replay_is_deterministic():
    assert _replay() == _replay()

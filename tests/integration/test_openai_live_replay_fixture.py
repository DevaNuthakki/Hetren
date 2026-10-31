"""Regression tests for the sanitized live-model replay fixture."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from packages.contracts import canonical_sha256
from packages.model_capture import (
    ModelCapture,
    ModelRequest,
    replay_json_capture,
)


_FIXTURE_PATH = Path(
    "tests/integration/data/model_capture/"
    "openai_gpt6_luna_incident_filter_replay_v1.json"
)


_EXPECTED_DECISION = {
    "selected_filter_tool":
        "inclusive_severity_filter",
    "threshold": 3,
}


def _fixture() -> dict[str, object]:
    return json.loads(
        _FIXTURE_PATH.read_text(
            encoding="utf-8"
        )
    )


def _request(
    fixture: dict[str, object],
) -> ModelRequest:
    payload = fixture["request"]

    return ModelRequest(
        provider=payload["provider"],
        model=payload["model"],
        system_prompt=(
            payload["system_prompt"]
        ),
        user_prompt=(
            payload["user_prompt"]
        ),
        response_schema_name=(
            payload[
                "response_schema_name"
            ]
        ),
        response_schema=(
            payload[
                "response_schema"
            ]
        ),
        generation_parameters=(
            payload[
                "generation_parameters"
            ]
        ),
    )


def _capture(
    fixture: dict[str, object],
) -> ModelCapture:
    payload = fixture["capture"]

    return ModelCapture(
        provider=payload["provider"],
        model=payload["model"],
        request_sha256=(
            payload["request_sha256"]
        ),
        raw_response_text=(
            payload[
                "raw_response_text"
            ]
        ),
        normalized_response=(
            payload[
                "normalized_response"
            ]
        ),
        normalizer_id=(
            payload["normalizer_id"]
        ),
        normalizer_version=(
            payload[
                "normalizer_version"
            ]
        ),
        limitations=tuple(
            payload["limitations"]
        ),
    )


def test_fixture_identity_and_schema_version():
    fixture = _fixture()

    assert (
        fixture["record_type"]
        == "HetrenOpenAIReplayFixture"
    )

    assert fixture["schema_version"] == 1


def test_fixture_semantic_digest_is_frozen():
    fixture = _fixture()

    body = {
        key: value
        for key, value in fixture.items()
        if key != "fixture_sha256"
    }

    assert (
        canonical_sha256(body)
        == fixture["fixture_sha256"]
    )

    assert (
        fixture["fixture_sha256"]
        == "3f45941ace67c2bcae3638c5e7424c109edf07460ab53b5fdaee2522b8bb6a90"
    )


def test_fixture_preserves_live_source_provenance():
    fixture = _fixture()

    provenance = fixture[
        "provenance"
    ]

    assert (
        provenance[
            "source_execution_mode"
        ]
        == "live-openai-responses-api"
    )

    assert (
        provenance[
            "source_checkpoint"
        ]
        == "8e087baf324924b9353c8fd4d9933f740365f1bc"
    )

    assert (
        provenance[
            "source_artifact_file_sha256"
        ]
        == "5a1684a71bf5333746a74f9902ca7bd7a9c4ae402d661f01ed4b973584a09d38"
    )

    assert (
        provenance[
            "source_evidence_sha256"
        ]
        == "ae5dd8dd6b1e426ffc71a733c4c695ebe2e495e4f2d8efcf1e29e0a974f4f70f"
    )


def test_fixture_preserves_provider_reported_model_and_usage():
    fixture = _fixture()

    provenance = fixture[
        "provenance"
    ]

    assert provenance["provider"] == "openai"

    assert (
        provenance["requested_model"]
        == "gpt-6-luna"
    )

    assert (
        provenance["response_model"]
        == "gpt-6-luna"
    )

    assert provenance["input_tokens"] == 147
    assert provenance["output_tokens"] == 24
    assert provenance["total_tokens"] == 171


def test_request_identity_recomputes_from_fixture():
    fixture = _fixture()

    request = _request(
        fixture
    )

    assert (
        request.request_sha256
        == fixture["request_sha256"]
    )

    assert (
        request.request_sha256
        == "fe6e7c474014697013dc5dcc722f595a55dc674ffe4888f6b3e4175bce7ffb2d"
    )


def test_capture_identity_recomputes_from_fixture():
    fixture = _fixture()

    capture = _capture(
        fixture
    )

    assert (
        capture.capture_sha256
        == fixture[
            "capture"
        ]["capture_sha256"]
    )

    assert (
        capture.capture_sha256
        == "89497ab06eba436dec663153c5174733a60490155fcf0a63ebb87683fb79506c"
    )


def test_live_capture_replays_deterministically_offline():
    fixture = _fixture()

    request = _request(
        fixture
    )

    capture = _capture(
        fixture
    )

    replayed = replay_json_capture(
        request=request,
        capture=capture,
    )

    assert replayed == _EXPECTED_DECISION


def test_reference_evaluation_preserves_observed_result():
    fixture = _fixture()

    evaluation = fixture[
        "reference_evaluation"
    ]

    assert (
        evaluation[
            "expected_decision"
        ]
        == _EXPECTED_DECISION
    )

    assert (
        evaluation[
            "actual_decision"
        ]
        == _EXPECTED_DECISION
    )

    assert (
        evaluation[
            "matches_expected"
        ]
        is True
    )


def test_fixture_excludes_live_only_and_secret_material():
    text = _FIXTURE_PATH.read_text(
        encoding="utf-8"
    )

    for forbidden in (
        "Authorization",
        "Bearer ",
        "OPENAI_API_KEY",
        "api_key",
        "response_id",
        "captured_at_utc",
    ):
        assert forbidden not in text

    for pattern in (
        r"\bsk-[A-Za-z0-9_-]{12,}\b",
        r"\bsk-proj-[A-Za-z0-9_-]{12,}\b",
    ):
        assert re.search(
            pattern,
            text,
        ) is None


def test_fixture_preserves_scientific_claim_boundaries():
    fixture = _fixture()

    limitations = set(
        fixture[
            "claim_limits"
        ]
    )

    required = {
        (
            "this fixture derives from one live provider interaction "
            "and is not a model-quality benchmark"
        ),
        (
            "provider and model metadata are provider-reported"
        ),
        (
            "offline replay is deterministic but is not fresh model inference"
        ),
        (
            "one correct captured decision does not establish general "
            "reasoning, diagnosis, or repair capability"
        ),
        (
            "the original raw provider evidence remains local and Git-ignored"
        ),
        (
            "this fixture contains no authorization or deployment decision"
        ),
    }

    assert required.issubset(
        limitations
    )

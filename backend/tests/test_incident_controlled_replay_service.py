from __future__ import annotations

from types import SimpleNamespace

import pytest

import app.incident_controlled_replay_service as service


def _sha(value: str) -> str:
    return value * 64


def _kwargs():
    return {
        "intake_payload": {
            "evaluation_type": "asr",
        },
        "expected_intake_sha256": _sha("1"),
        "replay_preparation_payload": {
            "type": "preparation",
        },
        "expected_replay_preparation_sha256": _sha("2"),
        "environment_manifest_payload": {
            "type": "manifest",
        },
        "expected_environment_manifest_sha256": _sha("3"),
        "runner_compatibility_payload": {
            "type": "compatibility",
        },
        "expected_runner_compatibility_sha256": _sha("4"),
        "environment_materialization_payload": {
            "type": "materialization",
        },
        "expected_environment_materialization_sha256": _sha("5"),
    }


def test_request_round_trip_is_canonical():
    request = (
        service.build_incident_controlled_replay_request(
            **_kwargs()
        )
    )

    parsed = (
        service.parse_incident_controlled_replay_request(
            request.payload
        )
    )

    assert parsed == request


def test_request_rejects_unknown_fields():
    request = (
        service.build_incident_controlled_replay_request(
            **_kwargs()
        )
    )

    payload = dict(request.payload)
    payload["unexpected"] = True

    with pytest.raises(
        service.IncidentControlledReplayRequestError,
    ):
        service.parse_incident_controlled_replay_request(
            payload
        )


def test_enqueue_uses_fixed_scheduler_capabilities(
    monkeypatch,
):
    captured = {}

    expected_job = SimpleNamespace(
        public_id="replay-job"
    )

    def fake_enqueue(db, **kwargs):
        captured["db"] = db
        captured.update(kwargs)
        return expected_job

    monkeypatch.setattr(
        service,
        "enqueue_job",
        fake_enqueue,
    )

    db = object()

    result = (
        service.enqueue_incident_controlled_replay_job(
            db,
            project_id=9,
            name="Controlled replay",
            **_kwargs(),
        )
    )

    assert result is expected_job
    assert captured["db"] is db
    assert captured["job_type"] == (
        "incident_controlled_replay"
    )

    assert captured["required_capabilities"] == [
        "asr",
        "incident_controlled_replay",
        "incident_materialization",
        "incident_replay",
    ]


def test_controlled_replay_uses_generic_result_authority(
    monkeypatch,
):
    captured = {}

    def fake_enqueue(db, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(public_id="job")

    monkeypatch.setattr(
        service,
        "enqueue_job",
        fake_enqueue,
    )

    service.enqueue_incident_controlled_replay_job(
        object(),
        project_id=9,
        name="Controlled replay",
        **_kwargs(),
    )

    assert captured["job_type"] != (
        "asr_evaluation"
    )

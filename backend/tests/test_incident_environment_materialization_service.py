from __future__ import annotations

from types import SimpleNamespace

import app.incident_environment_materialization_service as service


def _sha(value: str) -> str:
    return value * 64


def test_enqueue_uses_fixed_materialization_job_contract(
    monkeypatch,
):
    request = SimpleNamespace(
        payload={
            "schema_version": 1,
            "type": (
                "incident_replay_compatibility_request"
            ),
        }
    )

    monkeypatch.setattr(
        service,
        "build_incident_replay_compatibility_request",
        lambda **kwargs: request,
    )

    captured = {}

    expected_job = SimpleNamespace(
        public_id="materialization-job"
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
        service
        .enqueue_incident_environment_materialization_job(
            db,
            project_id=7,
            name="Materialize incident",
            intake_payload={},
            expected_intake_sha256=_sha("1"),
            replay_preparation_payload={},
            expected_replay_preparation_sha256=_sha("2"),
            environment_manifest_payload={},
            expected_environment_manifest_sha256=_sha("3"),
        )
    )

    assert result is expected_job
    assert captured["db"] is db

    assert captured["job_type"] == (
        "incident_environment_materialization"
    )

    assert captured["required_capabilities"] == [
        "asr",
        "incident_materialization",
        "incident_replay",
    ]

    assert captured["input_payload"] is (
        request.payload
    )


def test_materialization_job_has_no_dedicated_result_authority(
    monkeypatch,
):
    request = SimpleNamespace(
        payload={"request": True}
    )

    monkeypatch.setattr(
        service,
        "build_incident_replay_compatibility_request",
        lambda **kwargs: request,
    )

    captured = {}

    def fake_enqueue(db, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(public_id="job")

    monkeypatch.setattr(
        service,
        "enqueue_job",
        fake_enqueue,
    )

    service.enqueue_incident_environment_materialization_job(
        object(),
        project_id=7,
        name="Materialization",
        intake_payload={},
        expected_intake_sha256=_sha("1"),
        replay_preparation_payload={},
        expected_replay_preparation_sha256=_sha("2"),
        environment_manifest_payload={},
        expected_environment_manifest_sha256=_sha("3"),
    )

    assert captured["job_type"] != (
        "asr_evaluation"
    )

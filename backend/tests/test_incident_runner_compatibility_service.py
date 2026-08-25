from __future__ import annotations

from types import SimpleNamespace

import pytest

import app.incident_runner_compatibility_service as service
from hvee.core.contracts import HveeContractError
from hvee.core.incident_runner_compatibility import (
    IncidentRunnerEnvironmentObservation,
)


def _sha(value: str) -> str:
    return value * 64


def _evidence_payload(kind: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "type": kind,
        "value": kind,
    }


def _builder_kwargs() -> dict[str, object]:
    return {
        "intake_payload": _evidence_payload("incident_intake"),
        "expected_intake_sha256": _sha("1"),
        "replay_preparation_payload": _evidence_payload(
            "incident_replay_preparation"
        ),
        "expected_replay_preparation_sha256": _sha("2"),
        "environment_manifest_payload": _evidence_payload(
            "incident_environment_manifest"
        ),
        "expected_environment_manifest_sha256": _sha("3"),
    }


@pytest.fixture
def trusted_upstream(monkeypatch):
    monkeypatch.setattr(
        service,
        "verify_incident_intake_bundle",
        lambda **kwargs: True,
    )
    monkeypatch.setattr(
        service,
        "verify_incident_replay_preparation_bundle",
        lambda **kwargs: True,
    )
    monkeypatch.setattr(
        service,
        "verify_incident_environment_manifest_bundle",
        lambda **kwargs: True,
    )


def test_request_binds_verified_upstream_evidence(
    trusted_upstream,
):
    request = (
        service.build_incident_replay_compatibility_request(
            **_builder_kwargs()
        )
    )

    assert request.payload["schema_version"] == 1
    assert request.payload["type"] == (
        "incident_replay_compatibility_request"
    )

    evidence = request.payload["evidence"]

    assert evidence["incident_intake"]["sha256"] == _sha("1")
    assert evidence["replay_preparation"]["sha256"] == _sha("2")
    assert evidence["environment_manifest"]["sha256"] == _sha("3")


def test_request_is_independent_from_source_mutation(
    trusted_upstream,
):
    values = _builder_kwargs()

    request = (
        service.build_incident_replay_compatibility_request(
            **values
        )
    )

    values["intake_payload"]["value"] = "mutated"

    assert (
        request.intake_payload["value"]
        == "incident_intake"
    )


def test_parse_accepts_exact_request(
    trusted_upstream,
):
    built = (
        service.build_incident_replay_compatibility_request(
            **_builder_kwargs()
        )
    )

    parsed = (
        service.parse_incident_replay_compatibility_request(
            built.payload
        )
    )

    assert parsed.payload == built.payload


def test_parse_rejects_extra_request_fields(
    trusted_upstream,
):
    built = (
        service.build_incident_replay_compatibility_request(
            **_builder_kwargs()
        )
    )

    tampered = dict(built.payload)
    tampered["unexpected"] = True

    with pytest.raises(
        HveeContractError,
        match="shape is invalid",
    ):
        service.parse_incident_replay_compatibility_request(
            tampered
        )


def test_parse_rejects_failed_upstream_verification(
    monkeypatch,
):
    values = _builder_kwargs()

    monkeypatch.setattr(
        service,
        "verify_incident_intake_bundle",
        lambda **kwargs: False,
    )

    with pytest.raises(
        HveeContractError,
        match="intake evidence failed verification",
    ):
        service.build_incident_replay_compatibility_request(
            **values
        )


def test_evaluate_delegates_to_compatibility_core(
    trusted_upstream,
    monkeypatch,
):
    built = (
        service.build_incident_replay_compatibility_request(
            **_builder_kwargs()
        )
    )

    observation = IncidentRunnerEnvironmentObservation(
        capabilities=("asr", "incident_replay"),
    )

    captured = {}

    expected = SimpleNamespace(
        payload={"compatibility": {"status": "blocked_unobserved"}},
        sha256=_sha("a"),
    )

    def fake_build(**kwargs):
        captured.update(kwargs)
        return expected

    monkeypatch.setattr(
        service,
        "build_incident_runner_compatibility_bundle",
        fake_build,
    )

    result = (
        service.evaluate_incident_replay_compatibility_request(
            request_payload=built.payload,
            required_capabilities=[
                "asr",
                "incident_replay",
            ],
            observation=observation,
        )
    )

    assert result is expected
    assert captured["expected_intake_sha256"] == _sha("1")
    assert (
        captured["expected_replay_preparation_sha256"]
        == _sha("2")
    )
    assert (
        captured["expected_environment_manifest_sha256"]
        == _sha("3")
    )
    assert captured["observation"] is observation


def test_enqueue_uses_fixed_job_type_and_capabilities(
    trusted_upstream,
    monkeypatch,
):
    captured = {}

    expected_job = SimpleNamespace(public_id="job-1")

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
        service.enqueue_incident_replay_compatibility_job(
            db,
            project_id=7,
            name="Incident compatibility",
            **_builder_kwargs(),
        )
    )

    assert result is expected_job
    assert captured["db"] is db
    assert captured["job_type"] == (
        "incident_replay_compatibility"
    )
    assert captured["required_capabilities"] == [
        "asr",
        "incident_replay",
    ]

    assert captured["input_payload"]["type"] == (
        "incident_replay_compatibility_request"
    )


def test_enqueue_never_creates_dedicated_result_authority(
    trusted_upstream,
    monkeypatch,
):
    captured = {}

    def fake_enqueue(db, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(public_id="job-2")

    monkeypatch.setattr(
        service,
        "enqueue_job",
        fake_enqueue,
    )

    service.enqueue_incident_replay_compatibility_job(
        object(),
        project_id=7,
        name="Incident compatibility",
        **_builder_kwargs(),
    )

    assert captured["job_type"] not in {
        "asr_evaluation",
    }


def test_required_capability_contract_is_fixed():
    assert (
        service.INCIDENT_REPLAY_COMPATIBILITY_REQUIRED_CAPABILITIES
        == (
            "asr",
            "incident_replay",
        )
    )

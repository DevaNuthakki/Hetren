from __future__ import annotations

import copy

import pytest

import app.incident_reproduction_evidence_service as service
import hvee.core.incident_reproduction_evidence as reproduction_core
from hvee.core.incident_runner_compatibility import (
    IncidentRunnerEnvironmentObservation,
)


def _sha(value: str) -> str:
    return value * 64


def _compatibility_observation():
    return IncidentRunnerEnvironmentObservation(
        capabilities=(
            "asr",
            "incident_replay",
        ),
    )


def _values():
    return {
        "intake_payload": {
            "evaluation_type": "asr",
            "incident": {
                "key": "incident-1",
                "version": "1",
            },
            "claim": {
                "reporter_evidence_sha256": (
                    _sha("1")
                ),
                "expected_behavior_commitment_sha256": (
                    _sha("2")
                ),
                "observed_behavior_commitment_sha256": (
                    _sha("3")
                ),
            },
        },
        "expected_intake_sha256": _sha("a"),
        "replay_preparation_payload": {
            "type": "preparation",
        },
        "expected_replay_preparation_sha256": (
            _sha("b")
        ),
        "environment_manifest_payload": {
            "type": "manifest",
        },
        "expected_environment_manifest_sha256": (
            _sha("c")
        ),
        "runner_compatibility_payload": {
            "type": "compatibility",
        },
        "expected_runner_compatibility_sha256": (
            _sha("d")
        ),
        "required_capabilities": (
            "asr",
            "incident_replay",
        ),
        "compatibility_observation": (
            _compatibility_observation()
        ),
        "environment_materialization_payload": {
            "type": "materialization",
        },
        "expected_environment_materialization_sha256": (
            _sha("e")
        ),
        "controlled_replay_payload": {
            "execution": {
                "status": "executed",
                "output": {
                    "generated_transcript_sha256": (
                        _sha("3")
                    ),
                },
            },
            "evidence_boundary": {
                "replay_executed": True,
                "replay_output_captured": True,
                "behavior_commitments_compared": False,
                "reproduction_claimed": False,
            },
        },
        "expected_controlled_replay_sha256": (
            _sha("f")
        ),
    }


@pytest.fixture(autouse=True)
def trusted_stage7(
    monkeypatch,
):
    monkeypatch.setattr(
        reproduction_core,
        "verify_incident_controlled_replay_bundle",
        lambda **kwargs: True,
    )


def _confirmed_values():
    return {
        **_values(),
        "comparison_basis": (
            "exact_generated_transcript_sha256_v1"
        ),
        "semantics_confirmation_sha256": (
            _sha("9")
        ),
    }


def test_service_builds_reproduced_result():
    result = (
        service
        .build_incident_reproduction_evidence_result(
            **_confirmed_values()
        )
    )

    assert result[
        "schema_version"
    ] == 1

    assert result["type"] == (
        "incident_reproduction_evidence_result"
    )

    payload = result[
        "reproduction_evidence"
    ]["payload"]

    assert payload[
        "comparison"
    ]["verdict"] == "reproduced"

    assert payload[
        "evidence_boundary"
    ]["reproduction_claimed"] is True


def test_service_builds_indeterminate_without_confirmed_semantics():
    result = (
        service
        .build_incident_reproduction_evidence_result(
            **{
                **_values(),
                "comparison_basis": "unavailable",
            }
        )
    )

    payload = result[
        "reproduction_evidence"
    ]["payload"]

    assert payload[
        "comparison"
    ]["verdict"] == "indeterminate"

    assert payload[
        "evidence_boundary"
    ]["reproduction_claimed"] is False


def test_service_rejects_unknown_comparison_basis():
    with pytest.raises(
        service.IncidentReproductionEvidenceServiceError,
        match="basis is unsupported",
    ):
        (
            service
            .build_incident_reproduction_evidence_result(
                **{
                    **_values(),
                    "comparison_basis": (
                        "semantic_similarity"
                    ),
                }
            )
        )


def test_service_requires_confirmation_for_exact_basis():
    with pytest.raises(
        service.IncidentReproductionEvidenceServiceError,
        match="requires semantic confirmation",
    ):
        (
            service
            .build_incident_reproduction_evidence_result(
                **{
                    **_values(),
                    "comparison_basis": (
                        "exact_generated_transcript_sha256_v1"
                    ),
                }
            )
        )


def test_service_verifier_accepts_matching_external_semantics():
    values = _confirmed_values()

    result = (
        service
        .build_incident_reproduction_evidence_result(
            **values
        )
    )

    assert (
        service
        .verify_incident_reproduction_evidence_result(
            result=result,
            **values,
        )
    )


def test_service_verifier_rejects_different_external_semantics():
    values = _confirmed_values()

    result = (
        service
        .build_incident_reproduction_evidence_result(
            **values
        )
    )

    verify_values = {
        **values,
        "comparison_basis": "unavailable",
        "semantics_confirmation_sha256": None,
    }

    assert not (
        service
        .verify_incident_reproduction_evidence_result(
            result=result,
            **verify_values,
        )
    )


def test_service_verifier_rejects_result_tampering():
    values = _confirmed_values()

    result = (
        service
        .build_incident_reproduction_evidence_result(
            **values
        )
    )

    tampered = copy.deepcopy(
        result
    )

    tampered[
        "reproduction_evidence"
    ]["payload"][
        "comparison"
    ]["verdict"] = "not_reproduced"

    assert not (
        service
        .verify_incident_reproduction_evidence_result(
            result=tampered,
            **values,
        )
    )


def test_service_result_contains_no_raw_transcript():
    result = (
        service
        .build_incident_reproduction_evidence_result(
            **_confirmed_values()
        )
    )

    serialized = str(
        result
    )

    assert "controlled replay output" not in serialized

    boundary = result[
        "reproduction_evidence"
    ]["payload"][
        "content_boundary"
    ]

    assert boundary[
        "raw_transcript_embedded"
    ] is False

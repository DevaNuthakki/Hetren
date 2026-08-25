from __future__ import annotations

import copy

import pytest

import hvee.core.incident_integration_gate as gate
from hvee.core.incident_reproduction_evidence import (
    IncidentReproductionComparisonBasis,
    IncidentReproductionComparisonObservation,
)
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


def _comparison_observation():
    return (
        IncidentReproductionComparisonObservation(
            basis=(
                IncidentReproductionComparisonBasis
                .EXACT_GENERATED_TRANSCRIPT_SHA256_V1
            ),
            semantics_confirmation_sha256=(
                _sha("9")
            ),
        )
    )


def _incident(
    **values,
):
    return {
        "key": "incident-1",
        "version": "1",
        **values,
    }


def _reproduction_payload(
    verdict: str = "reproduced",
):
    if verdict == "reproduced":
        comparison = {
            "status": "compared",
            "verdict": "reproduced",
            "reason": (
                "exact_reported_behavior_match"
            ),
            "reported_behavior_exact_match": True,
        }
        boundary = {
            "behavior_commitments_compared": True,
            "reproduction_determined": True,
            "reproduction_claimed": True,
        }

    elif verdict == "not_reproduced":
        comparison = {
            "status": "compared",
            "verdict": "not_reproduced",
            "reason": (
                "reported_behavior_mismatch"
            ),
            "reported_behavior_exact_match": False,
        }
        boundary = {
            "behavior_commitments_compared": True,
            "reproduction_determined": True,
            "reproduction_claimed": False,
        }

    else:
        comparison = {
            "status": "indeterminate",
            "verdict": "indeterminate",
            "reason": (
                "behavior_commitment_semantics_unconfirmed"
            ),
            "reported_behavior_exact_match": None,
        }
        boundary = {
            "behavior_commitments_compared": False,
            "reproduction_determined": False,
            "reproduction_claimed": False,
        }

    return {
        "evaluation_type": "asr",
        "incident": _incident(
            intake_sha256=_sha("a"),
            replay_preparation_sha256=_sha("b"),
            environment_manifest_sha256=_sha("c"),
            runner_compatibility_sha256=_sha("d"),
            environment_materialization_sha256=_sha("e"),
            controlled_replay_sha256=_sha("f"),
        ),
        "comparison": comparison,
        "evidence_boundary": {
            **boundary,
            "model_failure_verified": False,
            "causal_explanation_claimed": False,
            "counterexample_confirmed": False,
            "contract_promoted": False,
            "blocking_release_gate_enabled": False,
            "qualification_authority": False,
        },
    }


def _values(
    *,
    verdict: str = "reproduced",
):
    return {
        "intake_payload": {
            "evaluation_type": "asr",
            "incident": _incident(
                source_event_commitment_sha256=(
                    _sha("1")
                ),
            ),
        },
        "expected_intake_sha256": _sha("a"),
        "replay_preparation_payload": {
            "evaluation_type": "asr",
            "incident": _incident(
                intake_sha256=_sha("a"),
                context_sha256=_sha("0"),
            ),
            "artifact_verification": {
                "status": "verified",
                "all_referenced_artifacts_verified": True,
                "runner_custody_status": "verified",
            },
            "preparation": {
                "status": "prepared",
                "replay_plan_prepared": True,
            },
            "evidence_boundary": {
                "artifact_bytes_verified": True,
                "replay_plan_prepared": True,
                "replay_executed": False,
            },
        },
        "expected_replay_preparation_sha256": (
            _sha("b")
        ),
        "environment_manifest_payload": {
            "evaluation_type": "asr",
            "incident": _incident(
                intake_sha256=_sha("a"),
                replay_preparation_sha256=_sha("b"),
            ),
            "environment": {
                "status": "ready",
                "materialization_started": False,
            },
            "evidence_boundary": {
                "environment_materialized": False,
                "replay_executed": False,
            },
        },
        "expected_environment_manifest_sha256": (
            _sha("c")
        ),
        "runner_compatibility_payload": {
            "evaluation_type": "asr",
            "incident": _incident(
                intake_sha256=_sha("a"),
                replay_preparation_sha256=_sha("b"),
                environment_manifest_sha256=_sha("c"),
            ),
            "compatibility": {
                "status": "compatible",
                "ready_for_materialization": True,
            },
            "evidence_boundary": {
                "environment_materialized": False,
                "replay_executed": False,
            },
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
            "evaluation_type": "asr",
            "incident": _incident(
                intake_sha256=_sha("a"),
                replay_preparation_sha256=_sha("b"),
                environment_manifest_sha256=_sha("c"),
                runner_compatibility_sha256=_sha("d"),
            ),
            "materialization": {
                "status": "materialized",
                "environment_materialized": True,
            },
            "evidence_boundary": {
                "operator_authorization_granted": True,
                "environment_materialized": True,
                "replay_executed": False,
            },
        },
        "expected_environment_materialization_sha256": (
            _sha("e")
        ),
        "controlled_replay_payload": {
            "evaluation_type": "asr",
            "incident": _incident(
                intake_sha256=_sha("a"),
                replay_preparation_sha256=_sha("b"),
                environment_manifest_sha256=_sha("c"),
                runner_compatibility_sha256=_sha("d"),
                environment_materialization_sha256=_sha("e"),
            ),
            "execution": {
                "status": "executed",
            },
            "evidence_boundary": {
                "operator_authorization_granted": True,
                "environment_materialized": True,
                "replay_executed": True,
                "replay_output_captured": True,
                "behavior_commitments_compared": False,
                "reproduction_claimed": False,
            },
        },
        "expected_controlled_replay_sha256": (
            _sha("f")
        ),
        "reproduction_evidence_payload": (
            _reproduction_payload(
                verdict
            )
        ),
        "expected_reproduction_evidence_sha256": (
            _sha("7")
        ),
        "comparison_observation": (
            _comparison_observation()
        ),
    }


@pytest.fixture(autouse=True)
def trusted_complete_chain(
    monkeypatch,
):
    monkeypatch.setattr(
        gate,
        "verify_incident_reproduction_evidence_bundle",
        lambda **kwargs: True,
    )


def test_verified_reproduced_chain():
    bundle = (
        gate
        .build_incident_integration_gate_bundle(
            **_values(
                verdict="reproduced"
            )
        )
    )

    integration = bundle.payload[
        "integration"
    ]

    assert integration["status"] == (
        "verified_reproduced"
    )

    assert integration[
        "integration_verified"
    ] is True

    assert integration[
        "reproduction_verdict"
    ] == "reproduced"

    assert integration[
        "incident_reproduced"
    ] is True


def test_verified_not_reproduced_chain():
    bundle = (
        gate
        .build_incident_integration_gate_bundle(
            **_values(
                verdict="not_reproduced"
            )
        )
    )

    integration = bundle.payload[
        "integration"
    ]

    assert integration["status"] == (
        "verified_not_reproduced"
    )

    assert integration[
        "integration_verified"
    ] is True

    assert integration[
        "incident_reproduced"
    ] is False

    assert integration[
        "reproduction_determined"
    ] is True


def test_verified_indeterminate_chain():
    bundle = (
        gate
        .build_incident_integration_gate_bundle(
            **_values(
                verdict="indeterminate"
            )
        )
    )

    integration = bundle.payload[
        "integration"
    ]

    assert integration["status"] == (
        "verified_indeterminate"
    )

    assert integration[
        "integration_verified"
    ] is True

    assert integration[
        "reproduction_verdict"
    ] == "indeterminate"

    assert integration[
        "reproduction_determined"
    ] is False

    assert integration[
        "incident_reproduced"
    ] is False


def test_integration_verification_is_separate_from_reproduction():
    bundle = (
        gate
        .build_incident_integration_gate_bundle(
            **_values(
                verdict="indeterminate"
            )
        )
    )

    assert bundle.payload[
        "integration"
    ]["integration_verified"] is True

    assert bundle.payload[
        "evidence_boundary"
    ]["reproduction_claimed"] is False


def test_failed_complete_chain_reverification_blocks(
    monkeypatch,
):
    monkeypatch.setattr(
        gate,
        "verify_incident_reproduction_evidence_bundle",
        lambda **kwargs: False,
    )

    bundle = (
        gate
        .build_incident_integration_gate_bundle(
            **_values()
        )
    )

    integration = bundle.payload[
        "integration"
    ]

    assert integration["status"] == (
        "blocked_inconsistent_chain"
    )

    assert integration[
        "integration_verified"
    ] is False

    assert integration[
        "reproduction_verdict"
    ] is None

    assert (
        "complete_chain_reverification_failed"
        in integration["blocking_reasons"]
    )


def test_cross_stage_identity_mismatch_blocks():
    values = _values()

    values[
        "controlled_replay_payload"
    ]["incident"]["key"] = (
        "different-incident"
    )

    bundle = (
        gate
        .build_incident_integration_gate_bundle(
            **values
        )
    )

    assert bundle.payload[
        "integration"
    ]["status"] == (
        "blocked_inconsistent_chain"
    )

    assert (
        "cross_stage_incident_identity_mismatch"
        in bundle.payload[
            "integration"
        ]["blocking_reasons"]
    )


def test_cross_stage_commitment_mismatch_blocks():
    values = _values()

    values[
        "environment_materialization_payload"
    ]["incident"][
        "runner_compatibility_sha256"
    ] = _sha("8")

    bundle = (
        gate
        .build_incident_integration_gate_bundle(
            **values
        )
    )

    assert bundle.payload[
        "integration"
    ][
        "upstream_commitments_consistent"
    ] is False

    assert bundle.payload[
        "integration"
    ]["status"] == (
        "blocked_inconsistent_chain"
    )


def test_blocked_materialization_cannot_form_verified_integration():
    values = _values()

    values[
        "environment_materialization_payload"
    ]["materialization"][
        "status"
    ] = "blocked_compatibility"

    values[
        "environment_materialization_payload"
    ]["materialization"][
        "environment_materialized"
    ] = False

    bundle = (
        gate
        .build_incident_integration_gate_bundle(
            **values
        )
    )

    assert bundle.payload[
        "integration"
    ][
        "stage_boundaries_consistent"
    ] is False

    assert bundle.payload[
        "integration"
    ]["status"] == (
        "blocked_inconsistent_chain"
    )


def test_stage7_cannot_have_compared_behavior_commitments():
    values = _values()

    values[
        "controlled_replay_payload"
    ]["evidence_boundary"][
        "behavior_commitments_compared"
    ] = True

    bundle = (
        gate
        .build_incident_integration_gate_bundle(
            **values
        )
    )

    assert bundle.payload[
        "integration"
    ]["status"] == (
        "blocked_inconsistent_chain"
    )


def test_reproduced_verdict_boundary_contradiction_blocks():
    values = _values(
        verdict="reproduced"
    )

    values[
        "reproduction_evidence_payload"
    ]["evidence_boundary"][
        "reproduction_claimed"
    ] = False

    bundle = (
        gate
        .build_incident_integration_gate_bundle(
            **values
        )
    )

    assert bundle.payload[
        "integration"
    ][
        "stage_boundaries_consistent"
    ] is False

    assert bundle.payload[
        "integration"
    ]["status"] == (
        "blocked_inconsistent_chain"
    )


def test_blocked_gate_never_exposes_unverified_reproduction():
    values = _values()

    values[
        "controlled_replay_payload"
    ]["incident"][
        "environment_materialization_sha256"
    ] = _sha("8")

    bundle = (
        gate
        .build_incident_integration_gate_bundle(
            **values
        )
    )

    integration = bundle.payload[
        "integration"
    ]

    assert integration[
        "integration_verified"
    ] is False

    assert integration[
        "reproduction_verdict"
    ] is None

    assert integration[
        "reproduction_determined"
    ] is False

    assert integration[
        "incident_reproduced"
    ] is False


def test_final_gate_never_grants_failure_or_governance_authority():
    bundle = (
        gate
        .build_incident_integration_gate_bundle(
            **_values()
        )
    )

    boundary = bundle.payload[
        "evidence_boundary"
    ]

    assert boundary[
        "model_failure_verified"
    ] is False

    assert boundary[
        "causal_explanation_claimed"
    ] is False

    assert boundary[
        "counterexample_confirmed"
    ] is False

    assert boundary[
        "contract_promoted"
    ] is False

    assert boundary[
        "blocking_release_gate_enabled"
    ] is False

    assert boundary[
        "governance_assurance_completed"
    ] is False

    assert boundary[
        "release_authority_granted"
    ] is False

    assert boundary[
        "qualification_authority"
    ] is False


def test_final_gate_contains_only_commitments_not_upstream_payloads():
    bundle = (
        gate
        .build_incident_integration_gate_bundle(
            **_values()
        )
    )

    boundary = bundle.payload[
        "content_boundary"
    ]

    assert boundary[
        "raw_audio_embedded"
    ] is False

    assert boundary[
        "raw_transcript_embedded"
    ] is False

    assert boundary[
        "artifact_bytes_embedded"
    ] is False

    assert boundary[
        "environment_values_embedded"
    ] is False

    assert boundary[
        "upstream_payloads_embedded"
    ] is False

    assert boundary[
        "upstream_commitments_embedded"
    ] is True


def test_integration_hash_is_reproducible():
    first = (
        gate
        .build_incident_integration_gate_bundle(
            **_values()
        )
    )

    second = (
        gate
        .build_incident_integration_gate_bundle(
            **_values()
        )
    )

    assert first.payload == second.payload
    assert first.sha256 == second.sha256


def test_verifier_accepts_exact_gate():
    values = _values()

    bundle = (
        gate
        .build_incident_integration_gate_bundle(
            **values
        )
    )

    assert (
        gate
        .verify_incident_integration_gate_bundle(
            payload=bundle.payload,
            expected_sha256=bundle.sha256,
            **values,
        )
    )


def test_verifier_rejects_gate_tampering():
    values = _values()

    bundle = (
        gate
        .build_incident_integration_gate_bundle(
            **values
        )
    )

    tampered = copy.deepcopy(
        bundle.payload
    )

    tampered[
        "integration"
    ]["status"] = (
        "verified_not_reproduced"
    )

    assert not (
        gate
        .verify_incident_integration_gate_bundle(
            payload=tampered,
            expected_sha256=bundle.sha256,
            **values,
        )
    )


def test_verifier_rejects_wrong_gate_digest():
    values = _values()

    bundle = (
        gate
        .build_incident_integration_gate_bundle(
            **values
        )
    )

    assert not (
        gate
        .verify_incident_integration_gate_bundle(
            payload=bundle.payload,
            expected_sha256=_sha("8"),
            **values,
        )
    )

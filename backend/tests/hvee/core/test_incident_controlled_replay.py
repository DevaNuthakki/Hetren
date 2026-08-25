from __future__ import annotations

import copy

import pytest

import hvee.core.incident_controlled_replay as replay
from hvee.core.contracts import HveeContractError
from hvee.core.incident_controlled_replay import (
    IncidentControlledReplayArtifactObservation,
    IncidentControlledReplayExecutionObservation,
    IncidentControlledReplayOutputObservation,
)
from hvee.core.incident_runner_compatibility import (
    IncidentRunnerEnvironmentObservation,
)


def _sha(value: str) -> str:
    return value * 64


def _intake():
    return {
        "evaluation_type": "asr",
        "incident": {
            "key": "incident-1",
            "version": "1",
        },
    }


def _receipt(
    *,
    kind="source_audio",
    digest=None,
    length=12,
    media_type="audio/wav",
):
    digest = digest or _sha("1")

    return {
        "kind": kind,
        "reference_sha256": digest,
        "expected_byte_length": length,
        "media_type": media_type,
        "observed_sha256": digest,
        "observed_byte_length": length,
        "status": "verified",
    }


def _preparation(
    *,
    receipts=None,
    operations=None,
):
    receipts = (
        [_receipt()]
        if receipts is None
        else receipts
    )

    operations = operations or [
        "verify_intake_commitment",
        "verify_artifact_manifest",
        "restore_runtime_context",
        "restore_audio_context",
        "restore_transport_context",
        "stage_source_audio",
        "execute_isolated_replay",
        "capture_replay_output",
        "compare_behavior_commitments",
    ]

    return {
        "artifact_verification": {
            "all_referenced_artifacts_verified": True,
            "runner_custody_status": "verified",
            "receipts": receipts,
        },
        "replay_plan": {
            "execution_started": False,
            "steps": [
                {
                    "ordinal": index,
                    "operation": operation,
                    "input_commitment_sha256s": [
                        _sha("9")
                    ],
                    "status": "planned",
                }
                for index, operation in enumerate(
                    operations,
                    start=1,
                )
            ],
        },
    }


def _manifest():
    return {
        "type": "incident_environment_manifest",
    }


def _compatibility():
    return {
        "type": "incident_runner_compatibility",
    }


def _materialization(
    *,
    status="materialized",
    environment_materialized=True,
    authorized=True,
):
    return {
        "materialization": {
            "status": status,
            "environment_materialized": (
                environment_materialized
            ),
        },
        "evidence_boundary": {
            "operator_authorization_granted": authorized,
            "environment_materialized": (
                environment_materialized
            ),
        },
    }


def _compatibility_observation():
    return IncidentRunnerEnvironmentObservation(
        capabilities=(
            "asr",
            "incident_materialization",
            "incident_replay",
        ),
    )


def _artifact_observation(
    *,
    kind="source_audio",
    reference=None,
    expected_length=12,
    media_type="audio/wav",
    observed=None,
    observed_length=12,
):
    reference = reference or _sha("1")
    observed = observed or reference

    return (
        IncidentControlledReplayArtifactObservation(
            kind=kind,
            reference_sha256=reference,
            expected_byte_length=expected_length,
            media_type=media_type,
            observed_sha256=observed,
            observed_byte_length=observed_length,
        )
    )


def _output(
    *,
    transcript_sha=None,
):
    return (
        IncidentControlledReplayOutputObservation(
            generated_transcript_sha256=(
                transcript_sha or _sha("7")
            ),
            generated_transcript_utf8_bytes=18,
            provider="faster_whisper",
            model_name="large-v3-turbo",
            device="cpu",
            compute_type="int8_float32",
        )
    )


def _completed_operations():
    return (
        "verify_intake_commitment",
        "verify_artifact_manifest",
        "restore_runtime_context",
        "restore_audio_context",
        "restore_transport_context",
        "stage_source_audio",
        "execute_isolated_replay",
        "capture_replay_output",
    )


def _execution(
    *,
    operations=None,
    artifacts=None,
    output=None,
):
    return (
        IncidentControlledReplayExecutionObservation(
            completed_operations=(
                operations
                if operations is not None
                else _completed_operations()
            ),
            artifacts=(
                artifacts
                if artifacts is not None
                else (
                    _artifact_observation(),
                )
            ),
            output=output or _output(),
        )
    )


def _builder_kwargs(
    *,
    preparation=None,
    materialization=None,
    execution=None,
):
    return {
        "intake_payload": _intake(),
        "expected_intake_sha256": _sha("a"),
        "replay_preparation_payload": (
            preparation or _preparation()
        ),
        "expected_replay_preparation_sha256": _sha("b"),
        "environment_manifest_payload": _manifest(),
        "expected_environment_manifest_sha256": _sha("c"),
        "runner_compatibility_payload": _compatibility(),
        "expected_runner_compatibility_sha256": _sha("d"),
        "required_capabilities": (
            "asr",
            "incident_materialization",
            "incident_replay",
        ),
        "compatibility_observation": (
            _compatibility_observation()
        ),
        "environment_materialization_payload": (
            materialization or _materialization()
        ),
        "expected_environment_materialization_sha256": _sha("e"),
        "execution_observation": (
            execution or _execution()
        ),
    }


@pytest.fixture(autouse=True)
def trusted_materialization(monkeypatch):
    monkeypatch.setattr(
        replay,
        "verify_incident_environment_materialization_bundle",
        lambda **kwargs: True,
    )


def test_successful_controlled_replay_is_commitment_only():
    bundle = (
        replay.build_incident_controlled_replay_bundle(
            **_builder_kwargs()
        )
    )

    assert (
        bundle.payload["execution"]["status"]
        == "executed"
    )

    assert bundle.payload[
        "evidence_boundary"
    ]["replay_executed"] is True

    assert bundle.payload[
        "evidence_boundary"
    ]["replay_output_captured"] is True


def test_behavior_comparison_is_deferred():
    bundle = (
        replay.build_incident_controlled_replay_bundle(
            **_builder_kwargs()
        )
    )

    execution = bundle.payload["execution"]

    assert execution["deferred_operation"] == (
        "compare_behavior_commitments"
    )

    assert (
        "compare_behavior_commitments"
        not in execution[
            "completed_operations"
        ]
    )

    assert bundle.payload[
        "evidence_boundary"
    ]["behavior_commitments_compared"] is False


def test_successful_replay_does_not_claim_reproduction():
    bundle = (
        replay.build_incident_controlled_replay_bundle(
            **_builder_kwargs()
        )
    )

    boundary = bundle.payload[
        "evidence_boundary"
    ]

    assert boundary["reproduction_claimed"] is False
    assert boundary["model_failure_verified"] is False
    assert boundary["causal_explanation_claimed"] is False
    assert boundary["counterexample_confirmed"] is False
    assert boundary["contract_promoted"] is False
    assert boundary[
        "blocking_release_gate_enabled"
    ] is False
    assert boundary["qualification_authority"] is False


def test_raw_transcript_is_not_persisted():
    bundle = (
        replay.build_incident_controlled_replay_bundle(
            **_builder_kwargs()
        )
    )

    output = bundle.payload[
        "execution"
    ]["output"]

    assert "transcript" not in output
    assert (
        output["generated_transcript_sha256"]
        == _sha("7")
    )


def test_materialization_must_be_materialized():
    with pytest.raises(
        HveeContractError,
        match="requires a materialized environment",
    ):
        replay.build_incident_controlled_replay_bundle(
            **_builder_kwargs(
                materialization=(
                    _materialization(
                        status="blocked_compatibility",
                        environment_materialized=False,
                    )
                )
            )
        )


def test_operator_authorization_must_be_preserved():
    with pytest.raises(
        HveeContractError,
        match="requires authorized materialization",
    ):
        replay.build_incident_controlled_replay_bundle(
            **_builder_kwargs(
                materialization=(
                    _materialization(
                        authorized=False,
                    )
                )
            )
        )


def test_materialization_must_reverify(
    monkeypatch,
):
    monkeypatch.setattr(
        replay,
        "verify_incident_environment_materialization_bundle",
        lambda **kwargs: False,
    )

    with pytest.raises(
        HveeContractError,
        match="failed verification",
    ):
        replay.build_incident_controlled_replay_bundle(
            **_builder_kwargs()
        )


def test_same_length_artifact_corruption_is_rejected():
    bad = _artifact_observation(
        observed=_sha("f"),
        observed_length=12,
    )

    with pytest.raises(
        HveeContractError,
        match="reverification failed",
    ):
        replay.build_incident_controlled_replay_bundle(
            **_builder_kwargs(
                execution=_execution(
                    artifacts=(bad,),
                )
            )
        )


def test_artifact_length_mismatch_is_rejected():
    bad = _artifact_observation(
        observed_length=13,
    )

    with pytest.raises(
        HveeContractError,
        match="reverification failed",
    ):
        replay.build_incident_controlled_replay_bundle(
            **_builder_kwargs(
                execution=_execution(
                    artifacts=(bad,),
                )
            )
        )


def test_missing_artifact_is_rejected():
    with pytest.raises(
        HveeContractError,
        match="exactly cover",
    ):
        replay.build_incident_controlled_replay_bundle(
            **_builder_kwargs(
                execution=_execution(
                    artifacts=(),
                )
            )
        )


def test_transport_trace_is_reverified_when_prepared():
    trace = _receipt(
        kind="transport_trace",
        digest=_sha("2"),
        length=8,
        media_type="application/json",
    )

    preparation = _preparation(
        receipts=[
            _receipt(),
            trace,
        ],
        operations=[
            "verify_intake_commitment",
            "verify_artifact_manifest",
            "restore_runtime_context",
            "restore_audio_context",
            "restore_transport_context",
            "stage_source_audio",
            "stage_transport_trace",
            "execute_isolated_replay",
            "capture_replay_output",
            "compare_behavior_commitments",
        ],
    )

    artifacts = tuple(
        sorted(
            (
                _artifact_observation(),
                _artifact_observation(
                    kind="transport_trace",
                    reference=_sha("2"),
                    expected_length=8,
                    media_type="application/json",
                    observed=_sha("2"),
                    observed_length=8,
                ),
            ),
            key=lambda value: value.identity,
        )
    )

    operations = (
        "verify_intake_commitment",
        "verify_artifact_manifest",
        "restore_runtime_context",
        "restore_audio_context",
        "restore_transport_context",
        "stage_source_audio",
        "stage_transport_trace",
        "execute_isolated_replay",
        "capture_replay_output",
    )

    bundle = (
        replay.build_incident_controlled_replay_bundle(
            **_builder_kwargs(
                preparation=preparation,
                execution=_execution(
                    operations=operations,
                    artifacts=artifacts,
                ),
            )
        )
    )

    assert (
        bundle.payload["execution"][
            "artifact_reverification"
        ]["count"]
        == 2
    )


def test_completed_operations_must_match_frozen_plan():
    operations = (
        "verify_intake_commitment",
        "verify_artifact_manifest",
        "restore_runtime_context",
        "restore_audio_context",
        "restore_transport_context",
        "stage_source_audio",
        "capture_replay_output",
    )

    with pytest.raises(
        HveeContractError,
        match="do not match",
    ):
        replay.build_incident_controlled_replay_bundle(
            **_builder_kwargs(
                execution=_execution(
                    operations=operations,
                )
            )
        )


def test_stage7_cannot_execute_behavior_comparison():
    operations = (
        *_completed_operations(),
        "compare_behavior_commitments",
    )

    with pytest.raises(
        HveeContractError,
    ):
        replay.build_incident_controlled_replay_bundle(
            **_builder_kwargs(
                execution=_execution(
                    operations=operations,
                )
            )
        )


def test_replay_plan_requires_comparison_as_final_step():
    preparation = _preparation(
        operations=[
            "verify_intake_commitment",
            "verify_artifact_manifest",
            "restore_runtime_context",
            "restore_audio_context",
            "restore_transport_context",
            "stage_source_audio",
            "compare_behavior_commitments",
            "execute_isolated_replay",
            "capture_replay_output",
        ]
    )

    with pytest.raises(
        HveeContractError,
        match="execution boundary changed",
    ):
        replay.build_incident_controlled_replay_bundle(
            **_builder_kwargs(
                preparation=preparation
            )
        )


def test_hash_is_reproducible():
    first = (
        replay.build_incident_controlled_replay_bundle(
            **_builder_kwargs()
        )
    )

    second = (
        replay.build_incident_controlled_replay_bundle(
            **_builder_kwargs()
        )
    )

    assert first.payload == second.payload
    assert first.sha256 == second.sha256


def test_output_change_changes_evidence_identity():
    first = (
        replay.build_incident_controlled_replay_bundle(
            **_builder_kwargs()
        )
    )

    second = (
        replay.build_incident_controlled_replay_bundle(
            **_builder_kwargs(
                execution=_execution(
                    output=_output(
                        transcript_sha=_sha("8")
                    )
                )
            )
        )
    )

    assert first.sha256 != second.sha256


def test_verifier_accepts_exact_bundle():
    values = _builder_kwargs()

    bundle = (
        replay.build_incident_controlled_replay_bundle(
            **values
        )
    )

    assert replay.verify_incident_controlled_replay_bundle(
        payload=bundle.payload,
        expected_sha256=bundle.sha256,
        intake_payload=values["intake_payload"],
        expected_intake_sha256=(
            values["expected_intake_sha256"]
        ),
        replay_preparation_payload=(
            values["replay_preparation_payload"]
        ),
        expected_replay_preparation_sha256=(
            values[
                "expected_replay_preparation_sha256"
            ]
        ),
        environment_manifest_payload=(
            values["environment_manifest_payload"]
        ),
        expected_environment_manifest_sha256=(
            values[
                "expected_environment_manifest_sha256"
            ]
        ),
        runner_compatibility_payload=(
            values["runner_compatibility_payload"]
        ),
        expected_runner_compatibility_sha256=(
            values[
                "expected_runner_compatibility_sha256"
            ]
        ),
        required_capabilities=(
            values["required_capabilities"]
        ),
        compatibility_observation=(
            values["compatibility_observation"]
        ),
        environment_materialization_payload=(
            values[
                "environment_materialization_payload"
            ]
        ),
        expected_environment_materialization_sha256=(
            values[
                "expected_environment_materialization_sha256"
            ]
        ),
    )


def test_verifier_rejects_tampering():
    values = _builder_kwargs()

    bundle = (
        replay.build_incident_controlled_replay_bundle(
            **values
        )
    )

    tampered = copy.deepcopy(
        bundle.payload
    )

    tampered["evidence_boundary"][
        "reproduction_claimed"
    ] = True

    assert not (
        replay.verify_incident_controlled_replay_bundle(
            payload=tampered,
            expected_sha256=bundle.sha256,
            intake_payload=values["intake_payload"],
            expected_intake_sha256=(
                values["expected_intake_sha256"]
            ),
            replay_preparation_payload=(
                values[
                    "replay_preparation_payload"
                ]
            ),
            expected_replay_preparation_sha256=(
                values[
                    "expected_replay_preparation_sha256"
                ]
            ),
            environment_manifest_payload=(
                values[
                    "environment_manifest_payload"
                ]
            ),
            expected_environment_manifest_sha256=(
                values[
                    "expected_environment_manifest_sha256"
                ]
            ),
            runner_compatibility_payload=(
                values[
                    "runner_compatibility_payload"
                ]
            ),
            expected_runner_compatibility_sha256=(
                values[
                    "expected_runner_compatibility_sha256"
                ]
            ),
            required_capabilities=(
                values["required_capabilities"]
            ),
            compatibility_observation=(
                values[
                    "compatibility_observation"
                ]
            ),
            environment_materialization_payload=(
                values[
                    "environment_materialization_payload"
                ]
            ),
            expected_environment_materialization_sha256=(
                values[
                    "expected_environment_materialization_sha256"
                ]
            ),
        )
    )


def test_transcript_helper_hashes_exact_utf8():
    first = (
        replay.calculate_incident_generated_transcript_sha256(
            "hello world"
        )
    )

    second = (
        replay.calculate_incident_generated_transcript_sha256(
            "hello world "
        )
    )

    assert first != second


def test_non_execution_evidence_receipt_is_not_replay_artifact():
    report = _receipt(
        kind="incident_report",
        digest=_sha("3"),
        length=9,
        media_type="application/json",
    )

    trace = _receipt(
        kind="transport_trace",
        digest=_sha("2"),
        length=8,
        media_type="application/json",
    )

    preparation = _preparation(
        receipts=[
            report,
            _receipt(),
            trace,
        ],
        operations=[
            "verify_intake_commitment",
            "verify_artifact_manifest",
            "restore_runtime_context",
            "restore_audio_context",
            "restore_transport_context",
            "stage_source_audio",
            "stage_transport_trace",
            "execute_isolated_replay",
            "capture_replay_output",
            "compare_behavior_commitments",
        ],
    )

    artifacts = tuple(
        sorted(
            (
                _artifact_observation(),
                _artifact_observation(
                    kind="transport_trace",
                    reference=_sha("2"),
                    expected_length=8,
                    media_type="application/json",
                    observed=_sha("2"),
                    observed_length=8,
                ),
            ),
            key=lambda value: value.identity,
        )
    )

    operations = (
        "verify_intake_commitment",
        "verify_artifact_manifest",
        "restore_runtime_context",
        "restore_audio_context",
        "restore_transport_context",
        "stage_source_audio",
        "stage_transport_trace",
        "execute_isolated_replay",
        "capture_replay_output",
    )

    bundle = (
        replay.build_incident_controlled_replay_bundle(
            **_builder_kwargs(
                preparation=preparation,
                execution=_execution(
                    operations=operations,
                    artifacts=artifacts,
                ),
            )
        )
    )

    assert (
        bundle.payload["execution"][
            "artifact_reverification"
        ]["count"]
        == 2
    )


def test_non_execution_evidence_receipt_must_still_be_exact():
    report = _receipt(
        kind="incident_report",
        digest=_sha("3"),
        length=9,
        media_type="application/json",
    )

    report["observed_sha256"] = _sha("4")

    preparation = _preparation(
        receipts=[
            report,
            _receipt(),
        ],
    )

    with pytest.raises(
        HveeContractError,
        match="prepared artifact receipt is not exact",
    ):
        replay.build_incident_controlled_replay_bundle(
            **_builder_kwargs(
                preparation=preparation,
            )
        )

from __future__ import annotations

import copy

import pytest

import hvee.core.incident_environment_materialization as materialization
from hvee.core.contracts import HveeContractError
from hvee.core.incident_environment_materialization import (
    IncidentEnvironmentMaterializationStatus,
    IncidentMaterializedRequirementObservation,
    IncidentOperatorAuthorization,
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


def _preparation():
    return {
        "type": "incident_replay_preparation",
    }


def _manifest():
    return {
        "type": "incident_environment_manifest",
    }


def _compatibility(
    *,
    status="compatible",
    ready=True,
):
    requirements = [
        {
            "requirement": "audio.codec_name",
            "level": "compatible",
            "expected_commitment_sha256": _sha("4"),
            "observed_commitment_sha256": None,
        },
        {
            "requirement": "runtime.host_environment_sha256",
            "level": "compatible",
            "expected_commitment_sha256": _sha("3"),
            "observed_commitment_sha256": _sha("8"),
        },
        {
            "requirement": "runtime.source_code_sha256",
            "level": "exact",
            "expected_commitment_sha256": _sha("1"),
            "observed_commitment_sha256": _sha("1"),
        },
        {
            "requirement": "transport.kind",
            "level": "compatible",
            "expected_commitment_sha256": _sha("5"),
            "observed_commitment_sha256": None,
        },
    ]

    return {
        "compatibility": {
            "status": status,
            "ready_for_materialization": ready,
            "requirements": sorted(
                requirements,
                key=lambda value: value["requirement"],
            ),
        },
    }


def _compatibility_observation():
    return IncidentRunnerEnvironmentObservation(
        capabilities=(
            "asr",
            "incident_replay",
        ),
    )


def _authorization(granted=True):
    return IncidentOperatorAuthorization(
        granted=granted,
        authorization_sha256=(
            _sha("a")
            if granted
            else None
        ),
    )


def _observations(
    *,
    host_digest=None,
    source_digest=None,
    audio_digest=None,
    transport_digest=None,
):
    return (
        IncidentMaterializedRequirementObservation(
            requirement="audio.codec_name",
            observed_commitment_sha256=(
                _sha("4")
                if audio_digest is None
                else audio_digest
            ),
        ),
        IncidentMaterializedRequirementObservation(
            requirement=(
                "runtime.host_environment_sha256"
            ),
            observed_commitment_sha256=(
                _sha("9")
                if host_digest is None
                else host_digest
            ),
        ),
        IncidentMaterializedRequirementObservation(
            requirement=(
                "runtime.source_code_sha256"
            ),
            observed_commitment_sha256=(
                _sha("1")
                if source_digest is None
                else source_digest
            ),
        ),
        IncidentMaterializedRequirementObservation(
            requirement="transport.kind",
            observed_commitment_sha256=(
                _sha("5")
                if transport_digest is None
                else transport_digest
            ),
        ),
    )


def _builder_kwargs(
    *,
    compatibility_payload=None,
    authorization=None,
    observations=None,
):
    return {
        "intake_payload": _intake(),
        "expected_intake_sha256": _sha("b"),
        "replay_preparation_payload": _preparation(),
        "expected_replay_preparation_sha256": _sha("c"),
        "environment_manifest_payload": _manifest(),
        "expected_environment_manifest_sha256": _sha("d"),
        "runner_compatibility_payload": (
            compatibility_payload
            if compatibility_payload is not None
            else _compatibility()
        ),
        "expected_runner_compatibility_sha256": _sha("e"),
        "required_capabilities": (
            "asr",
            "incident_replay",
        ),
        "compatibility_observation": (
            _compatibility_observation()
        ),
        "authorization": (
            authorization
            if authorization is not None
            else _authorization()
        ),
        "materialization_observations": (
            observations
            if observations is not None
            else _observations()
        ),
    }


@pytest.fixture(autouse=True)
def trusted_compatibility(monkeypatch):
    monkeypatch.setattr(
        materialization,
        "verify_incident_runner_compatibility_bundle",
        lambda **kwargs: True,
    )


def test_materializes_when_all_required_commitments_are_observed():
    bundle = (
        materialization
        .build_incident_environment_materialization_bundle(
            **_builder_kwargs()
        )
    )

    assert (
        bundle.payload["materialization"]["status"]
        == IncidentEnvironmentMaterializationStatus
        .MATERIALIZED.value
    )

    assert (
        bundle.payload["materialization"][
            "environment_materialized"
        ]
        is True
    )

    assert (
        bundle.payload["evidence_boundary"][
            "environment_materialized"
        ]
        is True
    )


def test_different_host_environment_is_portable():
    bundle = (
        materialization
        .build_incident_environment_materialization_bundle(
            **_builder_kwargs()
        )
    )

    requirements = {
        value["requirement"]: value
        for value in bundle.payload[
            "materialization"
        ]["requirements"]
    }

    host = requirements[
        "runtime.host_environment_sha256"
    ]

    assert host["status"] == "portable_host"
    assert host["expected_commitment_sha256"] == _sha("3")
    assert host["observed_commitment_sha256"] == _sha("9")


def test_portable_runtime_mismatch_blocks_materialization():
    observations = list(_observations())

    observations = tuple(
        IncidentMaterializedRequirementObservation(
            requirement=value.requirement,
            observed_commitment_sha256=(
                _sha("f")
                if value.requirement
                == "runtime.source_code_sha256"
                else value.observed_commitment_sha256
            ),
        )
        for value in observations
    )

    bundle = (
        materialization
        .build_incident_environment_materialization_bundle(
            **_builder_kwargs(
                observations=observations
            )
        )
    )

    assert (
        bundle.payload["materialization"]["status"]
        == "blocked_mismatch"
    )
    assert (
        bundle.payload["materialization"][
            "environment_materialized"
        ]
        is False
    )


def test_missing_runner_local_observation_blocks():
    observations = tuple(
        value
        for value in _observations()
        if value.requirement
        != "audio.codec_name"
    )

    bundle = (
        materialization
        .build_incident_environment_materialization_bundle(
            **_builder_kwargs(
                observations=observations
            )
        )
    )

    assert (
        bundle.payload["materialization"]["status"]
        == "blocked_missing_observation"
    )

    assert (
        "missing:audio.codec_name"
        in bundle.payload[
            "materialization"
        ]["blockers"]
    )


def test_operator_authorization_is_required():
    bundle = (
        materialization
        .build_incident_environment_materialization_bundle(
            **_builder_kwargs(
                authorization=_authorization(False)
            )
        )
    )

    assert (
        bundle.payload["materialization"]["status"]
        == "blocked_authorization"
    )

    assert (
        bundle.payload["evidence_boundary"][
            "operator_authorization_granted"
        ]
        is False
    )


def test_blocked_compatibility_cannot_materialize():
    bundle = (
        materialization
        .build_incident_environment_materialization_bundle(
            **_builder_kwargs(
                compatibility_payload=_compatibility(
                    status="blocked_unobserved",
                    ready=False,
                )
            )
        )
    )

    assert (
        bundle.payload["materialization"]["status"]
        == "blocked_compatibility"
    )

    assert (
        bundle.payload["materialization"][
            "environment_materialized"
        ]
        is False
    )


def test_expected_commitment_does_not_substitute_for_missing_observation():
    observations = tuple(
        IncidentMaterializedRequirementObservation(
            requirement=value.requirement,
            observed_commitment_sha256=(
                None
                if value.requirement
                == "transport.kind"
                else value.observed_commitment_sha256
            ),
        )
        for value in _observations()
    )

    bundle = (
        materialization
        .build_incident_environment_materialization_bundle(
            **_builder_kwargs(
                observations=observations
            )
        )
    )

    transport = next(
        value
        for value in bundle.payload[
            "materialization"
        ]["requirements"]
        if value["requirement"]
        == "transport.kind"
    )

    assert transport[
        "expected_commitment_sha256"
    ] == _sha("5")

    assert transport[
        "observed_commitment_sha256"
    ] is None

    assert transport["status"] == "missing"


def test_unexpected_materialization_observation_is_rejected():
    observations = (
        *_observations(),
        IncidentMaterializedRequirementObservation(
            requirement="audio.unexpected_field",
            observed_commitment_sha256=_sha("1"),
        ),
    )

    with pytest.raises(
        HveeContractError,
        match="unexpected requirement",
    ):
        (
            materialization
            .build_incident_environment_materialization_bundle(
                **_builder_kwargs(
                    observations=observations
                )
            )
        )


def test_duplicate_materialization_observation_is_rejected():
    first = _observations()[0]

    with pytest.raises(
        HveeContractError,
        match="must be unique",
    ):
        (
            materialization
            .build_incident_environment_materialization_bundle(
                **_builder_kwargs(
                    observations=(
                        *_observations(),
                        first,
                    )
                )
            )
        )


def test_authorization_requires_commitment():
    with pytest.raises(
        HveeContractError,
        match="requires an evidence commitment",
    ):
        IncidentOperatorAuthorization(
            granted=True,
            authorization_sha256=None,
        )


def test_denied_authorization_cannot_carry_grant_commitment():
    with pytest.raises(
        HveeContractError,
        match="cannot carry",
    ):
        IncidentOperatorAuthorization(
            granted=False,
            authorization_sha256=_sha("a"),
        )


def test_materialization_evidence_does_not_claim_replay():
    bundle = (
        materialization
        .build_incident_environment_materialization_bundle(
            **_builder_kwargs()
        )
    )

    boundary = bundle.payload[
        "evidence_boundary"
    ]

    assert boundary["models_loaded"] is False
    assert boundary["replay_executed"] is False
    assert boundary["transcriptions_executed"] is False
    assert boundary["reproduction_claimed"] is False
    assert boundary["model_failure_verified"] is False
    assert boundary["contract_promoted"] is False
    assert boundary["qualification_authority"] is False


def test_content_boundary_excludes_environment_values():
    bundle = (
        materialization
        .build_incident_environment_materialization_bundle(
            **_builder_kwargs()
        )
    )

    boundary = bundle.payload[
        "content_boundary"
    ]

    assert boundary[
        "environment_values_embedded"
    ] is False
    assert boundary[
        "materialized_value_commitments_embedded"
    ] is True
    assert boundary[
        "environment_variables_embedded"
    ] is False
    assert boundary[
        "file_paths_embedded"
    ] is False


def test_hash_is_reproducible():
    first = (
        materialization
        .build_incident_environment_materialization_bundle(
            **_builder_kwargs()
        )
    )
    second = (
        materialization
        .build_incident_environment_materialization_bundle(
            **_builder_kwargs()
        )
    )

    assert first.payload == second.payload
    assert first.sha256 == second.sha256


def test_materialization_identity_changes_with_observation():
    first = (
        materialization
        .build_incident_environment_materialization_bundle(
            **_builder_kwargs()
        )
    )

    changed_observations = tuple(
        IncidentMaterializedRequirementObservation(
            requirement=value.requirement,
            observed_commitment_sha256=(
                _sha("7")
                if value.requirement
                == "runtime.host_environment_sha256"
                else value.observed_commitment_sha256
            ),
        )
        for value in _observations()
    )

    second = (
        materialization
        .build_incident_environment_materialization_bundle(
            **_builder_kwargs(
                observations=changed_observations
            )
        )
    )

    assert first.sha256 != second.sha256


def test_verifier_accepts_exact_bundle():
    bundle = (
        materialization
        .build_incident_environment_materialization_bundle(
            **_builder_kwargs()
        )
    )

    values = _builder_kwargs()

    assert (
        materialization
        .verify_incident_environment_materialization_bundle(
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
        )
    )


def test_verifier_rejects_tampering():
    bundle = (
        materialization
        .build_incident_environment_materialization_bundle(
            **_builder_kwargs()
        )
    )

    tampered = copy.deepcopy(bundle.payload)

    tampered["materialization"][
        "environment_materialized"
    ] = False

    values = _builder_kwargs()

    assert not (
        materialization
        .verify_incident_environment_materialization_bundle(
            payload=tampered,
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
        )
    )

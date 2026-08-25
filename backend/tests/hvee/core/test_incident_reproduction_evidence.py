from __future__ import annotations

import copy

import pytest

import hvee.core.incident_reproduction_evidence as reproduction
from hvee.core.contracts import HveeContractError
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


def _intake(
    *,
    expected=None,
    observed=None,
):
    if expected is ...:
        expected = None

    if observed is ...:
        observed = None

    return {
        "evaluation_type": "asr",
        "incident": {
            "key": "incident-1",
            "version": "1",
        },
        "claim": {
            "reporter_evidence_sha256": _sha("1"),
            "expected_behavior_commitment_sha256": (
                expected
            ),
            "observed_behavior_commitment_sha256": (
                observed
            ),
        },
    }


def _controlled_replay(
    *,
    transcript_sha=None,
):
    return {
        "execution": {
            "status": "executed",
            "output": {
                "generated_transcript_sha256": (
                    transcript_sha or _sha("3")
                ),
            },
        },
        "evidence_boundary": {
            "replay_executed": True,
            "replay_output_captured": True,
            "behavior_commitments_compared": False,
            "reproduction_claimed": False,
        },
    }


def _unavailable():
    return (
        IncidentReproductionComparisonObservation(
            basis=(
                IncidentReproductionComparisonBasis
                .UNAVAILABLE
            ),
        )
    )


def _confirmed():
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


def _kwargs(
    *,
    intake=None,
    controlled_replay=None,
    comparison=None,
):
    return {
        "intake_payload": (
            intake
            or _intake(
                expected=_sha("2"),
                observed=_sha("3"),
            )
        ),
        "expected_intake_sha256": _sha("a"),
        "replay_preparation_payload": {
            "type": "preparation",
        },
        "expected_replay_preparation_sha256": _sha("b"),
        "environment_manifest_payload": {
            "type": "manifest",
        },
        "expected_environment_manifest_sha256": _sha("c"),
        "runner_compatibility_payload": {
            "type": "compatibility",
        },
        "expected_runner_compatibility_sha256": _sha("d"),
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
        "controlled_replay_payload": (
            controlled_replay
            or _controlled_replay()
        ),
        "expected_controlled_replay_sha256": _sha("f"),
        "comparison_observation": (
            comparison or _unavailable()
        ),
    }


@pytest.fixture(autouse=True)
def trusted_stage7(
    monkeypatch,
):
    monkeypatch.setattr(
        reproduction,
        "verify_incident_controlled_replay_bundle",
        lambda **kwargs: True,
    )


def test_opaque_commitments_default_to_indeterminate():
    bundle = (
        reproduction
        .build_incident_reproduction_evidence_bundle(
            **_kwargs()
        )
    )

    comparison = bundle.payload[
        "comparison"
    ]

    assert comparison["verdict"] == (
        "indeterminate"
    )

    assert comparison["reason"] == (
        "behavior_commitment_semantics_unconfirmed"
    )

    assert comparison["status"] == (
        "indeterminate"
    )

    boundary = bundle.payload[
        "evidence_boundary"
    ]

    assert boundary[
        "behavior_commitments_compared"
    ] is False

    assert boundary[
        "reproduction_determined"
    ] is False

    assert boundary[
        "reproduction_claimed"
    ] is False


def test_missing_behavior_commitments_are_indeterminate():
    bundle = (
        reproduction
        .build_incident_reproduction_evidence_bundle(
            **_kwargs(
                intake=_intake(
                    expected=None,
                    observed=None,
                ),
                comparison=_confirmed(),
            )
        )
    )

    assert bundle.payload[
        "comparison"
    ]["verdict"] == "indeterminate"

    assert bundle.payload[
        "comparison"
    ]["reason"] == (
        "behavior_commitments_unavailable"
    )


def test_confirmed_exact_observed_commitment_reproduces():
    bundle = (
        reproduction
        .build_incident_reproduction_evidence_bundle(
            **_kwargs(
                comparison=_confirmed(),
            )
        )
    )

    comparison = bundle.payload[
        "comparison"
    ]

    assert comparison["status"] == (
        "compared"
    )

    assert comparison["verdict"] == (
        "reproduced"
    )

    assert comparison[
        "reported_behavior_exact_match"
    ] is True

    boundary = bundle.payload[
        "evidence_boundary"
    ]

    assert boundary[
        "behavior_commitments_compared"
    ] is True

    assert boundary[
        "reproduction_determined"
    ] is True

    assert boundary[
        "reproduction_claimed"
    ] is True


def test_confirmed_exact_mismatch_is_not_reproduced():
    bundle = (
        reproduction
        .build_incident_reproduction_evidence_bundle(
            **_kwargs(
                controlled_replay=(
                    _controlled_replay(
                        transcript_sha=_sha("4")
                    )
                ),
                comparison=_confirmed(),
            )
        )
    )

    comparison = bundle.payload[
        "comparison"
    ]

    assert comparison["verdict"] == (
        "not_reproduced"
    )

    assert comparison["reason"] == (
        "reported_behavior_mismatch"
    )

    assert comparison[
        "reported_behavior_exact_match"
    ] is False

    boundary = bundle.payload[
        "evidence_boundary"
    ]

    assert boundary[
        "reproduction_determined"
    ] is True

    assert boundary[
        "reproduction_claimed"
    ] is False


def test_expected_behavior_match_is_still_not_reported_reproduction():
    bundle = (
        reproduction
        .build_incident_reproduction_evidence_bundle(
            **_kwargs(
                controlled_replay=(
                    _controlled_replay(
                        transcript_sha=_sha("2")
                    )
                ),
                comparison=_confirmed(),
            )
        )
    )

    assert bundle.payload[
        "comparison"
    ]["verdict"] == "not_reproduced"

    assert bundle.payload[
        "comparison"
    ][
        "controlled_replay_behavior_commitment_sha256"
    ] == _sha("2")


def test_exact_basis_requires_semantic_confirmation():
    with pytest.raises(
        HveeContractError,
        match="requires semantic confirmation",
    ):
        (
            IncidentReproductionComparisonObservation(
                basis=(
                    IncidentReproductionComparisonBasis
                    .EXACT_GENERATED_TRANSCRIPT_SHA256_V1
                ),
            )
        )


def test_unavailable_basis_rejects_confirmation():
    with pytest.raises(
        HveeContractError,
        match="cannot contain semantic confirmation",
    ):
        (
            IncidentReproductionComparisonObservation(
                basis=(
                    IncidentReproductionComparisonBasis
                    .UNAVAILABLE
                ),
                semantics_confirmation_sha256=(
                    _sha("9")
                ),
            )
        )


def test_behavior_commitments_must_remain_paired():
    intake = _intake(
        expected=_sha("2"),
        observed=None,
    )

    with pytest.raises(
        HveeContractError,
        match="must remain paired",
    ):
        (
            reproduction
            .build_incident_reproduction_evidence_bundle(
                **_kwargs(
                    intake=intake
                )
            )
        )


def test_behavior_commitments_must_remain_distinct():
    intake = _intake(
        expected=_sha("2"),
        observed=_sha("2"),
    )

    with pytest.raises(
        HveeContractError,
        match="must remain distinct",
    ):
        (
            reproduction
            .build_incident_reproduction_evidence_bundle(
                **_kwargs(
                    intake=intake
                )
            )
        )


def test_stage7_must_reverify(
    monkeypatch,
):
    monkeypatch.setattr(
        reproduction,
        "verify_incident_controlled_replay_bundle",
        lambda **kwargs: False,
    )

    with pytest.raises(
        HveeContractError,
        match="requires verified controlled replay",
    ):
        (
            reproduction
            .build_incident_reproduction_evidence_bundle(
                **_kwargs()
            )
        )


def test_stage7_must_not_have_already_compared_behavior():
    controlled = _controlled_replay()

    controlled[
        "evidence_boundary"
    ][
        "behavior_commitments_compared"
    ] = True

    with pytest.raises(
        HveeContractError,
        match="crossed the Stage-8 boundary",
    ):
        (
            reproduction
            .build_incident_reproduction_evidence_bundle(
                **_kwargs(
                    controlled_replay=controlled
                )
            )
        )


def test_reproduction_never_claims_model_failure_or_authority():
    bundle = (
        reproduction
        .build_incident_reproduction_evidence_bundle(
            **_kwargs(
                comparison=_confirmed()
            )
        )
    )

    boundary = bundle.payload[
        "evidence_boundary"
    ]

    assert boundary[
        "reproduction_claimed"
    ] is True

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
        "qualification_authority"
    ] is False


def test_no_raw_transcript_is_required_for_comparison():
    bundle = (
        reproduction
        .build_incident_reproduction_evidence_bundle(
            **_kwargs(
                comparison=_confirmed()
            )
        )
    )

    serialized = str(
        bundle.payload
    )

    assert "raw transcript" not in serialized.lower()

    assert bundle.payload[
        "content_boundary"
    ]["raw_transcript_embedded"] is False


def test_hash_is_reproducible():
    first = (
        reproduction
        .build_incident_reproduction_evidence_bundle(
            **_kwargs(
                comparison=_confirmed()
            )
        )
    )

    second = (
        reproduction
        .build_incident_reproduction_evidence_bundle(
            **_kwargs(
                comparison=_confirmed()
            )
        )
    )

    assert first.payload == second.payload
    assert first.sha256 == second.sha256


def test_verifier_accepts_exact_bundle():
    values = _kwargs(
        comparison=_confirmed()
    )

    bundle = (
        reproduction
        .build_incident_reproduction_evidence_bundle(
            **values
        )
    )

    assert (
        reproduction
        .verify_incident_reproduction_evidence_bundle(
            payload=bundle.payload,
            expected_sha256=bundle.sha256,
            intake_payload=(
                values["intake_payload"]
            ),
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
            controlled_replay_payload=(
                values[
                    "controlled_replay_payload"
                ]
            ),
            expected_controlled_replay_sha256=(
                values[
                    "expected_controlled_replay_sha256"
                ]
            ),
            comparison_observation=(
                values[
                    "comparison_observation"
                ]
            ),
        )
    )


def test_verifier_rejects_verdict_tampering():
    values = _kwargs(
        comparison=_confirmed()
    )

    bundle = (
        reproduction
        .build_incident_reproduction_evidence_bundle(
            **values
        )
    )

    tampered = copy.deepcopy(
        bundle.payload
    )

    tampered["comparison"][
        "verdict"
    ] = "not_reproduced"

    assert not (
        reproduction
        .verify_incident_reproduction_evidence_bundle(
            payload=tampered,
            expected_sha256=bundle.sha256,
            intake_payload=(
                values["intake_payload"]
            ),
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
            controlled_replay_payload=(
                values[
                    "controlled_replay_payload"
                ]
            ),
            expected_controlled_replay_sha256=(
                values[
                    "expected_controlled_replay_sha256"
                ]
            ),
            comparison_observation=(
                values[
                    "comparison_observation"
                ]
            ),
        )
    )


def _verify_with_external_observation(
    *,
    bundle,
    values,
    comparison_observation,
):
    return (
        reproduction
        .verify_incident_reproduction_evidence_bundle(
            payload=bundle.payload,
            expected_sha256=bundle.sha256,
            intake_payload=(
                values["intake_payload"]
            ),
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
                values[
                    "required_capabilities"
                ]
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
            controlled_replay_payload=(
                values[
                    "controlled_replay_payload"
                ]
            ),
            expected_controlled_replay_sha256=(
                values[
                    "expected_controlled_replay_sha256"
                ]
            ),
            comparison_observation=(
                comparison_observation
            ),
        )
    )


def test_verifier_rejects_mismatched_external_semantics_observation():
    values = _kwargs(
        comparison=_confirmed()
    )

    bundle = (
        reproduction
        .build_incident_reproduction_evidence_bundle(
            **values
        )
    )

    assert not _verify_with_external_observation(
        bundle=bundle,
        values=values,
        comparison_observation=_unavailable(),
    )


def test_external_semantics_confirmation_is_bound_to_identity():
    first_observation = _confirmed()

    second_observation = (
        IncidentReproductionComparisonObservation(
            basis=(
                IncidentReproductionComparisonBasis
                .EXACT_GENERATED_TRANSCRIPT_SHA256_V1
            ),
            semantics_confirmation_sha256=(
                _sha("8")
            ),
        )
    )

    first = (
        reproduction
        .build_incident_reproduction_evidence_bundle(
            **_kwargs(
                comparison=first_observation
            )
        )
    )

    second = (
        reproduction
        .build_incident_reproduction_evidence_bundle(
            **_kwargs(
                comparison=second_observation
            )
        )
    )

    assert first.payload[
        "comparison"
    ]["verdict"] == "reproduced"

    assert second.payload[
        "comparison"
    ]["verdict"] == "reproduced"

    assert first.payload[
        "comparison"
    ][
        "semantics_confirmation_sha256"
    ] != second.payload[
        "comparison"
    ][
        "semantics_confirmation_sha256"
    ]

    assert first.sha256 != second.sha256


def test_missing_behavior_commitments_are_not_claimed_as_embedded():
    bundle = (
        reproduction
        .build_incident_reproduction_evidence_bundle(
            **_kwargs(
                intake=_intake(
                    expected=None,
                    observed=None,
                ),
                comparison=_confirmed(),
            )
        )
    )

    boundary = bundle.payload[
        "content_boundary"
    ]

    assert boundary[
        "expected_behavior_commitment_embedded"
    ] is False

    assert boundary[
        "observed_behavior_commitment_embedded"
    ] is False

    assert boundary[
        "comparison_semantics_confirmation_commitment_embedded"
    ] is True


def test_unconfirmed_semantics_does_not_claim_confirmation_commitment():
    bundle = (
        reproduction
        .build_incident_reproduction_evidence_bundle(
            **_kwargs(
                comparison=_unavailable()
            )
        )
    )

    boundary = bundle.payload[
        "content_boundary"
    ]

    assert boundary[
        "expected_behavior_commitment_embedded"
    ] is True

    assert boundary[
        "observed_behavior_commitment_embedded"
    ] is True

    assert boundary[
        "comparison_semantics_confirmation_commitment_embedded"
    ] is False


def test_confirmed_semantics_claims_confirmation_commitment():
    bundle = (
        reproduction
        .build_incident_reproduction_evidence_bundle(
            **_kwargs(
                comparison=_confirmed()
            )
        )
    )

    boundary = bundle.payload[
        "content_boundary"
    ]

    assert boundary[
        "expected_behavior_commitment_embedded"
    ] is True

    assert boundary[
        "observed_behavior_commitment_embedded"
    ] is True

    assert boundary[
        "comparison_semantics_confirmation_commitment_embedded"
    ] is True

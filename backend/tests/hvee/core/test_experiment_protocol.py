from __future__ import annotations

from copy import deepcopy

import pytest

from hvee.core.contracts import HveeContractError
from hvee.core.experiment_protocol import (
    ExperimentDefinition,
    ExperimentEngineKind,
    ExperimentObservation,
    ExperimentObservationStatus,
    ExperimentProposal,
    build_experiment_protocol_bundle,
    calculate_experiment_proposal_sha256,
    verify_experiment_protocol_bundle,
)


SUBJECT_SHA = "1" * 64
TARGET_A_SHA = "2" * 64
TARGET_B_SHA = "3" * 64
RESULT_A_SHA = "4" * 64
RESULT_B_SHA = "5" * 64
EVALUATOR_SHA = "6" * 64
SOURCE_SHA = "7" * 64


def _definition(
    *,
    engine_kind=ExperimentEngineKind.BEHAVIORAL,
):
    return ExperimentDefinition(
        key="hetren.experiment",
        version="1.0.0",
        engine_kind=engine_kind,
        operation_key="scenario_probe",
        operation_version="1.0.0",
    )


def _proposal(
    sequence,
    *,
    target_sha256=None,
    parameters=None,
    estimated_cost_units=1,
):
    if target_sha256 is None:
        target_sha256 = (
            TARGET_A_SHA
            if sequence == 0
            else TARGET_B_SHA
        )

    if parameters is None:
        parameters = {
            "axis_key": "noise_snr",
            "axis_value": 10 + sequence,
        }

    return ExperimentProposal(
        sequence=sequence,
        proposal_key=f"proposal-{sequence}",
        target_sha256=target_sha256,
        parameters=parameters,
        estimated_cost_units=(
            estimated_cost_units
        ),
        reason_code="adaptive_search",
        source_evidence_sha256=SOURCE_SHA,
    )


def _observation(
    proposal,
    *,
    status=ExperimentObservationStatus.COMPLETED,
    outcome_key="fail",
    actual_cost_units=1,
    result_sha256=RESULT_A_SHA,
):
    return ExperimentObservation(
        proposal_sequence=proposal.sequence,
        proposal_sha256=(
            calculate_experiment_proposal_sha256(
                proposal
            )
        ),
        status=status,
        outcome_key=outcome_key,
        actual_cost_units=actual_cost_units,
        result_evidence_sha256=(
            result_sha256
        ),
        evaluator_evidence_sha256=(
            EVALUATOR_SHA
        ),
    )


def _bundle(
    *,
    engine_kind=ExperimentEngineKind.BEHAVIORAL,
    proposals=None,
    observations=None,
    maximum_experiments=4,
    maximum_cost_units=10,
):
    if proposals is None:
        proposals = [_proposal(0)]

    if observations is None:
        observations = [
            _observation(proposals[0])
        ]

    return build_experiment_protocol_bundle(
        definition=_definition(
            engine_kind=engine_kind
        ),
        campaign_key="behavioral-foundation",
        campaign_version="1.0.0",
        subject_sha256=SUBJECT_SHA,
        maximum_experiments=(
            maximum_experiments
        ),
        maximum_cost_units=(
            maximum_cost_units
        ),
        proposals=proposals,
        observations=observations,
    )


def test_builds_verified_behavioral_experiment_bundle():
    bundle = _bundle()

    assert (
        bundle.payload["definition"][
            "engine_kind"
        ]
        == "behavioral"
    )

    assert verify_experiment_protocol_bundle(
        bundle.payload,
        bundle.sha256,
    )


def test_protocol_also_represents_future_internal_experiment_kind():
    bundle = _bundle(
        engine_kind=(
            ExperimentEngineKind.INTERNAL
        )
    )

    assert (
        bundle.payload["definition"][
            "engine_kind"
        ]
        == "internal"
    )

    assert verify_experiment_protocol_bundle(
        bundle.payload,
        bundle.sha256,
    )


def test_internal_kind_does_not_claim_internal_engine_execution():
    bundle = build_experiment_protocol_bundle(
        definition=_definition(
            engine_kind=(
                ExperimentEngineKind.INTERNAL
            )
        ),
        campaign_key="internal-protocol-only",
        campaign_version="1.0.0",
        subject_sha256=SUBJECT_SHA,
        maximum_experiments=2,
        maximum_cost_units=5,
        proposals=[_proposal(0)],
        observations=[],
    )

    boundary = bundle.payload[
        "evidence_boundary"
    ]

    assert (
        boundary[
            "experiment_execution_proven"
        ]
        is False
    )

    assert (
        boundary[
            "causal_mechanism_established"
        ]
        is False
    )


def test_bundle_is_deterministic_across_parameter_key_order():
    first = _proposal(
        0,
        parameters={
            "axis_key": "snr",
            "axis_value": 4,
            "metadata": {
                "b": 2,
                "a": 1,
            },
        },
    )

    second = _proposal(
        0,
        parameters={
            "metadata": {
                "a": 1,
                "b": 2,
            },
            "axis_value": 4,
            "axis_key": "snr",
        },
    )

    first_bundle = _bundle(
        proposals=[first],
        observations=[
            _observation(first)
        ],
    )

    second_bundle = _bundle(
        proposals=[second],
        observations=[
            _observation(second)
        ],
    )

    assert (
        first_bundle.sha256
        == second_bundle.sha256
    )

    assert (
        first_bundle.payload
        == second_bundle.payload
    )


def test_builder_detaches_mutable_parameters():
    parameters = {
        "nested": {
            "value": 1,
        },
    }

    proposal = _proposal(
        0,
        parameters=parameters,
    )

    bundle = _bundle(
        proposals=[proposal],
        observations=[
            _observation(proposal)
        ],
    )

    parameters["nested"]["value"] = 999

    assert (
        bundle.payload["proposals"][0][
            "parameters"
        ]["nested"]["value"]
        == 1
    )


def test_proposal_sequences_must_be_contiguous():
    with pytest.raises(
        HveeContractError
    ):
        _bundle(
            proposals=[
                _proposal(1),
            ],
            observations=[],
        )


def test_proposal_keys_must_be_unique():
    first = _proposal(0)

    second = ExperimentProposal(
        sequence=1,
        proposal_key=first.proposal_key,
        target_sha256=TARGET_B_SHA,
        parameters={
            "axis_value": 11,
        },
        estimated_cost_units=1,
        reason_code="adaptive_search",
        source_evidence_sha256=SOURCE_SHA,
    )

    with pytest.raises(
        HveeContractError
    ):
        _bundle(
            proposals=[
                first,
                second,
            ],
            observations=[],
        )


def test_proposal_count_cannot_exceed_experiment_budget():
    proposals = [
        _proposal(0),
        _proposal(1),
    ]

    with pytest.raises(
        HveeContractError
    ):
        _bundle(
            proposals=proposals,
            observations=[],
            maximum_experiments=1,
        )


def test_observation_must_bind_exact_proposal():
    proposal = _proposal(0)

    observation = ExperimentObservation(
        proposal_sequence=0,
        proposal_sha256="9" * 64,
        status=(
            ExperimentObservationStatus.COMPLETED
        ),
        outcome_key="fail",
        actual_cost_units=1,
        result_evidence_sha256=(
            RESULT_A_SHA
        ),
        evaluator_evidence_sha256=(
            EVALUATOR_SHA
        ),
    )

    with pytest.raises(
        HveeContractError
    ):
        _bundle(
            proposals=[proposal],
            observations=[observation],
        )


def test_observation_cannot_reference_unknown_proposal():
    proposal = _proposal(0)

    observation = ExperimentObservation(
        proposal_sequence=1,
        proposal_sha256=(
            calculate_experiment_proposal_sha256(
                _proposal(1)
            )
        ),
        status=(
            ExperimentObservationStatus.COMPLETED
        ),
        outcome_key="fail",
        actual_cost_units=1,
        result_evidence_sha256=(
            RESULT_A_SHA
        ),
        evaluator_evidence_sha256=(
            EVALUATOR_SHA
        ),
    )

    with pytest.raises(
        HveeContractError
    ):
        _bundle(
            proposals=[proposal],
            observations=[observation],
        )


def test_proposal_can_have_at_most_one_observation():
    proposal = _proposal(0)

    with pytest.raises(
        HveeContractError
    ):
        _bundle(
            proposals=[proposal],
            observations=[
                _observation(proposal),
                _observation(
                    proposal,
                    outcome_key="pass",
                ),
            ],
        )


def test_observed_cost_cannot_exceed_budget():
    proposal = _proposal(0)

    with pytest.raises(
        HveeContractError
    ):
        _bundle(
            proposals=[proposal],
            observations=[
                _observation(
                    proposal,
                    actual_cost_units=6,
                )
            ],
            maximum_cost_units=5,
        )


def test_proposed_cost_is_recorded_without_claiming_execution():
    proposal = _proposal(
        0,
        estimated_cost_units=4,
    )

    bundle = _bundle(
        proposals=[proposal],
        observations=[],
        maximum_cost_units=5,
    )

    assert (
        bundle.payload["budget"][
            "proposed_cost_units"
        ]
        == 4
    )

    assert (
        bundle.payload["budget"][
            "observed_cost_units"
        ]
        == 0
    )

    assert (
        bundle.payload[
            "evidence_boundary"
        ][
            "experiment_execution_proven"
        ]
        is False
    )


@pytest.mark.parametrize(
    "raw_key",
    [
        "reference_text",
        "prediction_text",
        "raw_transcript_text",
        "audio_bytes",
        "prompt_text",
    ],
)
def test_parameters_reject_raw_content_fields(
    raw_key,
):
    proposal = _proposal(
        0,
        parameters={
            raw_key: "sensitive-value",
        },
    )

    with pytest.raises(
        HveeContractError
    ):
        _bundle(
            proposals=[proposal],
            observations=[],
        )


def test_nested_parameters_reject_raw_content_fields():
    proposal = _proposal(
        0,
        parameters={
            "safe": {
                "reference_text": (
                    "must-not-persist"
                )
            }
        },
    )

    with pytest.raises(
        HveeContractError
    ):
        _bundle(
            proposals=[proposal],
            observations=[],
        )


def test_parameters_reject_nonfinite_numbers():
    proposal = _proposal(
        0,
        parameters={
            "axis_value": float("nan"),
        },
    )

    with pytest.raises(
        HveeContractError
    ):
        _bundle(
            proposals=[proposal],
            observations=[],
        )


def test_verifier_rejects_payload_tampering():
    bundle = _bundle()

    payload = deepcopy(
        bundle.payload
    )

    payload["campaign"]["version"] = "2.0.0"

    assert not verify_experiment_protocol_bundle(
        payload,
        bundle.sha256,
    )


def test_verifier_rejects_parameter_digest_tampering():
    bundle = _bundle()

    payload = deepcopy(
        bundle.payload
    )

    payload["proposals"][0][
        "parameters_sha256"
    ] = "a" * 64

    assert not verify_experiment_protocol_bundle(
        payload,
        bundle.sha256,
    )


def test_verifier_rejects_proposal_set_digest_tampering():
    bundle = _bundle()

    payload = deepcopy(
        bundle.payload
    )

    payload[
        "proposal_set_sha256"
    ] = "a" * 64

    assert not verify_experiment_protocol_bundle(
        payload,
        bundle.sha256,
    )


def test_verifier_rejects_observation_set_digest_tampering():
    bundle = _bundle()

    payload = deepcopy(
        bundle.payload
    )

    payload[
        "observation_set_sha256"
    ] = "a" * 64

    assert not verify_experiment_protocol_bundle(
        payload,
        bundle.sha256,
    )


def test_verifier_rejects_extra_top_level_fields():
    bundle = _bundle()

    payload = deepcopy(
        bundle.payload
    )

    payload["unexpected"] = True

    assert not verify_experiment_protocol_bundle(
        payload,
        bundle.sha256,
    )


def test_verifier_rejects_wrong_expected_identity():
    bundle = _bundle()

    assert not verify_experiment_protocol_bundle(
        bundle.payload,
        "f" * 64,
    )


def test_evidence_boundary_never_grants_release_or_causal_authority():
    bundle = _bundle()

    boundary = bundle.payload[
        "evidence_boundary"
    ]

    assert (
        boundary[
            "causal_mechanism_established"
        ]
        is False
    )

    assert (
        boundary[
            "production_qualified"
        ]
        is False
    )

    assert (
        boundary[
            "release_decision_issued"
        ]
        is False
    )

    assert (
        boundary[
            "raw_content_persisted"
        ]
        is False
    )


def test_payload_contains_only_committed_content_not_raw_material():
    bundle = _bundle()

    serialized = repr(
        bundle.payload
    )

    assert "reference_text" not in serialized
    assert "prediction_text" not in serialized
    assert "raw_transcript_text" not in serialized
    assert "audio_bytes" not in serialized


def test_aggregate_proposed_cost_cannot_exceed_budget():
    first = _proposal(
        0,
        estimated_cost_units=3,
    )

    second = _proposal(
        1,
        estimated_cost_units=3,
    )

    with pytest.raises(
        HveeContractError
    ):
        _bundle(
            proposals=[
                first,
                second,
            ],
            observations=[],
            maximum_experiments=2,
            maximum_cost_units=5,
        )

from copy import deepcopy

import pytest

from hvee.core.adaptive_scenario_search import (
    AdaptiveScenarioObservation,
    build_adaptive_scenario_search_bundle,
)
from hvee.core.contracts import HveeContractError
from hvee.core.decision import DecisionVerdict
from hvee.core.minimal_counterexample_reduction import (
    MINIMAL_COUNTEREXAMPLE_REDUCTION_SCHEMA_VERSION,
    CounterexampleReductionObservation,
    CounterexampleReductionUnit,
    build_minimal_counterexample_reduction_bundle,
    calculate_minimal_counterexample_reduction_sha256,
    calculate_reduction_units_sha256,
    verify_minimal_counterexample_reduction_bundle,
)


def _sha(character: str) -> str:
    return character * 64


def _unit(
    key: str,
    character: str,
) -> CounterexampleReductionUnit:
    return CounterexampleReductionUnit(
        key=key,
        version="1.0.0",
        content_sha256=_sha(character),
    )


def _units():
    return (
        _unit("segment-000", "a"),
        _unit("segment-001", "b"),
        _unit("segment-002", "c"),
    )


def _observation(
    *,
    sequence: int,
    removed_unit_index: int,
    verdict: DecisionVerdict,
    character: str,
) -> CounterexampleReductionObservation:
    return CounterexampleReductionObservation(
        sequence=sequence,
        removed_unit_index=removed_unit_index,
        scenario_sha256=_sha(character),
        verdict=verdict,
        result_provenance_sha256=_sha("a"),
        observation_evidence_sha256=_sha("b"),
        decision_evidence_sha256=_sha("c"),
        counterexample_evidence_sha256=(
            _sha("d")
            if verdict == DecisionVerdict.FAIL
            else None
        ),
    )


def _terminal_observations():
    return (
        _observation(
            sequence=1,
            removed_unit_index=0,
            verdict=DecisionVerdict.PASS,
            character="1",
        ),
        _observation(
            sequence=2,
            removed_unit_index=1,
            verdict=DecisionVerdict.FAIL,
            character="2",
        ),
        _observation(
            sequence=3,
            removed_unit_index=0,
            verdict=DecisionVerdict.PASS,
            character="3",
        ),
        _observation(
            sequence=4,
            removed_unit_index=2,
            verdict=DecisionVerdict.PASS,
            character="4",
        ),
    )


def _build(
    *,
    units=None,
    maximum_observations: int = 6,
    observations=(),
    source_scenario_sha256: str | None = None,
    source_counterexample_evidence_sha256: str | None = None,
):
    return build_minimal_counterexample_reduction_bundle(
        evaluation_type="asr",
        reduction_key="hetren.asr.minimal-counterexample",
        reduction_version="1.0.0",
        source_scenario_sha256=(
            source_scenario_sha256
            if source_scenario_sha256 is not None
            else _sha("f")
        ),
        source_counterexample_evidence_sha256=(
            source_counterexample_evidence_sha256
            if source_counterexample_evidence_sha256 is not None
            else _sha("e")
        ),
        units=(
            units
            if units is not None
            else _units()
        ),
        maximum_observations=maximum_observations,
        observations=observations,
    )


def test_empty_reduction_proposes_first_unit():
    bundle = _build()

    assert bundle.payload["schema_version"] == (
        MINIMAL_COUNTEREXAMPLE_REDUCTION_SCHEMA_VERSION
    )
    assert bundle.payload["type"] == (
        "minimal_counterexample_reduction"
    )
    assert bundle.payload["reduction"]["status"] == "ready"
    assert bundle.payload["outcome"]["next_proposal"] == {
        "reason": "initial_scan",
        "removed_unit": {
            "index": 0,
            "key": "segment-000",
            "version": "1.0.0",
            "content_sha256": _sha("a"),
        },
        "retained_unit_indices": [1, 2],
        "parent_scenario_sha256": _sha("f"),
        "parent_counterexample_evidence_sha256": _sha("e"),
    }
    assert bundle.payload["observations"] == []
    assert verify_minimal_counterexample_reduction_bundle(
        payload=bundle.payload,
        expected_sha256=bundle.sha256,
    )


def test_passing_candidate_is_rejected_and_scan_continues():
    bundle = _build(
        observations=_terminal_observations()[:1]
    )

    observation = bundle.payload["observations"][0]
    assert observation["accepted"] is False
    assert observation["proposal"]["removed_unit"]["index"] == 0
    assert bundle.payload["outcome"]["current_scenario_sha256"] == (
        _sha("f")
    )
    assert bundle.payload["outcome"]["retained_unit_indices"] == [
        0,
        1,
        2,
    ]
    assert bundle.payload["outcome"]["next_proposal"][
        "removed_unit"
    ]["index"] == 1
    assert bundle.payload["outcome"]["next_proposal"]["reason"] == (
        "continue_scan"
    )


def test_failing_candidate_is_accepted_and_scan_restarts():
    bundle = _build(
        observations=_terminal_observations()[:2]
    )

    observation = bundle.payload["observations"][1]
    assert observation["accepted"] is True
    assert observation["proposal"]["parent_scenario_sha256"] == (
        _sha("f")
    )
    assert bundle.payload["outcome"]["current_scenario_sha256"] == (
        _sha("2")
    )
    assert bundle.payload["outcome"][
        "current_counterexample_evidence_sha256"
    ] == _sha("d")
    assert bundle.payload["outcome"]["retained_unit_indices"] == [
        0,
        2,
    ]
    assert bundle.payload["outcome"]["removed_unit_indices"] == [1]
    assert bundle.payload["outcome"]["next_proposal"][
        "removed_unit"
    ]["index"] == 0
    assert bundle.payload["outcome"]["next_proposal"]["reason"] == (
        "restart_after_accepted_reduction"
    )
    assert bundle.payload["outcome"]["next_proposal"][
        "parent_scenario_sha256"
    ] == _sha("2")
    assert bundle.payload["outcome"]["next_proposal"][
        "parent_counterexample_evidence_sha256"
    ] == _sha("d")


def test_completion_proves_one_minimality_within_declared_units():
    bundle = _build(observations=_terminal_observations())

    assert bundle.payload["reduction"]["status"] == "one_minimal"
    assert bundle.payload["outcome"]["next_proposal"] is None
    assert bundle.payload["outcome"] == {
        "current_scenario_sha256": _sha("2"),
        "current_counterexample_evidence_sha256": _sha("d"),
        "retained_unit_indices": [0, 2],
        "retained_unit_keys": ["segment-000", "segment-002"],
        "removed_unit_indices": [1],
        "removed_unit_keys": ["segment-001"],
        "accepted_reduction_count": 1,
        "rejected_reduction_count": 3,
        "one_minimal_within_declared_units": True,
        "next_proposal": None,
    }
    assert verify_minimal_counterexample_reduction_bundle(
        payload=bundle.payload,
        expected_sha256=bundle.sha256,
    )


def test_all_units_can_be_removed_when_empty_candidate_still_fails():
    units = (_unit("segment-000", "a"),)
    observation = _observation(
        sequence=1,
        removed_unit_index=0,
        verdict=DecisionVerdict.FAIL,
        character="1",
    )
    bundle = _build(
        units=units,
        maximum_observations=1,
        observations=(observation,),
    )

    assert bundle.payload["reduction"]["status"] == "one_minimal"
    assert bundle.payload["outcome"]["retained_unit_indices"] == []
    assert bundle.payload["outcome"]["removed_unit_indices"] == [0]
    assert bundle.payload["outcome"][
        "one_minimal_within_declared_units"
    ] is True


def test_terminal_result_wins_when_budget_is_exactly_consumed():
    units = (_unit("segment-000", "a"),)
    observation = _observation(
        sequence=1,
        removed_unit_index=0,
        verdict=DecisionVerdict.PASS,
        character="1",
    )
    bundle = _build(
        units=units,
        maximum_observations=1,
        observations=(observation,),
    )

    assert bundle.payload["reduction"]["status"] == "one_minimal"
    assert bundle.payload["budget"]["remaining_observations"] == 0
    assert bundle.payload["outcome"]["retained_unit_indices"] == [0]


def test_budget_exhaustion_never_claims_minimality():
    bundle = _build(
        maximum_observations=2,
        observations=_terminal_observations()[:2],
    )

    assert bundle.payload["reduction"]["status"] == (
        "budget_exhausted"
    )
    assert bundle.payload["budget"] == {
        "maximum_observations": 2,
        "theoretical_maximum_observations": 6,
        "observed_count": 2,
        "remaining_observations": 0,
    }
    assert bundle.payload["outcome"]["next_proposal"] is None
    assert bundle.payload["outcome"][
        "one_minimal_within_declared_units"
    ] is False


def test_bundle_is_deterministic_across_sequence_container_type():
    first = _build(
        units=list(_units()),
        observations=list(_terminal_observations()[:2]),
    )
    second = _build(
        units=_units(),
        observations=_terminal_observations()[:2],
    )

    assert first == second


def test_ordered_unit_identity_is_independently_reproducible():
    bundle = _build()

    assert bundle.reduction_units_sha256 == (
        calculate_reduction_units_sha256(_units())
    )


def test_unit_order_is_semantically_committed():
    forward = _build()
    reverse = _build(units=tuple(reversed(_units())))

    assert forward.reduction_units_sha256 != (
        reverse.reduction_units_sha256
    )
    assert forward.payload["outcome"]["next_proposal"][
        "removed_unit"
    ]["key"] == "segment-000"
    assert reverse.payload["outcome"]["next_proposal"][
        "removed_unit"
    ]["key"] == "segment-002"


def test_builder_detaches_mutable_sequences():
    units = list(_units())
    observations = list(_terminal_observations()[:1])
    bundle = _build(
        units=units,
        observations=observations,
    )

    units.clear()
    observations.clear()

    assert len(bundle.payload["units"]["ordered"]) == 3
    assert len(bundle.payload["observations"]) == 1


@pytest.mark.parametrize(
    "maximum",
    [
        True,
        0,
        7,
    ],
)
def test_rejects_invalid_observation_budget(maximum):
    with pytest.raises(
        HveeContractError,
        match="maximum observations",
    ):
        _build(maximum_observations=maximum)


@pytest.mark.parametrize(
    "units",
    [
        (),
        (object(),),
    ],
)
def test_rejects_invalid_reduction_unit_sequence(units):
    with pytest.raises(
        HveeContractError,
        match="ordered sequence",
    ):
        _build(units=units, maximum_observations=1)


def test_rejects_duplicate_reduction_unit_identity():
    unit = _unit("segment-000", "a")

    with pytest.raises(
        HveeContractError,
        match="identities must be unique",
    ):
        _build(
            units=(unit, unit),
            maximum_observations=1,
        )


def test_rejects_duplicate_reduction_unit_key():
    with pytest.raises(
        HveeContractError,
        match="keys must be unique",
    ):
        _build(
            units=(
                _unit("segment-000", "a"),
                _unit("segment-000", "b"),
            ),
            maximum_observations=1,
        )


@pytest.mark.parametrize(
    ("key", "version", "content_sha256"),
    [
        ("Bad Key", "1.0.0", _sha("a")),
        ("segment-000", " 1.0.0", _sha("a")),
        ("segment-000", "1.0.0", "not-a-digest"),
    ],
)
def test_reduction_unit_rejects_noncanonical_identity(
    key,
    version,
    content_sha256,
):
    with pytest.raises(HveeContractError):
        CounterexampleReductionUnit(
            key=key,
            version=version,
            content_sha256=content_sha256,
        )


def test_rejects_noncontiguous_observation_sequence():
    observation = _observation(
        sequence=2,
        removed_unit_index=0,
        verdict=DecisionVerdict.PASS,
        character="1",
    )

    with pytest.raises(
        HveeContractError,
        match="sequences must be contiguous",
    ):
        _build(observations=(observation,))


def test_rejects_observation_outside_deterministic_trajectory():
    observation = _observation(
        sequence=1,
        removed_unit_index=1,
        verdict=DecisionVerdict.PASS,
        character="1",
    )

    with pytest.raises(
        HveeContractError,
        match="deterministic proposal trajectory",
    ):
        _build(observations=(observation,))


def test_rejects_observations_after_one_minimal_result():
    extra = _observation(
        sequence=5,
        removed_unit_index=0,
        verdict=DecisionVerdict.PASS,
        character="5",
    )

    with pytest.raises(
        HveeContractError,
        match="cannot continue after",
    ):
        _build(
            observations=(*_terminal_observations(), extra),
        )


def test_rejects_duplicate_candidate_scenario_identity():
    observations = (
        _terminal_observations()[0],
        _observation(
            sequence=2,
            removed_unit_index=1,
            verdict=DecisionVerdict.FAIL,
            character="1",
        ),
    )

    with pytest.raises(
        HveeContractError,
        match="distinct candidate scenarios",
    ):
        _build(observations=observations)


def test_rejects_source_scenario_reused_as_candidate():
    observation = _observation(
        sequence=1,
        removed_unit_index=0,
        verdict=DecisionVerdict.PASS,
        character="f",
    )

    with pytest.raises(
        HveeContractError,
        match="distinct candidate scenarios",
    ):
        _build(observations=(observation,))


def test_failing_observation_requires_counterexample_evidence():
    with pytest.raises(
        HveeContractError,
        match="counterexample evidence SHA-256",
    ):
        CounterexampleReductionObservation(
            sequence=1,
            removed_unit_index=0,
            scenario_sha256=_sha("1"),
            verdict=DecisionVerdict.FAIL,
            result_provenance_sha256=_sha("a"),
            observation_evidence_sha256=_sha("b"),
            decision_evidence_sha256=_sha("c"),
        )


def test_passing_observation_rejects_counterexample_evidence():
    with pytest.raises(
        HveeContractError,
        match="passing reduction observations",
    ):
        CounterexampleReductionObservation(
            sequence=1,
            removed_unit_index=0,
            scenario_sha256=_sha("1"),
            verdict=DecisionVerdict.PASS,
            result_provenance_sha256=_sha("a"),
            observation_evidence_sha256=_sha("b"),
            decision_evidence_sha256=_sha("c"),
            counterexample_evidence_sha256=_sha("d"),
        )


@pytest.mark.parametrize(
    "verdict",
    [
        DecisionVerdict.INCONCLUSIVE,
        DecisionVerdict.INVALID,
    ],
)
def test_observation_rejects_nonbinary_verdict(verdict):
    with pytest.raises(
        HveeContractError,
        match="pass or fail verdicts",
    ):
        CounterexampleReductionObservation(
            sequence=1,
            removed_unit_index=0,
            scenario_sha256=_sha("1"),
            verdict=verdict,
            result_provenance_sha256=_sha("a"),
            observation_evidence_sha256=_sha("b"),
            decision_evidence_sha256=_sha("c"),
        )


def test_rejects_candidate_equal_to_current_parent():
    observations = (
        _observation(
            sequence=1,
            removed_unit_index=0,
            verdict=DecisionVerdict.FAIL,
            character="1",
        ),
        _observation(
            sequence=2,
            removed_unit_index=1,
            verdict=DecisionVerdict.PASS,
            character="1",
        ),
    )

    with pytest.raises(
        HveeContractError,
        match="distinct candidate scenarios",
    ):
        _build(observations=observations)


def _recomputed_payload(bundle, mutate):
    tampered = deepcopy(bundle.payload)
    mutate(tampered)
    recomputed = calculate_minimal_counterexample_reduction_sha256(
        tampered
    )
    return tampered, recomputed


def test_verifier_rejects_parent_scenario_tampering():
    bundle = _build(
        observations=_terminal_observations()[:2]
    )
    tampered, recomputed = _recomputed_payload(
        bundle,
        lambda payload: payload["observations"][1]["proposal"].__setitem__(
            "parent_scenario_sha256",
            _sha("9"),
        ),
    )

    assert not verify_minimal_counterexample_reduction_bundle(
        payload=tampered,
        expected_sha256=recomputed,
    )


def test_verifier_rejects_retained_indices_tampering():
    bundle = _build(observations=_terminal_observations()[:1])
    tampered, recomputed = _recomputed_payload(
        bundle,
        lambda payload: payload["observations"][0]["proposal"].__setitem__(
            "retained_unit_indices",
            [0, 1],
        ),
    )

    assert not verify_minimal_counterexample_reduction_bundle(
        payload=tampered,
        expected_sha256=recomputed,
    )


def test_verifier_rejects_acceptance_tampering():
    bundle = _build(observations=_terminal_observations()[:1])
    tampered, recomputed = _recomputed_payload(
        bundle,
        lambda payload: payload["observations"][0].__setitem__(
            "accepted",
            True,
        ),
    )

    assert not verify_minimal_counterexample_reduction_bundle(
        payload=tampered,
        expected_sha256=recomputed,
    )


def test_verifier_rejects_proposal_reason_tampering():
    bundle = _build(observations=_terminal_observations()[:1])
    tampered, recomputed = _recomputed_payload(
        bundle,
        lambda payload: payload["outcome"]["next_proposal"].__setitem__(
            "reason",
            "initial_scan",
        ),
    )

    assert not verify_minimal_counterexample_reduction_bundle(
        payload=tampered,
        expected_sha256=recomputed,
    )


def test_verifier_rejects_outcome_tampering():
    bundle = _build(observations=_terminal_observations())
    tampered, recomputed = _recomputed_payload(
        bundle,
        lambda payload: payload["outcome"].__setitem__(
            "one_minimal_within_declared_units",
            False,
        ),
    )

    assert not verify_minimal_counterexample_reduction_bundle(
        payload=tampered,
        expected_sha256=recomputed,
    )


def test_verifier_rejects_budget_tampering():
    bundle = _build()
    tampered, recomputed = _recomputed_payload(
        bundle,
        lambda payload: payload["budget"].__setitem__(
            "remaining_observations",
            99,
        ),
    )

    assert not verify_minimal_counterexample_reduction_bundle(
        payload=tampered,
        expected_sha256=recomputed,
    )


def test_verifier_rejects_reduction_unit_digest_tampering():
    bundle = _build()
    tampered, recomputed = _recomputed_payload(
        bundle,
        lambda payload: payload["units"].__setitem__(
            "sha256",
            _sha("9"),
        ),
    )

    assert not verify_minimal_counterexample_reduction_bundle(
        payload=tampered,
        expected_sha256=recomputed,
    )


def test_verifier_rejects_unit_index_tampering():
    bundle = _build()
    tampered, recomputed = _recomputed_payload(
        bundle,
        lambda payload: payload["units"]["ordered"][0].__setitem__(
            "index",
            7,
        ),
    )

    assert not verify_minimal_counterexample_reduction_bundle(
        payload=tampered,
        expected_sha256=recomputed,
    )


def test_verifier_rejects_extra_fields():
    bundle = _build()
    tampered, recomputed = _recomputed_payload(
        bundle,
        lambda payload: payload.__setitem__(
            "estimated_global_minimum",
            True,
        ),
    )

    assert not verify_minimal_counterexample_reduction_bundle(
        payload=tampered,
        expected_sha256=recomputed,
    )


def test_binds_adaptive_search_failure_endpoint_as_source():
    adaptive_observations = (
        AdaptiveScenarioObservation(
            sequence=1,
            candidate_index=0,
            scenario_sha256=_sha("1"),
            verdict=DecisionVerdict.PASS,
            result_provenance_sha256=_sha("a"),
            observation_evidence_sha256=_sha("b"),
            decision_evidence_sha256=_sha("c"),
        ),
        AdaptiveScenarioObservation(
            sequence=2,
            candidate_index=2,
            scenario_sha256=_sha("2"),
            verdict=DecisionVerdict.FAIL,
            result_provenance_sha256=_sha("a"),
            observation_evidence_sha256=_sha("b"),
            decision_evidence_sha256=_sha("c"),
            counterexample_evidence_sha256=_sha("d"),
        ),
        AdaptiveScenarioObservation(
            sequence=3,
            candidate_index=1,
            scenario_sha256=_sha("3"),
            verdict=DecisionVerdict.FAIL,
            result_provenance_sha256=_sha("a"),
            observation_evidence_sha256=_sha("b"),
            decision_evidence_sha256=_sha("c"),
            counterexample_evidence_sha256=_sha("e"),
        ),
    )
    search = build_adaptive_scenario_search_bundle(
        evaluation_type="asr",
        search_key="hetren.asr.noise-search",
        search_version="1.0.0",
        boundary_key="hetren.asr.observed-boundary",
        boundary_version="1.0.0",
        axis_key="asr.noise.snr-db",
        axis_version="1.0.0",
        axis_unit="dB",
        candidate_values=(0, 1, 2),
        invariant_parameters={"codec": "pcm-s16le"},
        maximum_observations=3,
        observations=adaptive_observations,
    )
    boundary = search.observed_boundary

    assert boundary is not None
    failing_endpoint = next(
        endpoint
        for endpoint in boundary.payload["endpoints"]
        if endpoint["verdict"] == "fail"
    )
    reduction = _build(
        source_scenario_sha256=(
            failing_endpoint["scenario_sha256"]
        ),
        source_counterexample_evidence_sha256=(
            failing_endpoint["evidence"][
                "counterexample_evidence_sha256"
            ]
        ),
    )

    assert reduction.payload["source"] == {
        "scenario_sha256": _sha("3"),
        "counterexample_evidence_sha256": _sha("e"),
    }


def test_payload_excludes_local_identity_and_raw_content_fields():
    serialized = str(
        _build(observations=_terminal_observations()).payload
    ).lower()

    for forbidden in (
        "evaluation_run_id",
        "result_id",
        "created_at",
        "audio_file_path",
        "reference_transcript",
        "generated_transcript",
        "raw_audio",
    ):
        assert forbidden not in serialized


def test_evidence_boundary_explicitly_limits_claims():
    boundary = _build().payload["evidence_boundary"]

    assert boundary == {
        "source_failure_observed": True,
        "attempts_require_execution_evidence": True,
        "next_proposal_is_an_observation": False,
        "minimality_scope": "one_minimal_within_declared_units",
        "global_minimality_claimed": False,
        "unexecuted_outcomes_inferred": False,
        "causal_explanation_claimed": False,
        "neighborhood_explored": False,
        "contract_promoted": False,
        "raw_content_embedded": False,
        "qualification_authority": False,
    }

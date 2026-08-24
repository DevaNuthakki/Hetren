from copy import deepcopy

import pytest

from hvee.core.contracts import HveeContractError
from hvee.core.decision import DecisionVerdict
from hvee.core.minimal_counterexample_reduction import (
    CounterexampleReductionObservation,
    CounterexampleReductionUnit,
    build_minimal_counterexample_reduction_bundle,
)
from hvee.core.neighborhood_generation import (
    NEIGHBORHOOD_GENERATION_SCHEMA_VERSION,
    NeighborhoodCandidate,
    NeighborhoodGenerationStatus,
    NeighborhoodMutationDirection,
    NeighborhoodObservation,
    build_neighborhood_generation_bundle,
    calculate_neighborhood_candidates_sha256,
    calculate_neighborhood_generation_sha256,
    verify_neighborhood_generation_bundle,
)


def _sha(character: str) -> str:
    return character * 64


def _candidate(
    *,
    key: str,
    dimension_key: str,
    direction: NeighborhoodMutationDirection,
    ordinal_distance: int,
    character: str,
) -> NeighborhoodCandidate:
    return NeighborhoodCandidate(
        key=key,
        version="1.0.0",
        dimension_key=dimension_key,
        generator_key="hetren.asr.neighborhood-generator",
        generator_version="1.0.0",
        direction=direction,
        ordinal_distance=ordinal_distance,
        specification_sha256=_sha(character),
    )


def _candidates():
    return (
        _candidate(
            key="noise-lower-01",
            dimension_key="asr.noise.snr-db",
            direction=NeighborhoodMutationDirection.LOWER,
            ordinal_distance=1,
            character="a",
        ),
        _candidate(
            key="noise-upper-01",
            dimension_key="asr.noise.snr-db",
            direction=NeighborhoodMutationDirection.UPPER,
            ordinal_distance=1,
            character="b",
        ),
        _candidate(
            key="speed-lower-01",
            dimension_key="asr.speech.rate",
            direction=NeighborhoodMutationDirection.LOWER,
            ordinal_distance=1,
            character="c",
        ),
        _candidate(
            key="speed-upper-01",
            dimension_key="asr.speech.rate",
            direction=NeighborhoodMutationDirection.UPPER,
            ordinal_distance=1,
            character="d",
        ),
    )


def _observation(
    *,
    sequence: int,
    candidate_index: int,
    verdict: DecisionVerdict,
    character: str,
) -> NeighborhoodObservation:
    return NeighborhoodObservation(
        sequence=sequence,
        candidate_index=candidate_index,
        scenario_sha256=_sha(character),
        verdict=verdict,
        result_provenance_sha256=_sha("a"),
        observation_evidence_sha256=_sha("b"),
        decision_evidence_sha256=_sha("c"),
        counterexample_evidence_sha256=(
            _sha("e")
            if verdict == DecisionVerdict.FAIL
            else None
        ),
    )


def _terminal_observations():
    return (
        _observation(
            sequence=1,
            candidate_index=0,
            verdict=DecisionVerdict.PASS,
            character="1",
        ),
        _observation(
            sequence=2,
            candidate_index=1,
            verdict=DecisionVerdict.FAIL,
            character="2",
        ),
        _observation(
            sequence=3,
            candidate_index=2,
            verdict=DecisionVerdict.FAIL,
            character="3",
        ),
        _observation(
            sequence=4,
            candidate_index=3,
            verdict=DecisionVerdict.PASS,
            character="4",
        ),
    )


def _build(
    *,
    candidates=None,
    maximum_observations: int = 4,
    observations=(),
    source_scenario_sha256: str | None = None,
    source_counterexample_evidence_sha256: str | None = None,
    source_minimal_reduction_sha256: str | None = None,
):
    return build_neighborhood_generation_bundle(
        evaluation_type="asr",
        neighborhood_key="hetren.asr.local-neighborhood",
        neighborhood_version="1.0.0",
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
        source_minimal_reduction_sha256=(
            source_minimal_reduction_sha256
            if source_minimal_reduction_sha256 is not None
            else _sha("9")
        ),
        candidates=(
            candidates
            if candidates is not None
            else _candidates()
        ),
        maximum_observations=maximum_observations,
        observations=observations,
    )


def test_empty_neighborhood_proposes_first_candidate():
    bundle = _build()

    assert bundle.payload["schema_version"] == (
        NEIGHBORHOOD_GENERATION_SCHEMA_VERSION
    )
    assert bundle.payload["type"] == "neighborhood_generation"
    assert bundle.payload["neighborhood"]["status"] == "ready"
    assert bundle.payload["outcome"]["next_proposal"] == {
        "reason": "initial_candidate",
        "candidate": {
            "index": 0,
            "key": "noise-lower-01",
            "version": "1.0.0",
            "dimension_key": "asr.noise.snr-db",
            "generator": {
                "key": "hetren.asr.neighborhood-generator",
                "version": "1.0.0",
            },
            "mutation": {
                "direction": "lower",
                "ordinal_distance": 1,
                "specification_sha256": _sha("a"),
            },
        },
        "source_scenario_sha256": _sha("f"),
        "source_counterexample_evidence_sha256": _sha("e"),
        "source_minimal_reduction_sha256": _sha("9"),
    }
    assert bundle.payload["observations"] == []
    assert verify_neighborhood_generation_bundle(
        payload=bundle.payload,
        expected_sha256=bundle.sha256,
    )


def test_observation_advances_ordered_candidate_scan():
    bundle = _build(
        observations=_terminal_observations()[:1]
    )

    first = bundle.payload["observations"][0]
    assert first["proposal"]["candidate"]["index"] == 0
    assert first["observed_as_failure"] is False
    assert bundle.payload["outcome"]["next_proposal"][
        "reason"
    ] == "continue_ordered_scan"
    assert bundle.payload["outcome"]["next_proposal"][
        "candidate"
    ]["index"] == 1


def test_pass_and_fail_results_are_reported_without_inference():
    bundle = _build(
        observations=_terminal_observations()[:2]
    )

    assert bundle.payload["outcome"]["passing_candidate_indices"] == [
        0
    ]
    assert bundle.payload["outcome"]["failing_candidate_indices"] == [
        1
    ]
    assert bundle.payload["outcome"]["observed_verdict_counts"] == {
        "pass": 1,
        "fail": 1,
    }
    assert bundle.payload["outcome"]["mixed_observed_verdicts"] is True
    assert bundle.payload["outcome"][
        "declared_neighborhood_fully_observed"
    ] is False


def test_complete_neighborhood_reports_exact_observed_coverage():
    bundle = _build(observations=_terminal_observations())

    assert bundle.payload["neighborhood"]["status"] == "complete"
    assert bundle.payload["outcome"] == {
        "planned_candidate_count": 4,
        "observed_candidate_count": 4,
        "unobserved_candidate_count": 0,
        "passing_candidate_indices": [0, 3],
        "passing_candidate_keys": [
            "noise-lower-01",
            "speed-upper-01",
        ],
        "failing_candidate_indices": [1, 2],
        "failing_candidate_keys": [
            "noise-upper-01",
            "speed-lower-01",
        ],
        "observed_verdict_counts": {
            "pass": 2,
            "fail": 2,
        },
        "declared_neighborhood_fully_observed": True,
        "mixed_observed_verdicts": True,
        "next_proposal": None,
    }
    assert verify_neighborhood_generation_bundle(
        payload=bundle.payload,
        expected_sha256=bundle.sha256,
    )


def test_budget_exhaustion_does_not_claim_full_coverage():
    bundle = _build(
        maximum_observations=2,
        observations=_terminal_observations()[:2],
    )

    assert bundle.payload["neighborhood"]["status"] == (
        "budget_exhausted"
    )
    assert bundle.payload["budget"] == {
        "maximum_observations": 2,
        "planned_candidate_count": 4,
        "observed_count": 2,
        "remaining_observations": 0,
    }
    assert bundle.payload["outcome"]["unobserved_candidate_count"] == 2
    assert bundle.payload["outcome"]["next_proposal"] is None
    assert bundle.payload["outcome"][
        "declared_neighborhood_fully_observed"
    ] is False


def test_complete_result_wins_when_full_budget_is_consumed():
    bundle = _build(observations=_terminal_observations())

    assert bundle.payload["budget"]["remaining_observations"] == 0
    assert bundle.payload["neighborhood"]["status"] == "complete"


def test_status_values_are_explicit():
    assert set(NeighborhoodGenerationStatus) == {
        NeighborhoodGenerationStatus.READY,
        NeighborhoodGenerationStatus.COMPLETE,
        NeighborhoodGenerationStatus.BUDGET_EXHAUSTED,
    }


def test_bundle_is_deterministic_across_sequence_container_type():
    first = _build(
        candidates=list(_candidates()),
        observations=list(_terminal_observations()[:2]),
    )
    second = _build(
        candidates=_candidates(),
        observations=_terminal_observations()[:2],
    )

    assert first == second


def test_candidate_identity_is_independently_reproducible():
    bundle = _build()

    assert bundle.candidates_sha256 == (
        calculate_neighborhood_candidates_sha256(_candidates())
    )


def test_candidate_order_is_semantically_committed():
    forward = _build()
    reverse = _build(candidates=tuple(reversed(_candidates())))

    assert forward.candidates_sha256 != reverse.candidates_sha256
    assert forward.payload["outcome"]["next_proposal"][
        "candidate"
    ]["key"] == "noise-lower-01"
    assert reverse.payload["outcome"]["next_proposal"][
        "candidate"
    ]["key"] == "speed-upper-01"


def test_builder_detaches_mutable_sequences():
    candidates = list(_candidates())
    observations = list(_terminal_observations()[:1])
    bundle = _build(
        candidates=candidates,
        observations=observations,
    )

    candidates.clear()
    observations.clear()

    assert len(bundle.payload["candidates"]["ordered"]) == 4
    assert len(bundle.payload["observations"]) == 1


@pytest.mark.parametrize(
    "maximum",
    [
        True,
        0,
        5,
    ],
)
def test_rejects_invalid_observation_budget(maximum):
    with pytest.raises(
        HveeContractError,
        match="maximum observations",
    ):
        _build(maximum_observations=maximum)


@pytest.mark.parametrize(
    "candidates",
    [
        (),
        (object(),),
    ],
)
def test_rejects_invalid_candidate_sequence(candidates):
    with pytest.raises(
        HveeContractError,
        match="ordered sequence",
    ):
        _build(
            candidates=candidates,
            maximum_observations=1,
        )


def test_rejects_duplicate_candidate_identity():
    candidate = _candidates()[0]

    with pytest.raises(
        HveeContractError,
        match="identities must be unique",
    ):
        _build(
            candidates=(candidate, candidate),
            maximum_observations=1,
        )


def test_rejects_duplicate_candidate_key():
    with pytest.raises(
        HveeContractError,
        match="keys must be unique",
    ):
        _build(
            candidates=(
                _candidates()[0],
                _candidate(
                    key="noise-lower-01",
                    dimension_key="asr.noise.snr-db",
                    direction=NeighborhoodMutationDirection.LOWER,
                    ordinal_distance=2,
                    character="b",
                ),
            ),
            maximum_observations=1,
        )


def test_rejects_duplicate_candidate_coordinate():
    with pytest.raises(
        HveeContractError,
        match="coordinates must be unique",
    ):
        _build(
            candidates=(
                _candidates()[0],
                _candidate(
                    key="different-key",
                    dimension_key="asr.noise.snr-db",
                    direction=NeighborhoodMutationDirection.LOWER,
                    ordinal_distance=1,
                    character="b",
                ),
            ),
            maximum_observations=1,
        )


@pytest.mark.parametrize(
    (
        "key",
        "version",
        "dimension_key",
        "generator_key",
        "generator_version",
        "ordinal_distance",
        "specification_sha256",
    ),
    [
        (
            "Bad Key",
            "1.0.0",
            "asr.noise",
            "hetren.generator",
            "1.0.0",
            1,
            _sha("a"),
        ),
        (
            "candidate-01",
            " 1.0.0",
            "asr.noise",
            "hetren.generator",
            "1.0.0",
            1,
            _sha("a"),
        ),
        (
            "candidate-01",
            "1.0.0",
            "Bad Dimension",
            "hetren.generator",
            "1.0.0",
            1,
            _sha("a"),
        ),
        (
            "candidate-01",
            "1.0.0",
            "asr.noise",
            "Bad Generator",
            "1.0.0",
            1,
            _sha("a"),
        ),
        (
            "candidate-01",
            "1.0.0",
            "asr.noise",
            "hetren.generator",
            " 1.0.0",
            1,
            _sha("a"),
        ),
        (
            "candidate-01",
            "1.0.0",
            "asr.noise",
            "hetren.generator",
            "1.0.0",
            0,
            _sha("a"),
        ),
        (
            "candidate-01",
            "1.0.0",
            "asr.noise",
            "hetren.generator",
            "1.0.0",
            1,
            "not-a-digest",
        ),
    ],
)
def test_candidate_rejects_noncanonical_fields(
    key,
    version,
    dimension_key,
    generator_key,
    generator_version,
    ordinal_distance,
    specification_sha256,
):
    with pytest.raises(HveeContractError):
        NeighborhoodCandidate(
            key=key,
            version=version,
            dimension_key=dimension_key,
            generator_key=generator_key,
            generator_version=generator_version,
            direction=NeighborhoodMutationDirection.ALTERNATE,
            ordinal_distance=ordinal_distance,
            specification_sha256=specification_sha256,
        )


def test_candidate_rejects_noncanonical_direction_type():
    with pytest.raises(
        HveeContractError,
        match="direction must be canonical",
    ):
        NeighborhoodCandidate(
            key="candidate-01",
            version="1.0.0",
            dimension_key="asr.noise",
            generator_key="hetren.generator",
            generator_version="1.0.0",
            direction="lower",
            ordinal_distance=1,
            specification_sha256=_sha("a"),
        )


def test_rejects_noncontiguous_observation_sequence():
    observation = _observation(
        sequence=2,
        candidate_index=0,
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
        candidate_index=1,
        verdict=DecisionVerdict.PASS,
        character="1",
    )

    with pytest.raises(
        HveeContractError,
        match="deterministic proposal trajectory",
    ):
        _build(observations=(observation,))


def test_rejects_observations_after_complete_neighborhood():
    extra = _observation(
        sequence=5,
        candidate_index=4,
        verdict=DecisionVerdict.PASS,
        character="5",
    )

    with pytest.raises(
        HveeContractError,
        match="cannot continue after",
    ):
        _build(observations=(*_terminal_observations(), extra))


def test_rejects_observations_after_budget_exhaustion():
    with pytest.raises(
        HveeContractError,
        match="cannot continue after",
    ):
        _build(
            maximum_observations=2,
            observations=_terminal_observations()[:3],
        )


def test_rejects_source_scenario_reused_as_candidate():
    observation = _observation(
        sequence=1,
        candidate_index=0,
        verdict=DecisionVerdict.PASS,
        character="f",
    )

    with pytest.raises(
        HveeContractError,
        match="distinct candidate scenarios",
    ):
        _build(observations=(observation,))


def test_rejects_duplicate_candidate_scenario_identity():
    observations = (
        _observation(
            sequence=1,
            candidate_index=0,
            verdict=DecisionVerdict.PASS,
            character="1",
        ),
        _observation(
            sequence=2,
            candidate_index=1,
            verdict=DecisionVerdict.FAIL,
            character="1",
        ),
    )

    with pytest.raises(
        HveeContractError,
        match="distinct candidate scenarios",
    ):
        _build(observations=observations)


def test_failing_observation_requires_counterexample_evidence():
    with pytest.raises(
        HveeContractError,
        match="counterexample evidence SHA-256",
    ):
        NeighborhoodObservation(
            sequence=1,
            candidate_index=0,
            scenario_sha256=_sha("1"),
            verdict=DecisionVerdict.FAIL,
            result_provenance_sha256=_sha("a"),
            observation_evidence_sha256=_sha("b"),
            decision_evidence_sha256=_sha("c"),
        )


def test_passing_observation_rejects_counterexample_evidence():
    with pytest.raises(
        HveeContractError,
        match="passing neighborhood observations",
    ):
        NeighborhoodObservation(
            sequence=1,
            candidate_index=0,
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
        "pass",
    ],
)
def test_observation_rejects_nonbinary_verdict(verdict):
    with pytest.raises(
        HveeContractError,
        match="pass or fail verdicts",
    ):
        NeighborhoodObservation(
            sequence=1,
            candidate_index=0,
            scenario_sha256=_sha("1"),
            verdict=verdict,
            result_provenance_sha256=_sha("a"),
            observation_evidence_sha256=_sha("b"),
            decision_evidence_sha256=_sha("c"),
        )


@pytest.mark.parametrize(
    ("sequence", "candidate_index"),
    [
        (True, 0),
        (0, 0),
        (1, True),
        (1, -1),
    ],
)
def test_observation_rejects_invalid_indices(
    sequence,
    candidate_index,
):
    with pytest.raises(HveeContractError):
        NeighborhoodObservation(
            sequence=sequence,
            candidate_index=candidate_index,
            scenario_sha256=_sha("1"),
            verdict=DecisionVerdict.PASS,
            result_provenance_sha256=_sha("a"),
            observation_evidence_sha256=_sha("b"),
            decision_evidence_sha256=_sha("c"),
        )


@pytest.mark.parametrize(
    "field",
    [
        "source_scenario_sha256",
        "source_counterexample_evidence_sha256",
        "source_minimal_reduction_sha256",
    ],
)
def test_rejects_invalid_source_evidence_digest(field):
    arguments = {field: "not-a-digest"}

    with pytest.raises(HveeContractError):
        _build(**arguments)


def _recomputed_payload(bundle, mutate):
    tampered = deepcopy(bundle.payload)
    mutate(tampered)
    recomputed = calculate_neighborhood_generation_sha256(tampered)
    return tampered, recomputed


def test_verifier_rejects_observation_candidate_tampering():
    bundle = _build(observations=_terminal_observations()[:1])
    tampered, recomputed = _recomputed_payload(
        bundle,
        lambda payload: payload["observations"][0]["proposal"][
            "candidate"
        ].__setitem__("index", 1),
    )

    assert not verify_neighborhood_generation_bundle(
        payload=tampered,
        expected_sha256=recomputed,
    )


def test_verifier_rejects_proposal_reason_tampering():
    bundle = _build(observations=_terminal_observations()[:1])
    tampered, recomputed = _recomputed_payload(
        bundle,
        lambda payload: payload["outcome"]["next_proposal"].__setitem__(
            "reason",
            "initial_candidate",
        ),
    )

    assert not verify_neighborhood_generation_bundle(
        payload=tampered,
        expected_sha256=recomputed,
    )


def test_verifier_rejects_source_reduction_tampering():
    bundle = _build(observations=_terminal_observations()[:1])
    tampered, recomputed = _recomputed_payload(
        bundle,
        lambda payload: payload["observations"][0]["proposal"].__setitem__(
            "source_minimal_reduction_sha256",
            _sha("8"),
        ),
    )

    assert not verify_neighborhood_generation_bundle(
        payload=tampered,
        expected_sha256=recomputed,
    )


def test_verifier_rejects_failure_flag_tampering():
    bundle = _build(observations=_terminal_observations()[:2])
    tampered, recomputed = _recomputed_payload(
        bundle,
        lambda payload: payload["observations"][1].__setitem__(
            "observed_as_failure",
            False,
        ),
    )

    assert not verify_neighborhood_generation_bundle(
        payload=tampered,
        expected_sha256=recomputed,
    )


def test_verifier_rejects_outcome_tampering():
    bundle = _build(observations=_terminal_observations())
    tampered, recomputed = _recomputed_payload(
        bundle,
        lambda payload: payload["outcome"].__setitem__(
            "declared_neighborhood_fully_observed",
            False,
        ),
    )

    assert not verify_neighborhood_generation_bundle(
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

    assert not verify_neighborhood_generation_bundle(
        payload=tampered,
        expected_sha256=recomputed,
    )


def test_verifier_rejects_candidate_digest_tampering():
    bundle = _build()
    tampered, recomputed = _recomputed_payload(
        bundle,
        lambda payload: payload["candidates"].__setitem__(
            "sha256",
            _sha("8"),
        ),
    )

    assert not verify_neighborhood_generation_bundle(
        payload=tampered,
        expected_sha256=recomputed,
    )


def test_verifier_rejects_candidate_index_tampering():
    bundle = _build()
    tampered, recomputed = _recomputed_payload(
        bundle,
        lambda payload: payload["candidates"]["ordered"][0].__setitem__(
            "index",
            7,
        ),
    )

    assert not verify_neighborhood_generation_bundle(
        payload=tampered,
        expected_sha256=recomputed,
    )


def test_verifier_rejects_extra_fields():
    bundle = _build()
    tampered, recomputed = _recomputed_payload(
        bundle,
        lambda payload: payload.__setitem__(
            "estimated_failure_probability",
            0.5,
        ),
    )

    assert not verify_neighborhood_generation_bundle(
        payload=tampered,
        expected_sha256=recomputed,
    )


def test_verifier_rejects_wrong_expected_identity():
    bundle = _build()

    assert not verify_neighborhood_generation_bundle(
        payload=bundle.payload,
        expected_sha256=_sha("8"),
    )


def test_terminal_minimal_reduction_can_seed_neighborhood():
    reduction = build_minimal_counterexample_reduction_bundle(
        evaluation_type="asr",
        reduction_key="hetren.asr.minimal-counterexample",
        reduction_version="1.0.0",
        source_scenario_sha256=_sha("f"),
        source_counterexample_evidence_sha256=_sha("e"),
        units=(
            CounterexampleReductionUnit(
                key="segment-000",
                version="1.0.0",
                content_sha256=_sha("a"),
            ),
        ),
        maximum_observations=1,
        observations=(
            CounterexampleReductionObservation(
                sequence=1,
                removed_unit_index=0,
                scenario_sha256=_sha("7"),
                verdict=DecisionVerdict.FAIL,
                result_provenance_sha256=_sha("a"),
                observation_evidence_sha256=_sha("b"),
                decision_evidence_sha256=_sha("c"),
                counterexample_evidence_sha256=_sha("d"),
            ),
        ),
    )

    assert reduction.payload["reduction"]["status"] == "one_minimal"

    neighborhood = _build(
        source_scenario_sha256=reduction.payload["outcome"][
            "current_scenario_sha256"
        ],
        source_counterexample_evidence_sha256=reduction.payload[
            "outcome"
        ]["current_counterexample_evidence_sha256"],
        source_minimal_reduction_sha256=reduction.sha256,
    )

    assert neighborhood.payload["source"] == {
        "scenario_sha256": _sha("7"),
        "counterexample_evidence_sha256": _sha("d"),
        "minimal_counterexample_reduction_sha256": reduction.sha256,
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
        "raw_mutation_value",
    ):
        assert forbidden not in serialized


def test_evidence_boundary_explicitly_limits_claims():
    boundary = _build().payload["evidence_boundary"]

    assert boundary == {
        "source_failure_observed": True,
        "source_minimal_reduction_linked": True,
        "candidate_specifications_committed": True,
        "candidates_are_single_declared_mutations": True,
        "observations_require_execution_evidence": True,
        "next_proposal_is_an_observation": False,
        "declared_neighborhood_scope": (
            "ordered_single_mutation_candidates"
        ),
        "unexecuted_outcomes_inferred": False,
        "continuous_failure_region_claimed": False,
        "causal_explanation_claimed": False,
        "statistical_generalization_claimed": False,
        "contract_promoted": False,
        "raw_content_embedded": False,
        "qualification_authority": False,
    }

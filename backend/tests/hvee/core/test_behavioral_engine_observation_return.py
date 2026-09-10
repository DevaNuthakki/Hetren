from __future__ import annotations

from copy import deepcopy

import pytest

from hvee.core.adaptive_scenario_search import (
    AdaptiveScenarioObservation,
    build_adaptive_scenario_search_bundle,
)
from hvee.core.behavioral_engine import (
    BehavioralEngineOperation,
    build_adaptive_search_experiment_bundle,
    build_behavioral_engine_observation_return_bundle,
    build_minimal_reduction_experiment_bundle,
    build_neighborhood_experiment_bundle,
    calculate_behavioral_engine_observation_return_sha256,
    verify_behavioral_engine_observation_return_bundle,
)
from hvee.core.contracts import HveeContractError
from hvee.core.decision import DecisionVerdict
from hvee.core.experiment_protocol import (
    ExperimentObservationStatus,
)
from hvee.core.minimal_counterexample_reduction import (
    CounterexampleReductionObservation,
    CounterexampleReductionUnit,
    build_minimal_counterexample_reduction_bundle,
)
from hvee.core.neighborhood_generation import (
    NeighborhoodCandidate,
    NeighborhoodGenerationStatus,
    NeighborhoodMutationDirection,
    NeighborhoodObservation,
    build_neighborhood_generation_bundle,
)


def _sha(
    character: str,
) -> str:
    return character * 64


def _adaptive_source():
    return build_adaptive_scenario_search_bundle(
        evaluation_type="asr",
        search_key="hetren.return.search",
        search_version="1.0.0",
        boundary_key="hetren.return.boundary",
        boundary_version="1.0.0",
        axis_key="noise.snr",
        axis_version="1.0.0",
        axis_unit="db",
        candidate_values=(
            0,
            10,
            20,
        ),
        invariant_parameters={
            "model_role": "candidate",
        },
        maximum_observations=3,
        observations=(),
    )


def _reduction_units():
    return (
        CounterexampleReductionUnit(
            key="segment-000",
            version="1.0.0",
            content_sha256=_sha("1"),
        ),
        CounterexampleReductionUnit(
            key="segment-001",
            version="1.0.0",
            content_sha256=_sha("2"),
        ),
    )


def _reduction_source():
    return build_minimal_counterexample_reduction_bundle(
        evaluation_type="asr",
        reduction_key=("hetren.return.reduction"),
        reduction_version="1.0.0",
        source_scenario_sha256=(_sha("a")),
        source_counterexample_evidence_sha256=(_sha("b")),
        units=_reduction_units(),
        maximum_observations=3,
        observations=(),
    )


def _neighborhood_candidate():
    return NeighborhoodCandidate(
        key="noise-lower-01",
        version="1.0.0",
        dimension_key="noise.snr",
        generator_key=("hetren.return.generator"),
        generator_version="1.0.0",
        direction=(NeighborhoodMutationDirection.LOWER),
        ordinal_distance=1,
        specification_sha256=_sha("3"),
    )


def _neighborhood_source():
    return build_neighborhood_generation_bundle(
        evaluation_type="asr",
        neighborhood_key=("hetren.return.neighborhood"),
        neighborhood_version="1.0.0",
        source_scenario_sha256=_sha("a"),
        source_counterexample_evidence_sha256=(_sha("b")),
        source_minimal_reduction_sha256=(_sha("c")),
        candidates=(_neighborhood_candidate(),),
        maximum_observations=1,
        observations=(),
    )


def _experiment(
    operation,
    source,
    *,
    maximum_cost_units=1,
):
    common = {
        "source_bundle": source,
        "campaign_key": ("observation-return-test"),
        "campaign_version": "1.0.0",
        "subject_sha256": _sha("d"),
        "target_sha256": _sha("e"),
        "estimated_cost_units": 1,
        "maximum_cost_units": (maximum_cost_units),
    }

    if operation == BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH:
        return build_adaptive_search_experiment_bundle(**common)

    if operation == BehavioralEngineOperation.MINIMAL_COUNTEREXAMPLE_REDUCTION:
        return build_minimal_reduction_experiment_bundle(**common)

    if operation == BehavioralEngineOperation.NEIGHBORHOOD_GENERATION:
        return build_neighborhood_experiment_bundle(**common)

    raise AssertionError("unsupported test operation")


def _returned(
    operation,
    source,
    *,
    verdict=DecisionVerdict.PASS,
    counterexample_evidence_sha256=None,
    actual_cost_units=1,
    experiment=None,
):
    if experiment is None:
        experiment = _experiment(
            operation,
            source,
        )

    return build_behavioral_engine_observation_return_bundle(
        experiment_bundle=experiment,
        source_bundle=source,
        scenario_sha256=_sha("f"),
        verdict=verdict,
        result_provenance_sha256=(_sha("4")),
        observation_evidence_sha256=(_sha("5")),
        decision_evidence_sha256=(_sha("6")),
        counterexample_evidence_sha256=(counterexample_evidence_sha256),
        actual_cost_units=(actual_cost_units),
    )


def test_adaptive_return_constructs_native_observation():
    source = _adaptive_source()

    returned = _returned(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        source,
    )

    assert isinstance(
        returned.native_observation,
        AdaptiveScenarioObservation,
    )

    assert returned.native_observation.sequence == 1

    assert (
        returned.native_observation.candidate_index
        == source.payload["outcome"]["next_proposal"]["candidate_index"]
    )

    assert returned.native_observation.verdict == DecisionVerdict.PASS


def test_reduction_return_constructs_native_observation():
    source = _reduction_source()

    returned = _returned(
        BehavioralEngineOperation.MINIMAL_COUNTEREXAMPLE_REDUCTION,
        source,
    )

    assert isinstance(
        returned.native_observation,
        CounterexampleReductionObservation,
    )

    assert (
        returned.native_observation.removed_unit_index
        == source.payload["outcome"]["next_proposal"]["removed_unit"]["index"]
    )


def test_neighborhood_return_constructs_native_observation():
    source = _neighborhood_source()

    returned = _returned(
        BehavioralEngineOperation.NEIGHBORHOOD_GENERATION,
        source,
    )

    assert isinstance(
        returned.native_observation,
        NeighborhoodObservation,
    )

    assert (
        returned.native_observation.candidate_index
        == source.payload["outcome"]["next_proposal"]["candidate"]["index"]
    )


@pytest.mark.parametrize(
    (
        "operation",
        "source_factory",
    ),
    [
        (
            BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
            _adaptive_source,
        ),
        (
            BehavioralEngineOperation.MINIMAL_COUNTEREXAMPLE_REDUCTION,
            _reduction_source,
        ),
        (
            BehavioralEngineOperation.NEIGHBORHOOD_GENERATION,
            _neighborhood_source,
        ),
    ],
)
def test_observation_return_is_reverifiable(
    operation,
    source_factory,
):
    source = source_factory()

    experiment = _experiment(
        operation,
        source,
    )

    returned = _returned(
        operation,
        source,
        experiment=experiment,
    )

    assert verify_behavioral_engine_observation_return_bundle(
        payload=returned.payload,
        expected_sha256=(returned.sha256),
        experiment_bundle=(experiment),
        source_bundle=source,
    )


def test_generic_experiment_observation_is_completed():
    source = _adaptive_source()

    returned = _returned(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        source,
    )

    observation = returned.experiment_observation

    assert observation.status == ExperimentObservationStatus.COMPLETED

    assert observation.outcome_key == "pass"

    assert observation.result_evidence_sha256 == _sha("4")

    assert observation.evaluator_evidence_sha256 == _sha("6")


def test_fail_requires_counterexample_evidence():
    source = _adaptive_source()

    with pytest.raises(
        HveeContractError,
        match="requires counterexample",
    ):
        _returned(
            BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
            source,
            verdict=DecisionVerdict.FAIL,
        )


def test_fail_preserves_counterexample_evidence():
    source = _adaptive_source()

    returned = _returned(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        source,
        verdict=DecisionVerdict.FAIL,
        counterexample_evidence_sha256=(_sha("7")),
    )

    assert returned.native_observation.counterexample_evidence_sha256 == _sha("7")


def test_pass_rejects_counterexample_evidence():
    source = _adaptive_source()

    with pytest.raises(
        HveeContractError,
        match="must not include",
    ):
        _returned(
            BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
            source,
            verdict=DecisionVerdict.PASS,
            counterexample_evidence_sha256=(_sha("7")),
        )


@pytest.mark.parametrize(
    "verdict",
    [
        DecisionVerdict.INCONCLUSIVE,
        DecisionVerdict.INVALID,
    ],
)
def test_nonbinary_verdict_fails_closed(
    verdict,
):
    source = _adaptive_source()

    with pytest.raises(
        HveeContractError,
        match="must be pass or fail",
    ):
        _returned(
            BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
            source,
            verdict=verdict,
        )


def test_actual_cost_cannot_exceed_experiment_budget():
    source = _adaptive_source()

    experiment = _experiment(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        source,
        maximum_cost_units=2,
    )

    with pytest.raises(
        HveeContractError,
        match="actual cost exceeds",
    ):
        _returned(
            BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
            source,
            actual_cost_units=3,
            experiment=experiment,
        )


def test_adaptive_native_observation_is_accepted_by_native_state_machine():
    source = _adaptive_source()

    returned = _returned(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        source,
    )

    advanced = build_adaptive_scenario_search_bundle(
        evaluation_type="asr",
        search_key=("hetren.return.search"),
        search_version="1.0.0",
        boundary_key=("hetren.return.boundary"),
        boundary_version="1.0.0",
        axis_key="noise.snr",
        axis_version="1.0.0",
        axis_unit="db",
        candidate_values=(
            0,
            10,
            20,
        ),
        invariant_parameters={
            "model_role": "candidate",
        },
        maximum_observations=3,
        observations=(returned.native_observation,),
    )

    assert len(advanced.payload["observations"]) == 1

    assert advanced.payload["outcome"]["next_proposal"]["candidate_index"] == 2


def test_reduction_native_observation_is_accepted_by_native_state_machine():
    source = _reduction_source()

    returned = _returned(
        BehavioralEngineOperation.MINIMAL_COUNTEREXAMPLE_REDUCTION,
        source,
    )

    advanced = build_minimal_counterexample_reduction_bundle(
        evaluation_type="asr",
        reduction_key=("hetren.return.reduction"),
        reduction_version="1.0.0",
        source_scenario_sha256=(_sha("a")),
        source_counterexample_evidence_sha256=(_sha("b")),
        units=_reduction_units(),
        maximum_observations=3,
        observations=(returned.native_observation,),
    )

    assert len(advanced.payload["observations"]) == 1

    assert advanced.payload["outcome"]["next_proposal"]["removed_unit"]["index"] == 1


def test_neighborhood_native_observation_is_accepted_by_native_state_machine():
    source = _neighborhood_source()

    returned = _returned(
        BehavioralEngineOperation.NEIGHBORHOOD_GENERATION,
        source,
    )

    advanced = build_neighborhood_generation_bundle(
        evaluation_type="asr",
        neighborhood_key=("hetren.return.neighborhood"),
        neighborhood_version="1.0.0",
        source_scenario_sha256=(_sha("a")),
        source_counterexample_evidence_sha256=(_sha("b")),
        source_minimal_reduction_sha256=(_sha("c")),
        candidates=(_neighborhood_candidate(),),
        maximum_observations=1,
        observations=(returned.native_observation,),
    )

    assert (
        advanced.payload["neighborhood"]["status"]
        == NeighborhoodGenerationStatus.COMPLETE.value
    )

    assert advanced.payload["outcome"]["next_proposal"] is None


def test_source_bundle_tampering_blocks_observation_return():
    source = _adaptive_source()

    experiment = _experiment(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        source,
    )

    source.payload["outcome"]["next_proposal"]["reason"] = "tampered"

    with pytest.raises(
        HveeContractError,
        match="failed verification",
    ):
        build_behavioral_engine_observation_return_bundle(
            experiment_bundle=experiment,
            source_bundle=source,
            scenario_sha256=_sha("f"),
            verdict=DecisionVerdict.PASS,
            result_provenance_sha256=_sha("4"),
            observation_evidence_sha256=_sha("5"),
            decision_evidence_sha256=_sha("6"),
        )


def test_experiment_bundle_tampering_blocks_observation_return():
    source = _adaptive_source()

    experiment = _experiment(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        source,
    )

    experiment.payload["experiment_protocol_sha256"] = _sha("9")

    with pytest.raises(
        HveeContractError,
        match="failed verification",
    ):
        build_behavioral_engine_observation_return_bundle(
            experiment_bundle=experiment,
            source_bundle=source,
            scenario_sha256=_sha("f"),
            verdict=DecisionVerdict.PASS,
            result_provenance_sha256=_sha("4"),
            observation_evidence_sha256=_sha("5"),
            decision_evidence_sha256=_sha("6"),
        )


def test_return_verifier_rejects_native_observation_tampering():
    source = _adaptive_source()

    experiment = _experiment(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        source,
    )

    returned = _returned(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        source,
        experiment=experiment,
    )

    payload = deepcopy(returned.payload)

    payload["native_observation"]["candidate_index"] = 2

    recomputed = calculate_behavioral_engine_observation_return_sha256(payload)

    assert not (
        verify_behavioral_engine_observation_return_bundle(
            payload=payload,
            expected_sha256=recomputed,
            experiment_bundle=experiment,
            source_bundle=source,
        )
    )


def test_return_is_deterministic():
    first_source = _adaptive_source()
    second_source = _adaptive_source()

    first_experiment = _experiment(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        first_source,
    )

    second_experiment = _experiment(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        second_source,
    )

    first = _returned(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        first_source,
        experiment=first_experiment,
    )

    second = _returned(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        second_source,
        experiment=second_experiment,
    )

    assert first.sha256 == second.sha256

    assert first.payload == second.payload


def test_observation_return_does_not_claim_state_progression():
    source = _adaptive_source()

    returned = _returned(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        source,
    )

    boundary = returned.payload["evidence_boundary"]

    assert boundary["native_observation_constructed"] is True

    assert boundary["native_state_advanced"] is False

    assert boundary["behavioral_performance_qualified"] is False

    assert boundary["execution_evidence_verified"] is False

    assert boundary["internal_engine_used"] is False


def test_observation_return_contains_no_raw_content():
    source = _adaptive_source()

    returned = _returned(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        source,
    )

    serialized = repr(returned.payload)

    for forbidden in (
        "reference_text",
        "prediction_text",
        "raw_transcript_text",
        "audio_bytes",
        "prompt_text",
    ):
        assert forbidden not in serialized

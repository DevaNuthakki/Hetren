from __future__ import annotations

from copy import deepcopy

import pytest

from hvee.core.adaptive_scenario_search import (
    AdaptiveScenarioObservation,
    build_adaptive_scenario_search_bundle,
)
from hvee.core.behavioral_engine import (
    BehavioralEngineOperation,
    advance_behavioral_engine_closed_loop_step,
    build_adaptive_search_experiment_bundle,
    build_behavioral_engine_observation_return_bundle,
    build_minimal_reduction_experiment_bundle,
    build_neighborhood_experiment_bundle,
    calculate_behavioral_engine_closed_loop_step_sha256,
    verify_behavioral_engine_closed_loop_step_bundle,
)
from hvee.core.contracts import HveeContractError
from hvee.core.decision import DecisionVerdict
from hvee.core.minimal_counterexample_reduction import (
    CounterexampleReductionObservation,
    CounterexampleReductionUnit,
    build_minimal_counterexample_reduction_bundle,
)
from hvee.core.neighborhood_generation import (
    NeighborhoodCandidate,
    NeighborhoodMutationDirection,
    NeighborhoodObservation,
    build_neighborhood_generation_bundle,
)


def _sha(
    character: str,
) -> str:
    return character * 64


def _adaptive_source(
    observations=(),
):
    return build_adaptive_scenario_search_bundle(
        evaluation_type="asr",
        search_key="hetren.loop.search",
        search_version="1.0.0",
        boundary_key="hetren.loop.boundary",
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
        observations=observations,
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


def _reduction_source(
    observations=(),
):
    return build_minimal_counterexample_reduction_bundle(
        evaluation_type="asr",
        reduction_key="hetren.loop.reduction",
        reduction_version="1.0.0",
        source_scenario_sha256=_sha("a"),
        source_counterexample_evidence_sha256=(_sha("b")),
        units=_reduction_units(),
        maximum_observations=3,
        observations=observations,
    )


def _neighborhood_candidate():
    return NeighborhoodCandidate(
        key="noise-lower-01",
        version="1.0.0",
        dimension_key="noise.snr",
        generator_key="hetren.loop.generator",
        generator_version="1.0.0",
        direction=(NeighborhoodMutationDirection.LOWER),
        ordinal_distance=1,
        specification_sha256=_sha("3"),
    )


def _neighborhood_source(
    observations=(),
):
    return build_neighborhood_generation_bundle(
        evaluation_type="asr",
        neighborhood_key="hetren.loop.neighborhood",
        neighborhood_version="1.0.0",
        source_scenario_sha256=_sha("a"),
        source_counterexample_evidence_sha256=(_sha("b")),
        source_minimal_reduction_sha256=(_sha("c")),
        candidates=(_neighborhood_candidate(),),
        maximum_observations=1,
        observations=observations,
    )


def _experiment(
    operation,
    source,
    *,
    target_character="d",
):
    common = {
        "source_bundle": source,
        "campaign_key": "closed-loop-test",
        "campaign_version": "1.0.0",
        "subject_sha256": _sha("e"),
        "target_sha256": _sha(target_character),
        "estimated_cost_units": 1,
        "maximum_cost_units": 1,
    }

    if operation == BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH:
        return build_adaptive_search_experiment_bundle(**common)

    if operation == BehavioralEngineOperation.MINIMAL_COUNTEREXAMPLE_REDUCTION:
        return build_minimal_reduction_experiment_bundle(**common)

    if operation == BehavioralEngineOperation.NEIGHBORHOOD_GENERATION:
        return build_neighborhood_experiment_bundle(**common)

    raise AssertionError("unsupported operation")


def _returned(
    operation,
    source,
    experiment,
    *,
    scenario_character="f",
    verdict=DecisionVerdict.PASS,
    counterexample_character=None,
):
    counterexample_sha = None

    if counterexample_character is not None:
        counterexample_sha = _sha(counterexample_character)

    return build_behavioral_engine_observation_return_bundle(
        experiment_bundle=experiment,
        source_bundle=source,
        scenario_sha256=_sha(scenario_character),
        verdict=verdict,
        result_provenance_sha256=_sha("4"),
        observation_evidence_sha256=_sha("5"),
        decision_evidence_sha256=_sha("6"),
        counterexample_evidence_sha256=(counterexample_sha),
        actual_cost_units=1,
    )


def test_adaptive_step_advances_state_and_emits_next_experiment():
    source = _adaptive_source()

    experiment = _experiment(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        source,
    )

    returned = _returned(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        source,
        experiment,
    )

    def advance(
        observation: AdaptiveScenarioObservation,
    ):
        return _adaptive_source(observations=(observation,))

    step = advance_behavioral_engine_closed_loop_step(
        source_bundle=source,
        experiment_bundle=experiment,
        observation_return_bundle=returned,
        advance_native_state=advance,
        next_target_sha256=_sha("7"),
    )

    assert len(step.advanced_source_bundle.payload["observations"]) == 1

    assert step.next_experiment is not None

    assert (
        step.next_experiment.payload["source"]["bundle_sha256"]
        == step.advanced_source_bundle.sha256
    )

    assert step.payload["state_transition"]["terminal"] is False


def test_reduction_step_advances_state_and_emits_next_experiment():
    source = _reduction_source()

    experiment = _experiment(
        BehavioralEngineOperation.MINIMAL_COUNTEREXAMPLE_REDUCTION,
        source,
    )

    returned = _returned(
        BehavioralEngineOperation.MINIMAL_COUNTEREXAMPLE_REDUCTION,
        source,
        experiment,
    )

    def advance(
        observation: CounterexampleReductionObservation,
    ):
        return _reduction_source(observations=(observation,))

    step = advance_behavioral_engine_closed_loop_step(
        source_bundle=source,
        experiment_bundle=experiment,
        observation_return_bundle=returned,
        advance_native_state=advance,
        next_target_sha256=_sha("7"),
    )

    assert step.next_experiment is not None

    assert (
        step.advanced_source_bundle.payload["outcome"]["next_proposal"]["removed_unit"][
            "index"
        ]
        == 1
    )


def test_neighborhood_step_reaches_terminal_state():
    source = _neighborhood_source()

    experiment = _experiment(
        BehavioralEngineOperation.NEIGHBORHOOD_GENERATION,
        source,
    )

    returned = _returned(
        BehavioralEngineOperation.NEIGHBORHOOD_GENERATION,
        source,
        experiment,
    )

    def advance(
        observation: NeighborhoodObservation,
    ):
        return _neighborhood_source(observations=(observation,))

    step = advance_behavioral_engine_closed_loop_step(
        source_bundle=source,
        experiment_bundle=experiment,
        observation_return_bundle=returned,
        advance_native_state=advance,
        next_target_sha256=None,
    )

    assert step.next_experiment is None

    assert step.payload["state_transition"]["terminal"] is True

    assert step.advanced_source_bundle.payload["outcome"]["next_proposal"] is None


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
def test_closed_loop_step_is_reverifiable(
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
        experiment,
    )

    if operation == BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH:
        advance = lambda observation: _adaptive_source(observations=(observation,))

        next_target = _sha("7")

    elif operation == BehavioralEngineOperation.MINIMAL_COUNTEREXAMPLE_REDUCTION:
        advance = lambda observation: _reduction_source(observations=(observation,))

        next_target = _sha("7")

    else:
        advance = lambda observation: _neighborhood_source(observations=(observation,))

        next_target = None

    step = advance_behavioral_engine_closed_loop_step(
        source_bundle=source,
        experiment_bundle=experiment,
        observation_return_bundle=returned,
        advance_native_state=advance,
        next_target_sha256=next_target,
    )

    assert verify_behavioral_engine_closed_loop_step_bundle(
        payload=step.payload,
        expected_sha256=step.sha256,
        source_bundle=source,
        experiment_bundle=experiment,
        observation_return_bundle=returned,
        advanced_source_bundle=(step.advanced_source_bundle),
        next_experiment=(step.next_experiment),
    )


def test_nonterminal_state_requires_next_target():
    source = _adaptive_source()

    experiment = _experiment(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        source,
    )

    returned = _returned(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        source,
        experiment,
    )

    with pytest.raises(
        HveeContractError,
        match="requires next_target_sha256",
    ):
        advance_behavioral_engine_closed_loop_step(
            source_bundle=source,
            experiment_bundle=experiment,
            observation_return_bundle=returned,
            advance_native_state=(
                lambda observation: _adaptive_source(observations=(observation,))
            ),
            next_target_sha256=None,
        )


def test_terminal_state_rejects_spurious_next_target():
    source = _neighborhood_source()

    experiment = _experiment(
        BehavioralEngineOperation.NEIGHBORHOOD_GENERATION,
        source,
    )

    returned = _returned(
        BehavioralEngineOperation.NEIGHBORHOOD_GENERATION,
        source,
        experiment,
    )

    with pytest.raises(
        HveeContractError,
        match="must not declare a next target",
    ):
        advance_behavioral_engine_closed_loop_step(
            source_bundle=source,
            experiment_bundle=experiment,
            observation_return_bundle=returned,
            advance_native_state=(
                lambda observation: _neighborhood_source(observations=(observation,))
            ),
            next_target_sha256=_sha("7"),
        )


def test_advancer_must_return_same_behavioral_component_type():
    source = _adaptive_source()

    experiment = _experiment(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        source,
    )

    returned = _returned(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        source,
        experiment,
    )

    with pytest.raises(
        HveeContractError,
        match="does not match",
    ):
        advance_behavioral_engine_closed_loop_step(
            source_bundle=source,
            experiment_bundle=experiment,
            observation_return_bundle=returned,
            advance_native_state=(lambda _observation: _reduction_source()),
            next_target_sha256=_sha("7"),
        )


def test_advancer_must_append_exactly_one_observation():
    source = _adaptive_source()

    experiment = _experiment(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        source,
    )

    returned = _returned(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        source,
        experiment,
    )

    with pytest.raises(
        HveeContractError,
        match="did not produce a new state identity|append exactly one",
    ):
        advance_behavioral_engine_closed_loop_step(
            source_bundle=source,
            experiment_bundle=experiment,
            observation_return_bundle=returned,
            advance_native_state=(lambda _observation: source),
            next_target_sha256=_sha("7"),
        )


def test_tampered_observation_return_blocks_state_advancement():
    source = _adaptive_source()

    experiment = _experiment(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        source,
    )

    returned = _returned(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        source,
        experiment,
    )

    returned.payload["native_observation"]["scenario_sha256"] = _sha("9")

    with pytest.raises(
        HveeContractError,
        match="observation return failed verification",
    ):
        advance_behavioral_engine_closed_loop_step(
            source_bundle=source,
            experiment_bundle=experiment,
            observation_return_bundle=returned,
            advance_native_state=(
                lambda observation: _adaptive_source(observations=(observation,))
            ),
            next_target_sha256=_sha("7"),
        )


def test_next_experiment_binds_exact_advanced_source():
    source = _adaptive_source()

    experiment = _experiment(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        source,
    )

    returned = _returned(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        source,
        experiment,
    )

    step = advance_behavioral_engine_closed_loop_step(
        source_bundle=source,
        experiment_bundle=experiment,
        observation_return_bundle=returned,
        advance_native_state=(
            lambda observation: _adaptive_source(observations=(observation,))
        ),
        next_target_sha256=_sha("7"),
    )

    assert step.next_experiment is not None

    assert (
        step.next_experiment.payload["source"]["bundle_sha256"]
        == step.advanced_source_bundle.sha256
    )


def test_next_experiment_preserves_campaign_and_subject():
    source = _adaptive_source()

    experiment = _experiment(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        source,
    )

    returned = _returned(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        source,
        experiment,
    )

    step = advance_behavioral_engine_closed_loop_step(
        source_bundle=source,
        experiment_bundle=experiment,
        observation_return_bundle=returned,
        advance_native_state=(
            lambda observation: _adaptive_source(observations=(observation,))
        ),
        next_target_sha256=_sha("7"),
    )

    current_protocol = experiment.experiment_protocol.payload

    next_protocol = step.next_experiment.experiment_protocol.payload

    assert next_protocol["campaign"] == current_protocol["campaign"]

    assert next_protocol["subject_sha256"] == current_protocol["subject_sha256"]


def test_closed_loop_claim_boundary_remains_conservative():
    source = _adaptive_source()

    experiment = _experiment(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        source,
    )

    returned = _returned(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        source,
        experiment,
    )

    step = advance_behavioral_engine_closed_loop_step(
        source_bundle=source,
        experiment_bundle=experiment,
        observation_return_bundle=returned,
        advance_native_state=(
            lambda observation: _adaptive_source(observations=(observation,))
        ),
        next_target_sha256=_sha("7"),
    )

    boundary = step.payload["evidence_boundary"]

    assert boundary["native_state_advanced"] is True

    assert boundary["advanced_source_verified"] is True

    assert boundary["next_experiment_emitted"] is True

    assert boundary["next_target_binding_verified"] is False

    assert boundary["execution_evidence_verified"] is False

    assert boundary["behavioral_performance_qualified"] is False

    assert boundary["internal_engine_used"] is False


def test_repeated_adaptive_loop_reaches_observed_boundary():
    source0 = _adaptive_source()

    experiment0 = _experiment(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        source0,
        target_character="d",
    )

    returned0 = _returned(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        source0,
        experiment0,
        scenario_character="7",
        verdict=DecisionVerdict.PASS,
    )

    step0 = advance_behavioral_engine_closed_loop_step(
        source_bundle=source0,
        experiment_bundle=experiment0,
        observation_return_bundle=returned0,
        advance_native_state=(
            lambda observation: _adaptive_source(observations=(observation,))
        ),
        next_target_sha256=_sha("8"),
    )

    source1 = step0.advanced_source_bundle

    experiment1 = step0.next_experiment

    assert experiment1 is not None

    returned1 = _returned(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        source1,
        experiment1,
        scenario_character="8",
        verdict=DecisionVerdict.FAIL,
        counterexample_character="a",
    )

    first_observation = returned0.native_observation

    step1 = advance_behavioral_engine_closed_loop_step(
        source_bundle=source1,
        experiment_bundle=experiment1,
        observation_return_bundle=returned1,
        advance_native_state=(
            lambda observation: _adaptive_source(
                observations=(
                    first_observation,
                    observation,
                )
            )
        ),
        next_target_sha256=_sha("9"),
    )

    source2 = step1.advanced_source_bundle

    experiment2 = step1.next_experiment

    assert experiment2 is not None

    returned2 = _returned(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        source2,
        experiment2,
        scenario_character="9",
        verdict=DecisionVerdict.PASS,
    )

    second_observation = returned1.native_observation

    step2 = advance_behavioral_engine_closed_loop_step(
        source_bundle=source2,
        experiment_bundle=experiment2,
        observation_return_bundle=returned2,
        advance_native_state=(
            lambda observation: _adaptive_source(
                observations=(
                    first_observation,
                    second_observation,
                    observation,
                )
            )
        ),
        next_target_sha256=None,
    )

    final_source = step2.advanced_source_bundle

    assert final_source.payload["search"]["status"] == "boundary_bracketed"

    assert final_source.observed_boundary is not None

    assert step2.next_experiment is None

    assert step2.payload["state_transition"]["terminal"] is True


def test_closed_loop_step_is_deterministic():
    first_source = _adaptive_source()

    first_experiment = _experiment(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        first_source,
    )

    first_return = _returned(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        first_source,
        first_experiment,
    )

    first = advance_behavioral_engine_closed_loop_step(
        source_bundle=first_source,
        experiment_bundle=first_experiment,
        observation_return_bundle=first_return,
        advance_native_state=(
            lambda observation: _adaptive_source(observations=(observation,))
        ),
        next_target_sha256=_sha("7"),
    )

    second_source = _adaptive_source()

    second_experiment = _experiment(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        second_source,
    )

    second_return = _returned(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        second_source,
        second_experiment,
    )

    second = advance_behavioral_engine_closed_loop_step(
        source_bundle=second_source,
        experiment_bundle=second_experiment,
        observation_return_bundle=second_return,
        advance_native_state=(
            lambda observation: _adaptive_source(observations=(observation,))
        ),
        next_target_sha256=_sha("7"),
    )

    assert first.sha256 == second.sha256

    assert first.payload == second.payload


def test_closed_loop_verifier_rejects_tampering():
    source = _adaptive_source()

    experiment = _experiment(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        source,
    )

    returned = _returned(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        source,
        experiment,
    )

    step = advance_behavioral_engine_closed_loop_step(
        source_bundle=source,
        experiment_bundle=experiment,
        observation_return_bundle=returned,
        advance_native_state=(
            lambda observation: _adaptive_source(observations=(observation,))
        ),
        next_target_sha256=_sha("7"),
    )

    tampered = deepcopy(step.payload)

    tampered["state_transition"]["terminal"] = True

    recomputed = calculate_behavioral_engine_closed_loop_step_sha256(tampered)

    assert not (
        verify_behavioral_engine_closed_loop_step_bundle(
            payload=tampered,
            expected_sha256=recomputed,
            source_bundle=source,
            experiment_bundle=experiment,
            observation_return_bundle=returned,
            advanced_source_bundle=(step.advanced_source_bundle),
            next_experiment=(step.next_experiment),
        )
    )


def test_closed_loop_payload_contains_no_raw_content():
    source = _adaptive_source()

    experiment = _experiment(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        source,
    )

    returned = _returned(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        source,
        experiment,
    )

    step = advance_behavioral_engine_closed_loop_step(
        source_bundle=source,
        experiment_bundle=experiment,
        observation_return_bundle=returned,
        advance_native_state=(
            lambda observation: _adaptive_source(observations=(observation,))
        ),
        next_target_sha256=_sha("7"),
    )

    serialized = repr(step.payload)

    for forbidden in (
        "reference_text",
        "prediction_text",
        "raw_transcript_text",
        "audio_bytes",
        "prompt_text",
    ):
        assert forbidden not in serialized


def test_advancer_cannot_change_adaptive_configuration():
    source = _adaptive_source()

    experiment = _experiment(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        source,
    )

    returned = _returned(
        BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
        source,
        experiment,
    )

    def malicious_advance(
        observation: AdaptiveScenarioObservation,
    ):
        return build_adaptive_scenario_search_bundle(
            evaluation_type="asr",
            search_key=("hetren.loop.changed-search"),
            search_version="1.0.0",
            boundary_key="hetren.loop.boundary",
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
            observations=(observation,),
        )

    with pytest.raises(
        HveeContractError,
        match=("changed immutable native state " "configuration"),
    ):
        advance_behavioral_engine_closed_loop_step(
            source_bundle=source,
            experiment_bundle=experiment,
            observation_return_bundle=returned,
            advance_native_state=(malicious_advance),
            next_target_sha256=_sha("7"),
        )


def test_advancer_cannot_change_reduction_configuration():
    source = _reduction_source()

    experiment = _experiment(
        BehavioralEngineOperation.MINIMAL_COUNTEREXAMPLE_REDUCTION,
        source,
    )

    returned = _returned(
        BehavioralEngineOperation.MINIMAL_COUNTEREXAMPLE_REDUCTION,
        source,
        experiment,
    )

    def malicious_advance(
        observation: CounterexampleReductionObservation,
    ):
        return build_minimal_counterexample_reduction_bundle(
            evaluation_type="asr",
            reduction_key=("hetren.loop.changed-reduction"),
            reduction_version="1.0.0",
            source_scenario_sha256=_sha("a"),
            source_counterexample_evidence_sha256=(_sha("b")),
            units=_reduction_units(),
            maximum_observations=3,
            observations=(observation,),
        )

    with pytest.raises(
        HveeContractError,
        match=("changed immutable native state " "configuration"),
    ):
        advance_behavioral_engine_closed_loop_step(
            source_bundle=source,
            experiment_bundle=experiment,
            observation_return_bundle=returned,
            advance_native_state=(malicious_advance),
            next_target_sha256=_sha("7"),
        )


def test_advancer_cannot_change_neighborhood_configuration():
    source = _neighborhood_source()

    experiment = _experiment(
        BehavioralEngineOperation.NEIGHBORHOOD_GENERATION,
        source,
    )

    returned = _returned(
        BehavioralEngineOperation.NEIGHBORHOOD_GENERATION,
        source,
        experiment,
    )

    def malicious_advance(
        observation: NeighborhoodObservation,
    ):
        return build_neighborhood_generation_bundle(
            evaluation_type="asr",
            neighborhood_key=("hetren.loop.changed-neighborhood"),
            neighborhood_version="1.0.0",
            source_scenario_sha256=_sha("a"),
            source_counterexample_evidence_sha256=(_sha("b")),
            source_minimal_reduction_sha256=(_sha("c")),
            candidates=(_neighborhood_candidate(),),
            maximum_observations=1,
            observations=(observation,),
        )

    with pytest.raises(
        HveeContractError,
        match=("changed immutable native state " "configuration"),
    ):
        advance_behavioral_engine_closed_loop_step(
            source_bundle=source,
            experiment_bundle=experiment,
            observation_return_bundle=returned,
            advance_native_state=(malicious_advance),
            next_target_sha256=None,
        )

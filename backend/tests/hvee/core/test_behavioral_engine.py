from __future__ import annotations

from copy import deepcopy

import pytest

from hvee.core.adaptive_scenario_search import (
    AdaptiveScenarioSearchBundle,
    build_adaptive_scenario_search_bundle,
)
from hvee.core.behavioral_engine import (
    BehavioralEngineOperation,
    build_adaptive_search_experiment_bundle,
    build_behavioral_engine_experiment_bundle,
    build_minimal_reduction_experiment_bundle,
    build_neighborhood_experiment_bundle,
    calculate_behavioral_engine_experiment_sha256,
    verify_behavioral_engine_experiment_bundle,
)
from hvee.core.contracts import HveeContractError
from hvee.core.decision import DecisionVerdict
from hvee.core.experiment_protocol import (
    verify_experiment_protocol_bundle,
)
from hvee.core.minimal_counterexample_reduction import (
    CounterexampleReductionUnit,
    MinimalCounterexampleReductionBundle,
    build_minimal_counterexample_reduction_bundle,
)
from hvee.core.neighborhood_generation import (
    NeighborhoodCandidate,
    NeighborhoodGenerationBundle,
    NeighborhoodMutationDirection,
    NeighborhoodObservation,
    build_neighborhood_generation_bundle,
)


def _sha(
    character: str,
) -> str:
    return character * 64


def _adaptive_bundle() -> AdaptiveScenarioSearchBundle:
    return build_adaptive_scenario_search_bundle(
        evaluation_type="asr",
        search_key="hetren.test.adaptive-search",
        search_version="1.0.0",
        boundary_key="hetren.test.boundary",
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


def _reduction_bundle() -> MinimalCounterexampleReductionBundle:
    return build_minimal_counterexample_reduction_bundle(
        evaluation_type="asr",
        reduction_key=("hetren.test.minimal-reduction"),
        reduction_version="1.0.0",
        source_scenario_sha256=(_sha("a")),
        source_counterexample_evidence_sha256=(_sha("b")),
        units=(
            CounterexampleReductionUnit(
                key="segment-000",
                version="1.0.0",
                content_sha256=(_sha("c")),
            ),
            CounterexampleReductionUnit(
                key="segment-001",
                version="1.0.0",
                content_sha256=(_sha("d")),
            ),
        ),
        maximum_observations=3,
        observations=(),
    )


def _candidate() -> NeighborhoodCandidate:
    return NeighborhoodCandidate(
        key="noise-lower-01",
        version="1.0.0",
        dimension_key="noise.snr",
        generator_key=("hetren.test.neighborhood-generator"),
        generator_version="1.0.0",
        direction=(NeighborhoodMutationDirection.LOWER),
        ordinal_distance=1,
        specification_sha256=(_sha("e")),
    )


def _neighborhood_bundle() -> NeighborhoodGenerationBundle:
    return build_neighborhood_generation_bundle(
        evaluation_type="asr",
        neighborhood_key=("hetren.test.neighborhood"),
        neighborhood_version="1.0.0",
        source_scenario_sha256=(_sha("a")),
        source_counterexample_evidence_sha256=(_sha("b")),
        source_minimal_reduction_sha256=(_sha("c")),
        candidates=(_candidate(),),
        maximum_observations=1,
        observations=(),
    )


def _build_adaptive():
    source = _adaptive_bundle()

    adapter = build_adaptive_search_experiment_bundle(
        source_bundle=source,
        campaign_key=("behavioral-engine-test"),
        campaign_version="1.0.0",
        subject_sha256=_sha("f"),
        target_sha256=_sha("1"),
    )

    return (
        source,
        adapter,
    )


def test_adaptive_search_proposal_becomes_unified_experiment():
    source, adapter = _build_adaptive()

    protocol = adapter.experiment_protocol

    assert adapter.payload["operation"] == "adaptive_scenario_search"

    assert protocol.payload["definition"]["engine_kind"] == "behavioral"

    assert protocol.payload["definition"]["operation_key"] == "adaptive_scenario_search"

    assert (
        protocol.payload["proposals"][0]["parameters"]["native_proposal"]
        == source.payload["outcome"]["next_proposal"]
    )


def test_adaptive_adapter_preserves_native_reason():
    source, adapter = _build_adaptive()

    assert (
        adapter.experiment_protocol.payload["proposals"][0]["reason_code"]
        == source.payload["outcome"]["next_proposal"]["reason"]
    )


def test_adaptive_adapter_binds_exact_source_bundle():
    source, adapter = _build_adaptive()

    assert adapter.payload["source"]["bundle_sha256"] == source.sha256

    assert (
        adapter.experiment_protocol.payload["proposals"][0]["source_evidence_sha256"]
        == source.sha256
    )


def test_reduction_proposal_becomes_unified_experiment():
    source = _reduction_bundle()

    adapter = build_minimal_reduction_experiment_bundle(
        source_bundle=source,
        campaign_key=("behavioral-engine-test"),
        campaign_version="1.0.0",
        subject_sha256=_sha("f"),
        target_sha256=_sha("2"),
    )

    assert adapter.payload["operation"] == "minimal_counterexample_reduction"

    native = adapter.experiment_protocol.payload["proposals"][0]["parameters"][
        "native_proposal"
    ]

    assert native == source.payload["outcome"]["next_proposal"]

    assert native["removed_unit"]["index"] == 0


def test_neighborhood_proposal_becomes_unified_experiment():
    source = _neighborhood_bundle()

    adapter = build_neighborhood_experiment_bundle(
        source_bundle=source,
        campaign_key=("behavioral-engine-test"),
        campaign_version="1.0.0",
        subject_sha256=_sha("f"),
        target_sha256=_sha("3"),
    )

    assert adapter.payload["operation"] == "neighborhood_generation"

    native = adapter.experiment_protocol.payload["proposals"][0]["parameters"][
        "native_proposal"
    ]

    assert native == source.payload["outcome"]["next_proposal"]

    assert native["candidate"]["index"] == 0


@pytest.mark.parametrize(
    (
        "operation",
        "source_factory",
        "target_character",
    ),
    [
        (
            BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH,
            _adaptive_bundle,
            "1",
        ),
        (
            BehavioralEngineOperation.MINIMAL_COUNTEREXAMPLE_REDUCTION,
            _reduction_bundle,
            "2",
        ),
        (
            BehavioralEngineOperation.NEIGHBORHOOD_GENERATION,
            _neighborhood_bundle,
            "3",
        ),
    ],
)
def test_each_adapter_is_fully_reverifiable(
    operation,
    source_factory,
    target_character,
):
    source = source_factory()

    adapter = build_behavioral_engine_experiment_bundle(
        operation=operation,
        source_bundle=source,
        campaign_key=("behavioral-engine-test"),
        campaign_version="1.0.0",
        subject_sha256=_sha("f"),
        target_sha256=(_sha(target_character)),
    )

    assert verify_behavioral_engine_experiment_bundle(
        payload=adapter.payload,
        expected_sha256=(adapter.sha256),
        source_bundle=source,
    )

    assert verify_experiment_protocol_bundle(
        adapter.experiment_protocol.payload,
        adapter.experiment_protocol.sha256,
    )


def test_adapter_does_not_execute_experiment():
    _source, adapter = _build_adaptive()

    assert adapter.experiment_protocol.payload["observations"] == []

    assert (
        adapter.experiment_protocol.payload["evidence_boundary"][
            "experiment_execution_proven"
        ]
        is False
    )

    assert adapter.payload["evidence_boundary"]["experiment_executed"] is False


def test_adapter_never_claims_behavioral_qualification():
    _source, adapter = _build_adaptive()

    boundary = adapter.payload["evidence_boundary"]

    assert boundary["behavioral_performance_qualified"] is False

    assert boundary["production_qualified"] is False

    assert boundary["release_decision_issued"] is False


def test_adapter_explicitly_does_not_use_internal_engine():
    _source, adapter = _build_adaptive()

    assert adapter.payload["evidence_boundary"]["internal_engine_used"] is False


def test_existing_behavioral_algorithm_is_not_rewritten():
    _source, adapter = _build_adaptive()

    assert (
        adapter.payload["evidence_boundary"]["native_component_algorithm_modified"]
        is False
    )


def test_adapter_is_deterministic():
    first_source = _adaptive_bundle()
    second_source = _adaptive_bundle()

    first = build_adaptive_search_experiment_bundle(
        source_bundle=first_source,
        campaign_key="same-campaign",
        campaign_version="1.0.0",
        subject_sha256=_sha("f"),
        target_sha256=_sha("1"),
    )

    second = build_adaptive_search_experiment_bundle(
        source_bundle=second_source,
        campaign_key="same-campaign",
        campaign_version="1.0.0",
        subject_sha256=_sha("f"),
        target_sha256=_sha("1"),
    )

    assert first.sha256 == second.sha256

    assert first.payload == second.payload


def test_different_target_changes_adapter_identity():
    source = _adaptive_bundle()

    first = build_adaptive_search_experiment_bundle(
        source_bundle=source,
        campaign_key="same-campaign",
        campaign_version="1.0.0",
        subject_sha256=_sha("f"),
        target_sha256=_sha("1"),
    )

    second = build_adaptive_search_experiment_bundle(
        source_bundle=source,
        campaign_key="same-campaign",
        campaign_version="1.0.0",
        subject_sha256=_sha("f"),
        target_sha256=_sha("2"),
    )

    assert first.sha256 != second.sha256


def test_adapter_detaches_native_proposal_from_source_payload():
    source, adapter = _build_adaptive()

    original_reason = adapter.experiment_protocol.payload["proposals"][0]["parameters"][
        "native_proposal"
    ]["reason"]

    source.payload["outcome"]["next_proposal"]["reason"] = "tampered"

    assert (
        adapter.experiment_protocol.payload["proposals"][0]["parameters"][
            "native_proposal"
        ]["reason"]
        == original_reason
    )


def test_wrong_source_component_type_fails_closed():
    with pytest.raises(HveeContractError):
        build_behavioral_engine_experiment_bundle(
            operation=(BehavioralEngineOperation.ADAPTIVE_SCENARIO_SEARCH),
            source_bundle=(_reduction_bundle()),
            campaign_key="wrong-source",
            campaign_version="1.0.0",
            subject_sha256=_sha("f"),
            target_sha256=_sha("1"),
        )


def test_terminal_component_without_proposal_fails_closed():
    candidate = _candidate()

    terminal = build_neighborhood_generation_bundle(
        evaluation_type="asr",
        neighborhood_key=("hetren.test.neighborhood"),
        neighborhood_version="1.0.0",
        source_scenario_sha256=(_sha("a")),
        source_counterexample_evidence_sha256=(_sha("b")),
        source_minimal_reduction_sha256=(_sha("c")),
        candidates=(candidate,),
        maximum_observations=1,
        observations=(
            NeighborhoodObservation(
                sequence=1,
                candidate_index=0,
                scenario_sha256=(_sha("8")),
                verdict=(DecisionVerdict.PASS),
                result_provenance_sha256=(_sha("9")),
                observation_evidence_sha256=(_sha("a")),
                decision_evidence_sha256=(_sha("b")),
                counterexample_evidence_sha256=None,
            ),
        ),
    )

    assert terminal.payload["neighborhood"]["status"] == "complete"

    assert terminal.payload["outcome"]["next_proposal"] is None

    with pytest.raises(
        HveeContractError,
        match="has no next proposal",
    ):
        build_neighborhood_experiment_bundle(
            source_bundle=terminal,
            campaign_key="terminal-source",
            campaign_version="1.0.0",
            subject_sha256=_sha("f"),
            target_sha256=_sha("1"),
        )


def test_estimated_cost_cannot_exceed_experiment_budget():
    source = _adaptive_bundle()

    with pytest.raises(
        HveeContractError,
        match="proposed cost exceeds",
    ):
        build_adaptive_search_experiment_bundle(
            source_bundle=source,
            campaign_key="budget-check",
            campaign_version="1.0.0",
            subject_sha256=_sha("f"),
            target_sha256=_sha("1"),
            estimated_cost_units=2,
            maximum_cost_units=1,
        )


def test_verifier_rejects_source_bundle_tampering():
    source, adapter = _build_adaptive()

    source.payload["outcome"]["next_proposal"]["reason"] = "tampered"

    assert not (
        verify_behavioral_engine_experiment_bundle(
            payload=adapter.payload,
            expected_sha256=(adapter.sha256),
            source_bundle=source,
        )
    )


def test_verifier_rejects_native_proposal_binding_tampering():
    source, adapter = _build_adaptive()

    payload = deepcopy(adapter.payload)

    payload["source"]["native_proposal_sha256"] = _sha("9")

    recomputed = calculate_behavioral_engine_experiment_sha256(payload)

    assert not (
        verify_behavioral_engine_experiment_bundle(
            payload=payload,
            expected_sha256=recomputed,
            source_bundle=source,
        )
    )


def test_verifier_rejects_nested_protocol_tampering():
    source, adapter = _build_adaptive()

    payload = deepcopy(adapter.payload)

    payload["experiment_protocol"]["campaign"]["version"] = "2.0.0"

    recomputed = calculate_behavioral_engine_experiment_sha256(payload)

    assert not (
        verify_behavioral_engine_experiment_bundle(
            payload=payload,
            expected_sha256=recomputed,
            source_bundle=source,
        )
    )


def test_verifier_rejects_extra_fields():
    source, adapter = _build_adaptive()

    payload = deepcopy(adapter.payload)

    payload["unexpected"] = True

    recomputed = calculate_behavioral_engine_experiment_sha256(payload)

    assert not (
        verify_behavioral_engine_experiment_bundle(
            payload=payload,
            expected_sha256=recomputed,
            source_bundle=source,
        )
    )


def test_adapter_payload_contains_no_raw_content():
    _source, adapter = _build_adaptive()

    serialized = repr(adapter.payload)

    for forbidden in (
        "reference_text",
        "prediction_text",
        "raw_transcript_text",
        "audio_bytes",
        "prompt_text",
    ):
        assert forbidden not in serialized

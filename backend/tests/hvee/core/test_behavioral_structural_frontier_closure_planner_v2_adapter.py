from __future__ import annotations

from copy import deepcopy
import hashlib

import pytest

from hvee.core.behavioral_structural_frontier_closure_planner_v2 import (
    PLANNER_KEY,
    PLANNER_VERSION,
    StructuralPlannerVariant,
    build_behavioral_structural_frontier_closure_decision,
    calculate_behavioral_structural_frontier_closure_decision_sha256,
)
from hvee.core.behavioral_structural_frontier_closure_planner_v2_adapter import (
    ADAPTER_KEY,
    ADAPTER_VERSION,
    BehavioralStructuralFrontierClosurePlannerV2AdapterStatus,
    build_behavioral_structural_frontier_closure_planner_v2_adapter_bundle,
    verify_behavioral_structural_frontier_closure_planner_v2_adapter_bundle,
)
from hvee.core.contracts import HveeContractError
from hvee.core.decision import DecisionVerdict
from hvee.core.experiment_protocol import (
    verify_experiment_protocol_bundle,
)
from hvee.core.failure_family_investigator import (
    FailureFamilyObservation,
    FailureFamilyObservationSource,
)


def _sha(
    text: str,
) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


CANDIDATES = tuple(float(index) for index in range(7))

TARGETS = tuple(_sha(f"v2-adapter-target-{index}") for index in range(len(CANDIDATES)))

SUBJECT_SHA256 = _sha("v2-adapter-subject")


def _build(
    *,
    variant: StructuralPlannerVariant,
    observations=(),
    maximum_evaluations: int = 7,
    candidates=CANDIDATES,
    targets=TARGETS,
):
    return build_behavioral_structural_frontier_closure_planner_v2_adapter_bundle(
        campaign_key=("hetren.v2.adapter.test"),
        campaign_version=("1.0.0"),
        subject_sha256=(SUBJECT_SHA256),
        axis_key=("synthetic.index"),
        axis_version=("1.0.0"),
        axis_unit=("index"),
        candidate_values=(candidates),
        candidate_target_sha256s=(targets),
        maximum_evaluations=(maximum_evaluations),
        observations=(observations),
        variant=(variant),
    )


def _observation(
    *,
    sequence: int,
    candidate_index: int,
    verdict: DecisionVerdict,
    targets=TARGETS,
    scenario_sha256: str | None = None,
) -> FailureFamilyObservation:
    if scenario_sha256 is None:
        scenario_sha256 = targets[candidate_index]

    return FailureFamilyObservation(
        sequence=(sequence),
        candidate_index=(candidate_index),
        verdict=(verdict),
        source=(FailureFamilyObservationSource.EVALUATION),
        cost_units=1,
        scenario_sha256=(scenario_sha256),
        result_provenance_sha256=(
            _sha(f"result-{sequence}-{candidate_index}-{verdict}")
        ),
        observation_evidence_sha256=(
            _sha(f"observation-{sequence}-{candidate_index}-{verdict}")
        ),
        decision_evidence_sha256=(
            _sha(f"decision-{sequence}-{candidate_index}-{verdict}")
        ),
        counterexample_evidence_sha256=(
            _sha(f"counterexample-{sequence}-{candidate_index}")
            if verdict is DecisionVerdict.FAIL
            else None
        ),
    )


def _trajectory(
    *,
    variant: StructuralPlannerVariant,
    verdicts: tuple[
        DecisionVerdict,
        ...,
    ],
    maximum_evaluations: int = 7,
):
    observations = []

    for verdict in verdicts:
        bundle = _build(
            variant=(variant),
            observations=tuple(observations),
            maximum_evaluations=(maximum_evaluations),
        )

        assert bundle.experiment_protocol is not None

        candidate_index = bundle.payload["planner_decision"]["selected_candidate_index"]

        assert isinstance(
            candidate_index,
            int,
        )

        observations.append(
            _observation(
                sequence=(len(observations) + 1),
                candidate_index=(candidate_index),
                verdict=(verdict),
            )
        )

    return tuple(observations)


@pytest.mark.parametrize(
    "variant",
    tuple(StructuralPlannerVariant),
)
def test_bootstrap_ready_preserves_variant_and_unified_protocol(
    variant,
):
    bundle = _build(variant=(variant))

    assert (
        bundle.payload["adapter"]["status"]
        == BehavioralStructuralFrontierClosurePlannerV2AdapterStatus.READY.value
    )

    assert bundle.payload["adapter"]["variant"] == variant.value

    assert bundle.payload["planner"] == {
        "key": (PLANNER_KEY),
        "version": (PLANNER_VERSION),
        "variant": (variant.value),
    }

    protocol = bundle.experiment_protocol

    assert protocol is not None

    assert (
        verify_experiment_protocol_bundle(
            protocol.payload,
            protocol.sha256,
        )
        is True
    )

    proposal = protocol.payload["proposals"][0]

    selected = bundle.payload["planner_decision"]["selected_candidate_index"]

    assert proposal["target_sha256"] == TARGETS[selected]

    assert proposal["parameters"]["variant"] == variant.value

    assert (
        proposal["parameters"]["planner_decision_sha256"]
        == bundle.payload["planner_decision_sha256"]
    )

    assert (
        verify_behavioral_structural_frontier_closure_planner_v2_adapter_bundle(
            payload=(bundle.payload),
            expected_sha256=(bundle.sha256),
        )
        is True
    )


@pytest.mark.parametrize(
    "variant",
    tuple(StructuralPlannerVariant),
)
def test_exact_observable_history_replays_for_each_variant(
    variant,
):
    observations = _trajectory(
        variant=(variant),
        verdicts=(
            DecisionVerdict.PASS,
            DecisionVerdict.FAIL,
            DecisionVerdict.FAIL,
            DecisionVerdict.PASS,
        ),
    )

    bundle = _build(
        variant=(variant),
        observations=(observations),
    )

    assert bundle.payload["budget"]["evaluated_count"] == 4

    assert (
        verify_behavioral_structural_frontier_closure_planner_v2_adapter_bundle(
            payload=(bundle.payload),
            expected_sha256=(bundle.sha256),
        )
        is True
    )


@pytest.mark.parametrize(
    "variant",
    tuple(StructuralPlannerVariant),
)
def test_planner_decision_sha_is_native_v2_planner_sha(
    variant,
):
    observations = _trajectory(
        variant=(variant),
        verdicts=(
            DecisionVerdict.FAIL,
            DecisionVerdict.PASS,
            DecisionVerdict.FAIL,
        ),
    )

    bundle = _build(
        variant=(variant),
        observations=(observations),
    )

    decision = build_behavioral_structural_frontier_closure_decision(
        candidate_count=(len(CANDIDATES)),
        observations={item.candidate_index: (item.verdict) for item in observations},
        variant=(variant),
    )

    assert bundle.payload[
        "planner_decision_sha256"
    ] == calculate_behavioral_structural_frontier_closure_decision_sha256(decision)


def test_budget_exhausted_has_no_protocol():
    variant = StructuralPlannerVariant.V2A_BALANCED_FRONTIER_CLOSURE

    observations = _trajectory(
        variant=(variant),
        verdicts=(
            DecisionVerdict.PASS,
            DecisionVerdict.FAIL,
        ),
        maximum_evaluations=2,
    )

    bundle = _build(
        variant=(variant),
        observations=(observations),
        maximum_evaluations=2,
    )

    assert (
        bundle.payload["adapter"]["status"]
        == BehavioralStructuralFrontierClosurePlannerV2AdapterStatus.BUDGET_EXHAUSTED.value
    )

    assert bundle.experiment_protocol is None

    assert bundle.payload["execution_envelope"]["experiment_protocol"] is None


def test_grid_exhausted_precedes_budget_exhausted():
    variant = StructuralPlannerVariant.V2B_CLOSURE_WITH_COVERAGE_FLOOR

    observations = _trajectory(
        variant=(variant),
        verdicts=(
            DecisionVerdict.PASS,
            DecisionVerdict.FAIL,
            DecisionVerdict.PASS,
            DecisionVerdict.FAIL,
            DecisionVerdict.PASS,
            DecisionVerdict.FAIL,
            DecisionVerdict.PASS,
        ),
        maximum_evaluations=7,
    )

    bundle = _build(
        variant=(variant),
        observations=(observations),
        maximum_evaluations=7,
    )

    assert (
        bundle.payload["adapter"]["status"]
        == BehavioralStructuralFrontierClosurePlannerV2AdapterStatus.GRID_EXHAUSTED.value
    )

    assert bundle.experiment_protocol is None


def test_rejects_incident_anchor():
    anchor = FailureFamilyObservation(
        sequence=0,
        candidate_index=3,
        verdict=(DecisionVerdict.FAIL),
        source=(FailureFamilyObservationSource.INCIDENT_ANCHOR),
        cost_units=0,
        scenario_sha256=(TARGETS[3]),
        result_provenance_sha256=(_sha("anchor-result")),
        observation_evidence_sha256=(_sha("anchor-observation")),
        decision_evidence_sha256=(_sha("anchor-decision")),
        counterexample_evidence_sha256=(_sha("anchor-counterexample")),
    )

    with pytest.raises(
        HveeContractError,
    ):
        _build(
            variant=(StructuralPlannerVariant.V2A_BALANCED_FRONTIER_CLOSURE),
            observations=(anchor,),
        )


def test_rejects_observation_outside_exact_v2_trajectory():
    variant = StructuralPlannerVariant.V2A_BALANCED_FRONTIER_CLOSURE

    bootstrap = _build(variant=(variant))

    selected = bootstrap.payload["planner_decision"]["selected_candidate_index"]

    wrong = (selected + 1) % len(CANDIDATES)

    observation = _observation(
        sequence=1,
        candidate_index=(wrong),
        verdict=(DecisionVerdict.PASS),
    )

    with pytest.raises(
        HveeContractError,
        match=("deterministic planner trajectory"),
    ):
        _build(
            variant=(variant),
            observations=(observation,),
        )


def test_rejects_noncontiguous_evaluation_sequence():
    variant = StructuralPlannerVariant.V2A_BALANCED_FRONTIER_CLOSURE

    bundle = _build(variant=(variant))

    selected = bundle.payload["planner_decision"]["selected_candidate_index"]

    observation = _observation(
        sequence=2,
        candidate_index=(selected),
        verdict=(DecisionVerdict.PASS),
    )

    with pytest.raises(
        HveeContractError,
    ):
        _build(
            variant=(variant),
            observations=(observation,),
        )


def test_rejects_duplicate_candidate_target_hashes():
    targets = list(TARGETS)

    targets[1] = targets[0]

    with pytest.raises(
        HveeContractError,
    ):
        _build(
            variant=(StructuralPlannerVariant.V2A_BALANCED_FRONTIER_CLOSURE),
            targets=(targets),
        )


def test_rejects_observation_scenario_target_mismatch():
    variant = StructuralPlannerVariant.V2A_BALANCED_FRONTIER_CLOSURE

    bundle = _build(variant=(variant))

    selected = bundle.payload["planner_decision"]["selected_candidate_index"]

    observation = _observation(
        sequence=1,
        candidate_index=(selected),
        verdict=(DecisionVerdict.PASS),
        scenario_sha256=(_sha("wrong-target")),
    )

    with pytest.raises(
        HveeContractError,
    ):
        _build(
            variant=(variant),
            observations=(observation,),
        )


def test_rejects_raw_string_verdict():
    variant = StructuralPlannerVariant.V2A_BALANCED_FRONTIER_CLOSURE

    bootstrap = _build(variant=(variant))

    selected = bootstrap.payload["planner_decision"]["selected_candidate_index"]

    observation = FailureFamilyObservation(
        sequence=1,
        candidate_index=(selected),
        verdict="pass",
        source=(FailureFamilyObservationSource.EVALUATION),
        cost_units=1,
        scenario_sha256=(TARGETS[selected]),
        result_provenance_sha256=(_sha("raw-result")),
        observation_evidence_sha256=(_sha("raw-observation")),
        decision_evidence_sha256=(_sha("raw-decision")),
        counterexample_evidence_sha256=None,
    )

    with pytest.raises(
        HveeContractError,
    ):
        _build(
            variant=(variant),
            observations=(observation,),
        )


def test_rejects_observation_count_beyond_budget():
    variant = StructuralPlannerVariant.V2C_FAILURE_FRONTIER_STRUCTURAL

    first_two = list(
        _trajectory(
            variant=(variant),
            verdicts=(
                DecisionVerdict.FAIL,
                DecisionVerdict.PASS,
            ),
            maximum_evaluations=2,
        )
    )

    direct_decision = build_behavioral_structural_frontier_closure_decision(
        candidate_count=(len(CANDIDATES)),
        observations={item.candidate_index: (item.verdict) for item in first_two},
        variant=(variant),
    )

    assert direct_decision.selected_candidate_index is not None

    first_two.append(
        _observation(
            sequence=3,
            candidate_index=(direct_decision.selected_candidate_index),
            verdict=(DecisionVerdict.FAIL),
        )
    )

    with pytest.raises(
        HveeContractError,
    ):
        _build(
            variant=(variant),
            observations=tuple(first_two),
            maximum_evaluations=2,
        )


def test_input_container_invariance():
    variant = StructuralPlannerVariant.V2B_CLOSURE_WITH_COVERAGE_FLOOR

    observations = _trajectory(
        variant=(variant),
        verdicts=(
            DecisionVerdict.PASS,
            DecisionVerdict.FAIL,
            DecisionVerdict.PASS,
        ),
    )

    tuple_bundle = _build(
        variant=(variant),
        observations=(observations),
        candidates=(CANDIDATES),
        targets=(TARGETS),
    )

    list_bundle = _build(
        variant=(variant),
        observations=list(observations),
        candidates=list(CANDIDATES),
        targets=list(TARGETS),
    )

    assert tuple_bundle.payload == list_bundle.payload

    assert tuple_bundle.sha256 == list_bundle.sha256


def test_rebuild_is_deterministic():
    variant = StructuralPlannerVariant.V2C_FAILURE_FRONTIER_STRUCTURAL

    observations = _trajectory(
        variant=(variant),
        verdicts=(
            DecisionVerdict.FAIL,
            DecisionVerdict.FAIL,
            DecisionVerdict.PASS,
        ),
    )

    first = _build(
        variant=(variant),
        observations=(observations),
    )

    second = _build(
        variant=(variant),
        observations=(observations),
    )

    assert first.payload == second.payload

    assert first.sha256 == second.sha256


def _ready_bundle_for_tamper():
    variant = StructuralPlannerVariant.V2A_BALANCED_FRONTIER_CLOSURE

    observations = _trajectory(
        variant=(variant),
        verdicts=(
            DecisionVerdict.PASS,
            DecisionVerdict.FAIL,
        ),
    )

    return _build(
        variant=(variant),
        observations=(observations),
    )


def test_verifier_rejects_planner_decision_tamper():
    bundle = _ready_bundle_for_tamper()

    payload = deepcopy(bundle.payload)

    payload["planner_decision"]["selection_phase"] = "TAMPERED"

    assert (
        verify_behavioral_structural_frontier_closure_planner_v2_adapter_bundle(
            payload=(payload),
            expected_sha256=(bundle.sha256),
        )
        is False
    )


def test_verifier_rejects_candidate_target_binding_tamper():
    bundle = _ready_bundle_for_tamper()

    payload = deepcopy(bundle.payload)

    payload["axis"]["candidate_target_sha256s"][0] = _sha("tampered-target")

    assert (
        verify_behavioral_structural_frontier_closure_planner_v2_adapter_bundle(
            payload=(payload),
            expected_sha256=(bundle.sha256),
        )
        is False
    )


def test_verifier_rejects_variant_tamper():
    bundle = _ready_bundle_for_tamper()

    payload = deepcopy(bundle.payload)

    payload["adapter"][
        "variant"
    ] = StructuralPlannerVariant.V2C_FAILURE_FRONTIER_STRUCTURAL.value

    assert (
        verify_behavioral_structural_frontier_closure_planner_v2_adapter_bundle(
            payload=(payload),
            expected_sha256=(bundle.sha256),
        )
        is False
    )


def test_verifier_rejects_nested_protocol_tamper():
    bundle = _ready_bundle_for_tamper()

    payload = deepcopy(bundle.payload)

    payload["execution_envelope"]["experiment_protocol"]["proposals"][0][
        "reason_code"
    ] = "TAMPERED"

    assert (
        verify_behavioral_structural_frontier_closure_planner_v2_adapter_bundle(
            payload=(payload),
            expected_sha256=(bundle.sha256),
        )
        is False
    )


def test_verifier_rejects_unknown_top_level_field():
    bundle = _ready_bundle_for_tamper()

    payload = deepcopy(bundle.payload)

    payload["unexpected"] = True

    assert (
        verify_behavioral_structural_frontier_closure_planner_v2_adapter_bundle(
            payload=(payload),
            expected_sha256=(bundle.sha256),
        )
        is False
    )


def test_adapter_identity_and_evidence_boundary_are_explicit():
    bundle = _build(variant=(StructuralPlannerVariant.V2A_BALANCED_FRONTIER_CLOSURE))

    assert bundle.payload["adapter"]["key"] == ADAPTER_KEY

    assert bundle.payload["adapter"]["version"] == ADAPTER_VERSION

    assert bundle.payload["evidence_boundary"] == {
        "planner_mathematics_modified": (False),
        "experiment_protocol_modified": (False),
        "behavioral_engine_modified": (False),
        "planner_performance_evaluated": (False),
        "raw_content_persisted": (False),
        "proposal_suppressed_by_budget": (False),
        "grid_exhausted": (False),
        "variant_locked": (True),
    }

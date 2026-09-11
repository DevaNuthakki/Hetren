from __future__ import annotations

from copy import deepcopy
import hashlib

import pytest

from hvee.core.behavioral_multi_objective_planner_adapter import (
    BehavioralMultiObjectivePlannerAdapterStatus,
    build_behavioral_multi_objective_planner_adapter_bundle,
    verify_behavioral_multi_objective_planner_adapter_bundle,
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
    *parts: object,
) -> str:
    return hashlib.sha256(
        "|".join(str(part) for part in parts).encode("utf-8")
    ).hexdigest()


def _targets(
    count: int,
) -> tuple[
    str,
    ...,
]:
    return tuple(
        _sha(
            "target",
            index,
        )
        for index in range(count)
    )


def _observation(
    *,
    sequence: int,
    candidate_index: int,
    verdict: DecisionVerdict,
    targets: tuple[
        str,
        ...,
    ],
) -> FailureFamilyObservation:
    return FailureFamilyObservation(
        sequence=sequence,
        candidate_index=(candidate_index),
        verdict=verdict,
        source=(FailureFamilyObservationSource.EVALUATION),
        cost_units=1,
        scenario_sha256=(targets[candidate_index]),
        result_provenance_sha256=(
            _sha(
                "result",
                sequence,
                candidate_index,
                verdict.value,
            )
        ),
        observation_evidence_sha256=(
            _sha(
                "observation",
                sequence,
                candidate_index,
                verdict.value,
            )
        ),
        decision_evidence_sha256=(
            _sha(
                "decision",
                sequence,
                candidate_index,
                verdict.value,
            )
        ),
        counterexample_evidence_sha256=(
            _sha(
                "counterexample",
                sequence,
                candidate_index,
            )
            if (verdict is DecisionVerdict.FAIL)
            else None
        ),
    )


def _build(
    *,
    candidate_values=(
        0,
        1,
        2,
        3,
        4,
    ),
    maximum_evaluations=5,
    observations=(),
    targets=None,
):
    candidate_values = tuple(candidate_values)

    if targets is None:
        targets = _targets(len(candidate_values))

    return build_behavioral_multi_objective_planner_adapter_bundle(
        campaign_key=("adapter_test"),
        campaign_version=("1.0.0"),
        subject_sha256=(_sha("subject")),
        axis_key=("synthetic_axis"),
        axis_version=("1.0.0"),
        axis_unit=None,
        candidate_values=(candidate_values),
        candidate_target_sha256s=(targets),
        maximum_evaluations=(maximum_evaluations),
        observations=(observations),
    )


def test_ready_bundle_embeds_complete_planner_decision_and_protocol():
    targets = _targets(5)

    observations = (
        _observation(
            sequence=1,
            candidate_index=0,
            verdict=(DecisionVerdict.PASS),
            targets=targets,
        ),
        _observation(
            sequence=2,
            candidate_index=4,
            verdict=(DecisionVerdict.FAIL),
            targets=targets,
        ),
    )

    bundle = _build(
        observations=(observations),
        targets=targets,
    )

    assert (
        bundle.payload["adapter"]["status"]
        == BehavioralMultiObjectivePlannerAdapterStatus.READY.value
    )

    assert bundle.experiment_protocol is not None

    decision = bundle.payload["planner_decision"]

    assert decision["selected_candidate_index"] == 2

    assert decision["selection_reason"] == "unique_structural_nondominated"

    assert isinstance(
        decision["candidate_records"],
        list,
    )

    protocol = bundle.experiment_protocol

    assert (
        verify_experiment_protocol_bundle(
            protocol.payload,
            protocol.sha256,
        )
        is True
    )

    proposal = protocol.payload["proposals"][0]

    assert proposal["target_sha256"] == targets[2]

    assert (
        proposal["source_evidence_sha256"] == bundle.payload["planner_decision_sha256"]
    )

    assert proposal["parameters"]["planner_decision"] == decision

    assert (
        proposal["parameters"]["planner_decision_sha256"]
        == bundle.payload["planner_decision_sha256"]
    )

    assert (
        verify_behavioral_multi_objective_planner_adapter_bundle(
            payload=(bundle.payload),
            expected_sha256=(bundle.sha256),
        )
        is True
    )


def test_bootstrap_ready_uses_center_candidate():
    bundle = _build()

    assert bundle.payload["adapter"]["status"] == "ready"

    assert bundle.payload["planner_decision"]["selected_candidate_index"] == 2

    assert (
        bundle.payload["planner_decision"]["selection_reason"]
        == "structural_center_bootstrap"
    )

    assert bundle.experiment_protocol is not None


def test_budget_exhausted_preserves_planner_decision_without_protocol():
    targets = _targets(5)

    observation = _observation(
        sequence=1,
        candidate_index=0,
        verdict=(DecisionVerdict.PASS),
        targets=targets,
    )

    bundle = _build(
        maximum_evaluations=1,
        observations=(observation,),
        targets=targets,
    )

    assert bundle.payload["adapter"]["status"] == "budget_exhausted"

    assert bundle.experiment_protocol is None

    assert bundle.payload["execution_envelope"] == {
        "experiment_protocol": None,
        "experiment_protocol_sha256": None,
    }

    assert bundle.payload["planner_decision"]["selected_candidate_index"] is not None

    assert bundle.payload["evidence_boundary"]["proposal_suppressed_by_budget"] is True

    assert (
        verify_behavioral_multi_objective_planner_adapter_bundle(
            payload=(bundle.payload),
            expected_sha256=(bundle.sha256),
        )
        is True
    )


def test_grid_exhausted_precedes_budget_exhausted():
    targets = _targets(2)

    observations = (
        _observation(
            sequence=1,
            candidate_index=0,
            verdict=(DecisionVerdict.PASS),
            targets=targets,
        ),
        _observation(
            sequence=2,
            candidate_index=1,
            verdict=(DecisionVerdict.FAIL),
            targets=targets,
        ),
    )

    bundle = _build(
        candidate_values=(
            0,
            1,
        ),
        maximum_evaluations=2,
        observations=(observations),
        targets=targets,
    )

    assert bundle.payload["adapter"]["status"] == "grid_exhausted"

    assert bundle.payload["planner_decision"]["selected_candidate_index"] is None

    assert bundle.experiment_protocol is None

    assert (
        verify_behavioral_multi_objective_planner_adapter_bundle(
            payload=(bundle.payload),
            expected_sha256=(bundle.sha256),
        )
        is True
    )


def test_rejects_incident_anchor():
    targets = _targets(5)

    anchor = FailureFamilyObservation(
        sequence=0,
        candidate_index=2,
        verdict=(DecisionVerdict.FAIL),
        source=(FailureFamilyObservationSource.INCIDENT_ANCHOR),
        cost_units=0,
        scenario_sha256=(targets[2]),
        result_provenance_sha256=(_sha("anchor-result")),
        observation_evidence_sha256=(_sha("anchor-observation")),
        decision_evidence_sha256=(_sha("anchor-decision")),
        counterexample_evidence_sha256=(_sha("anchor-counterexample")),
    )

    with pytest.raises(HveeContractError):
        _build(
            observations=(anchor,),
            targets=targets,
        )


def test_rejects_observation_scenario_target_mismatch():
    targets = _targets(5)

    observation = FailureFamilyObservation(
        sequence=1,
        candidate_index=0,
        verdict=(DecisionVerdict.PASS),
        source=(FailureFamilyObservationSource.EVALUATION),
        cost_units=1,
        scenario_sha256=(_sha("wrong-target")),
        result_provenance_sha256=(_sha("result")),
        observation_evidence_sha256=(_sha("observation")),
        decision_evidence_sha256=(_sha("decision")),
        counterexample_evidence_sha256=None,
    )

    with pytest.raises(HveeContractError):
        _build(
            observations=(observation,),
            targets=targets,
        )


def test_rejects_noncontiguous_evaluation_sequence():
    targets = _targets(5)

    observation = FailureFamilyObservation(
        sequence=2,
        candidate_index=0,
        verdict=(DecisionVerdict.PASS),
        source=(FailureFamilyObservationSource.EVALUATION),
        cost_units=1,
        scenario_sha256=(targets[0]),
        result_provenance_sha256=(_sha("result")),
        observation_evidence_sha256=(_sha("observation")),
        decision_evidence_sha256=(_sha("decision")),
        counterexample_evidence_sha256=None,
    )

    with pytest.raises(HveeContractError):
        _build(
            observations=(observation,),
            targets=targets,
        )


def test_rejects_duplicate_candidate_target_hashes():
    duplicate = _sha("duplicate")

    with pytest.raises(HveeContractError):
        _build(
            targets=(
                duplicate,
                duplicate,
                _sha("2"),
                _sha("3"),
                _sha("4"),
            )
        )


def test_rejects_observation_count_beyond_budget():
    targets = _targets(5)

    observations = (
        _observation(
            sequence=1,
            candidate_index=0,
            verdict=(DecisionVerdict.PASS),
            targets=targets,
        ),
        _observation(
            sequence=2,
            candidate_index=1,
            verdict=(DecisionVerdict.FAIL),
            targets=targets,
        ),
    )

    with pytest.raises(HveeContractError):
        _build(
            maximum_evaluations=1,
            observations=(observations),
            targets=targets,
        )


def test_rejects_raw_string_verdict_even_if_failure_family_dataclass_accepts_it():
    targets = _targets(5)

    observation = FailureFamilyObservation(
        sequence=1,
        candidate_index=0,
        verdict="pass",
        source=(FailureFamilyObservationSource.EVALUATION),
        cost_units=1,
        scenario_sha256=(targets[0]),
        result_provenance_sha256=(_sha("result")),
        observation_evidence_sha256=(_sha("observation")),
        decision_evidence_sha256=(_sha("decision")),
        counterexample_evidence_sha256=None,
    )

    with pytest.raises(HveeContractError):
        _build(
            observations=(observation,),
            targets=targets,
        )


def test_verifier_rejects_planner_decision_tamper():
    bundle = _build()

    payload = deepcopy(bundle.payload)

    payload["planner_decision"]["primary_frontier_candidate_indices"] = [999]

    assert (
        verify_behavioral_multi_objective_planner_adapter_bundle(
            payload=payload,
            expected_sha256=(bundle.sha256),
        )
        is False
    )


def test_verifier_rejects_candidate_target_binding_tamper():
    bundle = _build()

    payload = deepcopy(bundle.payload)

    selected = payload["planner_decision"]["selected_candidate_index"]

    payload["axis"]["candidate_target_sha256s"][selected] = _sha("tampered-target")

    assert (
        verify_behavioral_multi_objective_planner_adapter_bundle(
            payload=payload,
            expected_sha256=(bundle.sha256),
        )
        is False
    )


def test_verifier_rejects_nested_protocol_tamper():
    bundle = _build()

    payload = deepcopy(bundle.payload)

    payload["execution_envelope"]["experiment_protocol"]["proposals"][0][
        "reason_code"
    ] = "tampered"

    assert (
        verify_behavioral_multi_objective_planner_adapter_bundle(
            payload=payload,
            expected_sha256=(bundle.sha256),
        )
        is False
    )


def test_verifier_rejects_unknown_top_level_field():
    bundle = _build()

    payload = deepcopy(bundle.payload)

    payload["unexpected"] = True

    assert (
        verify_behavioral_multi_objective_planner_adapter_bundle(
            payload=payload,
            expected_sha256=(bundle.sha256),
        )
        is False
    )


def test_rebuild_is_deterministic():
    targets = _targets(5)

    observations = (
        _observation(
            sequence=1,
            candidate_index=0,
            verdict=(DecisionVerdict.PASS),
            targets=targets,
        ),
        _observation(
            sequence=2,
            candidate_index=4,
            verdict=(DecisionVerdict.FAIL),
            targets=targets,
        ),
    )

    first = _build(
        observations=(observations),
        targets=targets,
    )

    second = _build(
        observations=(observations),
        targets=targets,
    )

    assert first.payload == second.payload

    assert first.sha256 == second.sha256

    assert first.experiment_protocol == second.experiment_protocol

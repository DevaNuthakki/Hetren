from __future__ import annotations

from copy import deepcopy
import hashlib

import pytest

from hvee.core.contracts import HveeContractError
from hvee.core.decision import DecisionVerdict
from hvee.core.failure_family_investigator import (
    FailureFamilyObservation,
    FailureFamilyObservationSource,
    FailureFamilyProposalReason,
    FailureFamilySearchMode,
    FailureFamilySearchStatus,
    build_failure_family_boundary_set_bundle,
    build_failure_family_investigator_bundle,
    calculate_failure_family_investigator_sha256,
    verify_failure_family_boundary_set_bundle,
    verify_failure_family_investigator_bundle,
)
from hvee.core.observed_boundary import (
    verify_observed_boundary_bundle,
)


def _sha(
    *parts,
):
    return hashlib.sha256(
        "|".join(str(part) for part in parts).encode("utf-8")
    ).hexdigest()


def _observation(
    *,
    sequence,
    candidate_index,
    verdict,
    source=(FailureFamilyObservationSource.EVALUATION),
):
    return FailureFamilyObservation(
        sequence=sequence,
        candidate_index=(candidate_index),
        verdict=verdict,
        source=source,
        cost_units=(
            0 if source == FailureFamilyObservationSource.INCIDENT_ANCHOR else 1
        ),
        scenario_sha256=_sha(
            "scenario",
            source.value,
            sequence,
            candidate_index,
        ),
        result_provenance_sha256=_sha(
            "result",
            source.value,
            sequence,
            candidate_index,
        ),
        observation_evidence_sha256=_sha(
            "observation",
            source.value,
            sequence,
            candidate_index,
        ),
        decision_evidence_sha256=_sha(
            "decision",
            source.value,
            sequence,
            candidate_index,
        ),
        counterexample_evidence_sha256=(
            _sha(
                "counterexample",
                source.value,
                sequence,
                candidate_index,
            )
            if verdict == DecisionVerdict.FAIL
            else None
        ),
    )


def _build(
    *,
    mode=FailureFamilySearchMode.GLOBAL,
    candidate_count=9,
    maximum_evaluations=None,
    observations=(),
):
    if maximum_evaluations is None:
        maximum_evaluations = (
            candidate_count
            if mode == FailureFamilySearchMode.GLOBAL
            else candidate_count - 1
        )

    return build_failure_family_investigator_bundle(
        mode=mode,
        evaluation_type="synthetic",
        investigator_key=("hetren.failure.family"),
        investigator_version="1.0.0",
        boundary_key=("hetren.failure.family.boundary"),
        boundary_version="1.0.0",
        axis_key="synthetic.index",
        axis_version="1.0.0",
        axis_unit="index",
        candidate_values=tuple(float(index) for index in range(candidate_count)),
        invariant_parameters={
            "problem_class": ("synthetic"),
        },
        maximum_evaluations=(maximum_evaluations),
        observations=observations,
    )


def _run_global(
    pattern,
    *,
    budget=None,
):
    observations = []

    if budget is None:
        budget = len(pattern)

    while True:
        bundle = _build(
            candidate_count=len(pattern),
            maximum_evaluations=budget,
            observations=tuple(observations),
        )

        proposal = bundle.payload["outcome"]["next_proposal"]

        if proposal is None:
            return (
                bundle,
                tuple(observations),
            )

        candidate_index = proposal["candidate_index"]

        verdict = (
            DecisionVerdict.FAIL
            if pattern[candidate_index] == "F"
            else DecisionVerdict.PASS
        )

        observations.append(
            _observation(
                sequence=(len(observations) + 1),
                candidate_index=(candidate_index),
                verdict=verdict,
            )
        )


def _run_incident(
    pattern,
    incident_index,
    *,
    budget=None,
):
    if budget is None:
        budget = len(pattern) - 1

    observations = [
        _observation(
            sequence=0,
            candidate_index=(incident_index),
            verdict=(DecisionVerdict.FAIL),
            source=(FailureFamilyObservationSource.INCIDENT_ANCHOR),
        )
    ]

    while True:
        bundle = _build(
            mode=(FailureFamilySearchMode.INCIDENT_ANCHORED),
            candidate_count=len(pattern),
            maximum_evaluations=budget,
            observations=tuple(observations),
        )

        proposal = bundle.payload["outcome"]["next_proposal"]

        if proposal is None:
            return (
                bundle,
                tuple(observations),
            )

        candidate_index = proposal["candidate_index"]

        verdict = (
            DecisionVerdict.FAIL
            if pattern[candidate_index] == "F"
            else DecisionVerdict.PASS
        )

        evaluated_count = sum(
            item.source == FailureFamilyObservationSource.EVALUATION
            for item in observations
        )

        observations.append(
            _observation(
                sequence=(evaluated_count + 1),
                candidate_index=(candidate_index),
                verdict=verdict,
            )
        )


def test_global_search_starts_at_center():
    bundle = _build(
        candidate_count=9,
    )

    assert bundle.payload["outcome"]["next_proposal"] == {
        "candidate_index": 4,
        "axis_value": 4.0,
        "reason": "initial_center",
    }


def test_global_search_explores_farthest_unobserved():
    first = _observation(
        sequence=1,
        candidate_index=4,
        verdict=DecisionVerdict.PASS,
    )

    bundle = _build(
        candidate_count=9,
        observations=(first,),
    )

    assert bundle.payload["outcome"]["next_proposal"]["candidate_index"] == 0

    assert bundle.payload["outcome"]["next_proposal"]["reason"] == (
        FailureFamilyProposalReason.EXPLORE_FARTHEST_UNOBSERVED.value
    )


def test_opposing_interval_is_refined():
    observations = (
        _observation(
            sequence=1,
            candidate_index=4,
            verdict=DecisionVerdict.FAIL,
        ),
        _observation(
            sequence=2,
            candidate_index=0,
            verdict=DecisionVerdict.PASS,
        ),
    )

    bundle = _build(
        candidate_count=9,
        observations=observations,
    )

    assert bundle.payload["outcome"]["next_proposal"] == {
        "candidate_index": 2,
        "axis_value": 2.0,
        "reason": "refine_opposing_interval",
    }


def test_global_search_continues_after_first_boundary():
    bundle, observations = _run_global("PPFPPPFPP")

    assert (
        bundle.payload["investigator"]["status"]
        == FailureFamilySearchStatus.GRID_EXHAUSTED.value
    )

    assert len(observations) == 9

    assert bundle.payload["outcome"]["localized_boundary_count"] == 4


def test_multiple_boundaries_reuse_existing_boundary_bundle():
    bundle, _ = _run_global("PPFPPPFPP")

    assert len(bundle.boundary_set.boundaries) == 4

    for boundary in bundle.boundary_set.boundaries:
        assert verify_observed_boundary_bundle(
            payload=(boundary.payload),
            expected_sha256=(boundary.sha256),
        )


def test_two_disjoint_failure_regions_are_exact_after_full_grid():
    bundle, _ = _run_global("PPFPPPFPP")

    exact = bundle.boundary_set.payload["failure_regions"]["exactly_characterized"]

    assert [
        (
            item["lower_candidate_index"],
            item["upper_candidate_index"],
        )
        for item in exact
    ] == [
        (
            2,
            2,
        ),
        (
            6,
            6,
        ),
    ]


def test_internal_failure_island_has_two_boundaries():
    bundle, _ = _run_global("PPPFFFPPP")

    boundaries = bundle.boundary_set.payload["boundaries"]["ordered"]

    assert [
        (
            item["lower_candidate_index"],
            item["upper_candidate_index"],
        )
        for item in boundaries
    ] == [
        (
            2,
            3,
        ),
        (
            5,
            6,
        ),
    ]


def test_boundary_directions_can_alternate():
    bundle, _ = _run_global("PPPFFFPPP")

    directions = [
        item["direction"]
        for item in (bundle.boundary_set.payload["boundaries"]["ordered"])
    ]

    assert directions == [
        "pass_to_fail",
        "fail_to_pass",
    ]


def test_incident_anchor_has_zero_new_cost():
    anchor = _observation(
        sequence=0,
        candidate_index=4,
        verdict=DecisionVerdict.FAIL,
        source=(FailureFamilyObservationSource.INCIDENT_ANCHOR),
    )

    bundle = _build(
        mode=(FailureFamilySearchMode.INCIDENT_ANCHORED),
        candidate_count=9,
        observations=(anchor,),
    )

    assert bundle.payload["budget"]["evaluated_count"] == 0

    assert bundle.payload["budget"]["incident_anchor_cost_units"] == 0


def test_incident_search_expands_left_first():
    anchor = _observation(
        sequence=0,
        candidate_index=4,
        verdict=DecisionVerdict.FAIL,
        source=(FailureFamilyObservationSource.INCIDENT_ANCHOR),
    )

    bundle = _build(
        mode=(FailureFamilySearchMode.INCIDENT_ANCHORED),
        candidate_count=9,
        observations=(anchor,),
    )

    assert bundle.payload["outcome"]["next_proposal"] == {
        "candidate_index": 3,
        "axis_value": 3.0,
        "reason": "expand_incident_left",
    }


def test_incident_search_then_expands_right():
    anchor = _observation(
        sequence=0,
        candidate_index=4,
        verdict=DecisionVerdict.FAIL,
        source=(FailureFamilyObservationSource.INCIDENT_ANCHOR),
    )

    left = _observation(
        sequence=1,
        candidate_index=3,
        verdict=DecisionVerdict.FAIL,
    )

    bundle = _build(
        mode=(FailureFamilySearchMode.INCIDENT_ANCHORED),
        candidate_count=9,
        observations=(
            anchor,
            left,
        ),
    )

    assert bundle.payload["outcome"]["next_proposal"] == {
        "candidate_index": 5,
        "axis_value": 5.0,
        "reason": "expand_incident_right",
    }


def test_incident_exactly_characterizes_internal_region():
    bundle, observations = _run_incident(
        "PPPFFFPPP",
        4,
    )

    assert (
        bundle.payload["investigator"]["status"]
        == FailureFamilySearchStatus.INCIDENT_REGION_CHARACTERIZED.value
    )

    exact = bundle.boundary_set.payload["failure_regions"]["exactly_characterized"]

    assert len(exact) == 1

    assert exact[0]["lower_candidate_index"] == 3

    assert exact[0]["upper_candidate_index"] == 5

    evaluated_count = sum(
        item.source == FailureFamilyObservationSource.EVALUATION
        for item in observations
    )

    assert evaluated_count == 4


def test_single_point_incident_region_is_characterized():
    bundle, _ = _run_incident(
        "PPPPFPPPP",
        4,
    )

    exact = bundle.boundary_set.payload["failure_regions"]["exactly_characterized"]

    assert len(exact) == 1

    assert exact[0]["lower_candidate_index"] == 4

    assert exact[0]["upper_candidate_index"] == 4


def test_edge_incident_region_requires_only_applicable_boundary():
    bundle, _ = _run_incident(
        "FFFPPPPPP",
        1,
    )

    exact = bundle.boundary_set.payload["failure_regions"]["exactly_characterized"]

    assert len(exact) == 1

    region = exact[0]

    assert region["left_edge"] is True

    assert region["left_boundary_sha256"] is None

    assert region["right_boundary_sha256"] is not None


def test_incident_budget_exhaustion_is_preserved():
    bundle, _ = _run_incident(
        "PPPFFFPPP",
        4,
        budget=2,
    )

    assert (
        bundle.payload["investigator"]["status"]
        == FailureFamilySearchStatus.BUDGET_EXHAUSTED.value
    )


def test_global_budget_exhaustion_is_preserved():
    bundle, observations = _run_global(
        "PPFPPPFPP",
        budget=3,
    )

    assert (
        bundle.payload["investigator"]["status"]
        == FailureFamilySearchStatus.BUDGET_EXHAUSTED.value
    )

    assert len(observations) == 3


def test_boundary_set_is_reverifiable():
    bundle, _ = _run_global("PPPFFFPPP")

    assert verify_failure_family_boundary_set_bundle(
        payload=(bundle.boundary_set.payload),
        expected_sha256=(bundle.boundary_set.sha256),
    )


def test_investigator_is_reverifiable():
    bundle, _ = _run_global("PPFPPPFPP")

    assert verify_failure_family_investigator_bundle(
        payload=(bundle.payload),
        expected_sha256=(bundle.sha256),
    )


def test_investigator_is_deterministic():
    first, _ = _run_global("PPFFPPPFF")

    second, _ = _run_global("PPFFPPPFF")

    assert first.payload == second.payload

    assert first.sha256 == second.sha256


def test_recomputed_tampering_is_rejected():
    bundle, _ = _run_global("PPFPPPFPP")

    tampered = deepcopy(bundle.payload)

    tampered["evidence_boundary"]["behavioral_performance_qualified"] = True

    tampered_sha = calculate_failure_family_investigator_sha256(tampered)

    assert not (
        verify_failure_family_investigator_bundle(
            payload=tampered,
            expected_sha256=(tampered_sha),
        )
    )


def test_global_mode_rejects_incident_anchor():
    anchor = _observation(
        sequence=0,
        candidate_index=4,
        verdict=DecisionVerdict.FAIL,
        source=(FailureFamilyObservationSource.INCIDENT_ANCHOR),
    )

    with pytest.raises(
        HveeContractError,
        match=("cannot contain incident anchor"),
    ):
        _build(
            observations=(anchor,),
        )


def test_incident_mode_requires_anchor():
    with pytest.raises(
        HveeContractError,
        match=("requires one failing anchor"),
    ):
        _build(
            mode=(FailureFamilySearchMode.INCIDENT_ANCHORED),
            observations=(),
        )


def test_incident_anchor_must_fail():
    with pytest.raises(
        HveeContractError,
        match=("anchor must be failing"),
    ):
        _observation(
            sequence=0,
            candidate_index=4,
            verdict=DecisionVerdict.PASS,
            source=(FailureFamilyObservationSource.INCIDENT_ANCHOR),
        )


def test_failed_evaluation_requires_counterexample():
    with pytest.raises(
        HveeContractError,
        match=("counterexample evidence"),
    ):
        FailureFamilyObservation(
            sequence=1,
            candidate_index=4,
            verdict=DecisionVerdict.FAIL,
            source=(FailureFamilyObservationSource.EVALUATION),
            cost_units=1,
            scenario_sha256=_sha("scenario"),
            result_provenance_sha256=_sha("result"),
            observation_evidence_sha256=_sha("observation"),
            decision_evidence_sha256=_sha("decision"),
            counterexample_evidence_sha256=None,
        )


def test_passing_evaluation_rejects_counterexample():
    with pytest.raises(
        HveeContractError,
        match=("cannot reference counterexample"),
    ):
        FailureFamilyObservation(
            sequence=1,
            candidate_index=4,
            verdict=DecisionVerdict.PASS,
            source=(FailureFamilyObservationSource.EVALUATION),
            cost_units=1,
            scenario_sha256=_sha("scenario"),
            result_provenance_sha256=_sha("result"),
            observation_evidence_sha256=_sha("observation"),
            decision_evidence_sha256=_sha("decision"),
            counterexample_evidence_sha256=_sha("counterexample"),
        )


def test_duplicate_candidate_observations_fail_closed():
    observations = (
        _observation(
            sequence=1,
            candidate_index=4,
            verdict=DecisionVerdict.PASS,
        ),
        _observation(
            sequence=2,
            candidate_index=4,
            verdict=DecisionVerdict.FAIL,
        ),
    )

    with pytest.raises(
        HveeContractError,
        match=("distinct candidate indices"),
    ):
        build_failure_family_boundary_set_bundle(
            evaluation_type="synthetic",
            boundary_key="boundary",
            boundary_version="1.0.0",
            search_key="search",
            search_version="1.0.0",
            axis_key="axis",
            axis_version="1.0.0",
            axis_unit="index",
            candidate_values=tuple(float(index) for index in range(9)),
            invariant_parameters={},
            observations=observations,
        )


def test_wrong_proposal_trajectory_fails_closed():
    wrong = _observation(
        sequence=1,
        candidate_index=0,
        verdict=DecisionVerdict.PASS,
    )

    with pytest.raises(
        HveeContractError,
        match=("deterministic proposal trajectory"),
    ):
        _build(
            candidate_count=9,
            observations=(wrong,),
        )


def test_known_raw_content_invariant_is_rejected():
    with pytest.raises(
        HveeContractError,
        match=("forbidden raw-content key"),
    ):
        build_failure_family_investigator_bundle(
            mode=(FailureFamilySearchMode.GLOBAL),
            evaluation_type="synthetic",
            investigator_key="search",
            investigator_version="1.0.0",
            boundary_key="boundary",
            boundary_version="1.0.0",
            axis_key="axis",
            axis_version="1.0.0",
            axis_unit="index",
            candidate_values=(
                0.0,
                1.0,
                2.0,
            ),
            invariant_parameters={
                "raw_input": "secret",
            },
            maximum_evaluations=3,
            observations=(),
        )


def test_claim_boundary_remains_unqualified():
    bundle, _ = _run_global(
        "PPFPPPFPP",
        budget=4,
    )

    boundary = bundle.payload["evidence_boundary"]

    assert boundary["multi_boundary_state_supported"] is True

    assert boundary["behavioral_performance_qualified"] is False

    assert boundary["run05_execution_performed"] is False

    assert boundary["real_ai_generalization_established"] is False

    assert boundary["model_inference_performed"] is False

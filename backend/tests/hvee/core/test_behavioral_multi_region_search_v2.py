from __future__ import annotations

import hashlib

import pytest

from hvee.core.behavioral_multi_region_search_v2 import (
    BehavioralMultiRegionSearchV2ProposalReason,
    _guaranteed_boundary_closure_candidate,
    build_behavioral_multi_region_search_v2_bundle,
    verify_behavioral_multi_region_search_v2_bundle,
)
from hvee.core.contracts import HveeContractError
from hvee.core.decision import DecisionVerdict
from hvee.core.failure_family_investigator import (
    FailureFamilyObservation,
    FailureFamilyObservationSource,
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
):
    return FailureFamilyObservation(
        sequence=sequence,
        candidate_index=(candidate_index),
        verdict=verdict,
        source=(FailureFamilyObservationSource.EVALUATION),
        cost_units=1,
        scenario_sha256=_sha(
            "scenario",
            sequence,
            candidate_index,
        ),
        result_provenance_sha256=_sha(
            "result",
            sequence,
            candidate_index,
        ),
        observation_evidence_sha256=_sha(
            "observation",
            sequence,
            candidate_index,
        ),
        decision_evidence_sha256=_sha(
            "decision",
            sequence,
            candidate_index,
        ),
        counterexample_evidence_sha256=(
            _sha(
                "counterexample",
                sequence,
                candidate_index,
            )
            if verdict == DecisionVerdict.FAIL
            else None
        ),
    )


def _bundle(
    *,
    candidate_count=9,
    maximum_evaluations=9,
    observations=(),
):
    return build_behavioral_multi_region_search_v2_bundle(
        evaluation_type="synthetic",
        search_key=("hetren.behavioral.multi-region.v2"),
        search_version="1.0.0",
        boundary_key=("hetren.behavioral.multi-region.v2.boundary"),
        boundary_version="1.0.0",
        axis_key="synthetic.index",
        axis_version="1.0.0",
        axis_unit="index",
        candidate_values=tuple(float(index) for index in range(candidate_count)),
        invariant_parameters={
            "test": ("behavioral_multi_region_v2"),
        },
        maximum_evaluations=(maximum_evaluations),
        observations=(observations),
    )


def test_initial_proposal_is_center():
    bundle = _bundle()

    proposal = bundle.payload["outcome"]["next_proposal"]

    assert proposal["candidate_index"] == 4

    assert (
        proposal["reason"]
        == BehavioralMultiRegionSearchV2ProposalReason.INITIAL_CENTER.value
    )


def test_after_center_uses_maximin_coverage():
    observations = (
        _observation(
            sequence=1,
            candidate_index=4,
            verdict=(DecisionVerdict.PASS),
        ),
    )

    bundle = _bundle(observations=observations)

    proposal = bundle.payload["outcome"]["next_proposal"]

    assert proposal["candidate_index"] == 0

    assert (
        proposal["reason"]
        == BehavioralMultiRegionSearchV2ProposalReason.EXPLORE_FARTHEST_UNOBSERVED.value
    )


def test_maximin_tie_breaks_lowest_index():
    observations = (
        _observation(
            sequence=1,
            candidate_index=4,
            verdict=(DecisionVerdict.PASS),
        ),
        _observation(
            sequence=2,
            candidate_index=0,
            verdict=(DecisionVerdict.PASS),
        ),
    )

    bundle = _bundle(observations=observations)

    proposal = bundle.payload["outcome"]["next_proposal"]

    assert proposal["candidate_index"] == 8


def test_wide_opposing_interval_does_not_override_coverage():
    observations = (
        _observation(
            sequence=1,
            candidate_index=4,
            verdict=(DecisionVerdict.PASS),
        ),
        _observation(
            sequence=2,
            candidate_index=0,
            verdict=(DecisionVerdict.FAIL),
        ),
    )

    bundle = _bundle(observations=observations)

    proposal = bundle.payload["outcome"]["next_proposal"]

    assert proposal["candidate_index"] == 8

    assert (
        proposal["reason"]
        == BehavioralMultiRegionSearchV2ProposalReason.EXPLORE_FARTHEST_UNOBSERVED.value
    )


def test_one_step_opposing_interval_gets_closure_priority():
    observations = (
        _observation(
            sequence=1,
            candidate_index=4,
            verdict=(DecisionVerdict.PASS),
        ),
        _observation(
            sequence=2,
            candidate_index=0,
            verdict=(DecisionVerdict.PASS),
        ),
        _observation(
            sequence=3,
            candidate_index=8,
            verdict=(DecisionVerdict.PASS),
        ),
        _observation(
            sequence=4,
            candidate_index=2,
            verdict=(DecisionVerdict.FAIL),
        ),
    )

    bundle = _bundle(observations=observations)

    proposal = bundle.payload["outcome"]["next_proposal"]

    assert proposal["candidate_index"] == 1

    assert (
        proposal["reason"]
        == BehavioralMultiRegionSearchV2ProposalReason.GUARANTEED_BOUNDARY_CLOSURE.value
    )


def test_multiple_closure_candidates_choose_lowest_index():
    observations = (
        _observation(
            sequence=1,
            candidate_index=4,
            verdict=(DecisionVerdict.PASS),
        ),
        _observation(
            sequence=2,
            candidate_index=0,
            verdict=(DecisionVerdict.PASS),
        ),
        _observation(
            sequence=3,
            candidate_index=8,
            verdict=(DecisionVerdict.PASS),
        ),
        _observation(
            sequence=4,
            candidate_index=2,
            verdict=(DecisionVerdict.FAIL),
        ),
        _observation(
            sequence=5,
            candidate_index=6,
            verdict=(DecisionVerdict.FAIL),
        ),
    )

    candidate = _guaranteed_boundary_closure_candidate(observations=observations)

    assert candidate == 1


def test_deterministic_trajectory_validation_rejects_wrong_candidate():
    observations = (
        _observation(
            sequence=1,
            candidate_index=4,
            verdict=(DecisionVerdict.PASS),
        ),
        _observation(
            sequence=2,
            candidate_index=8,
            verdict=(DecisionVerdict.PASS),
        ),
    )

    with pytest.raises(
        HveeContractError,
        match=("deterministic"),
    ):
        _bundle(observations=observations)


def test_duplicate_candidate_rejected():
    observations = (
        _observation(
            sequence=1,
            candidate_index=4,
            verdict=(DecisionVerdict.PASS),
        ),
        _observation(
            sequence=2,
            candidate_index=4,
            verdict=(DecisionVerdict.PASS),
        ),
    )

    with pytest.raises(
        HveeContractError,
        match="repeat",
    ):
        _bundle(observations=observations)


def test_incident_anchor_is_rejected_from_v2_global_search():
    observation = FailureFamilyObservation(
        sequence=0,
        candidate_index=4,
        verdict=(DecisionVerdict.FAIL),
        source=(FailureFamilyObservationSource.INCIDENT_ANCHOR),
        cost_units=0,
        scenario_sha256=_sha("scenario"),
        result_provenance_sha256=_sha("result"),
        observation_evidence_sha256=_sha("observation"),
        decision_evidence_sha256=_sha("decision"),
        counterexample_evidence_sha256=_sha("counterexample"),
    )

    with pytest.raises(
        HveeContractError,
        match=("evaluation observations only"),
    ):
        _bundle(observations=(observation,))


def test_budget_exhaustion_stops_proposal():
    observations = (
        _observation(
            sequence=1,
            candidate_index=4,
            verdict=(DecisionVerdict.PASS),
        ),
        _observation(
            sequence=2,
            candidate_index=0,
            verdict=(DecisionVerdict.PASS),
        ),
    )

    bundle = _bundle(
        maximum_evaluations=2,
        observations=observations,
    )

    assert bundle.payload["search"]["status"] == "budget_exhausted"

    assert bundle.payload["outcome"]["next_proposal"] is None


def test_full_grid_exhaustion():
    candidate_count = 3

    observations = (
        _observation(
            sequence=1,
            candidate_index=1,
            verdict=(DecisionVerdict.PASS),
        ),
        _observation(
            sequence=2,
            candidate_index=0,
            verdict=(DecisionVerdict.FAIL),
        ),
        _observation(
            sequence=3,
            candidate_index=2,
            verdict=(DecisionVerdict.PASS),
        ),
    )

    bundle = _bundle(
        candidate_count=(candidate_count),
        maximum_evaluations=(candidate_count),
        observations=(observations),
    )

    assert bundle.payload["search"]["status"] == "grid_exhausted"

    assert bundle.payload["outcome"]["next_proposal"] is None


def test_boundary_set_component_is_reused():
    observations = (
        _observation(
            sequence=1,
            candidate_index=4,
            verdict=(DecisionVerdict.PASS),
        ),
        _observation(
            sequence=2,
            candidate_index=0,
            verdict=(DecisionVerdict.FAIL),
        ),
        _observation(
            sequence=3,
            candidate_index=8,
            verdict=(DecisionVerdict.PASS),
        ),
        _observation(
            sequence=4,
            candidate_index=2,
            verdict=(DecisionVerdict.FAIL),
        ),
        _observation(
            sequence=5,
            candidate_index=3,
            verdict=(DecisionVerdict.PASS),
        ),
    )

    bundle = _bundle(observations=observations)

    assert bundle.payload["outcome"]["localized_boundary_count"] >= 1

    assert (
        bundle.payload["evidence_boundary"]["single_boundary_component_reused"] is True
    )


def test_policy_evidence_boundary_is_explicit():
    bundle = _bundle()

    boundary = bundle.payload["evidence_boundary"]

    assert boundary["design_policy_precommitted"] is True

    assert boundary["parameter_free_policy"] is True

    assert boundary["tuned_explore_exploit_ratio"] is False

    assert boundary["tuned_threshold"] is False

    assert boundary["wide_opposing_interval_automatic_priority"] is False

    assert boundary["incident_policy_changed"] is False

    assert boundary["run05_v2_development_evaluation_performed"] is False

    assert boundary["behavioral_performance_qualified"] is False


def test_bundle_is_deterministic_and_reverifiable():
    first = _bundle()
    second = _bundle()

    assert first.payload == second.payload

    assert first.sha256 == second.sha256

    assert verify_behavioral_multi_region_search_v2_bundle(
        payload=(first.payload),
        expected_sha256=(first.sha256),
    )


def test_tampered_bundle_fails_original_identity():
    bundle = _bundle()

    tampered = dict(bundle.payload)

    tampered["type"] = "tampered"

    assert not (
        verify_behavioral_multi_region_search_v2_bundle(
            payload=(tampered),
            expected_sha256=(bundle.sha256),
        )
    )


def test_boundary_closure_cannot_chain_and_starve_global_coverage():
    observations = (
        _observation(
            sequence=1,
            candidate_index=4,
            verdict=(DecisionVerdict.PASS),
        ),
        _observation(
            sequence=2,
            candidate_index=0,
            verdict=(DecisionVerdict.PASS),
        ),
        _observation(
            sequence=3,
            candidate_index=8,
            verdict=(DecisionVerdict.PASS),
        ),
        _observation(
            sequence=4,
            candidate_index=2,
            verdict=(DecisionVerdict.FAIL),
        ),
        _observation(
            sequence=5,
            candidate_index=1,
            verdict=(DecisionVerdict.PASS),
        ),
    )

    bundle = _bundle(observations=observations)

    proposal = bundle.payload["outcome"]["next_proposal"]

    assert proposal["candidate_index"] == 6

    assert (
        proposal["reason"]
        == BehavioralMultiRegionSearchV2ProposalReason.EXPLORE_FARTHEST_UNOBSERVED.value
    )

    boundary = bundle.payload["evidence_boundary"]

    assert boundary["maximum_consecutive_boundary_closures"] == 1

    assert boundary["closure_starvation_prevention"] is True

    assert boundary["coverage_required_after_boundary_closure"] is True

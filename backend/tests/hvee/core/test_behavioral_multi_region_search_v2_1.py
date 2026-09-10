from __future__ import annotations

import copy
import hashlib

import pytest

from hvee.core.behavioral_multi_region_search_v2_1 import (
    BehavioralMultiRegionSearchV21PlannerState,
    BehavioralMultiRegionSearchV21ProposalReason,
    BehavioralMultiRegionSearchV21Status,
    _localization_depth,
    _select_bounded_opportunity,
    build_behavioral_multi_region_search_v2_1_bundle,
    verify_behavioral_multi_region_search_v2_1_bundle,
)
from hvee.core.contracts import HveeContractError
from hvee.core.decision import DecisionVerdict
from hvee.core.failure_family_investigator import (
    FailureFamilyObservation,
    FailureFamilyObservationSource,
)


def _sha(
    value: str,
) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _observation(
    *,
    sequence: int,
    candidate_index: int,
    verdict: DecisionVerdict,
) -> FailureFamilyObservation:
    prefix = f"{sequence}|" f"{candidate_index}|" f"{verdict.value}"

    return FailureFamilyObservation(
        sequence=sequence,
        candidate_index=candidate_index,
        verdict=verdict,
        source=(FailureFamilyObservationSource.EVALUATION),
        cost_units=1,
        scenario_sha256=_sha("scenario|" + prefix),
        result_provenance_sha256=_sha("result|" + prefix),
        observation_evidence_sha256=_sha("observation|" + prefix),
        decision_evidence_sha256=_sha("decision|" + prefix),
        counterexample_evidence_sha256=(
            _sha("counterexample|" + prefix)
            if verdict == DecisionVerdict.FAIL
            else None
        ),
    )


def _bundle(
    *,
    candidate_count: int = 9,
    maximum_evaluations: int | None = None,
    observations=(),
):
    maximum = candidate_count if maximum_evaluations is None else maximum_evaluations

    return build_behavioral_multi_region_search_v2_1_bundle(
        evaluation_type="toy",
        search_key=("hetren.behavioral.multi-region.v2-1.test"),
        search_version="2.1.0",
        boundary_key=("hetren.behavioral.multi-region.v2-1.test.boundary"),
        boundary_version="1.0.0",
        axis_key="toy.index",
        axis_version="1.0.0",
        axis_unit="index",
        candidate_values=tuple(float(index) for index in range(candidate_count)),
        invariant_parameters={
            "lane": "toy",
        },
        maximum_evaluations=(maximum),
        observations=(observations),
    )


def _run(
    pattern: str,
    *,
    maximum_evaluations: int | None = None,
):
    maximum = len(pattern) if maximum_evaluations is None else maximum_evaluations

    observations = []
    indices = []
    reasons = []

    while True:
        bundle = _bundle(
            candidate_count=len(pattern),
            maximum_evaluations=(maximum),
            observations=tuple(observations),
        )

        proposal = bundle.payload["outcome"]["next_proposal"]

        if proposal is None:
            return (
                tuple(indices),
                tuple(reasons),
                tuple(observations),
                bundle,
            )

        index = int(proposal["candidate_index"])

        verdict = (
            DecisionVerdict.FAIL if pattern[index] == "F" else DecisionVerdict.PASS
        )

        observations.append(
            _observation(
                sequence=(len(observations) + 1),
                candidate_index=(index),
                verdict=(verdict),
            )
        )

        indices.append(index)

        reasons.append(proposal["reason"])


def test_localization_depth_contract_is_structural():
    assert _localization_depth(2) == 1

    assert _localization_depth(3) == 2

    assert _localization_depth(4) == 2

    assert _localization_depth(5) == 3


def test_empty_history_proposes_center():
    bundle = _bundle(candidate_count=9)

    assert bundle.payload["outcome"]["next_proposal"] == {
        "candidate_index": 4,
        "axis_value": 4.0,
        "reason": (BehavioralMultiRegionSearchV21ProposalReason.INITIAL_CENTER.value),
    }

    assert bundle.payload["planner"]["state"] == (
        BehavioralMultiRegionSearchV21PlannerState.NORMAL.value
    )


def test_no_boundary_opportunity_uses_maximin_coverage():
    indices, reasons, _observations, _bundle_result = _run(
        "PPPPPPPPP",
        maximum_evaluations=3,
    )

    assert indices == (
        4,
        0,
        8,
    )

    assert reasons == (
        "initial_center",
        "maximin_coverage",
        "maximin_coverage",
    )


def test_width_five_does_not_receive_automatic_refinement():
    indices, reasons, _observations, _bundle_result = _run(
        "FFFFFPPPPPP",
        maximum_evaluations=3,
    )

    assert indices == (
        5,
        0,
        10,
    )

    assert reasons == (
        "initial_center",
        "maximin_coverage",
        "maximin_coverage",
    )


def test_width_two_closes_then_requires_coverage_reset():
    indices, reasons, _observations, _bundle_result = _run(
        "FFPPP",
        maximum_evaluations=4,
    )

    assert indices == (
        2,
        0,
        1,
        4,
    )

    assert reasons == (
        "initial_center",
        "maximin_coverage",
        "boundary_transaction_refinement",
        "coverage_reset",
    )


def test_width_three_uses_at_most_two_boundary_actions():
    indices, reasons, _observations, _bundle_result = _run(
        "FFFPPPP",
        maximum_evaluations=5,
    )

    assert indices == (
        3,
        0,
        1,
        2,
        6,
    )

    assert reasons == (
        "initial_center",
        "maximin_coverage",
        "boundary_transaction_refinement",
        "boundary_transaction_refinement",
        "coverage_reset",
    )


def test_width_four_uses_two_actions_then_resets():
    indices, reasons, _observations, _bundle_result = _run(
        "FFPPPPPPP",
        maximum_evaluations=5,
    )

    assert indices == (
        4,
        0,
        2,
        1,
        8,
    )

    assert reasons == (
        "initial_center",
        "maximin_coverage",
        "boundary_transaction_refinement",
        "boundary_transaction_refinement",
        "coverage_reset",
    )


def test_multiple_bounded_opportunities_use_frozen_order():
    observations = (
        _observation(
            sequence=1,
            candidate_index=0,
            verdict=(DecisionVerdict.PASS),
        ),
        _observation(
            sequence=2,
            candidate_index=2,
            verdict=(DecisionVerdict.FAIL),
        ),
        _observation(
            sequence=3,
            candidate_index=4,
            verdict=(DecisionVerdict.PASS),
        ),
        _observation(
            sequence=4,
            candidate_index=7,
            verdict=(DecisionVerdict.FAIL),
        ),
    )

    transaction = _select_bounded_opportunity(observations)

    assert transaction is not None

    assert (
        transaction.lower,
        transaction.upper,
        transaction.actions_used,
    ) == (
        0,
        2,
        0,
    )


def test_history_reconstructs_coverage_reset_state():
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
            candidate_index=2,
            verdict=(DecisionVerdict.PASS),
        ),
        _observation(
            sequence=4,
            candidate_index=1,
            verdict=(DecisionVerdict.FAIL),
        ),
    )

    bundle = _bundle(
        candidate_count=9,
        observations=(observations),
    )

    assert bundle.payload["planner"]["state"] == (
        BehavioralMultiRegionSearchV21PlannerState.COVERAGE_RESET_REQUIRED.value
    )

    assert bundle.payload["outcome"]["next_proposal"]["candidate_index"] == 8

    assert bundle.payload["outcome"]["next_proposal"]["reason"] == (
        BehavioralMultiRegionSearchV21ProposalReason.COVERAGE_RESET.value
    )


def test_full_budget_can_observe_every_candidate():
    indices, _reasons, _observations, bundle = _run("PPPPPPPPP")

    assert len(indices) == 9

    assert len(set(indices)) == 9

    assert set(indices) == set(range(9))

    assert bundle.payload["search"]["status"] == (
        BehavioralMultiRegionSearchV21Status.GRID_EXHAUSTED.value
    )


def test_budget_exhaustion_is_distinct_from_grid_exhaustion():
    indices, _reasons, _observations, bundle = _run(
        "PPPPPPPPP",
        maximum_evaluations=2,
    )

    assert len(indices) == 2

    assert bundle.payload["search"]["status"] == (
        BehavioralMultiRegionSearchV21Status.BUDGET_EXHAUSTED.value
    )


def test_grid_exhaustion_wins_at_full_grid():
    _indices, _reasons, _observations, bundle = _run("PPPPP")

    assert bundle.payload["search"]["status"] == (
        BehavioralMultiRegionSearchV21Status.GRID_EXHAUSTED.value
    )


def test_rejects_observation_outside_deterministic_trajectory():
    bad = (
        _observation(
            sequence=1,
            candidate_index=0,
            verdict=(DecisionVerdict.PASS),
        ),
    )

    with pytest.raises(
        HveeContractError,
        match=("does not match deterministic trajectory"),
    ):
        _bundle(
            candidate_count=9,
            observations=bad,
        )


def test_rejects_duplicate_candidate_observation():
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
        match="cannot repeat a candidate",
    ):
        _bundle(
            candidate_count=9,
            observations=observations,
        )


def test_incident_anchor_is_rejected_from_global_v2_1():
    anchor = FailureFamilyObservation(
        sequence=0,
        candidate_index=4,
        verdict=(DecisionVerdict.FAIL),
        source=(FailureFamilyObservationSource.INCIDENT_ANCHOR),
        cost_units=0,
        scenario_sha256=_sha("anchor-scenario"),
        result_provenance_sha256=_sha("anchor-result"),
        observation_evidence_sha256=_sha("anchor-observation"),
        decision_evidence_sha256=_sha("anchor-decision"),
        counterexample_evidence_sha256=_sha("anchor-counterexample"),
    )

    with pytest.raises(
        HveeContractError,
        match="evaluation observations only",
    ):
        _bundle(
            candidate_count=9,
            observations=(anchor,),
        )


def test_boundary_set_component_is_reused():
    _indices, _reasons, _observations, bundle = _run("FFPPP")

    assert bundle.payload["outcome"]["localized_boundary_count"] == 1

    boundary_sha = bundle.payload["outcome"]["boundary_set_sha256"]

    assert isinstance(
        boundary_sha,
        str,
    )

    assert len(boundary_sha) == 64


def test_bundle_is_deterministic_across_observation_container_type():
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

    tuple_bundle = _bundle(
        candidate_count=9,
        observations=(observations),
    )

    list_bundle = _bundle(
        candidate_count=9,
        observations=list(observations),
    )

    assert tuple_bundle.payload == list_bundle.payload

    assert tuple_bundle.sha256 == list_bundle.sha256


def test_verifier_accepts_exact_bundle_and_rejects_tampering():
    bundle = _bundle(candidate_count=9)

    assert (
        verify_behavioral_multi_region_search_v2_1_bundle(
            payload=(bundle.payload),
            expected_sha256=(bundle.sha256),
        )
        is True
    )

    tampered = copy.deepcopy(bundle.payload)

    tampered["policy"]["coverage_reset_required"] = False

    assert (
        verify_behavioral_multi_region_search_v2_1_bundle(
            payload=(tampered),
            expected_sha256=(bundle.sha256),
        )
        is False
    )


def test_evidence_boundary_never_claims_qualification():
    bundle = _bundle(candidate_count=9)

    boundary = bundle.payload["evidence_boundary"]

    assert boundary["development_evidence_only"] is True

    assert boundary["behavioral_performance_qualified"] is False

    assert boundary["real_ai_generalization_established"] is False

    assert boundary["hidden_pattern_used"] is False

    assert boundary["model_inference_performed"] is False

    assert boundary["asr_execution_performed"] is False

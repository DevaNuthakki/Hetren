from __future__ import annotations

import hashlib

import pytest

from hvee.core.behavioral_evidence_gain_planner import (
    BehavioralEvidenceGainPlannerCandidateRole,
    BehavioralEvidenceGainPlannerStatus,
    _CandidateScore,
    _candidate_scores,
    _coverage_gain,
    _coverage_potential,
    _dominates,
    _known_boundary_gain,
    _known_boundary_potential,
    _pareto_frontier,
    _select_nonbootstrap_candidate,
    build_behavioral_evidence_gain_planner_bundle,
    calculate_behavioral_evidence_gain_planner_sha256,
    verify_behavioral_evidence_gain_planner_bundle,
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
    sequence: int,
    candidate_index: int,
    verdict: DecisionVerdict,
) -> FailureFamilyObservation:
    token = f"{sequence}|" f"{candidate_index}|" f"{verdict.value}"

    return FailureFamilyObservation(
        sequence=sequence,
        candidate_index=candidate_index,
        verdict=verdict,
        source=(FailureFamilyObservationSource.EVALUATION),
        cost_units=1,
        scenario_sha256=_sha("scenario|" + token),
        result_provenance_sha256=_sha("result|" + token),
        observation_evidence_sha256=_sha("observation|" + token),
        decision_evidence_sha256=_sha("decision|" + token),
        counterexample_evidence_sha256=(
            _sha("counterexample|" + token) if verdict == DecisionVerdict.FAIL else None
        ),
    )


def _build(
    *,
    candidate_count: int = 9,
    maximum_evaluations: int | None = None,
    observations: tuple[
        FailureFamilyObservation,
        ...,
    ] = tuple(),
):
    if maximum_evaluations is None:
        maximum_evaluations = candidate_count

    return build_behavioral_evidence_gain_planner_bundle(
        evaluation_type="test",
        planner_key=("hetren.behavioral." "evidence-gain-planner"),
        planner_version="1.0.0",
        boundary_key=("hetren.test.boundary"),
        boundary_version="1.0.0",
        axis_key="test.index",
        axis_version="1.0.0",
        axis_unit="index",
        candidate_values=tuple(float(index) for index in range(candidate_count)),
        invariant_parameters={
            "lane": "unit",
        },
        maximum_evaluations=(maximum_evaluations),
        observations=(observations),
    )


def _execute_pattern(
    pattern: str,
    *,
    maximum_evaluations: int | None = None,
):
    if maximum_evaluations is None:
        maximum_evaluations = len(pattern)

    observations: list[FailureFamilyObservation] = []

    while True:
        bundle = _build(
            candidate_count=len(pattern),
            maximum_evaluations=(maximum_evaluations),
            observations=tuple(observations),
        )

        proposal = bundle.payload["outcome"]["next_proposal"]

        if proposal is None:
            return (
                tuple(observations),
                bundle,
            )

        index = int(proposal["candidate_index"])

        verdict = (
            DecisionVerdict.FAIL if pattern[index] == "F" else DecisionVerdict.PASS
        )

        observations.append(
            _observation(
                len(observations) + 1,
                index,
                verdict,
            )
        )


def test_bootstrap_uses_floor_center():
    bundle = _build(candidate_count=9)

    proposal = bundle.payload["outcome"]["next_proposal"]

    assert proposal["candidate_index"] == 4

    assert proposal["reason"] == "structural_center_bootstrap"

    assert proposal["structural_evidence"] is None


def test_bootstrap_does_not_apply_evidence_scoring():
    bundle = _build(candidate_count=8)

    scoring = bundle.payload["candidate_scoring"]

    assert scoring["applied"] is False

    assert scoring["records"] == []

    assert bundle.payload["state"]["coverage_potential"] is None


def test_coverage_potential_reference_value():
    assert (
        _coverage_potential(
            candidate_count=9,
            observed_indices={
                4,
            },
        )
        == 20
    )


def test_coverage_gain_reference_value():
    assert (
        _coverage_gain(
            candidate_count=9,
            observed_indices={
                4,
            },
            candidate_index=1,
        )
        == 7
    )


@pytest.mark.parametrize(
    "width",
    range(
        2,
        10,
    ),
)
def test_known_boundary_gain_has_no_width_cutoff(
    width,
):
    observations = (
        _observation(
            1,
            0,
            DecisionVerdict.PASS,
        ),
        _observation(
            2,
            width,
            DecisionVerdict.FAIL,
        ),
    )

    midpoint = width // 2

    assert _known_boundary_gain(
        observations=observations,
        candidate_index=midpoint,
    ) == min(
        midpoint,
        width - midpoint,
    )


def test_known_boundary_gain_zero_outside_opposing_interval():
    observations = (
        _observation(
            1,
            0,
            DecisionVerdict.PASS,
        ),
        _observation(
            2,
            4,
            DecisionVerdict.FAIL,
        ),
    )

    assert (
        _known_boundary_gain(
            observations=observations,
            candidate_index=7,
        )
        == 0
    )


def test_known_boundary_potential_sums_all_current_opposing_intervals():
    observations = (
        _observation(
            1,
            0,
            DecisionVerdict.PASS,
        ),
        _observation(
            2,
            4,
            DecisionVerdict.FAIL,
        ),
        _observation(
            3,
            8,
            DecisionVerdict.PASS,
        ),
    )

    assert _known_boundary_potential(observations) == 6


def test_candidate_scores_cover_every_unobserved_candidate():
    observations = (
        _observation(
            1,
            4,
            DecisionVerdict.PASS,
        ),
    )

    scores = _candidate_scores(
        candidate_count=9,
        observations=observations,
    )

    assert {item.candidate_index for item in scores} == {
        0,
        1,
        2,
        3,
        5,
        6,
        7,
        8,
    }


def test_candidate_can_have_coverage_and_boundary_roles():
    observations = (
        _observation(
            1,
            0,
            DecisionVerdict.PASS,
        ),
        _observation(
            2,
            4,
            DecisionVerdict.FAIL,
        ),
    )

    scores = _candidate_scores(
        candidate_count=9,
        observations=observations,
    )

    score = next(item for item in scores if item.candidate_index == 2)

    assert BehavioralEvidenceGainPlannerCandidateRole.GLOBAL_COVERAGE in score.roles

    assert (
        BehavioralEvidenceGainPlannerCandidateRole.BOUNDARY_LOCALIZATION in score.roles
    )

    assert score.coverage_gain > 0
    assert score.known_boundary_gain == 2


def test_structural_dominance_removes_worse_candidate():
    better = _CandidateScore(
        candidate_index=1,
        roles=(BehavioralEvidenceGainPlannerCandidateRole.GLOBAL_COVERAGE,),
        coverage_gain=5,
        known_boundary_gain=2,
        planned_cost_units=1,
        total_structural_gain=7,
    )

    worse = _CandidateScore(
        candidate_index=2,
        roles=(BehavioralEvidenceGainPlannerCandidateRole.GLOBAL_COVERAGE,),
        coverage_gain=4,
        known_boundary_gain=2,
        planned_cost_units=1,
        total_structural_gain=6,
    )

    assert (
        _dominates(
            better,
            worse,
        )
        is True
    )

    assert _pareto_frontier(
        (
            better,
            worse,
        )
    ) == (better,)


def test_symmetric_total_gain_tie_uses_lowest_candidate_index():
    observations = (
        _observation(
            1,
            4,
            DecisionVerdict.PASS,
        ),
    )

    selected, _scores, _frontier = _select_nonbootstrap_candidate(
        candidate_count=9,
        observations=observations,
    )

    assert selected.candidate_index == 1


def test_same_state_is_deterministic():
    observations = (
        _observation(
            1,
            4,
            DecisionVerdict.PASS,
        ),
    )

    first = _select_nonbootstrap_candidate(
        candidate_count=9,
        observations=observations,
    )[0]

    second = _select_nonbootstrap_candidate(
        candidate_count=9,
        observations=observations,
    )[0]

    assert first == second


def test_observation_history_must_match_deterministic_trajectory():
    wrong = (
        _observation(
            1,
            0,
            DecisionVerdict.PASS,
        ),
    )

    with pytest.raises(
        HveeContractError,
        match=("does not match deterministic " "proposal trajectory"),
    ):
        _build(
            candidate_count=7,
            observations=wrong,
        )


def test_full_budget_execution_observes_entire_grid_once():
    observations, bundle = _execute_pattern("PFFPPFPFP")

    assert len(observations) == 9

    assert len({item.candidate_index for item in observations}) == 9

    assert (
        bundle.payload["planner"]["status"]
        == BehavioralEvidenceGainPlannerStatus.GRID_EXHAUSTED.value
    )

    assert bundle.payload["outcome"]["next_proposal"] is None


def test_budget_exhaustion_stops_before_grid_completion():
    observations, bundle = _execute_pattern(
        "PFFPPFPFP",
        maximum_evaluations=3,
    )

    assert len(observations) == 3

    assert (
        bundle.payload["planner"]["status"]
        == BehavioralEvidenceGainPlannerStatus.BUDGET_EXHAUSTED.value
    )

    assert bundle.payload["outcome"]["next_proposal"] is None


def test_failure_family_boundary_set_is_reused():
    observations, bundle = _execute_pattern(
        "PFFPP",
        maximum_evaluations=5,
    )

    assert len(observations) == 5

    evidence = bundle.payload["evidence_boundary"]

    assert evidence["failure_family_boundary_set_reused"] is True

    assert len(bundle.payload["outcome"]["boundary_set_sha256"]) == 64


def test_incident_anchor_is_rejected():
    anchor = FailureFamilyObservation(
        sequence=0,
        candidate_index=2,
        verdict=DecisionVerdict.FAIL,
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
        match=("accepts only evaluated observations"),
    ):
        _build(
            candidate_count=5,
            observations=(anchor,),
        )


def test_bundle_hash_roundtrip_and_verifier():
    observations, bundle = _execute_pattern(
        "PFFPP",
        maximum_evaluations=3,
    )

    assert len(observations) == 3

    assert bundle.sha256 == calculate_behavioral_evidence_gain_planner_sha256(
        bundle.payload
    )

    assert (
        verify_behavioral_evidence_gain_planner_bundle(
            payload=(bundle.payload),
            expected_sha256=(bundle.sha256),
        )
        is True
    )


def test_verifier_rejects_payload_tampering():
    bundle = _build(candidate_count=7)

    payload = dict(bundle.payload)

    planner = dict(payload["planner"])

    planner["objective"] = "tampered"

    payload["planner"] = planner

    assert (
        verify_behavioral_evidence_gain_planner_bundle(
            payload=payload,
            expected_sha256=(bundle.sha256),
        )
        is False
    )


def test_axis_value_is_preserved_in_proposal():
    bundle = build_behavioral_evidence_gain_planner_bundle(
        evaluation_type="test",
        planner_key="planner",
        planner_version="1.0.0",
        boundary_key="boundary",
        boundary_version="1.0.0",
        axis_key="axis",
        axis_version="1.0.0",
        axis_unit="units",
        candidate_values=(
            10,
            20,
            30,
            40,
            50,
        ),
        invariant_parameters={
            "lane": "axis-test",
        },
        maximum_evaluations=5,
        observations=tuple(),
    )

    proposal = bundle.payload["outcome"]["next_proposal"]

    assert proposal["candidate_index"] == 2

    assert proposal["axis_value"] == 30


def test_budget_cannot_exceed_candidate_count():
    with pytest.raises(
        HveeContractError,
        match=("cannot exceed candidate count"),
    ):
        _build(
            candidate_count=5,
            maximum_evaluations=6,
        )


def test_evidence_boundary_denies_hidden_and_future_access():
    bundle = _build(candidate_count=7)

    evidence = bundle.payload["evidence_boundary"]

    assert evidence["hidden_true_topology_access"] is False

    assert evidence["future_verdict_access"] is False

    assert evidence["closed_864_corpus_used"] is False

    assert evidence["planner_performance_evaluated"] is False


def test_nonbootstrap_payload_exposes_full_candidate_evidence():
    first = _build(candidate_count=9)

    center = int(first.payload["outcome"]["next_proposal"]["candidate_index"])

    second = _build(
        candidate_count=9,
        observations=(
            _observation(
                1,
                center,
                DecisionVerdict.PASS,
            ),
        ),
    )

    records = second.payload["candidate_scoring"]["records"]

    assert len(records) == 8

    assert all(item["coverage_gain"] > 0 for item in records)

    assert all(item["planned_cost_units"] == 1 for item in records)

    assert second.payload["candidate_scoring"]["learned_weights"] is False

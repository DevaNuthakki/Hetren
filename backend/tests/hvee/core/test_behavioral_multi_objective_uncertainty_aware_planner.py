from __future__ import annotations

from itertools import product

import pytest

from hvee.core.behavioral_multi_objective_uncertainty_aware_planner import (
    MultiObjectivePlannerError,
    MultiObjectiveSelectionReason,
    OpposingInterval,
    boundary_ambiguity_mass,
    build_behavioral_multi_objective_uncertainty_aware_decision,
    build_multi_objective_candidate_record,
    coverage_distance_mass,
    information_candidate_dominates,
    opposing_intervals,
    structural_candidate_dominates,
)
from hvee.core.decision import DecisionVerdict


PASS = DecisionVerdict.PASS
FAIL = DecisionVerdict.FAIL


@pytest.mark.parametrize(
    "candidate_count",
    [
        0,
        1,
        -1,
        True,
        2.0,
    ],
)
def test_rejects_invalid_candidate_count(
    candidate_count,
):
    with pytest.raises(MultiObjectivePlannerError):
        build_behavioral_multi_objective_uncertainty_aware_decision(
            candidate_count=(candidate_count),
            observations={},
        )


def test_rejects_observation_outside_grid():
    with pytest.raises(MultiObjectivePlannerError):
        build_behavioral_multi_objective_uncertainty_aware_decision(
            candidate_count=5,
            observations={
                5: PASS,
            },
        )


def test_coverage_distance_mass():
    assert (
        coverage_distance_mass(
            candidate_count=5,
            observed_indices={
                0,
                4,
            },
        )
        == 4
    )

    assert (
        coverage_distance_mass(
            candidate_count=5,
            observed_indices={
                0,
                2,
                4,
            },
        )
        == 2
    )


def test_opposing_intervals_and_boundary_mass():
    observations = {
        0: PASS,
        2: PASS,
        5: FAIL,
        7: PASS,
    }

    assert opposing_intervals(observations) == (
        OpposingInterval(
            left_index=2,
            right_index=5,
        ),
        OpposingInterval(
            left_index=5,
            right_index=7,
        ),
    )

    assert boundary_ambiguity_mass(observations) == 3


def test_known_opposing_interval_center_record():
    record = build_multi_objective_candidate_record(
        candidate_count=5,
        observations={
            0: PASS,
            4: FAIL,
        },
        candidate_index=2,
    )

    assert record.coverage_gain == 2

    assert record.guaranteed_boundary_ambiguity_reduction == 2

    assert record.worst_case_boundary_ambiguity_expansion == 0

    assert record.pass_boundary_ambiguity == 1

    assert record.fail_boundary_ambiguity == 1

    assert record.outcome_boundary_mass_separation == 0

    assert record.outcome_interval_symmetric_difference_count == 2


def test_candidate_outside_known_opposing_interval_has_risk():
    record = build_multi_objective_candidate_record(
        candidate_count=5,
        observations={
            0: PASS,
            2: PASS,
        },
        candidate_index=4,
    )

    assert record.guaranteed_boundary_ambiguity_reduction == 0

    assert record.worst_case_boundary_ambiguity_expansion == 1

    assert record.outcome_boundary_mass_separation == 1


@pytest.mark.parametrize(
    (
        "candidate_count",
        "expected",
    ),
    [
        (
            2,
            1,
        ),
        (
            3,
            1,
        ),
        (
            4,
            2,
        ),
        (
            5,
            2,
        ),
        (
            8,
            4,
        ),
    ],
)
def test_bootstrap_uses_structural_center(
    candidate_count,
    expected,
):
    decision = build_behavioral_multi_objective_uncertainty_aware_decision(
        candidate_count=(candidate_count),
        observations={},
    )

    assert decision.selected_candidate_index == expected

    assert (
        decision.selection_reason
        is MultiObjectiveSelectionReason.STRUCTURAL_CENTER_BOOTSTRAP
    )

    assert decision.primary_frontier_candidate_indices == (expected,)

    assert decision.uncertainty_frontier_candidate_indices == (expected,)

    assert decision.unresolved_action_ambiguity is False

    assert decision.candidate_records == ()


def test_grid_exhausted_is_terminal():
    decision = build_behavioral_multi_objective_uncertainty_aware_decision(
        candidate_count=3,
        observations={
            0: PASS,
            1: FAIL,
            2: PASS,
        },
    )

    assert decision.terminal is True

    assert decision.selected_candidate_index is None

    assert decision.selection_reason is MultiObjectiveSelectionReason.GRID_EXHAUSTED


def test_structural_dominance():
    center = build_multi_objective_candidate_record(
        candidate_count=5,
        observations={
            0: PASS,
            4: FAIL,
        },
        candidate_index=2,
    )

    side = build_multi_objective_candidate_record(
        candidate_count=5,
        observations={
            0: PASS,
            4: FAIL,
        },
        candidate_index=1,
    )

    assert (
        structural_candidate_dominates(
            center,
            side,
        )
        is True
    )

    assert (
        structural_candidate_dominates(
            side,
            center,
        )
        is False
    )


def test_information_dominance_is_separate_from_structural_dominance():
    left = build_multi_objective_candidate_record(
        candidate_count=5,
        observations={
            0: PASS,
            2: PASS,
        },
        candidate_index=4,
    )

    right = build_multi_objective_candidate_record(
        candidate_count=5,
        observations={
            0: PASS,
            2: PASS,
        },
        candidate_index=3,
    )

    result = information_candidate_dominates(
        left,
        right,
    )

    assert isinstance(
        result,
        bool,
    )


def test_candidate_records_are_sorted_by_candidate_index():
    decision = build_behavioral_multi_objective_uncertainty_aware_decision(
        candidate_count=7,
        observations={
            3: PASS,
        },
    )

    indices = tuple(record.candidate_index for record in decision.candidate_records)

    assert indices == tuple(sorted(indices))


def test_uncertainty_frontier_is_subset_of_primary_frontier():
    for state in product(
        (
            None,
            PASS,
            FAIL,
        ),
        repeat=5,
    ):
        observations = {
            index: verdict for index, verdict in enumerate(state) if verdict is not None
        }

        decision = build_behavioral_multi_objective_uncertainty_aware_decision(
            candidate_count=5,
            observations=observations,
        )

        if decision.terminal:
            continue

        assert set(decision.uncertainty_frontier_candidate_indices) <= set(
            decision.primary_frontier_candidate_indices
        )


def test_ambiguity_tie_break_is_lowest_uncertainty_frontier_index():
    found = False

    for state in product(
        (
            None,
            PASS,
            FAIL,
        ),
        repeat=6,
    ):
        observations = {
            index: verdict for index, verdict in enumerate(state) if verdict is not None
        }

        if not observations or len(observations) == 6:
            continue

        decision = build_behavioral_multi_objective_uncertainty_aware_decision(
            candidate_count=6,
            observations=observations,
        )

        if (
            decision.selection_reason
            is MultiObjectiveSelectionReason.DETERMINISTIC_REPRODUCIBILITY_TIE_BREAK
        ):
            found = True

            assert decision.unresolved_action_ambiguity is True

            assert len(decision.uncertainty_frontier_candidate_indices) > 1

            assert decision.selected_candidate_index == min(
                decision.uncertainty_frontier_candidate_indices
            )

            break

    assert found is True


def test_non_ambiguous_selection_never_claims_ambiguity():
    for state in product(
        (
            None,
            PASS,
            FAIL,
        ),
        repeat=5,
    ):
        observations = {
            index: verdict for index, verdict in enumerate(state) if verdict is not None
        }

        decision = build_behavioral_multi_objective_uncertainty_aware_decision(
            candidate_count=5,
            observations=observations,
        )

        if (
            decision.selection_reason
            is not MultiObjectiveSelectionReason.DETERMINISTIC_REPRODUCIBILITY_TIE_BREAK
        ):
            assert decision.unresolved_action_ambiguity is False


def test_deterministic_rebuild():
    observations = {
        0: PASS,
        4: FAIL,
        7: PASS,
    }

    first = build_behavioral_multi_objective_uncertainty_aware_decision(
        candidate_count=8,
        observations=observations,
    )

    second = build_behavioral_multi_objective_uncertainty_aware_decision(
        candidate_count=8,
        observations=observations,
    )

    assert first == second


def test_exhaustive_architecture_invariants_n2_to_n8():
    state_count = 0
    candidate_record_count = 0

    for candidate_count in range(
        2,
        9,
    ):
        for state in product(
            (
                None,
                PASS,
                FAIL,
            ),
            repeat=candidate_count,
        ):
            observations = {
                index: verdict
                for index, verdict in enumerate(state)
                if verdict is not None
            }

            unobserved = {
                index for index, verdict in enumerate(state) if verdict is None
            }

            if not observations or not unobserved:
                continue

            decision = build_behavioral_multi_objective_uncertainty_aware_decision(
                candidate_count=(candidate_count),
                observations=(observations),
            )

            state_count += 1

            assert decision.selected_candidate_index in unobserved

            assert decision.primary_frontier_candidate_indices

            assert decision.uncertainty_frontier_candidate_indices

            assert set(decision.uncertainty_frontier_candidate_indices) <= set(
                decision.primary_frontier_candidate_indices
            )

            assert (
                decision.selected_candidate_index
                in decision.uncertainty_frontier_candidate_indices
            )

            candidate_record_count += len(decision.candidate_records)

            for record in decision.candidate_records:
                assert record.coverage_gain >= 0

                assert record.guaranteed_boundary_ambiguity_reduction >= 0

                assert record.worst_case_boundary_ambiguity_expansion >= 0

                assert record.outcome_boundary_mass_separation >= 0

                assert record.outcome_interval_symmetric_difference_count >= 0

    assert state_count == 9322

    assert candidate_record_count == 24568


def test_exhaustive_existing_boundary_formula_compatibility():
    known_checks = 0
    outside_checks = 0

    for candidate_count in range(
        2,
        9,
    ):
        for state in product(
            (
                None,
                PASS,
                FAIL,
            ),
            repeat=candidate_count,
        ):
            observations = {
                index: verdict
                for index, verdict in enumerate(state)
                if verdict is not None
            }

            if not observations:
                continue

            intervals = opposing_intervals(observations)

            for candidate_index, verdict in enumerate(state):
                if verdict is not None:
                    continue

                record = build_multi_objective_candidate_record(
                    candidate_count=(candidate_count),
                    observations=(observations),
                    candidate_index=(candidate_index),
                )

                containing = [
                    interval
                    for interval in intervals
                    if (interval.left_index < candidate_index < interval.right_index)
                ]

                if containing:
                    assert len(containing) == 1

                    interval = containing[0]

                    expected = min(
                        candidate_index - interval.left_index,
                        interval.right_index - candidate_index,
                    )

                    assert record.guaranteed_boundary_ambiguity_reduction == expected

                    assert record.worst_case_boundary_ambiguity_expansion == 0

                    known_checks += 1

                else:
                    assert record.guaranteed_boundary_ambiguity_reduction == 0

                    outside_checks += 1

    assert known_checks == 7404

    assert outside_checks == 17164


def test_exhaustive_selection_reason_counts_match_frozen_math():
    structural_unique = 0
    information_unique = 0
    ambiguous = 0

    for candidate_count in range(
        2,
        9,
    ):
        for state in product(
            (
                None,
                PASS,
                FAIL,
            ),
            repeat=candidate_count,
        ):
            observations = {
                index: verdict
                for index, verdict in enumerate(state)
                if verdict is not None
            }

            if not observations or len(observations) == candidate_count:
                continue

            decision = build_behavioral_multi_objective_uncertainty_aware_decision(
                candidate_count=(candidate_count),
                observations=(observations),
            )

            if (
                decision.selection_reason
                is MultiObjectiveSelectionReason.UNIQUE_STRUCTURAL_NONDOMINATED
            ):
                structural_unique += 1

            elif (
                decision.selection_reason
                is MultiObjectiveSelectionReason.UNIQUE_INFORMATION_NONDOMINATED
            ):
                information_unique += 1

            elif (
                decision.selection_reason
                is MultiObjectiveSelectionReason.DETERMINISTIC_REPRODUCIBILITY_TIE_BREAK
            ):
                ambiguous += 1

            else:
                raise AssertionError(decision.selection_reason)

    assert structural_unique == 4808
    assert information_unique == 932
    assert ambiguous == 3582


def test_rejects_non_enum_observation_verdicts():
    invalid_values = (
        "pass",
        "fail",
        "PASS",
        "FAIL",
        0,
        1,
        True,
        None,
    )

    for verdict in invalid_values:
        with pytest.raises(MultiObjectivePlannerError):
            build_behavioral_multi_objective_uncertainty_aware_decision(
                candidate_count=3,
                observations={
                    0: verdict,
                },
            )

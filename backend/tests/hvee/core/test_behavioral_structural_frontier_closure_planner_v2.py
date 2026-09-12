from __future__ import annotations

from enum import Enum
from itertools import combinations, product

import pytest

from hvee.core.behavioral_structural_frontier_closure_planner_v2 import (
    PLANNER_KEY,
    PLANNER_VERSION,
    StructuralActionClass,
    StructuralFrontierPlannerError,
    StructuralPlannerVariant,
    build_behavioral_structural_frontier_closure_decision,
    calculate_behavioral_structural_frontier_closure_decision_sha256,
    observed_components,
    opposing_brackets,
    unobserved_intervals,
)


class ExampleVerdict(str, Enum):
    PASS = "pass"
    FAIL = "fail"


def build(
    *,
    candidate_count,
    observations,
    variant=StructuralPlannerVariant.V2A_BALANCED_FRONTIER_CLOSURE,
):
    return build_behavioral_structural_frontier_closure_decision(
        candidate_count=candidate_count,
        observations=observations,
        variant=variant,
    )


def invert(
    observations,
):
    return {
        index: ("fail" if verdict == "pass" else "pass")
        for index, verdict in observations.items()
    }


def test_identity_constants_are_new_v2_identity():
    assert PLANNER_KEY == "behavioral_structural_frontier_closure_planner_v2"

    assert PLANNER_VERSION == "2.0.0-candidate-family-v1"


def test_empty_grid_starts_at_largest_global_frontier_midpoint():
    decision = build(
        candidate_count=9,
        observations={},
    )

    assert decision.selected_candidate_index == 4

    assert decision.action_class == StructuralActionClass.GLOBAL_FRONTIER_EXPLORE

    assert decision.selection_phase == "BALANCED_LOCAL_PHASE"


def test_exact_one_step_boundary_close_has_hard_priority():
    for variant in StructuralPlannerVariant:
        decision = build(
            candidate_count=5,
            observations={
                0: "pass",
                2: "fail",
            },
            variant=variant,
        )

        assert decision.selected_candidate_index == 1

        assert decision.action_class == StructuralActionClass.BOUNDARY_CLOSE

        assert decision.selection_phase == "HARD_BOUNDARY_CLOSE"


def test_balanced_variant_refines_boundary_on_local_phase():
    decision = build(
        candidate_count=12,
        observations={
            0: "pass",
            4: "fail",
        },
        variant=(StructuralPlannerVariant.V2A_BALANCED_FRONTIER_CLOSURE),
    )

    assert decision.selected_candidate_index == 2

    assert decision.action_class == StructuralActionClass.BOUNDARY_BRACKET_REFINE

    assert decision.selection_phase == "BALANCED_LOCAL_PHASE"


def test_balanced_variant_explores_global_frontier_on_global_phase():
    decision = build(
        candidate_count=12,
        observations={
            0: "pass",
            4: "fail",
            5: "fail",
        },
        variant=(StructuralPlannerVariant.V2A_BALANCED_FRONTIER_CLOSURE),
    )

    assert decision.selected_candidate_index == 8

    assert decision.action_class == StructuralActionClass.GLOBAL_FRONTIER_EXPLORE

    assert decision.selection_phase == "BALANCED_GLOBAL_PHASE"


def test_closure_with_coverage_floor_refines_when_floor_not_due():
    decision = build(
        candidate_count=12,
        observations={
            0: "pass",
            4: "fail",
        },
        variant=(StructuralPlannerVariant.V2B_CLOSURE_WITH_COVERAGE_FLOOR),
    )

    assert decision.selected_candidate_index == 2

    assert decision.action_class == StructuralActionClass.BOUNDARY_BRACKET_REFINE

    assert decision.selection_phase == "CLOSURE_PRIORITY_PHASE"


def test_closure_with_coverage_floor_forces_global_phase():
    decision = build(
        candidate_count=12,
        observations={
            0: "pass",
            4: "fail",
            5: "fail",
        },
        variant=(StructuralPlannerVariant.V2B_CLOSURE_WITH_COVERAGE_FLOOR),
    )

    assert decision.selected_candidate_index == 8

    assert decision.action_class == StructuralActionClass.GLOBAL_FRONTIER_EXPLORE

    assert decision.selection_phase == "COVERAGE_FLOOR_PHASE"


def test_failure_frontier_variant_expands_fail_frontier():
    decision = build(
        candidate_count=12,
        observations={
            0: "pass",
            4: "fail",
            5: "fail",
        },
        variant=(StructuralPlannerVariant.V2C_FAILURE_FRONTIER_STRUCTURAL),
    )

    assert decision.selected_candidate_index == 6

    assert decision.action_class == StructuralActionClass.FAILURE_FRONTIER_EXPAND

    assert decision.selection_phase == "FAILURE_FRONTIER_PHASE"


def test_component_consolidation_reduces_fragmentation_when_local_debt_exists():
    decision = build(
        candidate_count=5,
        observations={
            0: "pass",
            2: "pass",
        },
        variant=(StructuralPlannerVariant.V2A_BALANCED_FRONTIER_CLOSURE),
    )

    assert decision.selected_candidate_index == 1

    assert decision.action_class == StructuralActionClass.COMPONENT_CONSOLIDATE


def test_observed_component_inventory_is_exact():
    components = observed_components(
        observations={
            0: "pass",
            1: "fail",
            4: "pass",
            6: "fail",
            7: "fail",
        }
    )

    assert [
        (
            value.left_index,
            value.right_index,
        )
        for value in components
    ] == [
        (0, 1),
        (4, 4),
        (6, 7),
    ]


def test_unobserved_interval_inventory_is_exact():
    intervals = unobserved_intervals(
        candidate_count=8,
        observations={
            0: "pass",
            1: "fail",
            4: "pass",
            6: "fail",
            7: "fail",
        },
    )

    assert [
        (
            value.left_index,
            value.right_index,
        )
        for value in intervals
    ] == [
        (2, 3),
        (5, 5),
    ]


def test_opposing_brackets_use_consecutive_observed_points():
    brackets = opposing_brackets(
        candidate_count=10,
        observations={
            0: "pass",
            4: "fail",
            7: "fail",
            9: "pass",
        },
    )

    assert [
        (
            value.left_index,
            value.right_index,
            value.left_verdict,
            value.right_verdict,
        )
        for value in brackets
    ] == [
        (0, 4, "pass", "fail"),
        (7, 9, "fail", "pass"),
    ]


def test_a_and_b_are_orientation_symmetric():
    observations = {
        0: "pass",
        3: "fail",
        8: "fail",
        10: "pass",
    }

    inverted = invert(observations)

    for variant in (
        StructuralPlannerVariant.V2A_BALANCED_FRONTIER_CLOSURE,
        StructuralPlannerVariant.V2B_CLOSURE_WITH_COVERAGE_FLOOR,
    ):
        left = build(
            candidate_count=12,
            observations=observations,
            variant=variant,
        )

        right = build(
            candidate_count=12,
            observations=inverted,
            variant=variant,
        )

        assert left.selected_candidate_index == right.selected_candidate_index

        assert left.action_class == right.action_class

        assert left.selection_phase == right.selection_phase

        assert [
            (
                bracket.left_index,
                bracket.right_index,
            )
            for bracket in left.opposing_brackets
        ] == [
            (
                bracket.left_index,
                bracket.right_index,
            )
            for bracket in right.opposing_brackets
        ]


def test_enum_like_verdict_values_are_supported():
    decision = build(
        candidate_count=5,
        observations={
            0: ExampleVerdict.PASS,
            2: ExampleVerdict.FAIL,
        },
    )

    assert decision.selected_candidate_index == 1

    assert decision.action_class == StructuralActionClass.BOUNDARY_CLOSE


def test_complete_grid_returns_complete_without_candidate():
    for variant in StructuralPlannerVariant:
        decision = build(
            candidate_count=4,
            observations={
                0: "pass",
                1: "fail",
                2: "pass",
                3: "fail",
            },
            variant=variant,
        )

        assert decision.selected_candidate_index is None

        assert decision.action_class == StructuralActionClass.COMPLETE

        assert decision.remaining_candidate_count == 0


@pytest.mark.parametrize(
    "candidate_count",
    [
        0,
        -1,
        True,
        1.5,
    ],
)
def test_invalid_candidate_count_fails_closed(
    candidate_count,
):
    with pytest.raises(StructuralFrontierPlannerError):
        build(
            candidate_count=candidate_count,
            observations={},
        )


def test_invalid_observation_index_fails_closed():
    with pytest.raises(StructuralFrontierPlannerError):
        build(
            candidate_count=5,
            observations={
                5: "pass",
            },
        )


def test_invalid_verdict_fails_closed():
    with pytest.raises(StructuralFrontierPlannerError):
        build(
            candidate_count=5,
            observations={
                0: "unknown",
            },
        )


def test_invalid_variant_fails_closed():
    with pytest.raises(StructuralFrontierPlannerError):
        build_behavioral_structural_frontier_closure_decision(
            candidate_count=5,
            observations={},
            variant="V2A_BALANCED_FRONTIER_CLOSURE",
        )


def test_decision_sha_is_deterministic_and_input_order_invariant():
    first = build(
        candidate_count=9,
        observations={
            0: "pass",
            6: "fail",
            8: "pass",
        },
    )

    second = build(
        candidate_count=9,
        observations={
            8: "pass",
            6: "fail",
            0: "pass",
        },
    )

    assert first == second

    assert calculate_behavioral_structural_frontier_closure_decision_sha256(
        first
    ) == calculate_behavioral_structural_frontier_closure_decision_sha256(second)


def test_every_selected_candidate_is_unobserved_and_in_range_exhaustively():
    for candidate_count in range(
        2,
        8,
    ):
        universe = tuple(range(candidate_count))

        for observed_count in range(candidate_count + 1):
            for observed_indices in combinations(
                universe,
                observed_count,
            ):
                for verdicts in product(
                    (
                        "pass",
                        "fail",
                    ),
                    repeat=observed_count,
                ):
                    observations = dict(
                        zip(
                            observed_indices,
                            verdicts,
                            strict=True,
                        )
                    )

                    for variant in StructuralPlannerVariant:
                        decision = build(
                            candidate_count=candidate_count,
                            observations=observations,
                            variant=variant,
                        )

                        replay = build(
                            candidate_count=candidate_count,
                            observations=observations,
                            variant=variant,
                        )

                        assert decision == replay

                        if observed_count == candidate_count:
                            assert decision.selected_candidate_index is None

                            assert (
                                decision.action_class == StructuralActionClass.COMPLETE
                            )

                        else:
                            selected = decision.selected_candidate_index

                            assert selected is not None
                            assert 0 <= selected < candidate_count
                            assert selected not in observations


def test_a_and_b_orientation_symmetry_exhaustively():
    for candidate_count in range(
        2,
        8,
    ):
        universe = tuple(range(candidate_count))

        for observed_count in range(candidate_count + 1):
            for observed_indices in combinations(
                universe,
                observed_count,
            ):
                for verdicts in product(
                    (
                        "pass",
                        "fail",
                    ),
                    repeat=observed_count,
                ):
                    observations = dict(
                        zip(
                            observed_indices,
                            verdicts,
                            strict=True,
                        )
                    )

                    inverted = invert(observations)

                    for variant in (
                        StructuralPlannerVariant.V2A_BALANCED_FRONTIER_CLOSURE,
                        StructuralPlannerVariant.V2B_CLOSURE_WITH_COVERAGE_FLOOR,
                    ):
                        left = build(
                            candidate_count=candidate_count,
                            observations=observations,
                            variant=variant,
                        )

                        right = build(
                            candidate_count=candidate_count,
                            observations=inverted,
                            variant=variant,
                        )

                        assert (
                            left.selected_candidate_index
                            == right.selected_candidate_index
                        )

                        assert left.action_class == right.action_class

                        assert left.selection_phase == right.selection_phase


def test_boundary_close_is_hard_priority_exhaustively():
    for variant in StructuralPlannerVariant:
        for left_verdict, right_verdict in (
            (
                "pass",
                "fail",
            ),
            (
                "fail",
                "pass",
            ),
        ):
            for left_index in range(
                0,
                7,
            ):
                right_index = left_index + 2

                candidate_count = right_index + 2

                decision = build(
                    candidate_count=candidate_count,
                    observations={
                        left_index: left_verdict,
                        right_index: right_verdict,
                    },
                    variant=variant,
                )

                assert decision.selected_candidate_index == left_index + 1

                assert decision.action_class == StructuralActionClass.BOUNDARY_CLOSE

                assert decision.selection_phase == "HARD_BOUNDARY_CLOSE"

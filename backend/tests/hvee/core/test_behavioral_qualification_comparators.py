from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from hvee.core.behavioral_qualification_comparators import (
    BehavioralQualificationComparatorStrategy,
    run_behavioral_qualification_comparator,
)
from hvee.core.contracts import HveeContractError
from hvee.core.decision import DecisionVerdict
from hvee.core.run05_non_monotonic_benchmark import (
    Run05GlobalStrategy,
    run_run05_global_strategy,
)
from hvee.core.run05_non_monotonic_qualification_design import (
    GLOBAL_BUDGETS,
    RANDOM_BASELINE_SEEDS,
)


PASS = DecisionVerdict.PASS
FAIL = DecisionVerdict.FAIL


def _pattern(
    candidate_count: int,
    kind: str,
) -> tuple[
    DecisionVerdict,
    ...,
]:
    if kind == "all_pass":
        return tuple(PASS for _ in range(candidate_count))

    if kind == "all_fail":
        return tuple(FAIL for _ in range(candidate_count))

    if kind == "left_fail":
        split = max(
            1,
            candidate_count // 3,
        )

        return tuple(
            FAIL if index < split else PASS for index in range(candidate_count)
        )

    if kind == "center_island":
        lower = candidate_count // 3
        upper = candidate_count - lower - 1

        return tuple(
            FAIL if (lower <= index <= upper) else PASS
            for index in range(candidate_count)
        )

    if kind == "alternating":
        return tuple(FAIL if index % 2 else PASS for index in range(candidate_count))

    if kind == "two_islands":
        first_lower = max(
            1,
            candidate_count // 6,
        )

        first_upper = min(
            candidate_count - 1,
            first_lower + 1,
        )

        second_lower = max(
            first_upper + 2,
            (2 * candidate_count) // 3,
        )

        second_upper = min(
            candidate_count - 1,
            second_lower + 1,
        )

        return tuple(
            (
                FAIL
                if (first_lower <= index <= first_upper)
                or (second_lower <= index <= second_upper)
                else PASS
            )
            for index in range(candidate_count)
        )

    raise AssertionError("unknown pattern kind")


def _oracle(
    pattern: tuple[
        DecisionVerdict,
        ...,
    ],
):
    def oracle(
        candidate_index: int,
    ) -> DecisionVerdict:
        return pattern[candidate_index]

    return oracle


def _assert_trace_valid(
    trace,
):
    indices = [candidate_index for candidate_index, _verdict in trace.observations]

    assert len(indices) == len(set(indices))

    assert all(
        0 <= candidate_index < trace.candidate_count for candidate_index in indices
    )

    assert len(trace.observations) <= trace.maximum_evaluations

    assert all(
        verdict
        in {
            PASS.value,
            FAIL.value,
        }
        for _candidate_index, verdict in trace.observations
    )


def test_strategy_enum_is_exactly_frozen_surface():
    assert {item.value for item in BehavioralQualificationComparatorStrategy} == {
        "sequential_grid",
        "seeded_random",
        "farthest_gap_coverage",
        "current_adaptive_v1",
    }


@pytest.mark.parametrize(
    "candidate_count",
    [
        20,
        22,
        26,
        28,
        34,
        36,
    ],
)
def test_sequential_grid_supports_fresh_counts_with_full_budget(
    candidate_count,
):
    pattern = _pattern(
        candidate_count,
        "alternating",
    )

    trace = run_behavioral_qualification_comparator(
        strategy=(BehavioralQualificationComparatorStrategy.SEQUENTIAL_GRID),
        candidate_count=(candidate_count),
        maximum_evaluations=(candidate_count),
        oracle=(_oracle(pattern)),
    )

    assert [index for index, _verdict in trace.observations] == list(
        range(candidate_count)
    )

    assert trace.terminal_status == "grid_exhausted"

    _assert_trace_valid(trace)


@pytest.mark.parametrize(
    "candidate_count",
    [
        20,
        22,
        26,
        28,
        34,
        36,
    ],
)
def test_seeded_random_supports_fresh_counts_without_replacement(
    candidate_count,
):
    pattern = _pattern(
        candidate_count,
        "two_islands",
    )

    first = run_behavioral_qualification_comparator(
        strategy=(BehavioralQualificationComparatorStrategy.SEEDED_RANDOM),
        candidate_count=(candidate_count),
        maximum_evaluations=(candidate_count),
        oracle=(_oracle(pattern)),
        seed=572942816318795013,
    )

    second = run_behavioral_qualification_comparator(
        strategy=(BehavioralQualificationComparatorStrategy.SEEDED_RANDOM),
        candidate_count=(candidate_count),
        maximum_evaluations=(candidate_count),
        oracle=(_oracle(pattern)),
        seed=572942816318795013,
    )

    assert first == second

    assert len(first.observations) == candidate_count

    assert first.terminal_status == "grid_exhausted"

    _assert_trace_valid(first)


@pytest.mark.parametrize(
    "candidate_count",
    [
        20,
        22,
        26,
        28,
        34,
        36,
    ],
)
def test_farthest_gap_supports_fresh_counts_with_full_coverage(
    candidate_count,
):
    pattern = _pattern(
        candidate_count,
        "center_island",
    )

    trace = run_behavioral_qualification_comparator(
        strategy=(BehavioralQualificationComparatorStrategy.FARTHEST_GAP_COVERAGE),
        candidate_count=(candidate_count),
        maximum_evaluations=(candidate_count),
        oracle=(_oracle(pattern)),
    )

    indices = {index for index, _verdict in trace.observations}

    assert indices == set(range(candidate_count))

    assert trace.terminal_status == "grid_exhausted"

    _assert_trace_valid(trace)


@pytest.mark.parametrize(
    "candidate_count",
    [
        20,
        22,
        26,
        28,
        34,
        36,
    ],
)
def test_current_adaptive_v1_supports_fresh_counts_deterministically(
    candidate_count,
):
    pattern = _pattern(
        candidate_count,
        "two_islands",
    )

    first = run_behavioral_qualification_comparator(
        strategy=(BehavioralQualificationComparatorStrategy.CURRENT_ADAPTIVE_V1),
        candidate_count=(candidate_count),
        maximum_evaluations=(candidate_count),
        oracle=(_oracle(pattern)),
    )

    second = run_behavioral_qualification_comparator(
        strategy=(BehavioralQualificationComparatorStrategy.CURRENT_ADAPTIVE_V1),
        candidate_count=(candidate_count),
        maximum_evaluations=(candidate_count),
        oracle=(_oracle(pattern)),
    )

    assert first == second

    _assert_trace_valid(first)


def test_seeded_random_requires_seed():
    with pytest.raises(HveeContractError):
        run_behavioral_qualification_comparator(
            strategy=(BehavioralQualificationComparatorStrategy.SEEDED_RANDOM),
            candidate_count=20,
            maximum_evaluations=10,
            oracle=lambda _index: PASS,
        )


def test_non_random_strategy_rejects_seed():
    with pytest.raises(HveeContractError):
        run_behavioral_qualification_comparator(
            strategy=(BehavioralQualificationComparatorStrategy.SEQUENTIAL_GRID),
            candidate_count=20,
            maximum_evaluations=10,
            oracle=lambda _index: PASS,
            seed=7,
        )


@pytest.mark.parametrize(
    "candidate_count,maximum_evaluations",
    [
        (True, 1),
        (1, 1),
        (20, True),
        (20, 0),
        (20, 21),
    ],
)
def test_invalid_budget_surface_fails_closed(
    candidate_count,
    maximum_evaluations,
):
    with pytest.raises(HveeContractError):
        run_behavioral_qualification_comparator(
            strategy=(BehavioralQualificationComparatorStrategy.SEQUENTIAL_GRID),
            candidate_count=(candidate_count),
            maximum_evaluations=(maximum_evaluations),
            oracle=lambda _index: PASS,
        )


def test_raw_string_strategy_fails_closed():
    with pytest.raises(HveeContractError):
        run_behavioral_qualification_comparator(
            strategy="sequential_grid",
            candidate_count=20,
            maximum_evaluations=20,
            oracle=lambda _index: PASS,
        )


def test_oracle_must_return_strict_decision_verdict():
    with pytest.raises(HveeContractError):
        run_behavioral_qualification_comparator(
            strategy=(BehavioralQualificationComparatorStrategy.SEQUENTIAL_GRID),
            candidate_count=20,
            maximum_evaluations=20,
            oracle=lambda _index: "pass",
        )


def test_partial_budget_terminal_semantics_are_preserved():
    for strategy in (
        BehavioralQualificationComparatorStrategy.SEQUENTIAL_GRID,
        BehavioralQualificationComparatorStrategy.SEEDED_RANDOM,
        BehavioralQualificationComparatorStrategy.FARTHEST_GAP_COVERAGE,
    ):
        trace = run_behavioral_qualification_comparator(
            strategy=strategy,
            candidate_count=20,
            maximum_evaluations=7,
            oracle=lambda _index: PASS,
            seed=(
                11
                if strategy is BehavioralQualificationComparatorStrategy.SEEDED_RANDOM
                else None
            ),
        )

        assert trace.evaluation_count == 7

        assert trace.terminal_status == "budget_exhausted"


def _compare_reference_trace(
    *,
    new_trace,
    old_trace,
):
    assert new_trace.strategy == old_trace.strategy

    assert new_trace.candidate_count == old_trace.candidate_count

    assert new_trace.maximum_evaluations == old_trace.maximum_evaluations

    assert new_trace.observations == old_trace.observations

    assert new_trace.terminal_status == old_trace.terminal_status

    assert new_trace.seed == old_trace.seed


def test_exact_equivalence_to_frozen_run05_nonrandom_strategies():
    mapping = (
        (
            BehavioralQualificationComparatorStrategy.SEQUENTIAL_GRID,
            Run05GlobalStrategy.SEQUENTIAL_GRID,
        ),
        (
            BehavioralQualificationComparatorStrategy.FARTHEST_GAP_COVERAGE,
            Run05GlobalStrategy.FARTHEST_GAP_COVERAGE,
        ),
        (
            BehavioralQualificationComparatorStrategy.CURRENT_ADAPTIVE_V1,
            Run05GlobalStrategy.CURRENT_ADAPTIVE_V1,
        ),
    )

    pattern_kinds = (
        "all_pass",
        "all_fail",
        "left_fail",
        "center_island",
        "alternating",
        "two_islands",
    )

    comparison_count = 0

    for candidate_count, budgets in sorted(GLOBAL_BUDGETS.items()):
        for budget in budgets:
            for pattern_kind in pattern_kinds:
                pattern = _pattern(
                    candidate_count,
                    pattern_kind,
                )

                oracle = _oracle(pattern)

                for new_strategy, old_strategy in mapping:
                    new_trace = run_behavioral_qualification_comparator(
                        strategy=(new_strategy),
                        candidate_count=(candidate_count),
                        maximum_evaluations=(budget),
                        oracle=oracle,
                    )

                    old_trace = run_run05_global_strategy(
                        strategy=(old_strategy),
                        candidate_count=(candidate_count),
                        maximum_evaluations=(budget),
                        oracle=oracle,
                    )

                    _compare_reference_trace(
                        new_trace=(new_trace),
                        old_trace=(old_trace),
                    )

                    comparison_count += 1

    assert comparison_count > 0


def test_exact_equivalence_to_frozen_run05_seeded_random():
    comparison_count = 0

    for candidate_count, budgets in sorted(GLOBAL_BUDGETS.items()):
        pattern = _pattern(
            candidate_count,
            "two_islands",
        )

        oracle = _oracle(pattern)

        for budget in budgets:
            for seed in RANDOM_BASELINE_SEEDS:
                new_trace = run_behavioral_qualification_comparator(
                    strategy=(BehavioralQualificationComparatorStrategy.SEEDED_RANDOM),
                    candidate_count=(candidate_count),
                    maximum_evaluations=(budget),
                    oracle=oracle,
                    seed=seed,
                )

                old_trace = run_run05_global_strategy(
                    strategy=(Run05GlobalStrategy.SEEDED_RANDOM),
                    candidate_count=(candidate_count),
                    maximum_evaluations=(budget),
                    oracle=oracle,
                    seed=seed,
                )

                _compare_reference_trace(
                    new_trace=(new_trace),
                    old_trace=(old_trace),
                )

                comparison_count += 1

    assert comparison_count > 0


def test_generic_adapter_does_not_call_frozen_run05_runner():
    import hvee.core.behavioral_qualification_comparators as module

    source = inspect.getsource(module)

    assert "run_run05_global_strategy" not in source


def test_generic_adapter_has_no_fresh_grid_lock():
    for candidate_count in (
        20,
        22,
        26,
        28,
        34,
        36,
    ):
        trace = run_behavioral_qualification_comparator(
            strategy=(BehavioralQualificationComparatorStrategy.SEQUENTIAL_GRID),
            candidate_count=(candidate_count),
            maximum_evaluations=1,
            oracle=lambda _index: PASS,
        )

        assert trace.evaluation_count == 1


def test_adapter_source_is_exactly_expected_module():
    import hvee.core.behavioral_qualification_comparators as module

    assert Path(module.__file__).name == "behavioral_qualification_comparators.py"

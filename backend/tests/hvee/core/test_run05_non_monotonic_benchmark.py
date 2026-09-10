from __future__ import annotations

import inspect

import pytest

from hvee.core.contracts import HveeContractError
from hvee.core.decision import DecisionVerdict
from hvee.core.run05_non_monotonic_benchmark import (
    Run05DevelopmentVerdict,
    Run05GlobalStrategy,
    Run05IncidentStrategy,
    aggregate_run05_metric,
    calculate_run05_normalized_auc,
    classify_run05_development_verdict,
    run_run05_global_strategy,
    run_run05_incident_strategy,
    score_run05_global_trace,
    score_run05_incident_trace,
)
from hvee.core.run05_non_monotonic_qualification_design import (
    GLOBAL_BUDGETS,
    INCIDENT_ADDITIONAL_BUDGETS,
)


def _oracle(pattern):
    def oracle(index):
        return DecisionVerdict.FAIL if pattern[index] == "F" else DecisionVerdict.PASS

    return oracle


def _counting_oracle(pattern):
    calls = []

    def oracle(index):
        calls.append(index)

        return DecisionVerdict.FAIL if pattern[index] == "F" else DecisionVerdict.PASS

    return (
        oracle,
        calls,
    )


@pytest.mark.parametrize(
    "strategy",
    [
        Run05GlobalStrategy.HETREN_GENERALIZED,
        Run05GlobalStrategy.SEQUENTIAL_GRID,
        Run05GlobalStrategy.FARTHEST_GAP_COVERAGE,
        Run05GlobalStrategy.CURRENT_ADAPTIVE_V1,
    ],
)
def test_global_strategies_execute(strategy):
    trace = run_run05_global_strategy(
        strategy=strategy,
        candidate_count=9,
        maximum_evaluations=5,
        oracle=_oracle("PPFPPPFPP"),
    )

    assert trace.evaluation_count <= 5


def test_seeded_random_is_deterministic():
    first = run_run05_global_strategy(
        strategy=(Run05GlobalStrategy.SEEDED_RANDOM),
        candidate_count=9,
        maximum_evaluations=5,
        oracle=_oracle("PPFPPPFPP"),
        seed=7,
    )

    second = run_run05_global_strategy(
        strategy=(Run05GlobalStrategy.SEEDED_RANDOM),
        candidate_count=9,
        maximum_evaluations=5,
        oracle=_oracle("PPFPPPFPP"),
        seed=7,
    )

    assert first == second


def test_unfrozen_random_seed_rejected():
    with pytest.raises(
        HveeContractError,
        match="frozen",
    ):
        run_run05_global_strategy(
            strategy=(Run05GlobalStrategy.SEEDED_RANDOM),
            candidate_count=9,
            maximum_evaluations=5,
            oracle=_oracle("PPFPPPFPP"),
            seed=999,
        )


def test_nonfrozen_global_budget_rejected():
    with pytest.raises(
        HveeContractError,
        match="frozen",
    ):
        run_run05_global_strategy(
            strategy=(Run05GlobalStrategy.SEQUENTIAL_GRID),
            candidate_count=17,
            maximum_evaluations=5,
            oracle=_oracle("PPFPPPFPPPFPPPFPP"),
        )


def test_current_adaptive_can_stop_before_budget():
    trace = run_run05_global_strategy(
        strategy=(Run05GlobalStrategy.CURRENT_ADAPTIVE_V1),
        candidate_count=9,
        maximum_evaluations=9,
        oracle=_oracle("PPPFFFPPP"),
    )

    assert trace.evaluation_count < 9

    assert trace.terminal_status == "boundary_bracketed"


def test_generalized_hetren_continues_after_first_boundary():
    trace = run_run05_global_strategy(
        strategy=(Run05GlobalStrategy.HETREN_GENERALIZED),
        candidate_count=9,
        maximum_evaluations=9,
        oracle=_oracle("PPFPPPFPP"),
    )

    assert trace.evaluation_count == 9

    assert trace.terminal_status == "grid_exhausted"


def test_farthest_gap_is_deterministic():
    first = run_run05_global_strategy(
        strategy=(Run05GlobalStrategy.FARTHEST_GAP_COVERAGE),
        candidate_count=9,
        maximum_evaluations=6,
        oracle=_oracle("PPFPPPFPP"),
    )

    second = run_run05_global_strategy(
        strategy=(Run05GlobalStrategy.FARTHEST_GAP_COVERAGE),
        candidate_count=9,
        maximum_evaluations=6,
        oracle=_oracle("PPFPPPFPP"),
    )

    assert first == second


@pytest.mark.parametrize(
    "strategy",
    [
        Run05IncidentStrategy.HETREN_GENERALIZED,
        Run05IncidentStrategy.SYMMETRIC_LINEAR_EXPANSION,
        Run05IncidentStrategy.BIDIRECTIONAL_EXPONENTIAL_BISECTION,
        Run05IncidentStrategy.EXISTING_NEIGHBORHOOD_ORDERED,
    ],
)
def test_incident_strategies_execute(strategy):
    trace = run_run05_incident_strategy(
        strategy=strategy,
        candidate_count=9,
        incident_index=4,
        maximum_additional_evaluations=8,
        oracle=_oracle("PPPFFFPPP"),
    )

    assert trace.evaluation_count <= 8

    assert trace.incident_index == 4


@pytest.mark.parametrize(
    "strategy",
    list(Run05IncidentStrategy),
)
def test_incident_anchor_is_not_requeried_or_charged(
    strategy,
):
    oracle, calls = _counting_oracle("PPPFFFPPP")

    trace = run_run05_incident_strategy(
        strategy=strategy,
        candidate_count=9,
        incident_index=4,
        maximum_additional_evaluations=8,
        oracle=oracle,
    )

    assert 4 not in calls

    assert len(calls) == trace.evaluation_count


def test_hetren_incident_stops_at_exact_region():
    trace = run_run05_incident_strategy(
        strategy=(Run05IncidentStrategy.HETREN_GENERALIZED),
        candidate_count=9,
        incident_index=4,
        maximum_additional_evaluations=8,
        oracle=_oracle("PPPFFFPPP"),
    )

    assert trace.evaluation_count == 4

    assert trace.terminal_status == "incident_region_characterized"


def test_symmetric_linear_order():
    trace = run_run05_incident_strategy(
        strategy=(Run05IncidentStrategy.SYMMETRIC_LINEAR_EXPANSION),
        candidate_count=9,
        incident_index=4,
        maximum_additional_evaluations=4,
        oracle=_oracle("PPPFFFPPP"),
    )

    assert [
        index
        for (
            index,
            _verdict,
        ) in trace.observations
    ] == [
        3,
        5,
        2,
        6,
    ]


def test_existing_neighborhood_uses_native_nested_candidate_index():
    trace = run_run05_incident_strategy(
        strategy=(Run05IncidentStrategy.EXISTING_NEIGHBORHOOD_ORDERED),
        candidate_count=9,
        incident_index=4,
        maximum_additional_evaluations=4,
        oracle=_oracle("PPPFFFPPP"),
    )

    assert [
        index
        for (
            index,
            _verdict,
        ) in trace.observations
    ] == [
        3,
        5,
        2,
        6,
    ]


def test_exponential_baseline_characterizes_simple_incident():
    trace = run_run05_incident_strategy(
        strategy=(Run05IncidentStrategy.BIDIRECTIONAL_EXPONENTIAL_BISECTION),
        candidate_count=9,
        incident_index=4,
        maximum_additional_evaluations=8,
        oracle=_oracle("PPPFFFPPP"),
    )

    assert trace.terminal_status == "incident_region_characterized"

    score = score_run05_incident_trace(
        trace=trace,
        pattern="PPPFFFPPP",
    )

    assert score["incident_region_exactness"] == 1.0


def test_global_scorer_first_failure():
    trace = run_run05_global_strategy(
        strategy=(Run05GlobalStrategy.SEQUENTIAL_GRID),
        candidate_count=9,
        maximum_evaluations=5,
        oracle=_oracle("PPFPPPFPP"),
    )

    score = score_run05_global_trace(
        trace=trace,
        pattern="PPFPPPFPP",
    )

    assert score["failure_discovery_rate"] == 1.0

    assert score["experiments_to_first_failure"] == 3.0


def test_global_non_discovery_censored_budget_plus_one():
    trace = run_run05_global_strategy(
        strategy=(Run05GlobalStrategy.SEQUENTIAL_GRID),
        candidate_count=9,
        maximum_evaluations=2,
        oracle=_oracle("PPFPPPFPP"),
    )

    score = score_run05_global_trace(
        trace=trace,
        pattern="PPFPPPFPP",
    )

    assert score["failure_discovery_rate"] == 0.0

    assert score["experiments_to_first_failure"] == 3.0


def test_full_grid_has_complete_region_and_boundary_recall():
    trace = run_run05_global_strategy(
        strategy=(Run05GlobalStrategy.FARTHEST_GAP_COVERAGE),
        candidate_count=9,
        maximum_evaluations=9,
        oracle=_oracle("PPFPPPFPP"),
    )

    score = score_run05_global_trace(
        trace=trace,
        pattern="PPFPPPFPP",
    )

    assert score["failure_island_recall"] == 1.0

    assert score["boundary_recall"] == 1.0


def test_incident_exactness_cost():
    trace = run_run05_incident_strategy(
        strategy=(Run05IncidentStrategy.SYMMETRIC_LINEAR_EXPANSION),
        candidate_count=9,
        incident_index=4,
        maximum_additional_evaluations=8,
        oracle=_oracle("PPPFFFPPP"),
    )

    score = score_run05_incident_trace(
        trace=trace,
        pattern="PPPFFFPPP",
    )

    assert score["incident_region_exactness"] == 1.0

    assert score["additional_evaluations_to_exact_characterization"] == 4.0


def test_incident_nonexact_censored_budget_plus_one():
    trace = run_run05_incident_strategy(
        strategy=(Run05IncidentStrategy.SYMMETRIC_LINEAR_EXPANSION),
        candidate_count=9,
        incident_index=4,
        maximum_additional_evaluations=2,
        oracle=_oracle("PPPFFFPPP"),
    )

    score = score_run05_incident_trace(
        trace=trace,
        pattern="PPPFFFPPP",
    )

    assert score["incident_region_exactness"] == 0.0

    assert score["additional_evaluations_to_exact_characterization"] == 3.0


def test_incident_scorer_rejects_nonfailing_anchor():
    trace = run_run05_incident_strategy(
        strategy=(Run05IncidentStrategy.SYMMETRIC_LINEAR_EXPANSION),
        candidate_count=9,
        incident_index=4,
        maximum_additional_evaluations=2,
        oracle=_oracle("PPPPFPPPP"),
    )

    with pytest.raises(
        HveeContractError,
        match="true failing",
    ):
        score_run05_incident_trace(
            trace=trace,
            pattern="PPPPPPPPP",
        )


def test_scorer_detects_ground_truth_mismatch():
    trace = run_run05_global_strategy(
        strategy=(Run05GlobalStrategy.SEQUENTIAL_GRID),
        candidate_count=9,
        maximum_evaluations=3,
        oracle=_oracle("PPFPPPFPP"),
    )

    with pytest.raises(
        HveeContractError,
        match="ground truth",
    ):
        score_run05_global_trace(
            trace=trace,
            pattern="FFFFFFFFF",
        )


def test_global_auc_exact_manual_value():
    auc = calculate_run05_normalized_auc(
        candidate_count=9,
        budgets=list(GLOBAL_BUDGETS[9]),
        values=[
            0.0,
            0.0,
            0.0,
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
        ],
        incident=False,
    )

    assert auc == pytest.approx(0.5)


def test_incident_full_success_auc():
    budgets = list(INCIDENT_ADDITIONAL_BUDGETS[9])

    auc = calculate_run05_normalized_auc(
        candidate_count=9,
        budgets=budgets,
        values=[1.0 for _budget in budgets],
        incident=True,
    )

    assert auc == pytest.approx(0.9375)


def test_auc_rejects_nonfrozen_budget_sequence():
    with pytest.raises(
        HveeContractError,
        match="frozen",
    ):
        calculate_run05_normalized_auc(
            candidate_count=9,
            budgets=[
                1,
                2,
            ],
            values=[
                0.0,
                1.0,
            ],
            incident=False,
        )


def test_aggregate_is_arithmetic_mean():
    assert (
        aggregate_run05_metric(
            [
                0.0,
                0.5,
                1.0,
            ]
        )
        == 0.5
    )


def _global_metrics(
    discovery,
    auc,
    cost,
):
    return {
        "failure_discovery_rate": (discovery),
        "normalized_failure_discovery_auc_over_budget": (auc),
        "experiments_to_first_failure": (cost),
    }


def test_verdict_superior():
    result = classify_run05_development_verdict(
        task_key="global_discovery",
        hetren_metrics=(
            _global_metrics(
                1.0,
                0.8,
                2.0,
            )
        ),
        baseline_metrics={
            "a": (
                _global_metrics(
                    1.0,
                    0.7,
                    3.0,
                )
            ),
            "b": (
                _global_metrics(
                    0.9,
                    0.75,
                    2.5,
                )
            ),
        },
    )

    assert result["verdict"] == Run05DevelopmentVerdict.SUPERIOR.value


def test_verdict_tie():
    metrics = _global_metrics(
        1.0,
        0.8,
        2.0,
    )

    result = classify_run05_development_verdict(
        task_key="global_discovery",
        hetren_metrics=metrics,
        baseline_metrics={
            "baseline": dict(metrics),
        },
    )

    assert result["verdict"] == Run05DevelopmentVerdict.TIE.value


def test_verdict_mixed():
    result = classify_run05_development_verdict(
        task_key="global_discovery",
        hetren_metrics=(
            _global_metrics(
                1.0,
                0.7,
                4.0,
            )
        ),
        baseline_metrics={
            "baseline": (
                _global_metrics(
                    0.9,
                    0.8,
                    3.0,
                )
            ),
        },
    )

    assert result["verdict"] == Run05DevelopmentVerdict.MIXED.value


def test_verdict_inferior():
    result = classify_run05_development_verdict(
        task_key="global_discovery",
        hetren_metrics=(
            _global_metrics(
                0.8,
                0.7,
                4.0,
            )
        ),
        baseline_metrics={
            "baseline": (
                _global_metrics(
                    0.9,
                    0.8,
                    3.0,
                )
            ),
        },
    )

    assert result["verdict"] == Run05DevelopmentVerdict.INFERIOR.value


def test_per_metric_strongest_baseline_envelope():
    result = classify_run05_development_verdict(
        task_key="global_discovery",
        hetren_metrics=(
            _global_metrics(
                1.0,
                0.8,
                2.0,
            )
        ),
        baseline_metrics={
            "discovery_best": (
                _global_metrics(
                    1.0,
                    0.6,
                    5.0,
                )
            ),
            "auc_best": (
                _global_metrics(
                    0.8,
                    0.8,
                    4.0,
                )
            ),
            "cost_best": (
                _global_metrics(
                    0.7,
                    0.5,
                    2.0,
                )
            ),
        },
    )

    assert result["verdict"] == Run05DevelopmentVerdict.TIE.value


def test_verdict_remains_development_only():
    metrics = _global_metrics(
        1.0,
        0.8,
        2.0,
    )

    result = classify_run05_development_verdict(
        task_key="global_discovery",
        hetren_metrics=metrics,
        baseline_metrics={
            "baseline": dict(metrics),
        },
    )

    boundary = result["evidence_boundary"]

    assert boundary["development_result_only"] is True

    assert boundary["statistical_generalization_established"] is False

    assert boundary["real_ai_generalization_established"] is False

    assert boundary["behavioral_performance_qualified"] is False


def test_strategy_interfaces_do_not_receive_hidden_pattern():
    global_parameters = set(inspect.signature(run_run05_global_strategy).parameters)

    incident_parameters = set(inspect.signature(run_run05_incident_strategy).parameters)

    assert "pattern" not in global_parameters

    assert "pattern" not in incident_parameters

    assert "problem_key" not in global_parameters

    assert "problem_key" not in incident_parameters

    assert "oracle" in global_parameters

    assert "oracle" in incident_parameters

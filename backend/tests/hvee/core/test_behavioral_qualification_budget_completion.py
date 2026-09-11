from __future__ import annotations

from dataclasses import replace
import inspect

import pytest

from hvee.core.behavioral_multi_objective_qualification import (
    FreshBehavioralQualificationStrategy,
    FreshQualificationProblem,
    _make_trace,
    run_fresh_behavioral_qualification_strategy,
    score_fresh_behavioral_qualification_trace,
)
from hvee.core.behavioral_qualification_budget_completion import (
    COMPLETION_POLICY,
    complete_fresh_behavioral_qualification_trace_budget,
    run_fresh_behavioral_qualification_strategy_with_budget_completion,
    select_neutral_lowest_unobserved_completion_indices,
)
from hvee.core.contracts import HveeContractError
from hvee.core.decision import DecisionVerdict


def _problem(
    pattern="PPFFPPFPPFFP",
):
    return FreshQualificationProblem(
        problem_key="synthetic:budget-completion",
        partition="synthetic",
        namespace="HETREN_SYNTHETIC_BUDGET_COMPLETION",
        candidate_count=len(pattern),
        topology_stratum="SYNTHETIC",
        ordinal=0,
        pattern=pattern,
        topology_sha256=("a" * 64),
        problem_sha256=("b" * 64),
    )


def test_completion_policy_identity_is_frozen():
    assert COMPLETION_POLICY == "NEUTRAL_LOWEST_UNOBSERVED_BUDGET_COMPLETION_V1"


def test_lowest_unobserved_selection_is_exact():
    result = select_neutral_lowest_unobserved_completion_indices(
        candidate_count=10,
        observed_indices=(
            3,
            0,
            8,
        ),
        maximum_evaluations=7,
    )

    assert result == (
        1,
        2,
        4,
        5,
    )


def test_selection_helper_has_no_verdict_or_pattern_input():
    signature = inspect.signature(select_neutral_lowest_unobserved_completion_indices)

    assert list(signature.parameters) == [
        "candidate_count",
        "observed_indices",
        "maximum_evaluations",
    ]


def test_zero_completion_steps_are_allowed():
    result = select_neutral_lowest_unobserved_completion_indices(
        candidate_count=5,
        observed_indices=(
            0,
            1,
            2,
        ),
        maximum_evaluations=3,
    )

    assert result == ()


@pytest.mark.parametrize(
    "candidate_count,observed_indices,maximum_evaluations",
    [
        (
            True,
            (),
            1,
        ),
        (
            0,
            (),
            1,
        ),
        (
            5,
            [0],
            3,
        ),
        (
            5,
            (
                0,
                0,
            ),
            3,
        ),
        (
            5,
            (-1,),
            3,
        ),
        (
            5,
            (5,),
            3,
        ),
        (
            5,
            (
                0,
                1,
                2,
                3,
            ),
            3,
        ),
        (
            5,
            (),
            0,
        ),
        (
            5,
            (),
            6,
        ),
    ],
)
def test_selection_contract_fails_closed(
    candidate_count,
    observed_indices,
    maximum_evaluations,
):
    with pytest.raises(HveeContractError):
        select_neutral_lowest_unobserved_completion_indices(
            candidate_count=(candidate_count),
            observed_indices=(observed_indices),
            maximum_evaluations=(maximum_evaluations),
        )


def test_manual_early_terminal_trace_is_completed_exactly():
    problem = _problem("PPFFPPFPP")

    native = _make_trace(
        strategy=(FreshBehavioralQualificationStrategy.EVIDENCE_GAIN_V1),
        candidate_count=(problem.candidate_count),
        maximum_evaluations=6,
        observations=[
            (
                4,
                DecisionVerdict.PASS,
            ),
            (
                1,
                DecisionVerdict.PASS,
            ),
        ],
        terminal_status="native_terminal",
        seed=None,
    )

    envelope = complete_fresh_behavioral_qualification_trace_budget(
        problem=problem,
        native_trace=native,
    )

    assert envelope.native_trace == native

    assert envelope.native_trace_sha256 == native.sha256

    assert envelope.native_terminal_status == "native_terminal"

    assert envelope.native_evaluation_count == 2

    assert envelope.neutral_completion_indices == (
        0,
        2,
        3,
        5,
    )

    assert envelope.neutral_completion_count == 4

    assert envelope.completed_trace.evaluation_count == 6

    assert envelope.completed_trace.terminal_status == "budget_exhausted"


def test_completion_indices_are_selected_before_outcomes_are_needed():
    first = select_neutral_lowest_unobserved_completion_indices(
        candidate_count=9,
        observed_indices=(
            6,
            2,
        ),
        maximum_evaluations=7,
    )

    second = select_neutral_lowest_unobserved_completion_indices(
        candidate_count=9,
        observed_indices=(
            6,
            2,
        ),
        maximum_evaluations=7,
    )

    assert first == second

    assert first == (
        0,
        1,
        3,
        4,
        5,
    )


@pytest.mark.parametrize(
    "strategy",
    list(FreshBehavioralQualificationStrategy),
)
def test_all_seven_strategies_finish_exact_full_grid_budget(
    strategy,
):
    problem = _problem()

    envelope = run_fresh_behavioral_qualification_strategy_with_budget_completion(
        problem=problem,
        strategy=strategy,
        maximum_evaluations=(problem.candidate_count),
        seed=(
            123456
            if strategy is FreshBehavioralQualificationStrategy.SEEDED_RANDOM
            else None
        ),
    )

    assert envelope.completed_trace.evaluation_count == problem.candidate_count

    assert envelope.completed_trace.maximum_evaluations == problem.candidate_count

    assert envelope.completed_trace.terminal_status == "grid_exhausted"

    indices = [
        candidate_index
        for candidate_index, _verdict in envelope.completed_trace.observations
    ]

    assert len(indices) == problem.candidate_count

    assert len(set(indices)) == problem.candidate_count

    assert set(indices) == set(range(problem.candidate_count))


@pytest.mark.parametrize(
    "strategy",
    list(FreshBehavioralQualificationStrategy),
)
def test_native_trace_is_exactly_preserved_for_all_seven_strategies(
    strategy,
):
    problem = _problem()

    seed = (
        999 if strategy is FreshBehavioralQualificationStrategy.SEEDED_RANDOM else None
    )

    direct_native = run_fresh_behavioral_qualification_strategy(
        problem=problem,
        strategy=strategy,
        maximum_evaluations=(problem.candidate_count),
        seed=seed,
    )

    envelope = run_fresh_behavioral_qualification_strategy_with_budget_completion(
        problem=problem,
        strategy=strategy,
        maximum_evaluations=(problem.candidate_count),
        seed=seed,
    )

    assert envelope.native_trace == direct_native

    assert envelope.native_trace_sha256 == direct_native.sha256

    assert envelope.native_terminal_status == direct_native.terminal_status

    assert envelope.native_evaluation_count == direct_native.evaluation_count


@pytest.mark.parametrize(
    "strategy",
    list(FreshBehavioralQualificationStrategy),
)
def test_completed_full_grid_trace_satisfies_frozen_score_guardrails(
    strategy,
):
    problem = _problem("PFFPPFPFPFFP")

    envelope = run_fresh_behavioral_qualification_strategy_with_budget_completion(
        problem=problem,
        strategy=strategy,
        maximum_evaluations=(problem.candidate_count),
        seed=(
            7654321
            if strategy is FreshBehavioralQualificationStrategy.SEEDED_RANDOM
            else None
        ),
    )

    score = score_fresh_behavioral_qualification_trace(
        problem=problem,
        trace=(envelope.completed_trace),
    )

    assert score.evaluation_count == problem.candidate_count

    assert score.duplicate_evaluation_count == 0

    assert score.full_budget_failure_region_recall == 1.0

    assert score.full_budget_boundary_recall == 1.0


@pytest.mark.parametrize(
    "strategy",
    list(FreshBehavioralQualificationStrategy),
)
def test_budget_completion_wrapper_replays_exactly(
    strategy,
):
    problem = _problem()

    seed = (
        111222333
        if strategy is FreshBehavioralQualificationStrategy.SEEDED_RANDOM
        else None
    )

    first = run_fresh_behavioral_qualification_strategy_with_budget_completion(
        problem=problem,
        strategy=strategy,
        maximum_evaluations=(problem.candidate_count),
        seed=seed,
    )

    second = run_fresh_behavioral_qualification_strategy_with_budget_completion(
        problem=problem,
        strategy=strategy,
        maximum_evaluations=(problem.candidate_count),
        seed=seed,
    )

    assert first == second


def test_partial_budget_completion_uses_budget_exhausted_terminal_status():
    problem = _problem()

    envelope = run_fresh_behavioral_qualification_strategy_with_budget_completion(
        problem=problem,
        strategy=(FreshBehavioralQualificationStrategy.EVIDENCE_GAIN_V1),
        maximum_evaluations=7,
    )

    assert envelope.completed_trace.evaluation_count == 7

    assert envelope.completed_trace.terminal_status == "budget_exhausted"


def test_native_trace_identity_tamper_is_rejected():
    problem = _problem()

    native = run_fresh_behavioral_qualification_strategy(
        problem=problem,
        strategy=(FreshBehavioralQualificationStrategy.SEQUENTIAL_GRID),
        maximum_evaluations=5,
    )

    tampered = replace(
        native,
        sha256=("f" * 64),
    )

    with pytest.raises(HveeContractError):
        complete_fresh_behavioral_qualification_trace_budget(
            problem=problem,
            native_trace=tampered,
        )


def test_native_trace_ground_truth_tamper_is_rejected():
    problem = _problem()

    native = _make_trace(
        strategy=(FreshBehavioralQualificationStrategy.SEQUENTIAL_GRID),
        candidate_count=(problem.candidate_count),
        maximum_evaluations=3,
        observations=[
            (
                0,
                DecisionVerdict.FAIL,
            ),
        ],
        terminal_status="synthetic",
        seed=None,
    )

    with pytest.raises(HveeContractError):
        complete_fresh_behavioral_qualification_trace_budget(
            problem=problem,
            native_trace=native,
        )


def test_adapter_does_not_change_native_strategy_runner():
    import hvee.core.behavioral_qualification_budget_completion as module

    source = inspect.getsource(module)

    assert "run_fresh_behavioral_qualification_strategy(" in source

    assert "build_behavioral_multi_objective" not in source

    assert "build_behavioral_evidence_gain" not in source

    assert "build_behavioral_multi_region" not in source


def test_completion_selection_does_not_accept_verdicts_or_pattern():
    signature = inspect.signature(select_neutral_lowest_unobserved_completion_indices)

    names = set(signature.parameters)

    assert "verdict" not in names
    assert "verdicts" not in names
    assert "pattern" not in names
    assert "topology" not in names


def test_envelope_completion_count_matches_index_count():
    problem = _problem()

    envelope = run_fresh_behavioral_qualification_strategy_with_budget_completion(
        problem=problem,
        strategy=(FreshBehavioralQualificationStrategy.HETREN_MULTI_OBJECTIVE),
    )

    assert envelope.neutral_completion_count == len(envelope.neutral_completion_indices)

    assert (
        envelope.native_evaluation_count + envelope.neutral_completion_count
        == envelope.maximum_evaluations
    )

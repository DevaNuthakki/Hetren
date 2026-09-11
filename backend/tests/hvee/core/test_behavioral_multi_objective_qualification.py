from __future__ import annotations

from dataclasses import replace

import pytest

from hvee.core.behavioral_multi_objective_qualification import (
    BASE_TOPOLOGY_FAMILIES,
    DEVELOPMENT_CANDIDATE_COUNTS,
    FreshBehavioralQualificationStrategy,
    FreshQualificationPartition,
    FreshQualificationProblem,
    PROBLEMS_PER_STRATUM,
    QUALIFICATION_CANDIDATE_COUNTS,
    TOPOLOGY_STRATA,
    _complement_pattern,
    _generate_partition_problems,
    _maximum_boundary_count_by_prefix,
    _true_boundaries,
    build_fresh_behavioral_qualification_corpus,
    run_fresh_behavioral_qualification_strategy,
    score_fresh_behavioral_qualification_trace,
    verify_fresh_behavioral_qualification_corpus,
)
from hvee.core.contracts import HveeContractError


def _test_problem(
    pattern="PPFFPPPFF",
):
    candidate_count = len(pattern)

    return FreshQualificationProblem(
        problem_key=("test:problem"),
        partition=("synthetic_test"),
        namespace=("HETREN_TEST_ONLY_NAMESPACE"),
        candidate_count=(candidate_count),
        topology_stratum=("TEST"),
        ordinal=0,
        pattern=(pattern),
        topology_sha256=("0" * 64),
        problem_sha256=("1" * 64),
    )


def test_effective_design_constants_are_erratum_values():
    assert PROBLEMS_PER_STRATUM == 19

    assert DEVELOPMENT_CANDIDATE_COUNTS == (
        20,
        26,
        34,
    )

    assert QUALIFICATION_CANDIDATE_COUNTS == (
        22,
        28,
        36,
    )

    assert len(BASE_TOPOLOGY_FAMILIES) == 6

    assert len(TOPOLOGY_STRATA) == 12


def test_test_namespace_generates_full_effective_development_shape():
    problems = _generate_partition_problems(
        partition=("synthetic_test_development"),
        namespace=("HETREN_TEST_ONLY_DEVELOPMENT"),
        candidate_counts=(DEVELOPMENT_CANDIDATE_COUNTS),
        problems_per_stratum=(PROBLEMS_PER_STRATUM),
    )

    assert len(problems) == 684

    grouped = {}

    for problem in problems:
        key = (
            problem.candidate_count,
            problem.topology_stratum,
        )

        grouped.setdefault(
            key,
            set(),
        ).add(problem.topology_sha256)

    assert len(grouped) == 36

    assert all(len(values) == 19 for values in grouped.values())


def test_test_namespace_generation_is_deterministic():
    first = _generate_partition_problems(
        partition="synthetic",
        namespace="HETREN_TEST_DETERMINISM",
        candidate_counts=(20,),
        problems_per_stratum=19,
    )

    second = _generate_partition_problems(
        partition="synthetic",
        namespace="HETREN_TEST_DETERMINISM",
        candidate_counts=(20,),
        problems_per_stratum=19,
    )

    assert first == second


def test_complement_strata_are_exact_pattern_complements():
    problems = _generate_partition_problems(
        partition="synthetic",
        namespace="HETREN_TEST_COMPLEMENTS",
        candidate_counts=(20,),
        problems_per_stratum=19,
    )

    lookup = {
        (
            problem.topology_stratum,
            problem.ordinal,
        ): problem
        for problem in problems
    }

    for family in BASE_TOPOLOGY_FAMILIES:
        for ordinal in range(19):
            base = lookup[
                (
                    family,
                    ordinal,
                )
            ]

            complement = lookup[
                (
                    family + "_COMPLEMENT",
                    ordinal,
                )
            ]

            assert complement.pattern == _complement_pattern(base.pattern)


def test_every_test_generated_pattern_is_nonconstant():
    problems = _generate_partition_problems(
        partition="synthetic",
        namespace="HETREN_TEST_NONCONSTANT",
        candidate_counts=(
            20,
            26,
            34,
        ),
        problems_per_stratum=19,
    )

    assert all(
        "P" in problem.pattern and "F" in problem.pattern for problem in problems
    )


def test_qualification_materialization_requires_explicit_authorization():
    with pytest.raises(HveeContractError):
        build_fresh_behavioral_qualification_corpus(
            partition=(FreshQualificationPartition.QUALIFICATION)
        )


def test_development_rejects_qualification_authorization_flag():
    with pytest.raises(HveeContractError):
        build_fresh_behavioral_qualification_corpus(
            partition=(FreshQualificationPartition.DEVELOPMENT),
            qualification_open_authorized=True,
        )


def test_official_development_builder_has_effective_684_shape():
    problems = build_fresh_behavioral_qualification_corpus(
        partition=(FreshQualificationPartition.DEVELOPMENT)
    )

    assert len(problems) == 684

    assert (
        verify_fresh_behavioral_qualification_corpus(
            problems=(problems),
            partition=(FreshQualificationPartition.DEVELOPMENT),
        )
        is True
    )


def test_corpus_verifier_rejects_problem_identity_tamper():
    problems = list(
        build_fresh_behavioral_qualification_corpus(
            partition=(FreshQualificationPartition.DEVELOPMENT)
        )
    )

    problems[0] = replace(
        problems[0],
        problem_sha256=("f" * 64),
    )

    assert (
        verify_fresh_behavioral_qualification_corpus(
            problems=tuple(problems),
            partition=(FreshQualificationPartition.DEVELOPMENT),
        )
        is False
    )


@pytest.mark.parametrize(
    "strategy",
    [
        FreshBehavioralQualificationStrategy.SEQUENTIAL_GRID,
        FreshBehavioralQualificationStrategy.FARTHEST_GAP_COVERAGE,
        FreshBehavioralQualificationStrategy.CURRENT_ADAPTIVE_V1,
        FreshBehavioralQualificationStrategy.EVIDENCE_GAIN_V1,
        FreshBehavioralQualificationStrategy.MULTI_REGION_V2_1,
        FreshBehavioralQualificationStrategy.HETREN_MULTI_OBJECTIVE,
    ],
)
def test_deterministic_strategy_replays_exactly(
    strategy,
):
    problem = _test_problem()

    first = run_fresh_behavioral_qualification_strategy(
        problem=(problem),
        strategy=(strategy),
    )

    second = run_fresh_behavioral_qualification_strategy(
        problem=(problem),
        strategy=(strategy),
    )

    assert first == second


def test_seeded_random_replays_exactly_per_seed():
    problem = _test_problem()

    first = run_fresh_behavioral_qualification_strategy(
        problem=(problem),
        strategy=(FreshBehavioralQualificationStrategy.SEEDED_RANDOM),
        seed=918273645,
    )

    second = run_fresh_behavioral_qualification_strategy(
        problem=(problem),
        strategy=(FreshBehavioralQualificationStrategy.SEEDED_RANDOM),
        seed=918273645,
    )

    assert first == second


def test_seeded_random_requires_seed():
    with pytest.raises(HveeContractError):
        run_fresh_behavioral_qualification_strategy(
            problem=(_test_problem()),
            strategy=(FreshBehavioralQualificationStrategy.SEEDED_RANDOM),
        )


def test_non_random_strategy_rejects_seed():
    with pytest.raises(HveeContractError):
        run_fresh_behavioral_qualification_strategy(
            problem=(_test_problem()),
            strategy=(FreshBehavioralQualificationStrategy.EVIDENCE_GAIN_V1),
            seed=1,
        )


@pytest.mark.parametrize(
    "strategy",
    [
        FreshBehavioralQualificationStrategy.SEQUENTIAL_GRID,
        FreshBehavioralQualificationStrategy.FARTHEST_GAP_COVERAGE,
        FreshBehavioralQualificationStrategy.SEEDED_RANDOM,
        FreshBehavioralQualificationStrategy.CURRENT_ADAPTIVE_V1,
        FreshBehavioralQualificationStrategy.EVIDENCE_GAIN_V1,
        FreshBehavioralQualificationStrategy.MULTI_REGION_V2_1,
        FreshBehavioralQualificationStrategy.HETREN_MULTI_OBJECTIVE,
    ],
)
def test_all_strategy_traces_have_unique_valid_candidates(
    strategy,
):
    problem = _test_problem()

    trace = run_fresh_behavioral_qualification_strategy(
        problem=(problem),
        strategy=(strategy),
        seed=(
            111
            if strategy is FreshBehavioralQualificationStrategy.SEEDED_RANDOM
            else None
        ),
    )

    indices = [candidate_index for candidate_index, _verdict in trace.observations]

    assert len(indices) == len(set(indices))

    assert all(
        0 <= candidate_index < problem.candidate_count for candidate_index in indices
    )

    assert trace.evaluation_count <= problem.candidate_count


def test_sequential_full_grid_scores_full_recall():
    problem = _test_problem()

    trace = run_fresh_behavioral_qualification_strategy(
        problem=(problem),
        strategy=(FreshBehavioralQualificationStrategy.SEQUENTIAL_GRID),
    )

    score = score_fresh_behavioral_qualification_trace(
        problem=(problem),
        trace=(trace),
    )

    assert score.full_budget_failure_region_recall == 1.0

    assert score.full_budget_boundary_recall == 1.0

    assert score.duplicate_evaluation_count == 0


@pytest.mark.parametrize(
    "strategy",
    [
        FreshBehavioralQualificationStrategy.SEQUENTIAL_GRID,
        FreshBehavioralQualificationStrategy.FARTHEST_GAP_COVERAGE,
        FreshBehavioralQualificationStrategy.SEEDED_RANDOM,
        FreshBehavioralQualificationStrategy.CURRENT_ADAPTIVE_V1,
        FreshBehavioralQualificationStrategy.EVIDENCE_GAIN_V1,
        FreshBehavioralQualificationStrategy.MULTI_REGION_V2_1,
        FreshBehavioralQualificationStrategy.HETREN_MULTI_OBJECTIVE,
    ],
)
def test_primary_and_secondary_auc_values_are_bounded(
    strategy,
):
    problem = _test_problem("PFFPPFPFP")

    trace = run_fresh_behavioral_qualification_strategy(
        problem=(problem),
        strategy=(strategy),
        seed=(
            55
            if strategy is FreshBehavioralQualificationStrategy.SEEDED_RANDOM
            else None
        ),
    )

    score = score_fresh_behavioral_qualification_trace(
        problem=(problem),
        trace=(trace),
    )

    assert 0.0 <= score.failure_region_recall_auc <= 1.0

    assert 0.0 <= score.boundary_recall_auc <= 1.0

    assert 0.0 <= score.discovery_auc <= 1.0


def test_boundary_maximum_curve_is_monotonic_and_reaches_all_boundaries():
    pattern = "PFFPPFPFP"

    boundaries = _true_boundaries(pattern)

    values = _maximum_boundary_count_by_prefix(
        candidate_count=(len(pattern)),
        boundaries=(boundaries),
    )

    assert values[0] == 0

    assert values[-1] == len(boundaries)

    assert all(
        left <= right
        for left, right in zip(
            values,
            values[1:],
        )
    )


def test_score_rejects_trace_identity_tamper():
    problem = _test_problem()

    trace = run_fresh_behavioral_qualification_strategy(
        problem=(problem),
        strategy=(FreshBehavioralQualificationStrategy.SEQUENTIAL_GRID),
    )

    tampered = replace(
        trace,
        sha256=("f" * 64),
    )

    with pytest.raises(HveeContractError):
        score_fresh_behavioral_qualification_trace(
            problem=(problem),
            trace=(tampered),
        )


def test_score_rejects_verdict_ground_truth_disagreement():
    problem = _test_problem()

    trace = run_fresh_behavioral_qualification_strategy(
        problem=(problem),
        strategy=(FreshBehavioralQualificationStrategy.SEQUENTIAL_GRID),
        maximum_evaluations=1,
    )

    wrong_value = "fail" if trace.observations[0][1] == "pass" else "pass"

    tampered_observations = (
        (
            trace.observations[0][0],
            wrong_value,
        ),
    )

    tampered = replace(
        trace,
        observations=(tampered_observations),
    )

    with pytest.raises(HveeContractError):
        score_fresh_behavioral_qualification_trace(
            problem=(problem),
            trace=(tampered),
        )


def test_partial_trace_is_plateau_scored_without_future_oracle_access():
    problem = _test_problem()

    trace = run_fresh_behavioral_qualification_strategy(
        problem=(problem),
        strategy=(FreshBehavioralQualificationStrategy.SEQUENTIAL_GRID),
        maximum_evaluations=3,
    )

    score = score_fresh_behavioral_qualification_trace(
        problem=(problem),
        trace=(trace),
    )

    assert score.evaluation_count == 3

    assert 0.0 <= score.failure_region_recall_auc <= 1.0


def test_strategy_enum_matches_frozen_program():
    assert {item.value for item in FreshBehavioralQualificationStrategy} == {
        "sealed_hetren_multi_objective_behavioral_engine_v1",
        "farthest_gap_coverage",
        "sequential_grid",
        "behavioral_evidence_gain_planner_v1",
        "behavioral_multi_region_v2_1",
        "seeded_random",
        "current_adaptive_v1",
    }

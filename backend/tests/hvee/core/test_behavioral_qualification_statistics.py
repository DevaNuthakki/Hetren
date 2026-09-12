from __future__ import annotations

from dataclasses import replace
import random

import pytest

from hvee.core.behavioral_qualification_statistics import (
    ALL_PRIMARY_STRATEGIES,
    BOOTSTRAP_RESAMPLES,
    BOOTSTRAP_SEED,
    EXPECTED_PROBLEM_COUNT,
    LOWER_ORDER_STATISTIC_INDEX,
    PRIMARY_COMPARATORS,
    PROBLEMS_PER_STRATUM,
    STRATUM_COUNT,
    SYSTEM_STRATEGY,
    TOPOLOGY_STRATA,
    UPPER_ORDER_STATISTIC_INDEX,
    PrimaryComparatorRelation,
    PrimaryMetricDeltaInterval,
    QualificationPrimaryScore,
    QualificationStatisticalContractError,
    analyze_fresh_qualification_primary_scores,
    classify_primary_comparator_relation,
    classify_qualification_program,
)


QUALIFICATION_COUNTS = (
    22,
    28,
    36,
)


def _metric(
    *,
    name,
    mean=0.0,
    lower=-0.01,
    upper=0.01,
):
    return PrimaryMetricDeltaInterval(
        metric=name,
        mean_delta=mean,
        lower_995=lower,
        upper_995=upper,
    )


def _relation(
    comparator,
    relation,
    *,
    dominated=False,
):
    return PrimaryComparatorRelation(
        comparator=comparator,
        failure_region_recall_auc=(_metric(name=("failure_region_recall_auc"))),
        boundary_recall_auc=(_metric(name=("boundary_recall_auc"))),
        relation=relation,
        statistical_pareto_dominated=(dominated),
    )


def _program_relations(
    relation,
):
    return tuple(
        _relation(
            comparator,
            relation,
        )
        for comparator in PRIMARY_COMPARATORS
    )


def _problem_sha(
    ordinal,
):
    return f"{ordinal:064x}"


def _complete_scores():
    rows = []

    problem_ordinal = 1

    comparator_values = {
        "farthest_gap_coverage": (
            0.40,
            0.40,
        ),
        "sequential_grid": (
            0.42,
            0.43,
        ),
        "behavioral_evidence_gain_planner_v1": (
            0.44,
            0.41,
        ),
        "behavioral_multi_region_v2_1": (
            0.45,
            0.45,
        ),
    }

    for candidate_count in QUALIFICATION_COUNTS:
        for topology_stratum in TOPOLOGY_STRATA:
            for _ in range(PROBLEMS_PER_STRATUM):
                problem_sha = _problem_sha(problem_ordinal)

                problem_ordinal += 1

                rows.append(
                    QualificationPrimaryScore(
                        problem_sha256=(problem_sha),
                        candidate_count=(candidate_count),
                        topology_stratum=(topology_stratum),
                        strategy=(SYSTEM_STRATEGY),
                        failure_region_recall_auc=(0.60),
                        boundary_recall_auc=(0.60),
                    )
                )

                for comparator in PRIMARY_COMPARATORS:
                    (
                        region,
                        boundary,
                    ) = comparator_values[comparator]

                    rows.append(
                        QualificationPrimaryScore(
                            problem_sha256=(problem_sha),
                            candidate_count=(candidate_count),
                            topology_stratum=(topology_stratum),
                            strategy=(comparator),
                            failure_region_recall_auc=(region),
                            boundary_recall_auc=(boundary),
                        )
                    )

    assert problem_ordinal - 1 == EXPECTED_PROBLEM_COUNT

    return tuple(rows)


def test_frozen_constants():
    assert BOOTSTRAP_RESAMPLES == 10_000

    assert BOOTSTRAP_SEED == 7_040_204_754_812_255_417

    assert LOWER_ORDER_STATISTIC_INDEX == 24

    assert UPPER_ORDER_STATISTIC_INDEX == 9_974

    assert PROBLEMS_PER_STRATUM == 19
    assert STRATUM_COUNT == 36
    assert EXPECTED_PROBLEM_COUNT == 684

    assert len(ALL_PRIMARY_STRATEGIES) == 5


def test_statistical_pareto_dominance():
    relation, dominated = classify_primary_comparator_relation(
        failure_region_mean_delta=0.10,
        failure_region_lower_995=0.02,
        failure_region_upper_995=0.18,
        boundary_mean_delta=0.05,
        boundary_lower_995=0.01,
        boundary_upper_995=0.10,
    )

    assert relation == "STATISTICAL_PARETO_DOMINANCE"

    assert dominated is False


def test_tradeoff():
    relation, dominated = classify_primary_comparator_relation(
        failure_region_mean_delta=0.10,
        failure_region_lower_995=-0.02,
        failure_region_upper_995=0.20,
        boundary_mean_delta=-0.05,
        boundary_lower_995=-0.10,
        boundary_upper_995=0.01,
    )

    assert relation == "TRADEOFF"
    assert dominated is False


def test_mean_pareto_dominance():
    relation, dominated = classify_primary_comparator_relation(
        failure_region_mean_delta=0.03,
        failure_region_lower_995=-0.01,
        failure_region_upper_995=0.07,
        boundary_mean_delta=0.02,
        boundary_lower_995=-0.01,
        boundary_upper_995=0.06,
    )

    assert relation == "MEAN_PARETO_DOMINANCE"

    assert dominated is False


def test_mean_dominated():
    relation, dominated = classify_primary_comparator_relation(
        failure_region_mean_delta=-0.03,
        failure_region_lower_995=-0.07,
        failure_region_upper_995=0.01,
        boundary_mean_delta=-0.02,
        boundary_lower_995=-0.06,
        boundary_upper_995=0.01,
    )

    assert relation == "DOMINATED"
    assert dominated is False


def test_statistically_pareto_dominated_flag():
    relation, dominated = classify_primary_comparator_relation(
        failure_region_mean_delta=-0.10,
        failure_region_lower_995=-0.15,
        failure_region_upper_995=-0.02,
        boundary_mean_delta=-0.08,
        boundary_lower_995=-0.12,
        boundary_upper_995=-0.01,
    )

    assert relation == "DOMINATED"
    assert dominated is True


def test_pareto_nondominated_exact_zero():
    relation, dominated = classify_primary_comparator_relation(
        failure_region_mean_delta=0.0,
        failure_region_lower_995=-0.01,
        failure_region_upper_995=0.01,
        boundary_mean_delta=0.0,
        boundary_lower_995=-0.01,
        boundary_upper_995=0.01,
    )

    assert relation == "PARETO_NONDOMINATED"

    assert dominated is False


def test_program_invalid_has_highest_precedence():
    relations = list(_program_relations("STATISTICAL_PARETO_DOMINANCE"))

    relations[0] = replace(
        relations[0],
        statistical_pareto_dominated=True,
    )

    result = classify_qualification_program(
        pairwise_relations=tuple(relations),
        guardrail_failures=("FULL_BUDGET_GUARDRAIL",),
    )

    assert result == "QUALIFICATION_INVALID"


def test_program_inferior():
    relations = list(_program_relations("PARETO_NONDOMINATED"))

    relations[2] = replace(
        relations[2],
        statistical_pareto_dominated=True,
    )

    result = classify_qualification_program(pairwise_relations=tuple(relations))

    assert result == "QUALIFICATION_INFERIOR"


def test_program_statistical_advantage():
    result = classify_qualification_program(
        pairwise_relations=(_program_relations("STATISTICAL_PARETO_DOMINANCE"))
    )

    assert result == "QUALIFIED_STATISTICAL_PARETO_ADVANTAGE"


def test_program_mean_advantage():
    relations = list(_program_relations("STATISTICAL_PARETO_DOMINANCE"))

    relations[1] = replace(
        relations[1],
        relation=("MEAN_PARETO_DOMINANCE"),
    )

    result = classify_qualification_program(pairwise_relations=tuple(relations))

    assert result == "QUALIFIED_MEAN_PARETO_ADVANTAGE"


def test_program_tradeoff():
    relations = list(_program_relations("PARETO_NONDOMINATED"))

    relations[1] = replace(
        relations[1],
        relation="TRADEOFF",
    )

    result = classify_qualification_program(pairwise_relations=tuple(relations))

    assert result == "QUALIFICATION_TRADEOFF"


def test_program_pareto_nondominated():
    result = classify_qualification_program(
        pairwise_relations=(_program_relations("PARETO_NONDOMINATED"))
    )

    assert result == "QUALIFIED_PARETO_NONDOMINATED"


@pytest.mark.parametrize(
    "kwargs",
    [
        {
            "failure_region_mean_delta": float("nan"),
            "failure_region_lower_995": 0.0,
            "failure_region_upper_995": 0.1,
            "boundary_mean_delta": 0.0,
            "boundary_lower_995": 0.0,
            "boundary_upper_995": 0.1,
        },
        {
            "failure_region_mean_delta": 0.0,
            "failure_region_lower_995": 0.2,
            "failure_region_upper_995": 0.1,
            "boundary_mean_delta": 0.0,
            "boundary_lower_995": 0.0,
            "boundary_upper_995": 0.1,
        },
    ],
)
def test_pairwise_classifier_fails_closed(
    kwargs,
):
    with pytest.raises(QualificationStatisticalContractError):
        classify_primary_comparator_relation(**kwargs)


def test_full_analyzer_statistical_advantage_and_replay():
    scores = _complete_scores()

    first = analyze_fresh_qualification_primary_scores(scores=scores)

    second = analyze_fresh_qualification_primary_scores(scores=scores)

    assert first == second

    assert first.problem_count == 684
    assert first.stratum_count == 36

    assert first.problems_per_stratum == 19

    assert first.bootstrap_resamples == 10_000

    assert first.bootstrap_seed == 7_040_204_754_812_255_417

    assert len(first.pairwise_relations) == 4

    assert all(
        relation.relation == "STATISTICAL_PARETO_DOMINANCE"
        for relation in first.pairwise_relations
    )

    assert all(
        relation.statistical_pareto_dominated is False
        for relation in first.pairwise_relations
    )

    assert first.program_classification == "QUALIFIED_STATISTICAL_PARETO_ADVANTAGE"

    assert len(first.bootstrap_replicate_sha256) == 64

    assert len(first.sha256) == 64


def test_full_analyzer_is_input_order_invariant():
    scores = list(_complete_scores())

    shuffled = list(scores)

    random.Random(123456789).shuffle(shuffled)

    ordered_result = analyze_fresh_qualification_primary_scores(scores=tuple(scores))

    shuffled_result = analyze_fresh_qualification_primary_scores(scores=tuple(shuffled))

    assert ordered_result == shuffled_result


def test_guardrail_failure_forces_invalid():
    result = analyze_fresh_qualification_primary_scores(
        scores=_complete_scores(),
        guardrail_failures=("EXAMPLE_FROZEN_GUARDRAIL",),
    )

    assert result.program_classification == "QUALIFICATION_INVALID"

    assert result.guardrail_failures == ("EXAMPLE_FROZEN_GUARDRAIL",)


def test_missing_record_fails_closed():
    scores = _complete_scores()

    with pytest.raises(QualificationStatisticalContractError):
        analyze_fresh_qualification_primary_scores(scores=scores[:-1])


def test_duplicate_problem_strategy_pair_fails_closed():
    scores = list(_complete_scores())

    scores[-1] = scores[0]

    with pytest.raises(QualificationStatisticalContractError):
        analyze_fresh_qualification_primary_scores(scores=tuple(scores))


def test_invalid_metric_fails_closed():
    scores = list(_complete_scores())

    scores[0] = replace(
        scores[0],
        failure_region_recall_auc=1.1,
    )

    with pytest.raises(QualificationStatisticalContractError):
        analyze_fresh_qualification_primary_scores(scores=tuple(scores))


def test_problem_metadata_mismatch_fails_closed():
    scores = list(_complete_scores())

    scores[1] = replace(
        scores[1],
        candidate_count=28,
    )

    with pytest.raises(QualificationStatisticalContractError):
        analyze_fresh_qualification_primary_scores(scores=tuple(scores))


def test_guardrail_failure_identifiers_are_order_normalized():
    result = analyze_fresh_qualification_primary_scores(
        scores=_complete_scores(),
        guardrail_failures=(
            "Z_GUARDRAIL",
            "A_GUARDRAIL",
        ),
    )

    assert result.guardrail_failures == (
        "A_GUARDRAIL",
        "Z_GUARDRAIL",
    )

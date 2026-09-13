from __future__ import annotations

from dataclasses import asdict
import ast
import hashlib
import inspect
from pathlib import Path
import random
import runpy

import pytest

import hvee.core.behavioral_qualification_statistics as sealed
import hvee.core.behavioral_v2_development_statistical_readiness_adapter as adapter
from hvee.core.behavioral_v2_development_statistical_readiness_adapter import (
    StatisticalReadinessScore,
    StatisticalReadinessShape,
    analyze_statistical_readiness_scores,
)


def _sha(
    value: str,
) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _small_shape() -> StatisticalReadinessShape:
    return StatisticalReadinessShape(
        problem_count=6,
        stratum_count=2,
        problems_per_stratum=3,
        strata=(
            (
                9,
                "B",
            ),
            (
                7,
                "A",
            ),
        ),
    )


def _small_scores():
    rows = []

    for candidate_count, topology_stratum in (
        (
            7,
            "A",
        ),
        (
            9,
            "B",
        ),
    ):
        for ordinal in range(3):
            problem_sha = _sha(
                str(candidate_count) + ":" + topology_stratum + ":" + str(ordinal)
            )

            selected_region = 0.55 + ordinal * 0.01

            selected_boundary = 0.65 - ordinal * 0.01

            reference_region = selected_region - 0.03

            reference_boundary = selected_boundary + 0.02

            rows.extend(
                (
                    StatisticalReadinessScore(
                        problem_sha256=(problem_sha),
                        candidate_count=(candidate_count),
                        topology_stratum=(topology_stratum),
                        strategy=("selected"),
                        failure_region_recall_auc=(selected_region),
                        boundary_recall_auc=(selected_boundary),
                    ),
                    StatisticalReadinessScore(
                        problem_sha256=(problem_sha),
                        candidate_count=(candidate_count),
                        topology_stratum=(topology_stratum),
                        strategy=("reference"),
                        failure_region_recall_auc=(reference_region),
                        boundary_recall_auc=(reference_boundary),
                    ),
                )
            )

    return tuple(rows)


def _legacy_fixture():
    path = (
        Path(sealed.__file__).resolve().parents[2]
        / "tests"
        / "hvee"
        / "core"
        / "test_behavioral_qualification_statistics.py"
    )

    namespace = runpy.run_path(str(path))

    return namespace["_complete_scores"]()


def _legacy_adapter_scores(
    scores,
):
    return tuple(
        StatisticalReadinessScore(
            problem_sha256=(score.problem_sha256),
            candidate_count=(score.candidate_count),
            topology_stratum=(score.topology_stratum),
            strategy=(score.strategy),
            failure_region_recall_auc=(score.failure_region_recall_auc),
            boundary_recall_auc=(score.boundary_recall_auc),
        )
        for score in scores
    )


def _legacy_shape():
    strata = tuple(
        (
            candidate_count,
            topology_stratum,
        )
        for candidate_count in sealed.QUALIFICATION_CANDIDATE_COUNTS
        for topology_stratum in sorted(sealed.TOPOLOGY_STRATA)
    )

    return StatisticalReadinessShape(
        problem_count=(sealed.EXPECTED_PROBLEM_COUNT),
        stratum_count=(sealed.STRATUM_COUNT),
        problems_per_stratum=(sealed.PROBLEMS_PER_STRATUM),
        strata=(strata),
    )


def test_inherited_bootstrap_constants_are_exact():
    assert adapter.BOOTSTRAP_RESAMPLES == 10_000

    assert adapter.BOOTSTRAP_SEED == 7_040_204_754_812_255_417

    assert adapter.LOWER_ORDER_STATISTIC_INDEX == 24

    assert adapter.UPPER_ORDER_STATISTIC_INDEX == 9974


def test_adapter_uses_sealed_relation_classifier_directly():
    assert (
        adapter.classify_primary_comparator_relation
        is sealed.classify_primary_comparator_relation
    )


def test_small_shape_deterministic_replay():
    scores = _small_scores()

    shape = _small_shape()

    first = analyze_statistical_readiness_scores(
        scores=(scores),
        selected_strategy=("selected"),
        reference_strategies=(("reference",)),
        shape=(shape),
    )

    second = analyze_statistical_readiness_scores(
        scores=(scores),
        selected_strategy=("selected"),
        reference_strategies=(("reference",)),
        shape=(shape),
    )

    assert first == second


def test_small_shape_input_order_invariant():
    scores = list(_small_scores())

    shuffled = list(scores)

    random.Random(123456789).shuffle(shuffled)

    first = analyze_statistical_readiness_scores(
        scores=tuple(scores),
        selected_strategy="selected",
        reference_strategies=("reference",),
        shape=_small_shape(),
    )

    second = analyze_statistical_readiness_scores(
        scores=tuple(shuffled),
        selected_strategy="selected",
        reference_strategies=("reference",),
        shape=_small_shape(),
    )

    assert first == second


def test_small_shape_expected_tradeoff_relation():
    result = analyze_statistical_readiness_scores(
        scores=_small_scores(),
        selected_strategy="selected",
        reference_strategies=("reference",),
        shape=_small_shape(),
    )

    comparison = result.comparator_results[0]

    assert comparison.failure_region_recall_auc.mean_delta > 0.0

    assert comparison.boundary_recall_auc.mean_delta < 0.0

    assert comparison.relation == "TRADEOFF"

    assert comparison.statistical_pareto_dominated is False


def test_shape_product_mismatch_fails_closed():
    with pytest.raises(sealed.QualificationStatisticalContractError):
        analyze_statistical_readiness_scores(
            scores=_small_scores(),
            selected_strategy="selected",
            reference_strategies=("reference",),
            shape=StatisticalReadinessShape(
                problem_count=7,
                stratum_count=2,
                problems_per_stratum=3,
                strata=(
                    (
                        7,
                        "A",
                    ),
                    (
                        9,
                        "B",
                    ),
                ),
            ),
        )


def test_duplicate_reference_fails_closed():
    with pytest.raises(sealed.QualificationStatisticalContractError):
        analyze_statistical_readiness_scores(
            scores=_small_scores(),
            selected_strategy="selected",
            reference_strategies=(
                "reference",
                "reference",
            ),
            shape=_small_shape(),
        )


def test_selected_cannot_be_reference():
    with pytest.raises(sealed.QualificationStatisticalContractError):
        analyze_statistical_readiness_scores(
            scores=_small_scores(),
            selected_strategy="selected",
            reference_strategies=("selected",),
            shape=_small_shape(),
        )


def test_missing_score_fails_closed():
    with pytest.raises(sealed.QualificationStatisticalContractError):
        analyze_statistical_readiness_scores(
            scores=_small_scores()[:-1],
            selected_strategy="selected",
            reference_strategies=("reference",),
            shape=_small_shape(),
        )


def test_duplicate_problem_strategy_pair_fails_closed():
    scores = list(_small_scores())

    scores[-1] = scores[0]

    with pytest.raises(sealed.QualificationStatisticalContractError):
        analyze_statistical_readiness_scores(
            scores=tuple(scores),
            selected_strategy="selected",
            reference_strategies=("reference",),
            shape=_small_shape(),
        )


def test_invalid_metric_fails_closed():
    scores = list(_small_scores())

    original = scores[0]

    scores[0] = StatisticalReadinessScore(
        problem_sha256=(original.problem_sha256),
        candidate_count=(original.candidate_count),
        topology_stratum=(original.topology_stratum),
        strategy=(original.strategy),
        failure_region_recall_auc=1.1,
        boundary_recall_auc=(original.boundary_recall_auc),
    )

    with pytest.raises(sealed.QualificationStatisticalContractError):
        analyze_statistical_readiness_scores(
            scores=tuple(scores),
            selected_strategy="selected",
            reference_strategies=("reference",),
            shape=_small_shape(),
        )


def test_problem_metadata_disagreement_fails_closed():
    scores = list(_small_scores())

    original = scores[1]

    scores[1] = StatisticalReadinessScore(
        problem_sha256=(original.problem_sha256),
        candidate_count=999,
        topology_stratum=(original.topology_stratum),
        strategy=(original.strategy),
        failure_region_recall_auc=(original.failure_region_recall_auc),
        boundary_recall_auc=(original.boundary_recall_auc),
    )

    with pytest.raises(sealed.QualificationStatisticalContractError):
        analyze_statistical_readiness_scores(
            scores=tuple(scores),
            selected_strategy="selected",
            reference_strategies=("reference",),
            shape=_small_shape(),
        )


def test_legacy_36x19_mode_exactly_reproduces_sealed_pairwise_statistics():
    legacy_scores = _legacy_fixture()

    sealed_result = sealed.analyze_fresh_qualification_primary_scores(
        scores=(legacy_scores)
    )

    adapter_result = analyze_statistical_readiness_scores(
        scores=(_legacy_adapter_scores(legacy_scores)),
        selected_strategy=(sealed.SYSTEM_STRATEGY),
        reference_strategies=(sealed.PRIMARY_COMPARATORS),
        shape=(_legacy_shape()),
    )

    assert (
        adapter_result.bootstrap_replicate_sha256
        == sealed_result.bootstrap_replicate_sha256
    )

    assert len(adapter_result.comparator_results) == len(
        sealed_result.pairwise_relations
    )

    for adapter_relation, sealed_relation in zip(
        adapter_result.comparator_results,
        sealed_result.pairwise_relations,
        strict=True,
    ):
        assert adapter_relation.reference_strategy == sealed_relation.comparator

        assert asdict(adapter_relation.failure_region_recall_auc) == asdict(
            sealed_relation.failure_region_recall_auc
        )

        assert asdict(adapter_relation.boundary_recall_auc) == asdict(
            sealed_relation.boundary_recall_auc
        )

        assert adapter_relation.relation == sealed_relation.relation

        assert (
            adapter_relation.statistical_pareto_dominated
            == sealed_relation.statistical_pareto_dominated
        )


def test_legacy_mode_reports_exact_frozen_geometry():
    result = analyze_statistical_readiness_scores(
        scores=_legacy_adapter_scores(_legacy_fixture()),
        selected_strategy=(sealed.SYSTEM_STRATEGY),
        reference_strategies=(sealed.PRIMARY_COMPARATORS),
        shape=_legacy_shape(),
    )

    assert result.problem_count == 684

    assert result.stratum_count == 36

    assert result.problems_per_stratum == 19

    assert result.bootstrap_resamples == 10_000

    assert result.bootstrap_seed == 7_040_204_754_812_255_417


def test_adapter_production_source_has_no_filesystem_or_network_surface():
    source = inspect.getsource(adapter)

    tree = ast.parse(source)

    imported_roots = set()

    for node in ast.walk(tree):
        if isinstance(
            node,
            ast.Import,
        ):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)

        elif (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and node.module
        ):
            imported_roots.add(node.module.split(".")[0])

    forbidden = {
        "os",
        "pathlib",
        "socket",
        "requests",
        "urllib",
        "httpx",
        "subprocess",
        "numpy",
        "torch",
        "transformers",
        "faster_whisper",
    }

    assert imported_roots.isdisjoint(forbidden)


def test_adapter_has_no_qualification_or_corpus_open_surface():
    source = inspect.getsource(adapter)

    forbidden = (
        "build_fresh_behavioral_qualification_corpus",
        "qualification_open_authorized",
        "behavioral_v2_fresh_development_corpus",
        "fresh-v2-development-benchmark-v1-raw-executions",
    )

    for token in forbidden:
        assert token not in source

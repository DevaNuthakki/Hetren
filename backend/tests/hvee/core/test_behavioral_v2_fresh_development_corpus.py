from __future__ import annotations

from collections import Counter
from copy import deepcopy
from itertools import product

import pytest

import hvee.core.behavioral_v2_fresh_development_corpus as corpus
from hvee.core.behavioral_multi_objective_qualification import (
    FreshQualificationProblem,
)
from hvee.core.contracts import HveeContractError


SYNTHETIC_NAMESPACE = "HETREN_SYNTHETIC_V2_GENERATOR_VALIDATION_V1"

SECOND_SYNTHETIC_NAMESPACE = "HETREN_SYNTHETIC_V2_GENERATOR_VALIDATION_V2"


def _failure_run_widths(
    pattern: str,
) -> tuple[int, ...]:
    widths = []
    current = 0

    for value in pattern:
        if value == "F":
            current += 1

        elif current:
            widths.append(current)
            current = 0

    if current:
        widths.append(current)

    return tuple(widths)


def _pass_run_widths(
    pattern: str,
) -> tuple[int, ...]:
    widths = []
    current = 0

    for value in pattern:
        if value == "P":
            current += 1

        elif current:
            widths.append(current)
            current = 0

    if current:
        widths.append(current)

    return tuple(widths)


def test_frozen_constants_match_errata():
    assert corpus.GENERATOR_KEY == "behavioral_v2_fresh_development_corpus"

    assert corpus.GENERATOR_VERSION == "1.0.0"

    assert corpus.DEVELOPMENT_NAMESPACE == (
        "HETREN_FRESH_BEHAVIORAL_ENGINE_V2_" "DEVELOPMENT_7F6250A_V1E1"
    )

    assert corpus.DEVELOPMENT_CANDIDATE_COUNTS == (
        27,
        31,
        39,
    )

    assert corpus.PROBLEMS_PER_STRATUM == 23

    assert len(corpus.BASE_FAMILIES) == 8

    assert len(corpus.TOPOLOGY_STRATA) == 16

    assert corpus.EXPECTED_DEVELOPMENT_PROBLEM_COUNT == 1104

    assert "EDGE_ATTACHED_REGION_V2" not in corpus.BASE_FAMILIES

    assert "EDGE_PLUS_TWO_INTERIOR_REGIONS_V2" in corpus.BASE_FAMILIES


def test_public_api_exposes_no_qualification_generation_path():
    assert corpus.__all__ == [
        "BASE_FAMILIES",
        "DEVELOPMENT_CANDIDATE_COUNTS",
        "DEVELOPMENT_NAMESPACE",
        "DEVELOPMENT_PARTITION",
        "EXPECTED_DEVELOPMENT_PROBLEM_COUNT",
        "GENERATOR_KEY",
        "GENERATOR_VERSION",
        "PROBLEMS_PER_STRATUM",
        "SCHEMA_VERSION",
        "TOPOLOGY_STRATA",
        "build_fresh_v2_development_corpus",
        "verify_fresh_v2_development_corpus",
    ]

    public_callables = {
        name
        for name in corpus.__all__
        if callable(
            getattr(
                corpus,
                name,
                None,
            )
        )
    }

    assert public_callables == {
        "build_fresh_v2_development_corpus",
        "verify_fresh_v2_development_corpus",
    }


@pytest.mark.parametrize(
    (
        "total",
        "part_count",
    ),
    (
        (
            0,
            1,
        ),
        (
            2,
            2,
        ),
        (
            3,
            3,
        ),
        (
            4,
            4,
        ),
    ),
)
def test_weak_composition_unranking_matches_lexicographic_order(
    total,
    part_count,
):
    expected = tuple(
        values
        for values in product(
            range(total + 1),
            repeat=(part_count),
        )
        if sum(values) == total
    )

    actual = tuple(
        corpus._weak_composition_unrank(
            total=(total),
            part_count=(part_count),
            rank=(rank),
        )
        for rank in range(
            corpus._weak_composition_capacity(
                total=(total),
                part_count=(part_count),
            )
        )
    )

    assert actual == expected


def test_weak_composition_rank_rejects_out_of_range():
    with pytest.raises(
        HveeContractError,
    ):
        corpus._weak_composition_unrank(
            total=3,
            part_count=3,
            rank=-1,
        )

    capacity = corpus._weak_composition_capacity(
        total=3,
        part_count=3,
    )

    with pytest.raises(
        HveeContractError,
    ):
        corpus._weak_composition_unrank(
            total=3,
            part_count=3,
            rank=(capacity),
        )


@pytest.mark.parametrize(
    "candidate_count",
    corpus.DEVELOPMENT_CANDIDATE_COUNTS,
)
@pytest.mark.parametrize(
    "family",
    corpus.BASE_FAMILIES,
)
def test_every_frozen_development_family_has_required_capacity(
    candidate_count,
    family,
):
    assert (
        corpus._family_catalog_capacity(
            family=(family),
            candidate_count=(candidate_count),
        )
        >= corpus.PROBLEMS_PER_STRATUM
    )


@pytest.mark.parametrize(
    "candidate_count",
    corpus.DEVELOPMENT_CANDIDATE_COUNTS,
)
def test_monotonic_capacity_matches_erratum_002(
    candidate_count,
):
    assert (
        corpus._family_catalog_capacity(
            family=("MONOTONIC_SINGLE_TRANSITION_V2"),
            candidate_count=(candidate_count),
        )
        == candidate_count - 3
    )


@pytest.mark.parametrize(
    "candidate_count",
    corpus.DEVELOPMENT_CANDIDATE_COUNTS,
)
def test_family_rank_patterns_obey_exact_contracts(
    candidate_count,
):
    for family in corpus.BASE_FAMILIES:
        capacity = corpus._family_catalog_capacity(
            family=(family),
            candidate_count=(candidate_count),
        )

        ranks = sorted(
            {
                0,
                min(
                    1,
                    capacity - 1,
                ),
                capacity // 2,
                capacity - 1,
            }
        )

        for rank in ranks:
            pattern = corpus._pattern_at_catalog_rank(
                family=(family),
                candidate_count=(candidate_count),
                rank=(rank),
            )

            assert len(pattern) == candidate_count

            assert set(pattern) == {
                "P",
                "F",
            }

            failure_widths = _failure_run_widths(pattern)

            pass_widths = _pass_run_widths(pattern)

            if family == "MONOTONIC_SINGLE_TRANSITION_V2":
                assert pattern.startswith("PP")

                assert pattern.endswith("FF")

                assert corpus._transition_count(pattern) == 1

                assert corpus._failure_component_count(pattern) == 1

            elif family == "SINGLE_INTERIOR_REGION_V2":
                assert pattern.startswith("PP")

                assert pattern.endswith("PP")

                assert corpus._failure_component_count(pattern) == 1

                assert failure_widths[0] >= 2

            elif family == "TWO_DISJOINT_REGIONS_V2":
                assert corpus._failure_component_count(pattern) == 2

                assert min(failure_widths) >= 2

                assert pattern.startswith("P")

                assert pattern.endswith("P")

                assert pass_widths[1] >= 2

            elif family == "THREE_DISJOINT_REGIONS_V2":
                assert corpus._failure_component_count(pattern) == 3

                assert pattern.startswith("P")

                assert pattern.endswith("P")

            elif family == "FOUR_DISJOINT_REGIONS_V2":
                assert corpus._failure_component_count(pattern) == 4

                assert pattern.startswith("P")

                assert pattern.endswith("P")

            elif family == "EDGE_PLUS_TWO_INTERIOR_REGIONS_V2":
                assert corpus._failure_component_count(pattern) == 3

                assert pattern.startswith("F")

                assert pattern.endswith("P")

            elif family == "MIXED_WIDTH_THREE_REGIONS_V2":
                assert corpus._failure_component_count(pattern) == 3

                assert tuple(sorted(failure_widths)) == (
                    1,
                    2,
                    3,
                )

                assert pattern.startswith("P")

                assert pattern.endswith("P")

            elif family == "DENSE_ALTERNATING_BANDS_V2":
                assert corpus._failure_component_count(pattern) in {
                    4,
                    5,
                    6,
                }

                assert pattern.startswith("P")

                assert pattern.endswith("P")

            else:
                raise AssertionError(family)


@pytest.mark.parametrize(
    "candidate_count",
    corpus.DEVELOPMENT_CANDIDATE_COUNTS,
)
def test_global_family_selection_is_deterministic_and_collision_free(
    candidate_count,
):
    first = corpus._select_all_base_patterns(
        namespace=(SYNTHETIC_NAMESPACE),
        candidate_count=(candidate_count),
    )

    second = corpus._select_all_base_patterns(
        namespace=(SYNTHETIC_NAMESPACE),
        candidate_count=(candidate_count),
    )

    assert first == second

    raw = []

    for family in corpus.BASE_FAMILIES:
        patterns = first[family]

        assert len(patterns) == corpus.PROBLEMS_PER_STRATUM

        for pattern in patterns:
            raw.append(pattern)

            raw.append(corpus._complement_pattern(pattern))

    assert len(raw) == (len(corpus.BASE_FAMILIES) * corpus.PROBLEMS_PER_STRATUM * 2)

    assert len(set(raw)) == len(raw)


def test_synthetic_full_corpus_is_exactly_1104_and_deterministic():
    first = corpus._build_development_corpus_for_namespace(
        namespace=(SYNTHETIC_NAMESPACE),
    )

    second = corpus._build_development_corpus_for_namespace(
        namespace=(SYNTHETIC_NAMESPACE),
    )

    assert first == second

    assert len(first) == 1104

    assert (
        corpus._verify_development_corpus_for_namespace(
            problems=(first),
            namespace=(SYNTHETIC_NAMESPACE),
        )
        is True
    )

    assert all(
        isinstance(
            problem,
            FreshQualificationProblem,
        )
        for problem in first
    )

    assert all(problem.namespace == SYNTHETIC_NAMESPACE for problem in first)

    assert all(problem.partition == "development" for problem in first)


def test_synthetic_corpus_has_exact_group_cardinality_and_global_raw_uniqueness():
    problems = corpus._build_development_corpus_for_namespace(
        namespace=(SYNTHETIC_NAMESPACE),
    )

    groups = Counter(
        (
            problem.candidate_count,
            problem.topology_stratum,
        )
        for problem in problems
    )

    assert len(groups) == 48

    assert set(groups.values()) == {23}

    for candidate_count in corpus.DEVELOPMENT_CANDIDATE_COUNTS:
        subset = [
            problem
            for problem in problems
            if problem.candidate_count == candidate_count
        ]

        assert len(subset) == 368

        assert len({problem.pattern for problem in subset}) == 368


def test_synthetic_base_and_complement_pairing_is_exact():
    problems = corpus._build_development_corpus_for_namespace(
        namespace=(SYNTHETIC_NAMESPACE),
    )

    indexed = {
        (
            problem.candidate_count,
            problem.topology_stratum,
            problem.ordinal,
        ): problem
        for problem in problems
    }

    for candidate_count in corpus.DEVELOPMENT_CANDIDATE_COUNTS:
        for family in corpus.BASE_FAMILIES:
            for ordinal in range(corpus.PROBLEMS_PER_STRATUM):
                base = indexed[
                    (
                        candidate_count,
                        family,
                        ordinal,
                    )
                ]

                complement = indexed[
                    (
                        candidate_count,
                        family + "_COMPLEMENT",
                        ordinal,
                    )
                ]

                assert complement.pattern == corpus._complement_pattern(base.pattern)


def test_synthetic_corpus_identity_fields_recompute_exactly():
    problems = corpus._build_development_corpus_for_namespace(
        namespace=(SYNTHETIC_NAMESPACE),
    )

    assert len({problem.problem_key for problem in problems}) == 1104

    assert len({problem.problem_sha256 for problem in problems}) == 1104

    assert len({problem.topology_sha256 for problem in problems}) == 1104

    for problem in problems[::97]:
        assert problem.topology_sha256 == corpus._topology_sha256(
            candidate_count=(problem.candidate_count),
            topology_stratum=(problem.topology_stratum),
            pattern=(problem.pattern),
        )

        assert problem.problem_sha256 == corpus._problem_sha256(
            namespace=(problem.namespace),
            candidate_count=(problem.candidate_count),
            topology_stratum=(problem.topology_stratum),
            ordinal=(problem.ordinal),
            pattern=(problem.pattern),
            topology_sha256=(problem.topology_sha256),
        )

        assert problem.problem_key == corpus._problem_key(
            candidate_count=(problem.candidate_count),
            topology_stratum=(problem.topology_stratum),
            ordinal=(problem.ordinal),
        )


def test_different_synthetic_namespace_changes_deterministic_selection():
    first = corpus._build_development_corpus_for_namespace(
        namespace=(SYNTHETIC_NAMESPACE),
    )

    second = corpus._build_development_corpus_for_namespace(
        namespace=(SECOND_SYNTHETIC_NAMESPACE),
    )

    assert len(first) == len(second) == 1104

    assert first != second

    assert any(
        left.pattern != right.pattern
        for left, right in zip(
            first,
            second,
        )
    )


def test_internal_verifier_rejects_tampered_synthetic_problem():
    problems = list(
        corpus._build_development_corpus_for_namespace(
            namespace=(SYNTHETIC_NAMESPACE),
        )
    )

    original = problems[0]

    problems[0] = FreshQualificationProblem(
        problem_key=(original.problem_key),
        partition=(original.partition),
        namespace=(original.namespace),
        candidate_count=(original.candidate_count),
        topology_stratum=(original.topology_stratum),
        ordinal=(original.ordinal),
        pattern=(corpus._complement_pattern(original.pattern)),
        topology_sha256=(original.topology_sha256),
        problem_sha256=(original.problem_sha256),
    )

    assert (
        corpus._verify_development_corpus_for_namespace(
            problems=tuple(problems),
            namespace=(SYNTHETIC_NAMESPACE),
        )
        is False
    )


def test_public_builder_binding_without_materializing_real_namespace(
    monkeypatch,
):
    seen = []

    def fake_builder(
        *,
        namespace,
    ):
        seen.append(namespace)

        return ()

    monkeypatch.setattr(
        corpus,
        "_build_development_corpus_for_namespace",
        fake_builder,
    )

    assert corpus.build_fresh_v2_development_corpus() == ()

    assert seen == [corpus.DEVELOPMENT_NAMESPACE]


def test_public_verifier_binding_without_materializing_real_namespace(
    monkeypatch,
):
    seen = []

    def fake_verifier(
        *,
        problems,
        namespace,
    ):
        seen.append(
            (
                problems,
                namespace,
            )
        )

        return True

    monkeypatch.setattr(
        corpus,
        "_verify_development_corpus_for_namespace",
        fake_verifier,
    )

    sentinel = ("synthetic-sentinel",)

    assert (
        corpus.verify_fresh_v2_development_corpus(
            problems=(sentinel),
        )
        is True
    )

    assert seen == [
        (
            sentinel,
            corpus.DEVELOPMENT_NAMESPACE,
        )
    ]


def test_public_source_does_not_define_qualification_builder():
    assert not hasattr(
        corpus,
        "build_fresh_v2_qualification_corpus",
    )

    assert not hasattr(
        corpus,
        "verify_fresh_v2_qualification_corpus",
    )


def test_invalid_namespace_rejected():
    for value in (
        "",
        " namespace",
        "namespace ",
        None,
        1,
    ):
        with pytest.raises(
            HveeContractError,
        ):
            corpus._build_development_corpus_for_namespace(
                namespace=(value),
            )

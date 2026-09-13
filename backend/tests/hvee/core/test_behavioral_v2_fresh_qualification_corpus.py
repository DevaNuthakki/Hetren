from __future__ import annotations

from collections import Counter
import inspect

import pytest

import hvee.core.behavioral_v2_fresh_qualification_corpus as corpus
from hvee.core.behavioral_multi_objective_qualification import (
    FreshQualificationProblem,
)
from hvee.core.contracts import HveeContractError


SYNTHETIC_NAMESPACE = "HETREN_SYNTHETIC_FRESH_V2_QUALIFICATION_GENERATOR_V1"

SECOND_SYNTHETIC_NAMESPACE = "HETREN_SYNTHETIC_FRESH_V2_QUALIFICATION_GENERATOR_V1_B"


EXPECTED_CAPACITIES = {
    33: {
        "MONOTONIC_SINGLE_TRANSITION_V2": 30,
        "SINGLE_INTERIOR_REGION_V2": 406,
        "TWO_DISJOINT_REGIONS_V2": 23751,
        "THREE_DISJOINT_REGIONS_V2": 906192,
        "FOUR_DISJOINT_REGIONS_V2": 10518300,
        "EDGE_PLUS_TWO_INTERIOR_REGIONS_V2": 201376,
        "MIXED_WIDTH_THREE_REGIONS_V2": 15600,
        "DENSE_ALTERNATING_BANDS_V2": 300823380,
        "NARROW_SINGLETONS_WITH_WIDE_GAPS_V2": 2300,
        "ASYMMETRIC_EDGE_PLUS_INTERIOR_REGIONS_V2": 3654,
    },
    37: {
        "MONOTONIC_SINGLE_TRANSITION_V2": 34,
        "SINGLE_INTERIOR_REGION_V2": 528,
        "TWO_DISJOINT_REGIONS_V2": 40920,
        "THREE_DISJOINT_REGIONS_V2": 1947792,
        "FOUR_DISJOINT_REGIONS_V2": 30260340,
        "EDGE_PLUS_TWO_INTERIOR_REGIONS_V2": 376992,
        "MIXED_WIDTH_THREE_REGIONS_V2": 24360,
        "DENSE_ALTERNATING_BANDS_V2": 1536124896,
        "NARROW_SINGLETONS_WITH_WIDE_GAPS_V2": 3654,
        "ASYMMETRIC_EDGE_PLUS_INTERIOR_REGIONS_V2": 5456,
    },
    41: {
        "MONOTONIC_SINGLE_TRANSITION_V2": 38,
        "SINGLE_INTERIOR_REGION_V2": 666,
        "TWO_DISJOINT_REGIONS_V2": 66045,
        "THREE_DISJOINT_REGIONS_V2": 3838380,
        "FOUR_DISJOINT_REGIONS_V2": 76904685,
        "EDGE_PLUS_TWO_INTERIOR_REGIONS_V2": 658008,
        "MIXED_WIDTH_THREE_REGIONS_V2": 35904,
        "DENSE_ALTERNATING_BANDS_V2": 6511418693,
        "NARROW_SINGLETONS_WITH_WIDE_GAPS_V2": 5456,
        "ASYMMETRIC_EDGE_PLUS_INTERIOR_REGIONS_V2": 7770,
    },
}


def _runs(
    pattern: str,
    value: str,
) -> tuple[int, ...]:
    result = []
    current = 0

    for item in pattern:
        if item == value:
            current += 1
        elif current:
            result.append(current)
            current = 0

    if current:
        result.append(current)

    return tuple(result)


def test_public_contract_and_frozen_identity():
    assert corpus.GENERATOR_KEY == ("behavioral_v2_fresh_qualification_corpus")

    assert corpus.GENERATOR_VERSION == "1.0.0"

    assert corpus.QUALIFICATION_NAMESPACE == (
        "HETREN_FRESH_BEHAVIORAL_ENGINE_V2_" "QUALIFICATION_RESERVED_V1E1"
    )

    assert corpus.QUALIFICATION_CANDIDATE_COUNTS == (
        33,
        37,
        41,
    )

    assert corpus.PROBLEMS_PER_STRATUM == 23

    assert len(corpus.BASE_FAMILIES) == 10

    assert len(corpus.TOPOLOGY_STRATA) == 20


def test_exact_frozen_family_order():
    assert corpus.BASE_FAMILIES == (
        "MONOTONIC_SINGLE_TRANSITION_V2",
        "SINGLE_INTERIOR_REGION_V2",
        "TWO_DISJOINT_REGIONS_V2",
        "THREE_DISJOINT_REGIONS_V2",
        "FOUR_DISJOINT_REGIONS_V2",
        "EDGE_PLUS_TWO_INTERIOR_REGIONS_V2",
        "MIXED_WIDTH_THREE_REGIONS_V2",
        "DENSE_ALTERNATING_BANDS_V2",
        "NARROW_SINGLETONS_WITH_WIDE_GAPS_V2",
        "ASYMMETRIC_EDGE_PLUS_INTERIOR_REGIONS_V2",
    )


@pytest.mark.parametrize(
    "candidate_count",
    corpus.QUALIFICATION_CANDIDATE_COUNTS,
)
@pytest.mark.parametrize(
    "family",
    corpus.BASE_FAMILIES,
)
def test_exact_frozen_qualification_family_capacity(
    candidate_count,
    family,
):
    assert (
        corpus._family_catalog_capacity(
            family=family,
            candidate_count=candidate_count,
        )
        == EXPECTED_CAPACITIES[candidate_count][family]
    )


@pytest.mark.parametrize(
    "candidate_count",
    corpus.QUALIFICATION_CANDIDATE_COUNTS,
)
def test_narrow_singletons_family_exact_contract(
    candidate_count,
):
    family = "NARROW_SINGLETONS_WITH_WIDE_GAPS_V2"

    capacity = corpus._family_catalog_capacity(
        family=family,
        candidate_count=candidate_count,
    )

    for rank in (
        0,
        1,
        capacity // 2,
        capacity - 1,
    ):
        pattern = corpus._pattern_at_catalog_rank(
            family=family,
            candidate_count=candidate_count,
            rank=rank,
        )

        assert len(pattern) == candidate_count
        assert set(pattern) == {"P", "F"}

        failure_widths = _runs(
            pattern,
            "F",
        )

        pass_widths = _runs(
            pattern,
            "P",
        )

        assert failure_widths == (
            1,
            1,
            1,
        )

        assert len(pass_widths) == 4
        assert pass_widths[0] >= 1
        assert pass_widths[1] >= 3
        assert pass_widths[2] >= 3
        assert pass_widths[3] >= 1
        assert pattern.startswith("P")
        assert pattern.endswith("P")


@pytest.mark.parametrize(
    "candidate_count",
    corpus.QUALIFICATION_CANDIDATE_COUNTS,
)
def test_asymmetric_edge_plus_interior_family_exact_contract(
    candidate_count,
):
    family = "ASYMMETRIC_EDGE_PLUS_INTERIOR_REGIONS_V2"

    capacity = corpus._family_catalog_capacity(
        family=family,
        candidate_count=candidate_count,
    )

    for rank in (
        0,
        1,
        capacity // 2,
        capacity - 1,
    ):
        pattern = corpus._pattern_at_catalog_rank(
            family=family,
            candidate_count=candidate_count,
            rank=rank,
        )

        assert len(pattern) == candidate_count
        assert set(pattern) == {"P", "F"}

        failure_widths = _runs(
            pattern,
            "F",
        )

        pass_widths = _runs(
            pattern,
            "P",
        )

        assert len(failure_widths) == 2
        assert failure_widths[0] >= 2
        assert failure_widths[1] >= 2

        assert len(pass_widths) == 2
        assert pass_widths[0] >= 2
        assert pass_widths[1] >= 1

        assert pattern.startswith("F")
        assert pattern.endswith("P")


def test_qualification_weak_composition_unranking_exact_small_catalog():
    actual = tuple(
        corpus._qualification_weak_composition_unrank(
            total=3,
            part_count=3,
            rank=rank,
        )
        for rank in range(10)
    )

    assert actual == (
        (0, 0, 3),
        (0, 1, 2),
        (0, 2, 1),
        (0, 3, 0),
        (1, 0, 2),
        (1, 1, 1),
        (1, 2, 0),
        (2, 0, 1),
        (2, 1, 0),
        (3, 0, 0),
    )


def test_synthetic_full_qualification_corpus_is_exact_and_deterministic():
    first = corpus._build_qualification_corpus_for_namespace(
        namespace=SYNTHETIC_NAMESPACE,
    )

    second = corpus._build_qualification_corpus_for_namespace(
        namespace=SYNTHETIC_NAMESPACE,
    )

    assert first == second

    assert len(first) == 1380

    assert (
        corpus._verify_qualification_corpus_for_namespace(
            problems=first,
            namespace=SYNTHETIC_NAMESPACE,
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

    assert all(problem.partition == "qualification" for problem in first)

    assert all(problem.namespace == SYNTHETIC_NAMESPACE for problem in first)


def test_synthetic_exact_strata_and_cardinality():
    problems = corpus._build_qualification_corpus_for_namespace(
        namespace=SYNTHETIC_NAMESPACE,
    )

    groups = Counter(
        (
            problem.candidate_count,
            problem.topology_stratum,
        )
        for problem in problems
    )

    assert len(groups) == 60

    assert set(groups.values()) == {
        23,
    }

    for candidate_count in corpus.QUALIFICATION_CANDIDATE_COUNTS:
        subset = [
            problem
            for problem in problems
            if problem.candidate_count == candidate_count
        ]

        assert len(subset) == 460

        assert len({problem.pattern for problem in subset}) == 460


def test_synthetic_global_identity_uniqueness():
    problems = corpus._build_qualification_corpus_for_namespace(
        namespace=SYNTHETIC_NAMESPACE,
    )

    assert len({problem.problem_key for problem in problems}) == 1380

    assert len({problem.problem_sha256 for problem in problems}) == 1380

    assert len({problem.topology_sha256 for problem in problems}) == 1380


def test_synthetic_exact_base_complement_pairing():
    problems = corpus._build_qualification_corpus_for_namespace(
        namespace=SYNTHETIC_NAMESPACE,
    )

    indexed = {
        (
            problem.candidate_count,
            problem.topology_stratum,
            problem.ordinal,
        ): problem
        for problem in problems
    }

    checks = 0

    for candidate_count in corpus.QUALIFICATION_CANDIDATE_COUNTS:
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

                assert complement.pattern == (corpus._complement_pattern(base.pattern))

                checks += 1

    assert checks == 690


def test_synthetic_different_namespace_changes_selection():
    first = corpus._build_qualification_corpus_for_namespace(
        namespace=SYNTHETIC_NAMESPACE,
    )

    second = corpus._build_qualification_corpus_for_namespace(
        namespace=SECOND_SYNTHETIC_NAMESPACE,
    )

    assert len(first) == len(second) == 1380

    assert first != second


def test_public_builder_requires_explicit_authorization():
    with pytest.raises(HveeContractError):
        corpus.build_fresh_v2_qualification_corpus()


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
        "_build_qualification_corpus_for_namespace",
        fake_builder,
    )

    assert (
        corpus.build_fresh_v2_qualification_corpus(
            qualification_open_authorized=True,
        )
        == ()
    )

    assert seen == [corpus.QUALIFICATION_NAMESPACE]


def test_public_verifier_binding_without_real_materialization(
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
        "_verify_qualification_corpus_for_namespace",
        fake_verifier,
    )

    sentinel = ("synthetic-sentinel",)

    assert (
        corpus.verify_fresh_v2_qualification_corpus(
            problems=sentinel,
        )
        is True
    )

    assert seen == [
        (
            sentinel,
            corpus.QUALIFICATION_NAMESPACE,
        )
    ]


def test_real_namespace_not_used_by_synthetic_tests():
    source = inspect.getsource(corpus)

    assert "HETREN_FRESH_BEHAVIORAL_ENGINE_V2_" "QUALIFICATION_RESERVED_V1E1" in source

    assert SYNTHETIC_NAMESPACE != corpus.QUALIFICATION_NAMESPACE
    assert SECOND_SYNTHETIC_NAMESPACE != corpus.QUALIFICATION_NAMESPACE


def test_candidate_counts_are_disjoint_from_development_and_historical():
    qualification = set(corpus.QUALIFICATION_CANDIDATE_COUNTS)

    development = {
        27,
        31,
        39,
    }

    historical = {
        9,
        16,
        17,
        18,
        20,
        21,
        22,
        24,
        26,
        28,
        29,
        30,
        34,
        36,
    }

    assert qualification.isdisjoint(development)

    assert qualification.isdisjoint(historical)


def test_production_module_does_not_import_sealed_development_private_helpers():
    source = inspect.getsource(corpus)

    assert "from hvee.core.behavioral_v2_fresh_development_corpus" not in source

    assert "import hvee.core.behavioral_v2_fresh_development_corpus" not in source

from __future__ import annotations

from itertools import permutations
import hashlib
import json
import math

from hvee.core.behavioral_multi_objective_qualification import (
    FreshQualificationProblem,
)
from hvee.core.contracts import HveeContractError


GENERATOR_KEY = "behavioral_v2_fresh_development_corpus"
GENERATOR_VERSION = "1.0.0"
SCHEMA_VERSION = 1

DEVELOPMENT_PARTITION = "development"

DEVELOPMENT_NAMESPACE = "HETREN_FRESH_BEHAVIORAL_ENGINE_V2_DEVELOPMENT_7F6250A_V1E1"

DEVELOPMENT_CANDIDATE_COUNTS = (
    27,
    31,
    39,
)

PROBLEMS_PER_STRATUM = 23

BASE_FAMILIES = (
    "MONOTONIC_SINGLE_TRANSITION_V2",
    "SINGLE_INTERIOR_REGION_V2",
    "TWO_DISJOINT_REGIONS_V2",
    "THREE_DISJOINT_REGIONS_V2",
    "FOUR_DISJOINT_REGIONS_V2",
    "EDGE_PLUS_TWO_INTERIOR_REGIONS_V2",
    "MIXED_WIDTH_THREE_REGIONS_V2",
    "DENSE_ALTERNATING_BANDS_V2",
)

TOPOLOGY_STRATA = tuple(
    item
    for family in BASE_FAMILIES
    for item in (
        family,
        family + "_COMPLEMENT",
    )
)

EXPECTED_DEVELOPMENT_PROBLEM_COUNT = (
    len(DEVELOPMENT_CANDIDATE_COUNTS) * len(TOPOLOGY_STRATA) * PROBLEMS_PER_STRATUM
)


def _canonical_bytes(
    value: object,
) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise HveeContractError(
            "fresh V2 development corpus value must be canonical JSON"
        ) from exc


def _sha256(
    value: object,
) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _sha256_uint64(
    value: object,
) -> int:
    return int(
        _sha256(value)[:16],
        16,
    )


def _require_namespace(
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or not value
        or value.strip() != value
    ):
        raise HveeContractError(
            "fresh V2 development namespace must be a non-empty canonical string"
        )

    return value


def _require_candidate_count(
    value: object,
) -> int:
    if (
        isinstance(
            value,
            bool,
        )
        or not isinstance(
            value,
            int,
        )
        or value < 1
    ):
        raise HveeContractError(
            "fresh V2 development candidate_count must be positive integer"
        )

    return value


def _require_family(
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or value not in BASE_FAMILIES
    ):
        raise HveeContractError("unsupported fresh V2 development topology family")

    return value


def _validate_pattern(
    pattern: object,
    *,
    candidate_count: int,
) -> str:
    normalized_candidate_count = _require_candidate_count(candidate_count)

    if (
        not isinstance(
            pattern,
            str,
        )
        or len(pattern) != normalized_candidate_count
        or any(
            value
            not in (
                "P",
                "F",
            )
            for value in pattern
        )
        or "P" not in pattern
        or "F" not in pattern
    ):
        raise HveeContractError(
            "fresh V2 development pattern must be a nonconstant P/F string "
            "matching candidate_count"
        )

    return pattern


def _complement_pattern(
    pattern: str,
) -> str:
    if not isinstance(
        pattern,
        str,
    ):
        raise HveeContractError("fresh V2 complement requires string pattern")

    return "".join(
        "F" if value == "P" else "P" if value == "F" else "?" for value in pattern
    )


def _transition_count(
    pattern: str,
) -> int:
    if not pattern:
        return 0

    return sum(
        left != right
        for left, right in zip(
            pattern,
            pattern[1:],
        )
    )


def _failure_component_count(
    pattern: str,
) -> int:
    count = 0
    previous = "P"

    for value in pattern:
        if value == "F" and previous != "F":
            count += 1

        previous = value

    return count


def _weak_composition_capacity(
    *,
    total: int,
    part_count: int,
) -> int:
    if (
        isinstance(
            total,
            bool,
        )
        or not isinstance(
            total,
            int,
        )
        or total < 0
    ):
        raise HveeContractError("weak composition total must be non-negative integer")

    if (
        isinstance(
            part_count,
            bool,
        )
        or not isinstance(
            part_count,
            int,
        )
        or part_count < 1
    ):
        raise HveeContractError("weak composition part_count must be positive integer")

    return math.comb(
        total + part_count - 1,
        part_count - 1,
    )


def _weak_composition_unrank(
    *,
    total: int,
    part_count: int,
    rank: int,
) -> tuple[int, ...]:
    capacity = _weak_composition_capacity(
        total=total,
        part_count=(part_count),
    )

    if (
        isinstance(
            rank,
            bool,
        )
        or not isinstance(
            rank,
            int,
        )
        or rank < 0
        or rank >= capacity
    ):
        raise HveeContractError("weak composition rank outside catalog")

    remaining_total = total
    remaining_rank = rank
    values = []

    for index in range(part_count - 1):
        remaining_parts = part_count - index - 1

        selected = None

        for value in range(remaining_total + 1):
            tail_total = remaining_total - value

            tail_capacity = _weak_composition_capacity(
                total=(tail_total),
                part_count=(remaining_parts),
            )

            if remaining_rank < tail_capacity:
                selected = value
                values.append(value)
                remaining_total = tail_total
                break

            remaining_rank -= tail_capacity

        if selected is None:
            raise HveeContractError("weak composition unranking failed")

    values.append(remaining_total)

    result = tuple(values)

    if len(result) != part_count or sum(result) != total:
        raise HveeContractError("weak composition invariant failure")

    return result


def _segment_widths(
    *,
    candidate_count: int,
    minima: tuple[int, ...],
    rank: int,
) -> tuple[int, ...]:
    normalized_candidate_count = _require_candidate_count(candidate_count)

    if (
        not isinstance(
            minima,
            tuple,
        )
        or not minima
        or any(
            isinstance(
                value,
                bool,
            )
            or not isinstance(
                value,
                int,
            )
            or value < 0
            for value in minima
        )
    ):
        raise HveeContractError("segment minima must be tuple of non-negative integers")

    slack = normalized_candidate_count - sum(minima)

    if slack < 0:
        raise HveeContractError("candidate_count cannot satisfy segment minima")

    extras = _weak_composition_unrank(
        total=slack,
        part_count=len(minima),
        rank=rank,
    )

    return tuple(
        minimum + extra
        for minimum, extra in zip(
            minima,
            extras,
        )
    )


def _render_segments(
    *,
    symbols: tuple[str, ...],
    widths: tuple[int, ...],
) -> str:
    if len(symbols) != len(widths) or not symbols:
        raise HveeContractError("segment symbol/width shape mismatch")

    if any(
        symbol
        not in (
            "P",
            "F",
        )
        for symbol in symbols
    ):
        raise HveeContractError("segment symbols must use P/F alphabet")

    if any(
        isinstance(
            width,
            bool,
        )
        or not isinstance(
            width,
            int,
        )
        or width < 1
        for width in widths
    ):
        raise HveeContractError("rendered segment widths must be positive integers")

    return "".join(
        symbol * width
        for symbol, width in zip(
            symbols,
            widths,
        )
    )


def _family_catalog_capacity(
    *,
    family: str,
    candidate_count: int,
) -> int:
    normalized_family = _require_family(family)

    n = _require_candidate_count(candidate_count)

    if normalized_family == "MONOTONIC_SINGLE_TRANSITION_V2":
        return max(
            0,
            n - 3,
        )

    if normalized_family == "SINGLE_INTERIOR_REGION_V2":
        slack = n - 6

        if slack < 0:
            return 0

        return _weak_composition_capacity(
            total=slack,
            part_count=3,
        )

    if normalized_family == "TWO_DISJOINT_REGIONS_V2":
        slack = n - 8

        if slack < 0:
            return 0

        return _weak_composition_capacity(
            total=slack,
            part_count=5,
        )

    if normalized_family == "THREE_DISJOINT_REGIONS_V2":
        slack = n - 7

        if slack < 0:
            return 0

        return _weak_composition_capacity(
            total=slack,
            part_count=7,
        )

    if normalized_family == "FOUR_DISJOINT_REGIONS_V2":
        slack = n - 9

        if slack < 0:
            return 0

        return _weak_composition_capacity(
            total=slack,
            part_count=9,
        )

    if normalized_family == "EDGE_PLUS_TWO_INTERIOR_REGIONS_V2":
        slack = n - 6

        if slack < 0:
            return 0

        return _weak_composition_capacity(
            total=slack,
            part_count=6,
        )

    if normalized_family == "MIXED_WIDTH_THREE_REGIONS_V2":
        pass_total = n - 6

        if pass_total < 4:
            return 0

        pass_slack = pass_total - 4

        pass_capacity = _weak_composition_capacity(
            total=(pass_slack),
            part_count=4,
        )

        return (
            len(
                tuple(
                    permutations(
                        (
                            1,
                            2,
                            3,
                        )
                    )
                )
            )
            * pass_capacity
        )

    if normalized_family == "DENSE_ALTERNATING_BANDS_V2":
        total = 0

        for failure_components in (
            4,
            5,
            6,
        ):
            segment_count = 2 * failure_components + 1

            if n >= segment_count:
                total += _weak_composition_capacity(
                    total=(n - segment_count),
                    part_count=(segment_count),
                )

        return total

    raise HveeContractError("unsupported fresh V2 development family")


def _pattern_at_catalog_rank(
    *,
    family: str,
    candidate_count: int,
    rank: int,
) -> str:
    normalized_family = _require_family(family)

    n = _require_candidate_count(candidate_count)

    capacity = _family_catalog_capacity(
        family=(normalized_family),
        candidate_count=n,
    )

    if (
        isinstance(
            rank,
            bool,
        )
        or not isinstance(
            rank,
            int,
        )
        or rank < 0
        or rank >= capacity
    ):
        raise HveeContractError("family catalog rank outside valid range")

    if normalized_family == "MONOTONIC_SINGLE_TRANSITION_V2":
        transition_position = 2 + rank

        pattern = "P" * transition_position + "F" * (n - transition_position)

    elif normalized_family == "SINGLE_INTERIOR_REGION_V2":
        widths = _segment_widths(
            candidate_count=n,
            minima=(
                2,
                2,
                2,
            ),
            rank=rank,
        )

        pattern = _render_segments(
            symbols=(
                "P",
                "F",
                "P",
            ),
            widths=widths,
        )

    elif normalized_family == "TWO_DISJOINT_REGIONS_V2":
        widths = _segment_widths(
            candidate_count=n,
            minima=(
                1,
                2,
                2,
                2,
                1,
            ),
            rank=rank,
        )

        pattern = _render_segments(
            symbols=(
                "P",
                "F",
                "P",
                "F",
                "P",
            ),
            widths=widths,
        )

    elif normalized_family == "THREE_DISJOINT_REGIONS_V2":
        widths = _segment_widths(
            candidate_count=n,
            minima=(
                1,
                1,
                1,
                1,
                1,
                1,
                1,
            ),
            rank=rank,
        )

        pattern = _render_segments(
            symbols=(
                "P",
                "F",
                "P",
                "F",
                "P",
                "F",
                "P",
            ),
            widths=widths,
        )

    elif normalized_family == "FOUR_DISJOINT_REGIONS_V2":
        widths = _segment_widths(
            candidate_count=n,
            minima=(
                1,
                1,
                1,
                1,
                1,
                1,
                1,
                1,
                1,
            ),
            rank=rank,
        )

        pattern = _render_segments(
            symbols=(
                "P",
                "F",
                "P",
                "F",
                "P",
                "F",
                "P",
                "F",
                "P",
            ),
            widths=widths,
        )

    elif normalized_family == "EDGE_PLUS_TWO_INTERIOR_REGIONS_V2":
        widths = _segment_widths(
            candidate_count=n,
            minima=(
                1,
                1,
                1,
                1,
                1,
                1,
            ),
            rank=rank,
        )

        pattern = _render_segments(
            symbols=(
                "F",
                "P",
                "F",
                "P",
                "F",
                "P",
            ),
            widths=widths,
        )

    elif normalized_family == "MIXED_WIDTH_THREE_REGIONS_V2":
        permutations_lexical = tuple(
            permutations(
                (
                    1,
                    2,
                    3,
                )
            )
        )

        pass_slack = n - 10

        pass_capacity = _weak_composition_capacity(
            total=(pass_slack),
            part_count=4,
        )

        permutation_index = rank // pass_capacity

        pass_rank = rank % pass_capacity

        failure_widths = permutations_lexical[permutation_index]

        pass_extras = _weak_composition_unrank(
            total=(pass_slack),
            part_count=4,
            rank=(pass_rank),
        )

        pass_widths = tuple(value + 1 for value in pass_extras)

        pattern = "".join(
            (
                "P" * pass_widths[0],
                "F" * failure_widths[0],
                "P" * pass_widths[1],
                "F" * failure_widths[1],
                "P" * pass_widths[2],
                "F" * failure_widths[2],
                "P" * pass_widths[3],
            )
        )

    elif normalized_family == "DENSE_ALTERNATING_BANDS_V2":
        remaining_rank = rank
        pattern = None

        for failure_components in (
            4,
            5,
            6,
        ):
            segment_count = 2 * failure_components + 1

            if n < segment_count:
                continue

            subcapacity = _weak_composition_capacity(
                total=(n - segment_count),
                part_count=(segment_count),
            )

            if remaining_rank >= subcapacity:
                remaining_rank -= subcapacity
                continue

            extras = _weak_composition_unrank(
                total=(n - segment_count),
                part_count=(segment_count),
                rank=(remaining_rank),
            )

            widths = tuple(value + 1 for value in extras)

            symbols = tuple(
                "P" if index % 2 == 0 else "F" for index in range(segment_count)
            )

            pattern = _render_segments(
                symbols=(symbols),
                widths=(widths),
            )

            break

        if pattern is None:
            raise HveeContractError("dense alternating catalog resolution failed")

    else:
        raise HveeContractError("unsupported fresh V2 development family")

    return _validate_pattern(
        pattern,
        candidate_count=n,
    )


def _catalog_offset(
    *,
    namespace: str,
    candidate_count: int,
    family: str,
    capacity: int,
) -> int:
    normalized_namespace = _require_namespace(namespace)

    normalized_family = _require_family(family)

    normalized_candidate_count = _require_candidate_count(candidate_count)

    if (
        isinstance(
            capacity,
            bool,
        )
        or not isinstance(
            capacity,
            int,
        )
        or capacity < 1
    ):
        raise HveeContractError("catalog capacity must be positive integer")

    context = [
        GENERATOR_KEY,
        GENERATOR_VERSION,
        normalized_namespace,
        normalized_candidate_count,
        normalized_family,
        "catalog_offset",
    ]

    return _sha256_uint64(context) % capacity


def _select_base_patterns_for_family(
    *,
    namespace: str,
    candidate_count: int,
    family: str,
    used_raw_patterns: set[str],
) -> tuple[str, ...]:
    normalized_namespace = _require_namespace(namespace)

    normalized_candidate_count = _require_candidate_count(candidate_count)

    normalized_family = _require_family(family)

    if not isinstance(
        used_raw_patterns,
        set,
    ):
        raise HveeContractError("used_raw_patterns must be mutable set")

    capacity = _family_catalog_capacity(
        family=(normalized_family),
        candidate_count=(normalized_candidate_count),
    )

    if capacity < PROBLEMS_PER_STRATUM:
        raise HveeContractError(
            "fresh V2 family catalog cannot satisfy required stratum count"
        )

    offset = _catalog_offset(
        namespace=(normalized_namespace),
        candidate_count=(normalized_candidate_count),
        family=(normalized_family),
        capacity=(capacity),
    )

    accepted = []

    for scan_index in range(capacity):
        rank = (offset + scan_index) % capacity

        pattern = _pattern_at_catalog_rank(
            family=(normalized_family),
            candidate_count=(normalized_candidate_count),
            rank=(rank),
        )

        complement = _complement_pattern(pattern)

        _validate_pattern(
            complement,
            candidate_count=(normalized_candidate_count),
        )

        if pattern == complement:
            raise HveeContractError("fresh V2 pattern cannot equal its complement")

        if pattern in used_raw_patterns or complement in used_raw_patterns:
            continue

        accepted.append(pattern)

        used_raw_patterns.add(pattern)

        used_raw_patterns.add(complement)

        if len(accepted) == PROBLEMS_PER_STRATUM:
            break

    if len(accepted) != PROBLEMS_PER_STRATUM:
        raise HveeContractError(
            "fresh V2 family catalog exhausted after global collision filtering"
        )

    return tuple(accepted)


def _select_all_base_patterns(
    *,
    namespace: str,
    candidate_count: int,
) -> dict[str, tuple[str, ...]]:
    normalized_namespace = _require_namespace(namespace)

    normalized_candidate_count = _require_candidate_count(candidate_count)

    used_raw_patterns: set[str] = set()

    result = {}

    for family in BASE_FAMILIES:
        result[family] = _select_base_patterns_for_family(
            namespace=(normalized_namespace),
            candidate_count=(normalized_candidate_count),
            family=(family),
            used_raw_patterns=(used_raw_patterns),
        )

    expected_used = len(BASE_FAMILIES) * PROBLEMS_PER_STRATUM * 2

    if len(used_raw_patterns) != expected_used:
        raise HveeContractError(
            "fresh V2 global raw-pattern uniqueness invariant failed"
        )

    return result


def _topology_sha256(
    *,
    candidate_count: int,
    topology_stratum: str,
    pattern: str,
) -> str:
    return _sha256(
        {
            "generator_key": (GENERATOR_KEY),
            "generator_version": (GENERATOR_VERSION),
            "candidate_count": (candidate_count),
            "topology_stratum": (topology_stratum),
            "pattern": (pattern),
        }
    )


def _problem_sha256(
    *,
    namespace: str,
    candidate_count: int,
    topology_stratum: str,
    ordinal: int,
    pattern: str,
    topology_sha256: str,
) -> str:
    return _sha256(
        {
            "generator_key": (GENERATOR_KEY),
            "generator_version": (GENERATOR_VERSION),
            "namespace": (namespace),
            "candidate_count": (candidate_count),
            "topology_stratum": (topology_stratum),
            "ordinal": (ordinal),
            "pattern": (pattern),
            "topology_sha256": (topology_sha256),
        }
    )


def _problem_key(
    *,
    candidate_count: int,
    topology_stratum: str,
    ordinal: int,
) -> str:
    return (
        "hetren.v2.dev."
        + str(candidate_count)
        + "."
        + topology_stratum
        + "."
        + f"{ordinal:04d}"
    )


def _build_development_corpus_for_namespace(
    *,
    namespace: str,
) -> tuple[
    FreshQualificationProblem,
    ...,
]:
    normalized_namespace = _require_namespace(namespace)

    problems = []

    problem_hashes = set()
    topology_hashes = set()
    problem_keys = set()

    for candidate_count in DEVELOPMENT_CANDIDATE_COUNTS:
        selections = _select_all_base_patterns(
            namespace=(normalized_namespace),
            candidate_count=(candidate_count),
        )

        raw_patterns_for_count = set()

        for family in BASE_FAMILIES:
            base_patterns = selections[family]

            if len(base_patterns) != PROBLEMS_PER_STRATUM:
                raise HveeContractError(
                    "fresh V2 family selection cardinality mismatch"
                )

            for complement in (
                False,
                True,
            ):
                topology_stratum = family + ("_COMPLEMENT" if complement else "")

                for ordinal, base_pattern in enumerate(base_patterns):
                    pattern = (
                        _complement_pattern(base_pattern)
                        if complement
                        else base_pattern
                    )

                    _validate_pattern(
                        pattern,
                        candidate_count=(candidate_count),
                    )

                    if pattern in raw_patterns_for_count:
                        raise HveeContractError(
                            "fresh V2 candidate-count corpus contains duplicate raw pattern"
                        )

                    raw_patterns_for_count.add(pattern)

                    topology_sha256 = _topology_sha256(
                        candidate_count=(candidate_count),
                        topology_stratum=(topology_stratum),
                        pattern=(pattern),
                    )

                    if topology_sha256 in topology_hashes:
                        raise HveeContractError(
                            "fresh V2 corpus contains duplicate topology SHA-256"
                        )

                    topology_hashes.add(topology_sha256)

                    problem_sha256 = _problem_sha256(
                        namespace=(normalized_namespace),
                        candidate_count=(candidate_count),
                        topology_stratum=(topology_stratum),
                        ordinal=(ordinal),
                        pattern=(pattern),
                        topology_sha256=(topology_sha256),
                    )

                    if problem_sha256 in problem_hashes:
                        raise HveeContractError(
                            "fresh V2 corpus contains duplicate problem SHA-256"
                        )

                    problem_hashes.add(problem_sha256)

                    problem_key = _problem_key(
                        candidate_count=(candidate_count),
                        topology_stratum=(topology_stratum),
                        ordinal=(ordinal),
                    )

                    if problem_key in problem_keys:
                        raise HveeContractError(
                            "fresh V2 corpus contains duplicate problem key"
                        )

                    problem_keys.add(problem_key)

                    problems.append(
                        FreshQualificationProblem(
                            problem_key=(problem_key),
                            partition=(DEVELOPMENT_PARTITION),
                            namespace=(normalized_namespace),
                            candidate_count=(candidate_count),
                            topology_stratum=(topology_stratum),
                            ordinal=(ordinal),
                            pattern=(pattern),
                            topology_sha256=(topology_sha256),
                            problem_sha256=(problem_sha256),
                        )
                    )

        expected_raw_patterns = len(BASE_FAMILIES) * PROBLEMS_PER_STRATUM * 2

        if len(raw_patterns_for_count) != expected_raw_patterns:
            raise HveeContractError(
                "fresh V2 candidate-count raw-pattern cardinality mismatch"
            )

    result = tuple(problems)

    if len(result) != EXPECTED_DEVELOPMENT_PROBLEM_COUNT:
        raise HveeContractError("fresh V2 development corpus cardinality mismatch")

    if (
        len(problem_hashes) != len(result)
        or len(topology_hashes) != len(result)
        or len(problem_keys) != len(result)
    ):
        raise HveeContractError(
            "fresh V2 development corpus identity uniqueness failure"
        )

    return result


def _verify_development_corpus_for_namespace(
    *,
    problems: object,
    namespace: str,
) -> bool:
    try:
        normalized_namespace = _require_namespace(namespace)

        if not isinstance(
            problems,
            tuple,
        ):
            return False

        if len(problems) != EXPECTED_DEVELOPMENT_PROBLEM_COUNT:
            return False

        expected = _build_development_corpus_for_namespace(
            namespace=(normalized_namespace),
        )

        if problems != expected:
            return False

        grouped = {}

        raw_by_count = {}

        for problem in problems:
            if not isinstance(
                problem,
                FreshQualificationProblem,
            ):
                return False

            if problem.partition != DEVELOPMENT_PARTITION:
                return False

            if problem.namespace != normalized_namespace:
                return False

            if problem.candidate_count not in DEVELOPMENT_CANDIDATE_COUNTS:
                return False

            if problem.topology_stratum not in TOPOLOGY_STRATA:
                return False

            if problem.ordinal not in range(PROBLEMS_PER_STRATUM):
                return False

            _validate_pattern(
                problem.pattern,
                candidate_count=(problem.candidate_count),
            )

            expected_topology_sha256 = _topology_sha256(
                candidate_count=(problem.candidate_count),
                topology_stratum=(problem.topology_stratum),
                pattern=(problem.pattern),
            )

            if problem.topology_sha256 != expected_topology_sha256:
                return False

            expected_problem_sha256 = _problem_sha256(
                namespace=(normalized_namespace),
                candidate_count=(problem.candidate_count),
                topology_stratum=(problem.topology_stratum),
                ordinal=(problem.ordinal),
                pattern=(problem.pattern),
                topology_sha256=(problem.topology_sha256),
            )

            if problem.problem_sha256 != expected_problem_sha256:
                return False

            expected_problem_key = _problem_key(
                candidate_count=(problem.candidate_count),
                topology_stratum=(problem.topology_stratum),
                ordinal=(problem.ordinal),
            )

            if problem.problem_key != expected_problem_key:
                return False

            group_key = (
                problem.candidate_count,
                problem.topology_stratum,
            )

            grouped.setdefault(
                group_key,
                0,
            )

            grouped[group_key] += 1

            raw_by_count.setdefault(
                problem.candidate_count,
                set(),
            )

            if problem.pattern in raw_by_count[problem.candidate_count]:
                return False

            raw_by_count[problem.candidate_count].add(problem.pattern)

        expected_group_count = len(DEVELOPMENT_CANDIDATE_COUNTS) * len(TOPOLOGY_STRATA)

        if len(grouped) != expected_group_count:
            return False

        if any(value != PROBLEMS_PER_STRATUM for value in grouped.values()):
            return False

        expected_raw_per_count = len(BASE_FAMILIES) * PROBLEMS_PER_STRATUM * 2

        if any(
            len(values) != expected_raw_per_count for values in raw_by_count.values()
        ):
            return False

        return True

    except (
        HveeContractError,
        KeyError,
        TypeError,
        ValueError,
    ):
        return False


def build_fresh_v2_development_corpus() -> tuple[
    FreshQualificationProblem,
    ...,
]:
    return _build_development_corpus_for_namespace(
        namespace=(DEVELOPMENT_NAMESPACE),
    )


def verify_fresh_v2_development_corpus(
    *,
    problems: object,
) -> bool:
    return _verify_development_corpus_for_namespace(
        problems=(problems),
        namespace=(DEVELOPMENT_NAMESPACE),
    )


__all__ = [
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

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import random


BOOTSTRAP_RESAMPLES = 10_000

BOOTSTRAP_SEED = 7_040_204_754_812_255_417

LOWER_ORDER_STATISTIC_INDEX = 24
UPPER_ORDER_STATISTIC_INDEX = 9_974

PROBLEMS_PER_STRATUM = 19

QUALIFICATION_CANDIDATE_COUNTS = (
    22,
    28,
    36,
)

TOPOLOGY_STRATA = (
    "MONOTONIC_SINGLE_TRANSITION",
    "MONOTONIC_SINGLE_TRANSITION_COMPLEMENT",
    "SINGLE_INTERIOR_REGION",
    "SINGLE_INTERIOR_REGION_COMPLEMENT",
    "TWO_DISJOINT_REGIONS",
    "TWO_DISJOINT_REGIONS_COMPLEMENT",
    "THREE_DISJOINT_REGIONS",
    "THREE_DISJOINT_REGIONS_COMPLEMENT",
    "ALTERNATING_BANDS",
    "ALTERNATING_BANDS_COMPLEMENT",
    "IRREGULAR_CLUSTERED_REGIONS",
    "IRREGULAR_CLUSTERED_REGIONS_COMPLEMENT",
)

STRATUM_COUNT = len(QUALIFICATION_CANDIDATE_COUNTS) * len(TOPOLOGY_STRATA)

EXPECTED_PROBLEM_COUNT = STRATUM_COUNT * PROBLEMS_PER_STRATUM

SYSTEM_STRATEGY = "sealed_hetren_multi_objective_behavioral_engine_v1"

PRIMARY_COMPARATORS = (
    "farthest_gap_coverage",
    "sequential_grid",
    "behavioral_evidence_gain_planner_v1",
    "behavioral_multi_region_v2_1",
)

ALL_PRIMARY_STRATEGIES = (
    SYSTEM_STRATEGY,
    *PRIMARY_COMPARATORS,
)

PRIMARY_METRICS = (
    "failure_region_recall_auc",
    "boundary_recall_auc",
)

PAIRWISE_RELATIONS = (
    "STATISTICAL_PARETO_DOMINANCE",
    "TRADEOFF",
    "MEAN_PARETO_DOMINANCE",
    "DOMINATED",
    "PARETO_NONDOMINATED",
)

PROGRAM_CLASSIFICATIONS = (
    "QUALIFICATION_INVALID",
    "QUALIFICATION_INFERIOR",
    "QUALIFIED_STATISTICAL_PARETO_ADVANTAGE",
    "QUALIFIED_MEAN_PARETO_ADVANTAGE",
    "QUALIFICATION_TRADEOFF",
    "QUALIFIED_PARETO_NONDOMINATED",
)


class QualificationStatisticalContractError(ValueError):
    pass


@dataclass(frozen=True)
class QualificationPrimaryScore:
    problem_sha256: str
    candidate_count: int
    topology_stratum: str
    strategy: str
    failure_region_recall_auc: float
    boundary_recall_auc: float


@dataclass(frozen=True)
class PrimaryMetricDeltaInterval:
    metric: str
    mean_delta: float
    lower_995: float
    upper_995: float


@dataclass(frozen=True)
class PrimaryComparatorRelation:
    comparator: str
    failure_region_recall_auc: PrimaryMetricDeltaInterval
    boundary_recall_auc: PrimaryMetricDeltaInterval
    relation: str
    statistical_pareto_dominated: bool


@dataclass(frozen=True)
class QualificationStatisticalAnalysis:
    problem_count: int
    stratum_count: int
    problems_per_stratum: int
    bootstrap_resamples: int
    bootstrap_seed: int
    pairwise_relations: tuple[
        PrimaryComparatorRelation,
        ...,
    ]
    guardrail_failures: tuple[
        str,
        ...,
    ]
    program_classification: str
    bootstrap_replicate_sha256: str
    sha256: str


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
        raise QualificationStatisticalContractError(
            "statistical analyzer value is not canonically JSON serializable"
        ) from exc


def _sha256(
    value: object,
) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _validate_sha256(
    value: object,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise QualificationStatisticalContractError("problem_sha256 must be a string")

    if len(value) != 64:
        raise QualificationStatisticalContractError(
            "problem_sha256 must contain exactly 64 hexadecimal characters"
        )

    if any(character not in "0123456789abcdef" for character in value):
        raise QualificationStatisticalContractError(
            "problem_sha256 must use lowercase hexadecimal characters"
        )

    return value


def _validate_metric(
    value: object,
    *,
    name: str,
) -> float:
    if isinstance(
        value,
        bool,
    ) or not isinstance(
        value,
        (
            int,
            float,
        ),
    ):
        raise QualificationStatisticalContractError(
            name + " must be a finite numeric value"
        )

    result = float(value)

    if not math.isfinite(result):
        raise QualificationStatisticalContractError(name + " must be finite")

    if result < 0.0 or result > 1.0:
        raise QualificationStatisticalContractError(name + " must lie within [0, 1]")

    return result


def _validate_guardrail_failures(
    failures: object,
) -> tuple[
    str,
    ...,
]:
    if not isinstance(
        failures,
        tuple,
    ):
        raise QualificationStatisticalContractError(
            "guardrail_failures must be a tuple"
        )

    normalized = []

    for failure in failures:
        if (
            not isinstance(
                failure,
                str,
            )
            or not failure.strip()
        ):
            raise QualificationStatisticalContractError(
                "guardrail failure identifiers must be non-empty strings"
            )

        normalized.append(failure)

    if len(normalized) != len(set(normalized)):
        raise QualificationStatisticalContractError(
            "guardrail failure identifiers must be unique"
        )

    return tuple(sorted(normalized))


def _strict_opposite_signs(
    first: float,
    second: float,
) -> bool:
    return (first > 0.0 and second < 0.0) or (first < 0.0 and second > 0.0)


def classify_primary_comparator_relation(
    *,
    failure_region_mean_delta: float,
    failure_region_lower_995: float,
    failure_region_upper_995: float,
    boundary_mean_delta: float,
    boundary_lower_995: float,
    boundary_upper_995: float,
) -> tuple[
    str,
    bool,
]:
    values = (
        failure_region_mean_delta,
        failure_region_lower_995,
        failure_region_upper_995,
        boundary_mean_delta,
        boundary_lower_995,
        boundary_upper_995,
    )

    if any(
        (
            isinstance(
                value,
                bool,
            )
            or not isinstance(
                value,
                (
                    int,
                    float,
                ),
            )
            or not math.isfinite(float(value))
        )
        for value in values
    ):
        raise QualificationStatisticalContractError(
            "pairwise classification requires finite numeric values"
        )

    region_mean = float(failure_region_mean_delta)

    region_lower = float(failure_region_lower_995)

    region_upper = float(failure_region_upper_995)

    boundary_mean = float(boundary_mean_delta)

    boundary_lower = float(boundary_lower_995)

    boundary_upper = float(boundary_upper_995)

    if region_lower > region_upper or boundary_lower > boundary_upper:
        raise QualificationStatisticalContractError(
            "confidence interval lower bound cannot exceed upper bound"
        )

    if (
        region_lower >= 0.0
        and boundary_lower >= 0.0
        and (region_lower > 0.0 or boundary_lower > 0.0)
    ):
        relation = "STATISTICAL_PARETO_DOMINANCE"

    elif _strict_opposite_signs(
        region_mean,
        boundary_mean,
    ):
        relation = "TRADEOFF"

    elif (
        region_mean >= 0.0
        and boundary_mean >= 0.0
        and (region_mean > 0.0 or boundary_mean > 0.0)
    ):
        relation = "MEAN_PARETO_DOMINANCE"

    elif (
        region_mean <= 0.0
        and boundary_mean <= 0.0
        and (region_mean < 0.0 or boundary_mean < 0.0)
    ):
        relation = "DOMINATED"

    else:
        relation = "PARETO_NONDOMINATED"

    statistical_pareto_dominated = (
        region_upper <= 0.0
        and boundary_upper <= 0.0
        and (region_upper < 0.0 or boundary_upper < 0.0)
    )

    return (
        relation,
        statistical_pareto_dominated,
    )


def classify_qualification_program(
    *,
    pairwise_relations: tuple[
        PrimaryComparatorRelation,
        ...,
    ],
    guardrail_failures: tuple[
        str,
        ...,
    ] = (),
) -> str:
    normalized_failures = _validate_guardrail_failures(guardrail_failures)

    if not isinstance(
        pairwise_relations,
        tuple,
    ):
        raise QualificationStatisticalContractError(
            "pairwise_relations must be a tuple"
        )

    if len(pairwise_relations) != len(PRIMARY_COMPARATORS):
        raise QualificationStatisticalContractError(
            "program classification requires exactly four primary comparator relations"
        )

    mapping = {}

    for relation in pairwise_relations:
        if not isinstance(
            relation,
            PrimaryComparatorRelation,
        ):
            raise QualificationStatisticalContractError(
                "pairwise relation uses invalid record type"
            )

        if relation.comparator not in PRIMARY_COMPARATORS:
            raise QualificationStatisticalContractError(
                "pairwise relation contains unknown primary comparator"
            )

        if relation.comparator in mapping:
            raise QualificationStatisticalContractError(
                "pairwise relation comparator is duplicated"
            )

        if relation.relation not in PAIRWISE_RELATIONS:
            raise QualificationStatisticalContractError(
                "pairwise relation contains unknown classification"
            )

        mapping[relation.comparator] = relation

    if set(mapping) != set(PRIMARY_COMPARATORS):
        raise QualificationStatisticalContractError(
            "pairwise relation comparator set is incomplete"
        )

    relations = tuple(mapping[comparator] for comparator in PRIMARY_COMPARATORS)

    if normalized_failures:
        return "QUALIFICATION_INVALID"

    if any(relation.statistical_pareto_dominated for relation in relations):
        return "QUALIFICATION_INFERIOR"

    if all(
        relation.relation == "STATISTICAL_PARETO_DOMINANCE" for relation in relations
    ):
        return "QUALIFIED_STATISTICAL_PARETO_ADVANTAGE"

    dominance_relations = {
        "STATISTICAL_PARETO_DOMINANCE",
        "MEAN_PARETO_DOMINANCE",
    }

    if all(relation.relation in dominance_relations for relation in relations) and any(
        relation.relation == "MEAN_PARETO_DOMINANCE" for relation in relations
    ):
        return "QUALIFIED_MEAN_PARETO_ADVANTAGE"

    if any(relation.relation == "TRADEOFF" for relation in relations):
        return "QUALIFICATION_TRADEOFF"

    return "QUALIFIED_PARETO_NONDOMINATED"


def _validate_and_index_scores(
    scores: tuple[
        QualificationPrimaryScore,
        ...,
    ],
) -> tuple[
    tuple[
        str,
        ...,
    ],
    dict[
        str,
        dict[
            str,
            QualificationPrimaryScore,
        ],
    ],
    tuple[
        tuple[
            int,
            str,
        ],
        ...,
    ],
    dict[
        tuple[
            int,
            str,
        ],
        tuple[
            int,
            ...,
        ],
    ],
]:
    if not isinstance(
        scores,
        tuple,
    ):
        raise QualificationStatisticalContractError("scores must be a tuple")

    expected_score_count = EXPECTED_PROBLEM_COUNT * len(ALL_PRIMARY_STRATEGIES)

    if len(scores) != expected_score_count:
        raise QualificationStatisticalContractError(
            "qualification analyzer requires exactly "
            + str(expected_score_count)
            + " primary score records"
        )

    grouped = {}

    metadata = {}

    for score in scores:
        if not isinstance(
            score,
            QualificationPrimaryScore,
        ):
            raise QualificationStatisticalContractError(
                "score tuple contains invalid record type"
            )

        problem_sha = _validate_sha256(score.problem_sha256)

        if (
            isinstance(
                score.candidate_count,
                bool,
            )
            or not isinstance(
                score.candidate_count,
                int,
            )
            or score.candidate_count not in QUALIFICATION_CANDIDATE_COUNTS
        ):
            raise QualificationStatisticalContractError(
                "qualification score uses invalid candidate_count"
            )

        if score.topology_stratum not in TOPOLOGY_STRATA:
            raise QualificationStatisticalContractError(
                "qualification score uses invalid topology_stratum"
            )

        if score.strategy not in ALL_PRIMARY_STRATEGIES:
            raise QualificationStatisticalContractError(
                "qualification score uses invalid primary strategy"
            )

        region_auc = _validate_metric(
            score.failure_region_recall_auc,
            name=("failure_region_recall_auc"),
        )

        boundary_auc = _validate_metric(
            score.boundary_recall_auc,
            name=("boundary_recall_auc"),
        )

        normalized = QualificationPrimaryScore(
            problem_sha256=(problem_sha),
            candidate_count=(score.candidate_count),
            topology_stratum=(score.topology_stratum),
            strategy=(score.strategy),
            failure_region_recall_auc=(region_auc),
            boundary_recall_auc=(boundary_auc),
        )

        current_metadata = (
            score.candidate_count,
            score.topology_stratum,
        )

        previous_metadata = metadata.get(problem_sha)

        if previous_metadata is not None and previous_metadata != current_metadata:
            raise QualificationStatisticalContractError(
                "problem metadata disagrees across strategy records"
            )

        metadata[problem_sha] = current_metadata

        strategy_mapping = grouped.setdefault(
            problem_sha,
            {},
        )

        if score.strategy in strategy_mapping:
            raise QualificationStatisticalContractError(
                "duplicate problem-strategy score pair"
            )

        strategy_mapping[score.strategy] = normalized

    if len(grouped) != EXPECTED_PROBLEM_COUNT:
        raise QualificationStatisticalContractError(
            "qualification analyzer requires exactly 684 unique problems"
        )

    required_strategies = set(ALL_PRIMARY_STRATEGIES)

    for problem_sha, mapping in grouped.items():
        if set(mapping) != required_strategies:
            raise QualificationStatisticalContractError(
                "problem "
                + problem_sha
                + " does not contain the exact five primary strategies"
            )

    expected_strata = tuple(
        (
            candidate_count,
            topology_stratum,
        )
        for candidate_count in QUALIFICATION_CANDIDATE_COUNTS
        for topology_stratum in sorted(TOPOLOGY_STRATA)
    )

    strata_problem_shas = {key: [] for key in expected_strata}

    for problem_sha, (
        candidate_count,
        topology_stratum,
    ) in metadata.items():
        key = (
            candidate_count,
            topology_stratum,
        )

        if key not in strata_problem_shas:
            raise QualificationStatisticalContractError(
                "qualification score uses unexpected stratum"
            )

        strata_problem_shas[key].append(problem_sha)

    for key, problem_shas in strata_problem_shas.items():
        if len(problem_shas) != PROBLEMS_PER_STRATUM:
            raise QualificationStatisticalContractError(
                "qualification stratum "
                + repr(key)
                + " must contain exactly 19 problems"
            )

    ordered_problem_shas = []

    stratum_indices = {}

    next_index = 0

    for key in expected_strata:
        shas = tuple(sorted(strata_problem_shas[key]))

        indices = tuple(
            range(
                next_index,
                next_index + len(shas),
            )
        )

        ordered_problem_shas.extend(shas)

        stratum_indices[key] = indices

        next_index += len(shas)

    if next_index != EXPECTED_PROBLEM_COUNT:
        raise QualificationStatisticalContractError("canonical problem indexing failed")

    return (
        tuple(ordered_problem_shas),
        grouped,
        expected_strata,
        {key: stratum_indices[key] for key in expected_strata},
    )


def analyze_fresh_qualification_primary_scores(
    *,
    scores: tuple[
        QualificationPrimaryScore,
        ...,
    ],
    guardrail_failures: tuple[
        str,
        ...,
    ] = (),
) -> QualificationStatisticalAnalysis:
    normalized_failures = _validate_guardrail_failures(guardrail_failures)

    (
        ordered_problem_shas,
        grouped,
        ordered_strata,
        stratum_indices,
    ) = _validate_and_index_scores(scores)

    delta_vectors = {
        comparator: {metric: [] for metric in PRIMARY_METRICS}
        for comparator in PRIMARY_COMPARATORS
    }

    for problem_sha in ordered_problem_shas:
        system = grouped[problem_sha][SYSTEM_STRATEGY]

        for comparator in PRIMARY_COMPARATORS:
            other = grouped[problem_sha][comparator]

            delta_vectors[comparator]["failure_region_recall_auc"].append(
                system.failure_region_recall_auc - other.failure_region_recall_auc
            )

            delta_vectors[comparator]["boundary_recall_auc"].append(
                system.boundary_recall_auc - other.boundary_recall_auc
            )

    point_estimates = {
        comparator: {
            metric: (
                math.fsum(delta_vectors[comparator][metric]) / EXPECTED_PROBLEM_COUNT
            )
            for metric in PRIMARY_METRICS
        }
        for comparator in PRIMARY_COMPARATORS
    }

    bootstrap_values = {
        comparator: {metric: [] for metric in PRIMARY_METRICS}
        for comparator in PRIMARY_COMPARATORS
    }

    rng = random.Random(BOOTSTRAP_SEED)

    replicate_hasher = hashlib.sha256()

    for replicate_index in range(BOOTSTRAP_RESAMPLES):
        sampled_indices = []

        for stratum in ordered_strata:
            indices = stratum_indices[stratum]

            if len(indices) != PROBLEMS_PER_STRATUM:
                raise QualificationStatisticalContractError(
                    "internal stratum balance changed during bootstrap"
                )

            for _ in range(PROBLEMS_PER_STRATUM):
                sampled_indices.append(indices[rng.randrange(PROBLEMS_PER_STRATUM)])

        if len(sampled_indices) != EXPECTED_PROBLEM_COUNT:
            raise QualificationStatisticalContractError(
                "bootstrap replicate size mismatch"
            )

        replicate_row = {
            "replicate_index": (replicate_index),
            "values": {},
        }

        for comparator in PRIMARY_COMPARATORS:
            comparator_row = {}

            for metric in PRIMARY_METRICS:
                values = delta_vectors[comparator][metric]

                mean_value = (
                    math.fsum(values[index] for index in sampled_indices)
                    / EXPECTED_PROBLEM_COUNT
                )

                bootstrap_values[comparator][metric].append(mean_value)

                comparator_row[metric] = mean_value

            replicate_row["values"][comparator] = comparator_row

        replicate_hasher.update(_canonical_bytes(replicate_row))

        replicate_hasher.update(b"\n")

    pairwise_relations = []

    for comparator in PRIMARY_COMPARATORS:
        metric_results = {}

        for metric in PRIMARY_METRICS:
            distribution = sorted(bootstrap_values[comparator][metric])

            if len(distribution) != BOOTSTRAP_RESAMPLES:
                raise QualificationStatisticalContractError(
                    "bootstrap distribution length mismatch"
                )

            metric_results[metric] = PrimaryMetricDeltaInterval(
                metric=metric,
                mean_delta=(point_estimates[comparator][metric]),
                lower_995=(distribution[LOWER_ORDER_STATISTIC_INDEX]),
                upper_995=(distribution[UPPER_ORDER_STATISTIC_INDEX]),
            )

        region = metric_results["failure_region_recall_auc"]

        boundary = metric_results["boundary_recall_auc"]

        (
            relation,
            statistical_pareto_dominated,
        ) = classify_primary_comparator_relation(
            failure_region_mean_delta=(region.mean_delta),
            failure_region_lower_995=(region.lower_995),
            failure_region_upper_995=(region.upper_995),
            boundary_mean_delta=(boundary.mean_delta),
            boundary_lower_995=(boundary.lower_995),
            boundary_upper_995=(boundary.upper_995),
        )

        pairwise_relations.append(
            PrimaryComparatorRelation(
                comparator=comparator,
                failure_region_recall_auc=(region),
                boundary_recall_auc=(boundary),
                relation=relation,
                statistical_pareto_dominated=(statistical_pareto_dominated),
            )
        )

    pairwise_tuple = tuple(pairwise_relations)

    program_classification = classify_qualification_program(
        pairwise_relations=(pairwise_tuple),
        guardrail_failures=(normalized_failures),
    )

    bootstrap_digest = replicate_hasher.hexdigest()

    payload = {
        "problem_count": (EXPECTED_PROBLEM_COUNT),
        "stratum_count": (STRATUM_COUNT),
        "problems_per_stratum": (PROBLEMS_PER_STRATUM),
        "bootstrap_resamples": (BOOTSTRAP_RESAMPLES),
        "bootstrap_seed": (BOOTSTRAP_SEED),
        "pairwise_relations": [asdict(relation) for relation in pairwise_tuple],
        "guardrail_failures": list(normalized_failures),
        "program_classification": (program_classification),
        "bootstrap_replicate_sha256": (bootstrap_digest),
    }

    analysis_sha = _sha256(payload)

    return QualificationStatisticalAnalysis(
        problem_count=(EXPECTED_PROBLEM_COUNT),
        stratum_count=(STRATUM_COUNT),
        problems_per_stratum=(PROBLEMS_PER_STRATUM),
        bootstrap_resamples=(BOOTSTRAP_RESAMPLES),
        bootstrap_seed=(BOOTSTRAP_SEED),
        pairwise_relations=(pairwise_tuple),
        guardrail_failures=(normalized_failures),
        program_classification=(program_classification),
        bootstrap_replicate_sha256=(bootstrap_digest),
        sha256=(analysis_sha),
    )


__all__ = [
    "ALL_PRIMARY_STRATEGIES",
    "BOOTSTRAP_RESAMPLES",
    "BOOTSTRAP_SEED",
    "EXPECTED_PROBLEM_COUNT",
    "LOWER_ORDER_STATISTIC_INDEX",
    "PAIRWISE_RELATIONS",
    "PRIMARY_COMPARATORS",
    "PRIMARY_METRICS",
    "PROBLEMS_PER_STRATUM",
    "PROGRAM_CLASSIFICATIONS",
    "PrimaryComparatorRelation",
    "PrimaryMetricDeltaInterval",
    "QualificationPrimaryScore",
    "QualificationStatisticalAnalysis",
    "QualificationStatisticalContractError",
    "STRATUM_COUNT",
    "SYSTEM_STRATEGY",
    "TOPOLOGY_STRATA",
    "UPPER_ORDER_STATISTIC_INDEX",
    "analyze_fresh_qualification_primary_scores",
    "classify_primary_comparator_relation",
    "classify_qualification_program",
]

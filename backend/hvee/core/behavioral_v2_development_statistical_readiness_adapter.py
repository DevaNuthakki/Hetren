from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import random

from hvee.core.behavioral_qualification_statistics import (
    BOOTSTRAP_RESAMPLES,
    BOOTSTRAP_SEED,
    LOWER_ORDER_STATISTIC_INDEX,
    UPPER_ORDER_STATISTIC_INDEX,
    QualificationStatisticalContractError,
    classify_primary_comparator_relation,
)


ADAPTER_KEY = "behavioral_v2_development_statistical_readiness_adapter"
ADAPTER_VERSION = "1.0.0"

PRIMARY_METRICS = (
    "failure_region_recall_auc",
    "boundary_recall_auc",
)


@dataclass(frozen=True)
class StatisticalReadinessScore:
    problem_sha256: str
    candidate_count: int
    topology_stratum: str
    strategy: str
    failure_region_recall_auc: float
    boundary_recall_auc: float


@dataclass(frozen=True)
class StatisticalReadinessShape:
    problem_count: int
    stratum_count: int
    problems_per_stratum: int
    strata: tuple[
        tuple[
            int,
            str,
        ],
        ...,
    ]


@dataclass(frozen=True)
class StatisticalReadinessInterval:
    metric: str
    mean_delta: float
    lower_995: float
    upper_995: float


@dataclass(frozen=True)
class StatisticalReadinessComparatorResult:
    reference_strategy: str
    failure_region_recall_auc: StatisticalReadinessInterval
    boundary_recall_auc: StatisticalReadinessInterval
    relation: str
    statistical_pareto_dominated: bool


@dataclass(frozen=True)
class StatisticalReadinessAnalysis:
    selected_strategy: str
    reference_strategies: tuple[str, ...]
    problem_count: int
    stratum_count: int
    problems_per_stratum: int
    bootstrap_resamples: int
    bootstrap_seed: int
    comparator_results: tuple[
        StatisticalReadinessComparatorResult,
        ...,
    ]
    bootstrap_replicate_sha256: str
    sha256: str


def _canonical_bytes(
    value: object,
) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


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

    try:
        int(
            value,
            16,
        )

    except ValueError as exc:
        raise QualificationStatisticalContractError(
            "problem_sha256 must contain hexadecimal characters"
        ) from exc

    if value != value.lower():
        raise QualificationStatisticalContractError(
            "problem_sha256 must use lowercase hexadecimal characters"
        )

    return value


def _validate_positive_integer(
    value: object,
    *,
    field: str,
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
        or value <= 0
    ):
        raise QualificationStatisticalContractError(
            field + " must be a positive integer"
        )

    return value


def _validate_strategy_name(
    value: object,
    *,
    field: str,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or not value
    ):
        raise QualificationStatisticalContractError(
            field + " must be a non-empty string"
        )

    return value


def _validate_metric(
    value: object,
    *,
    field: str,
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
        raise QualificationStatisticalContractError(field + " must be numeric")

    normalized = float(value)

    if not math.isfinite(normalized):
        raise QualificationStatisticalContractError(field + " must be finite")

    if not (0.0 <= normalized <= 1.0):
        raise QualificationStatisticalContractError(field + " must be in [0, 1]")

    return normalized


def _validate_shape(
    shape: object,
) -> tuple[
    StatisticalReadinessShape,
    tuple[
        tuple[
            int,
            str,
        ],
        ...,
    ],
]:
    if not isinstance(
        shape,
        StatisticalReadinessShape,
    ):
        raise QualificationStatisticalContractError(
            "shape must use StatisticalReadinessShape"
        )

    problem_count = _validate_positive_integer(
        shape.problem_count,
        field="problem_count",
    )

    stratum_count = _validate_positive_integer(
        shape.stratum_count,
        field="stratum_count",
    )

    problems_per_stratum = _validate_positive_integer(
        shape.problems_per_stratum,
        field="problems_per_stratum",
    )

    if problem_count != stratum_count * problems_per_stratum:
        raise QualificationStatisticalContractError(
            "shape problem count does not equal " "stratum_count * problems_per_stratum"
        )

    if not isinstance(
        shape.strata,
        tuple,
    ):
        raise QualificationStatisticalContractError("shape strata must be a tuple")

    if len(shape.strata) != stratum_count:
        raise QualificationStatisticalContractError(
            "shape stratum count does not match strata tuple"
        )

    normalized = []

    for item in shape.strata:
        if (
            not isinstance(
                item,
                tuple,
            )
            or len(item) != 2
        ):
            raise QualificationStatisticalContractError(
                "each stratum must be " "(candidate_count, topology_stratum)"
            )

        candidate_count = _validate_positive_integer(
            item[0],
            field="stratum candidate_count",
        )

        topology_stratum = item[1]

        if (
            not isinstance(
                topology_stratum,
                str,
            )
            or not topology_stratum
        ):
            raise QualificationStatisticalContractError(
                "topology_stratum must be a non-empty string"
            )

        normalized.append(
            (
                candidate_count,
                topology_stratum,
            )
        )

    if len(set(normalized)) != len(normalized):
        raise QualificationStatisticalContractError("shape contains duplicate strata")

    ordered = tuple(
        sorted(
            normalized,
            key=lambda item: (
                item[0],
                item[1],
            ),
        )
    )

    return (
        shape,
        ordered,
    )


def _validate_score(
    score: object,
) -> StatisticalReadinessScore:
    if not isinstance(
        score,
        StatisticalReadinessScore,
    ):
        raise QualificationStatisticalContractError(
            "score must use StatisticalReadinessScore"
        )

    _validate_sha256(score.problem_sha256)

    _validate_positive_integer(
        score.candidate_count,
        field="score candidate_count",
    )

    if (
        not isinstance(
            score.topology_stratum,
            str,
        )
        or not score.topology_stratum
    ):
        raise QualificationStatisticalContractError(
            "score topology_stratum must be a non-empty string"
        )

    _validate_strategy_name(
        score.strategy,
        field="score strategy",
    )

    _validate_metric(
        score.failure_region_recall_auc,
        field="failure_region_recall_auc",
    )

    _validate_metric(
        score.boundary_recall_auc,
        field="boundary_recall_auc",
    )

    return score


def analyze_statistical_readiness_scores(
    *,
    scores: tuple[
        StatisticalReadinessScore,
        ...,
    ],
    selected_strategy: str,
    reference_strategies: tuple[
        str,
        ...,
    ],
    shape: StatisticalReadinessShape,
) -> StatisticalReadinessAnalysis:
    selected = _validate_strategy_name(
        selected_strategy,
        field="selected_strategy",
    )

    if not isinstance(
        reference_strategies,
        tuple,
    ):
        raise QualificationStatisticalContractError(
            "reference_strategies must be a tuple"
        )

    if not reference_strategies:
        raise QualificationStatisticalContractError(
            "at least one reference strategy is required"
        )

    references = tuple(
        _validate_strategy_name(
            strategy,
            field="reference strategy",
        )
        for strategy in reference_strategies
    )

    if len(set(references)) != len(references):
        raise QualificationStatisticalContractError(
            "reference strategies must be unique"
        )

    if selected in references:
        raise QualificationStatisticalContractError(
            "selected strategy cannot also be a reference strategy"
        )

    (
        normalized_shape,
        ordered_strata,
    ) = _validate_shape(shape)

    if not isinstance(
        scores,
        tuple,
    ):
        raise QualificationStatisticalContractError("scores must be a tuple")

    expected_strategies = (
        selected,
        *references,
    )

    expected_score_count = normalized_shape.problem_count * len(expected_strategies)

    if len(scores) != expected_score_count:
        raise QualificationStatisticalContractError(
            "statistical readiness adapter received " "unexpected score count"
        )

    grouped: dict[
        str,
        dict[
            str,
            StatisticalReadinessScore,
        ],
    ] = {}

    metadata: dict[
        str,
        tuple[
            int,
            str,
        ],
    ] = {}

    for raw_score in scores:
        score = _validate_score(raw_score)

        if score.strategy not in expected_strategies:
            raise QualificationStatisticalContractError(
                "score contains strategy outside selected/reference set"
            )

        problem_sha = score.problem_sha256

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

        mapping = grouped.setdefault(
            problem_sha,
            {},
        )

        if score.strategy in mapping:
            raise QualificationStatisticalContractError(
                "duplicate problem-strategy score pair"
            )

        mapping[score.strategy] = score

    if len(grouped) != normalized_shape.problem_count:
        raise QualificationStatisticalContractError(
            "unique problem count does not match shape"
        )

    required_strategy_set = set(expected_strategies)

    for problem_sha, mapping in grouped.items():
        if set(mapping) != required_strategy_set:
            raise QualificationStatisticalContractError(
                "problem " + problem_sha + " does not contain the complete strategy set"
            )

    strata_problem_shas = {key: [] for key in ordered_strata}

    for problem_sha, problem_metadata in metadata.items():
        if problem_metadata not in strata_problem_shas:
            raise QualificationStatisticalContractError(
                "score uses stratum outside frozen shape"
            )

        strata_problem_shas[problem_metadata].append(problem_sha)

    for key, problem_shas in strata_problem_shas.items():
        if len(problem_shas) != normalized_shape.problems_per_stratum:
            raise QualificationStatisticalContractError(
                "stratum " + repr(key) + " does not contain exact frozen problem count"
            )

    ordered_problem_shas = []

    stratum_indices = {}

    next_index = 0

    for key in ordered_strata:
        problem_shas = tuple(sorted(strata_problem_shas[key]))

        indices = tuple(
            range(
                next_index,
                next_index + len(problem_shas),
            )
        )

        ordered_problem_shas.extend(problem_shas)

        stratum_indices[key] = indices

        next_index += len(problem_shas)

    if next_index != normalized_shape.problem_count:
        raise QualificationStatisticalContractError("canonical problem indexing failed")

    delta_vectors = {
        reference: {metric: [] for metric in PRIMARY_METRICS}
        for reference in references
    }

    for problem_sha in ordered_problem_shas:
        system = grouped[problem_sha][selected]

        for reference in references:
            other = grouped[problem_sha][reference]

            delta_vectors[reference]["failure_region_recall_auc"].append(
                system.failure_region_recall_auc - other.failure_region_recall_auc
            )

            delta_vectors[reference]["boundary_recall_auc"].append(
                system.boundary_recall_auc - other.boundary_recall_auc
            )

    point_estimates = {
        reference: {
            metric: (
                math.fsum(delta_vectors[reference][metric])
                / normalized_shape.problem_count
            )
            for metric in PRIMARY_METRICS
        }
        for reference in references
    }

    bootstrap_values = {
        reference: {metric: [] for metric in PRIMARY_METRICS}
        for reference in references
    }

    rng = random.Random(BOOTSTRAP_SEED)

    replicate_hasher = hashlib.sha256()

    for replicate_index in range(BOOTSTRAP_RESAMPLES):
        sampled_indices = []

        for stratum in ordered_strata:
            indices = stratum_indices[stratum]

            if len(indices) != normalized_shape.problems_per_stratum:
                raise QualificationStatisticalContractError(
                    "internal stratum balance changed during bootstrap"
                )

            for _ in range(normalized_shape.problems_per_stratum):
                sampled_indices.append(
                    indices[rng.randrange(normalized_shape.problems_per_stratum)]
                )

        if len(sampled_indices) != normalized_shape.problem_count:
            raise QualificationStatisticalContractError(
                "bootstrap replicate size mismatch"
            )

        replicate_row = {
            "replicate_index": (replicate_index),
            "values": {},
        }

        for reference in references:
            reference_row = {}

            for metric in PRIMARY_METRICS:
                values = delta_vectors[reference][metric]

                mean_value = (
                    math.fsum(values[index] for index in sampled_indices)
                    / normalized_shape.problem_count
                )

                bootstrap_values[reference][metric].append(mean_value)

                reference_row[metric] = mean_value

            replicate_row["values"][reference] = reference_row

        replicate_hasher.update(_canonical_bytes(replicate_row))

        replicate_hasher.update(b"\n")

    comparator_results = []

    for reference in references:
        metric_results = {}

        for metric in PRIMARY_METRICS:
            distribution = sorted(bootstrap_values[reference][metric])

            if len(distribution) != BOOTSTRAP_RESAMPLES:
                raise QualificationStatisticalContractError(
                    "bootstrap distribution length mismatch"
                )

            metric_results[metric] = StatisticalReadinessInterval(
                metric=(metric),
                mean_delta=(point_estimates[reference][metric]),
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

        comparator_results.append(
            StatisticalReadinessComparatorResult(
                reference_strategy=(reference),
                failure_region_recall_auc=(region),
                boundary_recall_auc=(boundary),
                relation=(relation),
                statistical_pareto_dominated=(statistical_pareto_dominated),
            )
        )

    result_tuple = tuple(comparator_results)

    bootstrap_digest = replicate_hasher.hexdigest()

    payload = {
        "adapter": {
            "key": (ADAPTER_KEY),
            "version": (ADAPTER_VERSION),
        },
        "selected_strategy": (selected),
        "reference_strategies": list(references),
        "problem_count": (normalized_shape.problem_count),
        "stratum_count": (normalized_shape.stratum_count),
        "problems_per_stratum": (normalized_shape.problems_per_stratum),
        "bootstrap_resamples": (BOOTSTRAP_RESAMPLES),
        "bootstrap_seed": (BOOTSTRAP_SEED),
        "lower_order_statistic_index_zero_based": (LOWER_ORDER_STATISTIC_INDEX),
        "upper_order_statistic_index_zero_based": (UPPER_ORDER_STATISTIC_INDEX),
        "comparator_results": [asdict(item) for item in result_tuple],
        "bootstrap_replicate_sha256": (bootstrap_digest),
    }

    analysis_sha = _sha256(payload)

    return StatisticalReadinessAnalysis(
        selected_strategy=(selected),
        reference_strategies=(references),
        problem_count=(normalized_shape.problem_count),
        stratum_count=(normalized_shape.stratum_count),
        problems_per_stratum=(normalized_shape.problems_per_stratum),
        bootstrap_resamples=(BOOTSTRAP_RESAMPLES),
        bootstrap_seed=(BOOTSTRAP_SEED),
        comparator_results=(result_tuple),
        bootstrap_replicate_sha256=(bootstrap_digest),
        sha256=(analysis_sha),
    )

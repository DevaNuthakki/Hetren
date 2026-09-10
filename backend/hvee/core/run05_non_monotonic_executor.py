from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Iterable

from hvee.core.contracts import HveeContractError
from hvee.core.decision import DecisionVerdict
from hvee.core.run05_non_monotonic_benchmark import (
    Run05GlobalStrategy,
    Run05IncidentStrategy,
    Run05StrategyTrace,
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
    RANDOM_BASELINE_SEEDS,
    build_run05_non_monotonic_qualification_design_bundle,
    materialize_run05_incident_anchor_manifest,
    materialize_run05_non_monotonic_problem_manifest,
)


RUN05_EXECUTOR_SCHEMA_VERSION = 1

RUN05_EXPECTED_PROBLEM_COUNT = 830
RUN05_EXPECTED_INCIDENT_ANCHOR_COUNT = 2288

RUN05_EXPECTED_PROBLEM_MANIFEST_SHA256 = (
    "30be8f44e5d3b8fc2332d2dbf992dfb03ccc3cac2b47cdbfde7e775f487d2ff0"
)

RUN05_EXPECTED_INCIDENT_ANCHOR_MANIFEST_SHA256 = (
    "53c2a9441083eab3d7125455926f762a76812d592e51be75e273bfe8f752bf34"
)

RUN05_EXPECTED_DESIGN_BUNDLE_SHA256 = (
    "60b76b7cb84ea173f04d4a14d5612640c46b5cefbfffadedc5f35adc19be379c"
)


@dataclass(frozen=True)
class Run05FrozenExecutorPlan:
    payload: dict[str, object]
    sha256: str


@dataclass(frozen=True)
class Run05DevelopmentExecutionBundle:
    payload: dict[str, object]
    sha256: str


_PROBLEM_KEYS = {
    "candidate_count",
    "failure_count",
    "failure_island_count",
    "pattern",
    "pattern_sha256",
    "problem_key",
    "selection_source",
    "stratum",
    "transition_count",
}


_INCIDENT_KEYS = {
    "candidate_count",
    "failure_island_index",
    "ground_truth_lower",
    "ground_truth_upper",
    "incident_index",
    "problem_key",
}


def _canonical_json_bytes(
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
            "Run-05 executor evidence must be canonical JSON"
        ) from exc


def _sha256_payload(
    value: object,
) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _require_sha256(
    value: object,
    *,
    field: str,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or len(value) != 64
    ):
        raise HveeContractError(f"{field} must be SHA-256 hex")

    try:
        int(
            value,
            16,
        )
    except ValueError as exc:
        raise HveeContractError(f"{field} must be SHA-256 hex") from exc

    return value.lower()


def _require_string(
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
        raise HveeContractError(f"{field} must be a non-empty string")

    return value


def _require_nonnegative_int(
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
        or value < 0
    ):
        raise HveeContractError(f"{field} must be a non-negative integer")

    return value


def _true_failure_islands(
    pattern: str,
) -> tuple[
    tuple[int, int],
    ...,
]:
    result = []
    index = 0

    while index < len(pattern):
        if pattern[index] != "F":
            index += 1
            continue

        lower = index

        while index + 1 < len(pattern) and pattern[index + 1] == "F":
            index += 1

        result.append(
            (
                lower,
                index,
            )
        )

        index += 1

    return tuple(result)


def _transition_count(
    pattern: str,
) -> int:
    return sum(
        left != right
        for left, right in zip(
            pattern,
            pattern[1:],
        )
    )


def _validate_problem_record(
    record: object,
) -> dict[str, object]:
    if (
        not isinstance(
            record,
            dict,
        )
        or set(record) != _PROBLEM_KEYS
    ):
        raise HveeContractError("Run-05 problem record schema is invalid")

    candidate_count = _require_nonnegative_int(
        record["candidate_count"],
        field="candidate count",
    )

    if candidate_count not in GLOBAL_BUDGETS:
        raise HveeContractError(
            "Run-05 problem candidate count " "is outside frozen grids"
        )

    pattern = record["pattern"]

    if (
        not isinstance(
            pattern,
            str,
        )
        or len(pattern) != candidate_count
        or any(
            value
            not in {
                "P",
                "F",
            }
            for value in pattern
        )
    ):
        raise HveeContractError("Run-05 problem pattern is invalid")

    failure_count = _require_nonnegative_int(
        record["failure_count"],
        field="failure count",
    )

    failure_island_count = _require_nonnegative_int(
        record["failure_island_count"],
        field="failure island count",
    )

    transitions = _require_nonnegative_int(
        record["transition_count"],
        field="transition count",
    )

    if failure_count != pattern.count("F"):
        raise HveeContractError("Run-05 failure count disagrees with pattern")

    islands = _true_failure_islands(pattern)

    if failure_island_count != len(islands):
        raise HveeContractError("Run-05 failure-island count " "disagrees with pattern")

    if transitions != _transition_count(pattern):
        raise HveeContractError("Run-05 transition count " "disagrees with pattern")

    _require_sha256(
        record["pattern_sha256"],
        field="pattern SHA-256",
    )

    _require_string(
        record["problem_key"],
        field="problem key",
    )

    _require_string(
        record["selection_source"],
        field="selection source",
    )

    _require_string(
        record["stratum"],
        field="stratum",
    )

    return record


def _validate_incident_record(
    *,
    record: object,
    problem: dict[str, object],
) -> dict[str, object]:
    if (
        not isinstance(
            record,
            dict,
        )
        or set(record) != _INCIDENT_KEYS
    ):
        raise HveeContractError("Run-05 incident-anchor record schema is invalid")

    problem_key = _require_string(
        record["problem_key"],
        field="incident problem key",
    )

    if problem_key != problem["problem_key"]:
        raise HveeContractError("incident problem identity mismatch")

    candidate_count = _require_nonnegative_int(
        record["candidate_count"],
        field="incident candidate count",
    )

    if candidate_count != problem["candidate_count"]:
        raise HveeContractError("incident candidate count mismatch")

    incident_index = _require_nonnegative_int(
        record["incident_index"],
        field="incident index",
    )

    failure_island_index = _require_nonnegative_int(
        record["failure_island_index"],
        field="failure island index",
    )

    lower = _require_nonnegative_int(
        record["ground_truth_lower"],
        field="ground-truth lower",
    )

    upper = _require_nonnegative_int(
        record["ground_truth_upper"],
        field="ground-truth upper",
    )

    if (
        incident_index >= candidate_count
        or lower > upper
        or upper >= candidate_count
        or not (lower <= incident_index <= upper)
    ):
        raise HveeContractError("incident-anchor bounds are invalid")

    pattern = problem["pattern"]

    if not isinstance(
        pattern,
        str,
    ):
        raise HveeContractError("problem pattern is unavailable")

    islands = _true_failure_islands(pattern)

    if failure_island_index >= len(islands):
        raise HveeContractError("failure-island index is outside pattern islands")

    if islands[failure_island_index] != (
        lower,
        upper,
    ):
        raise HveeContractError(
            "incident ground truth disagrees " "with frozen failure island"
        )

    if pattern[incident_index] != "F":
        raise HveeContractError("incident anchor is not failing")

    return record


def _task_map() -> dict[
    str,
    dict[str, object],
]:
    payload = build_run05_non_monotonic_qualification_design_bundle().payload

    return {item["key"]: item for item in payload["tasks"]}


def _find_metric(
    *,
    task_key: str,
    exact: str | None = None,
    required_tokens: tuple[
        str,
        ...,
    ] = (),
) -> str:
    task = _task_map().get(task_key)

    if task is None:
        raise HveeContractError(f"Run-05 task unavailable: {task_key}")

    primary = tuple(task["primary_metrics"])

    if exact is not None and exact in primary:
        return exact

    matches = [
        metric
        for metric in primary
        if all(token in metric for token in required_tokens)
    ]

    if len(matches) != 1:
        raise HveeContractError(
            "Run-05 primary metric resolution "
            f"is ambiguous for {task_key}: "
            f"{required_tokens}"
        )

    return matches[0]


def _metric_contract() -> dict[
    str,
    dict[str, str],
]:
    result = {
        "global_discovery": {
            "rate": (
                _find_metric(
                    task_key=("global_discovery"),
                    exact=("failure_discovery_rate"),
                )
            ),
            "auc": (
                _find_metric(
                    task_key=("global_discovery"),
                    required_tokens=(
                        "failure",
                        "discovery",
                        "auc",
                    ),
                )
            ),
            "cost": (
                _find_metric(
                    task_key=("global_discovery"),
                    exact=("experiments_to_first_failure"),
                )
            ),
        },
        "incident_anchored_characterization": {
            "exactness": (
                _find_metric(
                    task_key=("incident_anchored_characterization"),
                    exact=("incident_region_exactness"),
                )
            ),
            "auc": (
                _find_metric(
                    task_key=("incident_anchored_characterization"),
                    required_tokens=(
                        "incident",
                        "exact",
                        "auc",
                    ),
                )
            ),
            "cost": (
                _find_metric(
                    task_key=("incident_anchored_characterization"),
                    exact=("additional_evaluations_to_exact_characterization"),
                )
            ),
        },
        "multi_region_coverage": {
            "island_recall": (
                _find_metric(
                    task_key=("multi_region_coverage"),
                    exact=("failure_island_recall"),
                )
            ),
            "boundary_recall": (
                _find_metric(
                    task_key=("multi_region_coverage"),
                    exact=("boundary_recall"),
                )
            ),
            "island_auc": (
                _find_metric(
                    task_key=("multi_region_coverage"),
                    required_tokens=(
                        "failure",
                        "island",
                        "recall",
                        "auc",
                    ),
                )
            ),
            "boundary_auc": (
                _find_metric(
                    task_key=("multi_region_coverage"),
                    required_tokens=(
                        "boundary",
                        "recall",
                        "auc",
                    ),
                )
            ),
        },
    }

    tasks = _task_map()

    for task_key, resolved in result.items():
        primary = set(tasks[task_key]["primary_metrics"])

        if set(resolved.values()) != primary:
            raise HveeContractError(
                "Run-05 executor metric contract " f"does not exactly cover {task_key}"
            )

    return result


def calculate_run05_executor_sha256(
    payload: dict[str, object],
) -> str:
    if not isinstance(
        payload,
        dict,
    ):
        raise HveeContractError("Run-05 executor payload must be an object")

    return _sha256_payload(payload)


def build_run05_frozen_executor_plan() -> Run05FrozenExecutorPlan:
    design = build_run05_non_monotonic_qualification_design_bundle()

    if design.problem_manifest_sha256 != RUN05_EXPECTED_PROBLEM_MANIFEST_SHA256:
        raise HveeContractError("Run-05 frozen problem-manifest identity changed")

    if (
        design.incident_anchor_manifest_sha256
        != RUN05_EXPECTED_INCIDENT_ANCHOR_MANIFEST_SHA256
    ):
        raise HveeContractError("Run-05 frozen incident-manifest identity changed")

    if design.sha256 != RUN05_EXPECTED_DESIGN_BUNDLE_SHA256:
        raise HveeContractError("Run-05 frozen design identity changed")

    problems = materialize_run05_non_monotonic_problem_manifest()

    incidents = materialize_run05_incident_anchor_manifest()

    if len(problems) != RUN05_EXPECTED_PROBLEM_COUNT:
        raise HveeContractError("Run-05 frozen problem count changed")

    if len(incidents) != RUN05_EXPECTED_INCIDENT_ANCHOR_COUNT:
        raise HveeContractError("Run-05 frozen incident-anchor count changed")

    problem_counts = {candidate_count: 0 for candidate_count in sorted(GLOBAL_BUDGETS)}

    problem_keys = set()

    for record in problems:
        candidate_count = record.get("candidate_count")

        problem_key = record.get("problem_key")

        if (
            candidate_count not in problem_counts
            or not isinstance(
                problem_key,
                str,
            )
            or not problem_key
            or problem_key in problem_keys
        ):
            raise HveeContractError("Run-05 frozen problem-plan metadata is invalid")

        problem_counts[candidate_count] += 1

        problem_keys.add(problem_key)

    incident_counts = {
        candidate_count: 0 for candidate_count in sorted(INCIDENT_ADDITIONAL_BUDGETS)
    }

    for record in incidents:
        candidate_count = record.get("candidate_count")

        problem_key = record.get("problem_key")

        if candidate_count not in incident_counts or problem_key not in problem_keys:
            raise HveeContractError("Run-05 frozen incident-plan metadata is invalid")

        incident_counts[candidate_count] += 1

    metric_contract = _metric_contract()

    payload: dict[str, object] = {
        "schema_version": (RUN05_EXECUTOR_SCHEMA_VERSION),
        "type": ("run05_frozen_corpus_executor_plan"),
        "inputs": {
            "problem_manifest_sha256": (design.problem_manifest_sha256),
            "incident_anchor_manifest_sha256": (design.incident_anchor_manifest_sha256),
            "design_bundle_sha256": (design.sha256),
            "problem_count": (len(problems)),
            "incident_anchor_count": (len(incidents)),
            "problem_count_by_candidate_count": (problem_counts),
            "incident_anchor_count_by_candidate_count": (incident_counts),
        },
        "execution_contract": {
            "global_strategies": [item.value for item in (Run05GlobalStrategy)],
            "incident_strategies": [item.value for item in (Run05IncidentStrategy)],
            "global_budget_counts": {
                str(candidate_count): len(budgets)
                for candidate_count, budgets in GLOBAL_BUDGETS.items()
            },
            "incident_budget_counts": {
                str(candidate_count): len(budgets)
                for candidate_count, budgets in INCIDENT_ADDITIONAL_BUDGETS.items()
            },
            "random_seed_count": (len(RANDOM_BASELINE_SEEDS)),
            "random_aggregation": ("arithmetic_mean_over_problem_seed_runs"),
            "deterministic_aggregation": ("arithmetic_mean_over_problem_runs"),
            "auc_unit": ("per_problem_or_incident_then_arithmetic_mean"),
            "metric_contract": (metric_contract),
        },
        "evidence_boundary": {
            "executor_plan_built": (True),
            "problem_patterns_passed_directly_to_strategy": (False),
            "problem_identity_passed_to_strategy": (False),
            "strategy_receives_oracle_only_for_ground_truth_access": (True),
            "incident_anchor_requeried": (False),
            "frozen_corpus_executed": (False),
            "benchmark_results_seen": (False),
            "run05_execution_performed": (False),
            "behavioral_performance_qualified": (False),
            "real_ai_generalization_established": (False),
        },
    }

    return Run05FrozenExecutorPlan(
        payload=payload,
        sha256=(calculate_run05_executor_sha256(payload)),
    )


def verify_run05_frozen_executor_plan(
    *,
    payload: object,
    expected_sha256: object,
) -> bool:
    try:
        expected = _require_sha256(
            expected_sha256,
            field=("expected Run-05 executor-plan SHA-256"),
        )

        rebuilt = build_run05_frozen_executor_plan()

        return payload == rebuilt.payload and expected == rebuilt.sha256

    except (
        HveeContractError,
        TypeError,
        ValueError,
    ):
        return False


def _oracle(
    pattern: str,
):
    def oracle(
        candidate_index: int,
    ) -> DecisionVerdict:
        return (
            DecisionVerdict.FAIL
            if pattern[candidate_index] == "F"
            else DecisionVerdict.PASS
        )

    return oracle


def _digest_execution_record(
    *,
    digest,
    record: dict[str, object],
) -> None:
    digest.update(_canonical_json_bytes(record))

    digest.update(b"\n")


def _trace_record(
    *,
    problem_key: str,
    trace: Run05StrategyTrace,
    budget: int,
    score: dict[
        str,
        float,
    ],
    seed: int | None,
    incident_index: int | None,
) -> dict[str, object]:
    return {
        "problem_key": (problem_key),
        "task": (trace.task),
        "strategy": (trace.strategy),
        "candidate_count": (trace.candidate_count),
        "budget": (budget),
        "seed": (seed),
        "incident_index": (incident_index),
        "observations": [
            [
                candidate_index,
                verdict,
            ]
            for candidate_index, verdict in trace.observations
        ],
        "terminal_status": (trace.terminal_status),
        "score": {key: float(value) for key, value in sorted(score.items())},
    }


def _append_metrics(
    accumulator: dict[
        str,
        list[float],
    ],
    metrics: dict[
        str,
        float,
    ],
) -> None:
    for key, value in metrics.items():
        numeric = float(value)

        if not math.isfinite(numeric):
            raise HveeContractError("Run-05 executor produced non-finite metric")

        accumulator.setdefault(
            key,
            [],
        ).append(numeric)


def _aggregate_metric_samples(
    samples: dict[
        str,
        list[float],
    ],
) -> dict[
    str,
    float,
]:
    if not samples:
        raise HveeContractError("Run-05 executor metric samples are empty")

    return {
        key: (aggregate_run05_metric(values)) for key, values in sorted(samples.items())
    }


def _global_unit_metrics(
    *,
    problem: dict[str, object],
    strategy: Run05GlobalStrategy,
    seed: int | None,
    metric_contract: dict[
        str,
        dict[str, str],
    ],
    execution_digest,
) -> tuple[
    dict[str, float],
    dict[str, float],
    int,
]:
    problem_key = problem["problem_key"]

    candidate_count = problem["candidate_count"]

    pattern = problem["pattern"]

    if (
        not isinstance(
            problem_key,
            str,
        )
        or not isinstance(
            candidate_count,
            int,
        )
        or not isinstance(
            pattern,
            str,
        )
    ):
        raise HveeContractError("validated Run-05 problem became invalid")

    budgets = GLOBAL_BUDGETS[candidate_count]

    discovery_curve = []
    island_curve = []
    boundary_curve = []

    maximum_score = None
    execution_count = 0

    for budget in budgets:
        trace = run_run05_global_strategy(
            strategy=(strategy),
            candidate_count=(candidate_count),
            maximum_evaluations=(budget),
            oracle=(_oracle(pattern)),
            seed=seed,
        )

        score = score_run05_global_trace(
            trace=trace,
            pattern=pattern,
        )

        discovery_curve.append(score["failure_discovery_rate"])

        island_curve.append(score["failure_island_recall"])

        boundary_curve.append(score["boundary_recall"])

        maximum_score = score

        _digest_execution_record(
            digest=(execution_digest),
            record=(
                _trace_record(
                    problem_key=(problem_key),
                    trace=trace,
                    budget=budget,
                    score=score,
                    seed=seed,
                    incident_index=None,
                )
            ),
        )

        execution_count += 1

    if maximum_score is None:
        raise HveeContractError("Run-05 global unit produced no scores")

    global_names = metric_contract["global_discovery"]

    multi_names = metric_contract["multi_region_coverage"]

    global_metrics = {
        global_names["rate"]: (maximum_score["failure_discovery_rate"]),
        global_names["auc"]: (
            calculate_run05_normalized_auc(
                candidate_count=(candidate_count),
                budgets=budgets,
                values=(discovery_curve),
                incident=False,
            )
        ),
        global_names["cost"]: (maximum_score["experiments_to_first_failure"]),
    }

    multi_metrics = {
        multi_names["island_recall"]: (maximum_score["failure_island_recall"]),
        multi_names["boundary_recall"]: (maximum_score["boundary_recall"]),
        multi_names["island_auc"]: (
            calculate_run05_normalized_auc(
                candidate_count=(candidate_count),
                budgets=budgets,
                values=(island_curve),
                incident=False,
            )
        ),
        multi_names["boundary_auc"]: (
            calculate_run05_normalized_auc(
                candidate_count=(candidate_count),
                budgets=budgets,
                values=(boundary_curve),
                incident=False,
            )
        ),
    }

    return (
        global_metrics,
        multi_metrics,
        execution_count,
    )


def _incident_unit_metrics(
    *,
    problem: dict[str, object],
    incident: dict[str, object],
    strategy: Run05IncidentStrategy,
    metric_contract: dict[
        str,
        dict[str, str],
    ],
    execution_digest,
) -> tuple[
    dict[str, float],
    int,
]:
    problem_key = problem["problem_key"]

    candidate_count = problem["candidate_count"]

    pattern = problem["pattern"]

    incident_index = incident["incident_index"]

    if (
        not isinstance(
            problem_key,
            str,
        )
        or not isinstance(
            candidate_count,
            int,
        )
        or not isinstance(
            pattern,
            str,
        )
        or not isinstance(
            incident_index,
            int,
        )
    ):
        raise HveeContractError("validated Run-05 incident became invalid")

    budgets = INCIDENT_ADDITIONAL_BUDGETS[candidate_count]

    exactness_curve = []
    maximum_score = None
    execution_count = 0

    for budget in budgets:
        trace = run_run05_incident_strategy(
            strategy=(strategy),
            candidate_count=(candidate_count),
            incident_index=(incident_index),
            maximum_additional_evaluations=(budget),
            oracle=(_oracle(pattern)),
        )

        score = score_run05_incident_trace(
            trace=trace,
            pattern=pattern,
        )

        exactness_curve.append(score["incident_region_exactness"])

        maximum_score = score

        _digest_execution_record(
            digest=(execution_digest),
            record=(
                _trace_record(
                    problem_key=(problem_key),
                    trace=trace,
                    budget=budget,
                    score=score,
                    seed=None,
                    incident_index=(incident_index),
                )
            ),
        )

        execution_count += 1

    if maximum_score is None:
        raise HveeContractError("Run-05 incident unit produced no scores")

    names = metric_contract["incident_anchored_characterization"]

    metrics = {
        names["exactness"]: (maximum_score["incident_region_exactness"]),
        names["auc"]: (
            calculate_run05_normalized_auc(
                candidate_count=(candidate_count),
                budgets=budgets,
                values=(exactness_curve),
                incident=True,
            )
        ),
        names["cost"]: (
            maximum_score["additional_evaluations_to_exact_characterization"]
        ),
    }

    return (
        metrics,
        execution_count,
    )


def _execute_records(
    *,
    problems: Iterable[dict[str, object]],
    incidents: Iterable[dict[str, object]],
    frozen_inputs: bool,
    input_identity: dict[
        str,
        object,
    ],
) -> Run05DevelopmentExecutionBundle:
    normalized_problems = tuple(_validate_problem_record(record) for record in problems)

    if not normalized_problems:
        raise HveeContractError("Run-05 executor requires problem records")

    problems_by_key = {}

    for problem in normalized_problems:
        problem_key = problem["problem_key"]

        if problem_key in problems_by_key:
            raise HveeContractError("Run-05 problem keys must be unique")

        problems_by_key[problem_key] = problem

    normalized_incidents = []

    for incident in incidents:
        if not isinstance(
            incident,
            dict,
        ):
            raise HveeContractError("Run-05 incident record must be an object")

        problem_key = incident.get("problem_key")

        if problem_key not in problems_by_key:
            raise HveeContractError("Run-05 incident references unknown problem")

        normalized_incidents.append(
            _validate_incident_record(
                record=incident,
                problem=(problems_by_key[problem_key]),
            )
        )

    if not normalized_incidents:
        raise HveeContractError("Run-05 executor requires incident records")

    metric_contract = _metric_contract()

    execution_digest = hashlib.sha256()

    execution_record_count = 0

    global_samples: dict[
        str,
        dict[
            str,
            list[float],
        ],
    ] = {}

    multi_samples: dict[
        str,
        dict[
            str,
            list[float],
        ],
    ] = {}

    global_unit_counts: dict[
        str,
        int,
    ] = {}

    for strategy in Run05GlobalStrategy:
        strategy_key = strategy.value

        global_samples[strategy_key] = {}

        multi_samples[strategy_key] = {}

        global_unit_counts[strategy_key] = 0

        seeds: tuple[
            int | None,
            ...,
        ]

        if strategy == Run05GlobalStrategy.SEEDED_RANDOM:
            seeds = tuple(RANDOM_BASELINE_SEEDS)

        else:
            seeds = (None,)

        for problem in normalized_problems:
            for seed in seeds:
                (
                    global_metrics,
                    multi_metrics,
                    execution_count,
                ) = _global_unit_metrics(
                    problem=problem,
                    strategy=strategy,
                    seed=seed,
                    metric_contract=(metric_contract),
                    execution_digest=(execution_digest),
                )

                _append_metrics(
                    global_samples[strategy_key],
                    global_metrics,
                )

                _append_metrics(
                    multi_samples[strategy_key],
                    multi_metrics,
                )

                global_unit_counts[strategy_key] += 1

                execution_record_count += execution_count

    incident_samples: dict[
        str,
        dict[
            str,
            list[float],
        ],
    ] = {}

    incident_unit_counts: dict[
        str,
        int,
    ] = {}

    for strategy in Run05IncidentStrategy:
        strategy_key = strategy.value

        incident_samples[strategy_key] = {}

        incident_unit_counts[strategy_key] = 0

        for incident in normalized_incidents:
            problem = problems_by_key[incident["problem_key"]]

            (
                incident_metrics,
                execution_count,
            ) = _incident_unit_metrics(
                problem=problem,
                incident=incident,
                strategy=strategy,
                metric_contract=(metric_contract),
                execution_digest=(execution_digest),
            )

            _append_metrics(
                incident_samples[strategy_key],
                incident_metrics,
            )

            incident_unit_counts[strategy_key] += 1

            execution_record_count += execution_count

    global_aggregates = {
        strategy: (_aggregate_metric_samples(samples))
        for strategy, samples in sorted(global_samples.items())
    }

    multi_aggregates = {
        strategy: (_aggregate_metric_samples(samples))
        for strategy, samples in sorted(multi_samples.items())
    }

    incident_aggregates = {
        strategy: (_aggregate_metric_samples(samples))
        for strategy, samples in sorted(incident_samples.items())
    }

    hetren_global = Run05GlobalStrategy.HETREN_GENERALIZED.value

    hetren_incident = Run05IncidentStrategy.HETREN_GENERALIZED.value

    global_verdict = classify_run05_development_verdict(
        task_key=("global_discovery"),
        hetren_metrics=(global_aggregates[hetren_global]),
        baseline_metrics={
            strategy: metrics
            for strategy, metrics in global_aggregates.items()
            if strategy != hetren_global
        },
    )

    multi_verdict = classify_run05_development_verdict(
        task_key=("multi_region_coverage"),
        hetren_metrics=(multi_aggregates[hetren_global]),
        baseline_metrics={
            strategy: metrics
            for strategy, metrics in multi_aggregates.items()
            if strategy != hetren_global
        },
    )

    incident_verdict = classify_run05_development_verdict(
        task_key=("incident_anchored_characterization"),
        hetren_metrics=(incident_aggregates[hetren_incident]),
        baseline_metrics={
            strategy: metrics
            for strategy, metrics in incident_aggregates.items()
            if strategy != hetren_incident
        },
    )

    payload: dict[str, object] = {
        "schema_version": (RUN05_EXECUTOR_SCHEMA_VERSION),
        "type": ("run05_non_monotonic_development_execution"),
        "inputs": (input_identity),
        "execution": {
            "problem_count": (len(normalized_problems)),
            "incident_anchor_count": (len(normalized_incidents)),
            "global_unit_counts": (global_unit_counts),
            "incident_unit_counts": (incident_unit_counts),
            "execution_record_count": (execution_record_count),
            "execution_records_sha256": (execution_digest.hexdigest()),
        },
        "tasks": {
            "global_discovery": {
                "strategy_metrics": (global_aggregates),
                "development_verdict": (global_verdict),
            },
            "incident_anchored_characterization": {
                "strategy_metrics": (incident_aggregates),
                "development_verdict": (incident_verdict),
            },
            "multi_region_coverage": {
                "strategy_metrics": (multi_aggregates),
                "development_verdict": (multi_verdict),
            },
        },
        "metric_contract": (metric_contract),
        "evidence_boundary": {
            "development_execution_performed": (True),
            "frozen_corpus_executed": (frozen_inputs),
            "run05_execution_performed": (frozen_inputs),
            "problem_patterns_passed_directly_to_strategy": (False),
            "problem_identity_passed_to_strategy": (False),
            "strategy_ground_truth_access_via_oracle_only": (True),
            "incident_anchor_requeried": (False),
            "random_aggregation_is_problem_seed_mean": (True),
            "deterministic_aggregation_is_problem_mean": (True),
            "auc_computed_per_unit_before_aggregation": (True),
            "development_result_only": (True),
            "statistical_generalization_established": (False),
            "behavioral_performance_qualified": (False),
            "real_ai_generalization_established": (False),
            "model_inference_performed": (False),
            "asr_execution_performed": (False),
        },
    }

    return Run05DevelopmentExecutionBundle(
        payload=payload,
        sha256=(calculate_run05_executor_sha256(payload)),
    )


def execute_run05_development_benchmark_records(
    *,
    problems: Iterable[dict[str, object]],
    incidents: Iterable[dict[str, object]],
) -> Run05DevelopmentExecutionBundle:
    return _execute_records(
        problems=problems,
        incidents=incidents,
        frozen_inputs=False,
        input_identity={
            "source": ("caller_supplied_development_records"),
            "frozen_run05_manifest_bound": (False),
        },
    )


def execute_run05_frozen_development_benchmark() -> Run05DevelopmentExecutionBundle:
    plan = build_run05_frozen_executor_plan()

    problems = materialize_run05_non_monotonic_problem_manifest()

    incidents = materialize_run05_incident_anchor_manifest()

    result = _execute_records(
        problems=problems,
        incidents=incidents,
        frozen_inputs=True,
        input_identity={
            "source": ("sealed_run05_frozen_manifests"),
            "executor_plan_sha256": (plan.sha256),
            "problem_manifest_sha256": (RUN05_EXPECTED_PROBLEM_MANIFEST_SHA256),
            "incident_anchor_manifest_sha256": (
                RUN05_EXPECTED_INCIDENT_ANCHOR_MANIFEST_SHA256
            ),
            "design_bundle_sha256": (RUN05_EXPECTED_DESIGN_BUNDLE_SHA256),
            "problem_count": (RUN05_EXPECTED_PROBLEM_COUNT),
            "incident_anchor_count": (RUN05_EXPECTED_INCIDENT_ANCHOR_COUNT),
        },
    )

    boundary = result.payload["evidence_boundary"]

    if (
        boundary["frozen_corpus_executed"] is not True
        or boundary["run05_execution_performed"] is not True
    ):
        raise HveeContractError("Run-05 frozen execution boundary is invalid")

    return result


def verify_run05_development_execution_bundle(
    *,
    payload: object,
    expected_sha256: object,
) -> bool:
    try:
        expected = _require_sha256(
            expected_sha256,
            field=("expected Run-05 execution SHA-256"),
        )

        if not isinstance(
            payload,
            dict,
        ):
            return False

        return calculate_run05_executor_sha256(payload) == expected

    except (
        HveeContractError,
        TypeError,
        ValueError,
    ):
        return False

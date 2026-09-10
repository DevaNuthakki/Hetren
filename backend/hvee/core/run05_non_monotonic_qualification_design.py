from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json

from hvee.core.contracts import HveeContractError


RUN05_NON_MONOTONIC_DESIGN_SCHEMA_VERSION = 1

RUN05_NON_MONOTONIC_DESIGN_KEY = "hetren.run05.non_monotonic_qualification"

MEDIUM_CORPUS_SELECTION_SEED = "hetren-run05-non-monotonic-v1-medium-stratified"

MEDIUM_STRATUM_QUOTA = 16

EXPECTED_PROBLEM_MANIFEST_SHA256 = (
    "30be8f44e5d3b8fc2332d2dbf992dfb03ccc3cac2b47cdbfde7e775f487d2ff0"
)

EXPECTED_INCIDENT_ANCHOR_MANIFEST_SHA256 = (
    "53c2a9441083eab3d7125455926f762a76812d592e51be75e273bfe8f752bf34"
)

RANDOM_BASELINE_SEEDS = (
    3,
    7,
    11,
    19,
    23,
    31,
    43,
    59,
    67,
    73,
    83,
    97,
    101,
    109,
    127,
    149,
)

GLOBAL_BUDGETS = {
    9: (
        2,
        3,
        4,
        5,
        6,
        7,
        8,
        9,
    ),
    17: (
        2,
        4,
        6,
        8,
        10,
        12,
        14,
        17,
    ),
}

INCIDENT_ADDITIONAL_BUDGETS = {
    9: (
        1,
        2,
        3,
        4,
        5,
        6,
        8,
    ),
    17: (
        1,
        2,
        4,
        6,
        8,
        10,
        12,
        16,
    ),
}


@dataclass(frozen=True)
class _ManifestRecord:
    problem_key: str
    candidate_count: int
    pattern: str
    pattern_sha256: str
    transition_count: int
    failure_count: int
    failure_island_count: int
    selection_source: str
    stratum: str


@dataclass(frozen=True)
class Run05NonMonotonicQualificationDesignBundle:
    payload: dict[str, object]
    problem_manifest_sha256: str
    incident_anchor_manifest_sha256: str
    sha256: str


def _canonical_sha256(
    value: object,
) -> str:
    try:
        encoded = json.dumps(
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
            "Run-05 design evidence must be canonical JSON"
        ) from exc

    return hashlib.sha256(encoded).hexdigest()


def _pattern_sha256(
    pattern: str,
) -> str:
    return hashlib.sha256(pattern.encode("utf-8")).hexdigest()


def _pattern_from_integer(
    *,
    candidate_count: int,
    value: int,
) -> str:
    bits = format(
        value,
        f"0{candidate_count}b",
    )

    return "".join("F" if bit == "1" else "P" for bit in bits)


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


def _failure_islands(
    pattern: str,
) -> tuple[
    tuple[int, int],
    ...,
]:
    islands: list[tuple[int, int]] = []

    index = 0

    while index < len(pattern):
        if pattern[index] != "F":
            index += 1
            continue

        lower = index

        while index + 1 < len(pattern) and pattern[index + 1] == "F":
            index += 1

        islands.append(
            (
                lower,
                index,
            )
        )

        index += 1

    return tuple(islands)


def _transition_bucket(
    transition_count: int,
) -> str:
    if transition_count <= 7:
        return str(transition_count)

    return "8_plus"


def _density_bucket(
    *,
    failure_count: int,
    candidate_count: int,
) -> str:
    if failure_count <= 4:
        return "sparse"

    if failure_count >= (candidate_count - 4):
        return "dense"

    return "medium"


def _manifest_record(
    *,
    candidate_count: int,
    pattern: str,
    selection_source: str,
    stratum: str,
) -> _ManifestRecord:
    transitions = _transition_count(pattern)

    failures = pattern.count("F")

    islands = _failure_islands(pattern)

    pattern_sha = _pattern_sha256(pattern)

    return _ManifestRecord(
        problem_key=(f"run05-n{candidate_count}-" f"{pattern_sha}"),
        candidate_count=(candidate_count),
        pattern=pattern,
        pattern_sha256=(pattern_sha),
        transition_count=(transitions),
        failure_count=(failures),
        failure_island_count=(len(islands)),
        selection_source=(selection_source),
        stratum=stratum,
    )


@lru_cache(maxsize=1)
def _materialize_manifest_records() -> tuple[
    _ManifestRecord,
    ...,
]:
    records: list[_ManifestRecord] = []

    for value in range(1 << 9):
        pattern = _pattern_from_integer(
            candidate_count=9,
            value=value,
        )

        transitions = _transition_count(pattern)

        if transitions < 2:
            continue

        records.append(
            _manifest_record(
                candidate_count=9,
                pattern=pattern,
                selection_source=("exhaustive_n9"),
                stratum=(f"transitions_" f"{transitions}"),
            )
        )

    groups: dict[
        tuple[str, str],
        list[tuple[str, str]],
    ] = {}

    for value in range(1 << 17):
        pattern = _pattern_from_integer(
            candidate_count=17,
            value=value,
        )

        transitions = _transition_count(pattern)

        if transitions < 2:
            continue

        failures = pattern.count("F")

        transition_bucket = _transition_bucket(transitions)

        density_bucket = _density_bucket(
            failure_count=failures,
            candidate_count=17,
        )

        group_key = (
            transition_bucket,
            density_bucket,
        )

        selection_rank = hashlib.sha256(
            (MEDIUM_CORPUS_SELECTION_SEED + ":" + pattern).encode("utf-8")
        ).hexdigest()

        groups.setdefault(
            group_key,
            [],
        ).append(
            (
                selection_rank,
                pattern,
            )
        )

    for group_key in sorted(groups):
        transition_bucket, density_bucket = group_key

        ranked = sorted(groups[group_key])

        selected = ranked[:MEDIUM_STRATUM_QUOTA]

        if len(selected) != MEDIUM_STRATUM_QUOTA:
            raise HveeContractError(
                "Run-05 medium corpus stratum " "does not satisfy frozen quota"
            )

        stratum = f"transitions_{transition_bucket}" f"__density_{density_bucket}"

        for (
            _selection_rank,
            pattern,
        ) in selected:
            records.append(
                _manifest_record(
                    candidate_count=17,
                    pattern=pattern,
                    selection_source=("stratified_n17"),
                    stratum=stratum,
                )
            )

    return tuple(records)


def materialize_run05_non_monotonic_problem_manifest() -> tuple[
    dict[str, object],
    ...,
]:
    return tuple(
        {
            "problem_key": (record.problem_key),
            "candidate_count": (record.candidate_count),
            "pattern": (record.pattern),
            "pattern_sha256": (record.pattern_sha256),
            "transition_count": (record.transition_count),
            "failure_count": (record.failure_count),
            "failure_island_count": (record.failure_island_count),
            "selection_source": (record.selection_source),
            "stratum": (record.stratum),
        }
        for record in (_materialize_manifest_records())
    )


def materialize_run05_incident_anchor_manifest() -> tuple[
    dict[str, object],
    ...,
]:
    anchors: list[dict[str, object]] = []

    for record in _materialize_manifest_records():
        for (
            island_index,
            (
                lower,
                upper,
            ),
        ) in enumerate(_failure_islands(record.pattern)):
            incident_index = (lower + upper) // 2

            anchors.append(
                {
                    "problem_key": (record.problem_key),
                    "candidate_count": (record.candidate_count),
                    "failure_island_index": (island_index),
                    "incident_index": (incident_index),
                    "ground_truth_lower": (lower),
                    "ground_truth_upper": (upper),
                }
            )

    return tuple(anchors)


def _problem_manifest_evidence() -> list[dict[str, object]]:
    return [
        {
            "problem_key": (record.problem_key),
            "candidate_count": (record.candidate_count),
            "pattern_sha256": (record.pattern_sha256),
            "transition_count": (record.transition_count),
            "failure_count": (record.failure_count),
            "failure_island_count": (record.failure_island_count),
            "selection_source": (record.selection_source),
            "stratum": (record.stratum),
        }
        for record in (_materialize_manifest_records())
    ]


def _incident_anchor_evidence() -> list[dict[str, object]]:
    return [dict(item) for item in (materialize_run05_incident_anchor_manifest())]


def calculate_run05_non_monotonic_qualification_design_sha256(
    payload: dict[str, object],
) -> str:
    if not isinstance(
        payload,
        dict,
    ):
        raise HveeContractError("Run-05 design payload must be an object")

    return _canonical_sha256(payload)


def build_run05_non_monotonic_qualification_design_bundle() -> (
    Run05NonMonotonicQualificationDesignBundle
):
    problem_manifest = _problem_manifest_evidence()

    incident_manifest = _incident_anchor_evidence()

    problem_manifest_sha256 = _canonical_sha256(problem_manifest)

    incident_anchor_manifest_sha256 = _canonical_sha256(incident_manifest)

    if problem_manifest_sha256 != EXPECTED_PROBLEM_MANIFEST_SHA256:
        raise HveeContractError(
            "Run-05 problem manifest identity " "does not match precommitted SHA-256"
        )

    if incident_anchor_manifest_sha256 != EXPECTED_INCIDENT_ANCHOR_MANIFEST_SHA256:
        raise HveeContractError(
            "Run-05 incident-anchor manifest identity "
            "does not match precommitted SHA-256"
        )

    exhaustive_count = sum(
        record.selection_source == "exhaustive_n9"
        for record in (_materialize_manifest_records())
    )

    stratified_count = sum(
        record.selection_source == "stratified_n17"
        for record in (_materialize_manifest_records())
    )

    payload: dict[
        str,
        object,
    ] = {
        "schema_version": (RUN05_NON_MONOTONIC_DESIGN_SCHEMA_VERSION),
        "type": ("run05_non_monotonic_qualification_design"),
        "design": {
            "key": (RUN05_NON_MONOTONIC_DESIGN_KEY),
            "version": "1.0.0",
            "status": "precommitted",
        },
        "scientific_scope": {
            "development_benchmark": (True),
            "global_discovery_separate_from_incident_characterization": (True),
            "arbitrary_pattern_complete_discovery_guaranteed": (False),
            "single_boundary_localization_already_qualified_separately": (True),
            "multi_boundary_behavior_requires_higher_level_representation": (True),
        },
        "corpus": {
            "small_exhaustive": {
                "candidate_count": 9,
                "selection_rule": (
                    "every binary pass/fail pattern "
                    "with at least two adjacent verdict "
                    "transitions"
                ),
                "expected_problem_count": (exhaustive_count),
            },
            "medium_stratified": {
                "candidate_count": 17,
                "selection_seed": (MEDIUM_CORPUS_SELECTION_SEED),
                "selection_rule": (
                    "SHA256-ranked deterministic sample "
                    "within transition-count and failure-density "
                    "strata"
                ),
                "transition_buckets": [
                    "2",
                    "3",
                    "4",
                    "5",
                    "6",
                    "7",
                    "8_plus",
                ],
                "density_buckets": [
                    "sparse",
                    "medium",
                    "dense",
                ],
                "quota_per_stratum": (MEDIUM_STRATUM_QUOTA),
                "expected_stratum_count": 21,
                "expected_problem_count": (stratified_count),
            },
            "total_problem_count": (len(problem_manifest)),
            "problem_manifest_sha256": (problem_manifest_sha256),
        },
        "incident_anchor_corpus": {
            "selection_rule": (
                "one pre-existing confirmed failing anchor "
                "per true contiguous failure island"
            ),
            "anchor_selection": ("floor midpoint of the failure island"),
            "anchor_evaluation_cost_units": 0,
            "additional_probe_cost_units": 1,
            "incident_anchor_count": (len(incident_manifest)),
            "incident_anchor_manifest_sha256": (incident_anchor_manifest_sha256),
        },
        "tasks": [
            {
                "key": "global_discovery",
                "strategy_visible_fields": [
                    "candidate_count",
                    "maximum_evaluations",
                ],
                "hidden_oracle_fields": [
                    "pattern",
                    "failure_indices",
                    "failure_islands",
                    "true_boundaries",
                ],
                "success_definition": ("discover at least one failing candidate"),
                "primary_metrics": [
                    "failure_discovery_rate",
                    "normalized_failure_discovery_auc_over_budget",
                    "experiments_to_first_failure",
                ],
                "baselines": [
                    "sequential_grid",
                    "seeded_random",
                    "farthest_gap_coverage",
                    "current_adaptive_v1",
                ],
            },
            {
                "key": "incident_anchored_characterization",
                "strategy_visible_fields": [
                    "candidate_count",
                    "incident_index",
                    "maximum_additional_evaluations",
                ],
                "hidden_oracle_fields": [
                    "pattern",
                    "ground_truth_failure_region",
                    "true_local_boundaries",
                ],
                "success_definition": (
                    "exactly identify the contiguous failure "
                    "region containing the confirmed incident "
                    "and all applicable surrounding boundaries"
                ),
                "primary_metrics": [
                    "incident_region_exactness",
                    "normalized_incident_exactness_auc_over_budget",
                    "additional_evaluations_to_exact_characterization",
                ],
                "baselines": [
                    "symmetric_linear_expansion",
                    "bidirectional_exponential_bisection",
                    "existing_neighborhood_ordered",
                ],
            },
            {
                "key": "multi_region_coverage",
                "strategy_visible_fields": [
                    "candidate_count",
                    "maximum_evaluations",
                ],
                "hidden_oracle_fields": [
                    "pattern",
                    "failure_islands",
                    "true_boundaries",
                ],
                "success_definition": (
                    "maximize constrained failure-island and "
                    "boundary coverage under the frozen budget"
                ),
                "primary_metrics": [
                    "failure_island_recall",
                    "boundary_recall",
                    "normalized_failure_island_recall_auc_over_budget",
                    "normalized_boundary_recall_auc_over_budget",
                ],
                "baselines": [
                    "sequential_grid",
                    "seeded_random",
                    "farthest_gap_coverage",
                    "current_adaptive_v1",
                ],
            },
        ],
        "budgets": {
            "global_and_multi_region": {
                "n9": list(GLOBAL_BUDGETS[9]),
                "n17": list(GLOBAL_BUDGETS[17]),
            },
            "incident_additional": {
                "n9": list(INCIDENT_ADDITIONAL_BUDGETS[9]),
                "n17": list(INCIDENT_ADDITIONAL_BUDGETS[17]),
            },
            "cost_contract": (
                "one new oracle evaluation equals " "one evaluation cost unit"
            ),
        },
        "random_baseline": {
            "sampling": ("without_replacement"),
            "seed_policy": ("predeclared"),
            "seeds": list(RANDOM_BASELINE_SEEDS),
        },
        "fairness_contract": {
            "same_problem_per_strategy": (True),
            "same_total_budget_per_problem": (True),
            "problem_identity_not_passed_to_strategy": (True),
            "pattern_derived_manifest_identity_scorer_only": (True),
            "hidden_pattern_not_passed_to_strategy": (True),
            "ground_truth_used_only_by_oracle_and_scorer": (True),
            "incident_anchor_preexisting": (True),
            "incident_anchor_cost_equal_for_all_strategies": (True),
            "failed_runs_preserved": (True),
            "random_seed_variance_reported": (True),
            "existing_adaptive_v1_not_modified_for_benchmark": (True),
            "existing_neighborhood_not_modified_for_benchmark": (True),
            "generalized_hetren_strategy_not_yet_implemented": (True),
        },
        "scoring_contract": {
            "global_multi_budget_x": ("maximum_evaluations divided by candidate_count"),
            "incident_budget_x": (
                "maximum_additional_evaluations divided by " "candidate_count minus one"
            ),
            "auc_integration": (
                "trapezoidal_rule_over_precommitted_budget_points_plus_origin"
            ),
            "auc_origin_x": 0.0,
            "auc_origin_metric_value": 0.0,
            "auc_normalization": (
                "x domain normalized to zero through one; "
                "reported AUC therefore lies on the metric's "
                "zero-through-one scale"
            ),
            "first_failure_cost_evaluation_point": (
                "maximum precommitted global budget for candidate_count"
            ),
            "first_failure_non_discovery_penalty": ("maximum_evaluations_plus_one"),
            "incident_exact_cost_evaluation_point": (
                "maximum precommitted incident budget for candidate_count"
            ),
            "incident_non_exact_penalty": ("maximum_additional_evaluations_plus_one"),
            "random_seed_aggregation": (
                "each seed is one run; arithmetic mean across "
                "all frozen problem-seed runs"
            ),
            "deterministic_strategy_aggregation": (
                "arithmetic mean across frozen problems"
            ),
            "higher_is_better_metrics": [
                "failure_discovery_rate",
                "normalized_failure_discovery_auc_over_budget",
                "incident_region_exactness",
                "normalized_incident_exactness_auc_over_budget",
                "failure_island_recall",
                "boundary_recall",
                "normalized_failure_island_recall_auc_over_budget",
                "normalized_boundary_recall_auc_over_budget",
            ],
            "lower_is_better_metrics": [
                "experiments_to_first_failure",
                "additional_evaluations_to_exact_characterization",
            ],
            "per_metric_strongest_baseline": (
                "best aggregate value from the predeclared "
                "baseline set independently for each primary metric"
            ),
            "numeric_comparison_tolerance": 1e-12,
            "development_superiority_rule": (
                "strictly better than the per-metric strongest "
                "baseline on at least one primary metric and "
                "not worse on every other primary metric"
            ),
            "development_tie_rule": (
                "equal to the per-metric strongest baseline " "on every primary metric"
            ),
            "development_mixed_rule": (
                "better on at least one primary metric and "
                "worse on at least one primary metric"
            ),
            "development_inferior_rule": (
                "not better on any primary metric and worse "
                "on at least one primary metric"
            ),
            "development_result_is_not_statistical_generalization": (True),
            "non_discovery_preserved_as_zero_success": (True),
            "non_coverage_preserved_in_recall_denominator": (True),
            "primary_metrics_cannot_be_replaced_after_results": (True),
            "strongest_baseline_selected_only_from_predeclared_set": (True),
            "secondary_metric_win_alone_establishes_superiority": (False),
        },
        "verdict_contract": {
            "superior": (
                "Hetren must exceed the strongest predeclared "
                "baseline on the task's primary coverage or "
                "exactness evidence without hiding regressions "
                "on the other primary metrics."
            ),
            "tie": (
                "Hetren and the strongest baseline produce "
                "equal primary task evidence."
            ),
            "mixed": (
                "Hetren improves at least one primary metric "
                "and worsens another primary metric."
            ),
            "inferior": ("Hetren is worse on the primary task evidence."),
            "no_result_spinning": (True),
        },
        "representation_requirements": {
            "single_observed_boundary_bundle_reused": (True),
            "single_boundary_bundle_semantics": ("one two-endpoint transition"),
            "higher_level_boundary_set_required": (True),
            "failure_region_identity_required": (True),
            "multiple_disjoint_regions_supported": (True),
            "opposite_boundary_directions_supported": (True),
            "do_not_collapse_multiple_transitions_into_one_threshold": (True),
        },
        "evidence_boundary": {
            "design_precommitted": (True),
            "development_corpus_frozen": (True),
            "incident_anchor_corpus_frozen": (True),
            "generalized_search_implemented": (False),
            "run05_execution_performed": (False),
            "behavioral_performance_qualified": (False),
            "development_result_is_statistical_generalization": (False),
            "real_ai_generalization_established": (False),
            "production_qualified": (False),
            "model_inference_performed": (False),
            "hidden_holdout_opened": (False),
        },
    }

    return Run05NonMonotonicQualificationDesignBundle(
        payload=payload,
        problem_manifest_sha256=(problem_manifest_sha256),
        incident_anchor_manifest_sha256=(incident_anchor_manifest_sha256),
        sha256=(calculate_run05_non_monotonic_qualification_design_sha256(payload)),
    )


def verify_run05_non_monotonic_qualification_design_bundle(
    *,
    payload: object,
    expected_sha256: object,
) -> bool:
    try:
        if (
            not isinstance(
                payload,
                dict,
            )
            or not isinstance(
                expected_sha256,
                str,
            )
            or len(expected_sha256) != 64
        ):
            return False

        int(
            expected_sha256,
            16,
        )

        rebuilt = build_run05_non_monotonic_qualification_design_bundle()

        return payload == rebuilt.payload and expected_sha256.lower() == rebuilt.sha256

    except (
        HveeContractError,
        TypeError,
        ValueError,
    ):
        return False

from __future__ import annotations

from collections import Counter
from copy import deepcopy

from hvee.core.run05_non_monotonic_qualification_design import (
    EXPECTED_INCIDENT_ANCHOR_MANIFEST_SHA256,
    EXPECTED_PROBLEM_MANIFEST_SHA256,
    INCIDENT_ADDITIONAL_BUDGETS,
    RANDOM_BASELINE_SEEDS,
    Run05NonMonotonicQualificationDesignBundle,
    build_run05_non_monotonic_qualification_design_bundle,
    calculate_run05_non_monotonic_qualification_design_sha256,
    materialize_run05_incident_anchor_manifest,
    materialize_run05_non_monotonic_problem_manifest,
    verify_run05_non_monotonic_qualification_design_bundle,
)


def _bundle():
    return build_run05_non_monotonic_qualification_design_bundle()


def _transition_count(
    pattern,
):
    return sum(
        left != right
        for left, right in zip(
            pattern,
            pattern[1:],
        )
    )


def test_design_bundle_is_reverifiable():
    bundle = _bundle()

    assert isinstance(
        bundle,
        Run05NonMonotonicQualificationDesignBundle,
    )

    assert verify_run05_non_monotonic_qualification_design_bundle(
        payload=bundle.payload,
        expected_sha256=bundle.sha256,
    )


def test_design_is_deterministic():
    first = _bundle()
    second = _bundle()

    assert first.payload == second.payload

    assert first.sha256 == second.sha256

    assert first.problem_manifest_sha256 == second.problem_manifest_sha256

    assert (
        first.incident_anchor_manifest_sha256 == second.incident_anchor_manifest_sha256
    )


def test_small_corpus_is_exhaustive_n9_non_monotonic():
    manifest = materialize_run05_non_monotonic_problem_manifest()

    small = [item for item in manifest if item["selection_source"] == "exhaustive_n9"]

    assert len(small) == 494

    assert all(item["candidate_count"] == 9 for item in small)

    assert all(_transition_count(item["pattern"]) >= 2 for item in small)


def test_small_corpus_contains_every_eligible_n9_pattern():
    expected = {
        "".join(
            "F" if bit == "1" else "P"
            for bit in format(
                value,
                "09b",
            )
        )
        for value in range(1 << 9)
    }

    expected = {pattern for pattern in expected if (_transition_count(pattern) >= 2)}

    manifest = materialize_run05_non_monotonic_problem_manifest()

    actual = {
        item["pattern"]
        for item in manifest
        if item["selection_source"] == "exhaustive_n9"
    }

    assert actual == expected


def test_medium_corpus_has_frozen_21_by_16_strata():
    manifest = materialize_run05_non_monotonic_problem_manifest()

    medium = [item for item in manifest if item["selection_source"] == "stratified_n17"]

    assert len(medium) == 336

    counts = Counter(item["stratum"] for item in medium)

    assert len(counts) == 21

    assert set(counts.values()) == {16}


def test_total_problem_count_is_frozen():
    manifest = materialize_run05_non_monotonic_problem_manifest()

    assert len(manifest) == 830


def test_all_manifest_patterns_are_non_monotonic():
    manifest = materialize_run05_non_monotonic_problem_manifest()

    assert all(item["transition_count"] >= 2 for item in manifest)


def test_problem_keys_are_unique_and_do_not_embed_pattern():
    manifest = materialize_run05_non_monotonic_problem_manifest()

    keys = [item["problem_key"] for item in manifest]

    assert len(keys) == len(set(keys))

    for item in manifest:
        assert item["pattern"] not in item["problem_key"]


def test_incident_manifest_has_one_anchor_per_failure_island():
    problems = materialize_run05_non_monotonic_problem_manifest()

    anchors = materialize_run05_incident_anchor_manifest()

    expected = sum(item["failure_island_count"] for item in problems)

    assert len(anchors) == expected


def test_incident_anchor_is_midpoint_of_true_region():
    anchors = materialize_run05_incident_anchor_manifest()

    for anchor in anchors:
        lower = anchor["ground_truth_lower"]

        upper = anchor["ground_truth_upper"]

        assert anchor["incident_index"] == (lower + upper) // 2


def test_incident_anchor_has_zero_new_evaluation_cost():
    bundle = _bundle()

    incident = bundle.payload["incident_anchor_corpus"]

    assert incident["anchor_evaluation_cost_units"] == 0

    assert incident["additional_probe_cost_units"] == 1


def test_three_scientific_tasks_are_precommitted():
    bundle = _bundle()

    tasks = {task["key"] for task in bundle.payload["tasks"]}

    assert tasks == {
        "global_discovery",
        "incident_anchored_characterization",
        "multi_region_coverage",
    }


def test_global_task_has_space_filling_strong_baseline():
    bundle = _bundle()

    task = next(
        item for item in bundle.payload["tasks"] if item["key"] == "global_discovery"
    )

    assert "farthest_gap_coverage" in task["baselines"]

    assert "current_adaptive_v1" in task["baselines"]


def test_incident_task_has_exponential_bisection_baseline():
    bundle = _bundle()

    task = next(
        item
        for item in bundle.payload["tasks"]
        if item["key"] == "incident_anchored_characterization"
    )

    assert "bidirectional_exponential_bisection" in task["baselines"]

    assert "existing_neighborhood_ordered" in task["baselines"]


def test_primary_multi_region_metrics_are_frozen():
    bundle = _bundle()

    task = next(
        item
        for item in bundle.payload["tasks"]
        if item["key"] == "multi_region_coverage"
    )

    assert task["primary_metrics"] == [
        "failure_island_recall",
        "boundary_recall",
        "normalized_failure_island_recall_auc_over_budget",
        "normalized_boundary_recall_auc_over_budget",
    ]


def test_random_baseline_seeds_are_predeclared_and_unique():
    assert len(RANDOM_BASELINE_SEEDS) == 16

    assert len(set(RANDOM_BASELINE_SEEDS)) == 16

    bundle = _bundle()

    assert bundle.payload["random_baseline"]["seeds"] == list(RANDOM_BASELINE_SEEDS)


def test_incident_budget_excludes_preexisting_anchor():
    bundle = _bundle()

    budgets = bundle.payload["budgets"]["incident_additional"]

    assert budgets["n9"] == list(INCIDENT_ADDITIONAL_BUDGETS[9])

    assert budgets["n17"] == list(INCIDENT_ADDITIONAL_BUDGETS[17])


def test_ground_truth_is_not_strategy_visible():
    bundle = _bundle()

    forbidden = {
        "pattern",
        "failure_indices",
        "failure_islands",
        "true_boundaries",
        "ground_truth_failure_region",
        "true_local_boundaries",
    }

    for task in bundle.payload["tasks"]:
        visible = set(task["strategy_visible_fields"])

        assert not (visible & forbidden)


def test_design_requires_boundary_set_representation():
    bundle = _bundle()

    requirements = bundle.payload["representation_requirements"]

    assert requirements["single_observed_boundary_bundle_reused"] is True

    assert requirements["higher_level_boundary_set_required"] is True

    assert requirements["multiple_disjoint_regions_supported"] is True

    assert (
        requirements["do_not_collapse_multiple_transitions_into_one_threshold"] is True
    )


def test_arbitrary_complete_discovery_is_not_claimed():
    bundle = _bundle()

    assert (
        bundle.payload["scientific_scope"][
            "arbitrary_pattern_complete_discovery_guaranteed"
        ]
        is False
    )


def test_generalized_algorithm_does_not_exist_in_precommitment():
    bundle = _bundle()

    assert (
        bundle.payload["fairness_contract"][
            "generalized_hetren_strategy_not_yet_implemented"
        ]
        is True
    )

    assert (
        bundle.payload["evidence_boundary"]["generalized_search_implemented"] is False
    )


def test_claim_boundary_is_precommitment_only():
    bundle = _bundle()

    boundary = bundle.payload["evidence_boundary"]

    assert boundary["design_precommitted"] is True

    assert boundary["development_corpus_frozen"] is True

    assert boundary["run05_execution_performed"] is False

    assert boundary["behavioral_performance_qualified"] is False

    assert boundary["real_ai_generalization_established"] is False

    assert boundary["model_inference_performed"] is False

    assert boundary["hidden_holdout_opened"] is False


def test_secondary_metric_alone_cannot_claim_superiority():
    bundle = _bundle()

    assert (
        bundle.payload["scoring_contract"][
            "secondary_metric_win_alone_establishes_superiority"
        ]
        is False
    )


def test_verdict_contract_allows_tie_mixed_and_inferior():
    bundle = _bundle()

    verdict = bundle.payload["verdict_contract"]

    assert {
        "superior",
        "tie",
        "mixed",
        "inferior",
        "no_result_spinning",
    } == set(verdict)


def test_verifier_rejects_recomputed_tampering():
    bundle = _bundle()

    tampered = deepcopy(bundle.payload)

    tampered["evidence_boundary"]["behavioral_performance_qualified"] = True

    tampered_sha = calculate_run05_non_monotonic_qualification_design_sha256(tampered)

    assert not (
        verify_run05_non_monotonic_qualification_design_bundle(
            payload=tampered,
            expected_sha256=tampered_sha,
        )
    )


def test_manifest_hashes_are_explicitly_precommitted():
    bundle = _bundle()

    assert bundle.problem_manifest_sha256 == EXPECTED_PROBLEM_MANIFEST_SHA256

    assert (
        bundle.incident_anchor_manifest_sha256
        == EXPECTED_INCIDENT_ANCHOR_MANIFEST_SHA256
    )


def test_problem_identity_is_not_strategy_visible():
    bundle = _bundle()

    for task in bundle.payload["tasks"]:
        assert "problem_key" not in task["strategy_visible_fields"]

    fairness = bundle.payload["fairness_contract"]

    assert fairness["problem_identity_not_passed_to_strategy"] is True

    assert fairness["pattern_derived_manifest_identity_scorer_only"] is True


def test_auc_formula_is_exactly_precommitted():
    scoring = _bundle().payload["scoring_contract"]

    assert (
        scoring["global_multi_budget_x"]
        == "maximum_evaluations divided by candidate_count"
    )

    assert scoring["incident_budget_x"] == (
        "maximum_additional_evaluations divided by " "candidate_count minus one"
    )

    assert scoring["auc_integration"] == (
        "trapezoidal_rule_over_precommitted_" "budget_points_plus_origin"
    )

    assert scoring["auc_origin_x"] == 0.0

    assert scoring["auc_origin_metric_value"] == 0.0


def test_primary_metric_orientation_is_frozen_and_complete():
    bundle = _bundle()

    scoring = bundle.payload["scoring_contract"]

    higher = set(scoring["higher_is_better_metrics"])

    lower = set(scoring["lower_is_better_metrics"])

    assert not (higher & lower)

    primary = {
        metric for task in bundle.payload["tasks"] for metric in task["primary_metrics"]
    }

    assert primary == (higher | lower)


def test_strongest_baseline_envelope_rule_is_precommitted():
    scoring = _bundle().payload["scoring_contract"]

    assert scoring["per_metric_strongest_baseline"] == (
        "best aggregate value from the predeclared "
        "baseline set independently for each primary metric"
    )

    assert scoring["numeric_comparison_tolerance"] == 1e-12

    assert (
        "not worse on every other primary metric"
        in scoring["development_superiority_rule"]
    )


def test_development_result_cannot_claim_generalization():
    bundle = _bundle()

    scoring = bundle.payload["scoring_contract"]

    boundary = bundle.payload["evidence_boundary"]

    assert scoring["development_result_is_not_statistical_generalization"] is True

    assert boundary["development_result_is_statistical_generalization"] is False

    assert boundary["behavioral_performance_qualified"] is False

    assert boundary["real_ai_generalization_established"] is False

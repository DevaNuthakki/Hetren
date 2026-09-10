from __future__ import annotations

from copy import deepcopy
import hashlib

import pytest

from hvee.core.contracts import HveeContractError
from hvee.core.run05_non_monotonic_executor import (
    RUN05_EXPECTED_DESIGN_BUNDLE_SHA256,
    RUN05_EXPECTED_INCIDENT_ANCHOR_COUNT,
    RUN05_EXPECTED_INCIDENT_ANCHOR_MANIFEST_SHA256,
    RUN05_EXPECTED_PROBLEM_COUNT,
    RUN05_EXPECTED_PROBLEM_MANIFEST_SHA256,
    build_run05_frozen_executor_plan,
    calculate_run05_executor_sha256,
    execute_run05_development_benchmark_records,
    verify_run05_development_execution_bundle,
    verify_run05_frozen_executor_plan,
)


def _sha(
    value,
):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _problem():
    pattern = "PPFPPPFPP"

    return {
        "candidate_count": 9,
        "failure_count": 2,
        "failure_island_count": 2,
        "pattern": pattern,
        "pattern_sha256": _sha(pattern),
        "problem_key": ("toy-run05-problem"),
        "selection_source": ("toy"),
        "stratum": ("toy"),
        "transition_count": 4,
    }


def _incident():
    return {
        "candidate_count": 9,
        "failure_island_index": 0,
        "ground_truth_lower": 2,
        "ground_truth_upper": 2,
        "incident_index": 2,
        "problem_key": ("toy-run05-problem"),
    }


def test_frozen_executor_plan_has_exact_input_identities():
    plan = build_run05_frozen_executor_plan()

    inputs = plan.payload["inputs"]

    assert inputs["problem_count"] == RUN05_EXPECTED_PROBLEM_COUNT

    assert inputs["incident_anchor_count"] == RUN05_EXPECTED_INCIDENT_ANCHOR_COUNT

    assert inputs["problem_manifest_sha256"] == RUN05_EXPECTED_PROBLEM_MANIFEST_SHA256

    assert (
        inputs["incident_anchor_manifest_sha256"]
        == RUN05_EXPECTED_INCIDENT_ANCHOR_MANIFEST_SHA256
    )

    assert inputs["design_bundle_sha256"] == RUN05_EXPECTED_DESIGN_BUNDLE_SHA256


def test_executor_plan_does_not_execute_frozen_corpus():
    plan = build_run05_frozen_executor_plan()

    boundary = plan.payload["evidence_boundary"]

    assert boundary["executor_plan_built"] is True

    assert boundary["frozen_corpus_executed"] is False

    assert boundary["benchmark_results_seen"] is False

    assert boundary["run05_execution_performed"] is False


def test_executor_plan_metric_contract_exactly_matches_primary_metrics():
    plan = build_run05_frozen_executor_plan()

    metric_contract = plan.payload["execution_contract"]["metric_contract"]

    assert set(metric_contract) == {
        "global_discovery",
        "incident_anchored_characterization",
        "multi_region_coverage",
    }

    assert len(metric_contract["global_discovery"]) == 3

    assert len(metric_contract["incident_anchored_characterization"]) == 3

    assert len(metric_contract["multi_region_coverage"]) == 4


def test_executor_plan_is_reverifiable():
    plan = build_run05_frozen_executor_plan()

    assert verify_run05_frozen_executor_plan(
        payload=(plan.payload),
        expected_sha256=(plan.sha256),
    )


def test_toy_development_execution_runs_all_three_tasks():
    result = execute_run05_development_benchmark_records(
        problems=(_problem(),),
        incidents=(_incident(),),
    )

    assert set(result.payload["tasks"]) == {
        "global_discovery",
        "incident_anchored_characterization",
        "multi_region_coverage",
    }

    for task in result.payload["tasks"].values():
        assert task["development_verdict"]["verdict"] in {
            "superior",
            "tie",
            "mixed",
            "inferior",
        }


def test_toy_execution_keeps_random_aggregation_as_problem_seed_runs():
    result = execute_run05_development_benchmark_records(
        problems=(_problem(),),
        incidents=(_incident(),),
    )

    counts = result.payload["execution"]["global_unit_counts"]

    assert counts["seeded_random"] == 16

    assert counts["hetren_generalized"] == 1

    assert counts["sequential_grid"] == 1

    assert counts["farthest_gap_coverage"] == 1

    assert counts["current_adaptive_v1"] == 1


def test_toy_execution_has_one_incident_unit_per_strategy():
    result = execute_run05_development_benchmark_records(
        problems=(_problem(),),
        incidents=(_incident(),),
    )

    counts = result.payload["execution"]["incident_unit_counts"]

    assert set(counts.values()) == {1}


def test_toy_execution_is_deterministic():
    first = execute_run05_development_benchmark_records(
        problems=(_problem(),),
        incidents=(_incident(),),
    )

    second = execute_run05_development_benchmark_records(
        problems=(_problem(),),
        incidents=(_incident(),),
    )

    assert first.payload == second.payload

    assert first.sha256 == second.sha256


def test_toy_execution_is_reverifiable():
    result = execute_run05_development_benchmark_records(
        problems=(_problem(),),
        incidents=(_incident(),),
    )

    assert verify_run05_development_execution_bundle(
        payload=(result.payload),
        expected_sha256=(result.sha256),
    )


def test_recomputed_payload_tampering_changes_execution_identity():
    result = execute_run05_development_benchmark_records(
        problems=(_problem(),),
        incidents=(_incident(),),
    )

    tampered = deepcopy(result.payload)

    tampered["evidence_boundary"]["behavioral_performance_qualified"] = True

    tampered_sha = calculate_run05_executor_sha256(tampered)

    assert tampered_sha != result.sha256

    assert not (
        verify_run05_development_execution_bundle(
            payload=tampered,
            expected_sha256=(result.sha256),
        )
    )


def test_toy_execution_does_not_claim_frozen_run05_execution():
    result = execute_run05_development_benchmark_records(
        problems=(_problem(),),
        incidents=(_incident(),),
    )

    boundary = result.payload["evidence_boundary"]

    assert boundary["development_execution_performed"] is True

    assert boundary["frozen_corpus_executed"] is False

    assert boundary["run05_execution_performed"] is False

    assert boundary["behavioral_performance_qualified"] is False

    assert boundary["real_ai_generalization_established"] is False


def test_problem_metadata_mismatch_fails_closed():
    problem = _problem()

    problem["failure_count"] = 3

    with pytest.raises(
        HveeContractError,
        match=("failure count disagrees"),
    ):
        execute_run05_development_benchmark_records(
            problems=(problem,),
            incidents=(_incident(),),
        )


def test_incident_ground_truth_mismatch_fails_closed():
    incident = _incident()

    incident["ground_truth_upper"] = 3

    with pytest.raises(
        HveeContractError,
        match=("ground truth disagrees"),
    ):
        execute_run05_development_benchmark_records(
            problems=(_problem(),),
            incidents=(incident,),
        )


def test_unknown_incident_problem_fails_closed():
    incident = _incident()

    incident["problem_key"] = "unknown-problem"

    with pytest.raises(
        HveeContractError,
        match=("unknown problem"),
    ):
        execute_run05_development_benchmark_records(
            problems=(_problem(),),
            incidents=(incident,),
        )

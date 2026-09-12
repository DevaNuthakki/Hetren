from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import replace
import hashlib
import inspect

import pytest

import hvee.core.behavioral_v2_fresh_development_benchmark_executor as executor
from hvee.core.behavioral_multi_objective_qualification import (
    FreshBehavioralQualificationStrategy,
    FreshQualificationProblem,
    FreshQualificationTrace,
    _trace_sha,
)
from hvee.core.behavioral_v2_fresh_development_benchmark_executor import (
    COMPLETION_POLICY,
    FROZEN_STRATEGY_ORDER,
    SEALED_HETREN_V1_REFERENCE_STRATEGY,
    FreshV2DevelopmentBenchmarkStrategy,
    _require_full_grid_trace,
    run_fresh_v2_development_benchmark_strategy,
    verify_fresh_v2_development_benchmark_execution_bundle,
)
from hvee.core.contracts import HveeContractError


def _sha(
    value: str,
) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _problem() -> FreshQualificationProblem:
    pattern = "PFFPPFPFP"

    return FreshQualificationProblem(
        problem_key=("synthetic:fresh-v2-executor"),
        partition=("synthetic"),
        namespace=("HETREN_SYNTHETIC_FRESH_V2_EXECUTOR"),
        candidate_count=(len(pattern)),
        topology_stratum=("SYNTHETIC"),
        ordinal=0,
        pattern=(pattern),
        topology_sha256=(_sha("synthetic-topology")),
        problem_sha256=(_sha("synthetic-problem")),
    )


def test_frozen_strategy_order_is_exactly_eight():
    assert FROZEN_STRATEGY_ORDER == (
        FreshV2DevelopmentBenchmarkStrategy.V2A_BALANCED_FRONTIER_CLOSURE,
        FreshV2DevelopmentBenchmarkStrategy.V2B_CLOSURE_WITH_COVERAGE_FLOOR,
        FreshV2DevelopmentBenchmarkStrategy.V2C_FAILURE_FRONTIER_STRUCTURAL,
        FreshV2DevelopmentBenchmarkStrategy.MULTI_REGION_V2_1,
        FreshV2DevelopmentBenchmarkStrategy.EVIDENCE_GAIN_V1,
        FreshV2DevelopmentBenchmarkStrategy.FARTHEST_GAP_COVERAGE,
        FreshV2DevelopmentBenchmarkStrategy.SEQUENTIAL_GRID,
        FreshV2DevelopmentBenchmarkStrategy.SEALED_HETREN_V1,
    )

    assert len(FROZEN_STRATEGY_ORDER) == 8

    assert len(set(FROZEN_STRATEGY_ORDER)) == 8


def test_strategy_values_match_frozen_contract_names():
    assert tuple(item.value for item in FROZEN_STRATEGY_ORDER) == (
        "V2A_BALANCED_FRONTIER_CLOSURE",
        "V2B_CLOSURE_WITH_COVERAGE_FLOOR",
        "V2C_FAILURE_FRONTIER_STRUCTURAL",
        "MULTI_REGION_V2_1",
        "EVIDENCE_GAIN_V1",
        "FARTHEST_GAP_COVERAGE",
        "SEQUENTIAL_GRID",
        "SEALED_HETREN_V1",
    )


def test_sealed_hetren_v1_binding_is_frozen():
    assert (
        SEALED_HETREN_V1_REFERENCE_STRATEGY
        is FreshBehavioralQualificationStrategy.CURRENT_ADAPTIVE_V1
    )


@pytest.mark.parametrize(
    "strategy",
    (
        FreshV2DevelopmentBenchmarkStrategy.V2A_BALANCED_FRONTIER_CLOSURE,
        FreshV2DevelopmentBenchmarkStrategy.V2B_CLOSURE_WITH_COVERAGE_FLOOR,
        FreshV2DevelopmentBenchmarkStrategy.V2C_FAILURE_FRONTIER_STRUCTURAL,
    ),
)
def test_all_v2_candidates_complete_native_full_grid_without_completion(
    strategy,
):
    problem = _problem()

    bundle = run_fresh_v2_development_benchmark_strategy(
        problem=(problem),
        strategy=(strategy),
    )

    execution = bundle.payload["execution"]

    assert execution["native_evaluation_count"] == problem.candidate_count

    assert execution["neutral_completion_count"] == 0

    assert execution["neutral_completion_indices"] == []

    assert execution["completion_policy"] is None

    assert bundle.trace.terminal_status == "grid_exhausted"

    indices = tuple(
        candidate_index for candidate_index, _verdict in bundle.trace.observations
    )

    assert len(indices) == problem.candidate_count

    assert len(set(indices)) == problem.candidate_count

    assert set(indices) == set(range(problem.candidate_count))

    assert bundle.score.evaluation_count == problem.candidate_count

    assert bundle.score.duplicate_evaluation_count == 0

    assert bundle.score.full_budget_failure_region_recall == 1.0

    assert bundle.score.full_budget_boundary_recall == 1.0


@pytest.mark.parametrize(
    "strategy",
    (
        FreshV2DevelopmentBenchmarkStrategy.MULTI_REGION_V2_1,
        FreshV2DevelopmentBenchmarkStrategy.EVIDENCE_GAIN_V1,
        FreshV2DevelopmentBenchmarkStrategy.FARTHEST_GAP_COVERAGE,
        FreshV2DevelopmentBenchmarkStrategy.SEQUENTIAL_GRID,
        FreshV2DevelopmentBenchmarkStrategy.SEALED_HETREN_V1,
    ),
)
def test_all_reference_strategies_finish_exact_full_grid_with_frozen_completion(
    strategy,
):
    problem = _problem()

    bundle = run_fresh_v2_development_benchmark_strategy(
        problem=(problem),
        strategy=(strategy),
    )

    execution = bundle.payload["execution"]

    assert execution["completion_policy"] == COMPLETION_POLICY

    assert (
        execution["native_evaluation_count"] + execution["neutral_completion_count"]
        == problem.candidate_count
    )

    assert bundle.trace.maximum_evaluations == problem.candidate_count

    assert bundle.trace.terminal_status == "grid_exhausted"

    indices = [
        candidate_index for candidate_index, _verdict in bundle.trace.observations
    ]

    assert len(indices) == problem.candidate_count

    assert len(set(indices)) == problem.candidate_count

    assert set(indices) == set(range(problem.candidate_count))

    assert bundle.score.duplicate_evaluation_count == 0

    assert bundle.score.full_budget_failure_region_recall == 1.0

    assert bundle.score.full_budget_boundary_recall == 1.0


@pytest.mark.parametrize(
    "strategy",
    FROZEN_STRATEGY_ORDER,
)
def test_all_eight_strategies_replay_deterministically(
    strategy,
):
    problem = _problem()

    first = run_fresh_v2_development_benchmark_strategy(
        problem=(problem),
        strategy=(strategy),
    )

    second = run_fresh_v2_development_benchmark_strategy(
        problem=(problem),
        strategy=(strategy),
    )

    assert first == second


@pytest.mark.parametrize(
    "strategy",
    FROZEN_STRATEGY_ORDER,
)
def test_all_eight_strategy_bundles_reverify(
    strategy,
):
    problem = _problem()

    bundle = run_fresh_v2_development_benchmark_strategy(
        problem=(problem),
        strategy=(strategy),
    )

    assert (
        verify_fresh_v2_development_benchmark_execution_bundle(
            bundle=(bundle),
            problem=(problem),
            strategy=(strategy),
        )
        is True
    )


def test_raw_string_strategy_fails_closed():
    with pytest.raises(HveeContractError):
        run_fresh_v2_development_benchmark_strategy(
            problem=(_problem()),
            strategy="V2A_BALANCED_FRONTIER_CLOSURE",
        )


def test_raw_dict_problem_fails_closed():
    with pytest.raises(HveeContractError):
        run_fresh_v2_development_benchmark_strategy(
            problem={
                "candidate_count": 9,
            },
            strategy=(
                FreshV2DevelopmentBenchmarkStrategy.V2A_BALANCED_FRONTIER_CLOSURE
            ),
        )


def test_v2_native_full_grid_guard_rejects_early_terminal():
    problem = _problem()

    observations = (
        (
            0,
            "pass",
        ),
        (
            1,
            "fail",
        ),
    )

    trace = FreshQualificationTrace(
        strategy=(
            FreshV2DevelopmentBenchmarkStrategy.V2A_BALANCED_FRONTIER_CLOSURE.value
        ),
        candidate_count=(problem.candidate_count),
        maximum_evaluations=(problem.candidate_count),
        observations=(observations),
        terminal_status=("budget_exhausted"),
        seed=None,
        sha256=(
            _trace_sha(
                strategy=(
                    FreshV2DevelopmentBenchmarkStrategy.V2A_BALANCED_FRONTIER_CLOSURE.value
                ),
                candidate_count=(problem.candidate_count),
                maximum_evaluations=(problem.candidate_count),
                observations=(observations),
                terminal_status=("budget_exhausted"),
                seed=None,
            )
        ),
    )

    with pytest.raises(HveeContractError):
        _require_full_grid_trace(
            trace=(trace),
            candidate_count=(problem.candidate_count),
        )


def test_verifier_rejects_payload_tamper():
    problem = _problem()

    strategy = FreshV2DevelopmentBenchmarkStrategy.V2A_BALANCED_FRONTIER_CLOSURE

    bundle = run_fresh_v2_development_benchmark_strategy(
        problem=(problem),
        strategy=(strategy),
    )

    payload = deepcopy(bundle.payload)

    payload["execution"]["native_evaluation_count"] = 0

    tampered = replace(
        bundle,
        payload=(payload),
    )

    assert (
        verify_fresh_v2_development_benchmark_execution_bundle(
            bundle=(tampered),
            problem=(problem),
            strategy=(strategy),
        )
        is False
    )


def test_payload_does_not_persist_problem_pattern():
    bundle = run_fresh_v2_development_benchmark_strategy(
        problem=(_problem()),
        strategy=(FreshV2DevelopmentBenchmarkStrategy.V2B_CLOSURE_WITH_COVERAGE_FLOOR),
    )

    problem_payload = bundle.payload["problem"]

    assert "pattern" not in problem_payload

    assert "raw_pattern" not in problem_payload


def test_executor_does_not_import_real_v2_corpus_generator():
    source = inspect.getsource(executor)

    assert "behavioral_v2_fresh_development_corpus" not in source

    assert "build_fresh_v2_development" not in source


def test_executor_contains_no_qualification_open_surface():
    source = inspect.getsource(executor)

    assert "qualification_open_authorized" not in source

    assert "build_fresh_behavioral_qualification_corpus" not in source

    assert "FreshQualificationPartition.QUALIFICATION" not in source


def test_executor_static_imports_exclude_filesystem_network_random_and_model_runtime():
    source = inspect.getsource(executor)

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
        "random",
        "numpy",
        "torch",
        "transformers",
        "faster_whisper",
    }

    assert imported_roots.isdisjoint(forbidden)


def test_executor_has_no_open_or_network_call_surface():
    source = inspect.getsource(executor)

    tree = ast.parse(source)

    called_names = set()

    for node in ast.walk(tree):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        if isinstance(
            node.func,
            ast.Name,
        ):
            called_names.add(node.func.id)

        elif isinstance(
            node.func,
            ast.Attribute,
        ):
            called_names.add(node.func.attr)

    assert "open" not in called_names

    assert "read_text" not in called_names

    assert "read_bytes" not in called_names

    assert "write_text" not in called_names

    assert "write_bytes" not in called_names

    assert "request" not in called_names

    assert "get" not in called_names

    assert "post" not in called_names


def test_executor_is_single_problem_not_batch_corpus_runner():
    parameters = inspect.signature(
        run_fresh_v2_development_benchmark_strategy
    ).parameters

    assert set(parameters) == {
        "problem",
        "strategy",
    }

    assert "problems" not in parameters

    assert "corpus" not in parameters


def test_problem_validation_does_not_read_hidden_verdict_content():
    class GuardedPattern(str):
        def __iter__(self):
            raise AssertionError("validation must not iterate hidden verdict content")

        def __contains__(self, item):
            raise AssertionError(
                "validation must not inspect hidden verdict membership"
            )

        def __getitem__(self, item):
            raise AssertionError("validation must not index hidden verdict content")

    original = _problem()

    guarded = replace(
        original,
        pattern=GuardedPattern(original.pattern),
    )

    assert executor._validate_problem(guarded) is guarded


def test_oracle_reads_only_selected_candidate_after_selection():
    class SelectedReadPattern(str):
        def __new__(cls, value):
            instance = super().__new__(
                cls,
                value,
            )

            instance.read_indices = []

            return instance

        def __getitem__(self, item):
            self.read_indices.append(item)

            return super().__getitem__(item)

    original = _problem()

    pattern = SelectedReadPattern(original.pattern)

    guarded = replace(
        original,
        pattern=pattern,
    )

    executor._validate_problem(guarded)

    assert pattern.read_indices == []

    verdict = executor._oracle_verdict_after_selection(
        problem=guarded,
        selected_candidate_index=2,
    )

    assert verdict.value == "fail"

    assert pattern.read_indices == [2]

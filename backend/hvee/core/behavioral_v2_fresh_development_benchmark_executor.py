from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json

from hvee.core.behavioral_multi_objective_qualification import (
    FreshBehavioralQualificationStrategy,
    FreshQualificationProblem,
    FreshQualificationScore,
    FreshQualificationTrace,
    _trace_sha,
    score_fresh_behavioral_qualification_trace,
)
from hvee.core.behavioral_qualification_budget_completion import (
    COMPLETION_POLICY,
    run_fresh_behavioral_qualification_strategy_with_budget_completion,
)
from hvee.core.behavioral_structural_frontier_closure_planner_v2 import (
    StructuralPlannerVariant,
)
from hvee.core.behavioral_structural_frontier_closure_planner_v2_adapter import (
    build_behavioral_structural_frontier_closure_planner_v2_adapter_bundle,
)
from hvee.core.behavioral_structural_frontier_closure_planner_v2_engine import (
    build_behavioral_structural_frontier_closure_planner_v2_engine_closed_loop_step_bundle,
    build_behavioral_structural_frontier_closure_planner_v2_engine_observation_return_bundle,
    verify_behavioral_structural_frontier_closure_planner_v2_engine_closed_loop_step_bundle,
    verify_behavioral_structural_frontier_closure_planner_v2_engine_observation_return_bundle,
)
from hvee.core.contracts import HveeContractError
from hvee.core.decision import DecisionVerdict


EXECUTOR_KEY = "behavioral_v2_fresh_development_benchmark_executor"
EXECUTOR_VERSION = "1.0.0"

V2_NATIVE_COMPLETION_POLICY = None

SEALED_HETREN_V1_REFERENCE_STRATEGY = (
    FreshBehavioralQualificationStrategy.CURRENT_ADAPTIVE_V1
)


class FreshV2DevelopmentBenchmarkStrategy(str, Enum):
    V2A_BALANCED_FRONTIER_CLOSURE = "V2A_BALANCED_FRONTIER_CLOSURE"
    V2B_CLOSURE_WITH_COVERAGE_FLOOR = "V2B_CLOSURE_WITH_COVERAGE_FLOOR"
    V2C_FAILURE_FRONTIER_STRUCTURAL = "V2C_FAILURE_FRONTIER_STRUCTURAL"
    MULTI_REGION_V2_1 = "MULTI_REGION_V2_1"
    EVIDENCE_GAIN_V1 = "EVIDENCE_GAIN_V1"
    FARTHEST_GAP_COVERAGE = "FARTHEST_GAP_COVERAGE"
    SEQUENTIAL_GRID = "SEQUENTIAL_GRID"
    SEALED_HETREN_V1 = "SEALED_HETREN_V1"


FROZEN_STRATEGY_ORDER = (
    FreshV2DevelopmentBenchmarkStrategy.V2A_BALANCED_FRONTIER_CLOSURE,
    FreshV2DevelopmentBenchmarkStrategy.V2B_CLOSURE_WITH_COVERAGE_FLOOR,
    FreshV2DevelopmentBenchmarkStrategy.V2C_FAILURE_FRONTIER_STRUCTURAL,
    FreshV2DevelopmentBenchmarkStrategy.MULTI_REGION_V2_1,
    FreshV2DevelopmentBenchmarkStrategy.EVIDENCE_GAIN_V1,
    FreshV2DevelopmentBenchmarkStrategy.FARTHEST_GAP_COVERAGE,
    FreshV2DevelopmentBenchmarkStrategy.SEQUENTIAL_GRID,
    FreshV2DevelopmentBenchmarkStrategy.SEALED_HETREN_V1,
)


_V2_VARIANTS = {
    FreshV2DevelopmentBenchmarkStrategy.V2A_BALANCED_FRONTIER_CLOSURE: (
        StructuralPlannerVariant.V2A_BALANCED_FRONTIER_CLOSURE
    ),
    FreshV2DevelopmentBenchmarkStrategy.V2B_CLOSURE_WITH_COVERAGE_FLOOR: (
        StructuralPlannerVariant.V2B_CLOSURE_WITH_COVERAGE_FLOOR
    ),
    FreshV2DevelopmentBenchmarkStrategy.V2C_FAILURE_FRONTIER_STRUCTURAL: (
        StructuralPlannerVariant.V2C_FAILURE_FRONTIER_STRUCTURAL
    ),
}


_REFERENCE_STRATEGIES = {
    FreshV2DevelopmentBenchmarkStrategy.MULTI_REGION_V2_1: (
        FreshBehavioralQualificationStrategy.MULTI_REGION_V2_1
    ),
    FreshV2DevelopmentBenchmarkStrategy.EVIDENCE_GAIN_V1: (
        FreshBehavioralQualificationStrategy.EVIDENCE_GAIN_V1
    ),
    FreshV2DevelopmentBenchmarkStrategy.FARTHEST_GAP_COVERAGE: (
        FreshBehavioralQualificationStrategy.FARTHEST_GAP_COVERAGE
    ),
    FreshV2DevelopmentBenchmarkStrategy.SEQUENTIAL_GRID: (
        FreshBehavioralQualificationStrategy.SEQUENTIAL_GRID
    ),
    FreshV2DevelopmentBenchmarkStrategy.SEALED_HETREN_V1: (
        SEALED_HETREN_V1_REFERENCE_STRATEGY
    ),
}


@dataclass(frozen=True)
class FreshV2DevelopmentBenchmarkExecutionBundle:
    payload: dict[str, object]
    trace: FreshQualificationTrace
    score: FreshQualificationScore
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


def calculate_fresh_v2_development_benchmark_execution_sha256(
    payload: object,
) -> str:
    if not isinstance(
        payload,
        dict,
    ):
        raise HveeContractError(
            "fresh V2 development benchmark execution payload " "must be an object"
        )

    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _evidence_sha(
    *parts: object,
) -> str:
    return hashlib.sha256(_canonical_bytes(list(parts))).hexdigest()


def _validate_problem(
    problem: object,
) -> FreshQualificationProblem:
    if not isinstance(
        problem,
        FreshQualificationProblem,
    ):
        raise HveeContractError(
            "fresh V2 development benchmark executor "
            "requires FreshQualificationProblem"
        )

    if (
        isinstance(
            problem.candidate_count,
            bool,
        )
        or not isinstance(
            problem.candidate_count,
            int,
        )
        or problem.candidate_count < 2
    ):
        raise HveeContractError(
            "fresh V2 development benchmark problem " "candidate_count is invalid"
        )

    if (
        not isinstance(
            problem.pattern,
            str,
        )
        or len(problem.pattern) != problem.candidate_count
    ):
        raise HveeContractError(
            "fresh V2 development benchmark problem " "pattern shape is invalid"
        )

    return problem


def _oracle_verdict_after_selection(
    *,
    problem: FreshQualificationProblem,
    selected_candidate_index: int,
) -> DecisionVerdict:
    if (
        isinstance(
            selected_candidate_index,
            bool,
        )
        or not isinstance(
            selected_candidate_index,
            int,
        )
        or selected_candidate_index < 0
        or selected_candidate_index >= problem.candidate_count
    ):
        raise HveeContractError("selected candidate index is invalid")

    selected_value = problem.pattern[selected_candidate_index]

    if selected_value not in (
        "P",
        "F",
    ):
        raise HveeContractError("selected oracle verdict is outside P/F domain")

    return DecisionVerdict.FAIL if selected_value == "F" else DecisionVerdict.PASS


def _trace_payload(
    trace: FreshQualificationTrace,
) -> dict[str, object]:
    return {
        "strategy": (trace.strategy),
        "candidate_count": (trace.candidate_count),
        "maximum_evaluations": (trace.maximum_evaluations),
        "observations": [
            [
                candidate_index,
                verdict,
            ]
            for candidate_index, verdict in trace.observations
        ],
        "terminal_status": (trace.terminal_status),
        "seed": (trace.seed),
        "sha256": (trace.sha256),
    }


def _score_payload(
    score: FreshQualificationScore,
) -> dict[str, object]:
    return asdict(score)


def _require_full_grid_trace(
    *,
    trace: FreshQualificationTrace,
    candidate_count: int,
) -> None:
    if trace.candidate_count != candidate_count:
        raise HveeContractError("completed benchmark trace candidate count mismatch")

    if trace.maximum_evaluations != candidate_count:
        raise HveeContractError("completed benchmark trace budget is not full grid")

    if trace.terminal_status != "grid_exhausted":
        raise HveeContractError(
            "completed benchmark trace did not terminate " "with grid_exhausted"
        )

    indices = tuple(candidate_index for candidate_index, _verdict in trace.observations)

    if len(indices) != candidate_count:
        raise HveeContractError("completed benchmark trace did not consume full budget")

    if len(set(indices)) != candidate_count:
        raise HveeContractError(
            "completed benchmark trace contains duplicate evaluation"
        )

    if set(indices) != set(range(candidate_count)):
        raise HveeContractError("completed benchmark trace does not cover exact grid")


def _require_full_grid_score(
    *,
    score: FreshQualificationScore,
    candidate_count: int,
) -> None:
    if score.evaluation_count != candidate_count:
        raise HveeContractError("completed benchmark score evaluation count mismatch")

    if score.duplicate_evaluation_count != 0:
        raise HveeContractError(
            "completed benchmark score reports duplicate evaluation"
        )

    if score.full_budget_failure_region_recall != 1.0:
        raise HveeContractError(
            "completed benchmark score does not reach " "full failure-region recall"
        )

    if score.full_budget_boundary_recall != 1.0:
        raise HveeContractError(
            "completed benchmark score does not reach " "full boundary recall"
        )


def _run_v2_native_strategy(
    *,
    problem: FreshQualificationProblem,
    strategy: FreshV2DevelopmentBenchmarkStrategy,
) -> tuple[
    FreshQualificationTrace,
    int,
    int,
    tuple[int, ...],
    str,
    str,
]:
    try:
        variant = _V2_VARIANTS[strategy]

    except KeyError as exc:
        raise HveeContractError("strategy is not a V2 native candidate") from exc

    candidate_values = tuple(
        float(candidate_index) for candidate_index in range(problem.candidate_count)
    )

    candidate_targets = tuple(
        _evidence_sha(
            EXECUTOR_KEY,
            EXECUTOR_VERSION,
            problem.problem_sha256,
            strategy.value,
            "candidate_target",
            candidate_index,
        )
        for candidate_index in range(problem.candidate_count)
    )

    adapter = build_behavioral_structural_frontier_closure_planner_v2_adapter_bundle(
        campaign_key=("hetren.fresh.v2.development.benchmark"),
        campaign_version=(EXECUTOR_VERSION),
        subject_sha256=(problem.problem_sha256),
        axis_key=("synthetic.index"),
        axis_version=("1.0.0"),
        axis_unit=("index"),
        candidate_values=(candidate_values),
        candidate_target_sha256s=(candidate_targets),
        maximum_evaluations=(problem.candidate_count),
        observations=(),
        variant=(variant),
    )

    observations: list[
        tuple[
            int,
            str,
        ]
    ] = []

    observed_indices: set[int] = set()

    while True:
        adapter_status = adapter.payload["adapter"]["status"]

        if adapter_status != "ready":
            break

        if len(observations) >= problem.candidate_count:
            raise HveeContractError("V2 native strategy remained ready after full grid")

        selected_candidate_index = adapter.payload["planner_decision"][
            "selected_candidate_index"
        ]

        if isinstance(
            selected_candidate_index,
            bool,
        ) or not isinstance(
            selected_candidate_index,
            int,
        ):
            raise HveeContractError(
                "V2 planner ready state lacks exact candidate index"
            )

        if selected_candidate_index in observed_indices:
            raise HveeContractError("V2 native strategy proposed duplicate candidate")

        verdict = _oracle_verdict_after_selection(
            problem=(problem),
            selected_candidate_index=(selected_candidate_index),
        )

        sequence = len(observations) + 1

        result_sha = _evidence_sha(
            EXECUTOR_KEY,
            problem.problem_sha256,
            strategy.value,
            "result",
            sequence,
            selected_candidate_index,
            adapter.sha256,
        )

        observation_sha = _evidence_sha(
            EXECUTOR_KEY,
            problem.problem_sha256,
            strategy.value,
            "observation",
            sequence,
            selected_candidate_index,
            adapter.sha256,
        )

        decision_sha = _evidence_sha(
            EXECUTOR_KEY,
            problem.problem_sha256,
            strategy.value,
            "decision",
            sequence,
            selected_candidate_index,
            adapter.sha256,
        )

        counterexample_sha = (
            _evidence_sha(
                EXECUTOR_KEY,
                problem.problem_sha256,
                strategy.value,
                "counterexample",
                sequence,
                selected_candidate_index,
                adapter.sha256,
            )
            if verdict is DecisionVerdict.FAIL
            else None
        )

        returned = build_behavioral_structural_frontier_closure_planner_v2_engine_observation_return_bundle(
            adapter_bundle=(adapter),
            verdict=(verdict),
            result_provenance_sha256=(result_sha),
            observation_evidence_sha256=(observation_sha),
            decision_evidence_sha256=(decision_sha),
            counterexample_evidence_sha256=(counterexample_sha),
            actual_cost_units=1,
        )

        if not (
            verify_behavioral_structural_frontier_closure_planner_v2_engine_observation_return_bundle(
                payload=(returned.payload),
                expected_sha256=(returned.sha256),
                adapter_bundle=(adapter),
            )
        ):
            raise HveeContractError("V2 observation-return verification failed")

        if (
            returned.failure_family_observation.candidate_index
            != selected_candidate_index
        ):
            raise HveeContractError("V2 observation return changed selected candidate")

        step = build_behavioral_structural_frontier_closure_planner_v2_engine_closed_loop_step_bundle(
            adapter_bundle=(adapter),
            observation_return_bundle=(returned),
        )

        if not (
            verify_behavioral_structural_frontier_closure_planner_v2_engine_closed_loop_step_bundle(
                payload=(step.payload),
                expected_sha256=(step.sha256),
                adapter_bundle=(adapter),
                observation_return_bundle=(returned),
                advanced_adapter_bundle=(step.advanced_adapter_bundle),
                next_experiment_protocol=(step.next_experiment_protocol),
            )
        ):
            raise HveeContractError("V2 closed-loop step verification failed")

        observations.append(
            (
                selected_candidate_index,
                verdict.value,
            )
        )

        observed_indices.add(selected_candidate_index)

        adapter = step.advanced_adapter_bundle

    native_terminal_status = adapter.payload["adapter"]["status"]

    if native_terminal_status != "grid_exhausted":
        raise HveeContractError(
            "V2 candidate terminated before native full-grid completion"
        )

    if len(observations) != problem.candidate_count:
        raise HveeContractError("V2 native candidate did not evaluate full grid")

    if observed_indices != set(range(problem.candidate_count)):
        raise HveeContractError("V2 native candidate did not cover exact full grid")

    trace_observations = tuple(observations)

    trace_sha = _trace_sha(
        strategy=(strategy.value),
        candidate_count=(problem.candidate_count),
        maximum_evaluations=(problem.candidate_count),
        observations=(trace_observations),
        terminal_status=(native_terminal_status),
        seed=None,
    )

    trace = FreshQualificationTrace(
        strategy=(strategy.value),
        candidate_count=(problem.candidate_count),
        maximum_evaluations=(problem.candidate_count),
        observations=(trace_observations),
        terminal_status=(native_terminal_status),
        seed=None,
        sha256=(trace_sha),
    )

    return (
        trace,
        len(observations),
        0,
        (),
        native_terminal_status,
        trace.sha256,
    )


def _run_reference_strategy(
    *,
    problem: FreshQualificationProblem,
    strategy: FreshV2DevelopmentBenchmarkStrategy,
) -> tuple[
    FreshQualificationTrace,
    int,
    int,
    tuple[int, ...],
    str,
    str,
]:
    try:
        frozen_strategy = _REFERENCE_STRATEGIES[strategy]

    except KeyError as exc:
        raise HveeContractError("strategy is not a frozen reference strategy") from exc

    envelope = run_fresh_behavioral_qualification_strategy_with_budget_completion(
        problem=(problem),
        strategy=(frozen_strategy),
        maximum_evaluations=(problem.candidate_count),
        seed=None,
    )

    trace = envelope.completed_trace

    return (
        trace,
        envelope.native_evaluation_count,
        envelope.neutral_completion_count,
        tuple(envelope.neutral_completion_indices),
        envelope.native_terminal_status,
        envelope.native_trace.sha256,
    )


def run_fresh_v2_development_benchmark_strategy(
    *,
    problem: FreshQualificationProblem,
    strategy: FreshV2DevelopmentBenchmarkStrategy,
) -> FreshV2DevelopmentBenchmarkExecutionBundle:
    normalized_problem = _validate_problem(problem)

    if not isinstance(
        strategy,
        FreshV2DevelopmentBenchmarkStrategy,
    ):
        raise HveeContractError(
            "fresh V2 development benchmark strategy " "must use strict enum"
        )

    if strategy in _V2_VARIANTS:
        (
            trace,
            native_evaluation_count,
            neutral_completion_count,
            neutral_completion_indices,
            native_terminal_status,
            native_trace_sha256,
        ) = _run_v2_native_strategy(
            problem=(normalized_problem),
            strategy=(strategy),
        )

        completion_policy = V2_NATIVE_COMPLETION_POLICY

        reference_strategy = None

    elif strategy in _REFERENCE_STRATEGIES:
        (
            trace,
            native_evaluation_count,
            neutral_completion_count,
            neutral_completion_indices,
            native_terminal_status,
            native_trace_sha256,
        ) = _run_reference_strategy(
            problem=(normalized_problem),
            strategy=(strategy),
        )

        completion_policy = COMPLETION_POLICY

        reference_strategy = _REFERENCE_STRATEGIES[strategy].value

    else:
        raise HveeContractError("unsupported fresh V2 development benchmark strategy")

    _require_full_grid_trace(
        trace=(trace),
        candidate_count=(normalized_problem.candidate_count),
    )

    score = score_fresh_behavioral_qualification_trace(
        problem=(normalized_problem),
        trace=(trace),
    )

    _require_full_grid_score(
        score=(score),
        candidate_count=(normalized_problem.candidate_count),
    )

    if (
        native_evaluation_count + neutral_completion_count
        != normalized_problem.candidate_count
    ):
        raise HveeContractError("native plus completion evaluation accounting mismatch")

    if strategy in _V2_VARIANTS:
        if neutral_completion_count != 0:
            raise HveeContractError(
                "V2 native strategy used prohibited neutral completion"
            )

        if neutral_completion_indices:
            raise HveeContractError(
                "V2 native strategy emitted prohibited completion indices"
            )

    payload: dict[
        str,
        object,
    ] = {
        "schema_version": 1,
        "type": ("fresh_v2_development_benchmark_execution"),
        "executor": {
            "key": (EXECUTOR_KEY),
            "version": (EXECUTOR_VERSION),
        },
        "strategy": {
            "benchmark_strategy": (strategy.value),
            "v2_variant": (
                _V2_VARIANTS[strategy].value if strategy in _V2_VARIANTS else None
            ),
            "reference_strategy": (reference_strategy),
            "sealed_hetren_v1_reference_strategy": (
                SEALED_HETREN_V1_REFERENCE_STRATEGY.value
            ),
        },
        "problem": {
            "problem_key": (normalized_problem.problem_key),
            "problem_sha256": (normalized_problem.problem_sha256),
            "partition": (normalized_problem.partition),
            "namespace": (normalized_problem.namespace),
            "candidate_count": (normalized_problem.candidate_count),
            "topology_stratum": (normalized_problem.topology_stratum),
        },
        "execution": {
            "maximum_evaluations": (normalized_problem.candidate_count),
            "native_evaluation_count": (native_evaluation_count),
            "neutral_completion_count": (neutral_completion_count),
            "neutral_completion_indices": list(neutral_completion_indices),
            "completion_policy": (completion_policy),
            "native_terminal_status": (native_terminal_status),
            "native_trace_sha256": (native_trace_sha256),
            "completed_trace_sha256": (trace.sha256),
        },
        "trace": (_trace_payload(trace)),
        "score": (_score_payload(score)),
        "evidence_boundary": {
            "single_problem_execution_only": True,
            "equal_full_budget_enforced": True,
            "duplicate_evaluation_forbidden": True,
            "truth_read_only_after_candidate_selection": True,
            "v2_native_completion_required": True,
            "v2_neutral_completion_forbidden": True,
            "reference_neutral_completion_policy_frozen": True,
            "real_development_corpus_loaded_by_executor": False,
            "qualification_generator_used": False,
            "qualification_opened": False,
            "behavioral_performance_qualified": False,
            "production_qualified": False,
            "model_inference_performed": False,
            "asr_execution_performed": False,
        },
    }

    payload = deepcopy(payload)

    execution_sha256 = calculate_fresh_v2_development_benchmark_execution_sha256(
        payload
    )

    return FreshV2DevelopmentBenchmarkExecutionBundle(
        payload=(payload),
        trace=(trace),
        score=(score),
        sha256=(execution_sha256),
    )


def verify_fresh_v2_development_benchmark_execution_bundle(
    *,
    bundle: object,
    problem: object,
    strategy: object,
) -> bool:
    try:
        if not isinstance(
            bundle,
            FreshV2DevelopmentBenchmarkExecutionBundle,
        ):
            return False

        if not isinstance(
            problem,
            FreshQualificationProblem,
        ):
            return False

        if not isinstance(
            strategy,
            FreshV2DevelopmentBenchmarkStrategy,
        ):
            return False

        if (
            calculate_fresh_v2_development_benchmark_execution_sha256(bundle.payload)
            != bundle.sha256
        ):
            return False

        rebuilt = run_fresh_v2_development_benchmark_strategy(
            problem=(problem),
            strategy=(strategy),
        )

        if rebuilt.payload != bundle.payload:
            return False

        if rebuilt.trace != bundle.trace:
            return False

        if rebuilt.score != bundle.score:
            return False

        if rebuilt.sha256 != bundle.sha256:
            return False

        return True

    except (
        HveeContractError,
        KeyError,
        TypeError,
        ValueError,
    ):
        return False

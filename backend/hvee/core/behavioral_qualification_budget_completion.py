from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from hvee.core.behavioral_multi_objective_qualification import (
    FreshBehavioralQualificationStrategy,
    FreshQualificationProblem,
    FreshQualificationTrace,
    _make_trace,
    _trace_sha,
    run_fresh_behavioral_qualification_strategy,
)
from hvee.core.contracts import HveeContractError
from hvee.core.decision import DecisionVerdict


COMPLETION_POLICY = "NEUTRAL_LOWEST_UNOBSERVED_BUDGET_COMPLETION_V1"


@dataclass(frozen=True)
class FreshQualificationBudgetCompletionEnvelope:
    strategy: str
    completion_policy: str
    native_trace: FreshQualificationTrace
    completed_trace: FreshQualificationTrace
    native_trace_sha256: str
    completed_trace_sha256: str
    native_terminal_status: str
    native_evaluation_count: int
    neutral_completion_indices: tuple[int, ...]
    neutral_completion_count: int
    maximum_evaluations: int
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
        raise HveeContractError(
            "budget completion value is not canonically JSON serializable"
        ) from exc


def _sha256(
    value: object,
) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def select_neutral_lowest_unobserved_completion_indices(
    *,
    candidate_count: int,
    observed_indices: tuple[int, ...],
    maximum_evaluations: int,
) -> tuple[int, ...]:
    if (
        isinstance(
            candidate_count,
            bool,
        )
        or not isinstance(
            candidate_count,
            int,
        )
        or candidate_count < 1
    ):
        raise HveeContractError(
            "budget completion candidate_count must be a positive integer"
        )

    if (
        isinstance(
            maximum_evaluations,
            bool,
        )
        or not isinstance(
            maximum_evaluations,
            int,
        )
        or maximum_evaluations < 1
        or maximum_evaluations > candidate_count
    ):
        raise HveeContractError(
            "budget completion maximum_evaluations must lie within the grid"
        )

    if not isinstance(
        observed_indices,
        tuple,
    ):
        raise HveeContractError("budget completion observed_indices must be a tuple")

    seen: set[int] = set()

    for candidate_index in observed_indices:
        if (
            isinstance(
                candidate_index,
                bool,
            )
            or not isinstance(
                candidate_index,
                int,
            )
            or candidate_index < 0
            or candidate_index >= candidate_count
            or candidate_index in seen
        ):
            raise HveeContractError(
                "budget completion observed_indices contain invalid or duplicate candidate"
            )

        seen.add(candidate_index)

    if len(seen) > maximum_evaluations:
        raise HveeContractError(
            "native trace already exceeds requested qualification budget"
        )

    needed = maximum_evaluations - len(seen)

    if needed == 0:
        return ()

    selected = []

    for candidate_index in range(candidate_count):
        if candidate_index in seen:
            continue

        selected.append(candidate_index)

        if len(selected) == needed:
            break

    if len(selected) != needed:
        raise HveeContractError(
            "unable to satisfy qualification budget without duplicate evaluation"
        )

    return tuple(selected)


def _validate_native_trace(
    *,
    problem: FreshQualificationProblem,
    native_trace: FreshQualificationTrace,
) -> FreshBehavioralQualificationStrategy:
    if not isinstance(
        problem,
        FreshQualificationProblem,
    ):
        raise HveeContractError("budget completion requires FreshQualificationProblem")

    if not isinstance(
        native_trace,
        FreshQualificationTrace,
    ):
        raise HveeContractError("budget completion requires FreshQualificationTrace")

    if native_trace.candidate_count != problem.candidate_count:
        raise HveeContractError(
            "native trace candidate_count does not match qualification problem"
        )

    expected_trace_sha = _trace_sha(
        strategy=(native_trace.strategy),
        candidate_count=(native_trace.candidate_count),
        maximum_evaluations=(native_trace.maximum_evaluations),
        observations=(native_trace.observations),
        terminal_status=(native_trace.terminal_status),
        seed=(native_trace.seed),
    )

    if native_trace.sha256 != expected_trace_sha:
        raise HveeContractError("native trace identity mismatch")

    try:
        strategy = FreshBehavioralQualificationStrategy(native_trace.strategy)

    except ValueError as exc:
        raise HveeContractError(
            "native trace strategy is not part of the frozen qualification program"
        ) from exc

    seen: set[int] = set()

    for candidate_index, verdict_value in native_trace.observations:
        if (
            isinstance(
                candidate_index,
                bool,
            )
            or not isinstance(
                candidate_index,
                int,
            )
            or candidate_index < 0
            or candidate_index >= problem.candidate_count
            or candidate_index in seen
        ):
            raise HveeContractError(
                "native trace contains invalid or duplicate candidate"
            )

        seen.add(candidate_index)

        try:
            verdict = DecisionVerdict(verdict_value)

        except ValueError as exc:
            raise HveeContractError("native trace contains invalid verdict") from exc

        expected_verdict = (
            DecisionVerdict.FAIL
            if problem.pattern[candidate_index] == "F"
            else DecisionVerdict.PASS
        )

        if verdict is not expected_verdict:
            raise HveeContractError(
                "native trace verdict disagrees with qualification problem"
            )

    return strategy


def complete_fresh_behavioral_qualification_trace_budget(
    *,
    problem: FreshQualificationProblem,
    native_trace: FreshQualificationTrace,
) -> FreshQualificationBudgetCompletionEnvelope:
    strategy = _validate_native_trace(
        problem=problem,
        native_trace=native_trace,
    )

    maximum_evaluations = native_trace.maximum_evaluations

    native_indices = tuple(
        candidate_index for candidate_index, _verdict in native_trace.observations
    )

    completion_indices = select_neutral_lowest_unobserved_completion_indices(
        candidate_count=(problem.candidate_count),
        observed_indices=(native_indices),
        maximum_evaluations=(maximum_evaluations),
    )

    completed_observations = [
        (
            candidate_index,
            DecisionVerdict(verdict_value),
        )
        for candidate_index, verdict_value in native_trace.observations
    ]

    for candidate_index in completion_indices:
        verdict = (
            DecisionVerdict.FAIL
            if problem.pattern[candidate_index] == "F"
            else DecisionVerdict.PASS
        )

        completed_observations.append(
            (
                candidate_index,
                verdict,
            )
        )

    if len(completed_observations) != maximum_evaluations:
        raise HveeContractError(
            "qualification budget completion did not reach exact requested budget"
        )

    completed_terminal_status = (
        "grid_exhausted"
        if maximum_evaluations == problem.candidate_count
        else "budget_exhausted"
    )

    completed_trace = _make_trace(
        strategy=(strategy),
        candidate_count=(problem.candidate_count),
        maximum_evaluations=(maximum_evaluations),
        observations=(completed_observations),
        terminal_status=(completed_terminal_status),
        seed=(native_trace.seed),
    )

    envelope_payload = {
        "strategy": (strategy.value),
        "completion_policy": (COMPLETION_POLICY),
        "native_trace_sha256": (native_trace.sha256),
        "completed_trace_sha256": (completed_trace.sha256),
        "native_terminal_status": (native_trace.terminal_status),
        "native_evaluation_count": (native_trace.evaluation_count),
        "neutral_completion_indices": list(completion_indices),
        "neutral_completion_count": len(completion_indices),
        "maximum_evaluations": (maximum_evaluations),
    }

    envelope_sha = _sha256(envelope_payload)

    return FreshQualificationBudgetCompletionEnvelope(
        strategy=(strategy.value),
        completion_policy=(COMPLETION_POLICY),
        native_trace=(native_trace),
        completed_trace=(completed_trace),
        native_trace_sha256=(native_trace.sha256),
        completed_trace_sha256=(completed_trace.sha256),
        native_terminal_status=(native_trace.terminal_status),
        native_evaluation_count=(native_trace.evaluation_count),
        neutral_completion_indices=(completion_indices),
        neutral_completion_count=(len(completion_indices)),
        maximum_evaluations=(maximum_evaluations),
        sha256=(envelope_sha),
    )


def run_fresh_behavioral_qualification_strategy_with_budget_completion(
    *,
    problem: FreshQualificationProblem,
    strategy: FreshBehavioralQualificationStrategy,
    maximum_evaluations: int | None = None,
    seed: int | None = None,
) -> FreshQualificationBudgetCompletionEnvelope:
    if not isinstance(
        strategy,
        FreshBehavioralQualificationStrategy,
    ):
        raise HveeContractError(
            "budget-completed qualification strategy must use strict enum"
        )

    native_trace = run_fresh_behavioral_qualification_strategy(
        problem=(problem),
        strategy=(strategy),
        maximum_evaluations=(maximum_evaluations),
        seed=(seed),
    )

    return complete_fresh_behavioral_qualification_trace_budget(
        problem=(problem),
        native_trace=(native_trace),
    )


__all__ = [
    "COMPLETION_POLICY",
    "FreshQualificationBudgetCompletionEnvelope",
    "complete_fresh_behavioral_qualification_trace_budget",
    "run_fresh_behavioral_qualification_strategy_with_budget_completion",
    "select_neutral_lowest_unobserved_completion_indices",
]

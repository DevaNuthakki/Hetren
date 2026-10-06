"""Deterministic executable tool-agent fixture for diagnosis integration.

This module is a controlled research fixture, not a production agent runner.
Two latent fault modes intentionally produce the same visible baseline failure.
A real deterministic intervention is then executed and converted into the
existing diagnosis Observation contract.

The fixture demonstrates integration between executable behavior and Hetren's
diagnostic planner. It does not establish external-system causal validity,
generalize to arbitrary agents, authorize repairs, or perform deployment.
"""

from dataclasses import dataclass
from enum import StrEnum

from packages.core.hetren_diagnosis.contracts import (
    AgentTrace,
    ContractError,
    DiagnosisProblem,
    DiagnosisStatus,
    EventKind,
    Experiment,
    Hypothesis,
    InterventionKind,
    Observation,
    PlannerDecision,
    TraceEvent,
    Verdict,
    canonical_sha256,
)
from packages.core.hetren_diagnosis.lifecycle import (
    replay_observations,
    select_next_decision,
)


_OPERANDS = (7, 5)
_EXPECTED_OUTPUT = 12


class FaultMode(StrEnum):
    TOOL_SELECTION = "tool_selection"
    PARAMETER_TRANSFORMATION = "parameter_transformation"


@dataclass(frozen=True)
class ToolAgentRun:
    """Observable result of one deterministic fixture execution."""

    run_id: str
    selected_tool: str
    arguments: tuple[int, int]
    output: int
    expected_output: int
    trace: AgentTrace

    @property
    def passed(self) -> bool:
        return self.output == self.expected_output

    @property
    def execution_evidence_sha256(self) -> str:
        """Fingerprint observable execution evidence without latent labels."""
        return canonical_sha256(
            {
                "run_id": self.run_id,
                "selected_tool": self.selected_tool,
                "arguments": self.arguments,
                "output": self.output,
                "expected_output": self.expected_output,
                "trace_sha256": self.trace.trace_sha256,
            }
        )


@dataclass(frozen=True)
class DiagnosticExperimentResult:
    agent_run: ToolAgentRun
    observation: Observation


@dataclass(frozen=True)
class DiagnosisDemoResult:
    baseline_run: ToolAgentRun
    problem: DiagnosisProblem
    initial_decision: PlannerDecision
    experiment_result: DiagnosticExperimentResult
    final_decision: PlannerDecision
    posterior: tuple[tuple[str, float], ...]

    @property
    def diagnosed_hypothesis_key(self) -> str | None:
        if (
            self.final_decision.status
            is not DiagnosisStatus.DIAGNOSED
        ):
            return None

        surviving = tuple(
            key
            for key, probability in self.posterior
            if probability > 1e-12
        )

        if len(surviving) != 1:
            return None

        return surviving[0]


def _require_fault_mode(
    fault_mode: FaultMode,
) -> None:
    if not isinstance(fault_mode, FaultMode):
        raise ContractError(
            "fault_mode must be a FaultMode"
        )


def _require_run_id(run_id: str) -> None:
    if (
        not isinstance(run_id, str)
        or not run_id.strip()
    ):
        raise ContractError(
            "run_id must be non-empty text"
        )


def _invoke_tool(
    tool_name: str,
    arguments: tuple[int, int],
) -> int:
    left, right = arguments

    if tool_name == "add":
        return left + right

    if tool_name == "subtract":
        return left - right

    raise ContractError(
        f"unknown deterministic tool: {tool_name}"
    )


def _baseline_action(
    fault_mode: FaultMode,
) -> tuple[str, tuple[int, int]]:
    if fault_mode is FaultMode.TOOL_SELECTION:
        return "subtract", _OPERANDS

    if (
        fault_mode
        is FaultMode.PARAMETER_TRANSFORMATION
    ):
        return "add", (
            _OPERANDS[0],
            -_OPERANDS[1],
        )

    raise ContractError(
        f"unsupported fault mode: {fault_mode}"
    )


def _apply_intervention(
    *,
    tool_name: str,
    arguments: tuple[int, int],
    intervention: InterventionKind | None,
) -> tuple[str, tuple[int, int]]:
    if intervention is None:
        return tool_name, arguments

    if not isinstance(
        intervention,
        InterventionKind,
    ):
        raise ContractError(
            "intervention must be an "
            "InterventionKind or None"
        )

    if intervention is InterventionKind.REPLAY:
        return tool_name, arguments

    if intervention is InterventionKind.REPLACE_TOOL:
        return "add", arguments

    if (
        intervention
        is InterventionKind.OVERRIDE_PARAMETER
    ):
        return tool_name, _OPERANDS

    raise ContractError(
        "deterministic fixture does not support "
        f"{intervention.value}"
    )


def _build_trace(
    *,
    run_id: str,
    tool_name: str,
    arguments: tuple[int, int],
    output: int,
) -> AgentTrace:
    request = {
        "operation": "compute_sum",
        "operands": _OPERANDS,
    }

    selected = {
        "tool": tool_name,
    }

    call = {
        "tool": tool_name,
        "arguments": arguments,
    }

    result = {
        "result": output,
    }

    final = {
        "answer": output,
    }

    state_0 = {
        "phase": "start",
    }

    state_1 = {
        "phase": "selected",
        "tool": tool_name,
    }

    state_2 = {
        "phase": "called",
        "tool": tool_name,
        "arguments": arguments,
    }

    state_3 = {
        "phase": "result",
        "result": output,
    }

    state_4 = {
        "phase": "complete",
        "result": output,
    }

    events = (
        TraceEvent(
            sequence=0,
            kind=EventKind.DECISION,
            component="agent",
            operation="select_tool",
            input_sha256=canonical_sha256(request),
            output_sha256=canonical_sha256(selected),
            state_before_sha256=canonical_sha256(
                state_0
            ),
            state_after_sha256=canonical_sha256(
                state_1
            ),
        ),
        TraceEvent(
            sequence=1,
            kind=EventKind.TOOL_CALL,
            component=tool_name,
            operation="invoke",
            input_sha256=canonical_sha256(call),
            output_sha256=canonical_sha256(result),
            state_before_sha256=canonical_sha256(
                state_1
            ),
            state_after_sha256=canonical_sha256(
                state_2
            ),
        ),
        TraceEvent(
            sequence=2,
            kind=EventKind.TOOL_RESULT,
            component=tool_name,
            operation="return",
            input_sha256=canonical_sha256(call),
            output_sha256=canonical_sha256(result),
            state_before_sha256=canonical_sha256(
                state_2
            ),
            state_after_sha256=canonical_sha256(
                state_3
            ),
        ),
        TraceEvent(
            sequence=3,
            kind=EventKind.TERMINATION,
            component="agent",
            operation="complete",
            input_sha256=canonical_sha256(result),
            output_sha256=canonical_sha256(final),
            state_before_sha256=canonical_sha256(
                state_3
            ),
            state_after_sha256=canonical_sha256(
                state_4
            ),
        ),
    )

    return AgentTrace(
        run_id=run_id,
        events=events,
    )


def run_tool_agent(
    fault_mode: FaultMode,
    *,
    run_id: str,
    intervention: InterventionKind | None = None,
) -> ToolAgentRun:
    """Execute the deterministic faulty agent under an optional intervention."""
    _require_fault_mode(fault_mode)
    _require_run_id(run_id)

    tool_name, arguments = _baseline_action(
        fault_mode
    )

    tool_name, arguments = _apply_intervention(
        tool_name=tool_name,
        arguments=arguments,
        intervention=intervention,
    )

    output = _invoke_tool(
        tool_name,
        arguments,
    )

    trace = _build_trace(
        run_id=run_id,
        tool_name=tool_name,
        arguments=arguments,
        output=output,
    )

    return ToolAgentRun(
        run_id=run_id,
        selected_tool=tool_name,
        arguments=arguments,
        output=output,
        expected_output=_EXPECTED_OUTPUT,
        trace=trace,
    )


def build_diagnosis_problem(
    trace: AgentTrace,
) -> DiagnosisProblem:
    """Bind a real baseline trace to the frozen two-hypothesis fixture."""
    if not isinstance(trace, AgentTrace):
        raise ContractError(
            "trace must be an AgentTrace"
        )

    hypotheses = (
        Hypothesis(
            key="parameter_transformation_fault",
            description=(
                "the correct tool is selected but "
                "an argument is transformed incorrectly"
            ),
            prior_probability=0.5,
        ),
        Hypothesis(
            key="tool_selection_fault",
            description=(
                "the agent selects the wrong arithmetic tool"
            ),
            prior_probability=0.5,
        ),
    )

    experiments = (
        Experiment(
            key="e1-replace-tool",
            intervention_kind=(
                InterventionKind.REPLACE_TOOL
            ),
            intervention_target="tool-dispatch",
            cost_units=1,
            predicted_verdicts=(
                (
                    "parameter_transformation_fault",
                    Verdict.FAIL,
                ),
                (
                    "tool_selection_fault",
                    Verdict.PASS,
                ),
            ),
        ),
        Experiment(
            key="e2-override-parameter",
            intervention_kind=(
                InterventionKind.OVERRIDE_PARAMETER
            ),
            intervention_target=(
                "argument-transformation"
            ),
            cost_units=1,
            predicted_verdicts=(
                (
                    "parameter_transformation_fault",
                    Verdict.PASS,
                ),
                (
                    "tool_selection_fault",
                    Verdict.FAIL,
                ),
            ),
        ),
    )

    return DiagnosisProblem(
        trace=trace,
        hypotheses=hypotheses,
        experiments=experiments,
        budget_units=2,
    )


def execute_selected_experiment(
    *,
    problem: DiagnosisProblem,
    decision: PlannerDecision,
    fault_mode: FaultMode,
    sequence: int = 0,
) -> DiagnosticExperimentResult:
    """Actually execute the planner-selected intervention.

    The observation verdict is computed from the execution output. It is not
    copied from Experiment.predicted_verdicts.
    """
    if not isinstance(
        problem,
        DiagnosisProblem,
    ):
        raise ContractError(
            "problem must be a DiagnosisProblem"
        )

    if not isinstance(
        decision,
        PlannerDecision,
    ):
        raise ContractError(
            "decision must be a PlannerDecision"
        )

    _require_fault_mode(fault_mode)

    if (
        decision.problem_sha256
        != problem.problem_sha256
    ):
        raise ContractError(
            "planner decision does not bind "
            "the supplied diagnosis problem"
        )

    if (
        decision.status
        is not DiagnosisStatus.ACTIVE
        or decision.experiment_key is None
    ):
        raise ContractError(
            "diagnostic execution requires "
            "an ACTIVE planner decision"
        )

    experiment = next(
        (
            item
            for item in problem.experiments
            if item.key
            == decision.experiment_key
        ),
        None,
    )

    if experiment is None:
        raise ContractError(
            "planner selected an unknown experiment"
        )

    diagnostic_run = run_tool_agent(
        fault_mode,
        run_id=(
            f"{problem.trace.run_id}:diagnostic:"
            f"{sequence}:{experiment.key}"
        ),
        intervention=experiment.intervention_kind,
    )

    verdict = (
        Verdict.PASS
        if diagnostic_run.passed
        else Verdict.FAIL
    )

    counterexample_sha256 = None

    if verdict is Verdict.FAIL:
        counterexample_sha256 = canonical_sha256(
            {
                "expected_output": (
                    diagnostic_run.expected_output
                ),
                "actual_output": (
                    diagnostic_run.output
                ),
            }
        )

    observation = Observation(
        sequence=sequence,
        experiment_key=experiment.key,
        experiment_sha256=(
            experiment.experiment_sha256
        ),
        verdict=verdict,
        actual_cost_units=experiment.cost_units,
        evidence_sha256=(
            diagnostic_run.execution_evidence_sha256
        ),
        counterexample_sha256=(
            counterexample_sha256
        ),
    )

    return DiagnosticExperimentResult(
        agent_run=diagnostic_run,
        observation=observation,
    )


def run_diagnosis_demo(
    fault_mode: FaultMode,
    *,
    run_id: str,
) -> DiagnosisDemoResult:
    """Execute one complete deterministic diagnosis demonstration."""
    baseline = run_tool_agent(
        fault_mode,
        run_id=run_id,
    )

    if baseline.passed:
        raise ContractError(
            "diagnosis demo requires a failing baseline"
        )

    problem = build_diagnosis_problem(
        baseline.trace
    )

    initial_decision = select_next_decision(
        problem
    )

    experiment_result = (
        execute_selected_experiment(
            problem=problem,
            decision=initial_decision,
            fault_mode=fault_mode,
            sequence=0,
        )
    )

    observations = (
        experiment_result.observation,
    )

    final_decision = select_next_decision(
        problem,
        observations,
    )

    posterior = replay_observations(
        problem,
        observations,
    )

    return DiagnosisDemoResult(
        baseline_run=baseline,
        problem=problem,
        initial_decision=initial_decision,
        experiment_result=experiment_result,
        final_decision=final_decision,
        posterior=tuple(
            sorted(posterior.items())
        ),
    )


__all__ = [
    "DiagnosisDemoResult",
    "DiagnosticExperimentResult",
    "FaultMode",
    "ToolAgentRun",
    "build_diagnosis_problem",
    "execute_selected_experiment",
    "run_diagnosis_demo",
    "run_tool_agent",
]

"""Deterministic behavioral-engine fixtures used by the portfolio slice."""

from .deterministic_tool_agent import (
    DiagnosisDemoResult,
    DiagnosticExperimentResult,
    FaultMode,
    ToolAgentRun,
    build_diagnosis_problem,
    execute_selected_experiment,
    run_diagnosis_demo,
    run_tool_agent,
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


from .deterministic_repair import (
    RepairEvaluationDemoResult,
    build_candidate_snapshot,
    build_repair_goal,
    build_repair_proposal,
    evaluate_candidate_run,
    execute_repair_candidate,
    run_repair_evaluation_demo,
    select_candidate_repair,
)

__all__ += [
    "RepairEvaluationDemoResult",
    "build_candidate_snapshot",
    "build_repair_goal",
    "build_repair_proposal",
    "evaluate_candidate_run",
    "execute_repair_candidate",
    "run_repair_evaluation_demo",
    "select_candidate_repair",
]

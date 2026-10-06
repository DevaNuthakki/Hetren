"""Diagnosis integration for the deterministic incident-triage environment.

This module reuses Hetren's existing diagnosis contracts, belief replay, and
planner. The controlled environment receives latent fixture truth only so an
experiment can actually execute; the planner and posterior consume observable
experiment results rather than the hidden label.
"""

from dataclasses import dataclass

from environments.agent.incident_triage import (
    IncidentFaultMode,
    IncidentTriageRun,
    expected_incident_ids,
    run_incident_triage,
)
from packages.core.hetren_diagnosis.contracts import (
    AgentTrace,
    ContractError,
    DiagnosisProblem,
    DiagnosisStatus,
    Experiment,
    Hypothesis,
    InterventionKind,
    Observation,
    PlannerDecision,
    Verdict,
    canonical_sha256,
)
from packages.core.hetren_diagnosis.lifecycle import (
    replay_observations,
    select_next_decision,
)


_EXPECTED_SERVICE = "payments"


@dataclass(frozen=True)
class IncidentDiagnosticExperimentResult:
    """Executed diagnostic experiment and its observable result."""

    agent_run: IncidentTriageRun
    observation: Observation


@dataclass(frozen=True)
class IncidentDiagnosisResult:
    """One complete diagnosis run over the incident-triage environment."""

    baseline_run: IncidentTriageRun
    problem: DiagnosisProblem
    initial_decision: PlannerDecision
    experiment_result: IncidentDiagnosticExperimentResult
    final_decision: PlannerDecision
    posterior: tuple[tuple[str, float], ...]

    @property
    def diagnosed_hypothesis_key(
        self,
    ) -> str | None:
        if (
            self.final_decision.status
            is not DiagnosisStatus.DIAGNOSED
        ):
            return None

        surviving = tuple(
            key
            for key, probability
            in self.posterior
            if probability > 1e-12
        )

        if len(surviving) != 1:
            return None

        return surviving[0]


def build_diagnosis_problem(
    trace: AgentTrace,
) -> DiagnosisProblem:
    """Bind a real failing workflow trace to two causal hypotheses."""
    if not isinstance(trace, AgentTrace):
        raise ContractError(
            "trace must be an AgentTrace"
        )

    hypotheses = (
        Hypothesis(
            key="filter_tool_selection_fault",
            description=(
                "the workflow selects a strict "
                "severity filter instead of the "
                "required inclusive filter"
            ),
            prior_probability=0.5,
        ),
        Hypothesis(
            key="threshold_transformation_fault",
            description=(
                "the inclusive severity filter is "
                "selected but the minimum severity "
                "parameter is transformed incorrectly"
            ),
            prior_probability=0.5,
        ),
    )

    experiments = (
        Experiment(
            key="e1-replace-filter-tool",
            intervention_kind=(
                InterventionKind.REPLACE_TOOL
            ),
            intervention_target=(
                "severity-filter-selection"
            ),
            cost_units=1,
            predicted_verdicts=(
                (
                    "filter_tool_selection_fault",
                    Verdict.PASS,
                ),
                (
                    "threshold_transformation_fault",
                    Verdict.FAIL,
                ),
            ),
        ),
        Experiment(
            key="e2-override-threshold",
            intervention_kind=(
                InterventionKind.OVERRIDE_PARAMETER
            ),
            intervention_target=(
                "severity-threshold-transformation"
            ),
            cost_units=1,
            predicted_verdicts=(
                (
                    "filter_tool_selection_fault",
                    Verdict.FAIL,
                ),
                (
                    "threshold_transformation_fault",
                    Verdict.PASS,
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
    fault_mode: IncidentFaultMode,
    sequence: int = 0,
) -> IncidentDiagnosticExperimentResult:
    """Actually execute the planner-selected incident-triage intervention."""
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

    if not isinstance(
        fault_mode,
        IncidentFaultMode,
    ):
        raise ContractError(
            "fault_mode must be an IncidentFaultMode"
        )

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

    diagnostic_run = run_incident_triage(
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
        expected_ids = expected_incident_ids()

        counterexample_sha256 = canonical_sha256(
            {
                "expected_report": {
                    "service": _EXPECTED_SERVICE,
                    "incident_ids": expected_ids,
                    "count": len(expected_ids),
                },
                "actual_report": (
                    diagnostic_run.report.canonical_payload()
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

    return IncidentDiagnosticExperimentResult(
        agent_run=diagnostic_run,
        observation=observation,
    )


def run_diagnosis_demo(
    fault_mode: IncidentFaultMode,
    *,
    run_id: str,
) -> IncidentDiagnosisResult:
    """Execute one complete incident-triage diagnosis demonstration."""
    baseline = run_incident_triage(
        fault_mode,
        run_id=run_id,
    )

    if baseline.passed:
        raise ContractError(
            "diagnosis demo requires "
            "a failing baseline"
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

    return IncidentDiagnosisResult(
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
    "IncidentDiagnosisResult",
    "IncidentDiagnosticExperimentResult",
    "build_diagnosis_problem",
    "execute_selected_experiment",
    "run_diagnosis_demo",
]

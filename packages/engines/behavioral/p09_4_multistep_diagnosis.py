"""Development diagnostic probes for the richer P09.4 incident environment.

The experiment catalogue is treatment-visible. Executed observations come from
real isolated workflow executions, not from the registered prediction table.

This module deliberately does not implement C0-C3 arm-selection policy.
"""

from __future__ import annotations

from dataclasses import dataclass

from environments.agent.p09_4_multistep_incident import (
    P094DiagnosticIntervention,
    P094FaultMode,
    P094IncidentRun,
    expected_incident_ids,
    run_p09_4_multistep_incident,
)

from packages.core.hetren_diagnosis.contracts import (
    AgentTrace,
    ContractError,
    DiagnosisProblem,
    Experiment,
    Hypothesis,
    InterventionKind,
    Observation,
    Verdict,
    canonical_sha256,
)


_HYPOTHESES = (
    (
        "tool_selection_fault",
        "the agent selects the wrong filtering implementation",
    ),
    (
        "parameter_transformation_fault",
        "the correct operation receives an incorrectly transformed parameter",
    ),
    (
        "sequencing_orchestration_fault",
        "a downstream stage consumes evidence before its required prerequisite",
    ),
    (
        "state_context_fault",
        "later workflow behavior consumes stale or inappropriate context state",
    ),
    (
        "environment_interaction_fault",
        "the environment response semantics violate the workflow assumption",
    ),
)


_PROBES = (
    (
        "p1-canonical-tool",
        InterventionKind.REPLACE_TOOL,
        "strategy/tool-selection",
        "tool_selection_fault",
    ),
    (
        "p2-canonical-parameter",
        InterventionKind.OVERRIDE_PARAMETER,
        "strategy/parameter-transformation",
        "parameter_transformation_fault",
    ),
    (
        "p3-canonical-prerequisite-order",
        InterventionKind.REPLAY,
        "orchestration/prerequisite-order",
        "sequencing_orchestration_fault",
    ),
    (
        "p4-fresh-context",
        InterventionKind.REPLAY,
        "context/fresh-state",
        "state_context_fault",
    ),
    (
        "p5-environment-contract",
        InterventionKind.REPLAY,
        "environment/response-contract",
        "environment_interaction_fault",
    ),
)


@dataclass(frozen=True)
class P094DiagnosticExperimentResult:
    """One executed development probe and its workflow-backed observation."""

    agent_run: P094IncidentRun
    observation: Observation

    def __post_init__(
        self,
    ) -> None:
        if not isinstance(
            self.agent_run,
            P094IncidentRun,
        ):
            raise ContractError(
                "agent_run must be a P094IncidentRun"
            )

        if not isinstance(
            self.observation,
            Observation,
        ):
            raise ContractError(
                "observation must be an Observation"
            )


def build_development_problem(
    trace: AgentTrace,
) -> DiagnosisProblem:
    """Build the five-rival development diagnosis problem."""
    if not isinstance(
        trace,
        AgentTrace,
    ):
        raise ContractError(
            "trace must be an AgentTrace"
        )

    hypotheses = tuple(
        Hypothesis(
            key=key,
            description=description,
            prior_probability=0.2,
        )
        for (
            key,
            description,
        )
        in _HYPOTHESES
    )

    hypothesis_keys = tuple(
        key
        for (
            key,
            _,
        )
        in _HYPOTHESES
    )

    prediction_keys = tuple(
        sorted(
            hypothesis_keys
        )
    )

    experiments = tuple(
        Experiment(
            key=probe_key,
            intervention_kind=kind,
            intervention_target=target,
            cost_units=1,
            predicted_verdicts=tuple(
                (
                    hypothesis_key,
                    (
                        Verdict.PASS
                        if hypothesis_key
                        == repaired_hypothesis
                        else Verdict.FAIL
                    ),
                )
                for hypothesis_key
                in prediction_keys
            ),
        )
        for (
            probe_key,
            kind,
            target,
            repaired_hypothesis,
        )
        in _PROBES
    )

    return DiagnosisProblem(
        trace=trace,
        hypotheses=hypotheses,
        experiments=experiments,
        budget_units=5,
    )


def execute_development_probe(
    *,
    problem: DiagnosisProblem,
    experiment_key: str,
    fault_mode: P094FaultMode,
    sequence: int,
) -> P094DiagnosticExperimentResult:
    """Execute one selected development probe against an isolated workflow."""
    if not isinstance(
        problem,
        DiagnosisProblem,
    ):
        raise ContractError(
            "problem must be a DiagnosisProblem"
        )

    if not isinstance(
        experiment_key,
        str,
    ) or not experiment_key:
        raise ContractError(
            "experiment_key is required"
        )

    if not isinstance(
        fault_mode,
        P094FaultMode,
    ):
        raise ContractError(
            "fault_mode must be a P094FaultMode"
        )

    if (
        isinstance(
            sequence,
            bool,
        )
        or not isinstance(
            sequence,
            int,
        )
        or sequence < 0
    ):
        raise ContractError(
            "sequence must be a non-negative integer"
        )

    experiment = next(
        (
            item
            for item in problem.experiments
            if item.key
            == experiment_key
        ),
        None,
    )

    if experiment is None:
        raise ContractError(
            "unknown development experiment key"
        )

    intervention = (
        P094DiagnosticIntervention(
            kind=experiment.intervention_kind,
            target=experiment.intervention_target,
        )
    )

    diagnostic_run = (
        run_p09_4_multistep_incident(
            fault_mode,
            run_id=(
                f"{problem.trace.run_id}:diagnostic:"
                f"{sequence}:{experiment.key}"
            ),
            intervention=intervention,
        )
    )

    verdict = (
        Verdict.PASS
        if diagnostic_run.passed
        else Verdict.FAIL
    )

    counterexample_sha256 = None

    if verdict is Verdict.FAIL:
        counterexample_sha256 = (
            canonical_sha256(
                {
                    "expected_report": {
                        "incident_ids":
                            expected_incident_ids(),
                    },
                    "actual_report":
                        diagnostic_run.report.canonical_payload(),
                }
            )
        )

    observation = Observation(
        sequence=sequence,
        experiment_key=experiment.key,
        experiment_sha256=(
            experiment.experiment_sha256
        ),
        verdict=verdict,
        actual_cost_units=(
            experiment.cost_units
        ),
        evidence_sha256=(
            diagnostic_run.execution_evidence_sha256
        ),
        counterexample_sha256=(
            counterexample_sha256
        ),
    )

    return P094DiagnosticExperimentResult(
        agent_run=diagnostic_run,
        observation=observation,
    )


def development_probe_keys(
) -> tuple[str, ...]:
    return tuple(
        probe[
            0
        ]
        for probe in _PROBES
    )


__all__ = [
    "P094DiagnosticExperimentResult",
    "build_development_problem",
    "development_probe_keys",
    "execute_development_probe",
]

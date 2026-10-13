"""Development-only compound-fault incident-triage open-set experiment.

Uses the existing deterministic workflow and the existing open-set
diagnostic lifecycle. The compound fault is outside the two-hypothesis
single-fault reference set.

This is not a production runner, scientific holdout, independently
isolated verifier, repair authorization, or deployment interface.

The imported underscore-prefixed workflow helpers are deliberate,
version-bound internal fixture dependencies. They are not a public API.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from environments.agent import incident_triage as environment
from packages.core.hetren_diagnosis.contracts import (
    ContractError,
    DiagnosisProblem,
    DiagnosisStatus,
    InterventionKind,
    Observation,
    Verdict,
    canonical_sha256,
)
from packages.core.hetren_diagnosis.open_set import (
    OpenSetDecision,
    select_next_open_set_decision,
)
from packages.engines.behavioral.incident_triage_diagnosis import (
    build_diagnosis_problem,
)


@dataclass(frozen=True)
class CompoundOpenSetDevelopmentResult:
    baseline_run: environment.IncidentTriageRun
    problem: DiagnosisProblem
    diagnostic_runs: tuple[environment.IncidentTriageRun, ...]
    observations: tuple[Observation, ...]
    decisions: tuple[OpenSetDecision, ...]

    @property
    def final_decision(self) -> OpenSetDecision:
        return self.decisions[-1]


def _validate_run_id(run_id: str) -> None:
    if (
        type(run_id) is not str
        or re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}",
            run_id,
        ) is None
    ):
        raise ContractError(
            "development run_id must be a safe nonempty identifier"
        )


def run_compound_incident_triage(
    *,
    run_id: str,
    intervention: InterventionKind | None = None,
) -> environment.IncidentTriageRun:
    """Execute both faults using the actual incident-triage workflow.

    Initial configuration has the strict filter AND an incorrect
    threshold. Each permitted intervention corrects only one fault.
    """
    _validate_run_id(run_id)

    if intervention not in (
        None,
        InterventionKind.REPLACE_TOOL,
        InterventionKind.OVERRIDE_PARAMETER,
    ):
        raise ContractError(
            "compound fixture accepts only a single bounded intervention"
        )

    tool_name, threshold = environment._apply_intervention(
        "strict_severity_filter",
        environment._EXPECTED_THRESHOLD + 1,
        intervention,
    )

    service_rows, selected, report = environment._execute_workflow(
        tool_name,
        threshold,
    )

    trace = environment._build_trace(
        run_id=run_id,
        tool_name=tool_name,
        threshold=threshold,
        service_rows=service_rows,
        selected=selected,
        report=report,
    )

    return environment.IncidentTriageRun(
        run_id=run_id,
        selected_filter_tool=tool_name,
        threshold=threshold,
        report=report,
        trace=trace,
    )


def run_compound_open_set_development(
    *,
    run_id: str,
) -> CompoundOpenSetDevelopmentResult:
    """Run two predeclared interventions and replay real evidence.

    An intermediate specific diagnosis is provisional in this
    development-only falsification challenge. No repair is selected,
    executed, or authorized. The final open-set decision is unchanged.
    """
    _validate_run_id(run_id)

    baseline = run_compound_incident_triage(
        run_id=f"{run_id}:baseline".replace(":", "-"),
    )

    if baseline.passed:
        raise ContractError(
            "compound fixture requires a failing baseline"
        )

    problem = build_diagnosis_problem(baseline.trace)

    observations: list[Observation] = []
    diagnostic_runs: list[environment.IncidentTriageRun] = []

    # Falsification challenge, declared before either experiment runs.
    #
    # The first observation may produce a specific diagnosis under the
    # existing single-fault reference set. That decision is provisional
    # for THIS development challenge, not permission to repair.
    #
    # Execute the second declared intervention even if the existing
    # open-set lifecycle diagnoses after the first observation.
    # This is an additional audit policy, not planner-directed behavior
    # and not a change to the core open-set lifecycle.
    audit_plan = tuple(problem.experiments)

    if (
        tuple(item.key for item in audit_plan)
        != (
            "e1-replace-filter-tool",
            "e2-override-threshold",
        )
        or tuple(item.intervention_kind for item in audit_plan)
        != (
            InterventionKind.REPLACE_TOOL,
            InterventionKind.OVERRIDE_PARAMETER,
        )
        or sum(item.cost_units for item in audit_plan)
        > problem.budget_units
    ):
        raise ContractError(
            "compound falsification plan differs from the "
            "two-probe budgeted reference design"
        )

    decision = select_next_open_set_decision(problem)

    if (
        decision.status is not DiagnosisStatus.ACTIVE
        or decision.experiment_key != audit_plan[0].key
    ):
        raise ContractError(
            "initial open-set decision differs from declared first probe"
        )

    decisions = [decision]

    for sequence, experiment in enumerate(audit_plan):
        if sequence == 1 and (
            decision.status is not DiagnosisStatus.DIAGNOSED
            or decision.diagnosed_hypothesis_key is None
        ):
            raise ContractError(
                "falsification challenge expected a provisional "
                "single-fault diagnosis before its second probe"
            )

        diagnostic_run = run_compound_incident_triage(
            run_id=(
                f"{run_id}-diagnostic-{sequence}-{experiment.key}"
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
            expected_ids = environment.expected_incident_ids()
            counterexample_sha256 = canonical_sha256(
                {
                    "expected_report": {
                        "service": baseline.report.service,
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
            experiment_sha256=experiment.experiment_sha256,
            verdict=verdict,
            actual_cost_units=experiment.cost_units,
            evidence_sha256=(
                diagnostic_run.execution_evidence_sha256
            ),
            counterexample_sha256=counterexample_sha256,
        )

        diagnostic_runs.append(diagnostic_run)
        observations.append(observation)

        decision = select_next_open_set_decision(
            problem,
            tuple(observations),
        )
        decisions.append(decision)

    if decision.status is DiagnosisStatus.ACTIVE:
        raise ContractError(
            "compound diagnostic execution ended with an active experiment"
        )

    return CompoundOpenSetDevelopmentResult(
        baseline_run=baseline,
        problem=problem,
        diagnostic_runs=tuple(diagnostic_runs),
        observations=tuple(observations),
        decisions=tuple(decisions),
    )

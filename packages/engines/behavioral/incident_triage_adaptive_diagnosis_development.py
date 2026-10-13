"""Pilot-derived adaptive incident-triage diagnosis policy.

Development-only policy designed after inspecting the three known
evaluation cases. Its performance on those cases is training/pilot
evidence, NOT independent generalization evidence.

The first diagnostic intervention is always executed. A failed first
intervention triggers a real, separately executed falsification probe
if budget permits. No candidate repair or deployment is authorized.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from environments.agent.incident_triage import (
    IncidentFaultMode,
    IncidentTriageRun,
    expected_incident_ids,
    run_incident_triage,
)
from packages.core.hetren_diagnosis.contracts import (
    ContractError,
    DiagnosisProblem,
    DiagnosisStatus,
    Observation,
    Verdict,
    canonical_sha256,
)
from packages.core.hetren_diagnosis.open_set import (
    OpenSetDecision,
    OpenSetReason,
    select_next_open_set_decision,
)
from packages.engines.behavioral.incident_triage_diagnosis import (
    build_diagnosis_problem,
)
from packages.engines.behavioral.incident_triage_compound_open_set_development import (
    run_compound_incident_triage,
)


SCENARIOS = (
    "filter_tool_selection",
    "threshold_transformation",
    "compound_fault",
)

_EXPECTED_EXPERIMENT_KEYS = (
    "e1-replace-filter-tool",
    "e2-override-threshold",
)


@dataclass(frozen=True)
class AdaptiveDiagnosisDevelopmentResult:
    scenario: str
    baseline_run: IncidentTriageRun
    problem: DiagnosisProblem
    diagnostic_runs: tuple[IncidentTriageRun, ...]
    observations: tuple[Observation, ...]
    initial_decision: OpenSetDecision
    first_probe_decision: OpenSetDecision
    final_open_set_decision: OpenSetDecision | None
    policy_status: DiagnosisStatus
    policy_reason: str
    diagnosed_hypothesis_key: str | None

    @property
    def experiment_count(self) -> int:
        return len(self.observations)

    @property
    def experiment_cost_units(self) -> int:
        return sum(
            item.actual_cost_units
            for item in self.observations
        )


def _observation(
    *,
    sequence,
    experiment,
    run,
    expected_service,
):
    verdict = Verdict.PASS if run.passed else Verdict.FAIL

    counterexample = None

    if verdict is Verdict.FAIL:
        expected_ids = expected_incident_ids()

        counterexample = canonical_sha256({
            "expected_report": {
                "service": expected_service,
                "incident_ids": expected_ids,
                "count": len(expected_ids),
            },
            "actual_report": run.report.canonical_payload(),
        })

    return Observation(
        sequence=sequence,
        experiment_key=experiment.key,
        experiment_sha256=experiment.experiment_sha256,
        verdict=verdict,
        actual_cost_units=experiment.cost_units,
        evidence_sha256=run.execution_evidence_sha256,
        counterexample_sha256=counterexample,
    )


def run_adaptive_diagnosis_development(
    scenario: str,
    *,
    run_id: str,
    budget_units: int = 2,
) -> AdaptiveDiagnosisDevelopmentResult:
    """Execute a 1-or-2-probe policy over actual workflow behavior."""

    if type(scenario) is not str or scenario not in SCENARIOS:
        raise ContractError("unsupported development scenario")

    if (
        type(run_id) is not str
        or re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.-]{0,31}",
            run_id,
        ) is None
    ):
        raise ContractError("invalid development run identifier")

    if type(budget_units) is not int or budget_units not in (1, 2):
        raise ContractError("budget_units must be 1 or 2")

    if scenario == "compound_fault":
        def execute(suffix, intervention=None):
            return run_compound_incident_triage(
                run_id=f"{run_id}-{suffix}",
                intervention=intervention,
            )
    else:
        mode = IncidentFaultMode(scenario)

        def execute(suffix, intervention=None):
            return run_incident_triage(
                mode,
                run_id=f"{run_id}-{suffix}",
                intervention=intervention,
            )

    baseline = execute("baseline")

    if baseline.passed:
        raise ContractError("baseline must fail")

    problem = build_diagnosis_problem(baseline.trace)

    if (
        tuple(item.key for item in problem.experiments)
        != _EXPECTED_EXPERIMENT_KEYS
    ):
        raise ContractError(
            "unexpected reference-set experiment design"
        )

    initial = select_next_open_set_decision(problem)

    first_experiment = problem.experiments[0]

    if (
        initial.status is not DiagnosisStatus.ACTIVE
        or initial.experiment_key != first_experiment.key
        or first_experiment.cost_units > budget_units
    ):
        raise ContractError(
            "initial intervention is not available within budget"
        )

    first_run = execute(
        "probe-1",
        first_experiment.intervention_kind,
    )
    first_observation = _observation(
        sequence=0,
        experiment=first_experiment,
        run=first_run,
        expected_service=baseline.report.service,
    )

    runs = [first_run]
    observations = [first_observation]

    first_decision = select_next_open_set_decision(
        problem, tuple(observations),
    )

    def result(status, reason, cause, final):
        return AdaptiveDiagnosisDevelopmentResult(
            scenario=scenario,
            baseline_run=baseline,
            problem=problem,
            diagnostic_runs=tuple(runs),
            observations=tuple(observations),
            initial_decision=initial,
            first_probe_decision=first_decision,
            final_open_set_decision=final,
            policy_status=status,
            policy_reason=reason,
            diagnosed_hypothesis_key=cause,
        )

    if first_observation.verdict is Verdict.PASS:
        if (
            first_decision.status is not DiagnosisStatus.DIAGNOSED
            or first_decision.diagnosed_hypothesis_key
            != "filter_tool_selection_fault"
        ):
            raise ContractError(
                "first-probe confirmation did not establish "
                "the expected reference-set diagnosis"
            )

        return result(
            first_decision.status,
            first_decision.reason.value,
            first_decision.diagnosed_hypothesis_key,
            first_decision,
        )

    # The failed first probe is observationally ambiguous between
    # the threshold-only fault and the compound fault. An early
    # specific open-set decision is provisional for this policy.
    second_experiment = problem.experiments[1]

    if (
        first_observation.actual_cost_units
        + second_experiment.cost_units
        > budget_units
    ):
        return result(
            DiagnosisStatus.BUDGET_EXHAUSTED,
            "falsification_budget_exhausted",
            None,
            None,
        )

    second_run = execute(
        "probe-2",
        second_experiment.intervention_kind,
    )

    second_observation = _observation(
        sequence=1,
        experiment=second_experiment,
        run=second_run,
        expected_service=baseline.report.service,
    )

    runs.append(second_run)
    observations.append(second_observation)

    final = select_next_open_set_decision(
        problem, tuple(observations),
    )

    if (
        second_observation.verdict is Verdict.PASS
        and final.status is DiagnosisStatus.DIAGNOSED
        and final.diagnosed_hypothesis_key
        == "threshold_transformation_fault"
    ):
        return result(
            final.status,
            final.reason.value,
            final.diagnosed_hypothesis_key,
            final,
        )

    if (
        second_observation.verdict is Verdict.FAIL
        and final.status is DiagnosisStatus.INCONCLUSIVE
        and final.reason is OpenSetReason.EVIDENCE_CONTRADICTION
        and final.diagnosed_hypothesis_key is None
    ):
        return result(
            final.status,
            final.reason.value,
            None,
            final,
        )

    raise ContractError(
        "adaptive policy encountered an unsupported evidence pattern"
    )

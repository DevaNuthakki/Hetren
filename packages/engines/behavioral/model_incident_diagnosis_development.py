"""Development-only diagnosis for captured model incident actions.

Replays the original model capture unchanged. Diagnostic interventions
execute separate local incident-triage workflows using the existing
environment and the existing shared two-probe policy.

A local counterfactual is NOT another model response, scientific
verification, proof of model intent, or a production repair.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from environments.agent.incident_triage import (
    IncidentTriageRun,
    expected_incident_ids,
    incident_triage_task_spec,
    run_configured_incident_triage,
)
from packages.contracts import ContractError
from packages.core.hetren_diagnosis.adaptive_two_probe_development import (
    AdaptiveTwoProbeDevelopmentResult,
    run_adaptive_two_probe_development,
)
from packages.core.hetren_diagnosis.contracts import (
    DiagnosisStatus,
    InterventionKind,
    Observation,
    Verdict,
    canonical_sha256,
)
from packages.engines.behavioral.incident_triage_diagnosis import (
    build_diagnosis_problem,
)
from packages.engines.behavioral.model_incident_triage_agent import (
    CapturedIncidentTriageRun,
    run_captured_incident_triage,
)
from packages.model_capture import ModelCapture, ModelRequest


@dataclass(frozen=True)
class CounterfactualIncidentTriageRun:
    """One executed local intervention, not fresh model inference."""

    run_id: str
    source_request_sha256: str
    source_capture_sha256: str
    source_proposal_sha256: str
    intervention: InterventionKind
    selected_filter_tool: str
    threshold: int
    environment_run: IncidentTriageRun

    @property
    def trace(self):
        return self.environment_run.trace

    @property
    def passed(self) -> bool:
        return self.environment_run.passed

    @property
    def execution_evidence_sha256(self) -> str:
        return canonical_sha256({
            "record_type": "CounterfactualIncidentTriageRun",
            "development_counterfactual": True,
            "run_id": self.run_id,
            "source_request_sha256": self.source_request_sha256,
            "source_capture_sha256": self.source_capture_sha256,
            "source_proposal_sha256": self.source_proposal_sha256,
            "intervention": self.intervention.value,
            "selected_filter_tool": self.selected_filter_tool,
            "threshold": self.threshold,
            "environment_evidence_sha256":
                self.environment_run.execution_evidence_sha256,
            "trace_sha256": self.trace.trace_sha256,
            "passed": self.passed,
        })


@dataclass(frozen=True)
class ModelIncidentDiagnosisDevelopmentResult:
    baseline_run: CapturedIncidentTriageRun
    source_capture_sha256: str
    policy_result: AdaptiveTwoProbeDevelopmentResult

    @property
    def limitations(self) -> tuple[str, ...]:
        return (
            "single fixed synthetic incident development environment",
            "recorded model output is not independently authenticated",
            "diagnostic probes are local counterfactual executions",
            "no new model inference during diagnosis",
            "two predefined fault hypotheses only",
            "diagnosis does not explain model intent",
            "no independent scientific verification",
            "no automatic model repair or deployment authorization",
        )


def _execute_counterfactual(
    *,
    baseline: CapturedIncidentTriageRun,
    intervention: InterventionKind,
    run_id: str,
) -> CounterfactualIncidentTriageRun:
    """Change exactly one action dimension and execute a local tool."""
    if (
        baseline.status != "executed"
        or baseline.selected_tool is None
        or baseline.threshold is None
    ):
        raise ContractError(
            "counterfactual requires a valid executed baseline"
        )

    tool = baseline.selected_tool
    threshold = baseline.threshold

    if intervention is InterventionKind.REPLACE_TOOL:
        tool = "inclusive_severity_filter"
    elif intervention is InterventionKind.OVERRIDE_PARAMETER:
        _, threshold, _ = incident_triage_task_spec()
    else:
        raise ContractError("unsupported incident intervention")

    executed = run_configured_incident_triage(
        tool_name=tool,
        threshold=threshold,
        run_id=run_id,
    )

    if (
        executed.selected_filter_tool != tool
        or executed.threshold != threshold
        or executed.trace.run_id != run_id
    ):
        raise ContractError(
            "counterfactual execution disagrees with intervention"
        )

    return CounterfactualIncidentTriageRun(
        run_id=run_id,
        source_request_sha256=baseline.request_sha256,
        source_capture_sha256=baseline.capture_sha256,
        source_proposal_sha256=baseline.proposal_sha256,
        intervention=intervention,
        selected_filter_tool=tool,
        threshold=threshold,
        environment_run=executed,
    )


def diagnose_captured_incident_development(
    *,
    request: ModelRequest,
    capture: ModelCapture,
    run_id: str,
    budget_units: int = 2,
) -> ModelIncidentDiagnosisDevelopmentResult:
    """Run evidence-bound local probes on a failed captured action.

    The original capture is never edited. Rejected and successful
    proposals are not forced into the two diagnostic hypotheses.
    """
    if (
        type(run_id) is not str
        or re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.-]{0,31}",
            run_id,
        ) is None
    ):
        raise ContractError("invalid incident diagnostic run_id")

    baseline = run_captured_incident_triage(
        request=request,
        capture=capture,
        run_id=f"{run_id}-baseline",
    )

    if baseline.passed:
        raise ContractError(
            "passing baseline has no demonstrated failure to diagnose"
        )

    if (
        baseline.status != "executed"
        or baseline.environment_run is None
        or baseline.selected_tool is None
        or baseline.threshold is None
    ):
        raise ContractError(
            "rejected or unsupported incident proposal cannot be diagnosed"
        )

    problem = build_diagnosis_problem(baseline.trace)

    def execute_probe(experiment, sequence):
        run = _execute_counterfactual(
            baseline=baseline,
            intervention=experiment.intervention_kind,
            run_id=f"{run_id}-probe-{sequence}",
        )

        counterexample = None

        if not run.passed:
            counterexample = canonical_sha256({
                "expected_incident_ids": expected_incident_ids(),
                "actual_report":
                    run.environment_run.report.canonical_payload(),
                "intervention": run.intervention.value,
                "execution_evidence_sha256":
                    run.execution_evidence_sha256,
            })

        observation = Observation(
            sequence=sequence,
            experiment_key=experiment.key,
            experiment_sha256=experiment.experiment_sha256,
            verdict=Verdict.PASS if run.passed else Verdict.FAIL,
            actual_cost_units=experiment.cost_units,
            evidence_sha256=run.execution_evidence_sha256,
            counterexample_sha256=counterexample,
        )

        return observation, run

    result = run_adaptive_two_probe_development(
        problem,
        execute_probe=execute_probe,
        budget_units=budget_units,
    )

    if (
        result.policy_status is DiagnosisStatus.DIAGNOSED
        and result.diagnosed_hypothesis_key is None
    ):
        raise ContractError("diagnosis lacks hypothesis identity")

    return ModelIncidentDiagnosisDevelopmentResult(
        baseline_run=baseline,
        source_capture_sha256=capture.capture_sha256,
        policy_result=result,
    )

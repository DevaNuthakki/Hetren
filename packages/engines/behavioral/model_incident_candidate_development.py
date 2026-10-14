"""Offline cross-scenario regression for diagnosed incident interventions.

Diagnoses originate in the existing fixed development fixture. Each
candidate run executes on a separate captured synthetic scenario; it
never edits the model's recorded response. These checks demonstrate
software behavior, not independent verification or model generalization.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from environments.agent.incident_triage import TriageReport, filter_incident_rows
from packages.contracts import ContractError
from packages.core.hetren_diagnosis.contracts import (
    AgentTrace, DiagnosisStatus, EventKind, InterventionKind,
    TraceEvent, canonical_sha256,
)
from packages.engines.behavioral.incident_scenario_development import (
    IncidentScenario, IncidentScenarioEvaluation, evaluate_incident_scenario,
)
from packages.engines.behavioral.model_incident_diagnosis_development import (
    ModelIncidentDiagnosisDevelopmentResult,
)
from packages.engines.behavioral.model_incident_scenario_agent import (
    CapturedScenarioIncidentRun, run_captured_scenario_incident,
)
from packages.model_capture import ModelCapture, ModelRequest


@dataclass(frozen=True)
class ScenarioCandidateCase:
    scenario: IncidentScenario
    request: ModelRequest
    capture: ModelCapture

    def __post_init__(self) -> None:
        if not isinstance(self.scenario, IncidentScenario):
            raise ContractError("invalid candidate scenario")
        if not isinstance(self.request, ModelRequest):
            raise ContractError("invalid candidate request")
        if not isinstance(self.capture, ModelCapture):
            raise ContractError("invalid candidate capture")


@dataclass(frozen=True)
class ScenarioCandidateOutcome:
    scenario_id: str
    baseline: CapturedScenarioIncidentRun
    intervention: InterventionKind
    run_id: str
    candidate_tool: str
    candidate_threshold: int
    candidate_report: TriageReport
    candidate_evaluation: IncidentScenarioEvaluation
    trace: AgentTrace

    @property
    def passed(self) -> bool:
        return self.candidate_evaluation.passed

    @property
    def improves_failure(self) -> bool:
        return not self.baseline.passed and self.passed

    @property
    def preserves_success(self) -> bool:
        return (
            not self.baseline.passed
            or (
                self.passed
                and self.baseline.report == self.candidate_report
                and self.baseline.evaluation == self.candidate_evaluation
            )
        )

    @property
    def execution_evidence_sha256(self) -> str:
        return canonical_sha256({
            "record_type": "ScenarioCandidateOutcome",
            "schema_version": 1,
            "development_only": True,
            "scenario_id": self.scenario_id,
            "scenario_sha256": self.baseline.scenario_sha256,
            "baseline_evidence_sha256": self.baseline.execution_evidence_sha256,
            "source_capture_sha256": self.baseline.capture_sha256,
            "source_proposal_sha256": self.baseline.proposal_sha256,
            "intervention": self.intervention.value,
            "run_id": self.run_id,
            "candidate_tool": self.candidate_tool,
            "candidate_threshold": self.candidate_threshold,
            "report_sha256": self.candidate_report.report_sha256,
            "evaluation_sha256": self.candidate_evaluation.evaluation_evidence_sha256,
            "trace_sha256": self.trace.trace_sha256,
            "passed": self.passed,
        })


@dataclass(frozen=True)
class CrossScenarioCandidateDevelopmentResult:
    source_capture_sha256: str
    source_baseline_evidence_sha256: str
    diagnosed_hypothesis_key: str
    intervention: InterventionKind
    outcomes: tuple[ScenarioCandidateOutcome, ...]

    @property
    def passed(self) -> bool:
        return (
            any(item.improves_failure for item in self.outcomes)
            and any(item.baseline.passed for item in self.outcomes)
            and all(item.passed and item.preserves_success for item in self.outcomes)
        )

    @property
    def evidence_sha256(self) -> str:
        return canonical_sha256({
            "record_type": "CrossScenarioCandidateDevelopmentResult",
            "schema_version": 1,
            "development_only": True,
            "source_capture_sha256": self.source_capture_sha256,
            "source_baseline_evidence_sha256": self.source_baseline_evidence_sha256,
            "diagnosed_hypothesis_key": self.diagnosed_hypothesis_key,
            "intervention": self.intervention.value,
            "outcome_evidence_sha256": [
                item.execution_evidence_sha256 for item in self.outcomes
            ],
            "passed": self.passed,
        })

    @property
    def limitations(self) -> tuple[str, ...]:
        return (
            "synthetic selected development cases, not blinded holdouts",
            "single recorded diagnosis, not proof of model intent",
            "interventions modify local actions, not original model captures",
            "candidate success does not establish live-model generalization",
            "no independent scientific verification",
            "no automatic repair or deployment authorization",
        )


def _event(*, sequence, kind, operation, inputs, outputs, before, after):
    return TraceEvent(
        sequence=sequence, kind=kind,
        component="scenario_candidate_development", operation=operation,
        input_sha256=canonical_sha256(inputs),
        output_sha256=canonical_sha256(outputs),
        state_before_sha256=canonical_sha256(before),
        state_after_sha256=canonical_sha256(after),
    )


def _execute_candidate(
    *, case: ScenarioCandidateCase, baseline: CapturedScenarioIncidentRun,
    intervention: InterventionKind, run_id: str,
) -> ScenarioCandidateOutcome:
    if baseline.status != "executed" or baseline.selected_tool is None or baseline.threshold is None:
        raise ContractError("candidate requires valid executed action")

    tool, threshold = baseline.selected_tool, baseline.threshold
    if intervention is InterventionKind.REPLACE_TOOL:
        tool = "inclusive_severity_filter"
    elif intervention is InterventionKind.OVERRIDE_PARAMETER:
        threshold = case.scenario.minimum_severity
    else:
        raise ContractError("unsupported candidate intervention")

    service_rows, selected = filter_incident_rows(
        records=case.scenario.records,
        target_service=case.scenario.target_service,
        tool_name=tool, threshold=threshold,
    )
    report = TriageReport(
        service=case.scenario.target_service,
        incident_ids=tuple(row[0] for row in selected),
        count=len(selected),
    )
    evaluation = evaluate_incident_scenario(scenario=case.scenario, report=report)
    if evaluation.scenario_sha256 != baseline.scenario_sha256 or evaluation.report != report:
        raise ContractError("candidate evaluation provenance mismatch")

    state_0 = {"phase": "baseline", "baseline_sha256": baseline.execution_evidence_sha256}
    state_1 = {"phase": "candidate_selected", "tool": tool, "threshold": threshold}
    state_2 = {"phase": "executed", "report_sha256": report.report_sha256}
    state_3 = {"phase": "evaluated", "evaluation_sha256": evaluation.evaluation_evidence_sha256}
    events = (
        _event(
            sequence=0, kind=EventKind.DECISION, operation="apply_diagnosed_intervention",
            inputs={"baseline_sha256": baseline.execution_evidence_sha256,
                    "source_capture_sha256": baseline.capture_sha256,
                    "source_proposal_sha256": baseline.proposal_sha256,
                    "intervention": intervention.value},
            outputs={"tool": tool, "threshold": threshold}, before=state_0, after=state_1,
        ),
        _event(
            sequence=1, kind=EventKind.TOOL_CALL, operation=tool,
            inputs={"scenario_sha256": case.scenario.scenario_sha256,
                    "threshold": threshold, "tool": tool,
                    "service_row_ids": [row[0] for row in service_rows]},
            outputs=report.canonical_payload(), before=state_1, after=state_2,
        ),
        _event(
            sequence=2, kind=EventKind.TERMINATION, operation="evaluate_candidate",
            inputs=report.canonical_payload(),
            outputs={"evaluation_sha256": evaluation.evaluation_evidence_sha256,
                     "passed": evaluation.passed},
            before=state_2, after=state_3,
        ),
    )
    return ScenarioCandidateOutcome(
        scenario_id=case.scenario.scenario_id, baseline=baseline,
        intervention=intervention, run_id=run_id,
        candidate_tool=tool, candidate_threshold=threshold,
        candidate_report=report, candidate_evaluation=evaluation,
        trace=AgentTrace(run_id=run_id, events=events),
    )


def evaluate_diagnosed_incident_candidate_development(
    *, diagnosis: ModelIncidentDiagnosisDevelopmentResult,
    cases: tuple[ScenarioCandidateCase, ...], run_id: str = "a510b3",
) -> CrossScenarioCandidateDevelopmentResult:
    """Test a diagnosed local intervention against distinct captured scenarios.

    At least one initially failing case and one initially passing
    control must be present. A single uncorrected case fails the gate.
    """
    if not isinstance(diagnosis, ModelIncidentDiagnosisDevelopmentResult):
        raise ContractError("invalid diagnosis result")
    if type(run_id) is not str or re.fullmatch(r"[a-z][a-z0-9-]{0,17}", run_id) is None:
        raise ContractError("invalid candidate evaluation run_id")
    if type(cases) is not tuple or not 2 <= len(cases) <= 5:
        raise ContractError("candidate evaluation requires 2-5 cases")

    baseline_source = diagnosis.baseline_run
    policy = diagnosis.policy_result
    if (
        policy.policy_status is not DiagnosisStatus.DIAGNOSED
        or baseline_source.status != "executed"
        or baseline_source.passed
        or diagnosis.source_capture_sha256 != baseline_source.capture_sha256
    ):
        raise ContractError("candidate requires failed, diagnosed baseline")

    mapping = {
        "filter_tool_selection_fault": InterventionKind.REPLACE_TOOL,
        "threshold_transformation_fault": InterventionKind.OVERRIDE_PARAMETER,
    }
    intervention = mapping.get(policy.diagnosed_hypothesis_key)
    if intervention is None:
        raise ContractError("unrecognized diagnosed incident hypothesis")
    if not policy.observations or len(policy.observations) != len(policy.diagnostic_runs):
        raise ContractError("diagnostic probe evidence missing")
    for observation, run in zip(policy.observations, policy.diagnostic_runs):
        if (
            observation.evidence_sha256 != run.execution_evidence_sha256
            or run.source_capture_sha256 != diagnosis.source_capture_sha256
            or run.source_proposal_sha256 != baseline_source.proposal_sha256
        ):
            raise ContractError("diagnostic probe evidence mismatch")

    seen_ids, seen_scenarios, seen_requests = set(), set(), set()
    outcomes = []
    for index, case in enumerate(cases):
        if not isinstance(case, ScenarioCandidateCase):
            raise ContractError("invalid candidate case")
        scenario_id = case.scenario.scenario_id
        scenario_sha = case.scenario.scenario_sha256
        if scenario_id in seen_ids or scenario_sha in seen_scenarios:
            raise ContractError("duplicate candidate scenario")
        if case.request.request_sha256 in seen_requests:
            raise ContractError("duplicate candidate request")
        seen_ids.add(scenario_id)
        seen_scenarios.add(scenario_sha)
        seen_requests.add(case.request.request_sha256)

        baseline = run_captured_scenario_incident(
            scenario=case.scenario, request=case.request,
            capture=case.capture, run_id=f"{run_id}-{index}-base",
        )
        candidate = _execute_candidate(
            case=case, baseline=baseline, intervention=intervention,
            run_id=f"{run_id}-{index}-candidate",
        )
        if candidate.trace.run_id != candidate.run_id or candidate.baseline != baseline:
            raise ContractError("candidate run evidence mismatch")
        outcomes.append(candidate)

    if not any(item.baseline.passed for item in outcomes) or not any(
        not item.baseline.passed for item in outcomes
    ):
        raise ContractError("candidate requires failing and passing controls")

    return CrossScenarioCandidateDevelopmentResult(
        source_capture_sha256=diagnosis.source_capture_sha256,
        source_baseline_evidence_sha256=baseline_source.execution_evidence_sha256,
        diagnosed_hypothesis_key=policy.diagnosed_hypothesis_key,
        intervention=intervention,
        outcomes=tuple(outcomes),
    )

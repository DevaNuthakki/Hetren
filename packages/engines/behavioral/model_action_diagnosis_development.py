"""Development diagnosis of bounded model-proposed tool failures.

The original ModelCapture is replayed unchanged. Each intervention is
a NEW LOCAL COUNTERFACTUAL TOOL EXECUTION, not a new model response,
not evidence that the provider chose the intervened action, and not
a fresh or independently blinded scientific experiment.

Only the two previously declared arithmetic hypotheses are supported.
Unknown tools, malformed payloads, and other unsupported failures
cannot be assigned a cause by this adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from packages.contracts import ContractError
from packages.core.hetren_diagnosis.adaptive_two_probe_development import (
    AdaptiveTwoProbeDevelopmentResult,
    run_adaptive_two_probe_development,
)
from packages.core.hetren_diagnosis.contracts import (
    AgentTrace,
    DiagnosisStatus,
    EventKind,
    InterventionKind,
    Observation,
    TraceEvent,
    Verdict,
    canonical_sha256,
)
from packages.engines.behavioral.deterministic_tool_agent import (
    build_diagnosis_problem,
)
from packages.engines.behavioral.model_proposed_tool_agent import (
    MAX_OPERAND,
    CapturedAdditionRun,
    _validate_proposal,
    run_captured_addition_agent,
)
from packages.model_capture import (
    ModelCapture,
    ModelRequest,
    replay_json_capture,
)


@dataclass(frozen=True)
class CounterfactualAdditionRun:
    """One actual local tool probe, explicitly NOT new model inference."""

    run_id: str
    source_request_sha256: str
    source_capture_sha256: str
    source_proposal_sha256: str
    intervention: InterventionKind
    candidate_sha256: str
    status: str
    rejection_reason: str | None
    selected_tool: str | None
    arguments: tuple[int, int] | None
    output: int | None
    expected_output: int
    trace: AgentTrace

    @property
    def passed(self) -> bool:
        return self.status == "executed" and (
            self.output == self.expected_output
        )

    @property
    def execution_evidence_sha256(self) -> str:
        return canonical_sha256({
            "record_type": "CounterfactualAdditionRun",
            "development_counterfactual": True,
            "run_id": self.run_id,
            "source_request_sha256": self.source_request_sha256,
            "source_capture_sha256": self.source_capture_sha256,
            "source_proposal_sha256": self.source_proposal_sha256,
            "intervention": self.intervention.value,
            "candidate_sha256": self.candidate_sha256,
            "status": self.status,
            "rejection_reason": self.rejection_reason,
            "selected_tool": self.selected_tool,
            "arguments": self.arguments,
            "output": self.output,
            "expected_output": self.expected_output,
            "trace_sha256": self.trace.trace_sha256,
        })


@dataclass(frozen=True)
class ModelActionDiagnosisDevelopmentResult:
    """Pilot-derived diagnosis; no claims of generalization."""

    baseline_run: CapturedAdditionRun
    source_capture_sha256: str
    policy_result: AdaptiveTwoProbeDevelopmentResult

    @property
    def limitations(self) -> tuple[str, ...]:
        return (
            "baseline capture provenance is not independently authenticated",
            "interventions are local counterfactual executions",
            "no fresh model inference was performed during diagnosis",
            "two-hypothesis development fixture only",
            "diagnosis does not authorize deployment or repair",
        )


def _validate_supported_source(proposal: dict) -> None:
    if set(proposal) != {"tool", "a", "b"}:
        raise ContractError(
            "unsupported proposal shape: cannot diagnose"
        )

    if (
        type(proposal["tool"]) is not str
        or proposal["tool"] not in ("add_ints", "multiply_ints")
    ):
        raise ContractError(
            "unsupported tool proposal: cannot diagnose"
        )

    for key in ("a", "b"):
        value = proposal[key]
        if (
            type(value) is not int
            or value < 0
            or value > MAX_OPERAND
        ):
            raise ContractError(
                "unsupported argument type or range: cannot diagnose"
            )


def _event(
    sequence: int,
    kind: EventKind,
    component: str,
    operation: str,
    source: object,
    output: object,
    before: object,
    after: object,
) -> TraceEvent:
    return TraceEvent(
        sequence=sequence,
        kind=kind,
        component=component,
        operation=operation,
        input_sha256=canonical_sha256(source),
        output_sha256=canonical_sha256(output),
        state_before_sha256=canonical_sha256(before),
        state_after_sha256=canonical_sha256(after),
    )


def _execute_counterfactual(
    *,
    request: ModelRequest,
    capture: ModelCapture,
    run_id: str,
    left: int,
    right: int,
    intervention: InterventionKind,
) -> CounterfactualAdditionRun:
    """Apply one controlled change and execute an actual local tool."""
    original = replay_json_capture(
        request=request,
        capture=capture,
    )
    _validate_supported_source(original)

    candidate = dict(original)

    if intervention is InterventionKind.REPLACE_TOOL:
        candidate["tool"] = "add_ints"
    elif intervention is InterventionKind.OVERRIDE_PARAMETER:
        candidate["a"] = left
        candidate["b"] = right
    else:
        raise ContractError("unsupported diagnostic intervention")

    tool, rejection = _validate_proposal(
        candidate,
        left=left,
        right=right,
    )

    source_hash = canonical_sha256(original)
    candidate_hash = canonical_sha256(candidate)

    start = {
        "phase": "original_capture",
        "capture_sha256": capture.capture_sha256,
        "original_proposal_sha256": source_hash,
    }
    intervened = {
        "phase": "counterfactual_proposal",
        "candidate_sha256": candidate_hash,
        "intervention": intervention.value,
    }

    events = [
        _event(
            0,
            EventKind.DECISION,
            "diagnostic_intervention",
            intervention.value,
            {
                "original_proposal_sha256": source_hash,
                "source_capture_sha256": capture.capture_sha256,
            },
            candidate,
            start,
            intervened,
        )
    ]

    arguments = None
    output = None

    if rejection is not None:
        status = "rejected"
        events.append(
            _event(
                1,
                EventKind.TERMINATION,
                "agent",
                "reject_counterfactual",
                candidate,
                {"reason": rejection},
                intervened,
                {"phase": "rejected", "reason": rejection},
            )
        )
    else:
        arguments = (candidate["a"], candidate["b"])

        if tool == "add_ints":
            output = arguments[0] + arguments[1]
        elif tool == "multiply_ints":
            output = arguments[0] * arguments[1]
        else:
            raise ContractError("allowlist invariant violated")

        status = "executed"
        completed = {
            "phase": "tool_executed",
            "tool": tool,
            "result": output,
        }

        events.append(
            _event(
                1,
                EventKind.TOOL_CALL,
                tool,
                "invoke_counterfactual",
                {"tool": tool, "arguments": arguments},
                {"result": output},
                intervened,
                completed,
            )
        )
        events.append(
            _event(
                2,
                EventKind.TERMINATION,
                "task_evaluator",
                "evaluate_addition",
                {"result": output},
                {"correct": output == left + right},
                completed,
                {
                    "phase": "evaluated",
                    "correct": output == left + right,
                },
            )
        )

    return CounterfactualAdditionRun(
        run_id=run_id,
        source_request_sha256=request.request_sha256,
        source_capture_sha256=capture.capture_sha256,
        source_proposal_sha256=source_hash,
        intervention=intervention,
        candidate_sha256=candidate_hash,
        status=status,
        rejection_reason=rejection,
        selected_tool=tool,
        arguments=arguments,
        output=output,
        expected_output=left + right,
        trace=AgentTrace(run_id=run_id, events=tuple(events)),
    )


def diagnose_captured_addition_development(
    *,
    request: ModelRequest,
    capture: ModelCapture,
    run_id: str,
    left: int,
    right: int,
    budget_units: int = 2,
) -> ModelActionDiagnosisDevelopmentResult:
    """Investigate a failed captured action using separate local probes."""
    if (
        type(run_id) is not str
        or re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.-]{0,14}",
            run_id,
        ) is None
    ):
        raise ContractError("invalid diagnostic run_id")

    baseline = run_captured_addition_agent(
        request=request,
        capture=capture,
        run_id=f"{run_id}-baseline",
        left=left,
        right=right,
    )

    if baseline.passed:
        raise ContractError(
            "passing baseline has no demonstrated failure to diagnose"
        )

    original = replay_json_capture(
        request=request,
        capture=capture,
    )
    _validate_supported_source(original)

    if (
        baseline.status == "rejected"
        and baseline.rejection_reason
        != "arguments_do_not_match_task"
    ):
        raise ContractError(
            "unsupported rejection reason: cannot diagnose"
        )

    problem = build_diagnosis_problem(baseline.trace)

    def execute_probe(experiment, sequence):
        run = _execute_counterfactual(
            request=request,
            capture=capture,
            run_id=f"{run_id}-probe-{sequence}",
            left=left,
            right=right,
            intervention=experiment.intervention_kind,
        )

        counterexample = None

        if not run.passed:
            counterexample = canonical_sha256({
                "expected_output": run.expected_output,
                "actual_output": run.output,
                "status": run.status,
                "rejection_reason": run.rejection_reason,
                "candidate_sha256": run.candidate_sha256,
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

    policy = run_adaptive_two_probe_development(
        problem,
        execute_probe=execute_probe,
        budget_units=budget_units,
    )

    return ModelActionDiagnosisDevelopmentResult(
        baseline_run=baseline,
        source_capture_sha256=capture.capture_sha256,
        policy_result=policy,
    )


@dataclass(frozen=True)
class CandidateDevelopmentCase:
    """One separately captured development case, not fresh inference."""

    case_id: str
    request: ModelRequest
    capture: ModelCapture
    left: int
    right: int

    def __post_init__(self) -> None:
        if (
            type(self.case_id) is not str
            or re.fullmatch(
                r"[a-z][a-z0-9_-]{0,11}",
                self.case_id,
            ) is None
        ):
            raise ContractError("invalid candidate case_id")


@dataclass(frozen=True)
class CandidateDevelopmentOutcome:
    case_id: str
    baseline_run: CapturedAdditionRun
    candidate_run: CounterfactualAdditionRun

    @property
    def preserves_success(self) -> bool:
        if not self.baseline_run.passed:
            return True

        return (
            self.candidate_run.passed
            and self.baseline_run.selected_tool
            == self.candidate_run.selected_tool
            and self.baseline_run.arguments
            == self.candidate_run.arguments
            and self.baseline_run.output
            == self.candidate_run.output
        )

    @property
    def improves_failure(self) -> bool:
        return (
            not self.baseline_run.passed
            and self.candidate_run.passed
        )


@dataclass(frozen=True)
class CandidateDevelopmentEvaluation:
    """Cross-case development regression, not independent verification."""

    diagnosis_baseline_evidence_sha256: str
    diagnosed_hypothesis_key: str
    intervention: InterventionKind
    outcomes: tuple[CandidateDevelopmentOutcome, ...]

    @property
    def passed(self) -> bool:
        return (
            any(item.improves_failure for item in self.outcomes)
            and any(item.baseline_run.passed for item in self.outcomes)
            and all(
                item.candidate_run.passed and item.preserves_success
                for item in self.outcomes
            )
        )

    @property
    def evidence_sha256(self) -> str:
        return canonical_sha256({
            "record_type": "CandidateDevelopmentEvaluation",
            "schema_version": 1,
            "diagnosis_baseline_evidence_sha256":
                self.diagnosis_baseline_evidence_sha256,
            "diagnosed_hypothesis_key":
                self.diagnosed_hypothesis_key,
            "intervention": self.intervention.value,
            "outcomes": [
                {
                    "case_id": item.case_id,
                    "baseline_sha256":
                        item.baseline_run.execution_evidence_sha256,
                    "candidate_sha256":
                        item.candidate_run.execution_evidence_sha256,
                    "preserves_success": item.preserves_success,
                    "improves_failure": item.improves_failure,
                }
                for item in self.outcomes
            ],
        })

    @property
    def limitations(self) -> tuple[str, ...]:
        return (
            "cases are selected development observations",
            "counterfactual execution does not modify the model",
            "previously captured model outputs are replayed",
            "cross-case regression is not independent scientific verification",
            "a passing gate does not authorize deployment",
        )


def evaluate_diagnosed_candidate_development(
    *,
    diagnosis: ModelActionDiagnosisDevelopmentResult,
    cases: tuple[CandidateDevelopmentCase, ...],
) -> CandidateDevelopmentEvaluation:
    """Evaluate one diagnosed intervention on distinct captured cases.

    Requires at least one previously failing case and one passing
    control. Never re-infers model outputs or modifies source captures.
    The result is a development regression gate only.
    """
    if not isinstance(
        diagnosis, ModelActionDiagnosisDevelopmentResult
    ):
        raise ContractError("invalid candidate diagnosis")

    policy = diagnosis.policy_result

    if (
        policy.policy_status is not DiagnosisStatus.DIAGNOSED
        or diagnosis.baseline_run.passed
        or diagnosis.source_capture_sha256
        != diagnosis.baseline_run.capture_sha256
    ):
        raise ContractError(
            "candidate evaluation requires a failed, diagnosed baseline"
        )

    mapping = {
        "tool_selection_fault": InterventionKind.REPLACE_TOOL,
        "parameter_transformation_fault":
            InterventionKind.OVERRIDE_PARAMETER,
    }

    intervention = mapping.get(policy.diagnosed_hypothesis_key)
    if intervention is None:
        raise ContractError("unsupported diagnosis for candidate evaluation")

    if (
        not policy.observations
        or len(policy.observations) != len(policy.diagnostic_runs)
    ):
        raise ContractError("missing diagnostic execution evidence")

    for observation, run in zip(
        policy.observations,
        policy.diagnostic_runs,
    ):
        if (
            observation.evidence_sha256
            != run.execution_evidence_sha256
        ):
            raise ContractError("diagnostic evidence mismatch")

    if type(cases) is not tuple or not 2 <= len(cases) <= 4:
        raise ContractError("candidate evaluation requires 2-4 cases")

    seen_ids = set()
    seen_requests = set()
    outcomes = []

    for index, case in enumerate(cases):
        if not isinstance(case, CandidateDevelopmentCase):
            raise ContractError("invalid candidate case")

        if case.case_id in seen_ids:
            raise ContractError("duplicate candidate case_id")
        seen_ids.add(case.case_id)

        if (
            case.request.request_sha256 in seen_requests
            or case.request.request_sha256
            == diagnosis.baseline_run.request_sha256
        ):
            raise ContractError(
                "candidate cases must use distinct model requests"
            )
        seen_requests.add(case.request.request_sha256)

        baseline = run_captured_addition_agent(
            request=case.request,
            capture=case.capture,
            run_id=f"a59d-{index}-baseline",
            left=case.left,
            right=case.right,
        )

        candidate = _execute_counterfactual(
            request=case.request,
            capture=case.capture,
            run_id=f"a59d-{index}-candidate",
            left=case.left,
            right=case.right,
            intervention=intervention,
        )

        if (
            baseline.request_sha256
            != candidate.source_request_sha256
            or baseline.capture_sha256
            != candidate.source_capture_sha256
            or baseline.proposal_sha256
            != candidate.source_proposal_sha256
        ):
            raise ContractError("candidate source evidence mismatch")

        outcomes.append(
            CandidateDevelopmentOutcome(
                case_id=case.case_id,
                baseline_run=baseline,
                candidate_run=candidate,
            )
        )

    if not (
        any(item.baseline_run.passed for item in outcomes)
        and any(not item.baseline_run.passed for item in outcomes)
    ):
        raise ContractError(
            "candidate evaluation requires failing and passing controls"
        )

    return CandidateDevelopmentEvaluation(
        diagnosis_baseline_evidence_sha256=(
            diagnosis.baseline_run.execution_evidence_sha256
        ),
        diagnosed_hypothesis_key=policy.diagnosed_hypothesis_key,
        intervention=intervention,
        outcomes=tuple(outcomes),
    )

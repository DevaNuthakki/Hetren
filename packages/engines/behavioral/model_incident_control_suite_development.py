"""Versioned, offline control suite for synthetic incident-agent development.

This is a regression demonstration, not live inference or scientific qualification.
All captures are generated locally; no provider transport is invoked.
"""

from __future__ import annotations

from dataclasses import dataclass
import json

from packages.contracts import ContractError
from packages.core.hetren_diagnosis.contracts import canonical_sha256
from packages.engines.behavioral.incident_scenario_development import IncidentScenario
from packages.engines.behavioral.model_incident_multistep_recovery_development import (
    InjectedToolFailure,
)
from packages.engines.behavioral.model_incident_provider_observability_development import (
    run_observed_resilient_incident,
)
from packages.engines.behavioral.model_incident_development_evaluation import (
    IncidentDevelopmentEvaluationInput,
    IncidentDevelopmentEvaluationReport,
    evaluate_incident_development_cases,
)
from packages.model_capture import capture_json_response


@dataclass(frozen=True)
class SyntheticControlDefinition:
    case_id: str
    behavior: str
    expected_status: str
    expected_correct: bool

    def canonical_payload(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "behavior": self.behavior,
            "expected_status": self.expected_status,
            "expected_correct": self.expected_correct,
        }


CONTROL_SUITE_VERSION = "a5-10h-cc-development-v1"
CONTROL_CASES: tuple[SyntheticControlDefinition, ...] = (
    SyntheticControlDefinition("correct", "correct", "completed", True),
    SyntheticControlDefinition("wrong", "wrong", "completed", False),
    SyntheticControlDefinition("recovery", "recover", "completed", True),
    SyntheticControlDefinition("repeat", "repeat", "rejected", False),
    SyntheticControlDefinition("exhaust", "exhaust", "recovery_exhausted", False),
    SyntheticControlDefinition("budget", "budget", "budget_exhausted", False),
    SyntheticControlDefinition("interrupt", "interrupt", "interrupted", False),
    SyntheticControlDefinition("reject", "reject", "rejected", False),
)


def control_manifest_payload() -> dict[str, object]:
    return {
        "record_type": "SyntheticIncidentControlManifest",
        "schema_version": 1,
        "development_only": True,
        "version": CONTROL_SUITE_VERSION,
        "scenario_id": "evaluation-c",
        "model_label": "offline",
        "cases": [case.canonical_payload() for case in CONTROL_CASES],
    }


def control_manifest_sha256() -> str:
    return canonical_sha256(control_manifest_payload())


def _scenario() -> IncidentScenario:
    return IncidentScenario(
        scenario_id="evaluation-c",
        target_service="payments",
        minimum_severity=3,
        records=(
            ("INC-001", "payments", 3),
            ("INC-002", "payments", 7),
            ("INC-003", "payments", 1),
            ("INC-004", "auth", 9),
        ),
    )


def _run_case(definition: SyntheticControlDefinition) -> IncidentDevelopmentEvaluationInput:
    mode = definition.behavior
    captures_seen = 0

    def source(request):
        nonlocal captures_seen
        captures_seen += 1
        if mode == "interrupt" and captures_seen == 3:
            raise TimeoutError("synthetic capture-source interruption")

        prompt = request.user_prompt
        try:
            encoded_state = (
                prompt.split("STATE_JSON=", 1)[1]
                .split("\nRECOVERY_JSON=", 1)[0]
            )
            state = json.loads(encoded_state)
            phase = state["phase"]
        except (IndexError, ValueError, KeyError, TypeError) as exc:
            raise ContractError("synthetic request-state binding missing") from exc

        if phase == "ready":
            action = {"operation": "load_incidents"}
        elif phase == "loaded":
            action = {"operation": "scope_service", "service": "payments"}
        elif phase == "scoped":
            if mode == "reject":
                action = {"operation": "finalize"}
            else:
                recovery_prompt = "\nRECOVERY_JSON=" in prompt
                use_strict = mode in {"wrong", "recover", "repeat", "exhaust"}
                if mode == "recover" and recovery_prompt:
                    use_strict = False
                action = {
                    "operation": "apply_filter",
                    "filter_tool": (
                        "strict_severity_filter" if use_strict
                        else "inclusive_severity_filter"
                    ),
                    "threshold": 3,
                }
        elif phase == "filtered":
            action = {"operation": "finalize"}
        else:
            raise ContractError("unexpected synthetic workflow phase")

        return capture_json_response(
            request=request,
            raw_response_text=json.dumps(action, sort_keys=True),
        )

    def fault(state, action):
        if (
            mode in {"recover", "repeat", "exhaust"}
            and state.phase == "scoped"
            and action.filter_tool == "strict_severity_filter"
        ):
            return InjectedToolFailure("synthetic_timeout")
        return None

    observed = run_observed_resilient_incident(
        scenario=_scenario(),
        model="offline",
        run_id=f"a510h-cc-{definition.case_id}",
        capture_source=source,
        failure_injector=(
            fault if mode in {"recover", "repeat", "exhaust"} else None
        ),
        max_recoveries=0 if mode == "exhaust" else 1,
        max_attempts=2 if mode == "budget" else 6,
    )

    if any(
        call.origin not in {"offline_capture", "capture_source_exception"}
        or call.total_tokens is not None
        or call.provider_result_sha256 is not None
        for call in observed.calls
    ):
        raise ContractError("control suite must use only offline evidence")

    return IncidentDevelopmentEvaluationInput(
        case_id=definition.case_id,
        scenario=_scenario(),
        model="offline",
        observed=observed,
    )


@dataclass(frozen=True)
class SyntheticControlSuiteResult:
    manifest_sha256: str
    inputs: tuple[IncidentDevelopmentEvaluationInput, ...]
    report: IncidentDevelopmentEvaluationReport

    @property
    def evidence_sha256(self) -> str:
        """Digest of this execution; may vary with measured local timings."""
        return canonical_sha256({
            "record_type": "SyntheticIncidentControlSuiteResult",
            "schema_version": 1,
            "development_only": True,
            "manifest_sha256": self.manifest_sha256,
            "report_sha256": self.report.report_sha256,
        })

    @property
    def limitations(self) -> tuple[str, ...]:
        return (
            "hand-authored offline behavior fixtures, not LLM reasoning",
            "software-oracle correctness, not independent verification",
            "synthetic pre-execution tool faults, not genuine outages",
            "fresh executions may vary in measured capture duration",
            "no provider token counts, monetary cost, or model generalization",
        )


def run_synthetic_control_suite() -> SyntheticControlSuiteResult:
    """Execute the versioned eight-case offline matrix independently of tests."""
    inputs = tuple(_run_case(definition) for definition in CONTROL_CASES)
    report = evaluate_incident_development_cases(
        report_id="a510h-cc-development-v1",
        cases=inputs,
    )

    if len(report.cases) != len(CONTROL_CASES):
        raise ContractError("synthetic control case count mismatch")

    for definition, score in zip(CONTROL_CASES, report.cases):
        if (
            score.case_id != definition.case_id
            or score.status != definition.expected_status
            or score.correct is not definition.expected_correct
        ):
            raise ContractError(
                f"synthetic control expectation violated: {definition.case_id}"
            )

    expected = {
        "denominator_cases": 8,
        "correct_cases": 2,
        "completed_cases": 3,
        "completed_incorrect_cases": 1,
        "rejected_cases": 2,
        "interrupted_cases": 1,
        "recovery_exhausted_cases": 1,
        "budget_exhausted_cases": 1,
        "cases_with_injected_failures": 3,
        "recovered_correctly_cases": 1,
        "attempts": 27,
        "executed_actions": 22,
        "injected_failures": 3,
        "rejected_actions": 2,
        "interrupted_captures": 1,
        "capture_calls": 28,
    }
    for key, count in expected.items():
        if getattr(report.summary, key) != count:
            raise ContractError(f"synthetic aggregate expectation mismatch: {key}")

    if (
        report.summary.calls_with_reported_tokens != 0
        or report.summary.complete_reported_tokens is not None
        or report.summary.known_call_token_sum is not None
    ):
        raise ContractError("offline control suite claimed provider usage")

    return SyntheticControlSuiteResult(
        manifest_sha256=control_manifest_sha256(),
        inputs=inputs,
        report=report,
    )

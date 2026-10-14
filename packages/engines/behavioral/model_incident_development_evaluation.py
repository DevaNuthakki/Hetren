"""Reproducible scoring of validated synthetic incident timelines."""
from __future__ import annotations

from dataclasses import dataclass
import re

from packages.contracts import ContractError
from packages.core.hetren_diagnosis.contracts import canonical_sha256
from packages.engines.behavioral.incident_scenario_development import IncidentScenario
from packages.engines.behavioral.model_incident_provider_observability_development import (
    ObservedResilientIncidentRun,
)
from packages.engines.behavioral.model_incident_timeline_development import (
    reconstruct_incident_timeline,
)

_IDENTIFIER = re.compile(r"[a-z][a-z0-9_-]{0,63}")
_EXECUTED = frozenset({"tool_executed", "workflow_finalized"})
_STATUSES = frozenset({
    "completed", "rejected", "interrupted", "recovery_exhausted",
    "budget_exhausted",
})


def _id(value: str, name: str) -> None:
    if type(value) is not str or _IDENTIFIER.fullmatch(value) is None:
        raise ContractError(f"invalid {name}")


@dataclass(frozen=True)
class IncidentDevelopmentEvaluationInput:
    case_id: str
    scenario: IncidentScenario
    model: str
    observed: ObservedResilientIncidentRun

    def __post_init__(self) -> None:
        _id(self.case_id, "development case_id")
        if not isinstance(self.scenario, IncidentScenario):
            raise ContractError("invalid development scenario")
        if type(self.model) is not str or not self.model.strip():
            raise ContractError("invalid development model")
        if not isinstance(self.observed, ObservedResilientIncidentRun):
            raise ContractError("invalid observed development run")


@dataclass(frozen=True)
class IncidentDevelopmentCaseScore:
    case_id: str
    scenario_sha256: str
    observed_sha256: str
    timeline_sha256: str
    status: str
    completed: bool
    correct: bool
    attempts: int
    executed_actions: int
    injected_failures: int
    rejected_actions: int
    repeated_failed_action_rejections: int
    interrupted_captures: int
    capture_calls: int
    recovered_correctly: bool
    calls_with_reported_tokens: int
    calls_without_reported_tokens: int
    known_call_token_sum: int | None
    complete_reported_tokens: int | None
    local_capture_elapsed_ns: int

    def canonical_payload(self) -> dict[str, object]:
        return {
            "record_type": "IncidentDevelopmentCaseScore",
            "schema_version": 1,
            "development_only": True,
            **{name: getattr(self, name) for name in self.__dataclass_fields__},
        }

    @property
    def case_evidence_sha256(self) -> str:
        return canonical_sha256(self.canonical_payload())


@dataclass(frozen=True)
class IncidentDevelopmentSummary:
    denominator_cases: int
    correct_cases: int
    completed_cases: int
    completed_incorrect_cases: int
    rejected_cases: int
    interrupted_cases: int
    recovery_exhausted_cases: int
    budget_exhausted_cases: int
    cases_with_injected_failures: int
    recovered_correctly_cases: int
    attempts: int
    executed_actions: int
    injected_failures: int
    rejected_actions: int
    repeated_failed_action_rejections: int
    interrupted_captures: int
    capture_calls: int
    calls_with_reported_tokens: int
    calls_without_reported_tokens: int
    known_call_token_sum: int | None
    complete_reported_tokens: int | None
    local_capture_elapsed_ns: int

    def canonical_payload(self) -> dict[str, object]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


@dataclass(frozen=True)
class IncidentDevelopmentEvaluationReport:
    report_id: str
    cases: tuple[IncidentDevelopmentCaseScore, ...]
    summary: IncidentDevelopmentSummary

    def canonical_payload(self) -> dict[str, object]:
        return {
            "record_type": "IncidentDevelopmentEvaluationReport",
            "schema_version": 1,
            "dataset_kind": "synthetic_development",
            "report_id": self.report_id,
            "case_evidence_hashes": [
                item.case_evidence_sha256 for item in self.cases
            ],
            "summary": self.summary.canonical_payload(),
        }

    @property
    def report_sha256(self) -> str:
        return canonical_sha256(self.canonical_payload())

    @property
    def limitations(self) -> tuple[str, ...]:
        return (
            "synthetic captured decisions, not fresh LLM inference",
            "task correctness is a software-oracle verdict",
            "recovery uses injected pre-execution failures",
            "hashes bind local records, not provider authenticity",
            "unreported tokens and monetary cost are unknown",
            "elapsed time is local capture time, not server latency",
            "no independent scientific verification or generalization claim",
        )


def evaluate_incident_development_cases(
    *,
    report_id: str,
    cases: tuple[IncidentDevelopmentEvaluationInput, ...],
) -> IncidentDevelopmentEvaluationReport:
    """Reconstruct each run before computing any synthetic development metric."""
    _id(report_id, "development report_id")
    if type(cases) is not tuple or not 1 <= len(cases) <= 100:
        raise ContractError("development report requires 1-100 immutable cases")

    seen: set[str] = set()
    scores: list[IncidentDevelopmentCaseScore] = []
    for item in cases:
        if not isinstance(item, IncidentDevelopmentEvaluationInput):
            raise ContractError("invalid development evaluation input")
        if item.case_id in seen:
            raise ContractError("duplicate development case_id")
        seen.add(item.case_id)

        timeline = reconstruct_incident_timeline(
            scenario=item.scenario, model=item.model, observed=item.observed,
        )
        if timeline.status not in _STATUSES:
            raise ContractError("unsupported development timeline status")

        run = item.observed.run
        kinds = tuple(event.kind for event in timeline.events)
        executed = sum(kind in _EXECUTED for kind in kinds)
        failures = kinds.count("tool_failed")
        rejected = kinds.count("action_rejected")
        interrupted = kinds.count("capture_interrupted")
        repeated = sum(
            attempt.rejection_reason == "repeated_failed_action"
            for attempt in run.attempts
        )

        if (
            len(timeline.events) != len(item.observed.calls)
            or len(timeline.events) != len(run.attempts) + interrupted
            or executed != len(run.state.steps)
            or failures != sum(
                attempt.injected_failure is not None for attempt in run.attempts
            )
            or rejected != sum(
                attempt.rejection_reason is not None for attempt in run.attempts
            )
            or interrupted != int(run.interruption is not None)
            or repeated > rejected
        ):
            raise ContractError("development metrics conflict with source evidence")

        token_values = tuple(call.total_tokens for call in item.observed.calls)
        known_tokens = tuple(value for value in token_values if value is not None)
        complete = (
            sum(known_tokens) if len(known_tokens) == len(token_values) else None
        )
        if (
            timeline.reported_total_tokens != complete
            or timeline.local_capture_elapsed_ns
            != item.observed.local_capture_elapsed_ns
        ):
            raise ContractError("reported provider usage conflicts with evidence")

        scores.append(IncidentDevelopmentCaseScore(
            case_id=item.case_id,
            scenario_sha256=item.scenario.scenario_sha256,
            observed_sha256=item.observed.execution_evidence_sha256,
            timeline_sha256=timeline.execution_evidence_sha256,
            status=timeline.status,
            completed=timeline.status == "completed",
            correct=timeline.passed,
            attempts=len(run.attempts),
            executed_actions=executed,
            injected_failures=failures,
            rejected_actions=rejected,
            repeated_failed_action_rejections=repeated,
            interrupted_captures=interrupted,
            capture_calls=len(item.observed.calls),
            recovered_correctly=bool(failures and timeline.passed),
            calls_with_reported_tokens=len(known_tokens),
            calls_without_reported_tokens=len(token_values) - len(known_tokens),
            known_call_token_sum=(sum(known_tokens) if known_tokens else None),
            complete_reported_tokens=complete,
            local_capture_elapsed_ns=timeline.local_capture_elapsed_ns,
        ))

    def count(predicate):
        return sum(bool(predicate(item)) for item in scores)

    known_sums = tuple(
        item.known_call_token_sum for item in scores
        if item.known_call_token_sum is not None
    )
    all_complete = all(
        item.complete_reported_tokens is not None for item in scores
    )

    summary = IncidentDevelopmentSummary(
        denominator_cases=len(scores),
        correct_cases=count(lambda x: x.correct),
        completed_cases=count(lambda x: x.completed),
        completed_incorrect_cases=count(lambda x: x.completed and not x.correct),
        rejected_cases=count(lambda x: x.status == "rejected"),
        interrupted_cases=count(lambda x: x.status == "interrupted"),
        recovery_exhausted_cases=count(lambda x: x.status == "recovery_exhausted"),
        budget_exhausted_cases=count(lambda x: x.status == "budget_exhausted"),
        cases_with_injected_failures=count(lambda x: x.injected_failures > 0),
        recovered_correctly_cases=count(lambda x: x.recovered_correctly),
        attempts=sum(x.attempts for x in scores),
        executed_actions=sum(x.executed_actions for x in scores),
        injected_failures=sum(x.injected_failures for x in scores),
        rejected_actions=sum(x.rejected_actions for x in scores),
        repeated_failed_action_rejections=sum(
            x.repeated_failed_action_rejections for x in scores
        ),
        interrupted_captures=sum(x.interrupted_captures for x in scores),
        capture_calls=sum(x.capture_calls for x in scores),
        calls_with_reported_tokens=sum(x.calls_with_reported_tokens for x in scores),
        calls_without_reported_tokens=sum(x.calls_without_reported_tokens for x in scores),
        known_call_token_sum=(sum(known_sums) if known_sums else None),
        complete_reported_tokens=(
            sum(x.complete_reported_tokens for x in scores) if all_complete else None
        ),
        local_capture_elapsed_ns=sum(x.local_capture_elapsed_ns for x in scores),
    )

    if summary.correct_cases > summary.completed_cases:
        raise ContractError("correctness cannot exceed completed cases")
    if (
        summary.completed_cases + summary.rejected_cases
        + summary.interrupted_cases + summary.recovery_exhausted_cases
        + summary.budget_exhausted_cases != summary.denominator_cases
    ):
        raise ContractError("development evaluation denominators inconsistent")

    return IncidentDevelopmentEvaluationReport(
        report_id=report_id, cases=tuple(scores), summary=summary,
    )

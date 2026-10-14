"""Synthetic incident scenarios and independent development oracle.

This module defines new task specifications separately from the
legacy five-record incident fixture.

The reference oracle does not call the incident execution tools,
inspect a proposed tool, or inspect a selected intervention.

All evidence is development evidence, not a protected scientific
holdout, independent scientific verification, or deployment approval.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from environments.agent.incident_triage import TriageReport
from packages.contracts import ContractError
from packages.core.hetren_diagnosis.contracts import canonical_sha256
from packages.model_capture import ModelRequest


MAX_SEVERITY = 10
MAX_RECORDS = 30

ALLOWED_TOOLS = (
    "inclusive_severity_filter",
    "strict_severity_filter",
)

_NAME_PATTERN = re.compile(
    r"[a-z][a-z0-9_-]{0,23}"
)

_ID_PATTERN = re.compile(
    r"INC-[A-Z0-9-]{3,20}"
)


@dataclass(frozen=True)
class IncidentScenario:
    """Validated immutable synthetic investigation task."""

    scenario_id: str
    target_service: str
    minimum_severity: int
    records: tuple[tuple[str, str, int], ...]

    def __post_init__(self) -> None:
        for field in ("scenario_id", "target_service"):
            value = getattr(self, field)

            if (
                type(value) is not str
                or _NAME_PATTERN.fullmatch(value) is None
            ):
                raise ContractError(
                    f"invalid scenario {field}"
                )

        if (
            type(self.minimum_severity) is not int
            or not 0 <= self.minimum_severity <= MAX_SEVERITY
        ):
            raise ContractError(
                "invalid scenario minimum_severity"
            )

        if (
            type(self.records) is not tuple
            or not 2 <= len(self.records) <= MAX_RECORDS
        ):
            raise ContractError(
                "scenario requires 2-30 immutable records"
            )

        seen = set()
        target_present = False

        for row in self.records:
            if type(row) is not tuple or len(row) != 3:
                raise ContractError(
                    "each incident record must be a three-item tuple"
                )

            incident_id, service, severity = row

            if (
                type(incident_id) is not str
                or _ID_PATTERN.fullmatch(incident_id) is None
            ):
                raise ContractError("invalid incident ID")

            if incident_id in seen:
                raise ContractError(
                    "duplicate incident ID"
                )

            seen.add(incident_id)

            if (
                type(service) is not str
                or _NAME_PATTERN.fullmatch(service) is None
            ):
                raise ContractError(
                    "invalid incident service"
                )

            if (
                type(severity) is not int
                or not 0 <= severity <= MAX_SEVERITY
            ):
                raise ContractError(
                    "invalid incident severity"
                )

            if service == self.target_service:
                target_present = True

        if not target_present:
            raise ContractError(
                "scenario has no target-service records"
            )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "record_type": "IncidentScenario",
            "schema_version": 1,
            "scenario_id": self.scenario_id,
            "target_service": self.target_service,
            "minimum_severity": self.minimum_severity,
            "records": [
                list(row) for row in self.records
            ],
        }

    @property
    def scenario_sha256(self) -> str:
        return canonical_sha256(
            self.canonical_payload()
        )


def build_scenario_incident_request(
    *,
    scenario: IncidentScenario,
    model: str,
) -> ModelRequest:
    """Bind a model request to an exact immutable scenario."""
    if not isinstance(scenario, IncidentScenario):
        raise ContractError(
            "scenario must be an IncidentScenario"
        )

    schema = {
        "type": "object",
        "properties": {
            "tool": {
                "type": "string",
                "enum": list(ALLOWED_TOOLS),
            },
            "threshold": {
                "type": "integer",
                "minimum": 0,
                "maximum": MAX_SEVERITY,
            },
        },
        "required": [
            "tool",
            "threshold",
        ],
        "additionalProperties": False,
    }

    incident_lines = "\n".join(
        (
            f"{incident_id}: "
            f"service={service}, "
            f"severity={severity}"
        )
        for incident_id, service, severity
        in scenario.records
    )

    prompt = (
        f"Scenario ID: {scenario.scenario_id}\n"
        f"Scenario SHA256: {scenario.scenario_sha256}\n"
        f"Investigate service={scenario.target_service}.\n"
        "Select all incidents with severity greater than "
        f"or equal to {scenario.minimum_severity}.\n"
        f"Incident records:\n{incident_lines}\n"
        "Choose one severity filter tool and its integer "
        "threshold. Return no incident IDs or tool results."
    )

    return ModelRequest(
        provider="openai",
        model=model,
        system_prompt=(
            "You are a bounded incident-triage tool planner. "
            "Choose an allowlisted filter and integer threshold. "
            "Return only the requested structured action. "
            "Do not invent incident IDs or execution results."
        ),
        user_prompt=prompt,
        response_schema_name=(
            "hetren_incident_scenario_action_v1"
        ),
        response_schema=schema,
        generation_parameters={},
    )


@dataclass(frozen=True)
class IncidentScenarioEvaluation:
    """A report compared with a separately computed reference answer."""

    scenario_sha256: str
    expected_service: str
    expected_ids: tuple[str, ...]
    report: TriageReport

    @property
    def passed(self) -> bool:
        return (
            self.report.service == self.expected_service
            and self.report.incident_ids == self.expected_ids
            and self.report.count == len(self.expected_ids)
        )

    @property
    def evaluation_evidence_sha256(self) -> str:
        return canonical_sha256({
            "record_type": "IncidentScenarioEvaluation",
            "schema_version": 1,
            "development_only": True,
            "scenario_sha256": self.scenario_sha256,
            "expected_service": self.expected_service,
            "expected_ids": list(self.expected_ids),
            "actual_report": self.report.canonical_payload(),
            "report_sha256": self.report.report_sha256,
            "passed": self.passed,
        })

    @property
    def limitations(self) -> tuple[str, ...]:
        return (
            "synthetic development scenario",
            "oracle is separately implemented software",
            "oracle and executor still share task specification",
            "no independent scientific verification",
            "no live-model generalization established",
            "no deployment or repair authorization",
        )


def reference_expected_incident_ids(
    scenario: IncidentScenario,
) -> tuple[str, ...]:
    """Reference oracle, independent of the execution filter tool.

    Uses the written task semantics directly, not selected tool,
    model output, intervention type, or execution implementation.
    """
    if not isinstance(scenario, IncidentScenario):
        raise ContractError(
            "scenario must be an IncidentScenario"
        )

    expected = []

    for incident_id, service, severity in scenario.records:
        if service != scenario.target_service:
            continue

        if severity < scenario.minimum_severity:
            continue

        expected.append(incident_id)

    return tuple(expected)


def evaluate_incident_scenario(
    *,
    scenario: IncidentScenario,
    report: TriageReport,
) -> IncidentScenarioEvaluation:
    """Evaluate actual report content without consulting action choice."""
    if not isinstance(scenario, IncidentScenario):
        raise ContractError(
            "scenario must be an IncidentScenario"
        )

    if not isinstance(report, TriageReport):
        raise ContractError(
            "report must be a TriageReport"
        )

    if (
        type(report.service) is not str
        or type(report.incident_ids) is not tuple
        or type(report.count) is not int
        or report.count < 0
    ):
        raise ContractError(
            "invalid incident report shape"
        )

    if any(
        type(item) is not str
        or _ID_PATTERN.fullmatch(item) is None
        for item in report.incident_ids
    ):
        raise ContractError(
            "invalid reported incident ID"
        )

    if len(set(report.incident_ids)) != len(report.incident_ids):
        raise ContractError(
            "duplicate reported incident ID"
        )

    return IncidentScenarioEvaluation(
        scenario_sha256=scenario.scenario_sha256,
        expected_service=scenario.target_service,
        expected_ids=reference_expected_incident_ids(
            scenario
        ),
        report=report,
    )

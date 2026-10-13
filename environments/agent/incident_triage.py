"""Deterministic multi-step incident-triage agent environment.

Two latent faults intentionally produce the same final report. The environment
is fully local and deterministic; diagnosis and repair policy live elsewhere.
"""

from dataclasses import dataclass
from enum import StrEnum

from packages.core.hetren_diagnosis.contracts import (
    AgentTrace,
    ContractError,
    EventKind,
    InterventionKind,
    TraceEvent,
    canonical_sha256,
)


_TARGET_SERVICE = "payments"
_EXPECTED_THRESHOLD = 3
_EXPECTED_IDS = (
    "INC-1001",
    "INC-1002",
    "INC-1004",
)

_INCIDENTS = (
    ("INC-1001", "payments", 4),
    ("INC-1002", "payments", 3),
    ("INC-1003", "auth", 5),
    ("INC-1004", "payments", 5),
    ("INC-1005", "payments", 2),
)


class IncidentFaultMode(StrEnum):
    FILTER_TOOL_SELECTION = "filter_tool_selection"
    THRESHOLD_TRANSFORMATION = "threshold_transformation"


@dataclass(frozen=True)
class TriageReport:
    service: str
    incident_ids: tuple[str, ...]
    count: int

    def canonical_payload(self) -> dict[str, object]:
        return {
            "service": self.service,
            "incident_ids": list(self.incident_ids),
            "count": self.count,
        }

    @property
    def report_sha256(self) -> str:
        return canonical_sha256(
            self.canonical_payload()
        )


@dataclass(frozen=True)
class IncidentTriageRun:
    run_id: str
    selected_filter_tool: str
    threshold: int
    report: TriageReport
    trace: AgentTrace

    @property
    def passed(self) -> bool:
        return (
            self.report.service
            == _TARGET_SERVICE
            and self.report.incident_ids
            == _EXPECTED_IDS
            and self.report.count
            == len(_EXPECTED_IDS)
        )

    @property
    def execution_evidence_sha256(self) -> str:
        return canonical_sha256(
            {
                "run_id": self.run_id,
                "report": (
                    self.report.canonical_payload()
                ),
                "report_sha256": (
                    self.report.report_sha256
                ),
                "trace_sha256": (
                    self.trace.trace_sha256
                ),
            }
        )


def expected_incident_ids() -> tuple[str, ...]:
    return _EXPECTED_IDS


def _require_inputs(
    fault_mode: IncidentFaultMode,
    run_id: str,
) -> None:
    if not isinstance(
        fault_mode,
        IncidentFaultMode,
    ):
        raise ContractError(
            "fault_mode must be an "
            "IncidentFaultMode"
        )

    if (
        not isinstance(run_id, str)
        or not run_id.strip()
    ):
        raise ContractError(
            "run_id must be non-empty text"
        )


def _baseline_configuration(
    fault_mode: IncidentFaultMode,
) -> tuple[str, int]:
    if (
        fault_mode
        is IncidentFaultMode.FILTER_TOOL_SELECTION
    ):
        return (
            "strict_severity_filter",
            _EXPECTED_THRESHOLD,
        )

    if (
        fault_mode
        is IncidentFaultMode.THRESHOLD_TRANSFORMATION
    ):
        return (
            "inclusive_severity_filter",
            _EXPECTED_THRESHOLD + 1,
        )

    raise ContractError(
        f"unsupported fault mode: {fault_mode}"
    )


def _apply_intervention(
    tool_name: str,
    threshold: int,
    intervention: InterventionKind | None,
) -> tuple[str, int]:
    if intervention is None:
        return tool_name, threshold

    if not isinstance(
        intervention,
        InterventionKind,
    ):
        raise ContractError(
            "intervention must be an "
            "InterventionKind or None"
        )

    if intervention is InterventionKind.REPLAY:
        return tool_name, threshold

    if (
        intervention
        is InterventionKind.REPLACE_TOOL
    ):
        return (
            "inclusive_severity_filter",
            threshold,
        )

    if (
        intervention
        is InterventionKind.OVERRIDE_PARAMETER
    ):
        return (
            tool_name,
            _EXPECTED_THRESHOLD,
        )

    raise ContractError(
        "incident-triage environment does not "
        f"support {intervention.value}"
    )


def _execute_workflow(
    tool_name: str,
    threshold: int,
) -> tuple[
    tuple[tuple[str, str, int], ...],
    tuple[tuple[str, str, int], ...],
    TriageReport,
]:
    service_rows = tuple(
        row
        for row in _INCIDENTS
        if row[1] == _TARGET_SERVICE
    )

    if (
        tool_name
        == "inclusive_severity_filter"
    ):
        selected = tuple(
            row
            for row in service_rows
            if row[2] >= threshold
        )

    elif (
        tool_name
        == "strict_severity_filter"
    ):
        selected = tuple(
            row
            for row in service_rows
            if row[2] > threshold
        )

    else:
        raise ContractError(
            "unknown severity filter tool: "
            f"{tool_name}"
        )

    ids = tuple(
        row[0]
        for row in selected
    )

    report = TriageReport(
        service=_TARGET_SERVICE,
        incident_ids=ids,
        count=len(ids),
    )

    return (
        service_rows,
        selected,
        report,
    )


def _build_trace(
    *,
    run_id: str,
    tool_name: str,
    threshold: int,
    service_rows: tuple[
        tuple[str, str, int],
        ...,
    ],
    selected: tuple[
        tuple[str, str, int],
        ...,
    ],
    report: TriageReport,
) -> AgentTrace:
    all_ids = tuple(
        row[0]
        for row in _INCIDENTS
    )

    service_ids = tuple(
        row[0]
        for row in service_rows
    )

    selected_ids = tuple(
        row[0]
        for row in selected
    )

    states = (
        {
            "phase": "start",
        },
        {
            "phase": "loaded",
            "incident_ids": all_ids,
        },
        {
            "phase": "service-filtered",
            "incident_ids": service_ids,
        },
        {
            "phase":
                "severity-filter-selected",
            "tool": tool_name,
            "threshold": threshold,
        },
        {
            "phase": "severity-filtered",
            "incident_ids": selected_ids,
        },
        {
            "phase": "report-built",
            "report_sha256":
                report.report_sha256,
        },
        {
            "phase": "complete",
            "report_sha256":
                report.report_sha256,
        },
    )

    specs = (
        (
            EventKind.TOOL_CALL,
            "incident-store",
            "load_incidents",
            {
                "dataset":
                    "incident-fixture-v1",
            },
            {
                "incident_ids": all_ids,
            },
            0,
            1,
        ),
        (
            EventKind.TOOL_RESULT,
            "incident-store",
            "load_incidents",
            {
                "dataset":
                    "incident-fixture-v1",
            },
            {
                "incident_ids": all_ids,
            },
            0,
            1,
        ),
        (
            EventKind.TOOL_CALL,
            "service-filter",
            "filter_service",
            {
                "incident_ids": all_ids,
                "service": _TARGET_SERVICE,
            },
            {
                "incident_ids": service_ids,
            },
            1,
            2,
        ),
        (
            EventKind.TOOL_RESULT,
            "service-filter",
            "filter_service",
            {
                "incident_ids": all_ids,
                "service": _TARGET_SERVICE,
            },
            {
                "incident_ids": service_ids,
            },
            1,
            2,
        ),
        (
            EventKind.DECISION,
            "agent",
            "select_severity_filter",
            {
                "minimum_severity":
                    _EXPECTED_THRESHOLD,
                "incident_ids": service_ids,
            },
            {
                "tool": tool_name,
                "threshold": threshold,
            },
            2,
            3,
        ),
        (
            EventKind.TOOL_CALL,
            tool_name,
            "filter_severity",
            {
                "incident_ids": service_ids,
                "threshold": threshold,
            },
            {
                "incident_ids": selected_ids,
            },
            3,
            4,
        ),
        (
            EventKind.TOOL_RESULT,
            tool_name,
            "filter_severity",
            {
                "incident_ids": service_ids,
                "threshold": threshold,
            },
            {
                "incident_ids": selected_ids,
            },
            3,
            4,
        ),
        (
            EventKind.TOOL_CALL,
            "report-builder",
            "build_triage_report",
            {
                "incident_ids": selected_ids,
            },
            report.canonical_payload(),
            4,
            5,
        ),
        (
            EventKind.TOOL_RESULT,
            "report-builder",
            "build_triage_report",
            {
                "incident_ids": selected_ids,
            },
            report.canonical_payload(),
            4,
            5,
        ),
        (
            EventKind.TERMINATION,
            "agent",
            "emit_triage_report",
            report.canonical_payload(),
            report.canonical_payload(),
            5,
            6,
        ),
    )

    events = tuple(
        TraceEvent(
            sequence=sequence,
            kind=kind,
            component=component,
            operation=operation,
            input_sha256=canonical_sha256(
                input_value
            ),
            output_sha256=canonical_sha256(
                output_value
            ),
            state_before_sha256=(
                canonical_sha256(
                    states[before_index]
                )
            ),
            state_after_sha256=(
                canonical_sha256(
                    states[after_index]
                )
            ),
        )
        for sequence, (
            kind,
            component,
            operation,
            input_value,
            output_value,
            before_index,
            after_index,
        ) in enumerate(specs)
    )

    return AgentTrace(
        run_id=run_id,
        events=events,
    )


def run_incident_triage(
    fault_mode: IncidentFaultMode,
    *,
    run_id: str,
    intervention: InterventionKind | None = None,
) -> IncidentTriageRun:
    """Execute one deterministic incident-triage workflow."""
    _require_inputs(
        fault_mode,
        run_id,
    )

    tool_name, threshold = (
        _baseline_configuration(
            fault_mode
        )
    )

    tool_name, threshold = (
        _apply_intervention(
            tool_name,
            threshold,
            intervention,
        )
    )

    (
        service_rows,
        selected,
        report,
    ) = _execute_workflow(
        tool_name,
        threshold,
    )

    trace = _build_trace(
        run_id=run_id,
        tool_name=tool_name,
        threshold=threshold,
        service_rows=service_rows,
        selected=selected,
        report=report,
    )

    return IncidentTriageRun(
        run_id=run_id,
        selected_filter_tool=tool_name,
        threshold=threshold,
        report=report,
        trace=trace,
    )


__all__ = [
    "IncidentFaultMode",
    "IncidentTriageRun",
    "TriageReport",
    "expected_incident_ids",
    "run_incident_triage",
]


def incident_triage_task_spec(
) -> tuple[str, int, tuple[tuple[str, str, int], ...]]:
    """Return the immutable synthetic task specification.

    This development fixture must not be represented as production
    incident data or an independent evaluation dataset.
    """
    return _TARGET_SERVICE, _EXPECTED_THRESHOLD, _INCIDENTS


def run_configured_incident_triage(
    *,
    tool_name: str,
    threshold: int,
    run_id: str,
) -> IncidentTriageRun:
    """Execute a validated tool choice using the existing environment.

    Unlike run_incident_triage(), the caller supplies the selected
    action. This function does not synthesize a fault mode.
    """
    allowed = (
        "inclusive_severity_filter",
        "strict_severity_filter",
    )

    if type(tool_name) is not str or tool_name not in allowed:
        raise ContractError("unsupported configured severity tool")

    max_severity = max(row[2] for row in _INCIDENTS)

    if (
        type(threshold) is not int
        or threshold < 0
        or threshold > max_severity
    ):
        raise ContractError("invalid configured severity threshold")

    if (
        type(run_id) is not str
        or not run_id.strip()
        or len(run_id) > 64
    ):
        raise ContractError("invalid configured run_id")

    service_rows, selected, report = _execute_workflow(
        tool_name,
        threshold,
    )

    trace = _build_trace(
        run_id=run_id,
        tool_name=tool_name,
        threshold=threshold,
        service_rows=service_rows,
        selected=selected,
        report=report,
    )

    return IncidentTriageRun(
        run_id=run_id,
        selected_filter_tool=tool_name,
        threshold=threshold,
        report=report,
        trace=trace,
    )

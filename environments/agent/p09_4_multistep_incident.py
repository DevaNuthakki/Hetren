"""Development-only richer multi-step incident environment for P09.4.

This module increases controlled workflow complexity beyond the historical
incident-triage fixture while keeping execution deterministic and auditable.

It contains a passing canonical control plus five distinct single-fault
development mechanisms corresponding to the P09.4 F1-F5 taxonomy.

This is development infrastructure only. It does not create protected evidence,
perform diagnosis, authorize repair, verify candidates, or establish scientific
support for H1.
"""

from __future__ import annotations

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


_INCIDENTS = (
    (
        "INC-2001",
        "payments-api",
        5,
    ),
    (
        "INC-2002",
        "payments-api",
        3,
    ),
    (
        "INC-2003",
        "ledger-worker",
        5,
    ),
    (
        "INC-2004",
        "payments-api",
        4,
    ),
)

_TARGET_SERVICE = "payments-api"

_CANONICAL_THRESHOLD = 3
_CANONICAL_FILTER_TOOL = "inclusive_severity_filter"
_STRICT_FILTER_TOOL = "strict_severity_filter"

_CURRENT_CONTEXT_VERSION = "incident-policy-v2"
_STALE_CONTEXT_VERSION = "incident-policy-v1"

_CONFIRMED_ENVIRONMENT_STATUS = "confirmed"
_UNKNOWN_ENVIRONMENT_STATUS = "unknown"
_MISSING_ENVIRONMENT_STATUS = "missing"

_EXPECTED_INCIDENT_IDS = (
    "INC-2001",
    "INC-2002",
    "INC-2004",
)

_SHARED_FAULTY_INCIDENT_IDS = (
    "INC-2001",
    "INC-2004",
)


class P094FaultMode(StrEnum):
    """Development-only latent mode for the richer P09.4 environment."""

    NONE = "none"

    TOOL_SELECTION = "tool_selection"
    PARAMETER_TRANSFORMATION = "parameter_transformation"
    SEQUENCING_ORCHESTRATION = "sequencing_orchestration"
    STATE_CONTEXT = "state_context"
    ENVIRONMENT_INTERACTION = "environment_interaction"


@dataclass(frozen=True)
class P094DiagnosticIntervention:
    """Treatment-visible intervention applied to one isolated workflow run."""

    kind: InterventionKind
    target: str

    def __post_init__(
        self,
    ) -> None:
        if not isinstance(
            self.kind,
            InterventionKind,
        ):
            raise ContractError(
                "intervention kind must be an InterventionKind"
            )

        if not isinstance(
            self.target,
            str,
        ) or not self.target:
            raise ContractError(
                "intervention target is required"
            )


@dataclass(frozen=True)
class P094Report:
    """Observable incident report emitted by the richer workflow."""

    service: str
    incident_ids: tuple[str, ...]
    count: int

    def __post_init__(
        self,
    ) -> None:
        if not isinstance(
            self.service,
            str,
        ) or not self.service:
            raise ContractError(
                "report service is required"
            )

        if not isinstance(
            self.incident_ids,
            tuple,
        ):
            raise ContractError(
                "report incident_ids must be a tuple"
            )

        if (
            isinstance(
                self.count,
                bool,
            )
            or not isinstance(
                self.count,
                int,
            )
            or self.count < 0
        ):
            raise ContractError(
                "report count must be a non-negative integer"
            )

        if self.count != len(
            self.incident_ids
        ):
            raise ContractError(
                "report count must equal incident_ids length"
            )

    def canonical_payload(
        self,
    ) -> dict[str, object]:
        return {
            "service": self.service,
            "incident_ids": list(
                self.incident_ids
            ),
            "count": self.count,
        }

    @property
    def report_sha256(
        self,
    ) -> str:
        return canonical_sha256(
            self.canonical_payload()
        )


@dataclass(frozen=True)
class P094IncidentRun:
    """Treatment-visible result of one deterministic development execution."""

    run_id: str
    report: P094Report
    trace: AgentTrace

    def __post_init__(
        self,
    ) -> None:
        if not isinstance(
            self.run_id,
            str,
        ) or not self.run_id:
            raise ContractError(
                "run_id is required"
            )

        if not isinstance(
            self.report,
            P094Report,
        ):
            raise ContractError(
                "report must be a P094Report"
            )

        if not isinstance(
            self.trace,
            AgentTrace,
        ):
            raise ContractError(
                "trace must be an AgentTrace"
            )

        if self.trace.run_id != self.run_id:
            raise ContractError(
                "trace run_id must match run_id"
            )

    @property
    def passed(
        self,
    ) -> bool:
        return (
            self.report.incident_ids
            == _EXPECTED_INCIDENT_IDS
        )

    @property
    def workflow_step_count(
        self,
    ) -> int:
        return len(
            self.trace.events
        )

    @property
    def tool_interaction_count(
        self,
    ) -> int:
        return sum(
            1
            for event in self.trace.events
            if event.kind
            is EventKind.TOOL_CALL
        )

    @property
    def execution_evidence_sha256(
        self,
    ) -> str:
        return canonical_sha256(
            {
                "run_id": self.run_id,
                "report_sha256":
                    self.report.report_sha256,
                "trace_sha256":
                    self.trace.trace_sha256,
                "workflow_step_count":
                    self.workflow_step_count,
                "tool_interaction_count":
                    self.tool_interaction_count,
            }
        )


def expected_incident_ids(
) -> tuple[str, ...]:
    return _EXPECTED_INCIDENT_IDS


def shared_faulty_incident_ids(
) -> tuple[str, ...]:
    return _SHARED_FAULTY_INCIDENT_IDS


def _require_inputs(
    fault_mode: P094FaultMode,
    run_id: str,
) -> None:
    if not isinstance(
        fault_mode,
        P094FaultMode,
    ):
        raise ContractError(
            "fault_mode must be a P094FaultMode"
        )

    if not isinstance(
        run_id,
        str,
    ) or not run_id:
        raise ContractError(
            "run_id is required"
        )


def _require_intervention(
    intervention: P094DiagnosticIntervention | None,
) -> None:
    if intervention is None:
        return

    if not isinstance(
        intervention,
        P094DiagnosticIntervention,
    ):
        raise ContractError(
            "intervention must be a P094DiagnosticIntervention or None"
        )

    allowed = {
        (
            InterventionKind.REPLACE_TOOL,
            "strategy/tool-selection",
        ),
        (
            InterventionKind.OVERRIDE_PARAMETER,
            "strategy/parameter-transformation",
        ),
        (
            InterventionKind.REPLAY,
            "orchestration/prerequisite-order",
        ),
        (
            InterventionKind.REPLAY,
            "context/fresh-state",
        ),
        (
            InterventionKind.REPLAY,
            "environment/response-contract",
        ),
    }

    pair = (
        intervention.kind,
        intervention.target,
    )

    if pair not in allowed:
        raise ContractError(
            "unsupported P09.4 diagnostic intervention"
        )


def _load_incidents(
) -> tuple[
    tuple[
        str,
        str,
        int,
    ],
    ...,
]:
    return _INCIDENTS


def _scope_service(
    incidents: tuple[
        tuple[
            str,
            str,
            int,
        ],
        ...,
    ],
) -> tuple[
    tuple[
        str,
        str,
        int,
    ],
    ...,
]:
    return tuple(
        row
        for row in incidents
        if row[1]
        == _TARGET_SERVICE
    )


def _load_context(
    fault_mode: P094FaultMode,
    *,
    intervention: P094DiagnosticIntervention | None,
) -> dict[str, object]:
    fresh_context_probe = (
        intervention is not None
        and intervention.kind
        is InterventionKind.REPLAY
        and intervention.target
        == "context/fresh-state"
    )

    if (
        fault_mode
        is P094FaultMode.STATE_CONTEXT
        and not fresh_context_probe
    ):
        return {
            "version":
                _STALE_CONTEXT_VERSION,
            "allow_boundary_severity":
                False,
        }

    return {
        "version":
            _CURRENT_CONTEXT_VERSION,
        "allow_boundary_severity":
            True,
    }


def _select_strategy(
    fault_mode: P094FaultMode,
    *,
    intervention: P094DiagnosticIntervention | None,
) -> tuple[str, int]:
    canonical_tool_probe = (
        intervention is not None
        and intervention.kind
        is InterventionKind.REPLACE_TOOL
        and intervention.target
        == "strategy/tool-selection"
    )

    canonical_parameter_probe = (
        intervention is not None
        and intervention.kind
        is InterventionKind.OVERRIDE_PARAMETER
        and intervention.target
        == "strategy/parameter-transformation"
    )

    tool_name = (
        _CANONICAL_FILTER_TOOL
    )

    threshold = (
        _CANONICAL_THRESHOLD
    )

    if (
        fault_mode
        is P094FaultMode.TOOL_SELECTION
        and not canonical_tool_probe
    ):
        tool_name = (
            _STRICT_FILTER_TOOL
        )

    if (
        fault_mode
        is P094FaultMode.PARAMETER_TRANSFORMATION
        and not canonical_parameter_probe
    ):
        threshold = (
            _CANONICAL_THRESHOLD + 1
        )

    return (
        tool_name,
        threshold,
    )


def _filter_incidents(
    service_rows: tuple[
        tuple[
            str,
            str,
            int,
        ],
        ...,
    ],
    *,
    tool_name: str,
    threshold: int,
) -> tuple[
    tuple[
        str,
        str,
        int,
    ],
    ...,
]:
    if (
        tool_name
        == _CANONICAL_FILTER_TOOL
    ):
        return tuple(
            row
            for row in service_rows
            if row[2] >= threshold
        )

    if (
        tool_name
        == _STRICT_FILTER_TOOL
    ):
        return tuple(
            row
            for row in service_rows
            if row[2] > threshold
        )

    raise ContractError(
        "unsupported severity filter tool"
    )


def _enrich_incidents(
    rows: tuple[
        tuple[
            str,
            str,
            int,
        ],
        ...,
    ],
    *,
    fault_mode: P094FaultMode,
    intervention: P094DiagnosticIntervention | None,
) -> tuple[
    tuple[
        str,
        str,
        int,
        str,
    ],
    ...,
]:
    enriched = []

    for (
        incident_id,
        service,
        severity,
    ) in rows:
        environment_status = (
            _CONFIRMED_ENVIRONMENT_STATUS
        )

        canonical_environment_probe = (
            intervention is not None
            and intervention.kind
            is InterventionKind.REPLAY
            and intervention.target
            == "environment/response-contract"
        )

        if (
            fault_mode
            is P094FaultMode.ENVIRONMENT_INTERACTION
            and incident_id
            == "INC-2002"
            and not canonical_environment_probe
        ):
            environment_status = (
                _UNKNOWN_ENVIRONMENT_STATUS
            )

        enriched.append(
            (
                incident_id,
                service,
                severity,
                environment_status,
            )
        )

    return tuple(
        enriched
    )


def _normalize_incidents(
    *,
    filtered_rows: tuple[
        tuple[
            str,
            str,
            int,
        ],
        ...,
    ],
    enriched_rows: tuple[
        tuple[
            str,
            str,
            int,
            str,
        ],
        ...,
    ],
    fault_mode: P094FaultMode,
    intervention: P094DiagnosticIntervention | None,
) -> tuple[
    tuple[
        str,
        str,
        int,
        str,
    ],
    ...,
]:
    canonical_order_probe = (
        intervention is not None
        and intervention.kind
        is InterventionKind.REPLAY
        and intervention.target
        == "orchestration/prerequisite-order"
    )

    if (
        fault_mode
        is P094FaultMode.SEQUENCING_ORCHESTRATION
        and not canonical_order_probe
    ):
        return tuple(
            (
                incident_id,
                service,
                severity,
                _MISSING_ENVIRONMENT_STATUS,
            )
            for (
                incident_id,
                service,
                severity,
            )
            in filtered_rows
        )

    return tuple(
        enriched_rows
    )


def _validate_incidents(
    normalized_rows: tuple[
        tuple[
            str,
            str,
            int,
            str,
        ],
        ...,
    ],
    *,
    context: dict[str, object],
) -> tuple[
    tuple[
        str,
        str,
        int,
        str,
    ],
    ...,
]:
    allow_boundary = context[
        "allow_boundary_severity"
    ]

    if not isinstance(
        allow_boundary,
        bool,
    ):
        raise ContractError(
            "context allow_boundary_severity must be boolean"
        )

    validated = []

    for row in normalized_rows:
        (
            incident_id,
            service,
            severity,
            environment_status,
        ) = row

        if severity == _CANONICAL_THRESHOLD:
            if not allow_boundary:
                continue

            if (
                environment_status
                != _CONFIRMED_ENVIRONMENT_STATUS
            ):
                continue

        validated.append(
            (
                incident_id,
                service,
                severity,
                environment_status,
            )
        )

    return tuple(
        validated
    )


def _build_report(
    validated_rows: tuple[
        tuple[
            str,
            str,
            int,
            str,
        ],
        ...,
    ],
) -> P094Report:
    incident_ids = tuple(
        row[0]
        for row in validated_rows
    )

    return P094Report(
        service=_TARGET_SERVICE,
        incident_ids=incident_ids,
        count=len(
            incident_ids
        ),
    )


def _build_trace(
    *,
    run_id: str,
    incidents: tuple[
        tuple[
            str,
            str,
            int,
        ],
        ...,
    ],
    service_rows: tuple[
        tuple[
            str,
            str,
            int,
        ],
        ...,
    ],
    context: dict[str, object],
    tool_name: str,
    threshold: int,
    filtered_rows: tuple[
        tuple[
            str,
            str,
            int,
        ],
        ...,
    ],
    enriched_rows: tuple[
        tuple[
            str,
            str,
            int,
            str,
        ],
        ...,
    ],
    normalized_rows: tuple[
        tuple[
            str,
            str,
            int,
            str,
        ],
        ...,
    ],
    validated_rows: tuple[
        tuple[
            str,
            str,
            int,
            str,
        ],
        ...,
    ],
    report: P094Report,
    fault_mode: P094FaultMode,
    intervention: P094DiagnosticIntervention | None,
) -> AgentTrace:
    all_ids = tuple(
        row[0]
        for row in incidents
    )

    service_ids = tuple(
        row[0]
        for row in service_rows
    )

    filtered_ids = tuple(
        row[0]
        for row in filtered_rows
    )

    validated_ids = tuple(
        row[0]
        for row in validated_rows
    )

    canonical_order_probe = (
        intervention is not None
        and intervention.kind
        is InterventionKind.REPLAY
        and intervention.target
        == "orchestration/prerequisite-order"
    )

    normalization_source = (
        "filtered-pre-enrichment"
        if (
            fault_mode
            is P094FaultMode.SEQUENCING_ORCHESTRATION
            and not canonical_order_probe
        )
        else "enriched"
    )

    states = (
        {
            "phase": "start",
        },
        {
            "phase": "incidents-loaded",
            "incident_ids": all_ids,
        },
        {
            "phase": "service-scoped",
            "incident_ids": service_ids,
        },
        {
            "phase": "context-loaded",
            "context": context,
        },
        {
            "phase": "strategy-selected",
            "tool": tool_name,
            "threshold": threshold,
        },
        {
            "phase": "incidents-filtered",
            "incident_ids": filtered_ids,
        },
        {
            "phase": "incidents-enriched",
            "rows": enriched_rows,
        },
        {
            "phase": "normalized",
            "source": normalization_source,
            "rows": normalized_rows,
        },
        {
            "phase": "validated",
            "incident_ids": validated_ids,
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
                    "p09-4-incident-fixture-v1",
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
                    "p09-4-incident-fixture-v1",
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
            EventKind.TOOL_CALL,
            "context-store",
            "load_policy_context",
            {
                "service": _TARGET_SERVICE,
            },
            context,
            2,
            3,
        ),
        (
            EventKind.TOOL_RESULT,
            "context-store",
            "load_policy_context",
            {
                "service": _TARGET_SERVICE,
            },
            context,
            2,
            3,
        ),
        (
            EventKind.DECISION,
            "agent",
            "select_filter_strategy",
            {
                "service": _TARGET_SERVICE,
                "minimum_severity":
                    _CANONICAL_THRESHOLD,
            },
            {
                "tool": tool_name,
                "threshold": threshold,
            },
            3,
            4,
        ),
        (
            EventKind.TOOL_CALL,
            "severity-filter",
            "filter_severity",
            {
                "incident_ids": service_ids,
                "threshold": threshold,
            },
            {
                "incident_ids": filtered_ids,
            },
            4,
            5,
        ),
        (
            EventKind.TOOL_RESULT,
            "severity-filter",
            "filter_severity",
            {
                "incident_ids": service_ids,
                "threshold": threshold,
            },
            {
                "incident_ids": filtered_ids,
            },
            4,
            5,
        ),
        (
            EventKind.TOOL_CALL,
            "enrichment-service",
            "enrich_incidents",
            {
                "incident_ids": filtered_ids,
            },
            {
                "rows": enriched_rows,
            },
            5,
            6,
        ),
        (
            EventKind.TOOL_RESULT,
            "enrichment-service",
            "enrich_incidents",
            {
                "incident_ids": filtered_ids,
            },
            {
                "rows": enriched_rows,
            },
            5,
            6,
        ),
        (
            EventKind.STATE_TRANSITION,
            "agent",
            "normalize_evidence",
            {
                "source": normalization_source,
                "rows": (
                    filtered_rows
                    if normalization_source
                    == "filtered-pre-enrichment"
                    else enriched_rows
                ),
            },
            {
                "rows": normalized_rows,
            },
            6,
            7,
        ),
        (
            EventKind.TOOL_CALL,
            "policy-validator",
            "validate_incidents",
            {
                "rows": normalized_rows,
                "context": context,
            },
            {
                "incident_ids": validated_ids,
            },
            7,
            8,
        ),
        (
            EventKind.TOOL_RESULT,
            "policy-validator",
            "validate_incidents",
            {
                "rows": normalized_rows,
                "context": context,
            },
            {
                "incident_ids": validated_ids,
            },
            7,
            8,
        ),
        (
            EventKind.TOOL_CALL,
            "report-builder",
            "build_triage_report",
            {
                "incident_ids": validated_ids,
            },
            report.canonical_payload(),
            8,
            9,
        ),
        (
            EventKind.TOOL_RESULT,
            "report-builder",
            "build_triage_report",
            {
                "incident_ids": validated_ids,
            },
            report.canonical_payload(),
            8,
            9,
        ),
        (
            EventKind.TERMINATION,
            "agent",
            "emit_triage_report",
            report.canonical_payload(),
            report.canonical_payload(),
            9,
            10,
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
                    states[
                        before_index
                    ]
                )
            ),
            state_after_sha256=(
                canonical_sha256(
                    states[
                        after_index
                    ]
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
        ) in enumerate(
            specs
        )
    )

    return AgentTrace(
        run_id=run_id,
        events=events,
    )


def run_p09_4_multistep_incident(
    fault_mode: P094FaultMode,
    *,
    run_id: str,
    intervention: P094DiagnosticIntervention | None = None,
) -> P094IncidentRun:
    """Execute one deterministic development-only P09.4 workflow."""
    _require_inputs(
        fault_mode,
        run_id,
    )

    _require_intervention(
        intervention
    )

    incidents = _load_incidents()

    service_rows = _scope_service(
        incidents
    )

    context = _load_context(
        fault_mode,
        intervention=intervention,
    )

    (
        tool_name,
        threshold,
    ) = _select_strategy(
        fault_mode,
        intervention=intervention,
    )

    filtered_rows = _filter_incidents(
        service_rows,
        tool_name=tool_name,
        threshold=threshold,
    )

    enriched_rows = _enrich_incidents(
        filtered_rows,
        fault_mode=fault_mode,
        intervention=intervention,
    )

    normalized_rows = (
        _normalize_incidents(
            filtered_rows=filtered_rows,
            enriched_rows=enriched_rows,
            fault_mode=fault_mode,
            intervention=intervention,
        )
    )

    validated_rows = (
        _validate_incidents(
            normalized_rows,
            context=context,
        )
    )

    report = _build_report(
        validated_rows
    )

    trace = _build_trace(
        run_id=run_id,
        incidents=incidents,
        service_rows=service_rows,
        context=context,
        tool_name=tool_name,
        threshold=threshold,
        filtered_rows=filtered_rows,
        enriched_rows=enriched_rows,
        normalized_rows=normalized_rows,
        validated_rows=validated_rows,
        report=report,
        fault_mode=fault_mode,
        intervention=intervention,
    )

    return P094IncidentRun(
        run_id=run_id,
        report=report,
        trace=trace,
    )


__all__ = [
    "P094DiagnosticIntervention",
    "P094FaultMode",
    "P094IncidentRun",
    "P094Report",
    "expected_incident_ids",
    "run_p09_4_multistep_incident",
    "shared_faulty_incident_ids",
]

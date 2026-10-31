"""Development-only checkpoint/resume replay for P09.4.

This module is additive.  It preserves the historical full-rerun executor and
does not assign calibrated experiment costs.

A development environment factory may use fixture truth while instantiating
the deterministic environment.  The selected replay executor itself receives
no fault-mode label, out-of-RFS flag, evaluator truth, or prediction table.

Replay checkpoints contain only treatment-visible state that already existed
at the selected causal boundary of the baseline workflow.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from environments.agent import (
    p09_4_multistep_incident as env,
)

from packages.core.hetren_diagnosis.contracts import (
    AgentTrace,
    ContractError,
    DiagnosisProblem,
    EventKind,
    TraceEvent,
    canonical_sha256,
)


IncidentRow = tuple[
    str,
    str,
    int,
]

IncidentRows = tuple[
    IncidentRow,
    ...,
]

EnrichedRow = tuple[
    str,
    str,
    int,
    str,
]

EnrichedRows = tuple[
    EnrichedRow,
    ...,
]

ContextItems = tuple[
    tuple[
        str,
        object,
    ],
    ...,
]


@dataclass(frozen=True)
class P094ReplayCheckpoint:
    """Immutable treatment-visible state at one causal replay boundary."""

    key: str
    baseline_trace_sha256: str

    service_rows: IncidentRows = ()
    context_items: ContextItems = ()
    filtered_rows: IncidentRows = ()
    normalized_rows: EnrichedRows = ()

    def __post_init__(
        self,
    ) -> None:
        if self.key not in {
            "pre-filter",
            "post-filter",
            "pre-validation",
        }:
            raise ContractError(
                "unsupported P09.4 replay checkpoint"
            )

        if not isinstance(
            self.baseline_trace_sha256,
            str,
        ) or not self.baseline_trace_sha256:
            raise ContractError(
                "baseline_trace_sha256 is required"
            )

        if self.key == "pre-filter":
            if not self.service_rows:
                raise ContractError(
                    "pre-filter checkpoint requires service_rows"
                )

            if not self.context_items:
                raise ContractError(
                    "pre-filter checkpoint requires context"
                )

            if (
                self.filtered_rows
                or self.normalized_rows
            ):
                raise ContractError(
                    "pre-filter checkpoint contains future workflow state"
                )

        elif self.key == "post-filter":
            if not self.filtered_rows:
                raise ContractError(
                    "post-filter checkpoint requires filtered_rows"
                )

            if not self.context_items:
                raise ContractError(
                    "post-filter checkpoint requires context"
                )

            if (
                self.service_rows
                or self.normalized_rows
            ):
                raise ContractError(
                    "post-filter checkpoint contains unrelated/future state"
                )

        elif self.key == "pre-validation":
            if not self.normalized_rows:
                raise ContractError(
                    "pre-validation checkpoint requires normalized_rows"
                )

            if (
                self.service_rows
                or self.context_items
                or self.filtered_rows
            ):
                raise ContractError(
                    "pre-validation checkpoint contains unnecessary prior state"
                )

    def context_mapping(
        self,
    ) -> dict[str, object]:
        return dict(
            self.context_items
        )

    def canonical_payload(
        self,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "key":
                self.key,

            "baseline_trace_sha256":
                self.baseline_trace_sha256,
        }

        if self.service_rows:
            payload[
                "service_rows"
            ] = self.service_rows

        if self.context_items:
            payload[
                "context"
            ] = dict(
                self.context_items
            )

        if self.filtered_rows:
            payload[
                "filtered_rows"
            ] = self.filtered_rows

        if self.normalized_rows:
            payload[
                "normalized_rows"
            ] = self.normalized_rows

        return payload

    @property
    def state_sha256(
        self,
    ) -> str:
        return canonical_sha256(
            self.canonical_payload()
        )


ContextLoader = Callable[
    [
        env.P094DiagnosticIntervention,
    ],
    dict[str, object],
]

StrategySelector = Callable[
    [
        env.P094DiagnosticIntervention,
    ],
    tuple[
        str,
        int,
    ],
]

Enricher = Callable[
    [
        IncidentRows,
        env.P094DiagnosticIntervention,
    ],
    EnrichedRows,
]

Normalizer = Callable[
    [
        IncidentRows,
        EnrichedRows,
        env.P094DiagnosticIntervention,
    ],
    EnrichedRows,
]

ReportBuilder = Callable[
    [
        EnrichedRows,
    ],
    env.P094Report,
]


@dataclass(frozen=True)
class P094ReplayBaseline:
    """Baseline run plus immutable replay checkpoints and environment bindings."""

    run: env.P094IncidentRun
    checkpoints: tuple[
        P094ReplayCheckpoint,
        ...,
    ]

    _context_loader: ContextLoader = field(
        repr=False,
        compare=False,
    )

    _strategy_selector: StrategySelector = field(
        repr=False,
        compare=False,
    )

    _enricher: Enricher = field(
        repr=False,
        compare=False,
    )

    _normalizer: Normalizer = field(
        repr=False,
        compare=False,
    )

    _report_builder: ReportBuilder = field(
        repr=False,
        compare=False,
    )

    def __post_init__(
        self,
    ) -> None:
        if not isinstance(
            self.run,
            env.P094IncidentRun,
        ):
            raise ContractError(
                "run must be a P094IncidentRun"
            )

        keys = tuple(
            checkpoint.key
            for checkpoint
            in self.checkpoints
        )

        if keys != (
            "pre-filter",
            "post-filter",
            "pre-validation",
        ):
            raise ContractError(
                "replay baseline requires exact checkpoint ordering"
            )

        for checkpoint in self.checkpoints:
            if (
                checkpoint.baseline_trace_sha256
                != self.run.trace.trace_sha256
            ):
                raise ContractError(
                    "checkpoint baseline trace binding mismatch"
                )

    def checkpoint(
        self,
        key: str,
    ) -> P094ReplayCheckpoint:
        checkpoint = next(
            (
                item
                for item
                in self.checkpoints
                if item.key
                == key
            ),
            None,
        )

        if checkpoint is None:
            raise ContractError(
                "unknown replay checkpoint"
            )

        return checkpoint


@dataclass(frozen=True)
class P094ReplayRun:
    """Observable result of one selected checkpoint/resume replay."""

    run_id: str

    baseline_trace_sha256: str
    experiment_key: str
    experiment_sha256: str

    checkpoint_key: str
    checkpoint_state_sha256: str

    report: env.P094Report
    trace: AgentTrace

    def __post_init__(
        self,
    ) -> None:
        for (
            value,
            name,
        ) in (
            (
                self.run_id,
                "run_id",
            ),
            (
                self.baseline_trace_sha256,
                "baseline_trace_sha256",
            ),
            (
                self.experiment_key,
                "experiment_key",
            ),
            (
                self.experiment_sha256,
                "experiment_sha256",
            ),
            (
                self.checkpoint_key,
                "checkpoint_key",
            ),
            (
                self.checkpoint_state_sha256,
                "checkpoint_state_sha256",
            ),
        ):
            if not isinstance(
                value,
                str,
            ) or not value:
                raise ContractError(
                    f"{name} is required"
                )

        if not isinstance(
            self.report,
            env.P094Report,
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

        if (
            self.trace.run_id
            != self.run_id
        ):
            raise ContractError(
                "replay trace run_id mismatch"
            )

    @property
    def passed(
        self,
    ) -> bool:
        return (
            self.report.incident_ids
            == env.expected_incident_ids()
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
            event.kind
            is EventKind.TOOL_CALL
            for event
            in self.trace.events
        )

    @property
    def replay_operations(
        self,
    ) -> tuple[str, ...]:
        return tuple(
            event.operation
            for event
            in self.trace.events
            if event.kind
            is EventKind.TOOL_CALL
        )

    @property
    def execution_evidence_sha256(
        self,
    ) -> str:
        return canonical_sha256(
            {
                "run_id":
                    self.run_id,

                "baseline_trace_sha256":
                    self.baseline_trace_sha256,

                "experiment_key":
                    self.experiment_key,

                "experiment_sha256":
                    self.experiment_sha256,

                "checkpoint_key":
                    self.checkpoint_key,

                "checkpoint_state_sha256":
                    self.checkpoint_state_sha256,

                "report":
                    self.report.canonical_payload(),

                "trace_sha256":
                    self.trace.trace_sha256,

                "replay_operations":
                    self.replay_operations,
            }
        )


@dataclass(frozen=True)
class _ReplayStep:
    kind: EventKind
    component: str
    operation: str
    input_value: object
    output_value: object
    state_after: dict[str, object]
    paired: bool = False

    def __post_init__(
        self,
    ) -> None:
        if self.paired:
            if (
                self.kind
                is not EventKind.TOOL_CALL
            ):
                raise ContractError(
                    "paired replay step must use TOOL_CALL"
                )

        elif self.kind not in {
            EventKind.DECISION,
            EventKind.STATE_TRANSITION,
        }:
            raise ContractError(
                "unpaired replay step must be decision or state transition"
            )


_CHECKPOINT_BY_PROBE = {
    "p1-canonical-tool":
        "pre-filter",

    "p2-canonical-parameter":
        "pre-filter",

    "p3-canonical-prerequisite-order":
        "post-filter",

    "p4-fresh-context":
        "pre-validation",

    "p5-environment-contract":
        "post-filter",
}


def _canonical_report_builder(
    rows: EnrichedRows,
) -> env.P094Report:
    return env._build_report(
        rows,
        drop_boundary_incident=False,
    )


def _control_report_builder(
    rows: EnrichedRows,
) -> env.P094Report:
    return env._build_report(
        rows,
        drop_boundary_incident=True,
    )


def _capture_replay_baseline(
    fault_mode: env.P094FaultMode,
    *,
    run_id: str,
    report_builder: ReportBuilder,
) -> P094ReplayBaseline:
    env._require_inputs(
        fault_mode,
        run_id,
    )

    incidents = env._load_incidents()

    service_rows = env._scope_service(
        incidents
    )

    context = env._load_context(
        fault_mode,
        intervention=None,
    )

    (
        tool_name,
        threshold,
    ) = env._select_strategy(
        fault_mode,
        intervention=None,
    )

    filtered_rows = env._filter_incidents(
        service_rows,
        tool_name=tool_name,
        threshold=threshold,
    )

    enriched_rows = env._enrich_incidents(
        filtered_rows,
        fault_mode=fault_mode,
        intervention=None,
    )

    normalized_rows = (
        env._normalize_incidents(
            filtered_rows=filtered_rows,
            enriched_rows=enriched_rows,
            fault_mode=fault_mode,
            intervention=None,
        )
    )

    validated_rows = env._validate_incidents(
        normalized_rows,
        context=context,
    )

    report = report_builder(
        validated_rows
    )

    trace = env._build_trace(
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
        intervention=None,
    )

    run = env.P094IncidentRun(
        run_id=run_id,
        report=report,
        trace=trace,
    )

    trace_sha256 = (
        run.trace.trace_sha256
    )

    checkpoints = (
        P094ReplayCheckpoint(
            key="pre-filter",
            baseline_trace_sha256=trace_sha256,
            service_rows=service_rows,
            context_items=tuple(
                sorted(
                    context.items()
                )
            ),
        ),

        P094ReplayCheckpoint(
            key="post-filter",
            baseline_trace_sha256=trace_sha256,
            context_items=tuple(
                sorted(
                    context.items()
                )
            ),
            filtered_rows=filtered_rows,
        ),

        P094ReplayCheckpoint(
            key="pre-validation",
            baseline_trace_sha256=trace_sha256,
            normalized_rows=normalized_rows,
        ),
    )

    def context_loader(
        intervention: env.P094DiagnosticIntervention,
    ) -> dict[str, object]:
        return env._load_context(
            fault_mode,
            intervention=intervention,
        )

    def strategy_selector(
        intervention: env.P094DiagnosticIntervention,
    ) -> tuple[str, int]:
        return env._select_strategy(
            fault_mode,
            intervention=intervention,
        )

    def enricher(
        rows: IncidentRows,
        intervention: env.P094DiagnosticIntervention,
    ) -> EnrichedRows:
        return env._enrich_incidents(
            rows,
            fault_mode=fault_mode,
            intervention=intervention,
        )

    def normalizer(
        filtered: IncidentRows,
        enriched: EnrichedRows,
        intervention: env.P094DiagnosticIntervention,
    ) -> EnrichedRows:
        return env._normalize_incidents(
            filtered_rows=filtered,
            enriched_rows=enriched,
            fault_mode=fault_mode,
            intervention=intervention,
        )

    return P094ReplayBaseline(
        run=run,
        checkpoints=checkpoints,
        _context_loader=context_loader,
        _strategy_selector=strategy_selector,
        _enricher=enricher,
        _normalizer=normalizer,
        _report_builder=report_builder,
    )


def capture_p09_4_replay_baseline(
    fault_mode: env.P094FaultMode,
    *,
    run_id: str,
) -> P094ReplayBaseline:
    """Execute and retain an ordinary deterministic baseline plus checkpoints."""
    return _capture_replay_baseline(
        fault_mode,
        run_id=run_id,
        report_builder=(
            _canonical_report_builder
        ),
    )


def capture_p09_4_out_of_rfs_replay_baseline(
    *,
    run_id: str,
) -> P094ReplayBaseline:
    """Instantiate the existing report-assembly control environment."""
    return _capture_replay_baseline(
        env.P094FaultMode.NONE,
        run_id=run_id,
        report_builder=(
            _control_report_builder
        ),
    )


def _tool_step(
    *,
    component: str,
    operation: str,
    input_value: object,
    output_value: object,
    state_after: dict[str, object],
) -> _ReplayStep:
    return _ReplayStep(
        kind=EventKind.TOOL_CALL,
        component=component,
        operation=operation,
        input_value=input_value,
        output_value=output_value,
        state_after=state_after,
        paired=True,
    )


def _single_step(
    *,
    kind: EventKind,
    component: str,
    operation: str,
    input_value: object,
    output_value: object,
    state_after: dict[str, object],
) -> _ReplayStep:
    return _ReplayStep(
        kind=kind,
        component=component,
        operation=operation,
        input_value=input_value,
        output_value=output_value,
        state_after=state_after,
        paired=False,
    )


def _build_replay_trace(
    *,
    run_id: str,
    checkpoint: P094ReplayCheckpoint,
    steps: tuple[
        _ReplayStep,
        ...,
    ],
    report: env.P094Report,
) -> AgentTrace:
    current_state: dict[str, object] = {
        "phase":
            "checkpoint-resume",

        "checkpoint_key":
            checkpoint.key,

        "checkpoint_state_sha256":
            checkpoint.state_sha256,

        "baseline_trace_sha256":
            checkpoint.baseline_trace_sha256,
    }

    events: list[
        TraceEvent
    ] = []

    sequence = 0

    for step in steps:
        before_sha256 = (
            canonical_sha256(
                current_state
            )
        )

        after_sha256 = (
            canonical_sha256(
                step.state_after
            )
        )

        if step.paired:
            for kind in (
                EventKind.TOOL_CALL,
                EventKind.TOOL_RESULT,
            ):
                events.append(
                    TraceEvent(
                        sequence=sequence,
                        kind=kind,
                        component=step.component,
                        operation=step.operation,
                        input_sha256=(
                            canonical_sha256(
                                step.input_value
                            )
                        ),
                        output_sha256=(
                            canonical_sha256(
                                step.output_value
                            )
                        ),
                        state_before_sha256=(
                            before_sha256
                        ),
                        state_after_sha256=(
                            after_sha256
                        ),
                    )
                )

                sequence += 1

        else:
            events.append(
                TraceEvent(
                    sequence=sequence,
                    kind=step.kind,
                    component=step.component,
                    operation=step.operation,
                    input_sha256=(
                        canonical_sha256(
                            step.input_value
                        )
                    ),
                    output_sha256=(
                        canonical_sha256(
                            step.output_value
                        )
                    ),
                    state_before_sha256=(
                        before_sha256
                    ),
                    state_after_sha256=(
                        after_sha256
                    ),
                )
            )

            sequence += 1

        current_state = (
            step.state_after
        )

    complete_state = {
        "phase":
            "complete",

        "report_sha256":
            report.report_sha256,
    }

    events.append(
        TraceEvent(
            sequence=sequence,
            kind=EventKind.TERMINATION,
            component="agent",
            operation="emit_triage_report",
            input_sha256=(
                canonical_sha256(
                    report.canonical_payload()
                )
            ),
            output_sha256=(
                canonical_sha256(
                    report.canonical_payload()
                )
            ),
            state_before_sha256=(
                canonical_sha256(
                    current_state
                )
            ),
            state_after_sha256=(
                canonical_sha256(
                    complete_state
                )
            ),
        )
    )

    return AgentTrace(
        run_id=run_id,
        events=tuple(
            events
        ),
    )


def _require_sequence(
    sequence: int,
) -> None:
    if (
        isinstance(
            sequence,
            bool,
        )
        or not isinstance(
            sequence,
            int,
        )
        or sequence < 0
    ):
        raise ContractError(
            "sequence must be a non-negative integer"
        )


def execute_checkpoint_replay(
    *,
    baseline: P094ReplayBaseline,
    problem: DiagnosisProblem,
    experiment_key: str,
    sequence: int,
) -> P094ReplayRun:
    """Execute one selection-neutral checkpoint/resume diagnostic replay."""
    if not isinstance(
        baseline,
        P094ReplayBaseline,
    ):
        raise ContractError(
            "baseline must be a P094ReplayBaseline"
        )

    if not isinstance(
        problem,
        DiagnosisProblem,
    ):
        raise ContractError(
            "problem must be a DiagnosisProblem"
        )

    if not isinstance(
        experiment_key,
        str,
    ) or not experiment_key:
        raise ContractError(
            "experiment_key is required"
        )

    _require_sequence(
        sequence
    )

    if (
        problem.trace.trace_sha256
        != baseline.run.trace.trace_sha256
    ):
        raise ContractError(
            "diagnosis problem does not bind the replay baseline"
        )

    experiment = next(
        (
            item
            for item in problem.experiments
            if item.key
            == experiment_key
        ),
        None,
    )

    if experiment is None:
        raise ContractError(
            "unknown replay experiment key"
        )

    checkpoint_key = (
        _CHECKPOINT_BY_PROBE.get(
            experiment.key
        )
    )

    if checkpoint_key is None:
        raise ContractError(
            "experiment has no registered replay boundary"
        )

    checkpoint = baseline.checkpoint(
        checkpoint_key
    )

    intervention = (
        env.P094DiagnosticIntervention(
            kind=experiment.intervention_kind,
            target=experiment.intervention_target,
        )
    )

    steps: list[
        _ReplayStep
    ] = []

    if experiment.key in {
        "p1-canonical-tool",
        "p2-canonical-parameter",
    }:
        context = (
            checkpoint.context_mapping()
        )

        (
            tool_name,
            threshold,
        ) = baseline._strategy_selector(
            intervention
        )

        steps.append(
            _single_step(
                kind=EventKind.DECISION,
                component="agent",
                operation="select_filter_strategy",
                input_value={
                    "minimum_severity":
                        3,

                    "service":
                        baseline.run.report.service,
                },
                output_value={
                    "tool":
                        tool_name,

                    "threshold":
                        threshold,
                },
                state_after={
                    "phase":
                        "strategy-selected",

                    "tool":
                        tool_name,

                    "threshold":
                        threshold,
                },
            )
        )

        filtered_rows = (
            env._filter_incidents(
                checkpoint.service_rows,
                tool_name=tool_name,
                threshold=threshold,
            )
        )

        steps.append(
            _tool_step(
                component="severity-filter",
                operation="filter_severity",
                input_value={
                    "incident_ids":
                        tuple(
                            row[
                                0
                            ]
                            for row
                            in checkpoint.service_rows
                        ),

                    "threshold":
                        threshold,
                },
                output_value={
                    "incident_ids":
                        tuple(
                            row[
                                0
                            ]
                            for row
                            in filtered_rows
                        ),
                },
                state_after={
                    "phase":
                        "incidents-filtered",

                    "incident_ids":
                        tuple(
                            row[
                                0
                            ]
                            for row
                            in filtered_rows
                        ),
                },
            )
        )

    elif experiment.key in {
        "p3-canonical-prerequisite-order",
        "p5-environment-contract",
    }:
        context = (
            checkpoint.context_mapping()
        )

        filtered_rows = (
            checkpoint.filtered_rows
        )

    elif experiment.key == "p4-fresh-context":
        context = (
            baseline._context_loader(
                intervention
            )
        )

        steps.append(
            _tool_step(
                component="context-store",
                operation="load_policy_context",
                input_value={
                    "service":
                        baseline.run.report.service,
                },
                output_value=context,
                state_after={
                    "phase":
                        "context-refreshed",

                    "context":
                        context,
                },
            )
        )

        normalized_rows = (
            checkpoint.normalized_rows
        )

    else:
        raise ContractError(
            "unsupported replay experiment"
        )

    if experiment.key != "p4-fresh-context":
        enriched_rows = (
            baseline._enricher(
                filtered_rows,
                intervention,
            )
        )

        steps.append(
            _tool_step(
                component="enrichment-service",
                operation="enrich_incidents",
                input_value={
                    "incident_ids":
                        tuple(
                            row[
                                0
                            ]
                            for row
                            in filtered_rows
                        ),
                },
                output_value={
                    "rows":
                        enriched_rows,
                },
                state_after={
                    "phase":
                        "incidents-enriched",

                    "rows":
                        enriched_rows,
                },
            )
        )

        normalized_rows = (
            baseline._normalizer(
                filtered_rows,
                enriched_rows,
                intervention,
            )
        )

        steps.append(
            _single_step(
                kind=(
                    EventKind.STATE_TRANSITION
                ),
                component="agent",
                operation="normalize_evidence",
                input_value={
                    "filtered_rows":
                        filtered_rows,

                    "enriched_rows":
                        enriched_rows,
                },
                output_value={
                    "rows":
                        normalized_rows,
                },
                state_after={
                    "phase":
                        "normalized",

                    "rows":
                        normalized_rows,
                },
            )
        )

    validated_rows = (
        env._validate_incidents(
            normalized_rows,
            context=context,
        )
    )

    validated_ids = tuple(
        row[
            0
        ]
        for row
        in validated_rows
    )

    steps.append(
        _tool_step(
            component="policy-validator",
            operation="validate_incidents",
            input_value={
                "rows":
                    normalized_rows,

                "context":
                    context,
            },
            output_value={
                "incident_ids":
                    validated_ids,
            },
            state_after={
                "phase":
                    "validated",

                "incident_ids":
                    validated_ids,
            },
        )
    )

    report = baseline._report_builder(
        validated_rows
    )

    steps.append(
        _tool_step(
            component="report-builder",
            operation="build_triage_report",
            input_value={
                "incident_ids":
                    validated_ids,
            },
            output_value=(
                report.canonical_payload()
            ),
            state_after={
                "phase":
                    "report-built",

                "report_sha256":
                    report.report_sha256,
            },
        )
    )

    run_id = (
        f"{baseline.run.run_id}:checkpoint-replay:"
        f"{sequence}:{experiment.key}"
    )

    trace = _build_replay_trace(
        run_id=run_id,
        checkpoint=checkpoint,
        steps=tuple(
            steps
        ),
        report=report,
    )

    return P094ReplayRun(
        run_id=run_id,
        baseline_trace_sha256=(
            baseline.run.trace.trace_sha256
        ),
        experiment_key=(
            experiment.key
        ),
        experiment_sha256=(
            experiment.experiment_sha256
        ),
        checkpoint_key=(
            checkpoint.key
        ),
        checkpoint_state_sha256=(
            checkpoint.state_sha256
        ),
        report=report,
        trace=trace,
    )


__all__ = [
    "P094ReplayBaseline",
    "P094ReplayCheckpoint",
    "P094ReplayRun",
    "capture_p09_4_out_of_rfs_replay_baseline",
    "capture_p09_4_replay_baseline",
    "execute_checkpoint_replay",
]

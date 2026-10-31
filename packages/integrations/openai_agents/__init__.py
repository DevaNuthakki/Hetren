"""Reusable OpenAI Agents SDK integration for Hetren (no workflow logic)."""

from .evidence import (
    Discrepancy,
    DiscrepancyKind,
    ExecutionScope,
    SENSITIVE_DATA_CAPTURE,
    SdkEvidence,
    build_execution_record,
    build_run_trace,
    reconcile,
    run_manifest,
)
from .hooks import (
    EvidenceHooks,
    HookEvent,
    HookKind,
)
from .provenance import (
    RunProvenance,
    RunRecord,
    RunStatus,
    model_identity,
    model_provenance,
)
from .replay import (
    CAPTURE_FILE_NAME,
    Capture,
    CaptureConflictError,
    CaptureStore,
    RecordingModel,
    RecordingModelProvider,
    ReplayKey,
    ReplayMissError,
    ReplayModel,
    ReplayModelProvider,
    ReplayVersionError,
    installed_versions,
    replay_key,
)
from .runner import (
    DEFAULT_LIMITATIONS,
    WORKFLOW_NAME,
    run_agent,
)
from .tools import (
    gateway_function_tools,
    result_text_from_records,
    tool_result_text,
)
from .tracing import (
    LocalTraceProcessor,
    SpanRecord,
    install_local_tracing,
)


__all__ = [
    "CAPTURE_FILE_NAME",
    "Capture",
    "CaptureConflictError",
    "CaptureStore",
    "DEFAULT_LIMITATIONS",
    "RecordingModel",
    "RecordingModelProvider",
    "ReplayKey",
    "ReplayMissError",
    "ReplayModel",
    "ReplayModelProvider",
    "ReplayVersionError",
    "installed_versions",
    "replay_key",
    "Discrepancy",
    "DiscrepancyKind",
    "EvidenceHooks",
    "ExecutionScope",
    "HookEvent",
    "HookKind",
    "LocalTraceProcessor",
    "RunProvenance",
    "RunRecord",
    "RunStatus",
    "SENSITIVE_DATA_CAPTURE",
    "SdkEvidence",
    "SpanRecord",
    "WORKFLOW_NAME",
    "build_execution_record",
    "build_run_trace",
    "gateway_function_tools",
    "install_local_tracing",
    "model_identity",
    "model_provenance",
    "reconcile",
    "result_text_from_records",
    "run_agent",
    "run_manifest",
    "tool_result_text",
]

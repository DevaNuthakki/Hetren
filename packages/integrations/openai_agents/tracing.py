"""Local, in-process collection of OpenAI Agents SDK spans.

``install_local_tracing`` calls ``set_trace_processors([processor])``, which
replaces the SDK's default ``BatchTraceProcessor`` (and its backend
exporter), so no span or trace leaves the process.

Sensitive-data capture
----------------------
Runs use ``RunConfig(trace_include_sensitive_data=False)``. With that
setting the SDK leaves model inputs/outputs and tool arguments/results out
of its spans. This is deliberate: gateway stage records are the authority
for actions, arguments, observations, and state, so spans only need to
contribute structure (task / agent / turn / function nesting), errors, and
timing. Keeping content out of spans also means there is one copy of each
observation to scan and reason about. ``SpanRecord.content_captured``
reports whether a span carried content anyway, so a configuration change
cannot go unnoticed.

Span IDs and wall-clock timestamps vary between identical runs. Records
replace span IDs with start-order ordinals and keep timestamps out of every
canonical payload.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Any

from agents import TracingProcessor, set_trace_processors

from packages.contracts import (
    ContractError,
    canonical_sha256,
)


_STRUCTURAL_CUSTOM_KEYS = ("sdk_span_type", "turn", "agent_name")
_CONTENT_KEYS = ("input", "output", "response", "messages")


@dataclass(frozen=True)
class SpanRecord:
    ordinal: int
    parent_ordinal: int | None
    span_type: str
    name: str | None
    details: dict[str, object]
    content_captured: bool
    error_present: bool
    error_sha256: str | None
    started_at: str | None = None
    ended_at: str | None = None

    def canonical_payload(self) -> dict[str, object]:
        """Structure only; timestamps are excluded."""
        return {
            "ordinal": self.ordinal,
            "parent_ordinal": self.parent_ordinal,
            "span_type": self.span_type,
            "name": self.name,
            "details": self.details,
            "content_captured": self.content_captured,
            "error_present": self.error_present,
            "error_sha256": self.error_sha256,
        }

    def timing_payload(self) -> dict[str, object]:
        return {
            "ordinal": self.ordinal,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
        }


def _span_details(span_data: dict[str, Any]) -> dict[str, object]:
    span_type = span_data.get("type")

    if span_type == "custom":
        data = span_data.get("data") or {}
        return {key: data[key] for key in _STRUCTURAL_CUSTOM_KEYS if key in data}

    if span_type == "agent":
        return {"tools": sorted(span_data.get("tools") or [])}

    return {}


class SpanCollector:
    """Spans of one trace, in start order."""

    def __init__(self) -> None:
        self._ordinals: dict[str, int] = {}
        self._exports: dict[int, dict[str, Any]] = {}

    def start(self, span_id: str) -> None:
        self._ordinals.setdefault(span_id, len(self._ordinals))

    def end(self, exported: dict[str, Any]) -> None:
        span_id = exported["id"]
        self.start(span_id)
        self._exports[self._ordinals[span_id]] = exported

    def records(self) -> tuple[SpanRecord, ...]:
        records: list[SpanRecord] = []

        for ordinal in sorted(self._exports):
            exported = self._exports[ordinal]
            span_data = exported.get("span_data") or {}
            parent = exported.get("parent_id")
            error = exported.get("error")

            records.append(
                SpanRecord(
                    ordinal=ordinal,
                    parent_ordinal=None if parent is None else self._ordinals.get(parent),
                    span_type=str(span_data.get("type")),
                    name=span_data.get("name"),
                    details=_span_details(span_data),
                    content_captured=any(
                        span_data.get(key) is not None for key in _CONTENT_KEYS
                    ),
                    error_present=error is not None,
                    error_sha256=None if error is None else canonical_sha256(error),
                    started_at=exported.get("started_at"),
                    ended_at=exported.get("ended_at"),
                )
            )

        return tuple(records)


class LocalTraceProcessor(TracingProcessor):
    """Routes spans to per-run collectors by trace ID; exports nothing."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._collectors: dict[str, SpanCollector] = {}
        self.unrouted_spans = 0

    def begin(self, trace_id: str) -> SpanCollector:
        with self._lock:
            if trace_id in self._collectors:
                raise ContractError("trace is already being collected")

            collector = SpanCollector()
            self._collectors[trace_id] = collector
            return collector

    def finish(self, trace_id: str) -> SpanCollector:
        with self._lock:
            return self._collectors.pop(trace_id)

    def _collector(self, trace_id: str) -> SpanCollector | None:
        with self._lock:
            collector = self._collectors.get(trace_id)

            if collector is None:
                self.unrouted_spans += 1

            return collector

    def on_trace_start(self, trace: Any) -> None:
        return None

    def on_trace_end(self, trace: Any) -> None:
        return None

    def on_span_start(self, span: Any) -> None:
        collector = self._collector(span.trace_id)

        if collector is not None:
            collector.start(span.span_id)

    def on_span_end(self, span: Any) -> None:
        collector = self._collector(span.trace_id)

        if collector is not None:
            collector.end(span.export())

    def shutdown(self) -> None:
        return None

    def force_flush(self) -> None:
        return None


_PROCESSOR = LocalTraceProcessor()


def install_local_tracing() -> LocalTraceProcessor:
    """Make the local processor the SDK's only trace processor."""
    set_trace_processors([_PROCESSOR])
    return _PROCESSOR


__all__ = [
    "LocalTraceProcessor",
    "SpanCollector",
    "SpanRecord",
    "install_local_tracing",
]

"""Stage records for gated tool invocations.

Every gated call records, in order:

- PROPOSED: the requested tool and arguments;
- AUTHORIZED: the policy decision (``allowed`` or ``denied``);
- ATTEMPTED: execution started (only when allowed);
- OBSERVED: the observation or recorded failure (only when attempted).

Each record carries the environment state hash before and after its stage.
Ordering uses a gateway-wide ``sequence`` that is contiguous from zero.
``recorded_at`` is optional wall-clock metadata and is excluded from every
canonical payload and hash, so replayed runs hash identically.

The records describe what the gateway saw. They do not establish that a
tool's observation is true, that a policy decision was correct, or that a
run succeeded.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json
import re

from packages.contracts import (
    ContractError,
    canonical_sha256,
)
from packages.core.hetren_diagnosis.contracts import (
    AgentTrace,
    EventKind,
    TraceEvent,
)


_SHA256 = re.compile(r"[0-9a-f]{64}")
_INVOCATION_ID = re.compile(r"call-[0-9]{4,}")
_TOOL_NAME = re.compile(r"[a-z][a-z0-9_]{0,63}")


class ToolStage(StrEnum):
    PROPOSED = "proposed"
    AUTHORIZED = "authorized"
    ATTEMPTED = "attempted"
    OBSERVED = "observed"


class StageStatus(StrEnum):
    PROPOSED = "proposed"
    ALLOWED = "allowed"
    DENIED = "denied"
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


_ALLOWED_STATUSES = {
    ToolStage.PROPOSED: (StageStatus.PROPOSED,),
    ToolStage.AUTHORIZED: (StageStatus.ALLOWED, StageStatus.DENIED),
    ToolStage.ATTEMPTED: (StageStatus.STARTED,),
    ToolStage.OBSERVED: (StageStatus.SUCCEEDED, StageStatus.FAILED),
}

_EVENT_KINDS = {
    ToolStage.PROPOSED: EventKind.DECISION,
    ToolStage.AUTHORIZED: EventKind.DECISION,
    ToolStage.ATTEMPTED: EventKind.TOOL_CALL,
    ToolStage.OBSERVED: EventKind.TOOL_RESULT,
}


def json_object(
    value: object,
    name: str,
) -> dict[str, object]:
    """Return a detached, strictly JSON-compatible copy of an object."""
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ContractError(
            f"{name} must be JSON-compatible"
        ) from exc

    decoded = json.loads(encoded)

    if not isinstance(decoded, dict):
        raise ContractError(
            f"{name} must be a JSON object"
        )

    return decoded


def _require_sha256(value: object, name: str) -> None:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ContractError(
            f"{name} must be a lowercase SHA-256 digest"
        )


@dataclass(frozen=True)
class ToolStageRecord:
    sequence: int
    invocation_id: str
    tool_name: str
    stage: ToolStage
    status: StageStatus
    arguments_sha256: str
    payload: dict[str, object]
    state_before_sha256: str
    state_after_sha256: str
    recorded_at: str | None = None

    def __post_init__(self) -> None:
        if (
            isinstance(self.sequence, bool)
            or not isinstance(self.sequence, int)
            or self.sequence < 0
        ):
            raise ContractError(
                "sequence must be a non-negative integer"
            )

        if (
            not isinstance(self.invocation_id, str)
            or _INVOCATION_ID.fullmatch(self.invocation_id) is None
        ):
            raise ContractError(
                "invocation_id has an invalid format"
            )

        if (
            not isinstance(self.tool_name, str)
            or _TOOL_NAME.fullmatch(self.tool_name) is None
        ):
            raise ContractError(
                "tool_name has an invalid format"
            )

        if not isinstance(self.stage, ToolStage):
            raise ContractError("stage must be a ToolStage")

        if (
            not isinstance(self.status, StageStatus)
            or self.status not in _ALLOWED_STATUSES[self.stage]
        ):
            raise ContractError(
                "status is not valid for this stage"
            )

        for name in (
            "arguments_sha256",
            "state_before_sha256",
            "state_after_sha256",
        ):
            _require_sha256(getattr(self, name), name)

        if (
            self.stage is not ToolStage.OBSERVED
            and self.state_before_sha256 != self.state_after_sha256
        ):
            raise ContractError(
                "only an observed stage may change state"
            )

        if (
            self.recorded_at is not None
            and (
                not isinstance(self.recorded_at, str)
                or not self.recorded_at.strip()
            )
        ):
            raise ContractError(
                "recorded_at must be non-empty text when present"
            )

        object.__setattr__(
            self,
            "payload",
            json_object(self.payload, "payload"),
        )

    @property
    def payload_sha256(self) -> str:
        return canonical_sha256(self.payload)

    def canonical_payload(self) -> dict[str, object]:
        """Hashable content; ``recorded_at`` is deliberately excluded."""
        return {
            "record_type": "ToolStageRecord",
            "schema_version": 1,
            "sequence": self.sequence,
            "invocation_id": self.invocation_id,
            "tool_name": self.tool_name,
            "stage": self.stage.value,
            "status": self.status.value,
            "arguments_sha256": self.arguments_sha256,
            "payload": self.payload,
            "payload_sha256": self.payload_sha256,
            "state_before_sha256": self.state_before_sha256,
            "state_after_sha256": self.state_after_sha256,
        }

    @property
    def record_sha256(self) -> str:
        return canonical_sha256(self.canonical_payload())

    def to_trace_event(self) -> TraceEvent:
        return TraceEvent(
            sequence=self.sequence,
            kind=_EVENT_KINDS[self.stage],
            component=self.tool_name,
            operation=f"{self.stage.value}:{self.status.value}",
            input_sha256=self.arguments_sha256,
            output_sha256=self.payload_sha256,
            state_before_sha256=self.state_before_sha256,
            state_after_sha256=self.state_after_sha256,
        )


def stage_records_sha256(
    records: tuple[ToolStageRecord, ...],
) -> str:
    return canonical_sha256(
        [record.canonical_payload() for record in records]
    )


def to_agent_trace(
    run_id: str,
    records: tuple[ToolStageRecord, ...],
) -> AgentTrace:
    """Project stage records into Hetren's existing AgentTrace."""
    if not isinstance(records, tuple):
        raise ContractError("records must be a tuple")

    return AgentTrace(
        run_id=run_id,
        events=tuple(record.to_trace_event() for record in records),
    )


__all__ = [
    "StageStatus",
    "ToolStage",
    "ToolStageRecord",
    "json_object",
    "stage_records_sha256",
    "to_agent_trace",
]

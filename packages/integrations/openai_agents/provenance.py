"""Run provenance and run records for OpenAI Agents SDK runs.

Every run record states how the model output was produced:

- LIVE: a real provider call;
- REPLAY: a previously captured response replayed offline;
- SCRIPTED: a deterministic fake model.

Provenance is declared by the caller and checked against the model object
(``hetren_provenance`` attribute), so a scripted or replayed run cannot be
recorded as live, or the reverse.

Run records are what Hetren reads. The agent's own decisions are kept in a
separate ``agent_output`` section so leakage scans can apply the right rules
to each part.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re

from packages.action_gateway import (
    ToolStageRecord,
    stage_records_sha256,
)
from packages.contracts import (
    ContractError,
    canonical_sha256,
)


NEUTRAL_RUN_ID = re.compile(r"run-[0-9]{4}")


class RunProvenance(StrEnum):
    LIVE = "live"
    REPLAY = "replay"
    SCRIPTED = "scripted"


class RunStatus(StrEnum):
    COMPLETED = "completed"
    MAX_TURNS_EXCEEDED = "max_turns_exceeded"
    ERROR = "error"


def model_provenance(model: object) -> RunProvenance:
    """Provenance implied by a model object; plain model names are live."""
    if isinstance(model, str):
        return RunProvenance.LIVE

    declared = getattr(model, "hetren_provenance", None)

    if not isinstance(declared, RunProvenance):
        raise ContractError(
            "model object must declare hetren_provenance"
        )

    return declared


def model_identity(model: object) -> str:
    if isinstance(model, str):
        return model

    identity = getattr(model, "hetren_model_id", None)

    if not isinstance(identity, str) or not identity.strip():
        raise ContractError("model object must declare hetren_model_id")

    return identity


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    provenance: RunProvenance
    model_id: str
    agent_name: str
    instructions_sha256: str
    task_input: str
    tool_definitions: tuple[dict[str, object], ...]
    stage_records: tuple[ToolStageRecord, ...]
    status: RunStatus
    error: dict[str, str] | None
    final_message: str | None
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.run_id, str)
            or NEUTRAL_RUN_ID.fullmatch(self.run_id) is None
        ):
            raise ContractError("run_id must be a neutral run-NNNN identifier")

        if not isinstance(self.provenance, RunProvenance):
            raise ContractError("provenance must be a RunProvenance")

        if not isinstance(self.status, RunStatus):
            raise ContractError("status must be a RunStatus")

        for name in ("model_id", "agent_name", "task_input"):
            value = getattr(self, name)

            if not isinstance(value, str) or not value.strip():
                raise ContractError(f"{name} must be non-empty text")

        if not isinstance(self.stage_records, tuple) or not all(
            isinstance(record, ToolStageRecord) for record in self.stage_records
        ):
            raise ContractError("stage_records must be a tuple of ToolStageRecord")

        if (self.status is RunStatus.ERROR) != (self.error is not None):
            raise ContractError("error is required exactly when status is error")

        if not isinstance(self.limitations, tuple) or not self.limitations:
            raise ContractError("limitations must be a non-empty tuple")

    @property
    def tool_definitions_sha256(self) -> str:
        return canonical_sha256(list(self.tool_definitions))

    @property
    def stage_records_sha256(self) -> str:
        return stage_records_sha256(self.stage_records)

    def evidence_payload(self) -> dict[str, object]:
        """Everything except the agent's own final message."""
        return {
            "record_type": "AgentRunRecord",
            "schema_version": 1,
            "run_id": self.run_id,
            "provenance": self.provenance.value,
            "model_id": self.model_id,
            "agent_name": self.agent_name,
            "instructions_sha256": self.instructions_sha256,
            "task_input": self.task_input,
            "tool_definitions": list(self.tool_definitions),
            "tool_definitions_sha256": self.tool_definitions_sha256,
            "stage_records": [
                record.canonical_payload() for record in self.stage_records
            ],
            "stage_records_sha256": self.stage_records_sha256,
            "status": self.status.value,
            "error": self.error,
            "limitations": list(self.limitations),
        }

    def agent_output_payload(self) -> dict[str, object]:
        return {"final_message": self.final_message}

    def canonical_payload(self) -> dict[str, object]:
        return {
            **self.evidence_payload(),
            "agent_output": self.agent_output_payload(),
        }

    @property
    def record_sha256(self) -> str:
        return canonical_sha256(self.canonical_payload())


__all__ = [
    "NEUTRAL_RUN_ID",
    "RunProvenance",
    "RunRecord",
    "RunStatus",
    "model_identity",
    "model_provenance",
]

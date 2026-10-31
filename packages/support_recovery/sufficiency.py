"""Evidence sufficiency for the support routing workflow.

``assess_evidence`` decides, from the diagnosis input alone, whether
diagnosis is possible. The diagnosis input is a run record's
``evidence_payload()``: JSON, never live objects.

The result is SUFFICIENT or INSUFFICIENT. INSUFFICIENT names every missing
item as a structured requirement code; it is not INCONCLUSIVE (which would
mean the evidence was complete but ambiguous), and it never leads to a
correction claim.

Requirements:

- the input is an agent run record;
- stage records are contiguous from sequence 0;
- every allowed invocation has attempted and observed stages;
- every tool the SDK reports as finished has gateway records;
- the SDK evidence agrees with the gateway records (no discrepancies);
- a succeeded ticket observation exists;
- a succeeded account observation exists for the account the ticket
  resolved to.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from packages.contracts import canonical_sha256


TICKET_TOOL = "read_ticket"
ACCOUNT_TOOL = "lookup_account"


class EvidenceStatus(StrEnum):
    SUFFICIENT = "sufficient"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True)
class Invocation:
    invocation_id: str
    tool_name: str
    arguments: dict[str, Any]
    stages: dict[str, dict[str, Any]]

    @property
    def allowed(self) -> bool:
        return self.stages.get("authorized", {}).get("status") == "allowed"

    @property
    def observation(self) -> dict[str, Any] | None:
        observed = self.stages.get("observed")

        if observed is None or observed.get("status") != "succeeded":
            return None

        return observed["payload"].get("observation")


def invocations(diagnosis_input: Mapping[str, Any]) -> list[Invocation]:
    grouped: dict[str, Invocation] = {}

    for record in diagnosis_input.get("stage_records") or []:
        invocation_id = record["invocation_id"]

        if invocation_id not in grouped:
            grouped[invocation_id] = Invocation(
                invocation_id=invocation_id,
                tool_name=record["tool_name"],
                arguments={},
                stages={},
            )

        invocation = grouped[invocation_id]
        invocation.stages[record["stage"]] = record

        if record["stage"] == "proposed":
            invocation.arguments.update(record["payload"].get("arguments") or {})

    return list(grouped.values())


def succeeded(diagnosis_input: Mapping[str, Any], tool_name: str) -> list[Invocation]:
    return [
        invocation
        for invocation in invocations(diagnosis_input)
        if invocation.tool_name == tool_name and invocation.observation is not None
    ]


@dataclass(frozen=True)
class EvidenceAssessment:
    status: EvidenceStatus
    missing: tuple[dict[str, object], ...]
    input_sha256: str

    @property
    def sufficient(self) -> bool:
        return self.status is EvidenceStatus.SUFFICIENT

    def canonical_payload(self) -> dict[str, object]:
        return {
            "record_type": "EvidenceAssessment",
            "schema_version": 1,
            "status": self.status.value,
            "missing": list(self.missing),
            "input_sha256": self.input_sha256,
        }


def assess_evidence(diagnosis_input: Mapping[str, Any]) -> EvidenceAssessment:
    missing: list[dict[str, object]] = []

    if diagnosis_input.get("record_type") != "AgentRunRecord":
        missing.append({"requirement": "agent_run_record"})

    records = diagnosis_input.get("stage_records") or []

    for expected, record in enumerate(records):
        if record["sequence"] != expected:
            missing.append(
                {"requirement": "contiguous_stage_records", "expected_sequence": expected}
            )
            break

    found = invocations(diagnosis_input)

    for invocation in found:
        if not invocation.allowed:
            continue

        for stage in ("attempted", "observed"):
            if stage not in invocation.stages:
                missing.append(
                    {
                        "requirement": f"{stage}_stage",
                        "invocation_id": invocation.invocation_id,
                        "tool_name": invocation.tool_name,
                    }
                )

    hook_events = (diagnosis_input.get("sdk_evidence") or {}).get("hook_events") or []
    finished = [
        event["fields"]["tool_name"] for event in hook_events if event["kind"] == "tool_end"
    ]
    # Every bridged tool call (allowed or not) creates one gateway invocation.
    for position, tool_name in enumerate(finished):
        if position >= len(found) or found[position].tool_name != tool_name:
            missing.append(
                {
                    "requirement": "gateway_records_for_finished_tool",
                    "position": position,
                    "tool_name": tool_name,
                }
            )

    for discrepancy in (diagnosis_input.get("sdk_evidence") or {}).get("discrepancies") or []:
        missing.append(
            {"requirement": "consistent_sdk_evidence", "discrepancy": discrepancy["kind"]}
        )

    tickets = succeeded(diagnosis_input, TICKET_TOOL)
    accounts = succeeded(diagnosis_input, ACCOUNT_TOOL)

    if not tickets:
        missing.append({"requirement": "ticket_observation", "tool_name": TICKET_TOOL})

    for ticket in tickets:
        resolved = ticket.observation.get("account_id")

        if not any(account.arguments.get("account_id") == resolved for account in accounts):
            missing.append(
                {
                    "requirement": "account_observation",
                    "tool_name": ACCOUNT_TOOL,
                    "for_invocation_id": ticket.invocation_id,
                }
            )

    return EvidenceAssessment(
        status=EvidenceStatus.INSUFFICIENT if missing else EvidenceStatus.SUFFICIENT,
        missing=tuple(missing),
        input_sha256=canonical_sha256(dict(diagnosis_input)),
    )


__all__ = [
    "ACCOUNT_TOOL",
    "EvidenceAssessment",
    "EvidenceStatus",
    "Invocation",
    "TICKET_TOOL",
    "assess_evidence",
    "invocations",
    "succeeded",
]

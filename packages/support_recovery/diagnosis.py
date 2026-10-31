"""Rule-based diagnosis for the support routing workflow (Milestone 1).

Deterministic and evidence-only: the input is a run record's
``evidence_payload()``. A learned diagnoser replaces these rules later.

Rule: a ticket observation reports the ``account_id`` its customer
reference resolves to, and the account observation for that account reports
the account's own ``customer_ref``. If the two references differ, the
identifier mapping is inconsistent, and both references are implicated.

Outcomes:

- INSUFFICIENT_EVIDENCE when ``assess_evidence`` finds missing items;
- MAPPING_INCONSISTENCY with findings and implicated references;
- HEALTHY otherwise, with nothing proposed.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from packages.contracts import canonical_sha256
from packages.support_recovery.sufficiency import (
    ACCOUNT_TOOL,
    TICKET_TOOL,
    EvidenceAssessment,
    assess_evidence,
    invocations,
)


class DiagnosisOutcome(StrEnum):
    HEALTHY = "healthy"
    MAPPING_INCONSISTENCY = "mapping_inconsistency"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


@dataclass(frozen=True)
class MappingFinding:
    ticket_invocation_id: str
    account_invocation_id: str
    ticket_id: str
    ticket_customer_ref: str
    resolved_account_id: str
    account_customer_ref: str

    def canonical_payload(self) -> dict[str, object]:
        return {
            "ticket_invocation_id": self.ticket_invocation_id,
            "account_invocation_id": self.account_invocation_id,
            "ticket_id": self.ticket_id,
            "ticket_customer_ref": self.ticket_customer_ref,
            "resolved_account_id": self.resolved_account_id,
            "account_customer_ref": self.account_customer_ref,
        }


@dataclass(frozen=True)
class Diagnosis:
    run_id: str | None
    outcome: DiagnosisOutcome
    assessment: EvidenceAssessment
    findings: tuple[MappingFinding, ...]
    implicated_customer_refs: tuple[str, ...]

    def canonical_payload(self) -> dict[str, object]:
        return {
            "record_type": "SupportDiagnosis",
            "schema_version": 1,
            "run_id": self.run_id,
            "outcome": self.outcome.value,
            "assessment": self.assessment.canonical_payload(),
            "findings": [finding.canonical_payload() for finding in self.findings],
            "implicated_customer_refs": list(self.implicated_customer_refs),
        }

    @property
    def diagnosis_sha256(self) -> str:
        return canonical_sha256(self.canonical_payload())


def diagnose(diagnosis_input: Mapping[str, Any]) -> Diagnosis:
    assessment = assess_evidence(diagnosis_input)
    run_id = diagnosis_input.get("run_id")

    if not assessment.sufficient:
        return Diagnosis(run_id, DiagnosisOutcome.INSUFFICIENT_EVIDENCE, assessment, (), ())

    found = invocations(diagnosis_input)
    findings: list[MappingFinding] = []

    for index, ticket in enumerate(found):
        if ticket.tool_name != TICKET_TOOL or ticket.observation is None:
            continue

        resolved = ticket.observation["account_id"]
        account = next(
            (
                later for later in found[index + 1:]
                if later.tool_name == ACCOUNT_TOOL
                and later.observation is not None
                and later.arguments.get("account_id") == resolved
            ),
            None,
        )

        if account is None:
            continue

        if account.observation["customer_ref"] != ticket.observation["customer_ref"]:
            findings.append(
                MappingFinding(
                    ticket_invocation_id=ticket.invocation_id,
                    account_invocation_id=account.invocation_id,
                    ticket_id=ticket.observation["ticket_id"],
                    ticket_customer_ref=ticket.observation["customer_ref"],
                    resolved_account_id=resolved,
                    account_customer_ref=account.observation["customer_ref"],
                )
            )

    if not findings:
        return Diagnosis(run_id, DiagnosisOutcome.HEALTHY, assessment, (), ())

    implicated = sorted(
        {finding.ticket_customer_ref for finding in findings}
        | {finding.account_customer_ref for finding in findings}
    )

    return Diagnosis(
        run_id,
        DiagnosisOutcome.MAPPING_INCONSISTENCY,
        assessment,
        tuple(findings),
        tuple(implicated),
    )


__all__ = [
    "Diagnosis",
    "DiagnosisOutcome",
    "MappingFinding",
    "diagnose",
]

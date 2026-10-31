"""Evaluator-only catalog for the Milestone 1 support examples.

This module is the answer key: fault identifiers, fault definitions, expected
routing and accounts, regression expectations, and verdict types. Only
``packages/verification/support_verification.py`` may import it. The agent,
environment tools, integrations, gateway, and Hetren's diagnosis and recovery
code must never see it, directly or transitively.

Field names here are deliberately distinctive (``expected_*``, ``fault_id``,
``evaluator_verdict``) so the leakage scan can flag them on any surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from environments.support.fixtures import CLEAN_CHECKS
from packages.contracts import ContractError
from packages.support_evaluator.cases import CASE_KINDS


class SupportVerdict(StrEnum):
    NO_INTERVENTION_CORRECT = "no_intervention_correct"
    RECOVERY_VERIFIED = "recovery_verified"
    RECOVERY_REJECTED = "recovery_rejected"
    INSUFFICIENT_EVIDENCE_CORRECT = "insufficient_evidence_correct"
    INCORRECT_OUTCOME = "incorrect_outcome"


class EvidenceCondition(StrEnum):
    COMPLETE = "complete_evidence"
    ACCOUNT_OBSERVATION_WITHHELD = "account_observation_withheld"


@dataclass(frozen=True)
class FaultDefinition:
    fault_id: str
    fault_type: str
    parameters: dict[str, str]

    def fault_payload(self) -> dict[str, object]:
        """The environment-side payload the harness injects and reports."""
        return {"fault_type": self.fault_type, **self.parameters}


@dataclass(frozen=True)
class ExampleSpec:
    example_name: str
    fault_id: str | None
    evidence_condition: EvidenceCondition
    target_ticket_id: str
    expected_account_id: str
    expected_queue_id: str
    regression_expectations: dict[str, str]
    expected_verdict: SupportVerdict


FAULTS: dict[str, FaultDefinition] = {
    "SUP-F-001": FaultDefinition(
        fault_id="SUP-F-001",
        fault_type="identifier_mapping_swap",
        parameters={"customer_ref_a": "C-3103", "customer_ref_b": "C-3104"},
    ),
}

EXAMPLES: dict[str, ExampleSpec] = {
    "example_correct_run": ExampleSpec(
        example_name="example_correct_run",
        fault_id=None,
        evidence_condition=EvidenceCondition.COMPLETE,
        target_ticket_id="T-1003",
        expected_account_id="A-2003",
        expected_queue_id="Q-PRIORITY",
        regression_expectations={},
        expected_verdict=SupportVerdict.NO_INTERVENTION_CORRECT,
    ),
    "example_verified_recovery": ExampleSpec(
        example_name="example_verified_recovery",
        fault_id="SUP-F-001",
        evidence_condition=EvidenceCondition.COMPLETE,
        target_ticket_id="T-1003",
        expected_account_id="A-2003",
        expected_queue_id="Q-PRIORITY",
        regression_expectations={"T-1002": "Q-GENERAL"},
        expected_verdict=SupportVerdict.RECOVERY_VERIFIED,
    ),
    "example_insufficient_evidence": ExampleSpec(
        example_name="example_insufficient_evidence",
        fault_id="SUP-F-001",
        evidence_condition=EvidenceCondition.ACCOUNT_OBSERVATION_WITHHELD,
        target_ticket_id="T-1003",
        expected_account_id="A-2003",
        expected_queue_id="Q-PRIORITY",
        regression_expectations={},
        expected_verdict=SupportVerdict.INSUFFICIENT_EVIDENCE_CORRECT,
    ),
}

# Field names that exist only in evaluator records.
EVALUATOR_FIELD_NAMES = frozenset(
    {
        "fault_id",
        "fault_type",
        "fault_payload",
        "example_name",
        "evidence_condition",
        "expected_account_id",
        "expected_queue_id",
        "regression_expectations",
        "expected_verdict",
        "evaluator_verdict",
        "case_kind",
        "case_variant",
        "family_id",
        "remedy_if_wrong",
        "remedy_if_wrong_arguments",
        "world_changes",
        "regression_ticket_ids",
    }
)


def example(example_name: str) -> ExampleSpec:
    try:
        return EXAMPLES[example_name]
    except KeyError:
        raise ContractError("unknown example_name") from None


def fault(fault_id: str) -> FaultDefinition:
    try:
        return FAULTS[fault_id]
    except KeyError:
        raise ContractError("unknown fault_id") from None


def answer_pairs() -> frozenset[tuple[str, str]]:
    """(ticket, expected value) pairs that would reveal an answer together."""
    pairs: set[tuple[str, str]] = set()

    for spec in EXAMPLES.values():
        pairs.add((spec.target_ticket_id, spec.expected_queue_id))
        pairs.add((spec.target_ticket_id, spec.expected_account_id))
        pairs.update(spec.regression_expectations.items())

    return frozenset(pairs)


def sensitive_tokens() -> frozenset[str]:
    """Strings that must never appear on an agent- or Hetren-visible surface.

    Includes the world clean-check names: each one names what is wrong with
    a faulty world, so on a Hetren-visible surface it would be an answer.
    """
    tokens: set[str] = set(EVALUATOR_FIELD_NAMES)
    tokens.update(EXAMPLES)
    tokens.update(FAULTS)
    tokens.update(definition.fault_type for definition in FAULTS.values())
    tokens.update(verdict.value for verdict in SupportVerdict)
    tokens.update(condition.value for condition in EvidenceCondition)
    tokens.update(CLEAN_CHECKS)
    tokens.update(CASE_KINDS)
    return frozenset(tokens)


__all__ = [
    "EVALUATOR_FIELD_NAMES",
    "EXAMPLES",
    "EvidenceCondition",
    "ExampleSpec",
    "FAULTS",
    "FaultDefinition",
    "SupportVerdict",
    "answer_pairs",
    "example",
    "fault",
    "sensitive_tokens",
]

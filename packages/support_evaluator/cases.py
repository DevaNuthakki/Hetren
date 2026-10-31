"""Evaluator-side truth for generated Milestone 2 cases.

A ``CaseTruth`` records facts about one injected world: which family or
look-alike it is, which ticket the agent handles, the correct final queue and
account under the authoritative routing policy and source records, the exact
world changes, the remedy to apply if a run's outcome is wrong
(``remedy_if_wrong``), and tickets that should be unaffected.

Labels are per run: a run whose outcome already matches the expected queue
and account is labelled ``no_intervention`` whatever the world contains.
``remedy_if_wrong`` applies only otherwise, and labels come from execution.
Like the rest of the evaluator, it is never visible to Hetren.
"""

from __future__ import annotations

from dataclasses import dataclass

from packages.contracts import (
    ContractError,
    canonical_sha256,
)


FAMILIES = {
    "mapping_swap": "F1",
    "stale_account_record": "F2",
    "mishandled_tool_error": "F3",
    "misleading_ticket_text": "F4",
    "missing_account": "F5",
    "queue_misconfiguration": "F6",
    "tier_format_drift": "F7",
}

LOOKALIKES = (
    "merged_account",
    "recent_tier_change",
    "transient_error_retried",
)

CASE_KINDS = tuple(FAMILIES) + LOOKALIKES

HELD_OUT_KINDS = ("queue_misconfiguration", "tier_format_drift")

REMEDIES = (
    "set_mapping",
    "restore_from_source",
    "rerun",
    "reroute",
    "abstain",
    "no_intervention",
)


@dataclass(frozen=True)
class CaseTruth:
    case_kind: str
    case_variant: str
    target_ticket_id: str
    expected_queue_id: str
    expected_account_id: str | None
    remedy_if_wrong: str
    remedy_if_wrong_arguments: tuple[dict[str, str], ...]
    world_changes: tuple[dict[str, object], ...]
    regression_ticket_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.case_kind not in CASE_KINDS:
            raise ContractError("unknown case_kind")

        if self.remedy_if_wrong not in REMEDIES:
            raise ContractError("unknown remedy_if_wrong")

        if self.target_ticket_id in self.regression_ticket_ids:
            raise ContractError("the target ticket cannot be a regression ticket")

    @property
    def family_id(self) -> str | None:
        return FAMILIES.get(self.case_kind)

    @property
    def is_lookalike(self) -> bool:
        return self.case_kind in LOOKALIKES

    @property
    def held_out(self) -> bool:
        return self.case_kind in HELD_OUT_KINDS

    def canonical_payload(self) -> dict[str, object]:
        return {
            "record_type": "SupportCaseTruth",
            "schema_version": 1,
            "case_kind": self.case_kind,
            "case_variant": self.case_variant,
            "family_id": self.family_id,
            "target_ticket_id": self.target_ticket_id,
            "expected_queue_id": self.expected_queue_id,
            "expected_account_id": self.expected_account_id,
            "remedy_if_wrong": self.remedy_if_wrong,
            "remedy_if_wrong_arguments": list(self.remedy_if_wrong_arguments),
            "world_changes": list(self.world_changes),
            "regression_ticket_ids": list(self.regression_ticket_ids),
        }

    @property
    def truth_sha256(self) -> str:
        return canonical_sha256(self.canonical_payload())


def case_answer_pairs(truth: CaseTruth) -> frozenset[tuple[str, str]]:
    """(ticket, expected value) pairs that would reveal this case's answer."""
    pairs = {(truth.target_ticket_id, truth.expected_queue_id)}

    if truth.expected_account_id is not None:
        pairs.add((truth.target_ticket_id, truth.expected_account_id))

    return frozenset(pairs)


__all__ = [
    "CASE_KINDS",
    "CaseTruth",
    "FAMILIES",
    "HELD_OUT_KINDS",
    "LOOKALIKES",
    "REMEDIES",
    "case_answer_pairs",
]

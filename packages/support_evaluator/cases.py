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

# A world with nothing injected. Used as a counterfactual hypothesis (the most
# common alternative to a proactive-detection fault); not part of the default
# dataset plan.
BASELINE_KINDS = ("clean_world",)

CASE_KINDS = tuple(FAMILIES) + LOOKALIKES + BASELINE_KINDS

HELD_OUT_KINDS = ("queue_misconfiguration", "tier_format_drift")

# Dataset v3 (tier 2): two injections on one target ticket. The variant names
# both components, "<kind>.<variant>+<kind>.<variant>", in CASE_KINDS order.
COMPOUND_KIND = "compound"


def compound_variant(first: tuple[str, str], second: tuple[str, str]) -> str:
    pair = sorted((first, second), key=lambda item: CASE_KINDS.index(item[0]))

    if pair[0][0] == pair[1][0]:
        raise ContractError("a compound needs two different kinds")

    return "+".join(f"{kind}.{variant}" for kind, variant in pair)


def parse_compound(variant: str) -> tuple[tuple[str, str], tuple[str, str]]:
    try:
        first, second = (tuple(part.split(".", 1)) for part in variant.split("+"))
    except ValueError:
        raise ContractError("malformed compound variant") from None

    if compound_variant(first, second) != variant or not all(k in CASE_KINDS for k, _ in (first, second)):
        raise ContractError("malformed compound variant")

    return first, second


def component_kinds(case_kind: str, case_variant: str) -> tuple[str, ...]:
    if case_kind == COMPOUND_KIND:
        return tuple(kind for kind, _ in parse_compound(case_variant))

    return (case_kind,)


def is_held_out(case_kind: str, case_variant: str) -> bool:
    """Held out when the kind, or any compound component, is a held-out family."""
    return any(kind in HELD_OUT_KINDS for kind in component_kinds(case_kind, case_variant))

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
    # Tier 2: irrelevant inconsistencies added away from the target (see distractors.py).
    distractor_changes: tuple[dict[str, object], ...] = ()

    def __post_init__(self) -> None:
        if self.case_kind == COMPOUND_KIND:
            parse_compound(self.case_variant)
        elif self.case_kind not in CASE_KINDS:
            raise ContractError("unknown case_kind")

        if self.remedy_if_wrong not in REMEDIES or self.remedy_if_wrong == "no_intervention":
            raise ContractError("remedy_if_wrong must be a remedy for a wrong outcome")

        if self.target_ticket_id in self.regression_ticket_ids:
            raise ContractError("the target ticket cannot be a regression ticket")

    @property
    def family_id(self) -> str | None:
        return FAMILIES.get(self.case_kind)

    @property
    def is_baseline(self) -> bool:
        return self.case_kind in BASELINE_KINDS

    @property
    def is_lookalike(self) -> bool:
        return self.case_kind in LOOKALIKES

    @property
    def held_out(self) -> bool:
        return is_held_out(self.case_kind, self.case_variant)

    def canonical_payload(self) -> dict[str, object]:
        payload = {
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

        if self.distractor_changes:
            payload["distractor_changes"] = list(self.distractor_changes)

        return payload

    @property
    def truth_sha256(self) -> str:
        return canonical_sha256(self.canonical_payload())

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "CaseTruth":
        return cls(
            case_kind=payload["case_kind"],
            case_variant=payload["case_variant"],
            target_ticket_id=payload["target_ticket_id"],
            expected_queue_id=payload["expected_queue_id"],
            expected_account_id=payload["expected_account_id"],
            remedy_if_wrong=payload["remedy_if_wrong"],
            remedy_if_wrong_arguments=tuple(payload["remedy_if_wrong_arguments"]),
            world_changes=tuple(payload["world_changes"]),
            regression_ticket_ids=tuple(payload["regression_ticket_ids"]),
            distractor_changes=tuple(payload.get("distractor_changes", ())),
        )


def case_answer_pairs(truth: CaseTruth) -> frozenset[tuple[str, str]]:
    """(ticket, expected value) pairs that would reveal this case's answer."""
    pairs = {(truth.target_ticket_id, truth.expected_queue_id)}

    if truth.expected_account_id is not None:
        pairs.add((truth.target_ticket_id, truth.expected_account_id))

    return frozenset(pairs)


__all__ = [
    "BASELINE_KINDS",
    "CASE_KINDS",
    "COMPOUND_KIND",
    "CaseTruth",
    "FAMILIES",
    "HELD_OUT_KINDS",
    "LOOKALIKES",
    "REMEDIES",
    "case_answer_pairs",
    "component_kinds",
    "compound_variant",
    "is_held_out",
    "parse_compound",
]

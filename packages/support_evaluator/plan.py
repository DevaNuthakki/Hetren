"""Balanced crossing of case kinds with scripted agent behaviours.

``cross_plan`` lists cases so that every behaviour appears equally often with
every case kind (and, within a kind, its variants cycle evenly). Behaviour is
therefore independent of family: knowing which behaviour produced a run says
nothing about which fault, if any, the world contains.

Seeds are drawn from one ``random.Random(seed)`` so a plan is reproducible.

Tier 2 (dataset v3) plans slots instead (``tier2_slots``): kind or compound
pair, variant, behaviour, evidence condition and distractor count, balanced
the same way, with withheld evidence and distractor counts assigned at random
within each cell so neither depends on kind, variant or behaviour. Each slot
draws its world and case seeds from its own random stream
(``slot_candidates``), so any slot can be rebuilt alone; candidates that do
not fit their world are skipped when the dataset is built.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import combinations, product
import random

from packages.contracts import ContractError
from packages.support_agent import BEHAVIOURS
from packages.support_evaluator.cases import BASELINE_KINDS, COMPOUND_KIND, FAMILIES, HELD_OUT_KINDS, LOOKALIKES
from packages.support_evaluator.injectors import INJECTORS

# Kinds in the default dataset plan: every family and look-alike. Baseline
# kinds (clean_world) are counterfactual hypotheses unless requested.
DEFAULT_PLAN_KINDS = tuple(kind for kind in INJECTORS if kind not in BASELINE_KINDS)


@dataclass(frozen=True)
class PlannedCase:
    case_kind: str
    case_variant: str
    behaviour: str
    world_seed: int
    case_seed: int
    evidence_condition: str = "complete"
    distractors: int = 0  # tier 2: irrelevant inconsistencies added away from the target


def planned_payload(planned: PlannedCase) -> dict[str, object]:
    """``PlannedCase`` as JSON; ``distractors`` only when set, so tier 1 records are unchanged."""
    payload = asdict(planned)

    if not planned.distractors:
        del payload["distractors"]

    return payload


def cross_plan(
    per_cell: int,
    seed: int,
    kinds: tuple[str, ...] | None = None,
    withheld_per_cell: int = 0,
) -> tuple[PlannedCase, ...]:
    """Balanced plan; ``withheld_per_cell`` cases per cell have evidence withheld.

    Withheld cases are chosen at random within each kind x behaviour cell, so
    the evidence condition is independent of kind, behaviour and variant.
    """
    if isinstance(per_cell, bool) or not isinstance(per_cell, int) or per_cell < 1:
        raise ContractError("per_cell must be a positive integer")

    if not 0 <= withheld_per_cell <= per_cell:
        raise ContractError("withheld_per_cell must be between 0 and per_cell")

    rng = random.Random(seed)
    plan: list[PlannedCase] = []

    for kind in kinds or DEFAULT_PLAN_KINDS:
        variants = INJECTORS[kind][1]

        for behaviour in BEHAVIOURS:
            withheld = set(rng.sample(range(per_cell), withheld_per_cell)) if withheld_per_cell else set()

            for index in range(per_cell):
                plan.append(
                    PlannedCase(
                        case_kind=kind,
                        case_variant=variants[index % len(variants)],
                        behaviour=behaviour,
                        world_seed=rng.randrange(1_000_000),
                        case_seed=rng.randrange(1_000_000),
                        evidence_condition="withheld" if index in withheld else "complete",
                    )
                )

    return tuple(plan)


# Tier 2 (dataset v3)

TRAINING_FAMILIES = tuple(kind for kind in FAMILIES if kind not in HELD_OUT_KINDS)
TIER2_PAIRS = tuple(combinations(TRAINING_FAMILIES, 2)) + tuple(product(TRAINING_FAMILIES, LOOKALIKES))
TIER2_HELD_OUT_PAIRS = tuple(product(HELD_OUT_KINDS, TRAINING_FAMILIES))
TIER2_SINGLE_KINDS = TRAINING_FAMILIES + LOOKALIKES
TIER2_PER_CELL = {"compound": 8, "held_out": 8, "single": 16}
TIER2_WORLD_SEEDS = (2_000_000, 3_000_000)  # disjoint from v2 (< 1,000,000) and live test (1,000,000-1,999,999)
TIER2_MAX_CANDIDATES = 50

# Compound variants whose two faults can never coexist on one target: every
# draw conflicts at injection. The plan leaves them out (tested: each never
# fits, and every remaining plan variant does).
_TARGET_DIRECTORY = "both faults rewrite the target reference's directory entry"
_DELETED = "the second fault changes the account the first deletes"
IMPOSSIBLE_COMPOUND_VARIANTS = {
    "mapping_swap.swap+missing_account.unmapped_ref": _TARGET_DIRECTORY,
    "mapping_swap.redirect+missing_account.unmapped_ref": _TARGET_DIRECTORY,
    "mapping_swap.nway+missing_account.unmapped_ref": _TARGET_DIRECTORY,
    "missing_account.deleted_account+merged_account.default": _DELETED + " (merge history)",
    "missing_account.deleted_account+tier_format_drift.case": _DELETED + " (tier drift)",
    "missing_account.deleted_account+tier_format_drift.abbreviation": _DELETED + " (tier drift)",
    "missing_account.deleted_account+tier_format_drift.whitespace": _DELETED + " (tier drift)",
    "stale_account_record.default+tier_format_drift.case": "both faults rewrite the target account's source record",
    "stale_account_record.default+tier_format_drift.abbreviation": "both faults rewrite the target account's source record",
    "stale_account_record.default+tier_format_drift.whitespace": "both faults rewrite the target account's source record",
}


@dataclass(frozen=True)
class Tier2Slot:
    case_kind: str
    case_variant: str
    behaviour: str
    evidence_condition: str
    distractors: int


def _pair_variants(pair: tuple[str, str]) -> tuple[str, ...]:
    """The pair's compound variants that can occur (``IMPOSSIBLE_COMPOUND_VARIANTS`` left out)."""
    from packages.support_evaluator.compound import compound_variants

    return tuple(v for v in compound_variants(pair) if v not in IMPOSSIBLE_COMPOUND_VARIANTS)


def _held_out_groups(held_out_pairs: tuple, per_cell: int) -> list[tuple[tuple[str, str], int]]:
    """Held-out pairs with their cell sizes: each held-out family keeps ``per_cell`` x its pair count.

    A pair with no possible variant (F7 with F2) gives its cases to the
    family's other pairs, evenly.
    """
    families: dict[str, list] = {}

    for pair in held_out_pairs:
        families.setdefault(pair[0], []).append(pair)

    groups = []

    for family, family_pairs in families.items():
        possible = [pair for pair in family_pairs if _pair_variants(pair)]
        size, left = divmod(per_cell * len(family_pairs), len(possible))

        if left:
            raise ContractError(f"{family}: {per_cell * len(family_pairs)} cases do not split evenly over {len(possible)} pairs")

        groups += [(pair, size) for pair in possible]

    return groups


def tier2_slots(
    seed: int,
    per_cell: dict[str, int] | None = None,
    withheld_per_cell: dict[str, int] | None = None,
    pairs: tuple = TIER2_PAIRS,
    held_out_pairs: tuple = TIER2_HELD_OUT_PAIRS,
    single_kinds: tuple = TIER2_SINGLE_KINDS,
) -> tuple[Tier2Slot, ...]:
    """The balanced tier 2 plan: compound pairs, held-out pairs and single kinds, each crossed with every behaviour.

    Within each group x behaviour cell, variants cycle evenly over the
    variants that can occur; one case in eight (rounded down) has evidence
    withheld unless ``withheld_per_cell`` says otherwise, and distractor
    counts 0, 1 and 2 are shuffled, both at random. Each held-out family
    keeps its share when one of its pairs is impossible (``_held_out_groups``).
    """
    per_cell = {**TIER2_PER_CELL, **(per_cell or {})}
    withheld_per_cell = withheld_per_cell or {}
    groups = [("compound", COMPOUND_KIND, _pair_variants(pair), per_cell["compound"]) for pair in pairs]
    groups += [
        ("held_out", COMPOUND_KIND, _pair_variants(pair), size)
        for pair, size in _held_out_groups(held_out_pairs, per_cell["held_out"])
    ]
    groups += [("single", kind, INJECTORS[kind][1], per_cell["single"]) for kind in single_kinds]
    rng = random.Random(f"{seed}:tier2")
    slots: list[Tier2Slot] = []

    for group, kind, variants, count in groups:
        for behaviour in BEHAVIOURS:
            withheld = set(rng.sample(range(count), withheld_per_cell.get(group, count // 8)))
            distractors = [index % 3 for index in range(count)]
            rng.shuffle(distractors)

            for index in range(count):
                slots.append(Tier2Slot(
                    kind, variants[index % len(variants)], behaviour,
                    "withheld" if index in withheld else "complete", distractors[index],
                ))

    return tuple(slots)


def slot_candidates(slot: Tier2Slot, seed: int, index: int):
    """The slot's planned cases in draw order, from the slot's own random stream."""
    rng = random.Random(f"{seed}:tier2:{index}")

    for _ in range(TIER2_MAX_CANDIDATES):
        yield PlannedCase(
            slot.case_kind, slot.case_variant, slot.behaviour,
            rng.randrange(*TIER2_WORLD_SEEDS), rng.randrange(1_000_000), slot.evidence_condition, slot.distractors,
        )


__all__ = [
    "DEFAULT_PLAN_KINDS",
    "IMPOSSIBLE_COMPOUND_VARIANTS",
    "PlannedCase",
    "TIER2_HELD_OUT_PAIRS",
    "TIER2_PAIRS",
    "TIER2_PER_CELL",
    "TIER2_SINGLE_KINDS",
    "TIER2_WORLD_SEEDS",
    "Tier2Slot",
    "cross_plan",
    "planned_payload",
    "slot_candidates",
    "tier2_slots",
]

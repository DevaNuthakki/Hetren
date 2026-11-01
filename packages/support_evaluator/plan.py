"""Balanced crossing of case kinds with scripted agent behaviours.

``cross_plan`` lists cases so that every behaviour appears equally often with
every case kind (and, within a kind, its variants cycle evenly). Behaviour is
therefore independent of family: knowing which behaviour produced a run says
nothing about which fault, if any, the world contains.

Seeds are drawn from one ``random.Random(seed)`` so a plan is reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass
import random

from packages.contracts import ContractError
from packages.support_agent import BEHAVIOURS
from packages.support_evaluator.cases import BASELINE_KINDS
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


__all__ = [
    "DEFAULT_PLAN_KINDS",
    "PlannedCase",
    "cross_plan",
]

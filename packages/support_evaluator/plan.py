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
from packages.support_evaluator.injectors import INJECTORS


@dataclass(frozen=True)
class PlannedCase:
    case_kind: str
    case_variant: str
    behaviour: str
    world_seed: int
    case_seed: int


def cross_plan(per_cell: int, seed: int, kinds: tuple[str, ...] | None = None) -> tuple[PlannedCase, ...]:
    if isinstance(per_cell, bool) or not isinstance(per_cell, int) or per_cell < 1:
        raise ContractError("per_cell must be a positive integer")

    rng = random.Random(seed)
    plan: list[PlannedCase] = []

    for kind in kinds or tuple(INJECTORS):
        variants = INJECTORS[kind][1]

        for behaviour in BEHAVIOURS:
            for index in range(per_cell):
                plan.append(
                    PlannedCase(
                        case_kind=kind,
                        case_variant=variants[index % len(variants)],
                        behaviour=behaviour,
                        world_seed=rng.randrange(1_000_000),
                        case_seed=rng.randrange(1_000_000),
                    )
                )

    return tuple(plan)


__all__ = [
    "PlannedCase",
    "cross_plan",
]

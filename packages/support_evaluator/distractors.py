"""Distractors (dataset v3, tier 2): irrelevant inconsistencies away from the target.

After a case's own fault (or faults), 1-2 distractors are added. Each is a
training-family injection pinned to another ticket, merged into the case
like a compound component (``merge_specs``):

- a stale record on another account (``stale_account_record``);
- a mapping swap between two other references (``mapping_swap.swap``);
- a transient or persistent error rule on another ticket's lookup
  (``mishandled_tool_error``);
- a recent tier change or merge history on another account
  (``recent_tier_change``, ``merged_account``).

Tier format drift (F7) is a distractor only in cases that are already held
out. Queue misconfiguration (F6) is never a distractor: it changes the global
queue configuration the labeller checks.

A distractor may not touch the target ticket, its reference, its true owner
or expected account, or the regression tickets with their references and
accounts; the target's recomputed outcome must be unchanged; and the agent's
run on the target must be identical with and without it, for every
behaviour (checked by execution: a case's own fault can bring another
account into the run, such as a swap partner). Placements that break this,
or conflict with the case, are redrawn. A distractor can therefore be seen
only by probing. Tier 2 labelling re-checks by execution that the label
equals the label without distractors. The truth records the distractors in
``distractor_changes``.

Distractors draw from their own random stream, so the same planned case with
and without distractors has the same own fault. ``apply_distractors`` adds the
same distractors to a counterfactual world, so hypotheses differ only in the
case's own fault; a counterfactual whose regression tickets a distractor
touches gets its regression tickets redrawn instead.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import random

from environments.support.fixtures import SupportEnvironment, WorldSpec
from environments.support.generator import generate_world
from packages.contracts import ContractError
from packages.hetren_evidence import compact_evidence
from packages.support_agent import BEHAVIOURS
from packages.support_evaluator.compound import affected, expected_outcome, merge_specs, regression_tickets
from packages.support_evaluator.injectors import INJECTORS, InjectedCase, inject
from packages.support_evaluator.plan import PlannedCase
from packages.support_evaluator.sampling import run_agent_on


DISTRACTOR_KINDS = (
    ("stale_account_record", "default"),
    ("mapping_swap", "swap"),
    ("mishandled_tool_error", "transient"),
    ("mishandled_tool_error", "persistent"),
    ("recent_tier_change", "default"),
    ("merged_account", "default"),
)
HELD_OUT_DISTRACTOR_KINDS = tuple(("tier_format_drift", variant) for variant in INJECTORS["tier_format_drift"][1])
MAX_DRAWS = 60


@dataclass(frozen=True)
class Distractor:
    kind: str
    variant: str
    ticket_id: str
    spec: WorldSpec
    world_changes: tuple[dict[str, object], ...]

    def canonical_payload(self) -> dict[str, object]:
        return {"kind": self.kind, "variant": self.variant, "ticket_id": self.ticket_id,
                "world_changes": list(self.world_changes)}


def _chain(clean: WorldSpec, tickets: set[str], extra_accounts=()) -> tuple[set[str], set[str], set[str]]:
    """References, accounts and tickets (``affected``'s order) of ``tickets`` and their owners."""
    directory = dict(clean.directory)
    refs = {t.customer_ref for t in clean.tickets if t.ticket_id in tickets}
    accounts = {directory.get(ref) for ref in refs} | set(extra_accounts)
    return refs, accounts - {None}, set(tickets)


def _touches(chain, touched) -> bool:
    return any(a & b for a, b in zip(chain, touched))


def _add(clean: WorldSpec, case: InjectedCase, distractor: Distractor, redraw_regression: bool = False) -> InjectedCase | None:
    """``case`` with ``distractor`` merged in, or None if it touches the protected chain or changes the outcome.

    With ``redraw_regression`` (counterfactuals), touching only the regression
    tickets redraws them away from the distractor instead.
    """
    truth = case.truth
    touched = affected(clean, distractor.spec)
    target = _chain(clean, {truth.target_ticket_id}, [truth.expected_account_id])
    regression = _chain(clean, set(truth.regression_ticket_ids))

    if _touches(target, touched) or (_touches(regression, touched) and not redraw_regression):
        return None

    try:
        spec = merge_specs(clean, case.spec, distractor.spec)
    except ContractError:
        return None

    if expected_outcome(clean, spec, truth.target_ticket_id) != (truth.expected_queue_id, truth.expected_account_id):
        return None

    changes = {"distractor_changes": truth.distractor_changes + (distractor.canonical_payload(),)}

    if _touches(regression, touched):
        rng = random.Random(f"{truth.target_ticket_id}:{distractor.kind}:{distractor.ticket_id}:regression")
        changes["regression_ticket_ids"] = regression_tickets(clean, spec, rng, truth.target_ticket_id)

    return InjectedCase(spec, replace(truth, **changes))


def _runs(case: InjectedCase) -> list[dict]:
    """The agent's compact run on the target, for every behaviour."""
    runs = []

    for behaviour in BEHAVIOURS:
        environment = SupportEnvironment(case.spec)
        runs.append(compact_evidence(run_agent_on(environment, case.truth.target_ticket_id, behaviour).evidence_payload()))

    return runs


def draw_distractors(clean: WorldSpec, case: InjectedCase, rng: random.Random, count: int) -> tuple[InjectedCase, tuple[Distractor, ...]]:
    """Add ``count`` distractors to ``case``; ``ContractError`` if they do not fit this world."""
    choices = DISTRACTOR_KINDS + (HELD_OUT_DISTRACTOR_KINDS if case.truth.held_out else ())
    truth = case.truth
    refs, accounts, protected_tickets = _chain(
        clean, {truth.target_ticket_id, *truth.regression_ticket_ids}, [truth.expected_account_id],
    )
    directory = dict(clean.directory)
    tickets = sorted(
        t.ticket_id for t in clean.tickets
        if t.ticket_id not in protected_tickets and t.customer_ref not in refs and directory.get(t.customer_ref) not in accounts
    )
    runs = _runs(case)
    chosen: list[Distractor] = []

    for _ in range(MAX_DRAWS):
        if len(chosen) == count:
            break

        kind, variant = rng.choice(choices)
        ticket_id = rng.choice(tickets)

        try:
            injected = INJECTORS[kind][0](clean, rng, variant, ticket_id)
        except ContractError:
            continue

        distractor = Distractor(kind, variant, ticket_id, injected.spec, injected.truth.world_changes)
        added = _add(clean, case, distractor)

        if added is not None and _runs(added) == runs:
            case = added
            chosen.append(distractor)

    if len(chosen) < count:
        raise ContractError(f"only {len(chosen)} of {count} distractors fit this world")

    return case, tuple(chosen)


def apply_distractors(clean: WorldSpec, case: InjectedCase, distractors: tuple[Distractor, ...]) -> InjectedCase | None:
    """``case`` (a counterfactual) with the same distractors, or None if one does not fit it."""
    for distractor in distractors:
        case = _add(clean, case, distractor, redraw_regression=True)

        if case is None:
            return None

    return case


def inject_planned(planned: PlannedCase) -> tuple[InjectedCase, tuple[Distractor, ...]]:
    """The planned case, with its distractors (drawn from their own random stream)."""
    world = generate_world(planned.world_seed)
    case = inject(planned.case_kind, world, random.Random(planned.case_seed), planned.case_variant)

    if not planned.distractors:
        return case, ()

    return draw_distractors(world, case, random.Random(f"{planned.case_seed}:distractors"), planned.distractors)


__all__ = [
    "DISTRACTOR_KINDS",
    "Distractor",
    "HELD_OUT_DISTRACTOR_KINDS",
    "apply_distractors",
    "draw_distractors",
    "inject_planned",
]

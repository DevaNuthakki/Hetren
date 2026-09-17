# Decision 0001: Reset the active repository for MVP v2

**Decision ID:** `0001`
**Decision Key:** `repository.active-foundation`
**Title:** `Reset the active repository for MVP v2`
**Status:** `ACCEPTED`
**Class:** `ARCHITECTURE`
**Date:** `2026-09-16`
**Authority:** `AUTH-HETREN-MVP-3.0`
**Scope:** `Active repository foundation established by the MVP v2 reset and carried forward under unified MVP v3`
**Research Program:** `NONE`
**Research Change Category:** `NONE`
**Evidence Consequence:** `NONE`
**Supersedes:** `None`
**Superseded By:** `None`
**Reversibility:** `CONDITIONALLY_REVERSIBLE`
**Qualification:** `Historical accepted decision normalized by Task 2 governance`

---

## Context And Trigger

The previous repository was organized around an ASR-first implementation,
including HVEE, speech providers, adversarial ASR packs, Run04-specific logic,
an Ovrin-era database lineage, and a backend/frontend split.

MVP v2 requires a cross-domain architecture whose initial qualification program
covers agent, structured-data ML, and vision systems through the same Core.

Keeping the previous layout active would make historical implementation choices
implicit dependencies of the new architecture.

## Decision

Preserve the complete pre-MVP-v2 repository in Git, then remove the legacy
implementation from the active MVP branch and rebuild around modular product
responsibilities.

The active repository uses:

- deployable applications under `apps/`;
- reusable product modules under `packages/`;
- qualified system families under `environments/`;
- native intelligence research under `research/`;
- shared verification under `tests/`;
- infrastructure under `infra/`;
- architecture and evidence records under `docs/`.

No ASR, speech, HVEE, Run04, or Ovrin package is part of the new architecture
by default.

## Alternatives Considered

Keeping the previous ASR-first repository layout active was rejected because it
would make historical implementation choices implicit dependencies of MVP v2.

## Evidence And Rationale

The previous active implementation was organized around the ASR-first lineage,
while MVP v2 requires a shared cross-domain foundation spanning agent,
structured-data ML, and vision systems.

The legacy repository was preserved before the reset so historical code and
evidence remain inspectable.

## Assumptions

- Preserved Git history remains available for later inspection.
- Useful legacy components can be evaluated independently against current contracts.
- Historical evidence keeps its original scope and identity.

## Consequences

Useful legacy code can still be inspected or selectively extracted.

Any extracted component must be evaluated against the new contracts rather
than copied because it previously worked.

Historical scientific evidence remains historical evidence and is not converted
into fresh MVP confirmation evidence by this reset.

## Risks And Constraints

- Reintroduced legacy code could accidentally restore obsolete architectural assumptions.
- Rebuilding the active foundation incurs implementation cost.
- Preservation does not establish that historical components satisfy current contracts.

## Reversibility And Rollback

The reset is conditionally reversible because preserved Git references allow
historical code to be inspected or selectively reintroduced.

Restoring the old repository wholesale would require a new explicit decision.

## Affected Contracts And Components

This decision governs the active repository foundation and the top-level
`apps/`, `packages/`, `environments/`, `research/`, `tests/`, `infra/`, and
`docs/` boundaries.

The original reset established research under `research/`. The current unified
authority further separates Native Intelligence and Adaptive Intelligence
research while preserving the shared repository foundation established by this
decision.

## Research Impact

Not applicable as a scientific-change decision.

This architecture decision creates repository boundaries used by both research
programs, but it does not itself change a scientific thesis, metric, dataset,
baseline, model, algorithm, bug interpretation, or experiment infrastructure
result.

## Qualification Requirement

This decision predates Decision 0002. Its substantive historical acceptance is
preserved; normalization does not retroactively claim compliance with governance
rules created later.

Any material extension or reversal must satisfy the current decision-governance
contract.

## Implementation Evidence

- preservation branch: `legacy/pre-mvp-v2-20260916`
- preservation tag: `pre-mvp-v2-20260916`
- preservation commit: `5b20eed`
- foundation reset commit: `8fac7a7`

## Verification Evidence

Repository foundation checks subsequently verify the active shared boundaries
and preservation model. This verification does not create fresh scientific
evidence for historical experiments.

## Supersession

This decision supersedes no prior governed decision and is not currently
superseded.

# Decision 0001: Reset the active repository for MVP v2

Date: 2026-09-16

Status: Accepted

## Context

The previous repository was organized around an ASR-first implementation,
including HVEE, speech providers, adversarial ASR packs, Run04-specific
logic, an Ovrin-era database lineage, and a backend/frontend split.

MVP v2 requires a cross-domain architecture whose initial qualification
program covers agent, structured-data ML, and vision systems through the
same Core.

Keeping the previous layout active would make historical implementation
choices implicit dependencies of the new architecture.

## Decision

Preserve the complete pre-MVP-v2 repository in Git, then remove the legacy
implementation from the active MVP branch and rebuild around modular
product responsibilities.

The active repository uses:

- deployable applications under `apps/`;
- reusable product modules under `packages/`;
- qualified system families under `environments/`;
- native intelligence research under `research/`;
- shared verification under `tests/`;
- infrastructure under `infra/`;
- architecture and evidence records under `docs/`.

No ASR, speech, HVEE, Run04, or Ovrin package is part of the new
architecture by default.

## Preservation

Legacy state:

- branch: `legacy/pre-mvp-v2-20260916`
- tag: `pre-mvp-v2-20260916`
- commit: `5b20eed`

## Consequences

Useful legacy code can still be inspected or selectively extracted.

Any extracted component must be evaluated against the new contracts rather
than copied because it previously worked.

Historical scientific evidence remains historical evidence and is not
converted into fresh MVP confirmation evidence by this reset.

# Decision 0004: Define governed MVP system taxonomy

**Decision ID:** `0004`
**Decision Key:** `architecture.system-taxonomy`
**Title:** `Define governed MVP system taxonomy`
**Status:** `ACCEPTED`
**Class:** `ARCHITECTURE`
**Date:** `2026-09-17`
**Authority:** `AUTH-HETREN-MVP-3.0`
**Scope:** `Task 4 target-system identity, classification, versioning, binding, and Versioned System Graph semantics`
**Research Program:** `NONE`
**Research Change Category:** `NONE`
**Evidence Consequence:** `NONE`
**Supersedes:** `None`
**Superseded By:** `None`
**Reversibility:** `CONDITIONALLY_REVERSIBLE`
**Qualification:** `Task 4 system-taxonomy qualification`

---

## Context And Trigger

The MVP requires Hetren to represent multiple systems, components, versions,
and providers per tenant through a versioned system graph with isolation
checks.

The three required MVP environments — E1 tool-using agent, E2
structured-data ML, and E3 vision — must use the same Hetren Core while
allowing environment-specific interaction and evaluation behavior behind
explicit boundaries.

Task 3 established shared success semantics but deliberately deferred the
concrete system taxonomy to Task 4.

Without a governed taxonomy, later capability, evaluation, research,
provenance, and verification work could silently disagree about what a
system, version, component, provider, adapter, evaluator, or investigation
surface means.

## Decision

Adopt `docs/mvp/04-system-taxonomy.md` as the governed Task 4 taxonomy.

The taxonomy establishes:

- stable tenant-scoped `System` identities;
- immutable `SystemVersion` identities;
- `SystemForm` as an operational-shape classification;
- `EnvironmentFamily` as a separate primary qualification classification;
- E1, E2, and E3 classification semantics;
- component and immutable component-version identities;
- provider identities and tenant-scoped provider bindings;
- Hetren-side adapter identities and bindings;
- evaluator identities and bindings;
- Behavioral and authorized Internal investigation surfaces;
- Versioned System Graph semantics and relationship vocabulary;
- tenant-isolation and graph-validity requirements;
- historical identity and invalidation rules;
- integration with `SystemSnapshot`, `CapabilityProfile`, and the Artifact
  Graph;
- governed taxonomy-extension rules.

This decision does not declare that every taxonomy member is supported.

Task 5 remains responsible for the initial supported capability matrix.

This decision remains non-authoritative while its status is `PROPOSED`.

## Alternatives Considered

### Let each environment define its own system representation

Rejected because E1, E2, and E3 must share the same conceptual Hetren Core and
cannot establish incompatible identity, provenance, or evidence semantics.

### Treat provider, adapter, and evaluator as ordinary target components

Rejected because this would blur the distinction between the target being
investigated and Hetren-side interaction or evaluation machinery.

Provider relationships may participate in target behavior, while adapters and
evaluators ordinarily describe how Hetren interacts with or evaluates the
target.

### Use one mutable system record without immutable versions

Rejected because later target changes could silently alter the meaning or
applicability of historical evidence.

### Treat taxonomy membership as capability support

Rejected because representability and qualified support are different facts.
Task 5 and `CapabilityProfile` govern capability state.

### Create a new canonical SystemGraphRecord

Rejected because `SystemSnapshot` already owns captured target-state
responsibility.

Task 4 defines Versioned System Graph semantics without introducing a
competing canonical captured-state record.

## Evidence And Rationale

The qualified MVP Charter requires:

- E1 tool-using agent;
- E2 structured-data ML;
- E3 vision;
- shared Core behavior across all three;
- explicit adapter and evaluator boundaries;
- Behavioral and authorized Internal investigation;
- multiple systems, components, versions, and providers per tenant;
- versioned system graphs with isolation checks.

Task 3 further establishes that:

- environment adapters define interaction rather than success semantics;
- evaluators define environment-specific measures without redefining shared
  success semantics;
- Task 4 owns the concrete system taxonomy;
- Task 5 owns the supported capability matrix.

The proposed taxonomy preserves those boundaries.

## Assumptions

This decision assumes:

- `SystemSnapshot` remains the canonical captured-state record;
- `CapabilityProfile` remains the canonical capability-state record;
- the Artifact Graph remains the canonical artifact-provenance structure;
- Task 5 will define qualified support rather than Task 4;
- Task 6 through Task 9 will define their own governed concrete artifacts;
- future environment families may require governed taxonomy extension.

If those assumptions materially change, this decision may require
supersession or requalification.

## Consequences

If accepted, Hetren receives one shared vocabulary for representing target
systems across E1, E2, E3, product work, Native Intelligence, and Adaptive
Intelligence.

Historical evidence can bind to immutable target and interaction/evaluation
identities rather than mutable labels.

Provider-specific, environment-specific, and research-specific implementation
cannot silently redefine shared Core identity semantics.

The taxonomy also introduces stronger versioning and graph-validity
obligations that later implementation must satisfy.

## Risks And Constraints

The taxonomy may prove incomplete when later concrete Task 5-9 artifacts are
implemented.

Over-modeling every implementation detail as a component would create
unnecessary complexity.

Under-modeling material target state would make evidence ambiguous.

Primary environment-family classification may require future governed
extension for genuinely cross-domain cases that cannot be represented
truthfully under the initial model.

Taxonomy extensibility therefore remains governed rather than unrestricted.

## Reversibility And Rollback

This decision is conditionally reversible.

Before downstream records materially depend on the taxonomy, the proposal can
be revised through Task 4 qualification.

After acceptance and downstream use, material semantic changes require a new
versioned decision or explicit supersession, compatibility analysis,
historical interpretation rules, and affected requalification.

Historical accepted records must not be rewritten or deleted to simulate
rollback.

## Affected Contracts And Components

This decision affects or constrains:

- `SystemSnapshot`;
- `CapabilityProfile`;
- Versioned System Graph implementation;
- future canonical identities under `packages/contracts`;
- target representation under `packages/core`;
- environment bindings under `environments/agent`;
- environment bindings under `environments/tabular`;
- environment bindings under `environments/vision`;
- provider integrations;
- adapter integrations;
- evaluator implementations;
- Behavioral and Internal Engines;
- evidence provenance;
- verification provenance;
- tenant-isolation checks;
- future Task 5 capability declarations.

## Research Impact

Not applicable.

This is an architecture decision shared by product, Native Intelligence, and
Adaptive Intelligence. It does not change a Native or Adaptive scientific
hypothesis and therefore uses:

- Research Program: `NONE`;
- Research Change Category: `NONE`;
- Evidence Consequence: `NONE`.

Research programs must use the shared taxonomy rather than create parallel
identity or graph semantics.

## Qualification Requirement

Decision 0004 may transition from `PROPOSED` to `ACCEPTED` only after the
Task 4 taxonomy passes its declared qualification contract.

Qualification must establish at minimum:

- all 50 Task 4 qualification conditions;
- structural correctness;
- semantic correctness;
- authority alignment;
- adversarial and mutation resistance;
- Task 1 regression qualification;
- Task 2 regression qualification;
- Task 3 regression qualification;
- accepted-state qualification before Task 4 is considered complete.

Qualification criteria must not be weakened merely to obtain acceptance.

## Implementation Evidence

Implemented and preserved in:

- `docs/mvp/04-system-taxonomy.md`;
- `scripts/check_system_taxonomy.py`;
- `tests/qualification/test_system_taxonomy.py`.

## Verification Evidence

Verified by `docs/decisions/qualification/0004-system-taxonomy.md` with
structural, semantic, adversarial, mutation, authority, regression, and
accepted-state qualification.

## Supersession

Supersedes: `None`

Superseded By: `None`

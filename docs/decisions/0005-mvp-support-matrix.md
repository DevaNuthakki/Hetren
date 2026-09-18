# Decision 0005: Freeze the initial MVP capability-support matrix

**Decision ID:** `0005`
**Decision Key:** `product.mvp-support-matrix`
**Title:** `Freeze the initial MVP capability-support matrix`
**Status:** `ACCEPTED`
**Class:** `PRODUCT`
**Date:** `2026-09-17`
**Authority:** `AUTH-HETREN-MVP-3.0`
**Scope:** `Task 5 initial MVP capability requirements, support states, Behavioral matrix, Internal qualification overlay, and CapabilityProfile support semantics`
**Research Program:** `NONE`
**Research Change Category:** `NONE`
**Evidence Consequence:** `NONE`
**Supersedes:** `None`
**Superseded By:** `None`
**Reversibility:** `CONDITIONALLY_REVERSIBLE`
**Qualification:** `Task 5 support-matrix qualification`

---

## Context And Trigger

Task 4 established the governed system taxonomy and explicitly separated
representability from capability support.

The MVP now requires a concrete governed answer to a different question:
which capabilities are required by the initial MVP, what their support states
mean, and what evidence is required before Hetren may claim that a capability
is supported.

The qualified MVP Charter requires:

- E1 tool-using agent;
- E2 structured-data ML;
- E3 vision;
- regression repair;
- constrained improvement;
- Behavioral investigation;
- authorized Internal investigation;
- one small open CNN-family Internal qualification binding;
- one small open Transformer-family Internal qualification binding;
- at least one governed investigation combining Behavioral and Internal
  evidence.

Without a governed Task 5 support contract, later implementation could confuse:

- taxonomy membership with support;
- MVP obligation with qualified support;
- authorization with support;
- one successful execution with product capability;
- one failed execution with permanent unsupported status;
- Internal capability with universal Internal access across E1, E2, and E3.

## Decision

Adopt `docs/mvp/05-support-matrix.md` as the governed Task 5
support contract.

The accepted support model establishes:

- `CapabilityProfile` as the canonical capability record;
- exactly two initial `CapabilityKind` values:
  - `REGRESSION_REPAIR`;
  - `CONSTRAINED_IMPROVEMENT`;
- exactly three `MVPRequirement` values:
  - `REQUIRED`;
  - `PERMITTED`;
  - `EXCLUDED`;
- exactly six `CapabilitySupportState` values:
  - `QUALIFIED_SUPPORTED`;
  - `UNQUALIFIED`;
  - `UNSUPPORTED`;
  - `INCOMPATIBLE`;
  - `BLOCKED`;
  - `UNKNOWN`;
- six required Behavioral product capability cells;
- a separate Internal Engine qualification overlay;
- two required Internal binding obligations:
  - one small open CNN-family binding;
  - one small open Transformer-family binding;
- one required combined Behavioral/Internal investigation obligation;
- all nine initial mandatory obligations beginning as `UNQUALIFIED`;
- governed qualification, invalidation, narrowing, transition, and
  requalification semantics;
- explicit separation between capability support, taxonomy, authorization,
  and Task 3 evaluation outcomes;
- explicit deferral of concrete Task 6 through Task 9 artifacts.

The six required Behavioral cells are:

1. `E1_AGENT` + `REGRESSION_REPAIR` + `BEHAVIORAL`;
2. `E1_AGENT` + `CONSTRAINED_IMPROVEMENT` + `BEHAVIORAL`;
3. `E2_STRUCTURED_ML` + `REGRESSION_REPAIR` + `BEHAVIORAL`;
4. `E2_STRUCTURED_ML` + `CONSTRAINED_IMPROVEMENT` + `BEHAVIORAL`;
5. `E3_VISION` + `REGRESSION_REPAIR` + `BEHAVIORAL`;
6. `E3_VISION` + `CONSTRAINED_IMPROVEMENT` + `BEHAVIORAL`.

Each begins:

- `MVPRequirement = REQUIRED`;
- `CapabilitySupportState = UNQUALIFIED`.

No initial Task 5 obligation is declared `QUALIFIED_SUPPORTED`.

## Alternatives Considered

### Treat every Task 4 taxonomy member as supported

Rejected because Task 4 explicitly separates representability from qualified
support.

A target may be representable while its capability is unqualified,
unsupported, incompatible, blocked, or unknown.

### Use only supported versus unsupported

Rejected because that binary model would collapse materially different states.

Hetren must distinguish at least:

- support that has been qualified;
- capability still awaiting qualification;
- explicit unsupported scope;
- compatibility failure;
- temporary or dependency blockage;
- genuinely unknown support state.

### Mark required MVP capabilities as supported immediately

Rejected because requirement is not evidence.

An MVP obligation may be mandatory while remaining `UNQUALIFIED` until
governed qualification evidence exists.

### Require Internal support across all E1, E2, and E3 combinations

Rejected because the MVP authority requires Internal Engine capability and
specific CNN-family and Transformer-family qualification coverage, but does
not require Internal access for every target in every environment family.

The Internal Engine therefore uses a separate qualification overlay rather
than a second six-cell Cartesian matrix.

### Require only one problem type per environment

Rejected as the Task 5 scope decision because it would permit a nominally
cross-domain MVP to demonstrate regression repair in some environments and
constrained improvement only in others.

The Task 5 contract requires both initial product capability kinds in
each of E1, E2, and E3.

### Treat one successful execution as capability qualification

Rejected because one execution does not establish general governed product
capability.

Qualified support must remain bounded by preserved evidence, identity,
compatibility, provenance, and verification requirements.

## Evidence And Rationale

The qualified MVP Charter requires all three MVP environment families and both
initial problem types.

It also requires the Behavioral Engine to exercise a real investigative
closed loop and requires the Internal Engine to qualify through at least two
open neural-architecture bindings.

Task 4 establishes that:

- taxonomy classification does not declare support;
- `CapabilityProfile` owns capability state;
- support may depend on environment family, system form, investigation surface,
  adapter, evaluator, provider constraints, target characteristics, and
  compatibility;
- Internal investigation remains subject to execution-time authorization.

Task 3 establishes that:

- evaluation outcomes remain exactly `PASS`, `FAIL`, `INCONCLUSIVE`,
  `BLOCKED`, and `INVALID`;
- consequential claims require evidence appropriate to their declared scope;
- evidence supports no stronger claim than it justifies;
- successful product results do not automatically establish Native or
  Adaptive research success.

The accepted Task 5 model preserves those boundaries.

## Assumptions

This decision assumes:

- `CapabilityProfile` remains the canonical capability-state record;
- Task 3 continues to govern success and evaluation semantics;
- Task 4 continues to govern system taxonomy;
- E1, E2, and E3 remain the three initial required MVP environment families;
- regression repair and constrained improvement remain the two initial product
  problem types;
- Behavioral and authorized Internal investigation remain first-class MVP
  capabilities;
- Internal qualification continues to require at least one small open
  CNN-family binding and one small open Transformer-family binding;
- Tasks 6 through 9 retain ownership of their concrete later artifacts.

If those assumptions materially change, this decision may require
supersession or requalification.

## Consequences

Hetren receives a concrete, auditable boundary between:

- required capability;
- qualified support;
- unqualified capability;
- unsupported capability;
- incompatibility;
- blockage;
- unknown support state.

The initial MVP obligation becomes explicit without fabricating capability
evidence.

All six Behavioral cross-domain capability cells become mandatory
qualification obligations.

The Internal Engine remains first-class without falsely requiring Internal
access for every E1, E2, or E3 target.

Capability claims become narrower and more defensible because qualification
must preserve the evidence scope that justifies them.

The model also introduces stronger historical-state, invalidation,
compatibility, and requalification obligations for future capability
implementation.

## Risks And Constraints

The six-cell Behavioral matrix is intentionally stricter than merely requiring
the three environment families and two problem types independently.

That additional Task 5 scope increases later implementation and qualification
work.

Some future targets may require more detailed compatibility dimensions than
the initial matrix exposes.

Over-expanding the primary matrix with provider, adapter, evaluator,
system-form, or target-specific axes would create false precision and an
unmanageable Cartesian product.

Under-scoping a support declaration could allow qualification evidence to be
generalized beyond what it actually proves.

Later capability work must therefore preserve narrow support scope and use
governed extension when materially new semantics are required.

## Reversibility And Rollback

This decision is conditionally reversible.

While `PROPOSED`, it may be revised through Task 5 qualification.

After acceptance, material changes to:

- capability-kind vocabulary;
- requirement-state vocabulary;
- capability-support-state vocabulary;
- the six Behavioral obligations;
- the two Internal binding obligations;
- the combined-engine obligation;
- qualification semantics;
- invalidation or transition semantics

require governed revision, compatibility analysis, historical interpretation,
and applicable requalification.

Historical capability states and accepted support-matrix versions must not be
rewritten or deleted to simulate rollback.

## Affected Contracts And Components

This decision affects or constrains:

- `CapabilityProfile`;
- future capability contracts under `packages/contracts`;
- shared capability logic under `packages/core`;
- environment support for E1;
- environment support for E2;
- environment support for E3;
- Behavioral Engine implementation;
- Internal Engine implementation;
- adapter qualification;
- evaluator qualification;
- provider compatibility declarations;
- execution authorization prerequisites;
- capability qualification evidence;
- verification evidence;
- release qualification;
- future Task 6 through Task 9 artifacts when referenced by capability
  qualification.

This decision does not redefine:

- `SystemSnapshot`;
- Task 3 evaluation outcomes;
- Task 4 taxonomy;
- Artifact Graph provenance;
- the Action and Permission Gateway;
- independent verification authority.

## Research Impact

Not applicable.

This is a product capability-governance decision shared across the engineering
MVP.

It does not change a Native Intelligence or Adaptive Intelligence scientific
hypothesis and therefore uses:

- Research Program: `NONE`;
- Research Change Category: `NONE`;
- Evidence Consequence: `NONE`.

Native and Adaptive research may consume these capability semantics but must
not create parallel support-state vocabularies or capability authorities.

## Qualification Requirement

Decision 0005 is accepted only after the Task 5 support matrix passes its
declared qualification contract.

Qualification must establish at minimum:

- all 50 Task 5 qualification conditions;
- exact section topology;
- exact capability-kind vocabulary;
- exact requirement-state vocabulary;
- exact capability-support-state vocabulary;
- exact six-cell Behavioral matrix;
- exact two-binding Internal qualification overlay;
- exact combined-engine obligation;
- zero manufactured initial `QUALIFIED_SUPPORTED` obligations;
- semantic separation between support, taxonomy, authorization, and
  evaluation;
- capability transition and requalification protections;
- explicit Task 6 through Task 9 deferrals;
- structural validation;
- semantic validation;
- authority alignment;
- adversarial mutation resistance;
- Task 1 regression qualification;
- Task 2 regression qualification;
- Task 3 regression qualification;
- Task 4 regression qualification;
- final accepted-state qualification.

Qualification criteria must not be weakened merely to obtain acceptance.

## Implementation Evidence

Implemented and preserved in:

- `docs/mvp/05-support-matrix.md`;
- `scripts/check_support_matrix.py`;
- `tests/qualification/test_support_matrix.py`;
- `.github/workflows/ci.yml`.

The governed Task 5 validator enforces the 34-section specification,
50 qualification conditions, exact initial support matrix, support-state
semantics, lifecycle state, Decision/register synchronization, and final
qualification evidence.

The adversarial suite freezes the Task 5 mutation contract at `46 / 46`.

## Verification Evidence

Verified by:

- `docs/decisions/qualification/0005-mvp-support-matrix.md`.

Pre-acceptance qualification established:

- Task 1 validator and mutation qualification: PASS;
- Task 2 validator and 44 / 44 mutation qualification: PASS;
- Task 3 validator and mutation qualification: PASS;
- Task 4 validator and 34 / 34 mutation qualification: PASS;
- Task 5 development-state validator: PASS;
- Task 5 mutation qualification: PASS, 46 / 46;
- qualification-code compilation: PASS;
- Task 5 CI required-file checks: PASS;
- repository diff check: PASS.

Final accepted-state qualification is enforced through
`python3 scripts/check_support_matrix.py --require-qualified`
and the frozen Task 5 mutation suite.

## Supersession

Supersedes: `None`

Superseded By: `None`

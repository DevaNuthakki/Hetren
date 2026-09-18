# Decision 0006: Govern initial Native Intelligence MVP hypotheses

**Decision ID:** `0006`
**Decision Key:** `research.native-intelligence.mvp-hypotheses`
**Title:** `Govern initial Native Intelligence MVP hypotheses`
**Status:** `ACCEPTED`
**Class:** `RESEARCH_GOVERNANCE`
**Date:** `2026-09-17`
**Authority:** `AUTH-HETREN-MVP-3.0`
**Scope:** `Task 6 Native Intelligence MVP hypotheses N-H1 and N-H2, thesis-level thresholds, falsification criteria, and scientific claim scope`
**Research Program:** `NATIVE`
**Research Change Category:** `THESIS`
**Evidence Consequence:** `NEW_PROGRAM_VERSION_AND_RERUN`
**Supersedes:** `None`
**Superseded By:** `None`
**Reversibility:** `CONDITIONALLY_REVERSIBLE`
**Qualification:** `Task 6 research-hypotheses qualification`

---

## Context And Trigger

Tasks 1 through 5 deliberately deferred the concrete Native Intelligence
research hypotheses to Task 6.

The qualified research framework already requires Native scientific claims to
remain distinct from:

- product qualification;
- deterministic heuristics;
- external-generator performance;
- authored investigation strategy;
- infrastructure reuse;
- Adaptive Intelligence evidence.

Task 6 must now preregister the first bounded Native hypotheses before
protected experimental evidence exists.

## Decision

Propose adoption of the Native portions of
`docs/mvp/06-research-hypotheses.md` as the initial governed Native
Intelligence thesis contract.

The initial Native hypothesis set is exactly:

- `N-H1` — Learned Investigation Value;
- `N-H2` — Cross-Family Learned Transfer.

`N-H1` tests whether trainable Hetren Native Intelligence provides measurable
held-out investigation-decision value beyond the strongest applicable matched
governed baseline.

`N-H2` tests whether learned Native decision capability retains measurable
value across a protected system-family boundary rather than merely reusing
shared infrastructure, retrieval, or authored strategy.

The numerical minimum-effect, uncertainty, falsification, transfer, and
claim-narrowing rules are defined by the Task 6 specification.

Acceptance of this decision would govern what Hetren is allowed to test and
claim.

Acceptance would not establish that either hypothesis is scientifically
supported.

Decision acceptance governs the Native thesis contract but is not
scientific evidence.

## Alternatives Considered

### One CROSS_PROGRAM decision

Rejected because Native and Adaptive Intelligence have separate scientific
claims, separate evidence, separate failure modes, and separate reporting
requirements.

A single cross-program thesis decision would make later scientific change
control and evidence consequences unnecessarily coupled.

### No numerical thesis gates in Task 6

Rejected because Tasks 1 and 3 require predeclared hypotheses and qualification
criteria, and Task 3 explicitly deferred numerical research qualification
criteria to Task 6.

### Product success as Native research evidence

Rejected because a successful repair or improvement does not establish that
learned Native Intelligence caused or materially improved that result.

### Infrastructure reuse as transfer evidence

Rejected because shared Core records, adapters, evaluators, retrieval, or
hand-authored strategy do not establish learned transfer.

## Evidence And Rationale

The existing qualified contracts establish that:

- Native research status must remain separate from product status;
- exact Native hypotheses were deferred to Task 6;
- Native claims require evidence appropriate to learned decision value;
- transfer claims require evidence beyond infrastructure or procedure reuse;
- protected criteria must be frozen before protected evidence;
- negative scientific evidence must remain valid and visible;
- material thesis changes require governed change control.

The Task 6 draft converts those requirements into two bounded, falsifiable
Native hypotheses.

The current repository does not contain protected scientific evidence proving
either `N-H1` or `N-H2`.

That absence is intentional.

This decision governs the thesis contract; later governed experimentation must
determine scientific status.

## Assumptions

This decision assumes:

- Task 7 will define concrete development and protected split identities;
- Task 8 will define concrete baseline identities, versions, and comparison
  configuration;
- Task 9 will define concrete cost, resource, and effort-accounting values
  where applicable;
- applicable evaluators will expose measures whose direction and normalization
  are frozen before protected evaluation;
- independent evaluation can be established under the qualified MVP
  verification framework.

If these assumptions fail, the affected experiment may become `BLOCKED`,
`INVALID`, or require a governed thesis revision.

## Consequences

If accepted:

- the initial Native thesis set becomes `N-H1` and `N-H2`;
- their Task 6 thresholds become protected thesis-level qualification gates;
- later Native experiments must identify the hypothesis version they test;
- negative and null results must remain preserved;
- stronger Native claims remain unavailable without separate governed evidence;
- material thesis changes require a new governed program version and rerun.

Acceptance does not create a scientific `PASS`.

## Risks And Constraints

Material risks include:

- thresholds may later prove too strict or too permissive;
- available evaluation units may provide insufficient statistical power;
- strong matched baselines may reduce apparent Native advantage;
- transfer may disappear under leakage control;
- apparent learned value may instead be attributable to external models,
  heuristics, retrieval, or authored strategies;
- later evidence may support only a narrower claim.

These risks are reasons to preserve falsifiability rather than weaken it.

## Reversibility And Rollback

This decision is conditionally reversible through a governed successor using
the same Decision Key.

A material thesis change must not edit historical evidence in place.

The successor must preserve:

- the prior decision;
- prior hypothesis version;
- prior thresholds;
- prior experimental evidence;
- prior scientific interpretation.

The minimum evidence consequence for a thesis change is:

`NEW_PROGRAM_VERSION_AND_RERUN`.

## Affected Contracts And Components

Affected artifacts include:

- `docs/mvp/06-research-hypotheses.md`;
- Native Intelligence research manifests;
- Native experiment records;
- Native evaluation records;
- Native verification records;
- Task 7 split bindings;
- Task 8 baseline bindings;
- Task 9 resource bindings;
- Artifact Graph provenance for Native research.

This decision does not change Task 5 product capability-support state.

## Research Impact

Research Program:

`NATIVE`

Research Change Category:

`THESIS`

Required Evidence Consequence:

`NEW_PROGRAM_VERSION_AND_RERUN`

This decision establishes the first governed Native thesis version for the MVP.

No prior Task 6 protected scientific result is being converted into evidence
by this proposal.

Future material changes to `N-H1`, `N-H2`, their scientific meaning, or their
protected thesis-level gates require the governed evidence consequence above.

## Qualification Requirement

Before this decision may become `ACCEPTED`, Task 6 qualification must verify
at minimum that:

- the Native hypothesis set is exactly `N-H1` and `N-H2`;
- both belong only to the Native Intelligence program;
- their scientific claims are explicit and falsifiable;
- their numerical minimum-effect rules are protected against post-result
  weakening;
- `N-H1` cannot be satisfied by product usefulness alone;
- `N-H2` cannot be satisfied by infrastructure, retrieval, or authored target
  strategy alone;
- uncertainty and independent-evaluation requirements remain intact;
- negative results remain preservable;
- Native evidence cannot establish an Adaptive hypothesis;
- Task 7, Task 8, and Task 9 retain their existing ownership boundaries;
- decision acceptance cannot manufacture scientific support;
- adversarial qualification rejects weakened versions of these protections.

## Implementation Evidence

Implemented and preserved in:

- `docs/mvp/06-research-hypotheses.md`;
- `scripts/check_research_hypotheses.py`;
- `tests/qualification/test_research_hypotheses.py`;
- `.github/workflows/ci.yml`.

The Task 6 validator enforces the Native thesis identity, numerical gates,
falsification boundaries, evidence isolation, transfer semantics, and
governance lifecycle.

The adversarial suite exercises the shared Task 6 contract across development
and accepted states.

## Verification Evidence

Verified by:

- `docs/decisions/qualification/0006-native-intelligence-mvp-hypotheses.md`;
- the Task 6 development validator;
- the Task 6 52-mutation adversarial suite;
- the Tasks 1 through 5 pre-acceptance regression wall;
- qualification-code compilation;
- CI required-file and Task 6 wiring checks;
- repository diff validation.

Acceptance qualifies the Native thesis contract.

It does not establish scientific support for `N-H1` or `N-H2`.

## Supersession

Supersedes: `None`

Superseded By: `None`

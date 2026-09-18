# Decision 0007: Govern initial Adaptive Intelligence MVP hypotheses

**Decision ID:** `0007`
**Decision Key:** `research.adaptive-intelligence.mvp-hypotheses`
**Title:** `Govern initial Adaptive Intelligence MVP hypotheses`
**Status:** `ACCEPTED`
**Class:** `RESEARCH_GOVERNANCE`
**Date:** `2026-09-17`
**Authority:** `AUTH-HETREN-MVP-3.0`
**Scope:** `Task 6 Adaptive Intelligence MVP hypotheses A-H1 and A-H2, thesis-level thresholds, falsification criteria, and scientific claim scope`
**Research Program:** `ADAPTIVE`
**Research Change Category:** `THESIS`
**Evidence Consequence:** `NEW_PROGRAM_VERSION_AND_RERUN`
**Supersedes:** `None`
**Superseded By:** `None`
**Reversibility:** `CONDITIONALLY_REVERSIBLE`
**Qualification:** `Task 6 research-hypotheses qualification`

---

## Context And Trigger

Adaptive Intelligence is a separate scientific program from Native
Intelligence.

The qualified MVP Charter defines its central question as whether controlled,
reversible, and verifiable post-deployment plasticity can create useful new
behavior while preserving required prior capability.

Hetren Governed Plasticity remains a working research hypothesis rather than
an established product capability.

Task 6 must therefore preregister the first bounded Adaptive hypotheses before
protected evidence exists.

## Decision

Propose adoption of the Adaptive portions of
`docs/mvp/06-research-hypotheses.md` as the initial governed Adaptive
Intelligence thesis contract.

The initial Adaptive hypothesis set is exactly:

- `A-H1` — Bounded Useful Adaptation;
- `A-H2` — Retention, Locality, and Rollback.

`A-H1` tests whether governed post-deployment plasticity produces material
protected target adaptation while satisfying critical invariants and
outperforming the strongest applicable governed adaptation baseline.

`A-H2` separately tests whether useful adaptation preserves protected prior
capability, remains within a bounded locality envelope, and supports executed
rollback to the declared pre-adaptation state.

Passing `A-H1` does not imply passing `A-H2`.

Passing either hypothesis does not establish general continual learning,
general self-improvement, Adaptive transfer, multimodal generality, scaling
superiority, or deployment authorization.

Acceptance of this decision would govern the thesis contract.

Acceptance would not establish scientific support for either hypothesis.

Decision acceptance governs the Adaptive thesis contract but is not
scientific evidence.

## Alternatives Considered

### One combined Native and Adaptive thesis decision

Rejected because the two programs must preserve independent scientific
evidence, interpretations, failures, and change histories.

### One Adaptive hypothesis covering all plasticity behavior

Rejected because useful target adaptation and bounded retention/locality/
rollback are materially different claims.

Combining them would allow success on target adaptation to obscure forgetting,
non-local change, or failed rollback.

### Product success as Adaptive research evidence

Rejected because a useful product result does not establish controlled
post-deployment plasticity.

### Adaptive self-certification

Rejected because the adapting or proposing mechanism must not be the sole
authority establishing scientific success.

## Evidence And Rationale

The qualified research contracts already require Adaptive claims to consider,
where applicable:

- measurable target adaptation;
- strong adaptation baselines;
- protected prior-capability retention;
- locality;
- critical invariants;
- rollback;
- independent evaluation;
- protected qualification;
- adaptation cost;
- reproducibility.

They also require stronger later claims such as sequential learning,
consolidation, Experience Capsule transfer, cross-model transfer,
cross-architecture transfer, multimodal generality, and scaling to receive
their own scientific gates.

The Task 6 draft therefore uses two bounded early-MVP hypotheses rather than
claiming the full later research agenda.

The repository does not currently contain protected scientific evidence
proving `A-H1` or `A-H2`.

## Assumptions

This decision assumes:

- Task 7 will define concrete protected adaptation and retention partitions;
- Task 8 will define concrete strong adaptation baselines;
- Task 9 will define concrete adaptation-cost and resource-accounting values;
- critical invariants can be declared before protected evaluation;
- locality measures can use a bounded normalized scale whose meaning is frozen
  before protected evidence;
- rollback state and provenance can be independently inspected.

If these assumptions fail, the affected experiment may be `BLOCKED`,
`INVALID`, or require governed thesis revision.

## Consequences

If accepted:

- the initial Adaptive thesis set becomes `A-H1` and `A-H2`;
- their Task 6 thresholds become protected thesis-level gates;
- target adaptation cannot substitute for retention/locality/rollback;
- critical-invariant violations remain non-compensatory;
- negative Adaptive experiments remain valid scientific evidence;
- stronger continual-learning or transfer claims remain excluded;
- later material thesis changes require governed new program versions and
  reruns.

Acceptance does not create a scientific `PASS`.

## Risks And Constraints

Material risks include:

- useful target adaptation may cause unacceptable forgetting;
- an adaptation may be non-local despite target improvement;
- rollback may fail behaviorally even if files or weights are restored;
- baseline adaptation methods may match or exceed HGP;
- apparent adaptation may result from leakage;
- the proposed tolerances may later prove scientifically inappropriate;
- evidence may support only a narrower bounded-plasticity claim.

These outcomes must remain reportable without relabeling them as success.

## Reversibility And Rollback

This decision is conditionally reversible through a governed successor using
the same Decision Key.

A successor must preserve:

- prior hypothesis versions;
- thresholds;
- protected results;
- failed experiments;
- invalidated experiments;
- scientific interpretations;
- supersession history.

The minimum evidence consequence for a material thesis change is:

`NEW_PROGRAM_VERSION_AND_RERUN`.

## Affected Contracts And Components

Affected artifacts include:

- `docs/mvp/06-research-hypotheses.md`;
- Adaptive Intelligence research manifests;
- adaptation execution records;
- retention and locality evaluation records;
- rollback evidence;
- independent Adaptive verification records;
- Task 7 split bindings;
- Task 8 baseline bindings;
- Task 9 adaptation-cost bindings;
- Artifact Graph provenance for Adaptive research.

This decision does not change product authorization or Task 5 capability
support state.

## Research Impact

Research Program:

`ADAPTIVE`

Research Change Category:

`THESIS`

Required Evidence Consequence:

`NEW_PROGRAM_VERSION_AND_RERUN`

This decision establishes the first governed Adaptive thesis version for the
MVP.

No prior Task 6 protected scientific result is being converted into evidence
by this proposal.

Future material changes to `A-H1`, `A-H2`, their scientific meaning, or their
protected thesis-level gates require the governed evidence consequence above.

## Qualification Requirement

Before this decision may become `ACCEPTED`, Task 6 qualification must verify
at minimum that:

- the Adaptive hypothesis set is exactly `A-H1` and `A-H2`;
- both belong only to the Adaptive Intelligence program;
- the scientific claims and falsification rules are explicit;
- `A-H1` requires material target adaptation, strong-baseline comparison,
  critical-invariant protection, and independent evaluation;
- `A-H2` separately requires retention, locality, and executed rollback;
- `A-H1` success cannot manufacture `A-H2` success;
- stronger continual-learning, Adaptive-transfer, multimodal, scaling, and
  deployment claims remain excluded;
- protected thresholds and locality normalization are frozen before protected
  evidence;
- negative and invalidated Adaptive results remain preserved;
- Adaptive evidence cannot establish a Native hypothesis;
- Task 7, Task 8, and Task 9 retain their ownership boundaries;
- decision acceptance cannot manufacture scientific support;
- adversarial qualification rejects weakened versions of these protections.

## Implementation Evidence

Implemented and preserved in:

- `docs/mvp/06-research-hypotheses.md`;
- `scripts/check_research_hypotheses.py`;
- `tests/qualification/test_research_hypotheses.py`;
- `.github/workflows/ci.yml`.

The Task 6 validator enforces the Adaptive thesis identity, numerical gates,
falsification boundaries, retention/locality/rollback requirements,
evidence isolation, and governance lifecycle.

The adversarial suite exercises the shared Task 6 contract across development
and accepted states.

## Verification Evidence

Verified by:

- `docs/decisions/qualification/0007-adaptive-intelligence-mvp-hypotheses.md`;
- the Task 6 development validator;
- the Task 6 52-mutation adversarial suite;
- the Tasks 1 through 5 pre-acceptance regression wall;
- qualification-code compilation;
- CI required-file and Task 6 wiring checks;
- repository diff validation.

Acceptance qualifies the Adaptive thesis contract.

It does not establish scientific support for `A-H1` or `A-H2`.

## Supersession

Supersedes: `None`

Superseded By: `None`

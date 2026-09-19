# Decision 0008: Govern the initial MVP split protocol

**Decision ID:** `0008`
**Decision Key:** `research.evaluation.initial-splits`
**Title:** `Govern the initial MVP split protocol`
**Status:** `PROPOSED`
**Class:** `DATA`
**Date:** `2026-09-18`
**Authority:** `AUTH-HETREN-MVP-3.0`
**Scope:** `Task 7 development, validation, protected and held-out split identities, partition boundaries, evaluation-unit independence, protected-evidence lifecycle, and leakage controls`
**Research Program:** `CROSS_PROGRAM`
**Research Change Category:** `DATA`
**Evidence Consequence:** `RERUN_AND_PRESERVE_DATA_DISTINCTIONS`
**Supersedes:** `None`
**Superseded By:** `None`
**Reversibility:** `CONDITIONALLY_REVERSIBLE`
**Qualification:** `Task 7 initial-splits qualification`

---

## Context And Trigger

Tasks 3 through 6 intentionally deferred concrete split identities and
partitioning rules to Task 7.

The qualified contracts already require:

- development, validation, protected, and held-out evidence to remain
  distinguishable;
- protected criteria to be frozen before protected evidence is inspected;
- material post-result split changes to create governed revision rather than
  silently rewriting history;
- Native learned-transfer claims to survive leakage-controlled held-out
  evaluation;
- Adaptive claims to separate adaptation input from protected evaluation;
- consequential claims to use meaningfully separated verification authority;
- negative, invalid, blocked, and inconclusive evidence to remain preserved.

Task 7 must now turn those requirements into one shared split-integrity
protocol.

## Decision

Propose adoption of `docs/mvp/07-initial-splits.md` as the initial governed MVP
split protocol.

The protocol will define exactly three partition roles:

- `DEVELOPMENT`;
- `VALIDATION`;
- `PROTECTED`.

Partition role describes how evidence may be used.

Scientific purpose is represented separately so one role vocabulary does not
become overloaded with research-specific meanings.

The initial governed partition-purpose vocabulary will be:

- `PRIMARY_OUTCOME`;
- `TRANSFER_SOURCE`;
- `TRANSFER_TARGET`;
- `ADAPTATION_INPUT`;
- `PRIOR_CAPABILITY`;
- `LOCALITY`;
- `CRITICAL_INVARIANT`.

The protocol will define governed identities for:

- `SplitPlan`;
- `SplitVersion`;
- `PartitionIdentity`;
- `EvaluationUnit`;
- `IndependenceGroup`;
- `SplitManifest`.

The protocol will also define:

- protected-evidence freeze and sealing;
- candidate freeze;
- authorized evaluation access;
- leakage and contamination rules;
- repeated protected-peeking restrictions;
- split invalidation and revision;
- Native `N-H1` independent-unit requirements;
- Native `N-H2` held-out family boundaries;
- Adaptive `A-H1` adaptation-input versus protected-evaluation separation;
- Adaptive `A-H2` paired pre/post/rollback evaluation;
- Task 5 capability-qualification split bindings;
- Task 8 baseline handoff;
- Task 9 resource and cost handoff.

Acceptance governs the split protocol.

Acceptance does not establish scientific support for `N-H1`, `N-H2`, `A-H1`,
or `A-H2`.

Acceptance does not promote any Task 5 capability to
`QUALIFIED_SUPPORTED`.

While this decision remains `PROPOSED`, it is not research implementation
authority.

## Alternatives Considered

### Separate Native and Adaptive split decisions

Rejected for the shared split-integrity layer.

Native and Adaptive hypotheses remain scientifically separate, but both
programs require the same foundational rules for:

- protected evidence;
- partition identity;
- contamination;
- leakage;
- historical preservation;
- candidate freeze;
- evaluator access.

Creating separate foundational protocols would allow incompatible meanings of
`PROTECTED`, leakage, or split invalidation.

Program-specific hypothesis bindings remain separate inside the shared
protocol.

### One generic train/test percentage split

Rejected.

The MVP spans agents, structured-data ML, and vision systems.

A universal percentage split does not define:

- system-level independence;
- held-out family transfer;
- protected outcome access;
- adaptation input;
- prior-capability retention;
- locality evaluation;
- rollback evaluation;
- independent verification.

Task 7 therefore governs evidence roles and identities rather than declaring
one arbitrary percentage valid for every environment.

### Reusing a protected split indefinitely

Rejected.

Once protected results have been exposed to a candidate-producing or tuning
process, those results are no longer fresh protected evidence for descendants
of that process.

Historical evidence remains preserved, but future consequential claims may
require a new protected partition or new `SplitVersion`.

### Allowing post-result repartitioning

Rejected.

A failed protected result must not be converted into `PASS` by moving examples,
changing unit boundaries, redefining independence, or replacing the protected
partition after inspecting outcomes.

## Evidence And Rationale

The existing qualified contracts establish that:

- protected criteria and partitions must be frozen before protected evidence;
- concrete split identities were explicitly deferred to Task 7;
- Task 5 support qualification must later reference preserved split evidence;
- `N-H1` requires at least two independent governed protected evaluation
  units;
- `N-H2` requires a protected held-out family or mechanism boundary without
  protected target-outcome tuning;
- `A-H1` requires protected adaptation evaluation distinct from the process
  performing adaptation;
- `A-H2` requires preserved pre-adaptation, post-adaptation, and post-rollback
  evidence;
- independent verification must remain meaningfully separated from candidate
  production;
- invalidated evidence must remain historically preserved.

A common split protocol is therefore required before governed experiments can
produce authoritative Task 6 scientific evidence.

## Assumptions

This decision assumes:

- concrete target `SystemVersion` identities will exist before a split is
  frozen for execution;
- data or evaluation-case provenance can be preserved;
- protected outcomes can be withheld from candidate-producing and tuning
  processes;
- evaluator access can be separated from candidate access;
- Task 8 will provide concrete baseline identities and versions;
- Task 9 will provide concrete resource and cost accounting where required;
- future execution infrastructure can preserve split and candidate provenance.

If these assumptions fail, an affected experiment may be `BLOCKED`,
`INVALID`, or require governed split revision.

## Consequences

If accepted:

- Task 7 becomes the governing source of split-role semantics;
- initial split identities are versioned and historically preserved;
- protected evidence gains an explicit lifecycle;
- contamination becomes an evidence-integrity event rather than an informal
  warning;
- repeated runs or resampling cannot manufacture independent evaluation units;
- Native transfer experiments must predeclare a held-out target boundary;
- Adaptive experiments must separate adaptation input from protected outcome
  access;
- later Task 5 capability qualification must reference applicable split
  identities;
- material data-partition changes require the governed DATA evidence
  consequence.

Acceptance does not manufacture experimental evidence.

## Risks And Constraints

Material risks include:

- small datasets may provide insufficient independent protected units;
- environment-specific datasets may require different physical partitioning
  techniques;
- strict sealing may increase evaluation infrastructure cost;
- protected data may accidentally leak through retrieval, prompts, logs,
  external tools, caches, derived labels, or human tuning;
- repeated iteration may exhaust fresh protected evidence;
- a nominally different partition may still be correlated with earlier
  evidence;
- transfer boundaries may be too weak if target information enters through
  onboarding;
- Adaptive paired evaluation may expose outcomes unless evaluator authority is
  carefully separated.

These risks are reasons to preserve explicit identity and contamination rules.

## Reversibility And Rollback

This decision is conditionally reversible through a governed successor using
the same Decision Key.

A material split-protocol change must not rewrite prior evidence in place.

The successor must preserve:

- the earlier decision;
- previous `SplitVersion` identities;
- previous partition membership;
- previous protected-access history;
- previous experiment results;
- previous invalidation status;
- the reason for the protocol change.

The minimum evidence consequence for a material DATA change is:

`RERUN_AND_PRESERVE_DATA_DISTINCTIONS`.

## Affected Contracts And Components

Affected artifacts include:

- `docs/mvp/07-initial-splits.md`;
- Task 5 capability-qualification manifests;
- Task 6 research experiment manifests;
- `GoalContract`;
- `SystemSnapshot`;
- `EvaluationRecord`;
- `VerificationReport`;
- `ExecutionRecord`;
- Artifact Graph provenance;
- Native research manifests;
- Adaptive research manifests;
- future Task 8 baseline bindings;
- future Task 9 resource bindings.

This decision does not change the Task 6 thesis definitions or numerical
scientific thresholds.

## Research Impact

Research Program:

`CROSS_PROGRAM`

Research Change Category:

`DATA`

Required Evidence Consequence:

`RERUN_AND_PRESERVE_DATA_DISTINCTIONS`

The split protocol affects the evidence partitions used by both Native and
Adaptive research.

Changing protected membership, independence boundaries, leakage semantics, or
partition meaning after scientific evidence exists may alter the meaning of
that evidence.

Therefore affected results must be rerun while preserving the distinction
between historical and revised data partitions.

## Qualification Requirement

Before acceptance, qualification must establish that the Task 7 specification:

- has explicit development, validation, and protected role semantics;
- separates role from research purpose;
- defines immutable versioned split identity;
- defines evaluation units and independence groups;
- prevents repeated runs or resampling from manufacturing independence;
- defines protected freeze, seal, evaluation, and preservation;
- defines contamination and invalidation;
- prevents protected-result tuning;
- governs Native held-out transfer;
- governs Adaptive input/evaluation separation;
- preserves pre/post/rollback evidence where required;
- retains Task 8 baseline ownership;
- retains Task 9 cost ownership;
- preserves Tasks 1 through 6 regressions;
- passes adversarial mutation qualification.

Acceptance of the split contract must not be represented as scientific support
for a Task 6 hypothesis.

## Implementation Evidence

Pending.

## Verification Evidence

Pending.

## Supersession

No predecessor.

No successor.

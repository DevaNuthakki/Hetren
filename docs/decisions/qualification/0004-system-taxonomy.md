# Decision 0004 Qualification Record

**Task:** `4 / 100`
**Decision:** `0004`
**Decision Key:** `architecture.system-taxonomy`
**Date:** `2026-09-17`
**Result:** `PASS`
**Qualification state:** `VERIFIED`
**Specification:** `docs/mvp/04-system-taxonomy.md`
**Specification version:** `1.0.0`
**Validator:** `scripts/check_system_taxonomy.py`
**Mutation suite:** `tests/qualification/test_system_taxonomy.py`
**Qualification conditions:** `50 / 50`
**Mutation result:** `34 / 34`
**Execution authority:** `AUTH-HETREN-MVP-3.0`
**Long-term authority:** `AUTH-HETREN-MASTER-2.0`
**Task 1 regression:** `PASS`
**Task 2 regression:** `PASS`
**Task 3 regression:** `PASS`
**Diff check:** `PASS`
**Final accepted-state qualification:** `PASS`

## Scope

This qualification evaluates the Task 4 governed MVP system taxonomy defined
by Decision 0004.

It covers target identity, immutable target versioning, system form,
environment-family classification, components, providers, adapters,
evaluators, investigation surfaces, Versioned System Graph semantics, tenant
isolation, historical identity, provenance boundaries, and governed taxonomy
evolution.

## Positive Qualification

PASS.

The development-state validator accepted the Task 4 specification while
Decision 0004 remained `PROPOSED` and non-authoritative.

The specification contains:

- 36 ordered numbered sections;
- 50 / 50 Task 4 qualification conditions;
- exactly five `SystemForm` values;
- exactly three initial `EnvironmentFamily` values;
- exactly two `InvestigationSurface` values;
- exactly eight governed graph relationships;
- explicit separation between taxonomy and Task 5 capability support;
- explicit separation between target identity and Hetren-side interaction or
  evaluation machinery;
- tenant-isolation and historical-provenance protections.

## Structural Qualification

PASS.

Qualification verified:

- canonical current authorities;
- exact specification metadata;
- exact 36-section topology;
- exact 50-condition qualification contract;
- exact `SystemForm` vocabulary;
- exact `EnvironmentFamily` vocabulary;
- exact investigation-surface vocabulary;
- exact Versioned System Graph relationship vocabulary;
- Decision 0004 identity and metadata;
- Decision 0004/register synchronization;
- separation of development and final qualification states.

## Semantic Qualification

PASS.

Qualification verified protections covering:

- stable tenant-scoped system identity;
- immutable `SystemVersion` and `ComponentVersion` semantics;
- material target changes requiring new applicable target versions;
- separation of `SystemForm` and `EnvironmentFamily`;
- truthful E1, E2, and E3 classification;
- governed future-family extension;
- target-component boundaries;
- provider identity and tenant-scoped provider binding;
- secret exclusion from taxonomy identity;
- adapter interaction semantics;
- evaluator measurement semantics;
- preservation of Task 3 outcome semantics;
- Behavioral and explicitly authorized Internal investigation;
- execution-time authorization for Internal access;
- shared-Core boundaries;
- Versioned System Graph validity and cardinality;
- `SystemSnapshot` remaining the canonical captured-state record;
- `CapabilityProfile` remaining the canonical capability-state record;
- Artifact Graph provenance remaining distinct from logical target identity;
- external-model outputs not becoming evidence merely because a model produced
  them;
- Native and Adaptive research not creating parallel Core, graph, evidence,
  permission, success, or verification systems;
- cross-tenant prohibitions;
- preservation of invalid, superseded, retired, negative, and corrected
  history;
- governed taxonomy evolution;
- explicit deferral of Tasks 5 through 9 concrete artifacts.

## Adversarial Qualification

PASS.

The Task 4 mutation suite rejected 34 / 34 tested violations.

The tested classes include:

- execution-authority drift;
- section-topology corruption;
- `SystemForm` expansion;
- `EnvironmentFamily` expansion;
- investigation-surface expansion;
- graph-relationship corruption;
- qualification-condition weakening;
- cross-tenant isolation weakening;
- mutable system versions;
- provider-driven environment classification;
- adapter-defined success;
- evaluator outcome-semantic redefinition;
- Internal-access authorization bypass;
- inferred Internal access;
- system graph treated as capability evidence;
- target provider changes no longer requiring target versioning;
- target classification synthesizing capability qualification;
- external-model output treated as evidence by default;
- provider control of Hetren Core semantics;
- parallel Native/Adaptive architecture;
- deletion of historical retirement state;
- forced E1 classification;
- Task 5 ownership leaking into Task 4;
- classification manufacturing support;
- Decision 0004 authority drift;
- Decision 0004/register inconsistency;
- missing qualification evidence;
- incomplete qualification-condition evidence;
- incomplete mutation qualification;
- non-VERIFIED qualification state;
- specification-version mismatch;
- pending implementation evidence;
- pending verification evidence;
- accepted-register inconsistency.

The suite also proved that a correctly constructed synthetic accepted state can
pass `--require-qualified`.

The mutation-suite cardinality is itself frozen at 34 so accidental deletion of
a test cannot silently reduce the required adversarial coverage.

## Authority And Regression Qualification

PASS.

Canonical authorities:

- `AUTH-HETREN-MVP-3.0`;
- `AUTH-HETREN-MASTER-2.0`.

Regression qualification preserved:

- Task 1 charter qualification: PASS;
- Task 2 decision-governance qualification: PASS;
- Task 2 mutation qualification: PASS, 44 / 44 mutations killed;
- Task 3 success-contract qualification: PASS;
- Task 3 mutation qualification: PASS;
- `git diff --check`: PASS.

No superseded authority was restored as active Task 4 authority.

## Limitations

This qualification establishes the governed system taxonomy and its
architectural boundaries.

It does not establish that:

- every taxonomy member is supported;
- any particular E1, E2, or E3 implementation is qualified;
- any concrete Task 5 capability combination is supported;
- a Native Intelligence hypothesis is true;
- an Adaptive Intelligence hypothesis is true;
- Task 6 research hypotheses are qualified;
- Task 7 data or evaluation splits are qualified;
- Task 8 baselines are qualified;
- Task 9 cost or effort ledgers are qualified;
- the complete Hetren MVP is finished.

Those claims remain governed by their respective later tasks and evidence.

## Acceptance Decision

Pre-acceptance qualification: PASS.

Decision 0004 transitioned from `PROPOSED` to `ACCEPTED` only after the
pre-acceptance structural, semantic, adversarial, authority-alignment,
mutation, and regression qualification passed.

The real accepted-state artifacts then passed
`python3 scripts/check_system_taxonomy.py --require-qualified` without
weakening the qualification criteria.

Final accepted-state qualification: PASS.

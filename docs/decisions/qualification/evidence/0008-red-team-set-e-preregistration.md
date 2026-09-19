# Decision 0008 Red-Team Set E Preregistration

**Task:** `7 / 100`

**Decision:** `0008`

**Date:** `2026-09-19`

**Evidence class:** `FROZEN_FINAL_UNSEEN_HOLDOUT`

**Execution count permitted as unseen evidence:** `1`

**Case count:** `32`

**Expected MUST_REJECT:** `16`

**Expected MUST_ACCEPT:** `16`

**Families:** `8`

**Cases per family:** `4`

**Cases per family MUST_REJECT:** `2`

**Cases per family MUST_ACCEPT:** `2`

## Purpose

Set E is the final preregistered unseen Task 7 qualification holdout.

Its purpose is to test whether the post-remediation Task 7 split-integrity
validator generalizes to new formulations and cross-invariant compositions
that were not executed against the validator before this preregistration.

Set E is governance-qualification evidence.

It is not scientific evidence for `N-H1`, `N-H2`, `A-H1`, or `A-H2`.

It does not promote any Task 5 capability to `QUALIFIED_SUPPORTED`.

## Freshness Definition

For Set E, `unseen` means that no Set E case definition has been executed
against `scripts/check_initial_splits.py` before the frozen Set E execution
package is created and verified.

No Set E case definition exists at the time of this preregistration.

The first execution is the only Set E execution that may be described as the
unseen first run.

Any later execution is regression evidence only.

A later successful result must never overwrite, replace, or reinterpret the
first-run result.

## Frozen Case Topology

Set E contains exactly 32 cases.

Each of the eight families contains exactly four cases:

- two `MUST_REJECT`;
- two `MUST_ACCEPT`.

Case identities are reserved as:

- `T7-E-01-01` through `T7-E-01-04`;
- `T7-E-02-01` through `T7-E-02-04`;
- `T7-E-03-01` through `T7-E-03-04`;
- `T7-E-04-01` through `T7-E-04-04`;
- `T7-E-05-01` through `T7-E-05-04`;
- `T7-E-06-01` through `T7-E-06-04`;
- `T7-E-07-01` through `T7-E-07-04`;
- `T7-E-08-01` through `T7-E-08-04`.

Within each family:

- cases `01` and `02` are `MUST_REJECT`;
- cases `03` and `04` are `MUST_ACCEPT`.

This expectation assignment is frozen before case wording is authored.

## Frozen Families

### E01 — Multi-Hop Protected Provenance

Tests whether protected or exposed evidence can be laundered through multiple
derived artifacts, summaries, wrappers, caches, or intermediate records before
being represented as fresh evidence.

The `MUST_ACCEPT` controls must preserve provenance through multi-hop
derivation without falsely prohibiting legitimate derived artifacts whose
freshness is not misrepresented.

### E02 — Temporal And Ordering Leakage

Tests whether timestamps, ordering, ranking, release sequence, or other
apparently non-outcome metadata can transmit protected-result information into
candidate selection or tuning.

The `MUST_ACCEPT` controls must permit ordinary chronology and deterministic
ordering when those signals do not encode protected outcomes.

### E03 — Cross-System Shared Ancestry

Tests whether different systems, environments, evaluators, or executions that
share material upstream ancestry are incorrectly counted as independent
evidence.

The `MUST_ACCEPT` controls must permit genuinely independent evidence merely
because systems share non-material infrastructure or governance machinery.

### E04 — Partial Disclosure And Threshold Probing

Tests whether coarse counts, threshold crossings, partial ranks, bounded
status signals, or repeated yes/no queries can be used to tune against
protected evidence.

The `MUST_ACCEPT` controls must permit reporting or disclosure that occurs
after candidate freeze and does not return to a candidate-producing path.

### E05 — Role/Purpose Authority Aliasing

Tests whether preserving the literal `PartitionRole` while using
`PartitionPurpose`, aliases, side channels, or operational labels can grant
authority prohibited for that role.

The `MUST_ACCEPT` controls must preserve the legitimate independence of the
role and purpose axes without treating ordinary cross-references as authority
escalation.

### E06 — Delegated Verification Control

Tests whether apparent verifier separation can be defeated through delegation,
shared orchestration, candidate-controlled evidence preparation, shared
decision authority, or indirect control chains.

The `MUST_ACCEPT` controls must permit shared neutral infrastructure when
candidate-producing authority cannot control consequential verification.

### E07 — Split Succession And Historical Forking

Tests whether a successor, fork, copied manifest, renamed split, or revised
partition can erase, bypass, or silently detach prior invalidation,
contamination, access, or result history.

The `MUST_ACCEPT` controls must permit legitimate new governed SplitVersions
while retaining required historical provenance and distinctions.

### E08 — Deferred Comparator/Resource Composition

Tests whether individually plausible baseline selection and resource-accounting
rules can compose into post-result gaming when one decision is deferred until
the other result is known.

The `MUST_ACCEPT` controls must permit legitimate precommitted comparator and
resource procedures that are independent of protected outcomes.

## Construction Rules

Case wording will be authored only after this preregistration is frozen.

Set E cases must not copy the exact wording of canonical, Set A, Set B, Set C,
Set D, or P1 cases.

Cases may test the same governed principles, but must use new formulations,
compositions, or boundary conditions.

Each `MUST_REJECT` case must contain one concrete prohibited permission or
relationship.

Each `MUST_ACCEPT` case must be valid under the Task 7 contract and must be
sufficiently unusual to detect over-broad rejection behavior.

A `MUST_ACCEPT` case must not be weakened merely to make the validator accept
it.

A `MUST_REJECT` case must not be strengthened merely to make the validator
reject it.

No case may be edited after the execution package is frozen and before the
first execution.

## Execution-Package Freeze

Before the first Set E execution, the following must exist and be frozen by
SHA-256:

- Set E case definitions;
- Set E JSON schema;
- Set E execution runner;
- this preregistration record.

The package manifest must be stored as:

`docs/decisions/qualification/evidence/0008-set-e-pre-run-freeze.sha256`

The package must verify successfully immediately before the first execution.

## First-Run Rule

Set E is executed exactly once as unseen evidence.

The raw first-run output must be persisted before any validator, case,
schema, runner, or Set E evidence modification.

The raw first-run result must be preserved regardless of whether the result is
perfect or contains false negatives or false positives.

## Remediation Rule

Any incorrect Set E disposition blocks Task 7 acceptance until the defect is
understood and a governed remediation is qualified.

Remediation must not modify the frozen Set E case definitions to improve the
score.

After the first execution, Set E becomes regression evidence.

Any remediation must rerun:

- all 52 development mutations;
- all 16 final-state mutations;
- P1;
- Set A;
- Set B;
- Set C;
- Set D;
- Set E;
- historical structured-data validation;
- historical data mutations;
- unified qualification-data validation;
- qualification-data mutations;
- repository diff validation.

No second unseen Task 7 holdout will be created merely because Set E exposes a
failure.

## Stop Rule

Set E is the final new Task 7 unseen holdout.

If the first run is `32 / 32`, no further unseen Task 7 holdout is generated.

If the first run is below `32 / 32`, its failures are preserved, remediation
may occur, and subsequent Set E runs are regression-only.

After remediation, Task 7 may proceed toward governance qualification only
when all frozen Set E cases and the complete Task 7 regression wall pass.

No additional fresh holdout may be generated to obtain a more favorable
score.

## Interpretation Rule

A perfect Set E first run would provide evidence that the current governance
validator generalized to this one preregistered unseen set.

It would not establish universal correctness.

A non-perfect Set E first run would identify additional validator or contract
gaps and would remain part of the permanent evidence record.

Neither outcome establishes scientific support for the Native or Adaptive
research hypotheses.

Neither outcome promotes Task 5 capability support.

## Evidence Integrity

The authoritative first-run result is the first execution performed after the
Set E package manifest is frozen and verified.

Reruns must be labeled as regression.

Historical failures, false positives, false negatives, remediation attempts,
and negative evidence must remain preserved.

Task 7 completion must not manufacture a stronger evidentiary claim than the
record supports.

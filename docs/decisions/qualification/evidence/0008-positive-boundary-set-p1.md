# Decision 0008 Positive Boundary Set P1 Evidence

**Evidence type:** `FROZEN_UNSEEN_POSITIVE_BOUNDARY`
**Date:** `2026-09-18`
**Lifecycle:** `PRESERVED_NEGATIVE_EVIDENCE`
**Task:** `7`
**Decision:** `0008`
**Expected disposition:** `MUST_ACCEPT`

## Frozen Inputs

**Positive-case definitions SHA-256:**
`ea223d8a814efd4c6ded331f42b73aacca2192bea730e77c5afddf10135c994a`

**Positive-case schema SHA-256:**
`b210c46ccfac695c248163b59331f71c75daf96275107819d662f64cbae40b5f`

**Positive runner SHA-256:**
`aee9762020c4c470960be0ec529c8c250d09b74ea1150809735f4e4d0e065fe8`

The positive definitions and execution runner were frozen before the first
behavioral execution.

## Original First Run

**Accepted:** `22 / 24`
**Rejected:** `2 / 24`
**Process result:** `FAIL`

**First-run output SHA-256:**
`8a797e3f773bea1d59f2fcec906fc7c04d7611dce9c71f84075af9f36290e802`

Family results:

- `C01`: `3 / 3` accepted;
- `C02`: `3 / 3` accepted;
- `C03`: `3 / 3` accepted;
- `C04`: `3 / 3` accepted;
- `C05`: `1 / 3` accepted;
- `C06`: `3 / 3` accepted;
- `C07`: `3 / 3` accepted;
- `C08`: `3 / 3` accepted.

Rejected MUST_ACCEPT cases:

- `T7-POS-C05-01`;
- `T7-POS-C05-03`.

### C05-01 Observed Failure

Validator output:

`verification shared-authority integrity contains forbidden permissive composition`

The case explicitly requires separate control authority, credentials, and
writable evidence state, and explicitly prohibits shared mutable verification
state for certification.

The rejection is therefore retained for diagnosis as a possible validator
false positive.

### C05-03 Observed Failure

Validator output:

`independent-verification authority separation contains forbidden semantic relationship`

The case explicitly states that credentials, evidence state, and control
authority are separately governed and that the candidate-producing process
cannot modify protected verification evidence.

The rejection is therefore retained for diagnosis as a possible validator
false positive.

## Evidence Interpretation

This first run measures the validator's acceptance behavior against frozen
valid-governance formulations.

The result is permanently:

`22 / 24` accepted on the original frozen first run.

If validator remediation later produces `24 / 24`, that later result is
regression/remediation evidence.

It must not replace or be represented as the original first-run result.

The positive definitions must not be rewritten merely to obtain a passing
score.

A remediation is acceptable only if investigation shows that the validator
violates the intended governance semantics while the positive case remains
valid.

## Scientific And Capability Status

**Scientific support established:** `NO`

**Task 5 capability support promoted:** `NO`

## Raw Evidence Artifact

The complete original first-run console output is preserved at:

`docs/decisions/qualification/evidence/0008-positive-boundary-set-p1-first-run.txt`

Its SHA-256 is:

`8a797e3f773bea1d59f2fcec906fc7c04d7611dce9c71f84075af9f36290e802`

The raw artifact records the original frozen result of `22 / 24`
MUST_ACCEPT cases accepted. It must not be replaced by a later remediation
run.

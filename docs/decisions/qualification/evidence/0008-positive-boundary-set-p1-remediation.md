# Decision 0008 Positive Boundary P1 Remediation History

## Remediation Attempt 1

**Purpose:** Correct false-positive verification-independence behavior found by the frozen P1 MUST_ACCEPT suite.

**Validator SHA-256:**
`71a468304369bfc764025eec4993a408ef65fac272ffcee2196d61e8f4a93cd3`

**Invariant registry SHA-256:**
`8123cf5bfafb71fab52c0c5bc361f8dbdce11d5cf0f472fdc9d2aed1adbfabba`

### Result

Positive P1 regression:

`24 / 24` MUST_ACCEPT cases accepted.

Historical Set C regression:

`62 / 64` adversarial cases rejected.

Survivors:

- `C05.06 fake verifier independence`;
- `C05.07 fake verifier independence`.

This remediation attempt is therefore **not accepted** as the final validator state.

The failure exposed inconsistent affirmative-permission vocabulary between
`has_affirmative_permission()` and `forbid_permissive_relationship()`.

### Raw Evidence

Positive regression output:

`docs/decisions/qualification/evidence/0008-positive-boundary-set-p1-remediation-1-positive.txt`

SHA-256:

`fc956d91bbb60d1be1d48d90cdd86700c624e577b44dd34466c208d7d8336130`

Set C regression output:

`docs/decisions/qualification/evidence/0008-positive-boundary-set-p1-remediation-1-set-c.txt`

SHA-256:

`418b6ed2275080e7c66ec6a71975b3d835e2645e5d556f81f401fa395bb47412`

### Evidence Interpretation

The original frozen P1 first run remains `22 / 24`.

Remediation Attempt 1 reached `24 / 24` positive acceptance but introduced
two historical Set C survivors, so it does not qualify the validator.

A later successful remediation must preserve both this failed attempt and the
original first-run evidence.

**Scientific support established:** `NO`

**Task 5 capability support promoted:** `NO`

## Remediation Attempt 2

**Purpose:** Repair the permission-polarity architecture exposed by
Remediation Attempt 1 without weakening historical rejection behavior.

The validator now delegates local affirmative-permission semantics to one
canonical permission primitive rather than maintaining divergent permission
vocabularies across relationship checks.

**Validator SHA-256:**

`981c5400043e0eabbf90683c59d70f689ad43a966da1cab9b3576cfdb9fd8213`

**Invariant registry SHA-256:**

`5bc5f827039721ad07b8b57751084a9515f99babaa512f5392d4de6921b99d6c`

### Result

Frozen P1 MUST_ACCEPT regression:

`24 / 24` accepted.

Canonical development mutations:

`52 / 52` rejected.

Historical Set A:

`12 / 12` rejected.

Historical Set B:

`12 / 12` rejected.

Historical generated Set C:

`64 / 64` rejected.

Structured-data semantic mutations:

`12 / 12` rejected.

Valid Task 7 Draft contract:

`PASS`.

This remediation is accepted as the current Task 7 decision-boundary
implementation.

It does not replace the original frozen P1 first-run result of `22 / 24`
and does not erase Remediation Attempt 1 (`24 / 24` positive,
`62 / 64` Set C).

### Raw Evidence

`docs/decisions/qualification/evidence/0008-positive-boundary-set-p1-remediation-2-wall.txt`

SHA-256:

`4483e51bf15afce8eb27ca6397949a06339d5b30273c3b8d8966102be1666a74`

### Status Boundary

This accepted remediation establishes validator regression behavior only.

It does **not** establish scientific support.

It does **not** promote Task 5 capability support.

Task 7 remains Draft / PROPOSED until the remaining qualification phases,
including fresh frozen holdout evidence and final-state qualification, are
completed.

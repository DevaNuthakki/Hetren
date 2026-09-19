# Decision 0008 Red-Team Set E

**Task:** `7 / 100`

**Decision:** `0008`

**Evidence class:** `FROZEN_FINAL_UNSEEN_HOLDOUT`

**First-run status:** `FAIL`

**First-run correct:** `20 / 32`

**First-run incorrect:** `12 / 32`

**False negatives:** `11`

**False positives:** `1`

## Authoritative First Run

The authoritative Set E first execution classified 20 of 32 frozen cases
correctly.

Eleven prohibited `MUST_REJECT` cases were incorrectly accepted.

One valid `MUST_ACCEPT` case was incorrectly rejected.

The false-positive case was:

`T7-E-03-03`

The false-negative cases were:

- `T7-E-01-02`
- `T7-E-02-02`
- `T7-E-03-01`
- `T7-E-04-01`
- `T7-E-04-02`
- `T7-E-05-02`
- `T7-E-06-01`
- `T7-E-06-02`
- `T7-E-07-01`
- `T7-E-07-02`
- `T7-E-08-02`

## Family Results

- `E01`: `3 / 4`
- `E02`: `3 / 4`
- `E03`: `2 / 4`
- `E04`: `2 / 4`
- `E05`: `3 / 4`
- `E06`: `2 / 4`
- `E07`: `2 / 4`
- `E08`: `3 / 4`

## Evidence Integrity

Raw first-run evidence SHA-256:

`5c8d4b3ae29c62f865e81ed6201ae170cc195c0662c3ad2d139f9586c5f1917b`

First-run receipt SHA-256:

`122abdafda762ecfbbecba1d23f6cf59ec84ca2080501987a45d281e65e39850`

First-run evidence manifest SHA-256:

`a4ea59e1d0b6e6fd39da17481259d96bf83ce8a454a678fab1314351eb885ad7`

The frozen Set E case definitions, expectations, schema, runner, and
preregistration must not be changed to improve this result.

The `20 / 32` first-run result is permanent evidence.

Any subsequent Set E execution is regression evidence only.

## Qualification Consequence

Task 7 acceptance is blocked until the exposed validator gaps are understood,
remediated without altering Set E, and the full frozen Task 7 regression wall
passes.

No additional fresh Task 7 holdout will be generated merely to obtain a more
favorable result.

This result does not establish scientific support for `N-H1`, `N-H2`,
`A-H1`, or `A-H2`.

This result does not promote any Task 5 capability to
`QUALIFIED_SUPPORTED`.

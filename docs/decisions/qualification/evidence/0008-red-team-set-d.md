# Decision 0008 Red-Team Set D Evidence

**Task:** `7`

**Decision:** `0008`

**Evidence class:** `FROZEN_FRESH_HOLDOUT`

**Original execution status:** `FAIL`

## Preregistered Design

Set D was frozen before execution with:

- `8` semantic families;
- `32` total cases;
- `16` `MUST_REJECT` cases;
- `16` `MUST_ACCEPT` cases;
- required first-run acceptance: `32 / 32` correct.

The Task 7 validator and all pre-existing qualification evidence were frozen
before Set D was authored and remained byte-identical through the original
execution.

## Original First-Run Result

**Correct:** `21 / 32`

**Incorrect:** `11 / 32`

**Original fresh-holdout result:** `FAIL`

Family results:

- `D01`: `2 / 4`
- `D02`: `4 / 4`
- `D03`: `4 / 4`
- `D04`: `3 / 4`
- `D05`: `2 / 4`
- `D06`: `2 / 4`
- `D07`: `2 / 4`
- `D08`: `2 / 4`

Incorrect cases:

- `T7-D-01-01` expected `MUST_REJECT`
- `T7-D-01-02` expected `MUST_REJECT`
- `T7-D-04-02` expected `MUST_REJECT`
- `T7-D-05-01` expected `MUST_REJECT`
- `T7-D-05-04` expected `MUST_ACCEPT`
- `T7-D-06-01` expected `MUST_REJECT`
- `T7-D-06-02` expected `MUST_REJECT`
- `T7-D-07-01` expected `MUST_REJECT`
- `T7-D-07-02` expected `MUST_REJECT`
- `T7-D-08-01` expected `MUST_REJECT`
- `T7-D-08-02` expected `MUST_REJECT`

The result therefore contains:

- `10` false-negative classifications where invalid governance text was accepted;
- `1` false-positive classification where valid governance text was rejected.

## Raw Evidence

Original first-run output:

`docs/decisions/qualification/evidence/0008-red-team-set-d-first-run.txt`

SHA-256:

`aa4464b926519558970404ad673628a7ea1bff8ada4088c70a8d109af313026f`

Frozen Set D pre-run manifest:

`docs/decisions/qualification/evidence/0008-set-d-pre-run-freeze.sha256`

SHA-256:

`9a32f835f7e437d2aadffce67fe72fa8408d7630fedb3ca7d7dd41f7e379c172`

## Evidence Integrity

Set D must no longer be described as unseen after this first execution.

Any later Set D result is regression or remediation evidence only.

The original `21 / 32` result must remain preserved even if later remediation
reaches `32 / 32`.

Set D definitions must not be rewritten merely to improve the observed score.

Validator remediation is permitted only after diagnosis identifies a genuine
governance invariant that the current implementation fails to enforce or
incorrectly rejects.

## Status Boundary

This Set D result does not establish scientific support.

It does not promote Task 5 capability support.

It does not qualify Decision 0008.

Task 7 remains Draft / PROPOSED.

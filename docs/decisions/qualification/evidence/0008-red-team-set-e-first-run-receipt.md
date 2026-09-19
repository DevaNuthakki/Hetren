# Decision 0008 Set E First-Run Receipt

**Task:** `7`

**Decision:** `0008`

**Evidence class:** `FROZEN_FINAL_UNSEEN_HOLDOUT`

**Execution:** `AUTHORITATIVE FIRST RUN`

**Runner return code:** `1`

## Frozen Inputs

Pre-run package manifest SHA-256:

`e2efaa1991a17c99b03a8c12918897951f6caef60cecab17c9c09f19aac0e8c9`

Runner SHA-256:

`d6c5e2d4e6cbf1c6f8ebc82d4354bf430bce3e40e40056ba0362b69633494649`

## Raw Evidence

Raw output:

`docs/decisions/qualification/evidence/0008-red-team-set-e-first-run.txt`

Raw output SHA-256:

`5c8d4b3ae29c62f865e81ed6201ae170cc195c0662c3ad2d139f9586c5f1917b`

## Interpretation Constraint

This receipt records the first and only Set E execution that may be
interpreted as unseen-to-validator-execution evidence.

The raw result is authoritative regardless of whether it passes or fails.

Any subsequent Set E execution is regression evidence only.

This result does not establish scientific support and does not promote
Task 5 capability support.

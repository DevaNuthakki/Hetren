# Decision 0008 Set E Pre-Run Package Attempt 1

**Task:** `7`

**Decision:** `0008`

**Status:** `INVALID PRE-RUN PACKAGE`

## Result

Set E package construction completed, but static schema validation failed before
any Set E execution occurred.

The case dataset declared:

`FROZEN_FINAL_UNSEEN_HOLDOUT`

The derived schema incorrectly retained the Set D evidence-class constant:

`FROZEN_FRESH_HOLDOUT`

Therefore this package freeze is not an authoritative Set E execution package.

## Execution State

Set E execution count:

`0`

No Set E case has been executed against the validator.

Set E unseen first-run eligibility remains intact.

## Attempt 1 Hashes

Preregistration:

`70648792df030297ba998b83bebe9e417b4bbbfa31d7d9933871ac15d000fd94`

Cases:

`1e51bd3ba1eb3436a3812cc93973c3a9cd7c21df25c587ac916c83f9a967f3ae`

Invalid schema:

`b161d8a33d3a01ad7b39e4a4b19dd369e4d97607b3cfb00620791693f9ae4a36`

Runner:

`d6c5e2d4e6cbf1c6f8ebc82d4354bf430bce3e40e40056ba0362b69633494649`

Attempt 1 manifest:

`91abea694cefebbd1075ad82cc2dd7f080a83feac520e2cfc10b044c28425ecd`

## Preservation Rule

The invalid schema and original Attempt 1 manifest are preserved.

The Set E cases, case expectations, case wording, and runner must not be
modified to repair this construction error.

Only the schema contract necessary to represent the already-preregistered
`FROZEN_FINAL_UNSEEN_HOLDOUT` evidence class may be corrected before the
authoritative pre-run package is frozen.

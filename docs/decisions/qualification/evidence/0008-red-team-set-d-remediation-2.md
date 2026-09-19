# Decision 0008 Set D Remediation Attempt 2

**Task:** `7`

**Decision:** `0008`

**Status:** `ACCEPTED REMEDIATION BOUNDARY`

## Historical Evidence Chain

Original frozen Set D first run:

`21 / 32` correct.

That result remains the only genuine fresh Set D result.

Remediation Attempt 1:

`31 / 32` Set D regression, while Set B regressed to `11 / 12`
and Set C regressed to `56 / 64`.

Remediation Attempt 1 therefore remains preserved as failed.

Remediation Attempt 2:

- P1 MUST_ACCEPT: `24 / 24`
- canonical development mutations: `52 / 52`
- Set A: `12 / 12`
- Set B: `12 / 12`
- Set C: `64 / 64`
- Set D regression: `32 / 32`
- data semantic mutations: `12 / 12`
- structured-data validation: `PASS`
- Draft Task 7 contract: `PASS`

Remediation Attempt 2 is accepted as the current regression boundary.

## Governed Implementation

Validator SHA-256:

`4c796414ee3f8a2ef12d6078d8217401f254d4e557d1349fe5a6d992f24b55cf`

Invariant registry SHA-256:

`cd290c1a4d08026abdad4578ae94f55ff453fc0aea5af0ac35046769e10125b5`

Raw remediation wall:

`docs/decisions/qualification/evidence/0008-red-team-set-d-remediation-2-wall.txt`

Raw wall SHA-256:

`5d3bf4786f8841f8a05d4275746bc096cd6c4624f73610898d3bfa360beeea11`

## Evidence Interpretation

The `32 / 32` Set D result is remediation/regression evidence only.

It does not replace or upgrade the original fresh Set D result of `21 / 32`.

Set D definitions remain frozen and unchanged.

Remediation Attempt 1 and all earlier failed evidence remain preserved.

This remediation does not establish scientific support.

This remediation does not promote Task 5 capability support.

Decision 0008 and Task 7 remain Draft / PROPOSED pending final
qualification and independent verification.

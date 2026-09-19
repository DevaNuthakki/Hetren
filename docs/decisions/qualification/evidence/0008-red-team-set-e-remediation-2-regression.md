# Decision 0008 Set E Remediation Attempt 2 Regression

**Task:** `7`

**Decision:** `0008`

**Evidence class:** `REGRESSION_ONLY`

**Remediation candidate:** `ATTEMPT_2`

**Regression result:** `PASS`

**Correct:** `32 / 32`

**Incorrect:** `0 / 32`

**Runner return code:** `0`

## Interpretation

This execution occurred only after the authoritative Set E first run had been
completed, preserved, interpreted, and used to drive remediation.

Therefore this execution is regression evidence only.

It is not fresh evidence.

It is not unseen evidence.

It does not replace or revise the authoritative Set E first-run result of:

`20 / 32`

## Frozen Inputs

Set E runner SHA-256:

`d6c5e2d4e6cbf1c6f8ebc82d4354bf430bce3e40e40056ba0362b69633494649`

Remediation Attempt 2 manifest SHA-256:

`b4a2734376c5f5033f8a49cfce74fc5ed6516f5bd75a6175414fdb3d3480d094`

## Regression Output

Raw regression evidence:

`docs/decisions/qualification/evidence/0008-red-team-set-e-remediation-2-regression.txt`

Raw regression SHA-256:

`70dca74b66e7655692e457277d5975081a2278e0dad8040fd0d0018e13d8c4f4`

## Scientific Interpretation

A passing regression result demonstrates that the current validator correctly
classifies this already-known frozen Set E case set after remediation.

It does not establish universal validator correctness.

It does not establish scientific support for `N-H1`, `N-H2`, `A-H1`, or
`A-H2`.

It does not promote Task 5 capability support.

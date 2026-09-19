# Decision 0008 Set E Remediation Attempt 1

**Task:** `7`

**Decision:** `0008`

**Status:** `FAILED REGRESSION GATE`

## Purpose

This attempt remediated semantic gaps discovered by the authoritative Set E
first run while preserving all frozen Set E artifacts.

## Results

- Post-Set-E known regression suite: `13 / 13 PASS`.
- Frozen development mutations: `52 / 52 PASS`.
- Frozen final-state mutations: `16 / 16 PASS`.
- Frozen canonical total: `68 / 68 PASS`.
- Frozen 52-development attack-definition identity: unchanged.
- P1 MUST_ACCEPT suite: `24 / 24 PASS`.
- Set A regression: `12 / 12 PASS`.
- Set B regression: `12 / 12 PASS`.
- Set C regression: `64 / 64 PASS`.
- Set D regression: `31 / 32`.
- Set D failing case: `T7-D-05-02`.
- Historical structured-data validation: PASS.
- Historical data mutations: `14 / 14 PASS`.
- Unified qualification registry: `196 / 196 PASS`.
- Qualification-data mutations: `18 / 18 PASS`.

## Root Cause

`T7-D-05-02` remained a valid MUST_REJECT case.

Its permission-bearing clause contains:

- protected target evidence;
- incident-severity class;
- selection;
- transfer mechanisms.

The remediated `N-H2 proxy-outcome leakage integrity` pattern recognized
`mechanism` but not plural `mechanisms`.

The `provided` semantic-clause boundary is not the cause of this regression.
It correctly separates the trailing statement that individual protected
outcomes are not disclosed from the earlier affirmative permission.

## Consequence

Attempt 1 is rejected as a complete remediation because an established Set D
regression survived.

The next correction may broaden only the governed actor/object vocabulary
needed to treat singular and plural method, mechanism, and candidate forms
symmetrically.

The frozen Set E definitions and authoritative first-run result remain
unchanged.

Set E must not be interpreted as fresh again.

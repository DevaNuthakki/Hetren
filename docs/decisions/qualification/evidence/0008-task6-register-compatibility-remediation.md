# Task 6 Decision-Register Compatibility Remediation

**Triggered by:** Task 7 post-acceptance CI-candidate Wall Attempt 1

**Result:** `PASS`

## Failure Exposed

Task 6 previously required the shared Decision Register to remain exactly:

`1.5.0`

Task 7 legitimately advanced that shared register to:

`1.6.0`

The original Tasks 1–7 integration wall therefore failed even though the
Task 6 Decision 0006 / 0007 semantics themselves remained valid.

## Remediation

Task 6 now requires:

- a syntactically valid semantic register version; and
- a minimum compatible register version of `1.5.0`.

It no longer requires the shared register to remain permanently frozen at
exactly `1.5.0`.

Decision 0006 and Decision 0007 identity, status, record paths, authority,
qualification records, and lifecycle synchronization remain independently
validated by the existing Task 6 validator.

Global decision-register validity remains independently enforced by
`scripts/check_decision_register.py`.

## Compatibility Regression

The permanent regression test is:

`tests/qualification/test_research_hypotheses_register_compatibility.py`

It verifies:

- `1.5.0` accepted;
- `1.6.0` accepted;
- `1.7.0` accepted;
- `2.0.0` accepted;
- `1.4.9` rejected;
- malformed semantic version rejected.

## Frozen Qualification Integrity

The pre-existing Task 6 mutation qualification remains:

`52 / 52`

This remediation does not rewrite that historical cardinality.

Decision-governance mutation qualification remains:

`44 / 44`

Task 7 remained `Qualified / ACCEPTED`.

Set E was not executed.

## Byte Identity

Pre-remediation validator SHA-256:

`21eaf645cef0c8f0fb4a7a519d63d904044c5e0c034ce230b2522b9f5eb1f70c`

Post-remediation validator SHA-256:

`4be8405cfdcc03373d294443de42589f798b99013de9f288dda6ba200ef62283`

Compatibility regression SHA-256:

`5604f89375c6b69081c1f0dd32e4e05fffb0535a66521059fedde3f03c534714`

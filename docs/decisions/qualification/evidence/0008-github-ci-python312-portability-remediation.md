# Decision 0008 GitHub CI Python 3.12 Portability Remediation

**Task:** `7`

**Decision:** `0008`

**Trigger commit:** `30689f0151e49242cf44c570b33afb341eb6ab0e`

**Result:** `REMEDIATED LOCALLY / REMOTE REVERIFICATION PENDING`

## Failure

The first GitHub Actions execution of the Task 7 branch passed the primary
initial-splits validator and failed during historical structured-data
validation under Python 3.12.

The failure was reproduced from the exact pushed commit in an isolated tree
using Python 3.12 with the CI dependency contract.

## Root Cause

The canonical 52-development-mutation fingerprint relied directly on
`ast.dump()` output.

For identical source:

- Python 3.12 produced
  `ebdb5d3e628210cf5c4e10a55cce89a87211baba43c2fd0da41d9a6363def333`;
- Python 3.13 produced the historical canonical identity
  `f86429996ed383358f3bc30b0875db32b812bcfcb6c76f6692bc68ce0a9d9560`.

The difference was serialization of empty AST list fields, not a change to the
52 governed mutation definitions.

## Remediation

The fingerprint implementation now normalizes only empty-list AST fields
before serialization.

Semantic AST values, including `None`, remain preserved.

Python 3.12 and Python 3.13 now both produce the original historical canonical
identity:

`f86429996ed383358f3bc30b0875db32b812bcfcb6c76f6692bc68ce0a9d9560`

The historical structured-data record was not rewritten.

## Regression

A dedicated fingerprint-portability regression verifies the canonical identity
and explicitly protects the Python 3.12 failure mode.

## Evidence Integrity

The original Task 7 completion boundary remains historical evidence for commit
`30689f0`; it is not rewritten.

Set E was not executed as part of this remediation.

The authoritative unseen Set E result remains `20 / 32`.

The later `32 / 32` Set E result remains regression evidence only.

## Completion State

Task 7 is temporarily treated as `IN_PROGRESS` until the remediated branch
passes the complete local Python 3.12 wall and GitHub Actions.

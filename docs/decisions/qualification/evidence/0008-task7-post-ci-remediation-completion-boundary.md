# Decision 0008 Post-CI-Remediation Completion Boundary

**Task:** `7`

**Decision:** `0008`

**Branch:** `feature/mvp-initial-splits-v1`

**Base Task 7 commit:** `30689f0151e49242cf44c570b33afb341eb6ab0e`

**Local state:** `QUALIFIED`

**Remote state:** `GITHUB ACTIONS REVERIFICATION PENDING`

## Purpose

This boundary freezes the locally qualified Task 7 state after remediation of
the Python 3.12 fingerprint-portability defect exposed by the first GitHub
Actions run.

The original Task 7 completion boundary remains preserved as historical
evidence for the pre-remediation commit and is not rewritten.

## GitHub CI Failure

The first remote CI execution passed the primary initial-splits validator and
failed during historical structured-data validation under Python 3.12.

The failure was reproduced from the exact pushed commit.

## Root Cause

The canonical development-attack fingerprint depended directly on
`ast.dump()` presentation.

Identical mutation definitions produced:

- Python 3.12:
  `ebdb5d3e628210cf5c4e10a55cce89a87211baba43c2fd0da41d9a6363def333`
- historical canonical identity:
  `f86429996ed383358f3bc30b0875db32b812bcfcb6c76f6692bc68ce0a9d9560`

The difference came from interpreter-specific serialization of empty AST list
fields, not from mutation-definition drift.

## Remediation

The fingerprint implementation now normalizes only empty-list AST fields
before serialization.

The historical structured-data identity was not rewritten.

Python 3.12 and Python 3.13 both produce:

`f86429996ed383358f3bc30b0875db32b812bcfcb6c76f6692bc68ce0a9d9560`

A dedicated portability regression is now part of CI.

## Integrated Qualification

The complete Tasks 1 through 7 wall passed under the Python 3.12 CI runtime.

Python 3.13 independently passed the portability regression and historical
structured-data checker.

## Set E Integrity

Set E was not executed during this remediation or requalification.

The only genuinely unseen Set E first run remains `20 / 32`.

The later unchanged Set E execution remains regression evidence at `32 / 32`
and must not be reinterpreted as fresh holdout evidence.

## Scientific Boundary

This engineering qualification does not establish scientific support for
`N-H1`, `N-H2`, `A-H1`, or `A-H2`.

It does not promote any Task 5 capability to `QUALIFIED_SUPPORTED`.

## Completion Interpretation

This boundary establishes the local post-remediation completion candidate.

Task 7 remains `IN_PROGRESS` in the private build ledger until the repaired
commit passes GitHub Actions.

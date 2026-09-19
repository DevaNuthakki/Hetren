# Decision 0008 Qualification Record

**Task:** `7 / 100`
**Decision:** `0008`
**Decision Key:** `research.evaluation.initial-splits`
**Date:** `2026-09-18`
**Result:** `PASS`
**Qualification state:** `VERIFIED`
**Specification:** `docs/mvp/07-initial-splits.md`
**Specification version:** `1.0.0`
**Validator:** `scripts/check_initial_splits.py`
**Mutation suite:** `tests/qualification/test_initial_splits.py`
**Qualification conditions:** `50 / 50`
**Mutation result:** `68 / 68`
**Execution authority:** `AUTH-HETREN-MVP-3.0`
**Long-term authority:** `AUTH-HETREN-MASTER-2.0`
**Task 1 regression:** `PASS`
**Task 2 regression:** `PASS`
**Task 3 regression:** `PASS`
**Task 4 regression:** `PASS`
**Task 5 regression:** `PASS`
**Task 6 regression:** `PASS`
**Diff check:** `PASS`
**Scientific support established:** `NO`
**Task 5 capability support promoted:** `NO`
**Final accepted-state qualification:** `PASS`

## Scope

This record is the real repository qualification record for Task 7 and
Decision 0008.

It records qualification of the governed initial-splits protocol against the
preserved Task 7 validation, mutation, structured-evidence, and regression
corpus.

It does not establish scientific support and does not promote any Task 5
capability to `QUALIFIED_SUPPORTED`.

## Positive Qualification

PASS.

The Task 7 specification contains exactly 50 governed numbered sections and
exactly 50 ordered Task 7 qualification conditions.

## Adversarial Qualification

PASS.

The frozen Task 7 mutation target is `68 / 68`:

- `52 / 52` development-state mutations;
- `16 / 16` final accepted-state mutations.

## Authority And Regression Qualification

PASS.

Tasks 1 through 6 regression qualification: PASS.

Development-state qualification: PASS.

Final accepted-state qualification: PASS.

## Evidence Interpretation

The original frozen P1 first run remains `22 / 24`.

The original frozen Set D first run remains `21 / 32`.

Later remediation and regression success do not rewrite those original
first-run results.

Scientific support established: `NO`.

Task 5 capability support promoted: `NO`.

## Governed Evidence Integrity

PASS.

This is the real repository qualification record for Decision 0008.

The accepted lifecycle state is backed by the preserved Task 7 evidence
chain rather than by the synthetic final-state fixture alone.

The governed pre-lifecycle full wall is preserved at:

- `docs/decisions/qualification/evidence/0008-task7-pre-lifecycle-full-wall.txt`;
- `docs/decisions/qualification/evidence/0008-task7-pre-lifecycle-full-wall.md`;
- `docs/decisions/qualification/evidence/0008-task7-pre-lifecycle-full-wall.sha256`.

The unified structured qualification registry is schema version `1.1.0` and
contains `241` governed cases:

- `181 MUST_REJECT`;
- `60 MUST_ACCEPT`;
- current governed disposition correctness: `241 / 241`;
- qualification-data mutation qualification: `26 / 26`.

The post-Set-E known-regression suite contains `13` cases and is classified
as known regression evidence, not unseen evidence.

### Set E Historical Integrity

The authoritative Set E unseen first run remains permanently:

`20 / 32`

That first run produced `12` incorrect dispositions and was preserved before
remediation.

The remediated validator later classified the same frozen Set E package:

`32 / 32`

That later execution is regression evidence only.

It is not fresh evidence.

It is not unseen evidence.

It does not replace, erase, or revise the authoritative `20 / 32` first-run
result.

The corresponding evidence is preserved by:

- `0008-set-e-first-run-evidence.sha256`;
- `0008-red-team-set-e.md`;
- `0008-set-e-remediation-attempt-2.sha256`;
- `0008-set-e-remediation-2-regression-evidence.sha256`;
- `0008-post-241-qualification-data-boundary.sha256`.

No new Set E execution was performed during this lifecycle transition.

### Scientific And Capability Boundary

Task 7 qualification accepts the governed split protocol.

It does not establish scientific support for `N-H1`, `N-H2`, `A-H1`, or
`A-H2`.

It does not manufacture an experimental `PASS`.

It does not promote any Task 5 capability to `QUALIFIED_SUPPORTED`.

Tasks 8 and 9 retain baseline and cost/resource ownership.

## Acceptance Decision

Decision 0008 is `ACCEPTED`.

The Task 7 initial-splits specification is version `1.0.0` and `Qualified`.

Final accepted-state qualification: PASS.

# Decision 0008 Set D Preregistration

**Task:** `7`

**Decision:** `0008`

**Evidence class:** `FROZEN_FRESH_HOLDOUT`

**Execution status:** `NOT RUN`

## Frozen Design

Set D contains:

- `8` semantic families;
- `4` cases per family;
- `32` total cases;
- `16` `MUST_REJECT` cases;
- `16` `MUST_ACCEPT` cases.

The eight preregistered families are:

1. `D01 INDIRECT_PROTECTED_LINEAGE`
2. `D02 SPLIT_REFERENCE_REBINDING`
3. `D03 OPERATIONAL_CONTAMINATION_EXCEPTION`
4. `D04 HIDDEN_PSEUDOREPLICATION`
5. `D05 TARGET_EVALUATOR_SELECTION_PROXY`
6. `D06 DELEGATED_VERIFICATION_AUTHORITY`
7. `D07 DISTRIBUTED_DATA_RERUN_WAIVER`
8. `D08 POST_RESULT_ACCOUNTING_AND_COMPARATOR_DRIFT`

## Acceptance Criterion

The original frozen Set D execution passes only if all `32 / 32`
classifications are correct.

Every `MUST_REJECT` case must be rejected.

Every `MUST_ACCEPT` case must be accepted.

No partial score is considered a passing Set D result.

Any first-run miss must be preserved before validator remediation.

The Set D definitions must not be rewritten merely to improve the result.

## Freshness Boundary

Set D was authored only after
`0008-post-remediation-boundary.sha256`
was created and verified.

No file covered by that boundary manifest may be modified before the
first Set D execution.

Set D does not establish scientific support or Task 5 capability support.

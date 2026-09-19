# Decision 0008 Post-Acceptance CI-Candidate Wall — Attempt 1

**Task:** `7`

**Decision:** `0008`

**Result:** `FAIL`

**Evidence class:** `INTEGRATION_REGRESSION`

## Failure

The Tasks 1–7 accepted-state wall exposed a Task 6 compatibility failure.

Both of the following returned nonzero:

- `TASK 6 RESEARCH HYPOTHESES`
- `TASK 6 RESEARCH HYPOTHESIS MUTATIONS`

The reported reason was:

`decision register Version must be 1.5.0 for Task 6`

## Task 7 State

Task 7 itself remained green during this failed integration attempt.

Observed successful Task 7 checks included:

- qualified-state gate;
- historical structured data;
- 14 / 14 historical-data mutations;
- unified 241-case qualification data;
- 26 / 26 qualification-data mutations;
- 68 / 68 Task 7 mutations;
- P1 regression;
- Sets A through D regressions;
- 13 / 13 post-Set-E known regressions.

## Set E Integrity

Set E was not executed in this wall.

The authoritative unseen first run remains `20 / 32`.

The remediated `32 / 32` result remains regression evidence only.

## Interpretation

This failed wall must not be rewritten as a successful run.

The failure must be diagnosed at the Task 6 / decision-register compatibility
boundary before another Tasks 1–7 CI-candidate wall is executed.

Raw failed-wall SHA-256:

`88e5ea25b571c358b0a1ea67b22a9bcb2ed4a1a5d677e0dc61deae94c57d065e`

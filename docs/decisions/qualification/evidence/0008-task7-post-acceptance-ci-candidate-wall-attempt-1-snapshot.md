# Task 7 Post-Acceptance CI-Candidate Attempt 1 Mutable-State Snapshot

This snapshot was materialized before repairing the Task 6 decision-register
version compatibility defect exposed by the first Tasks 1–7 accepted-state
CI-candidate wall.

The failed wall itself remains preserved separately.

The snapshot contains the exact mutable bytes for:

- `.github/workflows/ci.yml`;
- `docs/decisions/register.md`;
- `scripts/check_research_hypotheses.py`;
- `tests/qualification/test_research_hypotheses.py`.

The Task 6 failure was:

`decision register Version must be 1.5.0 for Task 6`

This snapshot does not reinterpret or replace that failed result.

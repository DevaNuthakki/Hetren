# Decision 0008 Red-Team Evidence — Set A

**Decision ID:** `0008`
**Evidence type:** `UNSEEN_HOLDOUT_DISCOVERY`
**Date:** `2026-09-18`
**Lifecycle:** `PRESERVED_NEGATIVE_EVIDENCE`
**Initial result:** `0 / 12`
**Initial killed:** `0`
**Initial survived:** `12`
**Final remediation result:** `12 / 12`
**Scientific support established:** `NO`
**Task 5 capability support established:** `NO`

## Frozen Qualification Implementation

The first Set A run was executed against a validator and canonical mutation
suite frozen before Set A was created.

Frozen SHA-256 fingerprints:

- `scripts/check_initial_splits.py`:
  `f615877c7a14a2d4aab7e1c8d6aecc4e766aa637d06e29ec69a35b43cf5fe564`
- `tests/qualification/test_initial_splits.py`:
  `055d42d902c196ab6242126a9cad8f0483245d00d5af71c9a46ca66337b90a00`

Both pre-holdout and post-holdout fingerprint verification passed.

The valid Task 7 Draft positive control also passed before Set A execution.

## Initial Set A Result

The frozen validator killed `0 / 12` previously unseen attacks.

All twelve attacks survived:

1. distant fourth `PartitionRole` authorization;
2. distant eighth `PartitionPurpose` authorization;
3. `SplitVersion` membership edited in place;
4. materially changed candidate keeps identity;
5. `UNKNOWN` contamination automatically expires to `CLEAN`;
6. unlimited aggregate protected-score peeking;
7. generated summaries declared freshness-neutral;
8. same `N-H1` source counted independent with different evaluators;
9. three `N-H2` boundaries manufacture universal transfer;
10. `A-H1` success automatically satisfies `A-H2`;
11. originating process self-certifies with an audit log;
12. comparator selected after outcomes for favorable efficiency.

## Interpretation

This result demonstrates that passing the 52 canonical development mutations
did not establish general semantic robustness.

The validator correctly enforced the known canonical attack set but failed to
detect a separate set of distant, indirect, and cross-rule contradictions.

Set A therefore becomes a discovered red-team regression set after this first
run.

It must not subsequently be described as unseen evidence after validator
remediation.

Any repaired validator must preserve this original `0 / 12` result and record
its later Set A regression result separately.

A new independently frozen Set B is required for the next genuinely unseen
generalization test.

## Evidence Preservation Rule

The initial failure must not be erased, replaced, or rewritten by a later
passing result.

Remediation changes the validator.

It does not change what happened during the original frozen Set A run.


## Remediation Attempt 1

**Result:** `11 / 12`
**Killed:** `11`
**Survived:** `1`

The canonical `52 / 52` development regression remained passing and the valid
Task 7 Draft positive control remained passing.

The surviving Set A attack was:

- `SplitVersion membership edited in place`

The observed validator weakness was semantic-scope fragmentation: the
permission to edit membership and the requirement to retain the existing
`SplitVersion` were connected through `while`, but the clause parser separated
those concepts before evaluating the forbidden relationship.

This is preserved as failed remediation evidence.

It does not replace or alter the original frozen `0 / 12` Set A discovery
result.


## Final Remediation Result

**Result:** `12 / 12`
**Killed:** `12`
**Survived:** `0`

The repaired validator killed all twelve previously discovered Set A attacks.

At the same checkpoint:

- the valid Task 7 Draft positive control passed;
- all `52 / 52` canonical development mutations remained killed;
- qualified mode remained closed while Task 7 was still Draft;
- `git diff --check` remained clean.

The final Set A repair addressed a semantic-scope defect in which `while`
incorrectly separated two parts of one operative relationship.

The Set A attack definitions were not changed to obtain this result.

The evidence history is therefore:

`0 / 12` unseen discovery
→ `11 / 12` remediation attempt
→ `12 / 12` regression remediation.

Only the first result was an unseen holdout result.

The final `12 / 12` result is regression evidence and must not be represented
as independent or unseen generalization evidence.

A newly frozen Set B is required for the next unseen test.

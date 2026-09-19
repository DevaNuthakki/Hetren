# Decision 0008 Red-Team Evidence — Set B

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

## Frozen Pre-Set-B State

The first Set B run was executed only after freezing the repaired Task 7
validator, canonical suite, Set A regression suite, Task 7 specification,
Decision 0008, and decision register.

Frozen SHA-256 fingerprints:

- `scripts/check_initial_splits.py`:
  `e84fd40eb2a8869476aaba649ab2f7ee6c496eddb76edcf63ffd1fda2c3f3ca3`
- `tests/qualification/test_initial_splits.py`:
  `055d42d902c196ab6242126a9cad8f0483245d00d5af71c9a46ca66337b90a00`
- `tests/qualification/test_initial_splits_holdout.py`:
  `8b98fb170423c4bbc6f9037ac2a92a5268e98e8b6b7a8d6de61fad55c714d736`
- `docs/mvp/07-initial-splits.md`:
  `937dac0a6e8664768e2ef2b1f92e08a9fadae8bcb200bf0fc5ce4134c4c912bd`
- `docs/decisions/0008-initial-split-protocol.md`:
  `f49fdb8fd6c45bef5c0f679007a343b46431e47f67915b3084214b12b30a6f1a`
- `docs/decisions/register.md`:
  `46a29c28d7790966b32e0e263480ce6fb3994955433b691510e30cc5e0f8ef0c`

Pre-run and post-run verification of all frozen files passed.

Set B attack-definition SHA-256:

`d8d6b8beb9bb5bc0db82a72177854928d793b351b75c50ae3f212e7af213f041`

The valid Task 7 Draft positive control passed before Set B execution.

## Initial Set B Result

The frozen validator killed `0 / 12` previously unseen Set B attacks.

All twelve attacks survived:

1. operational alias bypasses closed `PartitionRole` vocabulary;
2. operational alias bypasses closed `PartitionPurpose` vocabulary;
3. frozen `SplitVersion` repointed to revised member set;
4. protected telemetry dashboard influences descendant candidate;
5. `SUSPECTED` contamination treated as `CLEAN` below confidence threshold;
6. `INVALIDATED` protected result restored without rerun;
7. shared upstream source counted independent via disjoint windows;
8. target-family performance bands used for `N-H2` method selection;
9. `A-H2` retroactively validates contaminated `A-H1`;
10. separate process masquerades as independent verifier;
11. distributed baseline and cost rules manufacture preferred comparison;
12. Decision 0008 permits material DATA rerun waiver.

## Interpretation

Set B demonstrates that the repaired validator still does not generalize
sufficiently beyond the canonical and Set A attack families.

The surviving failures are not merely wording variants.

They expose broader missing reasoning capabilities involving:

- controlled-vocabulary aliases;
- governed identity continuity;
- indirect and proxy information flow;
- contamination-state laundering;
- lifecycle transition legality;
- shared-ancestry pseudoreplication;
- proxy target-outcome leakage;
- cross-hypothesis evidence laundering;
- structural independence rather than process separation;
- cross-section baseline/resource composition;
- and non-waivable evidence consequences.

Set B becomes a discovered regression set after this first execution.

It must never later be described as unseen evidence after remediation.

## Evidence Preservation Rule

The original `0 / 12` result must remain permanently distinguishable from all
later Set B remediation results.

Repairing the validator changes future behavior.

It does not change the original unseen result.


## Remediation Candidate 1 — Rejected Before Set B Replay

**Set B regression executed:** `NO`
**Reason:** `VALID_CONTRACT_FALSE_POSITIVE`

The first architecture-level remediation candidate introduced paragraph-scoped
permissive relationship checks.

It was rejected before any Set B regression result was collected because the
valid Task 7 Draft failed its positive control.

The false-positive labels were:

- `protected invalidation transition integrity`;
- `shared-ancestry independence integrity`;
- `Adaptive cross-hypothesis laundering integrity`.

Diagnostic inspection showed that all three originated from one large
semicolon-delimited numbered qualification contract being interpreted as a
single semantic paragraph.

A legitimate permission in one numbered condition was therefore combined with
unrelated concepts from other numbered conditions.

This remediation candidate receives no Set B score because a validator that
rejects the valid governing contract is not eligible for red-team evaluation.

The Set B attacks were not modified.


## Remediation Attempt 1 — Executed

**Result:** `11 / 12`
**Killed:** `11`
**Survived:** `1`
**Attack-definition SHA-256:**
`d8d6b8beb9bb5bc0db82a72177854928d793b351b75c50ae3f212e7af213f041`

The valid Task 7 Draft positive control passed.

The canonical development suite remained `52 / 52`.

Set A remained `12 / 12`.

Qualified mode remained closed while Task 7 was still Draft.

The sole surviving Set B attack was:

- `target-family performance bands used for N-H2 method selection`

The Set B attack definitions were unchanged.

This result is preserved as remediation evidence and does not replace the
original frozen `0 / 12` unseen Set B discovery result.


## Final Set B Remediation

**Result:** `12 / 12`
**Killed:** `12`
**Survived:** `0`
**Attack-definition SHA-256:**
`d8d6b8beb9bb5bc0db82a72177854928d793b351b75c50ae3f212e7af213f041`

The repaired validator killed every discovered Set B attack.

At this checkpoint:

- the valid Task 7 Draft positive control passed;
- the canonical development suite remained `52 / 52`;
- Set A remained `12 / 12`;
- the Set B attack-definition hash was unchanged;
- qualified mode remained closed because Task 7 was still Draft;
- `git diff --check` remained clean.

The final Set B repair generalized the method-selection action concept across
ordinary grammatical inflections such as `rank`, `ranked`, and `ranking`.

The Set B evidence history is:

`0 / 12` unseen discovery
→ remediation candidate rejected before replay
→ `11 / 12` executed remediation
→ `12 / 12` regression remediation.

Only the original `0 / 12` result is unseen Set B evidence.

The final `12 / 12` result is regression evidence and must not be represented
as an independent holdout result.

A separately frozen generated/compositional Set C is required before final
Task 7 qualification.

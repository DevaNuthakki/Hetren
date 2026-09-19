# Decision 0008 Red-Team Evidence — Set C

**Decision ID:** `0008`
**Evidence type:** `GENERATED_UNSEEN_HOLDOUT_DISCOVERY`
**Date:** `2026-09-18`
**Lifecycle:** `PRESERVED_NEGATIVE_EVIDENCE`
**Generator families:** `8`
**Variants per family:** `8`
**Generated attacks:** `64`
**Initial result:** `17 / 64`
**Initial killed:** `17`
**Initial survived:** `47`
**Final remediation result:** `64 / 64`
**Scientific support established:** `NO`
**Task 5 capability support established:** `NO`

## Frozen Pre-Set-C State

Set C was created only after freezing the repaired Task 7 validator,
canonical suite, Set A suite, Set B suite, Task 7 specification,
Decision 0008, and decision register.

Set C attack-definition SHA-256:

`368a0046c9fed38d007374c5a976a41b89dd0922c4e60d46c040dd890b73cfc2`

The pre-Set-C governing freeze passed before execution.

The same governing freeze passed again after execution.

The Set C attack-definition hash also matched before and after execution.

The valid Task 7 Draft positive control passed.

## Initial Set C Result

The frozen validator killed `17 / 64` generated attacks.

`47 / 64` generated attacks survived.

Family results were:

- `C01 protected proxy feedback`: `3 / 8` killed;
- `C02 pseudoreplication`: `0 / 8` killed;
- `C03 SplitVersion identity laundering`: `1 / 8` killed;
- `C04 contamination laundering`: `1 / 8` killed;
- `C05 fake verifier independence`: `0 / 8` killed;
- `C06 Adaptive hypothesis laundering`: `6 / 8` killed;
- `C07 DATA consequence waiver`: `6 / 8` killed;
- `C08 distributed baseline/resource gaming`: `0 / 8` killed.

## Interpretation

The first generated Set C run demonstrates that success on the canonical
`52 / 52`, Set A `12 / 12`, and Set B `12 / 12` regression suites did not
establish broad semantic generalization.

The surviving attacks expose multiple architectural weaknesses rather than
one isolated wording defect.

The principal observed families include:

- incomplete recognition of protected proxy signals;
- insufficient ancestry-based independence reasoning;
- narrow vocabulary for governed identity mutation;
- contamination laundering through alternate justifications;
- structural verification dependence hidden behind superficial separation;
- incomplete modal and permission recognition;
- and insufficient cross-section composition reasoning for baseline/resource
  selection.

Set C becomes a discovered generated regression corpus after this first run.

It must not later be described as unseen evidence after remediation.

## Evidence Preservation Rule

The original `17 / 64` result must remain permanently distinguishable from all
later Set C remediation results.

Repairing the validator may improve future Set C results.

It does not change the original generated unseen result.


## Diagnostic Analysis 1

The first generated Set C result was analyzed without modifying the validator
or the frozen Set C attack corpus.

### Permission Recognition

The permission engine recognized:

- `may`;
- `can`;
- `is allowed to`;
- `is permitted to`;
- `is authorized to`;
- `is operationally permitted to`.

It did not recognize:

- `is acceptable to`;
- `is considered valid when configured to`.

This accounts for part, but not all, of the generated failures.

### Intended-Invariant Coverage

The number of generated attacks detected by the architectural invariant
intended for that family was:

- `C01`: `2 / 8`;
- `C02`: `0 / 8`;
- `C03`: `1 / 8`;
- `C04`: `1 / 8`;
- `C05`: `0 / 8`;
- `C06`: `6 / 8`;
- `C07`: `6 / 8`;
- `C08`: `0 / 8`.

This demonstrates that the remaining problem is broader than modal parsing.

Several invariants still depended on incidental vocabulary from earlier
hand-authored attacks instead of directly modeling the governed relationship.

### Distributed C08 Diagnosis

The baseline/resource composition checker also failed asymmetrically.

Some generated variants activated only the Task 8 side, some only the Task 9
side, and several activated neither side.

The architectural problem is that the Task 8 side over-constrained the
vocabulary used for comparator filtering and the Task 9 side incorrectly
required comparator language to appear again even though comparator identity
was already supplied by Task 8.

The remediation must therefore model the two-stage relationship:

1. a comparator or baseline is made selectively reportable by a
   resource/cost/eligibility rule; and
2. protected results influence the resource/accounting rule.

Neither the original `17 / 64` result nor the generated attack corpus is
changed by this analysis.


## Final Set C Remediation

**Result:** `64 / 64`
**Killed:** `64`
**Survived:** `0`
**Attack-definition SHA-256:**
`368a0046c9fed38d007374c5a976a41b89dd0922c4e60d46c040dd890b73cfc2`

The repaired Task 7 validator rejected every previously discovered generated
Set C attack.

The generated attack corpus remained byte-identical to the corpus used for the
original unseen `17 / 64` result.

At the same checkpoint:

- the valid Task 7 Draft contract passed;
- the canonical development suite remained `52 / 52`;
- Set A remained `12 / 12`;
- Set B remained `12 / 12`;
- Set C reached `64 / 64`;
- qualified mode remained closed because Task 7 was still Draft;
- all Task 7 qualification Python files compiled;
- `git diff --check` remained clean.

### Intended Architectural Coverage

Every generated family was also rejected by its intended architectural
invariant rather than merely failing through an unrelated validator rule:

- `C01`: `8 / 8`;
- `C02`: `8 / 8`;
- `C03`: `8 / 8`;
- `C04`: `8 / 8`;
- `C05`: `8 / 8`;
- `C06`: `8 / 8`;
- `C07`: `8 / 8`;
- `C08`: `8 / 8`.

This distinction matters because mutation rejection alone does not demonstrate
that the intended governance relationship caused the rejection.

### Set C Evidence History

The Set C history is:

`17 / 64` generated unseen discovery
→ diagnostic analysis
→ architecture-level remediation
→ `64 / 64` generated regression remediation.

Only the original `17 / 64` result is unseen Set C evidence.

The final `64 / 64` result is regression evidence.

It must not be represented as an independent holdout result or used to erase
the original negative evidence.

The next qualification phase must build a structured positive/negative corpus
and then evaluate a separately frozen fresh holdout against the resulting
architecture.

# P09.3 H1 Protected Execution Authorization Contract

## Status

**PRE-EXECUTION CONTRACT FROZEN — EXECUTION NOT AUTHORIZED**

This document freezes the conditions under which the one-shot P09.3 H1
controlled protected experiment may later be authorized.

Creating, reviewing, or committing this document does **not** authorize
execution.

A separate explicit human authorization must occur after this document is
committed and after the resulting D3 Git checkpoint is verified.

---

## Experiment identity

- Protected batch: `protected_v1`
- One-shot execution attempt: `execution_v1`
- Production confirmation phrase:
  `EXECUTE_P09_3_H1_PROTECTED_V1_ONCE`
- Treatment arms:
  - C0 TRACE_ONLY
  - C1 SEEDED_RANDOM_ACTIVE
  - C2 MAX_INFORMATION_GAIN_ACTIVE
  - C3 HEAL_INFORMATION_GAIN_PER_COST
- Protected population: 96 matched cases
- Matched arm executions if successful: 384

`execution_v1` is a one-shot identity.

Once its attempt directory is claimed, the attempt is consumed whether the run
ultimately succeeds or fails.

A failed or unfavorable protected result must not be deleted, silently
replaced, rerolled, or rerun under the same attempt identity.

---

## Frozen Git lineage

- Generation evidence freeze:
  `aba783582336b9add67ed7d93bb1185e1243f430`
- D1 treatment/evaluation contract:
  `e00358f781cb23581a7bb6b8a423081350a6830d`
- D2 one-shot execution capability:
  `a11391cf90985e035dc091d117ea6eb68c774af7`

The future protected execution must occur only from a clean descendant whose
only post-D2 change before execution is this D3 authorization-contract
checkpoint.

The exact D3 checkpoint created from this document is not knowable until Git
creates it. Its full commit ID must therefore be captured and independently
verified after this document is committed.

That exact D3 commit ID must be supplied to the protected CLI using
`--expected-head`.

No later source, configuration, protocol, treatment, evaluation, persistence,
or protected-data change is permitted before execution.

If any such change becomes necessary, `execution_v1` must remain unexecuted and
a new reviewed authorization boundary is required.

---

## Frozen source bytes

### Controlled environment

`environments/agent/h1_controlled_active_diagnosis.py`

SHA-256:

`960c5a058bb92266e4c54430722f3a1e99933423f6fe9f0dda923bd250fdfd2e`

### D1 treatment contract

`packages/engines/behavioral/h1_controlled_active_diagnosis_protected_execution.py`

SHA-256:

`22a2b6b6e88cddd9057d79c500aa4f620f0081daf634bf566b31ad7a6488656f`

### D1 evaluator contract

`packages/engines/behavioral/h1_controlled_active_diagnosis_protected_evaluation.py`

SHA-256:

`c8f38aed18859ecb4f8720ef5839539790ef1723d46517c547852dcc5deec167`

### D2 one-shot persistence

`packages/engines/behavioral/h1_controlled_active_diagnosis_protected_execution_persistence.py`

SHA-256:

`ee976830cf84ea7dcc17e6e9431902c28ed87a3b23d1243197d5bae44e974184`

### D2 guarded execution CLI

`scripts/run_h1_controlled_active_diagnosis_protected.py`

SHA-256:

`444de92f1a8cec928a6846a55bcbdd03fae32b875afef801da613cfea2b2ca2d`

### D2 execution-persistence tests

`tests/integration/test_h1_controlled_active_diagnosis_protected_execution_persistence.py`

SHA-256:

`2278a941911075beebd00ce43bf70d8da3c081b3cc3d1a3985707005c96473b9`

---

## Frozen protected-generation evidence

### Generation disposition file SHA-256

`95161cffe0db2aac8a8029243d57febafaba68f7198af71a9cfc2101b3c6a9c1`

### Seed commitment file SHA-256

`1a04be21e6c908e390ea17ba8701dd124e5cd886d0d4ab23b887094858593c53`

### Raw-seed SHA-256 / public seed commitment

`c1cd47afe62a4ee303334c3cac443e5a263ff3725ddfec48b7695eafe783cf3d`

The raw seed itself remains evaluator-only and must not be printed before the
protected result is frozen.

### Public manifest SHA-256

`b88d9c3bd280f18a56ea9c9c6bb05127cacba8ebf6d7fbb91deb1b70a9e12c01`

### Hidden-truth manifest SHA-256

`b709a96d33d405d89c545b6c2fa2c923f6f4c66eb3380b0412faf501bae5e60c`

Individual case-to-fault assignments remain evaluator-only before protected
result freeze.

### Generation record SHA-256

`5cff5a433c5cb841a7a06e37ddc01a0418534a9a68a3ea3172a4a6991264291f`

---

## Required pre-execution repository state

Before authorization can be acted upon:

1. Branch must be `portfolio/v1-foundation`.
2. HEAD must equal the exact D3 checkpoint created by this contract.
3. Tracked worktree must be clean.
4. Git index must be clean.
5. Frozen source bytes above must remain exact.
6. Protected generation bytes above must remain exact.
7. `execution_v1` must not exist.
8. Protected runtime paths must remain Git-ignored.
9. The modern regression baseline must remain 509 tests and green.
10. Frozen P08.2C and P07 evidence must remain unchanged.
11. Historical Task 8/9 preservation material must remain untouched.
12. No hidden case-to-fault mapping may be printed or moved into the treatment
    surface.

A pre-run verification gate must establish these conditions immediately before
the authorized execution command.

---

## Authorization rule

Execution is **not authorized by this Git commit**.

After D3 is committed and independently verified, a separate explicit human
authorization is required.

That authorization must identify:

- `protected_v1`;
- `execution_v1`;
- the exact D3 Git HEAD;
- that C0-C3 may execute exactly once under the frozen D1/D2 contracts;
- that the run must not be rerun to obtain a preferred result;
- that ordinary unfavorable scientific outcomes remain valid results.

Authorization must occur before the production CLI is invoked with the real
confirmation phrase.

Absence of that separate explicit authorization means:

**DO NOT EXECUTE.**

---

## Execution rule after explicit authorization

Only after the separate authorization exists, the production invocation may
use:

- the exact committed D3 HEAD as `--expected-head`;
- the exact confirmation phrase
  `EXECUTE_P09_3_H1_PROTECTED_V1_ONCE`.

Only one production invocation is permitted for `execution_v1`.

No exploratory production invocation, partial production invocation, dry run
using protected truth, or second invocation is permitted.

---

## Outcome accounting

The protected result must be accepted as generated.

The following are valid unfavorable outcomes and must remain in the registered
denominator where applicable:

- wrong specific diagnosis;
- INCONCLUSIVE;
- BUDGET_EXHAUSTED;
- poor experiment choice;
- higher resource use;
- prediction mismatch.

They must not be relabeled operationally invalid merely because they are
scientifically unfavorable.

Operational invalidity is limited to the previously frozen failure categories
and rules.

A Python-level operational failure after the attempt is claimed consumes
`execution_v1`.

No silent replacement is permitted.

---

## Failure preservation

Where persistence remains possible, a failed execution must preserve available
audit evidence including:

- attempt identity;
- failure phase;
- operational failure category;
- failure type;
- whether treatment began;
- current case identity when available;
- active arm context when available;
- completed observation count;
- available evidence references;
- any completed treatment/evaluation/result hashes already produced.

Sudden power loss or unrecoverable filesystem failure remains outside the
strong durability guarantee.

---

## Information-flow boundary

Treatment receives only:

- the frozen public manifest;
- its expected public-manifest SHA-256;
- an opaque controlled-environment executor.

The frozen D1 treatment module has no hidden-truth input.

The trusted orchestration layer uses evaluator truth solely to instantiate the
controlled latent environment behind the executor.

Evaluator scoring occurs only after the treatment batch has completed and been
persisted.

The evaluator derives truth from the exact hash-bound hidden manifest.

The current separation is logical information-flow separation inside one local
Python process.

It is **not** evidence of:

- process independence;
- machine independence;
- infrastructure independence;
- organizational independence;
- external evaluator custody.

---

## Scientific scope

This P09.3 experiment is a deterministic controlled mechanism test of H1.

It can provide evidence about whether the frozen active experiment-selection
mechanism behaves better than the frozen trace-only and active baselines under
the preregistered synthetic construction.

It does not establish:

- realistic-agent effectiveness;
- stochastic model robustness;
- unknown-fault performance;
- multi-fault performance;
- production reliability;
- external validity;
- state-of-the-art performance;
- causal repair correctness;
- real-world agent debugging superiority.

Any later claim must remain bounded to the actual evidence obtained.

---

## Result-freeze rule

Immediately after the one-shot protected execution:

1. do not modify the result;
2. do not rerun;
3. verify the exact execution artifact surface;
4. verify hashes and lineage;
5. preserve both favorable and unfavorable outcomes;
6. freeze the protected result before any broader interpretation;
7. only then disclose/reconstruct evaluator truth if the frozen protocol calls
   for that disclosure;
8. report the preregistered criteria mechanically before broader discussion.

---

## Current state at this checkpoint

At the time this contract is created:

- protected generation succeeded previously;
- the protected batch is frozen;
- D1 treatment/evaluation semantics are frozen;
- D2 one-shot execution capability is frozen;
- `execution_v1` has never been created;
- C0-C3 have not been executed on the protected batch;
- no protected experimental outcome has been observed;
- no protected evaluator result exists;
- this document does not authorize execution.

The next gate is the D3 checkpoint verification followed by a separate explicit
human authorization.

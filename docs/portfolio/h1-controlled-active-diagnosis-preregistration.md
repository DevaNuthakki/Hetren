# P09.3B — Controlled Active-Diagnosis H1 Preregistration

Status: preregistration candidate.

Protected data generated: NO.

Protected experiment executed: NO.

This document specializes the frozen
`docs/portfolio/heal-research-preregistration.md`
contract for the first controlled evaluation of HEAL H1.

It does not replace, amend, weaken, or reinterpret P09.1.

If this document conflicts with the frozen P09.1 contract,
P09.1 controls unless a new explicitly versioned preregistration
is created before protected outcomes are observed.


## 1. Purpose

The first controlled experiment tests whether active diagnostic
experiments improve bounded fault diagnosis relative to diagnosis
from the initial observable trace alone.

It additionally measures whether experiment-selection policy matters.

The experiment is intentionally a deterministic controlled mechanism test.

It is not intended to establish realistic-agent reliability,
model-backed reasoning quality, stochastic robustness,
multi-fault diagnosis,
unknown-fault safety,
external state-of-the-art superiority,
or production readiness.


## 2. Frozen H1 Question

The primary H1 question for this phase is:

> Under a fixed deterministic controlled tool-agent benchmark,
> does HEAL active diagnosis produce a higher correct-specific-diagnosis
> rate than the frozen trace-only procedure under the declared budget?

A stronger secondary question is:

> When active interventions are available to every active arm,
> does information-gain-per-cost selection outperform non-adaptive
> or cost-insensitive experiment selection under the same experiment
> definitions and resource budget?


## 3. Claim Boundary For This Phase

Any positive result from P09.3 is limited to:

- deterministic controlled cases,
- the frozen benchmark family,
- single primary faults,
- true fault contained in the initial Rival Fault Set,
- binary deterministic experiment predictions,
- the frozen experiment catalogue,
- the frozen synthetic resource-cost model,
- and the exact comparison procedures preregistered here.

A positive result does not establish:

- realistic-agent performance,
- stochastic-model performance,
- unknown-fault handling,
- multi-fault diagnosis,
- production reliability,
- general repair correctness,
- independent verification,
- candidate eligibility,
- deployment authorization,
- or superiority to external systems.

Those limitations survive even if every protected case passes.


## 4. Existing Incident-Triage Fixture Status

The existing deterministic incident-triage fixture is development evidence.

It must not be used as the protected H1 benchmark.

Reasons:

1. its exact two hidden fault modes have already been inspected;
2. its expected repairs have already been inspected;
3. its experiment definitions have already been used during implementation;
4. its tests have already been used to validate the current planner;
5. both currently registered discriminating experiments use cost 1;
6. it is therefore insufficient to test a stronger cost-aware
   selection claim.

The existing fixture may be used only for regression preservation,
API understanding, and development calibration.

No result from that fixture may be counted in the protected P09.3
primary metric.


## 5. Experimental Layer

This is a Layer-1 controlled multi-step agent-environment experiment.

It uses no live language model.

It uses no provider API.

It uses no external network service.

It uses no GPU.

It uses no Kubernetes, Terraform, MCP, database, queue,
or other new infrastructure technology.

The experiment must execute real deterministic workflow interventions.
It must not simulate the protected answer by directly returning
the hidden fault label.


## 6. Unit Of Analysis

The unit of analysis is one protected case under one experimental arm.

Every protected case is evaluated under every arm.

The comparison is therefore case-matched.

A case contains:

- one treatment-visible case identifier,
- one treatment-visible initial trace,
- one four-hypothesis Rival Fault Set,
- one treatment-visible prior distribution,
- one treatment-visible experiment catalogue,
- declared experiment prediction tables,
- declared synthetic experiment costs,
- one hidden true fault available only to the evaluation harness,
- and benign case-specific workflow variation.

The hidden true fault must not be present in treatment-visible data.


## 7. Rival Fault Set

Every in-scope protected case contains exactly four candidate hypotheses:

- H1
- H2
- H3
- H4

Exactly one is the hidden true primary fault.

The first protected batch contains exactly one primary fault per case.

No simultaneous or interacting faults are included.

This is a deliberate single-fault scope limitation.


## 8. Registered Diagnostic Experiment Vocabulary

Every case contains four experiment slots:

- `BIT_A`
- `BIT_B`
- `SINGLETON_PROBE`
- `NULL_PROBE`

The names themselves contain no hidden fault identity.

`BIT_A` predicts:

| Hypothesis | Prediction |
|---|---|
| H1 | PASS |
| H2 | PASS |
| H3 | FAIL |
| H4 | FAIL |

`BIT_B` predicts:

| Hypothesis | Prediction |
|---|---|
| H1 | PASS |
| H2 | FAIL |
| H3 | PASS |
| H4 | FAIL |

Together, `BIT_A` and `BIT_B` uniquely encode H1-H4.

`NULL_PROBE` has the same registered prediction for every hypothesis
and therefore has zero expected information gain.

`SINGLETON_PROBE` predicts PASS only for the template's
treatment-visible `singleton_target` hypothesis and FAIL for the other
three hypotheses.

For cost-sensitive templates T1-T4, `singleton_target` is the
template's dominant-prior hypothesis.

For the cost-neutral template families:

- N1 has `singleton_target = H1`;
- N2 has `singleton_target = H2`;
- N3 has `singleton_target = H3`;
- N4 has `singleton_target = H4`.

The singleton target is a public template property.

It is never selected from the hidden true fault of an individual case.


## 9. Cost-Sensitive Templates

There are four cost-sensitive template families.

Their treatment-visible priors are:

| Template | H1 | H2 | H3 | H4 | Dominant |
|---|---:|---:|---:|---:|---|
| T1 | 0.70 | 0.10 | 0.10 | 0.10 | H1 |
| T2 | 0.10 | 0.70 | 0.10 | 0.10 | H2 |
| T3 | 0.10 | 0.10 | 0.70 | 0.10 | H3 |
| T4 | 0.10 | 0.10 | 0.10 | 0.70 | H4 |

For all cost-sensitive templates:

- `BIT_A` costs 1 synthetic unit;
- `BIT_B` costs 1 synthetic unit;
- `SINGLETON_PROBE` costs 2 synthetic units;
- `NULL_PROBE` costs 1 synthetic unit.

The total diagnostic budget is exactly 2 synthetic units.

Synthetic units are research accounting units.
They must not be described as actual monetary or production cost.

Actual workflow/tool-call consumption must also be recorded separately.


## 10. Why The Cost-Sensitive Construction Exists

Under the frozen prior:

`SINGLETON_PROBE` can have larger raw expected information gain
than either individual bit experiment.

However its cost is 2.

The two bit experiments each cost 1 and, when both are executed,
jointly identify all four registered hypotheses.

The benchmark therefore creates a controlled condition where:

- raw information gain,
- information gain per cost,
- and arbitrary experiment selection

can produce different behavior.

This is a mechanism test.

It must not be generalized beyond this registered construction.

The principal arm ordering is analytically predictable before any
protected execution.

For a cost-sensitive template with prior `(0.70, 0.10, 0.10, 0.10)`:

- either balanced bit initially has approximately
  `0.721928` bits of expected information gain;
- `SINGLETON_PROBE` initially has approximately
  `0.881291` bits of expected information gain;
- a balanced bit therefore has approximately
  `0.721928` information bits per synthetic cost unit;
- `SINGLETON_PROBE` has approximately
  `0.440645` information bits per synthetic cost unit.

Therefore, under the ideal registered deterministic prediction model:

- C0 has 0% Correct Specific Diagnosis Rate;
- C2 selects `SINGLETON_PROBE` first and has a preregistered
  70% Correct Specific Diagnosis Rate on the cost-sensitive subset;
- C3 selects the two complementary cost-1 bit experiments and has a
  preregistered 100% Correct Specific Diagnosis Rate on that subset.

For the uniform cost-neutral subset:

- a balanced bit has exactly 1 bit of initial expected information gain;
- `SINGLETON_PROBE` has approximately `0.811278` bits;
- C2 and C3 therefore both select a balanced bit first;
- under the registered tie-breaking rules, both are expected to reach
  100% Correct Specific Diagnosis Rate.

C1 remains case-ID/decision-sequence dependent under its frozen
pseudo-random control rule.

These are pre-run mechanism expectations, not protected empirical
discoveries.

The protected execution tests whether the frozen implementation,
intervention execution, accounting, lineage and hidden-truth isolation
actually realize the preregistered mechanism without leakage or
post-hoc adjustment.


## 11. Cost-Neutral Negative Control

The protected batch also contains a cost-neutral negative-control subset.

It uses four public neutral template families N1-N4.

All four have the same uniform prior:

H1 = H2 = H3 = H4 = 0.25.

Their only singleton-template distinction is the public
`singleton_target` frozen in Section 8.

For every cost-neutral case:

- `BIT_A` costs 1;
- `BIT_B` costs 1;
- `SINGLETON_PROBE` costs 1;
- `NULL_PROBE` costs 1;
- total budget remains 2.

The negative-control purpose is to verify that the cost-aware arm
does not manufacture an advantage when cost asymmetry is removed.

The expected scientific interpretation is not that HEAL must always win.

A null comparison on this subset is an acceptable and informative result.


## 12. Experimental Arms

Four frozen arms are used.


### C0 — TRACE_ONLY

C0 receives:

- the same initial trace,
- the same Rival Fault Set,
- the same priors,
- and the same treatment-visible case metadata.

C0 may not execute a diagnostic experiment.

C0 is explicitly a no-active-information trace-only control.

It is not presented as a competitive external trace-debugging system.

C0 initializes its posterior from the same frozen registered prior
available to every arm.

The benchmark's initial trace is intentionally constructed so that it
contains no registered discriminator among H1-H4.

C0 may consume every ordinary treatment-visible field available at
case start, but it may not invent a hidden or post-hoc trace feature
whose interpretation was designed from protected truth.

C0 must use the same specific-diagnosis criterion as the active arms.

C0 must not guess the MAP hypothesis merely because it has
the largest non-unit posterior probability.

If its initial posterior remains ambiguous, C0 returns INCONCLUSIVE.


### C1 — SEEDED_RANDOM_ACTIVE

C1 receives the same active experiment catalogue as C2 and C3.

At each decision point its candidate set is exactly:

- experiments not already executed;
- whose declared cost is less than or equal to remaining budget.

Zero-information experiments remain candidates when other informative
experiments are also available.

This is intentional: C1 is an arbitrary active-selection control,
not another information-gain policy.

Before random selection, candidate experiment keys are sorted
lexicographically.

For decision sequence `s`, C1 computes:

`seed_material = "hetren-p09.3-h1-c1-v1|" + CASE_ID + "|" + str(s)`

`seed_int = int(SHA256(seed_material.encode("utf-8")).hexdigest(), 16)`

It then constructs:

`random.Random(seed_int)`

and selects:

`candidate_keys[rng.randrange(len(candidate_keys))]`

The registered implementation runtime for this deterministic control is:

`CPython 3.12.7`

using the Python standard-library `random.Random` implementation.

The selection seed contains no:

- hidden fault label;
- protected expected outcome;
- observed future experiment result;
- evaluator-only metadata.

If no informative experiment remains at all, the common terminal rule
in Section 14 applies before C1 performs another selection.


### C2 — MAX_INFORMATION_GAIN_ACTIVE

C2 uses the same posterior and experiment predictions as C3.

Selection score:

`expected_information_gain`

Experiment cost is used only for affordability.

Experiment cost is not part of C2 ranking or tie-breaking.

C2 ranks eligible experiments by:

1. highest raw expected information gain;
2. lexicographically smallest experiment key.

No hidden fault information participates in the ranking.


### C3 — HEAL_INFORMATION_GAIN_PER_COST

C3 uses the existing HEAL active planner.

Selection score:

`expected_information_gain / declared_cost`

The implementation must reuse the existing
`information_gain_per_cost`,
`rank_eligible_experiments`,
and `select_active_experiment`
semantics rather than introducing a second hidden planner.

The frozen C3 ranking semantics are:

1. highest information gain per unit cost;
2. highest raw expected information gain;
3. lowest declared execution cost;
4. lexicographically smallest experiment key.

The exact planner source identity is frozen by the experiment-harness
checkpoint before protected case generation.


## 13. Observable-Information Parity

All four arms begin each matched case with the same:

- initial trace,
- initial system state,
- Rival Fault Set,
- prior distribution,
- case metadata,
- experiment definitions,
- experiment prediction table,
- and evaluator-visible non-hidden configuration.

C1, C2, and C3 receive the same active intervention capabilities.

The only intended difference among active arms is selection policy.

C0 differs only because active intervention access is the
explicitly studied treatment difference.

No arm receives the hidden fault label.


## 14. Diagnosis Stopping Rule

Every arm uses the following common terminal precedence.

After every completed observation, and before another experiment
selection:

1. reconstruct the posterior from the registered prior and observations;
2. if exactly one registered hypothesis retains probability 1.0,
   return DIAGNOSED even when remaining budget is zero;
3. for an ambiguous active arm, if remaining budget is zero,
   return BUDGET_EXHAUSTED;
4. for an ambiguous active arm, if no unexecuted affordable experiment
   exists, return BUDGET_EXHAUSTED;
5. if every unexecuted affordable experiment has effectively zero
   expected information gain, return INCONCLUSIVE;
6. otherwise the arm-specific selection policy chooses the next
   experiment.

C0 performs no experiment selection.

After its initial posterior is evaluated, an ambiguous C0 result is
INCONCLUSIVE rather than a guessed diagnosis.

A specific diagnosis is emitted only when the treatment posterior
assigns probability 1.0 to exactly one registered hypothesis.

A non-unit MAP posterior is not sufficient for a specific diagnosis.

A final affordable experiment that leaves exactly one surviving
hypothesis therefore produces DIAGNOSED even if that experiment
consumes the last budget unit.

Budget exhaustion and INCONCLUSIVE are valid outcomes.

They are not invalid runs.

They remain in the metric denominator.


## 15. Primary Metric

The P09.3 H1 primary metric is:

`Correct Specific Diagnosis Rate`

defined as:

    valid protected cases ending with the exact hidden in-RFS fault
    ---------------------------------------------------------------
                    all valid protected cases

A case is not removed because the arm:

- abstains,
- returns INCONCLUSIVE,
- exhausts budget,
- makes an incorrect specific diagnosis,
- or fails to diagnose.

All such valid outcomes remain in the denominator.


## 16. False-Certainty Metric

The principal safety metric is:

`False Specific Diagnosis Rate`

defined as:

    valid protected cases ending with the wrong specific fault
    -----------------------------------------------------------
                    all valid protected cases

INCONCLUSIVE and budget exhaustion are not false certainty.

They are reported separately.


## 17. Resource Metrics

Every valid run records:

- declared synthetic experiment cost,
- realized experiment cost,
- number of experiments executed,
- realized workflow/tool calls,
- and whether the full budget was consumed.

Cost-sensitive and cost-neutral subsets are reported separately.


## 18. Primary H1 Support Rule

H1 active-diagnosis support for this controlled benchmark requires:

1. C3 Correct Specific Diagnosis Rate minus
   C0 Correct Specific Diagnosis Rate
   is at least 0.25 absolute;

2. C3 False Specific Diagnosis Rate is no more than
   0.02 absolute above C0;

3. the result is obtained on the frozen protected batch;

4. no protected leakage invalidates the comparison;

5. and invalid-run accounting remains within the frozen protocol.

Failure to meet these conditions does not permit post-hoc
threshold adjustment.


## 19. Stronger Selection-Policy Support Rule

Within this frozen synthetic experiment catalogue, support for the
bounded statement that C3's registered selection policy outperforms
the seeded-random active control requires, on the cost-sensitive subset:

C3 Correct Specific Diagnosis Rate minus
C1 Correct Specific Diagnosis Rate >= 0.10.

If this threshold is not met, the active-intervention result may still
be reported, but the stronger selection-policy claim is unsupported.


## 20. Cost-Aware Selection Support Rule

Within this frozen synthetic cost construction, support for the
bounded statement that information-gain-per-cost selection outperforms
raw-information-gain selection requires, on the cost-sensitive subset:

C3 Correct Specific Diagnosis Rate minus
C2 Correct Specific Diagnosis Rate >= 0.20.

The cost-neutral negative-control subset must simultaneously satisfy:

absolute(
    C3 Correct Specific Diagnosis Rate
    -
    C2 Correct Specific Diagnosis Rate
) <= 0.05.

This prevents interpreting a generic implementation difference as
evidence specifically for the cost-aware mechanism.


## 21. No Population-Level Statistical Claim

This benchmark is a finite, frozen controlled case population.

The 96 protected cases are not treated as 96 independent fault
mechanisms.

Cases sharing a template × hidden-fault cell are deterministic
replicates with benign case-level variation and preregistered weighting.

The primary report therefore uses:

- exact counts;
- exact rates;
- paired arm differences;
- resource-use summaries;
- and template × hidden-fault cell results.

The report must not use the nominal `n = 96` to imply 96 independent
causal mechanisms or 96 independent stochastic samples.

It does not use a p-value or naive confidence interval to imply that
this synthetic case population represents all real-world agent failures.

Any later inferential statistical analysis must be separately justified
and labeled appropriately.


## 22. Protected Batch Size

The protected batch contains exactly 96 cases.

It contains:

- 80 cost-sensitive cases;
- 16 cost-neutral negative-control cases.


## 23. Cost-Sensitive Protected Composition

Each cost-sensitive template T1-T4 contains exactly 20 protected cases.

Within each template:

- 14 cases use the template's dominant hypothesis as hidden truth;
- 2 cases use each of the other three hypotheses.

Therefore, across T1-T4:

- H1 appears exactly 20 times;
- H2 appears exactly 20 times;
- H3 appears exactly 20 times;
- H4 appears exactly 20 times.

This preserves overall fault balance while keeping each template's
registered prior distribution calibrated to its own case composition.


## 24. Cost-Neutral Protected Composition

The 16 cost-neutral cases form the exact cross-product:

- N1 × H1, H2, H3, H4;
- N2 × H1, H2, H3, H4;
- N3 × H1, H2, H3, H4;
- N4 × H1, H2, H3, H4.

Each neutral template therefore appears exactly four times.

Each hidden fault therefore appears exactly four times.

Each public `singleton_target` appears exactly four times.

Every singleton-target × hidden-truth combination appears exactly once.

Their priors remain uniform.

The public singleton target is therefore balanced independently of
the evaluator-only hidden truth.


## 25. Development Cases

Development and calibration use a separate 32-case manifest.

Development cases may be inspected.

Development outcomes may guide implementation before harness freeze.

Development cases may not appear in the 96-case protected manifest.

Development results do not count toward the protected H1 metric.


## 26. Benign Case Variation

Cases must differ in treatment-visible workflow details that do not
directly expose hidden truth.

Examples may include:

- synthetic incident identifiers,
- benign ordering variation,
- non-diagnostic payload values,
- harmless metadata values,
- and workflow-instance identifiers.

The generator must not encode hidden truth into:

- case IDs,
- experiment names,
- provenance strings,
- ordering artifacts,
- hashes exposed to treatment,
- or other treatment-visible shortcuts.


## 27. Protected Generator Freeze

No protected case may be generated until:

1. benchmark generator implementation is complete;
2. experiment execution implementation is complete;
3. all four arm implementations are complete;
4. development testing is complete;
5. hidden-truth leakage tests pass;
6. the experiment harness is committed;
7. the exact harness commit SHA is frozen.

After the harness commit is frozen, the protected-generation command
creates exactly one 256-bit raw seed using:

`secrets.token_bytes(32)`

from the Python standard library.

The raw seed is evaluator-only during treatment.

The command immediately computes and records:

`SHA256(raw_seed)`

as the public protected-seed commitment.

The generator is deterministic given:

- the frozen harness commit;
- the raw protected seed;
- the frozen protocol version.

The public harness commit therefore does not itself reveal or permit
precomputation of the protected hidden assignment.

The one-shot generation command must refuse to proceed when a protected
seed record, protected manifest, hidden-truth manifest, or generation
disposition for the same batch version already exists.

A seed must never be discarded and rerolled because its generated
protected cases appear inconvenient or unfavorable.

If protected generation fails after the raw seed is created, that seed,
its commitment, and the failure disposition are preserved.

A corrected attempt requires an explicit new experiment-attempt identity
and the preregistered remediation procedure.

The raw seed may be disclosed after the protected result is frozen so
that the exact batch can be independently regenerated.

Changing benchmark or treatment code after protected generation creates
a new experiment version and requires a new preregistered protected batch.


## 28. Protected Manifest Separation

Protected generation must produce at least three separately fingerprinted
artifacts:

1. public protected-seed commitment record;
2. treatment-visible protected case manifest;
3. evaluator-only hidden-truth manifest.

The evaluator-only generation package preserves the raw seed or an exact
reference to the raw seed required for later deterministic regeneration.

The treatment-visible manifest must not contain:

- true fault labels,
- reference diagnoses,
- hidden oracle results,
- or evaluation-only metadata.

Both manifests receive SHA-256 fingerprints.

Only non-secret identities, counts, and fingerprints should be printed
during routine treatment execution.


## 29. Hidden-Truth Access

The following treatment components may not access the hidden-truth manifest:

- C0 diagnosis procedure;
- C1 selection policy;
- C2 selection policy;
- C3 HEAL planner;
- experiment executor;
- posterior updater.

The evaluation harness may access hidden truth only after treatment has
produced its final diagnostic outcome for the case.


## 30. Human Intervention

Protected runs are autonomous.

After the protected batch begins, humans may not:

- choose experiments,
- rewrite diagnoses,
- alter posterior values,
- retry unfavorable valid cases,
- replace case results,
- modify hidden labels,
- change costs,
- or selectively exclude valid cases.

Starting the batch and handling preregistered infrastructure operations
are allowed and must be logged.


## 31. Intervention State Isolation

Every diagnostic intervention must begin from an equivalent frozen
case state.

The first implementation should use an isolated case snapshot/reset
between experiments where technically possible.

If an intervention changes state, that state transition must be recorded.

An intervention that accidentally repairs or corrupts the workflow
must not be silently interpreted as clean diagnostic evidence.


## 32. Experiment Prediction Misspecification

Observed execution outcome is authoritative evidence of what happened.

The treatment must not rewrite an unexpected observation to match
a registered prediction.

Any disagreement between:

- observed experiment verdict,
- and the true hypothesis's registered prediction

must be retained and reported.

Such disagreement is not automatically an invalid run.

It may indicate:

- benchmark implementation error,
- experiment-model error,
- state contamination,
- or a limitation of deterministic prediction semantics.

Protected prediction mismatches must not be deleted merely because
they reduce HEAL performance.


## 33. Invalid Runs

A protected run is invalid only for a preregistered operational reason.

Candidate reasons are:

- harness crash before treatment completion;
- corrupted case artifact;
- missing required frozen artifact;
- treatment exposure to hidden truth;
- generator violation of a frozen structural invariant;
- unrecoverable execution infrastructure failure;
- or contract serialization failure preventing the registered arm
  from executing.

The following are valid unfavorable outcomes, not invalid runs:

- wrong diagnosis;
- INCONCLUSIVE;
- budget exhaustion;
- poor experiment choice;
- higher-than-expected resource use;
- prediction mismatch;
- or failure to outperform another arm.


## 34. Invalid-Run Replacement Rule

No invalid run is silently replaced.

The primary protected batch retains the scheduled case identity and arm.

If a systematic harness defect invalidates scientific interpretation,
the batch version is stopped and preserved.

A corrected implementation requires:

- a new committed harness version,
- a new protocol/version decision,
- and a newly derived protected seed.

The failed batch remains part of the research record.


## 35. No-Rerun-To-Win Rule

A valid protected outcome is never rerun because it is unfavorable.

The deterministic protected batch has one registered result per
case-arm pair.

Diagnostic reruns used to investigate a failure are exploratory and
must not replace the preregistered protected result.


## 36. Prior Discipline

The priors in Sections 9 and 11 are frozen experimental inputs.

They are public to all arms.

They are not estimated from protected outcomes.

Protected hidden labels may not be used to modify them.

Any later prior-sensitivity analysis is exploratory unless separately
preregistered.


## 37. Cost Discipline

Synthetic experiment costs are frozen before protected generation.

They may not be changed after viewing protected outcomes.

Declared synthetic cost and realized workflow/tool-call consumption
are reported separately.

Synthetic units must never be described as measured production cost.


## 38. External Comparison Boundary

No external agent-debugging system is included in this first H1
mechanism experiment.

Therefore P09.3 cannot support:

- state-of-the-art superiority;
- superiority to commercial observability products;
- superiority to external research systems;
- or broad market-performance claims.

A later experiment may add an external comparison if a relevant,
reproducible and fair method is available.


## 39. Unknown-Fault Boundary

The first P09.3 protected batch contains only in-RFS faults.

It therefore does not establish safe missing-hypothesis behavior.

No claim about realistic fault ambiguity or unknown-fault safety
is permitted from this batch.

A later separately preregistered protected evaluation must contain
out-of-RFS cases before such a claim becomes eligible for consideration.


## 40. Multi-Fault Boundary

The first P09.3 protected batch contains exactly one primary fault per case.

Success does not establish capability for:

- concurrent faults;
- interacting faults;
- cascading faults;
- or multi-causal failures.

A later separately preregistered evaluation is required before making
a multi-fault claim.


## 41. Repair / Verification Boundary

P09.3 H1 stops at diagnosis.

It does not invoke repair generation as part of the H1 primary comparison.

It does not use Repair Contrast as an H1 success criterion.

It does not use VerificationReport as an H1 success criterion.

It does not use VSP as an H1 success criterion.

It does not use CandidateEligibilityDecision.

It does not treat AssuranceBundle existence as experimental success.

Those mechanisms remain available for later H3-H5 experiments.


## 42. Protected Report Requirements

The protected report must preserve at least:

- protocol identity and hash;
- harness commit SHA;
- generator identity and hash;
- protected-seed commitment;
- protected-seed disclosure status;
- public-manifest hash;
- hidden-truth-manifest hash;
- case count;
- arm count;
- total scheduled runs;
- valid runs;
- invalid runs;
- invalid reasons;
- diagnosis outcome per valid case-arm pair;
- correct-specific-diagnosis counts;
- false-specific-diagnosis counts;
- INCONCLUSIVE counts;
- budget-exhaustion counts;
- declared cost;
- realized cost;
- experiment sequence;
- observed verdict sequence;
- prediction mismatches;
- and aggregate arm comparisons.

No unfavorable valid case may disappear from the report.


## 43. Planned Run Count

With 96 protected cases and four arms:

`96 × 4 = 384`

protected case-arm runs are scheduled.

Because the first environment is deterministic,
these are not described as 384 independent stochastic samples.

They are 384 matched deterministic benchmark executions.


## 44. Development-To-Protected Transition

The required order is:

1. implement benchmark environment;
2. implement generator;
3. implement C0-C3 harness;
4. run development-only cases;
5. test hidden-truth isolation;
6. test budget parity;
7. test cost accounting;
8. test deterministic replay;
9. test negative-control behavior;
10. freeze harness commit;
11. execute the one-shot protected seed/commitment generation step;
12. generate protected manifests without inspecting hidden outcomes;
13. freeze seed commitment and manifest hashes;
14. execute protected batch once;
15. analyze according to this protocol;
16. preserve negative results;
17. write bounded Claim Boundary.

Protected execution must not begin before steps 1-13 are complete.


## 45. Pre-Protected Stop Conditions

Do not begin protected execution if:

- an arm is incompletely specified;
- hidden truth is reachable from treatment;
- case generation is not deterministic;
- experiment cost assignment is still changing;
- priors are still changing;
- stopping rules are still changing;
- metric formulas are still changing;
- invalid-run policy is still changing;
- protected case composition is still changing;
- negative-control semantics are unresolved;
- or the harness has uncommitted tracked changes.


## 46. Interpretation Outcomes

The experiment may produce any of these legitimate conclusions:

1. active diagnosis helps and HEAL selection helps;
2. active diagnosis helps but HEAL selection does not beat active controls;
3. active diagnosis helps but cost-aware selection adds no measurable value;
4. active diagnosis provides no material improvement;
5. HEAL increases false certainty;
6. cost metadata harms selection;
7. implementation defects prevent valid interpretation;
8. the deterministic benchmark is too easy or too artificial to discriminate methods.

All outcomes must be retained.

The protocol must not be rewritten after protected results
to convert an unfavorable conclusion into a favorable one.


## 47. Technology Gate

This protocol introduces no new technology.

Implementation is expected to use the existing Python stack.

If implementation reveals a genuine need for a new meaningful technology,
work stops before introducing it.

The technology must then be explained and approved before use.


## 48. P09.3B Exit Criteria

This preregistration is ready to freeze only when:

- its relation to P09.1 is explicit;
- C0-C3 are unambiguously specified;
- C1 candidate eligibility and exact pseudo-random selection are frozen;
- C2 tie-breaking is frozen;
- C3 ranking semantics are frozen;
- terminal-state precedence is frozen;
- the benchmark prediction structure is frozen;
- cost-neutral singleton-target semantics are frozen;
- priors are frozen;
- costs are frozen;
- budget is frozen;
- protected case counts are frozen;
- deterministic replication limits are explicit;
- development/protected separation is explicit;
- leakage boundaries are explicit;
- invalid-run rules are explicit;
- protected-seed commitment and no-reroll rules are explicit;
- no-rerun rules are explicit;
- success thresholds are frozen;
- analytically predictable mechanism behavior is disclosed before execution;
- negative-control interpretation is frozen;
- claim limitations are explicit;
- no protected case has been generated;
- and no protected result has been observed.


## 49. Next Gate After Freeze

After this document is frozen:

P09.3C will implement the controlled benchmark and four-arm experiment
harness using development cases only.

P09.3C is not authorized to generate the protected manifest.

A later explicit pre-protected checkpoint must verify:

- implementation bytes;
- test results;
- leakage isolation;
- exact arm behavior;
- costs;
- budget;
- generator behavior;
- and harness commit identity

before the protected seed is derived.

No protected experiment begins merely because this document exists.

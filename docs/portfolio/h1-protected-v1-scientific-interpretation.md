# P09.3 H1 Protected Scientific Interpretation

## Status

**H1 SUPPORTED WITHIN THE FROZEN DETERMINISTIC CONTROLLED MECHANISM EXPERIMENT**

This document is the post-result scientific interpretation of the already-
frozen `protected_v1 / execution_v1` evidence.

It does not change the preregistration, treatment, evaluator, protected
population, result bytes, or registered decision rules.

It records what the frozen result supports and, equally importantly, what
the result does not support.

---

## Frozen evidence identity

- P09.3 preregistration SHA-256:
  `6b738092e28036ea400f6498a4ad1663dd8cbb1e1c9c1e54e48ff4030ceb6ef8`
- Protected batch: `protected_v1`
- One-shot execution: `execution_v1`
- Result-freeze Git checkpoint:
  `b1d45555e503c327e980840cd5443228ff72b502`
- Execution disposition SHA-256:
  `b649e8124ea62775f788e919297577852a1dde352672bbaf96ce879fa566f827`
- Treatment batch SHA-256:
  `d0075af51e5682e63f5fa790df9cf5e4927ddc0e4d46969791edcebe41a9989b`
- Execution record SHA-256:
  `d170ceb300e5b52829852bfd759507ec878c94ea6701de0564a115af86d50f0d`
- Evaluator result SHA-256:
  `f1f0ec239791105540d847a29e6764b8f713c6890818960f9e50e348ca20bbc6`

`execution_v1` is permanently consumed and must never be rerun to obtain a
different or preferred scientific result.

---

## Hypothesis under test

P09.3 tests the bounded H1 mechanism question:

> Does active diagnosis using the frozen experiment-selection policy improve
> correct specific diagnosis under the controlled registered construction,
> including the preregistered cost-sensitive comparison?

This is a diagnosis-mechanism experiment.

It is not an end-to-end repair, verification, eligibility, deployment, or
real-world-agent experiment.

---

## Frozen treatment arms

- C0 — `trace_only`
- C1 — `seeded_random_active`
- C2 — `max_information_gain_active`
- C3 — `heal_information_gain_per_cost`

C0 is a trace-only control. It is not presented as a competitive external
agent-debugging system.

---

## Registered decision rules and observed result

### Primary H1 criterion

Frozen rule:

- overall C3 minus C0 Correct Specific Diagnosis Rate must be at least `0.25`;
- C3 False Specific Diagnosis Rate must be no more than `0.02` above C0.

Observed:

- C3 minus C0: `1.000`;
- C3 false-specific rate: `0.000`;
- C0 false-specific rate: `0.000`.

**Decision: PASS.**

### Selection-policy bound

Frozen rule:

- on cost-sensitive cases, C3 minus C1 must be at least `0.10`.

Observed:

- C3 minus C1: `0.525`.

**Decision: PASS.**

### Cost-aware bound

Frozen rule:

- on cost-sensitive cases, C3 minus C2 must be at least `0.20`;
- on neutral cases, absolute C3 minus C2 must be at most `0.05`.

Observed:

- cost-sensitive C3 minus C2: `0.300`;
- neutral C3 minus C2: `0.000`.

**Decision: PASS.**

The frozen evaluator therefore records:

- `primary_h1_criteria_met = true`;
- `selection_policy_bound_met = true`;
- `cost_aware_bound_met = true`.

---

## Aggregate diagnosis outcomes

### Cost-sensitive protected cases

| Arm | Correct specific | Rate | Budget exhausted | False specific |
| --- | ---: | ---: | ---: | ---: |
| C3 HEAL IG-per-cost | 80 / 80 | 1.000 | 0 | 0 |
| C2 max raw IG | 56 / 80 | 0.700 | 24 | 0 |
| C1 seeded random | 38 / 80 | 0.475 | 42 | 0 |
| C0 trace only | 0 / 80 | 0.000 | 0 | 0 |

C0's 80 unfavorable outcomes are `INCONCLUSIVE`, not false-specific guesses.

### Neutral protected cases

| Arm | Correct specific | Rate | Budget exhausted | False specific |
| --- | ---: | ---: | ---: | ---: |
| C3 HEAL IG-per-cost | 16 / 16 | 1.000 | 0 | 0 |
| C2 max raw IG | 16 / 16 | 1.000 | 0 | 0 |
| C1 seeded random | 7 / 16 | 0.4375 | 9 | 0 |
| C0 trace only | 0 / 16 | 0.000 | 0 | 0 |

The exact C3-C2 tie on the neutral control is important to the bounded
cost-aware interpretation.

### Overall

| Arm | Correct specific | Rate | Budget exhausted | Inconclusive | False specific |
| --- | ---: | ---: | ---: | ---: | ---: |
| C3 HEAL IG-per-cost | 96 / 96 | 1.000 | 0 | 0 | 0 |
| C2 max raw IG | 72 / 96 | 0.750 | 24 | 0 | 0 |
| C1 seeded random | 45 / 96 | 0.46875 | 51 | 0 | 0 |
| C0 trace only | 0 / 96 | 0.000 | 0 | 96 | 0 |

---

## Matched-case evidence

The registered matched comparisons were:

- C3 versus C0 overall:
  - C3-only correct: `96`;
  - C0-only correct: `0`;
  - difference: `+1.000`.
- C3 versus C1 on cost-sensitive cases:
  - both correct: `38`;
  - C3-only correct: `42`;
  - C1-only correct: `0`;
  - difference: `+0.525`.
- C3 versus C2 on cost-sensitive cases:
  - both correct: `56`;
  - C3-only correct: `24`;
  - C2-only correct: `0`;
  - difference: `+0.300`.
- C3 versus C2 on neutral cases:
  - both correct: `16`;
  - C3-only correct: `0`;
  - C2-only correct: `0`;
  - difference: `0.000`.

This matched pattern is consistent with the preregistered mechanism
expectation: the C3 advantage over C2 appears where experiment costs create
a meaningful distinction between raw information gain and information gain
per cost, while the difference disappears on the neutral control.

This supports the bounded cost-aware mechanism interpretation within this
controlled construction.

---

## False-certainty behavior

All four arms produced zero false-specific diagnoses in the frozen protected
evaluation.

C2's unsuccessful cost-sensitive cases ended as budget exhaustion rather than
wrong specific diagnoses.

C0 abstained as inconclusive rather than guessing.

Accordingly, the observed C3 gain in this experiment did not arise from an
increase in false-specific diagnosis.

---

## Synthetic-cost and resource-accounting caveat

The registered cost units are synthetic experiment-cost units frozen for this
controlled experiment.

They must not be interpreted as measured wall-clock latency, monetary API
cost, GPU consumption, CPU consumption, network use, or production compute.

Overall resource accounting was:

| Arm | Synthetic actual cost | Experiments | Workflow steps |
| --- | ---: | ---: | ---: |
| C3 HEAL IG-per-cost | 192 | 192 | 768 |
| C2 max raw IG | 192 | 112 | 448 |
| C1 seeded random | 191 | 172 | 688 |
| C0 trace only | 0 | 0 | 0 |

Therefore the supported comparison is that C3 achieved higher diagnosis
quality than C2 under the same total preregistered synthetic cost in this
construction.

The result does **not** support saying that C3 used fewer experiments, fewer
workflow calls, lower latency, less compute, or lower real monetary cost.

Indeed, C3 used more experiment executions and workflow steps than C2 while
using the same registered synthetic cost.

---

## Scientific interpretation

**H1 is supported for the frozen P09.3 deterministic controlled mechanism
experiment.**

More precisely:

Under the preregistered synthetic single-fault diagnosis construction, the
frozen HEAL information-gain-per-cost selection policy produced a higher
Correct Specific Diagnosis Rate than the frozen trace-only, seeded-random
active, and raw-information-gain comparison policies where the registered
comparison applied, while preserving a zero false-specific rate.

The cost-sensitive C3-C2 advantage together with the neutral C3-C2 tie is
consistent with the intended cost-aware selection mechanism rather than a
general claim that C3 must dominate every active policy in every setting.

This is evidence about the mechanism represented by the frozen construction.
It is not evidence that the same effect magnitude transfers unchanged to
real agent systems.

---

## What this result does not establish

This result does not establish:

- effectiveness on realistic coding, browser, research, or tool agents;
- stochastic-model robustness;
- performance under model sampling variation;
- unknown-fault diagnosis;
- out-of-RFS diagnosis;
- multiple simultaneous faults;
- noisy or nondeterministic experiment outcomes;
- open-ended hypothesis generation;
- repair correctness;
- Repair Contrast effectiveness;
- verification-separation effectiveness;
- independent verification;
- candidate eligibility;
- deployment authorization;
- production reliability;
- measured latency or compute efficiency;
- measured monetary-cost efficiency;
- external validity;
- superiority to external commercial or research debugging systems;
- state-of-the-art performance;
- H2, H3, H4, or H5.

Observation is not explanation.

Diagnosis is not repair.

Evaluation is not verification.

Verification is not eligibility.

Eligibility is not authorization or deployment.

---

## Statistical boundary

This experiment reports exact frozen counts, rates, matched-case differences,
resource accounting, and template-by-fault aggregates.

The 96 cases are a controlled constructed mechanism population and must not be
treated as 96 independent real-world agent systems.

No naive population p-value or confidence interval is manufactured from these
controlled cases.

---

## P09.3 conclusion

P09.3 achieved its bounded purpose:

1. the diagnosis mechanism was preregistered before protected evaluation;
2. the protected population and hidden assignment were frozen before
   execution;
3. treatment and evaluator contracts were frozen before the one-shot run;
4. `execution_v1` ran exactly once;
5. the raw result bytes were frozen before scientific interpretation;
6. all registered H1 decision gates passed;
7. the interpretation remains bounded to deterministic controlled mechanism
   evidence.

The correct disposition is therefore:

**KEEP the cost-aware active-diagnosis mechanism as a supported foundation
component and advance it to a stronger validation layer.**

The next experiment must not merely repeat this synthetic construction.

It should increase ecological difficulty through a larger controlled
multi-step agent environment before any claim about realistic-agent
effectiveness is considered.

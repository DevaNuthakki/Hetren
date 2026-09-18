# Hetren MVP Research Hypotheses

**Version:** 1.0.0
**Status:** Qualified
**MVP Task:** 6 / 100
**Execution authority:** `AUTH-HETREN-MVP-3.0`
**Long-term authority:** `AUTH-HETREN-MASTER-2.0`
**Native governing decision:** `0006`
**Adaptive governing decision:** `0007`
**Native research program:** `NATIVE`
**Adaptive research program:** `ADAPTIVE`
**Research change category:** `THESIS`
**Required evidence consequence:** `NEW_PROGRAM_VERSION_AND_RERUN`
**Governing success semantics:** `docs/mvp/03-success-contracts.md`
**Governing support contract:** `docs/mvp/05-support-matrix.md`

---

## 1. Purpose

Task 6 freezes the first concrete scientific hypotheses for the Hetren MVP.

It does not establish that any hypothesis is scientifically true.

It defines:

- the exact initial Native Intelligence hypotheses;
- the exact initial Adaptive Intelligence hypotheses;
- their bounded scientific claim scopes;
- numerical minimum-effect criteria;
- falsification criteria;
- uncertainty requirements;
- negative-result semantics;
- stronger claims that remain excluded;
- dependencies on later governed split, baseline, and cost artifacts;
- the change-control rules that protect the hypotheses from post-result
  rewriting.

Task 6 completion means the research contract is qualified.

It does not mean any research hypothesis has already been supported.

## 2. Authority And Scope

This specification executes:

- `AUTH-HETREN-MVP-3.0`.

It remains subordinate to:

- `AUTH-HETREN-MASTER-2.0`.

Task 1 supplies the research-governance and transfer requirements.

Task 2 supplies decision governance.

Task 3 supplies shared evaluation outcomes and scientific-success semantics.

Task 4 supplies system and environment-family identity.

Task 5 supplies product capability-support semantics.

Task 6 owns the concrete MVP research hypotheses, numerical thesis-level
qualification thresholds, falsification criteria, and governed scientific
claim scope.

Task 6 does not own:

- concrete development, validation, or protected split identities — Task 7;
- concrete baseline implementations, identities, or versions — Task 8;
- concrete cost, effort, or accounting values — Task 9.

## 3. Research Programs Remain Separate

The MVP contains two separate scientific programs:

- Native Intelligence;
- Adaptive Intelligence.

They may share:

- Core records;
- execution infrastructure;
- evaluators;
- Artifact Graph semantics;
- permissions;
- verification machinery;
- qualification tooling.

They do not share scientific evidence merely because infrastructure is shared.

Native evidence cannot establish an Adaptive hypothesis.

Adaptive evidence cannot establish a Native hypothesis.

A product result cannot establish either research hypothesis by itself.

## 4. Initial Hypothesis Set

The initial Task 6 hypothesis vocabulary is exactly:

- `N-H1` — Learned Investigation Value;
- `N-H2` — Cross-Family Learned Transfer;
- `A-H1` — Bounded Useful Adaptation;
- `A-H2` — Retention, Locality, and Rollback.

All four are required MVP scientific obligations in the sense that the
research program must govern and evaluate them under the applicable protocol.

They are not requirements that all four hypotheses must receive `PASS` for
Task 6 specification completion or for general product qualification.

All four begin scientifically unresolved.

Acceptance of this specification or its governing decisions does not change
that unresolved scientific status.

## 5. Hypothesis Record Contract

Every governed hypothesis must preserve at least:

- hypothesis ID;
- research program;
- thesis version;
- scientific claim;
- claim scope;
- primary comparison;
- primary measure family;
- minimum-effect threshold;
- uncertainty requirement;
- hard constraints;
- falsification conditions;
- invalidation conditions;
- protected-evaluation dependency;
- baseline dependency;
- cost or resource dependency where applicable;
- stronger claims explicitly excluded;
- experiment-manifest references;
- resulting Task 3 evaluation records;
- scientific interpretation;
- decision and qualification provenance.

A hypothesis record must not silently mutate after governed evidence exists.

## 6. Thesis Versioning

The initial thesis version for each hypothesis is `1.0`.

A material change to:

- the scientific claim;
- minimum-effect threshold;
- primary metric meaning;
- protected-evaluation rule;
- baseline-comparison requirement;
- hard constraint;
- transfer meaning;
- falsification criterion

requires governed scientific change control.

For a material `THESIS` change, the minimum Evidence Consequence is:

`NEW_PROGRAM_VERSION_AND_RERUN`.

Prior hypothesis versions and their evidence remain preserved.

## 7. Task 3 Outcome Separation

Task 3 retains the exact evaluation outcome vocabulary:

- `PASS`;
- `FAIL`;
- `INCONCLUSIVE`;
- `BLOCKED`;
- `INVALID`.

Task 6 does not introduce a sixth evaluation outcome.

A hypothesis can be governed and preregistered while no valid evaluation has
yet occurred.

A `PASS` supports only the bounded claim actually tested.

A `FAIL` is valid negative evidence.

`INCONCLUSIVE` is not scientific success or scientific failure.

`BLOCKED` is not evidence for or against the hypothesis.

`INVALID` evidence must not be reused as if it were valid.

## 8. Scientific Interpretation

Task 3 outcomes and scientific interpretation remain distinct.

A valid `PASS` may support a bounded hypothesis claim.

A valid `FAIL` does not support that claim.

An `INCONCLUSIVE`, `BLOCKED`, or `INVALID` result must remain distinguishable.

Repeated failure does not authorize relabeling the hypothesis into a weaker
successful claim without a governed new hypothesis version or explicit claim
narrowing.

## 9. Numerical Threshold Principle

Task 6 freezes numerical MVP thesis thresholds.

These thresholds are minimum qualification gates for the MVP research claim.

They function as preregistered MVP smallest-effects-of-interest and bounded
tolerances: effects smaller than the applicable gate are not sufficient for
the corresponding MVP scientific claim even if they are statistically
detectable.

They are not universal scientific constants.

Future evidence may justify a different threshold in a new governed thesis
version, but protected results from this version must not be used to tune the
current threshold after the fact.

The concrete evaluator, split, baseline identity, and cost ledger used to
instantiate the thresholds are governed later by Tasks 7 through 9.

Protected thresholds must be frozen before protected results are inspected.

A threshold must not be weakened after protected evidence merely to obtain a
`PASS`.

## 10. Relative Improvement

Where this specification requires a relative improvement, the governing
evaluator must orient the primary measure so that larger means better before
the comparison is computed.

For a positive baseline magnitude, relative improvement is interpreted as:

`(candidate - baseline) / |baseline|`.

If the governing primary measure can legitimately be zero, negative, or
otherwise makes that expression unstable, the applicable metric decision must
predeclare an equivalent bounded normalization before protected evaluation.

The normalization itself must not be selected after seeing protected results.

## 11. Uncertainty Requirement

A numerical point estimate is insufficient by itself.

Unless a stricter program-specific requirement applies, a claimed positive
effect requires:

- a predeclared uncertainty procedure;
- a two-sided 95% interval or an equivalently conservative predeclared
  interval;
- the lower bound for the claimed positive candidate-over-comparator effect to
  be greater than zero.

Task 7 or the applicable metric decision may bind the concrete resampling,
replication, or analytical procedure.

It may not weaken the 95% minimum confidence requirement after observing
protected evidence.

## 12. Multiplicity And Selective Reporting

A hypothesis may define multiple diagnostic or secondary measures.

Scientific success must not be manufactured by selecting whichever secondary
measure happens to be favorable.

The primary measure family and any multiplicity treatment required for the
governed claim must be declared before protected evidence.

Negative and null primary outcomes remain preserved even when a secondary
measure is positive.

## 13. Hard Constraints

A hypothesis cannot pass by averaging away a hard constraint.

Applicable hard constraints include:

- protected critical invariants;
- evidence integrity;
- authorization;
- required independent evaluation;
- leakage controls;
- required rollback behavior;
- protected prior-capability limits;
- declared resource constraints when the claim depends on matched resources.

A hard-constraint violation makes the claimed hypothesis `PASS` unavailable
for that governed evaluation.

## 14. Negative Results

Negative results are first-class research evidence.

The repository and research records must preserve:

- failed comparisons;
- null effects;
- adverse effects;
- falsifying evidence;
- invalidated experiments;
- inconclusive experiments;
- failed transfer;
- failed retention;
- failed rollback.

Negative evidence must not be deleted, hidden, or converted into a product
success statement.

## 15. Protected-Evaluation Freeze

Before protected or hidden evidence is inspected, the applicable contract must
already identify:

- hypothesis version;
- primary metric meaning;
- success threshold;
- failure threshold;
- hard constraints;
- evaluator identity or binding rule;
- split-binding rule;
- baseline-binding rule;
- applicable resource-matching rule;
- invalidation conditions.

A material post-result change requires a new governed version and applicable
rerun.

## 16. Task 7 Dependency

Task 7 owns concrete:

- development splits;
- validation splits;
- protected or held-out splits;
- split identities;
- partition boundaries;
- leakage controls.

Task 6 defines what a hypothesis requires from those splits.

Task 6 does not choose the concrete records, examples, systems, datasets, or
partition identities.

## 17. Task 8 Dependency

Task 8 owns concrete:

- baseline implementations;
- baseline identities;
- baseline versions;
- baseline comparison configuration.

Task 6 may require:

- strongest matched baseline;
- non-learned baseline;
- learned baseline;
- adaptation baseline;
- equally resourced comparison.

Task 6 does not choose the concrete implementation or version satisfying that
role.

## 18. Task 9 Dependency

Task 9 owns concrete:

- compute-cost fields;
- execution-cost fields;
- engineering-effort fields;
- adaptation-cost fields;
- accounting values;
- practical-value measurement configuration.

Task 6 may require matched resources or bounded adaptation cost when the
scientific claim depends on them.

Task 6 does not choose the concrete accounting values.

## 19. Native Intelligence Program Scope

Native Intelligence asks whether Hetren-developed trainable decision
intelligence provides measurable value in investigation and decision making.

The MVP Native program does not claim merely that:

- shared Core infrastructure works;
- a hand-written strategy can be reused;
- retrieval can find a prior example;
- an external model can propose useful actions;
- a deterministic heuristic can solve a case.

The Native scientific claim concerns learned Hetren decision capability.

## 20. N-H1 — Learned Investigation Value

**Hypothesis ID:** `N-H1`

**Program:** `NATIVE`

**Thesis version:** `1.0`

**Name:** Learned Investigation Value

Scientific hypothesis:

A trainable Hetren Native Intelligence mechanism will provide measurable
held-out investigation-decision value beyond the strongest matched governed
baseline when selecting, ranking, revising, stopping, or abstaining from
investigative actions.

The claim is about learned decision value.

It is not merely a claim that the overall Hetren product can repair or improve
a target.

## 21. N-H1 Claim Scope

`N-H1` may cover decision value in one or more of:

- test or experiment selection;
- action ranking;
- evidence-gap prioritization;
- hypothesis revision;
- stopping;
- abstention;
- next-action recommendation.

The final reported claim must name the exact decision behavior supported by
evidence.

Evidence for one decision behavior does not automatically support all others.

## 22. N-H1 Qualification Criteria

A governed `N-H1` evaluation may return `PASS` only if all applicable
conditions hold:

1. the protected Task 7 evaluation is valid;
2. the strongest applicable Task 8 matched baseline is frozen before protected
   evaluation;
3. candidate and baseline use the declared resource-matching rule;
4. the Native candidate improves the predeclared primary decision-quality
   measure by at least **5% relative** to the strongest matched baseline;
5. the lower bound of the predeclared 95% interval for candidate-over-baseline
   improvement is greater than zero;
6. the effect is reproduced on at least **two independent governed evaluation
   units** defined by the Task 7 protected protocol; repeated observations,
   resamples, or runs from the same governed unit do not by themselves create
   a second independent unit;
7. no applicable hard constraint is violated;
8. no protected leakage or target-specific post-hoc tuning is detected;
9. raw outcomes and experiment manifests are preserved;
10. applicable independent verification agrees that the evidence supports the
    bounded claim.

The 5% threshold is the minimum MVP material-effect gate.

It is not a claim that 5% is universally sufficient for all later Native
research.

## 23. N-H1 Falsification And Narrowing

`N-H1` is not supported by a governed evaluation if:

- the valid protected result is below the 5% minimum-effect threshold;
- the candidate does not outperform the strongest matched baseline;
- the 95% interval includes or falls below zero for the claimed positive
  effect;
- the apparent gain disappears under the required resource matching;
- the gain depends on leakage or protected-case tuning;
- the claimed decision value is actually attributable only to an external
  generator, deterministic heuristic, or authored strategy;
- a hard constraint required by the claim is violated.

A narrower claim may be reported only when the preserved evidence actually
supports it and the narrowing is explicit.

## 24. N-H2 — Cross-Family Learned Transfer

**Hypothesis ID:** `N-H2`

**Program:** `NATIVE`

**Thesis version:** `1.0`

**Name:** Cross-Family Learned Transfer

Scientific hypothesis:

A Native Intelligence decision capability learned without access to protected
target-family outcomes will retain measurable decision value on at least one
held-out system-family boundary, beyond reuse of shared infrastructure,
schemas, retrieval, or a hand-written target strategy.

This is the MVP Native transfer hypothesis.

## 25. N-H2 Transfer Meaning

A valid `N-H2` claim requires transfer of learned decision capability.

The following do not establish `N-H2` by themselves:

- using the same repository;
- using the same Core records;
- using the same adapter abstraction;
- using the same evaluator interface;
- retrieving examples from another environment;
- copying a hand-authored investigation strategy;
- target-specific tuning on protected target outcomes.

The transfer protocol must identify what learned state or learned decision
mechanism is being transferred.

## 26. N-H2 Qualification Criteria

A governed `N-H2` evaluation may return `PASS` only if all applicable
conditions hold:

1. the target family or mechanism is protected under the Task 7 protocol;
2. protected target outcomes are not used to train or tune the transferred
   Native mechanism before protected evaluation;
3. the strongest applicable Task 8 transfer comparator is frozen;
4. the transferred Native mechanism improves the protected target primary
   decision-quality measure by at least **3% relative** to the strongest
   applicable non-transfer or non-learned comparator;
5. the lower bound of the predeclared 95% interval for the transferred
   candidate-over-comparator effect is greater than zero;
6. the candidate's source-side incremental advantage over its matched source
   comparator is strictly greater than zero under the predeclared comparison;
7. the protected target effect retains at least **50% of that positive
   source-side incremental advantage**;
8. the transfer result survives the declared leakage controls;
9. the result is not explained solely by target-specific authored strategy,
   retrieval, or hidden protected-case adaptation;
10. no applicable hard constraint is violated;
11. the result is independently verified.

The 3% target advantage and 50% retained-advantage thresholds are bounded MVP
transfer gates.

They do not establish universal cross-domain generality.

## 27. N-H2 Falsification And Narrowing

`N-H2` is not supported by a governed evaluation if:

- the valid protected target effect is below the 3% gate;
- the 95% interval does not exclude zero in the positive direction;
- the source-side incremental advantage is not strictly positive;
- the retained-advantage ratio is below 50%;
- the result requires protected target-outcome tuning;
- the result disappears when authored target strategy is controlled;
- the result is explained only by shared infrastructure or retrieval;
- leakage invalidates the transfer protocol.

Success in one source family without protected cross-family evaluation cannot
be reported as `N-H2` support.

## 28. Adaptive Intelligence Program Scope

Adaptive Intelligence asks whether controlled post-deployment plasticity can
produce useful new behavior while preserving required prior capabilities and
remaining governed, reversible, and independently verifiable.

Hetren Governed Plasticity, or HGP, remains a working research hypothesis.

Task 6 does not establish HGP as a product capability.

## 29. A-H1 — Bounded Useful Adaptation

**Hypothesis ID:** `A-H1`

**Program:** `ADAPTIVE`

**Thesis version:** `1.0`

**Name:** Bounded Useful Adaptation

Scientific hypothesis:

A governed post-deployment plasticity mechanism can produce material target
adaptation on protected evaluation while satisfying critical invariants and
outperforming the strongest applicable governed adaptation baseline.

## 30. A-H1 Qualification Criteria

A governed `A-H1` evaluation may return `PASS` only if all applicable
conditions hold:

1. the Task 7 protected adaptation evaluation is valid;
2. the pre-adaptation target state is preserved;
3. the strongest applicable Task 8 adaptation baseline is frozen;
4. the candidate improves the protected target primary measure by at least
   **5% relative** to its own pre-adaptation state;
5. the candidate improves the same protected target primary measure by at
   least **3% relative** to the strongest matched adaptation baseline;
6. the lower bound of the predeclared 95% interval for the
   candidate-over-baseline effect is greater than zero;
7. there are **zero critical-invariant violations**;
8. the applicable Task 9 adaptation-cost record is preserved;
9. the proposing or adapting mechanism is not the sole authority certifying
   success;
10. independent evaluation supports the bounded adaptation claim.

The 5% target-improvement and 3% baseline-advantage thresholds are MVP
minimum-effect gates.

They do not establish safe general self-improvement.

## 31. A-H1 Falsification And Narrowing

`A-H1` is not supported by a governed evaluation if:

- target improvement is below 5%;
- candidate advantage over the strongest matched adaptation baseline is below
  3%;
- the 95% interval does not exclude zero in the claimed positive direction;
- any critical invariant is violated;
- the result depends on invalid protected leakage;
- the adaptive candidate self-certifies without the required independent
  authority;
- the result cannot be reproduced under the declared protocol.

A useful product outcome without the required adaptive evidence does not
support `A-H1`.

## 32. A-H2 — Retention, Locality, And Rollback

**Hypothesis ID:** `A-H2`

**Program:** `ADAPTIVE`

**Thesis version:** `1.0`

**Name:** Retention, Locality, And Rollback

Scientific hypothesis:

A useful governed adaptation can preserve protected prior capability, keep
unrelated behavioral change within a bounded locality envelope, and return the
system to a qualified pre-adaptation state through rollback.

## 33. A-H2 Qualification Criteria

A governed `A-H2` evaluation may return `PASS` only if all applicable
conditions hold:

1. protected prior-capability evaluation is valid;
2. protected prior-capability degradation after adaptation is no more than
   **2% relative** on the predeclared retention measure;
3. unintended change on the predeclared locality measure is no more than
   **2% of that measure's governed normalized scale**;
4. there are **zero critical-invariant violations**;
5. rollback is actually executed rather than merely described;
6. after rollback, the protected prior-capability measure is restored to
   within **1% relative** of the preserved pre-adaptation value;
7. after rollback, system identity and applicable state provenance correspond
   to the declared rollback target;
8. retained or rolled-back behavior is evaluated independently from the
   adaptation proposal;
9. raw pre-adaptation, post-adaptation, and post-rollback outcomes are
   preserved;
10. applicable independent verification supports the bounded retention,
    locality, and rollback claim.

The 2% retention/locality and 1% rollback tolerances are MVP bounded-plasticity
gates.

For the locality gate, the locality measure must use a predeclared bounded
normalized scale whose orientation, endpoints, and aggregation meaning are
frozen before protected evidence is inspected. A post-result normalization
chosen to make the 2% gate pass is invalid.

They are not universal safety guarantees.

## 34. A-H2 Falsification And Narrowing

`A-H2` is not supported by a governed evaluation if:

- protected prior-capability degradation exceeds 2%;
- unintended locality change exceeds the governed 2% tolerance;
- any critical invariant is violated;
- rollback is not executed;
- rollback fails to restore protected prior capability within 1%;
- rollback provenance is invalid or ambiguous;
- the evaluation authority is not sufficiently independent;
- the evidence is invalidated by leakage, evaluator defect, or execution
  defect.

Passing `A-H1` does not imply `A-H2`.

Passing `A-H2` does not imply stronger continual-learning claims.

## 35. Stronger Claims Explicitly Excluded

Task 6 does not establish or preregister as successful:

- general intelligence;
- autonomous self-improvement;
- indefinite continual learning;
- long-horizon sequential stability;
- universal catastrophic-forgetting resistance;
- Experience Capsule transfer;
- cross-model Adaptive transfer;
- cross-architecture Adaptive transfer;
- multimodal Adaptive transfer;
- universal Native transfer;
- scaling-law superiority;
- safety beyond the explicitly tested critical invariants;
- deployment authorization.

Such claims require separate governed hypotheses and qualification gates.

## 36. Native And Adaptive Transfer Are Separate

`N-H2` concerns Native learned decision transfer.

It does not establish Adaptive transfer.

An Adaptive transfer claim would require a separate Adaptive hypothesis or
scientific gate.

Native transfer evidence cannot be reused as proof of Adaptive retained or
transferred adaptation.

## 37. Cross-Program Evidence Isolation

A research artifact may be physically shared while scientific interpretation
remains separate.

The following do not authorize cross-program evidence borrowing:

- shared execution;
- shared evaluator implementation;
- shared Artifact Graph;
- shared system identity;
- shared protected data;
- shared infrastructure;
- shared model architecture.

Every consequential research interpretation must identify its governing
program and hypothesis ID.

## 38. External Models

External generative models may assist with:

- hypothesis proposal;
- experiment proposal;
- candidate implementation;
- evidence summarization.

Their outputs do not become scientific evidence merely because the external
model is capable.

Native research success must remain separable from external-generator
performance.

Adaptive research success must remain separable from external-generator
confidence or self-evaluation.

## 39. Independent Evaluation

No Native or Adaptive candidate may be the sole authority certifying its own
scientific success.

Consequential scientific claims require applicable independent evaluation.

Independence may be established through the governed mechanisms allowed by
Task 3 and the MVP Charter.

## 40. Invalidation

A previously valid research result may be invalidated by:

- protected-data leakage;
- evaluator defect;
- baseline defect;
- implementation bug;
- incorrect metric direction;
- corrupted provenance;
- invalid experiment manifest;
- target contamination;
- hidden post-hoc tuning;
- failed reproduction where reproduction is required.

Invalidated evidence remains preserved as invalidated history.

It must not silently remain authoritative.

## 41. Rerun And Requalification

A material change to a hypothesis, threshold, primary metric, protected
protocol, baseline role, or interpretation requires the applicable governed
decision.

For a Task 6 thesis change, the minimum consequence is:

`NEW_PROGRAM_VERSION_AND_RERUN`.

A failed result cannot be repaired by editing the original thesis in place.

## 42. Claim Narrowing

Evidence may support a claim narrower than the preregistered hypothesis.

Claim narrowing is permitted only when:

- the preserved evidence actually supports the narrower claim;
- the narrower scope is explicit;
- the failed or unsupported broader claim remains visible;
- the narrower claim does not silently reuse the original `PASS` label for a
  materially different thesis.

A materially different thesis requires a governed new version.

## 43. Product And Research Status Separation

Task 5 product capability state and Task 6 research status remain independent.

A product capability may later become `QUALIFIED_SUPPORTED` while a Native or
Adaptive hypothesis fails.

A research hypothesis may later receive supporting evidence while a product
capability remains unavailable or unauthorized.

Neither state manufactures the other.

## 44. Task 6 Completion Versus Scientific Support

Task 6 may be complete when:

- the four hypotheses are explicitly defined;
- their numerical qualification gates are frozen;
- falsification rules are explicit;
- Native and Adaptive claim scopes are separated;
- Tasks 7 through 9 dependencies are explicit;
- decision governance is installed;
- qualification protects the contract against silent weakening.

Task 6 completion does not mean:

- `N-H1` is supported;
- `N-H2` is supported;
- `A-H1` is supported;
- `A-H2` is supported.

Scientific support requires later valid experimental evidence.

## 45. Task 7 Through Task 9 Handoff

Task 7 must bind concrete protected and development partition identities to the
requirements declared here.

Task 8 must bind concrete strong baseline identities and versions to the
baseline roles declared here.

Task 9 must bind concrete cost and resource-accounting values where this
contract requires matched resources or adaptation-cost preservation.

Those later tasks may instantiate this contract.

They may not silently weaken it.

## 46. Governed Extension

Adding, deleting, merging, or materially changing an initial Task 6 hypothesis
requires governed scientific change control.

Changing the meaning of:

- learned decision value;
- learned transfer;
- useful adaptation;
- retention;
- locality;
- rollback

requires versioned governance.

Historical hypotheses and their evidence remain preserved.

## 47. Native Governing Decision

Decision `0006` governs the Native Task 6 thesis set.

It must use:

- Research Program: `NATIVE`;
- Research Change Category: `THESIS`;
- Evidence Consequence: `NEW_PROGRAM_VERSION_AND_RERUN`.

Acceptance of Decision `0006` governs the research contract.

It does not establish that `N-H1` or `N-H2` is scientifically supported.

## 48. Adaptive Governing Decision

Decision `0007` governs the Adaptive Task 6 thesis set.

It must use:

- Research Program: `ADAPTIVE`;
- Research Change Category: `THESIS`;
- Evidence Consequence: `NEW_PROGRAM_VERSION_AND_RERUN`.

Acceptance of Decision `0007` governs the research contract.

It does not establish that `A-H1` or `A-H2` is scientifically supported.

## 49. Task 6 Qualification Contract

Task 6 qualification requires all of the following:

1. execution authority remains `AUTH-HETREN-MVP-3.0`;
2. long-term authority remains `AUTH-HETREN-MASTER-2.0`;
3. the initial hypothesis set is exactly `N-H1`, `N-H2`, `A-H1`, and `A-H2`;
4. `N-H1` and `N-H2` belong only to Native Intelligence;
5. `A-H1` and `A-H2` belong only to Adaptive Intelligence;
6. Decision `0006` governs the Native thesis set;
7. Decision `0007` governs the Adaptive thesis set;
8. both governing research decisions use change category `THESIS`;
9. both governing research decisions require `NEW_PROGRAM_VERSION_AND_RERUN`;
10. acceptance of a research decision is not treated as scientific support;
11. Task 3 retains the exact outcome vocabulary `PASS`, `FAIL`,
    `INCONCLUSIVE`, `BLOCKED`, and `INVALID`;
12. Task 6 introduces no sixth evaluation outcome;
13. hypotheses and scientific interpretations remain distinct from product
    capability state;
14. Native evidence cannot establish an Adaptive hypothesis;
15. Adaptive evidence cannot establish a Native hypothesis;
16. all protected thresholds are frozen before protected evidence;
17. post-result threshold weakening requires governed versioning and rerun;
18. a positive scientific effect requires a predeclared uncertainty procedure;
19. a claimed positive effect requires at least a 95% interval or stricter
    predeclared equivalent;
20. negative, null, inconclusive, blocked, and invalid evidence remain
    distinguishable;
21. `N-H1` tests learned investigation-decision value rather than product
    usefulness alone;
22. `N-H1` requires at least 5% relative improvement over the strongest matched
    governed baseline;
23. `N-H1` requires the 95% lower interval bound to exceed zero;
24. `N-H1` requires reproduction on at least two independent governed
    evaluation units;
25. `N-H1` cannot be established solely by an external model, deterministic
    heuristic, or authored strategy;
26. `N-H2` tests learned decision transfer across a protected system-family
    boundary;
27. `N-H2` requires at least 3% relative protected target advantage;
28. `N-H2` requires a positive 95% lower interval bound;
29. `N-H2` requires a strictly positive source-side incremental advantage
    and at least 50% retention of that positive advantage on the protected
    target;
30. `N-H2` cannot be established by shared infrastructure, retrieval, or
    hand-written target strategy alone;
31. `A-H1` tests material protected target adaptation;
32. `A-H1` requires at least 5% relative improvement over pre-adaptation state;
33. `A-H1` requires at least 3% relative improvement over the strongest matched
    adaptation baseline;
34. `A-H1` requires zero critical-invariant violations;
35. `A-H1` requires independent scientific evaluation;
36. `A-H2` tests retention, locality, and rollback rather than target
    adaptation alone;
37. `A-H2` limits protected prior-capability degradation to at most 2%;
38. `A-H2` limits locality change to at most 2% on a predeclared bounded
    normalized scale frozen before protected evidence;
39. `A-H2` requires zero critical-invariant violations;
40. `A-H2` requires executed rollback;
41. `A-H2` requires protected prior-capability restoration within 1% after
    rollback;
42. passing `A-H1` does not imply passing `A-H2`;
43. Native transfer does not establish Adaptive transfer;
44. stronger continual-learning, cross-model, cross-architecture, multimodal,
    scaling, or universal-transfer claims remain excluded;
45. Task 7 retains ownership of concrete split identities and partitioning;
46. Task 8 retains ownership of concrete baseline identities and versions;
47. Task 9 retains ownership of concrete cost and effort values;
48. invalidated research evidence remains preserved and non-authoritative;
49. material thesis changes require governed versioning and rerun rather than
    silent historical rewriting;
50. Task 6 completion remains explicitly separate from scientific support for
    any of the four hypotheses, and no hypothesis `PASS` is manufactured as a
    prerequisite for Task 6 specification completion or general product
    qualification.

## 50. Research-Hypothesis Principle

Hetren must claim no more scientific knowledge than its preserved evidence
supports.

A hypothesis is allowed to fail.

A hypothesis is allowed to remain inconclusive.

A product may succeed while a research hypothesis fails.

A research hypothesis may later gain support without authorizing product use.

The purpose of Task 6 is to make those distinctions testable before the
results exist.

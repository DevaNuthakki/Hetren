# Hetren MVP Success Contracts

**Version:** 1.0.0
**Status:** Qualified
**MVP Task:** 3 / 100
**Execution authority:** `AUTH-HETREN-MVP-3.0`
**Long-term authority:** `AUTH-HETREN-MASTER-2.0`
**Governing decision:** `0003`
**Canonical declaration record:** `GoalContract`
**Canonical measured-outcome record:** `EvaluationRecord`
**Canonical independent-verification record:** `VerificationReport`

---

## 1. Purpose

This specification defines what Hetren means by success, failure, improvement,
regression, uncertainty, blocked evaluation, invalid evidence, and verified
claims.

The purpose is not to select particular metrics or numerical thresholds.

The purpose is to ensure that every later environment and research program uses
the same semantics when converting observations into claims.

## 2. Authority And Scope

This specification derives from the unified MVP execution authority and the
qualified MVP Charter.

It applies to:

- E1 tool-using agent systems;
- E2 structured-data ML pipelines;
- E3 vision systems;
- regression repair;
- constrained improvement;
- Native Intelligence qualification;
- Adaptive Intelligence qualification;
- consequential product and release claims.

Concrete taxonomy, support boundaries, hypotheses, data partitions, baselines,
and cost-ledger values are deliberately deferred to later MVP tasks.

For this specification, a claim is consequential when it is used to justify a
material deployment, release, candidate acceptance, scientific conclusion,
transfer or generalization claim, protected qualification result, external
assertion, or another decision with material engineering, research, safety,
financial, or operational consequences.

A claim does not become non-consequential merely because a producing process
labels it that way. Consequence is determined by how the claim is used and by
the governing authority.

## 3. No Parallel SuccessContract Runtime Object

Task 3 does not introduce a new canonical runtime record named
`SuccessContract`.

`GoalContract` remains the canonical declaration of what an execution is trying
to establish.

Success-contract semantics describe the minimum information and rules a
`GoalContract` must provide when its outcome will support a material claim.

`EvaluationRecord` records measured evaluation.

`VerificationReport` records independent or authority-separated verification.

A later implementation may introduce nested schemas or typed components only
when doing so preserves these canonical responsibilities.

## 4. Three Independent Success Planes

Hetren maintains three independently inspectable success planes.

### 4.1 Product Success

Product success asks whether Hetren produced a useful and verified engineering
outcome under the declared constraints.

### 4.2 Native Intelligence Research Success

Native Intelligence success asks whether Hetren-developed trainable decision
intelligence provides measurable value beyond meaningful baselines under the
research contract.

### 4.3 Adaptive Intelligence Scientific Success

Adaptive Intelligence success asks whether controlled post-deployment
plasticity produces the claimed useful adaptation while satisfying the
applicable retention, locality, rollback, stability, and verification
requirements.

No result in one plane automatically establishes success in another plane.

There is no weighted overall score that may hide failure in one plane.

## 5. Required GoalContract Semantics

A material `GoalContract` must declare or reference enough information to
resolve:

- the bounded objective;
- the claim scope;
- target system identity and version;
- baseline or reference condition when comparison is claimed;
- primary measures;
- acceptance predicates;
- hard constraints;
- invariants;
- applicable budgets;
- evidence requirements;
- protected-evaluation requirements;
- uncertainty policy;
- blocked-evaluation policy;
- invalid-evidence policy;
- independent-verification requirements.

A contract that omits information necessary to determine its own outcome cannot
produce a verified consequential success claim.

Contract completeness is governed by applicable authority as well as by the
fields voluntarily declared by the author.

A `GoalContract` must not omit an authority-required acceptance predicate,
constraint, invariant, budget, evidence requirement, protected-evaluation
requirement, or verification requirement in order to make `PASS` easier.

If an applicable required element is omitted, the contract is not qualified to
support the affected consequential claim. An evaluation performed under that
materially incomplete contract cannot establish `PASS` until the contract is
corrected and the affected evaluation is requalified.

## 6. Evaluation Outcome Vocabulary

The shared evaluation outcomes are exactly:

- `PASS`
- `FAIL`
- `INCONCLUSIVE`
- `BLOCKED`
- `INVALID`

These outcomes describe evaluation status, not task lifecycle status.

They must not be silently replaced by vague labels such as "good",
"successful", "looks better", or "probably works".

Each governed evaluation has one primary outcome.

Individual evidence items, predicates, or sub-evaluations may retain their own
statuses, but the primary governed outcome must be resolved consistently when
multiple conditions coexist.

The resolution rules are:

1. `PASS` is possible only when all mandatory predicates, evidence-validity
   requirements, constraints, budgets, and required verification pass.
2. `FAIL` applies when valid evidence decisively demonstrates violation of any
   mandatory acceptance predicate, even if unrelated non-decisive checks remain
   incomplete.
3. `INVALID` applies when material evidence or protocol required to decide the
   claim is invalid and no independent valid evidence already establishes a
   decisive `FAIL`.
4. `BLOCKED` applies when required evaluation cannot complete and neither
   `PASS` nor a decisive valid `FAIL` can be established.
5. `INCONCLUSIVE` applies when the required evaluation is valid and sufficiently
   executed to evaluate the claim, but the evidence cannot discriminate
   `PASS` from `FAIL`.

Invalid or blocked evidence that is immaterial to an already established
decisive result must still be preserved, but it does not automatically replace
that primary outcome.

## 7. PASS

`PASS` requires valid evidence demonstrating every mandatory acceptance
predicate.

For a consequential comparison or improvement claim, `PASS` additionally
requires all applicable:

- baseline requirements;
- hard constraints;
- invariants;
- budget requirements;
- regression requirements;
- protected-evaluation requirements;
- independent-verification requirements.

`PASS` is conjunctive.

Improvement in one metric cannot compensate for violation of a mandatory hard
constraint or invariant.

## 8. FAIL

`FAIL` means valid evidence demonstrates that at least one mandatory acceptance
predicate is not satisfied.

A qualification failure is valid evidence.

`FAIL` must not be rewritten as `INCONCLUSIVE`, `BLOCKED`, or `INVALID` merely
because the result is undesirable.

A failed governed objective remains a failed objective even when other
non-mandatory measures improve.

## 9. INCONCLUSIVE

`INCONCLUSIVE` means the available evidence is valid but insufficient to decide
whether the contract passes or fails.

Examples include:

- insufficient statistical resolution;
- contradictory valid evidence;
- insufficient observations under the declared protocol;
- unresolved uncertainty explicitly permitted by the contract;
- an evaluation that completed correctly but did not discriminate between the
  governed alternatives.

`INCONCLUSIVE` is neither `PASS` nor `FAIL`.

It must not be converted into `PASS` because the available evidence appears
promising.

It must not be converted into `FAIL` merely because evidence sufficient for a
pass was not obtained.

## 10. BLOCKED

`BLOCKED` means the intended evaluation could not be completed because a
required dependency, permission, resource, or authorized execution condition
was unavailable.

Examples may include:

- permission denial;
- unavailable required infrastructure;
- budget exhaustion before the governed evaluation can complete;
- inaccessible protected evaluator;
- required credential failure;
- required dependency failure;
- cancellation or timeout that prevents the governed evaluation from
  completing;
- unavailable required system or model artifact.

A blocked evaluator or runner must never be translated into `PASS`.

A blocked result does not by itself demonstrate that the target objective
failed.

The blocking condition must be preserved separately from evidence about the
target system.

## 11. INVALID

`INVALID` means the evidence cannot support the governed claim because a
required integrity, identity, comparability, or protocol condition failed.

Examples include:

- evaluation leakage;
- corrupted evidence;
- lost provenance;
- wrong target system or model version;
- wrong evaluator or evaluator version;
- unauthorized alteration of protected criteria;
- incompatible baseline conditions;
- invalid execution identity;
- untracked material configuration drift;
- protocol violation that changes the meaning of the result;
- evaluating a different claim from the claim declared by the `GoalContract`.

Invalid evidence may be preserved for audit, debugging, or failure analysis.

Invalid evidence must not be used to establish `PASS` or `FAIL`.

If a result was previously treated as valid and a later defect demonstrates
that its evidence was invalid, the affected result must retain historical
traceability while its claim status is withdrawn or requalified.

## 12. Evidence-Validity Gate

Evidence validity is evaluated before success.

The required ordering is:

1. establish evidence validity;
2. evaluate the declared objective predicates;
3. verify hard constraints and invariants;
4. verify applicable budgets;
5. satisfy required independent verification;
6. support only the claim justified by those results.

A headline metric cannot bypass the evidence-validity gate.

Evidence integrity, identity, provenance, and protocol compatibility are
prerequisites for consequential success claims rather than measures that may
be traded against performance.

When validity cannot be established, the result is `INVALID`, not
`INCONCLUSIVE`.

When validity is established but the evidence cannot discriminate pass from
fail, the result may be `INCONCLUSIVE`.

When the governed evaluation cannot be completed, the result is `BLOCKED`
rather than an inferred pass or fail.

## 13. Baseline Semantics

Any claim of repair, improvement, learned advantage, transfer advantage, or
adaptive advantage must identify an appropriate comparison condition.

A comparison claim must preserve enough baseline identity to distinguish at
least:

- target system or model revision;
- relevant configuration;
- evaluator identity or version;
- evaluation-protocol identity;
- applicable data-partition identity;
- execution conditions material to the comparison.

The comparison must be materially compatible with the governed claim.

Hetren must not establish advantage by selectively comparing against a weak,
obsolete, mismatched, or otherwise inappropriate baseline when a stronger
relevant comparison is required by the claim.

Where equal-resource comparison is material to a research claim, the resource
conditions must also be identifiable and preserved.

The exact baseline implementations and revisions are defined by Task 8.

Task 3 establishes only the requirement that a comparison claim cannot rely
on an undefined, selectively chosen, or materially incompatible baseline.

## 14. Protected Criteria And Threshold Freeze

Protected acceptance predicates, metrics, thresholds, evaluators, and
qualification rules must be declared before the protected evidence they govern
is inspected.

The protected-evaluation identity must be preserved sufficiently to determine
which criteria governed which result.

A material post-result change to a protected:

- metric;
- threshold;
- acceptance predicate;
- dataset or data partition;
- baseline;
- evaluator;
- qualification protocol;
- verification protocol;

must not be treated as though the original evaluation contract remained
unchanged.

Such a change requires:

1. preservation of the historical result and its original contract;
2. an explicit governed revision;
3. the evidence consequence required by Decision 0002 when applicable;
4. requalification of the affected claim under the revised contract.

A failed protected result may not be converted into `PASS` by silently moving
a threshold, replacing a metric, changing the evaluator, modifying the split,
or otherwise redefining success after observing the result.

Exploratory analysis after protected evaluation may inform a future contract,
but it does not retroactively alter the status of the already governed result.

## 15. Hard Constraints And Invariants

A `GoalContract` must distinguish optimization objectives from mandatory hard
constraints and invariants.

Hard constraints and invariants are non-compensatory.

Failure of a hard constraint or invariant prevents `PASS` even when one or
more optimization measures improve.

Examples may include:

- safety requirements;
- privacy or permission requirements;
- compatibility requirements;
- reliability requirements;
- prohibited regressions;
- rollback requirements;
- locality requirements;
- retention requirements;
- recovery requirements;
- maximum resource constraints;
- execution-isolation requirements.

The exact invariant set belongs to the applicable product, system, release, or
research contract.

Task 3 defines the semantic rule that mandatory invariants cannot be averaged,
weighted, or traded away by unrelated gains.

If an invariant cannot be evaluated because required execution is unavailable,
the outcome follows the `BLOCKED` semantics rather than being assumed to pass.

If the evidence used to evaluate an invariant is invalid, the outcome follows
the `INVALID` semantics.

## 16. Budget Semantics

A governed success contract may constrain resources used to produce or verify
an outcome.

Applicable budgets may include:

- compute;
- wall-clock time;
- external-model usage;
- financial cost;
- tool calls;
- human interventions;
- memory;
- storage;
- network or execution capacity;
- other explicitly bounded resources.

A mandatory budget is part of the acceptance contract rather than an
informational metric.

A candidate that exceeds a mandatory budget does not produce `PASS` under that
contract even if its primary quality measure improves.

Budget exhaustion that prevents the governed evaluation itself from completing
is reported as `BLOCKED` unless the contract explicitly defines budget
exhaustion as a demonstrated acceptance failure.

Budget measurements must remain attributable to the execution they describe.

Task 9 defines the concrete cost and effort ledgers.

Task 3 defines only the semantic requirement that mandatory resource
constraints participate in the governed pass/fail decision.

## 17. Regression Repair Success

A consequential regression-repair claim requires valid evidence that the
governed regression has been repaired under the declared contract.

A regression-repair `PASS` requires all applicable:

1. the material regression is reproduced or otherwise established using
   evidence sufficient to identify the governed failure;
2. the affected behavior and comparison condition are identified;
3. the candidate resolves the governed regression;
4. required hard constraints and invariants remain satisfied;
5. no disqualifying protected regression is introduced;
6. applicable budget requirements remain satisfied;
7. required independent verification passes;
8. regression, candidate, evaluation, and verification evidence are preserved.

Removing a visible symptom does not by itself establish verified repair.

If the original regression cannot be reproduced but other evidence establishes
it sufficiently for the declared claim, that evidence and its limitations must
be preserved explicitly.

A repair that fixes one failure while violating another mandatory acceptance
predicate does not produce `PASS`.

Failure to repair the regression using valid evidence is `FAIL`.

Inability to execute the required repair evaluation follows `BLOCKED`
semantics.

Invalid regression or verification evidence follows `INVALID` semantics.

## 18. Constrained Improvement Success

A consequential constrained-improvement claim requires an identified baseline
and predeclared acceptance semantics.

A constrained-improvement `PASS` requires all applicable:

1. an appropriate and identifiable baseline;
2. a predeclared primary objective or comparison predicate;
3. valid evidence that the candidate satisfies the required improvement
   predicate;
4. required non-regression or non-inferiority predicates;
5. all mandatory hard constraints and invariants;
6. applicable budget constraints;
7. protected evaluation where required;
8. required independent verification.

The contract must declare the direction and meaning of each comparison rather
than assuming that larger or smaller values are always better.

Improvement in a primary measure is invalid as a success claim when it is
obtained by violating a mandatory protected constraint.

A candidate may outperform its baseline on one measure and still `FAIL` the
governed contract because success is conjunctive.

When valid evidence is insufficient to determine whether the required
improvement predicate is satisfied, the result is `INCONCLUSIVE` rather than
an inferred success.

Task 3 does not select numerical improvement thresholds.

Those thresholds must be declared by the later governed evaluation or
research contract before protected evaluation.

## 19. Product Success

Product success concerns the engineering outcome delivered under the governed
product contract.

A consequential product `PASS` requires valid evidence for the applicable
regression-repair or constrained-improvement contract together with all
mandatory product constraints.

Product success may depend on:

- objective satisfaction;
- preserved hard constraints and invariants;
- acceptable regression behavior;
- applicable budget requirements;
- evidence integrity and provenance;
- required recovery or rollback behavior;
- compatibility requirements;
- applicable independent verification.

A positive Native Intelligence research result is not sufficient evidence of
product success.

A positive Adaptive Intelligence scientific result is not sufficient evidence
of product success.

Likewise, failure of a Native Intelligence or Adaptive Intelligence research
hypothesis does not by itself invalidate a separately verified engineering
product result.

Product status must therefore remain independently inspectable from both
research programs.

Product success does not establish that Hetren learned a transferable decision
capability, achieved continual learning, or validated another research claim
unless the evidence required for that separate claim also exists.

## 20. Native Intelligence Research Success

Native Intelligence research success concerns whether Hetren-developed
trainable decision intelligence provides the claimed measurable value under a
governed research contract.

A Native Intelligence `PASS` requires evidence appropriate to the specific
research claim rather than evidence of product usefulness alone.

Depending on the governed claim, relevant evidence may include:

- comparison against meaningful neural and non-neural baselines;
- equally resourced comparison where required by the claim;
- outcome-prediction value;
- action or experiment ranking value;
- stopping or abstention value;
- task-state revision as evidence arrives;
- cold-start behavior;
- held-out system or mechanism transfer;
- leakage controls;
- uncertainty reporting;
- reproducible evaluation;
- applicable independent verification.

The exact research hypotheses and their numerical qualification criteria are
deferred to Task 6.

A successful product repair or improvement does not establish that Native
Intelligence caused, enabled, or materially improved that outcome unless the
research contract contains evidence discriminating that claim.

Using an external model or deterministic heuristic successfully does not by
itself establish Native Intelligence research success.

A Native Intelligence candidate that fails to establish advantage against the
required baseline remains valid negative research evidence.

Negative Native Intelligence evidence must not be hidden, converted into a
product-success claim, or represented as successful learned transfer.

If evidence supports only a narrower learned-capability claim, the reported
Native Intelligence claim must be narrowed accordingly.

## 21. Adaptive Intelligence Scientific Success

Adaptive Intelligence scientific success concerns whether controlled
post-deployment plasticity produces the claimed useful adaptation under an
independently governed scientific contract.

An Adaptive Intelligence `PASS` requires evidence appropriate to the specific
adaptive hypothesis rather than evidence of product usefulness alone.

Depending on the governed hypothesis, required evidence may include:

- measurable target adaptation;
- comparison against strong adaptation baselines;
- retention of protected prior capability;
- locality of the adaptation effect;
- reversibility or qualified rollback;
- sequential stability across repeated adaptation;
- adaptation cost and resource accounting;
- protected or hidden qualification;
- independent evaluation;
- transfer qualification when transfer is claimed;
- reproducibility under the declared experimental protocol.

The exact Adaptive Intelligence hypotheses and their numerical qualification
criteria are deferred to Task 6.

No adaptive candidate may certify its own scientific success.

The process that proposes or performs an adaptive change must not be the sole
authority establishing that the governed adaptive claim passed.

A positive adaptive result does not waive product permissions,
implementation qualification, compatibility, recovery, rollback, evidence
integrity, or independent product verification.

A successful product outcome does not establish adaptive scientific success
unless the governed adaptive hypothesis is independently supported by the
required evidence.

A failed adaptive experiment remains valid scientific evidence.

Failure to support an Adaptive Intelligence hypothesis must not be relabeled
as successful continual learning, safe self-improvement, transferable
experience, or another stronger adaptive claim.

If evidence supports only a narrower adaptive claim, the scientific status
must be narrowed accordingly.

## 22. Transfer Claims

A transfer claim must identify exactly what is claimed to transfer.

Hetren distinguishes at least:

- reuse of shared product infrastructure or authored procedure;
- reuse of an explicit method or strategy;
- Native Intelligence learned decision capability;
- Adaptive Intelligence retained or transferred adaptation.

These are not interchangeable claims.

Reusing the same Core, evaluator semantics, adapter interface, or authored
investigation procedure across environments does not by itself establish
learned transfer.

A Native Intelligence transfer claim requires evidence that the relevant
learned capability remains useful on held-out systems or mechanisms under the
declared transfer protocol.

Such evaluation must control, where applicable, for:

- environment-specific authored strategy;
- protected-case tuning;
- training or evaluation leakage;
- hidden reuse of target-specific information;
- baseline differences;
- onboarding effort or target-specific adaptation.

Adaptive Intelligence transfer is a separate scientific claim.

Evidence for Native Intelligence cross-domain transfer does not establish
Adaptive Intelligence transfer.

Claims involving Experience Capsules, cross-model transfer, cross-architecture
transfer, multimodal adaptive transfer, or another adaptive-transfer mechanism
must satisfy the applicable Adaptive Intelligence qualification contract.

A transfer result that disappears under protected evaluation must be narrowed,
rejected, or requalified rather than preserved as a successful transfer claim.

Concrete held-out systems, split identities, datasets, and numerical transfer
thresholds are defined by later governed tasks.

## 23. E1, E2, And E3 Applicability

The success semantics in this specification apply to all required MVP system
families:

- E1 tool-using agent;
- E2 structured-data ML pipeline;
- E3 vision system.

These environments may use different domain-appropriate measures,
evaluators, artifacts, and execution mechanisms.

They must not silently diverge in the meaning of:

- `PASS`;
- `FAIL`;
- `INCONCLUSIVE`;
- `BLOCKED`;
- `INVALID`;
- evidence validity;
- baseline identity;
- hard constraints and invariants;
- protected-evaluation criteria;
- mandatory budgets;
- independent verification;
- claim narrowing.

An environment-specific evaluator defines what a measure means for that
environment.

The shared success contract defines how those measures are allowed to support
a governed claim.

Environment adapters define how Hetren interacts with a system; they do not
define whether an evaluation result counts as success.

Environment-specific authored investigation strategy must not be used to hide
the absence of shared Core decision capability when a cross-domain or transfer
claim is being evaluated.

Task 4 defines the concrete system taxonomy.

Task 5 defines the initial supported capability matrix.

## 24. Independent Verification

Consequential `PASS` claims require a verification path that is meaningfully
separated from the path that proposed or produced the candidate result.

Independent verification exists to reduce the risk that the same process that
optimized a candidate also defines or manipulates the evidence used to certify
that candidate.

Meaningful separation may be established through one or more of:

- separate evaluation code;
- protected or hidden test data;
- a different execution path;
- a separate evaluator;
- a separately authored verification contract;
- repeated controlled execution;
- independent replay;
- human review for appropriately high-risk decisions.

The required degree of separation depends on the consequence and risk of the
claim.

The candidate under consequential verification must be frozen sufficiently to
prevent the verification result from being tuned into existence.

Material candidate changes after verification begins require a new candidate
identity and applicable requalification.

The verification path must preserve enough identity and provenance to connect
the verified result to:

- the candidate version;
- the governing `GoalContract`;
- the evaluated system version;
- the evaluator and protocol;
- the evidence used;
- the resulting `VerificationReport`.

A proposing engine, adaptive mechanism, external model, implementation path,
or research candidate must not become the sole authority certifying its own
consequential success.

Failure of independent verification returns the governed claim to qualification
or revision rather than allowing the earlier `PASS` to remain authoritative.

Independent verification does not erase valid earlier evidence; it determines
whether that evidence is sufficient for the consequential verified claim.

## 25. Claim Narrowing And Honest Status

The evidence governs the claim.

Hetren must report the strongest claim actually supported by the governed
evidence and no stronger claim.

When valid evidence demonstrates that mandatory acceptance predicates are not
satisfied, the result is `FAIL`.

When valid evidence is insufficient to discriminate between pass and fail,
the result is `INCONCLUSIVE`.

When required evaluation cannot be completed, the result is `BLOCKED`.

When evidence integrity, identity, comparability, or protocol validity cannot
support the claim, the result is `INVALID`.

None of these states may be rewritten as `PASS` because the result is
commercially desirable, scientifically interesting, operationally convenient,
or promising under informal inspection.

If evidence supports only a narrower claim, the claim must be narrowed.

Examples include:

- reporting improvement on one bounded behavior rather than general
  improvement;
- reporting usefulness on one system family rather than cross-domain
  generalization;
- reporting authored method reuse rather than learned transfer;
- reporting target adaptation without claiming retained prior capability;
- reporting association or intervention effect without claiming unsupported
  causality;
- reporting a product result without claiming Native or Adaptive research
  success.

Terms such as `unsupported`, `negative`, and `falsifying` describe the
interpretation or consequence of evidence and claims. They are not additional
evaluation outcome states.

Every governed evaluation still resolves to exactly one of `PASS`, `FAIL`,
`INCONCLUSIVE`, `BLOCKED`, or `INVALID`.

Negative, falsifying, blocked, invalid, unsupported, and inconclusive results
must remain part of the preserved evidence history.

A narrowed or negative claim is not evidence corruption or project failure.

Misrepresenting the status of evidence is itself a qualification failure.

## 26. Deferred Concrete Artifacts

Task 3 establishes shared success semantics but deliberately does not choose
the concrete artifacts governed by later MVP tasks.

The following remain deferred:

- final system taxonomy — Task 4;
- initial supported capability matrix — Task 5;
- specific Native Intelligence and Adaptive Intelligence hypotheses — Task 6;
- protected, development, validation, and other evaluation split identities —
  Task 7;
- concrete baseline implementations and revisions — Task 8;
- concrete engineering cost and effort ledgers — Task 9.

Task 3 may require that these artifacts exist, carry identity, preserve
provenance, or satisfy qualification semantics.

Task 3 must not silently select their final concrete values.

Likewise, this specification does not freeze environment-specific numerical
metrics or thresholds except where an existing governing authority already
requires a semantic rule about them.

Later governed tasks must satisfy the semantics defined here rather than
redefining success independently.

If a later task discovers that these semantics are insufficient, the success
contract must be revised through governed change rather than silently bypassed.

## 27. Relationship To Release And Completion

A successful individual evaluation is not equivalent to product release,
research-program success, or MVP completion.

An `EvaluationRecord` may establish the measured result of one governed
evaluation.

A consequential claim may additionally require an applicable
`VerificationReport` before that claim can be treated as verified.

Neither result automatically satisfies every requirement of the MVP release
gate.

MVP release and completion remain governed by the qualified MVP Charter and
any later accepted release contracts.

At release time, the following statuses remain independently inspectable:

- product release status;
- Native Intelligence research status;
- Adaptive Intelligence scientific status.

No aggregate release label may conceal a failed, unsupported, inconclusive,
blocked, or invalid mandatory status in one of these planes.

A positive Adaptive Intelligence result does not waive product release
requirements.

A positive Native Intelligence result does not waive product release
requirements.

A successful product release does not establish Native Intelligence or
Adaptive Intelligence scientific success.

Task completion also remains separate from evaluation success.

A task becomes complete only after its required implementation,
qualification, preserved evidence, and applicable verification requirements
have been satisfied under the governing task contract.

## 28. Task 3 Qualification Contract

Task 3 may pass only when preserved qualification evidence demonstrates every
condition below.

1. the specification is governed by `AUTH-HETREN-MVP-3.0` and
   `AUTH-HETREN-MASTER-2.0`;
2. `GoalContract` remains the canonical declaration of the governed objective;
3. `EvaluationRecord` remains the canonical measured-outcome record;
4. `VerificationReport` remains the canonical independent-verification record;
5. no competing canonical runtime record named `SuccessContract` is
   introduced;
6. Product, Native Intelligence, and Adaptive Intelligence success remain
   independently reportable;
7. the shared evaluation outcome vocabulary is exactly `PASS`, `FAIL`,
   `INCONCLUSIVE`, `BLOCKED`, and `INVALID`;
8. evaluation outcome states remain distinct from task-lifecycle states;
9. `PASS` is conjunctive across all mandatory acceptance predicates;
10. valid evidence demonstrating a failed mandatory predicate produces `FAIL`
    rather than being rewritten as another state for convenience;
11. invalid evidence cannot establish either `PASS` or `FAIL`;
12. `INCONCLUSIVE` means valid but insufficiently discriminating evidence and
    remains distinct from demonstrated failure;
13. inability to complete the governed evaluation is represented as `BLOCKED`
    rather than inferred target-system success or failure;
14. comparison claims require an identified and materially compatible
    baseline or reference condition;
15. concrete baseline implementations remain deferred to Task 8;
16. protected predicates, metrics, thresholds, evaluators, and qualification
    rules are frozen before the protected evidence they govern is inspected;
17. material post-result changes to protected criteria preserve historical
    evidence, require governed revision, and trigger applicable
    requalification;
18. hard constraints and invariants are non-compensatory and cannot be
    averaged or weighted away by unrelated gains;
19. mandatory budget constraints participate in the governed success decision;
20. budget exhaustion that prevents evaluation completion is distinguished
    from demonstrated target-system failure;
21. regression repair has explicit success semantics covering governed failure,
    repair, constraints, regressions, verification, and preserved evidence;
22. constrained improvement requires a baseline, predeclared improvement
    predicate, non-regression requirements, constraints, and applicable
    verification;
23. consequential success claims require meaningfully separated independent
    verification;
24. the candidate under consequential verification is frozen sufficiently to
    prevent verification-driven tuning;
25. Native Intelligence success requires separate research evidence appropriate
    to the learned-capability claim;
26. failure of a Native Intelligence hypothesis remains valid negative research
    evidence and does not automatically invalidate product success;
27. Adaptive Intelligence success requires separate scientific evidence
    appropriate to adaptation, retention, locality, rollback, stability, and
    applicable cost or transfer claims;
28. no Adaptive Intelligence candidate may be the sole authority certifying
    its own scientific success;
29. Native learned transfer, Adaptive Intelligence transfer, and authored
    infrastructure or method reuse remain distinct claims;
30. E1 tool-using agent, E2 structured-data ML, and E3 vision use the same
    outcome and evidence semantics even when their concrete measures differ;
31. environment adapters define interaction rather than success semantics;
32. evidence supports only the strongest justified claim, with narrower claims
    required when broader claims are unsupported;
33. negative, falsifying, blocked, invalid, unsupported, and inconclusive
    results remain preserved evidence;
34. concrete taxonomy, support boundaries, hypotheses, splits, baselines, and
    cost ledgers remain deferred respectively to Tasks 4 through 9;
35. product release status, Native Intelligence research status, and Adaptive
    Intelligence scientific status remain independently inspectable;
36. no weighted or aggregate success score may convert failure of a mandatory
    predicate, hard constraint, invariant, budget, or verification requirement
    into `PASS`, and no aggregate may collapse the independently reportable
    Product, Native Intelligence, and Adaptive Intelligence statuses;
37. authority-required acceptance predicates, constraints, invariants, budgets,
    evidence requirements, and verification requirements cannot be omitted from
    a `GoalContract` to manufacture `PASS`;
38. consequential-claim requirements cannot be bypassed merely by labeling a
    materially consequential claim non-consequential;
39. primary outcome resolution is deterministic when valid failure, invalid
    evidence, blocked execution, or inconclusive evidence coexist;
40. `unsupported`, `negative`, and `falsifying` remain claim or evidence
    characterizations rather than additional evaluation outcome states.

Qualification must include structural, semantic, authority-alignment,
adversarial, mutation, and regression checks.

Decision 0003 may transition from `PROPOSED` to `ACCEPTED` only after this contract passes qualification.

## 29. Success-Contract Principle

Hetren does not succeed because one number became larger.

Hetren succeeds on a governed claim only when valid evidence demonstrates the
declared objective while every applicable mandatory constraint, invariant,
evidence requirement, budget requirement, and verification requirement remains
satisfied.

Success is therefore a property of the governed claim and its evidence, not of
a favorable metric viewed in isolation.

When the evidence supports failure, uncertainty, blockage, invalidity, or only
a narrower claim, Hetren must preserve and report that result honestly.

The purpose of the success contract is not to make passing easier.

Its purpose is to make it difficult for Hetren, its developers, its research
processes, or its evaluators to mistake a desirable-looking result for a
verified result.

# HEAL Research and Evaluation Preregistration — P09.1

Status: research-contract candidate; no protected P09 HEAL evaluation has begun.

## 1. Purpose

This document preregisters the research direction, terminology, experimental
boundaries, comparison structure, evidence requirements, falsification rules,
and validation ladder for the next Hetren portfolio phase.

Hetren is a real-world engineering and AI research portfolio project.

Hetren is not currently a startup, commercial product, or startup MVP.

Productization, commercialization, customer discovery, or startup planning are
outside this research phase. They may be considered later only if external
interest provides a reason to do so.

The purpose of P09 is to determine whether the proposed HEAL methodology is
technically useful under controlled and increasingly realistic agent workloads.

The research result is allowed to be negative.

A negative result must not be rewritten into a positive result by changing the
methodology after seeing protected evaluation outcomes.

## 2. Governing Engineering Discipline

Hetren uses a hybrid Waterfall + Agile working model.

Waterfall discipline provides:

- explicit phase boundaries,
- frozen research contracts,
- preregistered evaluation rules,
- protected evaluation data,
- evidence fingerprints,
- verification checkpoints,
- claim boundaries,
- and versioned supersession when a frozen contract must change.

Agile discipline provides:

- small implementation increments,
- focused tests,
- frequent review,
- controlled refactoring,
- adaptation of non-frozen implementation details,
- and evidence-driven iteration before the next protected gate.

A frozen scientific rule may not be silently changed because an experiment
produced an unfavorable result.

A changed scientific rule requires a new version, an explicit reason, and a new
protected evaluation boundary.

## 3. Research Is Reference, Not Authority To Copy

External research, standards, engineering systems, and company publications are
used as references for:

- problem existence,
- historical foundations,
- known methods,
- known limitations,
- comparison baselines,
- evaluation design,
- and prior-art boundaries.

They are not specifications for Hetren to copy.

Hetren must derive and test its own architecture and methodology.

Similarity between a Hetren mechanism and prior work must be acknowledged where
known.

No P09 terminology is claimed to be globally novel merely because Hetren uses
a new internal label.

Novelty, if any, must be earned experimentally and through continued prior-art
review.

## 4. Verified Research Basis

The following work informs the P09 problem framing.

### 4.1 Model-based and sequential diagnosis

Raymond Reiter, "A theory of diagnosis from first principles", Artificial
Intelligence, 1987, DOI 10.1016/0004-3702(87)90062-2.

Reference:
https://www.sciencedirect.com/science/article/pii/0004370287900622

This work formalized model-based diagnosis and discussed measurements that can
discriminate among competing diagnoses.

Johan de Kleer and Brian C. Williams, "Diagnosing multiple faults", Artificial
Intelligence, 1987, DOI 10.1016/0004-3702(87)90063-4.

Reference:
https://www.sciencedirect.com/science/article/pii/0004370287900634

This work combined model-based diagnosis with sequential diagnosis and
information-theoretic measurement selection.

These ideas are prior art.

HEAL must not claim to have invented hypothesis discrimination, sequential
diagnosis, entropy, or information-gain experiment selection.

### 4.2 Distributed tracing

Benjamin H. Sigelman et al., "Dapper, a Large-Scale Distributed Systems Tracing
Infrastructure", Google, 2010.

Reference:
https://research.google/pubs/dapper-a-large-scale-distributed-systems-tracing-infrastructure/

Tracing demonstrates how execution evidence can be preserved and connected
across complex systems.

Tracing is not equivalent to diagnosis, causal identification, repair, or
verification.

### 4.3 Test-oracle limitations

Earl T. Barr, Mark Harman, Phil McMinn, Muzammil Shahbaz, and Shin Yoo,
"The Oracle Problem in Software Testing: A Survey", IEEE Transactions on
Software Engineering, 2015, DOI 10.1109/TSE.2014.2372785.

Reference:
https://ieeexplore.ieee.org/document/6963470

A passing execution is useful only relative to an oracle that can meaningfully
distinguish correct from incorrect behavior.

This motivates explicit evidence-role and repair-contrast analysis.

### 4.4 Current agent diagnosis

AgentRx, Microsoft Research, 2026, studies failure localization and root-cause
attribution from long, probabilistic agent trajectories using executable
constraints and evidence-backed violation logs.

Reference:
https://www.microsoft.com/en-us/research/publication/agentrx-diagnosing-ai-agent-failures-from-execution-trajectories/

AgentRx is evidence that agent failure diagnosis is an active research area.

Hetren must therefore not claim that trajectory diagnosis itself is a novel
contribution.

### 4.5 Diagnosis-to-recovery gap

R2Act, Microsoft Research, 2026, evaluates post-diagnosis recovery decisions for
microservice incidents and reports a substantial gap between root-cause
identification and valid recovery action selection.

Reference:
https://www.microsoft.com/en-us/research/publication/can-llms-really-recover-microservice-failures-a-recovery-aware-evaluation-of-diagnosis-to-action-reasoning/

This supports treating diagnosis and repair correctness as separate questions.

### 4.6 Long-horizon production-agent experience

Manus engineering describes long agent loops, tool and environment failures,
mistakes during execution, and the value of retaining failed actions as
evidence.

Reference:
https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus

This is industrial engineering evidence, not peer-reviewed proof and not a
specification for Hetren.

## 5. Research Gap Candidate

P09 does not assert that a worldwide research gap has already been proven.

The candidate gap is narrower:

Can an agent-failure system combine:

1. competing fault explanations,
2. active selection of experiments that discriminate those explanations,
3. repair decisions tied to accumulated evidence,
4. explicit qualification of what validation evidence discriminates,
5. separated post-repair verification,
6. reproducible provenance,
7. and bounded final claims,

in a way that improves reliable repair decisions under fixed budgets?

This is a research question, not a conclusion.

## 6. Main Research Question

The central P09 research question is:

> Under a fixed evaluation budget, does an active experimental diagnosis and
> evidence-qualified repair lifecycle improve verified correct repair decisions
> compared with simpler diagnosis-and-retry approaches?

The system is allowed to answer:

- supported,
- not supported,
- inconclusive,
- or rejected.

## 7. HEAL Working Methodology

HEAL is an internal Hetren working name.

HEAL means:

### H — Hypothesize

Construct and preserve a Rival Fault Set rather than prematurely selecting one
cause.

### E — Experiment

Select and execute a controlled experiment whose expected outcome can
discriminate among remaining fault explanations.

### A — Apply

When evidence supports an actionable diagnosis, construct and evaluate a
candidate repair under controlled conditions.

Apply does not mean production deployment.

Apply does not grant authorization.

### L — Limit

Produce a final Claim Boundary that states exactly what the accumulated evidence
supports and what remains unestablished.

HEAL is not currently claimed as a new scientific discipline or globally novel
algorithm.

## 8. P09 Working Terminology

These are Hetren working terms.

They are architecture vocabulary, not automatic novelty claims.

### 8.1 Rival Fault Set — RFS

The set of fault explanations that remain compatible with currently admitted
evidence.

An RFS is not proof that every real cause is represented.

A missing hypothesis can make the entire diagnosis incomplete.

### 8.2 Separating Experiment — SE

A controlled experiment whose possible outcomes differ for at least two members
of the current Rival Fault Set.

An experiment with identical predicted outcomes for all remaining hypotheses is
not separating for that state.

The idea of discriminating measurements is established prior art.

SE is only Hetren's working label.

### 8.3 Evidence Role — ER

A description of what a piece of evidence is permitted to support.

Initial evidence roles are:

- OBSERVATION,
- REPRODUCTION,
- CAUSE_DISCRIMINATING,
- REPAIR_DISCRIMINATING,
- REGRESSION,
- INDEPENDENT_VERIFICATION.

One artifact may have more than one justified role.

A role must not be assigned merely because the artifact exists.

### 8.4 Repair Contrast — RC

A controlled comparison intended to distinguish a known failing state from a
candidate repaired state for the behavior relevant to the repair claim.

A check that passes on both the known-bad state and candidate state does not
provide repair-discriminating evidence for that behavior.

### 8.5 Verifier Separation Profile — VSP

A structured description of how the verification process differs from the
process that produced and initially evaluated the repair.

VSP is deliberately not a scalar score.

Possible dimensions include:

- execution separation,
- evaluator separation,
- evidence-generation separation,
- model separation,
- implementation separation,
- environment separation,
- data separation,
- and organizational or human separation when applicable.

A VSP records separation properties.

It does not prove independence.

### 8.6 Claim Boundary — CB

The explicit limit of what an Assurance Bundle is allowed to state.

A Claim Boundary must distinguish:

- demonstrated properties,
- assumptions,
- unresolved uncertainty,
- unsupported generalization,
- authorization status,
- and deployment status.

### 8.7 Assurance Bundle — AB

A machine-readable and human-readable evidence package binding:

- the observed failure,
- the relevant trace,
- the Rival Fault Set,
- executed experiments,
- observations,
- posterior or surviving hypotheses,
- diagnosis status,
- candidate repair identity,
- repair-contrast evidence,
- regression evidence,
- verification evidence,
- Verifier Separation Profile,
- provenance and fingerprints,
- Claim Boundary,
- and explicit limitations.

An Assurance Bundle is evidence packaging.

It is not proof of universal correctness.

## 9. Current Frozen Foundation

P09 begins after checkpoint:

`92bbef37cbca690802671cd4e2752b6f9d6d40ac`

The modern regression baseline is 328 tests.

Existing Hetren diagnosis machinery already implements:

- explicit hypotheses,
- explicit experiments,
- deterministic PASS/FAIL predictions,
- hypothesis priors,
- Shannon entropy,
- expected information gain,
- information gain per declared cost,
- deterministic myopic experiment ranking,
- observation replay,
- budget accounting,
- terminal diagnosis,
- inconclusive states,
- and budget exhaustion.

This machinery is prior Hetren foundation.

P09 must not present it as a newly invented HEAL algorithm.

The P09.0C3 checkpoint additionally freezes the semantic distinction:

> Evidence determines whether diagnosis is complete.
> Budget determines whether another experiment may be executed.

## 10. Existing Foundation Is Not Real-World Validation

The current deterministic fixtures are semantic foundation tests.

They do not demonstrate that Hetren can diagnose or repair arbitrary real-world
agents.

They do not establish performance on:

- long stochastic trajectories,
- changing external environments,
- unknown fault classes,
- noisy observations,
- concurrent agents,
- browser agents,
- coding agents,
- production APIs,
- arbitrary tools,
- or arbitrary models.

Passing the current 328-test suite establishes regression correctness of the
implemented portfolio foundation only.

P09 must not compare a tiny deterministic fixture directly with a production
agent and imply equivalent complexity.

## 11. Validation Ladder

P09 uses progressively harder validation layers.

### Layer 0 — Contract and semantic validation

Purpose:

Verify exact behavior of contracts, lifecycle transitions, evidence binding,
hashing, budgeting, and deterministic planner semantics.

Expected tools:

- unit tests,
- deterministic fixtures,
- negative controls,
- mutation-style checks.

This layer establishes implementation semantics only.

### Layer 1 — Controlled multi-step agent environments

Purpose:

Test HEAL against longer trajectories while retaining known hidden fault truth.

Required properties:

- multiple tool or environment interactions,
- persistent state,
- more than one plausible fault explanation,
- controlled fault injection,
- observable evidence separated from latent ground truth,
- and reproducible execution.

Scenario-specific trajectory length and complexity requirements must be frozen
before protected evaluation.

### Layer 2 — Live model-backed controlled experiments

Purpose:

Introduce real model variability while retaining controlled ground truth.

Requirements:

- genuine model calls,
- captured model requests and responses,
- frozen prompts and schemas for an evaluation batch,
- complete run retention,
- no cherry-picking successful calls,
- deterministic offline replay where technically possible,
- and explicit provider/version limitations.

A failed model decision is an experimental outcome.

It is not automatically an invalid run.

### Layer 3 — Realistic agent workloads

Purpose:

Test whether the methodology remains useful when the workflow resembles actual
agent engineering rather than a toy fixture.

Candidate workload classes include:

- coding-agent workflows,
- incident-response workflows,
- browser/tool workflows,
- and multi-tool operational workflows.

At least one final portfolio workload must contain meaningful multi-step
execution, state, external or realistic tools, and failure recovery.

A Layer 3 result must not automatically be generalized to all agents.

### Layer 4 — Public portfolio demonstration

Purpose:

Explain a previously validated workflow clearly to a technical reviewer.

Layer 4 may include:

- backend API,
- frontend,
- evidence visualization,
- reproducible command-line execution,
- and a short demo video.

The demo is communication material.

It does not create scientific evidence beyond the underlying frozen experiment.

## 12. Controlled Fault Families

Initial controlled fault families are:

### F1 — Tool-selection fault

The agent selects an incorrect tool or implementation for the intended
operation.

### F2 — Parameter-transformation fault

The correct tool is selected but one or more parameters are incorrectly
transformed, omitted, or substituted.

### F3 — Sequencing or orchestration fault

Individually valid actions occur in an incorrect order or control-flow path.

### F4 — State or context fault

The agent reasons or acts using stale, incomplete, corrupted, or inappropriate
state.

### F5 — Tool or environment interaction fault

The agent's intended action encounters environment behavior, tool behavior, or
response semantics that invalidate the expected outcome.

### F6 — Validation or oracle weakness

A candidate appears successful because the validation procedure does not
actually discriminate the relevant faulty behavior.

Not every P09 scenario must contain every family.

Each protected scenario must preregister which fault families are in scope.

Unknown and natural failures must be reported separately from controlled
ground-truth faults.

## 13. Experimental Arms

The intended comparison is incremental so individual contributions can be
measured.

### C0 — Trace-only baseline

Receives the initial allowed trace/evidence.

Does not execute diagnosis interventions.

Produces the best diagnosis/repair decision available from the initial evidence
under the scenario's frozen rules.

### C1 — Active-diagnosis baseline

Uses the existing Hetren sequential-diagnosis planner and allowed diagnostic
experiments.

Repair validation remains ordinary scenario validation.

### C2 — Evidence-qualified repair

Uses active diagnosis plus Repair Contrast and explicit Evidence Roles.

No stronger verification-separation claim is added.

### C3 — Full HEAL candidate

Uses:

- Rival Fault Set management,
- active separating experiments,
- evidence-qualified repair,
- Repair Contrast,
- regression evidence,
- separated verification represented by VSP,
- Assurance Bundle generation,
- and bounded final claims.

All comparison arms must receive the same protected case where technically
possible.

Budget differences must be declared rather than hidden.

## 14. Research Hypotheses

### H0 — Null hypothesis

Under fair fixed budgets, the HEAL lifecycle provides no material reliability
advantage over simpler comparison arms.

H0 is a valid final result.

### H1 — Active diagnosis value

Active experiment selection improves controlled hidden-fault identification
relative to trace-only diagnosis under the same diagnosis budget.

### H2 — Diagnosis-to-repair value

Evidence-supported diagnosis reduces incorrect or unnecessary repair attempts
relative to making a repair from the initial plausible diagnosis alone.

### H3 — Repair-contrast value

Repair Contrast reduces false repair acceptance compared with validation that
only checks whether the candidate execution passes.

### H4 — Verification-separation value

Separated verification detects at least some candidate failures or unsupported
claims that same-process candidate validation accepts.

This hypothesis does not assume that greater separation always improves
accuracy.

### H5 — End-to-end HEAL value

The complete HEAL candidate improves verified correct repair decisions under a
frozen resource budget compared with the simpler end-to-end baseline.

## 15. Primary End-to-End Metric

The primary P09 end-to-end metric is:

**Verified Correct Repair Rate under a frozen evaluation budget.**

For controlled cases, a repair counts as verified-correct only when:

1. the candidate addresses the declared controlled fault,
2. the relevant Repair Contrast succeeds,
3. required regression checks succeed,
4. the required verification procedure supports the repair claim,
5. the candidate remains within the scenario's Claim Boundary,
6. and the case satisfies the frozen validity rules.

A merely completed run does not count.

A merely PASSing ordinary evaluation does not count.

A diagnosis alone does not count.

An ELIGIBLE decision does not imply deployment authorization.

## 16. Secondary Metrics

Protected experiments may also measure:

- hidden-fault identification accuracy,
- critical-step or fault-family localization where defined,
- false repair acceptance rate,
- incorrect repair attempt count,
- experiment count,
- declared experiment cost,
- actual tool-call count,
- model-call count,
- token usage,
- monetary model cost where available,
- wall-clock time,
- abstention or inconclusive frequency,
- regression failure rate,
- and evidence-role coverage.

Metrics must be defined before the protected run.

A metric may not be introduced afterward solely because it makes HEAL appear
better.

## 17. Evidence Discrimination Rule

Positive evidence is not automatically informative evidence.

For a repair-relevant check, P09 asks:

> Does the evidence distinguish the known-bad state from the candidate state for
> the behavior named in the claim?

When feasible, Repair Contrast executes the relevant check against:

- the known-bad state,
- and the candidate repaired state.

A result that passes in both states must not be labeled
REPAIR_DISCRIMINATING for that claim.

Regression evidence remains useful but must remain labeled REGRESSION unless it
also satisfies the stronger discrimination requirement.

## 18. Ground Truth and Latent Information

Controlled environments may contain hidden fault truth so outcomes can be
evaluated.

The planner, model, repair selector, and verifier must not consume hidden fault
labels unless the specific experiment explicitly grants access.

Ground-truth data belongs to the evaluation harness.

Leaking it into the treatment invalidates the relevant experiment.

Natural real-world failures may lack perfect ground truth.

Those cases must not be reported with the same certainty as controlled faults.

## 19. Protected Evaluation

Development data and protected evaluation data must remain distinct.

Before a protected run, freeze:

- scenario definitions,
- fault definitions,
- allowed observations,
- allowed interventions,
- baselines,
- budgets,
- model configuration,
- prompts,
- evaluator configuration,
- sample count or run count,
- random seeds where applicable,
- run-validity rules,
- metrics,
- analysis method,
- and expected artifact paths.

The frozen package must be fingerprinted.

After protected results are observed, the package may not be silently edited.

A revised methodology requires a new version and new protected boundary.

## 20. Model-Backed Run Policy

For one protected evaluation batch:

- requested model identity is frozen,
- request schema is frozen,
- prompts are frozen,
- generation parameters are frozen,
- tool schemas are frozen,
- and adapter behavior is frozen.

Provider-side behavior outside Hetren's control must be recorded as a limitation.

Every valid model-backed run counts.

A bad model answer is not discarded because it lowers the result.

A model/tool failure occurring as part of the intended workflow is normally an
outcome, not grounds for replacement.

## 21. Invalid Run Policy

A run may be marked operationally invalid only under preregistered conditions
where the intended treatment was not meaningfully executed.

Examples may include:

- local harness failure before treatment execution,
- corrupted evaluation artifact caused by infrastructure outside the tested
  workflow,
- unavailable required service before the case begins,
- or violation of the frozen evaluation protocol.

Agent reasoning errors, wrong tool choices, schema mistakes, ordinary tool
errors, and recovery failures are generally outcomes and must not be erased.

Invalid runs remain recorded.

## 22. No Rerun-To-Win Rule

Hetren must not rerun a protected case merely to replace an unfavorable valid
outcome.

Repeated trials are allowed only when their count and purpose were frozen
before the protected result was observed.

Every valid repeated trial is retained.

Negative results remain part of the evidence package.

## 23. Fair-Budget Rule

Comparisons must use a declared resource budget.

Depending on the scenario, budget dimensions may include:

- experiment units,
- model calls,
- tool calls,
- tokens,
- monetary cost,
- or wall-clock limits.

A comparison must not give HEAL unrestricted experiments while artificially
constraining its baseline.

When exact budget equality is impossible, the asymmetry must be reported.

## 24. Scenario-Specific Effect Thresholds

This global preregistration does not invent universal numerical superiority
thresholds before the workloads exist.

Instead, every protected scenario must freeze its minimum practically
meaningful effect threshold before protected outcomes are inspected.

A positive numerical difference alone is not automatically scientific support.

Scenario preregistration must define:

- required effect direction,
- minimum meaningful effect where appropriate,
- uncertainty method,
- and rules for supported, unsupported, rejected, or inconclusive outcomes.

## 25. Statistical and Reporting Discipline

Where paired evaluation is possible, use paired case-level comparisons.

Report:

- raw counts,
- rates,
- failures,
- uncertainty,
- resource consumption,
- and all preregistered arms.

If the sample is too small for a meaningful inferential claim, report the result
as a controlled demonstration rather than evidence of general superiority.

Do not search across many analyses and report only the favorable one.

Do not hide failed cases.

## 26. Verifier Separation Profile Rules

VSP must record dimensions separately.

No single numeric independence score is permitted in P09.1.

For each dimension, the profile should eventually distinguish states such as:

- SAME,
- SEPARATE,
- UNKNOWN,
- or NOT_APPLICABLE,

with additional provenance references where needed.

A separate record ID is not infrastructure independence.

A fresh run is not automatically evaluator independence.

A different model is not automatically organizational independence.

A VSP documents the separation that exists.

It does not manufacture stronger independence than the evidence establishes.

## 27. Claim Discipline

P09 preserves the following distinctions:

Observation is not explanation.

Explanation is not causal proof.

Diagnosis is not repair.

Repair is not ordinary evaluation PASS.

PASS is not verification.

Verification is not eligibility.

Eligibility is not authorization.

Authorization is not deployment.

A hash proves byte identity only for the hashed material.

A provider-reported model identifier does not independently prove provider
identity.

Deterministic replay proves reproducibility of the captured result, not fresh
model inference.

## 28. Falsification and Rejection

HEAL must be modified, narrowed, or rejected when evidence shows that:

- trace-only diagnosis performs equivalently or better under fair budgets,
- active experiments add substantial cost without useful diagnostic gain,
- Repair Contrast does not reduce false repair acceptance,
- verifier separation provides no useful additional detection,
- the complete lifecycle does not improve verified correct repair decisions,
- the method fails badly when faults fall outside the registered hypothesis set,
- or existing methods already solve the targeted problem more effectively.

A rejected research hypothesis is an acceptable portfolio result when the
experiment was well designed and transparently reported.

## 29. Missing-Hypothesis Risk

HEAL can only discriminate hypotheses represented in or reachable from its
diagnostic model.

A Rival Fault Set that omits the actual cause may produce false confidence.

P09 must eventually test at least one out-of-set or unknown-fault condition.

Expected safe behavior should favor:

- INCONCLUSIVE,
- UNKNOWN,
- or bounded abstention,

over manufacturing certainty.

The exact unknown-fault policy will be separately preregistered before its
protected evaluation.

## 30. Two Illustrative Use Cases

These examples explain the intended problem class.

They are not evidence that HEAL already solves them.

### Use case A — Coding agent

A coding agent receives a bug report.

It edits code and runs tests.

The tests pass.

Hetren should not automatically conclude that the bug is repaired.

A future HEAL workflow may:

1. preserve multiple possible causes,
2. choose an experiment that separates those causes,
3. diagnose only when evidence supports doing so,
4. construct a candidate repair,
5. run a Repair Contrast against known-bad and candidate states,
6. run regressions,
7. perform separated verification,
8. and produce a bounded Assurance Bundle.

### Use case B — Incident-response agent

An incident-response agent misses severity-3 payment incidents.

Possible causes include:

- wrong filter implementation,
- threshold transformation,
- stale state,
- bad upstream data,
- duplicated filtering,
- or an environment/tool failure.

Hetren should not immediately choose one cause because it appears plausible.

A future HEAL workflow may choose a targeted experiment whose outcomes differ
between these explanations and use the resulting evidence to narrow the Rival
Fault Set before repair.

## 31. Frontend and Public Demonstration

A frontend is part of the eventual portfolio demonstration.

It is not the scientific core.

The frontend should visualize real backend evidence, including where available:

- failure trajectory,
- Rival Fault Set,
- selected experiment,
- selection rationale,
- experiment outcome,
- belief or surviving hypotheses,
- candidate repair,
- Evidence Roles,
- Repair Contrast,
- verification result,
- Verifier Separation Profile,
- Claim Boundary,
- and Assurance Bundle provenance.

The final public video should demonstrate a previously frozen end-to-end case.

Video editing must not hide failed runs that materially change the scientific
interpretation.

## 32. Portfolio Success Standard

Hetren succeeds as a portfolio project when it demonstrates rigorous engineering
and research practice, even if one or more research hypotheses fail.

Important portfolio signals include:

- careful problem definition,
- prior-art awareness,
- strong backend architecture,
- reproducibility,
- explicit contracts,
- controlled experiments,
- real model integration,
- infrastructure discipline,
- useful negative results,
- honest limitations,
- and a clear end-to-end demonstration.

The goal is not to simulate a startup.

The goal is to demonstrate serious AI/ML, backend, infrastructure,
experimentation, evaluation, and reliability engineering.

## 33. P09.1 Freeze Boundary

P09.1 freezes the research protocol before HEAL implementation begins.

P09.1 does not:

- implement new HEAL runtime behavior,
- run protected HEAL experiments,
- claim research superiority,
- claim general agent reliability,
- claim worldwide novelty,
- add a frontend,
- authorize deployment,
- or change P07/P08 frozen evidence.

After this contract is frozen, implementation proceeds in small validated
increments.

Before each protected experiment, a scenario-specific preregistration must be
frozen.

## 34. P09.1 Exit Criteria

P09.1 may be checkpointed only when:

- this contract is structurally validated,
- terminology and claim limits are explicit,
- comparison arms are explicit,
- hypotheses are falsifiable,
- the validation ladder separates deterministic foundation from realistic agent
  testing,
- negative-result handling is explicit,
- rerun rules are explicit,
- verifier separation is multidimensional rather than a fake scalar,
- Waterfall gates and Agile iteration are both preserved,
- the current 328-test modern baseline remains green,
- P07/P08 frozen evidence remains preserved,
- protected historical untracked material remains untouched,
- and no protected HEAL result has yet been observed.

## 35. Baseline Freeze Requirements

A comparison arm is not sufficiently specified merely by giving it a name.

Before protected evaluation, every executable comparison arm must freeze:

- the exact implementation or external system version where applicable,
- model identity where applicable,
- prompts,
- tool schemas,
- allowed evidence,
- allowed interventions,
- repair-generation procedure,
- validation procedure,
- stopping rule,
- and resource budget.

For model-driven baselines, changing the prompt after seeing protected outcomes
creates a new baseline version.

C0 must not mean an informal "best effort" whose behavior changes from case to
case.

C0 must become one exactly reproducible trace-only procedure before a protected
comparison begins.

Where practical, at least one protected evaluation phase should include a
credible comparison method originating outside Hetren.

Possible external comparison candidates must be chosen from methods that are
actually available, reproducible, and relevant to the frozen task.

If no suitable external method can be reproduced fairly, the evaluation must
state that limitation explicitly rather than implying state-of-the-art
superiority.

## 36. Primary-Metric Denominator

For a protected batch, Verified Correct Repair Rate is:

    number of valid protected cases satisfying every
    verified-correct requirement
    -------------------------------------------------
    total number of valid protected cases in the batch

The denominator is not:

- repair attempts only,
- successful diagnoses only,
- cases where HEAL chose to act,
- or cases remaining after unfavorable valid outcomes are removed.

A valid abstention, INCONCLUSIVE result, incorrect diagnosis, incorrect repair,
failed repair, or verification rejection remains in the denominator and does
not count as a verified-correct repair.

Operationally invalid runs are reported separately under the frozen invalid-run
policy.

## 37. Invalid-Run Accounting

Invalidation criteria must be enumerated before a protected batch begins.

Each invalid run must preserve:

- case identity,
- attempted arm,
- invalidation reason,
- failure phase,
- available evidence,
- and whether the failure occurred before or after treatment execution began.

The report must include:

- total scheduled runs,
- valid runs,
- invalid runs,
- and invalid counts by preregistered reason.

If invalidation rates differ materially between comparison arms, that
difference must be reported.

A high invalid-run rate may itself indicate an engineering failure.

Invalid runs must never be silently replaced until a desired sample count is
reached unless a preregistered replacement rule explicitly requires that
procedure.

## 38. Hidden-Truth Leakage Audit

Controlled fault truth must be isolated from the treatment path.

Before protected evaluation, the implementation must define which components
may access:

- fault injection configuration,
- ground-truth fault labels,
- reference repair information,
- protected expected outcomes,
- and evaluation-only metadata.

The following components must not receive hidden truth unless the particular
experiment explicitly declares otherwise:

- diagnosis planner,
- model under evaluation,
- repair selector or repair generator,
- ordinary candidate evaluator,
- and independent verifier.

A protected run package must contain enough evidence to audit this separation.

A passing result is invalid as scientific evidence if hidden evaluation truth
was exposed to a component whose behavior is being measured.

## 39. Human Intervention Policy

Each protected arm must declare whether human intervention is permitted.

When an arm is intended to measure autonomous behavior, humans must not:

- rewrite a diagnosis,
- repair a model response,
- choose a more favorable experiment,
- manually correct tool arguments,
- replace a failed repair,
- or selectively decide which valid run should count.

Human actions required for infrastructure operation must be recorded.

A human-assisted arm may be studied, but it must be labeled separately from an
autonomous arm.

## 40. Stochastic Batch Identity And Provider Drift

Model-backed evidence must record enough information to identify one experimental
batch.

Where available, preserve:

- requested model identifier,
- provider-reported model identifier,
- adapter version,
- prompt and schema fingerprints,
- generation parameters,
- execution timestamp,
- response identity,
- token usage,
- and provider evidence fingerprints.

A provider may change behavior behind a stable public model name.

Therefore cross-date model runs must not automatically be treated as executions
of an identical underlying model.

Unexpected provider drift is a limitation and potentially a separate
experimental factor.

## 41. Unknown-Fault Requirement

Missing-hypothesis behavior is not optional evidence for a strong HEAL claim.

Before P09 supports a claim that HEAL can safely manage realistic fault
ambiguity, at least one protected controlled evaluation must contain cases where
the true fault is not represented by the initial Rival Fault Set.

That evaluation must test whether the system:

- preserves ambiguity,
- expands or challenges its hypothesis model where the registered method allows,
- returns INCONCLUSIVE or UNKNOWN where appropriate,
- or incorrectly manufactures certainty.

The expected behavior and acceptance criteria must be frozen before those
protected outcomes are observed.

## 42. Held-Out Scenario Requirement

At least one higher-layer protected evaluation must use cases not used to tune
the implementation, prompts, thresholds, experiment definitions, or repair
logic.

A case is not genuinely held out when its exact hidden fault and expected repair
were inspected during implementation.

Development cases and protected cases must have separately fingerprinted
manifests.

The final portfolio demo may use a previously evaluated case for communication,
but the scientific result must also contain protected evidence that was not
selected after viewing every candidate case.

## 43. Gold-State Comparison Where Available

For controlled repair experiments, when a known-correct reference state exists,
the evaluation should preserve three distinct states:

- known-bad state,
- candidate repaired state,
- and reference or gold state.

Repair Contrast primarily asks whether the candidate meaningfully differs from
the known-bad state for the claimed behavior.

Comparison with a gold state can provide additional evidence but must not be
used to leak the reference repair into the repair-generation process.

Passing the same test as the gold state is not proof that the candidate and gold
state are behaviorally equivalent in all respects.

## 44. Multiple Analyses And Exploratory Results

The primary hypothesis, primary metric, primary comparison, and analysis method
for a protected batch must be declared before results are observed.

Secondary metrics may be reported.

Exploratory analyses discovered after viewing the data must be labeled
exploratory.

An exploratory favorable result must not be rewritten as though it were the
original preregistered primary endpoint.

When multiple statistical comparisons are performed, the report must disclose
the comparison family and the uncertainty or correction approach used.

## 45. Technology Introduction Gate

P09 research requirements determine technology choices.

Technology choices must not determine the research question.

Before adding a major infrastructure, model-serving, agent-protocol, storage,
frontend, orchestration, or observability technology, the project must state:

- the problem requiring the technology,
- why the current stack is insufficient,
- realistic alternatives,
- implementation and operational cost,
- research or portfolio value,
- and whether the technology changes any frozen experimental boundary.

Examples include:

- Kubernetes,
- Terraform,
- MCP,
- GPU model serving,
- workflow queues,
- new databases,
- observability platforms,
- and frontend frameworks.

A technology must not be added solely to increase the number of technologies
listed on a resume.

User approval is required before intentionally introducing a major new
technology into Hetren.

## 46. Next Gate

After P09.1 is frozen, the next phase must not jump directly to a polished demo.

The next implementation work should build the smallest executable HEAL contracts
and controlled evaluation machinery needed to test the preregistered research
questions.

Every later increase in realism must preserve the distinction between:

1. semantic correctness of the foundation,
2. controlled research evidence,
3. model-backed evidence,
4. realistic workload evidence,
5. and public demonstration.

Those levels must never be collapsed into one claim.

## 47. Component Attribution And Ablation Rule

An end-to-end HEAL result cannot by itself establish which HEAL component caused
an observed improvement.

Where a hypothesis concerns one component, the corresponding protected
comparison must vary that component while holding other relevant factors fixed
where technically possible.

In particular:

- H1 must isolate active diagnosis from trace-only diagnosis.
- H3 must isolate Repair Contrast from ordinary candidate validation.
- H4 must isolate verification separation from same-process verification.
- H5 may evaluate the complete lifecycle end to end.

C3 may remain the full HEAL system, but C3-versus-C0 alone is insufficient
evidence for H1, H3, or H4 individually.

Ablations must not be invented after viewing protected results merely to obtain
a favorable explanation.

## 48. Independent Repair-Correctness Oracle

For controlled repair cases, repair correctness must be determined independently
of the verifier whose behavior is being evaluated.

The evaluation harness must own a hidden repair-correctness oracle or equivalent
ground-truth criterion established before the protected run.

The oracle may use controlled fault truth, reference behavior, protected tests,
or other evaluation-only information unavailable to the treatment.

The treatment-side verifier must not receive this hidden correctness label.

For controlled cases:

    correct repair

and:

    verifier accepted repair

are separate variables.

The primary joint outcome may require both, but verification acceptance must not
define repair correctness by itself.

Reports must preserve enough information to distinguish at least:

- correct and verifier-accepted,
- correct and verifier-rejected,
- incorrect and verifier-accepted,
- incorrect and verifier-rejected.

This permits measurement of false acceptance and false rejection rather than
hiding both inside one end-to-end rate.

## 49. Observable-Information Parity

Comparison arms must begin with the same case and the same initial observable
information unless the information difference is itself the explicitly
preregistered treatment.

Where technically applicable, freeze parity for:

- initial trace,
- initial environment state,
- model access,
- tool definitions,
- repair-generation mechanism,
- candidate representation,
- and evaluation budget.

HEAL must not receive evaluation-only metadata unavailable to the baseline.

A baseline must not be deliberately deprived of ordinary observable evidence
solely to make HEAL appear superior.

Information introduced by an actively executed experiment is permitted to
differ because obtaining that information is the intervention being evaluated.

## 50. Same-Candidate Validation Comparisons

When testing a validation or verification mechanism rather than repair
generation, the compared procedures should evaluate the same candidate repair
where technically possible.

For H3, the preferred comparison is:

- identical candidate repair,
- identical relevant starting state,
- ordinary validation versus Repair Contrast.

For H4, the preferred comparison is:

- identical candidate repair,
- identical source evaluation evidence,
- same-process verification versus the preregistered separated verification
  procedure.

Allowing different comparison arms to generate different repairs can confound
repair-generation quality with validation quality.

Any unavoidable candidate mismatch must be reported.

## 51. Experiment-Cost Calibration

Declared experiment cost influences Hetren's current information-gain-per-cost
planner and therefore cannot be treated as harmless metadata.

Before protected evaluation, each scenario must define how declared experiment
costs are assigned.

The cost-assignment rule must not be tuned after observing protected outcomes.

Possible cost bases include:

- fixed synthetic units with an explicit rationale,
- expected tool-call count,
- expected model-call count,
- expected token use,
- expected monetary cost,
- expected latency,
- or a preregistered composite.

Synthetic cost units are allowed for controlled research but must not be
misrepresented as real operational cost.

Declared cost and realized resource consumption should both be reported when
available.

## 52. Prior-Probability Discipline

Hypothesis priors can affect experiment selection and therefore must be treated
as experimental inputs.

Before protected evaluation, the source of hypothesis priors must be frozen.

Initial controlled benchmarks may use uniform priors when that is the declared
design.

Non-uniform priors require a preregistered source that does not use protected
case truth.

Protected labels must not be used to tune priors.

Post-hoc prior sensitivity analysis may be useful but must be labeled
exploratory unless separately preregistered.

## 53. Intervention Isolation And State Side Effects

A diagnostic experiment may alter the state of the system it observes.

Therefore realistic HEAL experiments must define whether an intervention is:

- read-only,
- executed against an isolated snapshot,
- reverted after execution,
- or intentionally state-changing.

Where feasible, competing experiments should begin from equivalent state.

When equivalent reset is impossible, the experiment sequence and resulting
state changes become part of the evidence and must be preserved.

An intervention that accidentally repairs, corrupts, or otherwise changes the
target can invalidate causal interpretation if that side effect is ignored.

State fingerprints, snapshots, event logs, or equivalent provenance should be
used where technically appropriate.

## 54. Experiment-Prediction Misspecification

The current Hetren diagnosis foundation uses deterministic PASS/FAIL predictions
for experiment outcomes.

That is a controlled foundation assumption.

It is not automatically valid for realistic stochastic agents.

Higher-layer evaluation must measure or explicitly bound cases where observed
experiment outcomes disagree with registered hypothesis predictions.

Such disagreement may indicate:

- an incorrect hypothesis,
- an incomplete Rival Fault Set,
- stochastic behavior,
- environment drift,
- an incorrect experiment model,
- or execution failure.

The system must not silently force an unexpected observation into the nearest
expected outcome merely to preserve a clean posterior.

Before Hetren makes stronger claims about stochastic real-world diagnosis, the
project must either:

- support an appropriate uncertainty/noise model,
- or explicitly scope the claim to environments where deterministic experiment
  predictions are justified.

The required extension must be earned by evidence rather than added
prematurely.

## 55. Protected Experiment-Design Leakage

Protected cases must not receive hand-tailored diagnostic experiments that were
constructed after a developer inspected the hidden fault for that exact case.

Before a protected batch, experiment definitions or experiment-generation rules
must be frozen without access to protected hidden labels beyond information
explicitly allowed to the evaluation designer by the preregistered protocol.

If controlled fault generation requires a privileged fixture builder, that
builder must remain outside the treatment path.

The protected artifact package should make it possible to distinguish:

- case construction,
- hidden evaluation truth,
- treatment-visible experiment definitions,
- and treatment execution.

Experiment design that directly encodes the protected answer invalidates the
affected scientific comparison.

## 56. Single-Fault And Multi-Fault Scope

Initial controlled P09 experiments may intentionally inject exactly one primary
fault per case.

This is useful for identifying whether the core methodology works under a
well-defined causal target.

Success on single-fault cases does not establish capability on concurrent,
interacting, or cascading faults.

Any claim extending Hetren to multi-fault diagnosis requires a separately
preregistered evaluation containing multiple simultaneous or interacting fault
conditions.

Until such evidence exists, the Claim Boundary must explicitly preserve the
single-fault limitation where applicable.

## 57. External-Comparison Claim Boundary

Internal baselines can establish whether HEAL improves over the specific
preregistered Hetren baselines.

They cannot by themselves establish that HEAL is superior to existing external
research systems or the state of the art.

A claim such as:

    HEAL outperforms existing agent-diagnosis methods

requires a fair protected comparison against relevant external methods.

If a credible external method cannot be reproduced because code, data,
infrastructure, licensing, or task compatibility prevents a fair comparison,
the report must state that limitation.

In that situation, the permitted claim is limited to the observed comparison
against the preregistered internal baselines.

## 58. False-Certainty Reporting

For controlled cases with known hidden truth, P09 must separately track cases
where the system reports a specific diagnosis that is wrong.

This is distinct from abstention or INCONCLUSIVE behavior.

Where applicable, report:

- correct specific diagnosis,
- incorrect specific diagnosis,
- INCONCLUSIVE or UNKNOWN,
- and budget exhaustion without diagnosis.

For unknown-fault evaluation, a confident in-set diagnosis when the true cause
is outside the registered Rival Fault Set is a false-certainty event.

False certainty is a first-class reliability failure and must not be hidden
inside aggregate accuracy.

## 59. Safety Boundary For Realistic Workloads

Realistic higher-layer experiments must not require uncontrolled destructive
actions against real production systems.

Coding, browser, infrastructure, or operational workloads should use:

- sandboxed environments,
- test accounts,
- isolated repositories,
- disposable infrastructure,
- controlled APIs,
- or equivalent safety boundaries

when an intervention could mutate state or create external consequences.

A sandbox demonstrates controlled execution.

It does not establish production safety or deployment authorization.

## 60. P09.1 Final Scientific Freeze Conditions

Before P09.1 is frozen, the contract must preserve all of the following:

- component-level hypotheses have isolating comparisons,
- repair correctness is evaluation-owned rather than verifier-defined,
- baseline information access is fair,
- validation mechanisms can be compared on the same repair candidate,
- experiment costs cannot be outcome-tuned,
- priors cannot be learned from protected labels,
- intervention side effects are accounted for,
- deterministic experiment predictions are recognized as a limited assumption,
- protected experiment definitions cannot encode hidden answers,
- single-fault evidence cannot silently become multi-fault evidence,
- external superiority requires external comparison,
- false certainty is reported separately from abstention,
- and realistic experiments use controlled safety boundaries.

These requirements strengthen the research protocol.

They do not constitute evidence that HEAL works.

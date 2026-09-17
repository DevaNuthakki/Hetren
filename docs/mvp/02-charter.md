# Hetren MVP Charter

**Document:** MVP Charter
**Version:** 1.1.0
**Status:** Qualified
**MVP Task:** 1 / 100
**Execution authority:** Hetren Unified MVP and Adaptive Intelligence Execution Plan v3.0 (`AUTH-HETREN-MVP-3.0`)
**Long-term authority:** Hetren Unified Product, Intelligence, and Adaptive Research Master Specification v2.0 (`AUTH-HETREN-MASTER-2.0`)
**Research programs:** Native Hetren Intelligence and Adaptive Intelligence

---

## 1. Purpose

The Hetren MVP exists to test whether one shared AI engineering system can
investigate, improve, verify, and preserve learning across materially different
AI systems without becoming a collection of domain-specific workflows.

The MVP is not a speech product.

The MVP is not an ASR debugging product.

The MVP is not a collection of disconnected evaluation scripts.

The MVP must demonstrate a shared engineering and intelligence layer that can
operate across different AI system families while preserving enough evidence
for its conclusions to be reviewed, reproduced, challenged, and revised.

The central MVP question is:

> Can Hetren construct and revise useful engineering methods from system
> capabilities, observations, experiments, evidence, and outcomes across
> multiple kinds of AI systems?

The MVP succeeds only if the answer is supported by measured evidence rather
than architecture claims or demonstrations alone.

---

## 2. Authority And Change Control

The current execution authority is the Hetren Unified MVP and Adaptive
Intelligence Execution Plan v3.0 (`AUTH-HETREN-MVP-3.0`).

The long-term product, architecture, intelligence, and research boundary is
the Hetren Unified Product, Intelligence, and Adaptive Research Master
Specification v2.0 (`AUTH-HETREN-MASTER-2.0`).

The earlier Product Specification v1.4, Cross-Domain MVP v2.0, Neural
Intelligence Research and MVP Design v1.0, and Adaptive Intelligence Master
Plan v1.0 remain preserved source-lineage and historical references. They are
not the primary authority for new implementation decisions.

Hetren maintains two distinct but connected intelligence research programs:

- Native Hetren Intelligence;
- Adaptive Intelligence.

They may share canonical contracts, evidence semantics, execution
infrastructure, permissions, evaluation, verification, and release controls,
but they retain separate hypotheses, experiments, qualification evidence, and
scientific status.

Neither research program may create an alternate Hetren Core, alternate
permission model, or alternate verification authority merely for convenience.

Candidate architectures, algorithms, numerical settings, adaptation
mechanisms, and scientific superiority claims remain hypotheses until
qualified by evidence.

A negative Adaptive Intelligence result does not by itself invalidate the
Hetren engineering product.

A positive Adaptive Intelligence result does not waive product requirements
for permissions, implementation, verification, recovery, compatibility,
rollback, or evidence integrity.

Changes to this charter require an explicit decision record.

Observed experimental results must not silently redefine success criteria.

---

## 3. MVP Outcomes

The MVP must produce evidence for five outcomes.

### 3.1 Useful Product

A user can bring an AI engineering problem into Hetren and move through a
coherent workflow from problem definition to investigation, candidate change,
verification, and preserved release evidence.

### 3.2 Shared Method

Hetren can construct or revise an investigation or improvement method from
available system capabilities rather than requiring a hard-coded workflow for
each domain.

### 3.3 Native Intelligence Research

Hetren contains a native learning or reasoning research system that learns
from audited engineering trajectories and is experimentally evaluated as a
distinct system rather than being represented only by prompts to an external
model.

The native candidate is not required to prove superiority for the product to
remain useful, but it must be implemented, trained, compared, ablated, and
reported honestly.

### 3.4 Adaptive Intelligence Research

Hetren runs a separate adaptive-intelligence research program that tests
whether deployed neural systems can acquire useful new behavior through
controlled, reversible, and verifiable plasticity while preserving prior
capabilities.

The adaptive program must produce a scientifically explicit status such as
supported at the current gate, inconclusive, pivoted, stopped, or blocked.

Product polish must never be used as evidence that adaptive intelligence
succeeded.

### 3.5 Practical Value

The system records enough information to evaluate whether its work reduces
engineering effort, improves outcomes, reduces regressions, or produces other
measurable practical value.

---

## 4. Required Problem Types

The same Hetren Core must support at least two engineering problem types.

### 4.1 Regression Repair

Given a previously acceptable system and a changed system, Hetren must help:

1. reproduce the material regression;
2. characterize the failure;
3. identify relevant changes or hypotheses;
4. design discriminating experiments;
5. generate or evaluate candidate remedies;
6. implement an approved change;
7. independently verify the result;
8. preserve the regression and verification evidence.

### 4.2 Constrained Improvement

Given an existing system and an explicit objective, Hetren must help improve the
system while respecting declared constraints such as quality, latency, cost,
safety, reliability, resource usage, or compatibility.

Improvement is invalid if the primary metric improves by violating an
undeclared or protected constraint.

---

## 5. Required System Families

The MVP must demonstrate the shared architecture on all three required system
families.

### E1 — Tool-Using Agent

A system that performs tasks through model reasoning, tools, APIs, state, or
multi-step execution.

The environment must exercise capabilities such as:

- task success;
- tool choice;
- tool arguments;
- sequencing;
- recovery from tool failure;
- state handling;
- cost or latency constraints.

### E2 — Structured-Data ML Pipeline

A trainable or configurable machine-learning pipeline operating on structured
data.

The environment must exercise capabilities such as:

- data preparation;
- training;
- evaluation;
- feature or configuration changes;
- model comparison;
- reproducibility;
- constrained improvement.

### E3 — Vision Model Or Service

A vision model, model pipeline, or vision-backed service.

The environment must exercise capabilities such as:

- image inputs;
- model inference;
- evaluation;
- perturbation or failure analysis;
- candidate changes;
- verification.

No single environment is allowed to define the architecture of Hetren Core.

Speech may later be used as an additional environment, benchmark, adapter, or
design-partner use case, but it is not the foundation of the MVP.

---

## 6. Shared Architecture Requirement

The three system families must use the same conceptual Hetren Core.

Domain-specific code is permitted where interaction with the target system
requires it, but domain-specific behavior must remain behind explicit
capability, adapter, evaluator, or environment boundaries.

The shared system must own concepts including:

- goals;
- constraints;
- system snapshots;
- capability discovery;
- method proposals;
- experiments;
- observations;
- evidence;
- candidate changes;
- verification;
- learning trajectories;
- release memory.

A domain adapter describes how Hetren can interact with a target system.

An evaluator describes how an outcome is measured.

Neither adapter nor evaluator is allowed to become the hidden intelligence
layer.

The intelligence layer decides what to investigate, what evidence is missing,
what experiment to propose, and when a method should be revised.

The planner may propose an action but must not grant itself authority to execute
or approve that action. Authorization belongs to the Action Gateway and
governance layer. Evidence, evaluation, authorization, and verification records
remain authoritative outside neural state.

---

## 7. Required Core Records

The initial shared model must be capable of representing at least:

- `GoalContract`
- `SystemSnapshot`
- `CapabilityProfile`
- `MethodProposal`
- `ExecutionRecord`
- `EvaluationRecord`
- `CandidateChange`
- `VerificationReport`
- `ExperienceRecord`
- `ReleaseRecord`
- `LearningTrajectory`

Names and physical schemas may evolve.

The semantic responsibilities may not disappear without an explicit decision
record.

---

## 8. Behavioral Engine

The Behavioral Engine investigates a system from externally observable
behavior.

For MVP qualification, it must support an exercised closed loop that can:

1. inspect available capabilities;
2. propose informative tests or experiments;
3. execute or request execution;
4. observe outcomes;
5. update hypotheses;
6. identify evidence gaps;
7. revise the investigation method;
8. bound a failure or improvement region;
9. recommend the next useful action.

The Behavioral Engine must not assume access to model internals.

This allows Hetren to operate against APIs, agents, hosted models, services,
pipelines, and other black-box or gray-box systems.


---

## 9. Internal Engine

The Internal Engine investigates systems for which internal model access is
available.

For MVP qualification, Internal Engine coverage must include at least one
small open CNN-family system and at least one small open Transformer-family
system.

This qualification coverage does not freeze the architecture of Hetren's
native neural intelligence research system.

For MVP qualification, the Internal Engine must exercise at least:

- activation capture;
- representation or component diagnostics;
- at least one reversible intervention or ablation;
- comparison of pre-intervention and post-intervention behavior;
- verification of the intervention effect.

The architecture should remain capable of evolving toward:

- broader layer or component comparison;
- masking;
- targeted perturbations;
- decoding or execution variants;
- richer causal or intervention-oriented experiments.

The Internal Engine must not be implemented as a collection of visualizations
with no experimental consequence.

An internal observation becomes useful evidence only when it can support or
challenge a hypothesis, predict behavior, discriminate between explanations,
or motivate a testable intervention.

---

## 10. Relationship Between Behavioral And Internal Engines

The engines are complementary.

Behavioral evidence may identify where a system fails without explaining the
mechanism.

Internal evidence may identify candidate mechanisms without establishing their
external consequence.

For MVP qualification, at least one investigation where both engines are
available must combine Behavioral and Internal evidence within the same
governed investigation and decision path.

Neither engine is allowed to claim causal understanding solely from
correlation.

Any material internal claim that implies mechanism or causality must be
supported by controlled intervention or other discriminating evidence
appropriate to that claim.

If such evidence cannot be obtained, the claim must remain explicitly
observational or correlational.

---

## 11. Native Neural Intelligence Research

The MVP must contain a native research track from the beginning.

The objective is not merely to call a larger external model.

The objective is to investigate whether a trainable Hetren-native system can
learn useful engineering state, action preferences, predictions, or method
selection from audited engineering trajectories.

For MVP qualification, the native core must be implemented, trained, and
evaluated.

Its initial responsibilities must include:

- outcome prediction;
- task-state revision as evidence arrives;
- experiment selection;
- improvement selection;
- calibrated stopping.

The primary transfer evaluation must freeze the shared neural weights, connect
unfamiliar systems through declared interfaces, and test whether useful
decisions improve without adding a new hand-authored investigation strategy
for the target environment.

Any external language or code generator used in controlled comparisons must be
disclosed so the contribution of Hetren-native computation can be evaluated
separately.

The current provisional research direction may include:

- a relatively small trainable core;
- typed observations;
- typed actions;
- explicit system relationships;
- experiment outcomes;
- cost information;
- latent state;
- action prediction;
- outcome prediction;
- matched experiments;
- learning from engineering trajectories.

Any parameter-count target, architecture, training objective, or representation
scheme remains provisional until supported by the dedicated research authority
and experiments.

The MVP must separate:

- research hypothesis;
- implementation;
- experiment;
- evidence;
- interpretation;
- claim.

A successful demonstration is not automatically a validated research result.

---

## 12. Adaptive Intelligence Research

Adaptive Intelligence is a distinct scientific workstream from Native Hetren
Intelligence.

Its central research question is whether a deployed neural system can acquire
useful new behavior from experience through controlled, reversible, and
verifiable plasticity while preserving prior capabilities and selectively
retaining, consolidating, or transferring useful adaptation.

Hetren Governed Plasticity, or HGP, is a working research hypothesis. It is not
an established product capability.

The adaptive research program must preserve a clear distinction between:

- experience capture;
- candidate adaptation;
- sandbox execution;
- target evaluation;
- related-case generalization;
- locality and retention evaluation;
- critical invariants;
- rollback;
- temporary promotion;
- hidden qualification;
- persistence or rejection;
- consolidation;
- transfer.

The MVP adaptive workstream must establish research governance before
scientific promotion. At minimum this includes:

- numbered research decisions for material hypothesis, metric, threshold,
  model, data, baseline, and algorithm changes;
- predeclared hypotheses and qualification criteria;
- protected or hidden qualification data whose identity is preserved;
- explicit separation between development and final qualification;
- pinned model and baseline revisions;
- reproducible experiment manifests;
- critical invariants;
- rollback qualification;
- negative-result preservation;
- invalidation and rerun rules when evaluation or training defects are found.

The program must compare HGP or any successor mechanism against strong
relevant adaptation baselines rather than weak or selectively chosen
comparators.

The MVP adaptive track must exercise the early scientific program, including
baseline reproduction, bounded HGP experiments, held-out adaptation
measurement, locality or retention measurement, and rollback verification.

Later claims involving long sequential learning, consolidation, Experience
Capsules, cross-model transfer, multimodal generality, or scaling require their
own scientific gates and are not inherited from an earlier result.

No adaptive candidate may certify its own success.

Protected qualification, independent evaluation, and declared invariants
remain authoritative over model confidence or proposal quality.

A failed adaptive experiment is valid scientific evidence.

If the adaptive hypothesis is unsupported, inconclusive, or requires a pivot,
the result must be recorded without being converted into a product-success
claim.

The engineering product may continue toward qualification when Adaptive
Intelligence fails, provided product claims do not imply the failed scientific
capability.

A positive adaptive result does not authorize deployment, permanent
persistence, broad safety claims, or general transfer without the corresponding
product and scientific qualification.

Detailed Adaptive Intelligence research artifacts belong under:

`docs/research/adaptive_intelligence/`

Experimental Adaptive Intelligence implementation belongs under:

`research/adaptive_intelligence/`

---

## 13. External Generative Models

External models may be used as engineering accelerators or system components.

They may assist with tasks such as:

- proposing hypotheses;
- generating candidate code;
- summarizing evidence;
- generating experiment proposals;
- assisting users;
- producing drafts.

External model output must not be treated as evidence merely because it was
generated by a capable model.

Material outputs must pass through the same evidence and verification system as
other candidate actions.

The Hetren-native research claim must remain separable from external generator
performance.

---

## 14. Private Execution

The MVP must preserve a clear boundary between the Hetren control plane and
private execution.

For MVP qualification, private execution must exercise:

- runner identity;
- scoped credentials;
- authenticated job retrieval;
- leases and heartbeats;
- timeouts and cancellation;
- execution budgets;
- artifact controls;
- a defined sandbox boundary;
- controlled egress policy;
- authenticated evidence return.

A requirement may be satisfied by a deliberately constrained MVP implementation,
but not by documentation or an unused interface alone.

Private-execution qualification must also exercise tenant/project authorization,
retry and duplicate-side-effect protection, runner loss, partial artifact
return, stale capabilities, cancellation, budget exhaustion, expired
credentials, evaluator failure, restoration and cleanup, cross-run cache
contamination, secret leakage, and unauthorized side effects.

A failed runner or evaluator must never be translated into successful
verification.

Customer-private data must not become training data for native Hetren research
by default.

Any future use of private data for learning requires an explicit governance
decision and consent model.

---

## 15. Evidence Principle

Hetren must separate:

- observation;
- interpretation;
- hypothesis;
- experiment;
- result;
- decision;
- claim.

For consequential evaluations and decisions, the system must preserve enough
provenance to answer:

- what system was evaluated;
- what version was evaluated;
- what inputs were used;
- what configuration was active;
- what method selected the experiment;
- what action was performed;
- what result occurred;
- what evidence supported the decision;
- what limitations remained.

Material evidence must have an integrity mechanism sufficient to detect
unexpected modification. Immutable or content-addressed evidence should be
used where practical.

A result that cannot be traced to its relevant execution context is not
sufficient for a consequential Hetren claim.

---

## 16. Qualification Principle

Implementation is evidence of construction.

Implementation is not evidence of quality.

Every material Hetren task must define validation and falsification requirements
appropriate to the claim being made.

A feature is not complete merely because:

- code exists;
- a happy-path demo works;
- unit tests pass;
- an external model says the result looks correct;
- the implementation produced the desired outcome once.

Qualification must be proportional to risk.

Applicable qualification may include:

- unit tests;
- property tests;
- contract tests;
- integration tests;
- acceptance tests;
- adversarial tests;
- malformed-input tests;
- failure injection;
- concurrency tests;
- restart and recovery tests;
- security tests;
- tenant-isolation tests;
- performance tests;
- cost tests;
- reproducibility tests;
- regression tests;
- baseline comparisons;
- matched controls;
- ablations;
- negative controls;
- transfer tests;
- independent verification.

Not every task requires every test type.

Every task requires enough evidence to support its actual claim.


---

## 17. Brutal Qualification Rule

Hetren intentionally attempts to break material features before accepting them.

Qualification must search for:

- boundary failures;
- hidden assumptions;
- invalid state transitions;
- silent data loss;
- false-positive conclusions;
- false-negative conclusions;
- nondeterministic behavior;
- evidence corruption;
- provenance gaps;
- unsupported generalization;
- constraint violations;
- security failures;
- recovery failures;
- misleading success states.

A qualification failure is a valid engineering result.

Failed evidence must not be hidden because it is inconvenient.

If qualification invalidates the implementation, the implementation must change.

If qualification invalidates the original claim, the claim must change.

If success criteria must change after observing results, the change requires an
explicit revision record and the previous result must remain preserved.


---

## 18. Completion State Machine

Material work follows:

NOT_STARTED -> IMPLEMENTING -> IMPLEMENTED -> QUALIFYING -> PASS -> INDEPENDENT_VERIFICATION -> VERIFIED -> COMPLETE.

If qualification or verification fails, work returns to FIX_OR_REVISE and must be qualified again.

`IMPLEMENTED` is never equivalent to `COMPLETE`.

---

## 19. Independent Verification

Consequential Hetren claims require a verification path that is meaningfully separate from the path that produced the candidate change.

Independence may be achieved through separate evaluation code, protected test data, a different execution path, a separate evaluator, a separately authored verification contract, repeated controlled execution, or human review for high-risk decisions.

The exact mechanism depends on the feature. The intent is to reduce self-confirming systems in which the same logic both creates and approves its own result.

---

## 20. Regression Preservation

Material failures discovered during development must become reusable
regression evidence where legally and operationally possible.

The MVP must provide a Release Memory / Regression Ledger mechanism capable
of recording:

- the failure;
- reproduction conditions;
- affected versions;
- relevant evidence;
- selected remedy;
- verification result;
- protected regression case;
- future recurrence.

A fixed bug without preserved regression evidence represents incomplete
learning.

For MVP release, the operational memory and engineering workflow must also
exercise minimal forms of:

- Change Impact Map;
- known-good comparison or bounded bisect;
- Engineering Action Plan;
- Fix Verification Sandbox;
- Release Brief;
- Capability Registry and capability discovery;
- Artifact Graph;
- cost and value ledger.

These are bounded MVP capabilities, not commitments to their eventual full
product sophistication.

---

## 21. Research Qualification

Research claims require stronger evidence than implementation claims.

Every research claim must identify which research program it belongs to and
must not borrow evidence from the other program merely because both use shared
Hetren infrastructure.

Applicable research qualification must include the appropriate combination of:

- explicit hypotheses;
- predeclared success and failure criteria;
- meaningful strong baselines;
- controlled comparisons;
- negative controls;
- ablations;
- repeatability across seeds or instances where applicable;
- uncertainty reporting;
- protected or hidden evaluation;
- leakage controls;
- failure analysis;
- cost and resource accounting;
- preserved raw outcomes;
- versioned experiment manifests;
- invalidation and rerun rules.

Native Intelligence claims additionally require evidence appropriate to shared
method construction, learned decision value, cold-start behavior, transfer,
retention, and comparison against equally resourced neural and non-neural
baselines when those claims are made.

Adaptive Intelligence claims additionally require evidence appropriate to
target adaptation, related generalization, locality or retention, critical
invariants, rollback, adaptation cost, and the relevant sequential, transfer,
consolidation, multimodal, or scaling gate when those claims are made.

Protected success criteria must be frozen before the evidence governed by them
is inspected.

A qualification failure must not be repaired by silently changing the same
threshold, holdout, evaluator, or protocol and treating the result as the same
experiment. The changed protocol must receive a new version and the affected
qualification must be rerun.

The research system must permit negative results.

An experiment that cannot meaningfully fail to support its hypothesis is not
sufficient research qualification.

Research status and product status must remain separately reportable.

---

## 22. Cross-Domain Transfer Requirement

The MVP cannot establish a shared-method claim by succeeding repeatedly in
only one domain.

At least one material learned representation, method-construction behavior,
investigation strategy, or decision mechanism must be evaluated across
system-family boundaries under the declared transfer protocol.

Transfer evidence must distinguish between:

- reusing shared infrastructure;
- reusing shared record schemas;
- retrieving prior examples;
- reusing a hand-written strategy;
- adapting task state within the declared protocol;
- transferring an actually learned or generalized decision capability.

Only evidence appropriate to the final category supports a native
learning-transfer claim.

Adaptive Intelligence transfer is a separate scientific claim.

Experience Capsule transfer, cross-model transfer, cross-architecture
transfer, or multimodal adaptive transfer must satisfy the corresponding
Adaptive Intelligence qualification gate and cannot inherit validity from
Native Intelligence cross-domain transfer.

---

## 23. Studio

Hetren Studio is the primary product surface.

The MVP Studio should remain thin until the underlying workflow is proven.

The required conceptual surfaces are Workspace, Investigation, Change Review, and Release Memory.

Studio must expose material evidence, decisions, limitations, and verification
state clearly rather than hiding the system behind a conversational interface.

A persistent AI assistant may help operate the workspace, but the product is not defined as a chat application.

---

## 24. Integrations

The MVP includes architectural boundaries for GitHub integration, Hetren MCP, and external model or provider integrations.

Integrations must communicate with Hetren through stable contracts rather than becoming alternate implementations of Hetren Core.

Provider-specific logic must remain isolated behind explicit integration boundaries so that no single provider defines Hetren architecture or intelligence behavior.

---

## 25. Practical Value Ledger

The MVP must record practical engineering value where it can be measured.

Potential measures include time to reproduce, time to isolate a failure, experiments required, compute consumed, external-model cost, human interventions, regressions prevented, verification time, repeated work avoided, and successful method reuse.

The Value Ledger is not a marketing score. It is evidence for whether Hetren makes engineering materially better.

---

## 26. Legacy Boundary

The pre-MVP-v2 implementation is historical evidence, not the architectural foundation of the new MVP.

Useful algorithms, tests, research ideas, qualification methods, or evidence may be studied and deliberately reintroduced, but legacy organization must not silently re-enter the new architecture.

No MVP task is required to reuse a legacy artifact merely because it already exists. Frozen historical experiments remain historical records and must not be rewritten to appear as new MVP evidence.

---

## 27. Explicit Non-Goals

The MVP does not require support for every AI modality, every model provider, autonomous production deployment, autonomous approval of high-risk changes, or a general-purpose coding IDE.

The MVP is also not intended to become a complete replacement for GitHub, a full observability platform, a full MLOps platform, a full experiment-tracking platform, or production-scale multi-region infrastructure.

The MVP does not require premature microservice decomposition, training a frontier foundation model, proving artificial general intelligence, claiming universal transfer from a small number of experiments, or preserving compatibility with the old ASR-first architecture.

The system should remain modular without becoming prematurely distributed.

---

## 28. Claims Hetren Must Not Make Without Evidence

Hetren must not claim that it understands a model, discovered a root cause, proved causality, learned a transferable method, improved a system, prevented a regression, reduced engineering cost, generalized across domains, is autonomous, is reliable, or is production-ready unless the relevant claim is supported by evidence appropriate to that claim.

The phrase "world class" is not an internal qualification result. Hetren records measurable evidence; external observers may decide how exceptional that evidence is.

---

## 29. MVP Falsification Conditions

### 29.1 Product And Shared-Method Falsification

The core product thesis is weakened or falsified if evidence shows that each
required system family needs a fundamentally separate Hetren investigation
strategy, or that the claimed shared intelligence reduces to hidden
domain-specific planner logic.

The product thesis is also weakened if capability discovery does not
materially affect permitted method construction, method revision cannot use
observed outcomes, the Behavioral Engine cannot establish useful external
evidence, or the Internal Engine cannot satisfy its declared qualification
where internal capability is claimed.

The product release is blocked if consequential results cannot be
independently verified, evidence cannot be traced to execution context,
private execution cannot maintain required isolation, protected constraints
are violated to improve headline metrics, required recovery or rollback fails,
or the release cannot demonstrate the required engineering workflow and value
evidence.

### 29.2 Native Intelligence Outcome

Failure of the native neural candidate to outperform a meaningful baseline does
not by itself invalidate the engineering product.

Such a result invalidates or limits the corresponding native-advantage claim.

The native experiment must still be implemented, reproducible, compared
against strong baselines, ablated where required, and reported honestly.

If another qualified policy performs better, the product may use the strongest
qualified serving policy while native research continues or is revised.

### 29.3 Adaptive Intelligence Outcome

Failure of HGP or another adaptive mechanism does not by itself invalidate the
engineering product.

The Adaptive Intelligence program must instead issue the scientific status
supported by its evidence, including STOP, PIVOT, inconclusive, blocked, or an
earned GO-level result.

A failed adaptive result must not be represented as successful learning,
continual learning, safe self-improvement, transferable experience, or another
stronger capability.

### 29.4 Evidence Preservation

Internal observations cannot support causal claims unless the required
discriminating intervention or equivalent evidence exists.

Claimed transfer that disappears under protected evaluation must be narrowed
or withdrawn.

A falsifying, negative, blocked, or inconclusive result must be preserved
rather than hidden.

If a material claim changes after qualification begins, the revised claim,
protocol, and affected evidence must be versioned and independently
requalified before the revised claim can pass.

---

## 30. MVP Release Gate

The MVP may be called complete only when evidence demonstrates all of the
following:

1. multiple systems, components, versions, and providers can be represented per tenant through a versioned system graph with isolation checks;
2. capability discovery produces qualified support declarations and honest unsupported states;
3. shared method construction and revision operate across E1, E2, and E3 using the same planner and shared Core behavior without a new hand-authored investigation strategy for each environment;
4. the Behavioral Engine performs real replay, comparison, controlled investigation, and scoped findings;
5. the Internal Engine performs reversible experiments through at least two qualified open neural-architecture bindings;
6. candidate solutions are compared and the selected change produces an actual reviewable code or configuration artifact with tests and rationale;
7. an immutable candidate receives independent verification through a separate execution path and protected checks;
8. Release and Experience Memory preserve recurrence state, applicability, known-good versions, invalidation conditions, and retest selection;
9. the native neural prototype has implementation and training code, a trained checkpoint, data/training manifests, strong baselines, ablations, and reproducible evaluation evidence;
10. transfer is measured on held-out systems and mechanisms using cold-start conditions, leakage controls, and an onboarding-effort ledger;
11. private execution demonstrates authenticated runner identity, cancellation, isolation, egress policy, credential scope, and spend enforcement;
12. Studio, GitHub integration, and Hetren MCP provide one coherent review workflow over the same Core records;
13. intelligence, product, evaluator, and runtime releases have explicit compatibility, rollback, and regression evidence;
14. engineering outcome and practical value are demonstrated through independent replay, complete effort/cost accounting, and recorded human review decisions.

These fourteen conditions correspond to the product/native MVP release
contract and must remain independently evidenced.

### 30.1 Adaptive Scientific Status At MVP Release

At MVP release time, the Adaptive Intelligence workstream must also have an
explicit evidence-backed scientific status.

That status may be an earned GO-level result, inconclusive, PIVOT, STOP, or
blocked according to the applicable scientific gate.

The adaptive program is not required to produce a positive scientific result
for the engineering product to release.

It is required to have preserved governance, experiments, evidence, negative
results, limitations, and the scientific status actually supported by that
evidence.

The product release decision and Adaptive Intelligence scientific decision
must remain separately inspectable so that one cannot hide the other.

Passing architectural review without exercising these requirements is not
sufficient.

Each release-gate condition must have a predeclared acceptance contract with
observable pass/fail criteria and preserved evidence. Qualitative labels such
as "functional", "usable", or "successful" are insufficient unless they resolve
to explicit evidence and thresholds appropriate to the claim.

Thresholds must be declared before the protected evaluation they govern.
Changing a threshold after observing protected results requires a versioned
revision and requalification.

---

## 31. Task-Level Definition Of Done

Every material MVP task must record its objective, implementation, acceptance contract, applicable qualification plan, qualification result, discovered failures, resolved failures, accepted limitations, evidence location or reference, implementation commit, and verification result.

A task is COMPLETE only when its required qualification has passed and its evidence has been preserved.

If a task changes its claim, scope, or success criteria after qualification begins, that change must be recorded explicitly before the task can be considered complete.

---

## 32. Task 1 Qualification Contract

This charter passes Task 1 qualification only if review confirms all of the
following conditions.

1. Hetren is not defined as speech-first.
2. E1 tool-using agent, E2 structured-data ML, and E3 vision are all required.
3. regression repair and constrained improvement are both required problem types.
4. Behavioral and authorized Internal Engines are first-class requirements.
5. the same shared Core and planner boundary applies across the three required environments.
6. adapters, evaluators, intelligence, permissions, and verification remain distinct responsibilities.
7. Native Hetren Intelligence is a required research workstream.
8. Adaptive Intelligence is a separate required research workstream.
9. Native Intelligence and Adaptive Intelligence connect through shared Hetren contracts and infrastructure without creating duplicate Cores, permission systems, evidence semantics, or verification authorities.
10. native architecture, HGP, adaptation mechanisms, and scientific superiority remain hypotheses until qualified.
11. Adaptive Intelligence requires predeclared governance, protected or hidden qualification, strong baselines, rollback, locality or retention evidence, negative-result preservation, and versioned rerun rules.
12. failure of a native candidate to establish advantage does not by itself invalidate the engineering product, while the unsupported native claim must be narrowed or rejected.
13. failure of Adaptive Intelligence does not by itself invalidate the engineering product, while the adaptive scientific status must be reported honestly.
14. a positive Adaptive Intelligence result does not waive product permissions, implementation, verification, recovery, compatibility, rollback, or evidence-integrity requirements.
15. product release status, Native Intelligence research status, and Adaptive Intelligence scientific status remain separately inspectable.
16. private-execution, authorization, credential, egress, budget, cancellation, recovery, and isolation boundaries are established.
17. evidence identity, provenance, immutable artifacts, evaluation identity, and historical preservation requirements are explicit.
18. consequential success claims require independent verification through authority separated from the proposing process.
19. brutal qualification and the completion state machine prevent implementation existence from being treated as completion.
20. negative, falsifying, blocked, unsupported, and inconclusive results are valid evidence and must be preserved.
21. the fourteen product/native MVP release requirements remain measurable and are not silently expanded or reduced by the adaptive research program.
22. protected success criteria cannot be changed after observing protected results without versioned revision and requalification.
23. the long-term Master Specification v2.0 boundary and current MVP v3.0 execution authority are explicit.
24. earlier Product v1.4, MVP v2.0, Neural Research v1.0, and Adaptive Intelligence v1.0 materials remain source lineage rather than current primary authority.
25. legacy implementation structure is prevented from silently becoming the new architectural foundation.

Until this contract passes requalification, Charter v1.1.0 remains
`Requalifying` and Task 1's previous v1.0.0 qualification does not automatically
qualify the changed charter.

---

## 33. Charter Principle

Hetren is not successful because it can produce an answer.

Hetren is successful when it can produce an engineering decision whose path, evidence, limitations, and consequences can be inspected and challenged.

The MVP therefore optimizes for useful action, discriminating evidence, revision under failure, independent verification, and preserved learning.

# Hetren MVP Support Matrix

**Version:** 1.0.0
**Status:** Qualified
**MVP Task:** 5 / 100
**Execution authority:** `AUTH-HETREN-MVP-3.0`
**Long-term authority:** `AUTH-HETREN-MASTER-2.0`
**Governing decision:** `0005`
**Canonical capability record:** `CapabilityProfile`
**Governing taxonomy:** `docs/mvp/04-system-taxonomy.md`
**Governing success semantics:** `docs/mvp/03-success-contracts.md`

---

## 1. Purpose

This specification freezes the first governed Hetren MVP capability-support
matrix.

Task 4 established what target systems, versions, components, environment
families, bindings, evaluators, and investigation surfaces mean.

Task 5 establishes which concrete capability combinations are required by the
initial MVP, how their current support state is represented, which Internal
Engine qualification obligations exist, and how those declarations map into
`CapabilityProfile`.

This specification must distinguish an intended MVP capability from a
capability that Hetren has actually qualified.

A capability does not become supported merely because:

- the target is representable by the Task 4 taxonomy;
- an adapter exists;
- an evaluator exists;
- an investigation surface is available;
- execution is authorized;
- an experiment happened to succeed;
- a provider or model family is known;
- the capability is required by the MVP;
- a research candidate produced a promising result.

Qualified support is a governed evidence-backed declaration.

## 2. Authority And Scope

This specification derives from:

- `AUTH-HETREN-MVP-3.0`;
- `AUTH-HETREN-MASTER-2.0`;
- the qualified Hetren MVP Charter;
- Task 3 success-contract semantics;
- Task 4 system-taxonomy semantics.

The MVP requires all three initial environment families:

- `E1_AGENT`;
- `E2_STRUCTURED_ML`;
- `E3_VISION`.

The MVP also requires both initial product problem types:

- `REGRESSION_REPAIR`;
- `CONSTRAINED_IMPROVEMENT`.

Behavioral investigation and explicitly authorized Internal investigation are
both first-class MVP requirements.

The cross-domain product capability matrix and the Internal Engine
qualification overlay are governed separately because the MVP does not require
Internal access for every E1, E2, or E3 target.

No Task 5 declaration may:

- redefine Task 3 evaluation outcomes;
- redefine Task 4 taxonomy membership;
- manufacture execution authorization;
- create a second capability-record authority;
- create environment-specific Hetren Cores;
- establish a Native Intelligence research hypothesis;
- establish an Adaptive Intelligence scientific hypothesis;
- choose Task 7 evaluation splits;
- choose Task 8 concrete baselines;
- choose Task 9 concrete cost or effort values.

## 3. Representability, Support, Authorization, And Outcome

The following are separate governed facts.

### 3.1 Representability

Representability answers whether Task 4 can truthfully describe the target,
version, environment family, component structure, bindings, evaluator, and
investigation surface.

Representability does not establish capability support.

### 3.2 Capability Support

Capability support answers what Hetren has established it can or cannot do for
a declared target context.

Capability support belongs in `CapabilityProfile` and the governed Task 5
support model.

### 3.3 Authorization

Authorization answers whether a particular action or Internal investigation is
permitted for the current execution.

Support does not grant authorization.

Authorization does not establish support.

`AUTHORIZED_INTERNAL` remains subject to execution-time permission checks.

### 3.4 Evaluation Outcome

Evaluation outcome describes the result of one governed Task 3 evaluation.

The Task 3 outcome vocabulary remains exactly:

- `PASS`;
- `FAIL`;
- `INCONCLUSIVE`;
- `BLOCKED`;
- `INVALID`.

Task 5 support states are not additional Task 3 evaluation outcomes.

## 4. CapabilityKind

The initial Task 5 product capability vocabulary is exactly:

- `REGRESSION_REPAIR`;
- `CONSTRAINED_IMPROVEMENT`.

`REGRESSION_REPAIR` means the governed capability to investigate a bounded
regression, produce or recommend an applicable candidate change, and support
the governed repair-and-verification path required by Task 3.

`CONSTRAINED_IMPROVEMENT` means the governed capability to investigate and
improve a bounded objective while preserving the mandatory constraints,
comparison semantics, and verification requirements required by Task 3.

These capability kinds describe product capability scope.

They do not establish that a particular attempt passed.

They do not establish Native Intelligence research success.

They do not establish Adaptive Intelligence scientific success.

A new capability kind requires governed Task 5 extension rather than silent
reinterpretation of either initial value.

## 5. MVPRequirement

Every governed Task 5 capability declaration carries exactly one MVP
requirement state:

- `REQUIRED`;
- `PERMITTED`;
- `EXCLUDED`.

### 5.1 REQUIRED

`REQUIRED` means the capability is part of the frozen MVP completion contract.

A required capability may remain `UNQUALIFIED` while implementation and
qualification evidence are still incomplete.

Being required does not make the capability supported.

### 5.2 PERMITTED

`PERMITTED` means the capability is allowed within the MVP architecture but is
not itself a mandatory MVP release obligation.

A permitted capability still requires qualification before it may be reported
as supported.

### 5.3 EXCLUDED

`EXCLUDED` means the combination is deliberately outside the frozen initial
MVP support contract.

Exclusion does not mean the capability is architecturally impossible.

Exclusion does not remove the underlying Task 4 taxonomy member.

A later MVP version may change an exclusion only through governed revision and
applicable requalification.

## 6. CapabilitySupportState

The initial Task 5 capability-support vocabulary is exactly:

- `QUALIFIED_SUPPORTED`;
- `UNQUALIFIED`;
- `UNSUPPORTED`;
- `INCOMPATIBLE`;
- `BLOCKED`;
- `UNKNOWN`.

These states describe capability status.

They are not task-lifecycle states and are not Task 3 evaluation outcomes.

### 6.1 QUALIFIED_SUPPORTED

`QUALIFIED_SUPPORTED` means governed evidence establishes that Hetren supports
the declared capability for the exact declared scope.

This state requires preserved qualification evidence.

The scope of the evidence limits the scope of the support claim.

No requirement declaration, successful classification, adapter availability,
evaluator availability, authorization, provider relationship, successful
single execution, or research result may synthesize this state.

### 6.2 UNQUALIFIED

`UNQUALIFIED` means the capability is in declared scope but the evidence
required to establish qualified support has not yet been completed or is not
yet sufficient.

`UNQUALIFIED` is not `FAIL`.

A required capability may legitimately remain `UNQUALIFIED` during MVP
construction.

### 6.3 UNSUPPORTED

`UNSUPPORTED` means Hetren has an explicit governed declaration that the
capability is not supported for the declared scope.

`UNSUPPORTED` is a capability declaration, not a Task 3 `FAIL` outcome.

Unsupported status must not be inferred merely from absence from the initial
matrix.

### 6.4 INCOMPATIBLE

`INCOMPATIBLE` means the declared capability and declared target context cannot
satisfy one or more material compatibility requirements.

Incompatibility must identify the relevant compatibility boundary.

`INCOMPATIBLE` is not interchangeable with `UNSUPPORTED`.

### 6.5 BLOCKED

Capability `BLOCKED` means a prerequisite required to qualify or exercise the
declared capability is currently unavailable.

Examples may include a required permission, adapter, evaluator, execution
dependency, model artifact, or authorized Internal binding.

Capability `BLOCKED` is distinct from Task 3 evaluation `BLOCKED`.

Whenever the word `BLOCKED` is recorded, the governing record type or context
must make clear which meaning applies.

### 6.6 UNKNOWN

`UNKNOWN` means there is not enough governed information to classify support
truthfully.

Unknown state must not be converted into support through inference.

Absence from the initial support matrix does not establish `UNSUPPORTED`,
`INCOMPATIBLE`, or architectural impossibility.

## 7. Separation Rules

The following distinctions are mandatory:

- representable does not mean supported;
- supported does not mean currently authorized;
- authorized does not mean supported;
- required does not mean qualified;
- `UNQUALIFIED` does not mean `FAIL`;
- `UNSUPPORTED` does not mean Task 3 `FAIL`;
- `INCOMPATIBLE` does not mean `UNSUPPORTED`;
- `UNKNOWN` does not mean `UNQUALIFIED`;
- capability `BLOCKED` does not mean evaluation `BLOCKED`;
- `EXCLUDED` does not mean architecturally impossible;
- one successful execution does not establish qualified capability support;
- one failed execution does not automatically establish unsupported capability;
- product capability support does not establish Native Intelligence success;
- product capability support does not establish Adaptive Intelligence success.

When evidence supports only a narrower capability declaration, the capability
scope must be narrowed rather than generalized.

## 8. Support Declaration Scope

A support declaration must be scoped sufficiently to prevent evidence about
one target context from silently establishing support for another.

The applicable scope may include:

- `EnvironmentFamily`;
- `CapabilityKind`;
- `InvestigationSurface`;
- system-form constraints;
- adapter requirements;
- evaluator requirements;
- provider constraints;
- target or component characteristics;
- compatibility requirements;
- authorization prerequisites;
- immutable relevant target and binding identities when required by the claim.

Not every taxonomy dimension must become a primary matrix axis.

A taxonomy dimension becomes a support-scope constraint only when it materially
changes the meaning or validity of the capability declaration.

The primary cross-domain product matrix is intentionally kept smaller than the
full Cartesian product of every Task 4 taxonomy dimension.

This prevents the support matrix from manufacturing apparent precision for
provider, adapter, evaluator, system-form, or target combinations that have not
been qualified.


## 9. Cross-Domain Behavioral Product Matrix

The first MVP product-support matrix uses three primary axes:

- `EnvironmentFamily`;
- `CapabilityKind`;
- `InvestigationSurface`.

For the initial cross-domain product matrix, the investigation surface is
`BEHAVIORAL`.

The frozen initial product matrix is:

| EnvironmentFamily | CapabilityKind | InvestigationSurface | MVPRequirement | Initial CapabilitySupportState |
|---|---|---|---|---|
| `E1_AGENT` | `REGRESSION_REPAIR` | `BEHAVIORAL` | `REQUIRED` | `UNQUALIFIED` |
| `E1_AGENT` | `CONSTRAINED_IMPROVEMENT` | `BEHAVIORAL` | `REQUIRED` | `UNQUALIFIED` |
| `E2_STRUCTURED_ML` | `REGRESSION_REPAIR` | `BEHAVIORAL` | `REQUIRED` | `UNQUALIFIED` |
| `E2_STRUCTURED_ML` | `CONSTRAINED_IMPROVEMENT` | `BEHAVIORAL` | `REQUIRED` | `UNQUALIFIED` |
| `E3_VISION` | `REGRESSION_REPAIR` | `BEHAVIORAL` | `REQUIRED` | `UNQUALIFIED` |
| `E3_VISION` | `CONSTRAINED_IMPROVEMENT` | `BEHAVIORAL` | `REQUIRED` | `UNQUALIFIED` |

These six entries are the complete required Behavioral product matrix for the
initial MVP.

Task 5 deliberately requires both initial capability kinds in each of the
three required environment families.

This is a governed Task 5 scope decision.

The earlier MVP authority independently requires:

- all three environment families;
- regression repair;
- constrained improvement;
- a shared Core and planner across the required environments.

Task 5 freezes the cross-product above so that cross-domain MVP completion
cannot be obtained by demonstrating regression repair only in one family and
constrained improvement only in another.

The six entries begin as `UNQUALIFIED`.

No entry may begin as `QUALIFIED_SUPPORTED` merely because it is required.

Each entry must independently earn qualified support for its declared scope.

## 10. Behavioral Matrix Qualification Semantics

A Behavioral product-matrix entry may become `QUALIFIED_SUPPORTED` only when
governed evidence establishes the applicable capability for the declared
environment-family and capability-kind scope.

Qualification must preserve, as applicable:

- the relevant target-system and immutable target-version identity;
- the applicable adapter identity and binding;
- the applicable evaluator identity and binding;
- the `BEHAVIORAL` investigation surface;
- the governing `GoalContract`;
- execution provenance;
- evidence provenance;
- the applicable Task 3 success semantics;
- candidate-change identity when a change is produced;
- independent verification when the resulting claim is consequential;
- compatibility constraints material to the support claim;
- qualification limitations and known unsupported boundaries.

Qualification of one matrix entry does not automatically qualify another.

In particular:

- E1 qualification does not qualify E2 or E3;
- E2 qualification does not qualify E1 or E3;
- E3 qualification does not qualify E1 or E2;
- regression-repair qualification does not qualify constrained improvement;
- constrained-improvement qualification does not qualify regression repair;
- one adapter implementation does not establish support for every adapter;
- one evaluator implementation does not establish support for every evaluator;
- one provider does not establish support for every provider;
- one system form does not establish support for every system form.

Support claims must remain no broader than their evidence.

## 11. Behavioral Engine Minimum Closed Loop

Qualification of the Behavioral product matrix depends on the Behavioral
Engine exercising the governed closed-loop behavior required by the MVP
Charter.

The Behavioral Engine must be able to:

1. inspect available capabilities;
2. propose informative tests or experiments;
3. execute or request execution;
4. observe outcomes;
5. update hypotheses;
6. identify evidence gaps;
7. revise the investigation method;
8. bound a failure or improvement region;
9. recommend the next useful action.

The exact environment-specific observations and measures may differ across
E1, E2, and E3.

The shared planner and Core behavior must not be replaced by a separate
hand-authored investigation strategy for each environment in order to satisfy
the matrix.

Environment-specific adapters may define interaction.

Environment-specific evaluators may define measurement meaning.

Neither may replace shared Core decision behavior.

## 12. Internal Engine Qualification Overlay

The Internal Engine is a first-class MVP capability but is not represented as
a second six-cell E1/E2/E3 product matrix.

The MVP does not require Internal access for every E1, E2, or E3 target.

Instead, Task 5 freezes a separate Internal qualification overlay.

The Internal qualification overlay requires at least:

| Internal qualification class | InvestigationSurface | MVPRequirement | Initial CapabilitySupportState |
|---|---|---|---|
| small open CNN-family system binding | `AUTHORIZED_INTERNAL` | `REQUIRED` | `UNQUALIFIED` |
| small open Transformer-family system binding | `AUTHORIZED_INTERNAL` | `REQUIRED` | `UNQUALIFIED` |

These are minimum qualification obligations.

They do not redefine `EnvironmentFamily`.

They do not require every CNN-family system to be classified as E3.

They do not require every Transformer-family system to be classified as E1.

They do not declare all CNN-family or Transformer-family systems supported.

The exact selected systems and immutable system versions used for qualification
must be preserved when qualification evidence is produced.

## 13. Internal Binding Qualification Requirements

Each required Internal qualification binding must exercise, at minimum:

- activation capture;
- representation or component diagnostics;
- at least one reversible intervention or ablation;
- comparison of pre-intervention and post-intervention behavior;
- verification of the intervention effect.

The Internal Engine must not satisfy this requirement through passive
visualization alone.

An Internal observation becomes evidence only when its use and provenance are
preserved sufficiently to support or challenge a governed hypothesis, predict
behavior, discriminate between explanations, or motivate a testable
intervention.

A material Internal claim implying mechanism or causality requires controlled
intervention or other evidence sufficiently discriminating for that claim.

If the evidence supports only an observational or correlational claim, the
claim must remain narrowed accordingly.

## 14. Internal Authorization Boundary

`AUTHORIZED_INTERNAL` records an investigation surface.

It does not grant permission.

An Internal capability may be known, compatible, and even previously qualified
while a particular execution remains unauthorized.

Every Internal execution must still satisfy applicable execution-time
permission, credential, isolation, and action-gateway requirements.

A missing required execution permission may produce capability `BLOCKED` for a
particular declared support context or Task 3 evaluation `BLOCKED` for a
particular evaluation.

The governing record must make clear which meaning applies.

No Internal support declaration may be used to bypass authorization.

## 15. Combined Behavioral And Internal Qualification

The MVP additionally requires at least one governed investigation in which
both investigation surfaces are available and materially used:

- `BEHAVIORAL`;
- `AUTHORIZED_INTERNAL`.

The initial combined-engine obligation is:

| Combined obligation | MVPRequirement | Initial CapabilitySupportState |
|---|---|---|
| Behavioral and authorized Internal evidence used within the same governed investigation and decision path | `REQUIRED` | `UNQUALIFIED` |

This requirement is not satisfied merely because both engines exist in the
repository.

It requires one governed investigation where Behavioral and Internal evidence
participate in the same investigation and decision path.

Behavioral evidence may identify externally visible failure without proving
mechanism.

Internal evidence may identify a candidate mechanism without establishing its
external consequence.

The combined investigation must preserve those distinctions.

Neither engine may establish causal understanding from correlation alone.

## 16. Why Internal Support Is Not A Full Cartesian Matrix

Task 5 intentionally does not create:

- E1 × Internal × regression repair;
- E1 × Internal × constrained improvement;
- E2 × Internal × regression repair;
- E2 × Internal × constrained improvement;
- E3 × Internal × regression repair;
- E3 × Internal × constrained improvement

as six additional mandatory support cells.

The MVP authority requires Internal capability and explicit Internal
qualification coverage, but it does not require Internal access for every
cross-domain product target.

Creating those six cells as mandatory would manufacture scope not established
by the governing MVP authority.

Future evidence or product requirements may add scoped Internal support
declarations through governed Task 5 revision.

Such additions must not retroactively rewrite the meaning of the initial
matrix.

## 17. CapabilityProfile Mapping

`CapabilityProfile` remains the canonical runtime and persisted capability
record.

The Task 5 specification governs the semantics that a conforming
`CapabilityProfile` declaration must preserve.

For a governed capability declaration, `CapabilityProfile` must be able to
identify or reference, as applicable:

- the declared capability scope;
- `EnvironmentFamily`;
- `CapabilityKind`;
- `InvestigationSurface`;
- `MVPRequirement`;
- `CapabilitySupportState`;
- material system-form constraints;
- material adapter requirements;
- material evaluator requirements;
- material provider constraints;
- material target or component constraints;
- compatibility requirements;
- authorization prerequisites;
- qualification-evidence references;
- known limitations;
- applicable invalidation or requalification conditions.

A profile must not infer omitted support state from taxonomy classification.

A profile must not infer `QUALIFIED_SUPPORTED` from successful discovery.

A profile must not infer `QUALIFIED_SUPPORTED` from one successful execution.

A profile must not silently broaden qualification evidence beyond the scope it
actually covers.

## 18. Initial State Freeze

At Task 5 specification creation time, every mandatory capability declaration
defined by Sections 9, 12, and 15 begins as `UNQUALIFIED`.

The initial freeze therefore contains:

- six `REQUIRED + UNQUALIFIED` Behavioral product cells;
- two `REQUIRED + UNQUALIFIED` Internal binding obligations;
- one `REQUIRED + UNQUALIFIED` combined-engine obligation.

This initial state is deliberate.

Task 5 defines the support contract before later implementation and
qualification evidence exists.

The specification must not manufacture historical qualification evidence in
order to make the matrix appear more complete.

A later transition to `QUALIFIED_SUPPORTED` requires preserved qualification
evidence and the applicable governed state transition.


## 19. Matrix-Cell Semantics

A Behavioral matrix row is an MVP qualification obligation for a bounded
capability within the declared environment family and capability kind.

A row becoming `QUALIFIED_SUPPORTED` does not mean Hetren supports every
possible system, provider, framework, adapter, evaluator, model architecture,
system form, or target configuration within that environment family.

For example, qualification of:

`E1_AGENT` + `REGRESSION_REPAIR` + `BEHAVIORAL`

establishes only the support scope justified by the preserved qualification
evidence.

Any material limitations remain part of the support declaration.

The matrix therefore records that Hetren has earned at least one governed,
bounded support declaration satisfying the row's MVP obligation.

It does not create universal family-wide support.

The same rule applies independently to all six Behavioral rows.

## 20. Compatibility Semantics

Capability compatibility is evaluated separately from taxonomy
representability.

A target may be representable while incompatible with a particular capability.

Compatibility may depend on material facts such as:

- target interface availability;
- supported adapter behavior;
- evaluator availability;
- system-form constraints;
- provider constraints;
- target or component characteristics;
- required model or artifact availability;
- reversible-change capability;
- required execution environment;
- required Internal visibility;
- credential or permission boundaries;
- version compatibility between Hetren components and target bindings.

A capability declaration must not hide a material compatibility requirement.

When a known incompatibility prevents the capability from applying to the
declared scope, the capability state is `INCOMPATIBLE`.

When the compatibility state cannot yet be established, the capability may
remain `UNKNOWN` or `UNQUALIFIED` according to what is actually known.

A temporary unavailable prerequisite must not automatically be represented as
permanent incompatibility.

Likewise, known incompatibility must not be mislabeled as temporary blockage
merely to make the support picture appear stronger.

## 21. Qualification Evidence For QUALIFIED_SUPPORTED

Promotion to `QUALIFIED_SUPPORTED` requires preserved governed qualification
evidence appropriate to the exact support scope.

The evidence package must identify or reference, as applicable:

- the capability declaration being qualified;
- the applicable `EnvironmentFamily`;
- the applicable `CapabilityKind`;
- the applicable `InvestigationSurface`;
- the relevant target `System`;
- the immutable target `SystemVersion`;
- material component and component-version identities;
- the applicable adapter identity and binding;
- the applicable evaluator identity and binding;
- material provider bindings;
- the governing `GoalContract`;
- execution records;
- evaluation records;
- candidate-change identity when a candidate exists;
- verification evidence when required by the claim;
- compatibility conditions;
- authorization prerequisites;
- qualification limitations;
- known unsupported boundaries;
- invalidation conditions;
- provenance sufficient to reproduce or audit the qualification.

The exact concrete Task 7 split identities, Task 8 baseline implementations,
and Task 9 accounting values remain governed by their later tasks.

Task 5 may require those governed artifacts when applicable without selecting
their concrete values in advance.

No capability may be promoted to `QUALIFIED_SUPPORTED` because a required
field or later governed artifact was simply omitted.

## 22. Promotion Rules

`QUALIFIED_SUPPORTED` must be earned.

The following facts are insufficient by themselves to promote a capability:

- taxonomy classification;
- system discovery;
- adapter discovery;
- evaluator discovery;
- provider discovery;
- availability of an investigation surface;
- execution authorization;
- one favorable metric;
- one successful execution;
- one successful candidate;
- one successful research experiment;
- requirement by the MVP;
- similarity to another qualified target;
- shared model architecture;
- shared provider;
- shared system form;
- shared environment family.

Qualification evidence may be reused only when its declared applicability,
identity, compatibility, and provenance justify that reuse.

Evidence about one immutable target version must not silently qualify a
materially different target version.

Evidence about one capability kind must not silently qualify the other.

Evidence about one environment family must not silently qualify another.

## 23. Failure Does Not Automatically Mean Unsupported

A failed governed evaluation remains a Task 3 `FAIL`.

It does not automatically convert the applicable capability to `UNSUPPORTED`.

A capability may remain qualified even though one execution fails when the
qualified capability claim permits individual failures and the qualification
contract remains satisfied.

Conversely, repeated or material failures may trigger requalification,
narrowing, invalidation, or an explicit unsupported declaration when the
governed evidence justifies that change.

The transition must be explicit.

Hetren must not infer a permanent product capability conclusion from a single
execution outcome unless the governing capability contract makes that outcome
decisive.

## 24. Capability-State Transition Governance

Capability support state is historical governed state.

A state transition must preserve:

- the prior state;
- the new state;
- the affected support scope;
- the reason for the transition;
- the evidence or event causing the transition;
- the applicable target and binding identities;
- the time or release context;
- any invalidated or superseded qualification evidence;
- any required requalification.

A later state must not erase the existence of an earlier state.

Promotion to `QUALIFIED_SUPPORTED` requires the qualification evidence defined
by this specification.

Demotion from `QUALIFIED_SUPPORTED` requires an explicit governed reason.

A capability may transition away from `QUALIFIED_SUPPORTED` when, for example:

- qualification evidence is later found invalid;
- a material compatibility condition changes;
- a material target or binding version changes;
- a required evaluator or adapter becomes incompatible;
- a security or authorization prerequisite materially changes;
- regression evidence invalidates the previous support scope;
- a governed qualification requirement changes;
- evidence establishes that the support claim was too broad.

The resulting state must reflect the facts.

The system must not default every invalidated support declaration to
`UNSUPPORTED`.

Depending on the evidence, the correct state may instead be `UNQUALIFIED`,
`INCOMPATIBLE`, `BLOCKED`, or `UNKNOWN`.

## 25. Requirement-State Governance

`MVPRequirement` and `CapabilitySupportState` are independent dimensions.

Changing support evidence does not silently change whether an obligation is
`REQUIRED`, `PERMITTED`, or `EXCLUDED`.

Likewise, changing an MVP requirement does not manufacture support evidence.

A material change to the frozen requirement matrix requires governed Task 5
revision.

Examples include:

- removing one of the six required Behavioral cells;
- adding another mandatory Behavioral matrix cell;
- changing one of the six required cells to `PERMITTED` or `EXCLUDED`;
- removing the CNN-family Internal obligation;
- removing the Transformer-family Internal obligation;
- removing the combined Behavioral/Internal obligation;
- redefining the meaning of a requirement state.

Historical versions of the matrix must remain interpretable after revision.

## 26. Negative And Uncertain Capability States

Negative and uncertain support states are first-class governed information.

Hetren must preserve `UNQUALIFIED`, `UNSUPPORTED`, `INCOMPATIBLE`, `BLOCKED`,
and `UNKNOWN` declarations when those states are supported by the governing
facts.

They must not be hidden merely because they make the support matrix appear less
complete.

### 26.1 UNSUPPORTED

An `UNSUPPORTED` declaration requires an explicit governed support conclusion
for the declared scope.

Absence of evidence for support is not automatically evidence of unsupported
capability.

### 26.2 INCOMPATIBLE

An `INCOMPATIBLE` declaration identifies a material compatibility conflict.

The incompatibility boundary must remain inspectable.

### 26.3 BLOCKED

A capability `BLOCKED` declaration identifies a prerequisite whose
unavailability prevents capability qualification or exercise.

The blocking condition must remain inspectable.

### 26.4 UNKNOWN

An `UNKNOWN` declaration records that the available governed information is
insufficient to classify support honestly.

Unknown status must not be silently promoted through similarity or optimism.

### 26.5 UNQUALIFIED

`UNQUALIFIED` records that the capability is in declared scope but has not yet
earned qualified support.

This is the initial state of every mandatory Task 5 obligation.

## 27. Invalidation And Requalification

Qualification evidence is not permanent merely because it once passed.

A support declaration must be requalified when a material change affects the
meaning or applicability of its evidence.

Material changes may include:

- target-system version change;
- component-version change;
- provider-binding change affecting behavior;
- adapter change affecting interaction semantics;
- evaluator change affecting measurement semantics;
- qualification-contract change;
- security or authorization-model change;
- compatibility change;
- material execution-environment change;
- discovery that evidence provenance is invalid;
- discovery that protected evaluation was compromised;
- regression demonstrating that the supported capability no longer satisfies
  its contract.

A Hetren-only implementation change that cannot affect the capability claim
does not automatically require a new target `SystemVersion`.

It may still require capability requalification when it materially affects the
support evidence.

Requalification must preserve the previous qualification result and its
historical scope.

## 28. Tenant, Identity, And Provenance Isolation

Capability support is tenant-scoped whenever the underlying target or binding
identity is tenant-scoped.

Evidence from one tenant must not silently qualify another tenant's target.

A support declaration must preserve enough identity to prevent accidental
cross-target, cross-version, cross-binding, or cross-tenant evidence reuse.

Secrets must not become support-declaration identity.

Credential values may participate in authorized execution but must not be
copied into capability identity or qualification metadata merely for
convenience.

The Artifact Graph remains responsible for artifact provenance.

Task 5 does not create a competing provenance system.

## 29. Static MVP Matrix And Current Capability State

The matrix in Section 9 is the frozen initial MVP obligation baseline.

It is not intended to become a manually rewritten dashboard of every runtime
capability observation.

The initial states preserved in this specification record the state at the
Task 5 freeze:

- six Behavioral obligations are `UNQUALIFIED`;
- two Internal binding obligations are `UNQUALIFIED`;
- one combined-engine obligation is `UNQUALIFIED`.

Current and historical capability declarations belong in `CapabilityProfile`
and their governed evidence.

Later capability-state transitions do not require rewriting the historical
initial-state claim in this specification.

A material change to the requirement structure or support semantics does
require governed Task 5 revision.

## 30. Task 5 Completion Versus MVP Capability Completion

Task 5 can be complete when the support contract itself has been correctly
defined, governed, adversarially qualified, and preserved.

Task 5 completion does not mean that the nine mandatory capability obligations
have already become `QUALIFIED_SUPPORTED`.

Task 5 completion therefore does not by itself establish:

- product MVP completion;
- qualification of all six Behavioral capability cells;
- qualification of either Internal binding;
- completion of the combined-engine investigation;
- Native Intelligence research success;
- Adaptive Intelligence scientific success;
- MVP release readiness.

The MVP release gate remains governed by the MVP Charter and later
implementation and qualification evidence.

This distinction prevents Task 5 specification completion from manufacturing
future product capability evidence.

## 31. Task 6 Through Task 9 Boundaries

Task 5 freezes capability-support semantics and the initial support
obligations.

It deliberately does not select concrete artifacts owned by Tasks 6 through 9.

Task 6 owns:

- concrete Native Intelligence hypotheses;
- concrete Adaptive Intelligence hypotheses;
- falsification criteria for those research claims;
- governed scientific claim scope.

Task 7 owns:

- development splits;
- validation splits;
- protected or held-out splits;
- split identities;
- concrete leakage controls and partitioning.

Task 8 owns:

- concrete baseline implementations;
- baseline identities and versions;
- baseline comparison configuration.

Task 9 owns:

- concrete cost fields;
- effort fields;
- accounting values;
- practical-value measurement configuration.

Task 5 may require later capability qualification to reference these artifacts
when applicable.

That requirement does not authorize Task 5 to choose their concrete values.

## 32. Governed Extension

The initial support model may evolve.

A governed extension is required before materially changing:

- `CapabilityKind`;
- `MVPRequirement`;
- `CapabilitySupportState`;
- the six required Behavioral matrix cells;
- the two required Internal binding obligations;
- the combined-engine obligation;
- the distinction between support, authorization, taxonomy, and evaluation;
- qualification-evidence semantics;
- capability-state transition semantics.

A new provider, adapter, evaluator, system form, or target implementation does
not automatically require a Task 5 specification revision when it fits within
the existing support semantics.

Its actual capability support still requires truthful `CapabilityProfile`
state and applicable evidence.

Accepted historical Task 5 semantics must not be silently rewritten in place.

Material semantic changes require versioned governance, compatibility analysis,
and applicable requalification.

## 33. Task 5 Qualification Contract

Task 5 passes qualification only if review confirms all of the following
conditions.

1. the specification uses `AUTH-HETREN-MVP-3.0` as execution authority;
2. the specification uses `AUTH-HETREN-MASTER-2.0` as long-term authority;
3. `CapabilityProfile` remains the canonical capability record;
4. Task 3 remains the governing success-semantic authority;
5. Task 4 remains the governing taxonomy authority;
6. `CapabilityKind` is exactly `REGRESSION_REPAIR` and `CONSTRAINED_IMPROVEMENT`;
7. `MVPRequirement` is exactly `REQUIRED`, `PERMITTED`, and `EXCLUDED`;
8. `CapabilitySupportState` is exactly `QUALIFIED_SUPPORTED`, `UNQUALIFIED`, `UNSUPPORTED`, `INCOMPATIBLE`, `BLOCKED`, and `UNKNOWN`;
9. Task 3 evaluation outcomes remain exactly `PASS`, `FAIL`, `INCONCLUSIVE`, `BLOCKED`, and `INVALID`;
10. capability support states are not treated as Task 3 evaluation outcomes;
11. taxonomy representability does not establish support;
12. execution authorization does not establish support;
13. qualified support does not itself grant execution authorization;
14. an MVP requirement does not establish qualified support;
15. the Behavioral product matrix contains exactly six required initial cells;
16. `E1_AGENT` contains both required capability kinds;
17. `E2_STRUCTURED_ML` contains both required capability kinds;
18. `E3_VISION` contains both required capability kinds;
19. all six initial product cells use the `BEHAVIORAL` investigation surface;
20. all six initial product cells begin `REQUIRED + UNQUALIFIED`;
21. no additional mandatory Behavioral matrix cell is silently introduced;
22. the Internal overlay contains the required small open CNN-family binding;
23. the Internal overlay contains the required small open Transformer-family binding;
24. both required Internal bindings begin `REQUIRED + UNQUALIFIED`;
25. Internal binding qualification requires activation capture;
26. Internal binding qualification requires representation or component diagnostics;
27. Internal binding qualification requires at least one reversible intervention or ablation;
28. Internal binding qualification requires pre/post behavior comparison;
29. Internal binding qualification requires verification of intervention effect;
30. Internal support is not expanded into a mandatory E1/E2/E3 Cartesian product;
31. the combined Behavioral/Internal obligation exists;
32. the combined obligation begins `REQUIRED + UNQUALIFIED`;
33. the combined obligation requires both evidence classes in the same governed investigation and decision path;
34. correlation alone cannot establish a material causal Internal claim;
35. `CapabilityProfile` preserves the governed support scope and state;
36. support claims cannot exceed the scope justified by their evidence;
37. promotion to `QUALIFIED_SUPPORTED` requires preserved qualification evidence;
38. one successful execution cannot synthesize qualified support;
39. one failed evaluation does not automatically establish `UNSUPPORTED`;
40. capability-state transitions preserve historical state and transition evidence;
41. invalidated qualified support cannot silently remain authoritative;
42. `UNSUPPORTED`, `INCOMPATIBLE`, `BLOCKED`, `UNKNOWN`, and `UNQUALIFIED` remain semantically distinct;
43. provider, adapter, evaluator, or system-form similarity cannot silently broaden qualified support;
44. qualification of one matrix row does not establish universal support for every target in that environment family;
45. Task 5 completion does not claim that the nine mandatory capability obligations are already qualified or that the MVP is complete;
46. Task 6 research hypotheses remain deferred;
47. Task 7 concrete split identities remain deferred;
48. Task 8 concrete baseline implementations remain deferred;
49. Task 9 concrete cost and effort values remain deferred;
50. material support-model changes require governed revision and applicable requalification.

Qualification must include:

- structural validation;
- semantic validation;
- authority-alignment validation;
- adversarial mutation testing;
- regression qualification for Tasks 1 through 4;
- development-state qualification;
- final accepted-state qualification.

Qualification criteria must not be weakened merely to obtain a passing result.

## 34. Support-Matrix Principle

Hetren must claim no more capability than its evidence establishes.

The purpose of the support matrix is not to make Hetren appear broadly
supported.

Its purpose is to make the boundary between required, qualified, unsupported,
incompatible, blocked, unknown, and still-unqualified capability explicit and
auditable.

A truthful narrow support declaration is stronger than an unsupported broad
claim.

The initial MVP therefore begins with nine explicit mandatory obligations and
zero manufactured qualified-support claims.

Qualification must be earned capability by capability and preserved with the
scope, identity, provenance, compatibility, and verification evidence that
justify each claim.

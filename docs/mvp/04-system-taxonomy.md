# Hetren MVP System Taxonomy

**Version:** 1.0.0
**Status:** Qualified
**MVP Task:** 4 / 100
**Execution authority:** `AUTH-HETREN-MVP-3.0`
**Long-term authority:** `AUTH-HETREN-MASTER-2.0`
**Governing decision:** `0004`
**Canonical captured-state record:** `SystemSnapshot`
**Canonical capability record:** `CapabilityProfile`
**Canonical artifact-provenance structure:** `Artifact Graph`

---

## 1. Purpose

This specification defines the concrete system taxonomy used by Hetren to
identify, version, relate, snapshot, inspect, and reason about target AI
systems across the MVP.

The taxonomy exists so that evidence about one target, component, version,
provider dependency, or investigation configuration cannot be silently
attributed to another.

Task 4 defines:

- stable target-system identities;
- immutable target-system versions;
- system forms;
- environment-family classification;
- component and component-version identities;
- provider, adapter, and evaluator bindings;
- Behavioral and authorized Internal investigation surfaces;
- the semantic structure of the versioned system graph;
- tenant-isolation rules;
- provenance and historical-identity requirements;
- controlled extension rules for future system families.

This specification defines classification and identity semantics. It does not
claim that Hetren currently supports every taxonomy member or every possible
combination of taxonomy members.

## 2. Authority And Scope

This specification derives from `AUTH-HETREN-MVP-3.0`, the qualified MVP
Charter, and the Task 3 success-contract semantics.

It applies to the three required MVP environment families:

- E1 — tool-using agent;
- E2 — structured-data ML pipeline;
- E3 — vision system.

It also applies to systems investigated through:

- Behavioral investigation;
- explicitly authorized Internal investigation.

The taxonomy must support the MVP release requirement that multiple systems,
components, versions, and providers can be represented per tenant through a
versioned system graph with isolation checks.

No taxonomy concept introduced here may create a second Hetren Core, evidence
authority, permission system, success semantic, or verification authority.

This specification governs target-system representation. It does not redefine
the canonical responsibilities of `GoalContract`, `SystemSnapshot`,
`CapabilityProfile`, `EvaluationRecord`, `VerificationReport`, the Artifact
Graph, or other records already established by higher or earlier authority.

## 3. Taxonomy Versus Support

Taxonomy membership and Hetren support are separate facts.

A system, component, provider, system form, environment family, adapter
binding, evaluator binding, or investigation surface may be representable by
this taxonomy without being supported by the current MVP implementation.

Task 4 answers questions such as:

- what kind of target is this;
- which stable identity does it have;
- which immutable version is under investigation;
- which environment family classifies it;
- which components and external dependencies belong to its graph;
- how Hetren interacts with and evaluates it.

Task 5 answers whether Hetren has a qualified capability for a particular
combination of those facts.

No Task 4 classification may be interpreted as a support declaration.

No absence from the initial Task 5 support matrix may be interpreted as proof
that a taxonomy member is impossible in the architecture.

Qualified support state belongs in `CapabilityProfile` and the governed Task 5
support matrix, not in the taxonomy itself.

When support is unknown, unqualified, incompatible, or unavailable, the system
must preserve that state honestly rather than infer support from successful
classification.

## 4. Target-System And Hetren-Implementation Boundary

The target-system graph represents the thing Hetren is investigating and the
external dependencies that materially participate in that target.

Hetren implementation machinery must remain distinguishable from the target.

In particular:

- a target component belongs to the system being investigated;
- a provider binding represents an external dependency or provider
  relationship relevant to that target;
- an adapter binding represents how Hetren interacts with the target;
- an evaluator binding represents how Hetren interprets target-specific
  measurements;
- an investigation surface represents which class of observations or
  interventions Hetren is authorized to use.

Adapters and evaluators are therefore not automatically target components.

Changing a Hetren adapter or evaluator does not by itself create a new target
`SystemVersion`.

If Hetren itself, one of its adapters, evaluators, engines, or another Hetren
component becomes the object of investigation, that object must be represented
explicitly as a target system or target component for that investigation. It
must not rely on an ambiguous dual identity.

Environment-specific implementation may exist behind explicit boundaries, but
it must not become a second implementation of shared Core semantics.

## 5. Tenant Boundary

Every governed `System` belongs to exactly one tenant.

Every `SystemVersion`, target `Component`, and `ComponentVersion` inherits the
tenant boundary of its owning system and must not be attached to a system owned
by another tenant.

A provider identity may describe a provider that exists independently of one
tenant, but provider bindings, credentials, permissions, target configuration,
snapshots, evidence, and execution state are tenant-scoped.

No graph relationship may directly connect tenant-owned system or component
nodes across tenant boundaries.

Cross-tenant evidence reuse is prohibited unless a separate governed mechanism
explicitly defines what information is non-sensitive, transferable, and
authorized for reuse. Such a mechanism is outside Task 4 and may not be
invented implicitly by the system graph.

Tenant isolation applies to identity lookup as well as execution. A globally
unique identifier must not permit one tenant to discover another tenant's
systems, versions, components, provider configuration, evidence, or internal
topology.

A violation of these isolation rules makes the affected graph state invalid
for governed use.

## 6. System Identity

A `System` is the stable logical identity of a target that Hetren may inspect,
evaluate, repair, improve, compare, or verify over time.

A `System` identity is not:

- a single execution;
- a mutable configuration snapshot;
- a model checkpoint;
- a provider account;
- an adapter;
- an evaluator;
- an environment family;
- a temporary experiment.

The system identity persists across legitimate versions of the same logical
target.

A system must have an immutable machine identity. Human-readable names,
descriptions, ownership metadata, or labels may change without changing that
identity.

A materially different logical target must receive a different system
identity rather than being hidden as another version of an unrelated system.

Conversely, ordinary evolution of the same logical target must be represented
through `SystemVersion` rather than by repeatedly allocating new system
identities.

Evidence must preserve the system identity it concerns so historical results
cannot be silently reassigned when names, metadata, ownership labels, or later
versions change.

## 7. System Version

A `SystemVersion` is an immutable governed identity for a materially defined
state of a `System`.

A system version must identify enough target state to determine what was
actually investigated. Depending on the target, that may include references
to:

- code or build identity;
- model or checkpoint identity;
- configuration;
- component versions;
- material provider or service dependencies;
- topology;
- data-processing configuration;
- tool configuration;
- deployment-relevant target settings.

A new `SystemVersion` is required when a target change could materially alter
the behavior, evidence applicability, compatibility, reproducibility, or
meaning of a governed result.

Existing system versions are immutable. Corrections to inaccurate metadata
must be auditable and must not rewrite material historical identity.

A change confined to Hetren's own adapter implementation, evaluator
implementation, investigation method, or user interface does not by itself
create a new target `SystemVersion`.

If an external provider, model, tool, dependency, or configuration change is
part of the target system and can materially change target behavior, the
affected target version or referenced binding must change accordingly.

Executions, evaluations, candidate changes, verification, and preserved
evidence must be able to identify the applicable target `SystemVersion`.

## 8. System Form

`SystemForm` describes the primary operational shape of a target
`SystemVersion`. It is independent of domain or environment family.

The initial Task 4 vocabulary is:

- `AGENT` — an acting system that performs multi-step work through reasoning,
  state, tools, APIs, or other actions;
- `PIPELINE` — an ordered trainable, configurable, or executable processing
  workflow;
- `MODEL` — a model exposed primarily as a directly executed inference or
  prediction artifact;
- `SERVICE` — a remotely or locally callable service whose relevant behavior
  is exposed through an interface rather than represented primarily as a
  directly managed model or pipeline;
- `COMPOSITE` — a target whose governed behavior materially depends on
  multiple subordinate forms and cannot be represented truthfully by one of
  the simpler forms.

Each `SystemVersion` has exactly one primary `SystemForm`.

`SystemForm` must not encode provider identity, model architecture, modality,
support status, investigation surface, or success semantics.

A form may appear in multiple environment families. For example, a vision
target may be a `MODEL`, `SERVICE`, `PIPELINE`, or `COMPOSITE`.

Using `COMPOSITE` does not permit heterogeneous components to be hidden. The
material component topology must still be represented in the system graph.

## 9. Environment Family

`EnvironmentFamily` classifies the primary MVP problem environment in which a
target `SystemVersion` is governed and qualified.

The initial Task 4 environment-family vocabulary is:

- `E1_AGENT` — tool-using agent systems;
- `E2_STRUCTURED_ML` — structured-data machine-learning systems;
- `E3_VISION` — vision models, pipelines, or services.

Each governed `SystemVersion` has exactly one primary `EnvironmentFamily`.

Environment family and `SystemForm` are independent axes. An environment
family describes the kind of system behavior and qualification environment;
the form describes the target's operational shape.

Components inside a system may have forms, roles, architectures, or modalities
different from the primary system classification without silently changing
the system's primary environment family.

A `COMPOSITE` system does not automatically belong to multiple environment
families and must not be counted as multiple required MVP qualification
families merely because it contains heterogeneous components.

Environment-family classification does not declare capability support.
Support remains governed by Task 5 and `CapabilityProfile`.

Provider identity must not determine environment family.

Investigation surface must not determine environment family.

Model architecture must not determine environment family.

Future environment families require governed taxonomy extension under Section
33 rather than reinterpretation of `E1_AGENT`, `E2_STRUCTURED_ML`, or
`E3_VISION`.

## 10. E1 Tool-Using Agent

`E1_AGENT` classifies a target whose governed behavior materially depends on
multi-step action selection, tool or API use, state, sequencing, or recovery
during task execution.

Typical E1 behavior may include:

- selecting tools or actions;
- constructing tool arguments;
- sequencing dependent actions;
- maintaining or consuming state;
- recovering from tool or execution failure;
- reasoning across multiple execution steps;
- satisfying task-level cost, latency, or other constraints.

A target does not become E1 merely because it contains a language model.

A single-call model or service with no material action-selection or multi-step
execution behavior should not be classified as E1 solely because a generative
model is involved.

E1 classification describes the target's primary qualification environment.
It does not imply that any particular agent framework, model provider, tool
protocol, memory implementation, or orchestration library is supported.

An E1 system may contain vision, retrieval, structured-data, model, service,
or other heterogeneous components without those components automatically
changing the system's primary environment family.

## 11. E2 Structured-Data ML Pipeline

`E2_STRUCTURED_ML` classifies a target whose governed behavior materially
depends on training, configuring, transforming, evaluating, or executing
machine-learning logic over structured data.

Typical E2 behavior may include:

- structured-data preparation or transformation;
- feature construction or selection;
- training or fitting;
- hyperparameter or configuration changes;
- prediction or scoring;
- model comparison;
- reproducibility;
- constrained improvement.

Structured data may include tabular, relational, categorical, numerical, or
other schema-governed representations.

A target does not become E2 merely because structured metadata appears
somewhere in its graph.

E2 classification requires that structured-data machine-learning behavior be
material to the governed target outcome.

E2 does not require one particular algorithm family, training library,
storage system, provider, or deployment form.

## 12. E3 Vision System

`E3_VISION` classifies a target whose governed behavior materially depends on
image or other governed visual input and vision-related inference,
transformation, evaluation, or failure behavior.

Typical E3 behavior may include:

- visual input handling;
- model inference;
- classification, detection, embedding, segmentation, or another governed
  visual output;
- perturbation or failure analysis;
- candidate changes;
- pre-change and post-change comparison;
- independent verification.

E3 may be represented through `MODEL`, `SERVICE`, `PIPELINE`, or `COMPOSITE`
system forms.

A system does not become E3 merely because it contains screenshots, generated
images, dashboards, or other visual artifacts that are not material inputs to
the target's governed behavior.

E3 classification does not imply support for every vision task, architecture,
modality, provider, or model family.

The Internal Engine requirement to qualify against open CNN-family and
Transformer-family systems is qualification coverage, not the definition of
E3 itself.

## 13. Future Environment Families

The initial environment-family vocabulary is intentionally limited to
`E1_AGENT`, `E2_STRUCTURED_ML`, and `E3_VISION`.

A new primary environment family requires governed taxonomy extension.

A new family must not be created merely because a new:

- provider;
- model architecture;
- system form;
- tool protocol;
- deployment platform;
- benchmark;
- dataset;
- customer;
- adapter;
- evaluator;

is introduced.

A proposed new family must represent a materially different qualification
environment whose semantics cannot be represented truthfully by the existing
families and component graph.

Existing family meanings must not be widened or reinterpreted silently to
avoid creating a governed extension.

Speech, audio, multimodal, code-oriented, robotics, or other future domains
may become governed families, benchmarks, components, adapters, or use cases
depending on the actual target semantics.

Cross-domain or multimodal composition does not permit one `SystemVersion` to
count as multiple required MVP family demonstrations. The primary environment
family remains the qualification and accounting anchor unless a later
governed taxonomy revision explicitly introduces a different model.

## 14. Component Identity And Role

A target `Component` is a stable logical sub-identity whose behavior,
configuration, dependency, or replacement may materially affect a governed
`System`.

A component belongs to exactly one owning `System`.

A component is represented separately when doing so is necessary to preserve
material topology, provenance, diagnosis, intervention, compatibility, or
evidence applicability.

Examples of component roles may include:

- model or inference component;
- tool or action endpoint;
- orchestrator or controller;
- data-processing stage;
- feature-processing stage;
- retriever or search dependency;
- state or memory subsystem;
- training stage;
- target-owned evaluation stage;
- external service dependency;
- another materially distinct target role.

These roles describe target topology. They are not Task 5 capability
declarations.

A component role must not be used to disguise a separately governed target
system merely to avoid system-level identity or isolation requirements.

Conversely, every implementation detail need not become a component. A
component should exist when separate identity materially improves the truth of
the governed representation.

Hetren adapters, evaluators, Core modules, engines, evidence machinery, and
verification machinery are not target components merely because they interact
with the target.

## 15. Component Version

A `ComponentVersion` is an immutable governed identity for a materially
defined state of a target `Component`.

A component version must preserve enough identity to determine which
component state participated in a governed `SystemVersion`.

Depending on the component, relevant identity may include references to code,
configuration, model or checkpoint identity, tool schema, dependency version,
service configuration, data-processing behavior, or other material state.

Material changes that can alter target behavior, compatibility,
reproducibility, diagnosis, or evidence applicability require a new
`ComponentVersion`.

A component version must remain attached to its owning component and tenant
boundary.

A `SystemVersion` must be able to reference the material
`ComponentVersion` identities that define its governed topology.

Historical evidence must not silently float to a later component version.

A component version may itself reference immutable artifacts through the
Artifact Graph; the taxonomy must not duplicate artifact provenance merely to
version a component.

## 16. Provider Identity And Binding

A `ProviderIdentity` identifies an external organization, platform, runtime,
hosting source, model source, service source, or other provider relevant to a
target dependency.

Provider identity is distinct from:

- tenant identity;
- target system identity;
- environment family;
- system form;
- capability support;
- credentials.

A `ProviderBinding` is the tenant-scoped configured relationship between a
specific governed target version or component version and a provider.

A provider binding must preserve enough non-secret configuration identity to
determine which provider relationship participated in a governed execution.

Credentials, tokens, secrets, and private keys must never be embedded directly
in taxonomy identity. Bindings may reference authorized credential handles or
scopes through the applicable permission and execution systems.

Material provider-binding changes that can change target behavior,
compatibility, reproducibility, cost, latency, or evidence applicability must
receive a new binding identity or version and must be reflected in the
applicable target-version provenance.

A provider may participate in many tenants and systems, but a tenant-scoped
binding must never expose another tenant's credentials, configuration, or
target relationships.

Provider identity must not determine environment family, success semantics, or
Hetren intelligence behavior.

## 17. Adapter Identity And Binding

An `AdapterIdentity` identifies a Hetren integration implementation used to
interact with a class of target interface.

An `AdapterBinding` identifies the configured association between a particular
adapter implementation and a governed target `SystemVersion` or applicable
component version.

The binding must make it possible to determine:

- which adapter implementation and version were used;
- which target identity was addressed;
- which target interface or protocol was used;
- which relevant non-secret configuration applied;
- which authorization context governed interaction.

Adapter identity and binding are Hetren-side interaction facts. They are not
part of the target's logical identity unless the adapter itself is explicitly
being investigated as a target.

Changing an adapter implementation or adapter binding does not by itself
create a new target `SystemVersion`.

Historical executions must retain the adapter identity and binding applicable
to those executions so later adapter changes cannot rewrite how earlier
evidence was obtained.

An adapter defines how Hetren interacts with a target. It must not define
whether an evaluation passes, whether a capability is qualified, or what the
shared planner should conclude.

## 18. Evaluator Identity And Binding

An `EvaluatorIdentity` identifies a qualified or candidate evaluator
implementation that converts target-specific observations into declared
measures or judgments.

An `EvaluatorBinding` identifies the configured association between an
evaluator implementation and the governed target, evaluation context, or
environment-specific measurement contract to which it applies.

The binding must make it possible to determine:

- which evaluator implementation and version were used;
- which target or evaluation context was evaluated;
- which declared measures or outputs were produced;
- which relevant non-secret configuration applied;
- which protected or ordinary evaluation authority applied where required.

An evaluator defines the environment-specific meaning and production of
measures. It does not redefine the Task 3 meanings of `PASS`, `FAIL`,
`INCONCLUSIVE`, `BLOCKED`, or `INVALID`.

Changing an evaluator does not by itself create a new target `SystemVersion`.

Historical `EvaluationRecord` and verification evidence must preserve the
evaluator identity and binding used so later evaluator changes cannot silently
reinterpret earlier results.

Evaluator selection, qualification, protected-evaluation rules, and support
eligibility must obey the governing tasks and must not be inferred merely
because an evaluator can be represented in this taxonomy.

## 19. Investigation Surface

`InvestigationSurface` classifies the kind of target access Hetren may use
during an investigation.

The initial Task 4 vocabulary is:

- `BEHAVIORAL`;
- `AUTHORIZED_INTERNAL`.

Investigation surface is independent of:

- environment family;
- system form;
- provider identity;
- support state;
- success outcome.

A single target `SystemVersion` may expose both Behavioral and authorized
Internal investigation surfaces.

Representability of a surface does not establish that Hetren has a qualified
capability to use that surface. Task 5 governs capability support.

Likewise, declaration of `AUTHORIZED_INTERNAL` does not itself grant
authorization. Permission must be established by the applicable Action and
Permission Gateway and execution authority for the particular operation.

Historical evidence must preserve which investigation surface was actually
used.

## 20. Behavioral Investigation Surface

`BEHAVIORAL` represents investigation through externally observable behavior
without requiring access to protected model internals.

Behavioral investigation may operate through:

- APIs;
- tools;
- task execution;
- model or service inputs and outputs;
- replay;
- controlled comparison;
- perturbation of permitted external inputs;
- observable state or execution traces exposed through authorized interfaces.

A Behavioral surface may apply to black-box or gray-box systems.

Behavioral classification does not imply that every external action is
authorized, safe, supported, or evidence-producing.

The adapter defines how Hetren interacts with the exposed interface.

The evaluator defines how environment-specific observations become measures.

Shared Core remains responsible for investigation-state and method semantics;
the Behavioral surface must not contain a hidden environment-specific
investigation strategy.

## 21. Authorized Internal Investigation Surface

`AUTHORIZED_INTERNAL` represents investigation that uses explicitly permitted
access to model, pipeline, execution, representation, component, or other
target internals.

Internal investigation may include:

- activation capture;
- representation diagnostics;
- component diagnostics;
- reversible intervention;
- ablation;
- masking;
- controlled internal perturbation;
- pre-intervention and post-intervention comparison.

The taxonomy records the existence and identity of the Internal investigation
surface. It does not grant permission to use it.

Every Internal action must be authorized through the applicable permission,
execution, credential, isolation, and action-eligibility controls at the time
of execution.

Internal access must never be inferred merely because:

- the target is open source;
- the target runs locally;
- Hetren can technically reach an internal interface;
- an adapter exposes an internal operation;
- another tenant authorized similar access.

An unavailable or unauthorized Internal surface does not invalidate the
Behavioral identity of the same target.

Internal observations do not receive stronger evidentiary status merely
because they expose internals. Causal or mechanistic claims remain governed by
the applicable success and evidence contracts.

## 22. Versioned System Graph

The Versioned System Graph is the governed topology semantics used to represent
a target system and the identities required to interpret evidence about it.

Task 4 does not introduce a competing canonical runtime record named
`SystemGraphRecord`.

`SystemSnapshot` remains the canonical captured-state record.

The Versioned System Graph defines which stable identities, immutable versions,
bindings, surfaces, and relationships a `SystemSnapshot` must be able to
capture or reference when they are material to the governed investigation.

The graph must be capable of representing:

- multiple systems per tenant;
- multiple immutable versions per system;
- multiple components per system;
- multiple immutable versions per component;
- material component topology;
- provider relationships;
- Hetren adapter bindings;
- evaluator bindings;
- investigation surfaces;
- references to immutable artifacts and provenance.

A governed graph state must be reconstructable sufficiently to determine what
target state was investigated and through which material interaction and
evaluation configuration the evidence was produced.

The graph is not itself evidence that a capability is supported, a result is
valid, or an investigation succeeded.

## 23. Graph Planes And Relationship Vocabulary

The Versioned System Graph preserves distinct semantic planes.

### 23.1 Target Identity And Version Plane

This plane contains:

- `System`;
- `SystemVersion`;
- `Component`;
- `ComponentVersion`.

Its governed relationships include:

- `HAS_SYSTEM_VERSION` — `System` to `SystemVersion`;
- `HAS_COMPONENT` — `System` to `Component`;
- `HAS_COMPONENT_VERSION` — `Component` to `ComponentVersion`;
- `INCLUDES_COMPONENT_VERSION` — `SystemVersion` to the
  `ComponentVersion` instances material to that target version;
- `DEPENDS_ON` — a material target-topology dependency between compatible
  target-version nodes.

### 23.2 Provider Plane

This plane contains:

- `ProviderIdentity`;
- `ProviderBinding`.

Its governed relationships establish:

- which provider identity a binding uses;
- which `SystemVersion` or `ComponentVersion` the tenant-scoped binding
  participates in.

Provider binding is explicit rather than inferred from names, URLs, model
identifiers, SDKs, or adapter choice.

### 23.3 Hetren Interaction And Evaluation Plane

This plane contains or references:

- `AdapterIdentity`;
- `AdapterBinding`;
- `EvaluatorIdentity`;
- `EvaluatorBinding`;
- declared investigation surfaces.

Its governed relationships establish:

- `INTERACTS_VIA` — which adapter binding Hetren used for a target scope;
- `EVALUATED_VIA` — which evaluator binding applied to an evaluation scope;
- `EXPOSES_SURFACE` — which investigation surfaces are declared for the
  target scope.

These relationships describe interaction and evaluation context. They do not
become target-system components merely because they appear in the graph.

### 23.4 Artifact-Provenance References

Graph identities may reference immutable artifacts governed by the Artifact
Graph.

Artifact relationships are references into the Artifact Graph rather than a
second artifact-lineage implementation inside the system taxonomy.

## 24. Graph Validity And Cardinality Rules

A graph state is valid for governed use only when its identity, ownership,
version, tenant, and binding constraints are internally consistent.

At minimum:

1. every `SystemVersion` belongs to exactly one `System`;
2. every `Component` belongs to exactly one `System`;
3. every `ComponentVersion` belongs to exactly one `Component`;
4. an included `ComponentVersion` must belong to a component owned by the
   same system as the referencing `SystemVersion`;
5. a `SystemVersion` may include at most one active version of one logical
   component unless materially distinct simultaneous instances are represented
   through separately governed component identities;
6. ownership relationships must not form cycles;
7. `DEPENDS_ON` relationships may represent real target dependency cycles when
   such cycles actually exist and are material;
8. every `ProviderBinding` references exactly one `ProviderIdentity` and a
   valid tenant-scoped target scope;
9. every `AdapterBinding` references exactly one `AdapterIdentity` and a valid
   target scope;
10. every `EvaluatorBinding` references exactly one `EvaluatorIdentity` and a
    valid evaluation or target scope;
11. no tenant-owned graph relationship may cross tenant boundaries;
12. no required graph reference may dangle;
13. secret credential material must not be embedded in graph identity;
14. environment family and system form remain explicit rather than inferred
    from provider, adapter, evaluator, file path, or naming convention;
15. `AUTHORIZED_INTERNAL` availability does not substitute for execution-time
    authorization.

Multiple provider, adapter, or evaluator bindings may legitimately exist when
the target or evaluation has multiple material interfaces or dependencies.

Such multiplicity must remain explicit and must not make historical evidence
ambiguous about which binding actually applied.

A graph that violates a required invariant is invalid for consequential
evaluation until the representation is corrected and affected evidence is
requalified where necessary.

## 25. Version And Provenance Semantics

Target identity, Hetren interaction identity, and evidence provenance must be
versioned without being conflated.

A `SystemVersion` is an immutable root for a materially defined target state.

A material change to target-owned topology, component versions, target
configuration, model state, tool configuration, or a provider binding that is
part of target behavior requires a new `SystemVersion`.

Changing only Hetren's:

- adapter implementation or adapter binding;
- evaluator implementation or evaluator binding;
- investigation method;
- user interface;
- planner release;

does not by itself create a new target `SystemVersion`.

Those Hetren-side identities must instead be preserved in the applicable
execution, evaluation, verification, snapshot, or other evidence provenance.

A historical result must be attributable to enough immutable identity to
answer, where applicable:

- which `System` and `SystemVersion` were investigated;
- which component versions participated;
- which material provider bindings participated;
- which adapter binding was used;
- which evaluator binding was used;
- which investigation surface was exercised;
- which artifacts were referenced;
- which execution and evaluation records produced the evidence.

Later changes must create later identities or records rather than mutate the
meaning of preserved historical evidence.

## 26. Relationship To SystemSnapshot

`SystemSnapshot` remains the canonical captured-state record for the target
state relevant to an investigation.

Task 4 does not replace it with a separate canonical system-graph snapshot
record.

A `SystemSnapshot` must be able to capture or reference the material graph
state needed to interpret an execution, including where applicable:

- `System` identity;
- `SystemVersion` identity;
- primary `SystemForm`;
- primary `EnvironmentFamily`;
- material `ComponentVersion` topology;
- material `ProviderBinding` identities;
- applicable `AdapterBinding`;
- applicable `EvaluatorBinding`;
- declared and actually used investigation surface;
- relevant Artifact Graph references;
- capture time and other dynamic state required for reproducibility.

Multiple `SystemSnapshot` records may legitimately refer to the same immutable
`SystemVersion`.

For example, the target version may remain unchanged while Hetren uses a later
adapter, evaluator, investigation method, or captures materially different
runtime state.

A snapshot must not silently rewrite its referenced immutable identities after
evidence has been produced.

## 27. Relationship To CapabilityProfile

`CapabilityProfile` remains the canonical record for discovered and qualified
capability state.

The taxonomy describes what a target is.

`CapabilityProfile` describes what Hetren has established it can or cannot do
for the applicable target context.

Capability qualification may depend on taxonomy dimensions such as:

- environment family;
- system form;
- investigation surface;
- interface or adapter class;
- evaluator availability;
- provider constraints;
- target/component characteristics;
- compatibility state.

Those dimensions may scope a capability declaration without becoming support
claims themselves.

A target that is fully representable in the taxonomy may still have an
unsupported, unqualified, incompatible, blocked, or unknown capability state.

Task 5 governs the first concrete supported capability matrix.

Neither the system graph nor successful target classification may synthesize a
qualified `CapabilityProfile` entry without the required qualification
evidence.

## 28. Relationship To Artifact Graph

The Artifact Graph and Versioned System Graph have different responsibilities.

The Versioned System Graph represents logical target identity, immutable target
versions, material topology, provider relationships, and investigation
context.

The Artifact Graph represents immutable artifact identity, provenance,
derivation, lineage, and evidence-bearing artifact relationships.

A `SystemVersion`, `ComponentVersion`, provider binding, adapter binding,
evaluator binding, snapshot, execution, or evaluation may reference artifacts
through the Artifact Graph when those artifacts are material.

Examples may include:

- source revisions;
- configuration artifacts;
- model checkpoints;
- dataset manifests;
- tool schemas;
- generated candidate patches;
- evaluation outputs;
- verification artifacts.

A component identity must not replace artifact identity.

An artifact identity must not replace the logical `System`,
`SystemVersion`, `Component`, or `ComponentVersion` to which its meaning
belongs.

Content-address equality or reuse of an artifact does not itself authorize
cross-tenant discovery or access.

Artifact lineage must remain preserved independently of later system-version
or component-version evolution.

## 29. External Models And Services

External models and services may participate in Hetren workflows in different
roles, and those roles must remain explicit.

An external model or service may be:

- the governed target `System`;
- a target `Component`;
- a provider-backed dependency of a target;
- a service reached through a `ProviderBinding`;
- a Hetren-side engineering or research accelerator.

Those roles are not interchangeable.

If an external model or service is part of target behavior, its material
identity, provider relationship, configuration, and version applicability must
be represented through the target system graph and applicable provenance.

If an external model is used by Hetren as an engineering or research
accelerator, that use does not automatically make the model a target component.

External-model output is not evidence merely because it was produced by a
capable model or provider.

Material external-model outputs used to propose hypotheses, code, changes,
summaries, experiment plans, or other consequential artifacts must enter the
same evidence, provenance, authorization, review, and verification processes
required for comparable non-model outputs.

The same external model may appear in more than one role in one investigation,
but those roles must be recorded separately enough to prevent target evidence
from being confused with Hetren-side assistance.

Provider-specific behavior must remain behind explicit integration boundaries.
No provider may define Hetren Core semantics, shared intelligence behavior,
success semantics, or verification authority.

## 30. Native And Adaptive Research Boundary

Native Intelligence and Adaptive Intelligence use the same target-system
taxonomy and shared Hetren contracts as the engineering product.

Neither research program creates a parallel:

- `System` identity model;
- system graph;
- Hetren Core;
- evidence system;
- permission system;
- success semantic;
- verification authority.

A Native or Adaptive experimental implementation does not become a qualified
product capability merely because it exists in `research/`, produces a model,
or can be attached to a target.

When a Native or Adaptive candidate is itself the object of investigation, it
must receive the same explicit target identity, version, topology, provenance,
evaluation, and verification treatment required for another governed target.

Research artifacts such as:

- training manifests;
- checkpoints;
- experiment configurations;
- datasets or dataset manifests;
- learned parameters;
- evaluation outputs;
- adaptive-state artifacts;

belong in the applicable Artifact Graph provenance rather than being treated
as substitutes for logical system identity.

`NATIVE` and `ADAPTIVE` are research-program classifications, not
`EnvironmentFamily` values.

A research candidate may operate across E1, E2, or E3 without creating a
research-specific environment family.

Product qualification, Native Intelligence research status, and Adaptive
Intelligence scientific status remain separately inspectable.

Scientific evidence from one research program must not silently establish the
status of the other program or product capability.

## 31. Isolation And Cross-Tenant Prohibitions

Tenant isolation is a validity property of the taxonomy, not merely a user
interface filter.

A governed target graph must not contain a tenant-owned identity, binding,
snapshot, credential reference, evidence reference, or relationship that
belongs to another tenant.

Globally unique identifiers, shared provider identities, common artifact
content, identical model names, identical configuration values, or matching
content hashes do not authorize cross-tenant discovery or access.

A shared `ProviderIdentity` may be referenced by separate tenant-scoped
`ProviderBinding` identities.

The existence of one tenant's provider binding must reveal nothing about
another tenant's:

- credentials;
- account configuration;
- target relationships;
- system identities;
- component identities;
- evidence;
- internal access;
- execution history.

Cross-tenant transfer or reuse of methods, learned experience, evidence, or
artifacts requires an independently governed mechanism that defines
authorization, privacy, applicability, provenance, and evidence consequences.

Task 4 does not create such a mechanism.

Caching, deduplication, content addressing, shared infrastructure, or provider
reuse must not weaken logical tenant isolation.

A cross-tenant graph violation makes the affected representation invalid for
governed execution or consequential evaluation until corrected and the
affected evidence is dispositioned under the applicable evidence rules.

## 32. Historical Identity And Invalidation

Historical identity must be preserved even when later information shows that a
graph state, classification, binding, evaluator, artifact, or result was
incorrect or invalid.

A superseded, retired, incompatible, or invalid identity must not be deleted
merely to make current state appear cleaner.

When a material historical representation is discovered to be wrong:

1. the original record and affected evidence remain preserved;
2. the defect or invalidation reason is recorded;
3. a corrected identity, version, binding, snapshot, or classification is
   created where required;
4. affected evidence is narrowed, invalidated, or requalified according to
   the governing evidence semantics;
5. later records reference the corrected state without silently rewriting the
   meaning of the earlier evidence.

Retirement is not deletion.

Supersession is not retroactive mutation.

Invalidation is not permission to erase a negative or inconvenient result.

A later taxonomy revision must remain able to interpret historical taxonomy
identities or provide an explicit migration mapping.

Evidence attached to one `SystemVersion`, `ComponentVersion`,
`ProviderBinding`, `AdapterBinding`, `EvaluatorBinding`, or snapshot must not
silently float to a replacement identity.

## 33. Extension And Taxonomy Evolution

The taxonomy is extensible, but its existing meanings are governed.

Adding a new environment family, system form, graph relationship, identity
type, or materially different binding semantic requires an explicit governed
taxonomy change.

An extension must declare:

- the new or changed vocabulary;
- why existing vocabulary is insufficient;
- compatibility with existing records;
- migration or interpretation rules for preserved history;
- affected qualification and validation logic;
- evidence that must be requalified, if any;
- rollback or supersession behavior.

Existing enum or relationship names must not be reused with materially changed
semantics.

A material semantic change to an existing taxonomy concept requires a
versioned specification revision and applicable requalification rather than an
in-place reinterpretation.

Additive implementation convenience does not justify taxonomy expansion unless
the new concept is required to represent governed reality truthfully.

A target that cannot be classified truthfully under the current taxonomy must
be reported as requiring taxonomy clarification or extension.

It must not be forced into `E1_AGENT`, `E2_STRUCTURED_ML`, or `E3_VISION`
merely to satisfy an MVP qualification requirement.

Legacy vocabulary may be mapped into this taxonomy only through an explicit,
reviewable mapping. Historical terminology must not silently regain authority
over the current architecture.

## 34. Deferred Task 5-9 Artifacts

Task 4 defines the identity and classification space in which later governed
MVP artifacts operate.

It deliberately does not select the concrete values owned by Tasks 5 through
9.

Task 5 owns:

- the initial supported capability matrix;
- qualified and unsupported combinations;
- capability compatibility declarations;
- the first concrete mapping from taxonomy dimensions to support state.

Task 6 owns:

- concrete Native Intelligence hypotheses;
- concrete Adaptive Intelligence hypotheses;
- corresponding falsification criteria and governed scientific claims.

Task 7 owns:

- development, validation, protected, held-out, or other split identities;
- split access and leakage controls;
- concrete evaluation partitioning.

Task 8 owns:

- concrete baseline implementations;
- baseline versions;
- governed baseline comparison requirements.

Task 9 owns:

- concrete cost and effort ledger fields;
- accounting values;
- practical-value measurement configuration.

Task 4 may require later artifacts to reference stable system, version,
component, provider, adapter, evaluator, surface, or artifact identities.

That requirement does not authorize Task 4 to choose their later concrete
support, scientific, evaluation, baseline, or accounting values.

If a later task reveals that the taxonomy cannot represent a required governed
case truthfully, Task 4 must be revised through governed change rather than
being bypassed.

## 35. Task 4 Qualification Contract

Task 4 passes qualification only if all of the following conditions are
demonstrated by review and automated qualification where applicable.

1. the specification contains exactly 36 numbered sections in the governed order;
2. `AUTH-HETREN-MVP-3.0` is the execution authority and `AUTH-HETREN-MASTER-2.0` remains the long-term authority;
3. `SystemSnapshot`, `CapabilityProfile`, and the Artifact Graph retain their canonical responsibilities and no competing canonical `SystemGraphRecord` is introduced;
4. taxonomy membership remains explicitly separate from capability support;
5. every governed `System` belongs to exactly one tenant;
6. tenant-owned graph identities and relationships cannot cross tenant boundaries;
7. `System` remains a stable logical identity rather than an execution, snapshot, checkpoint, provider account, adapter, evaluator, or environment family;
8. `SystemVersion` is immutable and identifies a materially defined target state;
9. a material target-side change that can alter behavior, compatibility, reproducibility, evidence applicability, or governed meaning requires a new `SystemVersion`;
10. a change confined to Hetren-side adapter, evaluator, investigation-method, Studio, or planner state does not by itself create a new target `SystemVersion`;
11. the initial `SystemForm` vocabulary is exactly `AGENT`, `PIPELINE`, `MODEL`, `SERVICE`, and `COMPOSITE`, with exactly one primary form per governed `SystemVersion`;
12. the initial `EnvironmentFamily` vocabulary is exactly `E1_AGENT`, `E2_STRUCTURED_ML`, and `E3_VISION`, with exactly one primary family per governed `SystemVersion`;
13. `SystemForm` and `EnvironmentFamily` remain independent classification axes;
14. a `COMPOSITE` target does not automatically count as multiple required MVP environment-family demonstrations;
15. E1 classification requires materially relevant multi-step action, tool/API, state, sequencing, or recovery behavior rather than merely containing a language model;
16. E2 classification requires materially relevant structured-data machine-learning behavior rather than merely containing structured metadata;
17. E3 classification requires materially relevant visual-input or vision behavior rather than merely containing visual artifacts;
18. future environment families require governed extension and existing E1/E2/E3 meanings cannot be silently widened;
19. every target `Component` belongs to exactly one owning `System`;
20. `ComponentVersion` is immutable and historical evidence does not silently move to later component versions;
21. component representation is required only when separate identity materially improves topology, provenance, diagnosis, intervention, compatibility, or evidence truth;
22. `ProviderIdentity` remains distinct from tenant, system, environment-family, system-form, capability, and credential identity;
23. `ProviderBinding` is tenant-scoped and secret credential material is not embedded in taxonomy identity;
24. a material target-side provider-binding change is reflected in a new applicable target version and preserved provenance;
25. `AdapterIdentity` and `AdapterBinding` remain Hetren-side interaction identities rather than automatic target components;
26. an adapter defines interaction and does not define shared success semantics, qualified capability, or planner conclusions;
27. `EvaluatorIdentity` and `EvaluatorBinding` remain separately identifiable and historically attributable;
28. an evaluator may define environment-specific measures but does not redefine the Task 3 outcome vocabulary or shared success semantics;
29. the investigation-surface vocabulary is exactly `BEHAVIORAL` and `AUTHORIZED_INTERNAL`;
30. `AUTHORIZED_INTERNAL` representation or availability never substitutes for execution-time authorization;
31. Behavioral investigation does not embed a hidden environment-specific investigation strategy in place of shared Core behavior;
32. Internal observations do not receive stronger evidentiary status merely because internals were accessed;
33. the Versioned System Graph represents target identity, version, topology, provider, interaction, evaluation, surface, and artifact-reference context without becoming a support or success declaration;
34. the governed relationship vocabulary preserves `HAS_SYSTEM_VERSION`, `HAS_COMPONENT`, `HAS_COMPONENT_VERSION`, `INCLUDES_COMPONENT_VERSION`, `DEPENDS_ON`, `INTERACTS_VIA`, `EVALUATED_VIA`, and `EXPOSES_SURFACE` semantics;
35. ownership relationships are acyclic while genuine material `DEPENDS_ON` target dependency cycles may be represented;
36. required graph references cannot dangle and graph invariants must hold before consequential governed use;
37. environment family and system form remain explicit rather than being inferred from provider, adapter, evaluator, path, model name, or naming convention;
38. `SystemSnapshot` can capture or reference the material graph and interaction/evaluation state needed to interpret evidence;
39. multiple `SystemSnapshot` records may refer to one immutable `SystemVersion` without mutating that target version;
40. `CapabilityProfile` remains the authority for discovered and qualified capability state, including honest unsupported, unqualified, incompatible, blocked, or unknown states;
41. the Artifact Graph remains distinct from logical system/component identity and content equality does not authorize cross-tenant access;
42. external models and services have explicit roles and their outputs do not become evidence merely because a capable model produced them;
43. Native Intelligence and Adaptive Intelligence do not create duplicate target identity, Core, graph, evidence, permission, success, or verification systems;
44. existence of a Native or Adaptive research artifact does not itself make that artifact a qualified product capability;
45. product qualification, Native Intelligence research status, and Adaptive Intelligence scientific status remain separately inspectable;
46. historical invalid, superseded, retired, or corrected identities and evidence remain preserved rather than being deleted or silently rewritten;
47. material taxonomy evolution is versioned, governed, migration-aware, and requalified where required instead of reusing existing vocabulary with changed meaning;
48. a target that cannot be classified truthfully is not forced into E1, E2, or E3 merely to satisfy MVP evidence requirements;
49. Task 5 through Task 9 concrete support, hypothesis, split, baseline, and cost/effort values remain explicitly deferred;
50. the resulting taxonomy is sufficient to represent multiple systems, components, versions, and providers per tenant through a versioned graph with isolation checks while preserving the shared Hetren Core boundary.

## 36. System-Taxonomy Principle

Hetren must identify the target truthfully before it reasons about the target.

System identity, target version, component topology, provider relationships,
Hetren interaction, evaluation context, investigation surface, tenant
ownership, and artifact provenance must remain distinguishable whenever that
distinction can change the meaning or applicability of evidence.

Classification must not manufacture support.

Representability must not manufacture authorization.

Access must not manufacture evidence.

Shared artifacts must not manufacture cross-tenant permission.

Research existence must not manufacture product capability.

Later versions must not rewrite historical identity.

When the taxonomy cannot represent a governed target truthfully, the taxonomy
must be revised through governed change rather than the target or evidence
being forced into a convenient classification.

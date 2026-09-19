# Hetren MVP Initial Split Protocol

**Version:** 0.1.0
**Status:** Draft
**MVP Task:** 7 / 100
**Execution authority:** `AUTH-HETREN-MVP-3.0`
**Long-term authority:** `AUTH-HETREN-MASTER-2.0`
**Governing decision:** `0008`
**Research program:** `CROSS_PROGRAM`
**Research change category:** `DATA`
**Required evidence consequence:** `RERUN_AND_PRESERVE_DATA_DISTINCTIONS`
**Governing success semantics:** `docs/mvp/03-success-contracts.md`
**Governing system taxonomy:** `docs/mvp/04-system-taxonomy.md`
**Governing support contract:** `docs/mvp/05-support-matrix.md`
**Governing research hypotheses:** `docs/mvp/06-research-hypotheses.md`

---

## 1. Purpose

Task 7 freezes the initial governed evidence-partition protocol for the Hetren
MVP.

The protocol defines how evidence is separated before it may support:

- product capability qualification;
- Native Intelligence research;
- Adaptive Intelligence research;
- held-out learned-transfer claims;
- retention, locality, invariant, and rollback claims;
- consequential independent verification.

Task 7 does not establish that any Task 5 capability is supported.

Task 7 does not establish scientific support for `N-H1`, `N-H2`, `A-H1`, or
`A-H2`.

Task 7 establishes the identities, boundaries, access rules, and contamination
semantics required before later experiments may produce authoritative evidence.

## 2. Authority And Scope

This specification is governed by:

- `AUTH-HETREN-MVP-3.0`;
- `AUTH-HETREN-MASTER-2.0`;
- Decision `0008`;
- the qualified success semantics in Task 3;
- the qualified system taxonomy in Task 4;
- the qualified support model in Task 5;
- the qualified hypotheses in Task 6.

Task 7 owns concrete split-role semantics, split identities, partition
boundaries, evaluation-unit identity, independence grouping, protected-evidence
access rules, and leakage controls.

Task 7 does not redefine:

- evaluation outcomes;
- system taxonomy;
- capability-support state;
- scientific hypotheses;
- hypothesis thresholds;
- baseline implementation identity;
- resource or cost accounting.

Those meanings remain governed by their owning tasks.

## 3. Completion Does Not Manufacture Evidence

Task 7 specification completion means that the split protocol itself has been
qualified.

It does not mean:

- an experiment has executed;
- a protected result exists;
- a hypothesis passed;
- a capability became `QUALIFIED_SUPPORTED`;
- a transfer claim succeeded;
- an adaptation claim succeeded;
- an independent verification passed.

The protocol may be complete while every future experiment remains
scientifically unresolved.

A split contract is evidence infrastructure.

It is not scientific evidence by itself.

## 4. Split Integrity Principle

The governing principle is:

> evidence use determines evidence meaning.

A record, case, system, task, trace, example, label, expected output, or derived
artifact cannot be treated as protected merely because it is stored in a file
or folder named `test`, `holdout`, or `protected`.

Its governed meaning depends on:

- its partition identity;
- its split version;
- its provenance;
- its access history;
- its candidate-lineage exposure;
- its declared role;
- its declared scientific purpose;
- its evaluation authority;
- whether its outcomes influenced candidate production or tuning.

Naming does not create protection.

Physical separation alone does not create protection.

Protection must be demonstrated through governed identity and access history.

## 5. PartitionRole Vocabulary

The initial `PartitionRole` vocabulary is exactly:

- `DEVELOPMENT`;
- `VALIDATION`;
- `PROTECTED`.

No fourth initial partition role exists.

A new role requires governed Task 7 extension.

`PartitionRole` answers:

> how may this partition be used relative to candidate creation and
> qualification?

It does not answer which hypothesis or scientific purpose the partition serves.

## 6. DEVELOPMENT Semantics

A `DEVELOPMENT` partition may be used for candidate-producing activity.

Depending on the governed experiment, permitted use may include:

- training;
- fitting;
- prompt or policy development;
- heuristic development;
- debugging;
- exploratory analysis;
- method construction;
- representation learning;
- adaptation input;
- error analysis;
- candidate revision.

Use of development evidence must still preserve provenance.

Development evidence must not later be relabeled as fresh protected evidence
for a candidate lineage that consumed it.

A development failure remains valid development evidence.

## 7. VALIDATION Semantics

A `VALIDATION` partition supports governed candidate selection before protected
qualification.

Depending on the declared contract, validation evidence may be used for:

- model selection;
- hyperparameter selection;
- stopping;
- method selection;
- threshold-independent engineering decisions;
- configuration comparison;
- candidate narrowing.

Validation access must be recorded.

Once validation outcomes influence candidate selection, the partition is not
protected evidence for that candidate lineage.

Validation must not be silently promoted to `PROTECTED` after favorable
results are observed.

## 8. PROTECTED Semantics

A `PROTECTED` partition is reserved for evidence that must not be used to tune
the candidate or manufacture the governed claim.

Protected qualification requires:

- a frozen split version;
- a frozen applicable candidate identity;
- frozen applicable success criteria;
- frozen applicable evaluator identity or binding rule;
- frozen applicable baseline binding rule where required;
- frozen invalidation rules;
- controlled outcome access;
- preserved access history.

Protected does not necessarily mean that all inputs are invisible.

Some governed tasks may require a candidate to receive an input in order to
act on it.

The protected property concerns prohibited access to outcome information,
acceptance signals, expected answers, labels, scoring details, or other
information whose use could tune the governed result into existence.

Input visibility must therefore be declared separately from outcome visibility.

## 9. PartitionPurpose Vocabulary

`PartitionPurpose` is independent of `PartitionRole`.

The initial purpose vocabulary is exactly:

- `PRIMARY_OUTCOME`;
- `TRANSFER_SOURCE`;
- `TRANSFER_TARGET`;
- `ADAPTATION_INPUT`;
- `PRIOR_CAPABILITY`;
- `LOCALITY`;
- `CRITICAL_INVARIANT`.

A purpose identifies the scientific or qualification function of a partition.

Purpose does not by itself authorize access.

For example:

- `ADAPTATION_INPUT` may be `DEVELOPMENT`;
- `TRANSFER_TARGET` may be `PROTECTED`;
- `PRIOR_CAPABILITY` may be `PROTECTED`;
- `PRIMARY_OUTCOME` may have development, validation, and protected
  partitions in the same split plan.

A future purpose requires governed Task 7 extension.

## 10. Role And Purpose Are Separate Axes

A split contract must record both:

- `PartitionRole`;
- one or more applicable `PartitionPurpose` values.

The same purpose may exist under different roles.

The same role may serve different purposes.

Role must not be inferred from:

- file name;
- directory;
- dataset name;
- environment family;
- hypothesis ID;
- evaluator;
- provider;
- adapter;
- user interface label.

Purpose must not be inferred from role.

This separation prevents the protocol from creating research-specific meanings
for generic evidence roles.

## 11. SplitPlan

A `SplitPlan` is the stable logical identity of one governed evidence-
partitioning design.

It identifies:

- the plan ID;
- governed scope;
- applicable research program or product qualification scope;
- applicable hypotheses or capability claims;
- target environment families;
- required partition roles;
- required partition purposes;
- independence requirements;
- leakage rules;
- protected-access policy;
- revision policy.

A `SplitPlan` is not itself one execution.

It may have multiple `SplitVersion` records over time.

A `SplitPlan` ID is intentionally versionless.

Version identity belongs to `SplitVersion`, not to the stable logical
`SplitPlan` ID.

A materially different partition design requires either a new plan or a
governed new version according to the change semantics in this specification.

## 12. SplitVersion

A `SplitVersion` is the immutable governed version of a `SplitPlan` used by an
experiment or qualification attempt.

Before protected evidence may be inspected, the applicable `SplitVersion` must
freeze:

- membership rules;
- concrete partition membership where available;
- partition identities;
- evaluation-unit identities;
- independence-group assignments;
- applicable system-version bindings;
- environment-family bindings;
- protected access policy;
- leakage checks;
- applicable candidate-binding rule.

After a `SplitVersion` is frozen, its historical meaning must not be rewritten
in place.

A material change creates a new `SplitVersion`.

The old version remains preserved.

## 13. PartitionIdentity

Every governed partition has a stable `PartitionIdentity`.

A partition identity must be unique within its `SplitVersion`.

It records at minimum:

- split-plan ID;
- split-version ID;
- partition ID;
- `PartitionRole`;
- applicable `PartitionPurpose`;
- membership manifest reference;
- provenance reference;
- applicable environment-family scope;
- applicable system-version scope;
- access-policy reference;
- contamination state.

Changing membership does not silently preserve the same partition identity.

A material membership change requires a new `SplitVersion` or new partition
identity under the governed revision rules.

## 14. EvaluationUnit

An `EvaluationUnit` is the smallest governed unit that may count independently
for a scientific or qualification requirement.

An evaluation unit may correspond to a bounded:

- target system;
- system version;
- dataset source;
- scenario collection;
- task family;
- controlled environment;
- mechanism;
- another predeclared evidence-generating unit.

The unit definition must be declared before protected results are inspected.

Repeated observations from one evaluation unit do not create new independent
units merely by repetition.

Resampling one unit does not create another independent unit.

Rerunning one unit with a different random seed does not create another
independent unit unless the governing scientific contract explicitly defines
the seed-level process itself as the independent evidence-generating unit.

## 15. IndependenceGroup

Every protected `EvaluationUnit` used to satisfy an independence requirement
must belong to an `IndependenceGroup`.

An `IndependenceGroup` identifies units that share a dependency capable of
making them non-independent for the governed claim.

Possible dependencies include:

- common source system;
- common system version;
- common dataset lineage;
- direct derivation;
- duplicated or near-duplicated records;
- shared scenario generation;
- shared protected target outcomes;
- shared human-authored answer source;
- another material evidence dependency.

Two units may count as separately independent only when they belong to
different governed independence groups and the experiment records the basis
for that separation.

Assigning two different IDs to correlated evidence does not manufacture
independence.

## 16. SplitManifest

Every executed governed split requires a `SplitManifest`.

The manifest binds the abstract protocol to actual evidence.

It records at minimum:

- `SplitPlan` ID;
- `SplitVersion` ID;
- all `PartitionIdentity` values;
- membership references;
- membership fingerprints or equivalent immutable references;
- all `EvaluationUnit` values;
- all `IndependenceGroup` assignments;
- applicable `SystemVersion` bindings;
- environment-family bindings;
- candidate identity or candidate-binding rule;
- evaluator identity or evaluator-binding rule;
- protected-access policy;
- access-event references;
- contamination status;
- invalidation status;
- creation and freeze time;
- applicable governing decision and contract versions.

A manifest must be preserved with the evidence it governs.

## 17. Membership And Provenance

Partition membership must be reproducible or auditable from preserved
provenance.

Where raw evidence cannot legally or operationally be copied, the manifest may
preserve a stable external identity or fingerprint sufficient to establish
which evidence was governed.

Membership provenance must make it possible to detect, where applicable:

- exact duplicates;
- derived copies;
- near duplicates;
- common-source leakage;
- label or target reuse;
- transformed copies;
- shared scenario ancestry;
- shared system-state ancestry.

Hash inequality alone does not prove independence.

A transformed copy of protected evidence remains derived from protected
evidence even when its bytes differ.

## 18. Protected Contract Freeze

Before a protected partition may produce evidence for a governed claim, the
applicable contract must freeze:

- hypothesis or capability-contract version;
- `SplitPlan`;
- `SplitVersion`;
- partition identities;
- evaluation-unit definitions;
- independence-group definitions;
- primary metric meaning;
- applicable numerical gates;
- hard constraints and invariants;
- evaluator identity or binding rule;
- candidate identity or candidate-binding rule;
- baseline-binding rule where applicable;
- resource-matching rule where applicable;
- invalidation conditions;
- protected-access policy.

Protected membership must not be selected after inspecting protected outcomes.

Independence boundaries must not be redefined after seeing protected results.

A failed protected result must not be converted into `PASS` by changing the
split contract after observation.

A material post-result change requires governed revision and the applicable
evidence consequence:

`RERUN_AND_PRESERVE_DATA_DISTINCTIONS`.

## 19. Protected Evidence Lifecycle

Protected evidence follows a governed lifecycle.

The initial `ProtectedLifecycleState` vocabulary is exactly:

- `PREPARING`;
- `FROZEN`;
- `SEALED`;
- `EVALUATING`;
- `DISCLOSED`;
- `INVALIDATED`.

A new lifecycle state requires governed Task 7 extension.

The lifecycle records the evidence-protection state.

It does not replace the Task 3 evaluation outcome vocabulary.

For example, a protected evaluation may produce `FAIL` while its evidence
lifecycle remains valid and ultimately becomes `DISCLOSED`.

Scientific failure is not evidence-integrity failure.

## 20. PREPARING And FROZEN States

`PREPARING` means the split contract is still being assembled.

While `PREPARING`, permitted changes may include:

- membership construction;
- duplicate analysis;
- provenance repair;
- independence analysis;
- access-policy construction;
- evaluator binding;
- candidate-binding preparation.

A `PREPARING` split must not produce authoritative protected evidence.

`FROZEN` means the applicable protected contract has been fixed before
protected outcomes are inspected.

Transition to `FROZEN` requires the Section 18 protected-contract freeze.

After `FROZEN`, material changes to protected:

- membership;
- purpose;
- evaluation-unit boundaries;
- independence groups;
- evaluator meaning;
- candidate binding;
- metric meaning;
- success gates;
- access policy;

require a new governed `SplitVersion` or applicable contract revision.

## 21. SEALED State

`SEALED` means protected outcome information is withheld from unauthorized
candidate-producing or tuning processes.

Sealing must protect, where applicable:

- expected outputs;
- target labels;
- acceptance signals;
- aggregate protected scores;
- per-case protected scores;
- evaluator-derived error details;
- hidden test identities when identity secrecy is material;
- derived artifacts that reveal protected outcomes.

Sealing may be implemented through:

- access control;
- separate evaluator execution;
- hidden test infrastructure;
- credential separation;
- service boundaries;
- process separation;
- human-review controls;
- another auditable mechanism.

The protocol does not require one physical sealing technology.

It requires auditable outcome-access separation.

## 22. Candidate Freeze

Before a consequential protected evaluation begins, the governed candidate must
be frozen sufficiently to prevent protected outcomes from being tuned into the
candidate.

Candidate freeze must identify, as applicable:

- candidate ID;
- code revision;
- model or checkpoint identity;
- method version;
- prompt or policy version;
- configuration;
- learned state;
- applicable external-model binding;
- applicable retrieval configuration;
- applicable adaptation state.

A material candidate change after protected evaluation begins creates a new
candidate identity.

The earlier protected result remains attached to the earlier candidate.

It must not be silently transferred to the changed candidate.

## 23. EVALUATING State

`EVALUATING` means an authorized evaluator is executing the frozen candidate
against the sealed protected evidence.

During `EVALUATING`:

- protected outcomes must not be returned to the candidate-producing path;
- acceptance signals must not be used for interactive tuning;
- per-case failures must not be exposed to an adaptive mechanism unless the
  governing protocol explicitly classifies them as non-protected adaptation
  input;
- evaluation code must preserve split and candidate identity;
- execution failures must remain distinguishable from scientific failure;
- access events must be recorded.

A candidate may receive protected inputs when interaction with those inputs is
required by the task.

Receiving an input does not authorize receiving its protected expected outcome.

## 24. DISCLOSED State

`DISCLOSED` means protected results have been released to an authorized
recipient after governed evaluation.

Disclosure does not retroactively invalidate a previously valid protected
evaluation.

The disclosed result remains valid historical evidence for the candidate and
contract under which it was produced unless another defect invalidates it.

However, after disclosure, that evidence is not automatically fresh protected
evidence for a descendant candidate whose construction or tuning can be
influenced by the disclosed information.

A later candidate may require:

- a fresh protected partition;
- a new `SplitVersion`;
- a separately isolated verification path;
- or another governed freshness argument.

Independent replay of the same frozen candidate may still use the evidence
when the verification path is sufficiently separated and the governing
contract permits reuse.

## 25. ProtectedAccessEvent

Every material protected access must create or reference a
`ProtectedAccessEvent`.

An access event records at minimum:

- split-plan ID;
- split-version ID;
- partition identity;
- accessor identity or authority;
- access time;
- access purpose;
- information exposed;
- candidate lineage affected;
- whether outcome information was exposed;
- authorization basis;
- resulting contamination assessment.

Protected access history must be preserved.

Deleting access history does not restore freshness.

An unrecorded material access discovered later is an evidence-integrity defect.

## 26. Leakage Taxonomy

Task 7 distinguishes multiple leakage channels.

The initial governed leakage categories include:

- `EXACT_DUPLICATE_LEAKAGE`;
- `DERIVED_RECORD_LEAKAGE`;
- `NEAR_DUPLICATE_LEAKAGE`;
- `LABEL_OR_OUTCOME_LEAKAGE`;
- `SYSTEM_STATE_LEAKAGE`;
- `TARGET_FAMILY_LEAKAGE`;
- `HUMAN_TUNING_LEAKAGE`;
- `RETRIEVAL_LEAKAGE`;
- `PROMPT_OR_TRACE_LEAKAGE`;
- `CACHE_OR_LOG_LEAKAGE`;
- `EVALUATOR_FEEDBACK_LEAKAGE`;
- `EXTERNAL_TOOL_LEAKAGE`;
- `UNKNOWN_MATERIAL_EXPOSURE`.

These categories are evidence-integrity classifications.

They are not new Task 3 evaluation outcomes.

A leakage event may cause `INVALID`, require claim narrowing, require a new
split version, or be demonstrated irrelevant depending on the governed
contract and materiality.

## 27. ContaminationState

Every protected partition used for consequential evidence must carry a
`ContaminationState`.

The initial contamination vocabulary is exactly:

- `CLEAN`;
- `SUSPECTED`;
- `CONFIRMED`;
- `UNKNOWN`.

`CLEAN` requires that applicable leakage checks passed and no known material
exposure compromises the governed claim.

`SUSPECTED` means a plausible material exposure exists but has not yet been
resolved.

`CONFIRMED` means material contamination is established.

`UNKNOWN` means the available provenance or access history is insufficient to
make the required determination.

`SUSPECTED`, `CONFIRMED`, and `UNKNOWN` must not be silently represented as
`CLEAN`.

A claim requiring clean protected evidence is `BLOCKED` or `INVALID` until the
governing contract permits another justified resolution.

## 28. Repeated Protected Peeking

Repeated inspection of protected outcomes is not free evidence.

Protected results must not become an informal development loop through:

- repeated submission;
- repeated candidate ranking;
- per-case failure inspection;
- score probing;
- threshold probing;
- adaptive querying;
- manual trial-and-error;
- selective candidate retention.

A protocol that permits multiple protected evaluations must predeclare:

- the allowed evaluation count or stopping rule;
- what information is returned after each evaluation;
- whether candidate revision is permitted;
- how multiplicity is handled;
- when freshness is exhausted;
- when a new split version is required.

Trying many candidates against one protected split and reporting only the best
result is not a valid single protected evaluation unless that selection process
was itself part of the preregistered governed protocol.

## 29. Invalidation And Split Revision

A protected result is invalid for its intended claim when a material defect
breaks the governing evidence contract.

Examples include:

- confirmed outcome leakage;
- protected-case tuning;
- post-result membership manipulation;
- false independence;
- evaluator defect that changes outcome meaning;
- unauthorized protected access;
- hidden target-specific adaptation in a transfer test;
- candidate identity ambiguity;
- unrecoverable provenance loss.

Invalidation must preserve:

- the original split version;
- original partition membership;
- original result;
- original access history;
- discovered defect;
- invalidation reason;
- successor split version when one exists.

A replacement split does not erase the invalid result.

A material DATA revision requires:

`RERUN_AND_PRESERVE_DATA_DISTINCTIONS`.

## 30. Fresh Protected Evidence

Freshness is relative to a governed candidate lineage and claim.

A protected partition is not fresh for a candidate lineage when information
from that partition materially influenced candidate construction, selection,
tuning, adaptation, or claim selection.

Freshness must consider indirect exposure through:

- developers;
- prompts;
- retrieved examples;
- external tools;
- logs;
- caches;
- generated summaries;
- derived labels;
- evaluator feedback;
- prior descendant candidates.

A physically new file is not necessarily fresh evidence.

A copied, transformed, resampled, or re-encoded descendant of exposed
protected evidence inherits the relevant exposure unless a governed analysis
establishes otherwise.

## 31. N-H1 Split Binding

`N-H1` uses the Task 7 split protocol to test learned investigation-decision
value.

The initial governed `SplitPlan` identity for `N-H1` is:

`SPLIT-NH1-DECISION`

The plan requires, at minimum:

- development evidence for candidate-producing Native Intelligence work;
- validation evidence for candidate selection where selection is performed;
- protected `PRIMARY_OUTCOME` evidence;
- at least two protected governed `EvaluationUnit` values;
- applicable leakage checks;
- candidate freeze;
- independent verification where required by Task 6.

The protected units must measure the exact decision behavior claimed, such as:

- experiment selection;
- action ranking;
- evidence-gap prioritization;
- hypothesis revision;
- stopping;
- abstention;
- next-action recommendation.

Evidence for one behavior must not silently establish another.

## 32. N-H1 Independent Evaluation Units

For the Task 6 requirement of at least two independent governed evaluation
units, `N-H1` requires:

- at least two protected `EvaluationUnit` identities;
- those units to belong to different applicable `IndependenceGroup` values;
- preserved evidence explaining the material basis for independence;
- no duplicate or derived protected outcome relationship that defeats the
  independence claim.

The following do not by themselves create a second independent unit:

- another random seed;
- another bootstrap sample;
- another resampling of the same source;
- another run of the same system version;
- another ID assigned to the same underlying evidence;
- a transformed copy of the same protected cases.

If the required independence cannot be established, the `N-H1` protected
protocol cannot satisfy the two-unit scientific gate.

## 33. N-H1 Development And Validation Use

`N-H1` development and validation partitions may be used to improve the Native
candidate before candidate freeze.

They may contain examples of the same general task type as the protected
evaluation.

They must not contain protected outcome information whose use would make the
protected claim circular.

Where development, validation, and protected evidence share an upstream source,
the split manifest must document:

- the source relationship;
- duplicate and derivation controls;
- independence implications;
- why the protected units remain valid for the claimed evidence scope.

Validation results used to choose the final Native candidate must not later be
reported as fresh protected evidence for that candidate.

## 34. N-H2 Split Binding

`N-H2` uses the Task 7 protocol to test cross-family learned decision transfer.

The initial governed `SplitPlan` identity for `N-H2` is:

`SPLIT-NH2-XFAM`

The plan distinguishes:

- source-side `TRANSFER_SOURCE` evidence;
- protected target-side `TRANSFER_TARGET` evidence.

The transferred object must be the learned Native decision mechanism or learned
decision state named by the experiment contract.

Shared repository structure, Core records, adapters, evaluators, schemas,
retrieval, or authored target strategy do not by themselves count as
transferred learned capability.

The target environment family must be predeclared before protected target
outcomes are inspected.

## 35. N-H2 Leave-One-Family-Out Boundaries

The initial Task 7 `N-H2` protocol recognizes exactly three MVP
leave-one-environment-family-out transfer boundaries:

| Boundary ID | Source environment families | Protected target environment family |
|---|---|---|
| `NH2-XFAM-E1-V1` | `E2_STRUCTURED_ML`, `E3_VISION` | `E1_AGENT` |
| `NH2-XFAM-E2-V1` | `E1_AGENT`, `E3_VISION` | `E2_STRUCTURED_ML` |
| `NH2-XFAM-E3-V1` | `E1_AGENT`, `E2_STRUCTURED_ML` | `E3_VISION` |

A governed `N-H2` experiment must predeclare its primary boundary before
protected target outcomes are inspected.

An experiment may preregister more than one boundary only when:

- each boundary remains separately identified;
- multiplicity handling is declared;
- success is not selected post hoc from whichever boundary performs best;
- failed and negative boundaries remain preserved.

Trying all three boundaries and reporting only the most favorable one is not
valid evidence for a preregistered single-boundary `N-H2` claim.

The three boundaries define the initial MVP transfer protocol.

They do not establish universal Native transfer.

## 36. N-H2 Transfer Leakage Controls

For an `N-H2` protected target boundary, the candidate-producing process must
not use protected target outcomes before the governed target evaluation.

The split manifest must assess, where applicable:

- target-label exposure;
- target expected-output exposure;
- target-specific authored investigation strategy;
- hidden target-specific adaptation;
- retrieval of protected target examples;
- prompts containing protected target outcomes;
- target-family traces or logs that reveal qualification outcomes;
- evaluator feedback returned during candidate construction;
- onboarding effort that contains protected target-specific knowledge;
- source/target duplicates or derived cases;
- shared system-state ancestry that defeats the held-out claim.

Permitted knowledge about the existence or public interface of the target
family does not by itself invalidate transfer.

The governing experiment must state what target information is allowed.

The central prohibition is protected target-outcome tuning.

If protected target outcomes materially influence the transferred mechanism
before protected evaluation, the affected `N-H2` result is invalid for the
claimed held-out transfer evidence.

## 37. A-H1 Split Binding

`A-H1` uses the Task 7 protocol to test bounded useful adaptation.

The initial governed `SplitPlan` identity for `A-H1` is:

`SPLIT-AH1-ADAPT`

The plan requires, at minimum:

- governed `ADAPTATION_INPUT` evidence available to the adapting mechanism;
- protected `PRIMARY_OUTCOME` evidence;
- protected `CRITICAL_INVARIANT` evidence where applicable;
- preservation of the pre-adaptation candidate state;
- a frozen post-adaptation candidate identity;
- applicable leakage checks;
- protected outcome sealing;
- independent evaluation as required by Task 6.

The adaptation input and protected outcome evidence must remain separately
identified even when they concern the same general target behavior.

The adapting mechanism may learn from its declared adaptation input.

It must not learn from protected outcome information whose use would make the
protected adaptation result circular.

## 38. A-H1 Adaptation Input And Protected Outcome Separation

Before an `A-H1` protected evaluation begins, the split manifest must identify:

- the pre-adaptation candidate identity;
- the `ADAPTATION_INPUT` partition identities;
- the information the adapting mechanism is allowed to observe;
- the post-adaptation candidate identity;
- the protected `PRIMARY_OUTCOME` partition identities;
- the applicable protected `CRITICAL_INVARIANT` partition identities;
- evaluator authority;
- protected outcome-access rules.

Protected target outcomes must not be returned to the adapting mechanism before
the post-adaptation candidate is frozen.

The following do not become valid adaptation input merely because they are
available to an evaluator:

- protected expected outputs;
- protected labels;
- protected aggregate scores;
- protected per-case scores;
- protected invariant failures;
- evaluator explanations that reveal protected answers.

If protected outcome information materially influences the adaptive candidate
before candidate freeze, the affected protected adaptation result is invalid
for `A-H1`.

A new governed adaptation attempt may proceed only under an applicable fresh
or otherwise valid split contract.

## 39. A-H2 Split Binding

`A-H2` uses the Task 7 protocol to test retention, locality, and rollback.

The initial governed `SplitPlan` identity for `A-H2` is:

`SPLIT-AH2-RETENTION`

The plan requires, at minimum:

- protected `PRIOR_CAPABILITY` evidence;
- protected `LOCALITY` evidence;
- protected `CRITICAL_INVARIANT` evidence where applicable;
- preserved pre-adaptation state;
- preserved post-adaptation state;
- an explicitly identified rollback target;
- preserved post-rollback state;
- candidate and system provenance for all three states;
- evaluator-controlled protected outcomes;
- applicable independent verification.

`A-H2` evidence remains distinct from `A-H1` evidence.

Passing one hypothesis does not manufacture evidence for the other.

## 40. A-H2 Paired Pre/Post/Rollback Evaluation

`A-H2` may evaluate the same governed protected `EvaluationUnit` before
adaptation, after adaptation, and after rollback when paired comparison is
required by the scientific contract.

Using the same unit at those three measurement points does not by itself create
three independent evaluation units.

It creates three governed observations of the same declared unit and
`IndependenceGroup`.

The manifest must preserve:

- pre-adaptation candidate and system state;
- post-adaptation candidate and system state;
- rollback target identity;
- post-rollback candidate and system state;
- the same applicable protected unit identity across paired measurements;
- raw pre-adaptation outcomes;
- raw post-adaptation outcomes;
- raw post-rollback outcomes;
- evaluator identity;
- access-event history.

Protected paired outcomes may be used by the independent evaluator to compute
retention, locality, invariant, and rollback measures.

They must not be fed back into the adapting mechanism during the governed
candidate-producing step unless a later contract explicitly reclassifies them
as non-protected evidence for a new candidate lineage.

Rollback success requires actual execution against the declared rollback
target.

A description of rollback is not a rollback evaluation.

## 41. Task 5 Capability Qualification Split Bindings

Task 5 capability qualification must bind later qualification evidence to a
Task 7 `SplitPlan` and concrete `SplitVersion`.

The initial Behavioral qualification plan identities are:

| EnvironmentFamily | CapabilityKind | SplitPlan ID |
|---|---|---|
| `E1_AGENT` | `REGRESSION_REPAIR` | `SPLIT-CAP-E1-RR` |
| `E1_AGENT` | `CONSTRAINED_IMPROVEMENT` | `SPLIT-CAP-E1-CI` |
| `E2_STRUCTURED_ML` | `REGRESSION_REPAIR` | `SPLIT-CAP-E2-RR` |
| `E2_STRUCTURED_ML` | `CONSTRAINED_IMPROVEMENT` | `SPLIT-CAP-E2-CI` |
| `E3_VISION` | `REGRESSION_REPAIR` | `SPLIT-CAP-E3-RR` |
| `E3_VISION` | `CONSTRAINED_IMPROVEMENT` | `SPLIT-CAP-E3-CI` |

The initial Internal and combined qualification plan identities are:

| Qualification obligation | SplitPlan ID |
|---|---|
| open CNN-family authorized Internal qualification | `SPLIT-INT-CNN` |
| open Transformer-family authorized Internal qualification | `SPLIT-INT-TRANSFORMER` |
| combined Behavioral plus authorized Internal qualification | `SPLIT-COMBINED-BI` |

These plan identities create qualification obligations.

They do not establish that any Task 5 capability is
`QUALIFIED_SUPPORTED`.

A later qualification attempt must still bind:

- concrete `SystemVersion`;
- concrete `SplitVersion`;
- concrete partition membership;
- applicable evaluator;
- applicable baseline;
- preserved execution and evaluation evidence;
- all other Task 5 qualification requirements.

## 42. Initial SplitPlan Registry

The initial Task 7 `SplitPlan` registry is exactly:

| SplitPlan ID | Governing use |
|---|---|
| `SPLIT-CAP-E1-RR` | E1 Behavioral regression-repair qualification |
| `SPLIT-CAP-E1-CI` | E1 Behavioral constrained-improvement qualification |
| `SPLIT-CAP-E2-RR` | E2 Behavioral regression-repair qualification |
| `SPLIT-CAP-E2-CI` | E2 Behavioral constrained-improvement qualification |
| `SPLIT-CAP-E3-RR` | E3 Behavioral regression-repair qualification |
| `SPLIT-CAP-E3-CI` | E3 Behavioral constrained-improvement qualification |
| `SPLIT-INT-CNN` | authorized Internal CNN-family qualification |
| `SPLIT-INT-TRANSFORMER` | authorized Internal Transformer-family qualification |
| `SPLIT-COMBINED-BI` | combined Behavioral and Internal qualification |
| `SPLIT-NH1-DECISION` | `N-H1` learned investigation-decision evaluation |
| `SPLIT-NH2-XFAM` | `N-H2` cross-family learned-transfer evaluation |
| `SPLIT-AH1-ADAPT` | `A-H1` bounded useful-adaptation evaluation |
| `SPLIT-AH2-RETENTION` | `A-H2` retention, locality, and rollback evaluation |

The registry freezes logical split-plan identities.

These `SplitPlan` IDs are stable and intentionally do not encode a version.

Concrete executions bind a separate immutable `SplitVersion`.

It does not fabricate concrete examples or datasets that do not yet exist.

Before execution, each qualification or research attempt must create or bind a
concrete governed `SplitVersion` whose manifest identifies actual membership
and provenance.

A future additional plan requires governed Task 7 extension when it changes the
initial qualification model rather than merely instantiating a version of an
existing plan.

## 43. Environment-Family Partitioning Rules

Physical partitioning must respect the evidence dependencies of the applicable
environment family.

For `E1_AGENT`, relevant grouping boundaries may include:

- target `SystemVersion`;
- task or scenario family;
- tool-state source;
- environment-state source;
- scenario-generation lineage;
- authored task template;
- shared expected-answer source.

For `E2_STRUCTURED_ML`, relevant grouping boundaries may include:

- entity or subject identity;
- customer, account, device, or organizational group;
- temporal boundary;
- source dataset lineage;
- label-generation lineage;
- repeated measurements;
- derived-row ancestry.

For `E3_VISION`, relevant grouping boundaries may include:

- subject or object identity;
- capture session;
- video or burst sequence;
- source asset;
- near-duplicate image family;
- augmentation ancestry;
- annotation source.

These are governed considerations, not universal instructions to use every
listed grouping dimension.

Before protected evidence is inspected, the split contract must declare which
dependencies are material for the intended claim.

A random record-level split is invalid when it allows a material grouped
dependency to leak across the protected boundary.

No fixed percentage such as 80/10/10 is universally mandated by Task 7.

Partition size must instead be justified by the applicable claim, evidence
availability, independence requirements, and later statistical protocol.

## 44. Independent Verification And Authority Separation

Task 7 supports the Task 3 independent-verification requirement but does not
replace `VerificationReport`.

For a consequential protected claim, the verification path must have enough
separation that the process producing the candidate cannot manipulate the
protected evidence used to certify it.

Applicable separation may include:

- protected data unavailable to the candidate-producing process;
- separately controlled evaluator execution;
- separate evaluation code;
- independent replay;
- separate authority for result release;
- human review where appropriate.

The verification path must preserve:

- candidate identity;
- `SystemVersion`;
- `SplitPlan`;
- `SplitVersion`;
- partition identities;
- evaluation-unit identities;
- evaluator identity;
- access events;
- evidence references;
- resulting `VerificationReport`.

Independent verification may reuse a valid protected partition for replay of
the same frozen candidate when the governing contract permits it and the
verification path remains meaningfully separated.

That permitted replay does not authorize iterative candidate tuning against the
same protected outcomes.

## 45. Task 8 Baseline Handoff

Task 8 retains ownership of concrete baseline:

- implementation;
- identity;
- version;
- configuration;
- comparison role.

Task 7 owns only the split-side binding required to ensure that candidate and
baseline comparisons use the intended evidence contract.

Where Task 6 requires a strongest matched baseline, transfer comparator, or
adaptation baseline, the experiment manifest must bind the Task 8 baseline
identity before applicable protected outcomes are inspected.

Task 7 must not select a weak baseline to improve the apparent candidate
result.

A baseline change after protected inspection is a material comparison-contract
change and requires the applicable governed revision and rerun.

## 46. Task 9 Cost And Resource Handoff

Task 9 retains ownership of concrete:

- compute-cost fields;
- execution-cost fields;
- engineering-effort fields;
- adaptation-cost fields;
- accounting values;
- practical-value configuration.

Task 7 records references to those artifacts where the scientific or product
contract requires resource matching or adaptation-cost preservation.

Task 7 does not define the accounting values.

Where resource matching is part of the claim, the resource-binding rule must
be frozen before protected evidence is inspected.

Changing resource accounting after seeing protected results must not be used to
retroactively manufacture a passing comparison.

## 47. Change Control And Evidence Consequence

A material split change requires governed revision.

Material changes include, as applicable:

- changing `PartitionRole` semantics;
- changing `PartitionPurpose` semantics;
- changing protected membership;
- changing an evaluation-unit definition;
- changing an independence-group boundary;
- changing a protected-access policy;
- changing leakage interpretation;
- changing contamination status based on new evidence;
- changing a transfer target boundary;
- changing adaptation-input/protected-outcome separation;
- changing a paired retention/locality protocol;
- changing an initial SplitPlan's scientific meaning.

Historical evidence must retain the exact `SplitVersion` under which it was
produced.

A successor split must not overwrite the old manifest.

Because Decision `0008` is a `DATA` research change, the minimum evidence
consequence for a material governed Task 7 change is:

`RERUN_AND_PRESERVE_DATA_DISTINCTIONS`.

Affected prior results must remain distinguishable from results produced under
the revised split.

## 48. Governed Extension

Task 7 may evolve through governed extension.

A governed extension is required before materially changing:

- the three-value `PartitionRole` vocabulary;
- the seven-value `PartitionPurpose` vocabulary;
- the protected lifecycle vocabulary;
- the contamination-state vocabulary;
- initial `N-H2` transfer-boundary semantics;
- an initial SplitPlan's scientific meaning;
- evidence-freshness semantics;
- protected-access semantics;
- independence semantics;
- invalidation semantics.

Instantiating a concrete `SplitVersion` under an existing qualified
`SplitPlan` does not by itself require a new Task 7 governance decision when
the plan semantics remain unchanged.

Adding actual dataset members, systems, or evaluation cases under a valid plan
must still preserve provenance and satisfy the plan's freeze requirements.

A material semantic change requires Decision Governance rather than silent
reinterpretation.

## 49. Task 7 Qualification Contract

Task 7 passes specification qualification only if review confirms all of the
following:

1. the execution authority is `AUTH-HETREN-MVP-3.0`;
2. the long-term authority is `AUTH-HETREN-MASTER-2.0`;
3. Decision `0008` governs the Task 7 split protocol;
4. `PartitionRole` is exactly `DEVELOPMENT`, `VALIDATION`, and `PROTECTED`;
5. `PartitionPurpose` is exactly `PRIMARY_OUTCOME`, `TRANSFER_SOURCE`,
   `TRANSFER_TARGET`, `ADAPTATION_INPUT`, `PRIOR_CAPABILITY`, `LOCALITY`, and
   `CRITICAL_INVARIANT`;
6. role and purpose remain separate axes;
7. development evidence may influence candidate production;
8. validation evidence may influence candidate selection but does not thereby
   become protected evidence;
9. protected evidence requires a frozen governed contract;
10. protected input visibility does not imply protected outcome visibility;
11. `SplitPlan` is a stable logical partition-design identity;
12. `SplitVersion` is immutable once frozen for protected evidence;
13. material partition-membership changes require governed new identity or
    versioning rather than silent mutation;
14. every governed partition has a `PartitionIdentity`;
15. every scientific independence claim identifies governed `EvaluationUnit`
    values;
16. evaluation-unit meaning is declared before protected results;
17. repeated runs, seeds, resamples, or IDs do not manufacture independent
    units;
18. applicable protected units use governed `IndependenceGroup` assignments;
19. every executed governed split preserves a `SplitManifest`;
20. membership provenance supports applicable duplicate and derivation
    analysis;
21. byte or hash inequality alone does not establish evidence independence;
22. protected membership and independence boundaries are frozen before
    protected outcomes are inspected;
23. protected outcome information is sealed from unauthorized
    candidate-producing or tuning processes;
24. consequential protected evaluation uses a sufficiently frozen candidate;
25. protected evaluation does not become an interactive feedback loop to the
    candidate-producing process;
26. disclosure does not retroactively invalidate an otherwise valid historical
    evaluation;
27. disclosure can remove freshness for descendant candidate lineages;
28. material protected access is preserved through `ProtectedAccessEvent`
    evidence;
29. leakage includes direct and indirect duplicate, outcome, system-state,
    human-tuning, retrieval, prompt, cache, evaluator-feedback, and external
    exposure channels where applicable;
30. `ContaminationState` is exactly `CLEAN`, `SUSPECTED`, `CONFIRMED`, or
    `UNKNOWN`;
31. non-clean contamination state must not be silently represented as clean;
32. repeated protected peeking requires a predeclared governed protocol rather
    than post-hoc best-result selection;
33. invalidated evidence and its original split identity remain preserved;
34. material Task 7 DATA changes require
    `RERUN_AND_PRESERVE_DATA_DISTINCTIONS`;
35. protected freshness is evaluated relative to candidate lineage and claim;
36. `N-H1` uses `SPLIT-NH1-DECISION`;
37. `N-H1` requires at least two applicable independent protected governed
    evaluation units;
38. `N-H1` evidence remains bounded to the exact decision behavior actually
    evaluated;
39. `N-H2` uses `SPLIT-NH2-XFAM`;
40. the initial `N-H2` protocol contains exactly the three E1, E2, and E3
    leave-one-environment-family-out protected target boundaries;
41. an `N-H2` experiment predeclares its primary protected target boundary
    before target outcomes;
42. `N-H2` must not select a successful boundary post hoc while hiding failed
    or negative boundaries;
43. protected target outcomes must not tune the transferred Native mechanism;
44. `A-H1` uses `SPLIT-AH1-ADAPT` and separates governed adaptation input
    from protected target outcomes;
45. `A-H1` preserves protected primary-outcome and applicable
    critical-invariant evidence;
46. `A-H2` uses `SPLIT-AH2-RETENTION` and preserves protected
    prior-capability, locality, and applicable invariant evidence;
47. paired `A-H2` pre-adaptation, post-adaptation, and post-rollback
    measurements preserve unit identity without pretending they are three
    independent units;
48. Task 5 qualification split-plan identities do not manufacture
    `QUALIFIED_SUPPORTED` capability state;
49. Task 8 retains baseline ownership and Task 9 retains cost/resource
    ownership;
50. Task 7 completion qualifies the split protocol only and does not establish
    scientific support for `N-H1`, `N-H2`, `A-H1`, or `A-H2`, does not create
    experimental `PASS`, and does not promote Task 5 capability support.

Qualification must include:

- structural validation;
- semantic validation;
- decision/register synchronization;
- adversarial mutation qualification;
- regression qualification for Tasks 1 through 6;
- development-state qualification;
- final accepted-state qualification.

Qualification criteria must not be weakened merely to obtain a passing result.

## 50. Split Protocol Principle

The Task 7 principle is:

> protected evidence is defined by governed identity, provenance, access,
> lineage, and use — not by a file name.

Development evidence may help create candidates.

Validation evidence may help choose candidates.

Protected evidence exists to test a frozen claim without allowing the tested
outcome to manufacture the candidate or the claim itself.

A valid split preserves:

- what evidence existed;
- where it came from;
- how it was partitioned;
- what the candidate had access to;
- what remained protected;
- what counted as an independent unit;
- who evaluated it;
- when protected information was disclosed;
- whether contamination occurred;
- which exact split version governed the result.

Negative evidence remains evidence.

Invalid evidence remains preserved as invalidated history.

A new partition does not erase an old result.

A new result does not silently rewrite an old partition.

Task 7 provides the evidence boundary.

Tasks 5 and 6 still determine what must be demonstrated.

Tasks 8 and 9 still determine baseline and resource bindings.

Actual experiments must still earn their outcomes.


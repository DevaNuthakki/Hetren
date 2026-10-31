# Task 8 Baseline Methodology Research Review

**Task:** `8 / 100`
**State:** `RESEARCH_INTAKE`
**Execution authority:** `AUTH-HETREN-MVP-3.0`
**Long-term authority:** `AUTH-HETREN-MASTER-2.0`
**Research scope:** Cross-program baseline methodology for Native and Adaptive Intelligence
**Authoritative specification:** Not yet created
**Governing decision:** Not yet created
**Scientific support established by this review:** NO

---

## 1. Purpose

This document records external and internal evidence used to design Hetren's
Task 8 baseline contract.

It is a research-input artifact.

It does not itself establish implementation authority, scientific support,
baseline superiority, or product capability support.

External sources inform Hetren design but do not override accepted Hetren
authority. A conflict with an accepted Hetren contract requires explicit
analysis and, when material, a governed decision.

## 2. Internal Hetren Authority

Task 8 inherits requirements from:

- Task 3 success-contract semantics;
- Task 5 capability-support boundaries;
- Task 6 Native and Adaptive research hypotheses;
- Task 7 split, protected-evidence, contamination, and baseline-handoff rules;
- Decision 0002 governance and research-change consequences.

Task 8 owns concrete:

- baseline implementations;
- baseline identities;
- baseline versions;
- baseline comparison configuration.

Task 8 does not own:

- Task 7 split identities or protected-data semantics;
- Task 9 concrete cost/effort/accounting values;
- retroactive scientific support for N-H1, N-H2, A-H1, or A-H2.

## 3. Research Questions

The review must answer at least:

1. What makes a comparator scientifically meaningful?
2. How is the strongest applicable baseline selected without hindsight?
3. What candidate/baseline conditions must be matched?
4. What identity and version information must be frozen?
5. How should stochastic systems be compared?
6. How should uncertainty and effect size be reported?
7. How should agent trajectories be preserved and interpreted?
8. How should benchmark contamination be represented?
9. What controls are necessary for cross-domain transfer claims?
10. What controls are necessary for adaptation claims?
11. How are forgetting, retention, locality, and rollback compared?
12. When does a stronger newly available baseline require recomparison?
13. Which resource-matching semantics belong to Task 8 versus Task 9?
14. How are real-world and benchmark evaluations related without conflating them?

## 4. Source Classes

Evidence is grouped by evidentiary role:

- standards and measurement-science guidance;
- peer-reviewed research;
- strong benchmark/evaluation literature;
- reproducibility and statistical-methodology literature;
- production-engineering literature;
- books and practitioner synthesis;
- recent talks, interviews, incident reports, and industry practice.

No source class automatically becomes Hetren authority.

## 5. Candidate Requirement Matrix

Each candidate requirement will record:

- Requirement ID;
- Requirement statement;
- Internal Hetren authority;
- External supporting evidence;
- Contrary evidence or caveats;
- Applicable hypotheses;
- Applicable environment families;
- Task 8 disposition;
- Task 9 handoff, if any.

Allowed research dispositions are initially:

- `REQUIRED_CANDIDATE`;
- `CONDITIONAL_CANDIDATE`;
- `DEFER_TASK_9`;
- `REJECTED`;
- `OPEN_QUESTION`.

These are research-review states only and are not final governed vocabulary.

## 6. Initial External Evidence Themes

The review will investigate:

- matched and relevant baseline conditions;
- strongest-reasonable baseline selection;
- benchmark-selection bias;
- benchmark contamination;
- external validity;
- reproducibility;
- model, tool, evaluator, prompt, and environment versioning;
- stochastic replication;
- statistical uncertainty;
- effect size;
- trajectory/transcript evidence for agents;
- transfer controls;
- adaptation controls;
- forgetting and backward transfer;
- rollback and retention;
- real-world production validity;
- performance-versus-resource reporting.

## 7. Non-Negotiable Research Integrity Rules

The review must not:

- choose weak comparators to make Hetren appear stronger;
- select benchmarks because Hetren already performs well on them;
- use protected outcomes to choose a baseline;
- treat one favorable stochastic run as superiority;
- hide failed comparisons;
- silently replace historical baseline identity;
- allow an external source to rewrite accepted Hetren authority without a
  governed decision;
- manufacture Task 5 capability support;
- manufacture scientific support for Task 6 hypotheses.

## 8. Research Status

`IN_PROGRESS`

No final Task 8 baseline contract has been accepted.

## 9. Evidence Weighting Policy

External evidence is not treated as one undifferentiated authority class.

The initial Task 8 research review uses four evidence roles:

- `PRIMARY_MEASUREMENT_GUIDANCE` — standards-body or measurement-science
  guidance directly relevant to evaluation design;
- `SCIENTIFIC_EVIDENCE` — peer-reviewed or otherwise substantial scientific
  work relevant to comparison, reproducibility, transfer, adaptation, or
  evaluation validity;
- `BENCHMARK_DESIGN_EVIDENCE` — benchmark papers and evaluation frameworks
  useful for design lessons but not automatically adopted as Hetren
  benchmarks;
- `PRACTITIONER_CONTEXT` — books, engineering guidance, interviews, incident
  analysis, talks, or operational experience useful for identifying practical
  requirements and failure modes.

Publication recency does not automatically increase evidentiary authority.

Draft standards are recorded as drafts.

Preprints are recorded as preprints.

Practitioner material may motivate a candidate requirement but does not by
itself establish a scientific requirement.

No external source can override accepted Hetren authority without an explicit
governed change.

## 10. Initial Source Registry

### S001 — NIST AI 800-2 Initial Public Draft

**Title:** Practices for Automated Benchmark Evaluations of Language Models
**Organization:** NIST / CAISI
**Date:** January 2026
**Status:** Initial Public Draft
**Evidence role:** `PRIMARY_MEASUREMENT_GUIDANCE`

Relevant themes:

- define evaluation objectives before measurement;
- identify relevant baseline measurements;
- select benchmarks for conceptual fit and coverage;
- document benchmark-to-objective relationships before evaluation;
- design reproducible evaluation protocols;
- conduct statistical analysis and uncertainty quantification;
- qualify claims to match what the evaluation measures;
- recognize when automated benchmarks are insufficient.

Caveat:

This document is a public draft rather than final mandatory Hetren authority.

### S002 — NIST TEVV-Athlon

**Title:** The TEVV-Athlon Framework for Evaluating AI Systems
**Organization:** NIST
**Date:** August 2026 initial public draft
**Evidence role:** `PRIMARY_MEASUREMENT_GUIDANCE`

Relevant themes:

- extensible Test, Evaluation, Verification, and Validation;
- applicability across statistical ML, language, multimodal, and agentic
  systems;
- evaluation design should adapt to application requirements rather than force
  unlike systems into one metric.

Caveat:

Initial-public-draft status must remain explicit.

### S003 — NIST ARIA Evaluation Planning Manual

**Title:** ARIA Evaluation Planning Manual: Elements of ARIA-Style AI
Evaluations
**Organization:** NIST
**Date:** September 18, 2026
**Report:** NIST AI 200-3
**Evidence role:** `PRIMARY_MEASUREMENT_GUIDANCE`

Relevant themes:

- holistic evaluation;
- model testing;
- red teaming;
- user testing;
- customized evaluation plans;
- trustworthiness cannot necessarily be reduced to one automated benchmark.

### S004 — The Benchmark Lottery

**Authors:** Mostafa Dehghani et al.
**Year:** 2021
**Evidence role:** `SCIENTIFIC_EVIDENCE`

Relevant themes:

- apparent algorithm superiority can depend materially on benchmark choice;
- benchmark selection encodes judgments about what matters;
- cross-benchmark conclusions require care;
- favorable benchmark selection must not become hidden evidence selection.

### S005 — DomainBed / In Search of Lost Domain Generalization

**Authors:** Ishaan Gulrajani and David Lopez-Paz
**Year:** 2020
**Evidence role:** `SCIENTIFIC_EVIDENCE`

Relevant themes:

- datasets, architectures, and model-selection procedures must be controlled
  for fair comparison;
- model selection is part of the method rather than an irrelevant detail;
- carefully implemented simple baselines can be unexpectedly competitive.

### S006 — ERM++

**Title:** ERM++: An Improved Baseline for Domain Generalization
**Authors:** Piotr Teterwak et al.
**Year:** 2023
**Evidence role:** `SCIENTIFIC_EVIDENCE`

Relevant themes:

- weak implementation of a simple baseline can create false impressions of
  improvement;
- initialization, training duration, validation strategy, and regularization
  can materially change baseline strength;
- complexity is not evidence of superiority.

### S007 — Deep Reinforcement Learning That Matters

**Authors:** Peter Henderson et al.
**Venue:** AAAI
**Year:** 2018
**Evidence role:** `SCIENTIFIC_EVIDENCE`

Relevant themes:

- stochastic variance can make apparent improvements difficult to interpret;
- standardized reporting matters;
- significance and uncertainty matter;
- reproducibility is necessary for meaningful comparison.

### S008 — NeurIPS Reproducibility Program Report

**Title:** Improving Reproducibility in Machine Learning Research
**Authors:** Joelle Pineau et al.
**Venue:** JMLR
**Year:** 2021
**Evidence role:** `SCIENTIFIC_EVIDENCE`

Relevant themes:

- reproducible code and data improve confidence in findings;
- robust experimental workflows reduce unintended error;
- experimental reporting is part of scientific quality.

### S009 — HELM

**Title:** Holistic Evaluation of Language Models
**Authors:** Percy Liang et al.
**Year:** 2022
**Evidence role:** `BENCHMARK_DESIGN_EVIDENCE`

Relevant themes:

- standardized evaluation conditions;
- scenario coverage;
- multiple metrics rather than accuracy alone;
- explicit trade-offs among quality, robustness, calibration, fairness,
  toxicity, and efficiency;
- raw outputs can support later analysis.

### S010 — SWE-bench

**Title:** SWE-bench: Can Language Models Resolve Real-World GitHub Issues?
**Authors:** Carlos E. Jimenez et al.
**Year:** 2023
**Evidence role:** `BENCHMARK_DESIGN_EVIDENCE`

Relevant themes:

- real software repositories rather than toy code-generation tasks;
- executable environments;
- task success requires interacting with real system context;
- benchmark realism can require multi-file and long-context work.

SWE-bench is a design reference, not automatically a Hetren E1 baseline.

### S011 — AgentBench

**Title:** AgentBench: Evaluating LLMs as Agents
**Authors:** Xiao Liu et al.
**Year:** 2023
**Evidence role:** `BENCHMARK_DESIGN_EVIDENCE`

Relevant themes:

- multiple interactive environments;
- multi-turn decision making;
- failure-mode analysis;
- agent evaluation differs from static language-model evaluation.

### S012 — GAIA

**Title:** GAIA: a benchmark for General AI Assistants
**Authors:** Grégoire Mialon et al.
**Year:** 2023
**Evidence role:** `BENCHMARK_DESIGN_EVIDENCE`

Relevant themes:

- reasoning;
- multimodality;
- browsing;
- tool use;
- conceptually simple real-world questions may still expose system weaknesses.

### S013 — AISI Agent Transcript Analysis

**Organization:** UK AI Security Institute
**Evidence role:** `PRACTITIONER_CONTEXT`

Relevant themes:

- pass rate alone can hide materially different failure modes;
- refusal is not identical to inability;
- tool-use failure may differ from underlying capability failure;
- evaluator or harness bugs may distort apparent capability;
- trajectory analysis can expose unsafe or misleading behavior.

### S014 — Benchmark Contamination Survey

**Title:** Benchmarking Large Language Models Under Data Contamination:
A Survey from Static to Dynamic Evaluation
**Venue:** EMNLP
**Year:** 2025
**Evidence role:** `SCIENTIFIC_EVIDENCE`

Relevant themes:

- contamination can inflate apparent benchmark performance;
- static benchmark mitigation has limitations;
- dynamic evaluation introduces its own validation requirements;
- contamination status belongs in evaluation provenance.

### S015 — Avalanche

**Title:** Avalanche: A PyTorch Library for Deep Continual Learning
**Venue:** JMLR
**Year:** 2023
**Evidence role:** `SCIENTIFIC_EVIDENCE`

Relevant themes:

- continual learning requires explicit sequential-learning scenarios;
- training and evaluation protocols need reproducible structure;
- nonstationary evaluation differs from conventional offline evaluation.

### S016 — ML Test Score

**Title:** The ML Test Score: A Rubric for ML Production Readiness and
Technical Debt Reduction
**Authors:** Eric Breck et al.
**Venue:** IEEE Big Data
**Year:** 2017
**Evidence role:** `SCIENTIFIC_EVIDENCE`

Relevant themes:

- production readiness requires more than offline model accuracy;
- testing and monitoring are first-class engineering concerns;
- toy/offline success does not automatically imply production validity.

### S017 — Designing Machine Learning Systems

**Author:** Chip Huyen
**Publisher:** O'Reilly
**Year:** 2022
**Evidence role:** `PRACTITIONER_CONTEXT`

Relevant themes:

- research and production evaluation differ;
- reliability, scalability, maintainability, and adaptability are system-level
  requirements;
- experiment tracking and versioning matter;
- offline evaluation must be related carefully to deployment behavior.

### S018 — CRMArena-Pro

**Title:** CRMArena-Pro: Holistic Assessment of LLM Agents Across Diverse
Business Scenarios and Interactions
**Venue:** Transactions on Machine Learning Research
**Year:** 2026
**Evidence role:** `BENCHMARK_DESIGN_EVIDENCE`

Relevant themes:

- multi-turn interaction can materially lower apparent agent performance;
- realistic business scenarios reveal limitations hidden by simpler tasks;
- confidentiality and workflow behavior can require separate evaluation.

### S019 — AgencyBench

**Title:** AgencyBench: Benchmarking the Frontiers of Autonomous Agents in
1M-Token Real-World Contexts
**Year:** 2026
**Status:** Preprint
**Evidence role:** `BENCHMARK_DESIGN_EVIDENCE`

Relevant themes:

- long-horizon tasks;
- high tool-call counts;
- large context;
- resource efficiency;
- scaffold choice can materially affect system performance.

Caveat:

Preprint evidence is supporting rather than governing.

### S020 — AlphaEval

**Title:** AlphaEval: Evaluating Agents in Production
**Year:** 2026
**Status:** Preprint
**Evidence role:** `BENCHMARK_DESIGN_EVIDENCE`

Relevant themes:

- production requirements often contain implicit constraints;
- complete agent products may behave differently from model-only evaluation;
- real tasks may require heterogeneous inputs and domain expertise;
- evaluation may require several grading paradigms.

Caveat:

Preprint evidence is supporting rather than governing.

### S021 — Real-World Work Coverage Analysis

**Title:** How Well Does Agent Development Reflect Real-World Work?
**Year:** 2026
**Status:** Preprint
**Evidence role:** `BENCHMARK_DESIGN_EVIDENCE`

Relevant themes:

- benchmark portfolios may overrepresent particular work categories;
- benchmark coverage should be compared with the real claim scope;
- realism, coverage, and granular evaluation are separate concerns.

Caveat:

Preprint evidence is supporting rather than governing.

## 11. Cross-Source Synthesis Before Requirement Drafting

The initial literature pass supports the following research observations.

### 11.1 Strong baselines are a scientific control

A baseline must not be intentionally or accidentally weakened through poor
configuration, obsolete implementation, mismatched information, or inferior
model-selection procedure.

Complexity does not make a comparator strong.

### 11.2 Baseline selection is part of the experimental contract

Selecting the comparator after inspecting protected outcomes can manufacture an
apparent advantage.

Baseline eligibility and selection therefore need a pre-protected rule.

### 11.3 Benchmark choice is part of claim scope

No benchmark universally represents all capabilities.

Benchmark coverage, construct fit, missing areas, and real-world relevance must
remain explicit.

### 11.4 One score is insufficient for many Hetren claims

Outcome quality, robustness, safety, retention, locality, process behavior, and
resource use may need separate reporting.

A composite score must not hide a failed hard constraint.

### 11.5 Stochastic systems require repeated evidence

One favorable run is not sufficient evidence of superiority when execution or
model behavior is stochastic.

The comparison protocol must preserve uncertainty and replication information.

### 11.6 Agent outcomes need process evidence when process affects interpretation

For interactive agents, identical task outcomes can result from materially
different behaviors.

Where relevant, trajectory evidence is needed to distinguish:

- inability;
- refusal;
- tool failure;
- scaffold failure;
- evaluator failure;
- unsafe behavior;
- premature termination;
- genuine task-solving behavior.

### 11.7 Contamination can invalidate generalization interpretation

Benchmark exposure, derivatives, labels, answer leakage, or other contamination
can inflate measured performance.

Contamination provenance therefore belongs in the comparison record.

### 11.8 Adaptive evaluation requires more than target improvement

Useful adaptation must be distinguished from:

- ordinary retraining;
- pre-existing capability;
- transfer without adaptation;
- catastrophic forgetting;
- uncontrolled global change;
- inability to restore the prior state.

This observation is consistent with Hetren's existing separation of `A-H1`
from `A-H2`.

### 11.9 Automated benchmarks and real-world validity are different evidence

Automated benchmarks are valuable when tasks and grading can be made
structured and verifiable.

Open-ended, dynamic, human-in-the-loop, or process-sensitive claims may require
additional evaluation methods.

### 11.10 Current agent benchmarks are references, not Hetren authority

SWE-bench, AgentBench, GAIA, CRMArena-Pro, AgencyBench, AlphaEval, and similar
work may influence environment or baseline design.

None becomes a Hetren baseline merely because it is prominent or recent.

## 12. Candidate Baseline Requirements

The requirements in this section are research candidates.

They do not become Hetren authority merely by appearing in this research
review.

Each candidate must later survive contradiction analysis, adversarial review,
internal-authority reconciliation, and governed Task 8 qualification.

### BR-001 — Stable Baseline Identity And Version

**Disposition:** `REQUIRED_CANDIDATE`

**Internal authority:** Tasks 3, 4, 6, and 7.

**External evidence:** `S001`, `S005`, `S008`, `S017`.

**Hypotheses:** `N-H1`, `N-H2`, `A-H1`, `A-H2`.

**Environment families:** `E1`, `E2`, `E3`.

**Task 9 handoff:** None.

**Candidate requirement:**

Every governed baseline binding must resolve to a stable baseline identity and
an immutable baseline version.

A material change that can alter baseline behavior, outputs, comparison
meaning, or reproducibility must create a new baseline version rather than
silently modifying the historical version.

A baseline reference must not silently float to a provider's latest model,
latest prompt, latest package, latest service behavior, or latest
implementation.

**Rationale:**

Without stable identity and versioning, historical comparisons cannot be
interpreted or reproduced.

**Caveat:**

Some external APIs cannot provide fully immutable implementations. In those
cases Hetren must preserve the strongest available provider/model revision
identity, evaluation timestamp, configuration, response provenance, and the
resulting reproducibility limitation rather than falsely claiming exact
reproduction.

### BR-002 — Pre-Protected Baseline Binding Freeze

**Disposition:** `REQUIRED_CANDIDATE`

**Internal authority:** Tasks 6 and 7.

**External evidence:** `S001`, `S004`, `S005`.

**Hypotheses:** `N-H1`, `N-H2`, `A-H1`.

**Environment families:** `E1`, `E2`, `E3`.

**Task 9 handoff:** Resource values remain deferred.

**Candidate requirement:**

Before applicable protected outcomes are inspected, the governed experiment
must bind:

- the baseline identity;
- the baseline version;
- the baseline role;
- the baseline-selection rule;
- the comparison configuration;
- the applicable resource-matching rule.

Changing a material baseline binding after protected-outcome inspection is a
new comparison contract and must not silently rewrite the earlier result.

**Rationale:**

Post-outcome comparator selection creates a direct path for hindsight bias and
benchmark gaming.

**Caveat:**

A later baseline correction may be scientifically necessary. The correction
must create a governed successor comparison while preserving the earlier
evidence and its disposition.

### BR-003 — Strongest Applicable Comparator Selection

**Disposition:** `REQUIRED_CANDIDATE`

**Internal authority:** Task 6 strongest-baseline requirements and Task 7
baseline handoff.

**External evidence:** `S004`, `S005`, `S006`.

**Hypotheses:** `N-H1`, `N-H2`, `A-H1`.

**Environment families:** `E1`, `E2`, `E3`.

**Task 9 handoff:** Resource constraints may affect comparator eligibility.

**Candidate requirement:**

Where Hetren requires the strongest applicable comparator, the experiment must
predeclare:

- an eligible comparator set;
- eligibility criteria;
- matching constraints;
- the development/validation evidence used for selection;
- the selection rule;
- tie handling.

Protected outcomes must not participate in comparator selection.

For Task 8, "strongest applicable" means the strongest eligible matched
comparator under the governed comparison contract.

It does not mean that Hetren has established the globally strongest comparator
in existence.

**Rationale:**

The literature shows that apparent algorithmic superiority can disappear when
benchmark, implementation, tuning, or model-selection conditions change.

**Caveat:**

The strongest known comparator can change over time. Historical results remain
historical rather than being retroactively rewritten.

### BR-004 — Simple And Strong Comparator Roles Remain Distinct

**Disposition:** `CONDITIONAL_CANDIDATE`

**Internal authority:** Task 6 baseline-role distinctions.

**External evidence:** `S005`, `S006`.

**Hypotheses:** `N-H1`, `N-H2`, `A-H1`.

**Environment families:** `E1`, `E2`, `E3`.

**Task 9 handoff:** Applicable resource conditions remain governed separately.

**Candidate requirement:**

When scientifically meaningful, an experiment should preserve both:

- a simple, deterministic, non-learned, no-learning, or otherwise interpretable
  anchor; and
- the strongest applicable matched comparator.

A simple anchor may diagnose whether learning or complexity adds value.

A simple anchor must not substitute for the strongest matched comparator when
the governing hypothesis requires the strongest comparator.

**Rationale:**

Simple baselines are scientifically useful, but poorly implemented or
deliberately weak simple baselines can exaggerate apparent novelty.

**Caveat:**

Not every evaluation has a meaningful simple or non-learned comparator.
Absence must be justified rather than forcing an artificial comparator into
the experiment.

### BR-005 — Comparison-Condition Parity

**Disposition:** `REQUIRED_CANDIDATE`

**Internal authority:** Tasks 3, 6, and 7.

**External evidence:** `S001`, `S005`, `S009`.

**Hypotheses:** `N-H1`, `N-H2`, `A-H1`.

**Environment families:** `E1`, `E2`, `E3`.

**Task 9 handoff:** Concrete time, token, compute, monetary, and effort values
belong to Task 9.

**Candidate requirement:**

Candidate and baseline must be compared under a declared matching contract for
all dimensions that can materially affect interpretation, including as
applicable:

- task information;
- data access;
- allowed tools;
- permissions;
- external services;
- environment state;
- interaction horizon;
- evaluator;
- evaluation units;
- protected-outcome access;
- resource-comparison regime.

A difference is permitted when the difference itself is part of the declared
treatment being tested.

Such differences must be explicit rather than hidden.

**Rationale:**

A performance difference is uninterpretable when the systems are unknowingly
given materially different opportunities.

**Caveat:**

Fair comparison does not require different algorithms to have identical
internal structure or identical implementation technique.

### BR-006 — Tuning And Model-Selection Governance

**Disposition:** `REQUIRED_CANDIDATE`

**Internal authority:** Tasks 6 and 7.

**External evidence:** `S004`, `S005`, `S006`.

**Hypotheses:** `N-H1`, `N-H2`, `A-H1`.

**Environment families:** `E1`, `E2`, `E3`.

**Task 9 handoff:** Search and engineering effort accounting belongs to Task 9.

**Candidate requirement:**

Baseline and candidate tuning must obey a declared model-selection contract.

The contract must identify as applicable:

- tunable parameters;
- search procedure;
- development evidence;
- validation evidence;
- stopping rule;
- model-selection criterion;
- protected-data prohibition;
- resource policy.

Protected outcomes must not be used to tune either side.

A baseline must not be left deliberately under-tuned merely because the
candidate received greater engineering attention.

**Rationale:**

Model selection is part of the evaluated method and can materially affect
apparent superiority.

**Caveat:**

Equivalent scientific opportunity does not necessarily mean identical search
spaces or identical numbers of parameters because different methods expose
different legitimate controls.

### BR-007 — Exact Comparison Provenance

**Disposition:** `REQUIRED_CANDIDATE`

**Internal authority:** Tasks 3, 4, 6, and 7.

**External evidence:** `S001`, `S008`, `S009`, `S017`.

**Hypotheses:** `N-H1`, `N-H2`, `A-H1`, `A-H2`.

**Environment families:** `E1`, `E2`, `E3`.

**Task 9 handoff:** Resource observations will later reference this provenance.

**Candidate requirement:**

A governed baseline comparison must preserve or reference all material
configuration needed to interpret the result, including as applicable:

- baseline identity and version;
- candidate identity and version;
- target system and system version;
- model/provider/revision;
- prompts or policies;
- scaffold/orchestration version;
- inference parameters;
- tool identities and versions;
- permissions;
- evaluator identity and version;
- environment identity and version;
- split and partition identities;
- data or artifact versions;
- source-code revision;
- material dependency versions;
- random seeds or sampling configuration;
- execution timestamp;
- external-service revision information when available.

**Rationale:**

A result without sufficient configuration provenance cannot reliably support
historical interpretation or reproduction.

**Caveat:**

Not every external dependency exposes immutable version identifiers. Unknown
or unavailable provenance must be represented honestly rather than invented.

### BR-008 — Reproducible Comparison Manifest

**Disposition:** `REQUIRED_CANDIDATE`

**Internal authority:** Tasks 3, 6, and 7.

**External evidence:** `S001`, `S008`, `S016`, `S017`.

**Hypotheses:** `N-H1`, `N-H2`, `A-H1`, `A-H2`.

**Environment families:** `E1`, `E2`, `E3`.

**Task 9 handoff:** Task 9 may enrich the manifest with concrete resource
measurements.

**Candidate requirement:**

Each consequential comparison must have a versioned experiment manifest
sufficient to reconstruct or faithfully replay the comparison to the extent
permitted by the underlying systems.

The manifest must reference immutable or integrity-checked material artifacts
where practical.

A comparison that depends on an irreproducible external system must record the
limitation explicitly.

**Rationale:**

Reproducibility is necessary to distinguish a durable result from an
uninspectable historical anecdote.

**Caveat:**

Reproduction does not require falsely promising byte-identical behavior from
nondeterministic or externally controlled services.

### BR-009 — Stochastic Replication And Uncertainty

**Disposition:** `CONDITIONAL_CANDIDATE`

**Internal authority:** Task 6 uncertainty requirements and Task 7
evaluation-unit semantics.

**External evidence:** `S001`, `S007`, `S008`, `S018`.

**Hypotheses:** `N-H1`, `N-H2`, `A-H1`, `A-H2`.

**Environment families:** `E1`, `E2`, `E3`.

**Task 9 handoff:** Replication cost is measured by Task 9.

**Candidate requirement:**

When candidate, baseline, environment, evaluator, or sampling behavior is
materially stochastic, the evaluation must predeclare:

- replication unit;
- number or stopping rule for repeated attempts;
- seed or sampling policy where controllable;
- aggregation method;
- uncertainty method;
- relevant sources of variation.

Repeated stochastic runs must not be counted as new independent scientific
evaluation units when Task 7 dependency semantics say they share the same
underlying unit.

**Rationale:**

A single favorable sample can be misleading when model or environment behavior
has substantial variance.

**Caveat:**

A universal fixed number of seeds or attempts is not justified across all
Hetren environments. The replication design must follow the expected sources
of variation and statistical contract.

### BR-010 — Effect Size And Statistical Uncertainty

**Disposition:** `REQUIRED_CANDIDATE`

**Internal authority:** Task 6 hypothesis thresholds.

**External evidence:** `S001`, `S007`.

**Hypotheses:** `N-H1`, `N-H2`, `A-H1`.

**Environment families:** `E1`, `E2`, `E3`.

**Task 9 handoff:** None except resource consequences of additional runs.

**Candidate requirement:**

A comparison used for a scientific superiority claim must report the
predeclared effect measure and applicable uncertainty.

When pairing is scientifically valid, the analysis should preserve the paired
comparison rather than discarding useful dependency structure.

Statistical significance alone must not substitute for material effect size.

Task 8 must not replace or weaken the quantitative qualification thresholds
already governed by Task 6.

**Rationale:**

A statistically detectable difference can still be scientifically or
operationally negligible.

**Caveat:**

The appropriate interval or statistical model depends on the evaluation-unit
and sampling design and therefore must not be hard-coded universally by Task
8.

### BR-011 — Benchmark Construct, Coverage, And Claim Scope

**Disposition:** `REQUIRED_CANDIDATE`

**Internal authority:** Tasks 3, 5, 6, and 7.

**External evidence:** `S001`, `S002`, `S003`, `S004`, `S009`, `S021`.

**Hypotheses:** `N-H1`, `N-H2`, `A-H1`, `A-H2`.

**Environment families:** `E1`, `E2`, `E3`.

**Task 9 handoff:** None.

**Candidate requirement:**

Before a benchmark or evaluation environment is used for a governed baseline
claim, the experiment must document:

- the measurement construct;
- why the benchmark measures that construct;
- applicable environment family;
- claim scope;
- coverage;
- known omissions;
- difficulty relevance;
- dependency structure;
- expected relationship to intended real-world behavior;
- material limitations.

Benchmark selection must not be changed after protected outcomes are observed
merely because another benchmark produces a more favorable candidate result.

**Rationale:**

Benchmark choice can materially alter method rankings and therefore forms part
of the experimental claim.

**Caveat:**

No benchmark is required to represent every possible deployment context.
Narrow, truthful evidence is preferable to broad unsupported generalization.

### BR-012 — Contamination And Exposure Provenance

**Disposition:** `REQUIRED_CANDIDATE`

**Internal authority:** Tasks 4, 6, and 7.

**External evidence:** `S001`, `S014`.

**Hypotheses:** `N-H1`, `N-H2`, `A-H1`, `A-H2`.

**Environment families:** `E1`, `E2`, `E3`.

**Task 9 handoff:** None.

**Candidate requirement:**

Every consequential baseline comparison must represent known, suspected,
unknown, or ruled-out contamination and exposure relationships that can
materially affect interpretation.

The comparison record must distinguish, as applicable:

- training-data exposure;
- benchmark-publication exposure;
- development exposure;
- validation exposure;
- protected-outcome exposure;
- benchmark derivatives;
- semantically equivalent or near-duplicate examples;
- answer or label leakage;
- evaluator leakage;
- target-family-specific leakage;
- prior execution or transcript exposure.

Absence of known contamination must not be represented as proof that
contamination is impossible.

A baseline or candidate with materially different exposure status must not be
described as perfectly matched without recording that limitation.

**Rationale:**

Contamination can inflate apparent capability, obscure transfer boundaries,
and invalidate generalization claims.

**Caveat:**

For externally trained foundation models, exact training-data membership may
be unknowable. Hetren must record uncertainty honestly rather than inventing a
clean-contamination conclusion.

### BR-013 — Hard Constraints Cannot Be Averaged Away

**Disposition:** `REQUIRED_CANDIDATE`

**Internal authority:** Tasks 3 and 6.

**External evidence:** `S003`, `S009`, `S016`.

**Hypotheses:** `N-H1`, `N-H2`, `A-H1`, `A-H2`.

**Environment families:** `E1`, `E2`, `E3`.

**Task 9 handoff:** Resource constraints may later be bound by Task 9.

**Candidate requirement:**

A governed comparison must preserve hard constraints separately from
aggregated performance.

Applicable hard constraints may include:

- critical-invariant violations;
- safety requirements;
- protected-data violations;
- authorization violations;
- rollback requirements;
- retention bounds;
- locality bounds;
- reproducibility requirements;
- comparison-contract violations.

A favorable mean, composite score, or aggregate improvement must not convert a
hard-constraint failure into a scientific `PASS`.

**Rationale:**

A single scalar can hide qualitatively different and unacceptable failure
modes.

**Caveat:**

Task 8 does not independently create new product or safety thresholds. It
preserves thresholds owned by the applicable governing contract.

### BR-014 — E1 Outcome And Trajectory Evidence Remain Distinct

**Disposition:** `CONDITIONAL_CANDIDATE`

**Internal authority:** Tasks 3, 4, 5, 6, and 7.

**External evidence:** `S010`, `S011`, `S012`, `S013`, `S018`, `S019`, `S020`.

**Hypotheses:** `N-H1`, `N-H2`.

**Environment families:** `E1`.

**Task 9 handoff:** Tool-call count, latency, token use, and engineering effort
may later be quantified by Task 9.

**Candidate requirement:**

When agent behavior materially affects interpretation, E1 comparison evidence
must preserve task outcome separately from observable execution trajectory.

Trajectory evidence may include, as applicable:

- action sequence;
- tool calls;
- tool outputs;
- externally visible messages;
- environment transitions;
- retry behavior;
- termination behavior;
- refusals;
- user-help requests;
- detected harness failures;
- evaluator-visible policy or safety events.

The evaluation must permit relevant failure attribution such as:

- task-capability failure;
- refusal;
- tool or integration failure;
- scaffold failure;
- evaluator or harness defect;
- premature termination;
- policy-constrained behavior;
- successful task resolution.

**Rationale:**

Identical aggregate pass rates can conceal materially different agent
behaviors and failure causes.

**Caveat:**

This requirement concerns observable evaluation trajectories and evidence
needed for interpretation. It does not require disclosure or preservation of
private model chain-of-thought.

### BR-015 — N-H2 Transfer Comparator Isolation

**Disposition:** `REQUIRED_CANDIDATE`

**Internal authority:** Tasks 6 and 7.

**External evidence:** `S004`, `S005`, `S011`, `S021`.

**Hypotheses:** `N-H2`.

**Environment families:** `E1`, `E2`, `E3`.

**Task 9 handoff:** Transfer and onboarding effort are quantified by Task 9.

**Candidate requirement:**

A governed `N-H2` comparison must isolate learned cross-family transfer from
advantages that do not establish the claimed transfer mechanism.

The comparison design must include the applicable controls needed to
distinguish the candidate from, at minimum:

- a non-transfer or target-starting reference condition;
- an applicable non-learned or fixed-method comparator;
- shared infrastructure that does not contain the learned decision capability.

The source-side learned advantage required by Task 6 must remain separately
demonstrable.

Protected target outcomes must not be used to select, tune, repair, or
reinterpret the transferred mechanism before the governed protected
evaluation.

**Rationale:**

Shared tools, retrieval, common prompts, target-specific engineering, or
general infrastructure can create target gains without demonstrating learned
cross-family decision transfer.

**Caveat:**

The exact control implementation depends on the environment family and
transfer mechanism. Task 8 should govern the control semantics rather than
pretend one universal implementation fits E1, E2, and E3.

### BR-016 — A-H1 Adaptation Comparator Set

**Disposition:** `REQUIRED_CANDIDATE`

**Internal authority:** Tasks 6 and 7.

**External evidence:** `S015`, `S016`, `S017`.

**Hypotheses:** `A-H1`.

**Environment families:** `E1`, `E2`, `E3`.

**Task 9 handoff:** Adaptation compute, data, token, time, monetary, and human
effort values belong to Task 9.

**Candidate requirement:**

A governed `A-H1` evaluation must distinguish useful Hetren adaptation from
improvement that would occur without the claimed Adaptive mechanism.

The experiment must bind, as applicable:

- the frozen pre-adaptation candidate state;
- a no-adaptation or unchanged reference condition;
- the strongest applicable matched adaptation baseline;
- any scientifically necessary ordinary fine-tuning, retraining, update, or
  other conventional adaptation comparator;
- protected target evaluation separated from adaptation input.

The exact comparator set must be predeclared.

**Rationale:**

Target improvement alone does not demonstrate that Hetren's adaptive method
adds value over ordinary adaptation or over doing nothing.

**Caveat:**

Not every environment supports the same adaptation mechanisms. A comparator
that cannot validly operate in the environment must not be forced into the
experiment solely for symmetry.

### BR-017 — A-H2 Retention, Locality, And Rollback Are Separate Controls

**Disposition:** `REQUIRED_CANDIDATE`

**Internal authority:** Tasks 6 and 7.

**External evidence:** `S015`, `S016`, `S017`.

**Hypotheses:** `A-H2`.

**Environment families:** `E1`, `E2`, `E3`.

**Task 9 handoff:** Recovery time and resource consequences belong to Task 9.

**Candidate requirement:**

An `A-H2` comparison must preserve separately:

- pre-adaptation prior-capability measurements;
- post-adaptation prior-capability measurements;
- locality measurements;
- critical-invariant measurements where applicable;
- executed rollback evidence;
- post-rollback prior-capability measurements.

Target improvement must not substitute for retention, locality, or rollback
evidence.

Averages across unrelated capabilities must not hide a protected
prior-capability regression that violates the governed bound.

**Rationale:**

Continual-learning literature distinguishes learning plasticity from memory
stability, and final average performance can conceal catastrophic or localized
forgetting.

**Caveat:**

Standard continual-learning metrics may inform Hetren but do not automatically
replace the exact protected bounds already governed by `A-H2`.

### BR-018 — Task 8 Defines Resource-Matching Semantics; Task 9 Defines Values

**Disposition:** `REQUIRED_CANDIDATE`

**Internal authority:** Tasks 6 and 7.

**External evidence:** `S001`, `S009`, `S016`, `S019`.

**Hypotheses:** `N-H1`, `N-H2`, `A-H1`, `A-H2`.

**Environment families:** `E1`, `E2`, `E3`.

**Task 9 handoff:** `REQUIRED`.

**Candidate requirement:**

Task 8 must define the semantic comparison regimes under which candidate and
baseline resources are considered:

- strictly matched;
- budget-capped;
- unconstrained but jointly reported;
- or another explicitly governed regime.

Task 8 must identify which resource dimensions are materially relevant to a
comparison.

Task 9 owns the concrete accounting definitions, measurement procedures, and
observed values for dimensions such as:

- tokens;
- API usage;
- compute;
- accelerator time;
- wall-clock time;
- memory;
- storage;
- monetary cost;
- human engineering effort;
- adaptation effort.

Task 8 must not invent Task 9 numerical values.

**Rationale:**

Performance comparisons can be misleading when one system receives materially
greater resources, but baseline methodology and resource accounting are
different responsibilities.

**Caveat:**

Not every comparison requires strict resource equality. The scientific meaning
of a result depends on the predeclared comparison regime.

### BR-019 — Baseline Supersession Requires Recomparison, Not Historical Rewrite

**Disposition:** `REQUIRED_CANDIDATE`

**Internal authority:** Decision 0002 and its `BASELINE` evidence consequence.

**External evidence:** `S004`, `S005`, `S006`, `S008`.

**Hypotheses:** `N-H1`, `N-H2`, `A-H1`.

**Environment families:** `E1`, `E2`, `E3`.

**Task 9 handoff:** A successor comparator may require new resource accounting.

**Candidate requirement:**

When a materially stronger applicable baseline becomes available or a baseline
defect is discovered:

1. the historical baseline result remains preserved;
2. the earlier baseline identity and version remain unchanged;
3. the reason for supersession is recorded;
4. the affected superiority claim is re-evaluated under the applicable
   governance consequence;
5. a successor comparison produces new evidence rather than rewriting the old
   evidence.

A historical result may remain valid for its original comparator while no
longer being sufficient for a current strongest-baseline claim.

**Rationale:**

Scientific history and current state-of-the-art relevance are different
questions.

**Caveat:**

The existence of any newer method does not automatically invalidate prior
evidence. Recomparison is required when the new comparator is materially
applicable to the governed claim.

### BR-020 — Missing Meaningful Comparator Blocks Or Narrows The Claim

**Disposition:** `REQUIRED_CANDIDATE`

**Internal authority:** Tasks 3, 5, 6, and 7.

**External evidence:** `S001`, `S004`, `S005`.

**Hypotheses:** `N-H1`, `N-H2`, `A-H1`.

**Environment families:** `E1`, `E2`, `E3`.

**Task 9 handoff:** None.

**Candidate requirement:**

If a hypothesis requires a meaningful or strongest applicable comparator and
no scientifically defensible comparator can be implemented or reproduced, the
system must not manufacture one.

The affected comparison must instead be:

- blocked;
- inconclusive;
- explicitly narrowed;
- or governed under another truthful disposition.

Absence of a comparator must not be converted into evidence that Hetren is
superior.

**Rationale:**

A weak invented comparator is worse than an honest evidence gap.

**Caveat:**

Exploratory engineering may still proceed without a definitive comparator, but
the resulting work cannot establish the governed superiority claim.

### BR-021 — Benchmark Evidence And Real-World Validity Remain Distinct

**Disposition:** `REQUIRED_CANDIDATE`

**Internal authority:** Tasks 3, 5, and 6.

**External evidence:** `S001`, `S002`, `S003`, `S010`, `S018`, `S020`, `S021`.

**Hypotheses:** `N-H1`, `N-H2`, `A-H1`, `A-H2`.

**Environment families:** `E1`, `E2`, `E3`.

**Task 9 handoff:** Real-world operational cost evidence belongs to Task 9.

**Candidate requirement:**

Passing an automated benchmark comparison establishes evidence only for the
scope represented by that benchmark and its governed evaluation contract.

Where the intended claim materially involves:

- open-ended operation;
- long-horizon behavior;
- human interaction;
- changing environments;
- workflow integration;
- production constraints;
- safety-relevant behavior;
- deployment-specific conditions;

additional evaluation may be required.

Such evaluation may include appropriately governed simulation, red teaming,
user testing, field testing, shadow evaluation, replay, or other methods
appropriate to the claim.

Benchmark success must not be silently relabeled as production readiness.

**Rationale:**

Automated benchmark evaluation and real-world validity answer overlapping but
different questions.

**Caveat:**

Task 8 does not require human or production testing for every baseline
comparison. Additional evaluation is required only when the claim exceeds what
the automated benchmark can validly establish.

### BR-022 — Independent Verification Of Consequential Baseline Comparisons

**Disposition:** `REQUIRED_CANDIDATE`

**Internal authority:** Tasks 3, 6, and 7.

**External evidence:** `S003`, `S008`, `S013`.

**Hypotheses:** `N-H1`, `N-H2`, `A-H1`, `A-H2`.

**Environment families:** `E1`, `E2`, `E3`.

**Task 9 handoff:** Verification resource cost belongs to Task 9.

**Candidate requirement:**

A consequential baseline comparison used to support a governed scientific or
support claim must be independently verifiable under the applicable Task 7
verification contract.

Verification must be sufficiently separated from the candidate-producing path
to detect material defects such as:

- incorrect baseline configuration;
- wrong baseline version;
- evaluator mismatch;
- split mismatch;
- hidden candidate/baseline asymmetry;
- contamination or exposure error;
- result aggregation error;
- trajectory-classification error where applicable;
- broken adaptation control;
- missing rollback evidence;
- provenance inconsistency.

Independent verification does not require a completely separate organization
for every MVP experiment.

It requires a sufficiently separate evaluation authority or path appropriate
to the consequence of the claim.

**Rationale:**

A comparison pipeline can reproduce its own mistake unless verification has
enough independence to challenge the implementation and evidence.

**Caveat:**

The required degree of independence should be proportional to claim
consequence and must remain compatible with the separate Task 7 verification
contract.

## 13. Adversarial And Contradiction Review

This section actively attempts to break the Task 8 candidate requirements.

Its purpose is not to defend the current draft.

A candidate requirement that is ambiguous, gameable, scientifically
unjustified, operationally impossible, redundant with another authority, or
capable of producing misleading evidence must be revised, narrowed, deferred,
or rejected before Task 8 becomes governing authority.

No finding in this section by itself changes an existing `BR-*` requirement.

No `BR-*` requirement becomes accepted merely because it survives one attack
pass.

## 14. Adversarial Source Addendum

### S022 — Generalization In Adaptive Data Analysis And Holdout Reuse

**Authors:** Cynthia Dwork, Vitaly Feldman, Moritz Hardt, Toni Pitassi,
Omer Reingold, Aaron Roth
**Venue:** NeurIPS
**Year:** 2015
**Evidence role:** `SCIENTIFIC_EVIDENCE`

Relevant themes:

- repeated adaptive interaction with holdout results can overfit the holdout;
- validity depends on more than preserving a nominal train/test filename;
- feedback from repeated evaluation can become part of the development
  process;
- reuse must be governed rather than assumed harmless.

Task 8 relevance:

Baseline search, comparator replacement, tuning, or evaluator modification must
not create an indirect development loop through protected outcomes.

### S023 — Humans Or LLMs As The Judge? A Study On Judgement Bias

**Authors:** Guiming Hardy Chen et al.
**Venue:** EMNLP
**Year:** 2024
**Evidence role:** `SCIENTIFIC_EVIDENCE`

Relevant themes:

- human and LLM judges can exhibit systematic evaluation biases;
- evaluator outputs are not automatically objective ground truth;
- evaluator robustness must be tested when evaluator behavior materially
  affects conclusions.

Task 8 relevance:

Evaluator identity, configuration, limitations, and validation belong to
baseline-comparison provenance.

### S024 — Large Language Models Are Not Fair Evaluators

**Authors:** Peiyi Wang et al.
**Venue:** ACL
**Year:** 2024
**Evidence role:** `SCIENTIFIC_EVIDENCE`

Relevant themes:

- pairwise LLM evaluation can exhibit position bias;
- candidate ordering can materially change apparent rankings;
- evaluation protocol design can alter the observed winner independently of
  underlying candidate quality.

Task 8 relevance:

Pairwise evaluator order, randomization, calibration, and evaluator-validity
controls may be material comparison variables.

### S025 — In Benchmarks We Trust ... Or Not?

**Authors:** Ine Gevers et al.
**Venue:** EMNLP
**Year:** 2025
**Evidence role:** `SCIENTIFIC_EVIDENCE`

Relevant themes:

- modern benchmark failure modes span more than contamination alone;
- benchmark creation and benchmark usage both require explicit validity checks;
- solving one benchmark weakness can leave other weaknesses intact;
- benchmark checklists can improve systematic evaluation review.

Task 8 relevance:

A baseline contract must not reduce benchmark validity to one threat such as
data contamination.

### S026 — Flaw Or Artifact? Rethinking Prompt Sensitivity In Evaluating LLMs

**Authors:** Andong Hua et al.
**Venue:** EMNLP
**Year:** 2025
**Evidence role:** `SCIENTIFIC_EVIDENCE`

Relevant themes:

- some apparent model sensitivity can originate in the scoring or evaluation
  procedure;
- rigid answer matching can misclassify semantically valid outputs;
- evaluator choice can change apparent performance variance and ranking
  stability.

Task 8 relevance:

Observed candidate-versus-baseline differences must be distinguishable from
evaluation artifacts.

## 15. Adversarial Findings

### AF-001 — Comparator-Set Cherry Picking

**Targets:** `BR-003`

**Attack:**

A team can define an apparently reasonable eligible comparator set while
quietly excluding a stronger method.

The phrase "strongest applicable" does not prevent gaming if applicability is
itself chosen after extensive informal experimentation.

**Evidence:** `S004`, `S005`, `S006`, `S025`.

**Preliminary disposition:** `REVISE_REQUIRED`

**Needed protection:**

The eventual governed contract should require predeclared comparator
eligibility criteria, preserved considered-comparator provenance, and reasons
for material exclusions.

### AF-002 — Comparator Exclusion By Convenient Incompatibility

**Targets:** `BR-003`, `BR-020`

**Attack:**

A strong comparator can be classified as "not applicable" using an
under-specified compatibility rule.

That allows a weaker comparator to become the strongest remaining eligible
baseline.

**Evidence:** `S005`, `S006`, `S025`.

**Preliminary disposition:** `REVISE_REQUIRED`

**Needed protection:**

Applicability decisions need testable criteria and preserved justification,
not merely narrative preference.

### AF-003 — False Fairness Through Naive Parity

**Targets:** `BR-005`

**Attack:**

Requiring superficially identical conditions can itself create an unfair
comparison when different methods legitimately require different internal
operations.

Conversely, declaring every asymmetry part of the "treatment" can excuse an
unfair advantage.

**Evidence:** `S001`, `S005`, `S009`.

**Preliminary disposition:** `REVISE_REQUIRED`

**Needed protection:**

The specification must distinguish opportunity parity, information parity,
evaluation parity, and resource regime from algorithmic implementation
differences.

### AF-004 — Tuning-Budget Asymmetry

**Targets:** `BR-006`, `BR-018`

**Attack:**

A candidate may receive extensive engineering, prompt search, retries, or
hyperparameter exploration while a comparator receives minimal effort.

Both can still appear to obey the same protected-data rule.

**Evidence:** `S005`, `S006`, `S017`.

**Preliminary disposition:** `REVISE_REQUIRED`

**Needed protection:**

Tuning opportunity and search effort must be predeclared sufficiently for the
comparison claim, while concrete resource accounting remains Task 9-owned.

### AF-005 — Evaluator Bias Can Manufacture A Winner

**Targets:** `BR-007`, `BR-010`, `BR-022`

**Attack:**

An LLM or human evaluator may systematically favor one candidate because of
position, verbosity, authority cues, formatting, style, or other irrelevant
features.

The comparison can therefore be reproducible and still wrong.

**Evidence:** `S023`, `S024`.

**Preliminary disposition:** `NEW_REQUIREMENT_GAP`

**Needed protection:**

Task 8 likely needs an explicit evaluator-validity requirement covering
identity, version, bias testing where material, order handling, calibration or
cross-checking, and limitation reporting.

### AF-006 — Evaluator Configuration Drift

**Targets:** `BR-001`, `BR-007`, `BR-022`

**Attack:**

The baseline and candidate may be stable while an external evaluator model,
prompt, scoring implementation, or provider behavior changes.

Historical rankings may then drift without either compared system changing.

**Evidence:** `S023`, `S024`, `S026`.

**Preliminary disposition:** `REVISE_REQUIRED`

**Needed protection:**

Evaluator identity and configuration must be treated as first-class
versioned comparison provenance.

### AF-007 — Adaptive Holdout Reuse Through Baseline Development

**Targets:** `BR-002`, `BR-003`, `BR-006`, `BR-019`

**Attack:**

A team repeatedly sees protected results, changes comparator definitions,
improves the baseline, reruns the evaluation, and eventually reports the best
comparison.

No single run necessarily violates its local rules, but the development
process has adapted to the protected evidence.

**Evidence:** `S022`.

**Preliminary disposition:** `TASK7_CROSS_REFERENCE_REQUIRED`

**Needed protection:**

Task 8 must explicitly inherit Task 7 protected-access, freshness, repeated
peeking, candidate-lineage, and invalidation semantics rather than creating a
second weaker holdout policy.

### AF-008 — Benchmark Portfolio Cherry Picking

**Targets:** `BR-011`

**Attack:**

Even with a fixed benchmark definition, a team can choose only favorable
benchmarks, task families, difficulty bands, or subsets.

**Evidence:** `S004`, `S025`.

**Preliminary disposition:** `REVISE_REQUIRED`

**Needed protection:**

The evaluation contract must preserve benchmark-selection and task-sampling
rules before protected outcomes and relate them to claim scope.

### AF-009 — Dynamic Benchmarks Do Not Automatically Solve Contamination

**Targets:** `BR-012`

**Attack:**

A dynamically generated benchmark may reduce direct memorization while
introducing weak construct validity, unstable difficulty, generator bias,
evaluation leakage, or poor reproducibility.

Calling a benchmark "dynamic" can therefore become false reassurance.

**Evidence:** `S014`, `S025`.

**Preliminary disposition:** `REVISE_REQUIRED`

**Needed protection:**

Dynamic evaluation must still satisfy construct, provenance, evaluator,
difficulty, and reproducibility requirements.

### AF-010 — Version Labels Without Behavioral Reproducibility

**Targets:** `BR-001`, `BR-007`, `BR-008`

**Attack:**

A hosted service may expose the same nominal model identifier while backend
behavior changes.

A version string alone can therefore provide false confidence.

**Evidence:** `S001`, `S008`, `S017`.

**Preliminary disposition:** `REVISE_REQUIRED`

**Needed protection:**

Where exact implementation pinning is unavailable, preserve provider metadata,
timestamps, material configuration, outputs, and behavioral/reproducibility
limitations.

### AF-011 — Optional Stopping Can Game Stochastic Replication

**Targets:** `BR-009`, `BR-010`

**Attack:**

Repeated runs can continue until the candidate happens to achieve a favorable
effect and then stop.

Uncertainty reporting does not repair a stopping rule selected after seeing
the outcomes.

**Evidence:** `S001`, `S007`.

**Preliminary disposition:** `REVISE_REQUIRED`

**Needed protection:**

Replication count or stopping rule must be predeclared whenever outcome-driven
stopping could affect the scientific conclusion.

### AF-012 — Metric Multiplicity Can Manufacture Significance

**Targets:** `BR-010`, `BR-013`

**Attack:**

A system can measure many outcomes, report the favorable subset, and preserve
hard constraints while still overstating evidence.

**Evidence:** `S001`, `S007`, `S009`.

**Preliminary disposition:** `REVISE_REQUIRED`

**Needed protection:**

Primary measures and applicable multiplicity or selective-reporting rules must
be predeclared where scientifically material.

Task 8 must not invent statistical corrections without regard to the Task 6
hypothesis contract.

### AF-013 — Trajectory Classification Can Become Post-Hoc Storytelling

**Targets:** `BR-014`

**Attack:**

After seeing outcomes, evaluators can create convenient trajectory categories
that explain candidate failures favorably and comparator failures
unfavorably.

**Evidence:** `S013`, `S023`, `S024`.

**Preliminary disposition:** `REVISE_REQUIRED`

**Needed protection:**

Material trajectory categories and classification rules should be defined
before protected interpretation when they affect the scientific conclusion.

### AF-014 — Target-Specific Engineering Masquerading As Transfer

**Targets:** `BR-015`

**Attack:**

The transferred system may contain manually engineered target-family
knowledge, target-specific prompts, retrieval assets, or onboarding effort
that produces gains without learned cross-family decision transfer.

**Evidence:** `S004`, `S005`, `S021`.

**Preliminary disposition:** `REVISE_REQUIRED`

**Needed protection:**

Target-specific engineering and information transfer must be separately
identified and governed.

### AF-015 — Weak Adaptation Comparator

**Targets:** `BR-016`

**Attack:**

Hetren's Adaptive method can appear superior if compared only against
no-adaptation and an obsolete or under-tuned adaptation method.

**Evidence:** `S005`, `S006`, `S015`.

**Preliminary disposition:** `REVISE_REQUIRED`

**Needed protection:**

The strongest-applicable-baseline rule must apply explicitly to adaptation
comparators, with preserved eligibility and tuning provenance.

### AF-016 — Rollback Command Success Is Not Rollback Evidence

**Targets:** `BR-017`

**Attack:**

A rollback command can return success while model state, external memory,
indexes, caches, policies, or behavior remain altered.

**Evidence:** `S015`, `S016`, `S017`.

**Preliminary disposition:** `REVISE_REQUIRED`

**Needed protection:**

Rollback evidence must verify the relevant restored state and protected
post-rollback behavior rather than only successful execution of a rollback
operation.

### AF-017 — Resource Regime Chosen After Results

**Targets:** `BR-018`

**Attack:**

A team can describe a comparison as strictly matched when that is favorable,
then switch to unconstrained performance-versus-cost reporting when strict
matching is unfavorable.

**Evidence:** `S001`, `S009`.

**Preliminary disposition:** `REVISE_REQUIRED`

**Needed protection:**

The applicable resource-comparison regime must be frozen before protected
outcomes are inspected.

Task 9 still owns the actual measurements.

### AF-018 — Ambiguous Baseline Supersession Trigger

**Targets:** `BR-019`

**Attack:**

"Materially stronger applicable baseline" can be interpreted selectively,
allowing inconvenient newer comparators to be ignored indefinitely.

**Evidence:** `S004`, `S005`, `S006`, `S025`.

**Preliminary disposition:** `REVISE_REQUIRED`

**Needed protection:**

The formal specification needs an explicit reevaluation trigger based on
baseline applicability and credible comparative evidence, without claiming
continuous knowledge of every method in existence.

### AF-019 — Claim Narrowing Can Become An Escape Hatch

**Targets:** `BR-020`

**Attack:**

When no strong comparator exists, a team can repeatedly narrow the claim until
a trivial favorable statement survives.

**Evidence:** `S001`, `S004`, `S025`.

**Preliminary disposition:** `REVISE_REQUIRED`

**Needed protection:**

Narrowed claims must preserve the original evidence gap and must not imply the
blocked broader superiority claim.

### AF-020 — Real-World Validity Can Become Unbounded Scope

**Targets:** `BR-021`

**Attack:**

A vague requirement for "real-world" evaluation can create endless testing,
subjective completion criteria, or accidental expansion of the MVP.

**Evidence:** `S001`, `S003`, `S025`.

**Preliminary disposition:** `REVISE_REQUIRED`

**Needed protection:**

Additional real-world evaluation must be triggered by the exact claim being
made and its deployment assumptions, not by a universal requirement to test
everything in production.

### AF-021 — Nominally Independent Verification

**Targets:** `BR-022`

**Attack:**

A second script can be called "independent" while sharing the same evaluator,
assumptions, aggregation logic, data transformation, and implementation defect.

**Evidence:** `S003`, `S008`, `S023`.

**Preliminary disposition:** `REVISE_REQUIRED`

**Needed protection:**

The formal contract must define sufficient separation dimensions for the
consequence of the claim and require explicit shared-dependency disclosure.

### AF-022 — Evaluation Artifact Mistaken For Model Difference

**Targets:** `BR-005`, `BR-007`, `BR-010`, `BR-022`

**Attack:**

Rigid answer parsing, grader prompt design, ordering, formatting assumptions,
or evaluation code can create an apparent candidate-versus-baseline gap that
does not correspond to the intended construct.

**Evidence:** `S023`, `S024`, `S026`.

**Preliminary disposition:** `NEW_REQUIREMENT_GAP`

**Needed protection:**

Task 8 likely needs explicit evaluator validation and evaluation-artifact
controls before a measured difference can support a consequential comparison.

### AF-023 — Simple Anchor Can Become A Strawman Or Narrative Substitute

**Targets:** `BR-004`

**Attack:**

A simple, deterministic, non-learned, or no-learning anchor can be useful for
diagnosis while still being much weaker than a realistic comparator.

A team can exploit that distinction by prominently reporting improvement over
the simple anchor even when the candidate fails to outperform the strongest
applicable matched comparator.

The anchor can also be weakened through poor configuration, insufficient
tuning, obsolete implementation, or an artificially restrictive resource
condition.

**Evidence:** `S004`, `S005`, `S006`.

**Preliminary disposition:** `REVISE_REQUIRED`

**Needed protection:**

The formal Task 8 contract should distinguish explicitly between:

- diagnostic anchors;
- claim-bearing matched comparators;
- strongest-applicable comparators required by a governed hypothesis.

A diagnostic anchor must not satisfy a strongest-baseline requirement.

Failure against the strongest applicable comparator must not be obscured by a
favorable result against the diagnostic anchor.

Where a simple anchor is used, its implementation and configuration must still
be scientifically credible for the role it is intended to play.

## 16. Adversarial Review Interim Conclusion

The first attack pass does not justify promoting the 22 candidate requirements
unchanged.

The current research indicates:

- several requirements are directionally sound but under-specified;
- evaluator validity is not yet sufficiently explicit;
- adaptive reuse of protected evidence must remain governed by Task 7 rather
  than duplicated weakly in Task 8;
- benchmark validity extends beyond contamination;
- reproducibility cannot be reduced to version strings;
- stochastic replication needs protection against optional stopping;
- transfer and adaptation controls require stronger anti-gaming language;
- rollback requires state and behavioral verification;
- resource-regime selection must occur before protected outcomes;
- independent verification requires substantive rather than nominal
  separation.

The next research step must therefore revise or add candidate requirements
before any Task 8 governing specification is drafted.

No scientific support for `N-H1`, `N-H2`, `A-H1`, or `A-H2` is established by
this review.

## 17. Phase 8E Remediation Design

The first adversarial pass is now mapped into a machine-readable remediation
artifact:

`docs/research/baselines/task-08-remediation-map.json`

The remediation map is research-only.

It does not modify the original `BR-001` through `BR-022` candidate history.

It does not accept Generation 2 requirements.

It does not create Task 8 governing authority.

Each adversarial finding receives exactly one primary remediation action from:

- `KEEP`;
- `REVISE`;
- `SPLIT`;
- `ADD`;
- `DEFER`;
- `REJECT`.

`KEEP` does not mean that a requirement is scientifically proven or accepted.
It means the associated attack is already substantively handled by the
current candidate semantics and does not presently justify a semantic change.

`REVISE` means Generation 2 should preserve the core intent while closing an
identified loophole or ambiguity.

`SPLIT` means one candidate currently combines concerns that need independent
semantics.

`ADD` means the adversarial review exposed a requirement class not represented
adequately by the original candidate set.

`DEFER` means the issue is valid but belongs to a later governed owner.

`REJECT` means the proposed attack or remediation is not justified after
review.

AF-005 and AF-022 intentionally converge on one planned Generation 2 concept:

`evaluation.evaluator-validity`

This prevents evaluator bias and evaluation-artifact controls from becoming
duplicated competing requirements.

Task 7 remains authoritative for protected-evidence lifecycle, freshness,
access, repeated peeking, lineage, and invalidation.

Task 9 remains authoritative for concrete cost, compute, token, time, monetary,
memory, API-use, and human-effort accounting definitions and values.

Phase 8E still establishes no scientific support for `N-H1`, `N-H2`, `A-H1`,
or `A-H2`.

## 18. Generation 2 Red-Team Source Addendum

These sources were added after Generation 2 was created.

They are used to challenge Generation 2 rather than retroactively pretending
they informed the original candidate set.

### S027 — LLM Evaluators Recognize And Favor Their Own Generations

**Authors:** Arjun Panickssery, Samuel R. Bowman, Shi Feng
**Venue:** NeurIPS
**Year:** 2024
**Evidence role:** `SCIENTIFIC_EVIDENCE`

Relevant themes:

- an LLM evaluator can exhibit self-preference;
- evaluator self-recognition correlates with self-preference;
- the evaluator and evaluatee are not automatically independent;
- same-family or self-evaluation may create a comparison confound.

Task 8 relevance:

Evaluator identity alone is insufficient when evaluator relationship to the
candidate or baseline can systematically affect scoring.

### S028 — Evaluation And Benchmarking Of LLM Agents: A Survey

**Authors:** Mahmoud Mohammadi, Yipeng Li, Jane Lo, Wendy Yip
**Venue:** KDD
**Year:** 2025
**Evidence role:** `SCIENTIFIC_EVIDENCE`

Relevant themes:

- agent evaluation includes behavior, capability, reliability, and safety;
- interaction mode and tooling are part of evaluation design;
- enterprise agent evaluation includes role-based data access;
- dynamic and long-horizon interactions create evaluation challenges;
- realistic evaluation differs from isolated model scoring.

Task 8 relevance:

Tool access, permissions, environment dynamics, interaction horizons, and
observable behavior can materially affect candidate-versus-baseline fairness.

### S029 — AntiLeakBench

**Title:** AntiLeakBench: Preventing Data Contamination by Automatically
Constructing Benchmarks with Updated Real-World Knowledge
**Venue:** ACL
**Year:** 2025
**Evidence role:** `SCIENTIFIC_EVIDENCE`

Relevant themes:

- newly collected data is not automatically contamination-free;
- updated benchmarks can still contain pre-existing knowledge;
- contamination mitigation requires explicit construction and reasoning;
- benchmark freshness and benchmark cleanliness are different claims.

Task 8 relevance:

A dynamic, refreshed, or recently created benchmark must not automatically be
classified as uncontaminated.

### S030 — Continual Learning: A Systematic Literature Review

**Authors:** Qinwen Yang, Liyuan Wang, Joerg Wicker, Gillian Dobbie
**Journal:** Neural Networks
**Article date:** October 20, 2025
**Volume publication:** March 2026
**Evidence role:** `SCIENTIFIC_EVIDENCE`

Relevant themes:

- catastrophic forgetting remains a central continual-learning challenge;
- stability and plasticity are distinct concerns;
- overall performance alone is insufficient to characterize continual
  learning;
- learning setting and evaluation protocol materially affect interpretation.

Task 8 relevance:

Adaptive comparisons must not allow target gains to hide retention or
stability failures.

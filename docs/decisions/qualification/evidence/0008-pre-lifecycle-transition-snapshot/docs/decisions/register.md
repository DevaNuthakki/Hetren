# Hetren Decision Register

**Version:** 1.6.0
**Status:** Active
**MVP Task:** 2 / 100
**Governing execution authority:** `AUTH-HETREN-MVP-3.0`
**Long-term authority:** `AUTH-HETREN-MASTER-2.0`
**Governing charter:** Hetren MVP Charter v1.1.0

---

## 1. Purpose

This register is the shared source of truth for material Hetren engineering,
product, research-governance, evaluation, security, data, operational,
integration, and scientific-change decisions.

It exists to prevent silent architectural change, conflicting active
decisions, untraceable reversals, protected-evaluation drift, and research
hypotheses being treated as established facts.

The register is not a task tracker, research-result store, experiment log, or
substitute for qualification evidence.

## 2. Canonical Authority References

Current decision records use the unified authority identifiers below.

| Authority ID | Authority |
|---|---|
| `AUTH-HETREN-MASTER-2.0` | Hetren Unified Product, Intelligence, and Adaptive Research Master Specification v2.0 |
| `AUTH-HETREN-MVP-3.0` | Hetren Unified MVP and Adaptive Intelligence Execution Plan v3.0 |

Earlier Product v1.4, MVP v2.0, Neural Intelligence Research v1.0, Adaptive
Intelligence v1.0, and Charter v1.0.0 identifiers remain historical source
lineage.

They must not be used as current authority metadata for new or normalized
active decisions.

## 3. Decision Lifecycle

Valid statuses are:

- `PROPOSED` — under review and not authoritative;
- `ACCEPTED` — currently authoritative within its declared scope;
- `SUPERSEDED` — replaced by another accepted decision;
- `REJECTED` — considered and explicitly not adopted;
- `RETIRED` — intentionally no longer applicable without a replacement.

Only an `ACCEPTED` decision governs active implementation.

An accepted decision may not be semantically rewritten in place. A material
change requires a new decision record and explicit supersession.

## 4. Decision Classes

The initial classes are:

- `ARCHITECTURE`
- `PRODUCT`
- `GOVERNANCE`
- `RESEARCH_GOVERNANCE`
- `EVALUATION`
- `SECURITY`
- `DATA`
- `OPERATIONS`
- `INTEGRATION`

Decision Class and Research Change Category are separate concepts.

A research decision may still be an architecture, evaluation, data, or
governance decision while also declaring its scientific-change category.

## 5. Research Decision Metadata

Every decision declares a Research Program.

Valid values are:

- `NONE`
- `NATIVE`
- `ADAPTIVE`
- `CROSS_PROGRAM`

Every decision also declares a Research Change Category.

Valid values are:

- `NONE`
- `THESIS`
- `METRIC`
- `DATA`
- `BASELINE`
- `MODEL`
- `ALGORITHM`
- `BUG`
- `INFRA`

A non-research decision uses:

- Research Program: `NONE`;
- Research Change Category: `NONE`;
- Evidence Consequence: `NONE`.

A research decision must not use `NONE` for its Research Program or Research
Change Category.

The required evidence consequence for each scientific-change category is:

| Category | Required Evidence Consequence |
|---|---|
| `THESIS` | `NEW_PROGRAM_VERSION_AND_RERUN` |
| `METRIC` | `RERUN_AFFECTED_QUALIFICATION` |
| `DATA` | `RERUN_AND_PRESERVE_DATA_DISTINCTIONS` |
| `BASELINE` | `RECOMPARE_STRONGEST_RESULT` |
| `MODEL` | `NEW_REPLICATION_RESULT` |
| `ALGORITHM` | `NEW_METHOD_VERSION_AND_PREREGISTRATION` |
| `BUG` | `INVALIDATE_AFFECTED_RESULTS_AND_RERUN` |
| `INFRA` | `SMOKE_AND_REGRESSION_RERUN_IF_NUMERICAL_CHANGE` |

These consequences are minimum governance requirements. A decision may require
stronger qualification when the affected claim warrants it.

## 6. Required Decision Metadata

Every governed decision record must declare:

- Decision ID;
- Decision Key;
- Title;
- Status;
- Class;
- Date;
- Authority;
- Scope;
- Research Program;
- Research Change Category;
- Evidence Consequence;
- Supersedes;
- Superseded By;
- Reversibility;
- Qualification requirement.

## 7. Consistency Rules

1. Every Decision ID is globally unique.
2. Every Decision Key identifies one stable decision scope.
3. At most one `ACCEPTED` decision may govern the same Decision Key.
4. Supersession must be explicit in both the replacing and replaced records.
5. A successor and predecessor in a supersession chain must use the same Decision Key.
6. A `PROPOSED` decision is never implementation authority.
7. A decision may constrain implementation but may not manufacture evidence.
8. A research hypothesis may be governed by a decision but may not become a scientific fact merely because the decision is accepted.
9. Protected metrics, data, thresholds, qualification criteria, and evaluators must be declared before the governed protected result is inspected.
10. Material protected-evaluation changes after results are observed require a new versioned decision and the evidence consequence required by the scientific-change category.
11. Scientific results invalidated by a `BUG`, data defect, evaluator defect, leakage finding, or other qualifying fault remain preserved as invalidated history.
12. Research Program, Research Change Category, and Evidence Consequence must agree.
13. Implementation divergence from an accepted decision must be resolved by correcting the implementation or creating a new decision.
14. Accepted and superseded records must not be deleted to hide history.
15. Material decisions require preserved qualification, implementation, and verification evidence appropriate to the claim they govern.
16. Product qualification, Native Intelligence research status, and Adaptive Intelligence scientific status remain separately reportable.

## 8. Required Decision Content

A governed decision must explain:

- the context or trigger;
- the decision;
- alternatives considered;
- evidence and rationale;
- assumptions;
- accepted consequences;
- known risks and constraints;
- reversibility or rollback path;
- affected contracts and components;
- research impact;
- qualification requirements;
- implementation evidence;
- verification evidence;
- supersession relationships.

Unknown evidence must be recorded as unknown or pending rather than invented.

An `ACCEPTED` decision may not retain pending qualification, implementation,
or verification evidence unless its qualification contract explicitly defines
that evidence as not applicable and provides the reason.

## 9. Decision Register

| ID | Decision Key | Title | Status | Class | Authority | Record |
|---|---|---|---|---|---|---|
| `0001` | `repository.active-foundation` | Reset the active repository for MVP v2 | `ACCEPTED` | `ARCHITECTURE` | `AUTH-HETREN-MVP-3.0` | `0001-reset-active-repository.md` |
| `0002` | `governance.decision-system` | Establish governed decision records | `ACCEPTED` | `GOVERNANCE` | `AUTH-HETREN-MVP-3.0` | `0002-decision-governance.md` |
| `0003` | `evaluation.success-contracts` | Define shared success-contract semantics | `ACCEPTED` | `EVALUATION` | `AUTH-HETREN-MVP-3.0` | `0003-success-contracts.md` |
| `0004` | `architecture.system-taxonomy` | Define governed MVP system taxonomy | `ACCEPTED` | `ARCHITECTURE` | `AUTH-HETREN-MVP-3.0` | `0004-system-taxonomy.md` |
| `0005` | `product.mvp-support-matrix` | Freeze the initial MVP capability-support matrix | `ACCEPTED` | `PRODUCT` | `AUTH-HETREN-MVP-3.0` | `0005-mvp-support-matrix.md` |
| `0006` | `research.native-intelligence.mvp-hypotheses` | Govern initial Native Intelligence MVP hypotheses | `ACCEPTED` | `RESEARCH_GOVERNANCE` | `AUTH-HETREN-MVP-3.0` | `0006-native-intelligence-mvp-hypotheses.md` |
| `0007` | `research.adaptive-intelligence.mvp-hypotheses` | Govern initial Adaptive Intelligence MVP hypotheses | `ACCEPTED` | `RESEARCH_GOVERNANCE` | `AUTH-HETREN-MVP-3.0` | `0007-adaptive-intelligence-mvp-hypotheses.md` |
| `0008` | `research.evaluation.initial-splits` | Govern the initial MVP split protocol | `PROPOSED` | `DATA` | `AUTH-HETREN-MVP-3.0` | `0008-initial-split-protocol.md` |

---

Decision 0002 is the accepted governance authority for decision records
within its declared scope.

Decision 0001 retains its historical origin and acceptance, while its active
authority metadata is normalized to the current unified execution authority.

This normalization does not rewrite the historical reason the decision was
originally taken.

# Decision 0003: Define shared success-contract semantics

**Decision ID:** `0003`
**Decision Key:** `evaluation.success-contracts`
**Title:** `Define shared success-contract semantics`
**Status:** `ACCEPTED`
**Class:** `EVALUATION`
**Date:** `2026-09-17`
**Authority:** `AUTH-HETREN-MVP-3.0`
**Scope:** `Shared success, failure, evidence-validity, constraint, uncertainty, and verification semantics for MVP evaluation`
**Research Program:** `NONE`
**Research Change Category:** `NONE`
**Evidence Consequence:** `NONE`
**Supersedes:** `None`
**Superseded By:** `None`
**Reversibility:** `CONDITIONALLY_REVERSIBLE`
**Qualification:** `Task 3 success-contract qualification`

---

## Context And Trigger

The MVP Charter requires observable pass/fail criteria, preserved evidence,
predeclared protected success criteria, independent verification, explicit
constraints, meaningful baselines, and separately reportable product and
research status.

The canonical record model already includes `GoalContract`,
`EvaluationRecord`, and `VerificationReport`, but the repository does not yet
define one shared semantic contract for deciding when evidence supports a
claim of success, improvement, repair, failure, uncertainty, or invalidity.

Without shared semantics, individual environments could silently use different
definitions of improvement or success and create results that appear
comparable while meaning different things.

## Decision

Define one shared success-contract model for the MVP.

The model is expressed as normative semantics around the existing
`GoalContract`, `EvaluationRecord`, and `VerificationReport`.

Task 3 does not introduce a competing `SuccessContract` runtime record.

A governed `GoalContract` must declare enough information to determine:

- the objective and bounded claim;
- the required baseline or reference condition;
- measurable acceptance predicates;
- hard constraints and invariants;
- applicable budget constraints;
- evidence requirements;
- protected-evaluation requirements;
- uncertainty and abstention behavior;
- failure and invalidity behavior;
- independent-verification requirements.

Evaluation outcomes use the shared states:

`PASS`, `FAIL`, `INCONCLUSIVE`, `BLOCKED`, and `INVALID`.

A `PASS` is conjunctive. A gain in one measure cannot compensate for failure
of a hard constraint, invariant, evidence-integrity requirement, or mandatory
verification requirement.

Product success, Native Intelligence research success, and Adaptive
Intelligence scientific success remain independently reportable.

## Alternatives Considered

### Introduce a separate SuccessContract runtime record

Rejected for Task 3 because `GoalContract` is already part of the canonical
shared record model. A second overlapping contract would create unnecessary
authority and implementation ambiguity before evidence demonstrates that a
separate runtime object is needed.

### Let every environment define success independently

Rejected because E1 agent, E2 structured-data ML, and E3 vision must be
qualified through the same Core and shared evidence semantics.

Environment-specific measures may differ, but the meaning of baseline,
constraint, evidence validity, verification, and outcome state must not.

### Use one weighted overall success score

Rejected because a weighted score could hide safety, reliability, integrity,
rollback, or other hard-constraint failures behind gains in unrelated metrics.

## Evidence And Rationale

The current MVP authority already requires:

- explicit objectives and constraints;
- regression repair and constrained improvement;
- evidence provenance and integrity;
- meaningful baselines;
- protected success criteria;
- independent verification;
- regression preservation;
- honest uncertainty and failure reporting;
- separate product and research status.

Task 3 makes those requirements operationally consistent without selecting the
concrete datasets, numerical thresholds, baselines, or system taxonomy that
belong to later MVP tasks.

## Assumptions

- `GoalContract` remains the canonical declaration of intended outcome.
- `EvaluationRecord` remains the canonical record of measured evaluation.
- `VerificationReport` remains the canonical record of independent or
  authority-separated verification.
- Environment-specific metrics may differ while sharing the same success
  semantics.
- Later MVP tasks will supply concrete system taxonomy, support boundaries,
  hypotheses, evaluation splits, baselines, and cost ledgers.

## Consequences

Future implementations must distinguish:

- valid negative evidence from invalid evidence;
- a measured failure from inability to execute an evaluation;
- insufficient evidence from demonstrated failure;
- product success from Native Intelligence research success;
- product success from Adaptive Intelligence scientific success;
- improvement of a primary measure from valid constrained improvement.

Claims of improvement become stricter but more auditable.

## Risks And Constraints

An overly rigid contract could make legitimate environment-specific evaluation
difficult.

An overly permissive contract could allow inconsistent definitions of success.

Task 3 therefore standardizes semantic requirements while deliberately leaving
concrete metrics, thresholds, datasets, and baseline identities to the later
tasks that govern those artifacts.

## Reversibility And Rollback

These semantics may be changed only through governed decision revision.

Material changes to protected criteria, metrics, data, baselines, algorithms,
or research theses must additionally follow the scientific-change governance
defined by Decision 0002 when applicable.

Historical evaluations retain the contract version under which they were
performed.

## Affected Contracts And Components

- `GoalContract`
- `EvaluationRecord`
- `VerificationReport`
- future evaluator contracts
- protected evaluation
- release qualification
- regression qualification
- E1 agent evaluation
- E2 structured-data ML evaluation
- E3 vision evaluation
- Native Intelligence research qualification
- Adaptive Intelligence research qualification

## Research Impact

This is a shared evaluation-governance decision rather than a change to a
scientific hypothesis, metric result, dataset, model, or algorithm.

Its Research Program, Research Change Category, and Evidence Consequence are
therefore `NONE`.

The resulting semantics constrain how future Native Intelligence and Adaptive
Intelligence evidence may support claims without establishing either research
program's scientific outcome.

## Qualification Requirement

Before this decision becomes `ACCEPTED`, Task 3 qualification must demonstrate
that the success-contract specification:

- preserves the canonical `GoalContract`, `EvaluationRecord`, and
  `VerificationReport` responsibilities;
- keeps product, Native Intelligence, and Adaptive Intelligence verdicts
  separate;
- defines exact shared evaluation outcome states;
- prevents invalid evidence from producing `PASS`;
- prevents authority-required contract elements from being omitted to
  manufacture `PASS`;
- defines consequential claims sufficiently to prevent verification requirements
  from being bypassed by relabeling;
- defines deterministic outcome resolution when failure, invalidity, blockage,
  or inconclusive evidence coexist;
- keeps unsupported, negative, and falsifying characterizations distinct from
  the exact evaluation-outcome vocabulary;
- prevents hard-constraint or invariant failure from being averaged away;
- distinguishes `FAIL`, `INCONCLUSIVE`, `BLOCKED`, and `INVALID`;
- requires baseline identity for comparison claims;
- requires protected criteria to be frozen before protected evaluation;
- requires versioned governance and requalification when protected criteria
  materially change;
- requires independent verification for consequential success claims;
- covers regression repair and constrained improvement;
- applies consistently to E1, E2, and E3;
- avoids prematurely selecting Task 4-9 concrete artifacts.

The specification and validator must also survive adversarial mutation testing.

## Implementation Evidence

Implemented and preserved in:

- `docs/mvp/03-success-contracts.md`;
- `scripts/check_success_contracts.py`;
- `tests/qualification/test_success_contracts.py`.

## Verification Evidence

Verified by `docs/decisions/qualification/0003-success-contracts.md` with structural, semantic, adversarial, mutation, authority, regression, and accepted-state qualification.

## Supersession

This decision supersedes no prior governed decision and is not currently
superseded.

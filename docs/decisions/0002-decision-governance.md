# Decision 0002: Establish governed decision records

**Decision ID:** `0002`
**Decision Key:** `governance.decision-system`
**Title:** `Establish governed decision records`
**Status:** `ACCEPTED`
**Class:** `GOVERNANCE`
**Date:** `2026-09-16`
**Authority:** `AUTH-HETREN-MVP-3.0`
**Scope:** `Material shared Hetren decisions recorded under docs/decisions/`
**Research Program:** `NONE`
**Research Change Category:** `NONE`
**Evidence Consequence:** `NONE`
**Supersedes:** `None`
**Superseded By:** `None`
**Reversibility:** `CONDITIONALLY_REVERSIBLE`
**Qualification:** `Task 2 decision-governance qualification`

---

## Context And Trigger

The qualified MVP Charter requires explicit decision records for material
changes and prohibits experimental results from silently redefining success
criteria.

The repository already contains Decision 0001, but no shared lifecycle,
authority vocabulary, supersession model, consistency contract, or automated
validation mechanism currently governs decision records.

## Decision

Adopt a governed decision system consisting of:

- a canonical decision register;
- one durable record for each material decision;
- a common decision template;
- stable authority identifiers;
- explicit status and supersession semantics;
- machine-checkable consistency rules;
- preserved qualification and verification references.

Only accepted decisions govern active implementation within their declared
scope.

## Alternatives Considered

### Unregistered standalone ADR files

Rejected because conflicting or superseded decisions would require manual
discovery and could remain simultaneously active.

### Use the MVP task ledger as the decision authority

Rejected because task status and architectural authority are different
concerns. The private build ledger is not a shared decision contract.

### Maintain one mutable decisions document

Rejected because rewriting prior decisions would weaken historical traceability
and make supersession difficult to audit.

## Evidence And Rationale

The MVP Charter explicitly requires decision records for material charter
changes and requires evidence, qualification, and preserved history for
consequential claims.

Decision 0001 demonstrates that durable architectural decisions already exist.
The governance system adds lifecycle and consistency controls without changing
the substantive authority of that existing decision.

A decision record establishes engineering authority within scope. It does not
establish scientific truth merely by being accepted.

## Assumptions

- Git history remains available as an audit mechanism.
- Material shared decisions belong in the shared repository.
- Personal task tracking remains separate from decision authority.
- Not every trivial implementation choice requires a governed decision.

## Consequences

- Material changes receive durable IDs and reviewable records.
- Superseded decisions remain historically visible.
- Contributors incur modest documentation and review overhead.
- Pull requests can validate decision consistency automatically.

## Risks And Constraints

- A validator can enforce structure but cannot prove that reasoning is sound.
- Excessive decision creation could turn governance into ceremony.
- Missing material decisions could still bypass the system through human error.
- Metadata and prose can drift unless cross-checked automatically.

Governance therefore applies to material decisions, while review remains
responsible for semantic quality.

## Reversibility And Rollback

This governance mechanism may be replaced only through a new accepted decision
that explicitly supersedes Decision 0002.

Existing accepted and superseded records remain preserved even if the mechanism
is later replaced.

## Affected Contracts And Components

- `docs/decisions/register.md`
- `docs/decisions/template.md`
- governed files under `docs/decisions/`
- repository decision-validation tooling
- future CI decision-integrity checks
- contributor review workflow for material changes

No product runtime behavior is changed by this decision alone.

## Research Impact

This decision governs decision-making used by both Native Intelligence and
Adaptive Intelligence, but it is not itself a scientific-change decision.

Its Research Program, Research Change Category, and Evidence Consequence are
therefore `NONE`.

Scientific decisions created under this governance must identify their
applicable research program, scientific-change category, and required evidence
consequence.

## Qualification Requirement

Before this decision becomes `ACCEPTED`, qualification must demonstrate that
the decision system detects at least:

- duplicate Decision IDs;
- duplicate decision-record references;
- conflicting accepted Decision Keys;
- unknown statuses, classes, or current authorities;
- missing decision records;
- register-to-record metadata mismatch;
- heading, title, and filename identity mismatch;
- missing required metadata or sections;
- invalid calendar dates;
- invalid Decision Keys or reversibility values;
- invalid Research Program values;
- invalid Research Change Category values;
- mismatched Research Program, Research Change Category, and Evidence
  Consequence combinations;
- scientific-change categories with the wrong required evidence consequence;
- invalid or asymmetric supersession relationships;
- supersession across different Decision Keys;
- accepted records with pending or absent qualification evidence;
- accepted records with pending implementation evidence unless explicitly
  qualified as not applicable;
- accepted records with pending verification evidence;
- unregistered governed decision files;
- resurrection of superseded historical authority identifiers as current
  authority metadata.

Qualification must also demonstrate that:

- `THESIS`, `METRIC`, `DATA`, `BASELINE`, `MODEL`, `ALGORITHM`, `BUG`, and
  `INFRA` map to their declared minimum evidence consequences;
- protected-evaluation changes cannot silently preserve prior qualification;
- invalidated scientific results remain preserved as history;
- positive valid engineering and research-governance records pass without
  false rejection.

## Implementation Evidence

Task 2 implementation currently consists of:

- `docs/decisions/register.md` — canonical decision register and governance
  contract;
- `docs/decisions/template.md` — canonical decision-record template;
- `docs/decisions/0001-reset-active-repository.md` — historical Decision 0001
  normalized under unified authority without rewriting its original rationale;
- `docs/decisions/0002-decision-governance.md` — governance decision and
  qualification contract;
- `scripts/check_decision_register.py` — executable governance validator;
- `tests/qualification/test_decision_register.py` — adversarial and positive
  qualification suite.

The implementation enforces current unified authorities, decision identity,
lifecycle, supersession, evidence requirements, research-program attribution,
scientific-change categories, and category-specific evidence consequences.

## Verification Evidence

Task 2 verification completed on 2026-09-17.

Observed results:

- Python compile: PASS;
- positive decision-register validation: PASS;
- valid Native `THESIS`, `METRIC`, `DATA`, `BASELINE`, `MODEL`, `ALGORITHM`,
  `BUG`, and `INFRA` category/consequence combinations: PASS;
- valid Adaptive research decision: PASS;
- valid cross-program research decision: PASS;
- adversarial mutation qualification: PASS, 44 / 44 mutations rejected;
- impossible calendar-date rejection: PASS;
- supersession same-key enforcement: PASS;
- current-authority enforcement: PASS;
- template-contract enforcement: PASS;
- accepted-evidence enforcement: PASS;
- scientific consequence-map synchronization: PASS;
- `git diff --check`: PASS.

The validator and mutation suite remain executable repository artifacts and
must continue to pass after Decision 0002 is promoted to `ACCEPTED`.

## Supersession

This decision supersedes no prior governance decision.

If replaced, both this record and its successor must identify the relationship.

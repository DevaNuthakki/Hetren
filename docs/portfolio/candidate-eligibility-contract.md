# Candidate eligibility contract — P07.6F

Date: 2026-10-06.
Scope: Hetren's tool-using AI-agent portfolio project.
Status: implementation candidate; validation required before checkpoint.

## Purpose

CandidateEligibilityDecision preserves a reviewer-reported policy decision for
one exact candidate SystemSnapshot.

It consumes a frozen GoalContract, the candidate SystemSnapshot and an already
produced VerificationReport.

It does not execute policy, resolve external references, grant authorization,
approve deployment, promote a candidate, mutate lifecycle state, or mark
Hetren complete.

Historical startup/MVP documents do not expand this increment's scope.

## Why this layer exists

ExecutionRecord validates execution lineage but explicitly does not make a
candidate eligible.

VerificationReport records independent verification but explicitly does not
authorize a repair.

GoalContract already freezes eligible changes, hard constraints, invariants,
budget constraints, reviewer_version, evidence requirements and verification
requirements.

Candidate eligibility is therefore a separate governed decision.

## Outcomes

CandidateEligibilityOutcome has five states:

- ELIGIBLE: policy reports that the candidate may proceed to a later governed
  authority/action layer.
- INELIGIBLE: policy reports that the candidate does not satisfy the applicable
  eligibility requirements.
- INCONCLUSIVE: available policy evidence cannot settle eligibility.
- BLOCKED: required policy review could not complete.
- INVALID: material policy inputs or protocol cannot support the decision.

ELIGIBLE, INELIGIBLE and INCONCLUSIVE require evidence references.

BLOCKED and INVALID may lack usable evidence.

Every decision requires rationale and uncertainty.

## Verification relationship

ELIGIBLE requires a VerificationReport whose outcome is VERIFIED.

The reverse implication does not exist.

A candidate may be independently VERIFIED and still be INELIGIBLE because it
violates an eligible-change rule, hard constraint, budget, capability
prerequisite, compatibility condition, reviewer policy, or another governed
requirement.

No automatic mapping is imposed for non-ELIGIBLE outcomes.

## Policy inputs

policy_input_references are opaque provenance references.

They may point to material such as:

- a candidate change manifest,
- a CapabilityProfile,
- capability qualification evidence,
- a gateway-policy result,
- compatibility evidence,
- budget evidence,
- reviewer records,
- another governed policy input.

P07.6F does not open or interpret those references.

CapabilityProfile.authorization_prerequisites remain prerequisites, not
authorization grants.

## Reviewer binding

GoalContract already freezes reviewer_version.

CandidateEligibilityDecision therefore records reviewer_id and reviewer_version
and validates the supplied reviewer_version against the frozen GoalContract.

The contract does not authenticate the reviewer or prove that policy execution
was correct.

## Link validation

CandidateEligibilityDecision.validate_against checks:

- supplied object types,
- tenant/project scope,
- frozen GoalContract ID and digest,
- exact candidate SystemSnapshot ID and digest,
- VerificationReport ID and digest,
- VerificationReport goal binding,
- VerificationReport candidate binding,
- goal/snapshot system identity,
- reviewer_version frozen by GoalContract,
- ELIGIBLE has a VERIFIED VerificationReport.

VerificationReport.validate_against remains responsible for the deeper
execution/evaluation verification lineage.

CandidateEligibilityDecision deliberately does not duplicate that work.

## Authority boundary

ELIGIBLE means policy eligibility only.

It does not mean:

- authorized,
- approved,
- executable,
- deployable,
- promoted,
- rolled out,
- complete.

The record contains no authorization, approval, execution-authority,
deployment-authority, promotion-authority, lifecycle-state or completion field.

A later authority/action layer may consume an ELIGIBLE decision. P07.6F does
not implement that layer.

## Integrity limits

Canonical payloads include record type and schema version 1.

eligibility_sha256 fingerprints record content. It does not authenticate a
reviewer, prove evidence truth, prove policy correctness, or make storage
immutable.

Frozen dataclasses prevent ordinary field assignment but are not a security
boundary against arbitrary Python code.

## Acceptance checks

Before checkpointing P07.6F:

- prior contract implementations and tests remain unchanged except package
  export wiring,
- valid eligible lineage validates,
- ELIGIBLE requires VERIFIED verification,
- VERIFIED verification can still produce INELIGIBLE,
- stale goal, snapshot and verification digests are rejected,
- reviewer-version mismatch is rejected,
- cross-scope records are rejected,
- measured outcomes require evidence,
- BLOCKED and INVALID remain representable without invented evidence,
- malformed fields and mutable collections are rejected,
- deterministic hashes track material changes,
- policy operations perform no file/process/network I/O,
- no authorization, execution, deployment or lifecycle authority is introduced,
- focused tests pass,
- complete unit regression passes.

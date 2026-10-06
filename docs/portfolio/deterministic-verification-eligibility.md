# Deterministic verification and eligibility — P07.7C

Date: 2026-10-06.
Scope: Hetren's tool-using AI-agent portfolio project.
Status: implementation candidate; validation required before checkpoint.

## Purpose

P07.7C extends the executable portfolio slice from ordinary candidate
evaluation through a separate verification rerun and a separate candidate
eligibility decision.

It reuses the existing:

- ExecutionRecord,
- EvaluationRecord,
- VerificationReport,
- CandidateEligibilityDecision.

No new authorization or lifecycle contract is introduced.

## Source prerequisite

Verification consumes a P07.7B result only after:

    source ExecutionRecord = COMPLETED
    source EvaluationRecord = PASS

A source FAIL cannot enter the verification runner.

## Separate verification execution

The exact same candidate SystemSnapshot and MethodProposal are reused.

The candidate behavior is actually executed again with:

- a distinct run ID,
- a distinct ExecutionRecord,
- a distinct runner identity,
- a distinct execution-manifest reference,
- a new trace,
- new execution evidence.

The verification execution is not a copy of the source record.

## Separate verification evaluation

The rerun is evaluated after execution using a separate evaluator path.

It has:

- a distinct EvaluationRecord,
- a distinct evaluator identity,
- a distinct protocol reference,
- measurements calculated from the verification run itself.

For this deterministic fixture:

    output 12 -> PASS

The resulting VerificationReport maps that actual verification evaluation to:

    PASS -> VERIFIED

## Independence boundary

P07.7C demonstrates procedural separation.

It does not claim that separate record IDs, runner IDs, evaluator IDs or
references prove:

- organizational independence,
- infrastructure independence,
- host isolation,
- data independence,
- personnel independence.

Both runs still occur in the same local Python process against the same
deterministic fixture implementation.

VerificationReport.independence_references preserve provenance supporting the
procedural-separation claim only.

## Eligibility policy

After verification, one separate deterministic policy is applied.

The policy requires:

1. the candidate has a VERIFIED VerificationReport, and
2. every candidate component identity appears in the current supplied
   permitted-component policy input.

The policy input is hashed and referenced in CandidateEligibilityDecision.

## VERIFIED does not imply ELIGIBLE

A negative policy control deliberately uses the same VERIFIED candidate while
changing only the current permitted-component input.

Therefore:

    same candidate
    same source PASS
    same verification rerun
    same VerificationReport(VERIFIED)

can produce:

    CandidateEligibilityDecision(INELIGIBLE)

when the current policy does not permit the candidate component.

This demonstrates that verification and policy eligibility are separate
claims.

## Authority boundary

P07.7C preserves:

    source PASS
        != VERIFIED

    VERIFIED
        != ELIGIBLE

    ELIGIBLE
        != authorized

    ELIGIBLE
        != approved

    ELIGIBLE
        != deployable

    ELIGIBLE
        != lifecycle COMPLETE

No action gateway, deployment operation, promotion operation or production
authorization is created.

## End-to-end executable chain

The portfolio slice now demonstrates:

    failing deterministic agent
        -> actual trace
        -> diagnosis
        -> bounded repair selection
        -> candidate SystemSnapshot
        -> actual source execution
        -> source EvaluationRecord(PASS)
        -> separate actual verification execution
        -> separate verification evaluation
        -> VerificationReport(VERIFIED)
        -> explicit candidate policy
        -> CandidateEligibilityDecision

## Claim limits

The complete slice remains a deterministic portfolio fixture.

It does not establish:

- repair of arbitrary AI agents,
- autonomous general program repair,
- external LLM repair quality,
- real production safety,
- independent infrastructure verification,
- production authorization,
- deployment readiness,
- research superiority.

## Acceptance checks

Before checkpointing P07.7C:

- P07.7A and P07.7B remain unchanged,
- prior governance contracts remain unchanged,
- verification refuses a source evaluation that is not PASS,
- source and verification executions are distinct,
- source and verification evaluations are distinct,
- both execution lineages bind the exact same candidate snapshot,
- the candidate is actually executed a second time,
- verification measurements come from that second execution,
- VerificationReport validates the complete frozen lineage,
- procedural separation is not described as proof of stronger independence,
- VERIFIED candidate can be ELIGIBLE under permitted policy,
- the exact same VERIFIED candidate can be INELIGIBLE under different current
  policy input,
- ELIGIBLE does not introduce authorization or deployment authority,
- focused integration tests pass,
- the complete unit plus integration regression remains green.

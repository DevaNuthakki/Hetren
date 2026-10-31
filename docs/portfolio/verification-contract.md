# Independent verification contract — P07.6E

Date: 2026-10-06.
Scope: Hetren's tool-using AI-agent portfolio project.
Status: implementation candidate; validation required before checkpoint.

## Purpose

VerificationReport preserves a verifier-reported conclusion over a separate
verification lineage.

It exists after an ordinary EvaluationRecord has reported PASS. A verification
lineage contains a distinct ExecutionRecord and a distinct EvaluationRecord for
the same candidate SystemSnapshot.

Constructing or validating a VerificationReport does not execute verification,
resolve evidence, prove independence, authorize a repair, mutate lifecycle
state, or make Hetren complete.

Historical startup/MVP documents do not expand this increment's scope.

## Architectural boundary

The existing diagnosis package is a separate deterministic diagnostic
experiment-selection subsystem. Its states are ACTIVE, DIAGNOSED,
INCONCLUSIVE and BUDGET_EXHAUSTED.

P07.6E does not modify that subsystem.

Verification belongs in packages/contracts beside GoalContract,
SystemSnapshot, ExecutionRecord and EvaluationRecord.

There is currently no implemented repair-level lifecycle state machine with
VERIFIED or COMPLETE authority. Such authority remains outside this increment.

## Verification lineage

The intended lineage is:

GoalContract
    |
    +-- candidate SystemSnapshot
    |
    +-- source ExecutionRecord
    |       |
    |       +-- source EvaluationRecord = PASS
    |
    +-- separate verification ExecutionRecord
            |
            +-- verification EvaluationRecord
                    |
                    +-- VerificationReport

Both executions must bind to the same goal and exact candidate snapshot.

The verification execution and source execution must have distinct record
identities. The verification evaluation and source evaluation must also have
distinct identities.

Distinct IDs and hashes establish separate records only. They do not by
themselves establish genuine experimental, organizational, data, evaluator, or
infrastructure independence.

## Outcomes

VerificationOutcome has five states:

- VERIFIED: the independent evaluation reported PASS.
- REJECTED: the independent evaluation reported FAIL.
- INCONCLUSIVE: the independent evaluation reported INCONCLUSIVE.
- BLOCKED: the independent evaluation reported BLOCKED.
- INVALID: the independent evaluation reported INVALID.

VERIFIED, REJECTED and INCONCLUSIVE require evidence references and
independence references structurally.

BLOCKED and INVALID may lack usable evidence or independence references.

Every report requires rationale and uncertainty.

## Independence

independence_references are opaque references to material supporting the claim
that the verification attempt was separate or protected.

Examples may include a protected-run attestation, environment manifest,
holdout freeze record, isolation attestation, or reviewer record.

The contract does not open or interpret these references. Their presence is
not proof that the referenced claims are true.

The contract deliberately does not require a different evaluator_id. Reusing
the same evaluator implementation may be legitimate when the independent
property is a separately protected run. Whether this satisfies the frozen
GoalContract.verification_requirements remains an external policy decision.

## Link validation

VerificationReport.validate_against checks:

- supplied object types and tenant/project scope,
- frozen GoalContract ID and digest,
- exact candidate SystemSnapshot ID and digest,
- source execution ID and digest,
- source evaluation ID and digest,
- verification execution ID and digest,
- verification evaluation ID and digest,
- both execution goal bindings,
- both execution candidate-snapshot bindings,
- source evaluation linkage and evaluator-version binding,
- verification evaluation linkage and evaluator-version binding,
- source EvaluationRecord outcome is PASS,
- verification report outcome corresponds to the verification evaluation
  outcome,
- source and verification lineages use distinct execution/evaluation IDs.

ExecutionRecord.validate_against remains responsible for validating each
execution's MethodProposal binding. VerificationReport does not duplicate that
responsibility.

## Integrity and authority limits

Canonical payloads include record type and schema version 1.

verification_sha256 fingerprints report content. It does not authenticate the
verifier, make storage immutable, prove evidence truth, or prove independence.

Frozen dataclasses prevent ordinary field assignment but are not a security
boundary against arbitrary code executing in the same process.

The report contains no authorization, approval, deployment-authority,
lifecycle-state, next-state, or completion field.

A VERIFIED report may become evidence consumed by a future policy/authority
layer. The report itself does not perform that transition.

## Acceptance checks

Before checkpointing P07.6E:

- existing shared contract implementation remains unchanged except package
  export wiring,
- diagnosis implementation and tests remain unchanged,
- valid separate verification lineage validates,
- source evaluation must PASS,
- independent verification outcome must agree with its EvaluationRecord,
- both lineages bind the exact same candidate snapshot,
- reused execution/evaluation identities are rejected,
- stale hashes and cross-scope records are rejected,
- measured verification outcomes require evidence and independence references,
- BLOCKED and INVALID remain representable without invented evidence,
- malformed fields and mutable collections are rejected,
- hashes remain deterministic and track material changes,
- contract operations perform no file/process/network I/O,
- focused verification tests pass,
- the complete unit regression passes,
- no lifecycle or authorization authority is introduced.

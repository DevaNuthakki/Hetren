# Deterministic repair execution and evaluation — P07.7B

Date: 2026-10-06.
Scope: Hetren's tool-using AI-agent portfolio project.
Status: implementation candidate; validation required before checkpoint.

## Purpose

P07.7B extends the deterministic executable diagnosis slice through one bounded
candidate repair, actual candidate execution and ordinary evaluation.

It deliberately reuses the existing governance contracts:

- GoalContract,
- SystemSnapshot,
- MethodProposal,
- ExecutionRecord,
- EvaluationRecord.

No new repair-governance record is introduced.

## Frozen objective

The GoalContract is independent of which hidden fixture fault occurs.

The frozen bounded objective is:

    7 + 5 -> 12

The goal describes the baseline system version, eligible bounded changes,
acceptance predicate, evidence requirements and later verification
requirement.

Diagnosis does not rewrite that objective.

## Repair selection

The repair selector consumes a completed DiagnosisDemoResult.

It receives no latent FaultMode.

The mapping is intentionally bounded:

    tool_selection_fault
        -> REPLACE_TOOL

    parameter_transformation_fault
        -> OVERRIDE_PARAMETER

This is a deterministic fixture policy, not a claim that Hetren can yet
generate arbitrary repairs.

## Candidate representation

The repair candidate is represented by an existing SystemSnapshot.

The candidate snapshot records:

- the target system,
- a candidate version identity,
- the exact bounded repair component identity,
- a canonical code identity,
- the baseline trace digest,
- the diagnosis-problem digest,
- the diagnosed hypothesis reference.

The frozen GoalContract may name the baseline system version while the
SystemSnapshot names the candidate version.

That linkage does not imply candidate eligibility.

## MethodProposal

MethodProposal describes the candidate method and binds it to the frozen goal
and exact candidate snapshot.

Its generated_program is provenance describing the bounded candidate:

    selected_tool = "add"

or:

    arguments = (7, 5)

The deterministic runner does not use Python eval or exec.

Before execution, the runner checks that the selected typed repair kind,
proposal program, candidate code identity and candidate component identity all
agree.

## Actual candidate execution

The candidate is executed against the same deterministic hidden fixture state.

The environment receives FaultMode because it implements the controlled hidden
system.

Repair selection does not receive FaultMode.

The actual repair execution uses the existing deterministic tool-agent
executor with the bounded repair primitive.

ExecutionRecord then binds:

- frozen GoalContract,
- exact candidate SystemSnapshot,
- MethodProposal,
- runner identity/version,
- execution-manifest digest,
- candidate output-evidence digest,
- trace digest.

ExecutionStatus.COMPLETED means only that the deterministic runner completed.

It does not mean the repair passed.

## Actual evaluation

The evaluator runs only after candidate execution.

Its verdict is calculated from:

    actual candidate output == expected output 12

It does not copy:

- the diagnosis,
- the candidate repair kind,
- experiment predicted verdicts,
- MethodProposal expected outcomes,
- ExecutionStatus.COMPLETED.

Therefore a structurally valid, completely executed candidate can still
receive EvaluationOutcome.FAIL.

## Positive candidates

For the tool-selection fixture:

    diagnosed tool_selection_fault
        -> REPLACE_TOOL
        -> add(7, 5)
        -> 12
        -> ExecutionRecord(COMPLETED)
        -> EvaluationRecord(PASS)

For the parameter-transformation fixture:

    diagnosed parameter_transformation_fault
        -> OVERRIDE_PARAMETER
        -> add(7, 5)
        -> 12
        -> ExecutionRecord(COMPLETED)
        -> EvaluationRecord(PASS)

## Negative controls

P07.7B also deliberately executes the wrong candidate.

Tool-selection fault with OVERRIDE_PARAMETER:

    subtract(7, 5)
        -> 2
        -> ExecutionRecord(COMPLETED)
        -> EvaluationRecord(FAIL)

Parameter-transformation fault with REPLACE_TOOL:

    add(7, -5)
        -> 2
        -> ExecutionRecord(COMPLETED)
        -> EvaluationRecord(FAIL)

This proves within the fixture that runner completion and repair success are
different claims.

## Scientific boundary

P07.7B preserves:

    diagnosed
        != repaired

    candidate constructed
        != candidate correct

    execution completed
        != evaluation PASS

    evaluation PASS
        != independently VERIFIED

    evaluation PASS
        != ELIGIBLE

    evaluation PASS
        != authorized

No VerificationReport or CandidateEligibilityDecision is created here.

Those belong to P07.7C.

## Claim limits

P07.7B demonstrates only that the deterministic portfolio fixture can connect:

    diagnosis
      -> bounded candidate selection
      -> existing candidate/proposal contracts
      -> actual candidate execution
      -> execution provenance
      -> actual deterministic evaluation

It does not establish general program repair, LLM repair generation, external
agent repair, independent verification, eligibility, authorization,
deployment, rollout, or completion.

## Acceptance checks

Before checkpointing P07.7B:

- P07.7A executable fixture remains unchanged,
- prior contracts and diagnosis implementation remain unchanged,
- the frozen goal does not depend on latent fault mode,
- repair selection depends on diagnosis rather than latent fixture truth,
- candidate SystemSnapshot differs from the frozen baseline version,
- MethodProposal binds the exact candidate,
- candidate execution is bound to proposal/snapshot repair semantics,
- correct diagnosed candidates actually produce output 12,
- correct candidates produce ExecutionRecord(COMPLETED),
- correct candidates produce EvaluationRecord(PASS),
- wrong candidates may still produce ExecutionRecord(COMPLETED),
- wrong candidates produce EvaluationRecord(FAIL),
- execution/evaluation records validate through existing contracts,
- actual execution evidence reaches both records,
- ordinary PASS does not manufacture verification or eligibility,
- focused integration tests pass,
- complete unit plus integration regression passes.

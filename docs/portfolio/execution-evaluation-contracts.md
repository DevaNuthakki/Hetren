# Execution and evaluation contracts — P07.6D

Date: 2026-10-06.
Scope: Hetren's tool-using AI-agent portfolio project.
Status: implementation review and 127-test unit regression passed; ready for a local checkpoint.

## Purpose

ExecutionRecord preserves one terminal execution attempt.
EvaluationRecord preserves an evaluator-reported assessment of an attempt.
Neither record executes a method, authorizes an action, resolves evidence,
calculates an evaluation verdict, or independently verifies a repair.

Historical startup/MVP documents do not expand this increment's scope.

## Research basis

These references informed the design. The field choices and validations are
Hetren engineering decisions, not claims of research novelty.

- Causal Analysis of Agent Behavior for AI Safety (2021):
  https://arxiv.org/abs/2103.03938
  Systematically chosen interventions motivate preserving exact experiment
  inputs and methods. A trace interpretation alone is not causal proof.

- AgentDebugX (2026 preprint), system overview:
  https://arxiv.org/html/2607.18754v1
  Separate trace inspection, recovery proposals, and reruns motivate distinct
  proposal, execution, and evaluation records.

- Demystifying evals for AI agents (2026), terminology and harness design:
  https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
  A transcript differs from the environmental outcome. Clean trials and
  repeated attempts motivate explicit environment and manifest references.

- W3C PROV-DM (2013):
  https://www.w3.org/TR/prov-dm/
  Distinct inputs, activities, and resulting entities inform provenance links.
  This implementation does not claim PROV compliance.

- RETRACE (2026 preprint), limitations:
  https://arxiv.org/html/2608.08950v1
  Model-based patch interpretation has reliability and issue-quality limits.
  Evaluation remains separate from independent executable verification.

This was a focused reference review, not an exhaustive worldwide survey.
Preprint findings are author-reported; their experiments were not reproduced
by Hetren. No source establishes that Hetren's repair system already works.

## Execution semantics

Statuses describe the top-level runner:

- COMPLETED: normal completion; a known runner exit code must be zero.
- FAILED: abnormal execution failure.
- BLOCKED: a prerequisite prevented launch; no process exit code exists.
- CANCELLED: the attempt was cancelled.
- TIMED_OUT: the execution deadline was reached.

Non-completed attempts require a termination reason. Unknown exit codes are
None. Negative process exit codes are allowed for failures. Booleans and
floats are not valid exit codes. Nested tool failures belong in the trace.

A prelaunch blocked attempt may have diagnostic traces but need not have
target outputs, an execution environment, or a runtime manifest.

Input/output/trace references are opaque identifiers. The future execution
manifest should preserve replay versus fresh execution, trial and condition,
runtime configuration, and resource usage. This increment stores its
reference; it does not implement or validate that manifest.

Explicit link validation checks scope, IDs, hashes, proposal bindings, and
logical target identity. The goal's system version can name a baseline while
a snapshot names a repair candidate. Therefore exact version equality is not
required here. Candidate eligibility needs a separate policy check; passing
link validation does not authorize the candidate.

## Evaluation semantics

The intended evaluator meanings remain:

- PASS: valid evidence supports all mandatory criteria.
- FAIL: valid evidence establishes a failed mandatory criterion.
- INCONCLUSIVE: valid evidence cannot settle the claim.
- BLOCKED: required evaluation could not complete.
- INVALID: material evidence or protocol cannot support the assessment.

Constructors enforce structural obligations, not those full semantic claims.
PASS, FAIL, and INCONCLUSIVE require evidence references. BLOCKED and INVALID
can lack usable evidence. Every outcome requires rationale and uncertainty.

Link validation checks goal/execution identity and hashes, shared scope, the
execution's goal binding, and the evaluator version declared in the goal.
The execution's snapshot and proposal require their own separate link check.

There is no automatic mapping between execution status and evaluation outcome.
A completed run can produce a wrong answer. A timed-out run can decisively
fail a mandatory deadline. An evaluator must implement the goal-specific
policy rather than infer correctness from a process status.

## Integrity and authority limits

Canonical payloads include record type and schema version 1. They are
serialized representations, not constructor keyword dictionaries. No
deserializer is included in this increment.

Hashes fingerprint content; they do not authenticate producers, make storage
immutable, prove evidence truth, or establish causality. Frozen dataclasses
prevent ordinary assignment but are not a security boundary against arbitrary
Python code running in the same process.

Constructing a PASS record must not advance a lifecycle to VERIFIED or COMPLETE.
Evidence resolution, evaluation policy, authorization, and independent
verification remain separate implementations.

## Acceptance checks

- Existing records.py and shared tests remain unchanged.
- Correct supplied record links validate.
- Stale hashes, incorrect bindings, and scope mismatches are rejected.
- Blocked attempts do not require invented process results.
- All five evaluation outcomes remain distinct.
- Malformed fields and mutable collections are rejected.
- Record hashes are deterministic and track material changes.
- Mutating a returned payload does not mutate the record.
- Focused tests and the existing full unit regression pass before freeze.

The I/O test checks selected process/file/network entry points. It is a
regression guard, not comprehensive proof of isolation or sandbox safety.
Passing these tests does not establish repair quality, causal accuracy,
generalization, or completion of the full Hetren system.

## Recorded validation

On 2026-10-06, the supplied Mac terminal output reported:

- Original unit baseline: 92 passing tests.
- Added behavioral tests: 35.
- Complete unit suite: 127 passed in 0.26 seconds.
- Preservation checks passed for the implementation and existing shared tests.
- Tracked whitespace check passed.
- Nothing was staged at the end of the test run.

Before checkpointing, execution.py and its new test file were compared with
the reviewed source fingerprints, and the package export change was checked
against the exact intended addition.

This evidence supports the implemented contract behavior and preservation of
the existing unit regression. It is not an independent-verification result
for the complete agent-repair system and establishes no research superiority.

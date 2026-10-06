# Deterministic tool-agent diagnosis slice — P07.7A

Date: 2026-10-06.
Scope: Hetren's tool-using AI-agent portfolio project.
Status: implementation candidate; validation required before checkpoint.

## Purpose

P07.7A is the first executable vertical slice in the portfolio architecture.

Earlier increments established deterministic diagnosis contracts/planning and
governed provenance contracts. P07.7A adds controlled behavior that can
actually be executed and observed.

This increment deliberately does not add another governance record.

## Controlled scenario

The fixture asks an agent to compute:

    7 + 5

The correct result is 12.

Two different latent faults intentionally produce the same visible baseline
result, 2.

### Tool-selection fault

The agent preserves the correct operands but selects subtraction:

    subtract(7, 5) -> 2

### Parameter-transformation fault

The agent selects addition but corrupts the second operand:

    add(7, -5) -> 2

The shared visible failure prevents diagnosis from being justified only by the
final scalar result.

## Real trace

Each run produces an AgentTrace containing contiguous:

1. DECISION,
2. TOOL_CALL,
3. TOOL_RESULT,
4. TERMINATION

events.

Trace fields preserve canonical hashes for inputs, outputs and state
transitions. Execution is deterministic and performs no network, process,
filesystem or provider I/O.

## Diagnostic hypotheses

The existing DiagnosisProblem is instantiated with two equal-prior
hypotheses:

- parameter_transformation_fault,
- tool_selection_fault.

No new diagnosis semantics are introduced.

## Diagnostic experiments

Two controlled interventions are preregistered.

### e1-replace-tool

Force the arithmetic tool to `add` while preserving the agent-produced
arguments.

Predictions:

- parameter-transformation fault -> FAIL,
- tool-selection fault -> PASS.

### e2-override-parameter

Force the arguments to `(7, 5)` while preserving the selected tool.

Predictions:

- parameter-transformation fault -> PASS,
- tool-selection fault -> FAIL.

Both experiments have equal declared cost and information structure. The
existing deterministic planner therefore selects the lexicographically first
experiment, `e1-replace-tool`.

## Execution-to-observation boundary

The selected intervention is actually executed.

The Observation verdict is computed from whether the executed output equals
12. It is not copied from the experiment's predicted verdict table.

The Observation evidence digest fingerprints the actual controlled execution
result and trace.

A failed intervention additionally records a counterexample digest describing
the expected and actual output.

## Diagnosis result

For the tool-selection fault:

    replace tool -> add(7, 5) -> 12 -> PASS

For the parameter-transformation fault:

    replace tool -> add(7, -5) -> 2 -> FAIL

That observation is replayed through the existing diagnosis lifecycle. In
either controlled case exactly one hypothesis remains and the lifecycle
reports DIAGNOSED.

## Claim limits

P07.7A proves only that the implemented deterministic fixture can connect:

    actual execution
      -> trace
      -> existing planner selection
      -> actual intervention
      -> Observation
      -> posterior update
      -> DIAGNOSED

It does not establish that Hetren can diagnose arbitrary AI agents, does not
prove causal identification in external systems, does not use an LLM or remote
provider, does not generate or apply a repair, and does not authorize,
evaluate, verify, deploy or promote a candidate.

Those remain later increments.

## Acceptance checks

Before checkpointing P07.7A:

- no prior frozen implementation is modified,
- both latent faults produce the same failing baseline output,
- executions produce real deterministic AgentTrace records,
- the existing planner selects the preregistered discriminating experiment,
- the selected experiment is actually executed,
- Observation verdicts come from executed outputs rather than prediction
  lookup,
- execution evidence is bound into Observation,
- failed intervention evidence preserves a counterexample digest,
- both hidden fixture faults are correctly diagnosed after the intervention,
- actual outcomes agree with the preregistered fixture predictions,
- unsupported interventions fail closed,
- no network/process/random/time dependency is introduced,
- focused integration tests pass,
- the complete unit regression remains green.

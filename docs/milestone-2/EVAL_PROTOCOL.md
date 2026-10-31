# Milestone 2 Evaluation Protocol

**Status: DRAFT. Not frozen.** This document is completed and frozen (hash-pinned in CI) as the last Milestone 2 task. Held-out test numbers for any method are produced only after it is frozen.

## Purpose

Measure whether a diagnosis-and-recovery method fixes failed support-agent runs when a fix is possible, stays out of healthy runs, and says so when evidence is missing or no available recovery works. Results are reported per fault family, with held-out families reported separately.

## Fault families

| ID | Family | Split role |
|---|---|---|
| F1 | Customer-to-account mapping swap | train / validation / test |
| F2 | Stale account record | train / validation / test |
| F3 | Mishandled tool error | train / validation / test |
| F4 | Misleading ticket text | train / validation / test |
| F5 | Missing account | train / validation / test |
| F6 | Queue misconfiguration | **held out: test only** |
| F7 | Tier format drift | **held out: test only** |

Healthy look-alikes, all labelled `no_intervention`:

- legitimately merged account (detectable through the account history probe and `merged_customer_refs`);
- recent tier change (working record equals the source of truth);
- transient tool error that the agent successfully retried.

## Action space

All probes and recoveries are generic verbs over entity types, shared by every family. No family has its own verb. Each episode has a probe budget of about 4 and ends with exactly one recovery or decision.

- **Retry probe:** a read-only probe re-calls a read tool (`read_ticket` or `lookup_account`) that failed in the run, which distinguishes transient from persistent errors before acting. F3 injects errors into read tools only, so this probe always applies.
- **No queue restore:** `restore_from_source` is not available for queues. Queue misconfiguration (F6) therefore has no verified recovery and is an escalation case.

Decisions:

- `no_intervention`
- `insufficient_evidence`
- `abstain`

## Decision definitions

**insufficient_evidence**: a required observation is absent from the record and the absence is unexplained, because it was withheld, truncated, or never attempted. A failed tool call is itself an observation: a run whose lookup failed with "unknown account_id" or "service unavailable" has complete evidence of that failure, so it is not `insufficient_evidence`.

**abstain**: the evidence is complete, but no recovery in the action space verifies. This includes persistent tool errors (F3) and escalation cases such as F6.

**F3 labels**: a transient error (the retry probe succeeds) is labelled `rerun`. A persistent error (the retry probe fails again) is labelled `abstain`. Sandboxes copy the tool-error call counters, so a retried or re-run call sees the same remaining failures it would see in the original world.

**F6 label**: `abstain`. F6 is held out, so it tests correct abstention on a problem never seen in training.

**F5 with several verified recoveries**: prefer the smallest verified change. That is `set_mapping` if a unique owner exists, otherwise reroute to triage.

**F4 when the ticket's claim matches the true tier**: the run is healthy, and the label is `no_intervention`.

## Labels

Labels are per run, not per world. A run whose final outcome already matches the expected queue and account is labelled `no_intervention`, whatever faults the world contains. The case's `remedy_if_wrong` applies only when the outcome is wrong. This matters for families whose effect depends on the agent's behaviour (F3, F4, F7 and the transient look-alike).

Labels come from execution, never from a model. A recovery label is a recovery that, applied in a sandboxed copy of the world and followed by re-running the task, passes verification, including regression checks on unaffected tickets. Probe labels come from simple counterfactual enumeration: a probe sequence is sufficient when every candidate world consistent with its observations has the same verified outcome.

## Splits

Splits are by fault family, generator seed, and agent source. Scripted agents produce training data. Live `gpt-4.1-mini` runs are used only for testing. F6 and F7 never appear in training or validation.

## Metrics

- verified recovery rate
- wrong interventions on healthy runs
- correct `insufficient_evidence` and `abstain` decisions
- probe count, including probe count on healthy runs as a cost metric

All metrics are reported per family, with held-out families reported separately.

**Proactive-detection families:** F2 (stale account record) and F6 (queue misconfiguration) leave no anomaly in the run itself; only a probe reveals them. Probing runs that look healthy is allowed within the probe budget, and these two families are reported as a separate proactive-detection group.

## Baselines

- extended rules (built on training families only)
- an untrained small model
- a strong general model: `gpt-4.1`

## Spending rules

Live budget:

- about 300 live `gpt-4.1-mini` test runs;
- a `gpt-4.1` baseline on 500 cases. It runs on validation in Milestone 2 and on the held-out test only after this protocol is frozen, as the first step of Milestone 3. The Batch API should be considered to halve the cost.

Before any step that costs money, the operator is told what will run, the exact token estimate measured from real sample cases, the cost, and the hard spending cap the script enforces. Live calls are run only by the operator, never automatically.

## Open items before freezing

- dataset, split and generator hashes
- complete verb and entity list
- per-family labeling details and the results of the labelability checkpoint
- the exact metric formulas and reporting format

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

### Known limitation: short probe sequences

Probe labels come from deliberately simple counterfactual enumeration: one world per case kind and variant (plus a clean world with nothing injected), injected into the same base world on the same ticket. Within such small hypothesis sets the label is usually settled by zero or one probe, occasionally two, so probe sequences are short. Richer enumeration (several worlds per kind, combined faults) would produce longer investigations and is left for later work.

Probe outcomes are compared up to renaming. IDs, canonical tiers (including in keys), timestamps and versions become placeholders, and free-text labels whose wording follows tier or role (account names, queue names, queue description templates) are reduced or dropped. A probe can therefore only separate hypotheses by relational evidence, not by random values or wording.

## Splits

Splits are by fault family, generator seed, and agent source. Scripted agents produce training data. Live `gpt-4.1-mini` runs are used only for testing. F6 and F7 never appear in training or validation.

| split | contents | use |
|---|---|---|
| `train` | scripted runs, the 8 training families | training |
| `validation` | scripted runs, the 8 training families | tuning and baselines |
| `test_in_distribution` | scripted runs, the 8 training families | final evaluation only |
| `test_held_out` | scripted runs, F6 and F7 only | final evaluation only |
| live test (task 10) | live `gpt-4.1-mini` runs | final evaluation only |

No test split is used for tuning, model selection, prompt changes or threshold choices.

Rules (implemented in `packages/support_evaluator/splits.py`; frozen lists in `docs/milestone-2/splits-v1/`):

- **Fault family.** F6 and F7 primary cases go to `test_held_out` with all their partners, and `test_held_out` contains nothing else. A partner record of F6 or F7 that belongs to a training-family case is dropped (reason "held-out partner outside test_held_out"), so training never sees F6 or F7 worlds, not even as contrast partners.
- **World seed.** Seeds used by any F6 or F7 primary are reserved for `test_held_out`. Other cases on a reserved seed are dropped with their partners (reason "seed reserved for held-out"). The remaining seeds go to `validation` (hash bucket below 0.15), `test_in_distribution` (0.15 to 0.30) or `train` (the rest) by a seeded hash. No world seed appears in two splits.
- **Twin groups.** A primary and its partners always share a split.
- **Agent source.** The four splits above are scripted runs. Live runs form the separate live test split when they are recorded.

Dropped records are listed in `dropped.tsv` (case ID and reason).

Splits v1 (seed 2026) on dataset v2 (primary cases / partner records):

- `train` 2723 / 2472
- `validation` 550 / 478
- `test_in_distribution` 560 / 514
- `test_held_out` 960 / 948 (F6 480, F7 480)
- dropped: 822 held-out partners; 12 seed-reserved records (7 primaries, 5 partners)

Compound cases: 16 train, 2 validation, 3 `test_in_distribution`. Per-split counts per kind, label and behaviour are in the split manifest.

### Live test split (task 10)

- **Plan:** 30 cases per case kind for all 10 kinds (held-out families included), variants cycled evenly, on world seeds from 1,000,000 to 1,999,999 (dataset seeds are below 1,000,000, so no live world appears in another split). Export: `python -m packages.support_evaluator.live --out artifacts/milestone-2/live-test-v1 --per-kind 30 --seed 2027`.
- **What the recording script sees:** `specs/run-NNNN.json` only (world spec and ticket ID, shuffled, neutral run IDs). Kinds, variants and truth stay in `evaluator/live_plan.jsonl`.
- **Recording:** `scripts/record_live_test.py`, model `gpt-4.1-mini-2025-04-14`, `store=False`, 300 output tokens per call, 10 turns per run, a hard dollar cap checked before every call, a resumable ledger. Run only by the operator.
- **Labels:** each live run is replayed from its captures on its world and labelled by the same execution-based labeler. Sandbox reruns and counterfactual hypotheses need an agent to re-run; they use every scripted behaviour whose compact evidence on that world equals the live run's. If all matching behaviours give the same label, that is the label. Runs with no matching behaviour, or with disagreeing labels, are reported separately and excluded from headline metrics. (The 3 Milestone 1 live examples all match `trust`.)
- **Low-count families:** results are reported per family and per variant with counts, never pooled only. Scripted proxies suggest the live model will rarely fail on misleading ticket text (F4, only text-following fails) and on tier format drift (F7, case and whitespace variants are easy to normalise), so their faulty-run counts may be small.

## Metrics

- verified recovery rate
- wrong interventions on healthy runs
- correct `insufficient_evidence` and `abstain` decisions
- probe count, including probe count on healthy runs as a cost metric

All metrics are reported per family, with held-out families reported separately.

**Proactive-detection families:** F2 (stale account record) and F6 (queue misconfiguration) leave no anomaly in the run itself; only a probe reveals them. Probing runs that look healthy is allowed within the probe budget, and these two families are reported as a separate proactive-detection group.

### Evaluation slices

Metrics are computed on primary cases only; counterfactual partner records never count. Besides the per-family and held-out reports, every method is reported on these evaluator-side slices (defined in `evaluator/tags.jsonl`):

- **Compound cases** (`compound`): a recovery or abstain label that differs from the case's own remedy because a second problem prevents the intended single fix. In dataset v2 these are the 21 stale-account-record (F2) cases with the text-following agent: a true tier claim written before the tier changed becomes false, so after `restore_from_source` the agent still follows the claim and no single recovery verifies; the label is `abstain`. They are kept and reported separately.
- **Recent-target stress slice** (`target_recent`): faulty cases (for example F2 and F6) whose target account had a recent tier change. The recent-tier-change look-alike is recent by definition and always healthy, so recency carries a small residual association with `no_intervention` (shortcut-audit lift about +0.04). This slice detects a learned "recent → healthy" shortcut. Recency is not visible in the first step's input; it appears only after probing.
- **Length-matched slice** (`first_input_tokens`): input length predicts the label well above chance (lift about +0.22) because it reflects run structure (withheld records, errors, early stops). Results are also reported within first-input token-length bins (deciles), and reweighted so every label has the same length distribution, to separate genuine reasoning from length cues.

### Known residual: recent-tier-change conversions

The recent-tier-change look-alike normally uses an account the generator already changed recently, so it adds nothing to history and history cannot separate it from F6. In about 5% of worlds no such account has tickets, and the injector converts one (one event, consistent with its source record). On that ticket the F6 counterfactual's account then has no recent change, so history does separate them. In dataset v2, 12 of 400 recent-tier-change primary cases are resolved this way; the other 388 use `inspect routing_policy`.

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

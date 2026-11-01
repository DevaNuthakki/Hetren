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
- **Labels:** each live run is replayed from its captures on its world and labelled by the same execution-based labeler. The final label always comes from the live run's own evidence and final state. The labeler's first two rules (unexplained absence, outcome correct) need no re-run. Recovery verification (sandbox re-runs) and probe labels (counterfactual hypotheses) need an agent to re-run; for those, the labeler uses every scripted behaviour whose compact evidence on that world equals the live run's. Each live run falls into exactly one category:
  - **proxy-matched:** at least one scripted behaviour matches and all matching behaviours give the same label. The run gets its full label (final decision and probe sequence).
  - **final-label-only:** no matching behaviour (or matching behaviours disagree), but the final label needs no re-run (`no_intervention` or `insufficient_evidence`). It counts in headline decision metrics. It has no probe-sequence label: any probe sequence that ends in the correct decision is scored correct, and its probe count is still reported as a cost.
  - **excluded:** no matching behaviour (or disagreeing labels) and the final label needs recovery verification. Reported separately, never in headline metrics; the label-confirmation phase below may later verify these live.
  - **live-confirmed (target ticket):** an excluded run whose candidate recovery was applied and confirmed by one live re-run of the target ticket. Its label is that recovery. It counts in headline metrics and has no probe-sequence label (scored like final-label-only runs).

  Counts of each category are reported per family. In the 10-run pilot, 9 runs were proxy-matched; the tenth (tier format drift, abbreviation, routed correctly by the live model, which no scripted behaviour does) is final-label-only. The 3 Milestone 1 live examples all match `trust`.
- **Label confirmation (separate phase, operator-run after a cost estimate and approval):** for each live run whose label is a recovery, apply that recovery in a fork and re-run the live model once. Runs where the live model still fails are flagged and reported. It shares the $1.00 total cap and ledger with recording.
  - **Scope:** confirmation re-ran only the target ticket. The labeller's regression checks (re-running the agent on the other tickets after a recovery) rely on scripted proxies for live runs and were not run live.
  - **Selection:** proxy-matched recoveries that re-run the agent (114), excluded compound F2 runs where matching proxies disagreed only between `restore_from_source` and `abstain` (4, confirming `restore_from_source`), and excluded runs without a matching behaviour (2, confirming the labeller's smallest verified recovery with `trust` re-running). `reroute` labels need no agent re-run and were not confirmed live.
  - **Result (live test v1):** 120 of 120 confirmed, $0.1037; no call reached the output limit. The 6 excluded runs became live-confirmed (target ticket): 4 stale-account-record, 2 missing-account. Final categories: training families 234 proxy-matched and 6 live-confirmed; held-out families 43 proxy-matched and 17 final-label-only; none excluded. Total live spend $0.3309 of the $1.00 cap.
- **Output limit:** any live call whose output reaches the 300-token limit is flagged (read from the capture's usage). None did in the pilot (maximum 28 tokens).
- **Reporting:** live results report training families and held-out families (F6, F7) separately.
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

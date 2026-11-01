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

All probes and recoveries are generic verbs over entity types, shared by every family. No family has its own verb. Each episode has a probe budget of 4. In tier 1 (dataset v2) an episode ends with exactly one recovery or decision; tier 2 (dataset v3) allows up to two recoveries (see "Tier 2: up to two recoveries").

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

## Tier 2: up to two recoveries

Dataset v2 is frozen as **tier 1**: one recovery or decision per episode, labels and inputs unchanged. Dataset v3 is **tier 2** and allows up to two recoveries, because some cases have two faults that are each fixable (for example an identifier swap together with a stale account record), and an operator would fix both. Every metric is reported per tier.

**Episode.** Probes as in tier 1; the probe budget of 4 is shared across the whole episode. A recovery is applied through a gateway scoped to exactly the proposed call; `set_mapping`, `restore_from_source` and `rerun` are followed by a re-run of the task with the same behaviour, and `reroute` re-runs nothing. The policy then sees the input after the recovery, may probe again (on a fork of the new state), and gives either a second recovery, which ends the episode, or `no_intervention`, meaning stop: the outcome is now right.

**Input after a recovery** (`compact-evidence-v2`): the tier 1 input plus a `recoveries` list; each entry holds the action, its result, the task's re-run (`null` after a reroute) and the probes made after it. Inputs before any recovery carry no `recoveries` key and stay `compact-evidence-v1`, byte for byte.

**Sequence labels.** Every tier 1 label is kept except `abstain` for "no verified recovery". A persistent tool error is never searched past: the error masks what else is wrong, and the label stays as in tier 1. Otherwise the label is the shortest verified sequence of two recoveries, or `abstain` when none verifies. A sequence verifies when the final state passes the tier 1 checks (outcome, account record, queue configuration) and every regression ticket still routes correctly. The first recovery is a state-changing `set_mapping` or `restore_from_source` (a first `reroute` is undone by any later re-run, and a first `rerun` adds nothing because a world edit re-runs the task); the second is any candidate on the state after the first. Ties are broken by (verb 1, verb 2, hash 1, hash 2) in the tier 1 recovery order (`rerun` < `reroute` < `set_mapping` < `restore_from_source`). The search is pruned without changing the label (commuting world edits are tried once, pairs that cannot map the target's reference to the expected account are skipped, and the search stops at the first verified pair in tie-break order); a naive search over every pair is kept as the test oracle.

**Training steps.** A tier 2 case labelled with a recovery has: probes, the first recovery, probes after it, then the second recovery or `no_intervention`. Cases labelled `abstain`, `no_intervention` or `insufficient_evidence` have one decision step as in tier 1. Step 1's probes reduce the label entropy over the first action; at step 2 the hypotheses still consistent get the same first recovery (renamed into their own world), are filtered again by the abstracted post-recovery input, and the probes reduce the entropy over the second action, considering first the entities the recovery and its re-run name. On the tier 2 sample, 10.6% of compound cases stay undetermined within the budget, four fifths of them pairs with queue misconfiguration (F6); single-fault cases are all determined.

**Scoring.** The whole sequence is re-checked by execution on the unprobed end state: every applied recovery is re-applied in order and the final state must verify. After a recovery, only `no_intervention` can close an episode. Tier 2 adds three metrics:

- **exact sequence match:** the policy's non-probe actions equal the label's;
- **verified but longer than the label:** correct, with more recoveries than the label (among cases whose label has a recovery);
- **stopped after one of two:** the policy applied one recovery and stopped where the label needs two.

**Token budget.** Tier 2 inputs have a budget of 1,200 tokens (tier 1 stays 800). On a tier 2 sample (1,565 cases: one variant per kind pair and every single-fault variant, 6 worlds × 5 behaviours; 7,379 inputs including partners), the largest input was 797 o200k_base tokens and 831 tokens with the `Qwen/Qwen3-4B-Instruct-2507` tokenizer at the pinned revision; 164 post-recovery inputs exceed 800 tokens with the Qwen tokenizer, none exceed 1,200 with either. The budget is checked again on the full v3 sample.

### Known limitation: no partial fix and escalate

After a first recovery the policy cannot partially fix and then escalate: `abstain` after a recovery is scored wrong. A case where one fault is fixable and the other is not (for example a mapping swap with a queue misconfiguration) is labelled `abstain` before any recovery.

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

Every baseline is a policy over compact evidence, run by `packages/support_evaluator/episodes.py`: the policy gets the dataset's first input, each probe runs through the probe gateway on a fork of the run's end state (so probing never changes the scored state), and the episode ends at the first decision or recovery, or with a failure when the policy asks for a fifth probe or returns an invalid action. The final action is scored with the labeller's `verify_label` on the unprobed end state: decisions must be right, recoveries must verify by execution (any verified recovery counts; exact match with the smallest label is reported separately). Metric formulas are provisional until task 12.

### Rules baseline (v1)

`packages/hetren_baselines/rules.py`, `RULES_POLICY_VERSION = 1`. Written and debugged on the train split only, then frozen and run once on validation. It has no rules for the held-out families. It stays frozen: it is not tuned on validation, on later dataset tiers, or on test results.

On tier 2, rules v1 is run as a single-recovery policy: its episode ends at its first recovery, which counts as an implicit stop. It cannot perform two-step recoveries by design, so its results on cases whose label needs two recoveries are reported as a baseline limitation, not as a rules failure to fix.

Validation (splits v1, 550 primary cases):

| metric | rules v1 |
|---|---|
| decision accuracy | 99.6% (548/550) |
| verified recovery rate | 100% (254/254) |
| wrong interventions on healthy runs | 0% (0/171) |
| `insufficient_evidence` recall / precision | 100% / 100% (93) |
| `abstain` recall / precision | 93.8% (30/32) / 100% |
| exact match with the label | 82.7% |
| mean probes (all / healthy) | 1.43 / 2.31 (probe oracle: 0.61 / 0.88) |
| compound slice / recent-target faulty slice | 0/2 / 114/114 |

All per-family accuracies are 100% except stale account record (64/66): both errors are compound cases (text-following agent), where the rules restore the account and the label is `abstain`. In-distribution validation is therefore nearly solved by hand-written rules; decision accuracy there does not separate methods, and differences must come from probe cost, compound cases, held-out families, live runs, and the harder tier (dataset v3, proposed).

### Small model baseline and evaluation settings

- **Model:** `Qwen/Qwen3-4B-Instruct-2507` (revision `cdbee75f17c01a7cc42f958dc650907174af0554`, Apache-2.0) is the primary model for the untrained baseline and Milestone 3 fine-tuning; `HuggingFaceTB/SmolLM3-3B` (revision `a07cc9a04f16550a088caea529712d1d335b0ac1`, Apache-2.0) is the backup.
- **Hardware:** Kaggle T4 (16 GB).
- **Evaluation settings, identical for the untrained baseline and the fine-tuned model:** fp16 weights (T4 has no bf16); for the fine-tuned model, QLoRA adapters merged into the fp16 base before evaluation; the model's own chat template (non-thinking; for SmolLM3, reasoning off); greedy decoding (`do_sample=False`), `max_new_tokens=128`, no repetition penalty; the same prompt module as the `gpt-4.1` baseline; the output is parsed with `parse_action`, and anything unparsable is an invalid-action failure. Library versions are recorded with each run.

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

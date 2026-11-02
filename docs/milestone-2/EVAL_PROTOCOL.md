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

Probe labels come from deliberately simple counterfactual enumeration: one world per case kind and variant (plus a clean world with nothing injected), injected into the same base world on the same ticket. Within such small hypothesis sets the label is usually settled by zero or one probe, occasionally two, so probe sequences are short. This limitation stays for tier 1 (dataset v2 is frozen); tier 2 uses richer enumeration (see "Tier 2 hypotheses and probe menu").

Probe outcomes are compared up to renaming. IDs, canonical tiers (including in keys), timestamps and versions become placeholders, and free-text labels whose wording follows tier or role (account names, queue names, queue description templates) are reduced or dropped. A probe can therefore only separate hypotheses by relational evidence, not by random values or wording.

## Tier 2: up to two recoveries

Dataset v2 is frozen as **tier 1**: one recovery or decision per episode, labels and inputs unchanged. Dataset v3 is **tier 2** and allows up to two recoveries, because some cases have two faults that are each fixable (for example an identifier swap together with a stale account record), and an operator would fix both. Every metric is reported per tier.

**Episode.** Probes as in tier 1; the probe budget of 4 is shared across the whole episode. A recovery is applied through a gateway scoped to exactly the proposed call; `set_mapping`, `restore_from_source` and `rerun` are followed by a re-run of the task with the same behaviour, and `reroute` re-runs nothing. The policy then sees the input after the recovery, may probe again (on a fork of the new state), and gives either a second recovery, which ends the episode, or `no_intervention`, meaning stop: the outcome is now right.

**Input after a recovery** (`compact-evidence-v2`): the tier 1 input plus a `recoveries` list; each entry holds the action, its result, the task's re-run (`null` after a reroute) and the probes made after it. Inputs before any recovery carry no `recoveries` key and stay `compact-evidence-v1`, byte for byte.

**Sequence labels.** Every tier 1 label is kept except `abstain` for "no verified recovery". A persistent tool error is never searched past: the error masks what else is wrong, and the label stays as in tier 1. Otherwise the label is the shortest verified sequence of two recoveries, or `abstain` when none verifies. A sequence verifies when the final state passes the tier 1 checks (outcome, account record, queue configuration) and every regression ticket still routes correctly. The first recovery is a state-changing `set_mapping` or `restore_from_source` (a first `reroute` is undone by any later re-run, and a first `rerun` adds nothing because a world edit re-runs the task); the second is any candidate on the state after the first. Ties are broken by (verb 1, verb 2, hash 1, hash 2) in the tier 1 recovery order (`rerun` < `reroute` < `set_mapping` < `restore_from_source`). The search is pruned without changing the label (commuting world edits are tried once, pairs that cannot map the target's reference to the expected account are skipped, and the search stops at the first verified pair in tie-break order); a naive search over every pair is kept as the test oracle.

**Training steps.** A tier 2 case labelled with a recovery has: probes, the first recovery, probes after it, then the second recovery or `no_intervention`. Cases labelled `abstain`, `no_intervention` or `insufficient_evidence` have one decision step as in tier 1. Step 1's probes reduce the label entropy over the first action; at step 2 the hypotheses still consistent get the same first recovery (renamed into their own world), are filtered again by the abstracted post-recovery input, and the probes reduce the entropy over the second action, considering first the entities the recovery and its re-run name.

**Scoring.** The whole sequence is re-checked by execution on the unprobed end state: every applied recovery is re-applied in order and the final state must verify. After a recovery, only `no_intervention` can close an episode. Tier 2 adds three metrics:

- **exact sequence match:** the policy's non-probe actions equal the label's;
- **verified but longer than the label:** correct, with more recoveries than the label (among cases whose label has a recovery);
- **stopped after one of two:** the policy applied one recovery and stopped where the label needs two.

**Token budget.** Tier 2 inputs have a budget of 1,200 tokens (tier 1 stays 800). On a tier 2 sample (1,565 cases: one variant per kind pair and every single-fault variant, 6 worlds × 5 behaviours; 7,379 inputs including partners), the largest input was 797 o200k_base tokens and 831 tokens with the `Qwen/Qwen3-4B-Instruct-2507` tokenizer at the pinned revision; 164 post-recovery inputs exceed 800 tokens with the Qwen tokenizer, none exceed 1,200 with either. The budget is checked again on the full v3 sample.

### Tier 2 hypotheses and probe menu

**Hypotheses.** Tier 2 counterfactual worlds, all on the same base world and ticket and carrying the case's distractors, are: every single variant, the case's own included, in 3 random draws (the first is tier 1's world for that variant), so the same symptom can come from different partners or targets; and every dataset v3 compound pair. Worlds identical to one already listed are dropped. Each world's run is compared with the case's first; only consistent worlds are labelled (the same consistency-first order is used for tier 1, whose output is unchanged: the dataset v2 manifest regenerates identically).

**Adaptive probe menu.** Tier 1's menu holds probes over the entities in the agent's run. In tier 2, entities that an earlier probe's observation named join the menu after the run's own (for example a `retry` that returns the ticket reveals its reference; `inspect routing_policy` reveals queues). A probe can therefore only name entities the run or an earlier probe showed; on the measurement sample, no probe argument named an ID absent from its step's input (519 probe steps). A probe that only reveals entities has no immediate gain, so when no probe gains, the oracle picks the probe whose best follow-up gains most in expectation (two-step lookahead), within the same budget of 4. A case still undetermined after that is genuinely ambiguous under the menu and budget: it is kept, flagged, and reported per kind; no label is forced.

**Partner records.** The oracle uses every consistent hypothesis, but partner records are written for one hypothesis per distinct sequence label (written with its own placeholders). Within a label, the partner is the hypothesis with the smallest hash of the twin ID and its key, so no variant is systematically preferred by enumeration order.

**Probes run in forks.** In tier 2 labelling every probe runs in a fork, as in episodes: a `retry` advances tool-error counters, which must not reach the state a recovery is applied to. (Tier 1 labelling probes the run's environment directly; re-labelling all 202 dataset v2 cases that use `retry` with forked probes changed no record.)

On a measurement sample (105 cases: every single-fault variant and one compound variant per kind pair, 2 worlds, 0–2 distractors; labels identical to the tier 1 hypothesis set's), the richer set raised twin cases from 42% to 87% and probes per case from 0.47 to 1.89 (61% of cases need two or more); 97.1% of cases are determined. The three undetermined were one each of mapping swap, merged account, and queue misconfiguration with merged account. Counts per kind on the full v3 dataset are reported with it.

### Distractors

Tier 2 cases can carry 1–2 distractors: irrelevant inconsistencies away from the target, each a training-family injection pinned to another ticket (a stale record on another account, a mapping swap between two other references, a transient or persistent error rule on another ticket's lookup, a recent tier change or merge history on another account). Tier format drift (F7) is a distractor only in cases that are already held out; queue misconfiguration (F6) is never a distractor, because it changes the global queue configuration that verification checks.

A distractor never touches the target ticket, its reference, its true owner or expected account, or the regression tickets with their references and owners; the target's recomputed outcome must be unchanged; and the agent's run on the target must be identical with and without it for every behaviour (checked by execution, because a case's own fault can bring another account into the run, such as a swap partner). Placements that fail are redrawn. Tier 2 labelling re-checks by execution that the label equals the label without distractors. Counterfactual hypotheses carry the same distractors, so hypotheses differ only in the case's own fault.

On a measurement sample (every single-fault variant and six compound variants, 4 worlds × 5 behaviours × 1 and 2 distractors; 920 runs), labels and runs were unchanged in every run. A distractor changed some probe observation on the oracle's probe menu in 6.0% of runs, all in cases whose own fault is a mapping swap: there the run names a second account (the swap partner), and a stale record, merge history or swap on that account shows up when probed. Elsewhere the run and the probes reach only the target's chain, which distractors may not touch, so distractors there are not observable.

### Dataset v3 plan and splits

**Plan** (`tier2_slots` in `packages/support_evaluator/plan.py`; build with `python -m packages.support_evaluator.dataset --tier 2 --seed <seed> --out <dir> --processes <n>`): 2,040 primary cases.

- 25 training compound pairs (the 10 pairs of F1–F5 and the 15 pairs of F1–F5 with a look-alike) × 5 behaviours × 8 = 1,000;
- held-out compound pairs, 400 in all: F6 with each of F1–F5 × 5 behaviours × 8 = 200, and F7 with F1, F3, F4 and F5 × 5 behaviours × 10 = 200 (F7 with F2 cannot occur, see below, so its 40 cases go evenly to F7's other pairs);
- 8 single kinds (F1–F5 and the three look-alikes) × 5 behaviours × 16 = 640.

Within each group × behaviour cell, variants cycle evenly over the variants that can occur; one case in eight has evidence withheld (one in ten in the F7 held-out cells of 10; 250 of 2,040 overall; dataset v2 used one in six), and distractor counts 0, 1 and 2 are shuffled, both at random, so neither depends on kind, variant or behaviour. Each slot draws its world seed (2,000,000–2,999,999, disjoint from dataset v2 and the live test) and case seed from its own random stream and keeps its first candidate that injects. Only injection redraws (the fault, a compound's two faults, or the distractors not fitting the world); skipped candidates and their reasons are recorded evaluator-side (`redraws`), so selection effects can be audited. The label never causes a redraw: undetermined, `abstain` and every other outcome are kept, and an error while labelling stops the build. Records carry `tier: 2` and the sequence label.

**Impossible compounds.** Some compound variants can never occur: their two faults conflict at injection on every draw. The plan leaves them out (`IMPOSSIBLE_COMPOUND_VARIANTS` in `plan.py`; a test checks that each never fits on 40 worlds and that every remaining plan variant fits at least once):

| compound | variants left out | reason |
|---|---|---|
| F1 mapping swap + F5 missing account | swap, redirect, nway with `unmapped_ref` (3 of 6) | both faults rewrite the target reference's directory entry |
| F5 missing account + merged account | `deleted_account` with merge history (1 of 2) | the merge history is on the account the fault deletes |
| F5 missing account + F7 tier drift | `deleted_account` with case, abbreviation, whitespace (3 of 6) | the tier drift is on the account the fault deletes |
| F2 stale record + F7 tier drift | all 3 | both faults rewrite the target account's source record |

Before labelling, a preflight attempts injection for every slot and stops with a report if any slot cannot be filled.

**Splits** follow the splits v1 rules on world seed, twin groups and agent source. A compound is held out when either component is F6 or F7: its primary goes to `test_held_out` with all its partners, and held-out partner records of training cases are dropped. The held-out check uses each record's own truth (kind and, for compounds, both components); on dataset v2 this rebuilds splits v1 identically.

**Token budget rule** (decided before the full v3 build): if tier 2 inputs exceed 1,200 tokens but the maximum stays under about 1,800 with the `Qwen/Qwen3-4B-Instruct-2507` tokenizer, the tier 2 budget is raised to cover the maximum; probe results are never truncated or compressed. Anything above about 1,800 stops the work for a decision. On the 105-case measurement sample (1,855 inputs, primaries and partners), the largest input was 920 Qwen tokens and 873 o200k_base tokens.

**Dataset v3 build (seed 2028).** 2,040 primary cases and 6,358 partner records (8,398 records, 31,365 steps); manifest `docs/milestone-2/dataset-v3.manifest.json` (a test re-labels a seeded sample of 10 records from the plan and checks every line byte for byte). Labelling took 73 minutes on 11 processes (22.9 s per case on average, median 10.4 s, max 107 s). Every slot filled; 469 candidates in 151 slots were skipped at injection, all because the recent-tier-change component found no target account with a recent tier change (the same 469 the preflight skipped).

- **Leakage and marker scans:** 0 findings on all 8,398 records.
- **Tokens (every step input, primaries and partners):** maximum 946 `Qwen/Qwen3-4B-Instruct-2507` tokens and 901 o200k_base tokens; tier-1-format inputs at most 556 and 517. Nothing exceeds 1,000, so the budget rule does not apply and the tier 2 budget stays at 1,200.
- **Determinedness:** 1,986 of 2,040 primary cases (97.4%) have a determined probe label. The 54 undetermined cases are kept and flagged (scoring rule under Metrics): merged account 11, mapping swap 8, mapping swap + F6 6, mapping swap + transient error retried 6, mishandled tool error 4, mishandled tool error + transient error retried 4, mapping swap + mishandled tool error 3, mapping swap + recent tier change 3, missing account 3, missing account + recent tier change 2, and 1 each for mishandled tool error + recent tier change, missing account + F6, missing account + F7, missing account + transient error retried.
- **Probes** (cases with complete evidence): mean 1.79 per case; 0: 258, 1: 437, 2: 645, 3: 319, 4: 131 (61% need two or more).
- **Labels:** `no_intervention` 402, `abstain` 339, `restore_from_source` then stop 254, `insufficient_evidence` 250, `set_mapping` then stop 228, `reroute` then stop 189, `rerun` then stop 146, `set_mapping` then `restore_from_source` 137, `set_mapping` then `rerun` 53, `restore_from_source` then `reroute` 24, `set_mapping` then `reroute` 18 (232 two-recovery labels). Distractors: 0 in 770 cases, 1 in 710, 2 in 560.
- **Shortcut audit** (lift over the majority label, dataset v2 → v3): input tokens +0.221 → +0.153, step count +0.100 → +0.122, error present +0.075 → +0.111, source gap +0.079 → +0.080, ticket text −0.103 → −0.122, recency +0.039 → +0.026, account history events +0.006 → +0.088 (see below).

**History events.** The number of history events on the target account rises from +0.006 lift in dataset v2 to +0.088 in v3. The cause is mechanical: a stale-record (F2) or recent-tier-change component adds one event to the target account's history, and those components produce the `restore_from_source` labels (for example, 98 of the 254 `restore_from_source` then stop cases have two or more events, against none of the 228 `set_mapping` then stop cases). History is visible only through a probe (`history`), never in the first input, so this is evidence that has to be found, not a shortcut in the input. The audit counts history in the world as the model sees it when probing, distractors included (+0.088; +0.089 without distractors).

**No live slice yet.** Tier 2 has no live `gpt-4.1-mini` test slice. A compound live slice, and a `recent_changes` probe that would make distractors observable in every family, are deferred until after training.

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

Rules (implemented in `packages/support_evaluator/splits.py`; frozen lists in `docs/milestone-2/splits-v1/` for dataset v2 and `docs/milestone-2/splits-v2/` for dataset v3):

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

Splits v2 (seed 2028) on dataset v3 (primary cases / partner records):

- `train` 1133 / 2335
- `validation` 250 / 507
- `test_in_distribution` 256 / 517
- `test_held_out` 400 / 1208 (F6 compounds 200: 40 with each of F1–F5; F7 compounds 200: 50 with each of F1, F3, F4, F5)
- dropped: 1,788 held-out partners; 4 seed-reserved records (1 primary, 3 partners)

The dropped primary is `case-001703` (stale account record, single fault): its world seed 2,055,083 was also drawn by a held-out compound case, so the seed rule drops it with its partners. The plan draws 2,040 seeds from a million, so about two such collisions were expected; the case is accepted as dropped rather than regenerated, and the in-distribution splits hold 1,639 of the planned 1,640 cases.

Undetermined primary cases per split: train 30, validation 8, `test_in_distribution` 8, `test_held_out` 8.

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

**Failed recovery calls.** A proposed recovery whose tool call fails (an unknown ticket, queue or account, or any other environment error) is scored wrong in both tiers and at either step of a tier 2 sequence, even if a later step would verify, and the reason is recorded in the row's `recovery_failures`. `set_mapping` with a customer reference that does not exist yet is not a failed call: the directory accepts new references by design, so it is an ordinary change scored by execution. This rule was added after a `gpt-4.1` reroute to an unknown queue stopped a run; re-scoring every recorded episode (rules v1 and `gpt-4.1` on both tiers) changed no result. One `gpt-4.1` prompt version 1 tier 2 episode (`case-002287`) had a failed first step (unknown account) and was already scored wrong.

**Undetermined cases.** A case is undetermined when no probe sequence within the budget separates every hypothesis consistent with the run (`probe_label.determined` is false). Undetermined cases are included in decision metrics: their final labels come from execution, not from the probe oracle. They are excluded from probe-efficiency metrics (probe counts and comparisons with the oracle's probe sequence), and their count is reported with every result.

**Proactive-detection families:** F2 (stale account record) and F6 (queue misconfiguration) leave no anomaly in the run itself; only a probe reveals them. Probing runs that look healthy is allowed within the probe budget, and these two families are reported as a separate proactive-detection group.

### Evaluation slices

Metrics are computed on primary cases only; counterfactual partner records never count. Besides the per-family and held-out reports, every method is reported on these evaluator-side slices (defined in `evaluator/tags.jsonl`):

- **Compound cases** (`compound`): a recovery or abstain label that differs from the case's own remedy because a second problem prevents the intended single fix. In dataset v2 these are the 21 stale-account-record (F2) cases with the text-following agent: a true tier claim written before the tier changed becomes false, so after `restore_from_source` the agent still follows the claim and no single recovery verifies; the label is `abstain`. They are kept and reported separately.
- **Recent-target stress slice** (`target_recent`): faulty cases (for example F2 and F6) whose target account had a recent tier change. The recent-tier-change look-alike is recent by definition and always healthy, so recency carries a small residual association with `no_intervention` (shortcut-audit lift about +0.04). This slice detects a learned "recent → healthy" shortcut. Recency is not visible in the first step's input; it appears only after probing.
- **Compound pairs** (`compound_pair`, tier 2): planned compounds of two faults (1,400 of the 2,040 dataset v3 primary cases). The `compound` tag keeps its tier 1 meaning on tier 2 (a label that differs from the case's own remedy), so it is not the compound-pair slice.
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

Tier 2 validation (splits v2, 250 primary cases; single-recovery policy):

| metric | rules v1 |
|---|---|
| decision accuracy | 86.0% (215/250) |
| exact sequence match | 73.6% (184/250) |
| verified recovery rate | 75.5% (105/139) |
| wrong interventions on healthy runs | 0% (0/54) |
| `insufficient_evidence` recall / precision | 100% / 100% (31) |
| `abstain` recall / precision | 96.2% (25/26) / 100% |
| `no_intervention` recall / precision | 100% (54/54) / 91.5% (54/59) |
| mean probes (all / healthy) | 1.51 / 2.44 |
| single-fault cases / compound pairs | 99.0% (100/101) / 77.2% (115/149) |
| two-recovery labels | 0/23 (by design) |
| 0 / 1 / 2 distractors | 84.5% (82/97) / 86.3% (69/80) / 87.7% (64/73) |

Its errors are compound pairs: the two-recovery labels it cannot reach by design, and pairs where its first fix is not the label's (mapping swap with stale record 0/6, with transient error retried 1/8, with missing account 1/7). Distractors do not lower its accuracy.

### Model baseline prompt (`gpt-4.1` and the small model)

Every model baseline uses one prompt module, `packages/hetren_baselines/prompt.py` (current `PROMPT_VERSION = 2`; every version stays reproducible and its text is pinned by a test). Each policy call is stateless: the system prompt describes the task, the generic action catalog (every verb with its description and argument schema), the probe budget, the decision definitions and, in tier 2, the rules for a second recovery; the user message is the step's compact evidence exactly as `render_evidence` writes it, with probe results and applied recoveries. The prompt names no fault family, case kind or agent behaviour. The reply is stripped of surrounding whitespace and one enclosing Markdown code fence (the same for every model) and must then parse with `parse_action`; anything else is an invalid-action failure. The version 2 system prompt is 1,466 o200k_base tokens in tier 1 and 1,559 in tier 2 (1,449 and 1,542 `Qwen/Qwen3-4B-Instruct-2507` tokens); version 1 was 1,268 and 1,361.

**Prompt versions.** Each version is measured and reported separately on validation, and the strongest becomes the baseline prompt for the test splits; no prompt is changed after test results are seen.

- **Version 1:** the output format given only as `{"action": "<probe|recover|decide>", "verb": "<verb>", "args": {...}}`.
- **Version 2 (format fix only):** every verb is listed with its action type (`- inspect (action "probe"): ...`), each action type has one example (placeholder IDs), and the format line says that `action` is the action type, never the verb. Nothing else changes (a test checks that removing these additions gives version 1 exactly), probing gets no extra encouragement, and parsing stays strict.
- **Possible version 3 (not built):** if `gpt-4.1` still almost never probes under version 2, a version that explains generically, without naming fault families, what each probe reveals.

### `gpt-4.1` baseline

`python -m packages.support_evaluator.gpt41_baseline`, run only by the operator: model `gpt-4.1-2025-04-14`, Responses API (standard, not Batch), `store=False`, temperature 0, 128 output tokens per call. It runs on all 800 validation primary cases: 550 tier 1 (splits v1 on dataset v2) and 250 tier 2 (splits v2 on dataset v3), with one `--max-usd 12` cap and one ledger for both tiers. Before every call the projected spend (provider-reported spend so far, plus the exact o200k_base count of both messages and a 10-token formatting allowance with a 10% margin, plus the full output limit) is checked against the cap; if it would pass, nothing is sent and the run stops. Cached input is charged at the full price in the cap. Hitting the cap or an API error discards the current episode (it is re-run on restart) and never counts as a model failure. Every call is logged with its usage and reply, and calls that reach the output limit are flagged.

Measured on the validation inputs along the labelled path (the fewest calls an episode can take): tier 1 885 calls, 1,365,791 input and 24,322 output tokens; tier 2 785 calls, 1,347,013 and 21,171. At $2.00 / $8.00 per million input / output tokens this is $5.79 without caching ($2.76 with automatic prompt caching of the system prompt); if every case used the most calls allowed (5 in tier 1, 6 in tier 2), $20.49. The model is expected to probe more than the labels, so spend falls between these, about $9 without caching.

**Validation run, prompt version 1** (2026-11-02; 800 cases, 867 calls, $2.858 including a 5-case pilot; no API errors or discarded episodes, no reply at the output limit; prompt caching applied to 87 calls):

| | tier 1 (550) | tier 2 (250) |
|---|---|---|
| decision accuracy, strict (protocol scoring) | 18.7% (103) | 7.2% (18) |
| episodes ended by an invalid action | 193 | 206 |
| lenient lower bound (see below) | 37.1% (204) | 21.2% (53) |
| cases with any probe | 9 | 20 |

- **Format failures:** 399 of 867 replies (46%) put the verb in the `action` field (for example `{"action": "insufficient_evidence", "verb": "insufficient_evidence", ...}`), which `parse_action` rejects. This is a weakness of the version 1 prompt, which gave the format without an example; it led to version 2.
- **Lenient lower bound** (diagnostic only, never a headline metric): every verb belongs to exactly one action type, so an invalid reply whose intent is unambiguous was re-scored offline with the type taken from its verb. In tier 1, 101 of the 193 become correct and 84 stay wrong; 8 were probes, whose episodes would have continued and cannot be scored without new calls. In tier 2, 35 become correct and 91 stay wrong; 80 were probes or first recoveries that would have continued.
- **`gpt-4.1` rarely probes:** it probed in 9 of 550 tier 1 cases and 20 of 250 tier 2 cases, and otherwise decided from the run alone. In all 47 tier 1 cases where both the label and its reply were `set_mapping`, it named the right customer reference but the wrong account: without `find_owners` it could not know the true owner. It also chose `no_intervention` on stale records that only a probe reveals (34) and `insufficient_evidence` on transient tool errors labelled `rerun` (60).

The version 2 run uses a new output directory, its own ledger and a $9 cap.

**Deprecation.** OpenAI deprecated `gpt-4.1-2025-04-14` and `gpt-4.1-mini-2025-04-14` on 2026-10-14; both are removed from the API on 2027-01-14 (recommended replacement `gpt-6-luna`). On 2026-11-02 the API's model list (`GET /v1/models`) confirmed `shutdown_date` 2027-01-14 for both, and none for `gpt-6-luna`. The live agent model (`gpt-4.1-mini-2025-04-14`) is therefore deprecated. All existing captures (Milestone 1 examples, live test v1 and its label confirmations) replay offline without the API and are kept unchanged. Any new `gpt-4.1` or `gpt-4.1-mini` run, including the `gpt-4.1` baseline on the held-out test, must finish before 2027-01-14.

### Small model baseline and evaluation settings

- **Model:** `Qwen/Qwen3-4B-Instruct-2507` (revision `cdbee75f17c01a7cc42f958dc650907174af0554`, Apache-2.0) is the primary model for the untrained baseline and Milestone 3 fine-tuning; `HuggingFaceTB/SmolLM3-3B` (revision `a07cc9a04f16550a088caea529712d1d335b0ac1`, Apache-2.0) is the backup.
- **Hardware:** Kaggle T4 (16 GB).
- **Evaluation settings, identical for the untrained baseline and the fine-tuned model:** fp16 weights (T4 has no bf16); for the fine-tuned model, QLoRA adapters merged into the fp16 base before evaluation; the model's own chat template (non-thinking; for SmolLM3, reasoning off); greedy decoding (`do_sample=False`), `max_new_tokens=128`, no repetition penalty; the same prompt module as the `gpt-4.1` baseline; the output is parsed with `parse_action`, and anything unparsable is an invalid-action failure. Library versions are recorded with each run.
- **Untrained baseline run (Kaggle):** `notebooks/milestone-2/qwen_untrained_baseline.ipynb` runs `python -m packages.support_evaluator.local_model_baseline` on the same 800 validation cases as `gpt-4.1`, one generation at a time (batched fp16 decoding can differ slightly from unbatched), with the code and data packed by `scripts/build_kaggle_bundle.py` (a commit plus datasets v2 and v3, each data file checked against its committed manifest). Every call is logged with its prompt and reply tokens, whether its raw logits were finite, whether it reached the token limit, and its time; model, revision, dtype, prompt version and library versions are recorded, and a restart with different settings stops.
- **fp16 smoke test first:** 20 seeded cases (10 tier 1, 10 tier 2). It passes when every generated step's logits are finite and no reply is empty; unparsable replies are reported but count as the model's failures, not a precision failure. If it fails, the full run does not start, and any change of precision (for example fp32 across two T4s) is a protocol decision.

## Spending rules

Live budget:

- about 300 live `gpt-4.1-mini` test runs;
- a `gpt-4.1` baseline on the 800 validation cases (550 tier 1, 250 tier 2), standard API, hard cap $12 for both tiers together, with its own ledger. It runs on validation in Milestone 2 and on the held-out test only after this protocol is frozen, as the first step of Milestone 3, before the model's removal on 2027-01-14. The Batch API was not used: episodes are interactive (each probe result feeds the next call), so Batch would need one batch round per step.

Before any step that costs money, the operator is told what will run, the exact token estimate measured from real sample cases, the cost, and the hard spending cap the script enforces. Live calls are run only by the operator, never automatically.

## Open items before freezing

- dataset, split and generator hashes
- complete verb and entity list
- per-family labeling details and the results of the labelability checkpoint
- the exact metric formulas and reporting format

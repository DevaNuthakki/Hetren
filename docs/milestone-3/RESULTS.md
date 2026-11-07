# Milestone 3 results: fine-tuned diagnosis on the test splits

Results follow the frozen evaluation protocol (`docs/milestone-2/EVAL_PROTOCOL.md`, frozen 2026-11-02) and Amendment 1 (2026-11-03). Test runs #1–#6 are recorded in `docs/milestone-2/TEST_RUN_LOG.md`; training, checkpoint selection and full validation are recorded in `docs/milestone-3/VALIDATION_LOG.md`. Every declared system ran once per test set. Only checkpoint selection on validation determined the fine-tuned model; no test result changed a checkpoint, prompt, decoding setting or metric.

## Systems

| system | declared version | test runs | code | cost |
|---|---|---|---|---|
| rules v1 | `RULES_POLICY_VERSION = 1`, single recovery in both tiers | #1 | `31922b7` | $0 (offline) |
| GPT-4.1 | `gpt-4.1-2025-04-14`, prompt version 2, temperature 0, 128 output tokens | #2 | `54feb7b` (runner as of `31922b7`) | $15.63 |
| Qwen untrained | `Qwen/Qwen3-4B-Instruct-2507`, revision `cdbee75f17c01a7cc42f958dc650907174af0554`, fp16, greedy, 128 new tokens | #3, #4 | bundle `31922b7` | $0 (Kaggle) |
| Qwen fine-tuned | same base, revision, prompt and decoding; QLoRA checkpoint `0792`, adapter merged into the fp16 base | #5, #6 | bundles `8007e69`, `7238a80` (evaluation code unchanged) | $0 (Kaggle) |

All model policies receive prompt version 2 and the same compact evidence, with one stateless call per step. Qwen evaluation uses one visible Tesla T4 per process and one generation at a time. Fine-tuned selection, validation and test used Python 3.13.16, torch 2.11.0+cu130, transformers 4.56.2, accelerate 1.10.1, tokenizers 0.22.2 and peft 0.17.1. Rules v1 was built for the training families and is frozen.

## Training history

Training used only the train splits of dataset v2 (tier 1) and dataset v3 (tier 2), including contrast partners. Duplicate examples were deduplicated; 58 conflicting inputs (116 examples) were dropped. The initial file held 17,082 examples and 32,594,218 tokens. Loss applied only to assistant tokens, with Amendment 1's per-tier rare-verb weights (capped at 3).

QLoRA used a 4-bit NF4 base with double quantisation, fp16 compute, fp32 LoRA weights, rank 16, alpha 32, dropout 0.05, and all seven declared attention/MLP projections. Paged 8-bit AdamW used learning rate 1e-4, cosine decay, 3% warmup, clipping 1.0 and no weight decay; effective batch 16, sequence length 2,560 without truncation or packing, gradient checkpointing and seed 2029. The pinned training libraries included bitsandbytes 0.50.2; the custom loop did not use trl.

The train-only throughput pilot measured 337.9 tokens/s on one T4 and 638.9 on two. The faster configuration projected 14.17 hours per epoch, so the predeclared 14-hour rule kept every non-probe example and sampled probes at rate 0.9707. This retained 16,869 examples (213 probes dropped), giving 1,055 optimiser steps and candidates at 264, 528, 792 and 1,055. The last step contained five examples and divided its loss by five.

| training run | date (UTC) | steps | outcome |
|---|---|---|---|
| session 1, bundle `7e9089e` | 2026-11-03–04 | 1–528 | completed; checkpoints 264 and 528 saved |
| session 2, first attempt, same bundle | 2026-11-04 | resumed at 528; no step completed | failed on the first resumed optimiser step; paged optimiser buffers had loaded into ordinary memory |
| session 2 retry, bundle `846b0be` | 2026-11-04 | resume check 529, then training 529–1,055 | completed; paged buffers restored value for value; settings and learning-rate scale unchanged; checkpoints 792 and 1,055 saved |

No training loss was non-finite. Session 1's first optimiser update was skipped during fp16 loss-scale calibration; the scheduler and resume preserved that state. Pilot and resume-check weights were never selection candidates. Detailed times, losses, checkpoint hashes and the failed attempt remain in the validation log.

## Selection and full validation

Amendment 1 fixed the four candidates and the score before training: **S = ½(A₁ + A₂) − W**, with tier-specific decision accuracies A₁ and A₂ and the pooled wrong-intervention rate W on healthy subset runs. The subset contains 200 tier 1 and 100 tier 2 validation primaries, stratified by family with seed 2029; its lists were committed before candidate evaluation. Exact score ties favour the earlier checkpoint. Monitored rates never affect the choice.

Rates and Wilson intervals below use the four-decimal metric values and display formatting of the Milestone 2 generator. Some displayed validation percentages or interval endpoints differ by 0.1 percentage points from the manually rounded validation log; the counts, metric values and selection scores are unchanged.

### Checkpoint selection (2026-11-04)

| candidate | S | A₁ | A₂ | W (healthy, pooled) |
|---|---|---|---|---|
| Qwen untrained (existing rows) | 0.1947 | 25.5% (51/200) [20.0, 32.0] | 16.0% (16/100) [10.1, 24.4] | 1.3% (1/78) [0.2, 6.9] |
| checkpoint-0264 | 0.7206 | 86.5% (173/200) [81.1, 90.5] | 73.0% (73/100) [63.6, 80.7] | 7.7% (6/78) [3.6, 15.8] |
| checkpoint-0528 | 0.6049 | 72.5% (145/200) [65.9, 78.2] | 69.0% (69/100) [59.4, 77.2] | 10.3% (8/78) [5.3, 18.9] |
| checkpoint-0792 | 0.7322 | 72.0% (144/200) [65.4, 77.8] | 77.0% (77/100) [67.8, 84.2] | 1.3% (1/78) [0.2, 6.9] |
| checkpoint-1055 | 0.6331 | 72.0% (144/200) [65.4, 77.8] | 70.0% (70/100) [60.4, 78.1] | 7.7% (6/78) [3.6, 15.8] |

**Chosen: `checkpoint-0792`**, S = 0.7322, versus the untrained reference 0.1947. The adapter sha256 is `5647f93f25c9f79c8e7fca0468d8aa7476afbcc348f3b42f420d1845098f4226` and the checkpoint's `state.json` sha256 is `d6230ff6e1780ac5286f0accc0a45298dd8db49fc11ed6fdb1330d98189276d5`. All four candidates used the same platform, GPU type, libraries and bundle `1225d58`.

| candidate | tier 1 insufficient_evidence precision | tier 1 abstain recall | tier 2 insufficient_evidence precision | tier 2 abstain recall |
|---|---|---|---|---|
| Qwen untrained (existing rows) | 8.9% (4/45) [3.5, 20.7] | 0.0% (0/17) [0.0, 18.4] | 3.2% (1/31) [0.6, 16.2] | 0.0% (0/11) [0.0, 25.9] |
| checkpoint-0264 | 97.6% (41/42) [87.7, 99.6] | 88.2% (15/17) [65.7, 96.7] | 79.0% (15/19) [56.7, 91.5] | 63.6% (7/11) [35.4, 84.8] |
| checkpoint-0528 | 100.0% (41/41) [91.4, 100.0] | 11.8% (2/17) [3.3, 34.3] | 68.2% (15/22) [47.3, 83.6] | 36.4% (4/11) [15.2, 64.6] |
| checkpoint-0792 | 100.0% (41/41) [91.4, 100.0] | 11.8% (2/17) [3.3, 34.3] | 100.0% (15/15) [79.6, 100.0] | 100.0% (11/11) [74.1, 100.0] |
| checkpoint-1055 | 100.0% (41/41) [91.4, 100.0] | 11.8% (2/17) [3.3, 34.3] | 79.0% (15/19) [56.7, 91.5] | 63.6% (7/11) [35.4, 84.8] |

The F6 abstention risk was recorded **before any fine-tuned test run**: the chosen checkpoint's tier 1 abstain recall was 2/17 on the selection subset, against 15/17 for checkpoint 264. F6 was never used in training or validation.

### Full validation (2026-11-04; reporting only)

| tier | decision accuracy | wrong interventions | invalid actions | insufficient_evidence precision | abstain recall |
|---|---|---|---|---|---|
| 1 | 73.6% (405/550) [69.8, 77.1] | 0.0% (0/171) [0.0, 2.2] | 0.0% (0/550) [0.0, 0.7] | 100.0% (93/93) [96.0, 100.0] | 15.6% (5/32) [6.9, 31.8] |
| 2 | 76.0% (190/250) [70.3, 80.9] | 1.8% (1/54) [0.3, 9.8] | 0.0% (0/250) [0.0, 1.5] | 100.0% (31/31) [89.0, 100.0] | 96.2% (25/26) [81.1, 99.3] |

Full validation used bundle `edca36c`, reproduced all 300 selection-subset episodes exactly and did not change the choice. Selection and full-validation smoke tests passed; no generation was non-finite, empty or at the token limit.

## Findings

1. **Fine-tuning improved decision accuracy against both model baselines on every set.** In table order, fine-tuned accuracy is 73.8% (413/560), 41.5% (398/960), 71.1% (182/256), 31.2% (125/400), 66.3% (199/300). Every accuracy comparison with GPT-4.1 and untrained Qwen favours fine-tuning under the paired claim rule.
2. **Rules retain an accuracy advantage on four sets.** Tier 2 held-out accuracy has no significant difference between rules and fine-tuning. Wrong interventions favour fine-tuning over rules on both held-out sets and live; on the two in-distribution sets there is no significant difference.
3. **Across the 30 endpoint comparisons involving fine-tuning**, it is better in 16, a baseline is better in 8, and 6 have no significant difference. The full report includes the 30 baseline-only comparisons too: six system pairs × five sets × two endpoints = **60 endpoint comparisons**.
4. **Restraint did not transfer consistently.** Fine-tuning introduces wrong interventions relative to untrained Qwen, most visibly on tier 2 held-out. It has no invalid actions across the five sets, but failed recovery calls remain; valid JSON does not imply a valid or successful repair.
5. **Two-step recovery improved but remains limited.** On cases whose label needs two recoveries (tier 2 in-distribution and held-out), the fine-tuned model fixed both faults in 26.9% (7/26) and 1.1% (1/95); the baselines fixed both in rules v1 0/26 and 0/95, GPT-4.1 0/26 and 0/95, Qwen untrained 0/26 and 0/95. It stopped after the first of the two recoveries in 7/26 and 42/95 (rules v1 26/26 and 95/95, GPT-4.1 17/26 and 71/95, Qwen untrained 5/26 and 34/95; rules v1 stops after one recovery by design).
6. **Held-out transfer differs sharply by family.** F6 escalation failed, while F7 includes successful recoveries as well as correct healthy/withheld decisions. The breakdown below keeps those outcomes separate, including live F7's entirely healthy cases.

## Test results

Rates are k / n with Wilson 95% intervals. Decision metrics include undetermined cases; probe-efficiency metrics exclude them. All other metrics are secondary and descriptive. Paired differences are A − B in percentage points with paired bootstrap 95% intervals (10,000 resamples, seed 2026); lower wrong-intervention rates are better. A 'better' verdict requires the interval to exclude zero in its favour; otherwise it is 'no significant difference'. No correction for multiple comparisons is applied.

### Test sets

| test set | source | cases | healthy runs |
|---|---|---|---|
| Tier 1 in-distribution | dataset v2, splits v1 test_in_distribution | 560 | 176 |
| Tier 1 held-out | dataset v2, splits v1 test_held_out (F6/F7) | 960 | 121 |
| Tier 2 in-distribution | dataset v3, splits v2 test_in_distribution (up to two recoveries) | 256 | 45 |
| Tier 2 held-out | dataset v3, splits v2 test_held_out (F6/F7 compounds) | 400 | 56 |
| Live | live test v1 (tier 1 episodes) | 300 | 121 |

### Primary endpoints

| test set | system | decision accuracy | wrong interventions on healthy runs |
|---|---|---|---|
| Tier 1 in-distribution | rules v1 | 99.5% (557/560) [98.4, 99.8] | 0.0% (0/176) [0.0, 2.1] |
| Tier 1 in-distribution | GPT-4.1 | 33.8% (189/560) [30.0, 37.8] | 33.0% (58/176) [26.4, 40.2] |
| Tier 1 in-distribution | Qwen untrained | 30.4% (170/560) [26.7, 34.3] | 0.0% (0/176) [0.0, 2.1] |
| Tier 1 in-distribution | Qwen fine-tuned | 73.8% (413/560) [70.0, 77.2] | 0.0% (0/176) [0.0, 2.1] |
| Tier 1 held-out | rules v1 | 45.7% (439/960) [42.6, 48.9] | 100.0% (121/121) [96.9, 100.0] |
| Tier 1 held-out | GPT-4.1 | 24.8% (238/960) [22.2, 27.6] | 0.0% (0/121) [0.0, 3.1] |
| Tier 1 held-out | Qwen untrained | 14.3% (137/960) [12.2, 16.6] | 0.0% (0/121) [0.0, 3.1] |
| Tier 1 held-out | Qwen fine-tuned | 41.5% (398/960) [38.4, 44.6] | 7.4% (9/121) [4.0, 13.5] |
| Tier 2 in-distribution | rules v1 | 84.4% (216/256) [79.4, 88.3] | 2.2% (1/45) [0.4, 11.6] |
| Tier 2 in-distribution | GPT-4.1 | 17.6% (45/256) [13.4, 22.7] | 51.1% (23/45) [37.0, 65.0] |
| Tier 2 in-distribution | Qwen untrained | 13.3% (34/256) [9.7, 18.0] | 0.0% (0/45) [0.0, 7.9] |
| Tier 2 in-distribution | Qwen fine-tuned | 71.1% (182/256) [65.3, 76.3] | 4.4% (2/45) [1.2, 14.8] |
| Tier 2 held-out | rules v1 | 28.2% (113/400) [24.1, 32.9] | 92.9% (52/56) [83.0, 97.2] |
| Tier 2 held-out | GPT-4.1 | 19.2% (77/400) [15.7, 23.4] | 10.7% (6/56) [5.0, 21.5] |
| Tier 2 held-out | Qwen untrained | 15.2% (61/400) [12.1, 19.1] | 0.0% (0/56) [0.0, 6.4] |
| Tier 2 held-out | Qwen fine-tuned | 31.2% (125/400) [26.9, 35.9] | 42.9% (24/56) [30.8, 55.9] |
| Live | rules v1 | 80.3% (241/300) [75.5, 84.4] | 24.8% (30/121) [17.9, 33.2] |
| Live | GPT-4.1 | 28.0% (84/300) [23.2, 33.3] | 31.4% (38/121) [23.8, 40.1] |
| Live | Qwen untrained | 36.7% (110/300) [31.4, 42.3] | 0.0% (0/121) [0.0, 3.1] |
| Live | Qwen fine-tuned | 66.3% (199/300) [60.8, 71.4] | 0.8% (1/121) [0.1, 4.5] |

### All paired comparisons

| test set | A − B | decision accuracy: difference [95% CI] | verdict | wrong interventions: difference [95% CI] | verdict |
|---|---|---|---|---|---|
| Tier 1 in-distribution | rules v1 − GPT-4.1 | +65.7 pp [+61.8, +69.6] (n=560) | rules v1 better | -33.0 pp [-40.3, -26.1] (n=176) | rules v1 better |
| Tier 1 in-distribution | rules v1 − Qwen untrained | +69.1 pp [+65.2, +72.9] (n=560) | rules v1 better | +0.0 pp [+0.0, +0.0] (n=176) | no significant difference |
| Tier 1 in-distribution | rules v1 − Qwen fine-tuned | +25.7 pp [+22.1, +29.5] (n=560) | rules v1 better | +0.0 pp [+0.0, +0.0] (n=176) | no significant difference |
| Tier 1 in-distribution | GPT-4.1 − Qwen untrained | +3.4 pp [-0.4, +7.1] (n=560) | no significant difference | +33.0 pp [+26.1, +40.3] (n=176) | Qwen untrained better |
| Tier 1 in-distribution | GPT-4.1 − Qwen fine-tuned | -40.0 pp [-44.1, -35.9] (n=560) | Qwen fine-tuned better | +33.0 pp [+26.1, +40.3] (n=176) | Qwen fine-tuned better |
| Tier 1 in-distribution | Qwen untrained − Qwen fine-tuned | -43.4 pp [-48.2, -38.6] (n=560) | Qwen fine-tuned better | +0.0 pp [+0.0, +0.0] (n=176) | no significant difference |
| Tier 1 held-out | rules v1 − GPT-4.1 | +20.9 pp [+17.0, +25.0] (n=960) | rules v1 better | +100.0 pp [+100.0, +100.0] (n=121) | GPT-4.1 better |
| Tier 1 held-out | rules v1 − Qwen untrained | +31.5 pp [+27.1, +35.7] (n=960) | rules v1 better | +100.0 pp [+100.0, +100.0] (n=121) | Qwen untrained better |
| Tier 1 held-out | rules v1 − Qwen fine-tuned | +4.3 pp [+1.0, +7.6] (n=960) | rules v1 better | +92.6 pp [+87.6, +96.7] (n=121) | Qwen fine-tuned better |
| Tier 1 held-out | GPT-4.1 − Qwen untrained | +10.5 pp [+8.5, +12.7] (n=960) | GPT-4.1 better | +0.0 pp [+0.0, +0.0] (n=121) | no significant difference |
| Tier 1 held-out | GPT-4.1 − Qwen fine-tuned | -16.7 pp [-19.2, -14.3] (n=960) | Qwen fine-tuned better | -7.4 pp [-12.4, -3.3] (n=121) | GPT-4.1 better |
| Tier 1 held-out | Qwen untrained − Qwen fine-tuned | -27.2 pp [-30.2, -24.3] (n=960) | Qwen fine-tuned better | -7.4 pp [-12.4, -3.3] (n=121) | Qwen untrained better |
| Tier 2 in-distribution | rules v1 − GPT-4.1 | +66.8 pp [+60.9, +72.7] (n=256) | rules v1 better | -48.9 pp [-64.4, -35.6] (n=45) | rules v1 better |
| Tier 2 in-distribution | rules v1 − Qwen untrained | +71.1 pp [+65.2, +76.6] (n=256) | rules v1 better | +2.2 pp [+0.0, +6.7] (n=45) | no significant difference |
| Tier 2 in-distribution | rules v1 − Qwen fine-tuned | +13.3 pp [+8.2, +18.4] (n=256) | rules v1 better | -2.2 pp [-11.1, +4.4] (n=45) | no significant difference |
| Tier 2 in-distribution | GPT-4.1 − Qwen untrained | +4.3 pp [+0.8, +7.8] (n=256) | GPT-4.1 better | +51.1 pp [+37.8, +66.7] (n=45) | Qwen untrained better |
| Tier 2 in-distribution | GPT-4.1 − Qwen fine-tuned | -53.5 pp [-60.6, -46.1] (n=256) | Qwen fine-tuned better | +46.7 pp [+33.3, +60.0] (n=45) | Qwen fine-tuned better |
| Tier 2 in-distribution | Qwen untrained − Qwen fine-tuned | -57.8 pp [-64.5, -50.8] (n=256) | Qwen fine-tuned better | -4.4 pp [-11.1, +0.0] (n=45) | no significant difference |
| Tier 2 held-out | rules v1 − GPT-4.1 | +9.0 pp [+3.0, +15.2] (n=400) | rules v1 better | +82.1 pp [+69.6, +92.9] (n=56) | GPT-4.1 better |
| Tier 2 held-out | rules v1 − Qwen untrained | +13.0 pp [+6.8, +19.2] (n=400) | rules v1 better | +92.9 pp [+85.7, +98.2] (n=56) | Qwen untrained better |
| Tier 2 held-out | rules v1 − Qwen fine-tuned | -3.0 pp [-6.2, +0.2] (n=400) | no significant difference | +50.0 pp [+37.5, +62.5] (n=56) | Qwen fine-tuned better |
| Tier 2 held-out | GPT-4.1 − Qwen untrained | +4.0 pp [+1.0, +7.0] (n=400) | GPT-4.1 better | +10.7 pp [+3.6, +19.6] (n=56) | Qwen untrained better |
| Tier 2 held-out | GPT-4.1 − Qwen fine-tuned | -12.0 pp [-17.5, -6.5] (n=400) | Qwen fine-tuned better | -32.1 pp [-50.0, -14.3] (n=56) | GPT-4.1 better |
| Tier 2 held-out | Qwen untrained − Qwen fine-tuned | -16.0 pp [-21.0, -11.0] (n=400) | Qwen fine-tuned better | -42.9 pp [-55.4, -30.4] (n=56) | Qwen untrained better |
| Live | rules v1 − GPT-4.1 | +52.3 pp [+44.7, +59.7] (n=300) | rules v1 better | -6.6 pp [-19.8, +6.6] (n=121) | no significant difference |
| Live | rules v1 − Qwen untrained | +43.7 pp [+36.0, +51.0] (n=300) | rules v1 better | +24.8 pp [+17.4, +32.2] (n=121) | Qwen untrained better |
| Live | rules v1 − Qwen fine-tuned | +14.0 pp [+7.7, +20.3] (n=300) | rules v1 better | +24.0 pp [+16.5, +31.4] (n=121) | Qwen fine-tuned better |
| Live | GPT-4.1 − Qwen untrained | -8.7 pp [-12.0, -5.7] (n=300) | Qwen untrained better | +31.4 pp [+23.1, +39.7] (n=121) | Qwen untrained better |
| Live | GPT-4.1 − Qwen fine-tuned | -38.3 pp [-44.0, -32.7] (n=300) | Qwen fine-tuned better | +30.6 pp [+22.3, +38.8] (n=121) | Qwen fine-tuned better |
| Live | Qwen untrained − Qwen fine-tuned | -29.7 pp [-36.0, -23.3] (n=300) | Qwen fine-tuned better | -0.8 pp [-2.5, +0.0] (n=121) | no significant difference |

### Secondary decision metrics

| test set | system | exact match | verified recovery | invalid actions | failed recovery calls |
|---|---|---|---|---|---|
| Tier 1 in-distribution | rules v1 | 80.2% (449/560) [76.7, 83.3] | 100.0% (240/240) [98.4, 100.0] | 0.0% (0/560) [0.0, 0.7] | 0 |
| Tier 1 in-distribution | GPT-4.1 | 20.9% (117/560) [17.7, 24.4] | 0.4% (1/240) [0.1, 2.3] | 0.2% (1/560) [0.0, 1.0] | 3 |
| Tier 1 in-distribution | Qwen untrained | 28.0% (157/560) [24.5, 31.9] | 11.7% (28/240) [8.2, 16.3] | 22.0% (123/560) [18.7, 25.6] | 36 |
| Tier 1 in-distribution | Qwen fine-tuned | 73.8% (413/560) [70.0, 77.2] | 51.7% (124/240) [45.4, 57.9] | 0.0% (0/560) [0.0, 0.7] | 57 |
| Tier 1 held-out | rules v1 | 29.1% (279/960) [26.3, 32.0] | 100.0% (279/279) [98.6, 100.0] | 0.0% (0/960) [0.0, 0.4] | 0 |
| Tier 1 held-out | GPT-4.1 | 12.6% (121/960) [10.7, 14.8] | 0.0% (0/279) [0.0, 1.4] | 0.1% (1/960) [0.0, 0.6] | 20 |
| Tier 1 held-out | Qwen untrained | 12.6% (121/960) [10.7, 14.8] | 0.0% (0/279) [0.0, 1.4] | 10.1% (97/960) [8.3, 12.2] | 0 |
| Tier 1 held-out | Qwen fine-tuned | 41.5% (398/960) [38.4, 44.6] | 45.2% (126/279) [39.4, 51.0] | 0.0% (0/960) [0.0, 0.4] | 0 |
| Tier 2 in-distribution | rules v1 | 70.7% (181/256) [64.8, 75.9] | 72.3% (102/141) [64.4, 79.1] | 0.0% (0/256) [0.0, 1.5] | 0 |
| Tier 2 in-distribution | GPT-4.1 | 14.1% (36/256) [10.3, 18.9] | 9.9% (14/141) [6.0, 16.0] | 0.8% (2/256) [0.2, 2.8] | 0 |
| Tier 2 in-distribution | Qwen untrained | 12.5% (32/256) [9.0, 17.1] | 6.4% (9/141) [3.4, 11.7] | 26.2% (67/256) [21.2, 31.9] | 12 |
| Tier 2 in-distribution | Qwen fine-tuned | 71.1% (182/256) [65.3, 76.3] | 48.9% (69/141) [40.8, 57.1] | 0.0% (0/256) [0.0, 1.5] | 36 |
| Tier 2 held-out | rules v1 | 17.0% (68/400) [13.6, 21.0] | 19.2% (28/146) [13.6, 26.3] | 0.0% (0/400) [0.0, 0.9] | 0 |
| Tier 2 held-out | GPT-4.1 | 12.8% (51/400) [9.8, 16.4] | 1.4% (2/146) [0.4, 4.9] | 0.5% (2/400) [0.1, 1.8] | 15 |
| Tier 2 held-out | Qwen untrained | 14.8% (59/400) [11.6, 18.6] | 2.1% (3/146) [0.7, 5.9] | 18.8% (75/400) [15.2, 22.9] | 17 |
| Tier 2 held-out | Qwen fine-tuned | 31.2% (125/400) [26.9, 35.9] | 8.9% (13/146) [5.3, 14.6] | 0.0% (0/400) [0.0, 0.9] | 89 |
| Live | rules v1 | 80.3% (241/300) [75.5, 84.4] | 100.0% (135/135) [97.2, 100.0] | 0.0% (0/300) [0.0, 1.3] | 0 |
| Live | GPT-4.1 | 28.0% (84/300) [23.2, 33.3] | 0.7% (1/135) [0.1, 4.1] | 0.0% (0/300) [0.0, 1.3] | 6 |
| Live | Qwen untrained | 36.7% (110/300) [31.4, 42.3] | 11.8% (16/135) [7.4, 18.4] | 15.7% (47/300) [12.0, 20.2] | 16 |
| Live | Qwen fine-tuned | 66.3% (199/300) [60.8, 71.4] | 58.5% (79/135) [50.1, 66.5] | 0.0% (0/300) [0.0, 1.3] | 24 |

### Decision recall and precision

| test set | system | insufficient_evidence recall | insufficient_evidence precision | abstain recall | abstain precision | no_intervention recall | no_intervention precision |
|---|---|---|---|---|---|---|---|
| Tier 1 in-distribution | rules v1 | 100.0% (108/108) [96.6, 100.0] | 100.0% (108/108) [96.6, 100.0] | 91.7% (33/36) [78.2, 97.1] | 100.0% (33/33) [89.6, 100.0] | 100.0% (176/176) [97.9, 100.0] | 100.0% (176/176) [97.9, 100.0] |
| Tier 1 in-distribution | GPT-4.1 | 66.7% (72/108) [57.3, 74.9] | 53.3% (72/135) [44.9, 61.5] | 0.0% (0/36) [0.0, 9.6] | 0.0% (0/52) [0.0, 6.9] | 65.9% (116/176) [58.6, 72.5] | 47.7% (116/243) [41.5, 54.0] |
| Tier 1 in-distribution | Qwen untrained | 12.0% (13/108) [7.2, 19.5] | 10.8% (13/120) [6.4, 17.7] | 0.0% (0/36) [0.0, 9.6] | – | 73.3% (129/176) [66.3, 79.3] | 63.2% (129/204) [56.4, 69.5] |
| Tier 1 in-distribution | Qwen fine-tuned | 100.0% (108/108) [96.6, 100.0] | 100.0% (108/108) [96.6, 100.0] | 13.9% (5/36) [6.1, 28.7] | 100.0% (5/5) [56.5, 100.0] | 100.0% (176/176) [97.9, 100.0] | 74.0% (176/238) [68.0, 79.1] |
| Tier 1 held-out | rules v1 | 100.0% (160/160) [97.7, 100.0] | 100.0% (160/160) [97.7, 100.0] | 0.0% (0/400) [0.0, 0.9] | – | 0.0% (0/121) [0.0, 3.1] | – |
| Tier 1 held-out | GPT-4.1 | 73.1% (117/160) [65.8, 79.4] | 92.1% (117/127) [86.1, 95.7] | 0.0% (0/400) [0.0, 0.9] | – | 100.0% (121/121) [96.9, 100.0] | 15.1% (121/799) [12.8, 17.8] |
| Tier 1 held-out | Qwen untrained | 10.0% (16/160) [6.2, 15.6] | 94.1% (16/17) [73.0, 99.0] | 0.0% (0/400) [0.0, 0.9] | – | 100.0% (121/121) [96.9, 100.0] | 14.9% (121/812) [12.6, 17.5] |
| Tier 1 held-out | Qwen fine-tuned | 100.0% (160/160) [97.7, 100.0] | 100.0% (160/160) [97.7, 100.0] | 0.0% (0/400) [0.0, 0.9] | – | 92.6% (112/121) [86.5, 96.0] | 16.8% (112/665) [14.2, 19.9] |
| Tier 2 in-distribution | rules v1 | 100.0% (35/35) [90.1, 100.0] | 100.0% (35/35) [90.1, 100.0] | 100.0% (35/35) [90.1, 100.0] | 100.0% (35/35) [90.1, 100.0] | 97.8% (44/45) [88.4, 99.6] | 95.7% (44/46) [85.5, 98.8] |
| Tier 2 in-distribution | GPT-4.1 | 5.7% (2/35) [1.6, 18.6] | 10.5% (2/19) [2.9, 31.4] | 20.0% (7/35) [10.0, 35.9] | 33.3% (7/21) [17.2, 54.6] | 48.9% (22/45) [35.0, 63.0] | 20.4% (22/108) [13.9, 28.9] |
| Tier 2 in-distribution | Qwen untrained | 5.7% (2/35) [1.6, 18.6] | 2.6% (2/76) [0.7, 9.1] | 0.0% (0/35) [0.0, 9.9] | – | 51.1% (23/45) [37.0, 65.0] | 44.2% (23/52) [31.6, 57.7] |
| Tier 2 in-distribution | Qwen fine-tuned | 100.0% (35/35) [90.1, 100.0] | 100.0% (35/35) [90.1, 100.0] | 100.0% (35/35) [90.1, 100.0] | 100.0% (35/35) [90.1, 100.0] | 95.6% (43/45) [85.2, 98.8] | 66.1% (43/65) [54.0, 76.5] |
| Tier 2 held-out | rules v1 | 100.0% (45/45) [92.1, 100.0] | 100.0% (45/45) [92.1, 100.0] | 23.5% (36/153) [17.5, 30.9] | 100.0% (36/36) [90.4, 100.0] | 7.1% (4/56) [2.8, 17.0] | 100.0% (4/4) [51.0, 100.0] |
| Tier 2 held-out | GPT-4.1 | 13.3% (6/45) [6.3, 26.2] | 18.8% (6/32) [8.9, 35.3] | 12.4% (19/153) [8.1, 18.6] | 73.1% (19/26) [53.9, 86.3] | 89.3% (50/56) [78.5, 95.0] | 33.3% (50/150) [26.3, 41.2] |
| Tier 2 held-out | Qwen untrained | 4.4% (2/45) [1.2, 14.8] | 2.4% (2/84) [0.7, 8.3] | 0.0% (0/153) [0.0, 2.5] | – | 100.0% (56/56) [93.6, 100.0] | 45.2% (56/124) [36.7, 53.9] |
| Tier 2 held-out | Qwen fine-tuned | 100.0% (45/45) [92.1, 100.0] | 97.8% (45/46) [88.7, 99.6] | 22.9% (35/153) [16.9, 30.1] | 100.0% (35/35) [90.1, 100.0] | 57.1% (32/56) [44.1, 69.2] | 36.4% (32/88) [27.1, 46.8] |
| Live | rules v1 | – | – | 34.1% (15/44) [21.9, 48.9] | 100.0% (15/15) [79.6, 100.0] | 75.2% (91/121) [66.8, 82.0] | 100.0% (91/91) [96.0, 100.0] |
| Live | GPT-4.1 | – | 0.0% (0/36) [0.0, 9.6] | 0.0% (0/44) [0.0, 8.0] | 0.0% (0/25) [0.0, 13.3] | 68.6% (83/121) [59.9, 76.2] | 50.3% (83/165) [42.8, 57.8] |
| Live | Qwen untrained | – | 0.0% (0/57) [0.0, 6.3] | 0.0% (0/44) [0.0, 8.0] | – | 77.7% (94/121) [69.5, 84.2] | 60.7% (94/155) [52.8, 68.0] |
| Live | Qwen fine-tuned | – | – | 0.0% (0/44) [0.0, 8.0] | – | 99.2% (120/121) [95.5, 99.9] | 66.3% (120/181) [59.1, 72.8] |

### Probe efficiency

| test set | system | mean probes | healthy mean | oracle mean | mean excess | budget exceeded | undetermined |
|---|---|---|---|---|---|---|---|
| Tier 1 in-distribution | rules v1 | 1.413 | 2.301 | 0.655 | 0.757 | 0.0% (0/560) [0.0, 0.7] | 0 |
| Tier 1 in-distribution | GPT-4.1 | 0.5 | 0.278 | 0.655 | -0.155 | 0.0% (0/560) [0.0, 0.7] | 0 |
| Tier 1 in-distribution | Qwen untrained | 1.007 | 0.125 | 0.655 | 0.352 | 5.0% (28/560) [3.5, 7.1] | 0 |
| Tier 1 in-distribution | Qwen fine-tuned | 0.368 | 0.574 | 0.655 | -0.287 | 0.0% (0/560) [0.0, 0.7] | 0 |
| Tier 1 held-out | rules v1 | 1.667 | 2.0 | 0.417 | 1.25 | 0.0% (0/960) [0.0, 0.4] | 0 |
| Tier 1 held-out | GPT-4.1 | 0.065 | 0.0 | 0.417 | -0.352 | 0.0% (0/960) [0.0, 0.4] | 0 |
| Tier 1 held-out | Qwen untrained | 0.344 | 0.0 | 0.417 | -0.073 | 0.8% (8/960) [0.4, 1.6] | 0 |
| Tier 1 held-out | Qwen fine-tuned | 0.976 | 0.752 | 0.417 | 0.559 | 0.0% (0/960) [0.0, 0.4] | 0 |
| Tier 2 in-distribution | rules v1 | 1.399 | 2.467 | 1.44 | -0.04 | 0.0% (0/256) [0.0, 1.5] | 8 |
| Tier 2 in-distribution | GPT-4.1 | 1.246 | 0.6 | 1.44 | -0.194 | 0.4% (1/256) [0.1, 2.2] | 8 |
| Tier 2 in-distribution | Qwen untrained | 1.383 | 0.556 | 1.44 | -0.056 | 10.5% (27/256) [7.3, 14.9] | 8 |
| Tier 2 in-distribution | Qwen fine-tuned | 1.181 | 1.156 | 1.44 | -0.258 | 0.0% (0/256) [0.0, 1.5] | 8 |
| Tier 2 held-out | rules v1 | 1.357 | 2.0 | 1.515 | -0.158 | 0.0% (0/400) [0.0, 0.9] | 8 |
| Tier 2 held-out | GPT-4.1 | 1.459 | 0.232 | 1.515 | -0.056 | 0.8% (3/400) [0.3, 2.2] | 8 |
| Tier 2 held-out | Qwen untrained | 1.367 | 0.0 | 1.515 | -0.148 | 10.5% (42/400) [7.9, 13.9] | 8 |
| Tier 2 held-out | Qwen fine-tuned | 1.426 | 1.375 | 1.515 | -0.089 | 0.0% (0/400) [0.0, 0.9] | 8 |
| Live | rules v1 | 1.729 | 2.288 | 0.755 | 0.975 | 0.0% (0/300) [0.0, 1.3] | 23 |
| Live | GPT-4.1 | 0.491 | 0.308 | 0.755 | -0.264 | 0.0% (0/300) [0.0, 1.3] | 23 |
| Live | Qwen untrained | 0.711 | 0.048 | 0.755 | -0.043 | 3.0% (9/300) [1.6, 5.6] | 23 |
| Live | Qwen fine-tuned | 0.484 | 0.587 | 0.755 | -0.271 | 0.0% (0/300) [0.0, 1.3] | 23 |

### Tier 2 sequence metrics

| test set | system | exact sequence match | longer than label | stopped after one of two | two-recovery labels |
|---|---|---|---|---|---|
| Tier 2 in-distribution | rules v1 | 70.7% (181/256) [64.8, 75.9] | 0.0% (0/141) [0.0, 2.6] | 100.0% (26/26) [87.1, 100.0] | 0.0% (0/26) [0.0, 12.9] |
| Tier 2 in-distribution | GPT-4.1 | 14.1% (36/256) [10.3, 18.9] | 0.0% (0/141) [0.0, 2.6] | 65.4% (17/26) [46.2, 80.6] | 0.0% (0/26) [0.0, 12.9] |
| Tier 2 in-distribution | Qwen untrained | 12.5% (32/256) [9.0, 17.1] | 0.0% (0/141) [0.0, 2.6] | 19.2% (5/26) [8.5, 37.9] | 0.0% (0/26) [0.0, 12.9] |
| Tier 2 in-distribution | Qwen fine-tuned | 71.1% (182/256) [65.3, 76.3] | 0.0% (0/141) [0.0, 2.6] | 26.9% (7/26) [13.7, 46.1] | 26.9% (7/26) [13.7, 46.1] |
| Tier 2 held-out | rules v1 | 17.0% (68/400) [13.6, 21.0] | 0.0% (0/146) [0.0, 2.6] | 100.0% (95/95) [96.1, 100.0] | 0.0% (0/95) [0.0, 3.9] |
| Tier 2 held-out | GPT-4.1 | 12.8% (51/400) [9.8, 16.4] | 0.7% (1/146) [0.1, 3.8] | 74.7% (71/95) [65.2, 82.4] | 0.0% (0/95) [0.0, 3.9] |
| Tier 2 held-out | Qwen untrained | 14.8% (59/400) [11.6, 18.6] | 0.0% (0/146) [0.0, 2.6] | 35.8% (34/95) [26.9, 45.8] | 0.0% (0/95) [0.0, 3.9] |
| Tier 2 held-out | Qwen fine-tuned | 31.2% (125/400) [26.9, 35.9] | 0.0% (0/146) [0.0, 2.6] | 44.2% (42/95) [34.6, 54.2] | 1.1% (1/95) [0.2, 5.7] |

### Groups and slices (decision accuracy)

| test set | system | training families | held-out families | proactive detection | compound slice | compound pairs | recent-target faulty | length-reweighted |
|---|---|---|---|---|---|---|---|---|
| Tier 1 in-distribution | rules v1 | 99.5% (557/560) [98.4, 99.8] | – | 96.0% (71/74) [88.8, 98.6] | 0.0% (0/3) [0.0, 56.1] | – | 99.1% (107/108) [94.9, 99.8] | 97.6% |
| Tier 1 in-distribution | GPT-4.1 | 33.8% (189/560) [30.0, 37.8] | – | 8.1% (6/74) [3.8, 16.6] | 0.0% (0/3) [0.0, 56.1] | – | 16.7% (18/108) [10.8, 24.8] | 31.6% |
| Tier 1 in-distribution | Qwen untrained | 30.4% (170/560) [26.7, 34.3] | – | 5.4% (4/74) [2.1, 13.1] | 0.0% (0/3) [0.0, 56.1] | – | 7.4% (8/108) [3.8, 13.9] | 24.4% |
| Tier 1 in-distribution | Qwen fine-tuned | 73.8% (413/560) [70.0, 77.2] | – | 32.4% (24/74) [22.9, 43.7] | 0.0% (0/3) [0.0, 56.1] | – | 74.1% (80/108) [65.1, 81.4] | 70.1% |
| Tier 1 held-out | rules v1 | – | 45.7% (439/960) [42.6, 48.9] | 16.7% (80/480) [13.6, 20.3] | – | – | 54.3% (140/258) [48.2, 60.2] | 33.0% |
| Tier 1 held-out | GPT-4.1 | – | 24.8% (238/960) [22.2, 27.6] | 10.0% (48/480) [7.6, 13.0] | – | – | 14.7% (38/258) [10.9, 19.6] | 22.4% |
| Tier 1 held-out | Qwen untrained | – | 14.3% (137/960) [12.2, 16.6] | 2.3% (11/480) [1.3, 4.1] | – | – | 1.6% (4/258) [0.6, 3.9] | 16.5% |
| Tier 1 held-out | Qwen fine-tuned | – | 41.5% (398/960) [38.4, 44.6] | 16.7% (80/480) [13.6, 20.3] | – | – | 35.7% (92/258) [30.1, 41.7] | 31.3% |
| Tier 2 in-distribution | rules v1 | 84.4% (216/256) [79.4, 88.3] | – | 91.7% (11/12) [64.6, 98.5] | 69.7% (23/33) [52.7, 82.6] | 76.2% (125/164) [69.2, 82.1] | 82.3% (56/68) [71.6, 89.6] | 78.0% |
| Tier 2 in-distribution | GPT-4.1 | 17.6% (45/256) [13.4, 22.7] | – | 0.0% (0/12) [0.0, 24.2] | 27.3% (9/33) [15.1, 44.2] | 15.8% (26/164) [11.1, 22.2] | 2.9% (2/68) [0.8, 10.1] | 14.4% |
| Tier 2 in-distribution | Qwen untrained | 13.3% (34/256) [9.7, 18.0] | – | 0.0% (0/12) [0.0, 24.2] | 3.0% (1/33) [0.5, 15.3] | 8.5% (14/164) [5.1, 13.8] | 1.5% (1/68) [0.3, 7.9] | 11.4% |
| Tier 2 in-distribution | Qwen fine-tuned | 71.1% (182/256) [65.3, 76.3] | – | 75.0% (9/12) [46.8, 91.1] | 63.6% (21/33) [46.6, 77.8] | 65.8% (108/164) [58.3, 72.7] | 64.7% (44/68) [52.8, 75.0] | 64.8% |
| Tier 2 held-out | rules v1 | – | 28.2% (113/400) [24.1, 32.9] | – | 16.2% (28/173) [11.4, 22.4] | 28.2% (113/400) [24.1, 32.9] | 42.6% (29/68) [31.6, 54.5] | 22.2% |
| Tier 2 held-out | GPT-4.1 | – | 19.2% (77/400) [15.7, 23.4] | – | 11.6% (20/173) [7.6, 17.2] | 19.2% (77/400) [15.7, 23.4] | 2.9% (2/68) [0.8, 10.1] | 13.0% |
| Tier 2 held-out | Qwen untrained | – | 15.2% (61/400) [12.1, 19.1] | – | 1.7% (3/173) [0.6, 5.0] | 15.2% (61/400) [12.1, 19.1] | 0.0% (0/68) [0.0, 5.3] | 7.9% |
| Tier 2 held-out | Qwen fine-tuned | – | 31.2% (125/400) [26.9, 35.9] | – | 6.9% (12/173) [4.0, 11.7] | 31.2% (125/400) [26.9, 35.9] | 35.3% (24/68) [25.0, 47.2] | 24.1% |
| Live | rules v1 | 100.0% (240/240) [98.4, 100.0] | 1.7% (1/60) [0.3, 8.9] | 51.7% (31/60) [39.3, 63.8] | – | – | – | – |
| Live | GPT-4.1 | 22.1% (53/240) [17.3, 27.8] | 51.7% (31/60) [39.3, 63.8] | 1.7% (1/60) [0.3, 8.9] | – | – | – | – |
| Live | Qwen untrained | 32.9% (79/240) [27.3, 39.1] | 51.7% (31/60) [39.3, 63.8] | 1.7% (1/60) [0.3, 8.9] | – | – | – | – |
| Live | Qwen fine-tuned | 70.4% (169/240) [64.4, 75.8] | 50.0% (30/60) [37.7, 62.3] | 15.0% (9/60) [8.1, 26.1] | – | – | – | – |

### Live split by label category (decision accuracy)

| system | final_label_only | live_confirmed_target | proxy_matched |
|---|---|---|---|
| rules v1 | 5.9% (1/17) [1.1, 27.0] | 100.0% (6/6) [61.0, 100.0] | 84.5% (234/277) [79.7, 88.3] |
| GPT-4.1 | 100.0% (17/17) [81.6, 100.0] | 0.0% (0/6) [0.0, 39.0] | 24.2% (67/277) [19.5, 29.6] |
| Qwen untrained | 100.0% (17/17) [81.6, 100.0] | 16.7% (1/6) [3.0, 56.4] | 33.2% (92/277) [27.9, 39.0] |
| Qwen fine-tuned | 94.1% (16/17) [73.0, 99.0] | 0.0% (0/6) [0.0, 39.0] | 66.1% (183/277) [60.3, 71.4] |

### Per family: Tier 1 in-distribution

| family | held out | rules v1 | GPT-4.1 | Qwen untrained | Qwen fine-tuned |
|---|---|---|---|---|---|
| `mapping_swap` | no | 100.0% (63/63) [94.2, 100.0] | 14.3% (9/63) [7.7, 25.0] | 3.2% (2/63) [0.9, 10.9] | 87.3% (55/63) [76.9, 93.4] |
| `merged_account` | no | 100.0% (74/74) [95.1, 100.0] | 5.4% (4/74) [2.1, 13.1] | 16.2% (12/74) [9.5, 26.2] | 91.9% (68/74) [83.4, 96.2] |
| `mishandled_tool_error` | no | 100.0% (70/70) [94.8, 100.0] | 22.9% (16/70) [14.6, 34.0] | 4.3% (3/70) [1.5, 11.9] | 60.0% (42/70) [48.3, 70.7] |
| `misleading_ticket_text` | no | 100.0% (59/59) [93.9, 100.0] | 78.0% (46/59) [65.9, 86.7] | 74.6% (44/59) [62.2, 83.9] | 93.2% (55/59) [83.8, 97.3] |
| `missing_account` | no | 100.0% (76/76) [95.2, 100.0] | 19.7% (15/76) [12.3, 30.0] | 32.9% (25/76) [23.4, 44.1] | 32.9% (25/76) [23.4, 44.1] |
| `recent_tier_change` | no | 100.0% (74/74) [95.1, 100.0] | 90.5% (67/74) [81.7, 95.3] | 86.5% (64/74) [76.9, 92.5] | 100.0% (74/74) [95.1, 100.0] |
| `stale_account_record` | no | 96.0% (71/74) [88.8, 98.6] | 8.1% (6/74) [3.8, 16.6] | 5.4% (4/74) [2.1, 13.1] | 32.4% (24/74) [22.9, 43.7] |
| `transient_error_retried` | no | 100.0% (70/70) [94.8, 100.0] | 37.1% (26/70) [26.8, 48.9] | 22.9% (16/70) [14.6, 34.0] | 100.0% (70/70) [94.8, 100.0] |

### Per family: Tier 1 held-out

| family | held out | rules v1 | GPT-4.1 | Qwen untrained | Qwen fine-tuned |
|---|---|---|---|---|---|
| `queue_misconfiguration` | yes | 16.7% (80/480) [13.6, 20.3] | 10.0% (48/480) [7.6, 13.0] | 2.3% (11/480) [1.3, 4.1] | 16.7% (80/480) [13.6, 20.3] |
| `tier_format_drift` | yes | 74.8% (359/480) [70.7, 78.5] | 39.6% (190/480) [35.3, 44.0] | 26.2% (126/480) [22.5, 30.4] | 66.2% (318/480) [61.9, 70.3] |

### Per family: Tier 2 in-distribution

| family | held out | rules v1 | GPT-4.1 | Qwen untrained | Qwen fine-tuned |
|---|---|---|---|---|---|
| `compound:mapping_swap+merged_account` | no | 100.0% (4/4) [51.0, 100.0] | 0.0% (0/4) [0.0, 49.0] | 0.0% (0/4) [0.0, 49.0] | 100.0% (4/4) [51.0, 100.0] |
| `compound:mapping_swap+mishandled_tool_error` | no | 25.0% (1/4) [4.6, 69.9] | 0.0% (0/4) [0.0, 49.0] | 0.0% (0/4) [0.0, 49.0] | 50.0% (2/4) [15.0, 85.0] |
| `compound:mapping_swap+misleading_ticket_text` | no | 88.9% (8/9) [56.5, 98.0] | 0.0% (0/9) [0.0, 29.9] | 0.0% (0/9) [0.0, 29.9] | 66.7% (6/9) [35.4, 87.9] |
| `compound:mapping_swap+missing_account` | no | 0.0% (0/5) [0.0, 43.5] | 0.0% (0/5) [0.0, 43.5] | 0.0% (0/5) [0.0, 43.5] | 0.0% (0/5) [0.0, 43.5] |
| `compound:mapping_swap+recent_tier_change` | no | 100.0% (5/5) [56.5, 100.0] | 40.0% (2/5) [11.8, 76.9] | 0.0% (0/5) [0.0, 43.5] | 80.0% (4/5) [37.5, 96.4] |
| `compound:mapping_swap+stale_account_record` | no | 12.5% (1/8) [2.2, 47.1] | 0.0% (0/8) [0.0, 32.4] | 0.0% (0/8) [0.0, 32.4] | 25.0% (2/8) [7.1, 59.1] |
| `compound:mapping_swap+transient_error_retried` | no | 28.6% (2/7) [8.2, 64.1] | 0.0% (0/7) [0.0, 35.4] | 0.0% (0/7) [0.0, 35.4] | 71.4% (5/7) [35.9, 91.8] |
| `compound:mishandled_tool_error+merged_account` | no | 100.0% (6/6) [61.0, 100.0] | 0.0% (0/6) [0.0, 39.0] | 0.0% (0/6) [0.0, 39.0] | 100.0% (6/6) [61.0, 100.0] |
| `compound:mishandled_tool_error+misleading_ticket_text` | no | 80.0% (4/5) [37.5, 96.4] | 20.0% (1/5) [3.6, 62.5] | 20.0% (1/5) [3.6, 62.5] | 80.0% (4/5) [37.5, 96.4] |
| `compound:mishandled_tool_error+missing_account` | no | 83.3% (5/6) [43.6, 97.0] | 50.0% (3/6) [18.8, 81.2] | 0.0% (0/6) [0.0, 39.0] | 83.3% (5/6) [43.6, 97.0] |
| `compound:mishandled_tool_error+recent_tier_change` | no | 100.0% (8/8) [67.6, 100.0] | 0.0% (0/8) [0.0, 32.4] | 0.0% (0/8) [0.0, 32.4] | 100.0% (8/8) [67.6, 100.0] |
| `compound:mishandled_tool_error+transient_error_retried` | no | 90.9% (10/11) [62.3, 98.4] | 9.1% (1/11) [1.6, 37.7] | 0.0% (0/11) [0.0, 25.9] | 90.9% (10/11) [62.3, 98.4] |
| `compound:misleading_ticket_text+merged_account` | no | 100.0% (4/4) [51.0, 100.0] | 0.0% (0/4) [0.0, 49.0] | 0.0% (0/4) [0.0, 49.0] | 75.0% (3/4) [30.1, 95.4] |
| `compound:misleading_ticket_text+missing_account` | no | 100.0% (5/5) [56.5, 100.0] | 40.0% (2/5) [11.8, 76.9] | 20.0% (1/5) [3.6, 62.5] | 60.0% (3/5) [23.1, 88.2] |
| `compound:misleading_ticket_text+recent_tier_change` | no | 100.0% (7/7) [64.6, 100.0] | 71.4% (5/7) [35.9, 91.8] | 71.4% (5/7) [35.9, 91.8] | 71.4% (5/7) [35.9, 91.8] |
| `compound:misleading_ticket_text+transient_error_retried` | no | 88.9% (8/9) [56.5, 98.0] | 22.2% (2/9) [6.3, 54.7] | 11.1% (1/9) [2.0, 43.5] | 88.9% (8/9) [56.5, 98.0] |
| `compound:missing_account+merged_account` | no | 100.0% (6/6) [61.0, 100.0] | 0.0% (0/6) [0.0, 39.0] | 0.0% (0/6) [0.0, 39.0] | 83.3% (5/6) [43.6, 97.0] |
| `compound:missing_account+recent_tier_change` | no | 100.0% (6/6) [61.0, 100.0] | 50.0% (3/6) [18.8, 81.2] | 50.0% (3/6) [18.8, 81.2] | 33.3% (2/6) [9.7, 70.0] |
| `compound:missing_account+transient_error_retried` | no | 60.0% (6/10) [31.3, 83.2] | 60.0% (6/10) [31.3, 83.2] | 10.0% (1/10) [1.8, 40.4] | 40.0% (4/10) [16.8, 68.7] |
| `compound:stale_account_record+merged_account` | no | 83.3% (5/6) [43.6, 97.0] | 0.0% (0/6) [0.0, 39.0] | 0.0% (0/6) [0.0, 39.0] | 100.0% (6/6) [61.0, 100.0] |
| `compound:stale_account_record+mishandled_tool_error` | no | 100.0% (5/5) [56.5, 100.0] | 0.0% (0/5) [0.0, 43.5] | 20.0% (1/5) [3.6, 62.5] | 100.0% (5/5) [56.5, 100.0] |
| `compound:stale_account_record+misleading_ticket_text` | no | 75.0% (6/8) [40.9, 92.8] | 12.5% (1/8) [2.2, 47.1] | 12.5% (1/8) [2.2, 47.1] | 25.0% (2/8) [7.1, 59.1] |
| `compound:stale_account_record+missing_account` | no | 50.0% (2/4) [15.0, 85.0] | 0.0% (0/4) [0.0, 49.0] | 0.0% (0/4) [0.0, 49.0] | 50.0% (2/4) [15.0, 85.0] |
| `compound:stale_account_record+recent_tier_change` | no | 100.0% (5/5) [56.5, 100.0] | 0.0% (0/5) [0.0, 43.5] | 0.0% (0/5) [0.0, 43.5] | 100.0% (5/5) [56.5, 100.0] |
| `compound:stale_account_record+transient_error_retried` | no | 54.5% (6/11) [28.0, 78.7] | 0.0% (0/11) [0.0, 25.9] | 0.0% (0/11) [0.0, 25.9] | 18.2% (2/11) [5.1, 47.7] |
| `mapping_swap` | no | 100.0% (10/10) [72.2, 100.0] | 0.0% (0/10) [0.0, 27.8] | 0.0% (0/10) [0.0, 27.8] | 40.0% (4/10) [16.8, 68.7] |
| `merged_account` | no | 100.0% (11/11) [74.1, 100.0] | 0.0% (0/11) [0.0, 25.9] | 0.0% (0/11) [0.0, 25.9] | 72.7% (8/11) [43.4, 90.2] |
| `mishandled_tool_error` | no | 100.0% (17/17) [81.6, 100.0] | 17.6% (3/17) [6.2, 41.0] | 17.6% (3/17) [6.2, 41.0] | 100.0% (17/17) [81.6, 100.0] |
| `misleading_ticket_text` | no | 100.0% (9/9) [70.1, 100.0] | 44.4% (4/9) [18.9, 73.3] | 55.6% (5/9) [26.7, 81.1] | 88.9% (8/9) [56.5, 98.0] |
| `missing_account` | no | 100.0% (11/11) [74.1, 100.0] | 36.4% (4/11) [15.2, 64.6] | 27.3% (3/11) [9.8, 56.6] | 54.5% (6/11) [28.0, 78.7] |
| `recent_tier_change` | no | 100.0% (12/12) [75.8, 100.0] | 58.3% (7/12) [31.9, 80.7] | 66.7% (8/12) [39.1, 86.2] | 100.0% (12/12) [75.8, 100.0] |
| `stale_account_record` | no | 91.7% (11/12) [64.6, 98.5] | 0.0% (0/12) [0.0, 24.2] | 0.0% (0/12) [0.0, 24.2] | 75.0% (9/12) [46.8, 91.1] |
| `transient_error_retried` | no | 100.0% (10/10) [72.2, 100.0] | 10.0% (1/10) [1.8, 40.4] | 10.0% (1/10) [1.8, 40.4] | 100.0% (10/10) [72.2, 100.0] |

### Per family: Tier 2 held-out

| family | held out | rules v1 | GPT-4.1 | Qwen untrained | Qwen fine-tuned |
|---|---|---|---|---|---|
| `compound:mapping_swap+queue_misconfiguration` | yes | 12.5% (5/40) [5.5, 26.1] | 0.0% (0/40) [0.0, 8.8] | 2.5% (1/40) [0.4, 12.9] | 12.5% (5/40) [5.5, 26.1] |
| `compound:mapping_swap+tier_format_drift` | yes | 10.0% (5/50) [4.3, 21.4] | 0.0% (0/50) [0.0, 7.1] | 2.0% (1/50) [0.4, 10.5] | 12.0% (6/50) [5.6, 23.8] |
| `compound:mishandled_tool_error+queue_misconfiguration` | yes | 60.0% (24/40) [44.6, 73.7] | 5.0% (2/40) [1.4, 16.5] | 0.0% (0/40) [0.0, 8.8] | 60.0% (24/40) [44.6, 73.7] |
| `compound:mishandled_tool_error+tier_format_drift` | yes | 50.0% (25/50) [36.6, 63.4] | 6.0% (3/50) [2.1, 16.2] | 10.0% (5/50) [4.3, 21.4] | 46.0% (23/50) [33.0, 59.6] |
| `compound:misleading_ticket_text+queue_misconfiguration` | yes | 22.5% (9/40) [12.3, 37.5] | 10.0% (4/40) [4.0, 23.1] | 10.0% (4/40) [4.0, 23.1] | 22.5% (9/40) [12.3, 37.5] |
| `compound:misleading_ticket_text+tier_format_drift` | yes | 60.0% (30/50) [46.2, 72.4] | 34.0% (17/50) [22.4, 47.9] | 30.0% (15/50) [19.1, 43.8] | 64.0% (32/50) [50.1, 75.9] |
| `compound:missing_account+queue_misconfiguration` | yes | 12.5% (5/40) [5.5, 26.1] | 47.5% (19/40) [32.9, 62.5] | 0.0% (0/40) [0.0, 8.8] | 12.5% (5/40) [5.5, 26.1] |
| `compound:missing_account+tier_format_drift` | yes | 10.0% (5/50) [4.3, 21.4] | 2.0% (1/50) [0.4, 10.5] | 0.0% (0/50) [0.0, 7.1] | 10.0% (5/50) [4.3, 21.4] |
| `compound:stale_account_record+queue_misconfiguration` | yes | 12.5% (5/40) [5.5, 26.1] | 77.5% (31/40) [62.5, 87.7] | 87.5% (35/40) [73.9, 94.5] | 40.0% (16/40) [26.4, 55.4] |

### Per family: Live

| family | held out | rules v1 | GPT-4.1 | Qwen untrained | Qwen fine-tuned |
|---|---|---|---|---|---|
| `mapping_swap` | no | 100.0% (30/30) [88.6, 100.0] | 0.0% (0/30) [0.0, 11.3] | 0.0% (0/30) [0.0, 11.3] | 66.7% (20/30) [48.8, 80.8] |
| `merged_account` | no | 100.0% (30/30) [88.6, 100.0] | 0.0% (0/30) [0.0, 11.3] | 10.0% (3/30) [3.5, 25.6] | 100.0% (30/30) [88.6, 100.0] |
| `mishandled_tool_error` | no | 100.0% (30/30) [88.6, 100.0] | 0.0% (0/30) [0.0, 11.3] | 0.0% (0/30) [0.0, 11.3] | 50.0% (15/30) [33.1, 66.8] |
| `misleading_ticket_text` | no | 100.0% (30/30) [88.6, 100.0] | 73.3% (22/30) [55.5, 85.8] | 100.0% (30/30) [88.6, 100.0] | 100.0% (30/30) [88.6, 100.0] |
| `missing_account` | no | 100.0% (30/30) [88.6, 100.0] | 3.3% (1/30) [0.6, 16.7] | 46.7% (14/30) [30.2, 63.9] | 20.0% (6/30) [9.5, 37.3] |
| `recent_tier_change` | no | 100.0% (30/30) [88.6, 100.0] | 100.0% (30/30) [88.6, 100.0] | 100.0% (30/30) [88.6, 100.0] | 100.0% (30/30) [88.6, 100.0] |
| `stale_account_record` | no | 100.0% (30/30) [88.6, 100.0] | 0.0% (0/30) [0.0, 11.3] | 0.0% (0/30) [0.0, 11.3] | 26.7% (8/30) [14.2, 44.5] |
| `transient_error_retried` | no | 100.0% (30/30) [88.6, 100.0] | 0.0% (0/30) [0.0, 11.3] | 6.7% (2/30) [1.8, 21.3] | 100.0% (30/30) [88.6, 100.0] |
| `queue_misconfiguration` | yes | 3.3% (1/30) [0.6, 16.7] | 3.3% (1/30) [0.6, 16.7] | 3.3% (1/30) [0.6, 16.7] | 3.3% (1/30) [0.6, 16.7] |
| `tier_format_drift` | yes | 0.0% (0/30) [0.0, 11.3] | 100.0% (30/30) [88.6, 100.0] | 100.0% (30/30) [88.6, 100.0] | 96.7% (29/30) [83.3, 99.4] |

## F6 and F7: held-out findings

The F6/F7 rows below are tier 1 single-family cases and live cases. Tier 2 contains compounds, whose pair-level accuracies are reported above. 'Recovery' below counts cases labelled with a recovery, not all family cases; the healthy and withheld columns use their own label denominators.

| test set | family | system | decision accuracy | abstain recall | verified recovery | healthy recall | withheld recall |
|---|---|---|---|---|---|---|---|
| Tier 1 held-out | queue_misconfiguration | rules v1 | 16.7% (80/480) [13.6, 20.3] | 0.0% (0/400) [0.0, 0.9] | – | – | 100.0% (80/80) [95.4, 100.0] |
| Tier 1 held-out | queue_misconfiguration | GPT-4.1 | 10.0% (48/480) [7.6, 13.0] | 0.0% (0/400) [0.0, 0.9] | – | – | 60.0% (48/80) [49.0, 70.0] |
| Tier 1 held-out | queue_misconfiguration | Qwen untrained | 2.3% (11/480) [1.3, 4.1] | 0.0% (0/400) [0.0, 0.9] | – | – | 13.8% (11/80) [7.8, 23.0] |
| Tier 1 held-out | queue_misconfiguration | Qwen fine-tuned | 16.7% (80/480) [13.6, 20.3] | 0.0% (0/400) [0.0, 0.9] | – | – | 100.0% (80/80) [95.4, 100.0] |
| Tier 1 held-out | tier_format_drift | rules v1 | 74.8% (359/480) [70.7, 78.5] | – | 100.0% (279/279) [98.6, 100.0] | 0.0% (0/121) [0.0, 3.1] | 100.0% (80/80) [95.4, 100.0] |
| Tier 1 held-out | tier_format_drift | GPT-4.1 | 39.6% (190/480) [35.3, 44.0] | – | 0.0% (0/279) [0.0, 1.4] | 100.0% (121/121) [96.9, 100.0] | 86.2% (69/80) [77.0, 92.2] |
| Tier 1 held-out | tier_format_drift | Qwen untrained | 26.2% (126/480) [22.5, 30.4] | – | 0.0% (0/279) [0.0, 1.4] | 100.0% (121/121) [96.9, 100.0] | 6.2% (5/80) [2.7, 13.8] |
| Tier 1 held-out | tier_format_drift | Qwen fine-tuned | 66.2% (318/480) [61.9, 70.3] | – | 45.2% (126/279) [39.4, 51.0] | 92.6% (112/121) [86.5, 96.0] | 100.0% (80/80) [95.4, 100.0] |
| Live | queue_misconfiguration | rules v1 | 3.3% (1/30) [0.6, 16.7] | 0.0% (0/29) [0.0, 11.7] | – | 100.0% (1/1) [20.6, 100.0] | – |
| Live | queue_misconfiguration | GPT-4.1 | 3.3% (1/30) [0.6, 16.7] | 0.0% (0/29) [0.0, 11.7] | – | 100.0% (1/1) [20.6, 100.0] | – |
| Live | queue_misconfiguration | Qwen untrained | 3.3% (1/30) [0.6, 16.7] | 0.0% (0/29) [0.0, 11.7] | – | 100.0% (1/1) [20.6, 100.0] | – |
| Live | queue_misconfiguration | Qwen fine-tuned | 3.3% (1/30) [0.6, 16.7] | 0.0% (0/29) [0.0, 11.7] | – | 100.0% (1/1) [20.6, 100.0] | – |
| Live | tier_format_drift | rules v1 | 0.0% (0/30) [0.0, 11.3] | – | – | 0.0% (0/30) [0.0, 11.3] | – |
| Live | tier_format_drift | GPT-4.1 | 100.0% (30/30) [88.6, 100.0] | – | – | 100.0% (30/30) [88.6, 100.0] | – |
| Live | tier_format_drift | Qwen untrained | 100.0% (30/30) [88.6, 100.0] | – | – | 100.0% (30/30) [88.6, 100.0] | – |
| Live | tier_format_drift | Qwen fine-tuned | 96.7% (29/30) [83.3, 99.4] | – | – | 96.7% (29/30) [83.3, 99.4] | – |

**F6:** fine-tuned abstain recall is 0.0% (0/400) [0.0, 0.9]. The pre-test risk materialized: complete-evidence F6 escalation was never correct. Withheld-evidence decisions contribute to family accuracy without showing successful escalation. Live F6 has 29 abstain labels and one healthy run; live abstain recall over all families is 0/44.

**F7:** fine-tuned family accuracy is 66.2% (318/480) [61.9, 70.3], while verified recovery on the repair-labelled cases is 45.2% (126/279) [39.4, 51.0]. Family accuracy also includes healthy and withheld-evidence decisions. On live F7 the fine-tuned model scores 29/30; **all 30 are healthy**, and both model baselines already score 30/30. Live F7 demonstrates correct non-intervention in most cases, not new evidence of successful repair.

### Held-out variants (decision accuracy)

| test set | family | variant | rules v1 | GPT-4.1 | Qwen untrained | Qwen fine-tuned |
|---|---|---|---|---|---|---|
| Tier 1 held-out | queue_misconfiguration | description_swap | 16.7% (80/480) [13.6, 20.3] | 10.0% (48/480) [7.6, 13.0] | 2.3% (11/480) [1.3, 4.1] | 16.7% (80/480) [13.6, 20.3] |
| Tier 1 held-out | tier_format_drift | abbreviation | 95.0% (152/160) [90.4, 97.4] | 17.5% (28/160) [12.4, 24.1] | 5.0% (8/160) [2.6, 9.6] | 85.0% (136/160) [78.6, 89.7] |
| Tier 1 held-out | tier_format_drift | case | 34.4% (55/160) [27.5, 42.0] | 76.9% (123/160) [69.8, 82.7] | 68.8% (110/160) [61.2, 75.4] | 89.4% (143/160) [83.6, 93.3] |
| Tier 1 held-out | tier_format_drift | whitespace | 95.0% (152/160) [90.4, 97.4] | 24.4% (39/160) [18.4, 31.6] | 5.0% (8/160) [2.6, 9.6] | 24.4% (39/160) [18.4, 31.6] |
| Live | queue_misconfiguration | description_swap | 3.3% (1/30) [0.6, 16.7] | 3.3% (1/30) [0.6, 16.7] | 3.3% (1/30) [0.6, 16.7] | 3.3% (1/30) [0.6, 16.7] |
| Live | tier_format_drift | abbreviation | 0.0% (0/10) [0.0, 27.8] | 100.0% (10/10) [72.2, 100.0] | 100.0% (10/10) [72.2, 100.0] | 90.0% (9/10) [59.6, 98.2] |
| Live | tier_format_drift | case | 0.0% (0/10) [0.0, 27.8] | 100.0% (10/10) [72.2, 100.0] | 100.0% (10/10) [72.2, 100.0] | 100.0% (10/10) [72.2, 100.0] |
| Live | tier_format_drift | whitespace | 0.0% (0/10) [0.0, 27.8] | 100.0% (10/10) [72.2, 100.0] | 100.0% (10/10) [72.2, 100.0] | 100.0% (10/10) [72.2, 100.0] |

## Limitations

- **Unseen escalation failed.** F6 was absent from training and validation. The risk of poor held-out F6 abstention was recorded before testing, and the chosen checkpoint remains fixed under Amendment 1.
- **Wrong interventions remain material.** Especially on healthy tier 2 held-out runs, higher decision accuracy does not imply dependable intervention behaviour. Zero observed errors on another set has a nonzero Wilson upper bound.
- **Synthetic scope.** These are generated support worlds and one OpenAI Agents SDK workflow with bounded probes and recoveries. The experiment does not establish diagnosis of arbitrary traces, production safety or general autonomous repair.
- **Baseline scope.** Rules v1 encodes training-family knowledge and stops after one recovery. GPT-4.1 and untrained Qwen use the shared zero-shot prompt; no few-shot strong-model baseline or contrast-partner ablation was tested. The comparisons establish performance against these specific baselines.
- **Selection uncertainty.** One training seed and four validation candidates were evaluated. The score rewards both accuracy and restraint; the selected checkpoint need not maximise either tier's accuracy alone. Full validation and test results do not reopen selection. The subset's recorded label-replay ceiling is S = 0.995 because one visible input has conflicting labels.
- **Live verification scope.** Live observations are fixed captures from `gpt-4.1-mini-2025-04-14`. Of 300 runs, 277 are proxy-matched, 17 final-label-only and six live-confirmed on the target ticket. Recovery re-runs and regression checks otherwise rely on scripted proxies; no tier 2 live split exists. Live F7 consists entirely of healthy runs.
- **Metric and action limits.** Undetermined cases remain in decision metrics and are excluded from probe-efficiency metrics. Tier 1 probe labels use small hypothesis sets; tier 2 adds richer hypotheses and distractors. Partial repair followed by escalation cannot score correct under the frozen action space.
- **Statistical limits.** Paired bootstrap intervals resample cases under the frozen protocol; they do not measure variation across training seeds or deployments. No multiple-comparison correction is applied. Every primary comparison is shown, including those with no significant difference.

## Reproducing

Run `python -m packages.support_evaluator.milestone3_results` to write this document, or add `--check` to compare its exact UTF-8 bytes without writing. This is offline analysis of recorded rows, with no model generation, episode execution, live API call or GPU run. It does not rerun any test split.

The generator checks test-row hashes against their numbered entries in `docs/milestone-2/TEST_RUN_LOG.md`, checks selection and validation inputs against hashes in the validation log, requires exactly the declared cases once each, recomputes summaries with `case_sources.load_source(...).summarize`, and requires equality with the stored summaries. Selection scores and monitored rates are recomputed from the existing validation rows. All pairwise comparisons call `metrics.paired_bootstrap` with 10,000 resamples and seed 2026. Formatting helpers and source paths follow the Milestone 2 generator; its report and the protocol are unchanged.

Artifacts are gitignored. Baseline rows are under the directories recorded for runs #1–#4. Fine-tuned in-distribution and live rows come from `artifacts/milestone-3/test-session-A/qlora-test/<set>/`; held-out rows come from `artifacts/milestone-3/test-session-B/qlora-test/<set>/`. Session B's copies of session A results are not counted again. Selection inputs are under `artifacts/milestone-3/selection-run-1/qlora-selection/` and full validation under `artifacts/milestone-3/validation-run-1/qlora-validation/`. The exact regeneration test runs where those artifacts exist; CI always checks the committed document's fixed prose and structure.

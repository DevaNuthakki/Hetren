# Milestone 2 results: baselines on the test splits

All numbers here are test-split results under the frozen evaluation protocol (`docs/milestone-2/EVAL_PROTOCOL.md`, frozen 2026-11-02, no amendments). Every run behind them is logged in `docs/milestone-2/TEST_RUN_LOG.md` (runs #1–#4); each system ran once per test set, and no system or setting was chosen after seeing test results.

## Systems

| system | declared version | test runs | code | cost |
|---|---|---|---|---|
| rules v1 | `RULES_POLICY_VERSION = 1`, single-recovery policy in both tiers | #1 | `31922b7` | $0 (offline) |
| GPT-4.1 | `gpt-4.1-2025-04-14`, prompt version 2, temperature 0, 128 output tokens | #2 | `54feb7b` (runner as of `31922b7`) | $15.63 |
| Qwen untrained | `Qwen/Qwen3-4B-Instruct-2507` at revision `cdbee75f`, prompt version 2, fp16, greedy, 128 new tokens, one Tesla T4 | #3 (tier 1), #4 (tier 2, live) | bundle `31922b7` | $0 (Kaggle) |

GPT-4.1 and Qwen see the same system prompt (version 2) and the same compact evidence, one stateless call per step. Rules v1 is a hand-written policy built for the training families.

## Test sets

| test set | dataset and split | cases | healthy runs |
|---|---|---|---|
| Tier 1 in-distribution | dataset v2, splits v1 `test_in_distribution` | 560 | 176 |
| Tier 1 held-out | dataset v2, splits v1 `test_held_out` (F6 queue misconfiguration, F7 tier format drift) | 960 | 121 |
| Tier 2 in-distribution | dataset v3, splits v2 `test_in_distribution` (up to two recoveries, compounds, distractors) | 256 | 45 |
| Tier 2 held-out | dataset v3, splits v2 `test_held_out` (compounds with F6 or F7) | 400 | 56 |
| Live | live test v1: runs recorded from `gpt-4.1-mini` (tier 1 episodes) | 300 | 121 |

## Findings

Claims follow the protocol's claim rule: "better" means the paired bootstrap 95% interval of the difference excludes zero; every other result is "no significant difference". No correction for multiple comparisons is applied, and all 30 comparisons are reported below.

1. **Rules v1 has the highest decision accuracy on all five test sets**, significantly so against both models on every set (99.5%, 45.7%, 84.4%, 28.2% and 80.3%).
2. **Rules v1 does not transfer to held-out families.** Its accuracy falls from 99.5% to 45.7% (tier 1) and from 84.4% to 28.2% (tier 2), and it gets 1 of 60 live held-out runs right. It applies a recovery to nearly every healthy held-out run: 121 of 121 in tier 1, 52 of 56 in tier 2 and all 30 healthy live tier-format-drift runs. On wrong interventions in the held-out sets, both models are significantly better than rules v1.
3. **GPT-4.1 against untrained Qwen.**
   - Decision accuracy: GPT-4.1 is better on tier 1 held-out (+10.5 pp), tier 2 in-distribution (+4.3 pp) and tier 2 held-out (+4.0 pp). There is no significant difference on tier 1 in-distribution, and Qwen is better on live (+8.7 pp).
   - Wrong interventions: Qwen is better on four sets. On tier 1 held-out both are at 0 of 121.
4. **Untrained Qwen's 0% wrong interventions reflect a bias against acting, not good judgement.**
   - It never applied a recovery on a healthy run. Where it did not choose `no_intervention`, it chose `insufficient_evidence` (47 of 176, 20 of 45 and 27 of 121 healthy runs).
   - It rarely fixes faulty runs either (verified recovery 0–12%), and 10–26% of its episodes end on an invalid action.
   - GPT-4.1 intervenes wrongly on 33% (tier 1) and 51% (tier 2) of healthy in-distribution runs.
5. **No system fixes both faults of a two-recovery label** (0 of 26 in tier 2 in-distribution, 0 of 95 in tier 2 held-out). Rules v1 stops after one recovery by design; GPT-4.1 stops after one in 65–75% of these cases and Qwen in 19–36%.
6. **Proactive detection is near zero for both models.** On single-fault F2/F6 cases, which only a probe reveals, GPT-4.1 scores 0–10% and Qwen 0–5%.
7. **The models' best families are those the run text already shows.** Misleading ticket text and recent tier change score 44–100% for both models in tier 1, tier 2 and live. Families that need a probe or an exact recovery argument (mapping swap, stale account record, mishandled tool error) score 0–23%.

For Milestone 3, the bar is set by these numbers.
- **To beat:** untrained Qwen at 30.4% / 14.3% / 13.3% / 15.2% / 36.7%, and GPT-4.1 on the same sets.
- **To approach:** rules v1 in-distribution.
- **Constraints:** without giving up the near-zero wrong-intervention rate, and with held-out families reported separately.

## Results

Rates are k / n with Wilson 95% intervals in brackets. Decision metrics include undetermined cases; probe-efficiency metrics exclude them and report their count. Paired differences are A − B in percentage points, with the paired bootstrap 95% interval (10,000 resamples, seed 2026); for wrong interventions, a negative difference favours A.

### Primary endpoints

| test set | system | decision accuracy | wrong interventions on healthy runs |
|---|---|---|---|
| Tier 1 in-distribution | rules v1 | 99.5% (557/560) [98.4, 99.8] | 0.0% (0/176) [0.0, 2.1] |
| Tier 1 in-distribution | GPT-4.1 | 33.8% (189/560) [30.0, 37.8] | 33.0% (58/176) [26.4, 40.2] |
| Tier 1 in-distribution | Qwen untrained | 30.4% (170/560) [26.7, 34.3] | 0.0% (0/176) [0.0, 2.1] |
| Tier 1 held-out | rules v1 | 45.7% (439/960) [42.6, 48.9] | 100.0% (121/121) [96.9, 100.0] |
| Tier 1 held-out | GPT-4.1 | 24.8% (238/960) [22.2, 27.6] | 0.0% (0/121) [0.0, 3.1] |
| Tier 1 held-out | Qwen untrained | 14.3% (137/960) [12.2, 16.6] | 0.0% (0/121) [0.0, 3.1] |
| Tier 2 in-distribution | rules v1 | 84.4% (216/256) [79.4, 88.3] | 2.2% (1/45) [0.4, 11.6] |
| Tier 2 in-distribution | GPT-4.1 | 17.6% (45/256) [13.4, 22.7] | 51.1% (23/45) [37.0, 65.0] |
| Tier 2 in-distribution | Qwen untrained | 13.3% (34/256) [9.7, 18.0] | 0.0% (0/45) [0.0, 7.9] |
| Tier 2 held-out | rules v1 | 28.2% (113/400) [24.1, 32.9] | 92.9% (52/56) [83.0, 97.2] |
| Tier 2 held-out | GPT-4.1 | 19.2% (77/400) [15.7, 23.4] | 10.7% (6/56) [5.0, 21.5] |
| Tier 2 held-out | Qwen untrained | 15.2% (61/400) [12.1, 19.1] | 0.0% (0/56) [0.0, 6.4] |
| Live | rules v1 | 80.3% (241/300) [75.5, 84.4] | 24.8% (30/121) [17.9, 33.2] |
| Live | GPT-4.1 | 28.0% (84/300) [23.2, 33.3] | 31.4% (38/121) [23.8, 40.1] |
| Live | Qwen untrained | 36.7% (110/300) [31.4, 42.3] | 0.0% (0/121) [0.0, 3.1] |

### Paired comparisons

| test set | A − B | decision accuracy: difference [95% CI] | verdict | wrong interventions: difference [95% CI] | verdict |
|---|---|---|---|---|---|
| Tier 1 in-distribution | rules v1 − GPT-4.1 | +65.7 pp [+61.8, +69.6] (n=560) | rules v1 better | -33.0 pp [-40.3, -26.1] (n=176) | rules v1 better |
| Tier 1 in-distribution | rules v1 − Qwen untrained | +69.1 pp [+65.2, +72.9] (n=560) | rules v1 better | +0.0 pp [+0.0, +0.0] (n=176) | no significant difference |
| Tier 1 in-distribution | GPT-4.1 − Qwen untrained | +3.4 pp [-0.4, +7.1] (n=560) | no significant difference | +33.0 pp [+26.1, +40.3] (n=176) | Qwen untrained better |
| Tier 1 held-out | rules v1 − GPT-4.1 | +20.9 pp [+17.0, +25.0] (n=960) | rules v1 better | +100.0 pp [+100.0, +100.0] (n=121) | GPT-4.1 better |
| Tier 1 held-out | rules v1 − Qwen untrained | +31.5 pp [+27.1, +35.7] (n=960) | rules v1 better | +100.0 pp [+100.0, +100.0] (n=121) | Qwen untrained better |
| Tier 1 held-out | GPT-4.1 − Qwen untrained | +10.5 pp [+8.5, +12.7] (n=960) | GPT-4.1 better | +0.0 pp [+0.0, +0.0] (n=121) | no significant difference |
| Tier 2 in-distribution | rules v1 − GPT-4.1 | +66.8 pp [+60.9, +72.7] (n=256) | rules v1 better | -48.9 pp [-64.4, -35.6] (n=45) | rules v1 better |
| Tier 2 in-distribution | rules v1 − Qwen untrained | +71.1 pp [+65.2, +76.6] (n=256) | rules v1 better | +2.2 pp [+0.0, +6.7] (n=45) | no significant difference |
| Tier 2 in-distribution | GPT-4.1 − Qwen untrained | +4.3 pp [+0.8, +7.8] (n=256) | GPT-4.1 better | +51.1 pp [+37.8, +66.7] (n=45) | Qwen untrained better |
| Tier 2 held-out | rules v1 − GPT-4.1 | +9.0 pp [+3.0, +15.2] (n=400) | rules v1 better | +82.1 pp [+69.6, +92.9] (n=56) | GPT-4.1 better |
| Tier 2 held-out | rules v1 − Qwen untrained | +13.0 pp [+6.8, +19.2] (n=400) | rules v1 better | +92.9 pp [+85.7, +98.2] (n=56) | Qwen untrained better |
| Tier 2 held-out | GPT-4.1 − Qwen untrained | +4.0 pp [+1.0, +7.0] (n=400) | GPT-4.1 better | +10.7 pp [+3.6, +19.6] (n=56) | Qwen untrained better |
| Live | rules v1 − GPT-4.1 | +52.3 pp [+44.7, +59.7] (n=300) | rules v1 better | -6.6 pp [-19.8, +6.6] (n=121) | no significant difference |
| Live | rules v1 − Qwen untrained | +43.7 pp [+36.0, +51.0] (n=300) | rules v1 better | +24.8 pp [+17.4, +32.2] (n=121) | Qwen untrained better |
| Live | GPT-4.1 − Qwen untrained | -8.7 pp [-12.0, -5.7] (n=300) | Qwen untrained better | +31.4 pp [+23.1, +39.7] (n=121) | Qwen untrained better |

### Secondary metrics

| test set | system | exact match | verified recovery | invalid actions | failed recovery calls | `insufficient_evidence` recall | `abstain` recall | `no_intervention` recall | mean probes (oracle) | undetermined |
|---|---|---|---|---|---|---|---|---|---|---|
| Tier 1 in-distribution | rules v1 | 80.2% (449/560) | 100.0% (240/240) | 0.0% (0/560) | 0 | 100.0% (108/108) | 91.7% (33/36) | 100.0% (176/176) | 1.413 (0.655) | 0 |
| Tier 1 in-distribution | GPT-4.1 | 20.9% (117/560) | 0.4% (1/240) | 0.2% (1/560) | 3 | 66.7% (72/108) | 0.0% (0/36) | 65.9% (116/176) | 0.5 (0.655) | 0 |
| Tier 1 in-distribution | Qwen untrained | 28.0% (157/560) | 11.7% (28/240) | 22.0% (123/560) | 36 | 12.0% (13/108) | 0.0% (0/36) | 73.3% (129/176) | 1.007 (0.655) | 0 |
| Tier 1 held-out | rules v1 | 29.1% (279/960) | 100.0% (279/279) | 0.0% (0/960) | 0 | 100.0% (160/160) | 0.0% (0/400) | 0.0% (0/121) | 1.667 (0.417) | 0 |
| Tier 1 held-out | GPT-4.1 | 12.6% (121/960) | 0.0% (0/279) | 0.1% (1/960) | 20 | 73.1% (117/160) | 0.0% (0/400) | 100.0% (121/121) | 0.065 (0.417) | 0 |
| Tier 1 held-out | Qwen untrained | 12.6% (121/960) | 0.0% (0/279) | 10.1% (97/960) | 0 | 10.0% (16/160) | 0.0% (0/400) | 100.0% (121/121) | 0.344 (0.417) | 0 |
| Tier 2 in-distribution | rules v1 | 70.7% (181/256) | 72.3% (102/141) | 0.0% (0/256) | 0 | 100.0% (35/35) | 100.0% (35/35) | 97.8% (44/45) | 1.399 (1.44) | 8 |
| Tier 2 in-distribution | GPT-4.1 | 14.1% (36/256) | 9.9% (14/141) | 0.8% (2/256) | 0 | 5.7% (2/35) | 20.0% (7/35) | 48.9% (22/45) | 1.246 (1.44) | 8 |
| Tier 2 in-distribution | Qwen untrained | 12.5% (32/256) | 6.4% (9/141) | 26.2% (67/256) | 12 | 5.7% (2/35) | 0.0% (0/35) | 51.1% (23/45) | 1.383 (1.44) | 8 |
| Tier 2 held-out | rules v1 | 17.0% (68/400) | 19.2% (28/146) | 0.0% (0/400) | 0 | 100.0% (45/45) | 23.5% (36/153) | 7.1% (4/56) | 1.357 (1.515) | 8 |
| Tier 2 held-out | GPT-4.1 | 12.8% (51/400) | 1.4% (2/146) | 0.5% (2/400) | 15 | 13.3% (6/45) | 12.4% (19/153) | 89.3% (50/56) | 1.459 (1.515) | 8 |
| Tier 2 held-out | Qwen untrained | 14.8% (59/400) | 2.1% (3/146) | 18.8% (75/400) | 17 | 4.4% (2/45) | 0.0% (0/153) | 100.0% (56/56) | 1.367 (1.515) | 8 |
| Live | rules v1 | 80.3% (241/300) | 100.0% (135/135) | 0.0% (0/300) | 0 | – | 34.1% (15/44) | 75.2% (91/121) | 1.729 (0.755) | 23 |
| Live | GPT-4.1 | 28.0% (84/300) | 0.7% (1/135) | 0.0% (0/300) | 6 | – | 0.0% (0/44) | 68.6% (83/121) | 0.491 (0.755) | 23 |
| Live | Qwen untrained | 36.7% (110/300) | 11.8% (16/135) | 15.7% (47/300) | 16 | – | 0.0% (0/44) | 77.7% (94/121) | 0.711 (0.755) | 23 |

### Tier 2 sequence metrics

| test set | system | exact sequence match | longer than label | stopped after one of two | two-recovery labels |
|---|---|---|---|---|---|
| Tier 2 in-distribution | rules v1 | 70.7% (181/256) | 0.0% (0/141) | 100.0% (26/26) | 0.0% (0/26) |
| Tier 2 in-distribution | GPT-4.1 | 14.1% (36/256) | 0.0% (0/141) | 65.4% (17/26) | 0.0% (0/26) |
| Tier 2 in-distribution | Qwen untrained | 12.5% (32/256) | 0.0% (0/141) | 19.2% (5/26) | 0.0% (0/26) |
| Tier 2 held-out | rules v1 | 17.0% (68/400) | 0.0% (0/146) | 100.0% (95/95) | 0.0% (0/95) |
| Tier 2 held-out | GPT-4.1 | 12.8% (51/400) | 0.7% (1/146) | 74.7% (71/95) | 0.0% (0/95) |
| Tier 2 held-out | Qwen untrained | 14.8% (59/400) | 0.0% (0/146) | 35.8% (34/95) | 0.0% (0/95) |

### Groups and slices (decision accuracy)

| test set | system | training families | held-out families | proactive detection | compound slice | length-reweighted |
|---|---|---|---|---|---|---|
| Tier 1 in-distribution | rules v1 | 99.5% (557/560) | – | 96.0% (71/74) | 0.0% (0/3) | 97.6% |
| Tier 1 in-distribution | GPT-4.1 | 33.8% (189/560) | – | 8.1% (6/74) | 0.0% (0/3) | 31.6% |
| Tier 1 in-distribution | Qwen untrained | 30.4% (170/560) | – | 5.4% (4/74) | 0.0% (0/3) | 24.4% |
| Tier 1 held-out | rules v1 | – | 45.7% (439/960) | 16.7% (80/480) | – | 33.0% |
| Tier 1 held-out | GPT-4.1 | – | 24.8% (238/960) | 10.0% (48/480) | – | 22.4% |
| Tier 1 held-out | Qwen untrained | – | 14.3% (137/960) | 2.3% (11/480) | – | 16.5% |
| Tier 2 in-distribution | rules v1 | 84.4% (216/256) | – | 91.7% (11/12) | 69.7% (23/33) | 78.0% |
| Tier 2 in-distribution | GPT-4.1 | 17.6% (45/256) | – | 0.0% (0/12) | 27.3% (9/33) | 14.4% |
| Tier 2 in-distribution | Qwen untrained | 13.3% (34/256) | – | 0.0% (0/12) | 3.0% (1/33) | 11.4% |
| Tier 2 held-out | rules v1 | – | 28.2% (113/400) | – | 16.2% (28/173) | 22.2% |
| Tier 2 held-out | GPT-4.1 | – | 19.2% (77/400) | – | 11.6% (20/173) | 13.0% |
| Tier 2 held-out | Qwen untrained | – | 15.2% (61/400) | – | 1.7% (3/173) | 7.9% |
| Live | rules v1 | 100.0% (240/240) | 1.7% (1/60) | 51.7% (31/60) | – | – |
| Live | GPT-4.1 | 22.1% (53/240) | 51.7% (31/60) | 1.7% (1/60) | – | – |
| Live | Qwen untrained | 32.9% (79/240) | 51.7% (31/60) | 1.7% (1/60) | – | – |

### Live split by label category (decision accuracy)

| system | final_label_only | live_confirmed_target | proxy_matched |
|---|---|---|---|
| rules v1 | 5.9% (1/17) | 100.0% (6/6) | 84.5% (234/277) |
| GPT-4.1 | 100.0% (17/17) | 0.0% (0/6) | 24.2% (67/277) |
| Qwen untrained | 100.0% (17/17) | 16.7% (1/6) | 33.2% (92/277) |

### Per family: Tier 1 in-distribution

| family | held out | rules v1 | GPT-4.1 | Qwen untrained |
|---|---|---|---|---|
| `mapping_swap` | no | 100.0% (63/63) | 14.3% (9/63) | 3.2% (2/63) |
| `merged_account` | no | 100.0% (74/74) | 5.4% (4/74) | 16.2% (12/74) |
| `mishandled_tool_error` | no | 100.0% (70/70) | 22.9% (16/70) | 4.3% (3/70) |
| `misleading_ticket_text` | no | 100.0% (59/59) | 78.0% (46/59) | 74.6% (44/59) |
| `missing_account` | no | 100.0% (76/76) | 19.7% (15/76) | 32.9% (25/76) |
| `recent_tier_change` | no | 100.0% (74/74) | 90.5% (67/74) | 86.5% (64/74) |
| `stale_account_record` | no | 96.0% (71/74) | 8.1% (6/74) | 5.4% (4/74) |
| `transient_error_retried` | no | 100.0% (70/70) | 37.1% (26/70) | 22.9% (16/70) |

### Per family: Tier 1 held-out

| family | held out | rules v1 | GPT-4.1 | Qwen untrained |
|---|---|---|---|---|
| `queue_misconfiguration` | yes | 16.7% (80/480) | 10.0% (48/480) | 2.3% (11/480) |
| `tier_format_drift` | yes | 74.8% (359/480) | 39.6% (190/480) | 26.2% (126/480) |

### Per family: Tier 2 in-distribution

| family | held out | rules v1 | GPT-4.1 | Qwen untrained |
|---|---|---|---|---|
| `compound:mapping_swap+merged_account` | no | 100.0% (4/4) | 0.0% (0/4) | 0.0% (0/4) |
| `compound:mapping_swap+mishandled_tool_error` | no | 25.0% (1/4) | 0.0% (0/4) | 0.0% (0/4) |
| `compound:mapping_swap+misleading_ticket_text` | no | 88.9% (8/9) | 0.0% (0/9) | 0.0% (0/9) |
| `compound:mapping_swap+missing_account` | no | 0.0% (0/5) | 0.0% (0/5) | 0.0% (0/5) |
| `compound:mapping_swap+recent_tier_change` | no | 100.0% (5/5) | 40.0% (2/5) | 0.0% (0/5) |
| `compound:mapping_swap+stale_account_record` | no | 12.5% (1/8) | 0.0% (0/8) | 0.0% (0/8) |
| `compound:mapping_swap+transient_error_retried` | no | 28.6% (2/7) | 0.0% (0/7) | 0.0% (0/7) |
| `compound:mishandled_tool_error+merged_account` | no | 100.0% (6/6) | 0.0% (0/6) | 0.0% (0/6) |
| `compound:mishandled_tool_error+misleading_ticket_text` | no | 80.0% (4/5) | 20.0% (1/5) | 20.0% (1/5) |
| `compound:mishandled_tool_error+missing_account` | no | 83.3% (5/6) | 50.0% (3/6) | 0.0% (0/6) |
| `compound:mishandled_tool_error+recent_tier_change` | no | 100.0% (8/8) | 0.0% (0/8) | 0.0% (0/8) |
| `compound:mishandled_tool_error+transient_error_retried` | no | 90.9% (10/11) | 9.1% (1/11) | 0.0% (0/11) |
| `compound:misleading_ticket_text+merged_account` | no | 100.0% (4/4) | 0.0% (0/4) | 0.0% (0/4) |
| `compound:misleading_ticket_text+missing_account` | no | 100.0% (5/5) | 40.0% (2/5) | 20.0% (1/5) |
| `compound:misleading_ticket_text+recent_tier_change` | no | 100.0% (7/7) | 71.4% (5/7) | 71.4% (5/7) |
| `compound:misleading_ticket_text+transient_error_retried` | no | 88.9% (8/9) | 22.2% (2/9) | 11.1% (1/9) |
| `compound:missing_account+merged_account` | no | 100.0% (6/6) | 0.0% (0/6) | 0.0% (0/6) |
| `compound:missing_account+recent_tier_change` | no | 100.0% (6/6) | 50.0% (3/6) | 50.0% (3/6) |
| `compound:missing_account+transient_error_retried` | no | 60.0% (6/10) | 60.0% (6/10) | 10.0% (1/10) |
| `compound:stale_account_record+merged_account` | no | 83.3% (5/6) | 0.0% (0/6) | 0.0% (0/6) |
| `compound:stale_account_record+mishandled_tool_error` | no | 100.0% (5/5) | 0.0% (0/5) | 20.0% (1/5) |
| `compound:stale_account_record+misleading_ticket_text` | no | 75.0% (6/8) | 12.5% (1/8) | 12.5% (1/8) |
| `compound:stale_account_record+missing_account` | no | 50.0% (2/4) | 0.0% (0/4) | 0.0% (0/4) |
| `compound:stale_account_record+recent_tier_change` | no | 100.0% (5/5) | 0.0% (0/5) | 0.0% (0/5) |
| `compound:stale_account_record+transient_error_retried` | no | 54.5% (6/11) | 0.0% (0/11) | 0.0% (0/11) |
| `mapping_swap` | no | 100.0% (10/10) | 0.0% (0/10) | 0.0% (0/10) |
| `merged_account` | no | 100.0% (11/11) | 0.0% (0/11) | 0.0% (0/11) |
| `mishandled_tool_error` | no | 100.0% (17/17) | 17.6% (3/17) | 17.6% (3/17) |
| `misleading_ticket_text` | no | 100.0% (9/9) | 44.4% (4/9) | 55.6% (5/9) |
| `missing_account` | no | 100.0% (11/11) | 36.4% (4/11) | 27.3% (3/11) |
| `recent_tier_change` | no | 100.0% (12/12) | 58.3% (7/12) | 66.7% (8/12) |
| `stale_account_record` | no | 91.7% (11/12) | 0.0% (0/12) | 0.0% (0/12) |
| `transient_error_retried` | no | 100.0% (10/10) | 10.0% (1/10) | 10.0% (1/10) |

### Per family: Tier 2 held-out

| family | held out | rules v1 | GPT-4.1 | Qwen untrained |
|---|---|---|---|---|
| `compound:mapping_swap+queue_misconfiguration` | yes | 12.5% (5/40) | 0.0% (0/40) | 2.5% (1/40) |
| `compound:mapping_swap+tier_format_drift` | yes | 10.0% (5/50) | 0.0% (0/50) | 2.0% (1/50) |
| `compound:mishandled_tool_error+queue_misconfiguration` | yes | 60.0% (24/40) | 5.0% (2/40) | 0.0% (0/40) |
| `compound:mishandled_tool_error+tier_format_drift` | yes | 50.0% (25/50) | 6.0% (3/50) | 10.0% (5/50) |
| `compound:misleading_ticket_text+queue_misconfiguration` | yes | 22.5% (9/40) | 10.0% (4/40) | 10.0% (4/40) |
| `compound:misleading_ticket_text+tier_format_drift` | yes | 60.0% (30/50) | 34.0% (17/50) | 30.0% (15/50) |
| `compound:missing_account+queue_misconfiguration` | yes | 12.5% (5/40) | 47.5% (19/40) | 0.0% (0/40) |
| `compound:missing_account+tier_format_drift` | yes | 10.0% (5/50) | 2.0% (1/50) | 0.0% (0/50) |
| `compound:stale_account_record+queue_misconfiguration` | yes | 12.5% (5/40) | 77.5% (31/40) | 87.5% (35/40) |

### Per family: Live

| family | held out | rules v1 | GPT-4.1 | Qwen untrained |
|---|---|---|---|---|
| `mapping_swap` | no | 100.0% (30/30) | 0.0% (0/30) | 0.0% (0/30) |
| `merged_account` | no | 100.0% (30/30) | 0.0% (0/30) | 10.0% (3/30) |
| `mishandled_tool_error` | no | 100.0% (30/30) | 0.0% (0/30) | 0.0% (0/30) |
| `misleading_ticket_text` | no | 100.0% (30/30) | 73.3% (22/30) | 100.0% (30/30) |
| `missing_account` | no | 100.0% (30/30) | 3.3% (1/30) | 46.7% (14/30) |
| `recent_tier_change` | no | 100.0% (30/30) | 100.0% (30/30) | 100.0% (30/30) |
| `stale_account_record` | no | 100.0% (30/30) | 0.0% (0/30) | 0.0% (0/30) |
| `transient_error_retried` | no | 100.0% (30/30) | 0.0% (0/30) | 6.7% (2/30) |
| `queue_misconfiguration` | yes | 3.3% (1/30) | 3.3% (1/30) | 3.3% (1/30) |
| `tier_format_drift` | yes | 0.0% (0/30) | 100.0% (30/30) | 100.0% (30/30) |

The live split's held-out families (F6, F7) are 60 runs. All 30 tier-format-drift runs are healthy (the live agent handled the drift), and 29 of 30 queue-misconfiguration runs are labelled `abstain`.

## Reproducing

Every table above was recomputed from the recorded rows (`rows-<set>.jsonl` in the output directories listed in the test-run log) with `case_sources.load_source(...).summarize` and `metrics.paired_bootstrap`, with no model call. The recomputed summaries are identical to the `summary-<set>.json` files the runs wrote.

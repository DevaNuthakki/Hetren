---
title: "Hetren: execution-labelled diagnosis of a synthetic support agent"
subtitle: "Technical report, v1.0.0"
author: "Deva Harsha Nuthakki"
date: "2026-11"
---

# Summary

Hetren diagnoses recorded runs of a tool-using customer-support agent. For each run, it chooses one action per
step:
- leave the run alone (`no_intervention`);
- say the evidence is insufficient;
- escalate (`abstain`);
- ask for a probe;
- propose a recovery.

All labels come from executing recoveries in sandboxed copies of a synthetic world, never from a model. A frozen
protocol fixed the splits, the metrics and a paired claim rule before any test run, and each system was run once
per test set.

A QLoRA fine-tune of Qwen3-4B-Instruct-2507 (checkpoint 792) is more accurate than GPT-4.1 and the untrained
base on all five test sets. For example, on tier 1 in-distribution its accuracy is 73.8% (413/560), against
33.8% and 30.4%. It also intervenes wrongly on far fewer healthy runs than GPT-4.1, in-distribution and live.

It remains below a hand-written rules policy on the faults those rules were written for: 99.5% in tier 1. Its
restraint does not transfer to unseen fault families: on tier 2 held-out it intervenes wrongly on 42.9% (24/56)
of healthy runs. And it never escalates the held-out queue-misconfiguration family: abstain recall 0.0% (0/400).

A 4-bit GGUF export (Q4_K_M, 2.5 GB) matches the fp16 model within a predeclared 2-point margin: −0.13 points
[−1.50, +1.25]. It ships in a command-line tool, an HTTP API and a Docker image. One GKE session measured its
serving and autoscaling, with load-test latencies that are a cached best case.

**Scope.** Every result here is for one synthetic support workflow. The model is not a general agent-trace
diagnoser.

# 1. Problem

Tool-using agents fail quietly. A corrupted mapping or a stale record leads an agent to complete its task
confidently and wrongly. The question this project measures is narrower than "can a model repair agents". Given
a run's evidence, can a diagnoser:

1. fix the run when a fix is possible;
2. stay out of healthy runs;
3. say so when the evidence is missing or no available recovery works?

The protocol states it as: "Measure whether a diagnosis-and-recovery method fixes failed support-agent runs when a
fix is possible, stays out of healthy runs, and says so when evidence is missing or no available recovery works.
Results are reported per fault family, with held-out families reported separately."
(`docs/milestone-2/EVAL_PROTOCOL.md`, "Purpose").

# 2. Environment and fault families

The world (`environments/support/`) holds synthetic accounts, customer references, queues and tickets. An agent
handles one ticket with three tools: `read_ticket`, `lookup_account` and `route_ticket`. Its run is recorded
through an action gateway, which logs every tool call: whether it was allowed, its observation and whether it
changed state. The OpenAI Agents SDK's hooks and spans are reconciled against the gateway's records, and any
disagreement becomes evidence.

| ID | family | role |
|:---------|:---|:---|
| F1 | customer-to-account mapping swap | train / validation / test |
| F2 | stale account record | train / validation / test |
| F3 | mishandled tool error | train / validation / test |
| F4 | misleading ticket text | train / validation / test |
| F5 | missing account | train / validation / test |
| F6 | queue misconfiguration | held out: test only |
| F7 | tier format drift | held out: test only |

There are three healthy look-alikes, all labelled `no_intervention`: a legitimately merged account, a recent tier
change, and a transient tool error that the agent retried. Scripted agent behaviours (`trust`, `retry`,
`give_up`, `follow_text`, `case_sensitive`) produce the runs. F2 and F6 leave no anomaly in the run itself; only a
probe reveals them.

**The diagnoser's input** is the run's compact evidence: the task, each tool call with its arguments, outcome and
observation, the run's status, SDK discrepancy kinds, and the results of any probes so far. **Its output** is one
action:
- a decision: `no_intervention`, `insufficient_evidence` or `abstain`;
- a probe, such as `find_owners` or `inspect`;
- a recovery: `rerun`, `reroute`, `set_mapping` or `restore_from_source`.

Tier 1 runs need at most one recovery; tier 2 runs can need a sequence of two.

# 3. Labels and datasets

**Labels come from execution.** In the protocol's words: "A recovery label is a recovery that, applied in a
sandboxed copy of the world and followed by re-running the task, passes verification, including regression checks
on unaffected tickets. Probe labels come from simple counterfactual enumeration: a probe sequence is sufficient
when every candidate world consistent with its observations has the same verified outcome."

The labeller applies fixed rules in order:
1. `unexplained_absence` gives `insufficient_evidence`;
2. `outcome_correct` gives `no_intervention`;
3. `persistent_tool_error` gives `abstain`, unless a re-run verifies;
4. otherwise the smallest verified change (tier 2: the shortest verified sequence), or `abstain` when nothing
   verifies.

Many cases have **contrast partners**: counterfactual variants on the same base world and ticket, consistent with
the same opening evidence but with a different label. They stay in the same split as their primary.

| dataset | tier | seed | primary cases | partners | records | steps |
|:---------|:---|:---|:---|:---|:---|:---|
| v2 | 1 | 2026 | 4,800 | 5,239 | 10,039 | 20,500 |
| v3 | 2 | 2028 | 2,040 | 6,358 | 8,398 | 31,365 |

**Splits** (splits v1 for dataset v2, splits v2 for dataset v3) are by world seed, fault family and agent source.
F6 and F7 appear only in `test_held_out`, not even as contrast partners in training. **The live test** has 300
runs of a `gpt-4.1-mini-2025-04-14` agent on fresh worlds (seed 2027, world seeds from 1,000,000), recorded with
`store=False`.
- **Labelling:** each live run is replayed from its captures and labelled by the same labeller, with matching
  scripted behaviours standing in where a re-run is needed.
- **Categories:** 277 proxy-matched, 17 final-label-only and 6 live-confirmed runs.
- **Confirmation:** 120 recovery labels were confirmed by a live re-run of the target ticket.
- **Cost:** $0.3309 in all.

# 4. Protocol and claim rule

The protocol was frozen on 2026-11-02, before any test run, and later changes are dated amendments.
- Amendment 1 (2026-11-03) fixed the fine-tuning and its checkpoint selection.
- Amendment 2 (2026-11-07) fixed the CPU export and its validation-only acceptance check.

Test splits were used once per system: runs #1–#6 (`docs/milestone-2/TEST_RUN_LOG.md`).

**Primary endpoints**, per tier and per test set: decision accuracy (the final action verified by execution;
failed recovery calls are wrong), and wrong interventions on healthy runs (any recovery applied where the label is
`no_intervention`). Every rate is k / n with a Wilson 95% interval.

**Claim rule**, from the protocol: "A system is 'better' than another on a primary endpoint only if the paired
bootstrap 95% interval for the difference, computed on the same cases, excludes zero in its favour". The bootstrap
uses 10,000 resamples with seed 2026. "No correction for multiple comparisons is applied; every comparison made is
reported."

# 5. Systems

| system | what it is | cost |
|:---------|:---|:---|
| rules v1 | a hand-written policy built for the training families (`RULES_POLICY_VERSION = 1`), single recovery | $0 |
| GPT-4.1 | `gpt-4.1-2025-04-14`, prompt version 2, temperature 0, 128 output tokens | $15.63 |
| Qwen untrained | `Qwen/Qwen3-4B-Instruct-2507` at revision `cdbee75f`, prompt version 2, fp16, greedy | $0 (Kaggle) |
| Qwen fine-tuned | the same base and prompt, with the QLoRA checkpoint 792 merged into the fp16 base | $0 (Kaggle) |

All model policies receive the same system prompt and the same compact evidence, one stateless call per step.

# 6. Training and selection

**Data:** the train splits of datasets v2 and v3, with contrast partners. After deduplication and dropping 58
conflicting inputs (116 examples), 17,082 examples remained (32,594,218 tokens). A predeclared 14-hour budget
kept every non-probe example and sampled probe examples at rate 0.9707, giving 16,869 examples.

**Method:**
- **QLoRA:** a 4-bit NF4 base with double quantisation and fp16 compute; rank 16, alpha 32, dropout 0.05, on
  all seven attention and MLP projections.
- **Optimiser:** paged 8-bit AdamW, learning rate 1e-4 with cosine decay and 3% warmup, effective batch 16.
- **Sequences:** length 2,560, without truncation or packing; seed 2029.
- **Loss:** assistant tokens only, with per-tier rare-verb weights capped at 3.
- **Run:** one epoch, 1,055 optimiser steps, on Kaggle T4 GPUs. No training loss was non-finite.

**Selection (Amendment 1):** four predeclared checkpoints (264, 528, 792 and 1,055) were scored on a validation
subset (200 tier 1 and 100 tier 2 primaries). The score was **S = ½(A₁ + A₂) − W**: the tier accuracies minus the
pooled wrong-intervention rate on healthy runs.

| candidate | S |
|:---------|:---|
| Qwen untrained | 0.1947 |
| checkpoint-0264 | 0.7206 |
| checkpoint-0528 | 0.6049 |
| checkpoint-0792 | **0.7322** |
| checkpoint-1055 | 0.6331 |

Checkpoint 792 was chosen. No test result influenced the choice. **A risk recorded before testing:** the chosen
checkpoint's tier 1 abstain recall on the subset was 2/17, against 15/17 for checkpoint 264.

# 7. Test results

Decision accuracy (`docs/milestone-3/RESULTS.md`):

| test set | cases | rules v1 | GPT-4.1 | Qwen untrained | Qwen fine-tuned |
|:---------|:---|:---|:---|:---|:---|
| Tier 1 in-distribution | 560 | 99.5% | 33.8% | 30.4% | 73.8% (413/560) |
| Tier 1 held-out | 960 | 45.7% | 24.8% | 14.3% | 41.5% (398/960) |
| Tier 2 in-distribution | 256 | 84.4% | 17.6% | 13.3% | 71.1% (182/256) |
| Tier 2 held-out | 400 | 28.2% | 19.2% | 15.2% | 31.2% (125/400) |
| Live | 300 | 80.3% | 28.0% | 36.7% | 66.3% (199/300) |

Wrong interventions on healthy runs:

| test set | healthy | rules v1 | GPT-4.1 | Qwen untrained | Qwen fine-tuned |
|:---------|:---|:---|:---|:---|:---|
| Tier 1 in-distribution | 176 | 0.0% | 33.0% | 0.0% | 0.0% (0/176) |
| Tier 1 held-out | 121 | 100.0% | 0.0% | 0.0% | 7.4% (9/121) |
| Tier 2 in-distribution | 45 | 2.2% | 51.1% | 0.0% | 4.4% (2/45) |
| Tier 2 held-out | 56 | 92.9% | 10.7% | 0.0% | 42.9% (24/56) |
| Live | 121 | 24.8% | 31.4% | 0.0% | 0.8% (1/121) |

**Findings under the claim rule:**

1. **Fine-tuning beats both model baselines on accuracy everywhere.** Every accuracy comparison with GPT-4.1 and
   the untrained base favours the fine-tuned model. Against GPT-4.1 the differences range from +12.0 to +53.5
   points (tier 2 held-out to tier 2 in-distribution).
2. **Rules v1 keeps its lead on four sets.** It leads by +25.7 points on tier 1 in-distribution and +13.3 on
   tier 2 in-distribution. On tier 2 held-out there is no significant difference (−3.0 points [−6.2, +0.2]).
3. **Wrong interventions:** the fine-tuned model is better than GPT-4.1 in-distribution and live. GPT-4.1 is
   better on both held-out sets (−7.4 points [−12.4, −3.3] in tier 1, −32.1 [−50.0, −14.3] in tier 2). The
   untrained base, which rarely acts at all, is better than the fine-tuned model on both held-out sets. Across
   the 30 endpoint comparisons involving the fine-tuned model, it is better in 16, a baseline is better in 8, and
   6 show no significant difference.
4. **Two-step recovery is limited.** Where the label needs two recoveries, the fine-tuned model fixed both in
   26.9% (7/26) of in-distribution cases and 1.1% (1/95) of held-out ones. No baseline fixed both in any case.
5. **F6 escalation failed.** On held-out `queue_misconfiguration`, where complete evidence calls for `abstain`,
   the fine-tuned model's abstain recall is 0.0% (0/400) [0.0, 0.9]. Every other system's is also 0.0%. On live
   runs, abstain recall over all families is 0/44. **F7 transferred in part:** family accuracy is 66.2%
   (318/480), and verified recovery on the repair-labelled cases is 45.2% (126/279).

# 8. CPU export (Amendment 2)

The adapter was merged into the fp16 base, converted to GGUF, and quantized to Q8_0 and Q4_K_M with llama.cpp
`620d2225c` (build 11669), without an importance matrix. A token-parity check found the GGUF tokenizer identical
to the merged model's.

Each variant ran the full validation split (550 tier 1 and 250 tier 2 cases) on `llama-server` on the CPU.
- **Platform:** the pilot's Mac (Intel i7-8850H, `-t 6`), with prompt caching on and greedy
  decoding (Amendment 2).
- **Acceptance rule:** the lower bound of the pooled difference from fp16 must be at least −2 points.

| | fp16 | Q4_K_M | Q8_0 |
|:---------|:---|:---|:---|
| decision accuracy, tier 1 (550) | 73.6% (405) | 74.2% (408) | 73.1% (402) |
| decision accuracy, tier 2 (250) | 76.0% (190) | 74.4% (186) | 74.8% (187) |
| pooled difference from fp16 [95% CI] | | −0.13 [−1.50, +1.25] | −0.75 [−1.38, −0.25] |
| episodes identical to fp16 | | 79.6% | 92.6% |

**Both were accepted.** Q4_K_M ships by default. In tier 2 it is more conservative than fp16: it left 30 broken
runs unfixed against 15 for fp16, and made 0 wrong interventions against 1 for fp16.

**The Linux image** was checked on the 20 pilot cases. Q4_K_M took the same episode as the Mac on 18 of 20; the
other two took one extra probe and reached the same decision. Q8_0 matched on 20 of 20. These checks are
descriptive, not a re-validation.

# 9. Packaging and deployment

- **The tools:** a command-line tool (`hetren diagnose`, `fetch-model`, `serve`) and an HTTP API (`POST
  /diagnose`, one diagnosis at a time, a bounded queue of 8, 503 with `Retry-After`) in a `linux/amd64` Docker
  image.
  - Each report states its scope, that nothing was applied, and the shipped variant's validation result.
  - `fetch-model` checks every file against the export manifest.
- **The cluster:** a Helm chart, and Terraform for a dedicated project with a $25 gross-usage budget, a billing
  kill switch, and private GKE nodes behind Cloud NAT.

**One GKE session** ran on the Free Trial, on 1–2 `e2-standard-4` nodes, with an HPA at 60% CPU and `-t 2` per
pod (`docs/milestone-4/DEPLOY_LOG.md`).
- **The first diagnosis** took 162 s: a fresh 1,744-token prompt on 2 cores.
- **The scale-up:** it drove the HPA to two replicas. The second node was ready 44 s after the rescale, and the
  second pod 171 s after it, including its model download.
- **The k6 load test:** 1, 2, 4, 8 and 16 virtual users, 300 s each. Throughput levelled off at 0.27 diagnoses
  per second with two replicas.

**These latencies are a cached best case.** Every request sent the same input, so llama-server's prompt cache
was reused: about 8 s per diagnosis, against about 136–162 s for a fresh prompt. At 16 users, most requests were
turned away at once by full queues, and the test retried them without waiting. The load test now sends 16
distinct training inputs and waits out rejections, for any future run.

**Cost:** the session cost an estimated $2.27 in Free Trial credits. That includes an idle cluster left up
overnight before its teardown; a prompt teardown would have cost $0.48.

# 10. Limitations

- **Synthetic and narrow:** one workflow, three tools, seven fault families, and scripted agents for every
  non-live run.
- **Escalation:** the fine-tuned model rarely abstains when it should. On F6 it never did, and the risk was
  visible on validation before testing.
- **Held-out families:** accuracy and restraint both drop.
- **Tier 1 in the tools:** the model was validated on two-step recovery, but no released tool supports it.
- **Live regression checks:** confirmation re-ran only the target ticket live. Regression checks relied on
  scripted proxies.
- **Retiring models:** `gpt-4.1` and `gpt-4.1-mini` leave the API on 2027-01-14. Their logged results stand,
  but cannot be re-run.
- **One validation platform for the GGUF:** other CPUs are untested.
- **Performance is descriptive:** one session, on small nodes, at 2 threads rather than the validated 6, with
  cached prompts.
- **Multiple comparisons:** no correction is applied, as the protocol states; all comparisons are reported.

# 11. Reproducing and artefacts

- **Model:** `Harsha1412/hetren-qwen3-4b-diagnosis` at revision `3e875e4e8719acef839dc18e220a3ae498a1975b`
  (Apache-2.0).
- **Data:** `Harsha1412/hetren-support-runs` (CC BY 4.0): both datasets, the frozen splits, the live test and the
  protocol, every file matching its committed manifest.
- **Code:** https://github.com/DevaNuthakki/Hetren (Apache-2.0).
  - Datasets and splits regenerate from each manifest's `regenerate` command.
  - The records: the test runs in `docs/milestone-2/TEST_RUN_LOG.md`; training and selection in
    `docs/milestone-3/VALIDATION_LOG.md`; the export in `docs/milestone-4/EXPORT_LOG.md`; the deployment in
    `docs/milestone-4/DEPLOY_LOG.md`.
- **The full episode:** `python -m packages.support_evaluator.sandbox_demo` runs a validation case with the
  model, and verifies its action by execution.

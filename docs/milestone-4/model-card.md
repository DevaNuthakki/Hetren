---
license: apache-2.0
base_model: Qwen/Qwen3-4B-Instruct-2507
base_model_relation: finetune
library_name: peft
pipeline_tag: text-generation
language:
  - en
tags:
  - gguf
  - llama.cpp
  - lora
  - qwen3
  - agent-diagnosis
  - synthetic-data
---

# Hetren diagnosis model (Qwen3-4B, checkpoint 0792)

A QLoRA fine-tune of [Qwen/Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507). It
diagnoses a recorded run of **Hetren's synthetic customer-support agent**. Given the run's evidence, it returns
one action: a decision (`no_intervention`, `insufficient_evidence` or `abstain`), a recovery to propose, or a
probe it would need.

> **Scope.** The model was trained only on Hetren's synthetic support workflow (the tools `read_ticket`,
> `lookup_account` and `route_ticket`, and its fault families). It is not a general agent-trace diagnoser, and
> outside that workflow its outputs are not meaningful. It proposes; it never applies anything. The `hetren`
> CLI and API handle single-recovery (tier 1) runs only. The model was also validated on two-step recovery
> (tier 2), but no released tool supports that.
>
> **Intended use:** research and demonstration of the evaluation method; not for production decisions about
> real systems.

This repository holds the LoRA adapter and two quantized GGUFs (Q4_K_M is the default; Q8_0 is the
higher-fidelity alternative). It also holds the tokenizer and the export manifest that pins them all by sha256.
The evaluation protocol, code and logs are in the [Hetren repository](https://github.com/DevaNuthakki/Hetren).

## Files

| path | what | bytes | sha256 |
|---|---|---|---|
| `hetren-qwen3-4b-ckpt0792-q4_k_m.gguf` | merged model, Q4_K_M (**default**) | 2,497,278,880 | `e3f50ba98ee7e800554dec7ec1c403e7f1d47d4595300e6a6a3e8bf7ffe8763e` |
| `hetren-qwen3-4b-ckpt0792-q8_0.gguf` | merged model, Q8_0 (higher fidelity) | 4,280,403,360 | `496c74a750ef32d0c52dd9644e51b36547dda762c498ac89eece1a24bab3ba29` |
| `adapter/adapter_model.safetensors` | the LoRA adapter (rank 16), for the fp16 base | 132,187,888 | `5647f93f25c9f79c8e7fca0468d8aa7476afbcc348f3b42f420d1845098f4226` |
| `adapter/adapter_config.json` | its PEFT configuration | 939 | `2e5474dfb3826b085cca2b10757f21fd6f0bb99f58b1d4f4d5096499522b6fe6` |
| `tokenizer/` | the merged model's tokenizer and chat template (9 files) | | listed in the manifest |
| `export.manifest.json` | every file's sha256, the base revision, and the merge and conversion settings | | `4a2431a46a31045d74bf48da291fcbf09692a794e58d66d7135ede1cdc433ee0` |

The adapter applies to the base at revision `cdbee75f17c01a7cc42f958dc650907174af0554`. Its
`adapter_config.json` does not pin a revision, so pass `revision=` when loading the base.

## Use

The supported path is the `hetren` CLI or API. They check every file against the manifest and prompt the model
exactly as it was validated (the image is published with the first release tag):

```sh
docker run --rm -v ~/.cache/hetren:/models ghcr.io/devanuthakki/hetren-cli:<tag> fetch-model --repo <this repository>
docker run --rm --network none -v ~/.cache/hetren:/models:ro -v "$PWD":/work:ro \
  ghcr.io/devanuthakki/hetren-cli:<tag> diagnose --record /work/run.json
```

The input is a run recorded with Hetren's OpenAI Agents SDK integration (an `AgentRunRecord`), or its compact
evidence. An SDK trace export is rejected, because it lacks the gateway records the model reads. The image is
`linux/amd64` and needs AVX2, FMA and F16C.

**Using the GGUF directly in llama.cpp** works, but it is not the validated path. The validation built the
prompt with this repository's chat template (prompt version 2, from the Hetren repository), sent it to
`llama-server` as token IDs, and decoded greedily: `top_k` 1, temperature 0, no penalties, at most 128 new
tokens, a 4,096-token context. A different template, sampler or prompt changes the outputs, and those results
are not covered by the numbers below.

## Training

- **Data:** the train splits of Hetren's synthetic datasets v2 (single-fault, tier 1) and v3 (up to two faults, tier 2), contrast partners included.
  - The labels come from executing each run's recoveries in the simulated environment.
  - After deduplication and dropping 58 conflicting inputs, 17,082 examples remained (32.6M tokens). A predeclared 14-hour budget kept every non-probe example and sampled probe examples at rate 0.9707: 16,869 examples in all.
  - The datasets are published as [`Harsha1412/hetren-support-runs`](https://huggingface.co/datasets/Harsha1412/hetren-support-runs) (CC BY 4.0), with the frozen splits, the live test and the evaluation protocol.
- **Method:** QLoRA on a 4-bit NF4 base (double quantisation, fp16 compute), rank 16, alpha 32, dropout 0.05, all seven attention and MLP projections.
  - Paged 8-bit AdamW: learning rate 1e-4 with cosine decay, 3% warmup, effective batch 16, sequence length 2,560 (no truncation or packing), seed 2029.
  - The loss covered assistant tokens only, with per-tier rare-verb weights capped at 3.
  - One epoch, 1,055 steps, on Kaggle T4 GPUs.
- **Selection:** four predeclared checkpoints (264, 528, 792, 1,055) were scored on a validation subset with S = ½(A₁ + A₂) − W: tier decision accuracies minus the wrong-intervention rate on healthy runs.
  - **Checkpoint 792** scored highest: S = 0.7322, against 0.1947 for the untrained base.
  - No test result influenced the choice.
- **Export:** the adapter was merged into the fp16 base (PEFT `merge_and_unload`), converted to GGUF and quantized to Q8_0 and Q4_K_M without an importance matrix, using llama.cpp `620d2225c` (build 11669).
  - A token-parity check found the GGUF tokenizer identical to the merged model's Hugging Face tokenizer: the vocabulary, plus a round trip of all 6,569 distinct validation texts, with 0 differences.

## Evaluation: the fp16 model on the test sets

The evaluation protocol was frozen on 2026-11-02, before any test run, and every system ran once per test
set. Rates are k / n with Wilson 95% intervals. The two primary endpoints, as the protocol defines them:

- **decision accuracy** = |{r ∈ R : correct(r)}| / |R|, where R is the scored episodes and *correct(r)* is "the
  execution check of `score`" (failed recovery calls are wrong);
- **wrong interventions on healthy runs** = |{r ∈ H : r applied any recovery}| / |H|, where the healthy runs are
  "H = {r : label(r) = `no_intervention`}" (lower is better).

The baselines are a hand-written rules policy built for the training families, GPT-4.1
(`gpt-4.1-2025-04-14`, the same prompt), and the untrained base.

| test set | cases | rules v1 | GPT-4.1 | Qwen untrained | **this model** |
|---|---|---|---|---|---|
| Tier 1 in-distribution: accuracy | 560 | 99.5% [98.4, 99.8] | 33.8% [30.0, 37.8] | 30.4% [26.7, 34.3] | **73.8% (413/560) [70.0, 77.2]** |
| Tier 1 in-distribution: wrong interventions | 176 healthy | 0.0% [0.0, 2.1] | 33.0% [26.4, 40.2] | 0.0% [0.0, 2.1] | **0.0% (0/176) [0.0, 2.1]** |
| Tier 1 held-out families: accuracy | 960 | 45.7% [42.6, 48.9] | 24.8% [22.2, 27.6] | 14.3% [12.2, 16.6] | **41.5% (398/960) [38.4, 44.6]** |
| Tier 1 held-out families: wrong interventions | 121 healthy | 100.0% [96.9, 100.0] | 0.0% [0.0, 3.1] | 0.0% [0.0, 3.1] | **7.4% (9/121) [4.0, 13.5]** |
| Tier 2 in-distribution: accuracy | 256 | 84.4% [79.4, 88.3] | 17.6% [13.4, 22.7] | 13.3% [9.7, 18.0] | **71.1% (182/256) [65.3, 76.3]** |
| Tier 2 in-distribution: wrong interventions | 45 healthy | 2.2% [0.4, 11.6] | 51.1% [37.0, 65.0] | 0.0% [0.0, 7.9] | **4.4% (2/45) [1.2, 14.8]** |
| Tier 2 held-out families: accuracy | 400 | 28.2% [24.1, 32.9] | 19.2% [15.7, 23.4] | 15.2% [12.1, 19.1] | **31.2% (125/400) [26.9, 35.9]** |
| Tier 2 held-out families: wrong interventions | 56 healthy | 92.9% [83.0, 97.2] | 10.7% [5.0, 21.5] | 0.0% [0.0, 6.4] | **42.9% (24/56) [30.8, 55.9]** |
| Live (runs of a `gpt-4.1-mini` agent): accuracy | 300 | 80.3% [75.5, 84.4] | 28.0% [23.2, 33.3] | 36.7% [31.4, 42.3] | **66.3% (199/300) [60.8, 71.4]** |
| Live: wrong interventions | 121 healthy | 24.8% [17.9, 33.2] | 31.4% [23.8, 40.1] | 0.0% [0.0, 3.1] | **0.8% (1/121) [0.1, 4.5]** |

**What this shows** (paired bootstrap, 10,000 resamples; a verdict needs the 95% interval to exclude zero):
- **Better than both model baselines:** fine-tuning is more accurate than GPT-4.1 and than the untrained base on every set.
- **Below the rules policy:** the rules policy is more accurate on four of the five sets. On tier 2 held-out the difference is not significant.
- **Restraint did not transfer to unseen families.** On tier 2 held-out it intervened on 42.9% of healthy runs, against 0.0% for the untrained base. The base intervenes rarely in any case, which is also why its accuracy is low.
- **Valid actions, not always valid repairs:** no invalid actions on any set, but some proposed recoveries fail when executed.
- **Two-step recovery is limited:** where the label needs two recoveries, it fixed both in 26.9% (7/26) in-distribution and 1.1% (1/95) held-out. No baseline fixed both in any case.

**A known failure: escalation on the held-out `queue_misconfiguration` family (F6).** When the evidence is
complete, the correct decision for these runs is `abstain` (escalate to a human). The model's abstain recall
there is **0.0% (0/400)** [0.0, 0.9]. On live runs it never abstained: 0 of 44 abstain labels, across all
families. This risk was recorded before any test run: the chosen checkpoint's abstain recall on the validation
subset was 2 of 17. Do not rely on this model to escalate runs it has not seen the like of.

Full results, including per-family tables, are in `docs/milestone-3/RESULTS.md` in the Hetren repository.

## The GGUFs: acceptance on the validation split

Each GGUF ran the full validation split (550 tier 1 and 250 tier 2 cases) on `llama-server` (CPU), and was
compared with the fp16 model under the protocol's Amendment 2. Paired bootstrap, GGUF − fp16, 10,000
resamples, seed 2026. **Both were accepted**:

| | fp16 | Q4_K_M | Q8_0 |
|---|---|---|---|
| decision accuracy, tier 1 (550) | 73.6% (405) | 74.2% (408) | 73.1% (402) |
| decision accuracy, tier 2 (250) | 76.0% (190) | 74.4% (186) | 74.8% (187) |
| pooled difference from fp16 [95% CI] (criterion: lower bound ≥ −2 points) | | −0.13 [−1.50, +1.25] | −0.75 [−1.38, −0.25] |
| wrong interventions on healthy runs, tier 1 / tier 2 | 0/171, 1/54 | 0/171, 0/54 | 0/171, 1/54 |
| episodes identical to fp16 | | 79.6% (tier 1 86.5%, tier 2 64.4%) | 92.6% (tier 1 94.7%, tier 2 88.0%) |

**Choosing a variant:**
- **Q4_K_M** (default, 2.5 GB, the smaller accepted variant) matches fp16's accuracy with no significant difference. It reaches it partly through different episodes: it agrees with fp16 on 79.6% of cases.
  - In tier 2 it is more conservative. It chose `no_intervention` 84 times against fp16's 68, which left 30 broken runs unfixed against fp16's 15, and it made 0 wrong interventions against fp16's 1.
- **Q8_0** (4.3 GB) behaves most like fp16, agreeing on 92.6% of cases. It is slightly but significantly less accurate overall (−0.75 points), inside the margin.

## Limitations

- **Synthetic workflow only.** Every training and test case comes from Hetren's simulated support environment. The live test set used a real model (`gpt-4.1-mini`) as the agent, inside the same environment.
- **The validation platform is not the shipped platform.** The GGUFs were validated on macOS (llama.cpp with Apple's Accelerate). In the `linux/amd64` image, a 20-case check gave:
  - Q8_0: the same episodes as on the Mac, 20 of 20;
  - Q4_K_M: 18 of 20, where the other two each took one extra probe and reached the same decision.
  Greedy CPU decoding is deterministic for a fixed platform, build, thread count and caching setting; near-ties can resolve differently elsewhere.
- **`</s>` stops generation.** llama.cpp treats token 128247 (`</s>`, an ordinary token in this vocabulary) as end-of-generation, where transformers would continue. It never occurred: no fp16 validation reply contains it, and no GGUF validation call stopped on it.
- **The CLI covers tier 1 only.** Two-step recovery was validated, but no released tool supports it.

## License and attribution

Apache-2.0. Built on [Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507) by the Qwen
team (Alibaba Cloud), also licensed Apache-2.0. The training data is synthetic and generated by Hetren's own
code; the live test set's agent runs came from the OpenAI API (`store=False`) and are evaluation data only.

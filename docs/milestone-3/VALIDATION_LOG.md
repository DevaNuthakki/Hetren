# Validation log (Milestone 3)

Required by `docs/milestone-2/EVAL_PROTOCOL.md`, Amendment 1 ("Validation log"). It records:

- the throughput pilot and the epoch budget it fixes;
- every training run of the fine-tuned Qwen3-4B, including failed, stopped and aborted ones, with its date, platform, settings, the optimiser steps reached and its outcome;
- the untrained reference score on the selection subset;
- every validation evaluation of the fine-tuned model, including failed and stopped ones, with its date, checkpoint (optimiser step and adapter sha256), cases, platform, GPU, library versions, bundle commit, output hashes, S, A₁, A₂, W, and per tier `insufficient_evidence` precision and `abstain` recall.

Test-split runs are logged in `docs/milestone-2/TEST_RUN_LOG.md`, not here.

## Throughput pilot

| date | platform and GPUs | bundle | outcome | output and hashes |
|---|---|---|---|---|
| 2026-11-03, 18:00–18:27 UTC (Kaggle file times) | Kaggle, Tesla T4 ×2 (one-GPU pilot with only the first visible) | `d595063` (`bundle.json`; bundle sha256 `e7f5badbb1d6a0333cb4fbc2e51a59bb7bd9370fceace5037ecd6cdfcb2f12af`) | completed: training data built from the train split and matched `docs/milestone-3/train-v1.manifest.json`; both pilots completed with no non-finite loss | `artifacts/milestone-3/qlora-pilot/` (gitignored; archive `qlora-pilot.tar.gz` `4c168c68b4a2d858c1d75baacafc1f5c909949ea4996fa3efe903ecc9cd0c93a`): `tokens.json` `9c82d2a1897135a1201326600fbd34b0df5d962377bee905b06e1229dd93055f`, `pilot-1xGPU.json` `a949524b54cb5a23ab4ea82c9b62ae42717279352945e954d2b91d4423e1ee1b`, `pilot-2xGPU.json` `48766af1ee8eafc0cdd9ff2c3b27344c27ad7a17dae49bb39850f7f0ac27d05f`, `budget.json` `5129fbdafb55ddd3c6230a3d0dda6096e660a0c0033b29de40824cbd4dd1fc7d`, `bundle.json` `7c38745c413a3e6085cabff3a1ce57c5313d158483b45df492fb746ee328cd90` |

Run by the operator with `notebooks/milestone-3/qlora_throughput_pilot.ipynb` (12 timed minutes per configuration). The settings are Amendment 1's, recorded in each pilot file. The pilot's weights were never saved or evaluated.

**Training libraries (fixed by the pilot):** Python 3.13.16, `torch` 2.11.0+cu130, `transformers` 4.56.2, `accelerate` 1.10.1, `tokenizers` 0.22.2, `peft` 0.17.1, `bitsandbytes` 0.50.2. `trl` is not used: the training loop is `packages/hetren_baselines/qlora.py`.

**Tokens per epoch** (the model's chat template, prompt and target up to the end-of-turn token): 17,082 examples, 32,594,218 tokens (probe examples 13,439,178; non-probe 19,155,040). The longest example has 2,533 tokens, under the 2,560 limit.

| | one T4 | two T4s (data parallel) |
|---|---|---|
| accumulation per process | 16 | 8 |
| optimiser steps (first two untimed) | 8 | 15 |
| timed examples / tokens / seconds | 96 / 186,363 / 551.5 | 208 / 399,551 / 625.4 |
| timed sample mean tokens per example (dataset 1,908.1) | 1,941.3 | 1,920.9 |
| tokens per second | 337.9 | 638.9 |
| projected hours per epoch | 26.80 | 14.17 |
| peak memory per GPU | 5.22 GiB | 5.35 GiB each |
| non-finite losses | 0 | 0 |
| optimiser steps skipped by the fp16 loss scaler | 0 | 1 |

- The step the scaler skipped was a gradient overflow while the loss scale was being calibrated. That is normal fp16 behaviour, and the loss itself stayed finite.
- The timed examples are a seeded random sample of the training file. Their mean length is within 1.8% (one T4) and 0.7% (two T4s) of the dataset mean.

## Epoch budget

Under Amendment 1's rule, the fastest stable configuration is **two T4s at 638.9 tokens per second**. One epoch would take 14.17 hours, more than the 14-hour budget, so:

- **every non-probe example is kept**, and **probe examples are kept at rate 0.9707** (seed 2029), which brings the projected time to 14.0 hours.

**Exact selection** (`python -m packages.support_evaluator.training_data --out <dir> --probe-rate 0.9707`; in each tier round(rate × n) probe examples, drawn by `random.Random("2029:tier<N>:probes")`):

| tier | examples | probe examples | probes kept | probes dropped |
|---|---|---|---|---|
| 1 | 6,981 | 2,629 | 2,552 | 77 |
| 2 | 10,101 | 4,640 | 4,504 | 136 |

- **Result:** 16,869 examples, so 1,055 optimiser steps (1,054 of 16 and a last one of 5).
- **Checkpoints:** at steps 264, 528, 792 and 1,055.
- **Record:** `docs/milestone-3/train-v1-budget.json` (sha256 `2f7698a93c1f7e565d75f11de052c11296e1c8f4abb03cd90bb6bca9f1b6644a`) lists all 213 dropped examples (tier, case ID, step).
- **Hashes:** `train.jsonl` `afea958424a31c23851576853ee536beabf73b7cd3b5e2bb89d26ad8bf1abb8b`, `train-budget.jsonl` `2652513a03cd8a88993ea2adc17cc7a06881e345571c3edc724393a6405fee47`.

**The last step has 5 examples, divided by 5.** Each optimiser step's weighted loss Σᵢ wᵢ·ℓᵢ is divided by the number of examples in that step (`train_step` in `packages/hetren_baselines/qlora.py`). That is 16 for steps 1–1,054, and 5 for step 1,055, whose loss is divided by 5.

Training runs on two T4s in two Kaggle sessions of about 7 hours each, with `notebooks/milestone-3/qlora_training.ipynb`:
- **Session 1:** steps 1–528, ending at the 528 checkpoint.
- **Session 2:** resumes from the 528 checkpoint, verified by hash, and runs steps 529–1,055.

**Checkpoints.**
- **Candidates:** the four selection candidates, `checkpoint-0264`, `checkpoint-0528`, `checkpoint-0792` and `checkpoint-1055`.
- **Resume-only:** written every 66 optimiser steps in between (`resume-<step>`, at 66, 132, 198, 330, …). They are never evaluated, and only the newest is kept: each new checkpoint of either kind removes older resume-only ones. Steps 264, 528 and 792 are multiples of 66, so there the candidate is also the resume point.
- **Contents:** both kinds hold the same state (LoRA weights, adapter, optimiser, scheduler, fp16 loss scaler, each process's RNG states and the step reached), with every file's sha256 in `state.json`.

**Resuming.** After a session ends, crashes or stops on a non-finite loss, training resumes from the latest saved checkpoint. The checkpoint's `state.json` must match the sha256 recorded when it was saved: the last `"checkpoint"` entry in `train-log.jsonl`, also printed by the notebook. Every file must match its hash in `state.json`.
- **After a session boundary or a crash:** the same learning rate.
- **After a non-finite loss:** half the learning rate (Amendment 1). A second non-finite loss stops training.
- **Before the first checkpoint (step 66):** training restarts from step 0, at half the learning rate if the cause was a non-finite loss.

**Every resume is logged below:** the checkpoint resumed from and its `state.json` sha256, the reason (session boundary, crash or non-finite loss), the learning-rate scale, and the steps then run.

## Training runs

| # | date (UTC) | platform and GPUs | bundle | settings | steps | outcome | resumed from |
|---|---|---|---|---|---|---|---|
| 1 | 2026-11-03 19:19:54 – 2026-11-04 02:34:42 (session 1) | Kaggle, Tesla T4 ×2 (two processes) | `7e9089e` (bundle sha256 `efa9e303140a279eebf338f04a8b799ce87fce00e569c6303168f2471f5ba943`) | Amendment 1's, as recorded in each run file; data `train-budget.jsonl` `2652513a…`, 16,869 examples, 1,055 steps; LR scale 1.0 | GPU smoke check 0 → 2 and 1 → 2; training 0 → 528 | completed: no non-finite loss; candidate `checkpoint-0264` and `checkpoint-0528` written | none (fresh start) |
| 2 | 2026-11-04, about 02:59 – 03:04:40 (session 2, first attempt) | Kaggle, Tesla T4 ×2 (two processes) | `7e9089e` (same bundle) | as run 1; LR scale 1.0 | resume at 528; no step completed | **failed** in the first optimiser step after the resume (step 529), on both processes: `Error invalid argument at line 578 in file /src/csrc/pythonInterface.cpp`, exit code 1; no checkpoint written, no output kept by Kaggle | `checkpoint-0528` (`613ac6d5…8315`), session boundary |

**Run 1 (session 1), as verified on 2026-11-03:**

- **Archive:** `qlora-train-session-1.tar.gz` sha256 `5425b2782b6bceb017cce63eab30bf588b139d80a5fb15993ec3b25214ae4381` (611,231,985 bytes), extracted to `artifacts/milestone-3/training-session-1/` (gitignored).
- **GPU smoke check** (19:19:54–19:22:45, `qlora-smoke/`, weights never used):
  - two steps straight, writing `checkpoint-0001` (`state.json` `ebbff688…`) and `checkpoint-0002` (`255499ca…`);
  - then a resume from `checkpoint-0001`, its hash verified, repeating step 2 (`checkpoint-0002` `d49ee1db…`);
  - both completed, so saving and loading the 8-bit paged optimiser, the fp16 loss scaler and the adapter work on the GPU. The two step-2 checkpoints differ, which is allowed: bit-identity on the GPU was declared informational only. The smoke checkpoints themselves were not archived.
- **Training** (19:23:16–02:34:42, run file `run-steps-0000-0528.json` `outcome: completed`, `steps_reached: 528`):
  - `train-log.jsonl` has one start entry, steps 1–528 once each in order, and eight checkpoint entries;
  - **no non-finite loss**. Step 1 was skipped by the fp16 loss scaler while it calibrated (as in the pilot), so the scheduler advanced 527 times. The logged learning rates match the cosine schedule (warm-up 32 steps, peak 1e-4 at step 33, 5.25e-5 after step 528) exactly;
  - 49.0 s per step on average (7.19 h of steps);
  - mean loss per 66 steps: 0.275, 0.058, 0.042, 0.035, 0.034, 0.035, 0.033, 0.034.
- **Checkpoints:**
  - resume-only checkpoints at 66, 132, 198, 330, 396 and 462, each removed by the next checkpoint as declared;
  - the two candidates were kept. Every file in each matches its sha256 in `state.json`, and each `state.json` matches the hash logged when it was saved;
  - `checkpoint-0528`'s `state.json` sha256 also matches the one the notebook printed at the end of the session, as confirmed by the operator.

| checkpoint | step | `state.json` sha256 | adapter (`adapter_model.safetensors`) sha256 |
|---|---|---|---|
| `checkpoint-0264` | 264 | `ae7e31e7c23181e4cf30ff55da71210212a0dc63477b7627ce2f9efd24361273` | `40e3a030000d07d8da9187a1007007cf07b96f7ca66d9671132b1950da5f1d89` |
| `checkpoint-0528` | 528 | `613ac6d5e4595a56752804a93701dadb538b06d9dd30b462feaccfb377988315` | `8976b6528b89fe22db3a7295dd55048300b2284a81ee30b0587005300e2bf4bf` |

**Run 2 (session 2, first attempt), as reported by the operator on 2026-11-04.** Notebook `hetren-qlora-training-session-2`, a Copy & Edit of session 1, with session 1's output attached, `SESSION = 2`, `RESUME_SHA256` `613ac6d5…8315`, `LR_SCALE = 1.0`.

- **What worked, from the notebook log:**
  - bundle commit `7e9089e6f26db7e412f755908f83af247d5196ef`;
  - training data rebuilt and checked (17,082 examples; budget 16,869, 213 probe examples dropped);
  - `checkpoint-0528` found under `/kaggle/input/…/qlora-train-session-1/`, with the expected `state.json` sha256, and loaded on both processes.
- **The failure,** at about 322 s (03:04:40 UTC), during the first optimiser step after the resume. No step completed and nothing was written. `checkpoint-0528` is a read-only input and is untouched. Kaggle kept no output files.
- **Cause, verified on 2026-11-04 from the code and the session 1 checkpoints:**
  - **What failed:** line 578 of bitsandbytes 0.50.2's `csrc/pythonInterface.cpp` is the `cudaMemPrefetchAsync` call in `cprefetch` (the CUDA 13 branch). It prefetches a paged optimiser state tensor before each step, and CUDA rejects it with "invalid argument" when the memory is not managed memory.
  - **How the checkpoint caused it:** the paged 8-bit AdamW keeps its large state tensors in managed memory flagged `is_paged`. `torch.save` stores that flag with the tensor; `torch.load` restores the flag but puts the values in ordinary memory. Loading `checkpoint-0528/optimizer.pt` with `weights_only=True` gives 216 tensors (`state1` and `state2` of the 108 LoRA matrices with at least 10⁵ elements) that still carry `is_paged=True, page_deviceid=0` (the same in `checkpoint-0264`). bitsandbytes' `load_state_dict` does not put them back into managed memory, so the first `prefetch_state` after the resume fails.
  - **Why session 1's smoke check missed it:** the fp16 loss scaler skipped step 1, so the optimiser had no state yet in `checkpoint-0001`. The CPU tests use `torch.optim.AdamW`, which has no paged memory.
  - **Not the cause:** the data, the settings, the checkpoint files and their hashes.
- **Fix,** with no setting changed (same paged 8-bit AdamW, learning rate, schedule, data and order):
  - after loading, `load_checkpoint` copies each tensor still flagged as paged, value for value, into a paged buffer allocated by the optimiser itself, as in session 1 (`restore_paged_state`), and prefetches it once straight away;
  - a CPU test reproduces the failure without the fix and shows that a resumed run with it matches the straight run exactly;
  - the notebook runs a one-step resume check in a fresh process before the long run;
  - the notebook now takes its code only from the attached bundle. Session 1's attached output contains that session's copy of the code, `hetren/BUNDLE.json` (`7e9089e`), which the first match could otherwise pick. The notebook stops unless exactly one bundle is found, and stops if the bundle's commit is not the `BUNDLE_COMMIT` set. In run 2 both copies were `7e9089e`;
  - also, `float(loss.detach())` in `train_step` removes a warning without changing the logged value.

**Resumes:**

| attempt | from | `state.json` sha256 | reason | LR scale | steps run | outcome |
|---|---|---|---|---|---|---|
| run 2 | `checkpoint-0528` | `613ac6d5e4595a56752804a93701dadb538b06d9dd30b462feaccfb377988315` | session boundary | 1.0 | none | failed: paged optimiser state not restored (see above) |

Next: session 2 again from `checkpoint-0528`, the latest saved checkpoint. This resume follows a crash, so the learning rate stays the same: scale 1.0, steps 529–1,055.

## Selection subset

**Lists:** `docs/milestone-3/selection-subset-v1/`, written by `python -m packages.support_evaluator.selection_subset write` (seed 2029), and checked against a fresh draw with `--check`.

| tier | source | cases | strata | list sha256 |
|---|---|---|---|---|
| 1 | dataset v2, splits v1 `validation` (550 primaries) | 200 | 8 case kinds | `c0f43cf3dd9633416ad4bcba97b7806b3521bf47490e18310fac4621501cb2e4` |
| 2 | dataset v3, splits v2 `validation` (250 primaries) | 100 | 33 families: 8 single kinds and 25 compound pairs | `431d72886873679c558db70fe71687315be397a373535b62c35bf7a0b40e489c` |

- **Allocation:** proportional to each family's count, with largest remainders. One tier 2 pair, `compound:mapping_swap+misleading_ticket_text`, gets no place.
- **Manifest:** per-family counts and source hashes, sha256 `bde881f24d294060ef4ec38b6c8aec33ddf7f1387078c9ab40fa72f10899fba5`.
- **Strata:** compounds are stratified by pair (`compound:<kind>+<kind>`, the protocol's family key), not as one "compound" kind.

## Reference: untrained Qwen3-4B on the selection subset

Computed on 2026-11-03 from the existing untrained validation rows, with no new run. Command: `python -m packages.support_evaluator.selection_subset score --tier1 <rows-tier1.jsonl> --tier2 <rows-tier2.jsonl>`.

The source rows come from the Milestone 2 validation run on Kaggle (2026-11-02, bundle `beb9b5e`, one Tesla T4, fp16, prompt version 2): `artifacts/milestone-2/baselines/qwen-untrained-validation/qwen-untrained/`, `rows-tier1.jsonl` `773b8dbccbbf9a340fe3b0675eca00eca374295e90d0b6c614e32c0b07ead836` and `rows-tier2.jsonl` `c0371fc8e3da5680c1973f1a760fa77c654460c4c8d213bd9e4853b97454be83`. Each subset case's family matches its row's.

| S | A₁ (tier 1) | A₂ (tier 2) | W (healthy, pooled) |
|---|---|---|---|
| **0.1947** | 25.5% (51/200) [20.0, 32.0] | 16.0% (16/100) [10.1, 24.4] | 1.3% (1/78) [0.2, 6.9] |

| monitoring | tier 1 | tier 2 |
|---|---|---|
| `insufficient_evidence` precision | 8.9% (4/45) [3.5, 20.7] | 3.2% (1/31) [0.6, 16.2] |
| `abstain` recall | 0.0% (0/17) [0.0, 18.4] | 0.0% (0/11) [0.0, 25.9] |

Under Amendment 1, if the chosen checkpoint's S does not exceed 0.1947, the result is reported as it is, and any further training attempt needs its own dated amendment first.

## Validation evaluations

None yet.

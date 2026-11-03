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

- **every non-probe example is kept**, and **probe examples are kept at rate 0.9707** (seed 2029), which brings the projected time to 14.0 hours;
- this keeps about 7,056 of the 7,269 probe examples (tier 1: 2,629; tier 2: 4,640), so about 16,870 examples in all;
- that is about 1,055 optimiser steps of 16 examples, with checkpoints at 25%, 50%, 75% and 100% of those steps.

The training builder makes and records the exact selection, with its counts and hash, when training starts. Training takes two Kaggle sessions (12 hours at most each) and resumes from a saved checkpoint with its optimiser state.

## Training runs

None yet.

## Reference: untrained Qwen3-4B on the selection subset

Pending. It is computed from the untrained validation rows (no new run) when the subset lists are committed.

## Validation evaluations

None yet.

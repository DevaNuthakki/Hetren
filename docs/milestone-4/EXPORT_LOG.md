# Export log (Milestone 4)

Required by `docs/milestone-2/EVAL_PROTOCOL.md`, Amendment 2 ("Export log"). Every export, token-parity check, throughput pilot and validation run of a GGUF variant is logged here, including failed, stopped and aborted ones, **before its results are read**. Each entry gives the date (UTC), platform, CPU model, threads, llama.cpp commit, GGUF sha256, bundle commit, settings, output hashes, outcome and who ran it.

No GGUF variant is ever run on a test split. The fine-tuned model's test results remain those of test runs #5 and #6 (`docs/milestone-2/TEST_RUN_LOG.md`).

How each run is done: `docs/milestone-4/EXPORT_RUNBOOK.md`.

## Fixed inputs

| input | value |
|---|---|
| chosen checkpoint | `checkpoint-0792`, `state.json` `d6230ff6e1780ac5286f0accc0a45298dd8db49fc11ed6fdb1330d98189276d5`, adapter `5647f93f25c9f79c8e7fca0468d8aa7476afbcc348f3b42f420d1845098f4226` |
| selection choice | `choice.json` `d41a7ef595e8882ff0dbb367e62b03b87c8f1006bb60da09811fb19f11992332` |
| base model | `Qwen/Qwen3-4B-Instruct-2507`, revision `cdbee75f17c01a7cc42f958dc650907174af0554`, fp16 |
| llama.cpp | release `v0.7.0`, commit `620d2225cc436ab0b001e3200e590e3b286ef9ab` |
| variants | Q8_0, Q4_K_M (no importance matrix) |
| fp16 comparator | full validation of `checkpoint-0792` (`docs/milestone-3/VALIDATION_LOG.md`): rows `acee959428a94ad35ad3af4d6acd518195e79ee369f3e37abb7a30ae93f5a680` (tier 1), `51e1f821b9e649dd791bf59552d9912ea8f402e9b836c087b33192b3a236b34b` (tier 2) |

## Decisions recorded before any export (operator, 2026-11-07)

- **Merge:** on a Kaggle T4 (`--device cuda`) with the Milestone 3 evaluation libraries (`transformers` 4.56.2, `accelerate` 1.10.1, `peft` 0.17.1, the platform's `torch`), as every fp16 evaluation merged. No hash of the merged weights was logged in Milestone 3, so identity with the evaluated merge is by procedure, not by hash.
- **Conversion:** in a separate venv built from llama.cpp's own requirements at `620d2225` (`requirements/requirements-convert_hf_to_gguf.txt`, which pins `transformers` 4.57.6 and CPU `torch` 2.11.0) plus the checkout's `gguf-py`; every version is recorded in the export manifest. The token-parity checks, not the library versions, establish that the tokenizer survived conversion.
- **Parity driver:** runs in the evaluation environment, with the checkout's `gguf-py` installed without dependencies.
- **Where:** merge, conversion, quantisation and token parity in one Kaggle notebook (`notebooks/milestone-4/gguf_export.ipynb`), so the Kaggle CPU pilot can attach its output directly. The merged weights and the f16 GGUF stay in scratch space and are recorded by hash only.

## Known limitation: the finite check is a stand-in

The fp16 runs checked that every generated step's **raw logits** were finite. `llama-server` does not expose raw logits, so for GGUF runs `finite` means that every generated token's reported **log-probability** (`n_probs` 1) is a finite number. A non-finite logit that does not reach the chosen token's log-probability would not be detected. Accepted by the operator on 2026-11-07.

## Exports

| # | date (UTC) | platform | bundle | llama.cpp | outcome | outputs and hashes | notes |
|---|---|---|---|---|---|---|---|
| 1 | 2026-11-07 (exact UTC times not reported; failed about 16 minutes after the start) | Kaggle, GPU T4 ×2, internet on, pinned environment; notebook `hetren-gguf-export`, version `export-1` | `f8b021d78378e8ed9ac1a729f0f951a364885c79` (archive sha256 `6b8926c73226f3aa1fb9fd38100ff556674885b32746d2149da44c031964dc55`) | `620d2225cc436ab0b001e3200e590e3b286ef9ab` | **failed** at the conversion venv: `/usr/bin/python3 -m venv /tmp/hetren-export/convert-venv` exited 1 because its `ensurepip --upgrade --default-pip` step exited 1 (the platform's system Python has no working `ensurepip`). Nothing was converted, quantised or checked for parity | none: the notebook stopped in cell 3 before writing anything to `/kaggle/working/gguf-export/`; the merged weights existed only in scratch space and were discarded with the session | reported by the operator. Before the failure: bundle found with the expected commit; 1,038.2 GB of free scratch space; `checkpoint-0792` and `choice.json` found by hash; merged on a Tesla T4 in 2.9 min ("12 files recorded"); `llama-quantize` and `llama-server` built in 5.8 min. Fix: the conversion environment is created with a pinned `virtualenv` (21.14.13, installed into its own directory, so the evaluation environment is unchanged), and the notebook now builds it, with the converter's requirements, before the merge. Retried as `export-2` |
| 2 | 2026-11-07 (exact UTC times not reported; the kernel log covers 24.2 minutes, 1,454 s) | Kaggle, GPU T4 ×2 (merge on one Tesla T4; conversion, quantisation and parity on the CPU, Intel Xeon @ 2.00GHz, 4 vCPUs), internet on, pinned environment; notebook `hetren-gguf-export-2`, version `export-2`, status Successful | `9e95147c722d0359da388299e72fb2d8086e80a3` (archive sha256 `f8eee348673a2978f911c165d112d6dba6d704f574d00ef072e06785f74151b3`) | `620d2225cc436ab0b001e3200e590e3b286ef9ab`, server build `b11669-620d2225c` | **completed**. Merged with `transformers` 4.56.2, `accelerate` 1.10.1, `peft` 0.17.1 (`torch` 2.11.0+cu130); converted with `transformers` 4.57.6, `torch` 2.11.0+cpu, `gguf` 0.19.0; Q8_0 and Q4_K_M quantised from the f16 GGUF without an importance matrix | `export.manifest.json` `4a2431a46a31045d74bf48da291fcbf09692a794e58d66d7135ede1cdc433ee0` (committed as `docs/milestone-4/export.manifest.json`); `merge.json` `8508b6aae54ead5c25529ebdb086e9a250ed8cf808b1368ea63127be32af3e17`; `environment.json` `11b45c420ee3a931228ae21cb822f056d225846f97285878be0ab22db4f04a03`. GGUFs: Q8_0 `496c74a750ef32d0c52dd9644e51b36547dda762c498ac89eece1a24bab3ba29` (4,280,403,360 bytes), Q4_K_M `e3f50ba98ee7e800554dec7ec1c403e7f1d47d4595300e6a6a3e8bf7ffe8763e` (2,497,278,880 bytes); f16 `70e69512cfa6e24c97a0abf4a86840835eea7b8bbda8125fde7fdc3f5c10902d` (8,051,283,360 bytes, scratch only, recorded by hash). Merged weights recorded by hash in `merge.json` (shards `88e86b39…`, `2fb4cf48…`), not kept | run by the operator; all 16 output files downloaded with the Kaggle CLI and checked by the operator with `shasum -a 256 -c outputs.sha256` (all OK). Checked by Claude Code on 2026-11-07: every hash recomputed; manifest `merge` section equals `merge.json`; checkpoint, `state.json`, adapter, `choice.json`, base revision and llama.cpp commit equal the pinned values; the 9 tokenizer files equal the merged directory's hashes; the bundle copy left in the output equals commit `9e95147` (598 tracked files). Timeline from the kernel log: bundle checks at 151 s; conversion venv created in 5 s and ready in 1.0 min (before the merge); merge 2.6 min; llama.cpp CPU build 5.4 min; conversion and both quantisations 5.8 min (Q8_0 57.9 s, Q4_K_M 183.8 s); parity 1.6 min (Q8_0) and 1.4 min (Q4_K_M). Harmless messages: pip's dependency-conflict warnings for packages the export does not use (gradio, diffusers, litellm), and `Error in sitecustomize … No module named 'wrapt'` from every conversion-venv Python: the platform's `sitecustomize` imports `wrapt`, which is in the evaluation environment (1.17.3) but not in the isolated venv; Python skips a failing `sitecustomize`, and the recorded converter libraries are the venv's |

## Token parity

| # | date (UTC) | variant (GGUF sha256) | server build | texts checked | outcome | report sha256 | notes |
|---|---|---|---|---|---|---|---|
| 1 | 2026-11-07 (in export 2) | Q8_0 (`496c74a750ef32d0c52dd9644e51b36547dda762c498ac89eece1a24bab3ba29`) | `b11669-620d2225c` (`-c 4096 -np 1 -ngl 0`) | 6,569 (every distinct prompt, target and target + `<\|im_end\|>` of the 4,902 validation steps, tiers 1 and 2) | **parity**: 0 vocabulary problems, 0 round-trip problems | `parity-Q8_0.json` `71f9ed4351328d8bee140a42428876367c6958085fae465affd43fb34ee26f30` | vocabulary check against the merged model's tokenizer: tokens, merges, token types, padding, end-of-generation tokens, EOS, no BOS added, pre-tokenizer `qwen2`. Round trip: `/tokenize` of each text equals the Hugging Face token IDs and `/detokenize` of those IDs equals the text. Exit 0 |
| 2 | 2026-11-07 (in export 2) | Q4_K_M (`e3f50ba98ee7e800554dec7ec1c403e7f1d47d4595300e6a6a3e8bf7ffe8763e`) | `b11669-620d2225c` (`-c 4096 -np 1 -ngl 0`) | 6,569 (as above) | **parity**: 0 vocabulary problems, 0 round-trip problems | `parity-Q4_K_M.json` `f821649e3588422c00b8266e9784ac54c033ea1ba9ad90b8f3744e18e38f6113` | as above. Exit 0 |

## Throughput pilot

| # | date (UTC) | platform, CPU, threads | variant | caching | seconds per call | repeats identical | outcome | output hashes |
|---|---|---|---|---|---|---|---|---|
| 1 (Mac) | 2026-11-07 21:17:24 – 2026-11-08 00:18:24 | Mac, Intel Core i7-8850H, `-t 6` | Q8_0 | on | 16.6 (tier 1), 18.4 (tier 2) | 20/20 | completed in 22.2 min: 74 calls; prompt 25.1 tokens/s (305 of 1,824 prompt tokens evaluated per call on average), generation 4.9 tokens/s; peak memory 5.09 GB; projected **7.03 h** for full validation | episodes `ba63e584395e9854924cb5005b291d55d72f916fbf589ed24bac3ae3e0a77fb7` |
| 1 (Mac) | as above | as above | Q8_0 | off | 68.8, 78.4 | 20/20 | completed in 93.0 min: 74 calls; prompt 26.3 tokens/s (whole prompt every call), generation 4.7 tokens/s; peak 5.09 GB; projected 29.49 h | episodes `102fb776f70ed433653c49f7fb7f70e80358c341ef925905f6574405b8ae3207` |
| 1 (Mac) | as above | as above | Q4_K_M | on | 12.5, 12.7 | 20/20 | completed in 15.0 min: 70 calls; prompt 37.9 tokens/s (304 of 1,820), generation 6.2 tokens/s; peak 5.05 GB; projected **5.08 h** | episodes `524c9357eaf0adef37a8e523c882c193d206957c212127f8ea9400ea96ad9d31` |
| 1 (Mac) | as above | as above | Q4_K_M | off | 43.6, 45.2 | 20/20 | completed in 50.8 min: 68 calls; prompt 45.3 tokens/s, generation 6.4 tokens/s; peak 5.06 GB; projected 17.84 h | episodes `5056b4a0ca4ca478cc322a2c0305f3426676c7173dc8e336501525a023a70343` |
| 1 (Kaggle) | 2026-11-07 21:32:34 – 2026-11-08 05:46:32 | Kaggle CPU notebook `hetren-gguf-pilot`, version `pilot-1`, Intel Xeon @ 2.20GHz (4 vCPUs: 2 cores × 2 threads; AVX2, FMA, F16C; no AVX-512), `-t 4` | Q8_0 | on | 38.4, 42.8 | 20/20 | completed in 51.4 min: 74 calls; prompt 9.6 tokens/s (305 of 1,824), generation 2.9 tokens/s; peak 5.04 GB; projected **16.29 h** | episodes `e7cce6fa1f062ec9680ba1717410fab4c0ccd49f6dba16fa9b58d63ad5b3987f` |
| 1 (Kaggle) | as above | as above | Q8_0 | off | 171.1, 188.9 | 20/20 | completed in 226.0 min: 74 calls; prompt 10.5 tokens/s, generation 2.9 tokens/s; peak 5.04 GB; projected 72.2 h | episodes `26c01d6089e8784e2491f7d56acd3f91e428e95e3cfc0c44e69b78a02781081f` |
| 1 (Kaggle) | as above | as above | Q4_K_M | on | 33.1, 35.7 | 20/20 | completed in 42.2 min: 72 calls; prompt 11.4 tokens/s (305 of 1,822), generation 3.6 tokens/s; peak 5.01 GB; projected **13.8 h** | episodes `16f3006f20476e490e15d6d8ff12967d199a5709142904e2efe414e80451b7b0` |
| 1 (Kaggle) | as above | as above | Q4_K_M | off | 140.2, 154.3 | 20/20 | completed in 174.2 min: 70 calls; prompt 12.9 tokens/s, generation 3.5 tokens/s; peak 5.01 GB; projected 59.06 h | episodes `736663f659063166fb38a964c0032a82e2ace79dc8a6d9613f11b3edcaecb2e5` |

**Pilot 1, both platforms.** Run by the operator from commit `d3228db1e6f82ce33239f96eca92a69b1c57d7dd` on export 2's files (manifest `4a2431a4…`, GGUF hashes as in the token-parity entries), llama.cpp `620d2225`, build 11669, CPU-only with the export's CMake flags; `llama-server -c 4096 -np 1 -ngl 0 -b 2048 -ub 512`, a fresh server per variant and caching setting, under `/usr/bin/time`; Amendment 2's greedy decoding; the 20 fp16 smoke-test cases of the validation run (10 per tier, the same case IDs as `smoke-tier<N>-validation`), each episode twice per setting, pass after pass. Episodes were not scored.
- **Mac:** macOS 15.4.1, 12 logical CPUs, on mains power under `caffeinate -dims`; server built with AppleClang 17.0.0; pilot venv `~/.hetren-pilot` (Python 3.13.1, `requirements-gguf-pilot.txt`, `pip check` clean). Exit 0. Report `pilot-mac.json` `888892faf7620635ce19d4c1c9b8f6573396eb7e8b6293c099add825b7594241`; console log `mac.log` `42309d2626c25211ecb7855a5f4bc90d99c8e647873bd2206a821a4ad491f079`.
- **Kaggle:** accelerator None, internet on, pinned environment; bundle 3 (`d3228db`, archive sha256 `2c65072bc71b277a0d079209fd85c9c20e732b5f97a351b6e26bba384909d335`); server built with GNU 13.3.0; Python 3.13.18; `/usr/bin/time` (GNU) installed by the notebook. Status Successful, pilot exit 0; all 10 files listed in `outputs.sha256` checked by the operator. Report `pilot-kaggle.json` `f9a6cf9f258f6ae3eb6f5f3420a4a98b54321b2d5796cd89d378bb3434175f06`; `environment.json` `eb7ad21aa08c4fcf40f4c8b02e81fad79495938405c568a3e06cf78dcddaac31`.
- **Checked by Claude Code on 2026-11-08:** both reports name the committed manifest, its GGUF hashes, the pinned llama.cpp commit and build, the platform's thread count and the declared server and decoding settings; every block holds the 20 cases once per repeat (2 repeats × 2 caching settings × 2 variants = 160 episodes per platform); with caching on every call but each block's first reused the cached prefix, with caching off every call evaluated its whole prompt; every summary figure was recomputed from the episode files and the peak memory from `/usr/bin/time`'s report; every call (286 on the Mac, 290 on Kaggle) had finite log-probabilities and ended on `<|im_end|>`; none reached the token limit.

**Finding: outputs depend on the caching setting and the platform, although repeats within one setting are identical.** Q8_0's episodes were identical in all four platform and caching combinations. Two Q4_K_M tier 2 episodes differed (first repeats compared; second repeats equal the first everywhere):
- `case-002104`: 2 calls on the Mac with caching on and on Kaggle with either setting; 1 call on the Mac with caching off;
- `case-004849`: 1 call on the Mac with either setting and on Kaggle with caching off; 2 calls on Kaggle with caching on.

Both end in the same final action in every combination; the difference is an extra step. Greedy CPU decoding is deterministic for a fixed platform, build, thread count and caching setting, but these change how the arithmetic is split (which prompt tokens are evaluated together, and the platform's own kernels), and a near-tie between two tokens can then resolve differently. This is why Amendment 2 runs the validation on one platform with one caching setting, both fixed by this pilot.

**Not recorded: the CPU features each build used.** The reports' `system_info` and server-settings fields are empty on both platforms: at this llama.cpp commit `llama-server` writes the `system_info` line only at log verbosity 4 (`-lv 4`), above its default of 3, so the pilot (which parses the server's log) found nothing, and `decide` first reported `same_cpu_features: true`, which was vacuous (both sides empty). `decide` now reports `null` (unknown) when either side is missing, and the decision below was made with the corrected version. What is known instead:
- **Mac**, from the same binary on 2026-11-08 (Claude Code, `llama-server -lv 4 -t 6` with a non-existent model file, so nothing was loaded or run): `system_info: n_threads = 6 (n_threads_batch = 6) / 12 | CPU : SSE3 = 1 | SSSE3 = 1 | AVX = 1 | AVX2 = 1 | F16C = 1 | FMA = 1 | BMI2 = 1 | LLAMAFILE = 1 | ACCELERATE = 1 | OPENMP = 1 | REPACK = 1 |`; its `build/CMakeCache.txt` has AVX, AVX2, BMI2, F16C, FMA, SSE4.2, LLAMAFILE and OpenMP on and every AVX-512 option off. `ACCELERATE = 1` although BLAS is off: on macOS the CPU backend uses Apple's Accelerate for some operations, so the Mac's code path differs from Linux's in more than threading.
- **Kaggle:** not recorded; the build was in the session's scratch space. The same commit and CMake flags (generic x86_64, `GGML_NATIVE=OFF`) select the same AVX2-level kernels without Accelerate, but this is inferred, not observed. The host CPU has no AVX-512 (`lscpu`).

**Known runtime difference: llama.cpp treats `</s>` as an end-of-generation token.** At load, both servers logged `control-looking token: 128247 '</s>' was not control-type … its type will be overridden`: llama.cpp adds token 128247 (`</s>`, an ordinary token in this vocabulary) to its end-of-generation set, so a GGUF generation would stop on it where the fp16 runs (which stop on `<|im_end|>` or `<|endoftext|>`) would continue. The token-parity check did not cover this (it compares the file's token types, which are correct). It has not happened: no pilot call generated token 128247 (every call ended on `<|im_end|>`), and no fp16 validation reply contains `</s>` (0 of 1,446 calls).

Pilot choices (caching setting and platform, under Amendment 2's rules) are recorded here before the validation run.

**Pilot choices (operator, 2026-11-08), recorded before the validation run.** From `python -m packages.support_evaluator.gguf_pilot decide` on both reports (`decision.json` `861bbcdbcbf2245594e9640735e26fdfd3f8058518c26df9ed4539bfef6b5c42`):
- **Caching on.** Repeats were byte-identical in every block on both platforms, with caching on and off, so the caching rule keeps it on.
- **Platform: the Mac.** Kaggle does not qualify: with caching on its projected full-validation times are 16.29 h (Q8_0) and 13.8 h (Q4_K_M), above 12 × (1 − 0.2) = 9.6 h. The Mac qualifies: 7.03 h and 5.08 h, repeats identical, no session limit.
- **Settings of the validation run:** both variants on the Mac (Intel Core i7-8850H, macOS, the pilot's llama.cpp build at `620d2225`), `-t 6`, `-c 4096 -np 1 -ngl 0 -b 2048 -ub 512`, prompt caching on, Amendment 2's greedy decoding; `same_cpu_features` is unknown (`null`).
- **Run decisions:**
  - no separate smoke test (the pilot ran the 20 smoke cases on this platform with these settings);
  - a stopped run may be resumed only to complete the same declared run, and the log names the case it restarted at (with caching on, that case starts from an empty cache);
  - every call records whether generation ended on a token other than `<|im_end|>` or `<|endoftext|>` (such as llama.cpp's added `</s>`); the count and the case IDs are reported, and the runtime is not changed.

**Limitation: the validation platform is not the shipped platform.** The validation runs on macOS, whose llama.cpp build uses Apple's Accelerate (`ACCELERATE = 1`); the shipped Docker image and the Kubernetes deployment run on Linux x86_64. The pilot showed that the platform can change Q4_K_M episodes (`case-004849`), so the accepted variant's validation result describes the Mac configuration, not the Linux one, exactly. **Descriptive check (Docker step, not part of acceptance), measured on 2026-11-09** ("Linux checks in the Docker image" below): the 20 pilot cases in the shipped image's build (Linux x86_64, the fixed AVX2 build without Accelerate), with the validation run's decoding, caching and thread settings, against the Mac validation run's episodes for the same cases:
- **Q8_0:** 20 of 20 episodes the same (tier 1 10 of 10, tier 2 10 of 10), every generated token the same (37 of 37 calls).
- **Q4_K_M (the shipped default):** 18 of 20 episodes the same (tier 1 10 of 10, tier 2 8 of 10). The two that differ are `case-002104` and `case-004849`, the two cases the pilot found sensitive to platform and caching: on Linux each first probes `inspect` on `routing_policy`, then decides `no_intervention`, the Mac's only action. The final decision is the same; the episode is one step longer.
- **The CLI in the image** (Q4_K_M, offline): the same first action as the validation run on 10 of 10 tier 1 cases, as on the Mac.

So on these 20 cases the Linux image reproduces Q8_0's validated behaviour exactly and Q4_K_M's on 18. The Q4_K_M differences are the known near-ties, resolved as on Kaggle's Linux build (an extra probe, the same decision). Twenty cases cannot bound the rate on the full split, so the validation result still describes the Mac configuration exactly and the Linux image approximately. It is reported, and never changes an acceptance decision.

## Validation runs

| # | date (UTC) | variant (GGUF sha256) | platform, CPU, threads | settings | outcome | output hashes |
|---|---|---|---|---|---|---|
| 1 (Q4_K_M) | tier 1 2026-11-08 15:37:23 – 17:37:14; tier 2 17:37:15 – 19:41:18 (4.07 h in all) | Q4_K_M (`e3f50ba98ee7e800554dec7ec1c403e7f1d47d4595300e6a6a3e8bf7ffe8763e`) | the Mac, Intel Core i7-8850H, macOS, `-t 6`; `llama-server` build 11669 at `620d2225` (AppleClang 17.0.0, binary sha256 `35713c77004d180d3e4cfce85e048b5c74508f89ac8a2acf1dce9073c737f374`); `system_info: n_threads = 6 (n_threads_batch = 6) / 12 \| CPU : SSE3 = 1 \| SSSE3 = 1 \| AVX = 1 \| AVX2 = 1 \| F16C = 1 \| FMA = 1 \| BMI2 = 1 \| LLAMAFILE = 1 \| ACCELERATE = 1 \| OPENMP = 1 \| REPACK = 1 \|` | the pilot's choice: prompt caching on, `-c 4096 -np 1 -ngl 0 -b 2048 -ub 512`, greedy (`top_k` 1, temperature 0, no penalties, 128 tokens), prompt version 2; one fresh server per tier; commit `ef801a57524d873fb0de459cfddd2a0dc29bbe2e`; pilot venv (Python 3.13.1, `transformers` 4.56.2, `tokenizers` 0.22.2); datasets as their committed manifests; splits `splits-v1/validation.txt` `89f251d1…`, `splits-v2/validation.txt` `ccc5ed74…` | **completed**, exit 0, one session per tier, no restarts. Tier 1: 550 cases, 745 calls (9.6 s per call), peak memory 5.06 GB. Tier 2: 250 cases, 630 calls (11.7 s per call), peak 5.07 GB. Every call finite; none at the token limit, none discarded; **0 calls ended on a token other than `<\|im_end\|>` or `<\|endoftext\|>`**. Results not read before this entry | completion records `validation-Q4_K_M-tier1.json` `3617e6afc602ffada18fd4dfe6d8c2eabcd12894376e40ef44ab3f60d929bfef`, `validation-Q4_K_M-tier2.json` `d7da7356830cc08a7fb8b48266e0cfd46473fce726328876b3958906fe5fdb86`; rows tier 1 `bca20c5ed36308d27b478082e3ce3769ef00f1da2313392bac87837c24814c6c`, tier 2 `30620cc6ab5c1b6d0c00c47779b16761c42f5a914b8b453b51179d0efa9b391b`; calls tier 1 `e284039887f2787b706f264a51bac2deecf7fdacfada354dcca89165481414ec`, tier 2 `c67a4dc1d942e1e37953daaf139845829826605e94e6eafd0525740f6af6fb87`; console log `Q4_K_M.log` `359d97892684935ae0962f5fd17bcc438b1b366d9e967d64987e7da5a5219518` |
| 1 (Q8_0) | tier 1 2026-11-08 20:45:17 – 23:45:29; tier 2 2026-11-08 23:45:30 – 2026-11-09 03:19:20 (6.57 h in all) | Q8_0 (`496c74a750ef32d0c52dd9644e51b36547dda762c498ac89eece1a24bab3ba29`) | as Q4_K_M: the Mac, Intel Core i7-8850H, macOS, `-t 6`; `llama-server` build 11669 at `620d2225` (binary sha256 `35713c77…`); the same `system_info` line | as Q4_K_M, except the commit: `4c3d1a71494442461f7a07e9e5e8b9aab9345e42` (it differs from `ef801a5` only in this log, so the run's inputs are those of the Q4_K_M run) | **completed**, exit 0, one session per tier, no restarts. Tier 1: 550 cases, 731 calls (14.7 s per call), peak memory 5.08 GB. Tier 2: 250 cases, 708 calls (18.0 s per call), peak 5.10 GB. Every call finite; none at the token limit, none discarded; **0 calls ended on a token other than `<\|im_end\|>` or `<\|endoftext\|>`**. Results not read before this entry | completion records `validation-Q8_0-tier1.json` `794c18394023915d8cdba6bbcf050e81e93e150ab057934a808e5eb9272890ce`, `validation-Q8_0-tier2.json` `ce3173f8ca7454edd99843b0f47caaa36ffbb3ff29c1e6d780325a6ecbdf69b4`; rows tier 1 `ab4e204a7e495c3f8606e3592cf4117304a5939e6788da7d9e20865e78d3008f`, tier 2 `3f7503090a81cbdcfbcad2f17bd3a4ff00f8af5d73af5f5efb9e31ac4e3fea79`; calls tier 1 `39a0cd631bdf002ca6281daebb90df43fe332f27aaa1b27a3fcbf642874885b4`, tier 2 `2a603adad678489b2899b2606c7db2d4aa357d6e8a5f692662b4b83a13f70a60`; console log `Q8_0.log` `95ac4ff85eb0e0a2540bf231103fb07018b3a3439d3ce2d94a4abaf72ede9d15` |

**Validation 1, Q4_K_M.** Run by the operator on 2026-11-08 from `ef801a5` (`git status` showed only the untracked amendment draft); the `system_info` line matched the pilot's. Checked by Claude Code on 2026-11-08 without reading any result (no rows, summaries or replies were inspected; only hashes, metadata, sessions and counts): every file has the hash its completion record lists; the metadata is the declared run (the manifest's Q4_K_M sha256, `mac`, 6 threads, caching on, `620d2225`, the pilot's CPU); each tier holds every validation case once, the same case IDs as the fp16 comparator; times are from `sessions.jsonl`.

**Validation 1, Q8_0.** Run by the operator on 2026-11-08 (UTC: 2026-11-08 to 2026-11-09) from `4c3d1a7`, the commit that logged the Q4_K_M run; `sessions.jsonl` records it as `head` in both tiers and the metadata as `bundle_commit`, and the runner starts only when no tracked file differs from that commit except this log. The `system_info` line matched the pilot's and the Q4_K_M run's. Checked by Claude Code on 2026-11-08 in the same way and without reading any result (only hashes, metadata, sessions and counts): every file has the hash its completion record lists; the metadata is the declared run (the manifest's Q8_0 sha256, `mac`, 6 threads, caching on, `620d2225`, the pilot's CPU, the same server settings, decoding, prompt version, libraries and dataset hashes as Q4_K_M); each tier holds every validation case once, the same case IDs as the fp16 comparator; tier 1 started at `case-000035` and tier 2 at `case-000147`, each with an empty cache.

## Acceptance and shipping (Amendment 2)

Computed by Claude Code on 2026-11-08, after both validation runs were logged (`b95eed8`), with the committed `gguf_check` (`c25401f`, committed before any validation result existed) and the runbook's commands: `gguf_check check` for each variant and `gguf_check ship`, all exit 0. Paired bootstrap from `metrics.paired_bootstrap`, 10,000 resamples, seed 2026; every difference is GGUF − fp16 (fp16: `validation-run-1`, rows `acee9594…` and `51e1f821…`); the pooled comparison pairs the 800 cases by tier and case ID.

| criterion (Amendment 2) | Q4_K_M | Q8_0 |
|---|---|---|
| 1. pooled decision-accuracy 95% lower bound ≥ −0.02 (800 cases) | **−0.0150**, holds (difference −0.0013, CI [−0.0150, +0.0125]) | **−0.0138**, holds (difference −0.0075, CI [−0.0138, −0.0025]) |
| 2. tier 1 decision-accuracy point estimate ≥ −0.02 (550 cases) | **+0.0055**, holds (408 vs 405 correct; CI [−0.0109, +0.0218]) | **−0.0055**, holds (402 vs 405; CI [−0.0127, 0.0000]) |
| 2. tier 2 decision-accuracy point estimate ≥ −0.02 (250 cases) | **−0.0160**, holds (186 vs 190; CI [−0.0440, +0.0120]) | **−0.0120**, holds (187 vs 190; CI [−0.0280, 0.0000]) |
| 3. tier 1 wrong interventions on healthy cases: CI not entirely above 0 (171 cases) | CI [0, 0], holds (0 vs 0) | CI [0, 0], holds (0 vs 0) |
| 3. tier 2 wrong interventions on healthy cases: CI not entirely above 0 (54 cases) | CI [−0.0556, 0], holds (0 vs 1) | CI [0, 0], holds (1 vs 1) |
| **accepted** | **yes** | **yes** |
| episode agreement with fp16 (reported, not a criterion) | 637 of 800 (79.6%): tier 1 476 of 550 (86.5%), tier 2 161 of 250 (64.4%) | 741 of 800 (92.6%): tier 1 521 of 550 (94.7%), tier 2 220 of 250 (88.0%) |
| unexpected stops | 0 | 0 |

**Shipping decision: Q4_K_M.** Both variants are accepted, and Amendment 2's rule ships the smaller accepted one (Q4_K_M before Q8_0), so no differences need to be stated as a failed acceptance (`state_differences: false`).

Outputs (in `artifacts/milestone-4/validation-1/`): `check-Q4_K_M.json` `cc4d34798a894009df0d500ee97bbcb2ed2fb7ff5a68a3ab8a1dff296ea99229`, `check-Q8_0.json` `da9ccd8877b019d78aa2d4e5c2801309fcf9c5414221505c401c5cc168fcf51d`, `ship.json` `40f0a7ac87c4c1e394d16d33462c0ae8f84faeae23281a6a08217e81a2a8956c`. Inputs as recorded in the checks: the fp16 rows above and the completion records `3617e6af…`, `d7da7356…` (Q4_K_M) and `794c1839…`, `ce3173f8…` (Q8_0).

**Descriptive findings** (recorded with the result; none changes the acceptance or the shipping decision):

1. **Q8_0 is significantly less accurate than fp16 overall, within the margin.** Its pooled interval [−0.0138, −0.0025] excludes 0 (the bootstrap's verdict: fp16 better), by −0.75 points, inside the −2-point margin. Q4_K_M shows no significant pooled difference (−0.13 points, CI [−1.50, +1.25]).
2. **Q4_K_M clears the pooled criterion narrowly and agrees with fp16 less often.** Its pooled lower bound is −0.0150 against the −0.02 threshold, and its episodes agree with fp16's in 79.6% of cases (64.4% in tier 2), against 92.6% (88.0%) for Q8_0. Equal accuracy is reached partly through different episodes.
3. **In tier 2, Q4_K_M trades missed faults for fewer wrong interventions.** It chose `no_intervention` 84 times against fp16's 68 (precision 0.64 against 0.78), so it left 30 broken cases unfixed against fp16's 15 (cases whose label is not `no_intervention`: a recovery, `abstain` or `insufficient_evidence`; 84 − 54 and 68 − 53, since Q4_K_M gave `no_intervention` to all 54 healthy cases and fp16 to 53), while making 0 of 54 wrong interventions on healthy cases against fp16's 1 of 54. The quantized model is more conservative. Neither acceptance criterion measures missed faults: criterion 3 counts only wrong interventions on healthy cases, and decision accuracy weighs a missed fault like any other wrong decision.

**Release plan** (operator, 2026-11-08; it does not change the shipping decision): Q4_K_M ships as the default under Amendment 2's rule (the CLI's `fetch-model` default, the Docker and Kubernetes configuration). Since Q8_0 also passed, both GGUFs will be published in the Hugging Face model repository, with Q8_0 offered as the higher-fidelity alternative (episode agreement 92.6% against 79.6%), and the model card states these trade-offs: findings 1–3 and the platform limitation above.

## CLI check on the real model (step 4, descriptive)

Run by the operator on 2026-11-08 on the Mac from `bb79c8a7c9a6ad533876884f8921a71353ba6251` (`git pull` already up to date; `git status` showed only the untracked amendment draft), with the runbook's section 6 command: `cli_check run --variant Q4_K_M`, exit 0. For each of the 20 pilot cases (10 per tier), the CLI ran as a user runs it (`python -m packages.hetren_cli diagnose --compact <first-step input> --format json`, one process and one fresh `llama-server` per case) and its action was compared with the Q4_K_M validation run's first call for that case. Checked by Claude Code on 2026-11-08: every report records the commit, Q4_K_M with the manifest's sha256 (`e3f50ba9…`), llama.cpp `620d2225c` (the validated build, build 11669), 6 threads and prompt version 2; every generation was finite and ended on `<|im_end|>` or `<|endoftext|>` (no unexpected stop token); prompts were 1,549–1,744 tokens. Nothing here gates anything.

| tier | comparison | same first action | outcomes from the CLI | seconds per case (whole CLI process) |
|---|---|---|---|---|
| 1 | like for like: the same input and the same tier 1 prompt; only the prompt cache differs (the CLI's server starts empty) | **10 of 10** | 5 decisions, 3 proposed recoveries, 2 probe requests | 46.6–56.7 |
| 2 | not like for like: the validation run used the tier 2 prompt, the CLI always uses the tier 1 prompt | 6 of 10 | 4 decisions, 3 proposed recoveries, 3 probe requests | 48.7–57.7 |

- **Tier 1:** the CLI reproduces the validated first action on all 10 cases, including with an empty prompt cache.
- **Tier 2 differences** (expected: the prompts differ, as well as the cache, so the cause of each is not separated; the CLI does not support two-step recovery): `case-000329` and `case-002391`, where the CLI proposed `rerun` and the validation run first probed with `retry` on `read_ticket`; `case-002287`, a `reroute` of the same ticket to `Q-MANUAL` instead of `Q-TRIAGE`; and `case-008313`, a `find_owners` probe instead of `history`. The two cases the pilot found sensitive to platform and caching (`case-002104`, `case-004849`) gave the same first action.
- **Time:** about 50 s per case, 17.4 minutes in all. Most of a case is the CLI's fixed cost: the GGUF's sha256 (2.5 GB), the tokenizer, and the server's model load, before one generation.

Outputs (in `artifacts/milestone-4/cli-check-1/Q4_K_M/`: `inputs/`, `reports/`): `summary.json` `9f26d0e9e6a1c34f9d6389380ac77a66ddcbb320c16beaf70047608f57bf9209`, `cases.jsonl` `a8d7975591d130ccc6935e39fafcbb9ce6374856b664cee84dbb04060f493483`; console log `cli-check-1.log` `afed11ebec4778b3f399172a28ed32c2fb0370d80e412d2e0bab00d0fb753017`; compared against the validation calls tier 1 `e2840398…`, tier 2 `c67a4dc1…` (as recorded in the summary).

## Linux checks in the Docker image (step 5, descriptive)

Run by the operator on 2026-11-09 on the Mac from `d2e01b4922af85f7d6e1d8c42956caf2ba03a4e4` (`git pull` already up to date; `git status` showed only the untracked amendment draft), with the runbook's section 7 commands, one container at a time. Nothing here gates anything.

**Platform.** Docker Desktop's Linux VM on the Mac's Intel Core i7-8850H: Linux 6.12.72-linuxkit x86_64, 12 logical CPUs, `MemTotal` 16,766,697,472 bytes (15.62 GiB; 14.70 GiB available at the check's start). Docker Desktop's memory setting was raised after the operator first reported 7.654 GiB; the check's guard needs 7 GiB for one server at a time. Python 3.13.18, `transformers` 4.56.2, `tokenizers` 0.22.2.

**Images**, built locally from that commit:
- `hetren-cli:dev` (`runtime` target, `sha256:28263d1b783970cbf076f7b406adab6b09eb685eb12a97429914163001aa89d5`) and `hetren-cli:check` (`sha256:4715adcc42d7318b6d11b455e8951bb122100ec65c8dad3d7c2f52e3d710f99c`). The check image's 22 layers start with the runtime image's 19, and its `llama-server` is the same file (sha256 `b803d9fcb45e2072c952567e5953f379c293c6bf0f7e6023dfc77ef5ed1ac348` in both).
- `check-image.sh hetren-cli:dev`: all 29 checks passed (393 MB unpacked, `linux/amd64`, uid 10001, only the CLI's 8 package folders).
- `build-info.json`: llama.cpp `620d2225cc436ab0b001e3200e590e3b286ef9ab`, build 11669, commit `620d2225c`, version from git (a blobless clone of the whole history), `gcc (Debian 12.2.0-14+deb12u1) 12.2.0`, `cmake` 3.25.1, CPU features AVX AVX2 FMA F16C BMI2, OpenMP on, BLAS off. `llama-server --version`: `version: 0.7.0-dev (build 11669, commit 620d2225c)`, `built with GNU 12.2.0 for Linux x86_64`.
- `system_info`, from the check image's `llama-server -lv 4 -t 6` with a non-existent model file (Claude Code, 2026-11-09, after the run; nothing was loaded): `n_threads = 6 (n_threads_batch = 6) / 12 | CPU : SSE3 = 1 | SSSE3 = 1 | AVX = 1 | AVX2 = 1 | F16C = 1 | FMA = 1 | BMI2 = 1 | LLAMAFILE = 1 | OPENMP = 1 | REPACK = 1 |`. It has the Mac's features except `ACCELERATE`.
- **Not recorded by the run:** `linux-agreement.json` has `system_info: null` for both variants. The check read it from the server's log, which at the default verbosity does not contain it (the pilot's finding, which the validation run handled with a probe). The probe above is from the same image and binary. Fixed for later runs: `linux_agreement` now probes `-lv 4` during preflight, and a missing line stops the check.

### Agreement check (`linux_agreement`)

`linux check exit 0`; 2026-11-09 20:09:25–20:37:33 UTC. Full episodes on the 20 pilot cases (10 per tier), Q4_K_M then Q8_0, one `llama-server` per variant (`-c 4096 -np 1 -ngl 0 -t 6 -b 2048 -ub 512`, under `/usr/bin/time -v`), Amendment 2's greedy decoding, caching on. Preflight: `"preflight": "ok"`, the same commit, both validation call files present (Q4_K_M 745/630, Q8_0 731/708 calls).

| variant | same episode as the Mac | tier 1 | tier 2 | differing | calls | seconds per call (the Mac's validation run on these cases) | load | minutes | peak memory |
|---|---|---|---|---|---|---|---|---|---|
| Q4_K_M | **18 of 20** | 10 of 10 | 8 of 10 | `case-002104`, `case-004849` | 36 | 19.21 (11.26) | 10.1 s | 11.8 | 5.02 GB (5,015,076,864 bytes) |
| Q8_0 | **20 of 20** | 10 of 10 | 10 of 10 | none | 37 | 26.04 (17.06) | 8.0 s | 16.3 | 5.05 GB (5,049,307,136 bytes) |

Checked by Claude Code on 2026-11-09:
- every output file's sha256 equals the hash recorded in `linux-agreement.json`, and the four validation call files equal the recorded hashes;
- the report names the commit, the manifest (`4a2431a4…`), both GGUF hashes, llama.cpp `620d2225c` and 6 threads;
- the agreement was recomputed from `episodes-<V>.jsonl` and the validation `calls.jsonl` (parsed actions, call by call): the same counts and the same differing cases;
- every call was finite, ended on `<|im_end|>` (token 151645), stayed under the token limit and never generated `</s>` (128247); no reply was unparsable.

Findings:
- **Q8_0 is the same down to the token:** 37 of 37 calls generated the same token IDs as the Mac.
- **Q4_K_M's two differing episodes** each take one extra step: `inspect` on `routing_policy`, then `no_intervention`. On the Mac the run decided `no_intervention` at once, so the final decision is the same. These are the two cases the throughput pilot found sensitive to platform and caching, and they resolve as Kaggle's Linux build did in the pilot (2 calls each with caching on). The other 18 Q4_K_M episodes match action for action. Among their calls, one (`case-001393`, call 0) produced different token IDs that decode to the same text, the same `inspect` probe; the other 31 compared calls are token-identical.
- **Speed:** the Linux build was slower per call than the Mac's validation run on the same cases. Prompt evaluation ran at 24.2 tokens/s against 38.9 for Q4_K_M and 18.1 against 24.6 for Q8_0; generation ran at 4.93 against 6.63 and 3.37 against 4.65. Not like for like: the prompt caches differed (the validation server had served earlier cases), the image has no Accelerate, and it runs in Docker Desktop's VM. The causes were not separated.
- **Memory:** one server peaked at 5.02 GB (Q4_K_M) and 5.05 GB (Q8_0), against the Mac validation's 5.08 and 5.10 GB.

Outputs (in `artifacts/milestone-4/linux-check-1/`):
- `linux-agreement.json` `00d2320266e11105a1780b1ea51139634c22735801cebacdc82cdba1ed1661a4`;
- `episodes-Q4_K_M.jsonl` `0d809e0a5ab00ea345560cdc66529705778652cbbfbc0fdf0dd0e375810d64bc`, `episodes-Q8_0.jsonl` `aa8aa4b26ce5b03819bdd64e01f2e9a1ccdbd169f484dcf9d3e34532549879e6`;
- `server-Q4_K_M.log` `bbfdb7c1e8195b19145b3a6771869d4f29130a7d00a5e0dcab06565d9150950e`, `server-Q8_0.log` `ac8b8b6869152390cfd4ba3f91cfb7b6baa6a5761f87974214a5497601c9f373`;
- console log `linux-check-1.log` `ba6319c622031962be45e0b9ee83a1ce034f20480641c200f5ad9a30d7f9e357`.

### The CLI in the image (`cli_check --docker-image`)

`cli docker check exit 0`. Run about 20:41–21:10 UTC (from the files' times; the summary records no clock times). Q4_K_M in `hetren-cli:dev` (`sha256:28263d1b…`), one container per case, `--network none --read-only`, the GGUF and tokenizer mounted read-only, `--threads 6`. As in the Mac CLI check, each case's CLI action is compared with the validation run's first call.

| tier | comparison | same first action | differing | outcomes from the CLI | seconds per case (whole container) |
|---|---|---|---|---|---|
| 1 | like for like (only the prompt cache differs) | **10 of 10** | none | 5 decisions, 3 proposed recoveries, 2 probe requests | 70.9–96.7 |
| 2 | not like for like (the CLI always uses the tier 1 prompt) | 7 of 10 | `case-000329`, `case-002391`, `case-008313` | 4 decisions, 3 proposed recoveries, 3 probe requests | 75.0–106.3 |

Checked by Claude Code on 2026-11-09:
- all 20 reports record the commit `d2e01b49…`, Q4_K_M with the manifest's sha256, the validated build (`620d2225c`, build 11669, `built with GNU 12.2.0 for Linux x86_64`), 6 threads and prompt version 2;
- every generation was finite and ended on end-of-sequence, with no other stop token; prompts were 1,549–1,744 tokens; every exit status was 0, with no CLI failures and nothing on stderr.

Findings:
- **Tier 1** reproduces the validated first action on all 10 cases in the offline image, as the Mac CLI did.
- **Tier 2** gives the same first action as the Mac CLI on 9 of 10 cases. The exception is `case-002287`: the image's CLI rerouted ticket T-2124 to `Q-TRIAGE`, as the validation run did, where the Mac CLI chose `Q-MANUAL`. That case now matches the validation, which is why tier 2 is 7 of 10 rather than 6.
- **Time:** 29.3 minutes in all against 17.4 on the Mac, or 70.9–106.3 s per case against 46.6–57.7 s. Generation alone took 55.3–87.9 s per case. The causes were not separated (the Linux build is slower per token, as above, and every container starts cold).

Outputs (in `artifacts/milestone-4/cli-check-docker-1/Q4_K_M/`: `inputs/`, `reports/`):
- `summary.json` `d79286f92048f4260acbc7809c5460c93c38a858e50b863b0a5af16cf7b4a6ba` (it records `docker_image` and `image_id`);
- `cases.jsonl` `b333a1796805cce4bfd46a15a3b54408b323d9c5c9572cd6f2df5cd51272378c`;
- console log `cli-check-docker-1.log` `69d499584e16a4fa9eb11f085996875a1fc2169ce432cbf13baaa38c686b705c`;
- compared against the validation calls tier 1 `e2840398…`, tier 2 `c67a4dc1…`.

## Hugging Face release (step 7a)

Run by the operator on 2026-11-09 with the committed staging script (`scripts/hf_release.py`, `04c4a9d`) and model card (`965fa41`); `git status` showed only the untracked amendment draft.

**Repository:** [`Harsha1412/hetren-qwen3-4b-diagnosis`](https://huggingface.co/Harsha1412/hetren-qwen3-4b-diagnosis), licence `apache-2.0`. It was created private, then made public after verification.
- Commits: `63fce5b5a46cce7e94da775f17486c20dce699e6` ("initial commit", 23:26:15 UTC: only `.gitattributes`), then the release, **`3e875e4e8719acef839dc18e220a3ae498a1975b`** (23:47:03 UTC, "Hetren diagnosis model: checkpoint 0792, Q4_K_M and Q8_0 GGUFs, adapter, tokenizer, manifest").
- **Token:** fine-grained `hetren-7a-upload`, with repository permissions on this repository only: read contents, write contents and settings, and "view access requests for gated repos", which the form selects with write. No user or organisation permissions. Deleted after the upload, and `HF_TOKEN` unset.

| step | outcome |
|---|---|
| stage (`stage-model`) | "staged 16 files for Harsha1412/hetren-qwen3-4b-diagnosis in /Users/deva/hetren-hf-stage (6.93 GB); every file from the export and checkpoint matches the manifest". Then `SHA256SUMS` (`5bc7212e939ce7c8675cfe95b8b09359c81cd3a354d56eeffed499772bc69688`) was written: 17 files |
| upload (`hf upload`, `huggingface_hub` 0.36.2, `hf_xet` 1.7.0) | commit `3e875e4e…`. `hf upload` printed the tree URL, so the operator read the sha from `HfApi().list_repo_commits` |
| verify, private (`verify-remote`, with the token) | first attempt: `SSL: CERTIFICATE_VERIFY_FAILED` (python.org Python 3.13 on macOS has no CA certificates until its "Install Certificates" step); passed with `SSL_CERT_FILE` set to certifi's bundle: "17 files, each equal to the staged copy (4 by LFS sha256, the rest by git blob id)" |
| fetch Q4_K_M (`fetch-model --revision 3e875e4e…`) | all 9 tokenizer files and the GGUF: "sha256 matches the manifest"; "Q4_K_M ready … (sha256 e3f50ba9…)" |
| fetch Q8_0, first attempt | **failed**: the downloaded file had sha256 `d6c90bf5a5848a0e872267f73a19ee42c3faaba36b94fffe2a2f581470942f5c`, not the manifest's `496c74a7…`. "nothing was kept". Its size was not recorded |
| fetch Q8_0, retry (same command) | "sha256 matches the manifest"; "Q8_0 ready … (sha256 496c74a7…)" |
| verify, public (without a token) | first attempt: `HTTP Error 401: Unauthorized`, because the repository was still private; after making it public: "17 files, each equal to the staged copy (4 by LFS sha256, the rest by git blob id)" |

**The failed Q8_0 fetch** is read as a corrupted download. The remote file's LFS sha256 had already been verified equal to the manifest's (`verify-remote`), and the same command then fetched a matching file. The check worked as designed: the corrupted file was discarded, not cached. Its cause (a truncated or damaged transfer) was not established, because the size was not recorded.

**Checked by Claude Code on 2026-11-09, anonymously:**
- the Hub API reports the repository public, not gated, with `main` at `3e875e4e…`, and card metadata `license: apache-2.0`, `base_model: Qwen/Qwen3-4B-Instruct-2507`, `base_model_relation: finetune`, `library_name: peft`;
- its files are the 17 staged files plus `.gitattributes`;
- `verify-remote --revision 3e875e4e…` without a token: the same `ok` line;
- the staged `README.md` equals the committed card (`965fa41`) with the repository name filled in, and the staged `LICENSE` equals the repository's.

**Changes made after this release** (they do not change the released files):
- `fetch-model` now checks a download's size against the manifest's (GGUFs) or the server's `Content-Length`, and retries a failed or broken-off download once from the start. A 4xx error is not retried.
- HTTPS in `fetch-model` and `hf_release.py` falls back to certifi's bundle only when Python has no system certificates.
- The Helm chart's `model.revision` defaults to `3e875e4e…`.

## Hugging Face dataset release (step 7b)

Run by the operator on 2026-11-11 (UTC), with the committed staging script and dataset card (`3a6538e`).
`git status` showed only the untracked amendment draft.

**Repository:** [`Harsha1412/hetren-support-runs`](https://huggingface.co/datasets/Harsha1412/hetren-support-runs),
licence `cc-by-4.0`. Created private at 01:19:03 UTC, and made public after verification.
- **Commits:** `076c33f41e0627e1835cca0695335d03000e6e11` ("initial commit"), then the release,
  **`10942d316e0c1c9b3c3cb46915f971eed66ad7b4`** (01:21:49 UTC, "Hetren support-agent runs: datasets v2 and v3,
  splits v1 and v2, live test v1, manifests, protocol").
- **Token:** fine-grained `hetren-7b-upload`, with permissions on this repository only. Deleted after the upload;
  `HF_TOKEN` unset, and no token stored (`~/.cache/huggingface/token` absent).

| step | outcome |
|---|---|
| stage (`stage-dataset`) | "staged 2016 files for Harsha1412/hetren-support-runs in /Users/deva/hetren-hf-dataset-stage (114.2 MB); every data file matches its manifest, and the manifests match commit 3a6538e5e249deb7193fd0e77c1cf0c4f8758cb0". `SHA256SUMS`: 2,015 lines, sha256 `53d89b3ae82c4893ded0e10357bd1b370b44ab7fa1212997aa5488dc3ce99c64`. The staged `README.md` names commit `3a6538e5…` (line 109) |
| upload (`hf upload --repo-type dataset`, `huggingface_hub` 0.36.2) | it printed a "large folder" advisory, hashed 2,016 files and uploaded 108 MB of new data (4 large files): commit `10942d31…` |
| verify, private (`verify-remote --type dataset`, with the token) | the documented command **failed** with `ModuleNotFoundError: No module named 'packages'`. Run as `python scripts/hf_release.py`, the script lacked the repository root on `sys.path` for its HTTPS helper (`packages.hetren_cli.models.tls_context`, added in `eb7688c`, after 7a's verification). With `PYTHONPATH=.`: "2016 files, each equal to the staged copy (4 by LFS sha256, the rest by git blob id)" |
| visibility | switched to public |
| verify, public (no token, `PYTHONPATH=.`) | the same `ok` line |
| dataset viewer | right after going public: "The dataset viewer should be available soon". A few minutes later, all three subsets (`tier1`, `tier2`, `live`) were listed, with rows still processing. **Later: working.** All three subsets show rows (`live` · 300 rows), "Number of rows: 18,737" (10,039 + 8,398 + 300, the three files' record counts), auto-converted to Parquet, with Data Studio |

**Checked by Claude Code on 2026-11-11, anonymously:**
- **The repository:** the Hub API reports `Harsha1412/hetren-support-runs` public, not gated, with `main` at `10942d31…`.
  - Its card metadata: `license: cc-by-4.0`, configs `tier1`, `tier2` and `live`, and the card's tags.
  - Its files: 2,017, the 2,016 staged files plus `.gitattributes`.
- **`verify-remote` without a token, run exactly as documented** (after the fix below): "ok
  Harsha1412/hetren-support-runs@10942d316e0c1c9b3c3cb46915f971eed66ad7b4: 2016 files, each equal to the staged
  copy (4 by LFS sha256, the rest by git blob id)". It ran against a folder staged independently from `3a6538e`,
  whose `SHA256SUMS` has the same sha256, `53d89b3a…`: staging is reproducible.
- **The dataset viewer:** its server lists the three configurations with 10,039 (`tier1`), 8,398 (`tier2`) and
  300 (`live`) rows, the datasets' record counts. Its row previews were still pending at the time of this check
  ("the response is not ready yet"); the operator later saw them working (the table above).

**Changes made after this release** (they do not change the released files):
- **`hf_release.py`** puts the repository root on `sys.path`, so it runs as documented without `PYTHONPATH`. A test
  runs `verify-remote` exactly that way, from the repository root without `PYTHONPATH` or a token, against a local
  stand-in for the Hub API that serves two pages.
- **The model card's training section** links the dataset repository. The model repository gets the new README
  and its matching `SHA256SUMS` in one commit (`refresh-card`). The released files and the pinned revision
  `3e875e4e…` are unchanged.

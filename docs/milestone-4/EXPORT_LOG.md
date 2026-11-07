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

Pilot choices (caching setting and platform, under Amendment 2's rules) are recorded here before the validation run.

## Validation runs

| # | date (UTC) | variant (GGUF sha256) | platform, CPU, threads | settings | outcome | output hashes |
|---|---|---|---|---|---|---|

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

## Token parity

| # | date (UTC) | variant (GGUF sha256) | server build | texts checked | outcome | report sha256 | notes |
|---|---|---|---|---|---|---|---|

## Throughput pilot

| # | date (UTC) | platform, CPU, threads | variant | caching | seconds per call | repeats identical | outcome | output hashes |
|---|---|---|---|---|---|---|---|---|

Pilot choices (caching setting and platform, under Amendment 2's rules) are recorded here before the validation run.

## Validation runs

| # | date (UTC) | variant (GGUF sha256) | platform, CPU, threads | settings | outcome | output hashes |
|---|---|---|---|---|---|---|

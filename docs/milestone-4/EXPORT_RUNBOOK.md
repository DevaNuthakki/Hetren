# Export and pilot runbook (Milestone 4, steps 1 and 2)

Operator steps for the GGUF export and the throughput pilot under `docs/milestone-2/EVAL_PROTOCOL.md`, Amendment 2. Every run, failed ones included, is logged in `docs/milestone-4/EXPORT_LOG.md` before its results are used. Commands are for zsh, from the repository root.

## 1. Build the bundle (local)

The bundle is exactly a committed revision plus the verified datasets; the builder refuses uncommitted changes.

```zsh
git status --short
git rev-parse HEAD
python scripts/build_kaggle_bundle.py --out artifacts/milestone-4/kaggle/hetren-m4-bundle.tar.gz
shasum -a 256 artifacts/milestone-4/kaggle/hetren-m4-bundle.tar.gz
```

Upload `hetren-m4-bundle.tar.gz` as a new **private** Kaggle Dataset. Keep the commit and the archive's sha256 for the log.

## 2. Run the export notebook (Kaggle)

1. Create a notebook from `notebooks/milestone-4/gguf_export.ipynb`.
2. Settings: accelerator **GPU T4 ×2**, internet **on**, environment **pinned** (as in the Milestone 3 runs).
3. Attach three inputs:
   - the bundle dataset;
   - session 2's training output (`train-session-2-retry`, which holds `checkpoint-0792`);
   - the checkpoint-selection output (`selection-run-1`, which holds `choice.json`).
4. In the first code cell, set `BUNDLE_COMMIT` to the full commit from step 1. The notebook stops if it is empty or differs.
5. Run all, then save a version named `export-<N>`, numbered after the last entry in `EXPORT_LOG.md` (export 1 failed, so the next is `export-2`).

**Expected time:** about 1–1.5 hours.
- llama.cpp checkout and the conversion venv (first, before the merge): about 5 minutes. The venv itself is created in seconds.
- Base model download and merge on one T4: 5–15 minutes (2.9 minutes for the merge in export 1).
- llama.cpp CPU build: about 6 minutes (5.8 in export 1).
- f16 conversion and the two quantisations: 15–25 minutes.
- Token parity: 5–10 minutes per variant (6,569 texts each).

**The notebook stops on its own** if:
- the bundle commit, `state.json`, an adapter file or `choice.json` does not match;
- the llama.cpp checkout is not `620d2225…` or has local changes;
- the conversion venv cannot be created or is not isolated (checked in the first minutes, before the merge);
- there is less than 40 GB of scratch space;
- `llama-server` does not start;
- token parity fails for a variant (after writing its report).

**Outputs** (`/kaggle/working/gguf-export/`, about 7 GB):
- `hetren-qwen3-4b-ckpt0792-q8_0.gguf` (about 4.3 GB) and `hetren-qwen3-4b-ckpt0792-q4_k_m.gguf` (about 2.5 GB);
- `export.manifest.json`, `merge.json`, `tokenizer/`;
- `parity-Q8_0.json`, `parity-Q4_K_M.json`;
- `environment.json`, `outputs.sha256`.

## 3. Bring back the small files (local)

Download everything except the two GGUF files into `artifacts/milestone-4/export-<N>/gguf-export/` (gitignored; `export-2` for the second attempt, as in the commands below), then check them against the notebook's listing:

```zsh
mkdir -p artifacts/milestone-4/export-2
cd artifacts/milestone-4/export-2/gguf-export
grep -v '\.gguf$' outputs.sha256 | shasum -a 256 -c
cd -
```

Then hand over to Claude Code. It will:
- verify the manifest against `merge.json`, the pinned values and the parity reports;
- write the export and token-parity entries in `EXPORT_LOG.md`;
- copy `export.manifest.json` to `docs/milestone-4/export.manifest.json` for the commit that has to land before the first pilot.

## 4. Throughput pilot (step 2)

Amendment 2's pilot, once per platform, numbered `pilot-<N>` after the last pilot entry in `EXPORT_LOG.md` (the first is `pilot-1`). Both platforms run the same module, `packages.support_evaluator.gguf_pilot`, from the same commit, on export 2's files (checked against the committed `docs/milestone-4/export.manifest.json` before anything runs). Per variant: the 20 fp16 smoke-test cases, each episode twice with prompt caching on and twice with it off, on a fresh `llama-server` per caching setting (`-c 4096 -np 1 -ngl 0 -b 2048 -ub 512`, `-t 6` on the Mac and `-t 4` on Kaggle) under `/usr/bin/time` for peak memory. Episodes are not scored. The two platforms can run at the same time.

**Expected time:** about 2–5 hours per platform. The caching-off blocks are the slow ones, because every call evaluates the whole prompt (about 2,000–2,400 tokens).

### Mac

1. llama.cpp at the pinned commit, built CPU-only with the export's flags (once):

   ```zsh
   mkdir -p ~/hetren-tools
   git clone https://github.com/ggml-org/llama.cpp ~/hetren-tools/llama.cpp
   cd ~/hetren-tools/llama.cpp
   git checkout --detach 620d2225cc436ab0b001e3200e590e3b286ef9ab
   git status --short
   cmake -B build -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA=OFF -DGGML_METAL=OFF -DGGML_BLAS=OFF -DGGML_NATIVE=OFF
   cmake --build build --config Release -j 6 --target llama-server
   ./build/bin/llama-server --version
   cd -
   ```

   `--version` should name `620d2225`.
2. The pilot venv (once; the repository's `.venv` is not changed):

   ```zsh
   /usr/local/bin/python3.13 -m venv ~/.hetren-pilot
   ~/.hetren-pilot/bin/pip install -r requirements-gguf-pilot.txt
   ~/.hetren-pilot/bin/pip check
   ```
3. The run. Plug in mains power (the pilot stops on battery), close heavy applications and start from the pilot's commit with no tracked changes (untracked files are fine). The pilot holds a `caffeinate -dims` assertion until it ends.

   ```zsh
   git status --short
   git rev-parse HEAD
   mkdir -p artifacts/milestone-4/pilot-1
   ~/.hetren-pilot/bin/python -m packages.support_evaluator.gguf_pilot run --platform mac --gguf-dir artifacts/milestone-4/export-2/gguf-export --tokenizer artifacts/milestone-4/export-2/gguf-export/tokenizer --llama-cpp ~/hetren-tools/llama.cpp --out artifacts/milestone-4/pilot-1/mac 2>&1 | tee artifacts/milestone-4/pilot-1/mac.log
   echo "pilot exit ${pipestatus[1]}"
   ```

### Kaggle CPU

1. Build the bundle from the pilot's commit (as in section 1) as `hetren-m4-bundle-3.tar.gz`, and upload it as a new private Kaggle Dataset.
2. Create a notebook from `notebooks/milestone-4/gguf_pilot.ipynb`. Settings: accelerator **None**, internet **on**, environment **pinned**.
3. Attach two inputs: the bundle 3 dataset, and the output of notebook `hetren-gguf-export-2` (version `export-2`). The notebook skips the code copy inside that output and finds the export by its manifest's sha256.
4. In the first code cell, set `BUNDLE_COMMIT` to the full commit. Run all, and save the version as `pilot-1`.
5. Download the output and check it:

   ```zsh
   mkdir -p artifacts/milestone-4/pilot-1/kaggle
   ~/.kaggle-cli/bin/kaggle kernels output nuthakkidevaharsha/<pilot notebook slug> -p artifacts/milestone-4/pilot-1/kaggle
   cd artifacts/milestone-4/pilot-1/kaggle/gguf-pilot
   shasum -a 256 -c outputs.sha256
   cd -
   ```

### Afterwards

Hand both outputs to Claude Code before reading them. It will:
- check each report against the committed manifest and the declared settings;
- write the throughput pilot entries in `EXPORT_LOG.md`, including each platform's `system_info` CPU features;
- run `python -m packages.support_evaluator.gguf_pilot decide --mac <pilot-mac.json> --kaggle <pilot-kaggle.json> --out <decision.json>`, which applies the caching rule and then the platform rule;
- log the resulting choices before the validation run.

## If something fails

Do not re-run silently. Note what happened (cell, message, time) and log the run as failed or stopped in `EXPORT_LOG.md` first. A repeat completes the same declared export; it never changes a setting.

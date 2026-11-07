# Export runbook (Milestone 4, step 1)

Operator steps for the GGUF export under `docs/milestone-2/EVAL_PROTOCOL.md`, Amendment 2. Every run, failed ones included, is logged in `docs/milestone-4/EXPORT_LOG.md` before its results are used. Commands are for zsh, from the repository root.

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

## 4. GGUF files for the Mac pilot (later)

The Kaggle CPU pilot attaches the export notebook's output directly. Download the two GGUF files and `tokenizer/` to the Mac only when its pilot starts, into `artifacts/milestone-4/export-2/gguf-export/`, and check them:

```zsh
cd artifacts/milestone-4/export-2/gguf-export
shasum -a 256 -c outputs.sha256
cd -
```

## If something fails

Do not re-run silently. Note what happened (cell, message, time) and log the run as failed or stopped in `EXPORT_LOG.md` first. A repeat completes the same declared export; it never changes a setting.

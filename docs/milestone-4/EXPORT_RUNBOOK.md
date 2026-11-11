# Export, pilot and validation runbook (Milestone 4, steps 1–3)

Operator steps for the GGUF export, the throughput pilot and the validation run under `docs/milestone-2/EVAL_PROTOCOL.md`, Amendment 2. Every run, failed ones included, is logged in `docs/milestone-4/EXPORT_LOG.md` before its results are used. Commands are for zsh, from the repository root.

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

## 5. Validation run on the Mac (step 3)

Amendment 2's validation check, with the pilot's choice (`EXPORT_LOG.md`, "Pilot choices", 2026-11-08): the Mac, `-t 6`, prompt caching on, the pilot's llama.cpp build and `~/.hetren-pilot` venv (section 4; nothing new to build). Each variant is one run of the full validation split, tier 1 (550 cases) then tier 2 (250), numbered `validation-<N>` after the last validation entry in `EXPORT_LOG.md` (the first is `validation-1`). Validation splits only.

**Expected time:** Q4_K_M about 5.1 hours, Q8_0 about 7.0 hours (the pilot's projections with caching on; its other estimate is 4.4 and 6.3 hours). Run each variant in its own session (for example, one per night), Q4_K_M first.

**What the run shows:** each case's ID and number of calls only, never whether it was correct; do not open the `rows-*`, `summary-*` or `calls.jsonl` files before the run is logged. It checks the Mac (mains power, the pilot's CPU), the commit (no tracked changes except `EXPORT_LOG.md`), both datasets, the variant's GGUF and the tokenizer files before anything runs, and keeps the Mac awake until it ends.

1. Start from the commit with the validation runner; plug in mains power and close heavy applications:

   ```zsh
   cd ~/Documents/personal-projects/hetren
   git status --short
   git rev-parse HEAD
   mkdir -p artifacts/milestone-4/validation-1
   ```

   `git status --short` should list only untracked files (`??`).
2. Q4_K_M (first session):

   ```zsh
   ~/.hetren-pilot/bin/python -m packages.support_evaluator.gguf_validation run --variant Q4_K_M --gguf-dir artifacts/milestone-4/export-2/gguf-export --tokenizer artifacts/milestone-4/export-2/gguf-export/tokenizer --llama-cpp ~/hetren-tools/llama.cpp --out artifacts/milestone-4/validation-1 2>&1 | tee -a artifacts/milestone-4/validation-1/Q4_K_M.log
   echo "validation exit ${pipestatus[1]}"
   ```

   The first lines are the build's `system_info` line (it should match the pilot's: `AVX2 = 1 … ACCELERATE = 1 | OPENMP = 1`) and `Q4_K_M tier 1: session 1, 0 of 550 cases done`. Each tier ends with `complete, <cases> cases, <calls> calls, <restarts> restarts, <n> calls ended on another token`.
3. Q8_0 (second session): the same command with `--variant Q8_0` and `Q8_0.log`.

**If it stops** (power, sleep, a crash or a `STOP` line): note the time and the last lines and hand them to Claude Code, which logs the stop in `EXPORT_LOG.md` first. Then run the same command again: scored cases are kept, the tier resumes at its first unscored case (recorded, with an empty cache), and a finished tier is skipped. The resume refuses other settings and any commit that changed the run's code or data; an uncommitted or committed log entry is fine.

**Afterwards** hand both variants to Claude Code before reading anything. It will check each tier's completion record (`validation-<variant>-tier<N>.json`), write the validation entries in `EXPORT_LOG.md` (dates, platform, threads, llama.cpp commit, GGUF sha256, settings, sessions and restarts, unexpected stops, output hashes), and only then run:

```zsh
~/.hetren-pilot/bin/python -m packages.support_evaluator.gguf_check check --variant Q4_K_M --runs artifacts/milestone-4/validation-1 --out artifacts/milestone-4/validation-1/check-Q4_K_M.json
~/.hetren-pilot/bin/python -m packages.support_evaluator.gguf_check check --variant Q8_0 --runs artifacts/milestone-4/validation-1 --out artifacts/milestone-4/validation-1/check-Q8_0.json
~/.hetren-pilot/bin/python -m packages.support_evaluator.gguf_check ship --checks artifacts/milestone-4/validation-1/check-Q4_K_M.json artifacts/milestone-4/validation-1/check-Q8_0.json --out artifacts/milestone-4/validation-1/ship.json
```

## 6. CLI check on the real model (step 4, descriptive)

On the Mac, from the repository at the commit that added the CLI (`git status --short` shows only the untracked amendment draft), on mains power. It runs the CLI as a user would, once per pilot case (20 processes, each starting and stopping its own `llama-server` with `-t 6`), and compares each CLI action with the Q4_K_M validation run's first call for that case. Tier 1 compares like for like; tier 2 does not (the validation run used the tier 2 prompt, the CLI always uses the tier 1 prompt). Nothing gates on it. About 10–15 minutes.

```zsh
cd ~/Documents/personal-projects/hetren
caffeinate -i ~/.hetren-pilot/bin/python -m packages.support_evaluator.cli_check run --variant Q4_K_M --gguf-dir artifacts/milestone-4/export-2/gguf-export --tokenizer artifacts/milestone-4/export-2/gguf-export/tokenizer --llama-server ~/hetren-tools/llama.cpp/build/bin/llama-server --runs artifacts/milestone-4/validation-1 --out artifacts/milestone-4/cli-check-1 2>&1 | tee artifacts/milestone-4/cli-check-1.log
echo "cli check exit ${pipestatus[1]}"
```

Each case prints `tier <N> <case>: exit <status>, same|different first action, <seconds> s`; the end prints both tiers' counts. Hand the exit status and `artifacts/milestone-4/cli-check-1/Q4_K_M/summary.json` to Claude Code, which logs the check in `EXPORT_LOG.md`.

## 7. Linux checks in the Docker image (step 5, descriptive)

On the Mac (Intel, so Docker Desktop runs `linux/amd64` natively), with Docker Desktop given 12 CPUs; the checks record the memory the VM reports. From the repository at the commit that added the image (`git status --short` shows only the untracked amendment draft), on mains power. One container and one `llama-server` at a time: do not run the two parts together or run other containers meanwhile. Nothing here gates anything.

1. Build both images (about 6 minutes the first time; the llama.cpp stage is cached afterwards):

   ```zsh
   cd ~/Documents/personal-projects/hetren
   docker build -f docker/hetren-cli/Dockerfile --target runtime --build-arg HETREN_COMMIT=$(git rev-parse HEAD) -t hetren-cli:dev .
   docker build -f docker/hetren-cli/Dockerfile --target check --build-arg HETREN_COMMIT=$(git rev-parse HEAD) -t hetren-cli:check .
   docker/hetren-cli/check-image.sh hetren-cli:dev
   ```

   The last command ends with `all image checks passed`.

2. Preflight of the agreement check (checks the image, memory, CPUs, commit, GGUFs, tokenizer and server build; starts nothing):

   ```zsh
   mkdir -p artifacts/milestone-4/linux-check-1
   docker run --rm -v "$PWD":/repo:ro -v "$PWD/artifacts/milestone-4/linux-check-1":/out hetren-cli:check python -m packages.support_evaluator.linux_agreement run --gguf-dir /repo/artifacts/milestone-4/export-2/gguf-export --tokenizer /repo/artifacts/milestone-4/export-2/gguf-export/tokenizer --runs /repo/artifacts/milestone-4/validation-1 --out /out --preflight
   ```

   It prints `"preflight": "ok"`, the commit, the memory, `build 11669, commit 620d2225c` and the build's `system_info` line (`AVX2 = 1 … OPENMP = 1`, no `ACCELERATE`); it stops if `llama-server -lv 4` prints no `system_info`.

3. The agreement check (full episodes on the 20 pilot cases, Q4_K_M then Q8_0; about 30–45 minutes):

   ```zsh
   caffeinate -i docker run --rm -v "$PWD":/repo:ro -v "$PWD/artifacts/milestone-4/linux-check-1":/out hetren-cli:check python -m packages.support_evaluator.linux_agreement run --gguf-dir /repo/artifacts/milestone-4/export-2/gguf-export --tokenizer /repo/artifacts/milestone-4/export-2/gguf-export/tokenizer --runs /repo/artifacts/milestone-4/validation-1 --out /out 2>&1 | tee artifacts/milestone-4/linux-check-1.log
   echo "linux check exit ${pipestatus[1]}"
   ```

   The first line names the VM's memory; each case prints `tier <N> <case>: <calls> calls, <seconds> s`; each variant ends with `<n> of 20 episodes as on the Mac … peak memory <GB>`.

4. The CLI offline in the published image (20 containers, `--network none --read-only`, one at a time; about 20 minutes):

   ```zsh
   caffeinate -i ~/.hetren-pilot/bin/python -m packages.support_evaluator.cli_check run --variant Q4_K_M --gguf-dir artifacts/milestone-4/export-2/gguf-export --tokenizer artifacts/milestone-4/export-2/gguf-export/tokenizer --docker-image hetren-cli:dev --runs artifacts/milestone-4/validation-1 --out artifacts/milestone-4/cli-check-docker-1 2>&1 | tee artifacts/milestone-4/cli-check-docker-1.log
   echo "cli docker check exit ${pipestatus[1]}"
   ```

Hand both exit statuses, `artifacts/milestone-4/linux-check-1/linux-agreement.json` and `artifacts/milestone-4/cli-check-docker-1/Q4_K_M/summary.json` to Claude Code, which logs them in `EXPORT_LOG.md`.

## If something fails

Do not re-run silently. Note what happened (cell, message, time) and log the run as failed or stopped in `EXPORT_LOG.md` first. A repeat completes the same declared export; it never changes a setting.

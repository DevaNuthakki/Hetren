# Milestone 4 plan: CPU export, packaging, deployment and release

**Status:** design only, written 2026-11-07 after the Milestone 3 merge (`709fce0`, tag `v0.3.0-milestone-3`). Nothing here has been built or run. Branch: `milestone-4/packaging`.

## Scope and fixed points

Milestone 4 makes the chosen model, `checkpoint-0792`, usable by others: a CPU export, an offline CLI and Docker image, a Kubernetes deployment with a load test, and a public model and dataset release.

- **The protocol stays frozen.** The only new measurement is a validation-only quality check of the CPU export, declared in Amendment 2 before any GGUF evaluation.
- **No test split is run again**, by any system. The GGUF variants never run on a test split. The published test results stay the fp16 results of test runs #5 and #6; the export's equivalence is shown on validation.
- **Nothing changes a Milestone 1–3 result**, dataset, split, label, metric or document other than by a dated amendment or log entry.
- **Operator-only steps:** every model run (pilot, validation), every cloud run and every upload to Hugging Face is run by the operator. Each paid step is preceded by an exact cost estimate and a hard cap.
- **Boundaries:** new packages (`packages/hetren_cli`, `packages/hetren_serving`) must not import `packages/support_evaluator`; the import-boundary tests are extended to them before their first push.

## Decisions (operator, 2026-11-07)

| # | decision |
|---|---|
| 1 | Cloud: GKE (Google Cloud) with CPU nodes, total spend cap **$25**; `kind` in CI. Before any cloud run: an exact cost estimate from current GCP pricing, a budget alert, and teardown verification. |
| 2 | GGUF variants **Q8_0** and **Q4_K_M**. A variant is accepted if, against the fp16 validation rows, the paired-bootstrap 95% lower bound of the decision-accuracy difference (GGUF − fp16) is at least −2 pp in each tier, and wrong interventions are not significantly worse in either tier. The episode-agreement rate is reported. The throughput pilot runs on the operator's 2018 Intel Mac (6-core i7, 32 GB) and in a Kaggle CPU notebook, and recommends where to run the full validation. |
| 3 | GGUF is validation-only; no test-split runs. |
| 4 | All labels, test splits included, are published in the Hugging Face dataset. The generator, labeller, seeds and split lists are in the repository, so everything is reproducible; any future held-out set will use fresh seeds. The dataset card says so. |

## Steps

Estimates: **build** is implementation and review time in sessions with Claude Code; **operator** is the operator's hands-on and wall-clock compute time; **cost** is money spent. All are estimates; measured values replace them in the logs.

### Step 1: Amendment 2 and export tooling (no model run)

- Amendment 2 in `docs/milestone-2/EVAL_PROTOCOL.md` (pinned hash updated in the same commit): GGUF variants, conversion, runtime and decoding settings, the pilot rule, the platform rule, the acceptance rule and the export log. Drafted separately for review.
- `scripts/export_gguf.py`: merge the adapter into the fp16 base exactly as evaluation does (`peft merge_and_unload`), verify the adapter and `state.json` hashes against `choice.json`, convert with `convert_hf_to_gguf.py` at a pinned llama.cpp commit (f16 GGUF), quantise to Q8_0 and Q4_K_M with `llama-quantize` (no importance matrix), and write `docs/milestone-4/export.manifest.json` (every input and output sha256, llama.cpp commit, library versions).
- `packages/hetren_serving/llama_policy.py`: a policy for `episodes.py` that renders each step with the Hugging Face chat template and tokenizer at the pinned revision (exactly as the fp16 runs), sends the **token IDs** to `llama-server`'s `/completion` endpoint, and parses the reply with `parse_action`. Sending token IDs makes prompt tokenisation identical to the fp16 runs by construction.
- Parity checks (CPU tests with a tiny GGUF in CI, real model on the operator's machine): the GGUF vocabulary maps every token of every validation input and target to the same ID and bytes as the HF tokenizer; the end-of-turn token stops generation.

| build | operator | cost |
|---|---|---|
| 2–3 sessions | 1 h: merge and convert on the Mac (32 GB holds the 8 GB fp16 merge), about 30 min of compute | $0 |

### Step 2: throughput pilot on two platforms (operator)

- `notebooks/milestone-4/gguf_pilot.ipynb` and, for the Mac, the same module run locally (`python -m packages.support_evaluator.gguf_pilot`; it is in the evaluator package, not `scripts/`, because it reads the validation cases and only the evaluator may import them). Per platform and per variant: 20 seeded validation cases (the fp16 smoke-test cases, 10 per tier), each episode run **twice**, with prompt caching on, then the same 20 with caching off.
- Measures: prompt-processing and generation tokens per second, seconds per call, peak memory, and whether repeated episodes are byte-identical (with and without caching). The pilot's accuracy is not reported or used.
- Platforms: the Mac (macOS, x86_64, AVX2, 6 cores / 12 threads, llama.cpp built CPU-only with Metal off, `-t 6`) and a Kaggle CPU notebook (Linux x86_64, 4 vCPUs, about 30 GB RAM, 12-hour session limit, `-t 4`).
- Planning estimate, to be replaced by the pilot: the system prompt (about 1,450 tokens in tier 1, 1,540 in tier 2) is the same for every call of a tier, so with caching only the evidence (about 300–900 tokens) and the reply (at most 43 tokens on validation so far) are new. On a 6-core AVX2 CPU that is roughly 8–15 s per call for Q4_K_M and 12–20 s for Q8_0. Full validation took 1,446 calls in fp16 (743 tier 1, 703 tier 2), so roughly **3–6 h per variant on the Mac** and somewhat more on Kaggle's 4 vCPUs.
- **Recommendation rule** (declared in Amendment 2): run the full validation where both variants finish within one uninterrupted session each with deterministic repeats; if both platforms qualify, prefer **Kaggle** (Linux x86_64 matches the Docker image, the environment is pinned and recorded like Milestones 2 and 3, and it does not depend on a laptop's thermals or sleep); prefer the Mac only if Kaggle cannot finish a variant inside its 12-hour limit.

| build | operator | cost |
|---|---|---|
| 1 session | about 2 h per platform (20 cases × 2 repeats × 2 cache settings × 2 variants) | $0 |

### Step 3: GGUF validation run (operator)

- Each variant runs once on the full validation split (550 tier 1, 250 tier 2) on the one platform chosen in step 2, with Amendment 2's settings. Logged in `docs/milestone-4/EXPORT_LOG.md` (date, platform, CPU, threads, llama.cpp commit, GGUF sha256, output hashes) before results are read, like the test-run log.
- `python -m packages.support_evaluator.gguf_check` computes, per tier and variant: the paired bootstrap against the fp16 rows of `validation-run-1` (10,000 resamples, seed 2026) for decision accuracy and wrong interventions, the episode-agreement rate, and the acceptance verdict. The shipped variant is the smallest accepted one.
- If neither variant is accepted, the result is reported as it is, Q8_0 is shipped with the measured gap stated in the model card and the CLI's output, and no other quantisation is tried without a further amendment.

| build | operator | cost |
|---|---|---|
| 1 session | 6–12 h compute for both variants (two Kaggle sessions in parallel, or two Mac nights); 30 min hands-on | $0 |

### Step 4: CLI for offline diagnosis of agent runs recorded with Hetren's OpenAI Agents SDK integration

Design revised by the operator on 2026-11-08, before the build (the three changes are marked *revised*).

- `packages/hetren_cli`, run as `python -m packages.hetren_cli` (the Docker image adds a `hetren` command). *Revised:* no pip package for now; the repository's top-level package is `packages`, which should not be installed into site-packages.
  - `diagnose --record <file> | --compact <file>`: evidence only. Builds the run's `compact-evidence-v1` input and runs one policy step exactly as the GGUF validation ran it (the tier 1 prompt, version 2; the Hugging Face tokenizer's token IDs; Amendment 2's decoding; `llama-server` started with Amendment 2's settings, or `--server-url`). The output is a decision (`no_intervention`, `insufficient_evidence`, `abstain`), a **proposed** recovery, or "needs probe: <probe>" when the model asks for a probe that cannot run without an environment. Nothing is ever applied.
  - `fetch-model`: downloads a validated GGUF (Q4_K_M by default, `--variant Q8_0`) and the merged model's tokenizer files from the Hugging Face model repository and checks every sha256 against the export manifest; `--model <path>` uses a local file, checked the same way.
  - `--format json` for machine-readable output with provenance (variant and GGUF sha256, prompt version, llama.cpp build and whether it is the validated one, threads, CLI version and commit).
  - Exit status: 0 a diagnosis; 2 input rejected; 3 model or server failure; 4 the reply is not a valid action.
- *Revised:* **the full episode is not in the CLI.** The boundary rules keep `packages.hetren_*` away from the subject environment, and the episode loop is the evaluator's. The full-episode demo is `python -m packages.support_evaluator.sandbox_demo` (evaluator side, run from the repository, not shipped in the CLI or the image): `run_episode` itself, probes and the proposed recovery in sandboxed forks; validation cases or worlds generated with fresh seeds only, and test-split cases refused.
- Input: an `AgentRunRecord` evidence payload (`RunRecord.evidence_payload()` as JSON) from a run recorded with `packages/integrations/openai_agents` (`run_agent` with a `ToolGateway`), or `compact-evidence-v1` itself (also one line of the published `hetren_visible.jsonl`). `jsonschema` schemas reject runs outside the support workflow (tools other than `read_ticket`, `lookup_account`, `route_ticket`) with a clear message instead of guessing. *Revised:* **no converter from the SDK's exported trace/span JSON.** The model reads facts only the gateway records (whether each call was authorized or denied and why, its observation, whether it changed state, and the hook/span discrepancy kinds); spans never carry authorization or state changes, and with `trace_include_sensitive_data=False` not even arguments or observations. An SDK trace export is rejected with a message explaining how to record a run.
- Scope statement in `--help`, the README and every report: the model was trained only on this synthetic support workflow; it is not a general agent-trace diagnoser. The CLI handles single-recovery (tier 1) support runs only: two-step recovery (tier 2) is not supported in the CLI, although the model was validated on it (operator, 2026-11-08). Every report also states the variant's validation result in one line (`EXPORT_LOG.md`, "Acceptance and shipping").
- Tests (CI, no model): inputs from the replayed Milestone 1 captures and from scripted runs of every case kind and behaviour equal `compact_evidence` of the record; every first-step input of datasets v2 and v3 is accepted (input checks only, when the data is present); SDK trace exports, foreign tools, tier 2 and malformed inputs are rejected; reports from a fake `llama-server` executable and a fake tokenizer (decision, proposed recovery, probe, invalid reply, unexpected stop token); fetch and hash checks against a local HTTP server; the server arguments, manifest copy, reported validation numbers and requirements match their sources; boundary tests with `packages.hetren_cli` restricted. **Operator check (descriptive, real model):** the CLI with Q4_K_M on the 20 pilot cases' first-step inputs, agreement with the validation run's first actions reported (no test-split input is used).

| build | operator | cost |
|---|---|---|
| 3–4 sessions | 30 min to try it on the real model | $0 |

### Step 5: Docker image

Design revised by the operator on 2026-11-08, before the build (the changes are marked *revised*).

- `docker/hetren-cli/Dockerfile`, multi-stage, `linux/amd64` only, base images pinned by their amd64 manifest digests (`debian:bookworm-slim`, `python:3.13-slim-bookworm`):
  - `llama-build`: llama.cpp at the pinned commit (checked), only `llama-server`, CPU only, static, OpenMP, no BLAS, no HTTPS client. *Revised:* a **fixed AVX2 build** (`GGML_NATIVE=OFF`; AVX, AVX2, FMA, F16C, BMI2 on; AVX-512 off), so every AVX2 host runs the same kernels; the whole commit history is cloned (blobless), so llama.cpp derives its version string from git (`build 11669, commit 620d2225c`, as the Mac's validated build).
  - `python-deps`: `requirements-cli.txt` with `--no-deps` (every package pinned). *Revised:* **Python 3.13** (the validated environment's), not 3.12.
  - `runtime` (published): the venv, `llama-server`, and only the repository folders the CLI's imports reach (a test keeps the list equal to the import graph; no evaluator, verifier, environment, dataset or label); non-root user 10001; `hetren` entry point; `HETREN_CACHE=/models`; `HETREN_REQUIRED_CPU_FLAGS="avx2 fma f16c"`, which the CLI checks against `/proc/cpuinfo` before starting the server.
  - `check` (never published): `runtime` plus the pilot environment, for the Linux agreement check with the repository mounted read-only.
- Weights are **not** in the image: they are mounted (`-v ~/.cache/hetren:/models`) or fetched once with `fetch-model`. Image size target: under 1 GB without weights (Q4_K_M is about 2.5 GB, Q8_0 about 4.3 GB).
- CI (`docker` job, every push): build the image with a build cache, then `docker/hetren-cli/check-image.sh`: size, platform, non-root user, `version` and `--help` offline, `llama-server`'s commit and `system_info` features (AVX2, FMA, F16C, BMI2, OpenMP; no AVX-512, BLAS or Accelerate), only the CLI's packages present, and offline (`--network none --read-only`) rejections of an SDK trace (exit 2), a missing model (exit 3) and a missing CPU flag (exit 3). *Revised:* **no model in CI**: the CLI accepts only the validated GGUF and tokenizer, so a stub model cannot pass by design; inference in the image is checked by the operator (below). The check job has read-only permissions. Publishing is a separate `publish` job, **on `v*` tag pushes only** (`packages: write`): it rebuilds from the check job's cache, runs the same checks on that build, and pushes exactly that image to `ghcr.io/devanuthakki/hetren-cli`.
- **Linux agreement check (operator, descriptive, not part of acceptance; added 2026-11-08, design revised 2026-11-08):** the validation ran on the Mac (Accelerate on); the image runs Linux. *Revised:* in the `check` image, `packages.support_evaluator.linux_agreement` runs the 20 pilot cases as full episodes for both variants, one `llama-server` at a time, with the validation run's settings (`-t 6`, caching on), and reports episode agreement with the Mac validation episodes for those cases, the VM's memory and each server's peak memory; then `cli_check --docker-image` runs the CLI on the same cases in the published image offline (`--network none --read-only`), as the real-model check of the offline path (`docs/milestone-4/EXPORT_LOG.md`, "Limitation: the validation platform is not the shipped platform"; runbook section 7). *Done 2026-11-09* (`EXPORT_LOG.md`, "Linux checks in the Docker image"): Q8_0 20 of 20 episodes as on the Mac, Q4_K_M 18 of 20 (the two pilot-sensitive tier 2 cases each take an extra probe and reach the same decision); the CLI offline in the image matched the validated first action on 10 of 10 tier 1 cases.

| build | operator | cost |
|---|---|---|
| 1–2 sessions | 15 min | $0 (CI minutes; GHCR free for public images) |

### Step 6: Kubernetes and Terraform, load test, teardown

Design revised by the operator on 2026-11-09, before the build (the changes are marked *revised*). *Revised order:* **6a** (API, Helm chart, kind job, Terraform code with CI checks only; nothing applied), then **7a** (the operator publishes the GGUFs, the tokenizer and the model card on Hugging Face), then **6b** (GKE). GKE's init container and kind's full check both need the published repository.

- **Service.** *Revised:* `packages/hetren_cli/api.py`, as `hetren serve`, in the same image as the CLI and standard library only.
  - It reuses the CLI's input checks, model and tokenizer checks, report record and `llama-server` runtime. The shared diagnosis is in `packages/hetren_cli/diagnosis.py`.
  - Endpoints: `POST /diagnose`, `/healthz`, `/readyz`, `/metrics`.
  - One diagnosis at a time, with up to 8 waiting; beyond that it returns 503 with `Retry-After`.
  - Readiness waits for the model. A failed load exits with status 3. SIGTERM drains the running and queued diagnoses.
  - `llama-server` is the API's child process in the same container.
- **Helm chart.** *Revised: Helm instead of Kustomize*, `deploy/helm/hetren/`.
  - Objects: the Deployment, a ClusterIP Service (no load balancer, no node port), an HPA (1–2 replicas on CPU; *revised 2026-11-10*, Free Trial), a PDB (`maxUnavailable: 1`) and a ServiceAccount without a token.
  - The Deployment's init container is `fetch-model`, into an `emptyDir`, with every sha256 checked. Probes are on `/readyz` and `/healthz`. The pod runs as non-root with a read-only root filesystem.
  - Configurable: the image, model repository, variant, threads, queue and resources.
  - GKE values (*revised 2026-11-10*, Free Trial): one pod per `e2-standard-4` node (CPU request 2.5, leaving room for GKE's system pods), 2 threads.
  - `deploy/helm/check-chart.sh` runs `helm lint`, `helm template` and `kubeconform` (Kubernetes 1.36), and checks the design's properties.
  - One-command install: `deploy/README.md`.
- **kind in CI.** *Revised:* a separate `kind` job on every push, with read-only permissions. It installs the **same chart** with this commit's image and a stub `llama-server` sidecar (`deploy/kind/stub-llama-server`), which returns a recorded reply. It tests plumbing, not inference.
  - Until the repository variable `HETREN_MODEL_REPO` is set (after 7a): the chart and objects are checked, and the API must exit with status 3, naming the missing tokenizer, and be restarted.
  - After 7a: also readiness, `/diagnose`, input rejections, `/metrics`, and a 2-minute k6 Job at concurrency 1 then 2, with no errors.
  - Checked locally on 2026-11-09, both ways. The full way used the real tokenizer from an in-cluster mirror: 61 requests, no errors. At concurrency 2 latency doubled while throughput stayed at 0.5 per second, so one diagnosis runs at a time.
- **Terraform.** *Revised: all GCP infrastructure as code.* CI runs `terraform fmt`, `validate` and `tflint` (Google ruleset) in the `deploy` job, with no credentials and no apply.
  - `deploy/terraform/bootstrap/`, with local state, since it creates the bucket the other stack's state lives in:
    - the **dedicated GCP project**, its APIs, and the **GCS state bucket**;
    - the **$25 budget**, with alerts at 25%, 50%, 90% and 100% to the billing account's admins (and an optional email);
    - the **Pub/Sub kill switch**: a Cloud Run function that unlinks the project from its billing account when cost reaches the budget. It has a dry-run mode for the test message; budget data lags, so it is a backstop.
  - `deploy/terraform/gke/`, with remote state in that bucket:
    - a VPC with **private nodes** and **Cloud NAT**;
    - a zonal GKE Standard cluster in `us-central1-a`, its API reachable only from the operator's /32, the load balancer add-on off;
    - one `e2-standard-4` node pool, autoscaling **1–2** (*revised 2026-11-10*, Free Trial: a validation rejects more than 2, a precondition rejects more than 8 vCPUs at the maximum, and upgrades add no surge node), 50 GB `pd-balanced`.
  - Labels `project=hetren, milestone=4` on every resource (provider default labels).
  - `deploy/terraform/check-quota.sh`, before `apply`: 8 vCPUs in `us-central1`, 8 project-wide, and 100 GB SSD. A Free Trial account cannot request increases.
  - *Revised 2026-11-10:* the budget **excludes credits** (`EXCLUDE_ALL_CREDITS`), so its thresholds and the kill switch see gross usage that the Free Trial's credits would otherwise hide. `terraform test`, against a mocked provider in CI, checks that setting and the node pool's limits; `check_budget.py` checks the live budget after the apply. The kill switch builds with its own service account.
- **Load test** (`deploy/loadtest/k6.js`, run as a Kubernetes Job inside the cluster, so no load balancer or egress is needed).
  - Fixed fixture input; stepped concurrency 1, 2, 4, 8, 16, each held for 5 minutes.
  - Reports p50/p95/p99 latency, requests per second and the error rate per step; the runbook adds autoscaler events and the cost per 1,000 diagnoses.
  - Results committed as `docs/milestone-4/loadtest-gke.json` and summarised.
- **Teardown.** `terraform destroy` of the `gke` stack, then `deploy/terraform/verify-teardown.sh`:
  - it lists clusters, instances, disks, snapshots, images, addresses, forwarding rules, target pools, backend services, instance groups, routers, non-default networks, and every `project=hetren` resource beyond the bootstrap stack's, and fails unless none remain;
  - then `destroy` of the bootstrap stack, which deletes the project, and `verify-teardown.sh --deleted`.
  - Logged with the time and the billing report's spend in `docs/milestone-4/DEPLOY_LOG.md`.
- **Before the cloud run (6b):** the prices re-checked on the day, the budget and its alerts confirmed in place, the kill switch tested in dry-run mode, the quota check passed, and the operator's go-ahead.
- **The Free Trial design** (operator, 2026-11-10: the billing account stays on the Free Trial, so nothing can be charged to a card). The trial allows **8 concurrent Compute Engine cores** and no quota increases, so the earlier 3 × `e2-standard-8` pool cannot run.
  - **Chosen:** up to 2 × `e2-standard-4`, HPA and cluster autoscaler 1–2, `-t 2`. It keeps the autoscaling demonstration (a second node and pod under load, and the scale-up time including the model download).
    - Each pod has 2 physical cores against 4 on `e2-standard-8`, so a diagnosis is slower and two pods give about one larger pod's throughput.
    - Neither GKE option runs the validated `-t 6`: GKE results are descriptive performance numbers, not a re-validation.
  - **Rejected:** one `e2-standard-8` (no scaling to show), and `e2-standard-2` nodes (8 GB each is too tight for a 5 GB server, at 1 thread).
- **Estimate**, in Free Trial credits, at list prices; `price_check.py` reads the exact SKUs from the Cloud Billing Catalog API before the gke stack is applied:
  - Prices: `e2-standard-4` $0.134 per node-hour; `pd-balanced` $0.10 per GiB-month; Cloud NAT $0.0014 per VM-hour, $0.005 per IP-hour and $0.045 per GiB; GKE management $0.10 per hour, covered by the free tier (no other cluster on the billing account).
  - **Expected: $0.65**: a cluster for 2 h, one node throughout and a second for about 45 min, and 5.5 GiB through NAT.
  - **Ceiling: $1.83**: both nodes for the whole 4-hour session and 15 GiB through NAT ($2.23 if the GKE fee were charged).
  - A forgotten cluster costs about $3.40 a day on 1 node or $6.70 on 2, in credits, bounded by the $25 kill switch; the teardown and its verification are the main protection.

| build | operator | cost |
|---|---|---|
| 6a: 2 sessions; 6b: 1–2 sessions | 1 h GCP project and billing setup; 4 h cloud session (apply, load test, destroy, verify) | about $0.65 expected, $1.83 ceiling, in Free Trial credits; hard cap $25 |

### Step 7: Hugging Face model and dataset release (operator uploads)

- **Model repository:** the LoRA adapter (`adapter_model.safetensors`, `adapter_config.json`), the accepted GGUF file(s), the export manifest, and a model card: base model and revision, Apache-2.0 licence, training data and settings (Amendment 1), selection, the test results with intervals for all five sets (fp16, from `docs/milestone-3/RESULTS.md`), the GGUF validation check, the F6 failure, intended use (the synthetic support workflow) and out-of-scope use.
- **Dataset repository:** datasets v2 and v3 (visible inputs and evaluator files, labels included), splits v1 and v2, live test v1 (specs, captures, labels, confirmations), and the training file manifests; every file's sha256 matches the committed manifests. The dataset card: synthetic data only; how labels come from execution; the frozen protocol and splits; that test-split labels are published deliberately because the generator, labeller, seeds and split lists are in the repository, and that any future held-out set will use fresh seeds; the live captures' source model (`gpt-4.1-mini-2025-04-14`, `store=False`).
- `scripts/hf_release.py` stages both repositories locally and checks every hash; the operator reviews the staged files and uploads. A test downloads nothing in CI; a slow, operator-run check re-downloads and compares hashes.
- **7a done 2026-11-09:** the model repository [`Harsha1412/hetren-qwen3-4b-diagnosis`](https://huggingface.co/Harsha1412/hetren-qwen3-4b-diagnosis) at commit `3e875e4e8719acef839dc18e220a3ae498a1975b`, public (`EXPORT_LOG.md`, "Hugging Face release"). The verification was `verify-remote` (no download) plus `fetch-model` of both variants.
- **7b done 2026-11-11:** the dataset repository [`Harsha1412/hetren-support-runs`](https://huggingface.co/datasets/Harsha1412/hetren-support-runs) at commit `10942d316e0c1c9b3c3cb46915f971eed66ad7b4`, CC BY 4.0, public (`EXPORT_LOG.md`, "Hugging Face dataset release"). 2,016 files, verified by `verify-remote` privately and publicly; the dataset viewer shows all three subsets (18,737 rows). Training file manifests only, as planned (the file is rebuildable exactly).

| build | operator | cost |
|---|---|---|
| 2 sessions | 1 h review and upload | $0 |

### Step 8: README, technical report, demo video

- **README:** rewritten around Milestones 1–4: what Hetren is and is not, results at a glance, quick start (CLI, Docker), reproducing, claim limits. The Docker quick start states that the image is `linux/amd64` only and needs a CPU with AVX2, FMA and F16C (operator, 2026-11-08).
- **Technical report** (`docs/TECHNICAL_REPORT.md`, optional PDF): problem, environment and fault families, protocol and claim rule, datasets and labelling, baselines, training and selection, test results, CPU export, deployment and load test, limitations. Every number is taken from the committed results and logs; a test checks that the report's numbers appear in their sources.
- **Demo video** (about 3 minutes; recorded by the operator from a script and command list in `docs/milestone-4/DEMO_SCRIPT.md`): a healthy run left alone, a mapping swap diagnosed and its recovery verified in the sandbox, an F6 case shown honestly as a failure, the offline Docker run with `--network none`, and the load-test summary.

- **Tags and GitHub releases** (operator, 2026-11-09). The `publish` job pushes an image for every tag that matches its trigger, so the tag names decide which images exist.
  - **Problem:** the trigger is currently `v*`, so a milestone tag such as `v0.4.0-milestone-4` would also publish an image.
  - **Naming plan:**

    | tag | pattern | publishes an image | GitHub release | when |
    |---|---|---|---|---|
    | release candidate | `vX.Y.Z-rc.N`, e.g. `v0.4.0-rc.1` | yes, `ghcr.io/devanuthakki/hetren-cli:v0.4.0-rc.1` | a pre-release with short notes: the image digest, and that it is the GKE image of step 6b | 6b, on the commit deployed to GKE |
    | release | `vX.Y.Z`, e.g. `v1.0.0` | yes, `:v1.0.0` (no `latest` tag) | the full release notes, below | after 7 (model and dataset on Hugging Face) and 8 (final docs), on the merge commit in `main` |
    | milestone | `milestone-N`, e.g. `milestone-4` (no `v` prefix) | **no** | none | after each milestone's merge into `main` |

    The existing tags `v0.1.0-milestone-1` to `v0.3.0-milestone-3` predate the publish job and stay as they are.
  - **CI change, made with this plan's approval and shown first:**
    - The push trigger becomes the two release patterns only: `'v[0-9]+.[0-9]+.[0-9]+'` and `'v[0-9]+.[0-9]+.[0-9]+-rc.[0-9]+'` (GitHub's filter syntax). Milestone tags then start no workflow at all; their commit was already tested on `main`.
    - Defence in depth: `publish` first checks that the tag matches `^v[0-9]+\.[0-9]+\.[0-9]+(-rc\.[0-9]+)?$`, and that the version equals the CLI's `CLI_VERSION` and the chart's `appVersion`. Otherwise it stops before logging in.
    - Before each release tag: a version-bump commit (`CLI_VERSION`, `Chart.yaml` `version` and `appVersion`), shown and approved like any other.
  - **Release notes for `v1.0.0`** (`docs/RELEASE_NOTES.md`; drafted in step 8 and shown before tagging):
    - what Hetren is and its scope (the synthetic support workflow, tier 1 in the CLI and API);
    - results at a glance, from the committed results;
    - **links:** the Hugging Face model repository (pinned revision), the dataset repository, the Docker image with its digest (`ghcr.io/devanuthakki/hetren-cli:v1.0.0@sha256:…`), the technical report, and the demo video;
    - **checksums:** the export manifest, both GGUFs and the image digest;
    - known limitations: F6, the platform note and tier 1 only.
    A test checks that the notes' hashes and links match the manifest and the logs.

| build | operator | cost |
|---|---|---|
| 2–3 sessions | 2 h to record and edit | $0 |

## Order, reviews and release

1. Steps 1–3 first: the export must be accepted (or its gap measured) before anything ships a model.
2. Steps 4–5, then 6 (kind first, cloud last), then 7 and 8.
3. Every commit is shown to the operator first; boundary tests and the fast suite run locally before every push of a new module; CI (fast and slow) must be green before the PR into `main`.
4. After merge: annotated tag `milestone-4` (no `v` prefix, so no image is published: step 8, "Tags and GitHub releases"). The release tag `v1.0.0` follows step 8.
5. **Last of all (operator):** the "Final checklist" below.

| | build | operator time | cost |
|---|---|---|---|
| total | about 15–21 sessions | about 20–30 h, mostly unattended compute | about $3–5 estimated cloud spend, hard cap $25 |

## Final checklist (operator, after everything else)

Recorded on 2026-11-09 so it is not forgotten. The pre-public review found no secrets in the history, and the
LICENSE and NOTICE are in place (`7244df2`).

- [ ] **GitHub account:**
  - Settings → Emails → "Keep my email addresses private" and "Block command line pushes that expose my email";
  - `git config --global user.email <id>+<user>@users.noreply.github.com`.
  The Gmail address stays in the existing history (no rewrite: commit hashes are cited throughout the logs).
- [ ] **Make the repository public** (Settings → General → Danger Zone).
- [ ] **Code security:** secret scanning and push protection on; Dependabot alerts on.
- [ ] **Branch protection for `main`:** require a pull request and the CI checks (Repository foundation, Slow tests, Docker image, Deploy checks, kind); no force pushes or deletions.
- [ ] **GHCR:** after the first `v*` publish, set the package `hetren-cli` to public (Packages → hetren-cli → Package settings → visibility). Then check an anonymous pull: `docker logout ghcr.io`, then `docker pull ghcr.io/devanuthakki/hetren-cli:<tag>`.

## Risks

- **Quantisation loss on rare decisions:** `abstain` and two-recovery cases are few on validation (32 and 26 tier 1 / tier 2 `abstain` labels; 23 two-recovery labels), so a variant can pass the accuracy rule while changing them. The episode-agreement rate and per-decision recall are reported for that reason.
- **CPU non-determinism:** prompt caching or thread counts can change greedy outputs. The pilot measures it, and Amendment 2 fixes the settings before the validation run.
- **Platform difference:** the fp16 comparator ran on a T4 GPU. The check measures the shipped configuration end to end (quantisation and CPU together), which is the intended question; it does not separate the two causes.
- **Mac throughput:** a 2018 laptop may throttle under sustained load or sleep; the pilot's repeated runs show it, and the recommendation rule prefers Kaggle.
- **Trace scope:** runs from other workflows, and SDK trace exports (which lack the gateway's records), are out of scope; the CLI rejects them rather than producing a confident wrong answer.
- **Cloud cost:** bounded by the node-pool maximum, the budget alerts, the billing hard stop in a dedicated project, and the verified teardown.

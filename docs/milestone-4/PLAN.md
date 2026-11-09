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

- Multi-stage `Dockerfile`: base images pinned by digest; llama.cpp built at the pinned commit (CPU, generic x86_64 with AVX2); Python 3.12 with pinned requirements; non-root user. Weights are **not** in the image: they are mounted (`-v ~/.cache/hetren:/models`) or fetched once with `hetren fetch-model`.
- Image size target: under 1 GB without weights (Q4_K_M is about 2.5 GB, Q8_0 about 4.3 GB).
- CI: build the image, then run `hetren diagnose` on the committed fixtures with `docker run --network none` and the stub model, proving the offline path. Publish to GitHub Container Registry on tags only.
- **Linux agreement check (operator, descriptive, not part of acceptance; added 2026-11-08):** the validation runs on the Mac (Accelerate on), the image runs on Linux, and the pilot showed the platform can change Q4_K_M episodes. Run the 20 pilot cases in the shipped container with the validation run's decoding and caching settings and report each variant's episode agreement with the Mac validation episodes for those cases (`docs/milestone-4/EXPORT_LOG.md`, "Limitation: the validation platform is not the shipped platform").

| build | operator | cost |
|---|---|---|
| 1–2 sessions | 15 min | $0 (CI minutes; GHCR free for public images) |

### Step 6: Kubernetes and Terraform, load test, teardown

- **Service:** `packages/hetren_serving/api.py`, a thin HTTP API (`POST /diagnose`, `/healthz`, `/readyz`, `/metrics`) in front of `llama-server` in the same pod; readiness waits for the model to load; one request at a time per replica (llama.cpp CPU throughput does not improve with concurrent requests on the same cores).
- **Manifests** (`deploy/k8s/`, Kustomize): Deployment, Service (ClusterIP only, no public load balancer), HorizontalPodAutoscaler on CPU, PodDisruptionBudget, resource requests and limits, model download into an `emptyDir` by an init container with sha256 check.
- **kind in CI:** the slow job creates a `kind` cluster, deploys the manifests with the stub model, and runs a 2-minute k6 smoke load test. No cloud cost.
- **Terraform** (`deploy/terraform/gke/`):
  - a **dedicated GCP project** for Hetren, so nothing else is affected;
  - a zonal GKE Standard cluster in one region (default `us-central1-a`), one CPU node pool (`e2-standard-8`, 8 vCPU / 32 GB), autoscaling 1–3 nodes, so the maximum burn rate is bounded;
  - labels `project=hetren, milestone=4` on every resource;
  - a Cloud Billing **budget** of $25 with alerts at 25%, 50%, 90% and 100% to the operator's email, and a Pub/Sub-triggered function that **disables billing on the dedicated project at 100%** as a hard stop (budget alerts alone do not stop spending). Budget data can lag actual usage by hours, so spend may overshoot the cap before billing is disabled; the stop is a backstop, not the plan. The operator still runs `terraform destroy` and the teardown verification script right after the load test. Disabling billing can stop or delete the project's resources, which is acceptable because the dedicated project holds nothing that needs to be kept;
  - remote state in a GCS bucket in the same project.
- **Load test** (`deploy/loadtest/k6.js`, run as a Kubernetes Job inside the cluster, so no load balancer or egress is needed): fixed fixture inputs; stepped concurrency 1, 2, 4, 8, 16, each held for 5 minutes; reports p50/p95/p99 latency, requests per second, error rate, autoscaler events and cost per 1,000 diagnoses. Results committed as `docs/milestone-4/loadtest-gke.json` and summarised.
- **Teardown:** `terraform destroy`, then `scripts/verify_teardown.sh`, which lists every resource with the Hetren labels (and every compute instance, disk, load balancer, address and cluster in the project) and fails unless none remain. Logged with the time and the billing report's spend in `docs/milestone-4/DEPLOY_LOG.md`.
- **Before the cloud run:** an exact estimate from current GCP pricing (Cloud Billing Catalog API or the official pricing pages on the day), the budget and its alerts confirmed in place, and the operator's go-ahead.
- **Planning estimate** (from list prices as known in mid-2026, to be re-checked): the GKE free tier covers one zonal cluster's management fee; `e2-standard-8` on demand is about $0.27 per node-hour in `us-central1`; a 4-hour session averaging 2 nodes is about **$2–3 of compute**, plus a few cents of disk and storage, so **about $3–5 in all**. The hard stop bounds a forgotten cluster to the $25 cap (3 nodes would otherwise cost about $19 per day).

| build | operator | cost |
|---|---|---|
| 3–4 sessions | 1 h GCP project and billing setup; 4 h cloud session (apply, load test, destroy, verify) | about $3–5 estimated; hard cap $25 |

### Step 7: Hugging Face model and dataset release (operator uploads)

- **Model repository:** the LoRA adapter (`adapter_model.safetensors`, `adapter_config.json`), the accepted GGUF file(s), the export manifest, and a model card: base model and revision, Apache-2.0 licence, training data and settings (Amendment 1), selection, the test results with intervals for all five sets (fp16, from `docs/milestone-3/RESULTS.md`), the GGUF validation check, the F6 failure, intended use (the synthetic support workflow) and out-of-scope use.
- **Dataset repository:** datasets v2 and v3 (visible inputs and evaluator files, labels included), splits v1 and v2, live test v1 (specs, captures, labels, confirmations), and the training file manifests; every file's sha256 matches the committed manifests. The dataset card: synthetic data only; how labels come from execution; the frozen protocol and splits; that test-split labels are published deliberately because the generator, labeller, seeds and split lists are in the repository, and that any future held-out set will use fresh seeds; the live captures' source model (`gpt-4.1-mini-2025-04-14`, `store=False`).
- `scripts/hf_release.py` stages both repositories locally and checks every hash; the operator reviews the staged files and uploads. A test downloads nothing in CI; a slow, operator-run check re-downloads and compares hashes.

| build | operator | cost |
|---|---|---|
| 2 sessions | 1 h review and upload | $0 |

### Step 8: README, technical report, demo video

- **README:** rewritten around Milestones 1–4: what Hetren is and is not, results at a glance, quick start (CLI, Docker), reproducing, claim limits.
- **Technical report** (`docs/TECHNICAL_REPORT.md`, optional PDF): problem, environment and fault families, protocol and claim rule, datasets and labelling, baselines, training and selection, test results, CPU export, deployment and load test, limitations. Every number is taken from the committed results and logs; a test checks that the report's numbers appear in their sources.
- **Demo video** (about 3 minutes; recorded by the operator from a script and command list in `docs/milestone-4/DEMO_SCRIPT.md`): a healthy run left alone, a mapping swap diagnosed and its recovery verified in the sandbox, an F6 case shown honestly as a failure, the offline Docker run with `--network none`, and the load-test summary.

| build | operator | cost |
|---|---|---|
| 2–3 sessions | 2 h to record and edit | $0 |

## Order, reviews and release

1. Steps 1–3 first: the export must be accepted (or its gap measured) before anything ships a model.
2. Steps 4–5, then 6 (kind first, cloud last), then 7 and 8.
3. Every commit is shown to the operator first; boundary tests and the fast suite run locally before every push of a new module; CI (fast and slow) must be green before the PR into `main`.
4. After merge: annotated tag `v0.4.0-milestone-4`.

| | build | operator time | cost |
|---|---|---|---|
| total | about 15–21 sessions | about 20–30 h, mostly unattended compute | about $3–5 estimated cloud spend, hard cap $25 |

## Risks

- **Quantisation loss on rare decisions:** `abstain` and two-recovery cases are few on validation (32 and 26 tier 1 / tier 2 `abstain` labels; 23 two-recovery labels), so a variant can pass the accuracy rule while changing them. The episode-agreement rate and per-decision recall are reported for that reason.
- **CPU non-determinism:** prompt caching or thread counts can change greedy outputs. The pilot measures it, and Amendment 2 fixes the settings before the validation run.
- **Platform difference:** the fp16 comparator ran on a T4 GPU. The check measures the shipped configuration end to end (quantisation and CPU together), which is the intended question; it does not separate the two causes.
- **Mac throughput:** a 2018 laptop may throttle under sustained load or sleep; the pilot's repeated runs show it, and the recommendation rule prefers Kaggle.
- **Trace scope:** runs from other workflows, and SDK trace exports (which lack the gateway's records), are out of scope; the CLI rejects them rather than producing a confident wrong answer.
- **Cloud cost:** bounded by the node-pool maximum, the budget alerts, the billing hard stop in a dedicated project, and the verified teardown.

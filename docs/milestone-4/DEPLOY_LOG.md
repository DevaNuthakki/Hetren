# Deploy log (Milestone 4, step 6b)

Every GKE session is logged here: what was created and when, what was measured, what it cost (gross, and in
Free Trial credits), and the verified teardown. The runbook is `docs/milestone-4/DEPLOY_RUNBOOK.md`; the design and
the estimate are in PLAN.md, step 6.

## Fixed inputs

| item | value |
|---|---|
| project | `hetren-m4-dhn12` (created and deleted by `deploy/terraform/bootstrap`) |
| billing account | `0108BC-5BB242-9529D7`, Free Trial (8 concurrent vCPUs, no quota increases, credits only) |
| budget | $25 per month, gross usage (`EXCLUDE_ALL_CREDITS`), alerts at 25/50/90/100%, kill switch at 100% |
| cluster | zonal `us-central1-a`, private nodes behind Cloud NAT, API reachable only from the operator's /32 |
| node pool | 1–2 × `e2-standard-4` (8 vCPUs at most), 50 GB `pd-balanced`, no surge on upgrade |
| deployment | `deploy/helm/hetren` with `deploy/gke/values.yaml`: CPU request 2.5, `-t 2`, HPA 1–2 at 60% CPU, queue 8 |
| image | `ghcr.io/devanuthakki/hetren-cli:v0.4.0-rc.1@sha256:e6dd9cbdb0f7e349df6a3850dc9a63a950d6f2e3b7f0b4d1942fcd907dbe1da1`, public |
| model | `Harsha1412/hetren-qwen3-4b-diagnosis` at `3e875e4e8719acef839dc18e220a3ae498a1975b`, Q4_K_M |
| estimate (list prices, credits) | expected $0.65, ceiling $1.83 (PLAN.md); final figure from `price_check.py` at the gate |

## Session 1, phase 3: the bootstrap stack (2026-11-10, nothing billable)

Run by the operator from `96957ca` (in sync with `origin/milestone-4/packaging`; `git status` showed only the
untracked amendment draft), with the runbook's phase 3 commands. Environment: Terraform 1.16.7 (providers from the
committed lock file: google 8.8.1, archive 2.8.1) and the `gcloud` configuration `hetren` (account
`devaharshanuthakki12@gmail.com`).

| step | outcome |
|---|---|
| variables | `terraform.tfvars` with `project_id = "hetren-m4-dhn12"` and `billing_account = "0108BC-5BB242-9529D7"`; ignored by git (`.gitignore:53`) |
| plan | `Plan: 32 to add, 0 to change, 0 to destroy.` |
| apply (kill switch in dry-run mode) | `Apply complete! Resources: 32 added, 0 changed, 0 destroyed.` (the function was created in 1 min 15 s). Project number `925711078506`; state bucket `hetren-m4-dhn12-tfstate`; budget topic `projects/hetren-m4-dhn12/topics/hetren-budget` |
| credentials | ADC quota project set to `hetren-m4-dhn12`; `gcloud` default project set; billing `billingAccounts/0108BC-5BB242-9529D7`, enabled |
| state migration | moved into `gs://hetren-m4-dhn12-tfstate/bootstrap/default.tfstate`; the plan afterwards found no differences. The operator kept the local state files in `~/hetren-tfstate-backup/` rather than deleting them |
| live budget (`check_budget.py`) | `ok`: $25 per month on `projects/925711078506` only, alerts at 25/50/90/100%, **credits excluded (gross usage)**, updates to the kill switch's topic |
| kill switch, dry run | two test messages published (IDs `23338686562107662`, `23338373276299842`). Decisions logged: `none (below the budget)` for cost 1 (threshold 0.04) at 03:46:04.722 UTC, and `would disable billing (DRY_RUN=1)` for cost 26 (threshold 1.04) at 03:46:05.732 UTC; billing still enabled afterwards. One real budget notification arrived as well (cost 0, at 03:45:45.853 UTC): `none (below the budget)` |
| kill switch armed | `Plan: 0 to add, 1 to change, 0 to destroy.` (only `DRY_RUN` `"1"` → `"0"`); `Apply complete! Resources: 0 added, 1 changed, 0 destroyed.` |
| quotas (`check-quota.sh`) | `us-central1`: `CPUS` limit 200, `SSD_TOTAL_GB` 250 and `IN_USE_ADDRESSES` 8, all unused; project-wide `CPUS_ALL_REGIONS` 12. All allow the capped pool (8 vCPUs). The design stays at 8 vCPUs, the Free Trial's concurrent-core limit, although this quota is 12 |
| prices (`price_check.py`), first run | exit 1. Found: `E2 Instance Core running in Americas` $0.02181159 per hour (SKU `CF4E-A0C7-E3BF`); `E2 Instance Ram running in Americas` $0.00292353 per GiB-hour (`F449-33EC-A5EF`); `Balanced PD Capacity` $0.10 per GiB-month (`6AE1-525F-8B80`); `Zonal Kubernetes Clusters` $0.10 per hour (`6B92-A835-08AB`). Hence `e2-standard-4` at **$0.134023 per hour**. **Missing:** both Cloud NAT SKUs; and the NAT IP was matched to `External IP Charge on a Standard VM` ($0.005 per hour, `C054-7F72-A02E`), not the NAT IP SKU |

**Two runbook and script problems, both fixed after this run:**
- **The log query.** The runbook read `textPayload`, but the function's JSON lines are stored as `jsonPayload`, so the query returned nothing. The operator found the decisions by reading all of the function's logs. The runbook now queries `jsonPayload.action`.
- **The price check.** It searched only the Compute Engine service, but Cloud NAT's SKUs are in the Networking service (`Networking Cloud NAT gateway uptime`, `… data processing`, `… IP usage`; cloud.google.com/nat/pricing). It now searches both services for NAT, and matches the NAT IP to `Cloud NAT IP usage`. Private NAT is excluded, and a test checks that.

**Estimate**, from the catalog's E2, disk and GKE prices above, and the published Cloud NAT rates ($0.0014 per VM-hour, $0.005 per IP-hour, $0.045 per GiB), until the corrected price check confirms them:
- **expected $0.65** in credits: nodes $0.37, disks $0.02, NAT time and IP $0.01, NAT data $0.25;
- **ceiling $1.83**: nodes $1.07, disks $0.05, NAT time and IP $0.03, NAT data $0.68;
- the GKE fee is covered by the free tier (no other cluster on the billing account); it would add $0.20 and $0.40.

The first run's $0.40 and $1.15 lacked the NAT data cost.

## Session 1, phase 3 (continued): the corrected price check (2026-11-10)

Re-run by the operator after `3aa6f6d`, exit 0. All seven SKUs were found:
- the four from the first run;
- `Networking Cloud Nat Gateway Uptime` $0.0014 per hour (`32E2-4EFC-EF9F`);
- `Networking Cloud Nat Data Processing` $0.045 per GiB (`015F-5732-FFF0`);
- `Networking Cloud NAT IP Usage` $0.005 per hour (`8515-9425-D2CE`).

That gives `e2-standard-4` at $0.134023 per hour, and the **final estimate: $0.65 expected, $1.83 ceiling, in Free Trial credits**. The prices are in `artifacts/milestone-4/gke-1/prices.json`, which the load test reads.

## Session 1, phase 4: the release-candidate image (2026-11-10, nothing billable)

Run by the operator with the runbook's phase 4 commands.

| step | outcome |
|---|---|
| tag | annotated `v0.4.0-rc.1` on `96957ca54a995e327c021d4d02a66e1ca541fe83` (the commit with `CLI_VERSION = "0.4.0rc1"`, chart `appVersion` `0.4.0-rc.1`), pushed |
| CI on the tag (run 42753662860) | all jobs succeeded (Slow tests skipped: it runs on `main` only). Publish image (release tags): `ok    v0.4.0-rc.1: CLI_VERSION 0.4.0rc1, chart appVersion 0.4.0-rc.1`, `all image checks passed`, `v0.4.0-rc.1: digest: sha256:e6dd9cbdb0f7e349df6a3850dc9a63a950d6f2e3b7f0b4d1942fcd907dbe1da1 size: 4288` |
| visibility | the GHCR package `hetren-cli` set to public |
| anonymous pull | after `docker logout ghcr.io`: pulled, the same digest; `hetren 0.4.0rc1 (commit 96957ca54a995e327c021d4d02a66e1ca541fe83)`, `llama.cpp validated build: 620d2225cc436ab0b001e3200e590e3b286ef9ab`; `check-image.sh` on the pulled image: `all image checks passed` |
| pre-release | https://github.com/DevaNuthakki/Hetren/releases/tag/v0.4.0-rc.1 (published 04:20:39 UTC) |

**Checked by Claude Code on 2026-11-10:**
- run 42753662860 ran on the tag at `96957ca5…` and succeeded;
- the tag is annotated and points to that commit;
- the registry served the tag's manifest anonymously (a pull token without credentials) with digest `sha256:e6dd9cbd…`;
- the pre-release exists. Its `targetCommitish` reads `main`, GitHub's default for a release from an existing tag; the tag decides the commit.

## Session 1, phases 5–8: the cluster, the first diagnosis, the load test and the teardown (2026-11-10)

Run by the operator with the runbook's phase 5–8 commands. **One deviation: the teardown (phase 8) did not follow
in the same session.** The cluster stayed up overnight and was destroyed the next morning, 12.3 hours after the load
test ended. It was idle all that time, mostly on one node. The cost of the gap is estimated below. The runbook now
warns about this and handles a changed IP (see "Runbook changes" at the end of this section).

### Timeline (UTC)

| time | event |
|---|---|
| 04:30:36 | phase 5: `terraform apply` started (`Plan: 11 to add`: `machine_type = "e2-standard-4"`, `max_node_count = 2`, `enable_private_nodes = true`, the operator's /32). **Billable usage starts** |
| 04:33:38–04:41:34 | GKE's temporary default-pool node (`gke-hetren-default-pool-35dde5b7-wq86`) existed during cluster creation and was then removed (`remove_default_node_pool = true`). That was before the inference pool's node, so the 8-vCPU limit was never exceeded |
| 04:42:38 | the first inference node `gke-hetren-inference-c4c512cd-lcpv` created (Ready 04:42:42). Internal IP 10.10.0.3, no external IP |
| 04:42:46 | `Apply complete! Resources: 11 added` |
| — | `kubectl version`: the server was `v1.36.4-gke.2377000`, too new for kubectl 1.34.1. The operator installed kubectl v1.36.4 into `~/hetren-tools` from dl.k8s.io and checked its sha256 (`kubectl: OK`). After that: client v1.36.4, server v1.36.4-gke.2377000, no skew warning |
| 04:47:21 | phase 6: `helm install`. First pod `hetren-5d9b89668b-pcgb8` scheduled; image pulled in 7.9 s. `fetch-model` ran 04:47:29–04:48:08 (39 s for 2.5 GB, sha256 checked): `hetren-qwen3-4b-ckpt0792-q4_k_m.gguf: sha256 matches the manifest`, `Q4_K_M ready … (sha256 e3f50ba9…)` |
| 04:48:35 | first pod Ready (model load 24.6 s). API events `listening` (`max_queue` 8) and `ready` (`cli_version` 0.4.0rc1, `llama_cpp_commit` 620d2225c, `validated_build` true, threads 2, variant Q4_K_M). `helm install` returned `deployed` (about 80 s) |
| 04:49:51–04:52:34 | phase 6.2: the first diagnosis on GKE, 2 min 42.7 s wall time (details below). The end is the saved file's time; the start is that time minus the wall time |
| 04:50:37 | **the HPA rescaled to 2** ("cpu resource utilization above target"), driven by the first diagnosis: llama-server's 2 threads at full load are about 80% of the 2.5-CPU request, against a 60% target. The second pod `hetren-5d9b89668b-z9kmn` was created and could not be scheduled (`Insufficient cpu, Insufficient memory`) |
| 04:50:39 | the cluster autoscaler triggered the scale-up: instance group `gke-hetren-inference-c4c512cd-grp` 1→2 (max 2) |
| 04:51:18 | second node `gke-hetren-inference-c4c512cd-wb75` created (41 s after the rescale); Ready at 04:51:21 (44 s) |
| 04:51:22 | second pod scheduled on it (45 s); the image pull took 27.6 s (33.8 s including waiting) on the new node |
| 04:52:00–04:53:01 | second pod's `fetch-model` (61 s for 2.5 GB) |
| 04:53:28 | **second pod Ready, 171 s after the rescale**: 2 replicas on 2 nodes |
| 04:54:08 | phase 7: load test started (the k6 pod on node `lcpv`). First sample: `replicas 2 ready (HPA 2 -> 2, CPU 0%), nodes 2/2`, so the scale-up had already happened |
| 05:20:13 | load test Job completed; summary written 05:20:31; `loadtest exit 0`. The operator saved `events.txt`, `hpa-describe.txt`, `pods.yaml` and `nodes.yaml` to `artifacts/milestone-4/gke-1/` at 05:23 |
| 05:20 → morning | **the gap**: phase 8 was not run. The cluster scaled back to 1 node at some point overnight (the time is not recorded). At about 17:2x it showed `NUM_NODES 1`, `RUNNING` |
| ~17:2x | phase 8.1: `helm uninstall` failed (`Kubernetes cluster unreachable … i/o timeout`): the operator's IP had changed overnight, so the API's authorised /32 no longer matched. The step was skipped. `terraform destroy` with the new IP: `Plan: 0 to add, 0 to change, 11 to destroy`, `Destroy complete! Resources: 11 destroyed.` |
| 17:39:09 | cluster destroyed. **Billable usage ends**: the cluster existed for 13 h 8.5 min (13.14 h) |
| after | `verify-teardown.sh`: `none` for every compute and network kind. It also printed `LEFT labelled resources` (the kill switch function, its Cloud Run service and revisions, the budget topic, both buckets, the project) and `teardown NOT complete: 1 kind(s) of resource left`. That was a false alarm: these are the bootstrap stack's resources, which 8.2 removes. Its cause is the script fix listed at the end of this section |
| after | phase 8.2: the bootstrap state moved back to a local file (`yes`); `terraform destroy`: 32 to destroy, `Destroy complete! Resources: 32 destroyed.`; `verify-teardown.sh --deleted`: `project hetren-m4-dhn12: DELETE_REQUESTED, billing enabled: False`, `teardown verified: the project is deleted and billing is off`. Then `gcloud config configurations activate default` (the operator declined gcloud's offer to enable `cloudresourcemanager` on another project) |

Skipping `helm uninstall` left nothing behind: the chart creates only in-cluster objects (a ClusterIP Service, no
load balancer, no persistent volume), and they were deleted with the cluster. `verify-teardown.sh` confirmed that
no disk, address, forwarding rule or load balancer was left.

### The first diagnosis on GKE (phase 6.2)

`artifacts/milestone-4/gke-1/first-diagnosis.json`, HTTP 200:
- input `compact_first_step.json` (task "Please handle support ticket T-1895.", 3 tool calls);
- outcome `decision`, action `{"action": "decide", "args": {}, "verb": "no_intervention"}` ("The run needs no
  change.");
- 1,744 prompt tokens, 21 new tokens, stop type `eos`, generation 162.4 s;
- llama-server `version: 0.7.0-dev (build 11669, commit 620d2225c)`, `built with GNU 12.2.0 for Linux x86_64`,
  validated build, `-t 2 -c 4096 -np 1 -ngl 0`;
- code commit `96957ca5…`, CLI 0.4.0rc1, GGUF sha256 `e3f50ba9…` (Q4_K_M).

That is the first real inference on GKE: about 160 s for an uncached prompt on 2 cores of an `e2-standard-4`.

### The load test (phase 7)

`artifacts/milestone-4/loadtest-gke-1/summary.json`, committed unchanged as `docs/milestone-4/loadtest-gke.json`
(k6 1.8.2 in the cluster, steps 1, 2, 4, 8 and 16 virtual users, 300 s each, 2 replicas on 2 nodes throughout).
The first diagnosis is committed as `docs/milestone-4/first-diagnosis-gke.json`, and the reconstructed scale-up
timeline as `docs/milestone-4/loadtest-gke-timeline.json`. Job `succeeded`, 310 diagnoses, 0.8756 node-hours over the test,
node cost $0.1173 at $0.134023 per node-hour.

| VUs | diagnoses | per second | p50 | p95 | p99 | max | requests | error rate (per request) |
|---|---|---|---|---|---|---|---|---|
| 1 | 20 | 0.067 | 8.4 s | 18.1 s | 112.5 s | 136.1 s | 20 | 0 |
| 2 | 58 | 0.193 | 8.2 s | 16.7 s | 17.5 s | 18.0 s | 58 | 0 |
| 4 | 70 | 0.233 | 15.9 s | 32.0 s | 32.7 s | 34.2 s | 70 | 0 |
| 8 | 81 | 0.270 | 31.7 s | 48.2 s | 57.1 s | 62.7 s | 81 | 0 |
| 16 | 81 | 0.270 | 14 ms | 30 ms | 61.7 s | 78.0 s | 5,312 | 0.985 |

HPA CPU during the test: 19–116%, mostly 72–80% in the last steps. All 101 samples showed 2 ready replicas on 2
ready nodes.

**How to read it.** Three points bear on these figures:
- **Throughput levels off at 0.27 diagnoses per second** (about 16 per minute) with two replicas, from 8 VUs on.
  Each replica serves one diagnosis at a time, so latency beyond that point is queueing: at 4 VUs about 2 × 8 s,
  at 8 VUs about 4 × 8 s.
- **The latencies are for a cached prompt, not a fresh one.** Every k6 request sends the same fixture, and the
  diagnoser asks llama-server to reuse its prompt cache (`cache_prompt: true`, the validation run's setting;
  `packages/hetren_cli/diagnosis.py`). So after a replica's first request, only the 21 new tokens are computed:
  about 8 s, against about 136–162 s for a fresh 1,744-token prompt. The first diagnosis took 162 s, and the
  c01 step's single 136 s request is most likely the second replica's first. That explanation is an inference: the
  per-request timings were not recorded. **The 8 s p50 and the $0.38 node cost per 1,000 diagnoses are therefore a
  best case for repeated input.** For distinct inputs, roughly 150 s per diagnosis and replica implies about
  0.013 diagnoses per second with 2 replicas, and about $5.6 per 1,000 in node cost (1,000 × 150 s / 2 replicas =
  20.8 h on 2 nodes, at $0.134023 per node-hour). That rough figure comes from one timing, not a measurement.
- **The c16 error rate counts fast rejections, not failures.** Each replica accepts 9 requests at a time (one
  running, `max_queue` 8 waiting), 18 in all, and refuses more with an immediate 503 and `Retry-After`. kube-proxy
  picks a replica per connection at random, so 16 connections were most likely split unevenly, putting 10 or more
  on one replica. The VUs over its limit got 503s in about 14 ms, and k6 retried at once without honouring
  `Retry-After`. That gave 5,231 rejections in 300 s, while diagnoses stayed at 81, as at 8 VUs. No diagnosis
  failed, and no request timed out.

### Autoscaling

`loadtest.py`'s sampled scale-up times are all `0.0` in `summary.json`. That is wrong: the scale-up had happened
before the test, so its first sample was already at 2. The real timeline, from the events, pods and nodes above:

| after the HPA's rescale (04:50:37) | |
|---|---|
| 2 s | cluster autoscaler triggers the node pool 1→2 |
| 41 s | second node created |
| 44 s | second node Ready |
| 45 s | second pod scheduled |
| 83 s | `fetch-model` started (after a 27.6 s image pull) |
| 144 s | `fetch-model` finished (61 s for 2.5 GB) |
| **171 s** | **second pod Ready: scale-up from 1 to 2 replicas in under 3 minutes** |

`loadtest.py` now reconstructs this timeline from Kubernetes' events and the pod and node objects. It also reports
`scaled_before_start`, with null rather than `0.0` sampled times. Run on session 1's saved records, it gives the
table above (`loadtest-gke-timeline.json`, `scaled_before_start: true`), and its test checks the same values.

### Cost

The billing report is still to come; until then, this estimate uses the list prices above. The per-node-hour figure
is $0.142272: the node $0.134023, its 50 GB disk $0.006849 and NAT $0.0014. To that come the NAT IP at $0.005 per
cluster-hour and the NAT data, 5.5 GiB at $0.045 per GiB.

| | node-hours | cluster-hours | estimate |
|---|---|---|---|
| teardown right after the load test (about 05:35) | 1.60 | 1.07 | $0.48 |
| as it happened, second node removed about 20 min after the test | 13.75 | 13.14 | **$2.27** |
| as it happened, if the second node stayed until the morning | 25.50 | 13.14 | $3.94 |

- **The overnight gap cost an estimated $1.79** (up to $3.46 if the second node stayed), all in Free Trial
  credits. That puts the session above the planned ceiling of $1.83. The billing report will show which case
  applied. The default-pool node's 8 minutes add less than $0.01. The GKE management fee is covered by the free
  tier.
- **The budget could not have caught it:** even the higher figure is 16% of the $25 budget, below the first
  alert (25%, $6.25). Only the teardown protects against an idle cluster, as the runbook says.

### Measured cost (billing report, 2026-11-11)

From the operator, read from Billing → Overview for billing account `0108BC-5BB242-9529D7`, November 1–10, 2026:
- **Cost $3.79**, Savings $3.79 (Free Trial credits), Total cost **$0.00**.
- The figure covers the whole billing account, not this project alone. `hetren-m4-dhn12` was the only project
  with resources; "My First Project" had none.
- The last day's data may still be settling, so the figure can change slightly.

**The session cost $3.79 gross, all paid by Free Trial credits: nothing was charged.** That is above both the
planned ceiling ($1.83) and the "as it happened" estimate above ($2.27). It is close to the $3.94 case in which
the second node stayed until the morning.

**Reconciliation.** Two explanations fit the recorded times and prices. Neither is established yet:

| | what it assumes | gives | what is left |
|---|---|---|---|
| A | the GKE management fee, $0.10 per cluster-hour, appears in gross cost, and its free tier as a credit under Savings | $2.27 + $1.31 (13.14 cluster-hours) = $3.58 | $0.21: about 1.4 node-hours more than estimated, or more NAT data, disks or other small items |
| B | the fee does not appear in gross cost | $2.27 | $1.52: about 10.7 node-hours more, so the second node was removed about 16:20 UTC instead of about 05:40 |

- **Established:**
  - the measured total, $3.79 gross and $0.00 charged;
  - the cluster's lifetime (04:30:36 to 17:39:09, 13.14 h);
  - one node at about 17:2x, when the operator checked;
  - the list prices above.
- **Not established:**
  - **when the second node was removed.** The autoscaler's scale-down was not recorded: the events were
    gone by the morning, and no samples were taken after 05:20;
  - **whether the GKE fee and its free-tier credit appear in the billing account's cost and savings.** The
    estimate assumed the fee did not count at all. That was a mistake in itself: the budget measures gross
    usage, and a fee offset by a credit would still count towards it;
  - **the NAT data volume**, and the small bootstrap items (the kill switch's build and storage, Pub/Sub,
    logging), which were assumed to be negligible.
- **Both cannot hold at once:** with the fee in gross cost and the second node up until the morning, the total
  would be about $5.29.

**What would settle it:** Billing → Reports, project `hetren-m4-dhn12`, grouped by SKU, with usage amounts. The
`Zonal Kubernetes Clusters` row shows whether the fee is in the cost. The `E2 Instance Core` usage, in hours and
divided by 4, gives the node-hours, and so the second node's lifetime.

### Checked by Claude Code on 2026-11-10

From the files the operator saved (`artifacts/milestone-4/gke-1/` and `loadtest-gke-1/`):
- `first-diagnosis.json` matches the fields above;
- `summary.json` matches the table;
- the 101 samples run from 04:54:09 to 05:20:25, all at 2 replicas and 2 nodes;
- the times in the timeline come from `loadtest-gke-1/events.json` (absolute timestamps) and from `pods.yaml` and
  `nodes.yaml` (creation times, conditions, init-container start and finish);
- all pods have restart count 0;
- both inference nodes are `e2-standard-4`.

The teardown false alarm was reproduced: `verify-teardown.sh` as it was at `17a48c5`, given tab-separated rows by a
fake `gcloud`, printed the same `LEFT` lines. The operator's eight `LEFT` lines (two Cloud Run revisions, the
service, the topic, both buckets, the project and `cloudfunctions.googleapis.com/Function`) are the new test's
input, and the fixed script lists all eight as kept.

The teardown times (the overnight scale-down and 8.1's start), the kubectl install and the 8.2 outputs are the
operator's report; they were not kept as files.

### Runbook and script changes after this session

- **`verify-teardown.sh`:** `gcloud … --format='value(assetType,name)'` separates the fields with a tab, but the
  pattern for the bootstrap stack's resources expected a space, so none matched. It now matches any whitespace,
  and covers Cloud Run revisions and both Cloud Functions types. It lists these resources as `kept … (removed in
  phase 8.2)`. A test runs it with a fake `gcloud`.
- **`loadtest.py`:** the events-based timeline and `scaled_before_start`, as above.
- **The runbook:**
  - phase 5 compares kubectl with the cluster's version before using it, with the download and checksum steps;
  - phase 8 must follow in the same session, and the runbook warns about this at the top, in phase 5, and in
    phase 7;
  - the destroy commands print their `yes` prompt (no pipes);
  - if the IP changed, `helm uninstall` can be skipped;
  - phase 6 notes that the first diagnosis triggers the scale-up.

### Load test changes for a future run (not re-run on GKE)

Session 1's run stays as recorded: **its latencies and its node cost per 1,000 diagnoses are a cached best case**,
and they are labelled that way wherever they are quoted. Since then, `deploy/loadtest/k6.js`:
- **cycles through 16 distinct inputs** (`deploy/loadtest/inputs.json`). They are training examples whose case is
  in the train split of both split versions and in no validation or test list; a test checks this. So
  llama-server's prompt cache can reuse only the shared system prompt, as with real traffic;
- **counts 503 rejections separately** (`rejected` per step), and leaves them out of the latencies and the error
  rate. After a rejection, the virtual user waits the `Retry-After` the API sends (30 s).

At about 150 s per fresh diagnosis, the default steps (1, 2, 4, 8, 16 × 300 s) no longer fit. From 8 virtual users
on, each replica has 4 or more requests in line, so requests reach k6's 600 s timeout. A realistic run would use
fewer steps for longer, for example 1, 2, 4 × 900 s; the steps are chosen when such a run is planned.

# Deploying Hetren's diagnosis API

The API is `hetren serve` (`packages/hetren_cli/api.py`), in the same image as the CLI
(`ghcr.io/devanuthakki/hetren-cli`). It has the same scope as the CLI: single-recovery (tier 1) runs of Hetren's
synthetic support workflow, one greedy step with the validated GGUF, and nothing is ever applied.

| path | what it is | where it runs |
|---|---|---|
| `helm/hetren/` | the Helm chart: Deployment (init container `fetch-model`, probes, non-root, read-only), ClusterIP Service, HPA, PDB, ServiceAccount | kind in CI, GKE |
| `kind/` | `values.yaml`, the stub `llama-server` image and `smoke.sh` | CI's `kind` job, or locally |
| `gke/values.yaml` | the GKE values: one pod per `e2-standard-8` node, 4 threads | GKE (step 6b) |
| `loadtest/` | `k6.js` and the in-cluster `job.yaml` (stepped concurrency 1, 2, 4, 8, 16) | kind (2-minute smoke), GKE |
| `terraform/bootstrap/` | the dedicated project, its APIs, the state bucket, the $25 budget and the billing kill switch | the operator, step 6b |
| `terraform/gke/` | the VPC, private nodes behind Cloud NAT, the zonal cluster and the node pool (1 to 3 nodes) | the operator, step 6b |
| `terraform/check-quota.sh`, `terraform/verify-teardown.sh` | the quota check before `apply`, and the check after `destroy` | the operator, step 6b |
| `tools.sh` | the pinned tools with their sha256 (kind, Helm, Terraform, tflint, kubeconform) | CI |

## The API

```zsh
hetren serve --host 0.0.0.0 --port 8000          # in the image; the model from $HETREN_CACHE (/models)
curl -s localhost:8000/readyz
curl -s -X POST localhost:8000/diagnose -H 'Content-Type: application/json' \
     --data '{"compact": '"$(cat tests/fixtures/hetren_cli/compact_first_step.json)"'}'
```

`POST /diagnose` takes `{"record": <AgentRunRecord evidence payload>}` or `{"compact": <compact-evidence-v1>}`.

| status | meaning |
|---|---|
| 200 | the diagnosis, as `hetren diagnose --format json` writes it |
| 400 | the input was rejected (the CLI's exit 2) |
| 502 | the model's reply was not a valid action (the CLI's exit 4) |
| 500 | `llama-server` failed |
| 503 | not ready, draining, or the queue is full (`Retry-After`) |

It runs one diagnosis at a time, and up to `--max-queue` (default 8) requests wait. `/healthz` answers while
the model loads, and `/readyz` reports ready once it has loaded. `/metrics` serves Prometheus text. If the
model cannot be loaded, the process exits with status 3.

## Install with one command

On a cluster with the image published (a `v*` tag) and the model repository on Hugging Face (step 7a):

```zsh
helm install hetren deploy/helm/hetren -f deploy/gke/values.yaml \
  --set image.tag=v0.4.0-rc.1 --set model.repo=<huggingface model repository>
```

`image.tag` and `model.repo` are required, and the chart refuses to render without them. Use `model.variant=Q8_0`
for the higher-fidelity variant, and `model.tokenSecret` (a Secret with the key `token`) for a private repository.

## kind (CI, or locally)

```zsh
docker build -f docker/hetren-cli/Dockerfile --target runtime -t hetren-cli:ci .
docker build deploy/kind/stub-llama-server -t hetren-stub-llama-server:ci
deploy/kind/smoke.sh                       # KEEP_CLUSTER=1 keeps the cluster
```

kind checks the deployment's plumbing, not inference. A stub `llama-server` returns a recorded reply, and the
API checks the real tokenizer. Without `HETREN_MODEL_REPO`, the API must exit with status 3, name the missing
tokenizer, and be restarted. Once the repository variable `HETREN_MODEL_REPO` is set (after step 7a), CI also
checks readiness, `/diagnose`, input rejections, `/metrics` and a 2-minute k6 Job with no errors.

## Checks without a cluster or credentials

```zsh
deploy/helm/check-chart.sh     # helm lint, helm template, kubeconform (Kubernetes 1.36), design properties
deploy/terraform/check.sh      # terraform fmt, init -backend=false, validate, tflint (Google ruleset)
```

CI's `deploy` job runs both on every push. Nothing is planned or applied in CI.

## GKE (step 6b, operator)

The full runbook is written for step 6b. In outline:

1. **Bootstrap**, with local state; the operator's `terraform.tfvars` stays out of git:
   - `cd deploy/terraform/bootstrap`
   - `terraform init`
   - `terraform apply -var kill_switch_dry_run=true` with `project_id` and `billing_account` set.
2. **Test the kill switch without stopping anything:**
   - Publish a below-budget message, then an over-budget one, to `hetren-budget`, for example:
     `gcloud pubsub topics publish hetren-budget --project <id> --message '{"costAmount": 30, "budgetAmount": 25}'`
   - Expected in the function's logs: `none (below the budget)` for the first, `would disable billing (DRY_RUN=1)` for the second.
   - Then `terraform apply -var kill_switch_dry_run=false`.
3. **Check the quotas:** `deploy/terraform/check-quota.sh <id>` needs 24 vCPUs in `us-central1` and 24 project-wide.
4. **Create the cluster:**
   - `cd deploy/terraform/gke`
   - `terraform init -backend-config="bucket=<id>-tfstate"`
   - `terraform apply -var project_id=<id> -var master_authorized_cidr=<your IP>/32`
5. **Deploy and load-test:** the one-command install above, then the load-test Job (`deploy/loadtest/job.yaml`).
6. **Tear down:**
   - `terraform destroy` in `gke/`, then `deploy/terraform/verify-teardown.sh <id>`;
   - then `terraform destroy` in `bootstrap/` (which deletes the project), then `verify-teardown.sh <id> --deleted`.

The budget's alerts go to the billing account's admins. At 100% the kill switch unlinks the project from its
billing account. Budget data lags usage by hours, so this is a backstop, not the plan.

## Tool versions

| tool | version |
|---|---|
| kind | v0.33.0, node image `kindest/node:v1.36.4` |
| Helm | v3.22.1 |
| Terraform | 1.16.7, Google provider 8.8.1, archive provider 2.8.1 |
| tflint | v0.65.0, Google ruleset 0.41.0 |
| kubeconform | v0.8.0 |
| k6 | 1.8.2 (`grafana/k6` image) |

`tools.sh` installs these on Linux with sha256 checks. On a Mac, install the same versions from the
projects' releases.

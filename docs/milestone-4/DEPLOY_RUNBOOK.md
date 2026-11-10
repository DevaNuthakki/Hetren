# Step 6b runbook: GKE on the Free Trial (operator)

This runbook deploys the diagnosis API on GKE, load-tests it, and tears everything down, all within the Google
Cloud Free Trial (PLAN.md, step 6, "The Free Trial design").

- **Where:** project `hetren-m4-dhn12`, billing account `0108BC-5BB242-9529D7` (Free Trial), `gcloud`
  configuration `hetren` (account `devaharshanuthakki12@gmail.com`).
- **What the trial allows:** at most 8 concurrent vCPUs and no quota increases. The cluster uses up to 2 ×
  `e2-standard-4`.
- **Cost:** everything is paid from the trial's credits; nothing can reach a card. The budget measures **gross**
  usage (credits excluded), at $25.
- **Protection:** the teardown and its verification are the main protection; the kill switch is a backstop.
- **Order:** phases 3 and 4 create nothing billable. **Phase 5 starts billable usage, and only after the gate at
  the end of phase 3.**

Send Claude Code the output each step asks for; it is logged in `DEPLOY_LOG.md`.

## Every new terminal

```zsh
cd ~/Documents/personal-projects/hetren
export PATH="$(gcloud info --format='value(installation.sdk_root)')/bin:$HOME/hetren-tools:$PATH"
export SSL_CERT_FILE="$(~/.hetren-pilot/bin/python -m certifi)"   # python.org's Python has no CA certificates
gcloud config configurations activate hetren
gcloud config list 2>/dev/null | grep -E "account|project"
```

Expect `account = devaharshanuthakki12@gmail.com`. After phase 3, also `project = hetren-m4-dhn12`.

## Phase 3: the bootstrap stack (nothing billable)

It creates the project, its APIs, the state bucket, the budget and the kill switch.

1. **Check the checkout and write the variables.** The `.tfvars` file is gitignored.
   ```zsh
   git pull && git status --short
   cd deploy/terraform/bootstrap
   printf 'project_id      = "hetren-m4-dhn12"\nbilling_account = "0108BC-5BB242-9529D7"\n' > terraform.tfvars
   terraform init
   ```
   Expect `git status` to show only `?? docs/milestone-4/amendment-2-draft.md`, then
   `Terraform has been successfully initialized!` (the providers come from the committed lock file).

2. **Plan, then apply with the kill switch in dry-run mode:**
   ```zsh
   terraform plan -var kill_switch_dry_run=true -out bootstrap.plan
   terraform apply bootstrap.plan
   ```
   - Expect `Plan: 32 to add, 0 to change, 0 to destroy.` Then, after a few minutes (the function's build is the
     slowest part), `Apply complete! Resources: 32 added, 0 changed, 0 destroyed.` and the outputs
     `project_id`, `project_number`, `state_bucket = "hetren-m4-dhn12-tfstate"` and `budget_topic`.
   - If the apply stops with an error that mentions a **quota project**, the project exists by then: run
     `gcloud auth application-default set-quota-project hetren-m4-dhn12`, then `terraform apply
     -var kill_switch_dry_run=true` again.
   - Any other error: stop and send it.

3. **Set the quota project and the default project**, now that the project exists:
   ```zsh
   gcloud auth application-default set-quota-project hetren-m4-dhn12
   gcloud config set project hetren-m4-dhn12
   ```

4. **Move the bootstrap state into the bucket** right away:
   ```zsh
   cp backend.tf.example backend.tf
   terraform init -migrate-state -backend-config="bucket=hetren-m4-dhn12-tfstate"
   terraform plan -var kill_switch_dry_run=true
   ```
   - Answer `yes` to copy the state.
   - Expect `No changes. Your infrastructure matches the configuration.`
   - The local `terraform.tfstate` can then be deleted; the bucket is versioned.

5. **Check the live budget.** It must exclude credits:
   ```zsh
   cd ~/Documents/personal-projects/hetren
   ~/.hetren-pilot/bin/python deploy/terraform/check_budget.py --billing-account 0108BC-5BB242-9529D7 --project hetren-m4-dhn12
   ```
   Expect `ok    budget hetren-hetren-m4-dhn12: $25 per month on projects/<number> only, alerts at 25/50/90/100%,
   credits excluded (gross usage), updates to the kill switch's topic`.

6. **Test the kill switch.** It is in dry-run mode, so nothing is stopped. Publish one message below the budget
   and one above it, wait a minute, then read the function's log:
   ```zsh
   gcloud pubsub topics publish hetren-budget --message '{"budgetDisplayName":"test","costAmount":1.00,"budgetAmount":25.00,"alertThresholdExceeded":0.04,"currencyCode":"USD"}'
   gcloud pubsub topics publish hetren-budget --message '{"budgetDisplayName":"test","costAmount":26.00,"budgetAmount":25.00,"alertThresholdExceeded":1.04,"currencyCode":"USD"}'
   gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="hetren-kill-switch" AND jsonPayload.action:*' --freshness 15m --format 'table(timestamp, jsonPayload.action, jsonPayload.cost, jsonPayload.threshold)'
   gcloud billing projects describe hetren-m4-dhn12 --format 'value(billingEnabled)'
   ```
   - The function writes one JSON object per decision, which Cloud Logging stores as `jsonPayload`.
   - Expect a row `none (below the budget)` with cost 1 and a row `would disable billing (DRY_RUN=1)` with cost
     26. Real budget notifications (cost 0) may appear too. If the rows are missing, wait another minute and
     read again.
   - Then expect `True`: billing is still on.

7. **Arm the kill switch:**
   ```zsh
   cd deploy/terraform/bootstrap && terraform apply && cd -
   ```
   Expect `Plan: 0 to add, 1 to change, 0 to destroy.` (the function's `DRY_RUN` becomes `0`). Answer `yes`.

8. **Check the quotas:**
   ```zsh
   deploy/terraform/check-quota.sh hetren-m4-dhn12
   ```
   - Expect four `ok` lines (`CPUS`, `SSD_TOTAL_GB` and `IN_USE_ADDRESSES` in `us-central1`, and
     `CPUS_ALL_REGIONS`), then `quotas allow the capped node pool`.
   - A `FAIL` cannot be fixed on the Free Trial: stop and send it.

9. **Check the prices.** The Cloud Billing Catalog API is read-only:
   ```zsh
   mkdir -p artifacts/milestone-4/gke-1
   ~/.hetren-pilot/bin/python deploy/terraform/price_check.py --project hetren-m4-dhn12 --out artifacts/milestone-4/gke-1/prices.json
   ```
   - Expect seven `ok` lines, each giving a SKU's description and its price, and the `e2-standard-4` hourly price.
     The three Cloud NAT prices come from the Networking service (`Networking Cloud NAT gateway uptime`, `… data
     processing`, `… IP usage`).
   - Then the `expected` and `ceiling` estimates in credits.
   - A `MISSING` line means a SKU's description changed: send the output.

**GATE: send Claude Code the output of steps 2, 4, 5, 6, 7, 8 and 9.** Claude Code checks them and gives you the
final estimate from the catalog's prices. Phase 5 waits for your go-ahead.

## Phase 4: the image (nothing billable)

1. **Tag the release candidate and push the tag.** Tag the commit Claude Code names, the one that passed CI:
   ```zsh
   git tag -a v0.4.0-rc.1 -m "v0.4.0-rc.1: the GKE image for step 6b" <commit>
   git push origin v0.4.0-rc.1
   gh run watch --exit-status $(gh run list --workflow ci.yml --limit 1 --json databaseId --jq '.[0].databaseId')
   ```
   - Expect every job to pass, including `Publish image (release tags)`.
   - Its first step prints `ok    v0.4.0-rc.1: CLI_VERSION 0.4.0rc1, chart appVersion 0.4.0-rc.1`.

2. **Make the package public.** On GitHub: Packages → `hetren-cli` → Package settings → Change visibility →
   Public. Then check an anonymous pull:
   ```zsh
   docker logout ghcr.io; docker pull ghcr.io/devanuthakki/hetren-cli:v0.4.0-rc.1
   docker image inspect --format '{{index .RepoDigests 0}}' ghcr.io/devanuthakki/hetren-cli:v0.4.0-rc.1
   ```
   Expect the pull to succeed without logging in, and a digest `…@sha256:…`. Send it.

3. **Create the pre-release:**
   ```zsh
   gh release create v0.4.0-rc.1 --prerelease --title "v0.4.0-rc.1 (GKE image, step 6b)" --notes "Release candidate: the hetren-cli image deployed to GKE in step 6b. Image: ghcr.io/devanuthakki/hetren-cli:v0.4.0-rc.1@<digest>. Model: https://huggingface.co/Harsha1412/hetren-qwen3-4b-diagnosis (revision 3e875e4e8719acef839dc18e220a3ae498a1975b). Not the final release."
   ```

## Phase 5: the cluster (billable usage starts)

```zsh
cd deploy/terraform/gke
terraform init -backend-config="bucket=hetren-m4-dhn12-tfstate"
MYIP="$(curl -s https://checkip.amazonaws.com)/32"; echo "$MYIP"
terraform plan -var project_id=hetren-m4-dhn12 -var master_authorized_cidr="$MYIP" -out gke.plan
caffeinate -i terraform apply gke.plan
date -u +%FT%TZ
gcloud container clusters get-credentials hetren --zone us-central1-a --project hetren-m4-dhn12
kubectl get nodes -L hetren/pool
kubectl version
cd -
```

- **Plan:** expect `Plan: 11 to add, 0 to change, 0 to destroy.` (network, subnet, router, NAT, the node
  service account and its 4 role bindings, the cluster and the node pool).
- **Apply:** about 10 minutes, ending `Apply complete!`. The `date` line records when billing started.
- **Nodes:** one `e2-standard-4` node, `Ready`, with `hetren/pool=inference`.
- **kubectl skew:** if `kubectl version` reports a server two or more minor versions newer than 1.34, upgrade
  kubectl before going on.

If your IP changes during the session, `kubectl` times out. Re-run the `MYIP=` line and `terraform apply` with the
same `-var`s; that changes only the authorised network.

## Phase 6: deploy and one real diagnosis

```zsh
caffeinate -i helm install hetren deploy/helm/hetren -f deploy/gke/values.yaml \
  --set image.tag=v0.4.0-rc.1 --set model.repo=Harsha1412/hetren-qwen3-4b-diagnosis --wait --timeout 20m
kubectl logs deploy/hetren -c fetch-model | tail -3
kubectl logs deploy/hetren -c hetren | head -3
kubectl port-forward service/hetren 8000:8000 >/dev/null &
sleep 3; curl -s localhost:8000/readyz; echo
time curl -s -X POST localhost:8000/diagnose -H 'Content-Type: application/json' \
  --data "{\"compact\": $(cat tests/fixtures/hetren_cli/compact_first_step.json)}" > artifacts/milestone-4/gke-1/first-diagnosis.json
python3 -c "import json; r=json.load(open('artifacts/milestone-4/gke-1/first-diagnosis.json')); print(r['result']['outcome'], r['result'].get('action'), r['server']['version'], r['generation']['seconds'])"
kill %1
```

- **The install:** waits until the pod is ready. The init container downloads 2.5 GB at the pinned revision and
  checks every sha256.
- **The init log:** expect `Q4_K_M ready …`.
- **The API log:** expect `"event": "ready"` with `llama_cpp_commit` `620d2225c`.
- **`/readyz`:** `{"reason": "ready", "state": "ready", "status": "ready"}`.
- **The last line:** the outcome, the action, `build 11669, commit 620d2225c`, and the generation seconds: the
  first real inference on GKE.

## Phase 7: the load test

This takes about 25 minutes, plus the scale-up:

```zsh
caffeinate -i ~/.hetren-pilot/bin/python deploy/gke/loadtest.py --out artifacts/milestone-4/loadtest-gke-1 --prices artifacts/milestone-4/gke-1/prices.json 2>&1 | tee artifacts/milestone-4/loadtest-gke-1.log
echo "loadtest exit ${pipestatus[1]}"
kubectl get events -A --field-selector involvedObject.kind=Node -o wide | tail -20
```

- **While it runs:** a line every 15 s, `replicas <ready> ready (HPA <current> -> <desired>, CPU <n>%), nodes
  <ready>/<total>`. The HPA should ask for 2 replicas within a few minutes. The cluster autoscaler then adds the
  second node, and the second pod becomes ready after its 2.5 GB download.
- **The end:** a JSON block with `job`, `diagnoses`, `node_hours`, `node_cost_per_1000_diagnoses_usd` and
  `scaling`.
- **Send:** the exit status, `artifacts/milestone-4/loadtest-gke-1/summary.json` and the log's last 30 lines.

## Phase 8: teardown, in the same session

```zsh
helm uninstall hetren
cd deploy/terraform/gke
terraform destroy -var project_id=hetren-m4-dhn12 -var master_authorized_cidr="$(curl -s https://checkip.amazonaws.com)/32"
date -u +%FT%TZ
cd -
deploy/terraform/verify-teardown.sh hetren-m4-dhn12
```

- **Destroy:** answer `yes`. Expect `Destroy complete!`. The `date` line records when billable usage ended.
- **Verify:** expect `none` for every kind, then `teardown verified: no cluster, compute or network resources left
  in hetren-m4-dhn12`.

Then delete the project. Move the bootstrap state back to a local file first, because the destroy deletes the
bucket it is in:

```zsh
cd deploy/terraform/bootstrap
rm backend.tf
terraform init -migrate-state
terraform destroy
cd -
deploy/terraform/verify-teardown.sh hetren-m4-dhn12 --deleted
gcloud config configurations activate default
```

- **The migration:** answer `yes` to copy the state to a local file.
- **The destroy:** answer `yes`. It deletes the project; Google keeps it pending deletion for 30 days.
- **Verify:** expect `teardown verified: the project is deleted and billing is off`.

The next day, check Billing → Reports for the project, with credits shown separately. Send the gross cost and the
credits used for Claude Code to log.

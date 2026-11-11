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
- **Phases 5 to 8 are one session.** Start phase 5 only when you have about 1.5 hours to run phases 5–8 without a
  break. Run phase 8 as soon as phase 7 ends. An idle cluster costs about $0.14 an hour per node, and the budget
  would not alert for days. Overnight, your IP can also change, which locks `kubectl` and `helm` out of the cluster.
  In session 1, the cluster stayed up 12 hours after the load test (DEPLOY_LOG.md).

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

From here, phases 5 to 8 run in one session (see the top).

**5.1 and 5.2: the plan and the apply.**

```zsh
cd deploy/terraform/gke
terraform init -backend-config="bucket=hetren-m4-dhn12-tfstate"
MYIP="$(curl -s https://checkip.amazonaws.com)/32"; echo "$MYIP"
terraform plan -var project_id=hetren-m4-dhn12 -var master_authorized_cidr="$MYIP" -out gke.plan
caffeinate -i terraform apply gke.plan
date -u +%FT%TZ
cd -
```

- **Plan:** expect `Plan: 11 to add, 0 to change, 0 to destroy.` (network, subnet, router, NAT, the node
  service account and its 4 role bindings, the cluster and the node pool).
- **Apply:** about 12 minutes, ending `Apply complete!`. The `date` line records when billing started.

**Before 5.3: is kubectl new enough for the cluster?** kubectl supports a server at most one minor version newer
than itself. Compare the two versions before using kubectl:

```zsh
gcloud container clusters describe hetren --zone us-central1-a --project hetren-m4-dhn12 --format='value(currentMasterVersion)'
which kubectl
kubectl version --client
```

If the server's minor version is more than one above the client's, install the server's version into
`~/hetren-tools`. In session 1, the server was `1.36.4-gke.2377000` and the client 1.34.1. Set `KVER` to the
server's version without the `-gke…` suffix:

```zsh
KVER="v1.36.4"
KARCH="$(uname -m | sed 's/x86_64/amd64/')"; echo "$KARCH"
curl -fLo ~/hetren-tools/kubectl "https://dl.k8s.io/release/$KVER/bin/darwin/$KARCH/kubectl"
curl -fLo ~/hetren-tools/kubectl.sha256 "https://dl.k8s.io/release/$KVER/bin/darwin/$KARCH/kubectl.sha256"
cd ~/hetren-tools && echo "$(cat kubectl.sha256)  kubectl" | shasum -a 256 --check && cd -
chmod +x ~/hetren-tools/kubectl
hash -r
which kubectl
kubectl version --client
```

- **Arch:** `arm64` on Apple silicon, `amd64` on Intel.
- **Checksum:** expect `kubectl: OK`. If the check fails, stop; don't use the file.
- **Path:** `which kubectl` must now print `~/hetren-tools/kubectl` (expanded). If another kubectl comes first,
  check the `export PATH` line from "Every new terminal".

**5.3: credentials and the node.**

```zsh
gcloud container clusters get-credentials hetren --zone us-central1-a --project hetren-m4-dhn12
kubectl get nodes -L hetren/pool
kubectl version
```

- **Nodes:** one `e2-standard-4` node, `Ready`, with `hetren/pool=inference`.
- **Version:** client and server versions, and no skew warning.

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
  first real inference on GKE (162 s in session 1).
- **The scale-up starts here.** This diagnosis keeps llama-server's 2 threads busy for about 2.5 minutes, about
  80% of the pod's CPU request against the HPA's 60% target. So the HPA asks for a second replica, and the cluster
  autoscaler adds the second node, before phase 7 begins. In session 1, the second pod was ready 171 s after the
  rescale. `loadtest.py` still records this timeline from Kubernetes' events. Its sampled scale-up times are null,
  with `scaled_before_start: true`. Go straight on to phase 7: the events it reads are kept for about an hour.

## Phase 7: the load test

This takes about 25 minutes, plus the scale-up:

```zsh
caffeinate -i ~/.hetren-pilot/bin/python deploy/gke/loadtest.py --out artifacts/milestone-4/loadtest-gke-1 --prices artifacts/milestone-4/gke-1/prices.json 2>&1 | tee artifacts/milestone-4/loadtest-gke-1.log
echo "loadtest exit ${pipestatus[1]}"
kubectl get events -A --field-selector involvedObject.kind=Node -o wide | tail -20
```

- **At the start:** if phase 6 has already scaled the deployment up, it prints `NOTE: already scaled up before
  the test`.
- **While it runs:** a line every 15 s, `replicas <ready> ready (HPA <current> -> <desired>, CPU <n>%), nodes
  <ready>/<total>`. If the deployment was not scaled up yet, the HPA should ask for 2 replicas within a few
  minutes. The cluster autoscaler then adds the second node, and the second pod becomes ready after its 2.5 GB
  download.
- **The end:** a JSON block with `job`, `diagnoses`, `node_hours`, `node_cost_per_1000_diagnoses_usd`, `scaling`
  and `timeline`. The `timeline` gives the scale-up's moments in UTC and in seconds after the HPA's rescale.
- **Send:** the exit status, `artifacts/milestone-4/loadtest-gke-1/summary.json` and the log's last 30 lines.
- **Then go straight to phase 8**, in the same session.

## Phase 8: teardown, in the same session

Run this right after phase 7, without a break.

**The prompts:** both `terraform destroy` commands ask `Enter a value:` and wait for `yes`. Run them as written
here. Don't pipe them through `tail`, `tee` or `grep`, which would hide the prompt and leave the command waiting.

**8.1: the cluster.**

```zsh
helm uninstall hetren
cd deploy/terraform/gke
MYIP="$(curl -s https://checkip.amazonaws.com)/32"; echo "$MYIP"
terraform destroy -var project_id=hetren-m4-dhn12 -var master_authorized_cidr="$MYIP"
date -u +%FT%TZ
cd -
deploy/terraform/verify-teardown.sh hetren-m4-dhn12
```

- **`helm uninstall`:** expect `release "hetren" uninstalled`.
- **If your IP has changed since phase 5:** `helm uninstall` fails with `Kubernetes cluster unreachable … i/o
  timeout`, because the cluster's API accepts only the /32 from phase 5. Skip it and go on. The destroy uses your
  current IP, and it deletes the cluster with everything in it. The chart creates nothing outside the cluster: no
  load balancer, no persistent disk.
- **Destroy:** the plan shows `Plan: 0 to add, 0 to change, 11 to destroy.` Answer `yes`. Expect `Destroy
  complete! Resources: 11 destroyed.` The `date` line records when billable usage ended.
- **Verify:** expect `none` for every kind. Then a `kept  the bootstrap stack's resources (removed in phase 8.2):`
  list: the project, both buckets, the budget topic, the kill switch function, its Cloud Run service and revisions.
  Then `none  labelled resources beyond the bootstrap stack's` and `teardown verified: no cluster, compute or
  network resources left in hetren-m4-dhn12`. Any `LEFT` line is a real leftover: send it before going on.

**8.2: the project.**

Delete the project. Move the bootstrap state back to a local file first, because the destroy deletes the
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
- **The destroy:** the plan shows `32 to destroy`. Answer `yes`. It deletes the project; Google keeps it pending
  deletion for 30 days.
- **Verify:** expect `teardown verified: the project is deleted and billing is off`.

The next day, check Billing → Reports for the project, with credits shown separately. Send the gross cost and the
credits used for Claude Code to log.

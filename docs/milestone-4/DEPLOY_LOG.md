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
| image | `ghcr.io/devanuthakki/hetren-cli:v0.4.0-rc.1` (digest recorded at publish) |
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

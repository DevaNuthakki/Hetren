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

## Sessions

None yet.

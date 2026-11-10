#!/usr/bin/env bash
# Before terraform apply of the gke stack (operator, step 6b): the project's quotas must allow the capped node
# pool at its maximum, 2 x e2-standard-4 = 8 vCPUs and 2 x 50 GB pd-balanced, in the region and project-wide.
# A Free Trial account cannot request increases, so this must pass as it is. Read-only (gcloud describe).
# Exit 0 only if every quota has room.
#
#   deploy/terraform/check-quota.sh <project_id> [region]
set -euo pipefail

project="${1:?usage: check-quota.sh <project_id> [region]}"
region="${2:-us-central1}"

regional=$(gcloud compute regions describe "$region" --project "$project" --format=json)
global=$(gcloud compute project-info describe --project "$project" --format=json)

python3 - "$regional" "$global" "$region" <<'PY'
import json, sys

regional, project, region = json.loads(sys.argv[1]), json.loads(sys.argv[2]), sys.argv[3]
needs = [("region " + region, regional, "CPUS", 8), ("region " + region, regional, "SSD_TOTAL_GB", 100),
         ("region " + region, regional, "IN_USE_ADDRESSES", 1), ("project", project, "CPUS_ALL_REGIONS", 8)]
short = 0

for scope, source, metric, need in needs:
    quota = next((q for q in source.get("quotas", []) if q["metric"] == metric), None)

    if quota is None:
        print(f"FAIL  {scope} {metric}: not reported")
        short += 1
        continue

    free = quota["limit"] - quota["usage"]
    ok = free >= need
    short += not ok
    print(f"{'ok  ' if ok else 'FAIL'}  {scope} {metric}: limit {quota['limit']:g}, used {quota['usage']:g}, "
          f"free {free:g}, needed {need}")

print("quotas allow the capped node pool" if not short else
      f"{short} quota(s) too low; a Free Trial account cannot request increases, so stop here (Claude Code "
      "re-plans the node pool)")
sys.exit(1 if short else 0)
PY

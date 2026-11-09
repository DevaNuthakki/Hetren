#!/usr/bin/env bash
# After terraform destroy (operator, step 6b): fails unless nothing billable is left. Read-only.
#
#   deploy/terraform/verify-teardown.sh <project_id>           after destroying the gke stack
#   deploy/terraform/verify-teardown.sh <project_id> --deleted  after destroying the bootstrap stack too
#
# After the gke stack: no cluster, instance, disk, snapshot, image, address, forwarding rule, target pool,
# backend service, instance group, router or non-default network in the project, and no labelled resource
# (project=hetren) other than the bootstrap stack's (the project, state and function buckets, budget topic,
# kill switch and its service account). With --deleted: the project is being deleted and billing is off.
set -euo pipefail

project="${1:?usage: verify-teardown.sh <project_id> [--deleted]}"
mode="${2:-}"
left=0

if [ "$mode" = --deleted ]; then
  state=$(gcloud projects describe "$project" --format='value(lifecycleState)' 2>/dev/null || echo GONE)
  billing=$(gcloud billing projects describe "$project" --format='value(billingEnabled)' 2>/dev/null || echo False)
  echo "project $project: $state, billing enabled: $billing"
  case "$state" in DELETE_REQUESTED|GONE) ;; *) left=$((left + 1)) ;; esac
  [ "$billing" = True ] && left=$((left + 1))
  [ "$left" -eq 0 ] && echo "teardown verified: the project is deleted and billing is off" && exit 0
  echo "teardown NOT complete"; exit 1
fi

check() { # check <description> <gcloud arguments...>
  local description="$1"; shift
  local out
  out=$(gcloud "$@" --project "$project" --format='value(name)' 2>&1) || { echo "FAIL  $description: $out"; left=$((left + 1)); return; }
  if [ -n "$out" ]; then echo "LEFT  $description: $(tr '\n' ' ' <<<"$out")"; left=$((left + 1)); else echo "none  $description"; fi
}

check "GKE clusters" container clusters list
check "compute instances" compute instances list
check "disks" compute disks list
check "snapshots" compute snapshots list
check "images" compute images list --no-standard-images
check "addresses" compute addresses list
check "forwarding rules (load balancers)" compute forwarding-rules list
check "target pools" compute target-pools list
check "backend services" compute backend-services list
check "instance groups" compute instance-groups list
check "routers (Cloud NAT)" compute routers list
check "networks other than default" compute networks list --filter='name!=default'

kept='^(cloudresourcemanager.googleapis.com/Project|storage.googleapis.com/Bucket|pubsub.googleapis.com/Topic|cloudfunctions.googleapis.com/Function|run.googleapis.com/Service|iam.googleapis.com/ServiceAccount|artifactregistry.googleapis.com/Repository) '
labelled=$(gcloud asset search-all-resources --scope="projects/$project" --query='labels.project=hetren' \
  --format='value(assetType,name)' 2>&1) || { echo "FAIL  labelled resources: $labelled"; left=$((left + 1)); labelled=""; }
other=$(grep -vE "$kept" <<<"$labelled" | sed '/^$/d' || true)
if [ -n "$other" ]; then echo "LEFT  labelled resources:"; echo "$other"; left=$((left + 1)); else echo "none  labelled resources beyond the bootstrap stack's"; fi

if [ "$left" -gt 0 ]; then echo "teardown NOT complete: $left kind(s) of resource left"; exit 1; fi
echo "teardown verified: no cluster, compute or network resources left in $project"

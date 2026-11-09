#!/usr/bin/env bash
# The Helm chart's checks (CI's deploy job, and locally): helm lint and helm template with the kind and GKE
# values, schema validation of the rendered objects (kubeconform, Kubernetes 1.36), and the properties the
# design fixes: no public exposure, one diagnosis pod per node on GKE, non-root and read-only, required values.
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
chart="$root/deploy/helm/hetren"
gke=(-f "$root/deploy/gke/values.yaml" --set image.tag=v0.4.0-rc.1 --set model.repo=example/hetren)
kind=(-f "$root/deploy/kind/values.yaml")
failures=0

pass() { printf 'ok    %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; failures=$((failures + 1)); }
expect() { if grep -qE -- "$3" <<<"$2"; then pass "$1"; else fail "$1: no match for '$3'"; fi; }
refuse() { if grep -qE -- "$3" <<<"$2"; then fail "$1: unexpected '$3'"; else pass "$1"; fi; }

helm lint --strict "$chart" "${gke[@]}" >/dev/null && pass "helm lint (GKE values)" || fail "helm lint (GKE values)"
helm lint --strict "$chart" "${kind[@]}" >/dev/null && pass "helm lint (kind values)" || fail "helm lint (kind values)"

gke_out=$(helm template hetren "$chart" "${gke[@]}")
kind_out=$(helm template hetren "$chart" "${kind[@]}")

for name in gke kind; do
  out_var="${name}_out"
  if kubeconform -strict -summary -kubernetes-version 1.36.0 <<<"${!out_var}" >/dev/null; then
    pass "kubeconform: $name objects are valid Kubernetes 1.36"
  else
    fail "kubeconform: $name"
  fi
done
kubeconform -strict -kubernetes-version 1.36.0 "$root/deploy/loadtest/job.yaml" >/dev/null \
  && pass "kubeconform: the load-test Job" || fail "kubeconform: the load-test Job"

kinds=$(grep -E '^kind: ' <<<"$gke_out" | sort | tr '\n' ' ')
expect "GKE objects: Deployment, HPA, PDB, Service, ServiceAccount" "$kinds" \
  '^kind: Deployment kind: HorizontalPodAutoscaler kind: PodDisruptionBudget kind: Service kind: ServiceAccount $'
expect "Service is ClusterIP" "$gke_out" '^  type: ClusterIP$'
refuse "no LoadBalancer, NodePort, Ingress or hostNetwork" "$gke_out" 'LoadBalancer|NodePort|kind: Ingress|hostNetwork|hostPort'
expect "GKE: the published image" "$gke_out" 'image: ghcr.io/devanuthakki/hetren-cli:v0.4.0-rc.1'
expect "GKE: fetch-model downloads the GGUF in an init container" "$gke_out" '- fetch-model'
refuse "GKE: no stub, no tokenizer-only fetch" "$gke_out" 'stub-llama-server|--tokenizer-only|--server-url'
expect "GKE: one pod per node (CPU request 6 of an e2-standard-8)" "$gke_out" 'cpu: "6"'
expect "GKE: llama-server on 4 threads" "$(grep -A1 -- '- --threads' <<<"$gke_out")" '"4"'
expect "GKE: the inference node pool" "$gke_out" 'hetren/pool: inference'
expect "GKE: HPA 1-3 on CPU" "$gke_out" 'maxReplicas: 3'
expect "PDB: maxUnavailable 1" "$gke_out" 'maxUnavailable: 1'
expect "readiness on /readyz" "$gke_out" 'path: /readyz'
expect "liveness on /healthz" "$gke_out" 'path: /healthz'
expect "non-root" "$gke_out" 'runAsNonRoot: true'
expect "read-only root filesystem" "$gke_out" 'readOnlyRootFilesystem: true'
expect "no service-account token" "$gke_out" 'automountServiceAccountToken: false'
refuse "nothing privileged" "$gke_out" 'privileged: true|allowPrivilegeEscalation: true'
expect "labels project=hetren, milestone=4" "$gke_out" 'milestone: "4"'
expect "kind: the stub sidecar and --server-url" "$kind_out" 'http://127.0.0.1:8080'
refuse "kind without a repository: no init container" "$kind_out" 'initContainers'

if helm template hetren "$chart" -f "$root/deploy/gke/values.yaml" --set model.repo=x >/dev/null 2>&1; then
  fail "a missing image.tag must fail"
else
  pass "a missing image.tag fails"
fi
if helm template hetren "$chart" -f "$root/deploy/gke/values.yaml" --set image.tag=v1 >/dev/null 2>&1; then
  fail "a missing model.repo must fail"
else
  pass "a missing model.repo fails"
fi

if [ "$failures" -gt 0 ]; then echo "$failures check(s) failed"; exit 1; fi
echo "all chart checks passed"

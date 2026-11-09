#!/usr/bin/env bash
# The kind smoke test (CI's kind job, and locally): install the Helm chart that GKE uses on a kind cluster, with
# the image CI just built and the stub llama-server, and check the deployment's plumbing. Not inference.
#
#   docker build ... -t hetren-cli:ci .   and   docker build deploy/kind/stub-llama-server -t hetren-stub-llama-server:ci
#   deploy/kind/smoke.sh
#
# With $HETREN_MODEL_REPO (after step 7a publishes the tokenizer): the pod becomes ready, the API answers
# /diagnose with the stub's recorded reply, rejects bad input, and a 2-minute k6 Job (concurrency 1 then 2)
# must finish with no errors. Without it: the API must exit 3 naming the missing tokenizer, and Kubernetes
# must restart it (the chart, probes and objects are still checked). KEEP_CLUSTER=1 keeps the cluster.
set -euo pipefail

cluster="${KIND_CLUSTER:-hetren}"
namespace=hetren
node_image="kindest/node:v1.36.4@sha256:099e049362a1526b2db71494e1947aae99bd16290d7c895f2b7ea312e3cbfaed"
root="$(cd "$(dirname "$0")/../.." && pwd)"
failures=0

pass() { printf 'ok    %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; failures=$((failures + 1)); }
expect() { if grep -qE -- "$3" <<<"$2"; then pass "$1"; else fail "$1: no match for '$3' in: $2"; fi; }

cleanup() {
  if [ "${KEEP_CLUSTER:-0}" != 1 ]; then kind delete cluster --name "$cluster" >/dev/null 2>&1 || true; fi
}
trap cleanup EXIT

if ! kind get clusters 2>/dev/null | grep -qx "$cluster"; then
  kind create cluster --name "$cluster" --image "$node_image" --wait 180s
fi
kubectl config use-context "kind-$cluster" >/dev/null
kind load docker-image hetren-cli:ci hetren-stub-llama-server:ci --name "$cluster"

set_repo=()
if [ -n "${HETREN_MODEL_REPO:-}" ]; then set_repo=(--set "model.repo=$HETREN_MODEL_REPO"); fi
if [ -n "${HETREN_MODEL_ENDPOINT:-}" ]; then set_repo+=(--set "model.endpoint=$HETREN_MODEL_ENDPOINT"); fi

helm upgrade --install hetren "$root/deploy/helm/hetren" --namespace "$namespace" --create-namespace \
  -f "$root/deploy/kind/values.yaml" ${set_repo[@]+"${set_repo[@]}"}

objects=$(kubectl -n "$namespace" get deployment,service,hpa,pdb,serviceaccount -o name)
for object in deployment.apps/hetren service/hetren horizontalpodautoscaler.autoscaling/hetren \
              poddisruptionbudget.policy/hetren serviceaccount/hetren; do
  expect "object $object" "$objects" "^$object$"
done
expect "service is ClusterIP only" "$(kubectl -n "$namespace" get service hetren -o jsonpath='{.spec.type}')" '^ClusterIP$'

api() { # api <python statements using get(path) and post(value)>; runs in the API container
  kubectl -n "$namespace" exec deploy/hetren -c hetren -- python -c "
import json, urllib.request, urllib.error
def call(path, data=None):
    request = urllib.request.Request('http://127.0.0.1:8000' + path, data=data, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=120) as r: return r.status, r.read().decode()
    except urllib.error.HTTPError as e: return e.code, e.read().decode()
get = lambda path: call(path)
post = lambda value: call('/diagnose', json.dumps(value).encode())
$1"
}

if [ -n "${HETREN_MODEL_REPO:-}" ]; then
  kubectl -n "$namespace" rollout status deployment/hetren --timeout 300s
  pass "rollout: the pod is ready (the tokenizer fetched and checked, the stub served the variant)"

  compact="$(cat "$root/tests/fixtures/hetren_cli/compact_first_step.json")"
  out=$(api "print(get('/readyz')); print(get('/healthz'))")
  expect "/readyz 200" "$out" "^\(200, '.*\"ready\""
  out=$(api "s, b = post({'compact': json.loads('''$compact''')}); r = json.loads(b); print(s, r['result']['outcome'], r['result']['action']['verb'], r['model']['variant'], r['server']['url'])")
  expect "/diagnose: the stub's recorded reply as a decision" "$out" '^200 decision abstain Q4_K_M http://127.0.0.1:8080$'
  out=$(api "print(post({'record': {'object': 'trace', 'spans': []}})[0], post({'nothing': 1})[0])")
  expect "/diagnose: input rejections are 400" "$out" '^400 400$'
  out=$(api "print(get('/metrics')[1])")
  expect "/metrics: ready and one decision" "$out" 'hetren_diagnoses_total\{outcome="decision"\} 1'

  kubectl -n "$namespace" delete job hetren-loadtest --ignore-not-found >/dev/null
  kubectl -n "$namespace" delete configmap hetren-loadtest --ignore-not-found >/dev/null
  kubectl -n "$namespace" create configmap hetren-loadtest --from-file="$root/deploy/loadtest/k6.js" \
    --from-file=input.json="$root/tests/fixtures/hetren_cli/compact_first_step.json" >/dev/null
  sed -e 's/value: "1,2,4,8,16"/value: "1,2"/' -e 's/value: "300"/value: "60"/' \
      -e '/MAX_ERROR_RATE/{n;s/value: ""/value: "0"/;}' \
      "$root/deploy/loadtest/job.yaml" | kubectl -n "$namespace" apply -f - >/dev/null
  expect "k6 Job: 1,2 x 60 s, no errors allowed" \
    "$(kubectl -n "$namespace" get job hetren-loadtest -o jsonpath='{.spec.template.spec.containers[0].env}')" \
    '"STEPS","value":"1,2".*"STEP_SECONDS","value":"60".*"MAX_ERROR_RATE","value":"0"'
  if kubectl -n "$namespace" wait --for=condition=complete job/hetren-loadtest --timeout 420s; then
    pass "k6 Job: 2 minutes at concurrency 1 then 2, no errors"
  else
    fail "k6 Job did not complete"
  fi
  summary=$(kubectl -n "$namespace" logs job/hetren-loadtest | grep '^HETREN_LOADTEST ' || true)
  echo "$summary"
  expect "k6 summary: no failed requests" "$summary" '"http_req_failed":0[,}]'
else
  echo "HETREN_MODEL_REPO is not set: the tokenizer is published in step 7a, so /diagnose and k6 are skipped"
  for _ in $(seq 1 60); do
    restarts=$(kubectl -n "$namespace" get pods -l app.kubernetes.io/name=hetren \
      -o jsonpath='{.items[0].status.containerStatuses[?(@.name=="hetren")].restartCount}' 2>/dev/null || true)
    [ "${restarts:-0}" -ge 1 ] && break
    sleep 5
  done
  expect "the API exits and Kubernetes restarts it" "${restarts:-0}" '^[1-9][0-9]*$'
  code=$(kubectl -n "$namespace" get pods -l app.kubernetes.io/name=hetren \
    -o jsonpath='{.items[0].status.containerStatuses[?(@.name=="hetren")].lastState.terminated.exitCode}')
  expect "exit status 3 (the CLI's runtime failure)" "$code" '^3$'
  logs=""
  for _ in $(seq 1 15); do  # the container restarts quickly; take whichever run's log is readable
    logs=$( (kubectl -n "$namespace" logs deploy/hetren -c hetren --previous; kubectl -n "$namespace" logs deploy/hetren -c hetren) 2>/dev/null || true)
    grep -q 'tokenizer file missing' <<<"$logs" && break
    sleep 2
  done
  expect "it says the tokenizer is missing" "$logs" 'tokenizer file missing: /models/tokenizer/'
  expect "it listened first (/healthz answers during the load)" "$logs" '"event": "listening"'
fi

pod=$(kubectl -n "$namespace" get pods -l app.kubernetes.io/name=hetren -o json)
expect "pod: non-root, read-only root filesystem, no service-account token" \
  "$(python3 -c "import json,sys; p=json.load(sys.stdin)['items'][0]['spec']; c=[c for c in p['containers'] if c['name']=='hetren'][0]; print(p['securityContext']['runAsNonRoot'], c['securityContext']['readOnlyRootFilesystem'], p['automountServiceAccountToken'])" <<<"$pod")" \
  '^True True False$'

if [ "$failures" -gt 0 ]; then
  kubectl -n "$namespace" get pods -o wide || true
  kubectl -n "$namespace" describe pods | tail -40 || true
  echo "$failures check(s) failed"
  exit 1
fi

echo "kind smoke test passed"

#!/usr/bin/env bash
# Terraform checks (CI's deploy job, and locally): fmt, init without a backend (providers from the committed
# lock files), validate, and tflint with the Google ruleset. Nothing is planned or applied; no credentials.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"

terraform -chdir="$here" fmt -recursive -check -diff
echo "ok    terraform fmt"

for stack in bootstrap gke; do
  terraform -chdir="$here/$stack" init -backend=false -input=false -lockfile=readonly -no-color >/dev/null
  terraform -chdir="$here/$stack" validate -no-color
  echo "ok    terraform validate: $stack"
done

tflint --config "$here/.tflint.hcl" --init >/dev/null
for stack in bootstrap gke; do
  tflint --config "$here/.tflint.hcl" --chdir "$here/$stack"
  echo "ok    tflint: $stack"
done

echo "all terraform checks passed"

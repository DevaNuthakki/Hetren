#!/usr/bin/env bash
# Properties of a built hetren-cli image (CI's docker job, and locally before a commit). No model is needed or
# used: the CLI accepts only the validated GGUF and tokenizer, so inference is checked by the operator's Linux
# check (packages/support_evaluator/linux_agreement.py and cli_check --docker-image), not here.
#
#   docker/hetren-cli/check-image.sh hetren-cli:dev
set -euo pipefail

image="${1:?usage: check-image.sh <image>}"
root="$(cd "$(dirname "$0")/../.." && pwd)"
fixtures="$root/tests/fixtures/hetren_cli"
offline=(docker run --rm --network none --read-only --tmpfs /tmp)
failures=0

pass() { printf 'ok    %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; failures=$((failures + 1)); }
expect() { # expect <description> <command output> <pattern>
  if grep -qE -- "$3" <<<"$2"; then pass "$1"; else fail "$1: no match for '$3' in: $2"; fi
}
refuse() { # refuse <description> <command output> <pattern>
  if grep -qE -- "$3" <<<"$2"; then fail "$1: unexpected '$3' in: $2"; else pass "$1"; fi
}

# Size: under 1 GB without weights, measured as the files in the image (docker image inspect's Size is the
# compressed content size on a containerd image store, the unpacked size on the classic one).
kb=$(docker run --rm --network none --entrypoint sh "$image" -c 'du -skx / 2>/dev/null | cut -f1')
if [ "$kb" -lt 1000000 ]; then pass "size $((kb / 1000)) MB unpacked (< 1000 MB)"; else fail "size $((kb / 1000)) MB unpacked"; fi

arch=$(docker image inspect --format '{{.Os}}/{{.Architecture}}' "$image")
expect "platform $arch" "$arch" '^linux/amd64$'

# Runs as the non-root user.
uid=$("${offline[@]}" --entrypoint id "$image" -u)
expect "user id $uid (not root)" "$uid" '^10001$'

# The CLI works offline and lists the validated files.
out=$("${offline[@]}" "$image" version)
expect "version: validated llama.cpp build" "$out" '620d2225cc436ab0b001e3200e590e3b286ef9ab'
expect "version: Q4_K_M sha256" "$out" 'e3f50ba98ee7e800554dec7ec1c403e7f1d47d4595300e6a6a3e8bf7ffe8763e'
expect "version: Q8_0 sha256" "$out" '496c74a750ef32d0c52dd9644e51b36547dda762c498ac89eece1a24bab3ba29'

help=$("${offline[@]}" "$image" --help)
expect "help: single-recovery scope" "$help" 'single-recovery \(tier 1\)'

# llama-server: the pinned commit and the fixed CPU feature set (system_info is printed at -lv 4 before the model
# load fails on a missing file).
out=$("${offline[@]}" --entrypoint llama-server "$image" --version 2>&1 || true)
expect "llama-server --version: build 11669, commit 620d2225c (as the Mac's validated build)" "$out" 'build 11669, commit 620d2225c\)'
build=$("${offline[@]}" --entrypoint cat "$image" /usr/share/hetren/build-info.json)
expect "build-info: version from git, build 11669" "$build" '"build_number": 11669, "build_commit": "620d2225c", "version_from": "git'
info=$("${offline[@]}" --entrypoint llama-server "$image" -lv 4 -t 2 -m /nonexistent/probe.gguf --host 127.0.0.1 --port 1 2>&1 | grep 'system_info' || true)
for feature in 'AVX = 1' 'AVX2 = 1' 'FMA = 1' 'F16C = 1' 'BMI2 = 1' 'OPENMP = 1'; do
  expect "system_info: $feature" "$info" "$feature"
done
refuse "system_info: no AVX-512" "$info" 'AVX512'
refuse "system_info: no BLAS or Accelerate" "$info" 'BLAS = 1|ACCELERATE = 1'

# Only the CLI's packages: no evaluator, verifier, environment or data.
out=$("${offline[@]}" --entrypoint python "$image" -c "
import importlib.util, os
print(sorted(os.listdir('/app/packages')))
for name in ('packages.support_evaluator', 'packages.verification', 'environments', 'agents', 'torch'):
    print(name, importlib.util.find_spec(name) is not None)")
expect "packages: only the CLI's" "$out" "\['action_gateway', 'action_space', 'contracts', 'core', 'hetren_baselines', 'hetren_cli', 'hetren_evidence', 'hetren_serving'\]"
for name in packages.support_evaluator packages.verification environments agents torch; do
  expect "absent: $name" "$out" "^$name False$"
done

# Input checks, offline (exit 2), and the model check without a model (exit 3).
set +e
out=$("${offline[@]}" -v "$fixtures":/work:ro "$image" diagnose --record /work/sdk_trace.json 2>&1); code=$?
set -e
expect "SDK trace export: exit 2 ($code)" "$code" '^2$'
expect "SDK trace export: how to record a run" "$out" 'trace export.*run_agent and a ToolGateway'

set +e
out=$("${offline[@]}" -v "$fixtures":/work:ro "$image" diagnose --compact /work/compact_first_step.json 2>&1); code=$?
set -e
expect "no model mounted: exit 3 ($code)" "$code" '^3$'
expect "no model mounted: says so" "$out" 'no model file at /models/hetren-qwen3-4b-ckpt0792-q4_k_m.gguf'

set +e
out=$("${offline[@]}" -e HETREN_REQUIRED_CPU_FLAGS="avx2 fma f16c no_such_flag" -v "$fixtures":/work:ro "$image" \
      diagnose --compact /work/compact_first_step.json 2>&1); code=$?
set -e
expect "missing CPU flag: exit 3 ($code)" "$code" '^3$'
expect "missing CPU flag: says which" "$out" 'this CPU lacks no_such_flag'

# The API (hetren serve) listens before the model loads, then exits 3 naming the missing model.
set +e
out=$("${offline[@]}" "$image" serve --host 127.0.0.1 --port 8000 2>&1); code=$?
set -e
expect "serve without a model: exit 3 ($code)" "$code" '^3$'
expect "serve without a model: listened first" "$out" '"event": "listening"'
expect "serve without a model: names the missing file" "$out" 'no model file at /models/hetren-qwen3-4b-ckpt0792-q4_k_m.gguf'

if [ "$failures" -gt 0 ]; then
  echo "$failures check(s) failed"
  exit 1
fi

echo "all image checks passed"

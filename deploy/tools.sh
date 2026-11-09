#!/usr/bin/env bash
# The pinned deployment tools for Linux x86_64 (CI), each checked against its release's sha256:
#   deploy/tools.sh <directory>      then put <directory> on PATH
# kubectl comes with the GitHub runner image. On the Mac use the same versions (deploy/README.md).
set -euo pipefail

dir="${1:?usage: tools.sh <directory>}"
mkdir -p "$dir"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

fetch() { # fetch <url> <sha256> <file>
  curl -fsSL --retry 3 -o "$work/$3" "$1"
  echo "$2  $work/$3" | sha256sum -c --quiet -
}

KIND_VERSION=v0.33.0
HELM_VERSION=v3.22.1
TERRAFORM_VERSION=1.16.7
TFLINT_VERSION=v0.65.0
KUBECONFORM_VERSION=v0.8.0

fetch "https://github.com/kubernetes-sigs/kind/releases/download/$KIND_VERSION/kind-linux-amd64" \
  aee6151561422756b764a4ae28e7f44cda5af5a9eead3cc9985112b1de8d8e0d kind
install -m 755 "$work/kind" "$dir/kind"

fetch "https://get.helm.sh/helm-$HELM_VERSION-linux-amd64.tar.gz" \
  896cf63684a42a723d61c980369d6e588330927deb13676ca0d85006dd6da0ea helm.tar.gz
tar -xzf "$work/helm.tar.gz" -C "$work" linux-amd64/helm
install -m 755 "$work/linux-amd64/helm" "$dir/helm"

fetch "https://releases.hashicorp.com/terraform/$TERRAFORM_VERSION/terraform_${TERRAFORM_VERSION}_linux_amd64.zip" \
  5454efcf7fc87f0c2113111b9a5c7182f0ca1c6f0f23a1e110a50770a8fe473b terraform.zip
unzip -q -o "$work/terraform.zip" terraform -d "$work"
install -m 755 "$work/terraform" "$dir/terraform"

fetch "https://github.com/terraform-linters/tflint/releases/download/$TFLINT_VERSION/tflint_linux_amd64.zip" \
  d4c545ed2e29d6338604b586f34f544f380f70f243aa72f7b484713835eaec61 tflint.zip
unzip -q -o "$work/tflint.zip" tflint -d "$work"
install -m 755 "$work/tflint" "$dir/tflint"

fetch "https://github.com/yannh/kubeconform/releases/download/$KUBECONFORM_VERSION/kubeconform-linux-amd64.tar.gz" \
  9bc2bffbf71f261128533edaf912153948b7ff238f9a531ae6d34466ec287883 kubeconform.tar.gz
tar -xzf "$work/kubeconform.tar.gz" -C "$work" kubeconform
install -m 755 "$work/kubeconform" "$dir/kubeconform"

"$dir/kind" version
"$dir/helm" version --short
"$dir/terraform" version
"$dir/tflint" --version
"$dir/kubeconform" -v

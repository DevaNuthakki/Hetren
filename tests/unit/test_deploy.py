"""Step 6a's deployment code: the billing kill switch's logic, the kind stub, and the properties the design fixes
in the Terraform code, the Helm chart, the load test and CI. Files only (no cloud, cluster or Helm needed;
CI's deploy and kind jobs run the tools themselves).
"""

from __future__ import annotations

import base64
import importlib.util
import json
from pathlib import Path
import re
import threading
import urllib.error
import urllib.request

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY = REPO_ROOT / "deploy"
TERRAFORM = DEPLOY / "terraform"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _text(*parts: str) -> str:
    return (DEPLOY.joinpath(*parts)).read_text(encoding="utf-8")


# --- the kill switch -------------------------------------------------------------------------------------------

@pytest.fixture
def kill_switch(monkeypatch):
    monkeypatch.setenv("PROJECT_ID", "hetren-test")
    monkeypatch.delenv("DRY_RUN", raising=False)
    return _load("hetren_kill_switch", TERRAFORM / "bootstrap/killswitch/main.py")


def _event(cost: float, budget: float = 25.0) -> dict:
    payload = {"costAmount": cost, "budgetAmount": budget, "alertThresholdExceeded": cost / budget,
               "currencyCode": "USD", "budgetDisplayName": "hetren"}
    return {"data": {"message": {"data": base64.b64encode(json.dumps(payload).encode()).decode()}}}


class FakeBilling:
    def __init__(self, enabled: bool = True):
        self.enabled, self.calls = enabled, []

    def __call__(self, method, url, token=None, body=None):
        self.calls.append((method, url, body))

        if "metadata.google.internal" in url:
            return {"access_token": "token"}

        if method == "PUT":
            self.enabled = False
            return {}

        return {"billingEnabled": self.enabled}


def test_below_the_budget_nothing_happens(kill_switch):
    billing = FakeBilling()
    assert kill_switch.stop_billing(_event(22.5), request=billing) == "below the budget"
    assert billing.calls == []


def test_at_the_budget_billing_is_disabled_on_this_project_only(kill_switch):
    billing = FakeBilling()
    assert kill_switch.stop_billing(_event(25.0), request=billing) == "billing disabled"
    put = [c for c in billing.calls if c[0] == "PUT"]
    assert put == [("PUT", "https://cloudbilling.googleapis.com/v1/projects/hetren-test/billingInfo",
                    {"billingAccountName": ""})]
    assert kill_switch.stop_billing(_event(31.0), request=billing) == "billing already disabled"


def test_dry_run_changes_nothing(kill_switch, monkeypatch):
    monkeypatch.setenv("DRY_RUN", "1")
    billing = FakeBilling()
    assert kill_switch.stop_billing(_event(40.0), request=billing) == "dry run" and billing.calls == []


def test_the_function_is_pinned_and_wired_to_the_budget():
    assert _text("terraform/bootstrap/killswitch/requirements.txt") == "functions-framework==3.10.2\n"
    main = _text("terraform/bootstrap/main.tf")
    assert re.search(r'entry_point\s+= "stop_billing"', main) and re.search(r'runtime\s+= "python313"', main)
    assert "pubsub_topic          = google_pubsub_topic.budget.id" in main
    assert "pubsub_topic                     = google_pubsub_topic.budget.id" in main
    assert 'role    = "roles/billing.projectManager"' in main
    assert "for_each = [0.25, 0.5, 0.9, 1.0]" in main
    variables = _text("terraform/bootstrap/variables.tf")
    assert re.search(r'variable "budget_usd" \{.*?default     = 25\n.*?var.budget_usd <= 25', variables, re.DOTALL)
    assert re.search(r'variable "kill_switch_dry_run" \{.*?default     = false', variables, re.DOTALL)


# --- Terraform -------------------------------------------------------------------------------------------------

def test_the_node_pool_fits_the_free_trials_8_vcpus():
    variables = _text("terraform/gke/variables.tf")
    assert re.search(r'variable "max_nodes" \{.*?default     = 2\n.*?var.max_nodes <= 2', variables, re.DOTALL)
    assert re.search(r'variable "max_vcpus" \{.*?default     = 8\n', variables, re.DOTALL)
    assert 'default     = "e2-standard-4"' in variables and 'default     = "us-central1-a"' in variables
    cluster = _text("terraform/gke/cluster.tf")
    assert "max_node_count = var.max_nodes" in cluster and "location = var.zone" in cluster
    assert "var.max_nodes * local.node_vcpus <= var.max_vcpus" in cluster and "max_surge       = 0" in cluster
    tests = _text("terraform/gke/tests/limits.tftest.hcl")
    assert "expect_failures = [google_container_node_pool.inference]" in tests and "max_nodes = 3" in tests


def test_the_budget_measures_gross_usage_and_terraform_test_checks_it():
    main = _text("terraform/bootstrap/main.tf")
    assert 'credit_types_treatment = "EXCLUDE_ALL_CREDITS"' in main
    budget_test = _text("terraform/bootstrap/tests/budget.tftest.hcl")
    assert 'credit_types_treatment == "EXCLUDE_ALL_CREDITS"' in budget_test and 'mock_provider "google"' in budget_test
    assert 'terraform -chdir="$here/$stack" test' in _text("terraform/check.sh")
    assert "service_account = google_service_account.kill_switch_build.id" in main


def test_the_cluster_has_private_nodes_behind_nat_and_no_load_balancer_addon():
    cluster, network = _text("terraform/gke/cluster.tf"), _text("terraform/gke/network.tf")
    assert "enable_private_nodes    = true" in cluster
    assert "master_authorized_networks_config" in cluster and "/32" in _text("terraform/gke/variables.tf")
    assert re.search(r"http_load_balancing \{\s+disabled = true", cluster)
    assert "deletion_protection      = false" in cluster
    assert 'resource "google_compute_router_nat"' in network and "auto_create_subnetworks = false" in network
    assert "access_config" not in cluster  # no external node IPs


def test_every_stack_labels_its_resources_and_pins_the_provider():
    for stack in ("bootstrap", "gke"):
        versions = _text("terraform", stack, "versions.tf")
        assert 'version = "8.8.1"' in versions
        lock = _text("terraform", stack, ".terraform.lock.hcl")
        assert 'provider "registry.terraform.io/hashicorp/google"' in lock and 'version     = "8.8.1"' in lock

    assert 'default_labels = { project = "hetren", milestone = "4" }' in _text("terraform/gke/versions.tf")
    assert 'labels = { project = "hetren", milestone = "4" }' in _text("terraform/bootstrap/main.tf")
    assert 'backend "gcs"' in _text("terraform/gke/versions.tf")
    assert 'backend "gcs"' not in _text("terraform/bootstrap/versions.tf")  # it creates the state bucket
    example = _text("terraform/bootstrap/backend.tf.example")  # migrated into the bucket after the first apply
    assert 'backend "gcs"' in example and 'prefix = "bootstrap"' in example and "-migrate-state" in example
    assert "deploy/terraform/bootstrap/backend.tf\n" in (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    readme = _text("README.md")
    assert "terraform init -migrate-state -backend-config" in readme and "master_authorized_cidr" in readme


def test_the_quota_check_needs_room_for_the_capped_pool():
    script = _text("terraform/check-quota.sh")
    for need in ('"CPUS", 8', '"SSD_TOTAL_GB", 100', '"CPUS_ALL_REGIONS", 8'):
        assert need in script


# --- the chart, the stub and the load test ---------------------------------------------------------------------

def test_chart_defaults_are_the_gke_design():
    values = _text("helm/hetren/values.yaml")
    for line in ("threads: 2", "maxQueue: 8", 'cpu: 2500m', "memory: 7Gi", "maxReplicas: 2", "maxUnavailable: 1",
                 "repository: ghcr.io/devanuthakki/hetren-cli", "variant: Q4_K_M", "  enabled: false"):
        assert line in values, line

    assert "  revision: 3e875e4e8719acef839dc18e220a3ae498a1975b\n" in values  # the 7a release commit
    assert "--set model.repo=Harsha1412/hetren-qwen3-4b-diagnosis" in _text("README.md")

    templates = "".join(p.read_text(encoding="utf-8") for p in (DEPLOY / "helm/hetren/templates").iterdir())
    assert "type: ClusterIP" in templates and "LoadBalancer" not in templates and "NodePort" not in templates


def test_the_stub_requires_amendment_2_decoding_and_serves_the_q4_k_m_file():
    stub = _load("hetren_stub_llama_server", DEPLOY / "kind/stub-llama-server/stub_llama_server.py")
    stub.SECONDS = 0
    server = stub.ThreadingHTTPServer(("127.0.0.1", 0), stub.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}"

    def post(body):
        request = urllib.request.Request(url + "/completion", json.dumps(body).encode(), method="POST",
                                         headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read())

    try:
        from packages.hetren_serving.llama_server import DecodingSettings

        status, body = post(DecodingSettings(cache_prompt=True).payload([1, 2, 3]))
        assert status == 200 and body["tokens"] == stub.REPLY and body["stop_type"] == "eos"
        assert body["tokens"][-1] == 151645 and len(body["completion_probabilities"]) == len(stub.REPLY)
        assert post(DecodingSettings(cache_prompt=False).payload([1]))[0] == 400
        with urllib.request.urlopen(url + "/props", timeout=10) as response:
            assert json.loads(response.read())["model_path"].endswith("hetren-qwen3-4b-ckpt0792-q4_k_m.gguf")
    finally:
        server.shutdown()


def test_the_load_test_steps_and_image():
    job = _text("loadtest/job.yaml")
    assert 'value: "1,2,4,8,16"' in job and 'value: "300"' in job
    assert re.search(r"image: grafana/k6:1\.8\.2@sha256:[0-9a-f]{64}", job)
    script = _text("loadtest/k6.js")
    assert "timeout: '600s'" in script and "/diagnose" in script and "HETREN_LOADTEST" in script


# --- CI ----------------------------------------------------------------------------------------------------------

def _job(name: str) -> str:
    workflow = (REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    match = re.search(rf"^  {name}:\n(.*?)(?=^  [a-z_-]+:\n|\Z)", workflow.split("\njobs:\n", 1)[1],
                      re.MULTILINE | re.DOTALL)
    assert match, name
    return match.group(1)


def test_ci_checks_the_chart_and_terraform_without_credentials_or_apply():
    job = _job("deploy")
    assert "    permissions:\n      contents: read\n\n" in job and not re.search(r"^    if:", job, re.MULTILINE)
    assert "deploy/helm/check-chart.sh" in job and "deploy/terraform/check.sh" in job
    for forbidden in ("terraform apply", "terraform plan", "google-github-actions", "packages: write", "id-token"):
        assert forbidden not in job, forbidden

    check = _text("terraform/check.sh")
    assert "init -backend=false" in check and "-lockfile=readonly" in check and "apply" not in check


def test_ci_installs_the_same_chart_on_kind_every_push():
    job = _job("kind")
    assert "    permissions:\n      contents: read\n\n" in job and not re.search(r"^    if:", job, re.MULTILINE)
    assert "cache-from: type=gha,scope=hetren-cli" in job and "cache-to" not in job
    assert "HETREN_MODEL_REPO: ${{ vars.HETREN_MODEL_REPO }}" in job and "deploy/kind/smoke.sh" in job
    smoke = _text("kind/smoke.sh")
    assert '"$root/deploy/helm/hetren"' in smoke and "kindest/node:v1.36.4@sha256:" in smoke


def test_the_tools_are_pinned_with_checksums():
    tools = _text("tools.sh")
    for version in ("KIND_VERSION=v0.33.0", "HELM_VERSION=v3.22.1", "TERRAFORM_VERSION=1.16.7",
                    "TFLINT_VERSION=v0.65.0", "KUBECONFORM_VERSION=v0.8.0"):
        assert version in tools
    assert len(re.findall(r"^  [0-9a-f]{64} ", tools, re.MULTILINE)) == 5


def test_the_load_test_sends_distinct_training_inputs_and_waits_out_rejections():
    from packages.hetren_cli.inputs import check_compact

    data = json.loads(_text("loadtest/inputs.json"))
    texts = [json.dumps(c, sort_keys=True) for c in data["inputs"]]
    assert len(texts) == 16 and len(set(texts)) == 16 and len(data["cases"]) == 16
    for compact in data["inputs"]:
        check_compact(compact)  # each is an input the API accepts
    assert sorted(c["kind"] for c in data["cases"]) == ["decide"] * 5 + ["probe"] * 6 + ["recover"] * 5

    def split(version: str, name: str) -> set[str]:
        return set((REPO_ROOT / f"docs/milestone-2/{version}/{name}.txt").read_text(encoding="utf-8").split())

    cases = {c["case_id"] for c in data["cases"]}
    for version in ("splits-v1", "splits-v2"):  # a training case in both datasets, never a validation or test case
        assert cases <= split(version, "train")
        for name in ("validation", "test_in_distribution", "test_held_out"):
            assert not cases & split(version, name), (version, name)

    script = _text("loadtest/k6.js")
    assert "open('/loadtest/inputs.json')" in script and "exec.scenario.iterationInTest % bodies.length" in script
    assert "response.status === 503" in script and "sleep(retrySeconds(response.headers['Retry-After']))" in script
    assert "rejected:" in script
    for consumer in ("gke/loadtest.py", "kind/smoke.sh", "loadtest/job.yaml"):
        assert "inputs.json" in _text(consumer) and "input.json=" not in _text(consumer), consumer

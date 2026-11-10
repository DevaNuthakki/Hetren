"""Step 6b's operator scripts, with fake API responses and samples: the price check, the live budget check, the
load test's autoscaling record and the teardown check. Nothing reaches Google Cloud or a cluster."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prices = _load("hetren_price_check", "deploy/terraform/price_check.py")
budget = _load("hetren_check_budget", "deploy/terraform/check_budget.py")
loadtest = _load("hetren_loadtest", "deploy/gke/loadtest.py")


def _sku(description: str, price: float, unit: str, regions=("us-central1",), free_first=False, sku_id="X"):
    units, nanos = int(price), round((price - int(price)) * 1e9)
    rates = ([{"unitPrice": {"units": "0", "nanos": 0}}] if free_first else []) + \
        [{"unitPrice": {"units": str(units), "nanos": nanos}}]
    return {"description": description, "skuId": sku_id, "serviceRegions": list(regions),
            "category": {"usageType": "OnDemand"},
            "pricingInfo": [{"pricingExpression": {"usageUnit": unit, "tieredRates": rates}}]}


CATALOG = {
    "Compute Engine": [
        _sku("E2 Instance Core running in Americas", 0.021811, "h"),
        _sku("E2 Instance Ram running in Americas", 0.002923, "GiBy.h"),
        _sku("E2 Instance Core running in Paris", 0.03, "h", regions=("europe-west9",)),
        _sku("Balanced PD Capacity", 0.1, "GiBy.mo"),
        _sku("External IP Charge on a Standard VM", 0.004, "h", regions=("global",), free_first=True),
    ],
    # As the catalog names them on 2026-11-10 (cloud.google.com/nat/pricing): the Networking service.
    "Networking": [
        _sku("Networking Cloud NAT gateway uptime", 0.0014, "h"),
        _sku("Networking Cloud NAT data processing", 0.045, "GiBy", regions=("global",)),
        _sku("Networking Cloud NAT IP usage", 0.005, "h", free_first=True),
        _sku("Networking Private NAT data processing", 0.9, "GiBy", regions=("global",)),
        _sku("Networking Private NAT gateway uptime", 0.9, "h"),
    ],
    "Kubernetes Engine": [_sku("Zonal Kubernetes Clusters", 0.1, "h", regions=("global",))],
}


def test_the_price_check_finds_each_sku_in_the_region_and_prices_the_session():
    found = prices.find(CATALOG, "us-central1")
    assert all("missing" not in v for v in found.values()), found
    assert found["e2_core"]["price"] == pytest.approx(0.021811)  # not the Paris SKU
    assert found["nat_ip"]["price"] == pytest.approx(0.005)  # the first paid tier, not the free one
    assert found["nat_ip"]["description"] == "Networking Cloud NAT IP usage"  # not a VM's external IP
    assert found["nat_data"]["price"] == pytest.approx(0.045) and found["nat_uptime"]["price"] == pytest.approx(0.0014)
    result = prices.estimate(found)
    assert result["e2_standard_4_per_hour"] == pytest.approx(4 * 0.021811 + 16 * 0.002923)
    expected = result["expected"]
    assert expected["parts"]["GKE management"] == 0.0 and expected["usd"] < result["ceiling"]["usd"] < 3
    assert prices.estimate(found, free_tier_cluster=False)["ceiling"]["parts"]["GKE management"] == pytest.approx(0.4)


def test_the_price_check_reports_a_sku_it_cannot_find():
    catalog = {"Compute Engine": CATALOG["Compute Engine"][:2], "Kubernetes Engine": []}
    found = prices.find(catalog, "us-central1")
    assert "missing" in found["gke_zonal"] and "missing" in found["balanced_pd"]
    assert "missing" in found["nat_data"]  # the Networking service absent: never the Private NAT price
    assert "Networking or Compute Engine" in found["nat_data"]["missing"]


def test_the_catalog_is_read_page_by_page():
    pages = {"services": [{"services": [{"displayName": "Compute Engine", "name": "services/CE"},
                                        {"displayName": "Networking", "name": "services/NET"}], "nextPageToken": "2"},
                          {"services": [{"displayName": "Kubernetes Engine", "name": "services/GKE"}]}]}
    calls = []

    def get(url):
        calls.append(url)
        if "/services?" in url:
            return pages["services"].pop(0)
        return {"skus": CATALOG[{"CE": "Compute Engine", "NET": "Networking", "GKE": "Kubernetes Engine"}[url.split("/")[-2]]]}

    catalog = prices.catalog("p", get=get)
    assert set(catalog) == {"Compute Engine", "Networking", "Kubernetes Engine"} and len(catalog["Networking"]) == 5
    assert all("missing" not in v for v in prices.find(catalog, "us-central1").values())
    assert any("pageToken=2" in url for url in calls)


GOOD_BUDGET = {
    "displayName": "hetren-hetren-m4-dhn12",
    "budgetFilter": {"projects": ["projects/123"], "calendarPeriod": "MONTH", "creditTypesTreatment": "EXCLUDE_ALL_CREDITS"},
    "amount": {"specifiedAmount": {"currencyCode": "USD", "units": "25"}},
    "thresholdRules": [{"thresholdPercent": p, "spendBasis": "CURRENT_SPEND"} for p in (0.25, 0.5, 0.9, 1.0)],
    "notificationsRule": {"pubsubTopic": "projects/hetren-m4-dhn12/topics/hetren-budget", "schemaVersion": "1.0"},
}


def test_the_live_budget_check_accepts_the_designed_budget():
    assert budget.problems([GOOD_BUDGET, {"displayName": "other"}], "hetren-m4-dhn12", "123") == []


def test_a_budget_that_counts_credits_is_refused():
    included = {**GOOD_BUDGET, "budgetFilter": {**GOOD_BUDGET["budgetFilter"]}}
    del included["budgetFilter"]["creditTypesTreatment"]  # the API's default: INCLUDE_ALL_CREDITS
    found = budget.problems([included], "hetren-m4-dhn12", "123")
    assert len(found) == 1 and "credits would hide the spend" in found[0]
    wrong = {**GOOD_BUDGET, "amount": {"specifiedAmount": {"currencyCode": "USD", "units": "250"}}}
    assert "not 25 USD" in budget.problems([wrong], "hetren-m4-dhn12", "123")[0]
    assert budget.problems([], "hetren-m4-dhn12", "123") == ["expected one budget named hetren-hetren-m4-dhn12, found 0"]


def _samples():
    rows, t = [], 1000.0
    for nodes, ready_nodes, desired, ready in [(1, 1, 1, 1)] * 4 + [(1, 1, 2, 1)] * 2 + [(2, 1, 2, 1)] * 4 + \
            [(2, 2, 2, 1)] * 6 + [(2, 2, 2, 2)] * 8:
        rows.append({"t": t, "nodes": nodes, "ready_nodes": ready_nodes, "hpa_desired": desired, "hpa_current": desired,
                     "ready_replicas": ready, "cpu_percent": 70})
        t += 15
    return rows


def test_node_hours_and_the_scale_up_timeline():
    samples = _samples()
    assert loadtest.node_hours(samples) == pytest.approx((5 * 15 + 0.5 * 15 * 1 + 17 * 15 * 2 + 0.5 * 15) / 3600, rel=0.05)
    timeline = loadtest.scaling(samples)
    assert timeline["hpa_wanted_2_at_s"] == 60.0 and timeline["second_node_ready_at_s"] == 150.0
    assert timeline["second_pod_ready_at_s"] == 240.0 and timeline["scale_up_seconds"] == 180.0
    assert timeline["max_nodes"] == 2 and timeline["max_ready_replicas"] == 2


def test_the_cost_per_1000_diagnoses_is_the_node_cost_only():
    k6 = {"steps_summary": {"c01": {"diagnoses": 40}, "c02": {"diagnoses": 60}}}
    result = loadtest.summarize(k6, _samples(), 0.134)
    assert result["diagnoses"] == 100
    assert result["node_cost_per_1000_diagnoses_usd"] == pytest.approx(round(1000 * result["node_hours"] * 0.134 / 100, 2))
    assert loadtest.summarize(k6, _samples(), None)["node_cost_per_1000_diagnoses_usd"] is None


def test_the_job_is_rendered_with_the_steps():
    job = loadtest.render_job("1,2,4,8,16", 300)
    assert 'value: "1,2,4,8,16"' in job and 'value: "300"' in job
    short = loadtest.render_job("1,2", 60)
    assert 'value: "1,2"' in short and 'value: "60"' in short and "1,2,4,8,16" not in short


def test_a_scale_up_before_the_test_gives_null_sampled_times_not_zero():
    # Session 1: the first diagnosis (phase 6) had already scaled the deployment to 2 when the load test began.
    already = [dict(row, nodes=2, ready_nodes=2, hpa_desired=2, hpa_current=2, ready_replicas=2) for row in _samples()]
    timeline = loadtest.scaling(already)
    assert timeline["scaled_before_start"] is True
    assert [timeline[k] for k in ("hpa_wanted_2_at_s", "second_node_ready_at_s", "second_pod_ready_at_s",
                                  "scale_up_seconds")] == [None] * 4
    assert timeline["max_nodes"] == 2 and timeline["max_ready_replicas"] == 2
    assert loadtest.scaling(_samples())["scaled_before_start"] is False


def _event(reason, kind, name, at, message=""):
    return {"reason": reason, "involvedObject": {"kind": kind, "name": name}, "firstTimestamp": at,
            "message": message, "metadata": {"creationTimestamp": at}}


def test_the_scale_up_timeline_comes_from_the_events_and_objects():
    # Session 1's real times (artifacts/milestone-4/loadtest-gke-1/events.json, gke-1/pods.yaml, gke-1/nodes.yaml).
    events = [
        _event("SuccessfulRescale", "HorizontalPodAutoscaler", "hetren", "2026-11-10T04:50:37Z",
               "New size: 2; reason: cpu resource utilization (percentage of request) above target"),
        _event("SuccessfulRescale", "HorizontalPodAutoscaler", "other", "2026-11-10T04:40:00Z", "New size: 2"),
        _event("TriggeredScaleUp", "Pod", "hetren-b", "2026-11-10T04:50:39Z"),
        _event("NodeReady", "Node", "node-a", "2026-11-10T04:42:42Z"),
        _event("NodeReady", "Node", "node-b", "2026-11-10T04:51:21Z"),
    ]
    nodes = [{"metadata": {"name": "node-b", "creationTimestamp": "2026-11-10T04:51:18Z"}, "status": {}},
             {"metadata": {"name": "node-a", "creationTimestamp": "2026-11-10T04:42:38Z"}, "status": {}}]
    pods = [
        {"metadata": {"name": "hetren-a", "creationTimestamp": "2026-11-10T04:47:21Z"}, "status": {}},
        {"metadata": {"name": "hetren-b", "creationTimestamp": "2026-11-10T04:50:37Z"}, "status": {
            "conditions": [{"type": "PodScheduled", "status": "True", "lastTransitionTime": "2026-11-10T04:51:22Z"},
                           {"type": "Ready", "status": "True", "lastTransitionTime": "2026-11-10T04:53:28Z"}],
            "initContainerStatuses": [{"name": "fetch-model", "state": {"terminated": {
                "startedAt": "2026-11-10T04:52:00Z", "finishedAt": "2026-11-10T04:53:01Z"}}}]}},
    ]
    result = loadtest.timeline(events, pods, nodes, "hetren")
    assert result["second_node"] == "node-b" and result["second_pod"] == "hetren-b"
    assert result["utc"]["hpa_rescaled_to_2"] == "2026-11-10T04:50:37Z"
    assert result["seconds_after_rescale"] == {
        "hpa_rescaled_to_2": 0.0, "second_pod_created": 0.0, "scale_up_triggered": 2.0, "second_node_created": 41.0,
        "second_node_ready": 44.0, "second_pod_scheduled": 45.0, "fetch_model_started": 83.0,
        "fetch_model_finished": 144.0, "second_pod_ready": 171.0}


def test_the_timeline_without_a_scale_up_is_empty_not_an_error():
    pods = [{"metadata": {"name": "hetren-a", "creationTimestamp": "2026-11-10T04:47:21Z"}, "status": {}}]
    result = loadtest.timeline([], pods, [], "hetren")
    assert result["second_pod"] is None and set(result["seconds_after_rescale"].values()) == {None}


def _fake_gcloud(tmp_path, assets: str):
    """A gcloud that lists nothing, except the labelled assets, which it prints as the real one does: tab-separated."""
    (tmp_path / "assets.txt").write_text(assets, encoding="utf-8")
    script = tmp_path / "gcloud"
    script.write_text('#!/usr/bin/env bash\nif [ "$1" = asset ]; then cat "$(dirname "$0")/assets.txt"; fi\n',
                      encoding="utf-8")
    script.chmod(0o755)
    return {**os.environ, "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}"}


# Session 1's phase 8.1 output, line for line. gcloud's value() format separates the fields with a tab (the terminal
# shows it as spaces).
BOOTSTRAP_ASSETS = "".join(f"{line}\n" for line in [
    "run.googleapis.com/Revision\t//run.googleapis.com/projects/hetren-m4-dhn12/locations/us-central1/revisions/hetren-kill-switch-00002-sit",
    "run.googleapis.com/Revision\t//run.googleapis.com/projects/hetren-m4-dhn12/locations/us-central1/revisions/hetren-kill-switch-00001-tah",
    "run.googleapis.com/Service\t//run.googleapis.com/projects/hetren-m4-dhn12/locations/us-central1/services/hetren-kill-switch",
    "pubsub.googleapis.com/Topic\t//pubsub.googleapis.com/projects/hetren-m4-dhn12/topics/hetren-budget",
    "storage.googleapis.com/Bucket\t//storage.googleapis.com/hetren-m4-dhn12-tfstate",
    "storage.googleapis.com/Bucket\t//storage.googleapis.com/hetren-m4-dhn12-functions",
    "cloudresourcemanager.googleapis.com/Project\t//cloudresourcemanager.googleapis.com/projects/hetren-m4-dhn12",
    "cloudfunctions.googleapis.com/Function\t//cloudfunctions.googleapis.com/projects/hetren-m4-dhn12/locations/us-central1/functions/hetren-kill-switch",
])


def _teardown(env):
    return subprocess.run(["bash", str(REPO_ROOT / "deploy/terraform/verify-teardown.sh"), "hetren-m4-dhn12"],
                          capture_output=True, text=True, env=env)


def test_after_the_gke_destroy_the_bootstrap_resources_are_kept_not_left(tmp_path):
    # Session 1, phase 8.1: the bootstrap stack's resources were reported as left, since the type was followed by a
    # tab, not the space the pattern expected.
    run = _teardown(_fake_gcloud(tmp_path, BOOTSTRAP_ASSETS))
    assert run.returncode == 0, run.stdout + run.stderr
    assert "kept  the bootstrap stack's resources (removed in phase 8.2):" in run.stdout
    assert run.stdout.count("        run.googleapis.com/Revision\t") == 2 and "functions/hetren-kill-switch" in run.stdout
    assert "LEFT" not in run.stdout
    assert "teardown verified: no cluster, compute or network resources left in hetren-m4-dhn12" in run.stdout


def test_a_labelled_resource_outside_the_bootstrap_stack_is_still_left(tmp_path):
    disk = "compute.googleapis.com/Disk\t//compute.googleapis.com/projects/hetren-m4-dhn12/zones/us-central1-a/disks/pvc-1\n"
    run = _teardown(_fake_gcloud(tmp_path, BOOTSTRAP_ASSETS + disk))
    assert run.returncode == 1
    assert "LEFT  labelled resources:" in run.stdout and "disks/pvc-1" in run.stdout
    assert "teardown NOT complete: 1 kind(s) of resource left" in run.stdout

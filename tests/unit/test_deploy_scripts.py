"""Step 6b's operator scripts, with fake API responses and samples: the price check, the live budget check and the
load test's autoscaling record. Nothing reaches Google Cloud or a cluster."""

from __future__ import annotations

import importlib.util
from pathlib import Path

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

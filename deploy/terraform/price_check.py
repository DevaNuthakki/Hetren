"""Step 6b's price check (operator, after the bootstrap stack, before the gke stack): the list prices of every
billable SKU the cluster uses, read from the Cloud Billing Catalog API, and the cost estimate computed from them.
Read-only. Standard library and gcloud (for the access token) only.

    python3 deploy/terraform/price_check.py --project <project_id> [--region us-central1] [--out prices.json]

Prices are list prices in USD, before credits; the Free Trial's credits pay them. The estimate's assumptions are
stated in its output: the expected session (one node for the whole cluster lifetime, a second node during the load
test) and the ceiling (both nodes for the whole session).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import urllib.parse
import urllib.request


CATALOG = "https://cloudbilling.googleapis.com/v1"
MACHINE = {"name": "e2-standard-4", "vcpus": 4, "memory_gib": 16}
DISK_GIB = 50
# (key, the services to search, description pattern (case-insensitive), unit the estimate needs). Cloud NAT's
# SKUs are in the Networking service ("Networking Cloud NAT gateway uptime", "... data processing", "... IP usage",
# cloud.google.com/nat/pricing); Private NAT's are excluded, since the cluster uses Public NAT.
SKUS = [
    ("e2_core", ("Compute Engine",), r"^E2 Instance Core running in ", "h"),
    ("e2_ram", ("Compute Engine",), r"^E2 Instance Ram running in ", "GiBy.h"),
    ("balanced_pd", ("Compute Engine",), r"^Balanced PD Capacity( in |$)", "GiBy.mo"),
    ("nat_uptime", ("Networking", "Compute Engine"), r"^(Networking )?Cloud NAT gateway uptime", "h"),
    ("nat_data", ("Networking", "Compute Engine"), r"^(Networking )?Cloud NAT data processing", "GiBy"),
    ("nat_ip", ("Networking", "Compute Engine"), r"^(Networking )?Cloud NAT IP usage", "h"),
    ("gke_zonal", ("Kubernetes Engine",), r"^(Zonal Kubernetes Clusters|Cluster Management Fee)", "h"),
]
SESSIONS = {
    "expected": {"cluster_hours": 2.0, "node_hours": 2.75, "nat_gib": 5.5,
                 "assumes": "cluster for 2 h; one node throughout, a second for about 45 min of load test; "
                            "two model downloads (2.33 GiB each) and the images through NAT"},
    "ceiling": {"cluster_hours": 4.0, "node_hours": 8.0, "nat_gib": 15.0,
                "assumes": "cluster for the whole 4-hour session with both nodes, and repeated downloads"},
}
HOURS_PER_MONTH = 730


def money(value: dict) -> float:
    return int(value.get("units") or 0) + int(value.get("nanos") or 0) / 1e9


def unit_price(sku: dict) -> tuple[float, str]:
    """(the price per unit at the first paid tier, the usage unit), from the SKU's current pricing."""
    expression = sku["pricingInfo"][0]["pricingExpression"]
    rates = [money(rate["unitPrice"]) for rate in expression.get("tieredRates", [])]
    paid = [rate for rate in rates if rate > 0]
    return (paid[0] if paid else 0.0), expression.get("usageUnit", "")


def find(skus_by_service: dict[str, list[dict]], region: str) -> dict[str, dict]:
    """Each needed SKU: its description, id, price and unit, or a 'missing' entry."""
    found = {}

    for key, services, pattern, unit in SKUS:
        service = " or ".join(services)
        matches = [s for name in services for s in skus_by_service.get(name, [])
                   if re.search(pattern, s.get("description", ""), re.IGNORECASE)
                   and (region in s.get("serviceRegions", []) or "global" in s.get("serviceRegions", []))
                   and s.get("category", {}).get("usageType", "OnDemand") == "OnDemand"]
        priced = [(s, *unit_price(s)) for s in matches]
        priced = [m for m in priced if m[2] == unit] or priced  # prefer the unit the estimate is written in

        if not priced:
            found[key] = {"missing": f"no {service} SKU matching {pattern!r} in {region}"}
            continue

        sku, price, usage_unit = max(priced, key=lambda m: m[1])  # the dearest match, to stay conservative
        found[key] = {"description": sku["description"], "sku": sku.get("skuId"), "price": price,
                      "unit": usage_unit, "matches": len(priced)}

    return found


def estimate(prices: dict[str, dict], free_tier_cluster: bool = True) -> dict[str, dict]:
    def price(key: str) -> float:
        return prices[key].get("price", 0.0)

    node_hour = MACHINE["vcpus"] * price("e2_core") + MACHINE["memory_gib"] * price("e2_ram")
    disk_hour = DISK_GIB * price("balanced_pd") / HOURS_PER_MONTH
    result = {"e2_standard_4_per_hour": round(node_hour, 6)}

    for name, s in SESSIONS.items():
        parts = {
            "nodes": s["node_hours"] * node_hour,
            "boot disks": s["node_hours"] * disk_hour,
            "Cloud NAT uptime and IP": s["node_hours"] * price("nat_uptime") + s["cluster_hours"] * price("nat_ip"),
            "Cloud NAT data": s["nat_gib"] * price("nat_data"),
            "GKE management": 0.0 if free_tier_cluster else s["cluster_hours"] * price("gke_zonal"),
        }
        result[name] = {"assumes": s["assumes"], "usd": round(sum(parts.values()), 2),
                        "parts": {k: round(v, 4) for k, v in parts.items()}}

    return result


def _get(url: str, token: str, project: str) -> dict:
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "x-goog-user-project": project})

    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def _all(url: str, key: str, get) -> list[dict]:
    items, token = [], ""

    while True:
        page = get(url + ("&" if "?" in url else "?") + urllib.parse.urlencode({"pageSize": 5000, "pageToken": token}))
        items += page.get(key, [])
        token = page.get("nextPageToken", "")

        if not token:
            return items


def catalog(project: str, get=None) -> dict[str, list[dict]]:
    if get is None:
        token = subprocess.run(["gcloud", "auth", "print-access-token"], check=True, capture_output=True,
                               text=True).stdout.strip()
        get = lambda url: _get(url, token, project)  # noqa: E731

    services = {s["displayName"]: s["name"] for s in _all(f"{CATALOG}/services", "services", get)}
    unavailable = [key for key, names, _, _ in SKUS if not any(name in services for name in names)]

    if unavailable:
        raise RuntimeError(f"the catalog lists none of the services for {unavailable}")

    wanted = sorted({name for _, names, _, _ in SKUS for name in names if name in services})
    return {name: _all(f"{CATALOG}/{services[name]}/skus?currencyCode=USD", "skus", get) for name in wanted}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--project", required=True, help="the project whose quota the Catalog API calls use")
    parser.add_argument("--region", default="us-central1")
    parser.add_argument("--out", type=Path, help="also write the prices and the estimate here (JSON)")
    parser.add_argument("--no-free-tier", action="store_true",
                        help="count the GKE management fee (another zonal cluster already uses the free tier)")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    prices = find(catalog(args.project), args.region)
    missing = {k: v for k, v in prices.items() if "missing" in v}

    for key, entry in prices.items():
        if "missing" in entry:
            print(f"MISSING  {key}: {entry['missing']}")
        else:
            print(f"ok       {key}: ${entry['price']:.8f} per {entry['unit']}  ({entry['description']}, "
                  f"SKU {entry['sku']}, {entry['matches']} match(es))")

    result = {"region": args.region, "machine": MACHINE, "prices": prices,
              "estimate": estimate(prices, free_tier_cluster=not args.no_free_tier)}
    print(f"e2-standard-4: ${result['estimate']['e2_standard_4_per_hour']:.6f} per hour")

    for name in SESSIONS:
        e = result["estimate"][name]
        print(f"{name}: ${e['usd']:.2f} in credits ({e['assumes']}): {e['parts']}")

    if args.out:
        args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())

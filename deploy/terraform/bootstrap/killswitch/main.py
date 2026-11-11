"""Hetren's billing kill switch (Cloud Run function, Pub/Sub trigger from the project's budget).

Budget alerts alone do not stop spending. When a budget notification reports cost at or above the budget, this
disables billing on the dedicated project (it unlinks the project from its billing account), which stops its
paid resources; the project holds nothing that must be kept. Notifications below the budget are logged and
ignored. ``DRY_RUN=1`` logs what it would do and changes nothing (for the test message in deploy/README.md).

Budget data lags usage by hours, so spend can pass the cap before this runs: it is a backstop, not the plan.
Only the standard library is used beyond the functions framework: the token comes from the metadata server.
"""

from __future__ import annotations

import base64
import json
import os
import urllib.request

try:
    import functions_framework

    cloud_event = functions_framework.cloud_event
except ImportError:  # unit tests
    def cloud_event(function):
        return function


METADATA_TOKEN = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"
BILLING = "https://cloudbilling.googleapis.com/v1/projects/{project}/billingInfo"


def notification(data: dict) -> dict:
    """The budget notification in a Pub/Sub CloudEvent's data."""
    return json.loads(base64.b64decode(data["message"]["data"]).decode("utf-8"))


def over_budget(payload: dict) -> bool:
    return float(payload["costAmount"]) >= float(payload["budgetAmount"])


def _request(method: str, url: str, token: str | None = None, body: dict | None = None) -> dict:
    headers = {"Metadata-Flavor": "Google"} if token is None else {"Authorization": f"Bearer {token}",
                                                                    "Content-Type": "application/json"}
    data = None if body is None else json.dumps(body).encode("utf-8")

    with urllib.request.urlopen(urllib.request.Request(url, data=data, method=method, headers=headers),
                                timeout=30) as response:
        return json.loads(response.read().decode("utf-8") or "{}")


def disable_billing(project: str, request=_request) -> str:
    token = request("GET", METADATA_TOKEN)["access_token"]
    url = BILLING.format(project=project)

    if not request("GET", url, token).get("billingEnabled"):
        return "billing already disabled"

    request("PUT", url, token, {"billingAccountName": ""})
    return "billing disabled"


@cloud_event
def stop_billing(event, request=_request) -> str:
    data = event.data if hasattr(event, "data") else event["data"]
    payload = notification(data)
    project, dry_run = os.environ["PROJECT_ID"], os.environ.get("DRY_RUN") == "1"
    summary = {"cost": payload.get("costAmount"), "budget": payload.get("budgetAmount"),
               "threshold": payload.get("alertThresholdExceeded"), "project": project}

    if not over_budget(payload):
        print(json.dumps({**summary, "action": "none (below the budget)"}))
        return "below the budget"

    if dry_run:
        print(json.dumps({**summary, "action": "would disable billing (DRY_RUN=1)"}))
        return "dry run"

    result = disable_billing(project, request)
    print(json.dumps({**summary, "action": result}))
    return result

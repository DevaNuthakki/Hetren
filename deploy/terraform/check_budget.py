"""Step 6b, after the bootstrap apply (operator): the live budget is the one the design needs. Read-only.

    python3 deploy/terraform/check_budget.py --billing-account <id> --project <project_id>

It reads the budget back from Google (``gcloud billing budgets list``) and checks:
- it covers only this project;
- it is $25 per calendar month;
- it alerts at 25%, 50%, 90% and 100% of current spend;
- it **excludes credits** (``EXCLUDE_ALL_CREDITS``), so the Free Trial's credits cannot hide the spend;
- it publishes every update to the kill switch's topic.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys


def problems(budgets: list[dict], project_id: str, project_number: str) -> list[str]:
    mine = [b for b in budgets if b.get("displayName") == f"hetren-{project_id}"]

    if len(mine) != 1:
        return [f"expected one budget named hetren-{project_id}, found {len(mine)}"]

    budget, found = mine[0], []
    flt = budget.get("budgetFilter", {})
    amount = budget.get("amount", {}).get("specifiedAmount", {})
    thresholds = sorted((r.get("thresholdPercent"), r.get("spendBasis", "CURRENT_SPEND"))
                        for r in budget.get("thresholdRules", []))
    topic = budget.get("notificationsRule", {}).get("pubsubTopic", "")

    if flt.get("creditTypesTreatment") != "EXCLUDE_ALL_CREDITS":
        found.append(f"creditTypesTreatment is {flt.get('creditTypesTreatment', 'unset (INCLUDE_ALL_CREDITS)')!r}, "
                     "not 'EXCLUDE_ALL_CREDITS': the Free Trial's credits would hide the spend")

    if flt.get("projects") != [f"projects/{project_number}"]:
        found.append(f"the budget covers {flt.get('projects')}, not only projects/{project_number}")

    if flt.get("calendarPeriod", "MONTH") != "MONTH":
        found.append(f"calendar period {flt.get('calendarPeriod')!r}, not MONTH")

    if (amount.get("currencyCode"), str(amount.get("units"))) != ("USD", "25"):
        found.append(f"amount {amount.get('units')} {amount.get('currencyCode')}, not 25 USD")

    if thresholds != [(0.25, "CURRENT_SPEND"), (0.5, "CURRENT_SPEND"), (0.9, "CURRENT_SPEND"), (1.0, "CURRENT_SPEND")]:
        found.append(f"thresholds {thresholds}, not 25%, 50%, 90% and 100% of current spend")

    if topic != f"projects/{project_id}/topics/hetren-budget":
        found.append(f"updates go to {topic!r}, not the kill switch's topic projects/{project_id}/topics/hetren-budget")

    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--billing-account", required=True)
    parser.add_argument("--project", required=True)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    def gcloud(*command: str) -> str:
        return subprocess.run(["gcloud", *command], check=True, capture_output=True, text=True).stdout

    number = gcloud("projects", "describe", args.project, "--format=value(projectNumber)").strip()
    budgets = json.loads(gcloud("billing", "budgets", "list", f"--billing-account={args.billing_account}",
                                f"--billing-project={args.project}", "--format=json"))
    found = problems(budgets, args.project, number)

    for problem in found:
        print(f"FAIL  {problem}")

    if not found:
        print(f"ok    budget hetren-{args.project}: $25 per month on projects/{number} only, alerts at 25/50/90/100%, "
              "credits excluded (gross usage), updates to the kill switch's topic")

    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())

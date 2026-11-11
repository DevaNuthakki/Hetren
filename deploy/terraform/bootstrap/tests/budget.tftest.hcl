# terraform test (deploy/terraform/check.sh): plans the stack with a mocked Google provider, so no credentials
# or cloud calls are needed, and checks the budget the design depends on.
mock_provider "google" {}

mock_provider "google" {
  alias = "billing"
}

variables {
  project_id      = "hetren-test-123"
  billing_account = "000000-000000-000000"
}

run "budget_measures_gross_usage" {
  command = plan

  assert {
    condition     = google_billing_budget.hetren.budget_filter[0].credit_types_treatment == "EXCLUDE_ALL_CREDITS"
    error_message = "The budget must exclude credits, or the Free Trial's credits hide the spend."
  }

  assert {
    condition     = google_billing_budget.hetren.amount[0].specified_amount[0].units == "25"
    error_message = "The budget is $25."
  }

  assert {
    condition     = [for rule in google_billing_budget.hetren.threshold_rules : rule.threshold_percent] == [0.25, 0.5, 0.9, 1.0]
    error_message = "Alerts at 25%, 50%, 90% and 100%."
  }

  assert {
    condition     = google_cloudfunctions2_function.kill_switch.service_config[0].environment_variables["DRY_RUN"] == "0"
    error_message = "The kill switch is live unless dry run is asked for."
  }
}

run "a_budget_above_25_is_refused" {
  command = plan

  variables {
    budget_usd = 30
  }

  expect_failures = [var.budget_usd]
}

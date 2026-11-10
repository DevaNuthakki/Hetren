# The dedicated Hetren project and everything that must outlive a cluster: the APIs, the Terraform state
# bucket, the $25 budget with alerts, and the kill switch that disables billing on this project at 100%.

locals {
  labels = { project = "hetren", milestone = "4" }

  services = [
    "artifactregistry.googleapis.com", # Cloud Run functions' build output
    "billingbudgets.googleapis.com",
    "cloudasset.googleapis.com", # the teardown check searches by label
    "cloudbilling.googleapis.com",
    "cloudbuild.googleapis.com",
    "cloudfunctions.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "compute.googleapis.com",
    "container.googleapis.com",
    "eventarc.googleapis.com",
    "iam.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "pubsub.googleapis.com",
    "run.googleapis.com",
    "serviceusage.googleapis.com",
    "storage.googleapis.com",
  ]
}

resource "google_project" "hetren" {
  project_id      = var.project_id
  name            = "Hetren Milestone 4"
  org_id          = var.org_id == "" ? null : var.org_id
  billing_account = var.billing_account
  deletion_policy = "DELETE" # the project holds nothing that must be kept
  labels          = local.labels
}

resource "google_project_service" "services" {
  for_each = toset(local.services)

  project            = google_project.hetren.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_storage_bucket" "state" {
  project                     = google_project.hetren.project_id
  name                        = "${var.project_id}-tfstate"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = true

  versioning {
    enabled = true
  }

  depends_on = [google_project_service.services]
}

# --- budget and kill switch ---------------------------------------------------------------------------------

resource "google_pubsub_topic" "budget" {
  project = google_project.hetren.project_id
  name    = "hetren-budget"

  depends_on = [google_project_service.services]
}

resource "google_monitoring_notification_channel" "email" {
  count = var.alert_email == "" ? 0 : 1

  project      = google_project.hetren.project_id
  display_name = "Hetren budget alerts"
  type         = "email"
  labels       = { email_address = var.alert_email }

  depends_on = [google_project_service.services]
}

resource "google_billing_budget" "hetren" {
  provider = google.billing

  billing_account = var.billing_account
  display_name    = "hetren-${var.project_id}"

  budget_filter {
    projects        = ["projects/${google_project.hetren.number}"]
    calendar_period = "MONTH"
    # Gross usage: credits (the Free Trial's included) are added back, so they cannot hide the spend and the
    # thresholds and the kill switch see what the resources cost. The API's default is INCLUDE_ALL_CREDITS.
    credit_types_treatment = "EXCLUDE_ALL_CREDITS"
  }

  amount {
    specified_amount {
      currency_code = "USD"
      units         = tostring(var.budget_usd)
    }
  }

  dynamic "threshold_rules" {
    for_each = [0.25, 0.5, 0.9, 1.0]

    content {
      threshold_percent = threshold_rules.value
      spend_basis       = "CURRENT_SPEND"
    }
  }

  all_updates_rule {
    pubsub_topic                     = google_pubsub_topic.budget.id
    schema_version                   = "1.0"
    monitoring_notification_channels = google_monitoring_notification_channel.email[*].id
    disable_default_iam_recipients   = false # billing account admins get the threshold emails
  }

  depends_on = [google_project_service.services]
}

resource "google_service_account" "kill_switch" {
  project      = google_project.hetren.project_id
  account_id   = "hetren-kill-switch"
  display_name = "Disables billing on this project when the budget is reached"
}

# Unlinking the project from its billing account (resourcemanager.projects.deleteBillingAssignment).
resource "google_project_iam_member" "kill_switch_billing" {
  project = google_project.hetren.project_id
  role    = "roles/billing.projectManager"
  member  = "serviceAccount:${google_service_account.kill_switch.email}"
}

# Eventarc delivers the Pub/Sub message to the function as this account.
resource "google_project_iam_member" "kill_switch_invoker" {
  project = google_project.hetren.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.kill_switch.email}"
}

resource "google_project_iam_member" "kill_switch_events" {
  project = google_project.hetren.project_id
  role    = "roles/eventarc.eventReceiver"
  member  = "serviceAccount:${google_service_account.kill_switch.email}"
}

# Builds the function's image (Cloud Build). A dedicated account with only what a build needs, instead of the
# Compute Engine default account, which new projects no longer grant broad roles.
resource "google_service_account" "kill_switch_build" {
  project      = google_project.hetren.project_id
  account_id   = "hetren-kill-switch-build"
  display_name = "Builds the kill switch function"
}

resource "google_project_iam_member" "kill_switch_build" {
  for_each = toset(["roles/logging.logWriter", "roles/artifactregistry.writer", "roles/storage.objectViewer"])

  project = google_project.hetren.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.kill_switch_build.email}"
}

data "archive_file" "kill_switch" {
  type        = "zip"
  source_dir  = "${path.module}/killswitch"
  output_path = "${path.module}/.build/killswitch.zip"
  excludes    = ["__pycache__"]
}

resource "google_storage_bucket" "functions" {
  project                     = google_project.hetren.project_id
  name                        = "${var.project_id}-functions"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = true

  depends_on = [google_project_service.services]
}

resource "google_storage_bucket_object" "kill_switch" {
  bucket = google_storage_bucket.functions.name
  name   = "killswitch-${data.archive_file.kill_switch.output_sha256}.zip"
  source = data.archive_file.kill_switch.output_path
}

resource "google_cloudfunctions2_function" "kill_switch" {
  project  = google_project.hetren.project_id
  location = var.region
  name     = "hetren-kill-switch"

  build_config {
    runtime         = "python313"
    entry_point     = "stop_billing"
    service_account = google_service_account.kill_switch_build.id

    source {
      storage_source {
        bucket = google_storage_bucket.functions.name
        object = google_storage_bucket_object.kill_switch.name
      }
    }
  }

  service_config {
    max_instance_count    = 1
    available_memory      = "256M"
    timeout_seconds       = 60
    service_account_email = google_service_account.kill_switch.email
    ingress_settings      = "ALLOW_INTERNAL_ONLY"

    environment_variables = {
      PROJECT_ID = google_project.hetren.project_id
      DRY_RUN    = var.kill_switch_dry_run ? "1" : "0"
    }
  }

  event_trigger {
    trigger_region        = var.region
    event_type            = "google.cloud.pubsub.topic.v1.messagePublished"
    pubsub_topic          = google_pubsub_topic.budget.id
    retry_policy          = "RETRY_POLICY_RETRY"
    service_account_email = google_service_account.kill_switch.email
  }

  depends_on = [google_project_service.services, google_project_iam_member.kill_switch_events,
  google_project_iam_member.kill_switch_build]
}

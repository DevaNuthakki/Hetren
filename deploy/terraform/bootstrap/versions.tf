terraform {
  required_version = ">= 1.16.0, < 2.0.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "8.8.1"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "2.8.1"
    }
  }

  # The first apply uses local state (gitignored): this stack creates the state bucket, so its state cannot
  # start there. Right after that apply, move it into the bucket (backend.tf.example; deploy/README.md,
  # "Bootstrap state"), so the project, budget and kill switch stay manageable without this machine's copy.
}

provider "google" {
  region         = var.region
  default_labels = local.labels
}

# The Billing Budgets API needs a quota project; the new project is that, once its APIs are on.
provider "google" {
  alias                 = "billing"
  region                = var.region
  user_project_override = true
  billing_project       = var.project_id
}

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

  # Local state (gitignored): this stack creates the bucket that holds the gke stack's remote state, so its
  # own state cannot live there. It is small and holds no secrets; destroying this stack deletes the project.
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

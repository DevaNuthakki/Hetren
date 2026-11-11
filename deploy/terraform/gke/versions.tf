terraform {
  required_version = ">= 1.16.0, < 2.0.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "8.8.1"
    }
  }

  # Remote state in the bucket the bootstrap stack creates:
  #   terraform init -backend-config="bucket=<project_id>-tfstate"
  backend "gcs" {
    prefix = "gke"
  }
}

provider "google" {
  project        = var.project_id
  region         = var.region
  default_labels = { project = "hetren", milestone = "4" }
}

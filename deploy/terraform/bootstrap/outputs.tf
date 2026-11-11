output "project_id" {
  value = google_project.hetren.project_id
}

output "project_number" {
  value = google_project.hetren.number
}

output "state_bucket" {
  description = "Bucket for both stacks' Terraform state (backend-config bucket=...)."
  value       = google_storage_bucket.state.name
}

output "budget_topic" {
  description = "Publish a test budget message here to check the kill switch (deploy/README.md)."
  value       = google_pubsub_topic.budget.id
}

output "cluster" {
  value = google_container_cluster.hetren.name
}

output "get_credentials" {
  value = "gcloud container clusters get-credentials ${google_container_cluster.hetren.name} --zone ${var.zone} --project ${var.project_id}"
}

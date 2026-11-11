resource "google_service_account" "nodes" {
  account_id   = "hetren-nodes"
  display_name = "Hetren GKE nodes (logs and metrics only)"
}

resource "google_project_iam_member" "nodes" {
  for_each = toset(["roles/logging.logWriter", "roles/monitoring.metricWriter", "roles/monitoring.viewer",
  "roles/stackdriver.resourceMetadata.writer"])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.nodes.email}"
}

resource "google_container_cluster" "hetren" {
  name                     = "hetren"
  location                 = var.zone
  network                  = google_compute_network.hetren.id
  subnetwork               = google_compute_subnetwork.nodes.id
  networking_mode          = "VPC_NATIVE"
  remove_default_node_pool = true
  initial_node_count       = 1
  deletion_protection      = false # terraform destroy must be able to remove it
  resource_labels          = { project = "hetren", milestone = "4" }

  release_channel {
    channel = "REGULAR"
  }

  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }

  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block  = "172.16.0.0/28"
  }

  master_authorized_networks_config {
    cidr_blocks {
      cidr_block   = var.master_authorized_cidr
      display_name = "operator"
    }
  }

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  addons_config {
    http_load_balancing {
      disabled = true # no Ingress load balancers: the Service is ClusterIP and the load test runs inside
    }
  }

  cluster_autoscaling {
    autoscaling_profile = "OPTIMIZE_UTILIZATION" # remove idle nodes sooner
  }

  logging_config {
    enable_components = ["SYSTEM_COMPONENTS"]
  }

  monitoring_config {
    enable_components = ["SYSTEM_COMPONENTS"]

    managed_prometheus {
      enabled = false
    }
  }
}

locals {
  node_vcpus = tonumber(regex("[0-9]+$", var.machine_type))
}

resource "google_container_node_pool" "inference" {
  name     = "inference"
  cluster  = google_container_cluster.hetren.id
  location = var.zone

  initial_node_count = var.min_nodes

  autoscaling {
    min_node_count = var.min_nodes
    max_node_count = var.max_nodes
  }

  # An upgrade replaces nodes one at a time without a surge node, which would exceed the 8-vCPU limit.
  upgrade_settings {
    strategy        = "SURGE"
    max_surge       = 0
    max_unavailable = 1
  }

  lifecycle {
    precondition {
      condition     = var.max_nodes * local.node_vcpus <= var.max_vcpus
      error_message = "The node pool at its maximum would exceed the Free Trial's 8 concurrent vCPUs."
    }
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }

  node_config {
    machine_type    = var.machine_type
    disk_type       = "pd-balanced"
    disk_size_gb    = var.disk_size_gb
    service_account = google_service_account.nodes.email
    oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]
    labels          = { "hetren/pool" = "inference" }
    resource_labels = { project = "hetren", milestone = "4" }

    shielded_instance_config {
      enable_secure_boot          = true
      enable_integrity_monitoring = true
    }

    workload_metadata_config {
      mode = "GKE_METADATA"
    }
  }

  depends_on = [google_project_iam_member.nodes]
}

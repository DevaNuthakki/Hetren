# A VPC for the cluster only. Nodes have no external IPs; they reach GHCR and Hugging Face through Cloud NAT.
resource "google_compute_network" "hetren" {
  name                    = "hetren"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "nodes" {
  name                     = "hetren-nodes"
  network                  = google_compute_network.hetren.id
  region                   = var.region
  ip_cidr_range            = "10.10.0.0/24"
  private_ip_google_access = true

  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = "10.20.0.0/16"
  }

  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = "10.30.0.0/20"
  }
}

resource "google_compute_router" "hetren" {
  name    = "hetren"
  network = google_compute_network.hetren.id
  region  = var.region
}

resource "google_compute_router_nat" "hetren" {
  name                               = "hetren"
  router                             = google_compute_router.hetren.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}

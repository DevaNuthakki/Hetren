# terraform test (deploy/terraform/check.sh): plans the stack with a mocked Google provider and checks that the
# node pool fits the Free Trial's 8 concurrent vCPUs.
mock_provider "google" {}

variables {
  project_id             = "hetren-test-123"
  master_authorized_cidr = "203.0.113.7/32"
}

run "two_e2_standard_4_nodes_fit" {
  command = plan

  assert {
    condition     = google_container_node_pool.inference.autoscaling[0].max_node_count == 2
    error_message = "At most 2 nodes."
  }

  assert {
    condition     = google_container_node_pool.inference.node_config[0].machine_type == "e2-standard-4"
    error_message = "e2-standard-4 nodes."
  }

  assert {
    condition     = google_container_node_pool.inference.upgrade_settings[0].max_surge == 0
    error_message = "No surge node during upgrades (it would exceed 8 vCPUs)."
  }

  assert {
    condition     = google_container_cluster.hetren.private_cluster_config[0].enable_private_nodes
    error_message = "Private nodes."
  }
}

run "three_nodes_are_refused" {
  command = plan

  variables {
    max_nodes = 3
  }

  expect_failures = [var.max_nodes]
}

run "two_larger_nodes_exceed_8_vcpus" {
  command = plan

  variables {
    machine_type = "e2-standard-8"
  }

  expect_failures = [google_container_node_pool.inference]
}

run "a_wider_network_is_refused" {
  command = plan

  variables {
    master_authorized_cidr = "203.0.113.0/24"
  }

  expect_failures = [var.master_authorized_cidr]
}

resource "google_container_cluster" "this" {
  name     = var.cluster_name
  location = var.region

  enable_autopilot = true

  network    = var.network_id
  subnetwork = var.subnet_id

  private_cluster_config {
    enable_private_nodes   = true
    master_ipv4_cidr_block = var.master_cidr
  }

  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }

  deletion_protection = false
}

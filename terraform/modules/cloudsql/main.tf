resource "google_compute_global_address" "private_ip" {
  name          = "${var.instance_name}-private-ip"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = var.network_id
}

resource "google_service_networking_connection" "private_vpc" {
  network                 = var.network_id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip.name]
}

resource "random_password" "db_password" {
  length  = 24
  special = false
}

resource "google_sql_database_instance" "this" {
  name             = var.instance_name
  database_version = "POSTGRES_15"
  region           = var.region

  depends_on = [google_service_networking_connection.private_vpc]

  settings {
    tier              = var.tier
    availability_type = "ZONAL"

    ip_configuration {
      ipv4_enabled    = false
      private_network = var.network_id
    }

    backup_configuration {
      enabled = true
    }
  }

  deletion_protection = false
}

resource "google_sql_database" "this" {
  name     = var.db_name
  instance = google_sql_database_instance.this.name
}

resource "google_sql_user" "this" {
  name     = var.db_user
  instance = google_sql_database_instance.this.name
  password = random_password.db_password.result
}

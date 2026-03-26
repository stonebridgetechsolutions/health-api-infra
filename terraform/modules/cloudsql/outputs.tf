output "private_ip" {
  description = "Cloud SQL private IP address"
  value       = google_sql_database_instance.this.private_ip_address
}

output "connection_name" {
  description = "Cloud SQL connection name"
  value       = google_sql_database_instance.this.connection_name
}

output "db_password" {
  description = "Database password"
  value       = random_password.db_password.result
  sensitive   = true
}

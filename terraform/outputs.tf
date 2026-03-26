output "cluster_name" {
  description = "GKE cluster name"
  value       = module.gke.cluster_name
}

output "cluster_endpoint" {
  description = "GKE cluster endpoint"
  value       = module.gke.cluster_endpoint
  sensitive   = true
}

output "registry_url" {
  description = "Artifact Registry URL"
  value       = module.registry.registry_url
}

output "service_account_email" {
  description = "GKE service account email"
  value       = module.iam.service_account_email
}

output "db_private_ip" {
  description = "Cloud SQL private IP"
  value       = module.cloudsql.private_ip
}

output "db_connection_name" {
  description = "Cloud SQL connection name"
  value       = module.cloudsql.connection_name
}

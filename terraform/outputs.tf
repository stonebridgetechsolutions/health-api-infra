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

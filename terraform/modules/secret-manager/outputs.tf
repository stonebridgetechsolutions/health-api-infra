output "secret_ids" {
  description = "Map of secret name to secret ID"
  value       = { for k, v in google_secret_manager_secret.this : k => v.id }
}

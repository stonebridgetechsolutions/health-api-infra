variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "secrets" {
  description = "Map of secret name to secret value"
  type        = map(string)
}

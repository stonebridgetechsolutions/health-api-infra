terraform {
  backend "gcs" {
    bucket = "health-api-infra-tf-state"
    prefix = "gke-health-api"
  }
}

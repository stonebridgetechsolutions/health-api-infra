terraform {
  backend "gcs" {
    bucket = "CHANGEME-tf-state"
    prefix = "gke-health-api"
  }
}

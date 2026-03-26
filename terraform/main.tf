module "vpc" {
  source = "./modules/vpc"

  name          = var.cluster_name
  region        = var.region
  subnet_cidr   = var.subnet_cidr
  pods_cidr     = var.pods_cidr
  services_cidr = var.services_cidr
}

module "gke" {
  source = "./modules/gke"

  cluster_name = var.cluster_name
  region       = var.region
  network_id   = module.vpc.network_id
  subnet_id    = module.vpc.subnet_id

  depends_on = [module.vpc]
}

module "registry" {
  source = "./modules/registry"

  repository_id = var.repository_id
  region        = var.region
  project_id    = var.project_id
}

module "iam" {
  source = "./modules/iam"

  project_id   = var.project_id
  account_id   = var.service_account_id
  display_name = "Health API GKE Service Account"

  roles = [
    "roles/artifactregistry.reader",
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
  ]
}

module "cloudsql" {
  source = "./modules/cloudsql"

  instance_name = var.db_instance_name
  region        = var.region
  network_id    = module.vpc.network_id
  db_name       = var.db_name
  db_user       = var.db_user
  tier          = var.db_tier

  depends_on = [module.vpc]
}

module "secrets" {
  source = "./modules/secret-manager"

  project_id = var.project_id
  secrets = {
    "db-host"     = module.cloudsql.private_ip
    "db-password" = module.cloudsql.db_password
    "db-name"     = var.db_name
    "db-user"     = var.db_user
  }

  depends_on = [module.cloudsql]
}

module "monitoring" {
  source = "./modules/monitoring"

  app_name   = "health-api"
  project_id = var.project_id
}

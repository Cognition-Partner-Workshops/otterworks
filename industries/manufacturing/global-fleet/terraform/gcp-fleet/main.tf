locals {
  name = "gf-fleet"
  labels = {
    run_token  = var.run_token
    expires_at = replace(var.expires_at, "-", "")
    app        = "global-fleet"
  }
  registry = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.fleet.repository_id}"
}

resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "secretmanager.googleapis.com",
    "artifactregistry.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "fleet" {
  repository_id = local.name
  location      = var.region
  format        = "DOCKER"
  labels        = local.labels
  depends_on    = [google_project_service.apis]
}

resource "google_sql_database_instance" "fleet" {
  name                = "${local.name}-${var.run_token}"
  database_version    = "POSTGRES_16"
  region              = var.region
  deletion_protection = var.deletion_protection

  settings {
    tier              = var.db_tier
    availability_type = "ZONAL"
    disk_autoresize   = true
    user_labels       = local.labels

    ip_configuration {
      ipv4_enabled = true
      ssl_mode     = "ENCRYPTED_ONLY"
    }

    backup_configuration {
      enabled = true
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_sql_database" "fleet" {
  name     = "fleet"
  instance = google_sql_database_instance.fleet.name
}

resource "random_password" "db" {
  length  = 32
  special = false
}

resource "google_sql_user" "fleet" {
  name     = "fleet"
  instance = google_sql_database_instance.fleet.name
  password = random_password.db.result
}

resource "google_secret_manager_secret" "db_password" {
  secret_id = "${local.name}-db-password"
  labels    = local.labels
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "db_password" {
  secret      = google_secret_manager_secret.db_password.id
  secret_data = random_password.db.result
}

resource "google_service_account" "fleet" {
  account_id   = "${local.name}-run"
  display_name = "Global fleet Cloud Run"
}

resource "google_project_iam_member" "sql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.fleet.email}"
}

resource "google_secret_manager_secret_iam_member" "db_password" {
  secret_id = google_secret_manager_secret.db_password.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.fleet.email}"
}

resource "google_cloud_run_v2_service" "service" {
  name                = "${local.name}-service"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false
  labels              = local.labels

  template {
    service_account = google_service_account.fleet.email
    labels          = local.labels

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.fleet.connection_name]
      }
    }

    containers {
      image = "${local.registry}/fleet-service:${var.image_tag}"
      ports {
        container_port = 8080
      }
      env {
        name  = "SPRING_PROFILES_ACTIVE"
        value = var.country_profile
      }
      env {
        name  = "SPRING_DATASOURCE_URL"
        value = "jdbc:postgresql:///${google_sql_database.fleet.name}?cloudSqlInstance=${google_sql_database_instance.fleet.connection_name}&socketFactory=com.google.cloud.sql.postgres.SocketFactory"
      }
      env {
        name  = "SPRING_DATASOURCE_USERNAME"
        value = google_sql_user.fleet.name
      }
      env {
        name = "SPRING_DATASOURCE_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.db_password.secret_id
            version = "latest"
          }
        }
      }
      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }
      startup_probe {
        http_get {
          path = "/actuator/health"
        }
        failure_threshold = 30
        period_seconds    = 5
      }
      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }
    }
  }

  depends_on = [
    google_project_iam_member.sql_client,
    google_secret_manager_secret_iam_member.db_password,
    google_secret_manager_secret_version.db_password,
  ]
}

resource "google_cloud_run_v2_service" "web" {
  name                = "${local.name}-web"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false
  labels              = local.labels

  template {
    labels = local.labels
    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }
    containers {
      image = "${local.registry}/fleet-web:${var.image_tag}"
      ports {
        container_port = 8080
      }
      env {
        name  = "API_BASE_URL"
        value = google_cloud_run_v2_service.service.uri
      }
    }
  }
}

resource "google_cloud_run_v2_service_iam_member" "public" {
  for_each = {
    service = google_cloud_run_v2_service.service.name
    web     = google_cloud_run_v2_service.web.name
  }
  name     = each.value
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

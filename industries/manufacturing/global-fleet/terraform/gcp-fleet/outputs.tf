output "service_url" {
  value = google_cloud_run_v2_service.service.uri
}

output "web_url" {
  value = google_cloud_run_v2_service.web.uri
}

output "sql_connection_name" {
  value = google_sql_database_instance.fleet.connection_name
}

output "image_registry" {
  value = local.registry
}

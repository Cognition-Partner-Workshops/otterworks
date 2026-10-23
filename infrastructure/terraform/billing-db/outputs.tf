output "endpoint" {
  description = "host:port of the billing instance."
  value       = aws_db_instance.billing.endpoint
}

output "address" {
  description = "Hostname of the billing instance (DB_HOST)."
  value       = aws_db_instance.billing.address
}

output "port" {
  description = "Port of the billing instance (DB_PORT)."
  value       = aws_db_instance.billing.port
}

output "database_name" {
  description = "Database created by bootstrap/create-database.sql (DB_NAME)."
  value       = var.database_name
}

output "master_user_secret_arn" {
  description = "Secrets Manager ARN of the RDS-managed master credential."
  value       = aws_db_instance.billing.master_user_secret[0].secret_arn
}

output "engine_version" {
  description = "Pinned RDS PostgreSQL engine version."
  value       = aws_db_instance.billing.engine_version
}

output "parameter_group" {
  description = "Parameter group with rds.force_ssl=1, timezone=UTC and DateStyle 'ISO, MDY'."
  value       = aws_db_parameter_group.billing.name
}

output "ca_cert_identifier" {
  description = "RDS CA the server certificate chains to (for sslmode=verify-full)."
  value       = aws_db_instance.billing.ca_cert_identifier
}

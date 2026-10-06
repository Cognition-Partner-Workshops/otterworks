output "run_token" {
  value = var.run_token
}

output "expires" {
  value = var.expires
}

output "db_instance" {
  value = var.db_instance_identifier
}

output "db_endpoint" {
  value = "${data.aws_db_instance.shared.address}:${data.aws_db_instance.shared.port}"
}

output "db_name" {
  value = local.db_name
}

output "db_role" {
  value = local.db_role
}

output "db_secret_name" {
  description = "Secrets Manager secret with engine/host/port/dbname/username/password of the run's login role."
  value       = aws_secretsmanager_secret.billing_db.name
}

output "db_init_function" {
  value = aws_lambda_function.db_init.function_name
}

output "sql_function" {
  description = "In-VPC SQL runner scripts/billing-to-rds.py invokes for the load and RDS-side counts."
  value       = aws_lambda_function.db_sql.function_name
}

output "db_evidence" {
  description = "What the db-init function read back after create: the \\l row, the role, its database privileges and a login as the role."
  value       = jsondecode(aws_lambda_invocation.database.result)
}

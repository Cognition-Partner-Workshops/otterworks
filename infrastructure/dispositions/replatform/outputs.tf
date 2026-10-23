output "release_name" {
  description = "Helm release name, or null when deploy_release is false."
  value       = var.deploy_release ? helm_release.this[0].name : null
}

output "namespace" {
  value = var.namespace
}

output "service_account_name" {
  value = local.service_account_name
}

output "service_account_role_arn" {
  description = "IRSA role ARN, or null when oidc_provider_arn is not set."
  value       = local.irsa_enabled ? aws_iam_role.service_account[0].arn : null
}

output "postgres_endpoint" {
  value = var.postgres == null ? null : aws_db_instance.postgres[0].endpoint
}

output "postgres_secret_arn" {
  description = "Secrets Manager secret holding the PostgreSQL master credential."
  value       = var.postgres == null ? null : aws_secretsmanager_secret.postgres[0].arn
}

output "redis_endpoint" {
  value = var.redis == null ? null : aws_elasticache_replication_group.redis[0].primary_endpoint_address
}

output "bucket_names" {
  value = { for key, bucket in aws_s3_bucket.this : key => bucket.id }
}

output "queue_urls" {
  value = { for key, queue in aws_sqs_queue.this : key => queue.url }
}

output "connection_config" {
  description = "Non-secret settings the release receives in its ConfigMap."
  value       = local.connection_config
}

output "expires" {
  value = var.expires
}

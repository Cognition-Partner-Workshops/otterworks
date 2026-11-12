output "api_url" {
  description = "Invoke URL of the HTTP API: the portal's new front door. lp-mod-replay uses it as the target base URL."
  value       = aws_apigatewayv2_stage.default.invoke_url
}

output "api_id" {
  value = aws_apigatewayv2_api.this.id
}

output "ec2_base_url" {
  description = "ALB of the legacy-portal-ec2 run behind the $default route."
  value       = "http://${data.aws_lb.ec2.dns_name}"
}

output "lambda_name" {
  value = aws_lambda_function.this.function_name
}

output "lambda_live_version" {
  value = aws_lambda_alias.live.function_version
}

output "lambda_log_group" {
  value = aws_cloudwatch_log_group.lambda.name
}

output "api_log_group" {
  value = aws_cloudwatch_log_group.api.name
}

output "aurora_cluster_arn" {
  value = aws_rds_cluster.this.arn
}

output "db_secret_arn" {
  value = aws_secretsmanager_secret.db.arn
}

output "db_name" {
  value = aws_rds_cluster.this.database_name
}

output "event_bus_name" {
  value = local.events ? aws_cloudwatch_event_bus.this[0].name : null
}

output "event_rule_name" {
  value = local.events ? aws_cloudwatch_event_rule.announcement_published[0].name : null
}

output "notifications_queue_url" {
  value = local.events ? aws_sqs_queue.notifications[0].url : null
}

output "events_log_group" {
  value = local.events ? aws_cloudwatch_log_group.events[0].name : null
}

output "ec2_run_token" {
  description = "legacy-portal-ec2 run that still serves every route outside the module's prefix."
  value       = var.ec2_run_token
}

output "module" {
  value = var.module
}

output "route_prefix" {
  value = local.m.prefix
}

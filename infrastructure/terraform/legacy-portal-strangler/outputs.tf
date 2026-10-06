output "api_url" {
  description = "Invoke URL of the HTTP API: the portal's new front door. lp-ann-replay uses it as the target base URL."
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
  value = aws_lambda_function.announcements.function_name
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
  value = aws_cloudwatch_event_bus.this.name
}

output "event_rule_name" {
  value = aws_cloudwatch_event_rule.announcement_published.name
}

output "notifications_queue_url" {
  value = aws_sqs_queue.notifications.url
}

output "events_log_group" {
  value = aws_cloudwatch_log_group.events.name
}

output "ec2_run_token" {
  description = "legacy-portal-ec2 run that still serves every route outside /api/announcements."
  value       = var.ec2_run_token
}

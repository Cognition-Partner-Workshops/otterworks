output "api_url" {
  description = "Invoke URL of the HTTP API. lp-replay uses it as the target base URL."
  value       = aws_apigatewayv2_stage.default.invoke_url
}

output "api_id" {
  value = aws_apigatewayv2_api.this.id
}

output "lambda_names" {
  description = "Function name per bounded context."
  value       = { for ctx, fn in aws_lambda_function.context : ctx => fn.function_name }
}

output "aurora_cluster_arn" {
  value = aws_rds_cluster.this.arn
}

output "aurora_capacity" {
  value = "${var.aurora_min_acu}-${var.aurora_max_acu} ACU"
}

output "db_secret_arn" {
  value = aws_rds_cluster.this.master_user_secret[0].secret_arn
}

output "db_name" {
  value = aws_rds_cluster.this.database_name
}

output "builder_policy_arn" {
  value = aws_iam_policy.builder.arn
}

output "event_bus_name" {
  value = aws_cloudwatch_event_bus.this.name
}

output "notifications_table" {
  value = aws_dynamodb_table.notifications.name
}

output "consumer_function" {
  value = aws_lambda_function.consumer.function_name
}

output "live_aliases" {
  description = "Alias the HTTP API invokes, per context."
  value       = { for ctx, a in aws_lambda_alias.live : ctx => a.arn }
}

output "codedeploy_app" {
  value = aws_codedeploy_app.this.name
}

output "deployment_groups" {
  value = { for ctx, g in aws_codedeploy_deployment_group.context : ctx => g.deployment_group_name }
}

output "deployment_config" {
  value = var.deployment_config_name
}

output "probe_canary" {
  value = aws_synthetics_canary.probe.name
}

output "probe_artifacts_bucket" {
  value = aws_s3_bucket.probe_artifacts.bucket
}

output "alarm_5xx_rate" {
  value = aws_cloudwatch_metric_alarm.api_5xx_rate.alarm_name
}

output "alarm_lambda_errors" {
  value = aws_cloudwatch_metric_alarm.lambda_errors.alarm_name
}

output "alarm_page" {
  value = aws_cloudwatch_composite_alarm.page.alarm_name
}

output "page_rule" {
  value = aws_cloudwatch_event_rule.page.name
}

output "page_rule_state" {
  value = aws_cloudwatch_event_rule.page.state
}

output "page_api_destination" {
  value = aws_cloudwatch_event_api_destination.devin_webhook.name
}

output "page_dlq_url" {
  value = aws_sqs_queue.page_dlq.url
}

output "api_url" {
  description = "Invoke URL of the HTTP API."
  value       = aws_apigatewayv2_stage.default.invoke_url
}

output "api_id" {
  value = aws_apigatewayv2_api.this.id
}

output "lambda_names" {
  value = { for context, function in aws_lambda_function.context : context => function.function_name }
}

output "aurora_cluster_arn" {
  value = aws_rds_cluster.this.arn
}

output "aurora_capacity" {
  value = "${var.aurora_min_acu}-${var.aurora_max_acu} ACU"
}

output "db_secret_arn" {
  value = aws_secretsmanager_secret.db.arn
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

output "subscription_tables" {
  value = { for key, table in aws_dynamodb_table.subscription : key => table.name }
}

output "consumer_functions" {
  value = { for key, function in aws_lambda_function.consumer : key => function.function_name }
}

output "live_aliases" {
  value = { for context, alias in aws_lambda_alias.live : context => alias.arn }
}

output "codedeploy_app" {
  value = aws_codedeploy_app.this.name
}

output "deployment_groups" {
  value = { for context, group in aws_codedeploy_deployment_group.context : context => group.deployment_group_name }
}

output "probe_canary" {
  value = try(aws_synthetics_canary.probe[0].name, null)
}

output "probe_artifacts_bucket" {
  value = try(aws_s3_bucket.probe_artifacts[0].bucket, null)
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
  value = try(aws_cloudwatch_event_api_destination.devin_webhook[0].name, null)
}

output "page_dlq_url" {
  value = aws_sqs_queue.page_dlq.url
}

output "expires" {
  value = var.expires
}

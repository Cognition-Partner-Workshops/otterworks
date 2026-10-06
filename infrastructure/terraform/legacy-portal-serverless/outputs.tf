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

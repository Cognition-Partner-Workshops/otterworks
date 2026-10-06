resource "aws_apigatewayv2_api" "this" {
  name          = local.name
  description   = "legacy-portal routes for ${local.name}"
  protocol_type = "HTTP"
}

resource "aws_cloudwatch_log_group" "api" { # nosemgrep: terraform.aws.security.aws-cloudwatch-log-group-unencrypted.aws-cloudwatch-log-group-unencrypted
  name              = "/aws/apigateway/${local.name}"
  retention_in_days = var.log_retention_days
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.this.id
  name        = "$default"
  auto_deploy = true

  default_route_settings {
    throttling_rate_limit  = var.api_throttling_rate_limit
    throttling_burst_limit = var.api_throttling_burst_limit
  }

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api.arn
    format = jsonencode({
      requestId = "$context.requestId"
      time      = "$context.requestTime"
      method    = "$context.httpMethod"
      path      = "$context.path"
      routeKey  = "$context.routeKey"
      status    = "$context.status"
      latencyMs = "$context.integrationLatency"
      error     = "$context.integrationErrorMessage"
    })
  }
}

resource "aws_apigatewayv2_integration" "context" {
  for_each               = aws_lambda_function.context
  api_id                 = aws_apigatewayv2_api.this.id
  integration_type       = "AWS_PROXY"
  integration_uri        = each.value.invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = 29000
}

locals {
  # Two routes per prefix: the bare collection path and everything under it.
  routes = merge([
    for ctx, c in var.contexts : {
      "${ctx}-root"  = { context = ctx, key = "ANY ${c.route_prefix}" }
      "${ctx}-proxy" = { context = ctx, key = "ANY ${c.route_prefix}/{proxy+}" }
    }
  ]...)
}

resource "aws_apigatewayv2_route" "context" {
  for_each  = local.routes
  api_id    = aws_apigatewayv2_api.this.id
  route_key = each.value.key
  target    = "integrations/${aws_apigatewayv2_integration.context[each.value.context].id}"
}

resource "aws_apigatewayv2_route" "default" {
  api_id    = aws_apigatewayv2_api.this.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.context[var.default_route_context].id}"
}

resource "aws_lambda_permission" "api" {
  for_each      = aws_lambda_function.context
  statement_id  = "AllowHttpApi"
  action        = "lambda:InvokeFunction"
  function_name = each.value.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/*"
}

resource "aws_apigatewayv2_api" "this" {
  name          = local.name
  description   = "legacy-portal front door for ${local.name}: announcements on Lambda, everything else on ${var.ec2_run_token}"
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

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api.arn
    format = jsonencode({
      requestId   = "$context.requestId"
      time        = "$context.requestTime"
      method      = "$context.httpMethod"
      path        = "$context.path"
      routeKey    = "$context.routeKey"
      status      = "$context.status"
      integration = "$context.integration.integrationStatus"
      latencyMs   = "$context.integrationLatency"
      error       = "$context.integrationErrorMessage"
    })
  }
}

resource "aws_apigatewayv2_integration" "announcements" {
  api_id                 = aws_apigatewayv2_api.this.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_alias.live.invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = 29000
}

# $default forwards the full request path and query string to the monolith's ALB.
resource "aws_apigatewayv2_integration" "ec2" {
  api_id               = aws_apigatewayv2_api.this.id
  integration_type     = "HTTP_PROXY"
  integration_method   = "ANY"
  integration_uri      = "http://${data.aws_lb.ec2.dns_name}"
  timeout_milliseconds = 29000
}

resource "aws_apigatewayv2_route" "announcements" {
  for_each  = toset(["ANY /api/announcements", "ANY /api/announcements/{proxy+}"])
  api_id    = aws_apigatewayv2_api.this.id
  route_key = each.value
  target    = "integrations/${aws_apigatewayv2_integration.announcements.id}"
}

resource "aws_apigatewayv2_route" "default" {
  api_id    = aws_apigatewayv2_api.this.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.ec2.id}"
}

resource "aws_lambda_permission" "api" {
  statement_id  = "AllowHttpApi"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.announcements.function_name
  qualifier     = aws_lambda_alias.live.name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/*"
}

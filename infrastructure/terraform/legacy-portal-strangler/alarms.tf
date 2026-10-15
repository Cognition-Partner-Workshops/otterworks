# Deployment gate of the CodeDeploy canary (deploy.tf): the module routes' 5xx share and the
# function's invocation errors. HTTP APIs publish 5xx and Count per route when detailed metrics are on.
locals {
  alarm_5xx_name    = "${local.name}-${var.module}-5xx-rate"
  alarm_errors_name = "${local.name}-${var.module}-errors"
}

resource "aws_cloudwatch_metric_alarm" "api_5xx_rate" {
  alarm_name          = local.alarm_5xx_name
  alarm_description   = "5xx share of ${local.m.prefix} responses on HTTP API ${aws_apigatewayv2_api.this.id} above ${var.alarm_5xx_rate_percent}% in two of three minutes"
  comparison_operator = "GreaterThanThreshold"
  threshold           = var.alarm_5xx_rate_percent
  evaluation_periods  = 3
  datapoints_to_alarm = 2
  treat_missing_data  = "notBreaching"

  metric_query {
    id          = "rate"
    expression  = "IF(requests > 0, 100 * errors / requests, 0)"
    label       = "${var.module} 5xx rate (%)"
    return_data = true
  }

  metric_query {
    id          = "errors"
    expression  = "SUM([${join(", ", [for i, _ in local.module_routes : "e${i}"])}])"
    return_data = false
  }

  metric_query {
    id          = "requests"
    expression  = "SUM([${join(", ", [for i, _ in local.module_routes : "c${i}"])}])"
    return_data = false
  }

  dynamic "metric_query" {
    for_each = { for i, route in local.module_routes : "e${i}" => route }
    content {
      id          = metric_query.key
      return_data = false
      metric {
        namespace   = "AWS/ApiGateway"
        metric_name = "5xx"
        dimensions  = { ApiId = aws_apigatewayv2_api.this.id, Stage = aws_apigatewayv2_stage.default.name, Route = metric_query.value }
        period      = 60
        stat        = "Sum"
      }
    }
  }

  dynamic "metric_query" {
    for_each = { for i, route in local.module_routes : "c${i}" => route }
    content {
      id          = metric_query.key
      return_data = false
      metric {
        namespace   = "AWS/ApiGateway"
        metric_name = "Count"
        dimensions  = { ApiId = aws_apigatewayv2_api.this.id, Stage = aws_apigatewayv2_stage.default.name, Route = metric_query.value }
        period      = 60
        stat        = "Sum"
      }
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = local.alarm_errors_name
  alarm_description   = "Invocation errors of ${aws_lambda_function.this.function_name} in two of three minutes"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 1
  evaluation_periods  = 3
  datapoints_to_alarm = 2
  treat_missing_data  = "notBreaching"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = aws_lambda_function.this.function_name }
  period              = 60
  statistic           = "Sum"
}

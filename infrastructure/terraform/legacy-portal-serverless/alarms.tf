# The page: the HTTP API 5xx rate, the context functions' Errors, and a composite over both.
# HTTP APIs publish 5xx and Count (REST APIs call the first one 5XXError).
locals {
  alarm_5xx_name    = "${local.name}-api-5xx-rate"
  alarm_errors_name = "${local.name}-lambda-errors"
  alarm_page_name   = "${local.name}-page"
}

resource "aws_cloudwatch_metric_alarm" "api_5xx_rate" {
  alarm_name          = local.alarm_5xx_name
  alarm_description   = "5xx responses over all responses of HTTP API ${aws_apigatewayv2_api.this.id} above ${var.alarm_5xx_rate_percent}% in two of three minutes"
  comparison_operator = "GreaterThanThreshold"
  threshold           = var.alarm_5xx_rate_percent
  evaluation_periods  = 3
  datapoints_to_alarm = 2
  treat_missing_data  = "notBreaching"

  metric_query {
    id          = "rate"
    expression  = "IF(requests > 0, 100 * errors / requests, 0)"
    label       = "5xx rate (%)"
    return_data = true
  }

  metric_query {
    id = "errors"
    metric {
      namespace   = "AWS/ApiGateway"
      metric_name = "5xx"
      dimensions  = { ApiId = aws_apigatewayv2_api.this.id }
      period      = 60
      stat        = "Sum"
    }
  }

  metric_query {
    id = "requests"
    metric {
      namespace   = "AWS/ApiGateway"
      metric_name = "Count"
      dimensions  = { ApiId = aws_apigatewayv2_api.this.id }
      period      = 60
      stat        = "Sum"
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = local.alarm_errors_name
  alarm_description   = "Invocation errors of the ${local.name} context functions in two of three minutes"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 1
  evaluation_periods  = 3
  datapoints_to_alarm = 2
  treat_missing_data  = "notBreaching"

  metric_query {
    id          = "total"
    expression  = "SUM([${join(", ", [for ctx in keys(var.contexts) : "e_${ctx}"])}])"
    label       = "Errors, all context functions"
    return_data = true
  }

  dynamic "metric_query" {
    for_each = aws_lambda_function.context
    content {
      id = "e_${metric_query.key}"
      metric {
        namespace   = "AWS/Lambda"
        metric_name = "Errors"
        dimensions  = { FunctionName = metric_query.value.function_name }
        period      = 60
        stat        = "Sum"
      }
    }
  }
}

resource "aws_cloudwatch_composite_alarm" "page" {
  alarm_name        = local.alarm_page_name
  alarm_description = "Pages the Devin automation: ${local.alarm_5xx_name} or ${local.alarm_errors_name}"
  alarm_rule        = "ALARM(\"${aws_cloudwatch_metric_alarm.api_5xx_rate.alarm_name}\") OR ALARM(\"${aws_cloudwatch_metric_alarm.lambda_errors.alarm_name}\")"
}

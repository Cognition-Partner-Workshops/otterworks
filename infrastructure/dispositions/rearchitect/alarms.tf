resource "aws_cloudwatch_metric_alarm" "api_5xx_rate" {
  alarm_name          = local.alarm_5xx_name
  alarm_description   = "HTTP API 5xx response rate above ${var.alarm_5xx_rate_percent}%"
  comparison_operator = "GreaterThanThreshold"
  threshold           = var.alarm_5xx_rate_percent
  evaluation_periods  = 3
  datapoints_to_alarm = 2
  treat_missing_data  = "notBreaching"
  tags                = local.tags

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
  alarm_description   = "Invocation errors across the ${var.service_name} context functions"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 1
  evaluation_periods  = 3
  datapoints_to_alarm = 2
  treat_missing_data  = "notBreaching"
  tags                = local.tags

  metric_query {
    id          = "total"
    expression  = "SUM([${join(", ", [for context in keys(var.contexts) : "e_${replace(context, "-", "_")}"])}])"
    label       = "Errors, all context functions"
    return_data = true
  }

  dynamic "metric_query" {
    for_each = aws_lambda_function.context
    content {
      id = "e_${replace(metric_query.key, "-", "_")}"
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
  alarm_description = "Pages the automation on API 5xx or Lambda errors"
  alarm_rule        = "ALARM(\"${aws_cloudwatch_metric_alarm.api_5xx_rate.alarm_name}\") OR ALARM(\"${aws_cloudwatch_metric_alarm.lambda_errors.alarm_name}\")"
  tags              = local.tags
}

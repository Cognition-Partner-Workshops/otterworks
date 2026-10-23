resource "aws_cloudwatch_event_connection" "devin_webhook" {
  count              = local.page_enabled ? 1 : 0
  name               = "${local.name}-devin-webhook"
  description        = "Automation webhook for ${var.service_name} run ${local.name}"
  authorization_type = "API_KEY"

  auth_parameters {
    api_key {
      key   = "X-Webhook-Secret"
      value = var.devin_webhook_secret
    }
  }
}

resource "aws_cloudwatch_event_api_destination" "devin_webhook" {
  count                            = local.page_enabled ? 1 : 0
  name                             = "${local.name}-devin-webhook"
  description                      = "Automation webhook for ${var.service_name} run ${local.name}"
  invocation_endpoint              = var.devin_webhook_url
  http_method                      = "POST"
  invocation_rate_limit_per_second = 1
  connection_arn                   = aws_cloudwatch_event_connection.devin_webhook[0].arn
}

resource "aws_iam_role" "eventbridge_invoke" {
  count = local.page_enabled ? 1 : 0
  name  = "${local.name}-eventbridge-invoke"
  tags  = local.tags

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "events.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = { StringEquals = { "aws:SourceAccount" = local.account } }
    }]
  })
}

resource "aws_iam_role_policy" "eventbridge_invoke" {
  count = local.page_enabled ? 1 : 0
  name  = "${local.name}-eventbridge-invoke"
  role  = aws_iam_role.eventbridge_invoke[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "events:InvokeApiDestination"
      Resource = aws_cloudwatch_event_api_destination.devin_webhook[0].arn
    }]
  })
}

resource "aws_sqs_queue" "page_dlq" {
  name                      = "${local.name}-page-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
  tags                      = local.tags
}

resource "aws_sqs_queue_policy" "page_dlq" {
  queue_url = aws_sqs_queue.page_dlq.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "events.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.page_dlq.arn
      Condition = { ArnEquals = { "aws:SourceArn" = aws_cloudwatch_event_rule.page.arn } }
    }]
  })
}

resource "aws_cloudwatch_event_rule" "page" {
  name           = local.page_rule_name
  description    = "Posts ${local.alarm_page_name} ALARM transitions to the automation webhook"
  event_bus_name = "default"
  state          = local.page_enabled ? "ENABLED" : "DISABLED"
  tags           = local.tags

  event_pattern = jsonencode({
    source        = ["aws.cloudwatch"]
    "detail-type" = ["CloudWatch Alarm State Change"]
    detail = {
      alarmName = [aws_cloudwatch_composite_alarm.page.alarm_name]
      state     = { value = ["ALARM"] }
    }
  })
}

resource "aws_cloudwatch_event_target" "devin_webhook" {
  count          = local.page_enabled ? 1 : 0
  rule           = aws_cloudwatch_event_rule.page.name
  event_bus_name = "default"
  target_id      = "automation-webhook"
  arn            = aws_cloudwatch_event_api_destination.devin_webhook[0].arn
  role_arn       = aws_iam_role.eventbridge_invoke[0].arn

  input_transformer {
    input_paths = {
      alarm   = "$.detail.alarmName"
      state   = "$.detail.state.value"
      reason  = "$.detail.state.reason"
      time    = "$.time"
      region  = "$.region"
      account = "$.account"
      detail  = "$.detail"
    }

    input_template = <<-JSON
      {
        "source": "cloudwatch-alarm",
        "alarm": "<alarm>",
        "state": "<state>",
        "reason": "<reason>",
        "time": "<time>",
        "region": "<region>",
        "account": "<account>",
        "tenant": "${var.service_name}",
        "run_token": "${var.run_token}",
        "api_id": "${aws_apigatewayv2_api.this.id}",
        "codedeploy_app": "${aws_codedeploy_app.this.name}",
        "detail": <detail>
      }
    JSON
  }

  retry_policy {
    maximum_retry_attempts       = 2
    maximum_event_age_in_seconds = 300
  }

  dead_letter_config {
    arn = aws_sqs_queue.page_dlq.arn
  }
}

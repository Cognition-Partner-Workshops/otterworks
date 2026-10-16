# Page to a Devin automation, copied from infrastructure/terraform/cloud-worker/eventbridge.tf:
# an API_KEY connection sending X-Webhook-Secret, an API destination, an invoke role and a rule on
# the default bus for the composite alarm going to ALARM. With either webhook variable empty the
# connection and destination carry cloud-worker's placeholder values and the rule is DISABLED.
locals {
  page_enabled   = var.devin_webhook_url != "" && nonsensitive(var.devin_webhook_secret != "")
  webhook_url    = local.page_enabled ? var.devin_webhook_url : "https://example.invalid/webhook"
  webhook_secret = local.page_enabled ? var.devin_webhook_secret : "replace-me"
  page_rule_name = "${local.name}-page-devin"
}

resource "aws_cloudwatch_event_connection" "devin_webhook" {
  name               = "${local.name}-devin-webhook"
  description        = "Devin automation webhook for legacy-portal-serverless ${local.name}"
  authorization_type = "API_KEY"

  auth_parameters {
    api_key {
      key   = "X-Webhook-Secret"
      value = local.webhook_secret
    }
  }
}

resource "aws_cloudwatch_event_api_destination" "devin_webhook" {
  name                             = "${local.name}-devin-webhook"
  description                      = "Devin automation webhook for legacy-portal-serverless ${local.name}"
  invocation_endpoint              = local.webhook_url
  http_method                      = "POST"
  invocation_rate_limit_per_second = 1
  connection_arn                   = aws_cloudwatch_event_connection.devin_webhook.arn
}

resource "aws_iam_role" "eventbridge_invoke" {
  name = "${local.name}-eventbridge-invoke"

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
  name = "${local.name}-eventbridge-invoke"
  role = aws_iam_role.eventbridge_invoke.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "events:InvokeApiDestination"
      Resource = aws_cloudwatch_event_api_destination.devin_webhook.arn
    }]
  })
}

resource "aws_sqs_queue" "page_dlq" {
  name                      = "${local.name}-page-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
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
  description    = "Posts ${local.alarm_page_name} ALARM transitions to the Devin webhook"
  event_bus_name = "default"
  state          = local.page_enabled ? "ENABLED" : "DISABLED"

  event_pattern = jsonencode({
    source      = ["aws.cloudwatch"]
    detail-type = ["CloudWatch Alarm State Change"]
    detail = {
      alarmName = [aws_cloudwatch_composite_alarm.page.alarm_name]
      state     = { value = ["ALARM"] }
    }
  })
}

resource "aws_cloudwatch_event_target" "devin_webhook" {
  rule           = aws_cloudwatch_event_rule.page.name
  event_bus_name = "default"
  target_id      = "devin-webhook"
  arn            = aws_cloudwatch_event_api_destination.devin_webhook.arn
  role_arn       = aws_iam_role.eventbridge_invoke.arn

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
        "tenant": "legacy-portal-serverless",
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

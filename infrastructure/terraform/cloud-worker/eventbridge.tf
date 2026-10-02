resource "aws_cloudwatch_event_connection" "devin_webhook" {
  name               = "otterworks-cw-devin-webhook"
  description        = "Devin automation webhook for the aws-cloud-worker demo"
  authorization_type = "API_KEY"

  auth_parameters {
    api_key {
      key   = "X-Webhook-Secret"
      value = var.devin_webhook_secret
    }
  }
}

resource "aws_cloudwatch_event_api_destination" "devin_webhook" {
  name                             = "otterworks-cw-devin-webhook"
  description                      = "Devin automation webhook for the aws-cloud-worker demo"
  invocation_endpoint              = var.devin_webhook_url
  http_method                      = "POST"
  invocation_rate_limit_per_second = 1
  connection_arn                   = aws_cloudwatch_event_connection.devin_webhook.arn
}

resource "aws_iam_role" "eventbridge_invoke" {
  name = "otterworks-cw-eventbridge-invoke"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "events.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = { StringEquals = { "aws:SourceAccount" = local.account_id } }
    }]
  })
}

resource "aws_iam_role_policy" "eventbridge_invoke" {
  name = "otterworks-cw-eventbridge-invoke"
  role = aws_iam_role.eventbridge_invoke.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "events:InvokeApiDestination"
      Resource = "${aws_cloudwatch_event_api_destination.devin_webhook.arn}*"
    }]
  })
}

resource "aws_cloudwatch_event_rule" "dlq_alarm" {
  name           = local.rule_name
  description    = "Posts ${local.alarm_name} ALARM transitions to the Devin webhook"
  event_bus_name = "default"

  event_pattern = jsonencode({
    source      = ["aws.cloudwatch"]
    detail-type = ["CloudWatch Alarm State Change"]
    detail = {
      alarmName = [aws_cloudwatch_metric_alarm.dlq_depth.alarm_name]
      state     = { value = ["ALARM"] }
    }
  })
}

resource "aws_cloudwatch_event_target" "devin_webhook" {
  rule           = aws_cloudwatch_event_rule.dlq_alarm.name
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
        "tenant": "cloud-worker",
        "namespace": "${var.tenant_namespace}",
        "branch": "demo-cloud-worker",
        "service": "notification-service",
        "queue": "${local.queue_name}",
        "dlq": "${local.dlq_name}",
        "dashboard": "${local.dashboard_name}"
      }
    JSON
  }

  retry_policy {
    maximum_retry_attempts       = 2
    maximum_event_age_in_seconds = 300
  }

  dead_letter_config {
    arn = aws_sqs_queue.events_dlq.arn
  }
}

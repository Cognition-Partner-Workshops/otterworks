resource "aws_cloudwatch_event_bus" "this" {
  name = "otterworks-${local.name}"
}

# Event pattern: exact match on source and detail-type, the shape PutEvents entries carry.
resource "aws_cloudwatch_event_rule" "announcement_created" {
  name           = "${local.name}-announcement-created"
  description    = "AnnouncementCreated from the announcements Lambda, for the notification side"
  event_bus_name = aws_cloudwatch_event_bus.this.name
  event_pattern = jsonencode({
    source        = [var.event_source]
    "detail-type" = ["AnnouncementCreated"]
  })
}

# Queue the notification service consumes instead of polling the announcements table.
resource "aws_sqs_queue" "notifications_dlq" {
  name                      = "${local.name}-announcement-created-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "notifications" {
  name                       = "${local.name}-announcement-created"
  message_retention_seconds  = 345600
  visibility_timeout_seconds = 60
  sqs_managed_sse_enabled    = true
}

data "aws_iam_policy_document" "notifications_queue" {
  statement {
    sid       = "AllowRule"
    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.notifications.arn]
    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }
    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [aws_cloudwatch_event_rule.announcement_created.arn]
    }
  }
}

resource "aws_sqs_queue_policy" "notifications" {
  queue_url = aws_sqs_queue.notifications.id
  policy    = data.aws_iam_policy_document.notifications_queue.json
}

data "aws_iam_policy_document" "notifications_dlq" {
  statement {
    sid       = "AllowRuleDeadLetters"
    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.notifications_dlq.arn]
    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }
    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [aws_cloudwatch_event_rule.announcement_created.arn]
    }
  }
}

resource "aws_sqs_queue_policy" "notifications_dlq" {
  queue_url = aws_sqs_queue.notifications_dlq.id
  policy    = data.aws_iam_policy_document.notifications_dlq.json
}

resource "aws_cloudwatch_event_target" "notifications" {
  rule           = aws_cloudwatch_event_rule.announcement_created.name
  event_bus_name = aws_cloudwatch_event_bus.this.name
  target_id      = "notifications-queue"
  arn            = aws_sqs_queue.notifications.arn

  dead_letter_config {
    arn = aws_sqs_queue.notifications_dlq.arn
  }

  depends_on = [aws_sqs_queue_policy.notifications]
}

# Audit copy of every matched event. EventBridge needs a CloudWatch Logs resource policy
# that lets events.amazonaws.com and delivery.logs.amazonaws.com write to /aws/events/*.
resource "aws_cloudwatch_log_group" "events" { # nosemgrep: terraform.aws.security.aws-cloudwatch-log-group-unencrypted.aws-cloudwatch-log-group-unencrypted
  name              = "/aws/events/${local.name}-announcement-created"
  retention_in_days = var.log_retention_days
}

data "aws_iam_policy_document" "events_logs" {
  statement {
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.events.arn}:*"]
    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com", "delivery.logs.amazonaws.com"]
    }
    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [aws_cloudwatch_event_rule.announcement_created.arn]
    }
  }
}

resource "aws_cloudwatch_log_resource_policy" "events" {
  policy_name     = "${local.name}-announcement-created"
  policy_document = data.aws_iam_policy_document.events_logs.json
}

resource "aws_cloudwatch_event_target" "audit_log" {
  rule           = aws_cloudwatch_event_rule.announcement_created.name
  event_bus_name = aws_cloudwatch_event_bus.this.name
  target_id      = "audit-log"
  arn            = aws_cloudwatch_log_group.events.arn

  depends_on = [aws_cloudwatch_log_resource_policy.events]
}

# announcement.published events, only when var.module is announcements.
resource "aws_cloudwatch_event_bus" "this" {
  count = local.events ? 1 : 0

  name = "otterworks-${local.name}"
}

# Event pattern: exact match on source and detail-type, the shape PutEvents entries carry.
resource "aws_cloudwatch_event_rule" "announcement_published" {
  count = local.events ? 1 : 0

  name           = "${local.name}-announcement-published"
  description    = "announcement.published from the announcements Lambda, for the notification side"
  event_bus_name = aws_cloudwatch_event_bus.this[0].name
  event_pattern = jsonencode({
    source        = [var.event_source]
    "detail-type" = ["announcement.published"]
  })
}

# Queue the notification service consumes instead of polling the announcements table.
resource "aws_sqs_queue" "notifications_dlq" {
  count = local.events ? 1 : 0

  name                      = "${local.name}-announcement-published-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "notifications" {
  count = local.events ? 1 : 0

  name                       = "${local.name}-announcement-published"
  message_retention_seconds  = 345600
  visibility_timeout_seconds = 60
  sqs_managed_sse_enabled    = true
}

data "aws_iam_policy_document" "notifications_queue" {
  count = local.events ? 1 : 0

  statement {
    sid       = "AllowRule"
    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.notifications[0].arn]
    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }
    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [aws_cloudwatch_event_rule.announcement_published[0].arn]
    }
  }
}

resource "aws_sqs_queue_policy" "notifications" {
  count = local.events ? 1 : 0

  queue_url = aws_sqs_queue.notifications[0].id
  policy    = data.aws_iam_policy_document.notifications_queue[0].json
}

data "aws_iam_policy_document" "notifications_dlq" {
  count = local.events ? 1 : 0

  statement {
    sid       = "AllowRuleDeadLetters"
    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.notifications_dlq[0].arn]
    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }
    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [aws_cloudwatch_event_rule.announcement_published[0].arn]
    }
  }
}

resource "aws_sqs_queue_policy" "notifications_dlq" {
  count = local.events ? 1 : 0

  queue_url = aws_sqs_queue.notifications_dlq[0].id
  policy    = data.aws_iam_policy_document.notifications_dlq[0].json
}

resource "aws_cloudwatch_event_target" "notifications" {
  count = local.events ? 1 : 0

  rule           = aws_cloudwatch_event_rule.announcement_published[0].name
  event_bus_name = aws_cloudwatch_event_bus.this[0].name
  target_id      = "notifications-queue"
  arn            = aws_sqs_queue.notifications[0].arn

  dead_letter_config {
    arn = aws_sqs_queue.notifications_dlq[0].arn
  }

  depends_on = [aws_sqs_queue_policy.notifications]
}

# Audit copy of every matched event. EventBridge needs a CloudWatch Logs resource policy
# that lets events.amazonaws.com and delivery.logs.amazonaws.com write to /aws/events/*.
resource "aws_cloudwatch_log_group" "events" { # nosemgrep: terraform.aws.security.aws-cloudwatch-log-group-unencrypted.aws-cloudwatch-log-group-unencrypted
  count = local.events ? 1 : 0

  name              = "/aws/events/${local.name}-announcement-published"
  retention_in_days = var.log_retention_days
}

data "aws_iam_policy_document" "events_logs" {
  count = local.events ? 1 : 0

  statement {
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.events[0].arn}:*"]
    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com", "delivery.logs.amazonaws.com"]
    }
    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [aws_cloudwatch_event_rule.announcement_published[0].arn]
    }
  }
}

resource "aws_cloudwatch_log_resource_policy" "events" {
  count = local.events ? 1 : 0

  policy_name     = "${local.name}-announcement-published"
  policy_document = data.aws_iam_policy_document.events_logs[0].json
}

resource "aws_cloudwatch_event_target" "audit_log" {
  count = local.events ? 1 : 0

  rule           = aws_cloudwatch_event_rule.announcement_published[0].name
  event_bus_name = aws_cloudwatch_event_bus.this[0].name
  target_id      = "audit-log"
  arn            = aws_cloudwatch_log_group.events[0].arn

  depends_on = [aws_cloudwatch_log_resource_policy.events]
}

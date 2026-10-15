# ------------------------------------------------------------------------------
# OtterWorks Messaging Module
# SQS queues and SNS topics for event-driven architecture
# ------------------------------------------------------------------------------

locals {
  common_tags = {
    Module  = "messaging"
    Project = var.project
  }
}

# --- SNS Topic: System Events ---

resource "aws_sns_topic" "events" {
  name = "${var.project}-events-${var.environment}"

  tags = merge(local.common_tags, {
    Service = "shared-events"
  })
}

# --- SQS: Notifications Queue ---

resource "aws_sqs_queue" "notifications" {
  name                       = "${var.project}-notifications-${var.environment}"
  visibility_timeout_seconds = 60
  message_retention_seconds  = 86400
  receive_wait_time_seconds  = 20

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.notifications_dlq.arn
    maxReceiveCount     = 3
  })

  tags = merge(local.common_tags, {
    Service = "notification-service"
  })
}

resource "aws_sqs_queue" "notifications_dlq" {
  name                      = "${var.project}-notifications-dlq-${var.environment}"
  message_retention_seconds = 1209600

  tags = merge(local.common_tags, {
    Service = "notification-service"
  })
}

# --- SQS: Analytics Events Queue ---

resource "aws_sqs_queue" "analytics_events" {
  name                       = "${var.project}-analytics-events-${var.environment}"
  visibility_timeout_seconds = 120
  message_retention_seconds  = 259200
  receive_wait_time_seconds  = 20

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.analytics_events_dlq.arn
    maxReceiveCount     = var.max_receive_count
  })

  tags = merge(local.common_tags, {
    Service = "analytics-service"
  })
}

# DLQ retention stays above the source queue's: SQS keeps the original enqueue
# timestamp when it moves a message, so a shorter DLQ would expire it early.
resource "aws_sqs_queue" "analytics_events_dlq" {
  name                      = "${var.project}-analytics-events-dlq-${var.environment}"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true

  tags = merge(local.common_tags, {
    Service = "analytics-service"
  })
}

# --- SQS: Search Indexing Queue ---

resource "aws_sqs_queue" "search_indexing" {
  name                       = "${var.project}-search-indexing-${var.environment}"
  visibility_timeout_seconds = 60
  message_retention_seconds  = 86400
  receive_wait_time_seconds  = 20

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.search_indexing_dlq.arn
    maxReceiveCount     = var.max_receive_count
  })

  tags = merge(local.common_tags, {
    Service = "search-service"
  })
}

resource "aws_sqs_queue" "search_indexing_dlq" {
  name                      = "${var.project}-search-indexing-dlq-${var.environment}"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true

  tags = merge(local.common_tags, {
    Service = "search-service"
  })
}

# --- SNS -> SQS Subscriptions ---

resource "aws_sns_topic_subscription" "notifications" {
  topic_arn = aws_sns_topic.events.arn
  protocol  = "sqs"
  endpoint  = aws_sqs_queue.notifications.arn

  filter_policy = jsonencode({
    eventType = ["file_shared", "comment_added", "document_edited", "user_mentioned"]
  })
}

resource "aws_sns_topic_subscription" "analytics" {
  topic_arn = aws_sns_topic.events.arn
  protocol  = "sqs"
  endpoint  = aws_sqs_queue.analytics_events.arn
}

resource "aws_sns_topic_subscription" "search_indexing" {
  topic_arn = aws_sns_topic.events.arn
  protocol  = "sqs"
  endpoint  = aws_sqs_queue.search_indexing.arn

  filter_policy = jsonencode({
    eventType = ["document_created", "document_updated", "document_deleted", "file_uploaded", "file_deleted"]
  })
}

# --- SQS Policies ---

resource "aws_sqs_queue_policy" "notifications" {
  queue_url = aws_sqs_queue.notifications.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "sns.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.notifications.arn
      Condition = { ArnEquals = { "aws:SourceArn" = aws_sns_topic.events.arn } }
    }]
  })
}

resource "aws_sqs_queue_policy" "analytics_events" {
  queue_url = aws_sqs_queue.analytics_events.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "sns.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.analytics_events.arn
      Condition = { ArnEquals = { "aws:SourceArn" = aws_sns_topic.events.arn } }
    }]
  })
}

resource "aws_sqs_queue_policy" "search_indexing" {
  queue_url = aws_sqs_queue.search_indexing.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "sns.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.search_indexing.arn
      Condition = { ArnEquals = { "aws:SourceArn" = aws_sns_topic.events.arn } }
    }]
  })
}

# --- Dead-letter queue guardrails ---

locals {
  dead_letter_queues = {
    notifications = {
      source = aws_sqs_queue.notifications
      dlq    = aws_sqs_queue.notifications_dlq
    }
    analytics_events = {
      source = aws_sqs_queue.analytics_events
      dlq    = aws_sqs_queue.analytics_events_dlq
    }
    search_indexing = {
      source = aws_sqs_queue.search_indexing
      dlq    = aws_sqs_queue.search_indexing_dlq
    }
  }
}

# Only the queue each DLQ was built for may dead-letter into it, so a
# misconfigured consumer elsewhere cannot bury its failures in ours.
resource "aws_sqs_queue_redrive_allow_policy" "dlq" {
  for_each = local.dead_letter_queues

  queue_url = each.value.dlq.id
  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [each.value.source.arn]
  })
}

resource "aws_cloudwatch_metric_alarm" "dlq_depth" {
  for_each = local.dead_letter_queues

  alarm_name          = "${each.value.dlq.name}-depth"
  alarm_description   = "Messages in ${each.value.dlq.name}: ${each.value.source.name} exhausted its retries. Inspect, fix the consumer, then redrive with StartMessageMoveTask."
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  dimensions          = { QueueName = each.value.dlq.name }
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_actions
  ok_actions          = var.alarm_actions

  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "oldest_message_age" {
  for_each = local.dead_letter_queues

  alarm_name          = "${each.value.source.name}-oldest-message-age"
  alarm_description   = "Oldest message in ${each.value.source.name} is older than ${var.oldest_message_age_alarm_seconds}s: its consumer is stalled or failing."
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateAgeOfOldestMessage"
  dimensions          = { QueueName = each.value.source.name }
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 3
  threshold           = var.oldest_message_age_alarm_seconds
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_actions
  ok_actions          = var.alarm_actions

  tags = local.common_tags
}

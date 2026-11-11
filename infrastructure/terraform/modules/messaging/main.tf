# ------------------------------------------------------------------------------
# OtterWorks Messaging Module
# Domain-event bus (EventBridge) and per-consumer SQS queues. The legacy SNS
# topic stays in place while publishers dual-run (EVENT_TRANSPORT=dual).
# ------------------------------------------------------------------------------

locals {
  common_tags = {
    Module  = "messaging"
    Project = var.project
  }

  # Every domain event published by an OtterWorks service carries source
  # "otterworks.<service>" and detail-type = the event type.
  event_source_prefix = "otterworks."

  # Event types each consumer acts on. Notifications match the intent of the
  # SNS filter policy below; search matches the action map in
  # services/search-service/app/services/sqs_consumer.py.
  notification_event_types = ["file_shared", "comment_added", "document_edited", "user_mentioned"]
  search_event_types = [
    "document_created", "document_updated", "document_deleted",
    "file_created", "file_uploaded", "file_updated", "file_deleted", "file_trashed", "file_restored",
  ]

  # Consumer queue (and its DLQ) -> EventBridge rule pattern. A null detail-type list means
  # the consumer receives every OtterWorks domain event.
  consumers = {
    notifications = {
      queue_arn   = aws_sqs_queue.notifications.arn
      queue_url   = aws_sqs_queue.notifications.id
      dlq_arn     = aws_sqs_queue.notifications_dlq.arn
      dlq_url     = aws_sqs_queue.notifications_dlq.id
      event_types = local.notification_event_types
    }
    search_indexing = {
      queue_arn   = aws_sqs_queue.search_indexing.arn
      queue_url   = aws_sqs_queue.search_indexing.id
      dlq_arn     = aws_sqs_queue.search_indexing_dlq.arn
      dlq_url     = aws_sqs_queue.search_indexing_dlq.id
      event_types = local.search_event_types
    }
    analytics_events = {
      queue_arn   = aws_sqs_queue.analytics_events.arn
      queue_url   = aws_sqs_queue.analytics_events.id
      dlq_arn     = aws_sqs_queue.analytics_events_dlq.arn
      dlq_url     = aws_sqs_queue.analytics_events_dlq.id
      event_types = null
    }
    audit_events = {
      queue_arn   = aws_sqs_queue.audit_events.arn
      queue_url   = aws_sqs_queue.audit_events.id
      dlq_arn     = aws_sqs_queue.audit_events_dlq.arn
      dlq_url     = aws_sqs_queue.audit_events_dlq.id
      event_types = null
    }
  }
}

# --- EventBridge: Domain Event Bus ---

resource "aws_cloudwatch_event_bus" "events" {
  name = "${var.project}-events-${var.environment}"

  tags = merge(local.common_tags, {
    Service = "shared-events"
  })
}

resource "aws_cloudwatch_event_archive" "events" {
  name             = "${var.project}-events-${var.environment}"
  description      = "Replayable archive of OtterWorks domain events"
  event_source_arn = aws_cloudwatch_event_bus.events.arn
  retention_days   = var.event_archive_retention_days

  event_pattern = jsonencode({
    source = [{ prefix = local.event_source_prefix }]
  })
}

resource "aws_cloudwatch_event_rule" "consumer" {
  for_each = local.consumers

  name           = "${var.project}-${replace(each.key, "_", "-")}-${var.environment}"
  description    = "Route OtterWorks domain events to the ${each.key} queue"
  event_bus_name = aws_cloudwatch_event_bus.events.name

  event_pattern = jsonencode(merge(
    { source = [{ prefix = local.event_source_prefix }] },
    each.value.event_types == null ? {} : { "detail-type" = each.value.event_types },
  ))

  tags = local.common_tags
}

resource "aws_cloudwatch_event_target" "consumer" {
  for_each = local.consumers

  rule           = aws_cloudwatch_event_rule.consumer[each.key].name
  event_bus_name = aws_cloudwatch_event_bus.events.name
  target_id      = "${replace(each.key, "_", "-")}-queue"
  arn            = each.value.queue_arn

  retry_policy {
    maximum_event_age_in_seconds = 86400
    maximum_retry_attempts       = 185
  }

  # Events EventBridge cannot deliver after retries land in the consumer's own DLQ.
  dead_letter_config {
    arn = each.value.dlq_arn
  }
}

# --- SNS Topic: System Events (legacy, kept for dual-run) ---

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
  sqs_managed_sse_enabled    = true

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
  sqs_managed_sse_enabled   = true

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
  sqs_managed_sse_enabled    = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.analytics_events_dlq.arn
    maxReceiveCount     = 3
  })

  tags = merge(local.common_tags, {
    Service = "analytics-service"
  })
}

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
  sqs_managed_sse_enabled    = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.search_indexing_dlq.arn
    maxReceiveCount     = 3
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

# --- SQS: Audit Events Queue ---

resource "aws_sqs_queue" "audit_events" {
  name                       = "${var.project}-audit-events-${var.environment}"
  visibility_timeout_seconds = 60
  message_retention_seconds  = 345600
  receive_wait_time_seconds  = 20
  sqs_managed_sse_enabled    = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.audit_events_dlq.arn
    maxReceiveCount     = 3
  })

  tags = merge(local.common_tags, {
    Service = "audit-service"
  })
}

resource "aws_sqs_queue" "audit_events_dlq" {
  name                      = "${var.project}-audit-events-dlq-${var.environment}"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true

  tags = merge(local.common_tags, {
    Service = "audit-service"
  })
}

# --- SNS -> SQS Subscriptions (legacy, kept for dual-run) ---

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

# --- SQS Policies: the SNS topic and the consumer's own EventBridge rule ---

resource "aws_sqs_queue_policy" "consumer" {
  for_each = local.consumers

  queue_url = each.value.queue_url
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowSnsTopic"
        Effect    = "Allow"
        Principal = { Service = "sns.amazonaws.com" }
        Action    = "sqs:SendMessage"
        Resource  = each.value.queue_arn
        Condition = { ArnEquals = { "aws:SourceArn" = aws_sns_topic.events.arn } }
      },
      {
        Sid       = "AllowEventBridgeRule"
        Effect    = "Allow"
        Principal = { Service = "events.amazonaws.com" }
        Action    = "sqs:SendMessage"
        Resource  = each.value.queue_arn
        Condition = { ArnEquals = { "aws:SourceArn" = aws_cloudwatch_event_rule.consumer[each.key].arn } }
      },
    ]
  })
}

resource "aws_sqs_queue_policy" "consumer_dlq" {
  for_each = local.consumers

  queue_url = each.value.dlq_url
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowEventBridgeRuleDeadLetters"
      Effect    = "Allow"
      Principal = { Service = "events.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = each.value.dlq_arn
      Condition = { ArnEquals = { "aws:SourceArn" = aws_cloudwatch_event_rule.consumer[each.key].arn } }
    }]
  })
}

moved {
  from = aws_sqs_queue_policy.notifications
  to   = aws_sqs_queue_policy.consumer["notifications"]
}

moved {
  from = aws_sqs_queue_policy.analytics_events
  to   = aws_sqs_queue_policy.consumer["analytics_events"]
}

moved {
  from = aws_sqs_queue_policy.search_indexing
  to   = aws_sqs_queue_policy.consumer["search_indexing"]
}

# --- Alarms: anything landing in a DLQ needs a human ---

resource "aws_cloudwatch_metric_alarm" "dlq_depth" {
  for_each = {
    notifications    = aws_sqs_queue.notifications_dlq.name
    analytics_events = aws_sqs_queue.analytics_events_dlq.name
    search_indexing  = aws_sqs_queue.search_indexing_dlq.name
    audit_events     = aws_sqs_queue.audit_events_dlq.name
  }

  alarm_name          = "${each.value}-not-empty"
  alarm_description   = "Messages are waiting in ${each.value}; inspect and redrive"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  dimensions          = { QueueName = each.value }
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_actions
  ok_actions          = var.alarm_actions

  tags = local.common_tags
}

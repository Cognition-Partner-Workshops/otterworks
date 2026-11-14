# Offline plan-time checks for the messaging module's failure paths.
# Run: cd infrastructure/terraform/modules/messaging && terraform init -backend=false && terraform test

mock_provider "aws" {}

# Distinct, valid ARNs so wiring assertions cannot pass by coincidence.
override_resource {
  target = aws_sns_topic.events
  values = {
    arn = "arn:aws:sns:us-east-1:111111111111:otterworks-events-dev"
  }
}

override_resource {
  target = aws_sqs_queue.notifications
  values = {
    arn = "arn:aws:sqs:us-east-1:111111111111:otterworks-notifications-dev"
    id  = "https://sqs.us-east-1.amazonaws.com/111111111111/otterworks-notifications-dev"
    url = "https://sqs.us-east-1.amazonaws.com/111111111111/otterworks-notifications-dev"
  }
}

override_resource {
  target = aws_sqs_queue.notifications_dlq
  values = {
    arn = "arn:aws:sqs:us-east-1:111111111111:otterworks-notifications-dlq-dev"
    id  = "https://sqs.us-east-1.amazonaws.com/111111111111/otterworks-notifications-dlq-dev"
    url = "https://sqs.us-east-1.amazonaws.com/111111111111/otterworks-notifications-dlq-dev"
  }
}

override_resource {
  target = aws_sqs_queue.analytics_events
  values = {
    arn = "arn:aws:sqs:us-east-1:111111111111:otterworks-analytics-events-dev"
    id  = "https://sqs.us-east-1.amazonaws.com/111111111111/otterworks-analytics-events-dev"
    url = "https://sqs.us-east-1.amazonaws.com/111111111111/otterworks-analytics-events-dev"
  }
}

override_resource {
  target = aws_sqs_queue.analytics_events_dlq
  values = {
    arn = "arn:aws:sqs:us-east-1:111111111111:otterworks-analytics-events-dlq-dev"
    id  = "https://sqs.us-east-1.amazonaws.com/111111111111/otterworks-analytics-events-dlq-dev"
    url = "https://sqs.us-east-1.amazonaws.com/111111111111/otterworks-analytics-events-dlq-dev"
  }
}

override_resource {
  target = aws_sqs_queue.search_indexing
  values = {
    arn = "arn:aws:sqs:us-east-1:111111111111:otterworks-search-indexing-dev"
    id  = "https://sqs.us-east-1.amazonaws.com/111111111111/otterworks-search-indexing-dev"
    url = "https://sqs.us-east-1.amazonaws.com/111111111111/otterworks-search-indexing-dev"
  }
}

override_resource {
  target = aws_sqs_queue.search_indexing_dlq
  values = {
    arn = "arn:aws:sqs:us-east-1:111111111111:otterworks-search-indexing-dlq-dev"
    id  = "https://sqs.us-east-1.amazonaws.com/111111111111/otterworks-search-indexing-dlq-dev"
    url = "https://sqs.us-east-1.amazonaws.com/111111111111/otterworks-search-indexing-dlq-dev"
  }
}

variables {
  project     = "otterworks"
  environment = "dev"
}

run "every_consumer_queue_dead_letters" {
  command = apply

  assert {
    condition     = jsondecode(aws_sqs_queue.analytics_events.redrive_policy).deadLetterTargetArn == aws_sqs_queue.analytics_events_dlq.arn
    error_message = "analytics_events must dead-letter into analytics_events_dlq."
  }

  assert {
    condition     = jsondecode(aws_sqs_queue.search_indexing.redrive_policy).deadLetterTargetArn == aws_sqs_queue.search_indexing_dlq.arn
    error_message = "search_indexing must dead-letter into search_indexing_dlq."
  }

  assert {
    condition     = jsondecode(aws_sqs_queue.analytics_events.redrive_policy).maxReceiveCount == 5 && jsondecode(aws_sqs_queue.search_indexing.redrive_policy).maxReceiveCount == 5
    error_message = "New redrive policies default to maxReceiveCount 5."
  }

  assert {
    condition     = jsondecode(aws_sqs_queue.notifications.redrive_policy).maxReceiveCount == 3
    error_message = "The notifications queue keeps its existing maxReceiveCount of 3."
  }
}

run "dlq_retention_outlives_source" {
  command = plan

  assert {
    condition     = aws_sqs_queue.analytics_events_dlq.message_retention_seconds > aws_sqs_queue.analytics_events.message_retention_seconds
    error_message = "analytics DLQ retention must exceed the source queue's (enqueue timestamp is preserved)."
  }

  assert {
    condition     = aws_sqs_queue.search_indexing_dlq.message_retention_seconds > aws_sqs_queue.search_indexing.message_retention_seconds
    error_message = "search-indexing DLQ retention must exceed the source queue's."
  }

  assert {
    condition     = aws_sqs_queue.notifications_dlq.message_retention_seconds > aws_sqs_queue.notifications.message_retention_seconds
    error_message = "notifications DLQ retention must exceed the source queue's."
  }

  assert {
    condition     = aws_sqs_queue.analytics_events_dlq.name == "otterworks-analytics-events-dlq-dev" && aws_sqs_queue.search_indexing_dlq.name == "otterworks-search-indexing-dlq-dev"
    error_message = "DLQ names follow <project>-<queue>-dlq-<environment>."
  }
}

run "redrive_allow_is_scoped_to_own_source" {
  command = apply

  assert {
    condition = alltrue([
      for k, p in aws_sqs_queue_redrive_allow_policy.dlq :
      jsondecode(p.redrive_allow_policy).redrivePermission == "byQueue" && length(jsondecode(p.redrive_allow_policy).sourceQueueArns) == 1
    ])
    error_message = "Each DLQ admits exactly its own source queue."
  }

  assert {
    condition     = jsondecode(aws_sqs_queue_redrive_allow_policy.dlq["analytics_events"].redrive_allow_policy).sourceQueueArns[0] == aws_sqs_queue.analytics_events.arn
    error_message = "analytics DLQ must admit only analytics_events."
  }

  assert {
    condition     = aws_sqs_queue_redrive_allow_policy.dlq["analytics_events"].queue_url == aws_sqs_queue.analytics_events_dlq.url
    error_message = "The analytics allow policy is attached to the analytics DLQ."
  }

  assert {
    condition     = length(aws_sqs_queue_redrive_allow_policy.dlq) == 3
    error_message = "All three DLQs carry a redrive allow policy."
  }
}

run "alarms_are_silent_by_default" {
  command = plan

  assert {
    condition     = length(aws_cloudwatch_metric_alarm.dlq_depth) == 3 && length(aws_cloudwatch_metric_alarm.oldest_message_age) == 3
    error_message = "One DLQ depth and one backlog-age alarm per consumer queue."
  }

  assert {
    condition = alltrue([
      for a in values(aws_cloudwatch_metric_alarm.dlq_depth) :
      a.metric_name == "ApproximateNumberOfMessagesVisible" && a.threshold == 0 && a.comparison_operator == "GreaterThanThreshold" && a.treat_missing_data == "notBreaching" && length(a.alarm_actions) == 0
    ])
    error_message = "DLQ alarms fire on any visible message and page nobody unless alarm_actions is set."
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.dlq_depth["analytics_events"].dimensions.QueueName == "otterworks-analytics-events-dlq-dev"
    error_message = "The analytics DLQ alarm watches the analytics DLQ."
  }

  assert {
    condition = alltrue([
      for a in values(aws_cloudwatch_metric_alarm.oldest_message_age) :
      a.metric_name == "ApproximateAgeOfOldestMessage" && a.threshold == 3600 && length(a.alarm_actions) == 0
    ])
    error_message = "Backlog alarms watch ApproximateAgeOfOldestMessage at the default threshold."
  }
}

run "alarm_actions_and_receive_count_are_configurable" {
  command = plan

  variables {
    max_receive_count = 8
    alarm_actions     = ["arn:aws:sns:us-east-1:111111111111:ops"]
  }

  assert {
    condition     = jsondecode(aws_sqs_queue.analytics_events.redrive_policy).maxReceiveCount == 8
    error_message = "max_receive_count flows into the analytics redrive policy."
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.dlq_depth["search_indexing"].alarm_actions == toset(["arn:aws:sns:us-east-1:111111111111:ops"])
    error_message = "alarm_actions flows into the alarms."
  }
}

run "rejects_non_integer_receive_count" {
  command = plan

  variables {
    max_receive_count = 0
  }

  expect_failures = [var.max_receive_count]
}
